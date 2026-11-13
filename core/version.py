# -*- coding: utf-8 -*-
"""代码版本指纹：判断「磁盘上的代码」是否与「正在运行的进程」一致。

原理：对所有源码文件做内容 sha256（排除 data/、build/ 等运行期产物），
得到一个稳定的 build 指纹。启动器（launch.py）拿它和正在运行实例登记的
指纹对比，不一致就自动重启到新版。

设计取舍：
- 用内容哈希而不是 mtime：git checkout / 编辑器保存 / 复制粘贴都可能不改
  mtime，只有内容才可信。
- 排除 data/：学习内容、知识库索引、日志、训练报告每天都在变，不该触发重启。
- 排除 tests/：改测试不该打断正在用的界面（CI 显式校验请用 launch.py check）。
- 总量 ~0.4MB / 30+ 文件，哈希耗时毫秒级，不需要缓存文件。
"""
import hashlib
from pathlib import Path

# 纳入版本指纹的源文件后缀
SOURCE_EXTS = {".py", ".pyw", ".yaml", ".yml", ".js", ".html", ".css", ".md", ".json"}

# 纳入版本指纹的源码目录（相对项目根）
SOURCE_DIRS = ("core", "modules", "gui", "webapp", "training", "evals",
               "prompts", "assets")

# 纳入版本指纹的根目录文件
SOURCE_FILES = ("main.py", "learn-agent.pyw", "launch.py", "config.yaml", "README.md")

# 跳过目录：运行期产物 / 缓存 / 版本库
SKIP_DIRS = {"__pycache__", ".git", ".idea", ".vscode", "data", "build", "dist",
             "models", ".tmp", "_tmpprobe", ".dshextract", "node_modules", "tests"}

_CACHE = {}  # root_str -> fingerprint dict，同一进程内只算一次


def project_root() -> Path:
    """项目根：打包成 exe 时取 exe 所在目录，源码运行时取仓库根。"""
    from core.config import ROOT
    return Path(ROOT)


def iter_source_files(root: Path = None):
    """遍历参与版本指纹的源文件（排序保证哈希可复现）。"""
    root = Path(root) if root else project_root()
    found = []
    for d in SOURCE_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for f in base.rglob("*"):
            if not f.is_file():
                continue
            rel_dirs = set(f.relative_to(root).parts[:-1])
            if rel_dirs & SKIP_DIRS:
                continue
            if f.suffix.lower() not in SOURCE_EXTS:
                continue
            found.append(f)
    for name in SOURCE_FILES:
        f = root / name
        if f.is_file():
            found.append(f)
    return sorted(found, key=lambda p: str(p.relative_to(root)).lower())


def fingerprint(root: Path = None, use_cache: bool = False) -> dict:
    """计算代码版本指纹。

    返回 {"build","hash","files","bytes","newest_ts","newest_file"}：
    - build：12 位短指纹，用于展示/对比
    - hash：完整 sha256，精确对比
    - files/bytes：参与计算的文件数与总字节
    - newest_ts/newest_file：最后修改的源文件（便于"我改了什么"定位）
    """
    root = Path(root) if root else project_root()
    key = str(root.resolve())
    if use_cache and key in _CACHE:
        return _CACHE[key]

    h = hashlib.sha256()
    n_files = 0
    n_bytes = 0
    newest_ts = 0.0
    newest_file = ""
    for f in iter_source_files(root):
        rel = str(f.relative_to(root)).replace("\\", "/")
        try:
            data = f.read_bytes()
        except OSError:
            continue  # 文件被占用/删除：跳过，不让指纹计算失败
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(data)
        h.update(b"\0")
        n_files += 1
        n_bytes += len(data)
        try:
            ts = f.stat().st_mtime
            if ts > newest_ts:
                newest_ts, newest_file = ts, rel
        except OSError:
            pass

    full = h.hexdigest()
    fp = {"build": full[:12], "hash": full, "files": n_files,
          "bytes": n_bytes, "newest_ts": round(newest_ts, 3),
          "newest_file": newest_file}
    if use_cache:
        _CACHE[key] = fp
    return fp


def build_id(root: Path = None) -> str:
    """只要短指纹（12 位），用于日志/接口。"""
    return fingerprint(root)["build"]


def clear_cache():
    """清空进程内缓存的指纹（测试或外部改动后强制重算时用）。"""
    _CACHE.clear()
