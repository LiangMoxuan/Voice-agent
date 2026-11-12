"""首字响应时延统计（C 维护，Day4；对应指南第 7.5 节）。

口径必须先说清楚，否则数字没法比：
    t0 = vad_end        —— 用户最后一个有效音频帧，即"说完了"的那一刻
    t1 = play_first     —— 浏览器第一块 TTS 音频真正开始播放
    首字响应时延 = t1 - t0

三个分段（都相对 t0 计偏移，用来定位是哪一段拖慢了）：
    asr_ms  = asr_final - vad_end
    llm_ms  = llm_first - vad_end
    tts_ms  = tts_first - vad_end

为什么不能混用：ASR 尾包延迟只是"字出来了"，不等于"出声了"；LLM 首 token 同理。
指南第 7.5 节点名禁止混用，方案书里也要按这套口径写。

用法：
    python -m eval.latency                       # 全部会话
    python -m eval.latency --session S-20261113-001
    python -m eval.latency --json                # 给看板/脚本吃
    python -m eval.latency --gate                # 按第 7.5 节验收线判定，不达标退出码 1
"""
import argparse
import json
import sys

import numpy as np

from server import db

# 指南第 7.5 节验收线：P50 ≤ 2s、P95 < 2.5s；样本至少 20 通电话
GATE_P50_MS = 2000
GATE_P95_MS = 2500
MIN_SAMPLES = 20


def load_rows(session_id=None, limit=2000):
    conn = db.get_conn()
    sql = ("SELECT session_id, turn_id, vad_end, asr_final, llm_first, "
           "tts_first, play_first FROM latency_marks")
    args = []
    if session_id:
        sql += " WHERE session_id = ?"
        args.append(session_id)
    sql += " ORDER BY rowid DESC LIMIT ?"
    args.append(limit)
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return rows


def _ms(a, b):
    if a is None or b is None:
        return None
    return round((b - a) * 1000, 1)


def _is_probe(session_id):
    """探针会话（scripts/day3_probe.py 造的）不是真人通话，数字不能进验收结论。"""
    s = (session_id or "").lower()
    return "check" in s or "probe" in s or "test" in s


def compute(session_id=None):
    """返回 {turns:[...], summary:{...}}；缺打点的轮次单独计数不入分位。"""
    rows = load_rows(session_id)
    turns, missing = [], 0
    for sid, turn, vad, asr, llm, tts, play in rows:
        e2e = _ms(vad, play)
        if e2e is None or e2e < 0:
            missing += 1
            continue
        turns.append({"session_id": sid, "turn_id": turn, "e2e_ms": e2e,
                      "asr_ms": _ms(vad, asr), "llm_ms": _ms(vad, llm),
                      "tts_ms": _ms(vad, tts), "probe": _is_probe(sid)})

    values = [t["e2e_ms"] for t in turns]
    summary = {"turns": len(values), "missing_marks": missing,
               "sessions": len({t["session_id"] for t in turns}),
               "probe_turns": sum(1 for t in turns if t["probe"])}
    if values:
        summary.update({
            "p50_ms": round(float(np.percentile(values, 50)), 1),
            "p95_ms": round(float(np.percentile(values, 95)), 1),
            "p99_ms": round(float(np.percentile(values, 99)), 1),
            "min_ms": min(values),
            "max_ms": max(values),
        })
        for key in ("asr_ms", "llm_ms", "tts_ms"):
            seg = [t[key] for t in turns if t[key] is not None]
            summary["mean_" + key] = round(float(np.mean(seg)), 1) if seg else None
    return {"turns": turns, "summary": summary}


def gate(summary):
    """按验收线判定。

    两类输出分开：problems 是致命项（直接不通过），notes 只是提示（样本不足等）。
    全部样本来自探针时一律不通过 —— 假数据跑得再快也不能当成绩。
    """
    problems, notes = [], []
    n = summary.get("turns", 0)
    probe = summary.get("probe_turns", 0)
    if n == 0:
        problems.append("没有任何带首播时点的样本")
    if n and probe == n:
        problems.append("样本 %d 轮全部来自探针脚本，不能作为验收证据" % n)
    if n < MIN_SAMPLES:
        notes.append("样本 %d 条，少于指南要求的 %d 通，只能看趋势" % (n, MIN_SAMPLES))
    if summary.get("p50_ms") is not None and summary["p50_ms"] > GATE_P50_MS:
        problems.append("P50 %s ms，超过 %d ms 门槛" % (summary["p50_ms"], GATE_P50_MS))
    if summary.get("p95_ms") is not None and summary["p95_ms"] >= GATE_P95_MS:
        problems.append("P95 %s ms，不低于 %d ms 门槛" % (summary["p95_ms"], GATE_P95_MS))
    return {"passed": not problems, "problems": problems, "notes": notes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()

    r = compute(a.session)
    g = gate(r["summary"])
    if a.json:
        print(json.dumps({"summary": r["summary"], "gate": g, "turns": r["turns"]},
                         ensure_ascii=False, indent=2))
    else:
        s = r["summary"]
        print("样本：%d 轮 / %d 通电话（缺首播时点 %d 条未计入）"
              % (s["turns"], s["sessions"], s["missing_marks"]))
        if s["probe_turns"]:
            print("注意：其中 %d 轮来自探针脚本（假数据，只用于验证工具本身，不可作为验收证据）"
                  % s["probe_turns"])
        if s["turns"]:
            print("首字响应时延  P50 %s ms  P95 %s ms  P99 %s ms  区间 %s ~ %s ms"
                  % (s["p50_ms"], s["p95_ms"], s["p99_ms"], s["min_ms"], s["max_ms"]))
            print("分段均值（相对说完那一刻）  ASR %s ms  LLM %s ms  TTS %s ms"
                  % (s["mean_asr_ms"], s["mean_llm_ms"], s["mean_tts_ms"]))
        for p in g["problems"]:
            print("不通过：" + p)
        for p in g["notes"]:
            print("提示：" + p)
        print("判定：%s" % ("达标" if g["passed"] else "未达标"))
    if a.gate and not g["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
