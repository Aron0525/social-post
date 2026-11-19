# -*- coding: utf-8 -*-
"""热点监测：多源抓取 + 跨榜聚类 + 题材过滤。

对外只暴露 fetch_hot(limit, keep_politics) -> dict
定时任务通过 GET /hot 调用，缓存 5 分钟。
"""
import json
import re
import threading
import time
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"

# 硬排除：领导人、外交仪式、军队、会议。命中即整条丢弃。
HARD = [
    "习近平", "彭丽媛", "普京", "特朗普", "拜登", "元首", "APEC", "峰会", "会见", "会谈",
    "合影", "欢迎宴会", "阅兵", "军演", "解放军", "国防部", "外交部", "驻华", "领事",
    "人大", "政协", "国台办", "就职", "宣誓", "当选", "访问", "抵达", "降落", "同框",
    "中俄美", "中美俄", "国务院", "中央军委", "党代会", "政治局",
    # 政要与涉外场合
    "李在明", "鲁比奥", "韩侨", "总统特别代表", "军人", "空军一号", "仪仗队", "国宴",
    "外长", "大使", "使馆", "主权", "领土", "台独", "两岸", "涉台", "涉港",
    "总理", "首相", "主席", "总书记", "常委", "办公厅", "白宫", "克里姆林宫",
    "军方", "击落", "美军", "空袭", "导弹", "开火", "冲突升级", "停火", "战争",
]
# 软标记：政策类，可能藏着财经角度，默认保留但打标签。
SOFT = ["关税", "制裁", "出口管制", "反垄断", "补贴", "监管", "新规", "央行", "美联储"]

# 主题筛选：账号只写科技、财经、产业，其余热搜（娱乐、健康、社会猎奇）不主动取。
TECH = [
    "AI", "大模型", "人工智能", "算力", "芯片", "半导体", "光刻", "英伟达", "AMD", "英特尔",
    "台积电", "苹果", "iPhone", "华为", "小米", "OPPO", "vivo", "荣耀", "三星", "高通",
    "特斯拉", "马斯克", "比亚迪", "宁德", "新能源", "电池", "光伏", "储能", "机器人",
    "具身智能", "无人机", "火箭", "卫星", "量子", "6G", "5G", "数据中心", "云计算", "阿里云", "腾讯云",
    "OpenAI", "Anthropic", "Claude", "GPT", "Gemini", "DeepSeek", "Grok", "谷歌", "Meta",
    "微软", "亚马逊", "英特", "腾讯", "阿里", "字节", "京东", "拼多多", "美团", "百度",
    "网易", "快手", "B站", "小红书", "微信", "抖音", "电商", "直播", "游戏", "暴雪",
    "任天堂", "Switch", "Steam", "GTA", "股价", "A股", "港股", "美股", "涨停", "市值",
    "IPO", "上市", "融资", "估值", "财报", "营收", "裁员", "降本", "裁员潮", "芯片法案",
    "自动驾驶", "智驾", "电动车", "手机", "折叠屏", "操作系统", "鸿蒙", "开源", "程序员",
]

CACHE_TTL = 300
_cache = {"ts": 0, "data": None}
_lock = threading.Lock()


def _get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def _codelife(bid):
    d = _get(f"https://api.codelife.cc/api/top/list?lang=cn&id={bid}")
    out = []
    for i, x in enumerate(d.get("data", []), 1):
        out.append({
            "title": (x.get("title") or "").strip(),
            "hot": (x.get("hotValue") or "").strip(),
            "url": x.get("link") or "",
            "rank": i,
        })
    return out


def _baidu():
    d = _get("https://top.baidu.com/api/board?platform=wise&tab=realtime")
    out = []
    for card in d.get("data", {}).get("cards", []):
        for grp in card.get("content", []):
            for it in grp.get("content", []):
                out.append({
                    "title": (it.get("word") or "").strip(),
                    "hot": it.get("hotScore") or "",
                    "url": it.get("url") or "",
                    "rank": len(out) + 1,
                })
    return out


def _wscn():
    d = _get("https://api-one.wallstcn.com/apiv1/content/lives?channel=global-channel&limit=25")
    out = []
    for it in d.get("data", {}).get("items", []):
        t = (it.get("title") or it.get("content_text") or "").strip()
        if not t:
            continue
        out.append({"title": t[:120], "hot": "", "url": "", "ts": it.get("display_time"),
                    "rank": len(out) + 1})
    return out


def _rank_hot(rank):
    """榜单不给热度值时按名次折算，第一名约 500 万，避免无热度条目被排到末位。"""
    try:
        r = int(rank or 0)
    except (TypeError, ValueError):
        return 0.0
    return 5_000_000.0 / r if r > 0 else 0.0


SOURCES = [
    ("weibo", lambda: _codelife("KqndgxeLl9")),
    ("zhihu", lambda: _codelife("mproPpoq6O")),
    ("douyin", lambda: _codelife("Jb0vmloB1G")),
    ("baidu", _baidu),
    ("wscn", _wscn),
]

_STRIP = re.compile(r"[\s，。！？、：；\"'“”‘’（）()\[\]【】…—\-·|]+")


def _norm(s):
    return _STRIP.sub("", s)


def _bigrams(s):
    s = _norm(s)
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else {s}


def _similar(a, b):
    A, B = _bigrams(a), _bigrams(b)
    if not A or not B:
        return False
    inter = len(A & B)
    return inter / min(len(A), len(B)) >= 0.55


def _hot_num(v):
    """52万 / 780.8万 / 1357万 / 12345 -> 数值，便于排序"""
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v or "").strip()
    m = re.match(r"^([\d.]+)\s*([万亿]?)$", s)
    if not m:
        return 0.0
    n = float(m.group(1))
    return n * {"万": 1e4, "亿": 1e8, "": 1}[m.group(2)]


def _grabbing():
    raw, ok, fail = [], [], []
    threads = []

    def work(name, fn):
        try:
            rows = fn()
            for r in rows:
                r["source"] = name
            raw.extend(rows)
            ok.append((name, len(rows)))
        except Exception as e:
            fail.append((name, str(e)[:60]))

    for name, fn in SOURCES:
        t = threading.Thread(target=work, args=(name, fn), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join(timeout=15)
    return raw, dict(ok), dict(fail)


def _collect():
    """抓取 + 过滤 + 聚类，结果进缓存。返回完整结构，不做 limit/topic 裁剪。"""
    raw, ok, fail = _grabbing()
    dropped, flagged, kept = [], [], []
    for r in raw:
        t = r["title"]
        if not t:
            continue
        if any(k in t for k in HARD):
            r["risk"] = "politics"
            dropped.append(r)
            continue
        if any(k in t for k in SOFT):
            r["risk"] = "policy"
            flagged.append(r["title"])
        kept.append(r)

    clusters = []
    for r in kept:
        hit = None
        for c in clusters:
            if _similar(r["title"], c["title"]):
                hit = c
                break
        if hit:
            if r["source"] not in hit["sources"]:
                hit["sources"].append(r["source"])
            if _hot_num(r["hot"]) > _hot_num(hit["hot"]):
                hit["hot"] = r["hot"]
            if not hit["url"] and r["url"]:
                hit["url"] = r["url"]
            hit["variants"].append(r["title"][:40])
        else:
            clusters.append({
                "title": r["title"],
                "hot": r["hot"],
                "hot_num": _hot_num(r["hot"]) or _rank_hot(r.get("rank")),
                "url": r["url"],
                "sources": [r["source"]],
                "risk": r.get("risk", ""),
                "variants": [],
            })

    for c in clusters:
        hn = _hot_num(c["hot"])  # 跨榜合并后可能换了更大的热度值，有值才覆盖
        if hn:
            c["hot_num"] = hn
        c["cross"] = len(c["sources"])
        c["tech"] = any(k.lower() in c["title"].lower() for k in TECH)
        c["score"] = c["cross"] * 1e8 + c["hot_num"]

    clusters.sort(key=lambda x: (-x["cross"], -x["hot_num"]))

    return {
        "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "counts": ok,
        "failed": fail,
        "total_raw": len(raw),
        "dropped_politics": len(dropped),
        "policy_flagged": flagged[:10],
        "count": len(clusters),
        "items": clusters,
    }


def fetch_hot(limit=30, keep_politics=False, topic=None):
    """topic: None 全部 / 'tech' 只保留科技财经产业相关"""
    now = time.time()
    with _lock:
        data = _cache["data"] if (now - _cache["ts"] < CACHE_TTL) else None
        cached = data is not None
    if data is None:
        data = _collect()
        with _lock:
            _cache.update(ts=now, data=data)

    items = data["items"]
    if not keep_politics:
        items = [x for x in items if x.get("risk") != "politics"]
    if topic == "tech":
        items = [x for x in items if x.get("tech")]

    out = {k: v for k, v in data.items() if k != "items"}
    out["cached"] = cached
    out["topic"] = topic or "all"
    out["count"] = len(items)
    out["items"] = items[:max(limit, 1)]
    return out


if __name__ == "__main__":
    import sys
    tp = "tech" if "--tech" in sys.argv else None
    d = fetch_hot(limit=25, topic=tp)
    print(json.dumps({k: v for k, v in d.items() if k != "items"}, ensure_ascii=False, indent=1))
    for i, x in enumerate(d["items"], 1):
        print(f"{i:02d} [{x['cross']}榜] {x['title'][:44]} | {x['hot']} | {','.join(x['sources'])}")
