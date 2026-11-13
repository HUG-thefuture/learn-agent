# -*- coding: utf-8 -*-
"""learn-agent 单元测试（不依赖大模型在线；LLM 相关为集成测试，Ollama 在线才跑）。

运行: python -m unittest discover tests -v
"""
import json
import sys
import tempfile
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

    def test_run_python_chinese_output_not_mojibake(self):
        """回归：Windows 子进程默认 GBK 输出曾被按 UTF-8 解码，导致中文变乱码。

        修复方式：子进程强制 PYTHONIOENCODING=utf-8 + 父进程按 bytes 解码。
        这里断言 stdout 与 stderr 的中文都完整可读（不能出现 U+FFFD 替换符）。
        """
        r = codecheck.run_python_code("print('平方列表: [1, 4, 9]')", timeout=10)
        self.assertTrue(r["ok"])
        self.assertIn("平方列表", r["output"], f"中文输出被破坏: {r['output']!r}")
        self.assertNotIn("\ufffd", r["output"], "输出中不应出现解码替换符")

        r2 = codecheck.run_python_code("raise ValueError('中文报错信息')", timeout=10)
        self.assertFalse(r2["ok"])
        self.assertIn("中文报错信息", r2["output"], f"中文报错被破坏: {r2['output']!r}")
        self.assertNotIn("\ufffd", r2["output"])

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
        """云端未启用时必须优雅跳过：通道池不含云端条目，全失败抛 LLMError 而非其他异常。"""
        from core.llm import LLMError, LLMRouter
        r = LLMRouter()
        # 屏蔽真实云端配置，测试确定性：云端禁用 → 任何档位的云端通道池都应为空
        r.cloud = {"enabled": False, "models": []}
        self.assertEqual(r._cloud_tier(strong=True), [])
        self.assertEqual(r._cloud_tier(strong=False), [])
        # 本地全挂 + 云端未启用 -> 所有通道失败应抛 LLMError 而非其他异常
        orig = r._ollama_chat
        try:
            r._ollama_chat = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
            with self.assertRaises(LLMError):
                r.chat([{"role": "user", "content": "x"}])
        finally:
            r._ollama_chat = orig

    def test_chat_recovers_on_single_channel_failure(self):
        """深度通道失败时应自动降级到快速通道（屏蔽云端 + mock 本地，纯路由可复现）。"""
        from core.llm import LLMRouter
        r = LLMRouter()
        r.cloud = {"enabled": False, "models": []}  # 不碰真实云端通道
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


class TestLLMJsonResilience(unittest.TestCase):
    """结构化输出韧性：推理模型把思考写进 reasoning_content / 空 content 时不崩，坏通道自动换下一条。"""
    import core.llm as _llm_mod

    def _fake_post(self, responses):
        class _Resp:
            def __init__(self, d):
                self._d = d
            def raise_for_status(self):
                pass
            def json(self):
                return self._d
        seq = list(responses)
        def fake(url, headers=None, json=None, timeout=None):
            return _Resp(seq.pop(0) if seq else {})
        return fake

    def test_reasoning_not_treated_as_answer(self):
        """content=None 且 reasoning 是纯思考文字（无 JSON）时，json_mode 返回空串而非思考文字。"""
        from core.llm import LLMRouter
        r = LLMRouter()
        r._ollama_chat = lambda *a, **k: ""
        reason = ("Let me design 3-4 exercises on iterators and generators for Python learners "
                  "who have learned: conditionals and loops, lists/dicts/sets/tuples, functions, "
                  "strings and formatting, file I/O, classes and objects.")
        orig = self._llm_mod.requests.post
        self._llm_mod.requests.post = self._fake_post([
            {"choices": [{"message": {"content": None, "reasoning_content": reason},
                          "finish_reason": "stop"}]}])
        try:
            entry = {"model": "m", "base_url": "http://x", "api_key": "k"}
            out = r._cloud_entry_chat(entry, [{"role": "user", "content": "x"}], json_mode=True)
            self.assertEqual(out, "", "纯思考文字不应被当作答案")
        finally:
            self._llm_mod.requests.post = orig

    def test_reasoning_json_recovered_in_json_mode(self):
        """content=None 且 reasoning 是合法 JSON 时，json_mode 应回退并从 reasoning 恢复。"""
        from core.llm import LLMRouter, extract_json
        r = LLMRouter()
        r._ollama_chat = lambda *a, **k: ""
        orig = self._llm_mod.requests.post
        self._llm_mod.requests.post = self._fake_post([
            {"choices": [{"message": {"content": None,
                          "reasoning_content": '{"topic": "x", "items": [{"title": "t"}]}'},
                          "finish_reason": "stop"}]}])
        try:
            entry = {"model": "m", "base_url": "http://x", "api_key": "k"}
            out = r._cloud_entry_chat(entry, [{"role": "user", "content": "x"}], json_mode=True)
            data = extract_json(out)
            self.assertEqual(data, {"topic": "x", "items": [{"title": "t"}]})
        finally:
            self._llm_mod.requests.post = orig

    def test_chat_skips_non_json_channel(self):
        """json_mode：第一条返回非 JSON 思考文字、第二条返回合法 JSON → 应落到第二条。"""
        from core.llm import LLMRouter
        r = LLMRouter()
        r.cloud = {"enabled": False, "models": []}
        calls = []
        def fake(model, messages, json_mode=False, think=False):
            calls.append(model)
            if "14b" in model:
                return "Let me think… no JSON here."
            return '{"ok": true}'
        orig = r._ollama_chat
        try:
            r._ollama_chat = fake
            out = r.chat([{"role": "user", "content": "x"}], deep=True, json_mode=True)
            self.assertEqual(out, '{"ok": true}')
            self.assertEqual(len(calls), 2, "第一条非 JSON 应被判失败并换第二条")
        finally:
            r._ollama_chat = orig

    def test_chat_skips_empty_channel(self):
        """json_mode：第一条返回空串 → 应落到第二条。"""
        from core.llm import LLMRouter
        r = LLMRouter()
        r.cloud = {"enabled": False, "models": []}
        calls = []
        def fake(model, messages, json_mode=False, think=False):
            calls.append(model)
            if "14b" in model:
                return ""
            return '{"ok": 1}'
        orig = r._ollama_chat
        try:
            r._ollama_chat = fake
            out = r.chat([{"role": "user", "content": "x"}], deep=True, json_mode=True)
            self.assertEqual(out, '{"ok": 1}')
        finally:
            r._ollama_chat = orig

    def test_ask_json_strips_thinking_prefix(self):
        """ask_json 对「思考前言 + 紧跟 JSON」应能解析。"""
        from core.llm import LLMRouter
        r = LLMRouter()
        r.cloud = {"enabled": False, "models": []}
        text = "Let me design the exercises.\n\n{\"items\": [1, 2, 3]}"
        orig = r._ollama_chat
        try:
            r._ollama_chat = lambda *a, **k: text
            data = r.ask_json("出一份练习", deep=True, force="local")
            self.assertEqual(data, {"items": [1, 2, 3]})
        finally:
            r._ollama_chat = orig


class TestDSHGateway(unittest.TestCase):
    """DeepSeek Harness 本机通道网关集成（QoderCN/Trae/Buddy 账号模型枚举）。"""
    import core.llm as _llm_mod

    def test_entries_only_use_authorized_channels(self):
        """无网络时优雅返回空；有网关时只接入已实测可用的账号通道，且档位齐全。

        接入前缀（core/llm.py::GATEWAY_PREFIXES）：workbuddy-cn / qodercn / qoder /
        trae / buddy / cline / workbuddy / our-free-model / zcode。
        实测无授权/已失效的通道必须排除：pi-github-copilot(502)、
        deepseek-official(402)、st-daily-use(502)。

        注意 zcode：它报的是「当日额度已用尽」（会按自然日恢复），属于 quota
        而非通道损坏，因此接入是对的——探活脚本与 here 都不该把它当"坏通道"。
        """
        from core.llm import LLMRouter
        cls = LLMRouter
        try:
            entries = cls._dsh_gateway_entries()
        except Exception as e:  # pragma: no cover
            self.fail(f"_dsh_gateway_entries 不应抛异常: {e}")
        if not entries:
            self.skipTest("DSH 网关不可达，跳过")
        allowed = cls.GATEWAY_PREFIXES
        blocked = ("pi-github-copilot/", "deepseek-official/", "deepseek/",
                   "deepseek-account/", "st-daily-use/",
                   "nvidia/", "amd/")
        for e in entries:
            self.assertIn("name", e)
            self.assertIn("tier", e)
            self.assertIn("model", e)
            self.assertTrue(e["model"].startswith(allowed),
                            f"只应接入已授权账号通道，得到 {e['model']}")
            self.assertFalse(e["model"].startswith(blocked),
                             f"无授权/失效通道不该接入：{e['model']}")
        tiers = [e["tier"] for e in entries]
        self.assertIn("strong", tiers)
        self.assertIn("fast", tiers)
        # strong 条目（排序后）应整体排在 fast 之前
        first_fast = tiers.index("fast")
        self.assertTrue(all(t == "strong" for t in tiers[:first_fast]),
                        "强档条目应排在 fast 之前")

    def test_gateway_excludes_unauthorized_subpaths(self):
        """cline-pass（需额外订阅，实测 403）与 workbuddy 的 gpt-*/grok-*（400）必须排除。"""
        from core.llm import LLMRouter
        cls = LLMRouter
        # 肯定不该接
        for bad in ("cline/cline-pass/deepseek-v4-pro",
                    "cline/cline-pass/kimi-k3",
                    "workbuddy/gpt-6-astra",
                    "workbuddy/grok-4.7",
                    "workbuddy/gemini-3.8-flash",
                    "st-daily-use/deepseek-v4-flash",
                    "pi-github-copilot/claude-opus-4.8"):
            self.assertFalse(cls._is_gateway_model(bad), f"不该接入: {bad}")
        # 应该在白名单内
        for good in ("cline/anthropic/claude-opus-5.5",
                     "cline/openai/gpt-6.1-sol",
                     "workbuddy/glm-5.3",
                     "workbuddy/kimi-k3",
                     "qoder/ultimate",
                     "zcode/GLM-5.3",          # 仅当日额度，会按日恢复
                     "workbuddy-cn/deepseek-v4-pro"):
            self.assertTrue(cls._is_gateway_model(good), f"应该接入: {good}")

    def test_flagship_models_survive_caps(self):
        """通道限额不能把该通道最强的模型切掉（回归：曾先切片后排序）。

        cline 有 30+ 模型，限额只取前 3；必须保证入选的是 opus/gpt 这类旗舰，
        而不是按网关返回顺序碰巧排在前面的免费小模型。
        """
        from core.llm import LLMRouter, _strong_rank
        cls = LLMRouter
        orig_cred = cls._dsh_gateway_credential
        orig_get = cls.__dict__["_dsh_gateway_entries"].__func__.__globals__["requests"].get

        class _R:
            def raise_for_status(self): pass

            def json(self):
                return {"data": [
                    {"id": "cline/cline-free/solar-mini4"},
                    {"id": "cline/nvidia/nemotron-3.5-lightning-free"},
                    {"id": "cline/reflection/beam-free"},
                    {"id": "cline/anthropic/claude-opus-5.5"},
                    {"id": "cline/openai/gpt-6.1-sol"},
                ]}

        class _Req:
            @staticmethod
            def get(*a, **k):
                return _R()

        import core.llm as llm_mod
        try:
            cls._dsh_gateway_credential = classmethod(lambda c: "fake")
            llm_mod.requests.get = _Req.get
            entries = cls._dsh_gateway_entries()
        finally:
            cls._dsh_gateway_credential = orig_cred
            llm_mod.requests.get = orig_get
        cline_strong = [e["model"] for e in entries
                        if e["model"].startswith("cline/") and e["tier"] == "strong"]
        self.assertTrue(any("claude-opus-5.5" in m for m in cline_strong),
                        f"管线排序错误，旗舰模型被切掉了：{cline_strong}")
        self.assertTrue(any("gpt-6.1-sol" in m for m in cline_strong),
                        f"旗舰模型被切掉：{cline_strong}")
        # 排序函数本身：旗舰分必须高于免费小模型
        self.assertGreater(_strong_rank("cline/anthropic/claude-opus-5.5"),
                           _strong_rank("cline/cline-free/solar-mini4"))

    def test_gateway_entries_have_max_tokens(self):
        """推理模型会先烧思考链：网关条目必须给足 max_tokens，否则正文被挤空。"""
        from core.llm import LLMRouter
        entries = LLMRouter._dsh_gateway_entries()
        if not entries:
            self.skipTest("DSH 网关不可达，跳过")
        for e in entries:
            self.assertGreaterEqual(e.get("max_tokens", 0), 2048,
                                    f"{e['model']} 未设置足够 max_tokens")

    def test_tier_mapping_qodercn_shortcodes(self):
        """qodercn 的 qfmodel/dfmodel/gfmodel 应归 fast，dmodel/gmodel 应归 strong。"""
        from core.llm import LLMRouter
        sample = [
            {"id": "qodercn/qfmodel"}, {"id": "qodercn/dfmodel"},
            {"id": "qodercn/gfmodel"}, {"id": "qodercn/dmodel"},
            {"id": "qodercn/gmodel"}, {"id": "qodercn/qmodel"},
        ]
        orig = LLMRouter._dsh_gateway_credential
        import requests as _req
        class _R:
            def raise_for_status(self): pass
            def json(self):
                return {"data": sample}
        LLMRouter._dsh_gateway_credential = classmethod(lambda cls: "fake")
        orig_post = self._llm_mod.requests.get
        try:
            self._llm_mod.requests.get = lambda *a, **k: _R()
            entries = {e["model"]: e["tier"] for e in LLMRouter._dsh_gateway_entries()}
            self.assertEqual(entries.get("qodercn/qfmodel"), "fast")
            self.assertEqual(entries.get("qodercn/dfmodel"), "fast")
            self.assertEqual(entries.get("qodercn/gfmodel"), "fast")
            self.assertEqual(entries.get("qodercn/dmodel"), "strong")
            self.assertEqual(entries.get("qodercn/gmodel"), "strong")
        finally:
            self._llm_mod.requests.get = orig_post
            LLMRouter._dsh_gateway_credential = orig


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


class TestChannelOrdering(unittest.TestCase):
    """模型调用顺序：可用性优先，兼顾性能（core.llm.LLMRouter._order_cloud）。

    不用真发请求：直接喂 _health / _lat 画像，验证排序规则。
    """

    def setUp(self):
        from core.llm import LLMRouter
        self.r = LLMRouter()
        # 隔离：不读写真实画像文件，也不受本机历史影响
        self.r._health = {}
        self.r._lat = {}
        self.r._health_path = lambda: Path(tempfile.gettempdir()) / "_t_llm_channels.json"
        self.r._save_health = lambda force=False: None

    def _names(self, entries):
        return [e["name"] for e in self.r._order_cloud(entries)]

    def test_unknown_channels_keep_config_order(self):
        """从未调用过的通道：保持配置顺序，不重排。"""
        entries = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
        self.assertEqual(self._names(entries), ["a", "b", "c"])

    def test_successful_channel_moves_ahead(self):
        """调用后成功的通道，下一轮排到前面。"""
        entries = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
        self.r._note_health("c", True)
        self.assertEqual(self._names(entries)[0], "c")

    def test_failed_only_channel_sinks(self):
        """只失败过、从未成功过的通道沉到队尾。"""
        entries = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
        self.r._note_health("a", False)
        self.r._note_health("b", True)
        ordered = self._names(entries)
        self.assertEqual(ordered[-1], "a")

    def test_availability_beats_speed(self):
        """可用性优先：慢但稳定 > 快但不稳。"""
        self.r._note_health("slow_ok", True)
        self.r._note_health("slow_ok", True)
        self.r._note_latency("slow_ok", 300.0)
        self.r._note_health("fast_flaky", True)
        self.r._note_health("fast_flaky", False)
        self.r._note_health("fast_flaky", False)
        self.r._note_latency("fast_flaky", 5.0)
        entries = [{"name": "fast_flaky"}, {"name": "slow_ok"}]
        self.assertEqual(self._names(entries)[0], "slow_ok")

    def test_speed_breaks_tie(self):
        """可用性同分时，实测耗时短的优先（兼顾性能）。"""
        for n in ("slow", "fast"):
            self.r._note_health(n, True)
        self.r._note_latency("slow", 300.0)
        self.r._note_latency("fast", 20.0)
        entries = [{"name": "slow"}, {"name": "fast"}]
        self.assertEqual(self._names(entries), ["fast", "slow"])

    def test_health_survives_reload(self):
        """画像落盘后新实例能读回（重启后不必从零试错）。"""
        self.r._health = {}
        self.r._note_health("x", True)
        self.r.flush_health()
        self.assertIn("x", self.r._health)

    def test_channel_state_exposes_health(self):
        """channel_state 暴露可用性画像，供 UI 展示。"""
        self.r._note_health("m", True)
        self.r._note_health("m", False)
        st = self.r.channel_state()
        self.assertIn("m", st["health"])
        self.assertEqual(st["health"]["m"]["ok"], 1)
        self.assertAlmostEqual(st["health"]["m"]["success_rate"], 0.5)

    def test_channel_state_no_deadlock(self):
        """channel_state 持锁时不可再取同一把非重入锁（曾有的自死锁隐患）。"""
        import threading
        self.r._note_health("d", True)
        done = []

        def worker():
            self.r.channel_state()
            done.append(True)

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        t.join(5)
        self.assertTrue(done, "channel_state 超时未返回（可能自死锁）")


class TestVersionFingerprint(unittest.TestCase):
    """代码版本指纹：改了代码才变，改数据不变（launch.py 靠它决定是否重启）。"""

    def _make_tree(self, root: Path):
        (root / "core").mkdir(parents=True, exist_ok=True)
        (root / "data").mkdir(parents=True, exist_ok=True)
        (root / "core" / "a.py").write_text("x = 1\n", encoding="utf-8")
        (root / "core" / "b.yaml").write_text("k: v\n", encoding="utf-8")
        (root / "main.py").write_text("print(1)\n", encoding="utf-8")

    def test_stable_and_sensitive(self):
        from core.version import fingerprint
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "proj"
            self._make_tree(root)
            fp1 = fingerprint(root)
            fp2 = fingerprint(root)
            self.assertEqual(fp1["build"], fp2["build"], "同样内容指纹必须稳定")
            self.assertEqual(fp1["files"], 3)

            # 改源码 → 指纹必须变
            (root / "core" / "a.py").write_text("x = 2\n", encoding="utf-8")
            self.assertNotEqual(fingerprint(root)["build"], fp1["build"])

            # 改回去 → 指纹回到原值（内容哈希，不看 mtime）
            (root / "core" / "a.py").write_text("x = 1\n", encoding="utf-8")
            self.assertEqual(fingerprint(root)["build"], fp1["build"])

    def test_data_dir_changes_ignored(self):
        """data/ 是运行期产物（知识库/日志/学习内容），不该触发重启。"""
        from core.version import fingerprint
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "proj"
            self._make_tree(root)
            before = fingerprint(root)["build"]
            (root / "data" / "knowledge.json").write_text('{"a": 1}', encoding="utf-8")
            (root / "data" / "server.log").write_text("log line", encoding="utf-8")
            self.assertEqual(fingerprint(root)["build"], before,
                             "data/ 变化不应改变代码版本指纹")

    def test_removed_file_changes_build(self):
        from core.version import fingerprint
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "proj"
            self._make_tree(root)
            before = fingerprint(root)["build"]
            (root / "core" / "b.yaml").unlink()
            self.assertNotEqual(fingerprint(root)["build"], before)

    def test_real_project_fingerprint(self):
        """真实仓库能算出合理指纹（文件数不为 0，build 是 12 位 hex）。"""
        from core.version import fingerprint
        fp = fingerprint()
        self.assertGreater(fp["files"], 10)
        self.assertRegex(fp["build"], r"^[0-9a-f]{12}$")


class TestRuntimeState(unittest.TestCase):
    """实例登记：识破 PID 复用、不误杀活进程。"""

    def test_pid_alive_self(self):
        from core.runtime import pid_alive
        import os
        self.assertTrue(pid_alive(os.getpid()))

    def test_pid_alive_bogus(self):
        from core.runtime import pid_alive
        self.assertFalse(pid_alive(0))
        self.assertFalse(pid_alive(-1))
        self.assertFalse(pid_alive(999999), "不存在的 PID 应判为不存活")

    def test_pid_alive_does_not_kill_target(self):
        """关键回归：探活绝不能杀掉目标进程。

        Windows 上 os.kill(pid, 0) 不是"发0号信号"，而是直接 TerminateProcess，
        早期实现用它会误杀。这里起一个真实子进程，探活后它必须还活着。
        """
        import subprocess
        from core.runtime import pid_alive
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            self.assertTrue(pid_alive(proc.pid))
            self.assertIsNone(proc.poll(), "探活后子进程必须仍存活（未被误杀）")
        finally:
            proc.kill()
            proc.wait(timeout=10)

    def test_proc_start_ts_distinguishes(self):
        """进程创建时间可用于识破 PID 复用（同一 PID 前后两次不等）。"""
        import subprocess
        from core.runtime import proc_start_ts
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            ts = proc_start_ts(proc.pid)
            if ts is None:
                self.skipTest("当前平台取不到进程创建时间")
            import time as _t
            self.assertLess(abs(_t.time() - ts), 120, "创建时间应接近当前时间")
        finally:
            proc.kill()
            proc.wait(timeout=10)

    def test_state_roundtrip(self):
        from core.runtime import (write_state, read_state, clear_state,
                                  instance_alive, state_path)
        import os
        original = None
        if state_path().exists():
            original = state_path().read_text(encoding="utf-8")
        try:
            st = write_state("test", "deadbeef1234", "deadbeef" * 8, port=0)
            self.assertEqual(st["pid"], os.getpid())
            back = read_state()
            self.assertEqual(back["build"], "deadbeef1234")
            self.assertTrue(instance_alive(back), "自己这个进程应判为存活")
            clear_state(os.getpid())
            self.assertIsNone(read_state())
        finally:
            if original is not None:
                state_path().parent.mkdir(parents=True, exist_ok=True)
                state_path().write_text(original, encoding="utf-8")

    def test_clear_state_ignores_foreign_pid(self):
        """退出中的旧实例不能把新实例刚写的登记抹掉。"""
        from core.runtime import write_state, read_state, clear_state, state_path
        import os
        original = None
        if state_path().exists():
            original = state_path().read_text(encoding="utf-8")
        try:
            write_state("test", "aa11bb22cc33", port=0)
            clear_state(999999)  # 冒用别人的 pid：不该删
            self.assertIsNotNone(read_state(), "异主 pid 不该删除登记")
            clear_state(os.getpid())
            self.assertIsNone(read_state())
        finally:
            if original is not None:
                state_path().parent.mkdir(parents=True, exist_ok=True)
                state_path().write_text(original, encoding="utf-8")


class TestTrainReportNoTruncation(unittest.TestCase):
    """训练报告不得被截断（回归：verify 曾被 [:300] 硬切，且切到的全是 <think> 思考链）。

    历史故障：make_ollama_model.run 用 `ollama run` 的 stdout 再 [:300]，
    而 CLI 会把思考链和进度控制符一起写进 stdout —— 用户看到的是
    "半句思考过程"而不是一条完整回答。
    """

    def test_trim_to_sentence_cuts_at_boundary(self):
        """裁剪必须落在句子边界，不能停在半句。"""
        from training.make_ollama_model import _trim_to_sentence
        text = "第一句话。第二句话！第三句话？" + "填充" * 100
        out = _trim_to_sentence(text, 20)
        self.assertLessEqual(len(out), 21, "裁剪结果不应超长太多")
        self.assertTrue(out.endswith(("。…", "！…", "？…")) or out.endswith("…"),
                        f"应在句子边界收尾，实际: {out!r}")

    def test_trim_keeps_short_text_intact(self):
        from training.make_ollama_model import _trim_to_sentence
        text = "短文本。"
        self.assertEqual(_trim_to_sentence(text, 1000), "短文本。")

    def test_strip_ansi_removes_control_sequences(self):
        from training.make_ollama_model import _strip_ansi
        raw = "\x1b[?2026h\x1b[?25l回答内容\x1b[?25h"
        self.assertEqual(_strip_ansi(raw), "回答内容")

    def test_verify_meta_separates_thinking(self):
        """验证结果必须暴露 content/thinking 分离情况（thinking 不能混进 content）。"""
        from training.make_ollama_model import _verify_via_api
        import training.make_ollama_model as mom

        orig = mom._ollama_api
        try:
            mom._ollama_api = lambda *a, **k: {
                "message": {"content": "我是 learn-agent。守则：资源用 with。",
                            "thinking": "让我想想怎么自我介绍……" * 20},
                "prompt_eval_count": 123, "eval_count": 45}
            res = _verify_via_api()
            self.assertTrue(res["ok"])
            self.assertNotIn("让我想想", res["content"], "思考链不能混进回答")
            self.assertEqual(res["content"], "我是 learn-agent。守则：资源用 with。")
            self.assertGreater(res["thinking_chars"], 0)
            self.assertEqual(res["content_chars"], len(res["content"]))
        finally:
            mom._ollama_api = orig

    def test_verify_reports_error_without_raising(self):
        from training.make_ollama_model import _verify_via_api
        import training.make_ollama_model as mom

        orig = mom._ollama_api

        def boom(*a, **k):
            raise RuntimeError("ollama 挂了")

        try:
            mom._ollama_api = boom
            res = _verify_via_api()
            self.assertFalse(res["ok"])
            self.assertIn("ollama 挂了", res["error"])
        finally:
            mom._ollama_api = orig

    def test_system_prompt_respects_budget(self):
        """system prompt 必须在预算内，且报告注入/跳过统计。"""
        from training.make_ollama_model import build_system_prompt_with_stats
        prompt, stats = build_system_prompt_with_stats(budget=3000)
        self.assertLessEqual(len(prompt), 3000 + 900,  # 骨架约 600 字不可裁
                             "总量应受预算约束（骨架+预算）")
        self.assertEqual(stats["budget"], 3000)
        self.assertIn("injected", stats)
        self.assertIn("skipped", stats)
        self.assertGreater(stats["total_docs"], 0)

    def test_system_prompt_contains_skeleton(self):
        """知识注入再多也不能挤掉角色/纪律骨架。"""
        from training.make_ollama_model import build_system_prompt_with_stats
        prompt, _ = build_system_prompt_with_stats(budget=200)
        for key in ("learn-agent", "工作纪律", "编码守则", "Python", "JavaScript", "Java"):
            self.assertIn(key, prompt, f"骨架缺少「{key}」")

    def test_system_prompt_no_truncated_sentences(self):
        """注入的知识条目不该以半个字/半句话结尾（按段落边界收尾）。"""
        from training.make_ollama_model import build_system_prompt_with_stats
        prompt, _ = build_system_prompt_with_stats(budget=4000)
        # 每行要么空、要么标题、要么正常文本；拒绝"零宽截断在词中间"的明显症状
        self.assertFalse(prompt.rstrip().endswith(("，", "、", "（", "(", ":", "：")),
                         "结尾不应停在连接词/未闭合括号")

    def test_report_has_all_sections(self):
        """真实报告必须含蒸馏/知识库/模型三段与 finished 时间戳。"""
        import json as _json
        from core.config import data_dir
        p = data_dir() / "train_report.json"
        if not p.exists():
            self.skipTest("尚无训练报告")
        rep = _json.loads(p.read_text(encoding="utf-8"))
        for key in ("started", "knowledge", "model", "seconds"):
            self.assertIn(key, rep, f"报告缺少 {key}")
        # 蒸馏段：要么有统计，要么显式标记 skipped（不能凭空消失）
        self.assertIn("distill", rep, "报告缺少 distill 段（曾被过滤掉）")
        m = rep["model"]
        if m.get("ok"):
            self.assertIn("verify", m)
            # 关键回归：verify 不能再是"正好 300 字被硬切"的样子
            v = m.get("verify") or ""
            if v:
                self.assertNotIn("</think", v)
                self.assertFalse(v.lstrip().startswith("<think>"),
                                 "verify 不应是思考链（思考应与回答分离）")
            self.assertIn("knowledge", m, "模型段应带知识注入统计")


class TestKnowledgeRetrieval(unittest.TestCase):
    """知识库检索质量（回归：TF-IDF 缺长度归一化时正确文档被长文挤掉）。

    历史故障：查询「背包问题 动态规划」时，真正讲背包的《动态规划入门要点》
    (205字, 命中全部4个词) 得分 88.75，而只沾了"动态规划"3个词的题解
    《爬楼梯》(456字) 拿到 100.85 —— 长文档靠词频刷分，检索排序是错的。
    hit_rate 却是 0.97（因为还在前 3），掩盖了真实问题。
    """

    def _build_kb(self):
        """构造一个能复现"长文刷分"的迷你知识库。"""
        import tempfile
        from core.knowledge import KnowledgeBase
        d = tempfile.mkdtemp()
        k = KnowledgeBase(Path(d) / "idx.json")
        k.train([
            {"id": "short", "title": "动态规划入门要点", "lang": "general",
             "source": "seed",
             "text": "动态规划 背包问题 状态转移方程 初始化边界 滚动数组"},
            {"id": "long", "title": "爬楼梯题解", "lang": "python",
             "source": "distill",
             "text": ("动态规划 动态规划 动态规划 要理解这个 概念。"
                      + "这是一段无关的冗长说明，用来把文档撑长。" * 30)},
        ])
        return k

    def test_specific_term_beats_repetition(self):
        """命中独特词（背包）的短文档，必须排在只重复常用词的长文档前面。"""
        k = self._build_kb()
        hits = k.search("背包问题 动态规划", k=2)
        self.assertTrue(hits, "应该有检索结果")
        self.assertEqual(hits[0]["id"], "short",
                         f"讲背包的文档应排第 1，实际第 1 是 {hits[0]['title']}")

    def test_scores_are_normalized(self):
        """归一化后得分应在 (0,1] 区间（余弦相似度），不是无上界的原始点积。"""
        k = self._build_kb()
        for h in k.search("动态规划 背包", k=5):
            self.assertGreater(h["score"], 0)
            self.assertLessEqual(h["score"], 1.0001,
                                 f"得分 {h['score']} 超出余弦相似度范围")

    def test_length_does_not_inflate_score(self):
        """同样的关键词，把文档撑长不能提高相关度分数。"""
        import tempfile
        from core.knowledge import KnowledgeBase
        d = tempfile.mkdtemp()
        k = KnowledgeBase(Path(d) / "idx.json")
        k.train([
            {"id": "a", "title": "甲", "lang": "g", "source": "seed", "text": "闭包 作用域"},
            {"id": "b", "title": "乙", "lang": "g", "source": "seed",
             "text": "闭包 作用域 " + "填充词 " * 200},
        ])
        hits = k.search("闭包 作用域", k=2)
        by_id = {h["id"]: h["score"] for h in hits}
        # 纯填充不该让分数变高；理想情况短文档更高，至少不能显著更低
        self.assertLessEqual(by_id.get("b", 0), by_id.get("a", 0) + 0.02,
                             "文档被填充词撑长后得分不应反超精简文档")

    def test_context_for_respects_min_score(self):
        """无关查询不返回上下文（避免把噪声塞进提示词）。

        中文二元组分词会造假阳性："完全不相关"里含「相关」，「查询」也是常见词，
        所以纯靠余弦分数挡不住。这里靠覆盖率（min_coverage=0.4）过滤：
        实测真实查询覆盖率 50~100%、噪声 22~33%。
        """
        k = self._build_kb()
        self.assertEqual(k.context_for("zzz_完全不相关的查询_qqq", k=2), "")

    def test_coverage_filter_keeps_real_query(self):
        """覆盖率过滤不能误伤真实查询。"""
        k = self._build_kb()
        ctx = k.context_for("动态规划 背包", k=2)
        self.assertTrue(ctx, "真实查询应能检索到内容")
        self.assertIn("动态规划", ctx)

    def test_context_for_trims_at_boundary(self):
        """注入上下文按段落边界截断，不把内容切在半句。"""
        k = self._build_kb()
        ctx = k.context_for("动态规划 背包", k=1, max_chars=60)
        self.assertTrue(ctx)
        self.assertLessEqual(len(ctx), 120, "截断应大致遵守 max_chars")

    def test_context_for_marks_truncation(self):
        """被截断的内容要有省略号标记，便于模型知道不完整。"""
        k = self._build_kb()
        ctx = k.context_for("动态规划", k=1, max_chars=30)
        if ctx and "…" in ctx:
            self.assertIn("…", ctx)


class TestKbContextInjection(unittest.TestCase):
    """LLM 调用层的知识库检索注入（kb_query）。"""

    def test_ask_without_kb_query_unchanged(self):
        """默认不注入：不能给每次调用都平白增加 token。"""
        from core.llm import LLMRouter
        r = LLMRouter()
        captured = {}

        def fake_chat(msgs, **kw):
            captured["msgs"] = msgs
            return "ok"

        r.chat = fake_chat
        r.ask("普通问题")
        text = captured["msgs"][-1]["content"]
        self.assertNotIn("知识库参考", text)

    def test_ask_injects_kb_context(self):
        """kb_query 指定检索词时，提示词里应出现知识库片段。"""
        from core.llm import LLMRouter
        r = LLMRouter()
        captured = {}

        def fake_chat(msgs, **kw):
            captured["msgs"] = msgs
            return "ok"

        r.chat = fake_chat
        r.ask("请出题", kb_query="Python 装饰器")
        text = captured["msgs"][-1]["content"]
        self.assertIn("知识库参考", text)
        self.assertGreater(len(text), len("请出题") + 20)

    def test_ask_kb_query_true_uses_prompt(self):
        """kb_query=True 用提示词本身当检索查询。"""
        from core.llm import LLMRouter
        r = LLMRouter()
        captured = {}
        r.chat = lambda msgs, **kw: (captured.update(msgs=msgs), "ok")[1]
        r.ask("Python 装饰器怎么写", kb_query=True)
        self.assertIn("知识库参考", captured["msgs"][-1]["content"])

    def test_kb_failure_does_not_break_call(self):
        """知识库损坏/检索异常时，主流程照常工作（只是没有上下文）。"""
        from core.llm import LLMRouter
        import core.knowledge as km
        r = LLMRouter()
        captured = {}
        r.chat = lambda msgs, **kw: (captured.update(msgs=msgs), "ok")[1]
        orig = km.kb
        try:
            def boom():
                raise RuntimeError("索引损坏")
            km.kb = boom
            out = r.ask("问题", kb_query="随便")
            self.assertEqual(out, "ok")
        finally:
            km.kb = orig
        self.assertNotIn("知识库参考", captured["msgs"][-1]["content"])

    def test_empty_query_skips_retrieval(self):
        from core.llm import LLMRouter
        r = LLMRouter()
        self.assertEqual(r._kb_context(""), "")


class TestLayoutMultiPanel(unittest.TestCase):
    """多开页签 + 学习页边学边练（需求：练习时能同时看着学习内容）。

    纯前端特性，这里做静态断言守住关键结构，行为细节由
    tests/layout_multi_check.js 覆盖。
    """

    def _html(self):
        from pathlib import Path
        return (Path(__file__).resolve().parent.parent
                / "webapp" / "templates" / "index.html").read_text(encoding="utf-8")

    def test_multi_mode_toggle_exists(self):
        """有「多开模式」开关与网格布局，且支持把多个页签同时点亮。"""
        html = self._html()
        for key in ("id=\"multi-mode\"", "body.multi main", "toggleMultiMode",
                    "isMultiMode", "syncMultiGrid"):
            self.assertIn(key, html, f"缺少多开支持: {key}")
        # 多开时点击页签是 toggle（并存），不是一律清空
        i = html.find("document.querySelectorAll('nav button').forEach(b => b.onclick")
        j = html.find("function toggleMultiMode")
        self.assertIn("classList.toggle", html[i:j],
                      "多开时点击页签应 toggle 而不是独占")

    def test_multi_mode_never_leaves_zero_panels(self):
        """至少保留一栏可见，避免用户把所有页签都关掉后白屏。"""
        html = self._html()
        self.assertIn("至少保留一个可见", html)

    def test_single_panel_fills_width(self):
        """多开但只点亮一栏时，不能只占半宽。"""
        html = self._html()
        self.assertIn("single-panel", html)
        self.assertIn("grid-template-columns:minmax(0,1fr)", html)

    def test_split_workbench_structure(self):
        """学习页有左右两栏 + 可拖拽分隔条，单栏时用 display:contents 保持不变。"""
        html = self._html()
        for key in ("id=\"learn-main\"", "wb-left", "wb-right",
                    "id=\"wb-resizer\"", "toggleSplitWorkbench", "display:contents"):
            self.assertIn(key, html, f"缺少双栏结构: {key}")
        self.assertIn(".learn-main.split", html, "双栏应切换为 grid 布局")
        self.assertIn("position:sticky", html, "右栏应 sticky 常驻")

    def test_split_keeps_tutorial_visible(self):
        """关键回归：双栏时练习相关函数不能把左栏教程隐藏掉，否则左半屏空白。

        实现方式是各函数里按 split 状态跳过对 #learn-course-view 的隐藏。
        """
        html = self._html()
        for fn in ("async function showPracticeList",
                   "async function showTopicPractices",
                   "async function openCourseFromToc"):
            i = html.find(fn)
            self.assertGreater(i, 0, f"找不到 {fn}")
            seg = html[i:i + 1600]
            self.assertIn("split", seg,
                          f"{fn} 未感知双栏模式，可能误隐藏另一栏内容")

    def test_one_click_open_topic_both(self):
        """课程目录的 ⇔ 按钮能一键在左右栏同时打开教程与练习。"""
        html = self._html()
        self.assertIn("openTopicBoth", html)
        i = html.find("async function openTopicBoth")
        j = html.find("async function openExtraCourse")
        seg = html[i:j]
        self.assertIn("toggleSplitWorkbench", seg)
        self.assertIn("openCourseFromToc", seg)
        self.assertIn("showTopicPractices", seg)

    def test_layout_persisted(self):
        """多开 / 双栏状态记在 localStorage，刷新后恢复。"""
        html = self._html()
        self.assertIn("la-multi-mode", html)
        self.assertIn("la-learn-split", html)
        self.assertIn("restoreLayoutPrefs", html)

    def test_deep_link_params(self):
        """支持 URL 深链：?multi/panels/split/lang/topic，便于收藏与分享视图。"""
        html = self._html()
        for key in ("get('multi')", "get('split')", "get('panels')",
                    "get('lang')", "get('topic')"):
            self.assertIn(key, html, f"缺少 URL 参数支持: {key}")

    def test_default_language_is_python(self):
        """默认语言应是 Python，而不是按字典序排第一的 c++。"""
        html = self._html()
        self.assertIn("ls.value = 'python'", html)

    def test_restore_runs_before_course_toc(self):
        """布局/语言恢复必须早于课程目录拉取，否则目录会用错语言。"""
        html = self._html()
        i_restore = html.find("restoreLayoutPrefs();")
        i_toc = html.find("loadCourseToc(); // 侧边栏课程目录")
        self.assertGreater(i_restore, 0)
        self.assertGreater(i_toc, 0)
        self.assertLess(i_restore, i_toc,
                        "restoreLayoutPrefs 应先于 loadCourseToc 执行")


class TestWebPracticeHistory(unittest.TestCase):
    """历史练习查看（回归：练习只存内存 JOBS，服务重启后 UI 里彻底看不到）。"""

    @classmethod
    def setUpClass(cls):
        from webapp.app import app
        cls.c = app.test_client()

    def test_practices_list_api(self):
        """必须能从磁盘列出已保存练习（不依赖内存 JOBS）。"""
        r = self.c.get("/api/practices")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertIn("items", d)
        self.assertIn("total", d)
        for it in d["items"]:
            for key in ("file", "lang", "topic", "count", "mtime"):
                self.assertIn(key, it, f"练习项缺少 {key}")
            self.assertGreater(it["count"], 0, f"{it['file']} 题目数为 0")

    def test_practices_list_matches_disk(self):
        """接口列出的文件必须与 data/practice/*.json 完全一致。"""
        from core.config import data_dir
        d = self.c.get("/api/practices").get_json()
        disk = {p.name for p in (data_dir() / "practice").glob("*.json")}
        listed = {i["file"] for i in d["items"]}
        self.assertEqual(disk, listed, "接口列表与磁盘文件不一致")

    def test_practice_single_file_loadable(self):
        """每个列出的练习都能按 ?file= 取到完整题目（可作答）。"""
        d = self.c.get("/api/practices").get_json()
        if not d["items"]:
            self.skipTest("还没有已保存练习")
        for it in d["items"][:3]:
            j = self.c.get("/api/practices?file=" + it["file"]).get_json()
            self.assertNotIn("error", j, f"{it['file']} 取不到: {j.get('error')}")
            self.assertIn("items", j)
            self.assertTrue(j["items"], f"{it['file']} 题目为空")
            for q in j["items"]:
                for key in ("title", "task", "starter"):
                    self.assertIn(key, q, f"{it['file']} 的题目缺少 {key}")

    def test_practice_path_traversal_blocked(self):
        """?file= 不能越出 data/practice 目录。"""
        for bad in ("../progress.json", "..\\progress.json", "../../config.yaml"):
            r = self.c.get("/api/practices?file=" + bad)
            self.assertIn(r.status_code, (400, 404),
                          f"路径穿越未被拦截: {bad}")

    def test_practice_by_topic_api(self):
        """按主题汇总（课程目录标注练习数用）。"""
        d = self.c.get("/api/practices/by-topic?lang=python").get_json()
        self.assertIn("topics", d)
        for t in d["topics"]:
            self.assertIn("topic", t)
            self.assertIn("count", t)
            self.assertGreater(t["count"], 0)
            self.assertIn("files", t)

    def test_frontend_has_practice_history_entry(self):
        """前端必须有「历史练习」入口与渲染函数（不能只靠内存 JOBS）。"""
        from pathlib import Path
        html = (Path(__file__).resolve().parent.parent
                / "webapp" / "templates" / "index.html").read_text(encoding="utf-8")
        for key in ("showPracticeList", "openSavedPractice", "learn-practices",
                    "/api/practices"):
            self.assertIn(key, html, f"缺少 {key}")

    def test_course_toc_marks_practice_count(self):
        """课程目录应能显示每课的练习数（_pracByTopic / prac-badge）。"""
        from pathlib import Path
        html = (Path(__file__).resolve().parent.parent
                / "webapp" / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertIn("_pracByTopic", html)
        self.assertIn("prac-badge", html)
        self.assertIn("by-topic", html)


class TestWebExplainAndCourses(unittest.TestCase):
    """Web 端讲解目录 / 课程目录（回归：讲解被当纯文本显示、无目录可跳转）。"""

    @classmethod
    def setUpClass(cls):
        from webapp.app import app
        cls.c = app.test_client()

    def test_explains_list_api(self):
        """必须有「列出所有已保存讲解」的接口（供侧边栏目录）。"""
        r = self.c.get("/api/explains")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertIn("items", d)
        self.assertIn("total", d)
        self.assertIn("with_explain", d)
        for it in d["items"]:
            for key in ("slug", "title", "difficulty", "has_explain"):
                self.assertIn(key, it, f"目录项缺少 {key}")

    def test_explains_list_matches_saved_files(self):
        """列表里 has_explain=True 的，必须真能读到内容。"""
        from core.config import data_dir
        d = self.c.get("/api/explains").get_json()
        saved = {p.stem for p in (data_dir() / "explain").glob("*.md")}
        listed = {i["slug"] for i in d["items"] if i["has_explain"]}
        self.assertEqual(saved, listed,
                         "目录与磁盘讲解文件不一致（有文件却没列出，或列了却没有）")
        for slug in list(saved)[:3]:
            content = self.c.get(f"/api/explain/{slug}").get_json()["content"]
            self.assertTrue(content, f"{slug} 标注有讲解但读不到内容")

    def test_explain_route_not_shadowed(self):
        """/api/explains 不能被 /api/explain/<slug> 抢占。"""
        d = self.c.get("/api/explains").get_json()
        self.assertIn("items", d, "返回的应是列表结构而不是单题 content")
        self.assertNotIn("content", d)

    def test_courses_toc_api(self):
        """课程目录：按阶段分组，标注已学与文件存在性。"""
        r = self.c.get("/api/courses?lang=python")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        for key in ("lang", "stages", "done", "total", "pct", "extras"):
            self.assertIn(key, d)
        self.assertGreater(len(d["stages"]), 0)
        self.assertEqual(d["done"],
                         sum(1 for s in d["stages"] for i in s["items"] if i["learned"]))
        for s in d["stages"]:
            self.assertIn("stage", s)
            for i in s["items"]:
                for key in ("topic", "learned", "has_file", "file"):
                    self.assertIn(key, i)

    def test_courses_unknown_lang_graceful(self):
        r = self.c.get("/api/courses?lang=不存在语言")
        self.assertIn(r.status_code, (200, 400))

    def test_courses_files_are_reachable(self):
        """目录里标了 has_file 的课，通过 /api/history?file= 必须能读到全文。"""
        d = self.c.get("/api/courses?lang=python").get_json()
        files = [i["file"] for s in d["stages"] for i in s["items"] if i["has_file"]]
        if not files:
            self.skipTest("python 还没有已生成教程")
        for f in files[:3]:
            j = self.c.get("/api/history?file=" + f"python/{f}").get_json()
            self.assertNotIn("error", j, f"{f} 打不开: {j.get('error')}")
            self.assertTrue(j.get("content"), f"{f} 内容为空")

    def _html(self):
        from pathlib import Path
        return (Path(__file__).resolve().parent.parent
                / "webapp" / "templates" / "index.html").read_text(encoding="utf-8")

    def test_frontend_renders_explain_as_markdown(self):
        """讲解必须走 tutorialHtml 渲染，不能 <pre>+esc 把 Markdown 原样显示。

        历史故障：loadExplain 用 `<pre>${esc(content)}</pre>`，用户看到满屏
        `#` 和 `**`，误以为"讲解没显示出来"。
        """
        html = self._html()
        i = html.find("async function loadExplain")
        self.assertGreater(i, 0)
        body = html[i:i + 1200]
        self.assertIn("renderExplain", body,
                      "loadExplain 应调用 renderExplain（Markdown 渲染）")

    def test_frontend_has_both_tocs(self):
        """前端必须有讲解目录与课程目录的挂载点与渲染函数。"""
        html = self._html()
        for key in ("lc-toc", "lc-toc-list", "loadExplainToc",
                    "learn-toc", "learn-toc-list", "loadCourseToc", "renderCourseToc"):
            self.assertIn(key, html, f"缺少 {key}")

    def test_explain_does_not_force_regenerate(self):
        """点「讲解」时若已有本地文件，应直接展示而不是重跑 30-90s。"""
        html = self._html()
        i = html.find("async function explainBySlug")
        body = html[i:i + 1500]
        self.assertIn("cur.content", body, "应先检查是否已有本地讲解")
        self.assertIn("_forceExplain", body, '应提供"重新生成"的显式入口')


class TestLauncherHelpers(unittest.TestCase):
    """启动器判定逻辑（不真的起服务）。"""

    def test_port_free_detects_bound_port(self):
        """回归：带 SO_REUSEADDR 的 bind 在 Windows 上会"抢到"已占用端口，
        导致启动器误判空闲、不去清理旧进程。这里真的绑一个端口验证判定为 False。
        """
        import socket
        import launch
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        port = srv.getsockname()[1]
        srv.listen(1)
        try:
            self.assertFalse(launch.port_free(port), "已绑定端口必须判为不空闲")
            self.assertTrue(launch.port_in_use(port), "已监听端口应可连接")
        finally:
            srv.close()

    def test_port_free_on_unused_port(self):
        import socket
        import launch
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        # 已关闭，端口应空闲
        self.assertTrue(launch.port_free(port))
        self.assertFalse(launch.port_in_use(port))

    def test_status_shape(self):
        import launch
        st = launch.status(port=1)   # 端口 1 不用来真连，只看结构
        for key in ("build", "files", "instance", "instance_alive",
                    "stale", "port_free"):
            self.assertIn(key, st)
        self.assertRegex(st["build"], r"^[0-9a-f]{12}$")

    def test_stale_flag_logic(self):
        """登记 build 与磁盘 build 不一致时 stale=True（这就是"该重启了"）。"""
        from core.runtime import write_state, clear_state, state_path
        import launch
        original = None
        if state_path().exists():
            original = state_path().read_text(encoding="utf-8")
        try:
            write_state("web", "000000000000", "0" * 64, port=0)
            st = launch.status(port=1)
            self.assertTrue(st["instance_alive"], "本进程真活着")
            self.assertTrue(st["stale"], "登记的是旧 build，应标记为需要重启")
            self.assertEqual(st["instance"]["build"], "000000000000")
        finally:
            clear_state()
            if original is not None:
                state_path().parent.mkdir(parents=True, exist_ok=True)
                state_path().write_text(original, encoding="utf-8")

    def test_same_build_not_stale(self):
        from core.runtime import write_state, clear_state, state_path
        from core.version import fingerprint
        import launch
        original = None
        if state_path().exists():
            original = state_path().read_text(encoding="utf-8")
        try:
            fp = fingerprint()
            write_state("web", fp["build"], fp["hash"], port=0)
            st = launch.status(port=1)
            self.assertFalse(st["stale"], "登记的是当前 build，不该判定需要重启")
        finally:
            clear_state()
            if original is not None:
                state_path().parent.mkdir(parents=True, exist_ok=True)
                state_path().write_text(original, encoding="utf-8")


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
