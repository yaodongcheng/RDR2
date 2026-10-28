# -*- coding: utf-8 -*-
"""按地形重算水面：每个水体用自己的岸线高程当水位，并把"海"补上。

## 为什么要改

原来的 `blender_continent.water()` 用一张**全局水位场** `world_water_level_2048.r16`，
但那张图只有 ~20% 的像素有值，其余是占位（ZMIN=-79.5），于是：
* 山地湖泊（岸线 232 m / 148 m）被画在 42.8 m —— **整个沉到地下**；
* 海（地形低于海平面的大片区域）根本没铺水，只剩海床。

实测（2026-10-21）：
    我方水面 10.8 km²，而地形低于 42.8 m 的面积 31.7 km²
    最大水体（Flat Iron Lake）岸线地形中位 42.0 m，水面 42.8 m —— 只差 0.8 m，说明**海平面定对了**

## 做法

1. 连通域分割现有水面掩码（`water_mask_from_blend.png`，行 0=北 → 先 flip 成与 H4 同向）；
2. 每个连通域：`level = median(岸线地形高程)`；
3. 海：`terrain < 全局海平面` 且**从图边连通**的区域（避免把内陆盆地灌满），
   水位 = 全局海平面 = 所有"大水体岸线高程"的中位数；
4. 重新生成 Water 网格（每个顶点用自己的水位），保存。

用法：
    blender -b deliverable/blender/continent/continent.blend -P tools/rebuild_water_levels.py
"""
import os
import sys
import json
import numpy as np
import cv2
from PIL import Image

ROOT = r'D:/BrainMaker/大镖客2解包分析'
OUT = os.path.join(ROOT, 'export/world/water_level_map.npy')
H4 = os.path.join(ROOT, 'work/terrain/H4.npy')
MASK = os.path.join(ROOT, 'export/world/water_mask_from_blend.png')
META = os.path.join(ROOT, 'export/world/world_meta.json')
X0, Y0 = -7684.0, -8196.0

P = 2048
RES = 12296.0 / P



def main():
    meta = json.load(open(META, encoding='utf-8'))
    Hg = np.load(H4)
    step = Hg.shape[0] / P
    idx = (np.arange(P) * step).astype(np.int32)
    Z = Hg[np.ix_(idx, idx)].astype(np.float32)

    m = np.array(Image.open(MASK).convert('L').resize((P, P))) > 60
    m = np.flipud(m)

    n, lab, stats, cent = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    order = [i for i in range(1, n) if stats[i, 4] > 60]
    info = []
    for i in order:
        comp = (lab == i)
        er = cv2.erode(comp.astype(np.uint8), np.ones((3, 3), np.uint8))
        ring = comp & (er == 0)
        lvl = float(np.median(Z[ring])) if ring.sum() > 30 else float(np.median(Z[comp]))
        info.append((i, int(stats[i, 4]), lvl))
    info.sort(key=lambda x: -x[1])
    print("[W] 水体 %d 个；最大的三个: " % len(info))
    for i, a, lvl in info[:3]:
        print("    comp %-3d area %-7d 岸线水位 %.1f" % (i, a, lvl))
    sea = float(np.median([lvl for _, _, lvl in info[:3]]))
    print("[W] 海平面 = %.1f m" % sea)

    low = (Z < sea).astype(np.uint8)
    ff = low.copy(); hgt, wid = ff.shape
    mask2 = np.zeros((hgt + 2, wid + 2), np.uint8)
    seeds = [(0, x) for x in range(0, wid, 32)] + [(hgt - 1, x) for x in range(0, wid, 32)] +             [(y, 0) for y in range(0, hgt, 32)] + [(y, wid - 1) for y in range(0, hgt, 32)]
    for sy, sx in seeds:
        if low[sy, sx] == 0: continue
        if mask2[sy + 1, sx + 1]: continue
        cv2.floodFill(ff, mask2, (sx, sy), 2)
    ocean = (ff == 2)
    print("[W] 海(连通边界) %.1f km²；内陆湖 %.1f km²" % (ocean.sum()*RES*RES/1e6, (m & ~ocean).sum()*RES*RES/1e6))

    level = np.full((P, P), np.nan, np.float32)
    for i, a, lvl in info:
        level[lab == i] = lvl
    level[ocean] = sea
    np.save(OUT, level)
    print("[W] ->", OUT, "wet %.1f km²" % ((~np.isnan(level)).sum()*RES*RES/1e6))

if __name__ == "__main__":
    main()
