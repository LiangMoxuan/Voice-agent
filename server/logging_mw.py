"""HTTP 访问日志中间件（C 维护）。

Day3 起不只是打控制台：每个请求一条 JSON 落 data/logs，异常单独记一条。
响应头带 X-Request-Id，方便把一次报错从浏览器查到日志里。
"""
import logging
import time
import uuid

from server.logs import log_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("http")


async def logging_mw(request, call_next):
    rid = uuid.uuid4().hex[:8]
    t0 = time.time()
    try:
        response = await call_next(request)
    except Exception:
        ms = int((time.time() - t0) * 1000)
        log.exception("异常 %s %s rid=%s", request.method, request.url.path, rid)
        log_event("http_error", rid=rid, method=request.method,
                  path=request.url.path, ms=ms,
                  ua=request.headers.get("user-agent", ""))
        raise
    ms = int((time.time() - t0) * 1000)
    log.info("%s %s -> %d %dms rid=%s",
             request.method, request.url.path, response.status_code, ms, rid)
    log_event("http", rid=rid, method=request.method, path=request.url.path,
              status=response.status_code, ms=ms,
              ua=request.headers.get("user-agent", ""))
    response.headers["X-Request-Id"] = rid
    return response
