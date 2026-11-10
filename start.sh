#!/usr/bin/env bash
# 兜底启动脚本（不用 Docker 时用）。用法：./start.sh
set -e
cd "$(dirname "$0")"

PY=${PY:-python3.12}
command -v "$PY" >/dev/null 2>&1 || PY=python3

if [ ! -d .venv ]; then
  echo ">> 创建虚拟环境"
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo ">> 安装依赖"
pip install -q -r requirements.txt

[ -f .env ] || { cp .env.example .env; echo ">> 已生成 .env，请先填入 API Key 再重启"; }

echo ">> 初始化数据库"
python -m server.db init

echo ">> 启动服务 http://localhost:8000"
exec uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
