"""WebSocket 协议冒烟脚本（手动跑，不被 pytest 收集）。

用法：
    # 终端1
    uvicorn server.main:app --port 8000
    # 终端2
    python tests/ws_check.py
"""
import asyncio
import json

import websockets


async def main():
    uri = "ws://localhost:8000/ws/control"
    async with websockets.connect(uri) as ws:
        payload = {"type": "ping", "session_id": "S-001", "turn_id": 1}
        await ws.send(json.dumps(payload))
        print("收到：", await ws.recv())


if __name__ == "__main__":
    asyncio.run(main())
