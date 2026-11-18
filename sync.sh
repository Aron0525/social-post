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

if ! git diff --cached --quiet; then
  git commit -q -m "$MSG" || { echo "提交失败"; exit 1; }
  echo "已提交: $MSG"
else
  echo "没有文件改动"
  if git rev-parse --verify -q '@{u}' >/dev/null 2>&1 && [ -z "$(git rev-list '@{u}..HEAD')" ]; then
    echo "远程已是最新，无需推送"
    exit 0
  fi
  echo "存在未推送的提交，继续推送"
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "未配置远程仓库，仅完成本地提交"
  exit 0
fi

if git push -q origin HEAD 2>/tmp/sync_push_err; then
  echo "已推送: $(git rev-parse --short HEAD)"
else
  # 推失败多半是 github.com 解析被污染，修一次再重试
  if [ -x ./fix_hosts.sh ] && ./fix_hosts.sh; then
    if git push -q origin HEAD 2>/tmp/sync_push_err; then
      echo "已推送: $(git rev-parse --short HEAD)"
      exit 0
    fi
  fi
  echo "推送失败:"
  cat /tmp/sync_push_err
  exit 1
fi
