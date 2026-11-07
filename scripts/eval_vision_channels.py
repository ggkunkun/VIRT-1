#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare local Qwen3-VL-2B vs cloud glm-4.5v on synthetic OCR marks.

Usage: .venv/Scripts/python.exe scripts/eval_vision_channels.py
"""
import base64
import io
import os
import sys
import time

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from virtu_real_backend import VirtuRealModel  # noqa: E402

CASES = ["VX7Q", "A7K9", "M8x1.25"]


def make_image(mark):
    img = Image.new("RGB", (640, 360), "white")
    d = ImageDraw.Draw(img)
    d.rectangle((40, 60, 600, 300), fill="black")
    try:
        font = ImageFont.load_default(size=72)
    except TypeError:
        font = ImageFont.load_default()
    d.text((70, 150), mark, fill="yellow", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def run(backend, mark, url):
    msgs = [{"role": "user", "content": [
        {"type": "text", "text": "黑色矩形上的文字是什么？只输出该文字，不要解释。"},
        {"type": "image_url", "image_url": {"url": url}},
    ]}]
    t = time.time()
    try:
        ans = backend.generate(msgs)
        return ans, time.time() - t
    except Exception as e:
        return "ERR:%s" % type(e).__name__, time.time() - t


def main():
    local = VirtuRealModel()
    local.vision_mode = "local"
    cloud = VirtuRealModel()
    cloud.vision_mode = "cloud"
    ok_l = ok_c = 0
    for mark in CASES:
        url = make_image(mark)
        a_l, t_l = run(local, mark, url)
        a_c, t_c = run(cloud, mark, url)
        hl = mark.lower() in a_l.lower()
        hc = mark.lower() in a_c.lower()
        ok_l += hl
        ok_c += hc
        print("%-8s local=%-18r %4.1fs hit=%s | cloud=%-18r %4.1fs hit=%s"
              % (mark, a_l[:18], t_l, hl, a_c[:18], t_c, hc))
    print("TOTAL local %d/%d | cloud %d/%d" % (ok_l, len(CASES), ok_c, len(CASES)))


if __name__ == "__main__":
    main()
