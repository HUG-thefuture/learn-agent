# -*- coding: utf-8 -*-
"""评估脚本（规范：训练与优化须可评估）。

评估项：
1. 环境：本地模型/数据库/网络 可用性
2. 知识库：文档数/词表/检索命中率（RAG 质量）
3. 判题器自检：已知正确/错误解法的判定准确率
4. 工作流：历史任务产物统计（成功率/平均轮次/定向修复使用率）
5. 错误模式库：累计错误模式数（提示优化依据）

运行: python main.py eval  或  python -m evals.run_eval
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import data_dir, ensure_dirs  # noqa: E402


def eval_env() -> dict:
    out = {}
    try:
        import requests
        from core.config import cfg
        r = requests.get(cfg()["local_model"]["base_url"] + "/api/tags", timeout=3)
        out["ollama"] = {"ok": r.ok, "models": [m["name"] for m in r.json()["models"]]}
    except Exception as e:
        out["ollama"] = {"ok": False, "error": str(e)[:100]}
    try:
        from core.db import db
        out["mysql"] = db().ping()
    except Exception as e:
        out["mysql"] = {"ok": False, "error": str(e)[:100]}
    try:
        from core import websearch
        hits = websearch.search("python教程", limit=1)
        out["web"] = {"ok": bool(hits), "results": len(hits)}
    except Exception as e:
        out["web"] = {"ok": False, "error": str(e)[:100]}
    return out


def eval_kb() -> dict:
    from core.knowledge import kb
    ev = kb().evaluate()
    return {"docs": len(kb().docs), "vocab": len(kb().idf), **ev}


def eval_judge() -> dict:
    """判题器自检：好解法必须通过，坏解法必须被拒。"""
    from modules.leetcode import get_problem, check_solution
    good = ("def two_sum(nums, target):\n"
            "    seen = {}\n"
            "    for i, n in enumerate(nums):\n"
            "        if target - n in seen:\n"
            "            return [seen[target - n], i]\n"
            "        seen[n] = i\n")
    p = get_problem("two-sum")
    good_ok = check_solution(p, good)["passed"]
    bad_ok = check_solution(p, "def two_sum(nums, target):\n    return [0, 1]\n")["passed"]
    return {"good_accepted": good_ok, "bad_rejected": not bad_ok,
            "judge_correct": good_ok and not bad_ok}


def eval_workflows() -> dict:
    outs = data_dir() / "outputs"
    stats = {"tasks": 0, "success": 0, "hotfix": 0, "rounds": []}
    if outs.exists():
        for d in outs.rglob("summary.md"):
            stats["tasks"] += 1
            if "完成" in d.read_text(encoding="utf-8", errors="replace")[:60]:
                stats["success"] += 1
    rep = data_dir() / "train_report.json"
    if rep.exists():
        stats["last_train"] = json.loads(rep.read_text(encoding="utf-8")).get("started")
    ep = data_dir() / "memory" / "error_patterns.json"
    if ep.exists():
        try:
            stats["error_patterns"] = len(json.loads(ep.read_text(encoding="utf-8")))
        except Exception:
            stats["error_patterns"] = 0
    return stats


def run() -> dict:
    ensure_dirs()
    t0 = time.time()
    report = {"date": time.strftime("%Y-%m-%d %H:%M"),
              "env": eval_env(), "kb": eval_kb(),
              "judge": eval_judge(), "workflows": eval_workflows(),
              "seconds": 0}
    report["seconds"] = round(time.time() - t0, 1)
    out = data_dir() / "evals" / f"eval_{time.strftime('%Y%m%d_%H%M')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[eval] 报告已保存: {out}")
    return report


if __name__ == "__main__":
    run()
