# -*- coding: utf-8 -*-
"""力扣算法模块：内置经典题库（带可运行测试用例）+ 走完整工作流解题。

解题流程复用 core.workflow：思考->计划->审查->实现->测试（含泄漏检测）。
"""
import json
from pathlib import Path

from core.config import outputs_dir
from core import codecheck
from core.workflow import Workflow, SYS_ENGINEER
from core.llm import router

# ---------------- 内置题库（python 测试） ----------------
# tests: [(args..., expected)]，函数签名统一在 signature 中
PROBLEMS = [
    {"slug": "two-sum", "title": "1. 两数之和", "difficulty": "简单",
     "desc": "给定整数数组 nums 和目标值 target，返回和为 target 的两个整数的下标（恰好一个解）。",
     "signature": "def two_sum(nums, target):",
     "tests": [([[2, 7, 11, 15], 9], [0, 1]), ([[3, 2, 4], 6], [1, 2]),
               ([[3, 3], 6], [0, 1])]},
    {"slug": "valid-parentheses", "title": "20. 有效的括号", "difficulty": "简单",
     "desc": "判断只含 ()[]{} 的字符串是否有效（正确闭合顺序）。",
     "signature": "def is_valid(s):",
     "tests": [(("()",), True), (("()[]{}",), True), (("(]",), False),
               (("([)]",), False), (("{[]}",), True), (("",), True)]},
    {"slug": "binary-search", "title": "704. 二分查找", "difficulty": "简单",
     "desc": "升序数组中查找 target，返回下标，不存在返回 -1。",
     "signature": "def search(nums, target):",
     "tests": [(([-1, 0, 3, 5, 9, 12], 9), 4), (([-1, 0, 3, 5, 9, 12], 2), -1),
               (([5], 5), 0), (([], 1), -1)]},
    {"slug": "climbing-stairs", "title": "70. 爬楼梯", "difficulty": "简单",
     "desc": "每次爬1或2阶，n 阶有几种不同爬法。",
     "signature": "def climb_stairs(n):",
     "tests": [((2,), 2), ((3,), 3), ((10,), 89), ((1,), 1)]},
    {"slug": "max-subarray", "title": "53. 最大子数组和", "difficulty": "中等",
     "desc": "找到和最大的连续子数组，返回其和。",
     "signature": "def max_sub_array(nums):",
     "tests": [(([-2, 1, -3, 4, -1, 2, 1, -5, 4],), 6), (([1],), 1),
               (([5, 4, -1, 7, 8],), 23), (([-1],), -1)]},
    {"slug": "merge-sorted-lists", "title": "21. 合并两个有序链表", "difficulty": "简单",
     "desc": "用 ListNode(val,next) 定义；合并两个升序链表为新升序链表，返回头结点。",
     "signature": "def merge_two_lists(l1, l2):  # ListNode 类已预置",
     "helper": """
class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next
def _to_list(head):
    out = []
    while head:
        out.append(head.val)
        head = head.next
    return out
def _from_list(arr):
    dummy = ListNode()
    cur = dummy
    for v in arr:
        cur.next = ListNode(v)
        cur = cur.next
    return dummy.next
""",
     "tests": [((([1, 2, 4], [1, 3, 4]),), [1, 1, 2, 3, 4, 4]),
               ((([], []),), []), ((([], [0]),), [0])],
     "wrap": "lambda *a: _to_list(merge_two_lists(_from_list(a[0]), _from_list(a[1])))"},
    {"slug": "valid-anagram", "title": "242. 有效的字母异位词", "difficulty": "简单",
     "desc": "判断 t 是否为 s 的字母异位词。",
     "signature": "def is_anagram(s, t):",
     "tests": [(("anagram", "nagaram"), True), (("rat", "car"), False),
               (("a", "ab"), False)]},
    {"slug": "contains-duplicate", "title": "217. 存在重复元素", "difficulty": "简单",
     "desc": "数组中是否存在重复元素。",
     "signature": "def contains_duplicate(nums):",
     "tests": [(([1, 2, 3, 1],), True), (([1, 2, 3, 4],), False),
               (([1, 1, 1, 3, 3, 4],), True)]},
    {"slug": "reverse-linked-list", "title": "206. 反转链表", "difficulty": "简单",
     "desc": "用 ListNode(val,next)；反转单链表并返回新头结点。",
     "signature": "def reverse_list(head):  # ListNode 类已预置",
     "helper": """
class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next
def _to_list(head):
    out = []
    while head:
        out.append(head.val)
        head = head.next
    return out
def _from_list(arr):
    dummy = ListNode()
    cur = dummy
    for v in arr:
        cur.next = ListNode(v)
        cur = cur.next
    return dummy.next
""",
     "tests": [((([1, 2, 3, 4, 5],),), [5, 4, 3, 2, 1]),
               ((([1, 2],),), [2, 1]), ((([],),), [])],
     "wrap": "lambda *a: _to_list(reverse_list(_from_list(a[0])))"},
    {"slug": "lru-cache", "title": "146. LRU 缓存", "difficulty": "中等",
     "desc": "实现 LRUCache 类：get(key) 存在返回值否则-1；put(key,val) 容量满时淘汰最久未用。",
     "signature": "class LRUCache:  # __init__(self, capacity)",
     "class": True,
     "tests": [((((2,), [("put", [1, 1]), ("put", [2, 2]), ("get", [1]), ("put", [3, 3]),
                     ("get", [2]), ("put", [4, 4]), ("get", [1]), ("get", [3]), ("get", [4])]),),
                [None, None, 1, None, -1, None, -1, 3, 4])],
     "wrap": "run_lru_ops"},
    {"slug": "longest-substring", "title": "3. 无重复字符的最长子串", "difficulty": "中等",
     "desc": "找出不含重复字符的最长子串长度。",
     "signature": "def length_of_longest_substring(s):",
     "tests": [(("abcabcbb",), 3), (("bbbbb",), 1), (("pwwkew",), 3), (("",), 0)]},
    {"slug": "coin-change", "title": "322. 零钱兑换", "difficulty": "中等",
     "desc": " coins 面额组成 amount 的最少硬币数，无法组成返回 -1。",
     "signature": "def coin_change(coins, amount):",
     "tests": [(([1, 2, 5], 11), 3), (([2], 3), -1), (([1], 0), 0),
               (([186, 419, 83, 408], 6249), 20)]},
]

_LRU_RUNNER = """
def run_lru_ops(ops_spec):
    cap, ops = ops_spec
    c = LRUCache(cap)
    out = []
    for name, args in ops:
        out.append(getattr(c, name)(*args))
    return out
"""


def list_problems(difficulty=None):
    return [p for p in PROBLEMS if not difficulty or p["difficulty"] == difficulty]


def get_problem(slug):
    for p in PROBLEMS:
        if p["slug"] == slug:
            return p
    raise KeyError(f"题库中没有 {slug}，可用: {', '.join(p['slug'] for p in PROBLEMS)}")


def _fname(p):
    return p["signature"].split("(")[0].split()[-1].split("(")[0]


def check_solution(p, code: str) -> dict:
    """运行内置测试 + 静态检查 + 泄漏抽检。返回 {static, tests, passed, leak}"""
    if p.get("class"):
        code = code + _LRU_RUNNER
    if p.get("helper"):
        code = p["helper"] + "\n\n" + code
    static = codecheck.check_python_syntax(code)
    results = []
    for args, expected in p["tests"]:
        call_args = ", ".join(repr(a) for a in args)
        wrap = p.get("wrap")
        if wrap == "run_lru_ops":
            call = f"run_lru_ops({call_args})"
        elif wrap and wrap.startswith("lambda"):
            call = f"({wrap})({', '.join(repr(a) for a in args[0])})"
        else:
            call = f"{_fname(p)}({call_args})"
        harness = (code +
                   "\nimport json as _j\n"
                   f"print('RESULT:' + _j.dumps({call}, default=str))\n")
        r = codecheck.run_python_code(harness, timeout=8)
        ok, got = False, None
        if r["ok"]:
            import re as _re
            m = _re.search(r"RESULT:(.*)", r["output"])
            if m:
                try:
                    got = json.loads(m.group(1).strip())
                except Exception:
                    got = None
            if got == expected:
                ok = True
            elif isinstance(expected, list) and isinstance(got, list):
                # 无序解（two-sum 等允许同组不同序）
                if sorted(map(str, got)) == sorted(map(str, expected)):
                    ok = True
                elif got and expected and isinstance(got[0], list):
                    ok = all(sorted(map(str, g)) == sorted(map(str, e))
                             for g, e in zip(got, expected))
        results.append({"args": str(args)[:80], "expected": expected,
                        "got": got, "ok": ok})
    # 内存泄漏抽检：数值型函数重复调用
    leak = None
    if p["slug"] in ("climbing-stairs", "coin-change", "binary-search"):
        fname = _fname(p)
        args_spec = ([["$i"], [50], [80]] if "climb" in fname
                     else [[[1, 2, 5], 30], [[2], 7], [[1], 0]])
        leak = codecheck.memory_leak_check(code, fname, args_spec)
    return {"static": static, "tests": results,
            "passed": not static and all(t["ok"] for t in results),
            "leak": leak}


def solve(slug: str) -> dict:
    """完整解题：走思考->计划->审查->实现->测试循环。"""
    p = get_problem(slug)
    tests_desc = "\n".join(f"- 输入 {a} -> 期望 {e}" for a, e in p["tests"])
    context = f"""【力扣题目】{p['title']}（{p['difficulty']}）
【题意】{p['desc']}
【函数签名（必须严格遵守）】
{p['signature']}
【内置测试用例（必须全部通过）】
{tests_desc}
【输出要求】只输出一个文件 solution.py，包含签名所指的函数/类，底部附简单自测。"""
    wf = Workflow(f"实现力扣题目 {p['title']} 并通过全部测试", kind="leetcode", context=context)
    res = wf.run()
    # 用题库真实测试再验一次
    code_file = wf.workspace / "code" / "solution.py"
    detail = None
    if code_file.exists():
        detail = check_solution(p, code_file.read_text(encoding="utf-8"))
        (wf.workspace / "local_tests.json").write_text(
            json.dumps(detail, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8", errors="replace")
        res["local_tests"] = detail
    return res


def explain(slug: str) -> str:
    """题解讲解：思路、复杂度、多解法对比。"""
    p = get_problem(slug)
    r = router()
    return r.ask(f"""给出力扣题「{p['title']}」的题解讲解：{p['desc']}
包含：1) 思路推导 2) 推荐解法与代码(python) 3) 复杂度分析 4) 其他解法对比 5) 同类题拓展。""",
                 system=SYS_ENGINEER, deep=True)
