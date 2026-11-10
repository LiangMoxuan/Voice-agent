#!/usr/bin/env bash
# 一键把本地仓库连到你的 GitHub 私有仓库并推送。
# 用法：cd ~/Desktop/voice-agent && ./scripts/connect_github.sh
set -e
cd "$(dirname "$0")/.."

echo "======================================================"
echo " 把 voice-agent 连到 GitHub"
echo "======================================================"
echo "请先在浏览器完成：GitHub → New repository"
echo "  Repository name: voice-agent"
echo "  选 Private（不要 Public）"
echo "  勾 Add a README file  ◯ 不要勾"
echo "  Add .gitignore 选 None"
echo "  Choose a license 选 None"
echo "  → Create repository"
echo ""
echo "⚠️ 建仓库时【不要】勾 Add a README file —— 我们要推本地已有的 main。"
echo ""

read -r -p "把仓库地址粘贴到这里（形如 https://github.com/你的用户名/voice-agent.git）: " URL
URL="$(echo "$URL" | tr -d '[:space:]')"

case "$URL" in
  https://github.com/*.git) ;;
  https://github.com/*)    URL="${URL}.git" ;;
  *) echo "❌ 地址不像 GitHub 仓库地址，已退出。"; exit 1 ;;
esac

if git remote | grep -qx origin; then
  echo ">> 已存在 origin，更新为：$URL"
  git remote set-url origin "$URL"
else
  echo ">> 添加 origin：$URL"
  git remote add origin "$URL"
fi

echo ""
echo ">> 开始推送 main（下面若要求 Password，请粘贴你的 ghp_ 开头的 Personal Access Token）"
echo "   获取位置：https://github.com/settings/tokens → Generate new token (classic) → 勾 repo"
echo ""
git push -u origin main

echo ""
echo "======================================================"
echo " ✅ 推送成功。下一步："
echo " 1) 仓库 Settings → Collaborators → Add people"
echo "    把 A、B 的 GitHub 用户名加进来，权限选 Write"
echo " 2) 把仓库地址发到群里，让他们："
echo "    git clone $URL"
echo "======================================================"
