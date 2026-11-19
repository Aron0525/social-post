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
ALLOWED_SRC = {"v1", "v2", "v3"}
REQUIRED = ("round", "title", "st", "note", "text")


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
        row = {k: str(row[k])[:20_000] for k in REQUIRED}
        row["src"] = src

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


@app.route("/count")
def count():
    return jsonify(total=len(load_rows()))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
