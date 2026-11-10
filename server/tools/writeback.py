"""结构化回写 + 幂等（B 维护）。幂等靠 results.tool_call_id 的 UNIQUE 约束。"""
import json
import time

from server.db import get_conn

REQUIRED_KEYS = ["is_self", "need", "plan", "final_status", "turn_count"]
ALLOWED_STATUS = {"已登记工单", "拒绝-已记录原因", "错号", "转人工"}


def write_back(session_id, result, tool_call_id):
    missing = [k for k in REQUIRED_KEYS if k not in result]
    if missing:
        return {"error": "missing_fields", "missing": missing}
    if result["final_status"] not in ALLOWED_STATUS:
        return {"error": "bad_status", "value": result["final_status"]}

    conn = get_conn()
    cur = conn.execute(
        """INSERT OR IGNORE INTO results
           (tool_call_id, session_id, slots_json, ticket_id, ts)
           VALUES (?,?,?,?,?)""",
        (tool_call_id, session_id,
         json.dumps(result, ensure_ascii=False),
         result.get("ticket_id"), time.time()),
    )
    conn.commit()
    conn.close()
    return {"inserted": cur.rowcount, "tool_call_id": tool_call_id,
            "duplicated": cur.rowcount == 0}
