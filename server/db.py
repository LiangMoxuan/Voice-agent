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


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        init()
    else:
        print("usage: python -m server.db init")
