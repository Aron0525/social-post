#!/bin/bash
# 重启 news-digest 服务。用独立进程组，避免调用方的 kill 连带影响。
cd /workspace/news-digest || exit 1

# 只杀真正监听 3000 的进程
PIDS=$(ps -eo pid,args | awk '/python3 app\/server\.py|server\.py/ && !/awk/ {print $1}')
if [ -n "$PIDS" ]; then
  for p in $PIDS; do kill "$p" 2>/dev/null; done
  sleep 2
  for p in $PIDS; do kill -9 "$p" 2>/dev/null; done
fi

setsid nohup python3 app/server.py > /tmp/newsd.log 2>&1 < /dev/null &
disown

for i in $(seq 1 15); do
  sleep 1
  if curl -sS --max-time 3 "http://127.0.0.1:3000/count" > /dev/null 2>&1; then
    echo "服务已就绪：$(curl -sS --max-time 3 http://127.0.0.1:3000/count)"
    exit 0
  fi
done

echo "启动失败，日志："
tail -20 /tmp/newsd.log
exit 1
