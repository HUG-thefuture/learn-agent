# -*- coding: utf-8 -*-
"""learn-agent Web 控制台（Flask）。

启动: python main.py serve  ->  http://127.0.0.1:7860
"""
import threading
import time
import uuid

import requests
from flask import Flask, jsonify, render_template, request

from core.config import cfg, data_dir
from core.knowledge import kb
from core.workflow import Workflow
from modules.learning import LearningModule, CURRICULUM, _flatten
from modules.leetcode import list_problems

app = Flask(__name__)

# 后台任务表 {id: {"status","result","kind","desc","started"}}
JOBS = {}
_LOCK = threading.Lock()


def _spawn(kind, desc, **kw):
    job_id = time.strftime("%H%M%S") + "_" + uuid.uuid4().hex[:4]
    with _LOCK:
        JOBS[job_id] = {"id": job_id, "kind": kind, "desc": desc,
                        "status": "running", "result": None,
                        "started": time.strftime("%H:%M:%S")}
    def _run():
        try:
            if kind == "task":
                res = Workflow(desc, kind="general", context=kw.get("context", ""),
                               quiet=True).run()
            elif kind == "solve":
                from modules.leetcode import solve
                res = solve(desc)
            elif kind == "learn":
                res = {"ok": True, "summary": LearningModule().learn(
                    kw.get("lang"), kw.get("topic") or None)}
            elif kind == "capstone":
                from modules.learning import LearningModule
                res = LearningModule().capstone(kw["lang"])
            else:
                res = {"ok": False, "summary": "未知任务类型"}
        except Exception as e:
            res = {"ok": False, "summary": f"执行异常: {e}"}
        with _LOCK:
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["result"] = res
    threading.Thread(target=_run, daemon=True).start()
    return job_id


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def status():
    try:
        models = [m["name"] for m in requests.get(
            cfg()["local_model"]["base_url"] + "/api/tags", timeout=3).json()["models"]]
    except Exception:
        models = []
    train_report = {}
    tr = data_dir() / "train_report.json"
    if tr.exists():
        import json
        try:
            train_report = json.loads(tr.read_text(encoding="utf-8"))
        except Exception:
            pass
    return jsonify(ollama=models, kb_docs=len(kb().docs),
                   curriculum={k: len(_flatten(v)) for k, v in CURRICULUM.items()},
                   languages_total=len(LearningModule().languages()),
                   train_report=train_report,
                   external_enabled=bool(cfg()["external_model"].get("enabled")))


@app.get("/api/path")
def api_path():
    lang = request.args.get("lang", "python")
    try:
        return jsonify(path=LearningModule().path(lang))
    except ValueError as e:
        return jsonify(error=str(e)), 400


@app.post("/api/chat")
def chat():
    body = request.get_json(force=True)
    msg, model = body.get("message", ""), body.get("model", "learn-agent")
    try:
        r = requests.post(cfg()["local_model"]["base_url"] + "/api/chat", json={
            "model": model, "stream": False, "think": False,
            "messages": [{"role": "system", "content":
                          "你是 learn-agent 编程学习助手，回答用中文，先结论后细节。"},
                         {"role": "user", "content": msg}],
            "options": {"temperature": 0.3, "num_ctx": 8192}}, timeout=300)
        r.raise_for_status()
        return jsonify(reply=r.json()["message"]["content"])
    except Exception:
        from core.llm import router
        try:
            return jsonify(reply=router().ask(msg), note="经路由降级")
        except Exception as e:
            return jsonify(reply=f"模型不可用: {e}"), 502


@app.post("/api/task")
def api_task():
    body = request.get_json(force=True)
    desc = (body.get("desc") or "").strip()
    if not desc:
        return jsonify(error="desc 必填"), 400
    return jsonify(job=_spawn("task", desc))


@app.post("/api/solve")
def api_solve():
    body = request.get_json(force=True)
    slug = (body.get("slug") or "").strip()
    if not slug:
        return jsonify(error="slug 必填"), 400
    return jsonify(job=_spawn("solve", slug))


@app.post("/api/learn")
def api_learn():
    body = request.get_json(force=True)
    lang, topic = body.get("lang"), (body.get("topic") or "").strip()
    if lang not in LearningModule().languages():
        return jsonify(error="lang 无效"), 400
    kind = "capstone" if body.get("capstone") else "learn"
    label = f"进阶实战 {lang}" if body.get("capstone") else \
        (f"学习 {lang}:{topic}" if topic else f"引导学习 {lang}(下一课)")
    return jsonify(job=_spawn(kind, label, lang=lang, topic=topic))


@app.get("/api/job/<job_id>")
def job(job_id):
    with _LOCK:
        j = JOBS.get(job_id)
        return jsonify(j or {"error": "not found"}), (200 if j else 404)


@app.get("/api/jobs")
def jobs():
    with _LOCK:
        return jsonify(list(JOBS.values())[::-1][:20])


@app.get("/api/kb")
def api_kb():
    q = request.args.get("q", "")
    return jsonify([{"score": h["score"], "title": h["title"], "lang": h["lang"],
                     "source": h["source"], "excerpt": h["text"][:200]}
                    for h in kb().search(q, k=5)])


@app.get("/api/problems")
def api_problems():
    return jsonify(list_problems())


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=7860, debug=False)
