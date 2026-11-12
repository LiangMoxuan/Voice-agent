#!/usr/bin/env bash
# Day3 二次核查脚本：日志中间件 + 协议消息落库
# 用法: bash scripts/verify_day3.sh
cd "$(dirname "$0")/.." || exit 1

PORT=8010
SID="S-$(date +%Y%m%d-%H%M%S)-check"
ok=0; bad=0
pass() { echo "  [通过] $1"; ok=$((ok+1)); }
fail() { echo "  [未过] $1"; echo "         → $2"; bad=$((bad+1)); }

echo "============================================"
echo " Day3 日志与落库核查（共 8 项）"
echo " 项目目录: $(pwd)"
echo "============================================"
echo ""

echo "1/8 Python 语法自检"
if .venv/bin/python -m compileall -q server scripts >/tmp/d3_compile.log 2>&1; then
  pass "server 与 scripts 无语法错误"
else
  fail "有语法错误" "看 /tmp/d3_compile.log"
fi
echo ""

echo "2/8 单元测试"
if .venv/bin/python -m pytest -q >/tmp/d3_pytest.log 2>&1; then
  pass "$(grep -E 'passed' /tmp/d3_pytest.log | tail -1)"
else
  fail "测试未通过" "看 /tmp/d3_pytest.log"
fi
echo ""

echo "3/8 建表"
if .venv/bin/python -m server.db init >/tmp/d3_dbinit.log 2>&1; then
  pass "$(tail -1 /tmp/d3_dbinit.log)"
else
  fail "建表失败" "看 /tmp/d3_dbinit.log"
fi
echo ""

echo "4/8 启动服务（端口 ${PORT}）"
nohup .venv/bin/python -m uvicorn server.main:app --port ${PORT} >/tmp/d3_uvicorn.log 2>&1 &
pid=$!
sleep 5
body=$(curl -s --max-time 5 http://127.0.0.1:${PORT}/health)
if [ "$body" = '{"status":"ok"}' ]; then
  pass "健康检查正常"
else
  fail "健康检查异常：$body" "看 /tmp/d3_uvicorn.log"
fi
echo ""

echo "5/8 HTTP 日志是否落盘"
if grep -q '"kind": "http"' data/logs/app-$(date +%Y%m%d).jsonl 2>/dev/null; then
  pass "data/logs 已有结构化访问日志"
else
  fail "没找到 http 日志" "确认 data/logs 目录可写、middleware 已挂载"
fi
echo ""

echo "6/8 走真实 WebSocket 发 8 条协议消息"
if .venv/bin/python scripts/day3_probe.py "ws://127.0.0.1:${PORT}/ws/control" "${SID}" >/tmp/d3_probe.log 2>&1; then
  pass "$(tail -1 /tmp/d3_probe.log)"
else
  fail "探针未全部成功" "看 /tmp/d3_probe.log"
fi
echo ""

echo "7/8 查 /api/turns，确认用户轮次与 Agent 轮次都在库里"
turns=$(curl -s --max-time 5 "http://127.0.0.1:${PORT}/api/turns/${SID}")
echo "$turns" >/tmp/d3_turns.json
u=$(grep -o '"role":"user"' /tmp/d3_turns.json | wc -l | tr -d ' ')
a=$(grep -o '"role":"agent"' /tmp/d3_turns.json | wc -l | tr -d ' ')
if [ "$u" -ge 1 ] && [ "$a" -ge 1 ]; then
  pass "用户轮次 ${u} 条、Agent 轮次 ${a} 条"
else
  fail "轮次不全：user=${u} agent=${a}" "看 /tmp/d3_turns.json"
fi
echo ""

echo "8/8 查 /api/stats，确认时延、工具、结果三表有数据"
stats=$(curl -s --max-time 5 "http://127.0.0.1:${PORT}/api/stats")
echo "$stats" >/tmp/d3_stats.json
if .venv/bin/python - "$stats" <<'PY'
import json, sys
d = json.loads(sys.argv[1])["tables"]
need = ("turns", "latency_marks", "tool_logs", "results")
sys.exit(0 if all(d[k] >= 1 for k in need) else 1)
PY
then
  pass "$(cat /tmp/d3_stats.json)"
else
  fail "有表没数据：$(cat /tmp/d3_stats.json)" "看 /tmp/d3_probe.log 哪条 action 是 error"
fi
echo ""

kill -TERM $pid >/dev/null 2>&1
sleep 1
kill -9 $pid >/dev/null 2>&1

echo "============================================"
echo " 通过 ${ok} 项，未过 ${bad} 项"
echo "============================================"
[ "$bad" -eq 0 ] || exit 1
