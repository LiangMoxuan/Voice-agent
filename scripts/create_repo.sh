#!/usr/bin/env bash
# 用 API 建仓库 —— 绕开 github.com 网页（网页在国内常因 TLS 极慢而"创建失败"）
# 用法：cd ~/Desktop/voice-agent && ./scripts/create_repo.sh
set -e
cd "$(dirname "$0")/.."

NAME="voice-agent"

echo "======================================================"
echo " 用命令行建私有仓库（不依赖网页，快 20 倍）"
echo "======================================================"
echo " 1) GitHub   （需要 ghp_ 开头的 Personal Access Token，权限勾 repo）"
echo " 2) Gitee 码云（国内访问快，今天就能让队友拉；需要「私人令牌」，权限勾 projects）"
echo "======================================================"
read -r -p "选平台 [1/2，直接回车 = 1]: " PLAT
PLAT="${PLAT:-1}"

if [ "$PLAT" = "2" ]; then
  HOST="gitee.com"; API="https://gitee.com/api/v5"
  echo ""
  echo "Gitee 令牌获取：https://gitee.com/profile/personal_access_tokens → 生成新令牌 → 勾 projects"
else
  HOST="github.com"; API="https://api.github.com"
  echo ""
  echo "GitHub 令牌获取：https://github.com/settings/tokens → Generate new token (classic) → 勾 repo"
fi

read -r -s -p "把令牌粘贴到这里（输入时不显示，粘完按回车）: " TOKEN
echo ""
[ -z "$TOKEN" ] && { echo "❌ 没收到令牌，退出。"; exit 1; }

# --- 1. 验证令牌 + 拿到用户名 ---
if [ "$PLAT" = "2" ]; then
  LOGIN=$(curl -s --max-time 15 "$API/user?access_token=$TOKEN" | sed -n 's/.*"login":"([^"]*)".*/\1/p')
else
  LOGIN=$(curl -s --max-time 15 -H "Authorization: token $TOKEN" "$API/user" | sed -n 's/.*"login": *"([^"]*)".*/\1/p')
fi
[ -z "$LOGIN" ] && { echo "❌ 令牌无效或没权限。请重新生成（勾 repo / projects）。"; exit 1; }
echo ">> 已登录为：$LOGIN"

# --- 2. 建私有仓库 ---
echo ">> 正在创建私有仓库 $NAME ..."
if [ "$PLAT" = "2" ]; then
  RESP=$(curl -s --max-time 25 -X POST "$API/user/repos" \
    -d "access_token=$TOKEN" -d "name=$NAME" -d "private=true" \
    -d "description=智语外呼-人工智能+创新大赛")
else
  RESP=$(curl -s --max-time 25 -X POST -H "Authorization: token $TOKEN" \
    -H "Accept: application/vnd.github+json" "$API/user/repos" \
    -d "{\"name\":\"$NAME\",\"private\":true,\"description\":\"智语外呼-人工智能+创新大赛\"}")
fi

if echo "$RESP" | grep -q '"name": *"'"$NAME"'", *"private": *true'; then
  echo ">> ✅ 私有仓库创建成功"
elif echo "$RESP" | grep -qi "already exists"; then
  echo ">> 仓库已存在，直接复用（不会覆盖任何东西）"
else
  echo ">> ⚠️ 返回内容如下，请核对："
  echo "$RESP" | head -c 600
  echo ""
fi

# --- 3. 配 remote 并推送 ---
URL="https://$HOST/$LOGIN/$NAME.git"
if git remote | grep -qx origin; then
  git remote set-url origin "$URL"
else
  git remote add origin "$URL"
fi
echo ">> remote origin = $URL"
echo ""

# 顺手把提交身份配好（用 GitHub/Gitee 的 noreply 邮箱，不暴露真实邮箱）
git config user.name "$LOGIN"
git config user.email "$LOGIN@users.noreply.$HOST"
echo ">> 提交身份已设为：$LOGIN"

echo ""
echo ">> 开始推送 main。若提示 Password，把刚才那个令牌再粘一次即可。"
echo ""
git push -u origin main

echo ""
echo "======================================================"
echo " ✅ 完成。接下来加队友："
if [ "$PLAT" = "2" ]; then
  echo " 打开 https://gitee.com/$LOGIN/$NAME → 管理 → 仓库成员管理"
  echo " 添加 A、B 为「开发者」（开发者才有推送权限）"
else
  echo " 打开 https://github.com/$LOGIN/$NAME/settings/access"
  echo " Add people → 填 A、B 的用户名 → 权限选 Write"
fi
echo ""
echo " 让队友克隆：git clone $URL"
echo "======================================================"
