#!/usr/bin/env bash
# 修复 github.com 解析：DNS 常被污染到不可达地址，这里探测一组真实 IP 并写死 hosts
set -uo pipefail

HOSTS=/etc/hosts
CANDIDATES="140.82.113.3 140.82.112.3 140.82.114.3 20.27.177.113 20.200.245.247 57.155.223.240"

current=$(getent hosts github.com | awk '{print $1}' | head -1)
if [ -n "$current" ] && timeout 6 git -C /workspace ls-remote --heads origin >/dev/null 2>&1; then
  echo "github 解析正常: $current"
  exit 0
fi

for ip in $CANDIDATES; do
  if timeout 4 bash -c "echo > /dev/tcp/$ip/443" 2>/dev/null &&
     timeout 12 curl -s -m 10 -o /dev/null -w '%{http_code}' \
       "https://$ip/Aron0525/social-post.git/info/refs?service=git-upload-pack" \
       -H "Host: github.com" 2>/dev/null | grep -q '^200$'; then
    grep -v -E '[[:space:]]github\.com$' "$HOSTS" > /tmp/hosts.new 2>/dev/null
    printf '%s github.com\n%s api.github.com\n' "$ip" "$ip" >> /tmp/hosts.new
    cat /tmp/hosts.new > "$HOSTS" && cp "$HOSTS" /root/.user_hosts
    echo "已切换到 $ip"
    exit 0
  fi
done

echo "所有候选 IP 均不可用"
exit 1
