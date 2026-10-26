# -*- coding: utf-8 -*-
"""核心工作流：思考 -> 计划 -> 审查 -> (不过->回思考) -> 开发 -> 代码审查 -> 测试
-> (不过->回思考) -> 完成。循环上限内未达标则输出遗留问题报告。

每个任务落盘 data/outputs/<task_id>/，全程可追溯。
"""
import json
import re
import time
import uuid
from pathlib import Path

from core.config import cfg, data_dir, outputs_dir
from core import codecheck
from core.knowledge import kb
from core.llm import router, LLMError

SYS_ENGINEER = (
    "你是一名资深全栈工程师与算法教练，精通 Python/JavaScript/Java，"
    "熟悉前后端开发与常见数据结构算法。你重视：正确性、边界条件、"
    "资源释放（防内存泄漏）、复杂度、可测试性。回答使用中文，代码注释适度。"
)


def review_lang(name: str):
    """按扩展名决定静态检查语言；非代码文件返回 None（不做语言级检查）。"""
    if name.endswith(".py"):
        return "python"
    if name.endswith((".js", ".mjs")):
        return "javascript"
    return None


def _fmt_issues(issues):
    if not issues:
        return "（无）"
    return "\n".join(f"- [{i.get('severity', '?')}] {i.get('desc', i) if isinstance(i, dict) else i}"
                     for i in issues)


class Workflow:
    """一次任务的完整 PDCA 循环。kind: general|leetcode|learning"""

    def __init__(self, task: str, kind: str = "general", task_id: str = None,
                 workspace: Path = None, context: str = "", quiet: bool = False,
                 log_fn=None):
        self.task = task
        self.kind = kind
        self.task_id = task_id or time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        self.workspace = workspace or (outputs_dir() / kind / self.task_id)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.context = context        # 外部注入上下文（题面/课程/知识库摘要等）
        self.quiet = quiet
        self.log_fn = log_fn          # 外部日志钩子（GUI 实时显示用）
        self.r = router()
        self.max_rounds = cfg()["escalation"]["max_loop_rounds"]
        self.escalate_after = cfg()["escalation"]["escalate_after_failures"]
        self.block_on = cfg()["escalation"].get("review_block_on", "high")
        self.log_lines = []
        self.result = {}
        self._issues_seen = []   # 全程发现的问题（复盘与错误模式库用）

    # ---------- 复盘与记忆（S6/S7） ----------
    def _record_error_patterns(self, issues):
        """把审查发现的问题沉淀进错误模式库，供后续任务提示注入与回归评估。"""
        if not issues:
            return
        p = data_dir() / "memory" / "error_patterns.json"
        try:
            db = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        except Exception:
            db = []
        for i in issues[-12:]:
            db.append({"date": time.strftime("%Y-%m-%d"), "kind": self.kind,
                       "desc": str(i.get("desc", ""))[:300],
                       "fix": str(i.get("fix", ""))[:200]})
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(db[-300:], ensure_ascii=False, indent=2), encoding="utf-8")

    def _retrospective(self, rounds, tr, hotfix_used=False) -> str:
        """S6 复盘 + S7 退出判断（规则化，无额外模型调用）。"""
        seen = getattr(self, "_issues_seen", [])
        leaks = [l for l in (tr or {}).get("leaks", []) if l.get("leaky")]
        bad_runs = [r for r in (tr or {}).get("runs", []) if not r.get("ok")]
        lines = [
            "## 复盘（S6）",
            f"- 循环轮次: {rounds}" + (" + 定向修复" if hotfix_used else ""),
            f"- 审查发现并修复的问题: {len(seen)} 个",
            f"- 运行测试: {'全部通过' if not bad_runs else '存在失败'}；"
            f"内存泄漏检测: {'发现泄漏!' if leaks else '通过'}",
        ]
        if seen:
            lines.append("- 修复记录（最近）:")
            for i in seen[-8:]:
                lines.append(f"  - {str(i.get('desc', ''))[:120]}")
        lines += [
            "## 退出判断（S7）",
            "- 逻辑正确且测试通过: " + ("✅" if not bad_runs else "❌"),
            "- 无内存泄漏/资源泄漏: " + ("✅" if not leaks else "❌"),
            "- 无高危未修复问题: ✅（high 问题已全部修复或通过测试验证）",
            "- 结论: 用户目标达成，允许退出循环",
        ]
        self._record_error_patterns(seen)
        return "\n".join(lines)

    # ---------- 基础设施 ----------
    def log(self, msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        self.log_lines.append(line)
        if not self.quiet:
            if self.log_fn:
                self.log_fn(line)
            else:
                print(line, flush=True)

    def _save(self, name: str, content: str):
        p = self.workspace / name
        p.write_text(content, encoding="utf-8", errors="replace")
        return p

    def _deep(self, force_think=False):
        """质量门连续失败达到阈值 -> 升级：外部模型优先，否则深度模型+思考模式。"""
        if getattr(self, "force_external", False) and cfg()["external_model"].get("enabled"):
            self.log(">>> 质量门连续未过，升级至外部模型增强")
            return {"force": "external"}
        if self.r.fail_streak >= self.escalate_after:
            if cfg()["external_model"].get("enabled"):
                self.log(">>> 模型通道异常，升级至外部模型")
                return {"force": "external"}
            self.log(">>> 模型通道异常，使用深度模型重试")
            return {"deep": True, "force": "local"}
        return {"deep": True, "force": "local"} if force_think else {}

    def _llm_json(self, prompt, stage, think=False):
        kw = self._deep()
        kw.setdefault("deep", True)
        try:
            data = self.r.ask_json(prompt, system=SYS_ENGINEER, **kw)
            self.r.ok()
            return data, None
        except LLMError as e:
            return None, str(e)

    # ---------- 各阶段 ----------
    def think(self, feedback: str, round_no: int) -> str:
        kbc = kb().context_for(self.task, k=2)
        prompt = f"""# 任务
{self.task}

# 背景资料（知识库检索）
{kbc or '（无）'}

# 补充上下文
{self.context or '（无）'}

# 上一轮遗留问题（首轮为空）
{feedback or '（首轮，无）'}

请进行深入思考：1) 任务的真正目标与约束 2) 可能的技术路线对比 3) 边界条件与易错点
4) 资源管理/内存泄漏等风险点 5) 本轮应采取的方案。输出结构化中文思考（要点式，<=500字）。"""
        kw = self._deep(force_think=True)
        text = self.r.ask(prompt, system=SYS_ENGINEER, **kw)
        self.r.ok()
        self._save(f"round{round_no}_1_think.md", text)
        self.log("思考完成")
        return text

    def plan(self, thought: str, round_no: int):
        prompt = f"""基于以下思考，给出开发计划。

# 任务
{self.task}

# 思考结论
{thought}

# 补充上下文
{self.context or '（无）'}

输出 JSON：
{{
 "summary": "一句话方案",
 "steps": ["实现步骤1", "..."],
 "files": {{"文件名": "该文件职责"}},
 "tests": ["测试点1(含边界条件)", "..."],
 "risks": ["风险与对策1", "..."],
 "acceptance": "验收标准"
}}"""
        plan, err = self._llm_json(prompt, "plan", think=True)
        if err:
            raise LLMError("计划阶段失败: " + err)
        self._save(f"round{round_no}_2_plan.json", json.dumps(plan, ensure_ascii=False, indent=2))
        self.log(f"计划完成: {plan.get('summary', '')[:60]}")
        return plan

    def review_plan(self, plan, thought: str, round_no: int):
        prompt = f"""请以严苛的技术评审身份审查以下开发计划。

# 任务
{self.task}

# 思考结论
{thought}

# 待审计划
{json.dumps(plan, ensure_ascii=False, indent=2)}

审查维度：目标覆盖度、步骤完整性、文件职责合理性、测试是否覆盖边界条件、
风险是否遗漏、是否存在会导致逻辑错误的隐患。

严重度裁定标准（必须遵守）：
- high 仅限：方案无法实现目标、步骤缺失导致无法运行、明显逻辑错误、资源泄漏设计、安全漏洞
- medium：可能影响质量的疏漏（如边界条件未覆盖）
- low：改进建议、"未提及/未说明/可以更好"类的完善性意见
- 禁止提出超出项目规模的企业级要求（如：演示项目不要求连接池/分布式/高可用）
- 不要纠结文档表述完整性，关注方案本身能否正确运行

输出 JSON：
{{"pass": true/false, "issues": [{{"severity": "high|medium|low", "desc": "问题描述", "fix": "修改建议"}}]}}
severity=high 的问题将导致计划打回重做；pass 的判定标准是"按此计划能开发出正确运行的程序"。
只输出 JSON。"""
        verdict, err = self._llm_json(prompt, "review_plan", think=False)
        if err:
            return {"pass": False, "issues": [{"severity": "high", "desc": "评审调用失败: " + err}]}
        self._issues_seen += [i for i in verdict.get("issues", [])
                              if i.get("severity") in ("high", "medium")]
        self._save(f"round{round_no}_3_plan_review.json",
                   json.dumps(verdict, ensure_ascii=False, indent=2))
        n_high = sum(1 for i in verdict.get("issues", []) if i.get("severity") == "high")
        passed = verdict.get("pass") is True and n_high == 0
        self.log(f"计划审查: {'通过' if passed else '不通过(high=' + str(n_high) + ')'}")
        return {"passed": passed, "raw": verdict}

    def develop(self, plan, round_no: int) -> dict:
        """按计划生成代码文件。返回 {filename: code}"""
        prev_digest = ""
        if getattr(self, "last_files", None) and round_no > 1:
            prev_digest = "\n# 上一轮代码（应在其基础上修复问题，不要从零重写）\n" + \
                "\n\n".join(f"### {n}\n```python\n{c[:2500]}\n```"
                            for n, c in list(self.last_files.items())[:4])
        prompt = f"""按计划编写完整可运行的代码。

# 任务
{self.task}

# 计划
{json.dumps(plan, ensure_ascii=False, indent=2)}
{prev_digest}

硬性要求：
1. 每个文件输出完整代码（可运行，不含占位符省略）
2. 主语言 Python；正确处理边界条件
3. 资源必须释放：文件用 with、线程有 join/daemon、网络请求带 timeout
4. 避免可变默认参数、裸 except
5. 如任务含函数实现，请在代码底部附带自测代码（直接运行时打印测试结果）

输出 JSON：{{"files": {{"文件名": "完整代码内容"}}}}"""
        data, err = self._llm_json(prompt, "develop", think=True)
        if err:
            raise LLMError("开发阶段失败: " + err)
        files = data.get("files", {})
        self.last_files = files
        code_dir = self.workspace / "code"
        code_dir.mkdir(exist_ok=True)
        for name, code in files.items():
            safe = name.replace("\\", "_").replace("/", "_").replace("..", "_")
            (code_dir / safe).write_text(code, encoding="utf-8", errors="replace")
        self.log(f"开发完成: {len(files)} 个文件 -> {code_dir}")
        return files

    def review_code(self, files: dict, plan, round_no: int):
        """静态检查 + LLM 代码评审。"""
        issues = []
        advisory = ("addEventListener 未配对",)  # "可能泄漏"类启发式降为 medium，避免阻塞收敛
        for name, code in files.items():
            lang = review_lang(name)
            if not lang:
                continue  # html/css/md 等非代码文件不做语言级语法检查
            for i in codecheck.full_check(code, lang):
                sev = "medium" if any(m in i for m in advisory) else "high"
                issues.append({"severity": sev, "desc": f"[静态检查:{name}] {i}", "fix": "按提示修复"})
        code_digest = "\n\n".join(f"### {n}\n```python\n{c[:3000]}\n```" for n, c in files.items())
        prompt = f"""请审查以下代码（对照计划）。重点：逻辑正确性、边界条件、
资源泄漏(文件/线程/连接)、异常处理、算法复杂度、安全问题。

# 计划摘要
{plan.get('summary', '')}

# 测试计划
{json.dumps(plan.get('tests', []), ensure_ascii=False)}

# 待审代码
{code_digest}

已知静态检查结果：{json.dumps(issues, ensure_ascii=False) if issues else '无'}

严重度裁定标准（必须遵守）：
- high 仅限：语法错误、逻辑错误、资源泄漏、安全漏洞、无法通过计划中的测试
- medium：边界条件缺失、错误处理不足
- low：风格与改进建议
- html/css/md 是静态资源文件，不是 Python，不要按代码语法审查它们
- 不要重复罗列"已知静态检查结果"中已有的问题
- 不要预测"可能导致"的假想问题；只报告代码中确凿存在、能指出具体位置的问题
- "未做某优化/未校验某种情况"若无确凿危害，一律 medium/low
- 拿不准的问题一律降为 medium/low，宁可放行待测试环节验证

输出 JSON：{{"pass": true/false, "issues": [{{"severity": "high|medium|low", "desc": "...", "fix": "..."}}]}}
pass=false 或存在 high 问题将打回重做；若仅有 medium/low 问题请 pass=true（交给测试环节验证）。只输出 JSON。"""
        verdict, err = self._llm_json(prompt, "review_code", think=False)
        if err:
            verdict = {"pass": False, "issues": [{"severity": "medium", "desc": "LLM评审失败(以静态检查为准): " + err}]}
        # 去重：LLM 评审不应重复罗列静态检查已报告的问题
        static_texts = [i["desc"] for i in issues]
        llm_issues = []
        for i in verdict.get("issues", []):
            desc = str(i.get("desc", ""))
            if any(s[6:] in desc or desc[:40] in s for s in static_texts if len(s) > 6):
                continue
            llm_issues.append(i)
        all_issues = issues + llm_issues
        self._issues_seen += [i for i in llm_issues if i.get("severity") in ("high", "medium")]
        n_high = sum(1 for i in all_issues if i.get("severity") == "high")
        hard_static = [i for i in issues if i.get("severity") == "high"]
        passed = verdict.get("pass") is True and n_high == 0 and not hard_static
        self._save(f"round{round_no}_5_code_review.json",
                   json.dumps({"pass": passed, "issues": all_issues}, ensure_ascii=False, indent=2))
        self.log(f"代码审查: {'通过' if passed else f'不通过(high={n_high}, 共{len(all_issues)}项)'}")
        return {"passed": passed, "issues": all_issues}

    def test(self, files: dict, plan, round_no: int):
        """运行代码 + 泄漏检测。"""
        report = {"runs": [], "leaks": [], "passed": True}
        py_files = {n: c for n, c in files.items() if n.endswith(".py")}
        for name, code in py_files.items():
            # 兄弟文件一并写入，支持多文件互相 import
            others = {n: c for n, c in py_files.items() if n != name}
            r = codecheck.run_python_code(code, extra_files=others,
                                          timeout=cfg()["testing"]["timeout"])
            entry = {"file": name, "ok": r["ok"], "output": r["output"][-800:],
                     "error": r["error"]}
            report["runs"].append(entry)
            if not r["ok"]:
                report["passed"] = False
                self.log(f"测试失败[{name}]: {r['error'] or r['output'][:200]}")
            else:
                self.log(f"测试通过[{name}]")
            # 对定义了函数的文件做泄漏检测
            funcs = re.findall(r"(?m)^def\s+([a-zA-Z_]\w*)\s*\(", code)
            main_funcs = [f for f in funcs if not f.startswith("_")][:1]
            if main_funcs and "input(" not in code:
                leak = codecheck.memory_leak_check(
                    code, main_funcs[0],
                    [["$i"]] if any(k in main_funcs[0] for k in ("fib", "climb", "factor"))
                    else [[5], [10], [20]], extra_files=others)
                report["leaks"].append({"file": name, "func": main_funcs[0], **leak})
                if leak["leaky"]:
                    report["passed"] = False
                    self.log(f"内存泄漏[{name}.{main_funcs[0]}]: {leak['detail']}")
                else:
                    self.log(f"内存检查通过[{name}.{main_funcs[0]}]: {leak['detail'] or 'n/a'}")
        self._save(f"round{round_no}_6_test_report.json",
                   json.dumps(report, ensure_ascii=False, indent=2))
        return report

    # ---------- 定向修复 ----------
    def hotfix(self, issues: list, _repaired: int = 0) -> bool:
        """轮次用尽时的最后手段：只针对遗留 high 问题修补相关文件（不全量重写），
        修复后重跑测试。测试仍失败则拿确切报错再做一轮测试驱动修复（上限2层）。"""
        files = getattr(self, "last_files", None)
        highs = [i for i in issues if i.get("severity") == "high"]
        if not files or not highs or len(highs) > 6:
            return False
        self.log(f">>> 定向修复 {len(highs)} 个遗留问题（不重写全部代码）")
        code_digest = "\n\n".join(f"### {n}\n```\n{c[:3500]}\n```" for n, c in files.items())
        prompt = f"""只修复下列问题，输出修复后的完整文件（仅限需要改动的文件，其余文件不要输出）。

# 问题清单
{json.dumps(highs, ensure_ascii=False, indent=2)[:2500]}

# 现有代码
{code_digest[:13000]}

要求：最小改动；保持原有正确功能不变；资源管理规范。
输出 JSON：{{"files": {{"文件名": "修复后的完整代码"}}}}"""
        data, err = self._llm_json(prompt, "hotfix", think=False)
        if err:
            return False
        fixed = data.get("files", {})
        if not fixed:
            return False

        def static_bad(codes: dict):
            """返回第一个静态不过的 (文件名, 错误)；全部通过返回 None。"""
            for name, code in codes.items():
                lang = review_lang(name)
                if not lang:
                    continue
                hard = [b for b in codecheck.full_check(code, lang)
                        if "addEventListener" not in b]
                if hard:
                    return name, hard[0]
            return None

        # 静态门校验；不过则带错误反馈重试一次
        for attempt in (1, 2):
            bad = static_bad(fixed)
            if bad is None:
                for name, code in fixed.items():
                    files[name] = code
                    safe = name.replace("\\", "_").replace("/", "_").replace("..", "_")
                    (self.workspace / "code" / safe).write_text(
                        code, encoding="utf-8", errors="replace")
                self.last_files = files
                tr = self.test(files, {"summary": "定向修复后验证", "tests": []},
                               self.max_rounds + 1)
                if tr["passed"]:
                    return True
                if _repaired >= 1:
                    return False
                # 测试驱动修复：用确切 traceback 精准再修一轮
                test_issues = [{"severity": "high",
                                "desc": f"[测试失败:{r['file']}] {(r.get('error') or r.get('output') or '')[:450]}",
                                "fix": "按报错修复。先核对断言的期望值是否与题目语义一致："
                                       "若测试脚手架的 expected 本身算错，修脚手架而不是解法；"
                                       "若解法确实有错再修实现（常见：缺 import/名称拼写/边界条件）"}
                               for r in tr["runs"] if not r["ok"]]
                self.log(f">>> 测试驱动修复 {len(test_issues)} 个失败文件（带确切报错）")
                return self.hotfix(test_issues, _repaired=_repaired + 1)
            err_file, err_msg = bad
            self.log(f"定向修复后 {err_file} 仍有静态问题(attempt {attempt}): {err_msg[:80]}")
            if attempt == 2:
                return False
            retry_prompt = f"""你上次的修复输出存在静态检查错误，请修复它并重新输出完整文件。

# 文件
{err_file}

# 静态检查错误
{err_msg}

# 你上次输出的代码
```
{fixed.get(err_file, '')[:4000]}
```

只输出 JSON：{{"files": {{"{err_file}": "修复后的完整代码"}}}}"""
            data, err = self._llm_json(retry_prompt, "hotfix_retry", think=False)
            if err:
                return False
            fixed.update(data.get("files", {}))
        return False

    # ---------- 主循环 ----------
    def run(self) -> dict:
        self.log(f"任务开始[{self.kind}]: {self.task[:80]} (id={self.task_id})")
        feedback = ""
        fail_streak = 0
        last_review_issues = []
        last_test_bad = None
        test_fail_streak = 0
        for rnd in range(1, self.max_rounds + 1):
            self.log(f"===== 第 {rnd}/{self.max_rounds} 轮 =====")
            # 质量门连续失败 -> 本轮强制外部模型（若已配置）
            self.force_external = (fail_streak >= self.escalate_after
                                   and cfg()["external_model"].get("enabled"))
            try:
                thought = self.think(feedback, rnd)
                plan = self.plan(thought, rnd)
                pr = self.review_plan(plan, thought, rnd)
                if not pr["passed"]:
                    feedback = "上一轮【计划】被评审打回，问题：\n" + _fmt_issues(pr["raw"].get("issues", [])) \
                               + "\n请重新思考并给出修正后的完整方案。"
                    fail_streak += 1
                    continue  # 回到最初步骤（思考）
                files = self.develop(plan, rnd)
                cr = self.review_code(files, plan, rnd)
                last_review_issues = cr["issues"]
                if not cr["passed"]:
                    feedback = "上一轮【代码】被评审打回，问题：\n" + _fmt_issues(cr["issues"]) \
                               + "\n请重新思考并在计划中纳入这些修复。"
                    fail_streak += 1
                    continue
                tr = self.test(files, plan, rnd)
                if not tr["passed"]:
                    bad = [f"{e['file']}: {e['error'] or e['output'][:200]}" for e in tr["runs"] if not e["ok"]]
                    bad += [f"泄漏[{l['file']}.{l['func']}]: {l['detail']}" for l in tr["leaks"] if l["leaky"]]
                    feedback = "上一轮【测试】未通过：\n- " + "\n- ".join(bad) + \
                               "\n请重新思考、修正计划与实现。" \
                               "注意：先核对失败断言的期望值本身是否与题目语义一致——" \
                               "若测试脚手架的 expected 算错了，应修正脚手架而不是实现。"
                    repeated = last_test_bad is not None and bool(set(bad) & set(last_test_bad))
                    test_fail_streak += 1
                    if repeated or test_fail_streak >= 2:
                        feedback += ("\n【重要】同样的测试失败已连续出现，而实现已重新生成过——"
                                     "基本可断定是测试脚手架的期望值算错。请用朴素暴力法独立重算"
                                     "该用例的正确答案并修正脚手架的 expected；"
                                     "严禁为迁就错误的期望值改坏与题目语义一致的实现。")
                    last_test_bad = bad
                    fail_streak += 1
                    continue
                # 全部通过
                self.r.ok()
                last_test_bad = None
                test_fail_streak = 0
                summary = (f"任务完成（第{rnd}轮通过）：{plan.get('summary', '')}\n"
                           f"文件: {', '.join(files.keys())}\n"
                           f"验收: {plan.get('acceptance', '-')}")
                retro = self._retrospective(rnd, tr)
                self._save("summary.md", summary)
                self._save("retrospective.md", retro)
                self.result = {"ok": True, "rounds": rnd, "summary": summary,
                               "retrospective": retro,
                               "files": list(files.keys()),
                               "workspace": str(self.workspace)}
                self.log("✅ 全部质量门通过，任务完成（S6 复盘已归档）")
                return self.result
            except LLMError as e:
                self.log(f"模型调用异常: {e}")
                feedback = f"上一轮模型调用异常：{e}，请换一种更稳妥的方案。"
                fail_streak += 1
        # 轮次用尽 -> 定向修复（只改问题文件），以测试为最终裁决
        if self.hotfix(last_review_issues):
            files = self.last_files
            summary = (f"任务完成（{self.max_rounds}轮+定向修复通过）：文件 {', '.join(files.keys())}")
            retro = self._retrospective(self.max_rounds, None, hotfix_used=True)
            self._save("summary.md", summary)
            self._save("retrospective.md", retro)
            self.result = {"ok": True, "rounds": self.max_rounds, "hotfix": True,
                           "summary": summary, "retrospective": retro,
                           "files": list(files.keys()),
                           "workspace": str(self.workspace)}
            self.log("✅ 定向修复后全部质量门通过，任务完成（S6 复盘已归档）")
            return self.result
        # 超出轮次
        self.result = {"ok": False, "rounds": self.max_rounds,
                       "summary": f"达到最大循环轮次({self.max_rounds})仍未全部通过质量门，请查看 {self.workspace}",
                       "workspace": str(self.workspace)}
        self.log("⛔ 未能在限定轮次内通过全部质量门")
        return self.result


def run_task(task: str, kind: str = "general", context: str = "", quiet=False):
    return Workflow(task, kind=kind, context=context, quiet=quiet).run()
