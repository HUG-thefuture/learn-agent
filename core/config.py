# -*- coding: utf-8 -*-
"""全局配置加载。"""
import os
import sys
from pathlib import Path

import yaml

# 打包成 exe(PyInstaller) 时以 exe 所在目录为项目根；源码运行时以仓库根为根
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent

_CFG = None


def load_config(path: str = None) -> dict:
    """读取 config.yaml 并缓存。"""
    global _CFG
    if _CFG is None:
        p = Path(path) if path else ROOT / "config.yaml"
        with open(p, "r", encoding="utf-8") as f:
            _CFG = yaml.safe_load(f) or {}
        _CFG["_root"] = str(ROOT)
    return _CFG


def cfg() -> dict:
    return load_config()


def data_dir() -> Path:
    return ROOT / cfg()["project"]["data_dir"]


def outputs_dir() -> Path:
    return ROOT / cfg()["project"]["outputs_dir"]


def ensure_dirs():
    for d in (data_dir(), outputs_dir(), data_dir() / "knowledge",
              data_dir() / "datasets", data_dir() / "memory",
              data_dir() / "logs", data_dir() / "evals",
              data_dir() / "languages", data_dir() / "leetcode" / "templates",
              data_dir() / "leetcode" / "easy", data_dir() / "leetcode" / "medium",
              data_dir() / "leetcode" / "hard",
              data_dir() / "projects" / "frontend",
              data_dir() / "projects" / "backend",
              data_dir() / "projects" / "fullstack",
              outputs_dir() / "learning", outputs_dir() / "leetcode",
              outputs_dir() / "projects"):
        d.mkdir(parents=True, exist_ok=True)
