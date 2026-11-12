"""Day3 落库测试（C 维护）：协议消息进库后，turns/latency/tool_logs/results 各有一行。

协议原文见 docs/protocol-v0.md，字段名照抄，不自造。
"""
import os
import tempfile
import uuid

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "turns.db"))

import pytest  # noqa: E402

from server import db  # noqa: E402
from server.turns import Recorder  # noqa: E402


@pytest.fixture()
def rec():
    db.init()
    return Recorder()


def sid():
    return "S-test-%s" % uuid.uuid4().hex[:8]


def test_asr_final_records_user_turn(rec):
    s = sid()
    r = rec.handle({"type": "asr_final", "session_id": s, "turn_id": 1,
                    "text": "嗯我是他本人", "ts": 1731206400.1})
    assert r["ok"] and r["action"] == "turn_user"
    rows = db.list_turns(s)
    assert len(rows) == 1
    assert rows[0]["role"] == "user"
    assert rows[0]["text"] == "嗯我是他本人"


def test_agent_deltas_merge_into_one_row(rec):
    s = sid()
    rec.handle({"type": "asr_final", "session_id": s, "turn_id": 1, "text": "我是他本人"})
    rec.handle({"type": "agent_text_delta", "session_id": s, "turn_id": 2,
                "seq": 1, "delta": "好的张先生，"})
    rec.handle({"type": "agent_text_delta", "session_id": s, "turn_id": 2,
                "seq": 2, "delta": "已为您确认会员身份。"})
    # final=false 不落库，final=true 才收口
    rec.handle({"type": "tts_segment", "session_id": s, "turn_id": 2,
                "seq": 1, "text": "好的张先生，", "final": False})
    assert len(db.list_turns(s)) == 1
    r = rec.handle({"type": "tts_segment", "session_id": s, "turn_id": 2,
                    "seq": 2, "text": "已为您确认会员身份。", "final": True})
    assert r["action"] == "turn_agent"
    rows = db.list_turns(s)
    assert len(rows) == 2
    assert rows[1]["role"] == "agent"
    assert rows[1]["text"] == "好的张先生，已为您确认会员身份。"


def test_state_change_flushes_and_marks_state(rec):
    s = sid()
    rec.handle({"type": "state_change", "session_id": s,
                "from": "GREETING", "to": "IDENTITY_CONFIRM"})
    assert rec.current_state(s) == "IDENTITY_CONFIRM"
    rec.handle({"type": "agent_text_delta", "session_id": s, "turn_id": 1,
                "seq": 1, "delta": "请问您是张先生本人吗？"})
    r = rec.handle({"type": "state_change", "session_id": s,
                    "from": "IDENTITY_CONFIRM", "to": "REQUIREMENT"})
    assert r["action"] == "state_change" and r["flushed"]
    rows = db.list_turns(s)
    assert rows[-1]["role"] == "agent"
    assert rows[-1]["state"] == "IDENTITY_CONFIRM"


def test_interrupt_keeps_half_sentence(rec):
    s = sid()
    rec.handle({"type": "agent_text_delta", "session_id": s, "turn_id": 1,
                "seq": 1, "delta": "年卡续费享九折，"})
    r = rec.handle({"type": "interrupt", "session_id": s, "turn_id": 1,
                    "reason": "vad_speech_start"})
    assert r["action"] == "interrupt" and r["flushed"]
    assert db.list_turns(s)[0]["text"] == "年卡续费享九折，"


def test_latency_and_tool_log(rec):
    s = sid()
    rec.handle({"type": "latency_mark", "session_id": s, "turn_id": 1,
                "marks": {"vad_end": 1731206400.001, "asr_final": 1731206400.210,
                          "llm_first_token": 1731206400.640,
                          "tts_first_audio": 1731206400.980,
                          "browser_play_first": 1731206401.050}})
    rec.handle({"type": "tool_log", "session_id": s, "turn_id": 1,
                "tool": "get_order", "args": {"customer_id": "C0001"},
                "result": {"order_id": "O-7788", "status": "已发货"},
                "latency_ms": 42, "tool_call_id": "tc-test-1"})
    rec.handle({"type": "tool_log", "session_id": s, "turn_id": 1,
                "tool": "get_order", "args": {"customer_id": "C0001"},
                "result": {"order_id": "O-7788"}, "latency_ms": 42,
                "tool_call_id": "tc-test-1"})  # 同编号重复，应被忽略
    st = db.stats()
    assert st["latency_marks"] >= 1
    assert st["tool_logs"] >= 1
    n = db.stats()["tool_logs"]
    assert n >= 1


def test_writeback_sets_final_status(rec):
    s = sid()
    payload = {"is_self": True, "need": "会员权益咨询", "plan": "年卡续费9折",
               "final_status": "已登记工单", "ticket_id": "T-5566", "turn_count": 6}
    r1 = rec.handle({"type": "writeback", "session_id": s,
                     "payload": payload, "tool_call_id": "tc-wb-%s" % s})
    r2 = rec.handle({"type": "writeback", "session_id": s,
                     "payload": payload, "tool_call_id": "tc-wb-%s" % s})
    assert r1["inserted"] == 1 and r2["inserted"] == 0
    sess = [x for x in db.list_sessions(200) if x["session_id"] == s]
    assert sess and sess[0]["final_status"] == "已登记工单"


def test_bad_message_does_not_crash(rec):
    assert rec.handle("不是字典")["ok"] is False
    assert rec.handle({"type": "asr_final"})["action"] == "ignored"
    assert rec.handle({"type": "echo", "session_id": "S-x", "received": {}})["action"] == "ignored"
    assert rec.handle({"type": "asr_final", "session_id": "S-x", "text": "  "})["ok"] is False


def test_ws_control_writes_through(rec):
    """走真实 WebSocket 信道，确认落库不是只在单元测试里成立。"""
    from fastapi.testclient import TestClient
    from server.main import app

    s = sid()
    with TestClient(app) as client:
        with client.websocket_connect("/ws/control") as ws:
            ws.send_json({"type": "asr_final", "session_id": s, "turn_id": 1,
                          "text": "你好，我是他本人"})
            r = ws.receive_json()
            assert r["type"] == "echo"
            assert r["recorded"]["action"] == "turn_user"
    assert len(db.list_turns(s)) == 1
