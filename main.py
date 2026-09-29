# -*- coding: utf-8 -*-
"""learn-agent 命令行入口。

常用命令：
  python main.py chat                      交互对话（默认用训练出的 learn-agent 模型）
  python main.py learn python 装饰器        学习主题（教程+沉淀知识库）
  python main.py quiz python 生成器         生成测验
  python main.py solve two-sum             解力扣题（走完整工作流）
  python main.py problems                  列出题库
  python main.py task "用Python实现xxx"     通用开发任务（完整工作流）
  python main.py dev my-app --stack fastapi 生成前后端脚手架
  python main.py ask "..."                 单问（快模型）
  python main.py tools "搜索xxx并总结"      function-calling 工具循环
  python main.py kb "查询知识"             知识库检索
  python main.py train                     一键训练
  python main.py serve                     启动 Web 控制台
"""
import argparse
import json
import sys

# Windows 控制台中文输出保护
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))

from core.config import cfg, ensure_dirs  # noqa: E402


def cmd_chat(args):
    from core.llm import router
    import subprocess
    r = router()
    if args.model:
        model = args.model
    else:
        model = "learn-agent"  # 优先用训练出的定制模型
        import requests
        try:
            names = [m["name"] for m in requests.get(
                cfg()["local_model"]["base_url"] + "/api/tags", timeout=3).json()["models"]]
            if model not in names and model + ":latest" not in names:
                model = cfg()["local_model"]["fast_model"]
        except Exception:
            model = cfg()["local_model"]["fast_model"]
    print(f"== learn-agent 对话模式 (模型: {model})，输入 exit 退出 ==")
    history = [{"role": "system", "content": "你是 learn-agent 编程学习助手。回答用中文。"}]
    while True:
        try:
            q = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q.lower() in ("exit", "quit", "q"):
            break
        history.append({"role": "user", "content": q})
        try:
            resp = requests.post(cfg()["local_model"]["base_url"] + "/api/chat",
                                 json={"model": model, "messages": history,
                                       "stream": False, "think": False,
                                       "options": {"temperature": 0.3}},
                                 timeout=300)
            resp.raise_for_status()
            ans = resp.json()["message"]["content"]
        except Exception as e:
            ans = f"[模型调用失败: {e}]"
            ans = r.ask(q) if model == "learn-agent" else ans  # 降级路由
        print("助手>", ans)
        history.append({"role": "assistant", "content": ans})


def cmd_learn(args):
    from modules.learning import LearningModule
    print(LearningModule().learn(args.lang, args.topic))


def cmd_quiz(args):
    from modules.learning import LearningModule
    data = LearningModule().quiz(args.lang, args.topic)
    for i, q in enumerate(data.get("questions", []), 1):
        print(f"\n[{i}] {q.get('type')}: {q.get('question')}")
        for o in q.get("options", []):
            print("   ", o)
        print(f"    答案: {q.get('answer')}\n    解析: {q.get('explain', '')}")


def cmd_problems(_args):
    from modules.leetcode import list_problems
    for p in list_problems():
        print(f"{p['slug']:<22} {p['title']:<28} {p['difficulty']}")


def cmd_solve(args):
    from modules.leetcode import solve
    res = solve(args.slug)
    print("\n==== 结果 ====")
    print(res["summary"])
    if res.get("local_tests"):
        t = res["local_tests"]
        print(f"内置测试: {'全部通过' if t['passed'] else '存在失败'}")
        for r in t["tests"]:
            mark = "✓" if r["ok"] else "✗"
            print(f"  {mark} {r['args']} -> 期望 {r['expected']} / 实际 {r['got']}")
        if t.get("leak"):
            print(f"内存检查: {t['leak']['detail'] or '未运行'}"
                  f"{' [泄漏!]' if t['leak']['leaky'] else ''}")


def cmd_task(args):
    from core.workflow import run_task
    res = run_task(args.desc, kind="general")
    print("\n==== 结果 ====")
    print(res["summary"])


def cmd_dev(args):
    from modules.devkit import DevToolkit
    proj = DevToolkit().scaffold(args.name, args.stack)
    print(f"项目已生成: {proj}")
    print(f"体检报告: {(proj / 'check_report.txt').read_text(encoding='utf-8')}")


def cmd_ask(args):
    from core.llm import router
    print(router().ask(args.prompt, deep=args.deep))


def cmd_tools(args):
    from modules.devkit import tool_loop
    print(tool_loop(args.prompt))


def cmd_kb(args):
    from core.knowledge import kb
    for h in kb().search(args.query, k=args.k):
        print(f"[{h['score']}] {h['title']} ({h['lang']}) {h['source']}")
        print("   ", h["text"][:120].replace("\n", " "))


def cmd_train(args):
    from training.run_training import run
    report = run(skip_distill=args.skip_distill, use_external=not args.no_external,
                 topics_limit=args.topics)
    print(json.dumps({k: v for k, v in report.items() if k != "distill"},
                     ensure_ascii=False, indent=2))


def cmd_serve(_args):
    from webapp.app import app
    print("Web 控制台: http://127.0.0.1:7860")
    app.run(host="127.0.0.1", port=7860, debug=False)


def cmd_gui(_args):
    from gui.app import main as gui_main
    gui_main()


def main():
    ensure_dirs()
    ap = argparse.ArgumentParser(prog="learn-agent",
                                 description="编程学习与开发 Agent（本地大模型驱动）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("chat").set_defaults(fn=cmd_chat)
    p = sub.add_parser("learn"); p.add_argument("lang"); p.add_argument("topic")
    p.set_defaults(fn=cmd_learn)
    p = sub.add_parser("quiz"); p.add_argument("lang"); p.add_argument("topic")
    p.set_defaults(fn=cmd_quiz)
    sub.add_parser("problems").set_defaults(fn=cmd_problems)
    p = sub.add_parser("solve"); p.add_argument("slug"); p.set_defaults(fn=cmd_solve)
    p = sub.add_parser("task"); p.add_argument("desc"); p.set_defaults(fn=cmd_task)
    p = sub.add_parser("dev"); p.add_argument("name")
    p.add_argument("--stack", default="fastapi"); p.set_defaults(fn=cmd_dev)
    p = sub.add_parser("ask"); p.add_argument("prompt")
    p.add_argument("--deep", action="store_true"); p.set_defaults(fn=cmd_ask)
    p = sub.add_parser("tools"); p.add_argument("prompt"); p.set_defaults(fn=cmd_tools)
    p = sub.add_parser("kb"); p.add_argument("query"); p.add_argument("--k", type=int, default=3)
    p.set_defaults(fn=cmd_kb)
    p = sub.add_parser("train")
    p.add_argument("--skip-distill", action="store_true")
    p.add_argument("--no-external", action="store_true")
    p.add_argument("--topics", type=int, default=6, help="每种语言蒸馏的主题数上限")
    p.set_defaults(fn=cmd_train)
    sub.add_parser("serve").set_defaults(fn=cmd_serve)
    sub.add_parser("gui").set_defaults(fn=cmd_gui)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
