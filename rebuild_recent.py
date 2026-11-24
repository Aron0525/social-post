#!/usr/bin/env python3
"""生成「最近六小时完整对话」+「项目全局对话脉络」两份文档。"""
import json, io, datetime, subprocess, collections, os

WS = '/workspace'
SESSION = '/root/.codebuddy/projects/workspace/2f8a7d30-9c21-4f0b-1d72-d4b584e11000.jsonl'
OUT6 = '/workspace/最近六小时对话.md'
OUTALL = '/workspace/项目对话脉络.md'

def git(*a):
    return subprocess.run(['git', '-C', WS] + list(a), capture_output=True, text=True).stdout

# ---------- 解析会话 ----------
msgs = []
for line in io.open(SESSION, encoding='utf-8'):
    line = line.strip()
    if not line:
        continue
    try:
        o = json.loads(line)
    except Exception:
        continue
    if o.get('type') != 'message':
        continue
    ts = o.get('timestamp')
    if not ts or not isinstance(ts, (int, float)):
        continue
    if ts > 1e12:
        ts /= 1000
    dt = datetime.datetime.fromtimestamp(ts)
    role = o.get('role')
    if role not in ('user', 'assistant'):
        continue
    c = o.get('content')
    txt = ''
    if isinstance(c, list):
        for b in c:
            if isinstance(b, dict) and b.get('type') in ('text', 'output_text', 'input_text'):
                txt += (b.get('text') or '') + '\n'
    txt = txt.strip()
    if not txt:
        continue
    # 逐块过滤：只丢纯提示块，保留同一 message 里的真实用户发言
    keep = []
    for b in c:
        if not isinstance(b, dict):
            continue
        bt = b.get('type')
        if bt not in ('text', 'output_text', 'input_text'):
            continue
        bt_txt = (b.get('text') or '').strip()
        if not bt_txt:
            continue
        if bt_txt.startswith(('<system-reminder', '<cb_summary>', '<conversation_history_summary>')):
            continue
        if 'compact-summary' in bt_txt[:200] or 'conversation_history_summary' in bt_txt[:200]:
            continue
        keep.append(bt_txt)
    txt = '\n'.join(keep).strip()
    if not txt:
        continue
    msgs.append((dt, role, txt))
msgs.sort(key=lambda x: x[0])

NOW = datetime.datetime(2026, 11, 24, 22, 10)
CUT6 = NOW - datetime.timedelta(hours=6)

# ---------- 工具调用统计（按时间桶）----------
tools = collections.Counter()
tool_by_hour = collections.defaultdict(collections.Counter)
for line in io.open(SESSION, encoding='utf-8'):
    line = line.strip()
    if not line:
        continue
    try:
        o = json.loads(line)
    except Exception:
        continue
    if o.get('type') != 'function_call':
        continue
    ts = o.get('timestamp')
    if not ts or not isinstance(ts, (int, float)):
        continue
    if ts > 1e12:
        ts /= 1000
    dt = datetime.datetime.fromtimestamp(ts)
    if dt < CUT6:
        continue
    n = o.get('name', '?')
    tools[n] += 1
    tool_by_hour[dt.strftime('%H:00')][n] += 1

# ---------- 产出数据 ----------
rows = [json.loads(l) for l in io.open(WS + '/news-digest/posts.jsonl', encoding='utf-8') if l.strip()]
byday = collections.defaultdict(collections.Counter)
for r in rows:
    rd = r.get('round', '')
    day = rd[:10] if len(rd) >= 10 and rd[:4].isdigit() else rd[:5]
    byday[day][r.get('src', 'v1')] += 1

commits = []
for ln in git('log', '--since=2026-11-24 16:00', '--format=%ad|%s',
              '--date=format:%m-%d %H:%M').strip().split('\n'):
    if ln.strip():
        d, s = ln.split('|', 1)
        commits.append((d.strip(), s))
commits.sort()

# ================= 文档一：最近六小时 =================
L = []
w = L.append
w('# 最近六小时完整对话')
w('')
w(f'> 窗口：**{CUT6:%Y-%m-%d %H:%M} → {NOW:%Y-%m-%d %H:%M}**（6 小时）')
w('> 数据源：本地沙箱完整会话记录（不只是本对话窗口）')
w('>')
w('> 说明：这 6 小时内本机沙箱只有 **1 个交互会话**（本对话），')
w('> 其余活动全部来自**云端定时任务**（每 2 小时一轮，在云端 sandbox 执行）。')
w('> 两条线的产出都汇总在下面第二节。')
w('')

w('## 一、本对话窗口的完整内容')
w('')
r6 = [m for m in msgs if m[0] >= CUT6]
users = [m for m in r6 if m[1] == 'user']
w(f'本窗口共 {len(r6)} 条消息（用户 {len(users)} 条，助手 {len(r6) - len(users)} 条）。')
w('')

w('### 你的发言（按时间）')
w('')
for dt, role, txt in r6:
    if role != 'user':
        continue
    w(f'**`{dt:%m-%d %H:%M}`**')
    w('')
    w(txt)
    w('')

w('### 我的动作轨迹（按时间）')
w('')
w('| 时间 | 动作 |')
w('| --- | --- |')
for dt, role, txt in r6:
    if role != 'assistant':
        continue
    w(f'| `{dt:%m-%d %H:%M}` | {txt.strip().splitlines()[0][:100]} |')
w('')

w('### 工具调用统计')
w('')
w('| 工具 | 次数 |')
w('| --- | --- |')
for k, v in tools.most_common():
    w(f'| {k} | {v} |')
w('')
w('按小时分布：')
w('')
w('| 小时 | 工具调用 | 主要动作 |')
w('| --- | --- | --- |')
for h in sorted(tool_by_hour):
    c = tool_by_hour[h]
    top = ', '.join(f'{k}×{v}' for k, v in c.most_common(3))
    w(f'| {h} | {sum(c.values())} | {top} |')
w('')

w('## 二、这六小时的实际产出')
w('')
w('### Git 提交')
w('')
w('| 时间 | 说明 |')
w('| --- | --- |')
for d, s in commits:
    w(f'| {d} | {s} |')
w('')

w('### 内容产出')
w('')
w('| 日期 | v1 速览 | v2 热点 | v3 博眼球 | v4 讲解 | 合计 |')
w('| --- | --- | --- | --- | --- | --- |')
for d in sorted(byday):
    if d[:5] != '11-24':
        continue
    c = byday[d]
    w(f'| {d} | {c.get("v1",0)} | {c.get("v2",0)} | {c.get("v3",0)} | {c.get("v4",0)} | {sum(c.values())} |')
w('')
day24 = [r for r in rows if r.get('round', '').startswith('2026-11-24')]
w(f'11-24 当天累计 {len(day24)} 条，其中 16:00 之后新增 '
  f'{sum(1 for r in day24 if r.get("round","")[11:13].isdigit() and int(r["round"][11:13]) >= 16)} 条。')
w('')
w('### 16:00 之后新增条目')
w('')
NAME = {'v1': '速览', 'v2': '热点', 'v3': '眼球', 'v4': '讲解'}
for r in day24:
    rd = r.get('round', '')
    if not (rd[11:13].isdigit() and int(rd[11:13]) >= 16):
        continue
    wd = len(r.get('text', '').replace('\n', '').replace(' ', ''))
    w(f'- `{rd[11:]}` **[{NAME.get(r.get("src"), r.get("src"))}]** {r.get("title","")} — {wd} 字')
w('')

io.open(OUT6, 'w', encoding='utf-8').write('\n'.join(L))
print('已生成:', OUT6, os.path.getsize(OUT6), '字节')

# ================= 文档二：项目全局脉络 =================
A = []
w = A.append
w('# 项目对话脉络 · 全部四天')
w('')
w('> 数据源：本地沙箱完整会话记录（11-15 起）')
w('')

w('## 一、你的全部发言（按时间，一条不漏）')
w('')
w('| 时间 | 发言 |')
w('| --- | --- |')
for dt, role, txt in msgs:
    if role != 'user':
        continue
    one = txt.replace('\n', ' ')
    one = one[:220] + ('…' if len(one) > 220 else '')
    w(f'| `{dt:%m-%d %H:%M}` | {one} |')
w('')

w('## 二、按天分组的完整原文')
w('')
bydaymsg = collections.defaultdict(list)
for dt, role, txt in msgs:
    bydaymsg[dt.strftime('%m-%d')].append((dt, role, txt))
for d in sorted(bydaymsg):
    items = bydaymsg[d]
    nu = sum(1 for _, r, _ in items if r == 'user')
    w(f'### {d} — {len(items)} 条消息（你 {nu} 条）')
    w('')
    for dt, role, txt in items:
        tag = '用户' if role == 'user' else '助手'
        w(f'**`{dt:%H:%M}` {tag}**')
        w('')
        w(txt)
        w('')

io.open(OUTALL, 'w', encoding='utf-8').write('\n'.join(A))
print('已生成:', OUTALL, os.path.getsize(OUTALL), '字节')
print()
print('用户发言总数:', sum(1 for _, r, _ in msgs if r == 'user'))
print('助手回复总数:', sum(1 for _, r, _ in msgs if r == 'assistant'))
print('覆盖天数:', sorted(bydaymsg.keys()))
