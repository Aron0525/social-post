#!/usr/bin/env python3
"""为每一条内容生成英文版本（en_title / en_text），写入 posts.jsonl。

用法：
    python3 translate_en.py              # 全量（断点续跑）
    python3 translate_en.py --limit 20   # 只处理前 20 条待翻译的
    python3 translate_en.py --workers 4  # 并发数
"""
import concurrent.futures
import json, io, os, re, subprocess, sys, argparse, time
import threading

P = '/workspace/news-digest/posts.jsonl'
MODEL = os.environ.get('EN_MODEL', 'minimax-m3.1-flash')
LOCK = threading.Lock()

SYSTEM_PROMPT = """You are a professional Chinese-to-English translator who specializes in social media posts for X (Twitter).

For each item you receive, translate both "title" and "text" into natural English.

Hard requirements:
1. MARKER: Every item's "title" begins with a marker of the form [[M0001]]. You MUST keep that exact marker string at the very beginning of the translated title, unchanged. It is an internal tracking tag, not part of the content. Never alter, reorder, drop, or invent markers. Each output element must carry the same marker as its input element.
2. Preserve paragraph breaks. A paragraph break in the source is exactly two characters: \\n\\n. Keep that exact separator in the output. Never merge paragraphs, never split one.
3. Keep every number, percentage, currency amount, date, ticker, product name and proper noun exactly accurate. Do not round, convert units, or paraphrase figures.
4. Match the register of the source. If the Chinese is casual and conversational, the English must be casual and conversational. If it is a formal report, keep it formal. Do NOT upgrade casual writing into corporate English.
5. If the source contains a rhetorical question or a punchline, preserve that rhetorical structure in English.
6. Do not add explanations, do not add a preamble, do not add markdown fences, do not add commentary.

Output format: a single valid JSON array and nothing else.
Each element: {"id": <the same id you received>, "title": "[[Mxxxx]] english title", "text": "<english text>"}
"""

MARK_RE = re.compile(r'\[\[(M\d{4})\]\]')


def load_rows():
    return [json.loads(l) for l in io.open(P, encoding='utf-8') if l.strip()]


def save_rows(rows):
    tmp = P + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    os.replace(tmp, P)


def translate_batch(items, model=MODEL, retries=3, home=None):
    """items: list of dict(id,marker,title,text) -> list of dict(id,title,text)

    home: 独立的 CODEBUDDY_HOME 目录。并发时必须传，否则多个 CLI 进程
    会共用同一份 session 状态，导致输出串味（实测会把别的批次的译文返回）。
    """
    payload = json.dumps(items, ensure_ascii=False)
    prompt = SYSTEM_PROMPT + "\nINPUT:\n" + payload
    env = dict(os.environ)
    if home:
        os.makedirs(home, exist_ok=True)
        env['CODEBUDDY_HOME'] = home
    last_err = None
    for attempt in range(retries):
        try:
            cp = subprocess.run(
                ['codebuddy', '-p', '--model', model, '--tools', '',
                 '--output-format', 'text', prompt],
                capture_output=True, text=True, timeout=600, env=env)
            out = (cp.stdout or '').strip()
            if not out:
                last_err = 'empty stdout: ' + (cp.stderr or '')[:200]
                time.sleep(3 + attempt * 5)
                continue
            # 提取 JSON 数组
            i = out.find('[')
            j = out.rfind(']')
            if i < 0 or j < 0:
                last_err = 'no json array in output: ' + out[:200]
                time.sleep(2)
                continue
            arr = json.loads(out[i:j + 1])
            if not isinstance(arr, list) or not arr:
                last_err = 'bad array'
                continue
            return arr
        except subprocess.TimeoutExpired:
            last_err = 'timeout'
            time.sleep(5)
        except Exception as e:
            last_err = repr(e)
            time.sleep(3)
    raise RuntimeError('translate_batch failed: %s' % last_err)


def source_fingerprint(text):
    """从中文原文提取指纹：数字集合 + 段落数 + 首段特征字符。

    用于校验返回的英文确实对应这条源文，防止并发串味或模型跑偏。
    """
    nums = set(re.findall(r'\d+(?:[.,]\d+)*%?', text))
    paras = text.count('\n\n')
    head = re.sub(r'\s', '', text)[:6]
    return nums, paras, head


RE_PCT = re.compile(r'(\d+(?:\.\d+)?)\s*%')
RE_YEAR = re.compile(r'(?<!\d)(19|20)\d{2}(?!\d)')
RE_DATE_CN = re.compile(r'(\d{1,2})\s*月\s*(\d{1,2})\s*日')
RE_DATE_EN = re.compile(r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(\d{1,2})')


def _norm_pct(m):
    try:
        return round(float(m.group(1)), 4)
    except Exception:
        return None


def check_pair(src, en_text):
    """校验英文确实对应这条中文源文。

    注意：不能简单要求"源文所有数字都出现在英文里"，因为正常翻译就会改变数字形态：
      11月17日 -> November 17  （月的数字 11 必然消失）
      2.5亿美元 -> $250 million （量词换算后数值变了）
      810亿美元 -> $81 billion  （同上）
    所以只对"不会被换算的数字"做硬校验：百分比、4 位年份。
    其余用数量比 + 专有名词覆盖率做软校验。
    """
    if not en_text or len(en_text.strip()) < 10:
        return False, 'empty'
    if src.count('\n\n') != en_text.count('\n\n'):
        return False, 'para-mismatch'

    # 1) 百分比必须完全一致
    src_pct = sorted(_norm_pct(m) for m in RE_PCT.finditer(src))
    en_pct = sorted(_norm_pct(m) for m in RE_PCT.finditer(en_text))
    if src_pct and len(src_pct) == len(en_pct):
        if src_pct != en_pct:
            return False, 'pct-mismatch'
    elif src_pct and len(en_pct) < len(src_pct) * 0.7:
        return False, 'pct-missing'

    # 2) 4 位年份必须一致
    src_years = sorted(set(re.findall(r'(?<!\d)((?:19|20)\d{2})(?!\d)', src)))
    en_years = sorted(set(re.findall(r'(?<!\d)((?:19|20)\d{2})(?!\d)', en_text)))
    if src_years:
        lost = [y for y in src_years if y not in en_years]
        if len(lost) > len(src_years) * 0.34:
            return False, 'year-mismatch'

    # 3) 数字密度：英文里的数字个数不应远少于中文
    src_n = len(re.findall(r'\d', src))
    en_n = len(re.findall(r'\d', en_text))
    if src_n >= 4 and en_n < src_n * 0.45:
        return False, 'num-density'

    # 4) 专有名词覆盖：源文里的英文大写词应在英文里出现
    props = set(re.findall(r'\b[A-Z][A-Za-z0-9]{2,}\b', src))
    props = {p for p in props if p.lower() not in
             ('the', 'this', 'that', 'these', 'those', 'and', 'but', 'for', 'are', 'not')}
    if props:
        missing = [p for p in props if p.lower() not in en_text.lower()]
        if len(missing) > len(props) * 0.5:
            return False, 'prop-mismatch'

    return True, 'ok'


def worker(batch, results, stats, home):
    """并发跑一批。任何一条配不上（标记缺失/校验不过），单独重试该条。

    实测并发下模型偶尔会返回别的批次的译文（内容对但条目错）。
    哨兵标记 + 数字/段落校验能把这种错位挡下来，挡不下来的逐条串行重试。
    """
    def run(items, h):
        arr = translate_batch(items, home=h)
        by_marker = {}
        for it in arr:
            if not isinstance(it, dict):
                continue
            ti = (it.get('title') or '')
            m = MARK_RE.search(ti)
            if not m:
                continue
            by_marker[m.group(1)] = {
                'title': MARK_RE.sub('', ti).strip(),
                'text': (it.get('text') or '').strip(),
            }
        return by_marker

    def collect(by_marker, items, out_ok, quiet=False):
        for item in items:
            mk = item['marker']
            key = (MARK_RE.search(mk).group(1) if MARK_RE.search(mk) else mk)
            g = by_marker.get(key)
            if not g:
                if not quiet:
                    with LOCK:
                        stats['errors'].append('no-marker %s | %s'
                                               % (mk, item['title'][:26]))
                continue
            ok, reason = check_pair(item['text'], g['text'])
            if not ok:
                if not quiet:
                    with LOCK:
                        stats['errors'].append('reject %s %s | %s'
                                               % (mk, reason, item['title'][:26]))
                continue
            out_ok[item['id']] = {'title': g['title'], 'text': g['text']}

    try:
        got = {}
        collect(run(batch, home), batch, got)

        # 补跑 1：配不上的条目逐条重试（单条输入，串行）
        missing = [it for it in batch if it['id'] not in got]
        for item in missing:
            try:
                bm = run([item], home)
            except Exception:
                bm = {}
            if bm:
                collect(bm, [item], got, quiet=True)

        # 补跑 2：仍失败的，用独立 home 再试一次
        still = [it for it in batch if it['id'] not in got]
        for item in still:
            try:
                bm = run([item], home + '_r2')
            except Exception:
                bm = {}
            if bm:
                collect(bm, [item], got, quiet=True)

        with LOCK:
            results.update(got)
            stats['ok'] += len(got)
            stats['fail'] += len(batch) - len(got)
            if len(still):
                stats['errors'].append('UNRESOLVED %d: %s'
                                       % (len(still),
                                          ' | '.join(s['title'][:20] for s in still)))
    except Exception as e:
        with LOCK:
            stats['fail'] += len(batch)
            stats['errors'].append(str(e)[:200])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--batch', type=int, default=10)
    ap.add_argument('--model', default=MODEL)
    args = ap.parse_args()

    rows = load_rows()
    todo = [i for i, r in enumerate(rows)
            if not (r.get('en_text') or '').strip()]
    if args.limit:
        todo = todo[:args.limit]
    print('[translate] 待翻译 %d 条 / 总 %d 条' % (len(todo), len(rows)), flush=True)
    if not todo:
        print('[translate] 全部已完成')
        return

    batches = []
    for k in range(0, len(todo), args.batch):
        idxs = todo[k:k + args.batch]
        batch = []
        for j, i in enumerate(idxs):
            r = rows[i]
            marker = '[[M%04d]]' % (j + 1)
            batch.append({'id': j, 'marker': marker,
                          'title': marker + ' ' + r.get('title', ''),
                          'text': r.get('text', '')})
        batches.append((idxs, batch))

    results = {}
    stats = {'ok': 0, 'fail': 0, 'errors': []}
    done = 0
    t0 = time.time()
    home_root = '/tmp/cb_en_homes'
    os.makedirs(home_root, exist_ok=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(worker, batch, results, stats,
                          os.path.join(home_root, 'b%d' % k))
                for k, (_, batch) in enumerate(batches)]
        for fut in concurrent.futures.as_completed(futs):
            fut.result()
            done += 1
            if done % 5 == 0 or done == len(batches):
                print('[translate] 批次 %d/%d | 成功 %d 失败 %d | %.0fs'
                      % (done, len(batches), stats['ok'], stats['fail'],
                         time.time() - t0), flush=True)

    # 回写
    applied = 0
    for k, (idxs, batch) in enumerate(batches):
        for j, i in enumerate(idxs):
            got = results.get(j)
            if not got:
                continue
            rows[i]['en_title'] = got['title']
            rows[i]['en_text'] = got['text']
            applied += 1
    save_rows(rows)
    print('[translate] 回写 %d 条 | 失败 %d 条 | 用时 %.0fs'
          % (applied, stats['fail'], time.time() - t0), flush=True)
    for e in stats['errors'][:5]:
        print('  err:', e, flush=True)


if __name__ == '__main__':
    main()
