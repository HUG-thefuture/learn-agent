# -*- coding: utf-8 -*-
"""把训练成果固化成本地定制模型：构建 Modelfile 并执行 `ollama create learn-agent`。

- 基座: qwen3:8b（RTX 4070 上交互流畅）
- SYSTEM 提示词由知识库高置信条目蒸馏而成（角色 + 工作流纪律 + 编码守则 + 速查精华）
- 这是本项目的"本地模型训练产物"：ollama run learn-agent 即可使用
"""
import subprocess
import sys
from pathlib import Path

from core.config import ROOT
from core.knowledge import kb
from core.config import cfg

MODEL_NAME = "learn-agent"
BASE_MODEL = None  # 运行时取配置


def build_system_prompt(max_chars: int = 6500) -> str:
    _kb = kb()
    if not _kb.docs:
        from training.train_knowledge import run as kb_train
        kb_train(use_distilled=True)
    parts = ["""你是 learn-agent，一名资深编程教练与全栈工程师（Python/JavaScript/Java）。
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
- 算法：注意复杂度与边界（空输入/单元素/极值）"""]
    # 注入知识库精华（每篇取前 700 字符）
    used = 0
    for d in _kb.docs:
        chunk = f"\n### {d['title']}\n{d['text'][:700].strip()}"
        if used + len(chunk) > max_chars:
            break
        parts.append(chunk)
        used += len(chunk)
    return "\n".join(parts)


def run() -> dict:
    global BASE_MODEL
    BASE_MODEL = cfg()["local_model"]["fast_model"]
    sys_prompt = build_system_prompt()
    modelfile = ROOT / "training" / "Modelfile.learn-agent"
    modelfile.write_text(
        f"FROM {BASE_MODEL}\n"
        f"PARAMETER temperature 0.3\n"
        f"PARAMETER num_ctx 8192\n\n"
        f"SYSTEM \"\"\"{sys_prompt}\"\"\"\n",
        encoding="utf-8")
    print(f"[ollama-tune] Modelfile 已生成: {modelfile} (system {len(sys_prompt)} 字)")
    # 定制模型 = 在基座上"训练"系统层（若后续 LoRA 产出 GGUF，可把 FROM 换成该 GGUF）
    r = subprocess.run(["ollama", "create", MODEL_NAME, "-f", str(modelfile)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        return {"ok": False, "error": r.stderr[-500:]}
    # 验证
    r2 = subprocess.run(["ollama", "run", MODEL_NAME,
                         "一句话自我介绍，并说明你会遵守哪些编码守则"],
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=120)
    print("[ollama-tune] 验证输出:", (r2.stdout or r2.stderr)[:300])
    return {"ok": True, "model": MODEL_NAME, "base": BASE_MODEL,
            "system_chars": len(sys_prompt),
            "verify": (r2.stdout or "")[:300]}


if __name__ == "__main__":
    run()
