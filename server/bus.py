"""进程内事件总线（C 维护）。topic 命名严格按 docs/protocol-v0.md。"""
import asyncio
import logging

log = logging.getLogger("bus")


class Bus:
    def __init__(self):
        self._subs = {}

    def on(self, topic, handler):
        self._subs.setdefault(topic, []).append(handler)

    async def publish(self, topic, payload):
        for h in self._subs.get(topic, []):
            try:
                r = h(payload)
                if asyncio.iscoroutine(r):
                    await r
            except Exception:
                log.exception("handler %s failed on topic %s",
                              getattr(h, "__name__", h), topic)
        log.info("[bus] %s session=%s", topic, (payload or {}).get("session_id"))


bus = Bus()
