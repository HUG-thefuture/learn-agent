# -*- coding: utf-8 -*-
"""learn-agent 单元测试（不依赖大模型在线；LLM 相关为集成测试，Ollama 在线才跑）。

运行: python -m unittest discover tests -v
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import cfg, ensure_dirs  # noqa: E402
from core import codecheck  # noqa: E402
from core.knowledge import KnowledgeBase, tokenize  # noqa: E402


def ollama_up() -> bool:
    import requests
    try:
        requests.get(cfg()["local_model"]["base_url"] + "/api/tags", timeout=3)
        return True
    except Exception:
        return False


class TestConfig(unittest.TestCase):
    def test_load(self):
        c = cfg()
        self.assertIn("local_model", c)
        self.assertTrue(c["local_model"]["base_url"].startswith("http"))


class TestKnowledge(unittest.TestCase):
    def test_tokenize(self):
        t = tokenize("Python 装饰器 decorator 用法")
        self.assertIn("decorator", t)
        self.assertTrue(any(len(x) == 2 for x in t))  # 中文二元组

    def test_train_search(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            kbx = KnowledgeBase(Path(d) / "idx.json")
            stats = kbx.train([
                {"id": "a", "title": "python 装饰器", "text": "装饰器 decorator 是包装函数的语法糖 @wraps"},
                {"id": "b", "title": "js promise", "text": "promise then catch async await 链式调用"},
            ])
            self.assertEqual(stats["docs"], 2)
            hits = kbx.search("装饰器怎么用", k=1)
            self.assertTrue(hits and hits[0]["id"] == "a")
            ev = kbx.evaluate()
            self.assertEqual(ev["hit_rate"], 1.0)


class TestCodeCheck(unittest.TestCase):
    def test_syntax_ok(self):
        self.assertEqual(codecheck.check_python_syntax("def f():\n    return 1\n"), [])

    def test_syntax_bad(self):
        self.assertTrue(codecheck.check_python_syntax("def f(:\n  pass"))

    def test_static_leak_patterns(self):
        code = "def f():\n    fp = open('x.txt')\n    return fp.read()\n"
        issues = codecheck.static_issues(code)
        self.assertTrue(any("open" in i for i in issues))
        code2 = "import requests\ndef g(u):\n    return requests.get(u).text"
        issues2 = codecheck.static_issues(code2)
        self.assertTrue(any("timeout" in i for i in issues2))

    def test_run_python_ok(self):
        r = codecheck.run_python_code("print(6*7)", timeout=10)
        self.assertTrue(r["ok"])
        self.assertIn("42", r["output"])

    def test_run_python_timeout(self):
        r = codecheck.run_python_code("while True:\n    x=1", timeout=4)
        self.assertFalse(r["ok"])
        self.assertIn("超时", r["error"])

    def test_memory_leak_detect(self):
        leaky = ("import functools\n"
                 "CACHE = {}\n"
                 "def grow(n):\n"
                 "    CACHE.setdefault(len(CACHE), 'x' * 2048)\n"
                 "    return n\n")
        v = codecheck.run_python_code(leaky, func="grow", args_spec=[[1]],
                                      rounds=50, timeout=30)
        self.assertTrue(v.get("leak") and v["leak"]["growth"] > 0,
                        "应当检测到堆增长")

    def test_full_check_js(self):
        code = "function f(){ var a = 1; if(a == 1){ eval('2'); } setInterval(()=>{},100); }"
        issues = codecheck.static_issues(code, "javascript")
        self.assertTrue(len(issues) >= 3)


class TestLeetCode(unittest.TestCase):
    GOOD_TWO_SUM = "def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen:\n            return [seen[target - n], i]\n        seen[n] = i\n"

    def test_check_solution_good(self):
        from modules.leetcode import get_problem, check_solution
        p = get_problem("two-sum")
        r = check_solution(p, self.GOOD_TWO_SUM)
        self.assertEqual(r["static"], [])
        self.assertTrue(r["passed"], f"tests: {r['tests']}")

    def test_check_solution_bad(self):
        from modules.leetcode import get_problem, check_solution
        p = get_problem("two-sum")
        r = check_solution(p, "def two_sum(nums, target):\n    return [0, 1]\n")
        self.assertFalse(r["passed"])


class TestDistill(unittest.TestCase):
    def test_load_empty(self):
        from training.distill import load_dataset
        # 未训练时文件可能不存在
        if not __import__("core.config", fromlist=["data_dir"]).data_dir() \
                .joinpath("datasets/sft_distilled.jsonl").exists():
            self.assertEqual(load_dataset(), [])
        else:
            data = load_dataset()
            self.assertTrue(all("instruction" in d and "output" in d for d in data))


class TestSeeds(unittest.TestCase):
    def test_seed_docs_valid(self):
        from training.train_knowledge import SEED_DOCS
        for d in SEED_DOCS:
            self.assertIn("id", d); self.assertIn("title", d); self.assertIn("text", d)


@unittest.skipUnless(ollama_up(), "Ollama 未运行，跳过集成测试")
class IntegrationLLM(unittest.TestCase):
    def test_router_ask(self):
        from core.llm import router
        out = router().ask("用一句话回答：1+1等于几？")
        self.assertTrue(out.strip())

    def test_workflow_two_sum(self):
        """端到端：完整工作流实现两数之和并通过质量门。"""
        from core.workflow import run_task
        res = run_task("实现力扣 two-sum：def two_sum(nums, target) 返回和为target的两个下标，"
                       "用哈希表一次遍历。文件 solution.py，底部附自测打印。", kind="general")
        self.assertTrue(res["ok"], res["summary"])


if __name__ == "__main__":
    ensure_dirs()
    unittest.main(verbosity=2)
