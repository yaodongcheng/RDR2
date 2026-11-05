# -*- coding: utf-8 -*-
"""从**原生 H4** 生成「场景用」高度图（与交付给骑砍2 的大地图高度图分开）。

## 为什么需要这张

`deliverable/terrain/final/height_4m_16bit.png` 来自
`build_final_map_heightmap.py` → `deliverable/heightmap/continent_height_4m.png`，
那个脚本是给**骑砍2 大地图**用的，会**主动改地形**：
抬西北高原、压南边平原、**把内陆水系挖平到固定深度**（河 12~35 / 塘 8~18 / 湖 25~60 / 海 90~300）。

场景地形却直接读这张图 ⇒ 城里河段被挖成一片死平（实测安尼斯堡 x≥2960 处恒定 z=7.1，
水位 40.5 ⇒ 整段河被水淹，半个城看着泡在水里），而区域 blend 读原生 H4 是正常河床。

🔴 最高原则 §6.2：地形只用 RDR2 原生高度，不做压平/拟合/局部拉伸。
所以场景必须从 `work/terrain/H4.npy` 取高度。

## 做法

沿用交付图的**世界框与编码**（同一 pixel 网格、同一 zmin/zmax），
逐像素从 H4 最近邻取值 —— 场景侧代码不用改坐标口径，只换数据源。

产物：`deliverable/terrain/final/height_4m_16bit_native.png`

    python tools/build_scene_heightmap_native.py
"""
import json
import os

import numpy as np
from PIL import Image

RDR2 = r'D:/BrainMaker/大镖客2解包分析'
TERRAIN = os.path.join(RDR2, 'deliverable', 'terrain', 'final')
H4_PATH = os.path.join(RDR2, 'work', 'terrain', 'H4.npy')
OUT = os.path.join(TERRAIN, 'height_4m_16bit_native.png')

# H4 的世界框（与 blender_continent 同一份口径）
H4_X0, H4_Y0, H4_WORLD = -7684.0, -8196.0, 12296.0


def joaat(x):
    return x


def main():
    meta = json.load(open(os.path.join(TERRAIN, 'meta.json'), encoding='utf-8'))
    h = meta['height']
    x0, y0 = meta['world']['x0'], meta['world']['y0']
    x1, y1 = meta['world']['x1'], meta['world']['y1']
    res = h['m_per_px']
    W, Hh = int(h['px'][0]), int(h['px'][1])
    zmin, zmax = h['zmin'], h['zmax']

    H4 = np.load(H4_PATH).astype(np.float64)
    hh, hw = H4.shape
    print('H4 %dx%d  世界框 (%.0f,%.0f) %.0f m' % (hw, hh, H4_X0, H4_Y0, H4_WORLD))
    print('交付框 X[%.0f,%.0f] Y[%.0f,%.0f]  %dx%d @ %.0f m' % (x0, x1, y0, y1, W, Hh, res))

    # 🔴 H4 是**行 0 = 南**（Y0=-8196 为南边，行号随 y 增大而增大）——
    #    `blender_continent.terrain()` 的取法是 `r=(y-Y0)/res`、`c=(x-X0)/res`。
    #    而**交付高度图是行 0 = 北**，所以写图时要按 y1 - r*res 反推世界 y。
    # 🔴 像素**左上角**对齐（不加 0.5）—— 交付图的采样口径就是 `(y1-y)/res`，
    #    加半像素会让整张图偏移半格，实测回归点差 0.64 m（= 文档里的 shift(0,0) 0.678）。
    wx = x0 + np.arange(W) * res
    wy = y1 - np.arange(Hh) * res
    c = np.rint((wx - H4_X0) / res).astype(int)
    r = np.rint((wy - H4_Y0) / res).astype(int)
    c = np.clip(c, 0, hw - 1)
    r = np.clip(r, 0, hh - 1)
    z = H4[np.ix_(r, c)]

    q = np.rint((z - zmin) / (zmax - zmin) * 65535.0)
    q = np.clip(q, 0, 65535).astype(np.uint16)
    Image.fromarray(q, mode='I;16').save(OUT)
    print('写出 %s  (%.1f MB)' % (OUT, os.path.getsize(OUT) / 1e6))

    # 自检：抽几个点与 H4 对账
    for (tx, ty) in ((2883.6, 1347.9), (2960, 1348), (3000, 1348), (3200, 1348)):
        cc = int((tx - H4_X0) / res)
        rr = int((H4_Y0 + H4_WORLD - ty) / res)
        print('   H4 直取 世界(%.0f,%.0f) z=%.1f' % (tx, ty, H4[rr, cc]))


if __name__ == '__main__':
    main()
