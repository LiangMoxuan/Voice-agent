#!/usr/bin/env bash
# Day2 二次核查脚本（在项目根目录或任意位置运行都行）
# 用法: bash scripts/verify_day2.sh
cd "$(dirname "$0")/.." || exit 1

ok=0; bad=0
pass() { echo "  [通过] $1"; ok=$((ok+1)); }
fail() { echo "  [未过] $1"; echo "         → $2"; bad=$((bad+1)); }

echo "============================================"
echo " Day2 环境与骨架核查（共 10 项）"
echo " 项目目录: $(pwd)"
echo "============================================"
echo ""

echo "1/10 Python 3.12 是否已安装"
if command -v python3.12 >/dev/null 2>&1; then
  pass "python3.12 = $(python3.12 -V 2>&1)"
else
  fail "找不到 python3.12" "双击桌面的 python-3.12.10-macos11.pkg 安装，装完重开终端"
fi
echo ""

echo "2/10 虚拟环境是否已建立"
if [ -x .venv/bin/python ]; then
  pass ".venv 已存在，版本 $(.venv/bin/python -V 2>&1)"
else
  fail ".venv 不存在" "执行: python3.12 -m venv .venv"
fi
echo ""

echo "3/10 三个关键依赖能否导入"
if [ -x .venv/bin/python ]; then
  if .venv/bin/python -c "import fastapi, dashscope, aiortc" >/dev/null 2>&1; then
    pass "fastapi / dashscope / aiortc 均可导入"
  else
    fail "依赖导入失败" "source .venv/bin/activate 后执行: pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple"
  fi
else
  fail "跳过（venv 未建）" "先完成第 2 项"
fi
echo ""

echo "4/10 数据库能否初始化"
if [ -x .venv/bin/python ] && .venv/bin/python -m server.db init >/tmp/db_init.log 2>&1; then
  pass "建表成功：$(tail -1 /tmp/db_init.log)"
  [ -f data/app.db ] && pass "data/app.db 已生成"
else
  fail "建表失败" "请看 /tmp/db_init.log；常见原因是依赖没装全"
fi
echo ""

echo "5/10 服务能否启动并返回健康检查"
if [ -x .venv/bin/python ]; then
  nohup .venv/bin/python -m uvicorn server.main:app --port 8000 >/tmp/uvicorn.log 2>&1 &
  pid=$!
  sleep 5
  body=$(curl -s --max-time 5 http://127.0.0.1:8000/health)
  kill -TERM $pid >/dev/null 2>&1
  sleep 1
  kill -9 $pid >/dev/null 2>&1
  if echo "$body" | grep -q '"ok"'; then
    pass "健康检查返回: $body"
  else
    fail "健康检查不通，返回: ${body:-（空）}" "看 /tmp/uvicorn.log，多半是依赖缺失"
  fi
else
  fail "跳过（venv 未建）" "先完成第 2 项"
fi
echo ""

echo "6/10 首页是否有“发起模拟外呼”按钮"
if grep -q "发起模拟外呼" frontend/index.html; then
  pass "按钮已写入 frontend/index.html"
else
  fail "首页没有按钮" "联系我做补丁"
fi
echo ""

echo "7/10 识别演示脚本是否存在"
if [ -f tests/asr_demo.py ]; then pass "tests/asr_demo.py 存在"; else fail "缺失" "需要重新生成"; fi
echo ""

echo "8/10 合成演示脚本是否存在"
if [ -f tests/tts_demo.py ]; then pass "tests/tts_demo.py 存在"; else fail "缺失" "需要重新生成"; fi
echo ""

echo "9/10 .env 里的 Key 是否已填真值"
k=$(grep -E "^DASHSCOPE_API_KEY=" .env 2>/dev/null | cut -d= -f2-)
if echo "$k" | grep -q "^sk-" && ! echo "$k" | grep -q "在这里填"; then
  pass "DASHSCOPE_API_KEY 已填写（长度 ${#k}）"
else
  fail "Key 仍是占位或为空" "找组长拿 Key，写进 .env 的 DASHSCOPE_API_KEY="
fi
echo ""

echo "10/10 本地与远端是否同步"
if git rev-parse HEAD >/dev/null 2>&1; then
  local_h=$(git rev-parse --short HEAD)
  # 加超时保护：远端查询最多等 20 秒，超时就判为未过
  GIT_TERMINAL_PROMPT=0 git ls-remote origin >/tmp/lsremote.tmp 2>/dev/null &
  lp=$!
  n=0
  while kill -0 $lp 2>/dev/null && [ $n -lt 20 ]; do sleep 1; n=$((n+1)); done
  kill -9 $lp >/dev/null 2>&1
  remote_h=$(head -1 /tmp/lsremote.tmp 2>/dev/null | cut -c1-7)
  if [ -z "$remote_h" ]; then
    fail "连不上 GitHub（20 秒无响应）" "换个时间重跑本脚本，或检查网络"
  elif [ "$local_h" = "$remote_h" ]; then
    pass "本地 $local_h 与 GitHub $remote_h 一致"
  else
    fail "本地 $local_h / GitHub $remote_h 不一致" "执行: git push origin main"
  fi
else
  fail "不在 git 仓库里" "确认目录是 ~/Desktop/voice-agent"
fi
echo ""
echo "============================================"
echo " 通过 $ok 项，未过 $bad 项"
if [ $bad -eq 0 ]; then echo " Day2 全部达标"; else echo " 按上面 [未过] 后面的箭头提示逐项处理"; fi
echo "============================================"
