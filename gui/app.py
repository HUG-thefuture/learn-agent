# -*- coding: utf-8 -*-
"""learn-agent 桌面图形应用（Tkinter，零第三方 GUI 依赖）。

启动: python main.py gui   或双击 learn-agent-gui.bat
页签: 对话(流式) / 语言学习 / 力扣刷题 / 开发任务(实时工作流日志) / 训练
所有耗时操作均在后台线程执行，通过队列回传 UI，界面不卡顿。
"""
import json
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import cfg, data_dir, ensure_dirs  # noqa: E402

BASE_URL = cfg()["local_model"]["base_url"]

# ---------------- 深色主题配色 ----------------
C_BG = "#0f1420"
C_PANEL = "#161d2e"
C_LINE = "#2a3450"
C_FG = "#e8edf7"
C_DIM = "#93a0bd"
C_ACC = "#5b9dff"
C_OK = "#3ecf8e"
C_BAD = "#ff6b6b"
C_WARN = "#f7c948"
FONT = ("Microsoft YaHei UI", 10)
FONT_MONO = ("Consolas", 9)


def setup_style(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure(".", background=C_BG, foreground=C_FG, fieldbackground=C_PANEL,
                    bordercolor=C_LINE, lightcolor=C_PANEL, darkcolor=C_PANEL)
    style.configure("TNotebook", background=C_BG, borderwidth=0)
    style.configure("TNotebook.Tab", background=C_BG, foreground=C_DIM,
                    padding=(16, 8), bordercolor=C_BG)
    style.map("TNotebook.Tab", background=[("selected", C_PANEL)],
              foreground=[("selected", C_FG)])
    style.configure("TFrame", background=C_BG)
    style.configure("TLabel", background=C_BG, foreground=C_FG)
    style.configure("Dim.TLabel", background=C_BG, foreground=C_DIM)
    style.configure("TButton", background=C_PANEL, foreground=C_FG, padding=6)
    style.map("TButton", background=[("active", C_LINE)])
    style.configure("Acc.TButton", background=C_ACC, foreground="#ffffff")
    style.map("Acc.TButton", background=[("active", "#4a8bef"), ("disabled", "#3a4664")])
    style.configure("TEntry", fieldbackground=C_PANEL, foreground=C_FG, insertcolor=C_FG)
    style.configure("TCombobox", fieldbackground=C_PANEL, foreground=C_FG, arrowcolor=C_FG)
    style.configure("Treeview", background=C_PANEL, foreground=C_FG,
                    fieldbackground=C_PANEL, rowheight=26, bordercolor=C_LINE)
    style.map("Treeview", background=[("selected", "#2b4a77")])
    style.configure("Treeview.Heading", background=C_PANEL, foreground=C_DIM)
    style.configure("TCheckbutton", background=C_BG, foreground=C_FG)
    style.configure("TSpinbox", fieldbackground=C_PANEL, foreground=C_FG, arrowcolor=C_FG)


def make_text(parent):
    t = tk.Text(parent, bg="#0d1220", fg=C_FG, insertbackground=C_FG,
                relief="flat", borderwidth=1, highlightthickness=1,
                highlightbackground=C_LINE, wrap="word", font=FONT)
    for name, color, extra in [("me", C_ACC, {"font": ("Microsoft YaHei UI", 10, "bold")}),
                               ("bot", C_FG, {}),
                               ("sys", C_DIM, {"font": FONT_MONO}),
                               ("head", C_WARN, {"font": ("Microsoft YaHei UI", 10, "bold")}),
                               ("ok", C_OK, {}),
                               ("bad", C_BAD, {})]:
        t.tag_configure(name, foreground=color, **extra)
    return t


class App:
    def __init__(self, root: tk.Tk, smoke: bool = False):
        self.root = root
        self.q = queue.Queue()
        self.models = []
        self.chat_history = []      # 对话上下文
        self.busy = set()           # 正在执行的后台任务类型
        self._chat_pos = "1.0"      # 助手回答起始位置（流式渲染）
        self._chat_stream = ""
        root.title("learn-agent — 编程学习助手")
        root.geometry("1100x740")
        root.configure(bg=C_BG)
        setup_style(root)
        self._build()
        self._poll_queue()
        threading.Thread(target=self._load_models, daemon=True).start()
        if smoke:
            root.after(1800, root.destroy)

    # ============ 界面搭建 ============
    def _build(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        self._tab_chat(nb)
        self._tab_learn(nb)
        self._tab_leetcode(nb)
        self._tab_task(nb)
        self._tab_train(nb)
        self.status = ttk.Label(self.root, text="初始化…", style="Dim.TLabel")
        self.status.pack(fill="x", padx=12, pady=6)

    # ---------- 页签1：对话 ----------
    def _tab_chat(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text=" 对话 ")
        top = ttk.Frame(f)
        top.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(top, text="模型：").pack(side="left")
        self.chat_model = ttk.Combobox(top, width=24, state="readonly")
        self.chat_model.pack(side="left", padx=4)
        ttk.Button(top, text="刷新模型", command=lambda: threading.Thread(
            target=self._load_models, daemon=True).start()).pack(side="left", padx=4)
        ttk.Button(top, text="清空对话", command=self._chat_clear).pack(side="right")
        self.chatlog = make_text(f)
        self.chatlog.pack(fill="both", expand=True, padx=10, pady=6)
        bottom = ttk.Frame(f)
        bottom.pack(fill="x", padx=10, pady=(0, 10))
        self.chat_in = ttk.Entry(bottom)
        self.chat_in.pack(side="left", fill="x", expand=True, ipady=6)
        self.chat_in.bind("<Return>", lambda e: self._chat_send())
        self.btn_send = ttk.Button(bottom, text="发送", style="Acc.TButton",
                                   command=self._chat_send)
        self.btn_send.pack(side="left", padx=6)
        self._chat_welcome()

    def _chat_welcome(self):
        t = self.chatlog
        t.insert("end", "learn-agent", "head")
        t.insert("end", "  已就绪。可以问编程概念、让它写代码、讲算法。\n"
                        "提示：教新知识用「语言学习」页签；完整开发任务用「开发任务」页签。\n\n", "sys")

    def _chat_clear(self):
        self.chat_history.clear()
        self.chatlog.delete("1.0", "end")
        self._chat_welcome()

    def _chat_send(self):
        msg = self.chat_in.get().strip()
        if not msg or "chat" in self.busy:
            return
        self.busy.add("chat")
        self.btn_send.state(["disabled"])
        t = self.chatlog
        t.insert("end", "你\n", "me")
        t.insert("end", msg + "\n\n", "bot")
        t.insert("end", "助手\n", "me")
        self._chat_pos = t.index("end-1c")
        self._chat_stream = ""
        t.see("end")
        self.chat_in.delete(0, "end")
        model = self.chat_model.get() or "learn-agent"
        self.chat_history.append({"role": "user", "content": msg})
        threading.Thread(target=self._chat_worker, args=(model,), daemon=True).start()

    def _chat_worker(self, model):
        """流式拉取回答；失败时降级走路由。"""
        ans, err = None, ""
        try:
            import requests
            payload = {"model": model, "stream": True,
                       "messages": ([{"role": "system",
                                      "content": "你是 learn-agent 编程学习助手，回答用中文，先结论后细节。"}]
                                    + self.chat_history[-12:])}
            r = requests.post(BASE_URL + "/api/chat", json=payload, stream=True, timeout=600)
            r.raise_for_status()
            parts = []
            for line in r.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                delta = data.get("message", {}).get("content", "")
                if delta:
                    parts.append(delta)
                    self.q.put(("chat_delta", delta))
                if data.get("done"):
                    break
            ans = "".join(parts)
        except Exception as e:
            err = str(e)
            try:
                from core.llm import router
                ans = router().ask(self.chat_history[-1]["content"])
                self.q.put(("chat_delta", ans))
            except Exception as e2:
                self.q.put(("chat_err", f"{err} / {e2}"))
                return
        self.chat_history.append({"role": "assistant", "content": ans})
        self.q.put(("chat_done", None))

    # ---------- 页签2：语言学习 ----------
    def _tab_learn(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text=" 语言学习 ")
        row = ttk.Frame(f)
        row.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(row, text="语言").pack(side="left")
        from modules.learning import CURRICULUM
        self.learn_lang = ttk.Combobox(row, values=list(CURRICULUM),
                                       width=12, state="readonly")
        self.learn_lang.current(0)
        self.learn_lang.pack(side="left", padx=4)
        ttk.Label(row, text="主题").pack(side="left", padx=(10, 0))
        self.learn_topic = ttk.Entry(row, width=24)
        self.learn_topic.pack(side="left", padx=4, ipady=4)
        self.btn_path = ttk.Button(row, text="学习路径", command=self._show_path)
        self.btn_path.pack(side="left", padx=(10, 0))
        self.btn_start = ttk.Button(row, text="下一课", style="Acc.TButton",
                                    command=self._learn_next)
        self.btn_start.pack(side="left", padx=4)
        self.btn_learn = ttk.Button(row, text="学指定主题", command=self._learn_run)
        self.btn_learn.pack(side="left", padx=4)
        self.btn_quiz = ttk.Button(row, text="测验", command=self._quiz_run)
        self.btn_quiz.pack(side="left", padx=4)
        self.btn_cap = ttk.Button(row, text="进阶实战", style="Acc.TButton",
                                  command=self._capstone_run)
        self.btn_cap.pack(side="left", padx=4)
        ttk.Label(f, text="L0零基础→L6算法 分阶段路径；「下一课」从0开始自动推进；"
                          "学习自动沉淀知识库；「进阶实战」用已学知识自主完成前后端/算法项目（走完整工作流）。",
                  style="Dim.TLabel").pack(anchor="w", padx=12)
        self.learn_out = make_text(f)
        self.learn_out.pack(fill="both", expand=True, padx=10, pady=6)
        kbrow = ttk.Frame(f)
        kbrow.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Label(kbrow, text="知识库检索").pack(side="left")
        self.kb_q = ttk.Entry(kbrow, width=32)
        self.kb_q.pack(side="left", padx=6, ipady=4)
        self.kb_q.bind("<Return>", lambda e: self._kb_search())
        ttk.Button(kbrow, text="检索", command=self._kb_search).pack(side="left")

    def _show_path(self):
        lang = self.learn_lang.get()
        from modules.learning import LearningModule
        self.learn_out.delete("1.0", "end")
        self.learn_out.insert("end", LearningModule().path(lang), "bot")

    def _learn_next(self):
        if "learn" in self.busy:
            return
        self.busy.add("learn")
        self._set_learn_buttons("disabled")
        lang = self.learn_lang.get()
        self.learn_out.delete("1.0", "end")
        self.learn_out.insert("end", f"正在进入 {lang} 下一课（自动选择未学的第一课）…\n", "sys")

        def work():
            from modules.learning import LearningModule
            return LearningModule().learn(lang, None)

        def done(res):
            self.learn_out.delete("1.0", "end")
            self.learn_out.insert("end", str(res), "bot")
            self._learn_ready()

        threading.Thread(target=lambda: self._run_bg(work, done), daemon=True).start()

    def _capstone_run(self):
        if "learn" in self.busy:
            return
        self.busy.add("learn")
        self._set_learn_buttons("disabled")
        lang = self.learn_lang.get()
        self.learn_out.delete("1.0", "end")
        self.learn_out.insert("end", f"进阶实战启动：Agent 将用已学知识自主完成 {lang} 项目（见实时日志）…\n", "sys")

        def work():
            from modules.learning import LearningModule
            return LearningModule().capstone(lang,
                                             log_fn=lambda m: self.q.put(("log_learn", m)))

        def done(res):
            t = self.learn_out
            t.insert("end", "\n==== 实战结果 ====\n", "head")
            t.insert("end", (res.get("summary") if isinstance(res, dict) else str(res)) + "\n",
                     "ok" if isinstance(res, dict) and res.get("ok") else "bad")
            if isinstance(res, dict) and res.get("workspace"):
                t.insert("end", f"项目目录: {res['workspace']}\n", "sys")
            self._learn_ready()

        threading.Thread(target=lambda: self._run_bg(work, done), daemon=True).start()

    def _set_learn_buttons(self, state):
        for b in (self.btn_learn, self.btn_quiz, self.btn_start, self.btn_cap, self.btn_path):
            b.state([state])

    def _learn_run(self):
        topic = self.learn_topic.get().strip()
        if not topic or "learn" in self.busy:
            return
        self.busy.add("learn")
        self._set_learn_buttons("disabled")
        lang = self.learn_lang.get()
        self.learn_out.delete("1.0", "end")
        self.learn_out.insert("end", f"正在学习 {lang} · {topic}（生成教程中，约1~2分钟）…\n", "sys")

        def work():
            from modules.learning import LearningModule
            return LearningModule().learn(lang, topic)

        def done(res):
            self.learn_out.delete("1.0", "end")
            self.learn_out.insert("end", str(res), "bot")
            self._learn_ready()
            self._load_models_async()

        threading.Thread(target=lambda: self._run_bg(work, done), daemon=True).start()

    def _quiz_run(self):
        topic = self.learn_topic.get().strip()
        if not topic or "learn" in self.busy:
            return
        self.busy.add("learn")
        self._set_learn_buttons("disabled")
        lang = self.learn_lang.get()
        self.learn_out.delete("1.0", "end")
        self.learn_out.insert("end", "出题中…\n", "sys")

        def work():
            from modules.learning import LearningModule
            return LearningModule().quiz(lang, topic)

        def done(data):
            self.learn_out.delete("1.0", "end")
            t = self.learn_out
            for i, qd in enumerate(data.get("questions", []), 1):
                t.insert("end", f"[{i}] {qd.get('question')}\n", "head")
                for o in qd.get("options", []):
                    t.insert("end", f"    {o}\n", "bot")
                t.insert("end", "答案: ", "sys")
                t.insert("end", f"{qd.get('answer')}\n", "ok")
                t.insert("end", f"解析: {qd.get('explain', '')}\n\n", "sys")
            self._learn_ready()

        threading.Thread(target=lambda: self._run_bg(work, done), daemon=True).start()

    def _learn_ready(self):
        self.busy.discard("learn")
        self._set_learn_buttons("!disabled")

    def _kb_search(self):
        q = self.kb_q.get().strip()
        if not q:
            return
        from core.knowledge import kb
        hits = kb().search(q, k=5)
        t = self.learn_out
        t.delete("1.0", "end")
        if not hits:
            t.insert("end", "没有命中。先到上方学习主题来充实知识库。\n", "sys")
            return
        for h in hits:
            t.insert("end", h["title"], "head")
            t.insert("end", f"  [{h['lang']}] score={h['score']} src={h['source']}\n", "sys")
            t.insert("end", h["text"][:260].replace("\n", " ") + " …\n\n", "bot")

    # ---------- 页签3：力扣刷题 ----------
    def _tab_leetcode(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text=" 力扣刷题 ")
        cols = ("slug", "title", "diff")
        tv = ttk.Treeview(f, columns=cols, show="headings", height=8)
        for c, w, txt in [("slug", 170, "slug"), ("title", 380, "题目"),
                          ("diff", 90, "难度")]:
            tv.heading(c, text=txt)
            tv.column(c, width=w, anchor="w")
        tv.pack(fill="x", padx=10, pady=(10, 4))
        self.lc_tree = tv
        btns = ttk.Frame(f)
        btns.pack(fill="x", padx=10, pady=4)
        self.btn_solve = ttk.Button(btns, text="完整工作流解题", style="Acc.TButton",
                                    command=self._lc_solve)
        self.btn_solve.pack(side="left")
        self.btn_explain = ttk.Button(btns, text="题解讲解", command=self._lc_explain)
        self.btn_explain.pack(side="left", padx=6)
        ttk.Label(btns, text="解题走 思考→计划→审查→实现→测试+内存泄漏检测 全流程，约1~3分钟",
                  style="Dim.TLabel").pack(side="left", padx=10)
        self.lc_out = make_text(f)
        self.lc_out.pack(fill="both", expand=True, padx=10, pady=6)
        from modules.leetcode import list_problems
        for p in list_problems():
            tv.insert("", "end", values=(p["slug"], p["title"], p["difficulty"]))

    def _lc_sel(self):
        sel = self.lc_tree.selection()
        return str(self.lc_tree.item(sel[0])["values"][0]) if sel else None

    def _lc_solve(self):
        slug = self._lc_sel()
        if not slug or "lc" in self.busy:
            return
        self.busy.add("lc")
        self.btn_solve.state(["disabled"])
        self.btn_explain.state(["disabled"])
        self.lc_out.delete("1.0", "end")
        self.lc_out.insert("end", f"开始解题: {slug}\n", "sys")

        def work():
            from modules.leetcode import solve
            return solve(slug, log_fn=lambda m: self.q.put(("log_lc", m)))

        def done(res):
            t = self.lc_out
            t.insert("end", "\n==== 结果 ====\n", "head")
            t.insert("end", res["summary"] + "\n", "ok" if res["ok"] else "bad")
            lt = res.get("local_tests")
            if lt:
                t.insert("end", "内置测试: ", "sys")
                t.insert("end", "全部通过\n" if lt["passed"] else "存在失败\n",
                         "ok" if lt["passed"] else "bad")
                for r in lt["tests"]:
                    t.insert("end", ("  ✓ " if r["ok"] else "  ✗ ") +
                             f"{r['args']} -> 期望 {r['expected']} / 实际 {r['got']}\n",
                             "ok" if r["ok"] else "bad")
                if lt.get("leak") and lt["leak"].get("detail"):
                    t.insert("end", f"内存: {lt['leak']['detail']}\n",
                             "bad" if lt["leak"]["leaky"] else "ok")
            t.insert("end", f"\n产物目录: {res.get('workspace', '')}\n", "sys")
            self.busy.discard("lc")
            self.btn_solve.state(["!disabled"])
            self.btn_explain.state(["!disabled"])

        threading.Thread(target=lambda: self._run_bg(work, done), daemon=True).start()

    def _lc_explain(self):
        slug = self._lc_sel()
        if not slug or "lc" in self.busy:
            return
        self.busy.add("lc")
        self.btn_solve.state(["disabled"])
        self.btn_explain.state(["disabled"])
        self.lc_out.delete("1.0", "end")
        self.lc_out.insert("end", "生成题解讲解…\n", "sys")

        def work():
            from modules.leetcode import explain
            return explain(slug)

        def done(text):
            self.lc_out.insert("end", str(text), "bot")
            self.busy.discard("lc")
            self.btn_solve.state(["!disabled"])
            self.btn_explain.state(["!disabled"])

        threading.Thread(target=lambda: self._run_bg(work, done), daemon=True).start()

    # ---------- 页签4：开发任务 ----------
    def _tab_task(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text=" 开发任务 ")
        row = ttk.Frame(f)
        row.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(row, text="任务").pack(side="left")
        self.task_desc = ttk.Entry(row)
        self.task_desc.pack(side="left", fill="x", expand=True, padx=6, ipady=4)
        self.task_desc.bind("<Return>", lambda e: self._task_run())
        self.btn_task = ttk.Button(row, text="运行工作流", style="Acc.TButton",
                                   command=self._task_run)
        self.btn_task.pack(side="left")
        ttk.Label(f, text="工作流: 思考 → 计划 → 审查 →(不过回思考)→ 开发 → 代码审查 → 测试(含内存泄漏检测)，最多3轮。",
                  style="Dim.TLabel").pack(anchor="w", padx=12)
        self.task_log = make_text(f)
        self.task_log.pack(fill="both", expand=True, padx=10, pady=6)

    def _task_run(self):
        desc = self.task_desc.get().strip()
        if not desc or "task" in self.busy:
            return
        self.busy.add("task")
        self.btn_task.state(["disabled"])
        self.task_log.delete("1.0", "end")

        def work():
            from core.workflow import Workflow
            wf = Workflow(desc, kind="general", quiet=False,
                          log_fn=lambda m: self.q.put(("log_task", m)))
            return wf.run()

        def done(res):
            t = self.task_log
            t.insert("end", "\n==== 结果 ====\n", "head")
            t.insert("end", res["summary"] + "\n", "ok" if res["ok"] else "bad")
            self.busy.discard("task")
            self.btn_task.state(["!disabled"])

        threading.Thread(target=lambda: self._run_bg(work, done), daemon=True).start()

    # ---------- 页签5：训练 ----------
    def _tab_train(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text=" 训练 ")
        row = ttk.Frame(f)
        row.pack(fill="x", padx=10, pady=(10, 4))
        self.skip_distill = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="跳过蒸馏（复用已有数据集）",
                        variable=self.skip_distill).pack(side="left")
        ttk.Label(row, text="蒸馏主题数/语言").pack(side="left", padx=(16, 4))
        self.topics_n = ttk.Spinbox(row, from_=1, to=12, width=4)
        self.topics_n.set(5)
        self.topics_n.pack(side="left")
        self.btn_train = ttk.Button(row, text="开始训练", style="Acc.TButton",
                                    command=self._train_run)
        self.btn_train.pack(side="left", padx=10)
        ttk.Label(f, text="训练 = 数据蒸馏(qwen3:14b) → 知识库TF-IDF重建(含命中率评估) → 重建 learn-agent 定制模型。"
                          "完整训练约6~15分钟，期间可切其他页签继续使用。",
                  style="Dim.TLabel").pack(anchor="w", padx=12)
        self.train_log = make_text(f)
        self.train_log.pack(fill="both", expand=True, padx=10, pady=6)
        self._show_train_report()

    def _show_train_report(self):
        rep = {}
        p = data_dir() / "train_report.json"
        if p.exists():
            try:
                rep = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                rep = {}
        t = self.train_log
        t.delete("1.0", "end")
        if not rep:
            t.insert("end", "尚未训练。点击「开始训练」执行完整训练管线。\n", "sys")
            return
        k = rep.get("knowledge", {}).get("knowledge_train", {})
        m = rep.get("model", {})
        d = rep.get("distill", {})
        t.insert("end", "上次训练报告 ", "head")
        t.insert("end", f"({rep.get('started', '')}，耗时 {rep.get('seconds', '?')}s)\n", "sys")
        t.insert("end", f"知识库: {k.get('docs', '?')} 篇 / 词表 {k.get('vocab', '?')} / "
                        f"命中率 {k.get('hit_rate', 0):.0%} / 蒸馏新增 {k.get('distilled_docs', '?')} 条\n", "ok")
        t.insert("end", f"定制模型: {m.get('model', '-')} (基座 {m.get('base', '-')}, "
                        f"系统提示词 {m.get('system_chars', '?')} 字)\n", "ok")
        if d:
            t.insert("end", f"蒸馏: {d.get('pairs', '?')} 对，耗时 {d.get('seconds', '?')}s\n", "bot")

    def _train_run(self):
        if "train" in self.busy:
            return
        self.busy.add("train")
        self.btn_train.state(["disabled"])
        self.train_log.insert("end", "\n===== 训练开始（日志见下方）=====\n", "head")

        def work():
            import io
            from contextlib import redirect_stdout
            from training.run_training import run
            buf = io.StringIO()
            with redirect_stdout(buf):
                run(skip_distill=self.skip_distill.get(),
                    topics_limit=int(self.topics_n.get() or 5))
            return buf.getvalue()

        def done(text):
            self.train_log.insert("end", text, "sys")
            self.train_log.insert("end", "✅ 训练完成，learn-agent 模型已更新\n", "ok")
            self.busy.discard("train")
            self.btn_train.state(["!disabled"])
            self._load_models_async()

        threading.Thread(target=lambda: self._run_bg(work, done), daemon=True).start()

    # ============ 后台执行与队列 ============
    def _run_bg(self, work, done):
        """后台线程执行 work()，完成后把 done 回调排回主线程。"""
        try:
            res = work()
            self.q.put(("done", (done, res)))
        except Exception as e:
            self.q.put(("done", (done, f"[执行出错] {e}")))

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "chat_delta":
                    self._chat_stream += payload
                    t = self.chatlog
                    t.delete(self._chat_pos, "end")
                    t.insert(self._chat_pos, self._chat_stream, "bot")
                    t.see("end")
                elif kind == "chat_done":
                    self.chatlog.insert("end", "\n\n", "bot")
                    self.busy.discard("chat")
                    self.btn_send.state(["!disabled"])
                elif kind == "chat_err":
                    self.chatlog.insert("end", f"[模型不可用] {payload}\n", "bad")
                    self.busy.discard("chat")
                    self.btn_send.state(["!disabled"])
                elif kind == "models":
                    self._apply_models(payload)
                elif kind == "log_lc":
                    self.lc_out.insert("end", payload + "\n", "sys")
                    self.lc_out.see("end")
                elif kind == "log_learn":
                    self.learn_out.insert("end", payload + "\n", "sys")
                    self.learn_out.see("end")
                elif kind == "log_task":
                    self.task_log.insert("end", payload + "\n", "sys")
                    self.task_log.see("end")
                elif kind == "done":
                    cb, res = payload
                    try:
                        cb(res)
                    except Exception as e:
                        print("GUI回调异常:", e, file=sys.stderr)
        except queue.Empty:
            pass
        self.root.after(80, self._poll_queue)

    def _apply_models(self, names):
        self.models = names
        self.chat_model["values"] = names
        if not self.chat_model.get():
            self.chat_model.current(0)
        try:
            from core.knowledge import kb
            kb_docs = len(kb().docs)
        except Exception:
            kb_docs = "?"
        ext = "开" if cfg()["external_model"].get("enabled") else "未配置Key"
        self.status.config(text=f"Ollama 模型: {', '.join(names) or '离线'} | "
                                f"知识库 {kb_docs} 篇 | 外部增强: {ext}")

    def _load_models_async(self):
        threading.Thread(target=self._load_models, daemon=True).start()

    def _load_models(self):
        try:
            import requests
            names = [m["name"] for m in requests.get(
                BASE_URL + "/api/tags", timeout=3).json().get("models", [])]
        except Exception:
            names = []
        ordered = (["learn-agent"] + [m for m in names if not m.startswith("learn-agent")]) \
            if any(m.startswith("learn-agent") for m in names) else (names or ["learn-agent"])
        self.q.put(("models", ordered))


def main(smoke=False):
    ensure_dirs()
    root = tk.Tk()
    App(root, smoke=smoke)
    root.mainloop()
    if smoke:
        print("GUI SMOKE OK")


if __name__ == "__main__":
    main(smoke="--smoke" in sys.argv)
