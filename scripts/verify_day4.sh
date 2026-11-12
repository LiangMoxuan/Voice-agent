#!/usr/bin/env bash
# Day4 二次核查脚本：WebRTC 备选验证 + 首字时延统计
# 用法: bash scripts/verify_day4.sh
cd "$(dirname "$0")/.." || exit 1

PORT=8010
SID="S-$(date +%Y%m%d-%H%M%S)-check"
ok=0; bad=0
pass() { echo "  [通过] $1"; ok=$((ok+1)); }
fail() { echo "  [未过] $1"; echo "         → $2"; bad=$((bad+1)); }

echo "============================================"
echo " Day4 WebRTC 与时延核查（共 8 项）"
echo " 项目目录: $(pwd)"
echo "============================================"
echo ""

echo "1/8 Python 语法自检"
if .venv/bin/python -m compileall -q server eval scripts >/tmp/d4_compile.log 2>&1; then
  pass "server / eval / scripts 无语法错误"
else
  fail "有语法错误" "看 /tmp/d4_compile.log"
fi
echo ""

echo "2/8 单元测试"
if .venv/bin/python -m pytest -q >/tmp/d4_pytest.log 2>&1; then
  pass "$(grep -E 'passed' /tmp/d4_pytest.log | tail -1)"
else
  fail "测试未通过" "看 /tmp/d4_pytest.log"
fi
echo ""

echo "3/8 aiortc 本机回环（发 30 帧音频，能否收到）"
if .venv/bin/python scripts/verify_aiortc.py --frames 30 >/tmp/d4_aiortc.log 2>&1; then
  pass "$(grep '结论' /tmp/d4_aiortc.log)"
  echo "         $(grep '连接建立耗时' /tmp/d4_aiortc.log)"
  echo "         $(grep '帧数' /tmp/d4_aiortc.log)"
else
  fail "WebRTC 回环不通" "按第 13 章对策转 WS 等效方案；明细见 /tmp/d4_aiortc.log"
fi
echo ""

echo "4/8 启动服务（端口 ${PORT}）"
nohup .venv/bin/python -m uvicorn server.main:app --port ${PORT} >/tmp/d4_uvicorn.log 2>&1 &
pid=$!
sleep 5
body=$(curl -s --max-time 5 http://127.0.0.1:${PORT}/health)
if [ "$body" = '{"status":"ok"}' ]; then
  pass "健康检查正常"
else
  fail "健康检查异常：$body" "看 /tmp/d4_uvicorn.log"
fi
echo ""

echo "5/8 灌一轮探针对话（含时延打点）"
if .venv/bin/python scripts/day3_probe.py "ws://127.0.0.1:${PORT}/ws/control" "${SID}" >/tmp/d4_probe.log 2>&1; then
  pass "$(tail -1 /tmp/d4_probe.log)"
else
  fail "探针未成功" "看 /tmp/d4_probe.log"
fi
echo ""

echo "6/8 时延统计工具能否出数"
if .venv/bin/python -m eval.latency --session "${SID}" --json >/tmp/d4_lat.json 2>&1; then
  p50=$(.venv/bin/python -c "import json;print(json.load(open('/tmp/d4_lat.json'))['summary'].get('p50_ms'))")
  pass "本会话 P50 = ${p50} ms，工具出数正常"
else
  fail "统计脚本失败" "看 /tmp/d4_lat.json"
fi
echo ""

echo "7/8 探针数据是否被拦在验收之外（防止拿假数据当成绩）"
if .venv/bin/python -m eval.latency --session "${SID}" --gate >/tmp/d4_gate.log 2>&1; then
  fail "假数据竟被判达标" "检查 eval/latency.py 的 gate 逻辑"
else
  pass "$(grep '不通过' /tmp/d4_gate.log | head -1)"
fi
echo ""

echo "8/8 六表数据齐全"
stats=$(curl -s --max-time 5 "http://127.0.0.1:${PORT}/api/stats")
if .venv/bin/python - "$stats" <<'PY'
import json, sys
d = json.loads(sys.argv[1])["tables"]
sys.exit(0 if all(d[k] >= 1 for k in ("sessions", "turns", "latency_marks", "tool_logs", "results")) else 1)
PY
then
  pass "$stats"
else
  fail "有表没数据：$stats" "看 /tmp/d4_probe.log"
fi
echo ""

kill -TERM $pid >/dev/null 2>&1
sleep 1
kill -9 $pid >/dev/null 2>&1

echo "============================================"
echo " 通过 ${ok} 项，未过 ${bad} 项"
echo "============================================"
[ "$bad" -eq 0 ] || exit 1
