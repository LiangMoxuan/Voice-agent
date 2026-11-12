"""查询接口（C 维护）。

Day3 先给三张最小查询，供人工核对与前端/看板取数：
    GET /api/sessions        最近会话列表（含轮次数）
    GET /api/turns/{sid}     某个会话的完整轮次
    GET /api/stats           六张表的行数，一眼看出落库有没有生效
"""
from fastapi import APIRouter

from server import db

router = APIRouter(prefix="/api", tags=["inspect"])


@router.get("/sessions")
def sessions(limit: int = 50):
    return {"ok": True, "items": db.list_sessions(limit)}


@router.get("/turns/{session_id}")
def turns(session_id: str, limit: int = 200):
    items = db.list_turns(session_id, limit)
    return {"ok": True, "session_id": session_id,
            "turn_count": len(items), "items": items}


@router.get("/stats")
def stats():
    return {"ok": True, "tables": db.stats()}
