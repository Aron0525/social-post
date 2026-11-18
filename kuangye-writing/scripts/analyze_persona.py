# -*- coding: utf-8 -*-
"""从 posts.jsonl 生成作者画像的量化证据快照。

纯本地只读，不联网，不改动输入。默认读交付包内 data/posts.jsonl，
也可把源工作区的 posts.jsonl 路径作为第一个参数传入。

    python scripts/analyze_persona.py
    python scripts/analyze_persona.py E:/workbuddy/杂/books/kuangyezhixin/posts.jsonl

输出写到 audit/persona_stats.md，终端只打印摘要。
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
PKG = HERE.parents[1]
DEFAULT_CORPUS = PKG / "data" / "posts.jsonl"
OUT = PKG / "audit" / "persona_stats.md"

TOPICS = {
    "关系与边界": r"关系|远离|断联|不联系|朋友|相处|圈子|人际|合群|得罪",
    "金钱与生存": r"钱|穷|富|收入|赚钱|存钱|资产|经济|工资|供养|积蓄|阶层",
    "自我处境": r"自己|内耗|情绪|孤独|低谷|成长|命运|人生|消耗|清醒",
    "家庭与教育": r"父母|孩子|家庭|教育|婚姻|原生|儿子|女儿|夫妻",
    "识人与判断": r"人性|看透|看清|识人|本质|真相|格局|认知|层次",
}

MARKERS = {
    "第二人称你": r"你",
    "绝对化词": r"永远|从来|一定|所有|凡是|绝对|根本|全都|没有人|每个人|任何",
    "情态与 hedging": r"可能|也许|大概|似乎|我觉得|某种程度上|或许|大概|应该会",
    "祈使与劝止": r"不要|别再|别把|远离|记住|你要|只需要|少去",
    "问号": r"[？?]",
    "翻案句": r"不是.{0,30}而是|并非.{0,30}而在于|与其说.{0,30}不如说",
    "越字对举": r"越.{1,12}越",
    "因果连接": r"因为|所以|因此|于是",
    "群体号召": r"让我们一起|愿我们|希望大家|与君共勉",
}


def load(path):
    posts = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                posts.append(json.loads(line))
    return posts


def is_full(post):
    return not post["text"].rstrip().endswith(("…", "..."))


def clip(text, limit=76):
    flat = text.replace("\n", " ")
    return flat if len(flat) <= limit else flat[:limit] + "…"


def pct(n, total):
    return f"{n / total * 100:.1f}%" if total else "0.0%"


def sample_for(posts, pattern, limit=3):
    rx = re.compile(pattern)
    picked = [p for p in posts if 18 <= p["chars"] <= 90 and rx.search(p["text"])]
    return picked[:limit]


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CORPUS
    if not path.exists():
        print("语料不存在", path)
        print("把 posts.jsonl 放到 ", DEFAULT_CORPUS, " 或传入路径参数")
        return 1

    posts = load(path)
    full = [p for p in posts if is_full(p)]
    total = len(posts)

    lines = [
        "# 作者画像证据快照",
        "",
        f"> 由 `scripts/analyze_persona.py` 从 `{path.name}` 生成。纯本地只读。",
        "",
        "## 口径",
        "",
        f"- 全部帖 {total} 条，完整帖 {len(full)} 条，截断帖 {total - len(full)} 条。",
        "- 主题与语气占比的分母是全部帖。收尾与引用样本只从完整帖取。",
        "- 截断帖以省略号收尾，是 140 字上限造成的导出截断，不参与收尾与画像判断。",
        "",
        "## 主题分布",
        "",
        "| 主题 | 命中帖数 | 占比 |",
        "| --- | --- | --- |",
    ]
    for name, pattern in TOPICS.items():
        rx = re.compile(pattern)
        n = sum(1 for p in posts if rx.search(p["text"]))
        lines.append(f"| {name} | {n} | {pct(n, total)} |")

    lines += ["", "## 语气与判断标记", "", "| 标记 | 命中帖数 | 占比 |", "| --- | --- | --- |"]
    for name, pattern in MARKERS.items():
        rx = re.compile(pattern)
        n = sum(1 for p in posts if rx.search(p["text"]))
        lines.append(f"| {name} | {n} | {pct(n, total)} |")

    lines += ["", "## 各主题可回查样本", "", "样本一律取自完整帖，18 至 90 字，按帖子 id 顺序取前 3 条。", ""]
    for name, pattern in TOPICS.items():
        lines += [f"### {name}", ""]
        for p in sample_for(full, pattern):
            lines.append(
                f"- `{p['id']}` ｜ {p['date']} ｜ 第 {p['page']} 页 ｜ {p['chars']} 字 ｜ {clip(p['text'])}"
            )
        lines.append("")

    lengths = sorted(p["chars"] for p in full)
    mid = lengths[len(lengths) // 2] if lengths else 0
    lines += [
        "## 完整帖长度",
        "",
        f"- 完整帖 {len(full)} 条，长度中位 {mid} 字，最短 {lengths[0] if lengths else 0} 字，"
        f"最长 {lengths[-1] if lengths else 0} 字。",
        "",
        "## 未覆盖项",
        "",
        "- 作者生平、职业、年龄、地域、教育背景，语料里没有，不推断。",
        "- 真实对话记录、回复他人的方式、处理分歧的实录，语料是单向发布短帖，没有这类证据。",
        "- 协作风格只能由表达习惯推导，推导部分须在 PERSONA.md 里标为 B 层。",
        "",
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")

    print("语料", path)
    print("全部帖", total, "完整帖", len(full), "截断帖", total - len(full))
    for name, pattern in TOPICS.items():
        rx = re.compile(pattern)
        n = sum(1 for p in posts if rx.search(p["text"]))
        print(f"  {name}: {n} / {pct(n, total)}")
    for name, pattern in MARKERS.items():
        rx = re.compile(pattern)
        n = sum(1 for p in posts if rx.search(p["text"]))
        print(f"  {name}: {n} / {pct(n, total)}")
    print("已写", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
