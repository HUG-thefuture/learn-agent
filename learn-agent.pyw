# -*- coding: utf-8 -*-
"""learn-agent 静默启动器：双击运行（pythonw/.pyw），无控制台黑窗。

同时作为 PyInstaller 打包入口：pyinstaller --onefile --windowed learn-agent.pyw
"""
import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from gui.app import main  # noqa: E402

if __name__ == "__main__":
    main()
