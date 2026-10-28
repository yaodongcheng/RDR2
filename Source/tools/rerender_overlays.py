# -*- coding: utf-8 -*-
"""按标定好的相似变换，重画「据点 / 水面」两张比对图。

被 `fit_map_anchors.py --rerender` 调用，也可以自己跑：

    python tools/rerender_overlays.py --a 1.7188 --tx -60 --ty 11.3
"""
import os
import json
import argparse

import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "docs/世界与地编/img")
REF = os.path.join(IMG, "ref_map_grid_clean.png")     # 官方图水体掩码（无网格）
WATER = os.path.join(ROOT, "export/world/water_mask_from_blend.png")
CAMPAIGN = os.path.join(ROOT, "export/world/campaign.json")
BASE_JPG = os.path.join(ROOT, "地图下载/大陆地图_缩略.jpg")

W = 1400
X0, YM1, SCALE = -7684.0, 4100.0, 14.5


def _ref_mask():
    p = os.path.join(IMG, "ref_water_mask_1400.png")
    if os.path.exists(p):
        return np.array(Image.open(p).convert("L")) > 60
    # 现场从原图算
    ref = np.array(Image.open(os.path.join(ROOT, "地图下载/大陆地图_缩略.jpg")).convert("RGB"))
    ref = cv2.resize(ref, (W, int(ref.shape[0] * W / ref.shape[1])), interpolation=cv2.INTER_AREA)
    d = np.abs(ref.astype(np.int16) - np.array([145, 138, 120], np.int16)).sum(2)
    m = (d < 55).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    Image.fromarray((m * 255).astype(np.uint8)).save(p)
    return m > 0


def run(a, c, tx, ty):
    os.makedirs(IMG, exist_ok=True)
    ref = _ref_mask()
    H = ref.shape[0]
    water = np.array(Image.open(WATER).convert("L")) > 60
    M = np.array([[a, -c, tx], [c, a, ty]], np.float32)
    w = cv2.warpAffine((water * 255).astype(np.uint8), M, (W, H), flags=cv2.INTER_NEAREST) > 60

    # 水面：橙填充 + 官方轮廓
    cnts, _ = cv2.findContours(ref.astype(np.uint8) * 255, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    cv = np.zeros((H, W, 3), np.uint8)
    cv[w] = (40, 190, 255)                       # BGR
    cv2.drawContours(cv, cnts, -1, (255, 110, 40), 2)
    Image.fromarray(cv2.cvtColor(cv, cv2.COLOR_BGR2RGB)).save(os.path.join(IMG, "overlay_water.png"))

    # 据点
    base = Image.open(BASE_JPG).convert("RGB")
    base = base.resize((W, int(base.height * W / base.width)))
    im = base.copy()
    d = ImageDraw.Draw(im)
    camp = json.load(open(CAMPAIGN, encoding="utf-8"))
    for t in camp.get("towns", []):
        if not t.get("r") or t.get("u") is None:
            continue
        x = a * t["u"] - c * t["v"] + tx
        y = c * t["u"] + a * t["v"] + ty
        d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(230, 30, 30))
    im.save(os.path.join(IMG, "overlay_towns.png"))

    iou = float((w & ref).sum() / max(1, (w | ref).sum()))
    return iou


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", type=float, required=True)
    ap.add_argument("--c", type=float, default=0.0)
    ap.add_argument("--tx", type=float, required=True)
    ap.add_argument("--ty", type=float, required=True)
    a = ap.parse_args()
    iou = run(a.a, a.c, a.tx, a.ty)
    print("重画完成，水面 IoU = %.3f" % iou)


if __name__ == "__main__":
    main()
