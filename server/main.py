"""FastAPI 入口（C 维护）。注意：app.mount("/") 必须在文件最后一行。"""
# 1) 先加载 .env，再 import 其他模块（db.py 在 import 时就会读 DB_PATH）
from dotenv import load_dotenv

load_dotenv()

import json  # noqa: E402

from fastapi import FastAPI, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from server.logging_mw import logging_mw  # noqa: E402
from server.agent.routes import router as agent_router  # noqa: E402
from server.tools.mock_api import router as mock_router  # noqa: E402

app = FastAPI(title="voice-agent")
app.middleware("http")(logging_mw)
app.include_router(agent_router)
app.include_router(mock_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.websocket("/ws/control")
async def control(ws: WebSocket):
    """Day1 只做回声，证明协议链路通。Day3 之后接真总线（A 负责音频侧）。"""
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                msg = {"type": "raw", "error": "invalid_json"}
            await ws.send_text(json.dumps(
                {"type": "echo", "received": msg}, ensure_ascii=False))
    except WebSocketDisconnect:
        return


# ===== 必须放在最后：静态站点挂载会吃掉后面所有路由 =====
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
