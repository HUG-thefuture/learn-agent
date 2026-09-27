# -*- coding: utf-8 -*-
"""一键训练入口：

    python main.py train                 # 全流程：蒸馏 -> 知识库训练 -> 本地模型定制
    python main.py train --skip-distill  # 跳过蒸馏（复用已有数据集）
    python -m training.run_training --samples 1
"""
import argparse
import json
import time

from core.config import data_dir


def run(skip_distill: bool = False, use_external: bool = True, topics_limit: int = 6) -> dict:
    t0 = time.time()
    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S")}
    if not skip_distill:
        from training import distill
        report["distill"] = distill.run(use_external=use_external, topics_limit=topics_limit)
    from training import train_knowledge
    report["knowledge"] = train_knowledge.run()
    from training import make_ollama_model
    report["model"] = make_ollama_model.run()
    report["seconds"] = round(time.time() - t0, 1)
    out = data_dir() / "train_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[train] 全部完成 ({report['seconds']}s)，报告: {out}")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-distill", action="store_true")
    ap.add_argument("--no-external", action="store_true", help="禁用外部模型蒸馏")
    a = ap.parse_args()
    run(skip_distill=a.skip_distill, use_external=not a.no_external)
