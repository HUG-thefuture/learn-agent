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

from core.config import cfg, outputs_dir
from core import codecheck
from core.knowledge import kb
from core.llm import router, LLMError

SYS_ENGINEER = (
    "你是一名资深全栈工程师与算法教练，精通 Python/JavaScript/Java，"
    "熟悉前后端开发与常见数据结构算法。你重视：正确性、边界条件、"
    "资源释放（防内存泄漏）、复杂度、可测试性。回答使用中文，代码注释适度。"
)


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
风险是否遗漏、是否存在会导致逻辑错误的隐患。输出 JSON：
{{"pass": true/false, "issues": [{{"severity": "high|medium|low", "desc": "问题描述", "fix": "修改建议"}}]}}
severity=high 的问题将导致计划打回重做。只输出 JSON。"""
        verdict, err = self._llm_json(prompt, "review_plan", think=False)
        if err:
            return {"pass": False, "issues": [{"severity": "high", "desc": "评审调用失败: " + err}]}
        self._save(f"round{round_no}_3_plan_review.json",
                   json.dumps(verdict, ensure_ascii=False, indent=2))
        n_high = sum(1 for i in verdict.get("issues", []) if i.get("severity") == "high")
        passed = verdict.get("pass") is True and n_high == 0
        self.log(f"计划审查: {'通过' if passed else '不通过(high=' + str(n_high) + ')'}")
        return {"passed": passed, "raw": verdict}

    def develop(self, plan, round_no: int) -> dict:
        """按计划生成代码文件。返回 {filename: code}"""
        prompt = f"""按计划编写完整可运行的代码。

# 任务
{self.task}

# 计划
{json.dumps(plan, ensure_ascii=False, indent=2)}

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
        for name, code in files.items():
            lang = "javascript" if name.endswith((".js", ".mjs")) else "python"
            for i in codecheck.full_check(code, lang):
                issues.append({"severity": "high", "desc": f"[静态检查:{name}] {i}", "fix": "按提示修复"})
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

输出 JSON：{{"pass": true/false, "issues": [{{"severity": "high|medium|low", "desc": "...", "fix": "..."}}]}}
pass=false 或存在 high 问题将打回重做。只输出 JSON。"""
        verdict, err = self._llm_json(prompt, "review_code", think=False)
        if err:
            verdict = {"pass": False, "issues": [{"severity": "medium", "desc": "LLM评审失败(以静态检查为准): " + err}]}
        all_issues = issues + verdict.get("issues", [])
        n_high = sum(1 for i in all_issues if i.get("severity") == "high")
        passed = verdict.get("pass") is True and n_high == 0 and not issues
        if issues:
            passed = False
        self._save(f"round{round_no}_5_code_review.json",
                   json.dumps({"pass": passed, "issues": all_issues}, ensure_ascii=False, indent=2))
        self.log(f"代码审查: {'通过' if passed else f'不通过(high={n_high}, 共{len(all_issues)}项)'}")
        return {"passed": passed, "issues": all_issues}

    def test(self, files: dict, plan, round_no: int):
        """运行代码 + 泄漏检测。"""
        report = {"runs": [], "leaks": [], "passed": True}
        for name, code in files.items():
            if not name.endswith(".py"):
                continue
            has_main = "__main__" in code or re.search(r"(?m)^print\(", code)
            r = codecheck.run_python_code(code, timeout=cfg()["testing"]["timeout"])
            entry = {"file": name, "ok": r["ok"], "output": r["output"][-800:],
                     "error": r["error"]}
            report["runs"].append(entry)
            if not r["ok"]:
                report["passed"] = False
                self.log(f"测试失败[{name}]: {r['error'] or r['output'][:200]}")
            else:
                self.log(f"测试通过[{name}]")
            # 对定义了函数的文件做泄漏检测
            import re as _re
            funcs = _re.findall(r"(?m)^def\s+([a-zA-Z_]\w*)\s*\(", code)
            main_funcs = [f for f in funcs if not f.startswith("_")][:1]
            if main_funcs and "input(" not in code:
                leak = codecheck.memory_leak_check(code, main_funcs[0], [["$i"]] if any(
                    k in main_funcs[0] for k in ("fib", "climb", "factor")) else [[5], [10], [20]])
                report["leaks"].append({"file": name, "func": main_funcs[0], **leak})
                if leak["leaky"]:
                    report["passed"] = False
                    self.log(f"内存泄漏[{name}.{main_funcs[0]}]: {leak['detail']}")
                else:
                    self.log(f"内存检查通过[{name}.{main_funcs[0]}]: {leak['detail'] or 'n/a'}")
        self._save(f"round{round_no}_6_test_report.json",
                   json.dumps(report, ensure_ascii=False, indent=2))
        return report

    # ---------- 主循环 ----------
    def run(self) -> dict:
        self.log(f"任务开始[{self.kind}]: {self.task[:80]} (id={self.task_id})")
        feedback = ""
        fail_streak = 0
        best = None
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
                               "\n请重新思考、修正计划与实现。"
                    fail_streak += 1
                    continue
                # 全部通过
                self.r.ok()
                summary = (f"任务完成（第{rnd}轮通过）：{plan.get('summary', '')}\n"
                           f"文件: {', '.join(files.keys())}\n"
                           f"验收: {plan.get('acceptance', '-')}")
                self._save("summary.md", summary)
                self.result = {"ok": True, "rounds": rnd, "summary": summary,
                               "files": list(files.keys()),
                               "workspace": str(self.workspace)}
                self.log("✅ 全部质量门通过，任务完成")
                return self.result
            except LLMError as e:
                self.log(f"模型调用异常: {e}")
                feedback = f"上一轮模型调用异常：{e}，请换一种更稳妥的方案。"
                fail_streak += 1
            best = {"rounds": rnd}
        # 超出轮次
        self.result = {"ok": False, "rounds": self.max_rounds,
                       "summary": f"达到最大循环轮次({self.max_rounds})仍未全部通过质量门，请查看 {self.workspace}",
                       "workspace": str(self.workspace)}
        self.log("⛔ 未能在限定轮次内通过全部质量门")
        return self.result


def run_task(task: str, kind: str = "general", context: str = "", quiet=False):
    return Workflow(task, kind=kind, context=context, quiet=quiet).run()
