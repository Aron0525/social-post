"""Local read-only style checker for kuangye-writing skill.

Reads a text file (or stdin with "-"), reports FAIL / WARN / INFO per paragraph.
Never modifies the input, never touches the network, never deletes anything.
"""
import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SENT_SPLIT = re.compile(r"[。！？!?；;]+")
UNIT_SPLIT = re.compile(r"\n\s*\n")

PATTERNS = {
    "中文冒号": (r"[：:]", "FAIL", "strict"),
    "破折号": (r"——|--|–", "FAIL", "always"),
    "感叹号": (r"[！!]", "FAIL", "always"),
    "省略号": (r"…|\.\.\.", "FAIL", "always"),
    "翻案句": (r"不是.{0,30}而是|并非.{0,30}而在于|与其说.{0,30}不如说|表面.{0,20}实际|看似.{0,20}实则|并不是.{0,30}而是|不在于.{0,20}而在于", "FAIL", "strict"),
    "洞察路标词": (r"说到底|说穿了|先说结论|更微妙的是|值得注意的是|从某种意义上说", "FAIL", "always"),
    "商业与模型黑话": (r"赋能|抓手|闭环|底层逻辑|颗粒度|对齐一下|打通|复盘到", "FAIL", "always"),
    "行动号召": (r"建议你|你应该|不妨|试试看|希望大家|祝你|愿你|加油|与君共勉", "FAIL", "always"),
    "总结段": (r"所以综上|综上|总之|以上就是|希望对你有帮助|希望能帮到你|希望这对你", "FAIL", "always"),
    "情态词": (r"可能|也许|大概|或许|我认为|我觉得|似乎|好像|某种程度上", "WARN", "always"),
    "绝对化断言": (r"永远不要|绝大多数|从来不|从不|绝不|永不|一定|所有|任何|一切|最|唯一", "INFO", "always"),
    "对称句": (r"越.{1,12}越|不.{1,8}不.{1,8}", "INFO", "always"),
}
COMPILED = {k: (re.compile(v[0]), v[1], v[2]) for k, v in PATTERNS.items()}
NUMBERED = re.compile(r"[0-9]+[、．.]|第[一二三四五六七八九十]+[、，]")
QUESTION_END = re.compile(r"[？?]\s*$")
ELLIPSIS_END = re.compile(r"(…|\.\.\.)\s*$")


def split_units(text):
    units = [u.strip() for u in UNIT_SPLIT.split(text) if u.strip()]
    if len(units) == 1 and "\n" in units[0]:
        units = [u.strip() for u in units[0].splitlines() if u.strip()]
    return units


def check_unit(text, strict):
    issues = []
    clean = text.replace("\n", "")
    sents = [s.strip() for s in SENT_SPLIT.split(clean) if s.strip()]
    sent_lens = [len(s) for s in sents]

    for name, (rx, level, scope) in COMPILED.items():
        if scope == "strict" and not strict:
            continue
        hits = rx.findall(clean)
        if hits:
            issues.append({"level": level, "rule": name, "detail": "命中 %d 处 %s" % (len(hits), "、".join(dict.fromkeys(str(h) for h in hits[:3])))})

    if ELLIPSIS_END.search(clean):
        issues.append({"level": "FAIL", "rule": "省略号收尾", "detail": "导出截断是假特征，生成稿不得使用"})

    length = len(clean)
    if length > 160:
        issues.append({"level": "FAIL", "rule": "总长", "detail": "%d 字，超过 160 字上限" % length})
    elif length > 120 or length < 20:
        issues.append({"level": "WARN", "rule": "总长", "detail": "%d 字，舒适区 20 至 120 字" % length})

    if sent_lens:
        if max(sent_lens) > 40:
            issues.append({"level": "FAIL", "rule": "句长", "detail": "最长 %d 字，超过 40 字" % max(sent_lens)})
        elif max(sent_lens) > 30 or min(sent_lens) < 12:
            issues.append({"level": "WARN", "rule": "句长", "detail": "区间 %d 至 %d 字，目标 12 至 30 字" % (min(sent_lens), max(sent_lens))})
    if len(sents) > 4:
        issues.append({"level": "FAIL", "rule": "句数", "detail": "%d 句，超过 4 句" % len(sents)})
    elif len(sents) > 3:
        issues.append({"level": "WARN", "rule": "句数", "detail": "%d 句，目标 1 至 3 句" % len(sents)})

    comma = clean.count("，")
    period = clean.count("。")
    if period:
        ratio = round(comma / period, 2)
        if ratio > 5:
            issues.append({"level": "WARN", "rule": "逗号句号比", "detail": "%.2f 比 1，判为流水句" % ratio})
        elif ratio < 1:
            issues.append({"level": "WARN", "rule": "逗号句号比", "detail": "%.2f 比 1，目标 2 比 1 至 3 比 1" % ratio})
    else:
        ratio = None
        issues.append({"level": "WARN", "rule": "句号", "detail": "无句号，检查是否未收束"})

    q = clean.count("？") + clean.count("?")
    if q:
        first = sents[0] if sents else ""
        if "？" not in first and "?" not in first:
            issues.append({"level": "WARN", "rule": "问句位置", "detail": "问句应压在首句"})
    if QUESTION_END.search(clean):
        issues.append({"level": "FAIL", "rule": "问号收尾", "detail": "设问只做开头钩子"})

    semi = clean.count("；")
    if semi > 2:
        issues.append({"level": "WARN", "rule": "分号", "detail": "%d 个，一条帖最多 2 个" % semi})

    numbered = NUMBERED.findall(clean)
    if numbered and strict:
        issues.append({"level": "WARN", "rule": "编号清单", "detail": "命中 %d 项，报数句默认用句号" % len(numbered)})

    return {
        "chars": length,
        "sentences": len(sents),
        "sentence_lengths": sent_lens,
        "comma": comma,
        "period": period,
        "comma_period_ratio": ratio,
        "questions": q,
        "issues": issues,
    }


def main():
    ap = argparse.ArgumentParser(description="旷野体写法校验，纯本地只读")
    ap.add_argument("path", help="稿件路径，或 - 表示标准输入")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--no-strict", action="store_true", help="放开与 human-writing 冲突的手法")
    ap.add_argument("--corpus", action="store_true", help="语料模式，跳过以省略号收尾的段落")
    args = ap.parse_args()
    strict = not args.no_strict

    if args.path == "-":
        text = sys.stdin.read()
        source = "stdin"
    else:
        p = Path(args.path)
        if not p.is_file():
            print("找不到文件 %s" % p, file=sys.stderr)
            return 2
        text = p.read_text(encoding="utf-8", errors="replace")
        source = str(p)

    units = split_units(text)
    results = []
    skipped = 0
    for i, unit in enumerate(units, 1):
        if args.corpus and ELLIPSIS_END.search(unit.replace("\n", "")):
            skipped += 1
            continue
        r = check_unit(unit, strict)
        r["unit"] = i
        r["preview"] = unit.replace("\n", " ")[:40]
        results.append(r)

    fails = sum(1 for r in results for x in r["issues"] if x["level"] == "FAIL")
    warns = sum(1 for r in results for x in r["issues"] if x["level"] == "WARN")
    summary = {
        "source": source,
        "strict": strict,
        "corpus_mode": args.corpus,
        "units": len(units),
        "checked": len(results),
        "skipped_truncated": skipped,
        "fail": fails,
        "warn": warns,
    }

    if args.json:
        print(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2))
    else:
        print("旷野体写法校验  %s" % source)
        print("严格模式 %s ｜ 语料模式 %s ｜ 段落 %d ｜ 已检 %d ｜ 跳过截断 %d" % ("开" if strict else "关", "开" if args.corpus else "关", len(units), len(results), skipped))
        print("FAIL %d ｜ WARN %d" % (fails, warns))
        print()
        for r in results:
            hard = [x for x in r["issues"] if x["level"] == "FAIL"]
            soft = [x for x in r["issues"] if x["level"] == "WARN"]
            info = [x for x in r["issues"] if x["level"] == "INFO"]
            print("[段 %d] %d 字 ｜ %d 句 ｜ 句长 %s ｜ 逗号句号 %s 比 1" % (r["unit"], r["chars"], r["sentences"], r["sentence_lengths"], r["comma_period_ratio"]))
            print("  %s" % r["preview"])
            for x in hard:
                print("  FAIL  %s  %s" % (x["rule"], x["detail"]))
            for x in soft:
                print("  WARN  %s  %s" % (x["rule"], x["detail"]))
            if info:
                print("  INFO  %s" % "；".join("%s(%s)" % (x["rule"], x["detail"]) for x in info))
            if not r["issues"]:
                print("  OK")
            print()
        print("FAIL 为硬规则违规，WARN 为风格偏离，INFO 为需人工确认的断言项或识别到的手法。")
        print("本脚本只读输入，未改动 %s" % source)

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
