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


def _fmt(sec: float) -> str:
    if sec < 60:
        return f"{sec:.0f} 秒"
    if sec < 3600:
        return f"{sec / 60:.1f} 分钟"
    return f"{sec / 3600:.1f} 小时"


def run(skip_distill: bool = False, use_external: bool = True, topics_limit: int = 6,
        log_fn=None, progress_fn=None) -> dict:
    """一键训练：蒸馏 -> 知识库训练 -> 本地模型定制。

    每一步真实计时并记录到报告；蒸馏阶段内部会自行上报动态 ETA（见 distill.run）。
    顶层这里只负责「每步已耗时」的准确记录，避免再给任何拍脑袋的固定时长。

    progress_fn(text, pct)：可选百分比进度回调（Web 任务卡片用）。
    """
    def _p(text):
        if log_fn:
            try:
                log_fn(text)
            except Exception:
                pass
        print(text)

    def _pct(text, pct):
        if progress_fn:
            try:
                progress_fn(text, pct)
            except Exception:
                pass
        _p(text)

    t0 = time.time()
    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S")}
    _p("[train] 开始。蒸馏耗时取决于主题数与模型档位；知识库/定制模型秒级完成。")
    if not skip_distill:
        from training import distill
        _pct("步骤 1/3 数据蒸馏…（真实 ETA 见下方日志）", 5)
        report["distill"] = distill.run(use_external=use_external,
                                        topics_limit=topics_limit, log_fn=log_fn)
        _p(f"[train] 步骤 1/3 蒸馏完成（{_fmt(time.time() - t0)}）")
    else:
        _p("[train] 跳过蒸馏（复用已有数据集）")
        report["distill"] = {"skipped": True}
    from training import train_knowledge
    _pct("步骤 2/3 知识库训练…", 70)
    t1 = time.time()
    report["knowledge"] = train_knowledge.run()
    _p(f"[train] 步骤 2/3 知识库完成（{_fmt(time.time() - t1)}）")
    from training import make_ollama_model
    _pct("步骤 3/3 定制本地模型（ollama）…", 88)
    t2 = time.time()
    report["model"] = make_ollama_model.run()
    _p(f"[train] 步骤 3/3 定制模型完成（{_fmt(time.time() - t2)}）")
    report["seconds"] = round(time.time() - t0, 1)
    report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    out = data_dir() / "train_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _p(f"\n[train] 全部完成（{_fmt(report['seconds'])}），报告: {out}")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-distill", action="store_true")
    ap.add_argument("--no-external", action="store_true", help="禁用外部模型蒸馏")
    a = ap.parse_args()
    run(skip_distill=a.skip_distill, use_external=not a.no_external)
