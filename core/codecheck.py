# -*- coding: utf-8 -*-
"""代码体检：静态检查 + 测试执行 + 内存泄漏检测。

工作流的"测试"环节依赖本模块：
- check_python_syntax / check_js_syntax   语法门
- static_issues                          常见逻辑/泄漏模式启发式
- run_python_code                        子进程带超时执行
- memory_leak_check                      tracemalloc 重复调用增长检测
"""
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from core.config import cfg

PY = sys.executable

_LEAK_RUNNER = textwrap.dedent("""
import json, sys, gc, tracemalloc, importlib.util
spec = importlib.util.spec_from_file_location("solution", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
fn = getattr(mod, sys.argv[2])
rounds = int(sys.argv[3])
args_spec = json.loads(sys.argv[4])   # list of arg-lists; "$i" 会被替换为轮次i
def build(a, i):
    return [i if x == "$i" else x for x in a]
tracemalloc.start()
for i in range(rounds):
    for a in args_spec:
        try:
            fn(*build(a, i))
        except Exception:
            pass  # 个别轮次输入非法不视为失败
gc.collect()
_, base = tracemalloc.get_traced_memory()
base_cur, _ = tracemalloc.get_traced_memory()
snap_base = base_cur
for i in range(rounds):
    for a in args_spec:
        try:
            fn(*build(a, i))
        except Exception:
            pass
gc.collect()
cur, peak = tracemalloc.get_traced_memory()
print(json.dumps({"base": snap_base, "final": cur, "peak": peak,
                  "growth": cur - snap_base, "rounds": rounds}))
""")


# ---------------- 语法 ----------------
def check_python_syntax(code: str):
    try:
        ast.parse(code)
        return []
    except SyntaxError as e:
        return [f"语法错误: 第{e.lineno}行 {e.msg}"]


def check_js_syntax(code: str):
    """借助本机 node --check（可用时）。"""
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as f:
            f.write(code)
            p = f.name
        r = subprocess.run(["node", "--check", p], capture_output=True,
                           text=True, timeout=15, encoding="utf-8", errors="replace")
        Path(p).unlink(missing_ok=True)
        if r.returncode != 0:
            return ["JS语法错误: " + (r.stderr or r.stdout)[:300]]
        return []
    except FileNotFoundError:
        return []  # 无 node 则跳过
    except Exception as e:
        return [f"JS检查失败: {e}"]


# ---------------- 静态启发式 ----------------
def static_issues(code: str, lang: str = "python"):
    """常见问题启发式：返回 [描述]。用于初审与代码评审补充。"""
    issues = []
    if lang == "python":
        if re.search(r"(?m)^\s*while\s+True\s*:", code) and \
           not re.search(r"\b(break|return|raise|sys\.exit|sleep)\b", code):
            issues.append("while True 循环内未发现 break/return/raise，可能死循环")
        for m in re.finditer(r"open\(([^)]*)\)", code):
            ctx = code[max(0, m.start() - 80):m.start()]
            if "with" not in ctx.split("\n")[-1] and ".close()" not in code[m.end():m.end() + 200]:
                issues.append("open() 未用 with 或未显式 close，可能文件句柄泄漏: " +
                              code[m.start():m.end() + 30].splitlines()[0])
        if re.search(r"except\s*:\s*$", code, re.M) or re.search(r"except\s+Exception\s*:\s*pass", code):
            issues.append("存在裸 except / except:pass，异常被静默吞掉，易掩盖逻辑错误")
        if re.search(r"def\s+\w+\s*\([^)]*=\s*(\[\]|\{\})", code):
            issues.append("函数使用了可变默认参数([]/{})，跨调用共享状态")
        if re.search(r"requests\.(get|post)\((?![^)]*timeout)", code):
            issues.append("requests 请求未设置 timeout，可能永久阻塞")
        if re.search(r"\bthreading\.Thread\(.*\)\.(?!.*\.join)", code) and ".join()" not in code:
            issues.append("创建线程后未见 join/daemon 说明，可能产生悬挂线程")
        if re.search(r"(?m)^\s*global\s+", code) and "lock" not in code.lower():
            issues.append("使用 global 可变状态且未见加锁，存在并发风险")
        if re.search(r"\blist\s*\+\s*list\b.*\bfor\b.*\bfor\b", code):
            issues.append("多重循环内拼接列表，疑似 O(n^2) 以上复杂度")
        if re.search(r"\bnew\s+\w+", code):
            issues.append("Python 中误用 new 关键字")
    elif lang == "javascript":
        if re.search(r"(?<![=!<>])==(?!=)", code):
            issues.append("使用 == 比较，建议 === 避免隐式转换")
        if re.search(r"(?m)\bvar\s+", code):
            issues.append("使用 var 声明，建议 let/const（块级作用域）")
        if re.search(r"\beval\s*\(", code):
            issues.append("使用 eval，存在注入与性能风险")
        if re.search(r"setInterval\(", code) and "clearInterval" not in code:
            issues.append("setInterval 未配对 clearInterval，定时器泄漏")
        # addEventListener: 顶层一次性绑定(页面生命周期)可豁免；嵌套/循环内的绑定可能重复注册，须配对移除
        if re.search(r"addEventListener\(", code) and "removeEventListener" not in code:
            dangling = re.findall(r"(?m)^[ \t]+.*addEventListener\(", code)
            if dangling:
                issues.append("嵌套作用域中的 addEventListener 未配对移除，可能重复注册造成监听器泄漏")
        if re.search(r"fetch\(", code) and "catch" not in code and "try" not in code:
            issues.append("fetch 未处理 reject/catch")
    elif lang == "java":
        if re.search(r"new\s+(FileInputStream|FileOutputStream|BufferedReader|InputStreamReader)\(", code) \
           and "close()" not in code and "try (" not in code and "try(" not in code:
            issues.append("流资源未用 try-with-resources 或显式 close，句柄泄漏")
        if re.search(r"catch\s*\([^)]*\)\s*\{\s*\}", code):
            issues.append("空 catch 块，异常被吞掉")
        if re.search(r"\bnew\s+Thread\(", code) and ".join" not in code:
            issues.append("Thread 未 join/管理，线程生命周期失控")
        if re.search(r"System\.out\.println.*for\s*\(", code) or \
           re.search(r"for\s*\(.*\)\s*\{[^}]*System\.out\.print", code, re.S):
            issues.append("循环内打印，注意输出量与性能")
    return issues


# ---------------- 测试执行 ----------------
def run_python_code(code: str, func: str = None, args_spec: list = None,
                    rounds: int = None, timeout: int = None,
                    extra_files: dict = None) -> dict:
    """把 code 写入临时文件执行。
    - extra_files: 同项目兄弟文件（支持多文件互相 import）
    - func+args_spec 给定时：执行 leak 检测（args_spec 中 "$i" 表示轮次）
    - 否则：直接运行脚本，捕获 stdout
    返回 {ok, output, leak:{growth,...}, error}
    """
    tc = cfg()["testing"]
    timeout = timeout or tc["timeout"]
    rounds = rounds or tc["leak_rounds"]
    # 强制子进程输出 UTF-8，避免 Windows 上默认 GBK(cp936) 导致的乱码/解码错乱。
    # 父进程用 bytes 捕获后统一按 UTF-8 解码，不再依赖 text=True 的 locale 编码。
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    with tempfile.TemporaryDirectory() as d:
        sol = Path(d) / "solution.py"
        sol.write_text(code, encoding="utf-8")
        for name, content in (extra_files or {}).items():
            safe = name.replace("\\", "_").replace("/", "_").replace("..", "_")
            (Path(d) / safe).write_text(content, encoding="utf-8", errors="replace")
        if func:
            runner = Path(d) / "_leak_runner.py"
            runner.write_text(_LEAK_RUNNER, encoding="utf-8")
            cmd = [PY, str(runner), str(sol), func, str(rounds),
                   json.dumps(args_spec or [])]
        else:
            cmd = [PY, str(sol)]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=timeout,
                               env=env, cwd=d)
        except subprocess.TimeoutExpired:
            return {"ok": False, "output": "", "error": f"执行超时(>{timeout}s)，疑似死循环或超时逻辑",
                    "leak": None}
        out_bytes = (r.stdout or b"") + (("\n[stderr] ".encode("utf-8") + r.stderr)
                                          if (r.stderr or b"").strip() else b"")
        out = out_bytes.decode("utf-8", errors="replace")
        res = {"ok": r.returncode == 0, "output": out[-4000:], "error": None,
               "leak": None}
        if func and r.returncode == 0:
            for line in reversed(out.splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        res["leak"] = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    break
            res["ok"] = True
        elif func:
            res["error"] = out[-1500:]
        return res


def memory_leak_check(code: str, func: str, args_spec: list,
                      extra_files: dict = None) -> dict:
    """专项泄漏检测：growth 为两轮 N 次调用之间的堆增长。"""
    tc = cfg()["testing"]
    r = run_python_code(code, func=func, args_spec=args_spec, extra_files=extra_files,
                        rounds=tc["leak_rounds"], timeout=tc["timeout"] + 30)
    verdict = {"leaky": False, "growth": None, "detail": ""}
    if r.get("leak"):
        g = r["leak"]["growth"]
        verdict["growth"] = g
        verdict["detail"] = f"{tc['leak_rounds']}轮重复调用堆增长 {g} 字节"
        if g > tc["leak_growth_bytes"]:
            verdict["leaky"] = True
    elif r.get("error"):
        verdict["detail"] = "泄漏检测运行失败: " + r["error"][:300]
    return verdict


def full_check(code: str, lang: str = "python") -> list:
    """语法 + 静态启发式，返回问题列表。"""
    if lang == "python":
        issues = check_python_syntax(code)
    elif lang == "javascript":
        issues = check_js_syntax(code)
    else:
        issues = []
    if not issues:
        issues = static_issues(code, lang)
    return issues
