# -*- coding: utf-8 -*-
"""可选：真·LoRA/QLoRA 微调（在 RTX 4070 12GB 上可微调 Qwen3-1.7B/4B 级别）。

默认不执行（需要大体积依赖），先装环境：
    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple torch --index-url ... 
    实际命令：
    pip install torch --index-url https://download.pytorch.org/whl/cu121
    pip install transformers peft datasets accelerate bitsandbytes

训练数据: data/datasets/sft_distilled.jsonl -> 训练后:
    1) 合并/导出 LoRA 权重
    2) llama.cpp 转 GGUF 后 `ollama create learn-agent-lora -f Modelfile`（FROM 指向 GGUF）
用法:
    python -m training.finetune_lora --check-env     # 检查依赖
    python -m training.finetune_lora --base Qwen/Qwen3-1.7B --epochs 3
"""
import argparse
import json
from pathlib import Path

from core.config import data_dir, ROOT

REQUIRED = ["torch", "transformers", "peft", "datasets", "accelerate"]


def check_env() -> dict:
    import importlib.util as iu
    status = {m: bool(iu.find_spec(m)) for m in REQUIRED}
    print("[lora] 依赖状态:", status)
    if all(status.values()):
        import torch
        print(f"[lora] torch={torch.__version__} cuda={torch.cuda.is_available()}"
              f" device={torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu'}")
    else:
        print("[lora] 缺少依赖，安装命令见本文件头注释")
    return status


def to_chat_format(row: dict) -> str:
    """转为 chatml 训练文本。"""
    inst = row["instruction"] + (("\n" + row["input"]) if row.get("input") else "")
    return ("<|im_start|>user\n" + inst + "<|im_end|>\n"
            "<|im_start|>assistant\n" + row["output"] + "<|im_end|>")


def run(base: str = "Qwen/Qwen3-1.7B", epochs: int = 3,
        out: Path = None, max_len: int = 1024):
    status = check_env()
    if not all(status.values()):
        raise SystemExit("缺少微调依赖，请先安装（见文件头注释）")
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (AutoModelForCausalLM, AutoTokenizer,
                              BitsAndBytesConfig, Trainer, TrainingArguments)

    data_file = data_dir() / "datasets" / "sft_distilled.jsonl"
    rows = [json.loads(l) for l in open(data_file, encoding="utf-8") if l.strip()]
    print(f"[lora] 样本数: {len(rows)}")
    tok = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
    tok.pad_token = tok.eos_token

    def tokenize(row):
        ids = tok(to_chat_format(row), truncation=True, max_length=max_len)
        ids["labels"] = ids["input_ids"].copy()
        return ids

    ds = Dataset.from_list(rows).map(tokenize)

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_quant_type="nf4")
    model = AutoModelForCausalLM.from_pretrained(base, quantization_config=bnb,
                                                 device_map="auto", trust_remote_code=True)
    model = prepare_model_for_kbit_training(model)
    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                      "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    out = out or ROOT / "models" / "lora-learn-agent"
    args = TrainingArguments(
        output_dir=str(out), num_train_epochs=epochs, per_device_train_batch_size=2,
        gradient_accumulation_steps=4, learning_rate=2e-4, lr_scheduler_type="cosine",
        warmup_ratio=0.03, logging_steps=5, save_strategy="epoch", bf16=True,
        report_to=[])
    Trainer(model=model, args=args, train_dataset=ds).train()
    model.save_pretrained(str(out / "adapter"))
    tok.save_pretrained(str(out / "adapter"))
    print(f"[lora] LoRA 适配器已保存: {out/'adapter'}")
    print("[lora] 后续: 用 llama.cpp convert_hf_to_gguf.py 转 GGUF -> ollama create 导入")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-env", action="store_true")
    ap.add_argument("--base", default="Qwen/Qwen3-1.7B")
    ap.add_argument("--epochs", type=int, default=3)
    a = ap.parse_args()
    if a.check_env:
        check_env()
    else:
        run(base=a.base, epochs=a.epochs)
