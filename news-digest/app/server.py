import json
import os
import re
import subprocess
import sys
import threading
from flask import Flask, request, jsonify, Response

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hotwatch  # noqa: E402

app = Flask(__name__)

DATA_FILE = "/workspace/news-digest/posts.jsonl"
PAGE_FILE = "/workspace/news-digest/记录.html"
TOKEN_FILE = "/workspace/news-digest/.sync_token"
CORPUS_FILE = "/workspace/news-digest/corpus/corpus.json"

ALLOWED_ST = {"new", "overlap", "same"}
ALLOWED_SRC = {"v1", "v2", "v3", "v4"}
REQUIRED = ("round", "title", "st", "note", "text")
OPTIONAL = ("link",)  # v4 讲解人关联的 v1 标题，用于在速览栏内联展示


def read_token():
    try:
        return open(TOKEN_FILE, encoding="utf-8").read().strip()
    except Exception:
        return ""


def git_sync_async(message):
    """写入后在后台提交并推送，不阻塞接口响应。失败只记日志。"""
    if os.environ.get("GIT_AUTOSYNC", "1") != "1":
        return

    def run():
        try:
            with open("/workspace/news-digest/.git-sync.log", "a", encoding="utf-8") as log:
                subprocess.run(
                    ["/workspace/sync.sh", message],
                    cwd="/workspace",
                    stdout=log,
                    stderr=log,
                    timeout=120,
                )
        except Exception as e:
            try:
                with open("/workspace/news-digest/.git-sync.log", "a", encoding="utf-8") as log:
                    log.write(f"[{message}] sync failed: {e}\n")
            except Exception:
                pass

    threading.Thread(target=run, daemon=True).start()


def load_rows():
    rows = []
    try:
        for line in open(DATA_FILE, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    except FileNotFoundError:
        pass
    return rows


def norm(s):
    return re.sub(r"[\s\u3000，。、：；！？（）()\[\]【】“”‘’\"'0-9a-zA-Z]+", "", s or "")


def similar(a, b):
    """标题相似判定：8 字以上公共前缀，或汉字 bigram Jaccard >= 0.55"""
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    n = 0
    for x, y in zip(na, nb):
        if x != y:
            break
        n += 1
    if n >= 8:
        return True
    sa = {na[i:i + 2] for i in range(len(na) - 1)}
    sb = {nb[i:i + 2] for i in range(len(nb) - 1)}
    if sa and sb:
        j = len(sa & sb) / len(sa | sb)
        if j >= 0.55:
            return True
    return False


@app.after_request
def add_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/")
def page():
    with open(PAGE_FILE, "rb") as f:
        return Response(f.read(), mimetype="text/html")


@app.route("/posts.jsonl")
def data():
    with open(DATA_FILE, "rb") as f:
        return Response(f.read(), mimetype="text/plain")


@app.route("/list")
def list_all():
    """给定时任务做判重用的全量已有记录。"""
    rows = load_rows()
    out = []
    for i, r in enumerate(rows, 1):
        out.append({
            "i": i,
            "round": r.get("round", ""),
            "title": r.get("title", ""),
            "st": r.get("st", ""),
            "src": r.get("src", "v1"),
            "link": r.get("link", ""),
            "note": r.get("note", "")[:120],
            "text": r.get("text", "")[:160],
        })
    return jsonify(total=len(out), items=out)


@app.route("/corpus")
def corpus():
    """给定时任务做照抄用的原帖清单。

    每条含原帖全文、段落数、每段句数、抄的什么手法，以及一条同格式的新稿示范。
    任务按 orig_text 的段落结构复制，只换内容。
    """
    try:
        with open(CORPUS_FILE, "rb") as f:
            return Response(f.read(), mimetype="application/json")
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500


@app.route("/hot")
def hot():
    """热点监测：五源抓取 + 跨榜聚类 + 题材过滤。
    ?limit=30  返回条数
    ?topic=tech  只看科技财经产业
    ?politics=1  保留已标记的时政条目（仅供人工核查，正常不使用）
    """
    limit = request.args.get("limit", "30")
    try:
        limit = max(1, min(80, int(limit)))
    except ValueError:
        limit = 30
    topic = request.args.get("topic") or None
    keep = request.args.get("politics") == "1"
    try:
        data = hotwatch.fetch_hot(limit=limit, keep_politics=keep, topic=topic)
    except Exception as e:
        return jsonify(ok=False, error=str(e)[:200]), 500
    return jsonify(ok=True, **data)


@app.route("/append", methods=["POST"])
def append():
    tok = read_token()
    if not tok or request.headers.get("X-Sync-Token") != tok:
        return jsonify(ok=False, error="unauthorized"), 401
    body = request.get_data(as_text=True)
    if not body or len(body) > 200_000:
        return jsonify(ok=False, error="invalid body"), 400

    force = request.args.get("force") == "1"
    existing = load_rows()
    added, errors, dups = 0, [], []

    for line in body.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            errors.append("invalid json")
            continue
        if any(k not in row for k in REQUIRED) or row.get("st") not in ALLOWED_ST:
            errors.append("missing fields or bad st")
            continue
        src = str(row.get("src", "v1"))
        if src not in ALLOWED_SRC:
            src = "v1"
        # v4 讲解人用 link 指向它所讲解的 v1 标题，展示时并入速览栏
        link = str(row.get("link", "") or "").strip()[:200]
        # 英文版：en_title / en_text，供前端一键复制，展示仍用中文
        en_title = str(row.get("en_title", "") or "")[:2_000]
        en_text = str(row.get("en_text", "") or "")[:20_000]
        row = {k: str(row[k])[:20_000] for k in REQUIRED}
        row["src"] = src
        if link:
            row["link"] = link
        if en_title:
            row["en_title"] = en_title
        if en_text:
            row["en_text"] = en_text

        hit = None
        for old in existing:
            # 三个栏目各自独立：只在同一 src 内判重
            if str(old.get("src", "v1")) != src:
                continue
            if similar(row["title"], old.get("title", "")):
                hit = old
                break
        if hit and not force:
            dups.append({
                "title": row["title"],
                "same_as": hit.get("title", ""),
                "round": hit.get("round", ""),
            })
            continue

        with open(DATA_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        existing.append(row)
        added += 1

    total = len(load_rows())
    if added:
        git_sync_async(f"自动同步：新增 {added} 条推文")
    return jsonify(
        ok=True,
        added=added,
        total=total,
        skipped_duplicate=dups,
        errors=errors,
        hint="skipped_duplicate 里的条目已存在。确认这次确实带来新进展，才可带 ?force=1 重新提交。",
    )


@app.route("/audit")
def audit():
    """全库文案体检：扫描四个栏目，返回不合格条目。

    v4 讲解人专查（元话语，见 D1.2）：
      1. 认知标签：我的理解是/我的看法是/我的读法是/我的观点是/我的判断是
      2. 预告思考：我试着/我先说说/接下来讲
      3. 自问自答：要是让我/你问我怎么看
      4. 标签+冒号/逗号引出结论
      5. "你"少于两次
      6. 书面连接词

    全部四栏通用：
      7. 中文与数字之间的空格（Markdown 排版惯性，真人不这么写）
      8. 中文里夹的孤立英文单词（rules / CPU / API 之类）
      9. 测试条目残留（标题含 __ 或 note 以"测试"开头）
    """
    rows = load_rows()
    v4rows = [r for r in rows if r.get("src") == "v4"]
    TAGS = ["我的理解是", "我的看法是", "我的读法是", "我的观点是", "我的判断是",
            "我试着", "我先说说", "接下来讲", "要是让我", "你问我怎么看",
            "综上所述", "由此可见", "值得注意的是", "本质上", "总而言之"]
    # 已知的合法专有名词，不算混排污染
    PROPER = {
        "AI", "GPU", "CPU", "NPU", "API", "APIs", "LLM", "TPU", "ASIC", "SoC", "FPGA",
        "RTL", "ISA", "OS", "PC", "App", "USB", "PCIe", "DDR", "HBM", "SSD", "HDD",
        "IDC", "CEO", "CTO", "CFO", "IPO", "GDP", "CPI", "PPI", "MaaS", "SaaS", "IaaS",
        "PaaS", "Saa", "MLOps", "DevOps", "K8s", "RAG", "OCR", "ASR", "TTS", "RLHF",
        "MoE", "KV", "GPU", "TOPS", "TPU", "VPU", "x86", "Arm", "ARM", "RISC",
        "OpenAI", "Anthropic", "DeepSeek", "Kimi", "Qwen", "Gemini", "Claude", "Llama",
        "Cboe", "Nasdaq", "NYSE", "GPU", "CEO", "SEC", "FDA", "NASA", "IEEE", "ISO",
        "Defender", "VPN", "MIM", "LOCKER", "Dragos", "DesignArena", "Frostbite",
        "Turbo", "Suno", "Vision", "Pro", "Max", "Ultra", "Mini", "Flash", "Plus",
        "SEMI", "TSMC", "ASML", "ARM", "BLK", "JPM", "Citi", "GS", "UBS",
    }
    # 疑似生成杂质的通用英文词（排除专有名词、缩写、型号、技术通用词）
    SUSPECT = {
        "rules", "rule", "the", "and", "for", "with", "that", "this", "from",
        "your", "you", "are", "was", "were", "not", "but", "all", "can", "has",
        "have", "will", "would", "should", "could", "what", "when", "where",
        "which", "who", "how", "why", "into", "than", "then", "them", "they",
    }
    # 技术领域通用词，中文里直接用英文是行业习惯，不算杂质
    TECH_OK = {
        "token", "tokens", "api", "apis", "ai", "gpu", "gpus", "cpu", "cpus",
        "npu", "llm", "tpu", "asic", "soc", "fpga", "ram", "ssd", "hdd", "hbm",
        "os", "pc", "app", "usb", "pcie", "ddr", "rtl", "isa", "arm", "x86",
        "risc", "ide", "sdk", "cli", "gui", "url", "pdf", "html", "css", "sql",
        "cdn", "ip", "tcp", "udp", "http", "wifi", "sim", "ota", "rom", "ram",
        "iot", "suv", "mpv", "ev", "ceo", "cto", "cfo", "ipo", "gdp", "cpi",
        "ppi", "id", "ip",
    }
    CN_SP = re.compile(r"[\u4e00-\u9fa5]\s+\d|\d\s+[\u4e00-\u9fa5]")
    MIXED = re.compile(r"([\u4e00-\u9fa5])\s+([A-Za-z]{3,})\s+([\u4e00-\u9fa5])")

    bad = []
    for r in rows:
        text = r.get("text", "")
        title = r.get("title", "")
        is_v4 = r.get("src") == "v4"
        issues = []

        if is_v4:
            for t in TAGS:
                if t in text:
                    issues.append(f"标签:{t}")
            for i, seg in enumerate(text.split("\n\n")):
                if "：" in seg:
                    head = seg.split("：")[0]
                    if any(k in head for k in ["我", "所以", "这说明", "三层", "综上"]):
                        issues.append(f"第{i + 1}块 标签+冒号")
                if "，" in seg[:12] and any(k in seg[:12] for k in ["我的理解", "我的看法", "我的读法"]):
                    issues.append(f"第{i + 1}块 标签+逗号")
            if text.count("你") < 2:
                issues.append(f"你×{text.count('你')}")

        # 通用项
        if CN_SP.search(text):
            issues.append("中文数字间空格")
        for seg in text.split("\n\n"):
            for m in MIXED.finditer(seg):
                w = m.group(2)
                if w.lower() in SUSPECT and w.lower() not in TECH_OK:
                    issues.append(f"混排:{w}")
                    break
        if title.startswith("__"):
            issues.append("测试残留")

        if issues:
            bad.append({"title": title, "round": r.get("round", ""),
                        "src": r.get("src", "v1"), "issues": issues})
    return jsonify(ok=True, total=len(rows), v4=len(v4rows),
                   bad=len(bad), items=bad)


@app.route("/count")
def count():
    return jsonify(total=len(load_rows()))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
