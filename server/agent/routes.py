"""Agent 的 HTTP 调试入口（B 维护）。

Day2 先当回声用，确认 HTTP 通路是通的；Day3 之后把 agent_text 换成真 Agent。
"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/agent", tags=["agent"])


class TextIn(BaseModel):
    session_id: str
    text: str


@router.post("/text")
async def agent_text(inp: TextIn):
    # TODO(B, Day3)：换成 server.agent.fsm.step(...) 的真实现
    return {"session_id": inp.session_id, "reply": "(收到) " + inp.text}
