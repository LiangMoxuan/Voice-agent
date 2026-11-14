#!/usr/bin/env bash
# Day5 二次核查脚本：必说/禁语词表 + 文本闭环到 COMPLETED
# 用法: bash scripts/verify_day5.sh
set -u

cd "$(dirname "$0")/.." || exit 2
PY=".venv/bin/python"
PORT="${PORT:-8010}"
PASS=0
FAIL=0

ok()   { PASS=$((PASS+1)); printf "  [通过] %s\n" "$1"; }
bad()  { FAIL=$((FAIL+1)); printf "  [失败] %s\n" "$1"; }
head_() { printf "\n== %s ==\n" "$1"; }

head_ "1 词表可加载且条数够"
if $PY - <<'PY'
import sys
from server.agent.guardrails import _BANNED, _MUST
sys.exit(0 if len(_BANNED) >= 25 and len(_MUST) >= 6 else 1)
PY
then ok "词表条数达标（禁语≥25、必说≥6）"; else bad "词表条数不足（要求禁语≥25、必说≥6）"; fi

head_ "2 禁语命中被拦截"
if $PY - <<'PY'
import sys
from server.agent.guardrails import check
r = check("SOLUTION", "这个方案绝对保证有效，年卡续费享9折，有效期12个月")
sys.exit(0 if (not r["ok"]) and r["reply"].startswith("不好意思") else 1)
PY
then ok "禁语→换兜底话术"; else bad "禁语没拦住"; fi

head_ "3 隐私（手机号）被拦截"
if $PY - <<'PY'
import sys
from server.agent.guardrails import check
r = check("REQUIREMENT", "您的手机号13800138000已登记")
sys.exit(0 if not r["ok"] and "隐私" in "".join(r["problems"]) else 1)
PY
then ok "手机号→拦截"; else bad "手机号没拦住"; fi

head_ "4 隐私（身份证）被拦截"
if $PY - <<'PY'
import sys
from server.agent.guardrails import check
r = check("REQUIREMENT", "这边显示您身份证110101199001011234")
sys.exit(0 if not r["ok"] else 1)
PY
then ok "身份证号→拦截"; else bad "身份证号没拦住"; fi

head_ "5 合规回复正常放行"
if $PY - <<'PY'
import sys
from server.agent.guardrails import check
r = check("SOLUTION", "现在续费可以享9折，有效期12个月，到期前会有短信提醒")
sys.exit(0 if r["ok"] and r["reply"] else 1)
PY
then ok "合规话术直接下发"; else bad "合规话术被误拦"; fi

head_ "6 缺必说话术被拦截"
if $PY - <<'PY'
import sys
from server.agent.guardrails import check
r = check("GREETING", "你好呀，有什么事吗")
sys.exit(0 if not r["ok"] and "必说" in "".join(r["problems"]) else 1)
PY
then ok "GREETING 缺自我介绍→拦截"; else bad "缺必说话术没拦住"; fi

head_ "7 自动测试全过"
if $PY -m pytest -q >/tmp/verify_d5_pytest.log 2>&1; then
  ok "$(tail -1 /tmp/verify_d5_pytest.log | tr -d '\n')"
else
  bad "pytest 未全过，见 /tmp/verify_d5_pytest.log"
fi

head_ "8 文本闭环走到 COMPLETED"
$PY -m uvicorn server.main:app --port "$PORT" >/tmp/verify_d5_server.log 2>&1 &
SRV=$!
sleep 6
if $PY scripts/day5_close_loop.py "ws://127.0.0.1:$PORT/ws/control" "S-$(date +%Y%m%d)-probe-d5v" >/tmp/verify_d5_loop.log 2>&1; then
  ok "$(grep '结论：' /tmp/verify_d5_loop.log | tr -d '\n')"
else
  bad "闭环未通过，见 /tmp/verify_d5_loop.log"
fi
kill -TERM $SRV 2>/dev/null; sleep 1; kill -9 $SRV 2>/dev/null

printf "\n== 汇总 ==\n  通过 %d 项，失败 %d 项\n" "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
