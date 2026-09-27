# -*- coding: utf-8 -*-
"""全局配置加载。"""
import os
from pathlib import Path

import yaml

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
              data_dir() / "datasets", outputs_dir() / "learning",
              outputs_dir() / "leetcode", outputs_dir() / "projects"):
        d.mkdir(parents=True, exist_ok=True)
