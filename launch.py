# -*- coding: utf-8 -*-
"""learn-agent 智能启动器：自动识别代码版本，变了就重启到新版。

双击图标（或 `python launch.py web|gui`）后：

  1. 计算磁盘上源码的版本指纹（core/version.py）
  2. 读取运行实例登记（data/runtime/instance.json）并确认它**真的还活着**
     （PID + 进程创建时间双重校验，防 PID 复用误杀）
  3. 三种情况分别处理：
       没在跑            → 启动
       在跑但版本一致    → 复用（Web 直接开浏览器，GUI 前置窗口提示，不重复起进程）
       在跑但版本不一致  → 杀掉旧实例 → 等端口释放 → 启动新版
  4. 把新实例的 PID/build 写回登记文件，供下次判断

这样就实现「改了代码，双击图标就自动重启到新版」：不需要手动关旧窗口，
也不会因为忘了重启而对着旧代码调试半天。

用法：
    python launch.py web              # Web 控制台（默认）
    python launch.py gui              # 桌面 GUI
    python launch.py web --force      # 无论如何都重启
    python launch.py check            # 只检查版本状态，不启动（CI/脚本用）
    python launch.py watch --interval 5   # 常驻守护：代码一变就自动重启
    python launch.py stop             # 停止当前实例
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOG_DIR = ROOT / "data"
DEFAULT_WEB_PORT = 7860


def _utf8_stdout():
    """Windows 控制台默认 GBK，中文日志会炸；统一成 UTF-8 + 替换非法字节。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _log(msg: str):
    print(msg, flush=True)


def _python_exe() -> str:
    """选一个可用的解释器：优先当前进程（保证依赖一致）。"""
    return sys.executable or "python"


def _pythonw_exe() -> str:
    """GUI 用 pythonw 启动，避免带出黑色控制台窗口。"""
    exe = Path(_python_exe())
    pyw = exe.with_name("pythonw.exe")
    return str(pyw) if pyw.exists() else str(exe)


def port_free(port: int, host: str = "127.0.0.1") -> bool:
    """端口是否可绑定（True = 没被占用）。

    Windows 陷阱：带 SO_REUSEADDR 的 bind() 能"成功"抢到已被监听端口的使用权，
    于是探测永远返回 True，启动器会误判"端口空闲"而不去清理旧进程。
    因此 Windows 上不设 SO_REUSEADDR；跨平台一律用 SO_EXCLUSIVEADDRUSE 语义
    最稳的做法是直接不设，Windows 默认 bind 到占用端口会抛 WSAEADDRINUSE。
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if os.name != "nt":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """端口是否真的有人在监听（连接探测，作为 bind 判定的交叉验证）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex((host, port)) == 0


def wait_port_free(port: int, timeout: float = 12.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_free(port):
            return True
        time.sleep(0.2)
    return port_free(port)


def wait_port_ready(port: int, timeout: float = 25.0, host: str = "127.0.0.1") -> bool:
    """等服务端真正 LISTEN（比 '进程还活着' 更可靠的就绪判据）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.25)
    return False


def kill_port_owner(port: int) -> bool:
    """兜底：杀掉监听该端口的进程（旧版留下的野进程、非本启动器启动的实例）。"""
    if os.name != "nt":
        return False
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True,
                             text=True, errors="replace", timeout=15).stdout
    except Exception:
        return False
    pids = set()
    for line in out.splitlines():
        if "LISTENING" not in line.upper():
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local, pid = parts[1], parts[-1]
        if local.endswith(f":{port}") and pid.isdigit() and int(pid) > 0:
            pids.add(int(pid))
    from core.runtime import kill_pid
    killed = False
    for pid in pids:
        if pid != os.getpid():
            _log(f"  结束占用端口 {port} 的进程 PID {pid}")
            killed |= kill_pid(pid)
    return killed


def stop_instance(port: int = DEFAULT_WEB_PORT) -> bool:
    """停止当前登记的实例（连同占着端口的野进程）。"""
    from core.runtime import (read_state, instance_alive, kill_pid,
                              clear_state, describe)
    st = read_state()
    stopped = False
    if st and instance_alive(st):
        _log(f"  停止旧实例：{describe(st)}")
        stopped |= kill_pid(int(st.get("pid") or 0))
        clear_state(int(st.get("pid") or 0))
    # Web 模式再兜底清端口
    if not port_free(port):
        stopped |= kill_port_owner(port)
    return stopped


def spawn_web(port: int, env: dict = None):
    """后台启动 Web 服务，日志重定向到 data/（窗口关了也不影响服务）。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    out = open(LOG_DIR / "server.log", "a", encoding="utf-8", errors="replace")
    err = open(LOG_DIR / "server.err.log", "a", encoding="utf-8", errors="replace")
    creation = 0
    if os.name == "nt":
        creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        [_python_exe(), "main.py", "serve", "--port", str(port)],
        cwd=str(ROOT), stdout=out, stderr=err, stdin=subprocess.DEVNULL,
        creationflags=creation, env=env)
    return proc


def spawn_gui():
    """后台启动桌面 GUI（pythonw，无控制台）。"""
    creation = 0
    if os.name == "nt":
        creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    env = dict(os.environ)
    env["LEARN_AGENT_LAUNCHED"] = "1"   # 让 GUI 知道自己是经启动器接管
    return subprocess.Popen([_pythonw_exe(), str(ROOT / "learn-agent.pyw")],
                            cwd=str(ROOT), creationflags=creation, env=env)


def open_browser(url: str):
    try:
        if os.name == "nt":
            os.startfile(url)  # noqa: S606  (Windows 默认浏览器)
        else:
            import webbrowser
            webbrowser.open(url)
    except Exception:
        _log(f"  （无法自动打开浏览器，请手动访问 {url}）")


def launch(mode: str = "web", port: int = DEFAULT_WEB_PORT,
           force: bool = False, wait_gui: bool = False,
           browser: bool = True) -> dict:
    """核心流程：比较版本 → 决定启动/复用/重启。返回结果描述（便于测试断言）。

    browser=False 时不自动开浏览器（无头测试、CI、服务器上用）。
    """
    from core.version import fingerprint
    from core.runtime import (read_state, instance_alive, describe,
                              clear_state)
    t0 = time.time()
    fp = fingerprint()
    build = fp["build"]
    _log(f"[launch] 代码版本 {build}（{fp['files']} 文件，最新改动：{fp['newest_file']}）")

    st = read_state()
    alive = instance_alive(st)
    old_build = (st or {}).get("build")
    result = {"mode": mode, "build": build, "action": None,
              "old_build": old_build, "pid": None}

    if alive and not force:
        # 端口对不上也没意义（比如登记的是 web 但你说要 gui）——按 mode 分别判断
        same_mode = (st or {}).get("mode") == mode
        if same_mode and old_build == build:
            _log(f"[launch] 已有同版本实例在运行（{describe(st)}），直接复用。")
            result["action"] = "reuse"
            result["pid"] = st.get("pid")
            if mode == "web":
                url = f"http://127.0.0.1:{port}"
                if wait_port_ready(port, timeout=8):
                    if browser:
                        open_browser(url)
                else:
                    _log(f"  实例登记在案但端口 {port} 未就绪，请查看 data/server.err.log")
                result["url"] = url
            else:
                _log("  GUI 实例已在前台运行（如没看到窗口，请检查任务栏或先执行 stop）。")
            return result
        _log(f"[launch] 检测到版本变化：{old_build or '未知'} → {build}，重启到新版。"
             if old_build != build else
             f"[launch] 实例模式不匹配（{st.get('mode')} → {mode}），重启。")
        result["action"] = "restart"
    elif force:
        _log("[launch] --force：强制重启。")
        result["action"] = "restart" if alive else "start"
    else:
        _log("[launch] 没有运行中的实例，启动新版。")
        result["action"] = "start"

    # 先把旧实例清干净（kill + 等端口释放）
    if alive:
        stop_instance(port)
        clear_state()
    if mode == "web":
        # 端口判定用 bind + connect 双重校验：只看 bind 会被 Windows 的
        # 地址复用行为骗过，只看 connect 又认不出"已绑定但未监听"的僵死态。
        if not (port_free(port) and not port_in_use(port)):
            _log(f"  端口 {port} 仍被占用，清理占用进程。")
            kill_port_owner(port)
            wait_port_free(port, timeout=8)

    if mode == "web":
        proc = spawn_web(port)
        _log(f"[launch] 已启动 Web 服务（PID {proc.pid}），等待就绪…")
        if wait_port_ready(port):
            url = f"http://127.0.0.1:{port}"
            _log(f"[launch] 服务就绪：{url}")
            if browser:
                open_browser(url)
            result["url"] = url
        else:
            _log("[launch] 服务未在预期时间内就绪，请查看 data/server.err.log：")
            try:
                tail = (LOG_DIR / "server.err.log").read_text(
                    encoding="utf-8", errors="replace").strip().splitlines()[-8:]
                for line in tail:
                    _log("    " + line)
            except OSError:
                pass
            result["error"] = "port not ready"
    else:
        proc = spawn_gui()
        _log(f"[launch] 已启动桌面 GUI（PID {proc.pid}）。")
        if wait_gui:
            _log("[launch] 等待 GUI 退出（--wait）…")
            proc.wait()

    result["pid"] = proc.pid
    result["elapsed"] = round(time.time() - t0, 2)
    _log(f"[launch] 完成，用时 {result['elapsed']}s。")
    return result


def status(port: int = DEFAULT_WEB_PORT) -> dict:
    """只检查版本状态，不启动任何东西（CI 与调试用）。"""
    from core.version import fingerprint
    from core.runtime import read_state, instance_alive, describe
    fp = fingerprint()
    st = read_state()
    alive = instance_alive(st)
    state = {
        "build": fp["build"],
        "files": fp["files"],
        "newest_file": fp["newest_file"],
        "instance": st if alive else None,
        "instance_alive": alive,
        "instance_desc": describe(st) if alive else "无运行实例",
        "stale": bool(alive and st and st.get("build") != fp["build"]),
        "port_free": port_free(port),
    }
    return state


def watch(interval: float = 5.0, mode: str = "web", port: int = DEFAULT_WEB_PORT):
    """常驻守护：每隔 interval 秒比对指纹，一变就重启到新版。"""
    from core.version import fingerprint
    last = fingerprint()["build"]
    _log(f"[watch] 守护中（每 {interval}s 检查一次），当前版本 {last}。Ctrl+C 退出。")
    try:
        while True:
            time.sleep(interval)
            cur = fingerprint()["build"]
            if cur != last:
                _log(f"[watch] 代码变化：{last} → {cur}，重启…")
                launch(mode=mode, port=port, force=True)
                last = cur
    except KeyboardInterrupt:
        _log("[watch] 已退出。")


def main(argv=None):
    _utf8_stdout()
    ap = argparse.ArgumentParser(
        prog="launch.py",
        description="learn-agent 智能启动器：自动检测代码版本，改了代码就重启到新版")
    ap.add_argument("mode", nargs="?", default="web",
                    choices=["web", "gui", "check", "watch", "stop"],
                    help="web=Web 控制台(默认) / gui=桌面应用 / check=只看状态 / "
                         "watch=常驻守护 / stop=停止实例")
    ap.add_argument("--port", type=int, default=DEFAULT_WEB_PORT)
    ap.add_argument("--force", action="store_true", help="无论版本是否变化都重启")
    ap.add_argument("--wait", action="store_true", help="GUI 模式下等待退出")
    ap.add_argument("--no-browser", action="store_true",
                    help="不自动打开浏览器（无头/CI 用）")
    ap.add_argument("--interval", type=float, default=5.0, help="watch 模式的检查间隔秒")
    a = ap.parse_args(argv)

    if a.mode == "check":
        st = status(a.port)
        print(json.dumps(st, ensure_ascii=False, indent=2))
        # 退出码：0=无实例或已是最新；1=有旧版实例在跑（适合 CI 卡住"忘重启"）
        return 1 if st["stale"] else 0
    if a.mode == "stop":
        stopped = stop_instance(a.port)
        _log("[launch] 已停止。" if stopped else "[launch] 没有运行中的实例。")
        return 0
    if a.mode == "watch":
        watch(interval=a.interval, mode="web", port=a.port)
        return 0
    res = launch(mode=a.mode, port=a.port, force=a.force, wait_gui=a.wait,
                 browser=not a.no_browser)
    return 0 if not res.get("error") else 1


if __name__ == "__main__":
    sys.exit(main())
