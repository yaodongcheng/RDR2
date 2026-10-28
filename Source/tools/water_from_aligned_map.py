# -*- coding: utf-8 -*-
"""用"已对齐的官方地图水体"当形状真值，重建逐像素水位图（供 rebuild_water_from_map.py 用）。

## 为什么不能按高程灌水

RDR2 的世界 z 不是单一海平面基准：
* Flat Iron Lake / 东部海岸水面 ≈ **41.9 m**；
* 犰狳镇 **-14.7 m**、风滚草镇 **-3.3 m** —— 都是**干燥**的内陆洼地；
* 山地湖 **240 m / 147 m**。
所以"地形低于 41.9 就灌水"会把整个新奥斯汀淹掉（实测：犰狳镇、风滚草镇都会被淹）。

## 正确做法

1. 用标定好的相似变换（`地图下载/配准结果.json`）把官方图水体掩码反算到世界网格；
2. `mask = 官方水体 ∪ 我方原掩码`（官方补海/大湖，原掩码补小池塘）；
3. 按连通域给水位：`level = median(该水体岸线地形高程)`；
4. 输出 `export/world/water_level_map.npy`（float32，NaN = 陆地）。

用法：
    python tools/water_from_aligned_map.py
    blender -b deliverable/blender/continent/continent.blend -P tools/rebuild_water_from_map.py
"""
import os
import json
import numpy as np
import cv2
from PIL import Image

ROOT = r'D:/BrainMaker/大镖客2解包分析'
P = 2048
X0, Y0, WORLD, SCALE = -7684.0, -8196.0, 12296.0, 14.5
REF = os.path.join(ROOT, 'docs/世界与地编/img/ref_water_mask_1400.png')
OURS = os.path.join(ROOT, 'export/world/water_mask_from_blend.png')
OUT = os.path.join(ROOT, 'export/world/water_level_map.npy')


def main():
    fit = json.load(open(os.path.join(ROOT, '地图下载/配准结果.json'), encoding='utf-8'))
    a, c, tx, ty = fit['a'], fit['c'], fit['tx'], fit['ty']

    # 官方水体 → 世界网格
    ref = np.array(Image.open(REF).convert('L')) > 60
    Hm, Wm = ref.shape
    ys, xs = np.mgrid[0:P, 0:P].astype(np.float32)
    X = X0 + xs / P * WORLD
    Y = Y0 + ys / P * WORLD
    u = (X - X0) / SCALE
    v = (4100.0 - Y) / SCALE
    mx = (a * u - c * v + tx)
    my = (c * u + a * v + ty)
    map_water = cv2.remap(ref.astype(np.float32), mx, my, cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 0.5

    our = np.array(Image.open(OURS).convert('L').resize((P, P))) > 60
    our = np.flipud(our)                       # 行 0=北 → 与高程同向
    m = (map_water | our).astype(np.uint8)
    print('[W] 官方 %.1f km²  原掩码 %.1f km²  合并 %.1f km²' % (
        map_water.sum() * (WORLD / P) ** 2 / 1e6, our.sum() * (WORLD / P) ** 2 / 1e6,
        m.sum() * (WORLD / P) ** 2 / 1e6))

    h = np.load(os.path.join(ROOT, 'work/terrain/H4.npy')).astype(np.float32)
    step = h.shape[0] / P
    idx = (np.arange(P) * step).astype(np.int32)
    Z = h[np.ix_(idx, idx)]

    n, lab, stats, cent = cv2.connectedComponentsWithStats(m, 8)
    level = np.full((P, P), np.nan, np.float32)
    rows = []
    for i in range(1, n):
        if stats[i, 4] < 80:
            continue
        comp = (lab == i)
        er = cv2.erode(comp.astype(np.uint8), np.ones((3, 3), np.uint8))
        ring = comp & (er == 0)
        lvl = float(np.median(Z[ring])) if ring.sum() > 30 else float(np.median(Z[comp]))
        level[comp] = lvl
        rows.append((i, stats[i, 4], lvl))
    rows.sort(key=lambda r: -r[1])
    for i, sz, lvl in rows[:6]:
        print('    comp %-3d %8.2f km²  水位 %.1f' % (i, sz * (WORLD / P) ** 2 / 1e6, lvl))
    np.save(OUT, level)
    print('[W] ->', OUT, '  wet %.1f km²' % ((~np.isnan(level)).sum() * (WORLD / P) ** 2 / 1e6))


if __name__ == '__main__':
    main()
