# -*- coding: utf-8 -*-
"""把训练成果固化成本地定制模型：构建 Modelfile 并执行 `ollama create learn-agent`。

- 基座: qwen3:8b（RTX 4070 上交互流畅）
- SYSTEM 提示词由知识库高置信条目蒸馏而成（角色 + 工作流纪律 + 编码守则 + 速查精华）
- 这是本项目的"本地模型训练产物"：ollama run learn-agent 即可使用

关于知识注入的取舍：
    SYTEM 提示词不能无限长——它要占掉每次对话的上下文预算（num_ctx=8192），
    还必须给用户问题和模型回答留出空间。所以这里的策略是：
      1) 先放固定的角色/纪律/守则骨架（约 600 字，永不裁掉）
      2) 再按「与常见提问的相关度」挑知识条目填 budget（默认 6000 字）
      3) 每条知识保留完整段落而不是硬切前 N 字——按段落边界收尾，避免半句话
      4) 被裁掉多少、为什么裁，写进报告（knowledge_injected / knowledge_skipped）
    真正检索式的长期记忆由 core/knowledge.py 的 TF-IDF 在运行时做（kb.search），
    不依赖把整个知识库塞进 system prompt。
"""
import json
import re
import subprocess
import time

import requests

from core.config import ROOT
from core.config import cfg
from core.knowledge import kb

MODEL_NAME = "learn-agent"
BASE_MODEL = None  # 运行时取配置

# system prompt 预算：默认 6000 字（num_ctx=8192 下留足对话空间）
DEFAULT_PROMPT_BUDGET = 6000

# 验证提示词（短问句，让模型用一两句话回答，便于完整呈现）
VERIFY_PROMPT = "用三句话以内自我介绍，并列出你会遵守的编码守则要点。"


def _ollama_api(path: str, payload: dict, timeout: int = 600) -> dict:
    """调 Ollama HTTP API（比 CLI 可靠：能干净分离 thinking 与 content）。"""
    base = cfg()["local_model"]["base_url"].rstrip("/")
    r = requests.post(base + path, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _strip_ansi(s: str) -> str:
    """去掉终端控制序列（ollama CLI 会输出进度/光标控制符）。"""
    return re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07", "", s or "")


def _trim_to_sentence(text: str, max_chars: int) -> str:
    """按句子/段落边界裁剪，避免"半句话"式截断。

    优先在 max_chars 内的最后一个句号/换行处收尾；找不到就退回硬切并标注。
    """
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    window = text[:max_chars]
    # 从后往前找自然断点：段落 > 句号 > 分号/逗号
    for pattern in (r"\n\n", r"[。！？!?]\s*", r"[；;]\s*", r"[，,]\s*"):
        matches = list(re.finditer(pattern, window))
        if matches:
            cut = matches[-1].end()
            if cut > max_chars * 0.5:      # 别为了断句只剩一小截
                return window[:cut].rstrip() + "…"
    return window.rstrip() + "…"


def _doc_priority(doc: dict) -> int:
    """知识条目优先级：数字越小越先注入。

    关键教训：`source` 字段含义不统一——种子知识是 `"seed"`，
    而学习沉淀的教程存的是**文件绝对路径**（`C:\\...\\某课.md`）。
    早期版本用 `src == "seed"` 判断，结果所有教程都掉进默认档，
    把 16 万字的大部头排进了 6000 字预算里，真正该进的精华反而被挤掉。
    这里改成按「内容形态」判断，不看 source 字符串。
    """
    src = str(doc.get("source") or "")
    tags = doc.get("tags") or []
    if src == "seed" or src.startswith("seed:"):
        return 0                       # 内置精华：速查表/要点，信息密度最高
    if src == "cheatsheet" or "cheatsheet" in tags:
        return 1                       # 速查表
    text_len = len(doc.get("text") or "")
    is_learn = src.startswith("learn:") or "learn" in tags
    # 学习教程（含长文）：按长度再分两档，超长的排最后
    if is_learn or src.startswith(("C:", "D:", "/", "\\\\")):
        return 3 if text_len > 4000 else 2
    if src == "distill":
        return 2                       # SFT 蒸馏语料：问答对，中等密度
    return 3 if text_len > 4000 else 2


def _pack_chunks(docs: list, budget: int) -> tuple:
    """把知识条目按优先级装进预算，返回 (chunks, 统计)。

    每条按段落边界收尾（不硬切前 N 字），并保证至少收下标题+首段，
    避免出现"标题进了、正文一个字都没有"的空条目。
    """
    stats = {"injected": 0, "skipped": 0, "per_doc_chars": 0,
             "skipped_long": 0, "skipped_budget": 0}
    ordered = sorted(docs, key=lambda d: (_doc_priority(d), len(d.get("text", ""))))
    chunks = []
    used = 0
    for d in ordered:
        title = d.get("title", "未命名")
        text = (d.get("text") or "").strip()
        if not text:
            stats["skipped"] += 1
            stats["skipped_budget"] += 1
            continue
        header = f"\n### {title}\n"
        remain = budget - used - len(header)
        if remain < 120:                     # 剩下的空间塞不下有意义的正文
            stats["skipped"] += 1
            stats["skipped_budget"] += 1
            continue
        body = _trim_to_sentence(text, remain)
        chunk = header + body
        chunks.append(chunk)
        used += len(chunk)
        stats["injected"] += 1
        stats["per_doc_chars"] += len(body)
        # 一条超长教程可能一次吃掉大半预算：即便被注入了也记一笔"长文"
        if len(body) >= remain * 0.8 and len(text) > 4000:
            stats["skipped_long"] += 1
    stats["used_chars"] = used
    stats["budget"] = budget
    return chunks, stats


def build_system_prompt(budget: int = DEFAULT_PROMPT_BUDGET) -> str:
    """构建 SYSTEM 提示词：固定骨架 + 预算内的知识精华。"""
    return build_system_prompt_with_stats(budget)[0]


def build_system_prompt_with_stats(budget: int = DEFAULT_PROMPT_BUDGET) -> tuple:
    """返回 (system_prompt, 统计)。统计进训练报告，让"注入了多少知识"可见。"""
    _kb = kb()
    if not _kb.docs:
        from training.train_knowledge import run as kb_train
        kb_train(use_distilled=True)
        _kb = kb()
    skeleton = """你是 learn-agent，一名资深编程教练与全栈工程师（Python/JavaScript/Java）。
职责：教编程、讲算法（力扣）、协助前后端开发与函数调用。

工作纪律（必须遵守）：
1. 接到开发任务先【思考】再【计划】再自查【审查】，确认无逻辑漏洞后才动手写代码
2. 写完自查：边界条件、异常处理、资源释放（文件 with / 线程 join / 请求 timeout）
3. 给出代码时同时给出测试要点；发现内存泄漏或死循环风险必须指出并给出修复
4. 回答用中文，先结论后细节，代码完整可运行

编码守则：
- Python：资源用 with；requests 带 timeout；禁可变默认参数与裸 except；线程 daemon+join
- JS：用 === 与 let/const；setInterval/addEventListener 必须配对清理；fetch 必须处理错误
- Java：流用 try-with-resources；不吞异常；线程池显式 shutdown
- 算法：注意复杂度与边界（空输入/单元素/极值）"""
    chunks, stats = _pack_chunks(_kb.docs, budget)
    prompt = skeleton + "\n" + "".join(chunks)
    stats["total_docs"] = len(_kb.docs)
    stats["prompt_chars"] = len(prompt)
    # 说明"为什么只注入 N 篇"——这不是知识库太小，而是上下文预算的物理限制。
    # 真正的补偿机制是运行时检索（kb.search / LLMRouter._kb_context）。
    kb_stat = _kb.stats()
    stats["kb"] = {
        "total_docs": kb_stat["total"],
        "total_chars": kb_stat["total_chars"],
        "by_source": kb_stat["by_source"],
    }
    stats["note"] = (
        f"system prompt 只装 {stats['injected']}/{stats['total_docs']} 篇，"
        f"是因为它要长期驻留在 num_ctx={cfg()['local_model'].get('num_ctx', 8192)} 里，"
        f"给用户提问和模型回答留空间；整库 {kb_stat['total_chars']} 字无法常驻。"
        f"其余 {stats['skipped']} 篇由运行时按查询检索注入（kb.search），"
        f"每次对话只取最相关的几篇，命中率见知识库自评。"
    )
    return prompt, stats


def _verify_via_api(timeout: int = 300) -> dict:
    """用 API 验证模型：干净分离 thinking 与 content，返回完整回答（不截断）。

    为什么不用 `ollama run`：CLI 把思考链和进度控制符一起写进 stdout，
    再被 [:300] 一裁——得到的就是"半句思考过程"，既看不出模型好坏，
    也不像一条完整回答。API 里 message.content 是纯回答，message.thinking 单独给。
    """
    try:
        data = _ollama_api("/api/chat", {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": VERIFY_PROMPT}],
            "stream": False,
            "think": True,
            "options": {"temperature": 0.3, "num_ctx": cfg()["local_model"].get("num_ctx", 8192)},
        }, timeout=timeout)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "content": "",
                "thinking_chars": 0}
    msg = data.get("message") or {}
    content = _strip_ansi(msg.get("content") or "").strip()
    thinking = _strip_ansi(msg.get("thinking") or "")
    return {"ok": bool(content), "content": content,
            "thinking_chars": len(thinking),
            "content_chars": len(content),
            "prompt_eval_count": data.get("prompt_eval_count"),
            "eval_count": data.get("eval_count")}


def run(budget: int = DEFAULT_PROMPT_BUDGET) -> dict:
    """生成 Modelfile、创建模型、验证。返回完整报告（不做任何截断）。"""
    global BASE_MODEL
    t0 = time.time()
    BASE_MODEL = cfg()["local_model"]["fast_model"]
    sys_prompt, stats = build_system_prompt_with_stats(budget)
    modelfile = ROOT / "training" / "Modelfile.learn-agent"
    modelfile.write_text(
        f"FROM {BASE_MODEL}\n"
        f"PARAMETER temperature 0.3\n"
        f"PARAMETER num_ctx {cfg()['local_model'].get('num_ctx', 8192)}\n\n"
        f"SYSTEM \"\"\"{sys_prompt}\"\"\"\n",
        encoding="utf-8")
    print(f"[ollama-tune] Modelfile 已生成: {modelfile}")
    print(f"[ollama-tune] SYSTEM {len(sys_prompt)} 字：知识注入 {stats['injected']}/"
          f"{stats['total_docs']} 篇（预算 {stats['budget']} 字，"
          f"因预算跳过 {stats['skipped']} 篇）")

    # 定制模型 = 在基座上"训练"系统层（若后续 LoRA 产出 GGUF，可把 FROM 换成该 GGUF）
    r = subprocess.run(["ollama", "create", MODEL_NAME, "-f", str(modelfile)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        return {"ok": False, "error": r.stderr[-500:],
                "knowledge": stats, "seconds": round(time.time() - t0, 1)}

    # 验证：走 API 拿完整回答（thinking 与 content 分离，不截断）
    ver = _verify_via_api()
    if ver["ok"]:
        print("[ollama-tune] 验证回答（完整）：")
        for line in ver["content"].splitlines():
            print("    " + line)
        print(f"[ollama-tune] 回答 {ver['content_chars']} 字，"
              f"思考链 {ver['thinking_chars']} 字（已分离）")
    else:
        print(f"[ollama-tune] 验证失败: {ver.get('error')}")

    return {"ok": True, "model": MODEL_NAME, "base": BASE_MODEL,
            "system_chars": len(sys_prompt),
            "knowledge": stats,
            "verify": ver["content"],              # 完整回答，不再 [:300]
            "verify_meta": {k: ver.get(k) for k in
                            ("ok", "content_chars", "thinking_chars",
                             "prompt_eval_count", "eval_count", "error")},
            "verify_prompt": VERIFY_PROMPT,
            "seconds": round(time.time() - t0, 1)}


if __name__ == "__main__":
    out = run()
    print(json.dumps(out, ensure_ascii=False, indent=2))
