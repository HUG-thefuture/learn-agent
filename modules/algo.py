# -*- coding: utf-8 -*-
"""算法训练体系（规范：四阶段训练 + 错题复盘 + 模板整理）。

- 阶段一 基础:   easy 30题目标（数组/字符串/链表/栈/队列/哈希）
- 阶段二 进阶:   medium 30题目标（树/图/排序/查找/递归/回溯/贪心）
- 阶段三 高阶:   medium/hard 20题目标（DP/位运算/并查集/前缀和/滑动窗口/二分）
- 阶段四 实战:   周赛模拟/限时训练/错题复盘/模板整理

进度与错题本存于 data/memory/algo_progress.json。
"""
import json
import time
from pathlib import Path

from core.config import data_dir
from core.knowledge import kb
from core.llm import router
from modules.leetcode import PROBLEMS, get_problem

STAGES = [
    {"idx": 0, "name": "阶段一·基础", "target": "easy×30", "diff": ["简单"],
     "topics": "数组、字符串、链表、栈、队列、哈希表"},
    {"idx": 1, "name": "阶段二·进阶", "target": "medium×30", "diff": ["中等"],
     "topics": "树、图、排序、查找、递归、回溯、贪心"},
    {"idx": 2, "name": "阶段三·高阶", "target": "medium/hard×20", "diff": ["中等", "困难"],
     "topics": "动态规划、位运算、并查集、前缀和、滑动窗口、二分"},
    {"idx": 3, "name": "阶段四·实战", "target": "独立AC",
     "diff": [], "topics": "周赛模拟、限时训练、错题复盘、模板整理"},
]

# 内置题库的题目 -> 阶段映射
PROBLEM_STAGE = {
    "two-sum": 0, "valid-parentheses": 0, "valid-anagram": 0,
    "contains-duplicate": 0, "plus-one": 0, "roman-to-integer": 0,
    "palindrome-number": 0, "single-number": 0, "majority-element": 0,
    "move-zeroes": 0, "search-insert-position": 0,
    "best-time-buy-sell-stock": 0,
    "binary-search": 2, "climbing-stairs": 2, "coin-change": 2,
    "max-subarray": 2, "longest-substring": 2,
    "reverse-linked-list": 0, "merge-sorted-lists": 0,
    "lru-cache": 1,
}


def _path() -> Path:
    return data_dir() / "memory" / "algo_progress.json"


def _load() -> dict:
    if _path().exists():
        try:
            return json.loads(_path().read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"solved": [], "attempts": {}, "wrong": {}}


def _save(d: dict):
    _path().parent.mkdir(parents=True, exist_ok=True)
    _path().write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def stage_of(slug: str) -> int:
    return PROBLEM_STAGE.get(slug, 0)


def plan() -> str:
    """分阶段训练计划与进度。"""
    d = _load()
    solved = set(d["solved"])
    lines = ["【算法训练计划】(题库内置 20 题 + 任意题面可自定义解题)"]
    for st in STAGES:
        if st["idx"] == 3:
            lines.append(f"■ {st['name']}  目标: {st['target']}")
            lines.append(f"   主题: {st['topics']}")
            lines.append("   做法: `solve <slug>` 限时解题 → 错题进 `wrong` → `algo review` 复盘")
            continue
        bank = [p for p in PROBLEMS if PROBLEM_STAGE.get(p["slug"], 0) == st["idx"]]
        done = [p for p in bank if p["slug"] in solved]
        lines.append(f"■ {st['name']}  目标: {st['target']}  主题: {st['topics']}")
        lines.append(f"   题库进度: {len(done)}/{len(bank)}"
                     + ("  ✅ 题库内全部完成，可继续用自定义题面" if len(done) == len(bank) else ""))
        todo = [p for p in bank if p["slug"] not in solved]
        if todo:
            lines.append("   待解: " + ", ".join(f"{p['slug']}(★)" if p["slug"] in d["wrong"] else p["slug"]
                                            for p in todo[:8])
                         + (" ..." if len(todo) > 8 else ""))
        wrong_in_stage = [s for s, w in d["wrong"].items()
                          if stage_of(s) == st["idx"] and not w.get("cleared")]
        if wrong_in_stage:
            lines.append(f"   ⚠ 错题待复盘: {', '.join(wrong_in_stage)}")
    return "\n".join(lines)


def next_problem(stage_idx: int = 0):
    """推荐下一题：优先错题，其次阶段内未解题。"""
    d = _load()
    solved = set(d["solved"])
    for slug, w in d["wrong"].items():
        if not w.get("cleared") and stage_of(slug) == stage_idx:
            return get_problem(slug), "错题重做"
    for p in PROBLEMS:
        if stage_of(p["slug"]) == stage_idx and p["slug"] not in solved:
            return p, "新题"
    return None, "该阶段题库已完成，可用 solve <slug> 自定义题面或进入下一阶段"


def record(slug: str, ok: bool, detail: str = ""):
    """记录一次解题结果；失败进错题本。"""
    d = _load()
    d.setdefault("attempts", {})[slug] = d.get("attempts", {}).get(slug, 0) + 1
    if ok:
        if slug not in d["solved"]:
            d["solved"].append(slug)
        if slug in d["wrong"]:
            d["wrong"][slug]["cleared"] = True
            d["wrong"][slug]["cleared_at"] = time.strftime("%Y-%m-%d %H:%M")
    else:
        d.setdefault("wrong", {})[slug] = {"date": time.strftime("%Y-%m-%d %H:%M"),
                                           "detail": detail[:400], "cleared": False}
    _save(d)


def wrongbook() -> str:
    d = _load()
    wrong = d.get("wrong", {})
    if not wrong:
        return "错题本是空的。保持这个状态！"
    lines = ["【错题本】"]
    for slug, w in wrong.items():
        mark = "✅已复盘清掉" if w.get("cleared") else "⚠待重做"
        try:
            title = get_problem(slug)["title"]
        except Exception:
            title = slug
        lines.append(f"- {title} ({slug}) [{mark}] {w.get('date', '')}")
        if w.get("detail"):
            lines.append(f"    {w['detail'][:160]}")
    return "\n".join(lines)


def review_wrong() -> str:
    """对错题本做复盘：错因归纳 + 同类题 + 模板建议。"""
    d = _load()
    wrong = {s: w for s, w in d.get("wrong", {}).items() if not w.get("cleared")}
    if not wrong:
        return "错题本为空，无需复盘。"
    items = []
    for s, w in wrong.items():
        try:
            items.append(f"- {get_problem(s)['title']}: {w.get('detail', '')[:200]}")
        except Exception:
            items.append(f"- {s}: {w.get('detail', '')[:200]}")
    text = router().ask(f"""以下是我近期做错的算法题与失败详情：
{chr(10).join(items)}

请生成错题复盘（Markdown）：
1. 错因归纳（按模式分类：边界/复杂度/思路/实现细节）
2. 每类的通用解题模板（伪代码或python）
3. 同类拓展题推荐（力扣题号+一句话思路）
4. 下次做题前检查清单""", deep=True)
    out = data_dir() / "leetcode" / "templates" / \
        f"wrong_review_{time.strftime('%Y%m%d_%H%M')}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", errors="replace")
    return text + f"\n\n---\n复盘已保存: {out}"


def templates() -> str:
    """生成算法模板库（二分/滑动窗口/DFS/BFS/DP），沉淀知识库。"""
    text = router().ask("""生成力扣常用算法模板速查（Markdown, python）：
二分查找、滑动窗口、链表反转、BFS/DFS(树与网格)、回溯、动态规划(一维/二维)、
前缀和、单调栈、并查集。每个模板给出适用场景+代码+2个力扣例题号。""",
                         deep=True)
    out = data_dir() / "leetcode" / "templates" / "templates.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", errors="replace")
    kb().train([{"id": "algo:templates", "title": "力扣算法模板速查",
                 "lang": "general", "tags": ["algorithm", "template"],
                 "text": text, "source": str(out)}])
    return text + f"\n\n---\n模板库已保存: {out}"
