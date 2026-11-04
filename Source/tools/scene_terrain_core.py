# -*- coding: utf-8 -*-
"""场景地形采样核心（**纯 Python，不依赖 bpy**）。

`tools/scene_terrain.py`（Blender 里建网格）和 `tools/check_scene_terrain.py`（离线自检）
共用这一份实现 —— 保证"检查的"和"用于生产的"是同一段代码，不复制、不分叉。

🔴 三条硬口径（2026-11-04 实测，错一条断崖处就差 2~3 m，平地上看不出来）：
1. **行索引差一格**：交付物高度图与 H4 的最佳对齐是 `dy = -1`
   （shift(0,-1) 中位差 0.014 m；shift(0,0) 中位差 0.678 m）。
2. **顶点吸附全局格点**：`floor(x0/step)*step` 起算；从矩形左下角起算会落在半格上。
3. **最近邻**（`H[r, c]` 直取），不要双线性 —— 大陆 `blender_continent.terrain()` 就是这么做的。
"""

import json
import os

import numpy as np
from PIL import Image

RDR2 = r"D:/BrainMaker/大镖客2解包分析"
TERRAIN = os.path.join(RDR2, "deliverable", "terrain", "final")
H4 = os.path.join(RDR2, "work", "terrain", "H4.npy")

STEP = 4.0
ROW_SHIFT = 1.0     # 见上：dy = -1 格


def load_meta(path=None):
    m = json.load(open(path or os.path.join(TERRAIN, "meta.json"), encoding="utf-8"))
    h = m["height"]
    return {
        "x0": m["world"]["x0"], "y0": m["world"]["y0"],
        "x1": m["world"]["x1"], "y1": m["world"]["y1"],
        "hfile": os.path.join(TERRAIN, h["file"]),
        "hw": h["px"][0], "hh": h["px"][1], "hres": h["m_per_px"],
        "zmin": h["zmin"], "zmax": h["zmax"],
        "cfile": os.path.join(TERRAIN, m["color"]["file"]),
        "cw": m["color"]["px"][0], "ch": m["color"]["px"][1],
        "cres": m["color"]["m_per_px"],
    }


def heights(meta):
    im = np.asarray(Image.open(meta["hfile"]), dtype=np.float32)
    return meta["zmin"] + im / 65535.0 * (meta["zmax"] - meta["zmin"])


def sample_h(meta, H, x, y):
    """世界坐标 → 高度：**最近邻 + 行偏移一格**（与大陆同口径）。"""
    fx = (x - meta["x0"]) / meta["hres"]
    fy = (meta["y1"] - y) / meta["hres"] - ROW_SHIFT
    ix = np.clip(np.rint(fx).astype(int), 0, meta["hw"] - 1)
    iy = np.clip(np.rint(fy).astype(int), 0, meta["hh"] - 1)
    return H[iy, ix]


def axis(x0, x1, step=STEP):
    """一条网格轴：**吸附到全局格点**，并保证覆盖到 x1。"""
    a = np.arange(np.floor(x0 / step) * step, x1 + 1e-6, step, dtype=np.float64)
    if a[-1] < x1 - 1e-6:
        a = np.append(a, x1)
    return a


def uv_of(x, y, box):
    fx0, fy0, fx1, fy1 = box
    return ((x - fx0) / max(1e-6, fx1 - fx0),
            1.0 - (y - fy0) / max(1e-6, fy1 - fy0))


# 回归点：黑水镇贫民屋一带（**必须取 4 m 格点上的点**，否则"最近邻"取值本身有歧义）
# 这一组跨着一道 3.2 m 断崖 —— 行偏移/双线性/半格偏移任何一处出错都会被抓到。
REGRESSION = [
    (-804.0, -1412.0, 42.75),   # 断崖南侧（低台）
    (-800.0, -1412.0, 42.75),
    (-804.0, -1416.0, 45.92),   # 断崖北侧（高台），与低台差 3.17 m
]
