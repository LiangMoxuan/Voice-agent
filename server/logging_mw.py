"""HTTP 访问日志中间件（C 维护）。"""
import logging
import time
import uuid

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("http")


async def logging_mw(request, call_next):
    rid = uuid.uuid4().hex[:8]
    t0 = time.time()
    response = await call_next(request)
    ms = int((time.time() - t0) * 1000)
    log.info("%s %s -> %d %dms rid=%s",
             request.method, request.url.path, response.status_code, ms, rid)
    response.headers["X-Request-Id"] = rid
    return response
