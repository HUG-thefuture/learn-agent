# -*- coding: utf-8 -*-
"""运行实例登记：记录「谁在跑、跑的是哪一版代码」，供启动器判断是否需要重启。

状态文件：data/runtime/instance.json
{
  "pid": 1234, "mode": "gui|web", "port": 7860,
  "build": "a1b2c3d4e5f6", "hash": "...",
  "started_at": "2026-10-30 10:46:00",
  "proc_start_ts": 1793327706.31   # 进程创建时间，用于识破 PID 复用
}

为什么需要 proc_start_ts：Windows 的 PID 会被复用，只凭 PID 判断「旧进程还在」
可能误杀一个碰巧拿到同号的新进程。进程创建时间在一台机器上是单调的，
PID + 创建时间 才能唯一确定「还是那个实例」。

注意：不要用 os.kill(pid, 0) 探活——在 Windows 上它并不是「发 0 号信号」，
而是直接 TerminateProcess(handle, 0)，会把进程杀掉。这里用 ctypes 调
OpenProcess + GetExitCodeProcess。
"""
import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

STILL_ACTIVE = 259
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _is_windows() -> bool:
    return os.name == "nt"


# ---------------- 进程探活 ----------------
def pid_alive(pid: int) -> bool:
    """判断 PID 是否仍存活（不伤害目标进程）。"""
    if not pid or pid <= 0:
        return False
    if _is_windows():
        try:
            k32 = ctypes.windll.kernel32
            handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            try:
                code = ctypes.c_ulong()
                ok = k32.GetExitCodeProcess(handle, ctypes.byref(code))
                return bool(ok) and code.value == STILL_ACTIVE
            finally:
                k32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)  # POSIX 上 sig=0 才是真正的「只探活」
        return True
    except (OSError, ValueError):
        return False


def proc_start_ts(pid: int):
    """进程创建时间（epoch 秒）；取不到返回 None。

    Windows 用 GetProcessTimes 拿 FILETIME 再转 Unix 时间。
    """
    if not _is_windows() or not pid:
        return None
    try:
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        try:
            class FILETIME(ctypes.Structure):
                _fields_ = [("dwLowDateTime", ctypes.c_ulong),
                            ("dwHighDateTime", ctypes.c_ulong)]
            creation, exit_t, kernel, user = (FILETIME(), FILETIME(),
                                              FILETIME(), FILETIME())
            ok = k32.GetProcessTimes(handle, ctypes.byref(creation),
                                     ctypes.byref(exit_t),
                                     ctypes.byref(kernel), ctypes.byref(user))
            if not ok:
                return None
            # FILETIME: 100ns 自 1601-01-01 UTC
            ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
            return ticks / 1e7 - 11644473600.0
        finally:
            k32.CloseHandle(handle)
    except Exception:
        return None


def kill_pid(pid: int, wait: float = 5.0) -> bool:
    """强制结束进程并等待其退出。返回是否确认已退出。"""
    if not pid_alive(pid):
        return True
    try:
        if _is_windows():
            subprocess.run(["taskkill", "/pid", str(pid), "/f"],
                           capture_output=True, timeout=10)
        else:
            os.kill(pid, 15)
    except Exception:
        pass
    deadline = time.time() + wait
    while time.time() < deadline:
        if not pid_alive(pid):
            return True
        time.sleep(0.15)
    return not pid_alive(pid)


# ---------------- 状态文件 ----------------
def runtime_dir() -> Path:
    from core.config import data_dir
    return data_dir() / "runtime"


def state_path() -> Path:
    return runtime_dir() / "instance.json"


def write_state(mode: str, build: str, build_hash: str = "",
                port: int = 0, pid: int = None) -> dict:
    """由正在运行的应用（web/gui）启动时登记自己。"""
    pid = pid or os.getpid()
    st = {
        "pid": pid,
        "mode": mode,
        "port": int(port or 0),
        "build": build,
        "hash": build_hash,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "proc_start_ts": proc_start_ts(pid),
        "updated_at": time.time(),
    }
    try:
        p = state_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
    return st


def read_state():
    """读状态文件；不存在或损坏返回 None。"""
    try:
        p = state_path()
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def clear_state(pid: int = None):
    """删除状态文件。传 pid 时只在「文件确实属于该进程」时才删，
    避免退出中的旧实例把新实例刚写好的状态抹掉。"""
    try:
        st = read_state()
        if st is None:
            return
        if pid is not None and int(st.get("pid") or 0) != int(pid):
            return
        state_path().unlink(missing_ok=True)
    except OSError:
        pass


def instance_alive(st=None):
    """状态文件描述的实例是否仍真实存活。

    双重校验：PID 活着 + 进程创建时间对得上（识破 PID 复用）。
    老状态文件没记 proc_start_ts 时退化为只看 PID。
    """
    st = st if st is not None else read_state()
    if not st:
        return False
    pid = int(st.get("pid") or 0)
    if not pid_alive(pid):
        return False
    recorded = st.get("proc_start_ts")
    if recorded:
        actual = proc_start_ts(pid)
        if actual is not None and abs(actual - float(recorded)) > 2.0:
            return False  # 同号不同命：这是被复用的 PID，旧实例已不在
    return True


def describe(st) -> str:
    """给人看的实例描述（日志用）。"""
    if not st:
        return "无运行实例"
    return (f"{st.get('mode', '?')} mode, PID {st.get('pid')}, "
            f"build {st.get('build', '?')}, 启动于 {st.get('started_at', '?')}")


if __name__ == "__main__":
    s = read_state()
    print("state:", json.dumps(s, ensure_ascii=False, indent=2))
    print("alive:", instance_alive(s))
    if s:
        print("pid_alive:", pid_alive(int(s.get("pid") or 0)))
        print("proc_start_ts(now):", proc_start_ts(int(s.get("pid") or 0)))
