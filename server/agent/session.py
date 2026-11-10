"""会话状态（B 维护）。内存为主，每 N 轮落一份 JSON 便于断线恢复（C 的 Day6 会用它）。"""
import json
import os
import time
import uuid

ARCHIVE_DIR = os.getenv("SESSION_ARCHIVE_DIR", "data/sessions")


def new_session(customer_id="C0001"):
    sid = "S-%s-%s" % (time.strftime("%Y%m%d"), uuid.uuid4().hex[:4])
    return {
        "session_id": sid,
        "customer_id": customer_id,
        "state": "INIT",
        "slots": {},
        "history": [],
        "turns_in_state": 0,
        "consecutive_fail": 0,
        "ask_counts": {},
        "created_at": time.time(),
    }


def save(session):
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    path = os.path.join(ARCHIVE_DIR, session["session_id"] + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False)
    return path


def load(session_id):
    path = os.path.join(ARCHIVE_DIR, session_id + ".json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
