"""SQLite 数据层（C 维护，A/B 只调用不修改表结构）。

用法：
    python -m server.db init     # 建表（可重复执行）
"""
import os
import pathlib
import sqlite3

from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/app.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions(
  session_id TEXT PRIMARY KEY, started_at REAL, ended_at REAL, final_status TEXT);

CREATE TABLE IF NOT EXISTS turns(
  turn_id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, text TEXT,
  intent TEXT, state TEXT, ts REAL);

CREATE TABLE IF NOT EXISTS tool_logs(
  tool_call_id TEXT PRIMARY KEY, session_id TEXT, tool TEXT, args TEXT, result TEXT,
  latency_ms INT, ok INT, ts REAL);

CREATE TABLE IF NOT EXISTS results(
  tool_call_id TEXT UNIQUE, session_id TEXT, slots_json TEXT, ticket_id TEXT, ts REAL);

CREATE TABLE IF NOT EXISTS quality_issues(
  id INTEGER PRIMARY KEY, session_id TEXT, rule TEXT, snippet TEXT, action TEXT, ts REAL);

CREATE TABLE IF NOT EXISTS latency_marks(
  session_id TEXT, turn_id INT, vad_end REAL, asr_final REAL,
  llm_first REAL, tts_first REAL, play_first REAL);
"""


def get_conn():
    pathlib.Path(os.path.dirname(DB_PATH) or ".").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print("init db ok: %s" % DB_PATH)


# ===== 写入口（C 维护；A/B 只准调这些函数，不写裸 SQL）=====

def add_session(session_id, ts=None):
    """首个消息到达时建会话行，重复调用不覆盖开始时间。"""
    import time
    conn = get_conn()
    cur = conn.execute(
        "INSERT OR IGNORE INTO sessions(session_id, started_at) VALUES (?, ?)",
        (session_id, ts or time.time()))
    conn.commit()
    conn.close()
    return cur.rowcount


def add_turn(session_id, role, text, intent=None, state=None, ts=None):
    """记一轮发言。role 只有 user / agent 两种。"""
    import time
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO turns(session_id, role, text, intent, state, ts) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, role, text, intent, state, ts or time.time()))
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def list_turns(session_id, limit=200):
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT turn_id, session_id, role, text, intent, state, ts FROM turns "
        "WHERE session_id = ? ORDER BY turn_id LIMIT ?",
        (session_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_latency(session_id, turn_id, marks):
    """协议里 marks 的键名 → latency_marks 表列名，这里转换一次。"""
    m = marks or {}
    conn = get_conn()
    conn.execute(
        "INSERT INTO latency_marks(session_id, turn_id, vad_end, asr_final, "
        "llm_first, tts_first, play_first) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session_id, turn_id, m.get("vad_end"), m.get("asr_final"),
         m.get("llm_first_token"), m.get("tts_first_audio"),
         m.get("browser_play_first")))
    conn.commit()
    conn.close()


def add_tool_log(session_id, tool, args, result, latency_ms, tool_call_id, turn_id=None):
    import json
    import time
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO tool_logs(tool_call_id, session_id, tool, args, "
        "result, latency_ms, ok, ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (tool_call_id, session_id, tool,
         json.dumps(args, ensure_ascii=False),
         json.dumps(result, ensure_ascii=False),
         latency_ms, 1 if (result or {}).get("error") is None else 0,
         time.time()))
    conn.commit()
    conn.close()


def set_final_status(session_id, final_status, ts=None):
    import time
    conn = get_conn()
    conn.execute(
        "UPDATE sessions SET final_status = ?, ended_at = ? WHERE session_id = ?",
        (final_status, ts or time.time(), session_id))
    conn.commit()
    conn.close()


# ===== 读出口（给 /api 查询页与第 11 章看板）=====

def list_sessions(limit=50):
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT s.session_id, s.started_at, s.ended_at, s.final_status, "
        "(SELECT COUNT(*) FROM turns t WHERE t.session_id = s.session_id) AS turn_count "
        "FROM sessions s ORDER BY s.started_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def stats():
    conn = get_conn()
    out = {}
    for tbl in ("sessions", "turns", "tool_logs", "results",
                "quality_issues", "latency_marks"):
        out[tbl] = conn.execute("SELECT COUNT(*) FROM %s" % tbl).fetchone()[0]
    conn.close()
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        init()
    else:
        print("usage: python -m server.db init")
