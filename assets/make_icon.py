# -*- coding: utf-8 -*-
"""生成应用图标 assets/learn-agent.ico（纯本地，PIL 绘制）。"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "learn-agent.ico"


def rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def build() -> Path:
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 深色底 + 蓝色圆角方块
    rounded(d, (8, 8, size - 8, size - 8), 52, (22, 29, 46, 255))
    rounded(d, (24, 24, size - 24, size - 24), 40, (45, 91, 219, 255))
    # 终端提示符 ">_" 象征编程助手
    try:
        font = ImageFont.truetype("consola.ttf", 130)
    except OSError:
        font = ImageFont.load_default()
    d.text((62, 52), ">_", font=font, fill=(232, 237, 247, 255))
    # 底部书本横线（学习）
    d.rounded_rectangle((56, 196, 200, 210), radius=7, fill=(247, 201, 72, 255))
    img.save(OUT, sizes=[(256, 256), (128, 128), (64, 64), (48, 48),
                         (32, 32), (16, 16)])
    return OUT


if __name__ == "__main__":
    print("icon:", build())
