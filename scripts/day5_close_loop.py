"""Day5 文本闭环验收：按协议把一通电话从 INIT 走到 COMPLETED（C 维护）。

指南第 10 章 Day5 验收项："文本闭环走通到 COMPLETED"。
A 的麦克风和 B 的 Agent 还没接上时，由本脚本扮演"整条链路"，
把 8 种协议消息按真实顺序发进 /ws/control，验证落库侧能还原出一通完整电话。

用法（先起服务）：
    .venv/bin/python -m uvicorn server.main:app --port 8010
    .venv/bin/python scripts/day5_close_loop.py
    .venv/bin/python scripts/day5_close_loop.py ws://127.0.0.1:8010/ws/control S-20261114-probe-d5

会话号里带 probe，会被 eval/latency.py 识别为探针数据，不计入比赛验收。
"""
import asyncio
import json
import sqlite3
import sys
import time

try:
    import websockets
except ImportError:
    sys.exit("缺 websockets：.venv/bin/pip install websockets")

URL = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8010/ws/control"
SID = sys.argv[2] if len(sys.argv) > 2 else "S-%s-probe-d5" % time.strftime("%Y%m%d")
DB = "data/app.db"

REQUIRED_SLOTS = ["is_self", "need", "plan", "final_status", "turn_count"]


def _latency(turn_id):
    """造一组递增的时延打点（合计约 1.1 秒），仅用于验证统计链路。"""
    base = time.time()
    return {"type": "latency_mark", "session_id": SID, "turn_id": turn_id,
            "marks": {"vad_end": base - 1.10, "asr_final": base - 0.80,
                      "llm_first_token": base - 0.30,
                      "tts_first_audio": base - 0.05,
                      "browser_play_first": base}}


def _round(turn_id, user, agent_parts, frm, to, writeback=False):
    """一轮对话的消息序列：用户开口 → Agent 流式出字 → 合成句 → 切状态 → 打点。"""
    msgs = []
    if user:
        msgs.append({"type": "asr_final", "session_id": SID, "turn_id": turn_id,
                     "text": user, "ts": time.time()})
    for i, part in enumerate(agent_parts, 1):
        msgs.append({"type": "agent_text_delta", "session_id": SID,
                     "turn_id": turn_id, "seq": i, "delta": part})
    msgs.append({"type": "tts_segment", "session_id": SID, "turn_id": turn_id,
                 "seq": len(agent_parts), "text": "".join(agent_parts), "final": True})
    if to:
        msgs.append({"type": "state_change", "session_id": SID, "from": frm, "to": to})
    msgs.append(_latency(turn_id))
    if writeback:
        tc = "tc-%s-wb" % SID
        payload = {"is_self": True, "need": "会员权益咨询", "plan": "年卡续费9折",
                   "final_status": "已登记工单", "ticket_id": "T-20261114-01",
                   "turn_count": turn_id, "followup_required": False,
                   "customer_decision": "agree", "selected_plan": "renew_9off"}
        msgs.append({"type": "tool_log", "session_id": SID, "turn_id": turn_id,
                     "tool": "write_back", "args": payload,
                     "result": {"inserted": 1}, "latency_ms": 12,
                     "tool_call_id": tc})
        msgs.append({"type": "writeback", "session_id": SID,
                     "payload": payload, "tool_call_id": tc, "ts": time.time()})
    return msgs


ROUNDS = [
    # 轮1：Agent 自报身份（GREETING 必说话术）
    _round(1, None,
           ["您好，我是京东客服小智，", "今天想跟您确认一下会员到期的处理意向。"],
           "INIT", "GREETING"),
    # 轮2：确认身份
    _round(2, "喂，你好，是我本人。",
           ["好的，已确认是您本人，", "您之前办理的会员下个月到期。"],
           "GREETING", "IDENTITY_CONFIRM"),
    # 轮3：追问需求
    _round(3, "哦对，那个到期了要怎么办？",
           ["到期后权益会自动停止，", "想跟您确认一下您是想续费还是先放着？"],
           "IDENTITY_CONFIRM", "REQUIREMENT"),
    # 轮4：给方案（SOLUTION 必说话术：9折 + 12个月 + 到期提醒）
    _round(4, "我还想继续用，续一下怎么算？",
           ["现在续费可以享9折，", "有效期12个月，到期前会有短信提醒，没有隐藏条款。"],
           "REQUIREMENT", "SOLUTION"),
    # 轮5：确认决定
    _round(5, "行，那就按这个办。",
           ["好的，那我就按这个方案帮您登记了，", "可以吗？"],
           "SOLUTION", "CONFIRM"),
    # 轮6：登记 + 回写（写回业务系统，results 落一行）
    _round(6, "可以，办吧。",
           ["好的，已经为您登记，", "稍后会有短信通知您。"],
           "CONFIRM", "WRITEBACK", writeback=True),
    # 轮7：收尾
    _round(7, None,
           ["感谢您的时间，祝您生活愉快，再见。"],
           "WRITEBACK", "COMPLETED"),
]

FLAT = [m for r in ROUNDS for m in r]


async def send_all():
    ok, actions = 0, []
    async with websockets.connect(URL) as ws:
        for m in FLAT:
            await ws.send(json.dumps(m, ensure_ascii=False))
            r = json.loads(await ws.recv())
            act = (r.get("recorded") or {}).get("action")
            if act == "error":
                print("  ✗ %-16s %s" % (m["type"], (r.get("recorded") or {}).get("reason")))
            else:
                ok += 1
            actions.append(act)
    print("已发 %d 条，正常 %d 条" % (len(FLAT), ok))
    return ok == len(FLAT)


def verify_db():
    """落库侧能不能还原出一通完整电话。"""
    checks, problems = [], []

    def ck(name, cond, detail=""):
        checks.append((name, bool(cond), detail))
        if not cond:
            problems.append(name)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT role, text, state FROM turns WHERE session_id=? ORDER BY turn_id",
        (SID,)).fetchall()
    users = [r for r in rows if r["role"] == "user"]
    agents = [r for r in rows if r["role"] == "agent"]
    ck("轮次落库：用户轮 ≥5 且 Agent 轮 ≥6", len(users) >= 5 and len(agents) >= 6,
       "用户 %d / Agent %d / 合计 %d" % (len(users), len(agents), len(rows)))

    res = conn.execute(
        "SELECT slots_json, ticket_id FROM results WHERE session_id=?", (SID,)).fetchone()
    slots = json.loads(res["slots_json"]) if res else {}
    missing = [k for k in REQUIRED_SLOTS if k not in slots]
    ck("results 落一行且槽位齐全", res and not missing,
       "缺 %s" % missing if missing else "ticket=%s" % (res["ticket_id"] if res else "-"))

    lat = conn.execute(
        "SELECT COUNT(*) c FROM latency_marks WHERE session_id=?", (SID,)).fetchone()["c"]
    ck("时延打点 7 轮齐全", lat == 7, "实际 %d 条" % lat)

    tools = conn.execute(
        "SELECT COUNT(*) c FROM tool_logs WHERE session_id=?", (SID,)).fetchone()["c"]
    ck("工具调用有记录", tools >= 1, "实际 %d 条" % tools)

    conn.close()
    return checks, problems


def main():
    if not asyncio.run(send_all()):
        print("✗ 有消息落库报错，先看服务端输出")
        sys.exit(2)
    checks, problems = verify_db()
    print("\n落库验收：")
    for name, ok, detail in checks:
        print("  %s %-28s %s" % ("✓" if ok else "✗", name, detail))
    print("\nsession_id = %s" % SID)
    if problems:
        print("结论：未通过（%s）" % "、".join(problems))
        sys.exit(2)
    print("结论：通过（文本闭环已走到 COMPLETED）")


if __name__ == "__main__":
    main()
