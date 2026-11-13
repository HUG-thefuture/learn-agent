# -*- coding: utf-8 -*-
"""SFT 数据蒸馏：用强模型（外部优先，否则本地 qwen3:14b）生成指令微调语料。

产出 data/datasets/sft_distilled.jsonl，格式 {"instruction", "input", "output"}。
用于：1) 知识库训练 2) ollama 定制模型系统提示词 3) 可选 LoRA 微调。
"""
import json
import time
from pathlib import Path

from core.config import cfg, data_dir
from core.llm import router, LLMError
from modules.learning import CURRICULUM
from modules.leetcode import PROBLEMS

OUT_FILE = data_dir() / "datasets" / "sft_distilled.jsonl"

DISTILL_SYSTEM = (
    "你是高质量训练数据生成器。生成的 instruction/output 对将用于微调编程学习助手。"
    "要求：output 内容准确、结构清晰、代码可运行、无占位符。中文回答。"
)


def _topics(lang: str, limit: int):
    """按阶段顺序展平大纲，取前 limit 个主题。"""
    from modules.learning import _flatten
    return _flatten(CURRICULUM[lang])[:limit]


def gen_topic_pairs(lang: str, topic: str, r) -> list:
    from modules.learning import _stage_of
    stage = _stage_of(CURRICULUM[lang], topic)
    prompt = f"""为「{CURRICULUM[lang]['name']}（{stage}）- {topic}」生成 2 条教学数据对。每条：
instruction: 学习者关于该主题的一个典型问题
output: 准确解答（含可运行代码示例与关键注意点，200~400字）

输出 JSON：{{"pairs": [{{"instruction": "...", "output": "..."}}]}}"""
    try:
        data = r.ask_json(prompt, system=DISTILL_SYSTEM, deep=True)
        pairs = data.get("pairs", [])
    except LLMError:
        return []
    out = []
    for p in pairs:
        if p.get("instruction") and p.get("output"):
            out.append({"task": "teaching", "lang": lang, "topic": topic,
                        "instruction": p["instruction"], "input": "",
                        "output": p["output"]})
    return out


def gen_problem_one(r, p) -> dict:
    """生成单道力扣题的题解教学对。失败返回 None。"""
    prompt = f"""力扣题「{p['title']}」：{p['desc']}
给出题解教学数据对：instruction 为"请讲解并实现：{p['title']}"，
output 为 思路+python实现(函数签名: {p['signature']})+复杂度分析。

输出 JSON：{{"instruction": "...", "output": "..."}}"""
    try:
        d = r.ask_json(prompt, system=DISTILL_SYSTEM, deep=True)
    except LLMError:
        return None
    if d.get("instruction") and d.get("output"):
        return {"task": "algorithm", "lang": "python", "topic": p["slug"],
                "instruction": d["instruction"], "input": "",
                "output": d["output"]}
    return None


def gen_problem_pairs(r, limit=6) -> list:
    out = []
    for p in PROBLEMS[:limit]:
        d = gen_problem_one(r, p)
        if d:
            out.append(d)
    return out


def gen_review_pairs(r, limit=4) -> list:
    """代码审查对：坏代码 -> 指出问题并修复（训练审查能力）。"""
    bad_samples = [
        ("修复这段代码的问题：def load(f):\n    fp = open(f)\n    return fp.read()",
         "问题：文件未关闭（资源泄漏）。修复：\ndef load(f):\n    with open(f, encoding='utf-8') as fp:\n        return fp.read()"),
        ("修复这段代码的问题：def fetch(url):\n    import requests\n    return requests.get(url).text",
         "问题：未设置 timeout，可能永久阻塞。修复：\ndef fetch(url):\n    import requests\n    r = requests.get(url, timeout=10)\n    r.raise_for_status()\n    return r.text"),
        ("修复这段代码的问题：def add_item(item, items=[]):\n    items.append(item)\n    return items",
         "问题：可变默认参数导致跨调用共享状态。修复：\ndef add_item(item, items=None):\n    if items is None:\n        items = []\n    items.append(item)\n    return items"),
        ("修复这段代码的问题：def wait_all(ts):\n    for t in ts:\n        threading.Thread(target=t).start()",
         "问题：线程未 join，主线程可能提前退出。修复：\ndef wait_all(jobs):\n    ts = [threading.Thread(target=j) for j in jobs]\n    for t in ts: t.start()\n    for t in ts: t.join()"),
    ]
    out = []
    for q, a in bad_samples[:limit]:
        out.append({"task": "code-review", "lang": "python", "topic": "review",
                    "instruction": q, "input": "", "output": a})
    return out


def _fmt_eta(sec: float) -> str:
    if sec < 60:
        return f"{sec:.0f} 秒"
    if sec < 3600:
        return f"{sec / 60:.1f} 分钟"
    return f"{sec / 3600:.1f} 小时"


def run(samples_per_topic: int = 1, topics_limit: int = 12, use_external: bool = True,
        log_fn=None) -> dict:
    """执行蒸馏。返回统计。

    关键：蒸馏耗时与「语言数 × topics_limit」强相关（云端强模型每条约 30~90s），
    旧版文案写死「6~15 分钟」与实际严重不符。这里预计算任务总数，用真实已耗时
    的移动平均动态估算剩余时间，并把进度与 ETA 通过 log_fn / stdout 上报。
    """
    def _p(text):
        if log_fn:
            try:
                log_fn(text)
            except Exception:
                pass
        print(text)

    r = router()
    from core.llm import external_enabled
    mode = "云端/外部" if (use_external and external_enabled()) else "本地 qwen3:14b"
    _p(f"[distill] 使用{mode}模型蒸馏")

    # 预计算任务清单（真实工作量；审查对为静态内容，不消耗 LLM 调用）
    topic_tasks = [(lang, t) for lang in CURRICULUM for t in _topics(lang, topics_limit)]
    problem_tasks = PROBLEMS[:6]
    review_tasks = 4
    total = len(topic_tasks) + len(problem_tasks) + review_tasks
    _p(f"[distill] 共 {total} 个任务（主题 {len(topic_tasks)} + 题解 {len(problem_tasks)}"
       f" + 审查 {review_tasks}）。主题/题解各 1 次模型调用，审查为静态内容。")

    all_pairs = []
    t0 = time.time()
    done = 0
    per_item = []  # 每个「耗时任务」的真实秒数，用于移动平均 ETA

    def _note(sec, produced, label):
        nonlocal done
        done += 1
        per_item.append(sec)
        avg = sum(per_item) / len(per_item)
        eta = avg * (total - done)
        _p(f"[distill] {done}/{total} {label}：+{produced} 对，本步 {sec:.0f}s，"
           f"平均 {avg:.0f}s，预计剩余 {_fmt_eta(eta)}")

    for lang, topic in topic_tasks:
        ts = time.time()
        pairs = gen_topic_pairs(lang, topic, r)
        all_pairs += pairs
        _note(time.time() - ts, len(pairs), f"[{lang}] {topic}")

    for p in problem_tasks:
        ts = time.time()
        d = gen_problem_one(r, p)
        if d:
            all_pairs.append(d)
        _note(time.time() - ts, 1 if d else 0, f"[题解] {p['slug']}")

    # 审查对为静态内容，瞬时完成
    review_out = gen_review_pairs(r, review_tasks)
    all_pairs += review_out
    done += review_tasks
    _p(f"[distill] 审查对 +{len(review_out)}（静态内容，瞬时）")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        for p in all_pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    elapsed = time.time() - t0
    stats = {"pairs": len(all_pairs), "file": str(OUT_FILE),
             "seconds": round(elapsed, 1),
             "llm_calls": len(per_item),
             "avg_per_call": round(sum(per_item) / len(per_item), 1) if per_item else 0}
    _p(f"[distill] 完成: 共 {stats['pairs']} 对，{stats['llm_calls']} 次模型调用，"
       f"总耗时 {_fmt_eta(elapsed)}")
    return stats


def load_dataset() -> list:
    if not OUT_FILE.exists():
        return []
    with open(OUT_FILE, "r", encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


if __name__ == "__main__":
    run()
