"""按协议发一轮假对话，验证落库是否生效（C 维护）。

服务启动后可单独跑：
    python scripts/day3_probe.py
    python scripts/day3_probe.py ws://127.0.0.1:8010/ws/control S-20261113-check

它不做语音，只发协议 JSON —— 目的是在 A 的麦克风、B 的 Agent 还没接上时，
先把"每条消息都能落库"这件事验证掉。
"""
import asyncio
import json
import sys
import time

try:
    import websockets
except ImportError:
    sys.exit("缺 websockets：.venv/bin/pip install websockets")

URL = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8010/ws/control"
SID = sys.argv[2] if len(sys.argv) > 2 else "S-%s-check" % time.strftime("%Y%m%d")

MSGS = [
    {"type": "asr_final", "session_id": SID, "turn_id": 1,
     "text": "喂，你好，我是张先生本人", "ts": time.time()},
    {"type": "agent_text_delta", "session_id": SID, "turn_id": 1, "seq": 1,
     "delta": "您好，我是京东客服小智，"},
    {"type": "agent_text_delta", "session_id": SID, "turn_id": 1, "seq": 2,
     "delta": "您之前办理的会员下月到期，想跟您确认一下到期处理意向。"},
    {"type": "tts_segment", "session_id": SID, "turn_id": 1, "seq": 2,
     "text": "您之前办理的会员下月到期，想跟您确认一下到期处理意向。", "final": True},
    {"type": "state_change", "session_id": SID,
     "from": "GREETING", "to": "IDENTITY_CONFIRM"},
    {"type": "latency_mark", "session_id": SID, "turn_id": 1,
     "marks": {"vad_end": time.time() - 1.2, "asr_final": time.time() - 0.9,
               "llm_first_token": time.time() - 0.5,
               "tts_first_audio": time.time() - 0.2,
               "browser_play_first": time.time()}},
    {"type": "tool_log", "session_id": SID, "turn_id": 1, "tool": "get_order",
     "args": {"customer_id": "C0001"},
     "result": {"order_id": "O-7788", "status": "已发货"},
     "latency_ms": 42, "tool_call_id": "tc-%s-1" % SID},
    {"type": "writeback", "session_id": SID,
     "payload": {"is_self": True, "need": "会员权益咨询", "plan": "年卡续费9折",
                 "final_status": "已登记工单", "ticket_id": "T-5566", "turn_count": 1},
     "tool_call_id": "tc-%s-2" % SID},
]


async def main():
    ok = 0
    async with websockets.connect(URL) as ws:
        for m in MSGS:
            await ws.send(json.dumps(m, ensure_ascii=False))
            r = json.loads(await ws.recv())
            act = r.get("recorded", {}).get("action")
            print("%-18s -> %s" % (m["type"], act))
            ok += 1 if act and act != "error" else 0
    print("session_id = %s" % SID)
    print("已发 %d 条，落库动作 %d 条" % (len(MSGS), ok))
    if ok != len(MSGS):
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
