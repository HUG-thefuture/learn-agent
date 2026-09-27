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
    c = CURRICULUM[lang]
    return c["topics"][:limit]


def gen_topic_pairs(lang: str, topic: str, r) -> list:
    prompt = f"""为「{CURRICULUM[lang]['name']} - {topic}」生成 2 条教学数据对。每条：
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


def gen_problem_pairs(r, limit=6) -> list:
    out = []
    for p in PROBLEMS[:limit]:
        prompt = f"""力扣题「{p['title']}」：{p['desc']}
给出题解教学数据对：instruction 为"请讲解并实现：{p['title']}"，
output 为 思路+python实现(函数签名: {p['signature']})+复杂度分析。

输出 JSON：{{"instruction": "...", "output": "..."}}"""
        try:
            d = r.ask_json(prompt, system=DISTILL_SYSTEM, deep=True)
        except LLMError:
            continue
        if d.get("instruction") and d.get("output"):
            out.append({"task": "algorithm", "lang": "python", "topic": p["slug"],
                        "instruction": d["instruction"], "input": "",
                        "output": d["output"]})
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


def run(samples_per_topic: int = 1, topics_limit: int = 12, use_external: bool = True) -> dict:
    """执行蒸馏。返回统计。"""
    r = router()
    if use_external and cfg()["external_model"].get("enabled"):
        print("[distill] 使用外部模型增强蒸馏")
    else:
        print("[distill] 使用本地 qwen3:14b 蒸馏（外部未启用）")
    all_pairs = []
    t0 = time.time()
    for lang in CURRICULUM:
        for topic in _topics(lang, topics_limit):
            pairs = gen_topic_pairs(lang, topic, r)
            all_pairs += pairs
            print(f"  [{lang}] {topic}: +{len(pairs)}")
    all_pairs += gen_problem_pairs(r)
    all_pairs += gen_review_pairs(r)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        for p in all_pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    stats = {"pairs": len(all_pairs), "file": str(OUT_FILE),
             "seconds": round(time.time() - t0, 1)}
    print(f"[distill] 完成: {stats}")
    return stats


def load_dataset() -> list:
    if not OUT_FILE.exists():
        return []
    with open(OUT_FILE, "r", encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


if __name__ == "__main__":
    run()
