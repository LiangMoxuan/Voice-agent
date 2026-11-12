"""结构化日志（C 维护）。

两个去处：
1. 控制台 —— 人看，开发时排错用；
2. `data/logs/app-YYYYMMDD.jsonl` —— 第 12 章自测报告要求的"原始日志"，
   一行一条 JSON，评测脚本与看板直接读。

`data/` 已在 .gitignore 里，日志不会误提交。
"""
import datetime
import json
import logging
import os
import pathlib
import time

LOG_DIR = os.getenv("LOG_DIR", "data/logs")
log = logging.getLogger("app")


def _today_path() -> pathlib.Path:
    pathlib.Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    return pathlib.Path(LOG_DIR) / ("app-%s.jsonl" % datetime.date.today().strftime("%Y%m%d"))


def log_event(kind: str, **fields) -> dict:
    """写一条结构化日志，返回这条记录（便于测试断言，不必读文件）。"""
    rec = {"ts": round(time.time(), 3), "kind": kind}
    rec.update(fields)
    try:
        with open(_today_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    except OSError as e:
        log.warning("日志文件写入失败：%s (%s)", _today_path(), e)
    return rec
