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


class TestDB(unittest.TestCase):
    def setUp(self):
        from core.db import DBTool
        self.d = DBTool()
        st = self.d.ping()
        if not st.get("ok"):
            self.skipTest(f"MySQL 不可用: {st.get('error')}")

    def test_databases(self):
        dbs = self.d.databases()
        self.assertIn("mysql", dbs)

    def test_query_select(self):
        r = self.d.query("SELECT 1 AS a, 'b' AS b")
        self.assertTrue(r["ok"])
        self.assertEqual(r["rows"], [[1, "b"]])

    def test_query_forbidden(self):
        r = self.d.query("DROP DATABASE mysql")
        self.assertFalse(r["ok"])

    def test_query_bad_sql(self):
        r = self.d.query("SELECT * FROM no_such_table_xyz")
        self.assertFalse(r["ok"])
        self.assertIn("error", r)


class TestLanguageMatrix(unittest.TestCase):
    def test_catalog_size(self):
        from modules.learning import CATALOG, CURRICULUM
        all_langs = {**{k: c["name"] for k, c in CURRICULUM.items()}, **CATALOG}
        self.assertGreaterEqual(len(all_langs), 25, "语言矩阵应覆盖25+门")
        for group in ("typescript", "rust", "haskell", "mongodb", "shell"):
            self.assertIn(group, all_langs)

    def test_fallback_curriculum_nine_stages(self):
        from modules.learning import _fallback_curriculum
        c = _fallback_curriculum("haskell")
        self.assertEqual(len(c["stages"]), 9, "九阶段框架")
        self.assertIn("capstone", c)
        self.assertTrue(all(v for v in c["stages"].values()))

    def test_matrix_no_llm_for_unknown(self):
        """matrix/radar 对未学语言不得触发 LLM 生成（只统计内置/缓存/有进度者）。"""
        from modules.learning import LearningModule
        lm = LearningModule()
        m = lm.matrix()
        self.assertIn("python", m)
        # 未学且未生成的语言 total=0
        fresh = [k for k, v in m.items() if v["total"] == 0]
        self.assertTrue(all(m[k]["learned"] == 0 for k in fresh))


class TestAlgo(unittest.TestCase):
    def setUp(self):
        import tempfile
        from modules import algo
        self.algo = algo
        self._tmp = tempfile.TemporaryDirectory()
        algo._path = lambda: Path(self._tmp.name) / "algo_progress.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_bank_size(self):
        from modules.leetcode import PROBLEMS
        self.assertGreaterEqual(len(PROBLEMS), 20)
        from modules.algo import PROBLEM_STAGE
        for p in PROBLEMS:
            self.assertIn(p["slug"], PROBLEM_STAGE, f"{p['slug']} 未映射阶段")

    def test_plan_next_record(self):
        plan = self.algo.plan()
        self.assertIn("阶段一", plan)
        p, why = self.algo.next_problem(0)
        self.assertIsNotNone(p)
        self.algo.record(p["slug"], False, "测试失败详情")
        self.assertIn(p["slug"], self.algo.wrongbook())
        # 重做通过后清除错题
        self.algo.record(p["slug"], True, "")
        w, why2 = self.algo.next_problem(0)
        self.assertNotEqual(w["slug"], p["slug"], "已解决题目不应再次推荐")


class TestLLMFallback(unittest.TestCase):
    def test_external_disabled_falls_back(self):
        """外部模型未启用时必须优雅跳过，不得抛未处理异常。"""
        from core.llm import LLMError, LLMRouter
        r = LLMRouter()
        with self.assertRaises(LLMError):
            r._external_chat([{"role": "user", "content": "x"}])
        # 本地全挂 + 外部未启用 -> 所有通道失败应抛 LLMError 而非其他异常
        orig = r._ollama_chat
        try:
            r._ollama_chat = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
            with self.assertRaises(LLMError):
                r.chat([{"role": "user", "content": "x"}])
        finally:
            r._ollama_chat = orig

    def test_chat_recovers_on_single_channel_failure(self):
        """深度通道失败时应自动降级到快速通道。"""
        from core.llm import LLMRouter
        r = LLMRouter()
        calls = []
        def fake(model, messages, json_mode=False, think=False):
            calls.append(model)
            if "14b" in model:
                raise RuntimeError("deep down")
            return "ok"
        orig = r._ollama_chat
        try:
            r._ollama_chat = fake
            out = r.chat([{"role": "user", "content": "x"}], deep=True)
            self.assertEqual(out, "ok")
            self.assertEqual(len(calls), 2, "应依次尝试 deep->fast")
        finally:
            r._ollama_chat = orig


class TestBankReferenceSanity(unittest.TestCase):
    def test_bank_module_import(self):
        from tests.test_bank_reference import REFERENCES, PROBLEMS  # noqa: F401
        self.assertEqual(len(REFERENCES), len(PROBLEMS))


class TestWorkflow(unittest.TestCase):
    def test_review_lang_filter(self):
        """非代码文件不应做语言级静态检查（曾误报 html/css 语法错误）。"""
        from core.workflow import review_lang
        self.assertEqual(review_lang("main.py"), "python")
        self.assertEqual(review_lang("app.js"), "javascript")
        self.assertIsNone(review_lang("templates/index.html"))
        self.assertIsNone(review_lang("static/style.css"))
        self.assertIsNone(review_lang("README.md"))


class TestLearningV2(unittest.TestCase):
    def test_curriculum_integrity(self):
        from modules.learning import CURRICULUM, _flatten, _stage_of
        self.assertGreaterEqual(len(CURRICULUM), 7, "至少7门语言")
        for lang, c in CURRICULUM.items():
            self.assertIn("name", c); self.assertIn("runner", c); self.assertIn("goal", c)
            stages = c["stages"]
            self.assertTrue(any(s.startswith("L0") for s in stages), f"{lang} 缺少零基础阶段")
            self.assertIn("capstone", c)
            topics = _flatten(c)
            self.assertGreaterEqual(len(topics), 20, f"{lang} 主题过少")
            self.assertEqual(len(topics), len(set(topics)), f"{lang} 主题重复")
            for t in topics:
                self.assertTrue(_stage_of(c, t), f"{lang} 主题 {t} 无所属阶段")

    def test_progress_and_next_topic(self):
        import tempfile
        from modules.learning import LearningModule
        lm = LearningModule()
        with tempfile.TemporaryDirectory() as d:
            lm._progress_path = lambda: Path(d) / "progress.json"
            first = lm.next_topic("python")
            self.assertEqual(first, lm.flat_topics("python")[0])
            lm._mark_learned("python", first)
            second = lm.next_topic("python")
            self.assertNotEqual(first, second)
            p = lm.path("python")
            self.assertIn("✓", p) and self.assertIn("总进度", p)
            self.assertIn(second, p)

    def test_distill_flatten(self):
        from modules.learning import CURRICULUM, _flatten
        from training.distill import _topics
        self.assertTrue(set(_topics("python", 100)).issubset(set(_flatten(CURRICULUM["python"]))))


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
