#!/usr/bin/env bash
# 一键提交并推送 /workspace 到 GitHub
# 用法: ./sync.sh "提交说明"    不传说明则用时间戳
set -uo pipefail

cd "$(dirname "$0")" || exit 1

MSG="${1:-}"
if [ -z "$MSG" ]; then
  MSG="更新 $(date '+%Y-%m-%d %H:%M')"
fi

# 暂存全部改动（.gitignore 已排除令牌、缓存、会话数据）
git add -A

if git diff --cached --quiet; then
  echo "没有改动，跳过提交"
  exit 0
fi

git commit -q -m "$MSG" || { echo "提交失败"; exit 1; }
echo "已提交: $MSG"

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "未配置远程仓库，仅完成本地提交"
  exit 0
fi

if git push -q origin HEAD 2>/tmp/sync_push_err; then
  echo "已推送: $(git rev-parse --short HEAD)"
else
  echo "推送失败:"
  cat /tmp/sync_push_err
  exit 1
fi
