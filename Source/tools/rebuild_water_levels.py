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
import bpy
import os
import sys
import json
import numpy as np
import cv2
from PIL import Image

ROOT = r'D:/BrainMaker/大镖客2解包分析'
H4 = os.path.join(ROOT, 'work/terrain/H4.npy')
MASK = os.path.join(ROOT, 'export/world/water_mask_from_blend.png')
META = os.path.join(ROOT, 'export/world/world_meta.json')
X0, Y0 = -7684.0, -8196.0

P = 2048
RES = 12296.0 / P


def main():
    meta = json.load(open(META, encoding='utf-8'))
    Hg = np.load(H4)                      # 4 m 原始高程，行 0 = 南
    # 采样到 2048
    step = Hg.shape[0] / P
    idx = (np.arange(P) * step).astype(np.int32)
    Z = Hg[np.ix_(idx, idx)].astype(np.float32)

    m = np.array(Image.open(MASK).convert('L').resize((P, P))) > 60
    m = np.flipud(m)                      # 渲染图行 0=北 → 与 Z 同向

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
    print('[W] 水体 %d 个，最大 3 个面积(px)/岸线水位:' % len(info))
    for i, a, lvl in info[:3]:
        print('    comp %-3d area %-7d level %.1f' % (i, a, lvl))

    # 全局海平面：取面积前 3 的水体岸线水位的中位
    sea = float(np.median([lvl for _, _, lvl in info[:3]]))
    print('[W] 海平面 = %.1f m' % sea)

    # 海：地形低于海平面 & 从边界连通
    low = (Z < sea).astype(np.uint8)
    ff = low.copy()
    hgt, wid = ff.shape
    mask2 = np.zeros((hgt + 2, wid + 2), np.uint8)
    for seed in [(0, 0), (0, wid - 1), (hgt - 1, 0), (hgt - 1, wid - 1)] + \
                [((0, x)) for x in range(0, wid, 64)] + [((hgt - 1, x)) for x in range(0, wid, 64)]:
        if low[seed] == 0:
            continue
        if mask2[seed[0] + 1, seed[1] + 1]:
            continue
        cv2.floodFill(ff, mask2, (seed[1], seed[0]), 2)
    ocean = (ff == 2)
    print('[W] 海(连通到边界) %.1f km²，内陆湖 %.1f km²' % (ocean.sum() * RES * RES / 1e6,
                                                   (m & ~ocean).sum() * RES * RES / 1e6))

    # 逐像素水位
    level = np.full((P, P), np.nan, np.float32)
    for i, a, lvl in info:
        level[lab == i] = lvl
    level[ocean] = sea
    wet = ~np.isnan(level)

    # 建网格（8 m 步长）
    s = max(1, int(round(8.0 / RES)))
    rows = np.arange(0, P - s, s)
    cols = np.arange(0, P - s, s)
    W4 = wet[np.ix_(rows, cols)] & wet[np.ix_(rows, cols + s)] & \
         wet[np.ix_(rows + s, cols)] & wet[np.ix_(rows + s, cols + s)]
    Lv = level[np.ix_(rows, cols)]
    ny, nx = len(rows), len(cols)
    X, Y = np.meshgrid(X0 + cols * RES, Y0 + rows * RES, indexing='xy')
    co = np.stack([X.ravel(), Y.ravel(), Lv.ravel()], axis=1).astype(np.float32)
    idx2 = np.arange(ny * nx, dtype=np.int32).reshape(ny, nx)
    a_ = idx2[:-1, :-1].ravel(); b_ = idx2[:-1, 1:].ravel()
    c_ = idx2[1:, :-1].ravel(); d_ = idx2[1:, 1:].ravel()
    quads = np.stack([a_, b_, d_, c_], axis=1)[W4.ravel()]
    print('[W] quads %d' % len(quads))

    old = bpy.data.objects.get('Water')
    mat = old.data.materials[0] if old and old.data.materials else None
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.new('Water')
    me.vertices.add(len(co)); me.vertices.foreach_set('co', co.ravel())
    me.loops.add(quads.size); me.loops.foreach_set('vertex_index', quads.ravel())
    me.polygons.add(len(quads))
    me.polygons.foreach_set('loop_start', np.arange(0, quads.size, 4, dtype=np.int32))
    me.update()
    if mat:
        me.materials.append(mat)
    ob = bpy.data.objects.new('Water', me)
    bpy.context.scene.collection.objects.link(ob)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'deliverable/blender/continent/continent.blend'))
    print('[W] saved')


if __name__ == '__main__':
    main()
