"""数据库表结构与幂等约束（C 维护）。"""
import os
import tempfile

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

from server import db  # noqa: E402
from server.tools.writeback import write_back  # noqa: E402

EXPECTED = {"sessions", "turns", "tool_logs", "results", "quality_issues", "latency_marks"}
RESULT = {"is_self": True, "need": "会员权益咨询", "plan": "年卡续费9折",
          "final_status": "已登记工单", "ticket_id": "T-5566", "turn_count": 6}


def test_init_creates_all_tables():
    db.init()
    conn = db.get_conn()
    names = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
    conn.close()
    assert EXPECTED <= names


def test_writeback_is_idempotent():
    db.init()
    r1 = write_back("S-t-001", RESULT, "tc-20261110-0001")
    r2 = write_back("S-t-001", RESULT, "tc-20261110-0001")
    assert r1["inserted"] == 1
    assert r2["inserted"] == 0 and r2["duplicated"] is True


def test_writeback_rejects_bad_payload():
    db.init()
    assert write_back("S-t-002", {"is_self": True}, "tc-x1")["error"] == "missing_fields"
    bad = dict(RESULT, final_status="随便写的")
    assert write_back("S-t-003", bad, "tc-x2")["error"] == "bad_status"
