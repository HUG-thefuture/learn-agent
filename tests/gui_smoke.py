# -*- coding: utf-8 -*-
"""GUI 交互链路验证（非交互环境运行）：发送消息 -> 流式回答 -> 校验渲染。"""
import sys
import time
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gui.app import App  # noqa: E402

root = tk.Tk()
app = App(root)
root.update()

app.chat_model.set("learn-agent")
app.chat_in.insert(0, "用一句话回答：什么是列表推导式")
app._chat_send()
print("sent, waiting for stream...")

deadline = time.time() + 240
while time.time() < deadline and "chat" in app.busy:
    root.update()
    time.sleep(0.05)

content = app.chatlog.get("1.0", "end")
ok = ("推导" in content or "列表" in content) and len(content) > 60 \
     and "模型不可用" not in content and app.chat_history[-1]["role"] == "assistant"
print("CHAT_OK" if ok else "CHAT_FAIL tail=" + content[-300:])
root.destroy()
