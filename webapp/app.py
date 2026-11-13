# -*- coding: utf-8 -*-
"""learn-agent Web 控制台（Flask）。

启动: python main.py serve  ->  http://127.0.0.1:7860
"""
import threading
import time
import uuid
import json

import requests
from flask import Flask, jsonify, render_template, request

from core.config import cfg, data_dir
from core.knowledge import kb
from core.llm import router, external_enabled
from core.workflow import Workflow
import pathlib
from modules.learning import LearningModule, CURRICULUM, _flatten
from modules.leetcode import list_problems, get_problem, check_solution, explain

app = Flask(__name__)

# 中文直接以 UTF-8 输出，不再转成 \uXXXX 转义（前端读起来一致，抓包/日志也可读）。
# 注意：这只是「展示层」优化；真正导致练习输出乱码的是 codecheck 子进程的 GBK 解码问题。
try:
    app.json.ensure_ascii = False
except Exception:
    app.config["JSON_AS_ASCII"] = False

# 后台任务表 {id: {"status","result","kind","desc","started"}}
JOBS = {}
_LOCK = threading.Lock()


def _train_step(label: str, fn, *a, **kw):
    """训练单步执行：某一步失败记录 error 继续下一步，报告不再整体丢失。"""
    try:
        return fn(*a, **kw)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "step": label}


def _spawn(kind, desc, **kw):
    job_id = time.strftime("%H%M%S") + "_" + uuid.uuid4().hex[:4]
    with _LOCK:
        JOBS[job_id] = {"id": job_id, "kind": kind, "desc": desc,
                        "status": "running", "result": None,
                        "progress": "排队中…", "progress_pct": 0,
                        "started": time.strftime("%H:%M:%S"),
                        "started_at": time.time()}

    def _report(text, pct=None):
        with _LOCK:
            j = JOBS.get(job_id)
            if j is not None and j["status"] == "running":
                j["progress"] = text
                if pct is not None:
                    j["progress_pct"] = pct

    def _run():
        router().set_cloud_first(kw.get("cloud_first"))  # 线程级云端优先覆盖
        router().set_progress(_report)                  # 线程级进度回调
        try:
            if kind == "task":
                res = Workflow(desc, kind="general", context=kw.get("context", ""),
                               quiet=False, log_fn=lambda s: _report(s)).run()
            elif kind == "solve":
                from modules.leetcode import solve
                res = solve(desc)
            elif kind == "learn":
                res = {"ok": True, "summary": LearningModule().learn(
                    kw.get("lang"), kw.get("topic") or None,
                    log_fn=lambda s: _report(s))}
            elif kind == "practice":
                res = LearningModule().practice(
                    kw["lang"], kw.get("topic") or None,
                    weak_only=bool(kw.get("weak_only")),
                    log_fn=lambda s: _report(s))
            elif kind == "smartreview":
                res = LearningModule().smart_review(
                    kw["lang"], log_fn=lambda s: _report(s))
            elif kind == "capstone":
                res = LearningModule().capstone(kw["lang"],
                                                log_fn=lambda s: _report(s))
            elif kind == "explain":
                res = {"ok": True, "summary": explain(desc)}
            elif kind == "followup":
                res = {"ok": True, "summary": kw["_fn"](kw["slug"], kw["q"])}
            elif kind == "train":
                # 复用统一的训练入口（与 CLI `python main.py train` 完全同一条管线），
                # 避免两处各写一份导致字段/精度不一致。
                from training.run_training import run as _train_run
                t0 = time.time()
                _report("步骤 1/3 数据蒸馏…（真实 ETA 见日志）", 10)
                rep = _train_run(skip_distill=bool(kw.get("skip_distill")),
                                 use_external=not kw.get("no_external", False),
                                 topics_limit=kw.get("topics", 5),
                                 log_fn=lambda s: _report(s),
                                 progress_fn=lambda text, pct: _report(text, pct))
                rep.setdefault("seconds", round(time.time() - t0, 1))
                # 完整报告进任务结果（不再剔除 distill；前端训练卡片本就完整展示）
                res = {"ok": all(not isinstance(v, dict) or not v.get("error")
                                 for k, v in rep.items()
                                 if k in ("distill", "knowledge", "model")),
                       "summary": json.dumps(rep, ensure_ascii=False, indent=2),
                       "report": rep}
                # 训练期间路由层的进度回调由 _train_run 内部逐阶段驱动
                _report("全部完成", 100)
            else:
                res = {"ok": False, "summary": "未知任务类型"}
        except Exception as e:
            res = {"ok": False, "summary": f"执行异常: {e}"}
        finally:
            router().set_cloud_first(None)  # 清除线程级覆盖
            router().set_progress(None)
        with _LOCK:
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["result"] = res
            JOBS[job_id]["elapsed"] = round(time.time() - JOBS[job_id]["started_at"], 1)
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
    # 代码版本：显示正在跑的 build；磁盘代码已变则提示"重启后生效"
    build, build_stale = "?", False
    try:
        from core.version import fingerprint
        from core.runtime import read_state
        fp = fingerprint()
        st = read_state() or {}
        build = st.get("build") or fp["build"]
        build_stale = bool(st.get("build")) and st["build"] != fp["build"]
    except Exception:
        pass
    return jsonify(ollama=models, kb_docs=len(kb().docs),
                   curriculum={k: len(_flatten(v)) for k, v in CURRICULUM.items()},
                   languages_total=len(LearningModule().languages()),
                   train_report=train_report,
                   external_enabled=external_enabled(),
                   build=build, build_stale=build_stale)


@app.get("/api/courses")
def api_courses():
    """学习课程目录树：按阶段分组，标注每课是否已学、有没有已生成的教程文件。

    供「语言学习」页侧边栏目录使用——点目录项直接跳转/查看对应教程，
    不用在任务列表里翻找。
    """
    lang = (request.args.get("lang") or "python").strip()
    try:
        lm = LearningModule()
        c = lm.curriculum(lang)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    learned = set(lm._load_progress().get(lang, {}).get("learned", []))
    langs_root = data_dir() / "languages" / lang

    # 建立「主题 -> 教程文件」映射：文件名是主题清洗后的形式（含空格转下划线等）
    def _norm(s: str) -> str:
        import re as _re
        return _re.sub(r"[^\w\u4e00-\u9fff]+", "_", str(s)).strip("_").lower()

    files_by_norm = {}
    if langs_root.exists():
        for p in langs_root.rglob("*.md"):
            try:
                st = p.stat()
            except OSError:
                continue
            rel = str(p.relative_to(langs_root)).replace("\\", "/")
            files_by_norm[_norm(p.stem)] = {
                "file": rel,
                "mtime": time.strftime("%Y-%m-%d %H:%M",
                                       time.localtime(st.st_mtime)),
                "size": st.st_size,
            }

    stages = []
    done_n = total_n = 0
    for stage, topics in c.get("stages", {}).items():
        items = []
        for t in topics:
            total_n += 1
            is_learned = t in learned
            if is_learned:
                done_n += 1
            f = files_by_norm.get(_norm(t))
            items.append({"topic": t, "learned": is_learned,
                          "has_file": bool(f),
                          "file": (f or {}).get("file", ""),
                          "mtime": (f or {}).get("mtime", ""),
                          "size": (f or {}).get("size", 0)})
        stages.append({"stage": stage,
                       "done": sum(1 for i in items if i["learned"]),
                       "total": len(items), "items": items})

    # 目录外的自定义教程（custom 目录等），单独列一组，避免"生成了却看不到"
    known_files = {i["file"] for s in stages for i in s["items"] if i["file"]}
    extras = []
    for norm, f in files_by_norm.items():
        if f["file"] not in known_files:
            extras.append({"file": f["file"],
                           "name": f["file"].split("/")[-1][:-3],
                           "mtime": f["mtime"], "size": f["size"]})
    extras.sort(key=lambda x: x["mtime"], reverse=True)

    return jsonify(lang=lang, name=c.get("name", lang),
                   goal=c.get("goal", ""),
                   runner=c.get("runner"),
                   done=done_n, total=total_n,
                   pct=round(done_n / total_n * 100, 1) if total_n else 0,
                   next_topic=lm.next_topic(lang),
                   stages=stages, extras=extras)


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
    return jsonify(job=_spawn("solve", slug, cloud_first=body.get("cloud_first")))


@app.post("/api/learn")
def api_learn():
    body = request.get_json(force=True)
    lang, topic = body.get("lang"), (body.get("topic") or "").strip()
    if lang not in LearningModule().languages():
        return jsonify(error="lang 无效"), 400
    kind = "capstone" if body.get("capstone") else "learn"
    label = f"进阶实战 {lang}" if body.get("capstone") else \
        (f"学习 {lang}:{topic}" if topic else f"引导学习 {lang}(下一课)")
    return jsonify(job=_spawn(kind, label, lang=lang, topic=topic,
                              cloud_first=body.get("cloud_first")))


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
    full = request.args.get("full") == "1"
    # 每次查询用最新磁盘索引（避免全局单例缓存旧索引导致检索不到新沉淀内容）
    from core.knowledge import KnowledgeBase
    hits = KnowledgeBase().search(q, k=5)
    return jsonify([{"score": h["score"], "title": h["title"], "lang": h["lang"],
                     "source": h["source"],
                     "excerpt": h["text"][:200],
                     "text": h["text"] if full else None}
                    for h in hits])


@app.get("/api/problems")
def api_problems():
    return jsonify(list_problems())


@app.get("/api/problem")
def api_problem():
    """取单题详情（题意/函数签名/内置用例），供「动手写」编辑器预填。"""
    slug = (request.args.get("slug") or "").strip()
    if not slug:
        return jsonify(error="slug 必填"), 400
    try:
        p = get_problem(slug)
    except KeyError as e:
        return jsonify(error=str(e)), 404
    return jsonify(slug=p["slug"], title=p["title"], difficulty=p["difficulty"],
                   desc=p["desc"], signature=p.get("signature", ""),
                   tests=[{"args": a, "expected": e} for a, e in p["tests"]])


@app.post("/api/judge")
def api_judge():
    """用户提交自写代码，用题库内置测试判题：静态检查 + 逐测 + 泄漏抽检。"""
    body = request.get_json(force=True)
    slug = (body.get("slug") or "").strip()
    code = body.get("code") or ""
    if not slug:
        return jsonify(error="slug 必填"), 400
    try:
        p = get_problem(slug)
    except KeyError as e:
        return jsonify(error=str(e)), 404
    if not code.strip():
        return jsonify(error="代码为空"), 400
    try:
        detail = check_solution(p, code)
    except Exception as e:
        return jsonify(error=f"判题异常: {e}"), 500
    return jsonify(detail)


@app.get("/api/practices")
def api_practices_list():
    """列出 data/practice/ 下所有已保存的练习集（按时间倒序）。

    为什么需要：练习生成后只存在于内存 JOBS，服务一重启就查不到了，
    磁盘上的 JSON 却一直在——用户感觉"生成的练习无法查看"。
    这里提供磁盘目录接口，配 ?file= 取单个练习集完整内容。
    """
    practice_dir = data_dir() / "practice"
    file = (request.args.get("file") or "").strip()
    if file:
        # 安全：限制在 practice 目录内
        p = (practice_dir / file).resolve()
        try:
            inside = str(p).startswith(str(practice_dir.resolve()))
        except OSError:
            inside = False
        if not inside or not p.exists() or not p.is_file():
            return jsonify(error="练习文件不存在"), 404
        try:
            data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError) as e:
            return jsonify(error=f"练习文件损坏: {e}"), 500
        data["file"] = file
        return jsonify(data)
    flt = (request.args.get("lang") or "").strip()
    items = []
    if practice_dir.exists():
        for p in practice_dir.glob("*.json"):
            try:
                st = p.stat()
                raw = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except (OSError, ValueError):
                continue
            lang = str(raw.get("lang") or "")
            if flt and lang != flt:
                continue
            its = raw.get("items") or []
            items.append({
                "file": p.name,
                "lang": lang,
                "topic": str(raw.get("topic") or ""),
                "count": len(its),
                "titles": [str(i.get("title") or "") for i in its][:4],
                "weak_used": bool(raw.get("weak_used")),
                "mtime": time.strftime("%Y-%m-%d %H:%M",
                                       time.localtime(st.st_mtime)),
                "mtime_ts": st.st_mtime,
                "size": st.st_size,
            })
    items.sort(key=lambda x: -x["mtime_ts"])
    return jsonify(items=items, total=len(items),
                   langs=sorted({i["lang"] for i in items if i["lang"]}))


@app.get("/api/practices/by-topic")
def api_practices_by_topic():
    """按「语言+主题」汇总练习，供课程目录标注「这一课有几套练习」。

    主题匹配用宽松规则：练习 topic 可能写成「树与递归、动态规划入门」
    这种合并主题，所以用"包含"而不是全等。
    """
    lang = (request.args.get("lang") or "").strip()
    practice_dir = data_dir() / "practice"
    out = {}
    if practice_dir.exists():
        for p in practice_dir.glob("*.json"):
            try:
                st = p.stat()
                raw = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except (OSError, ValueError):
                continue
            if lang and str(raw.get("lang") or "") != lang:
                continue
            topic = str(raw.get("topic") or "")
            for t in [x.strip() for x in topic.replace("、", ",").split(",") if x.strip()]:
                rec = out.setdefault(t, {"topic": t, "count": 0, "latest": "", "files": []})
                rec["count"] += 1
                m = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
                if m > rec["latest"]:
                    rec["latest"] = m
                rec["files"].append(p.name)
    return jsonify(lang=lang, topics=list(out.values()))


@app.post("/api/practice")
def api_practice():
    """强化学习闭环：出一组实操练习题（可选只练薄弱点），后台任务执行。"""
    body = request.get_json(force=True, silent=True) or {}
    lang = (body.get("lang") or "").strip()
    if lang not in LearningModule().languages():
        return jsonify(error="lang 无效"), 400
    topic = (body.get("topic") or "").strip()
    weak = bool(body.get("weak_only"))
    label = f"练习 {lang}:{topic or ('薄弱点' if weak else '下一课')}"
    return jsonify(job=_spawn("practice", label, lang=lang, topic=topic,
                              weak_only=weak,
                              cloud_first=body.get("cloud_first")))


@app.post("/api/practice/judge")
def api_practice_judge():
    """实时判题：沙箱运行学员代码，按关键输出行判定。"""
    body = request.get_json(force=True, silent=True) or {}
    code = body.get("code") or ""
    expects = body.get("expects") or []
    if not code.strip():
        return jsonify(error="代码为空"), 400
    try:
        r = LearningModule().judge_practice(code, expects)
    except Exception as e:
        return jsonify(error=f"判题异常: {e}"), 500
    return jsonify(r)


@app.post("/api/practice/record")
def api_practice_record():
    """记录练习结果，维护薄弱点清单（progress.json）。"""
    body = request.get_json(force=True, silent=True) or {}
    lang = (body.get("lang") or "").strip()
    if not lang:
        return jsonify(error="lang 必填"), 400
    try:
        pr = LearningModule().record_practice(
            lang, (body.get("topic") or "").strip(),
            (body.get("title") or "").strip(), bool(body.get("passed")))
    except Exception as e:
        return jsonify(error=f"记录异常: {e}"), 500
    return jsonify(stats=pr)


@app.post("/api/review")
def api_review():
    """智能复习：按薄弱点/到期主题生成针对性复习卡。"""
    body = request.get_json(force=True, silent=True) or {}
    lang = (body.get("lang") or "").strip()
    if lang not in LearningModule().languages():
        return jsonify(error="lang 无效"), 400
    return jsonify(job=_spawn("smartreview", f"智能复习 {lang}",
                              lang=lang, cloud_first=body.get("cloud_first")))


@app.post("/api/run")
def api_run():
    """学习实操：运行用户编辑后的任意 Python 代码（沙箱子进程 + 超时），返回 stdout。"""
    from core.codecheck import run_python_code
    body = request.get_json(force=True, silent=True) or {}
    code = body.get("code") or ""
    if not code.strip():
        return jsonify(error="代码为空"), 400
    try:
        r = run_python_code(code)
    except Exception as e:
        return jsonify(error=f"运行异常: {e}"), 500
    return jsonify(ok=r.get("ok"), output=r.get("output", ""),
                   error=r.get("error"))


@app.post("/api/explain")
def api_explain():
    """派发力扣题解讲解任务（思路/解法/复杂度/多解法对比/同类拓展），结果进任务区。"""
    body = request.get_json(force=True)
    slug = (body.get("slug") or "").strip()
    if not slug:
        return jsonify(error="slug 必填"), 400
    try:
        get_problem(slug)
    except KeyError as e:
        return jsonify(error=str(e)), 404
    return jsonify(job=_spawn("explain", slug, cloud_first=body.get("cloud_first")))


@app.get("/api/explains")
def api_explains_list():
    """列出所有已保存的本地讲解（侧边栏目录用）。

    返回每题的 slug/title/难度/字数/更新时间/是否有讲解，
    前端据此渲染「算法讲解目录」，点一下即可跳转查看，无需重新生成。
    """
    from modules.leetcode import list_problems, load_explain
    explain_dir = data_dir() / "explain"
    meta = {}
    if explain_dir.exists():
        for p in explain_dir.glob("*.md"):
            try:
                st = p.stat()
            except OSError:
                continue
            meta[p.stem] = {
                "chars": st.st_size,
                "mtime": time.strftime("%Y-%m-%d %H:%M",
                                       time.localtime(st.st_mtime)),
                "mtime_ts": st.st_mtime,
            }
    items = []
    for prob in list_problems():
        slug = prob["slug"]
        m = meta.pop(slug, None)
        items.append({"slug": slug, "title": prob["title"],
                      "difficulty": prob["difficulty"],
                      "has_explain": bool(m),
                      "chars": (m or {}).get("chars", 0),
                      "mtime": (m or {}).get("mtime", ""),
                      "mtime_ts": (m or {}).get("mtime_ts", 0)})
    # 讲解文件存在但题库已移除的（历史遗留），也列出来免得"看不见"
    for slug, m in sorted(meta.items(), key=lambda kv: -kv[1]["mtime_ts"]):
        items.append({"slug": slug, "title": slug, "difficulty": "?",
                      "has_explain": True, "chars": m["chars"],
                      "mtime": m["mtime"], "mtime_ts": m["mtime_ts"],
                      "orphan": True})
    return jsonify(items=items,
                   total=len(items),
                   with_explain=sum(1 for i in items if i["has_explain"]))


@app.get("/api/explain/<slug>")
def api_explain_get(slug):
    """读取本地已保存的讲解（无则 content 为空串）。"""
    from modules.leetcode import load_explain
    return jsonify(slug=slug, content=load_explain(slug))


@app.post("/api/explain/followup")
def api_explain_followup():
    """对已保存的讲解追问；回答自动追加进本地文档，后台任务执行。"""
    from modules.leetcode import explain_followup
    body = request.get_json(force=True)
    slug = (body.get("slug") or "").strip()
    q = (body.get("question") or "").strip()
    if not slug or not q:
        return jsonify(error="slug 与 question 必填"), 400
    try:
        get_problem(slug)
    except KeyError as e:
        return jsonify(error=str(e)), 404
    return jsonify(job=_spawn("followup", f"追问 {slug}", slug=slug, q=q,
                              cloud_first=body.get("cloud_first"),
                              _fn=explain_followup))


@app.get("/api/cloud")
def api_cloud():
    """返回云端模型池、当前 cloud_first 开关与通道状态。

    - models：按「可用性优先、兼顾性能」排序后的实际调用顺序（order 字段即优先级）
    - channels：冷却剩余、耗时估计与可用性画像（成功/失败/成功率/排序分）
    """
    r = router()
    models = []
    for tier in ("strong", "fast"):
        for i, m in enumerate(r._order_cloud(r._cloud_tier(strong=(tier == "strong"))), 1):
            prov = m.get("provider") or "config"
            models.append({"name": m.get("name"), "provider": prov,
                           "model": m.get("model"), "tier": m.get("tier"),
                           "order": i,
                           "source": "dsh-gateway" if prov == "dsh-gateway" else "config"})
    return jsonify(enabled=True, cloud_first=r.cloud_first_effective,
                   models=models, channels=r.channel_state())


@app.post("/api/cloud")
def api_cloud_set():
    """切换云端优先开关（运行时持久，不重启服务）。"""
    body = request.get_json(force=True, silent=True) or {}
    val = body.get("cloud_first")
    if val is not None:
        router().cloud["cloud_first"] = bool(val)
    return jsonify(cloud_first=router().cloud_first_effective)


@app.get("/api/history")
def api_history():
    """回顾已学内容：列出 data/languages 下的所有已学教程（按时间倒序），
    带 ?lang= 过滤；带 ?file= 返回该教程全文。"""
    langs_root = data_dir() / "languages"
    if not langs_root.exists():
        return jsonify(items=[])
    flt = (request.args.get("lang") or "").strip()
    file = (request.args.get("file") or "").strip()
    if file:
        # 安全：限制在 languages 目录内
        p = (langs_root / file).resolve()
        if not str(p).startswith(str(langs_root.resolve())):
            return jsonify(error="非法路径"), 400
        if not p.exists() or not p.is_file():
            return jsonify(error="文件不存在"), 404
        return jsonify(path=str(p), content=p.read_text(encoding="utf-8", errors="replace"))
    items = []
    for p in sorted(langs_root.rglob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
        rel = str(p.relative_to(langs_root)).replace("\\", "/")
        lang = p.parts[-3] if len(p.parts) >= 3 else "?"
        stage = p.parts[-2] if len(p.parts) >= 2 else ""
        if flt and lang != flt:
            continue
        items.append({"file": rel, "lang": lang, "stage": stage,
                      "name": p.stem, "mtime": time.strftime("%Y-%m-%d %H:%M",
                                                             time.localtime(p.stat().st_mtime)),
                      "size": p.stat().st_size})
    return jsonify(items=items)


@app.post("/api/train")
def api_train():
    """一键训练（蒸馏→知识库→定制本地模型）。后台任务执行。"""
    body = request.get_json(force=True, silent=True) or {}
    topics = int(body.get("topics") or 5)
    skip_distill = bool(body.get("skip_distill"))
    desc = f"训练(topics={topics}, skip_distill={skip_distill})"
    return jsonify(job=_spawn("train", desc, topics=topics, skip_distill=skip_distill))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=7860, debug=False, threaded=True)
