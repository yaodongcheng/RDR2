# -*- coding: utf-8 -*-
"""全图地形贴合：把 Terrain 拉到"建筑基底"上（修 PAD 造成的整片浮空/陷地）。

## 为什么需要

`pad_field()` 把据点区域的地形压平到「该 100 m 格内**所有实例 z 的中位数**」。
但实例 z 混杂了道具/围栏/植被，中位数比建筑基底低 ⇒ **建筑整体浮空**。

2026-10-27 实测（continent.blend，2,042 个建筑类实例）：

| 指标 | 值 |
|---|---|
| 建筑底 − 地形（全图） | 中位 **+1.03 m**；浮空 >0.5 m **61.8%**；贴地 \|d\|≤0.5 仅 **17.9%** |
| 只统计「PAD 未改动」的区域 | 中位 **−0.23 m**（正常） |
| PAD 对地形的改动 | 中位 **−1.12 m**；压低 >0.5 m 占 **63.9%** |

⇒ **模型和高程数据都没错，是 PAD 压错了**。

## 做法（后处理，不重建）

1. 收集建筑类实例的"底点" `(x, y, zmin_world)` 作为锚点；
2. 锚点残差 `r = zmin − terrain_z(x,y)` 落到 4 m 栅格，逐格取均值；
3. 对 `r×w` 与 `w` 分别做可分离盒式模糊（3 遍 × 半径 8 格 ≈ 32 m），得到平滑校正场；
4. 每个地形顶点按双线性采样校正场，`z += clamp(field, ±MAX_DZ)`；`w` 太小的区域不动（避免野外被拉）。

## 用法

    blender -b deliverable/blender/continent/continent.blend \
      -P tools/fit_terrain_to_buildings.py -- --out <out.blend> [--max-dz 8] [--dry]

`--dry` 只打印前后统计，不写文件。
"""
import bpy
import os
import sys
import json
import re
import argparse
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
META = os.path.join(ROOT, 'deliverable/heightmap/continent_height_meta.json')

BUILD = re.compile(r'_ext_|building|_house|house_|cabin|barn|church|store|saloon|bank|hotel|shed|shack|manor|stable|station|factory|warehouse|roof|porch|wall|dock|tower', re.I)


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF


def load_names():
    d = {}
    if not os.path.exists(NAMES):
        return d
    with open(NAMES, encoding='latin1', errors='ignore') as f:
        for l in f:
            n = l.strip()
            if n:
                d.setdefault(joaat(n), n)
    return d


def box_sum(a, r, passes=3):
    """可分离盒式和（不归一化，零填充）——用来算窗口内的权重和。"""
    out = a.astype(np.float64).copy()
    n0, n1 = out.shape
    for _ in range(passes):
        for axis in (0, 1):
            n = out.shape[axis]
            k = 2 * r + 1
            pad = [(0, 0), (0, 0)]
            pad[axis] = (r + 1, r)
            p = np.pad(out, pad, mode='constant', constant_values=0.0)
            c = np.cumsum(p, axis=axis)
            hi = [slice(None), slice(None)]
            lo = [slice(None), slice(None)]
            hi[axis] = slice(2 * r + 1, 2 * r + 1 + n)
            lo[axis] = slice(0, n)
            out = c[tuple(hi)] - c[tuple(lo)]
    return out


def anchors_from_scene(names):
    ter = bpy.data.objects.get('Terrain')
    bvh = BVHTree.FromObject(ter, bpy.context.evaluated_depsgraph_get())
    ents = bpy.data.collections.get('ENTITIES')
    pts = []
    for o in ents.objects:
        try:
            hx = int(o.name[2:], 16)
        except Exception:
            continue
        if not BUILD.search(names.get(hx, '')):
            continue
        M = o.matrix_world
        zs = [(M @ Vector(c)).z for c in o.bound_box]
        x, y = o.location.x, o.location.y
        hit = bvh.ray_cast(Vector((x, y, 2000.0)), Vector((0, 0, -1)), 4000.0)
        if hit[0] is None:
            continue
        pts.append((x, y, min(zs), hit[0].z))
    return pts, ter, bvh


def stats(ter, bvh, pts):
    d = np.array([zmin - g for _, _, zmin, g in pts])
    # 用"改后"的地形重新取地面
    d2 = []
    for x, y, zmin, _ in pts:
        hit = bvh.ray_cast(Vector((x, y, 2000.0)), Vector((0, 0, -1)), 4000.0)
        if hit[0] is not None:
            d2.append(zmin - hit[0].z)
    d2 = np.array(d2)
    return d, d2


def cells_for(o):
    """建筑的世界 bbox → (center, half-extents, zmin)。"""
    M = o.matrix_world
    cs = [M @ Vector(c) for c in o.bound_box]
    xs = [v.x for v in cs]; ys = [v.y for v in cs]
    cx = (min(xs) + max(xs)) / 2.0; cy = (min(ys) + max(ys)) / 2.0
    hx = max(1.5, (max(xs) - min(xs)) / 2.0); hy = max(1.5, (max(ys) - min(ys)) / 2.0)
    return cx, cy, hx, hy, min(v.z for v in cs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='')
    ap.add_argument('--max-dz', type=float, default=8.0)
    ap.add_argument('--radius', type=int, default=2)
    ap.add_argument('--mode', choices=['pad', 'field'], default='pad')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args(argv())

    names = load_names()
    meta_all = json.load(open(META, encoding='utf-8'))
    hm = meta_all['heightmap']
    W, H = hm['w'], hm['h']
    X0, Y1, RES = meta_all['x0'], meta_all['y1'], hm['res_m']

    pts, ter, bvh = anchors_from_scene(names)
    print('[fit] 锚点 %d 个（建筑类实例）' % len(pts))
    before = np.array([zmin - g for _, _, zmin, g in pts])
    print('[fit] 改前: 中位 %+.2f m  MAE %.2f  浮>0.5 %.1f%%  埋<-0.5 %.1f%%  贴地 %.1f%%' % (
        np.median(before), np.abs(before).mean(), 100 * (before > 0.5).mean(),
        100 * (before < -0.5).mean(), 100 * (np.abs(before) <= 0.5).mean()))

    delta = np.zeros((H, W), dtype=np.float64)
    cover = np.zeros((H, W), dtype=np.float64)

    if a.mode == 'pad':
        # 每栋建筑：以 (zmin - 地面) 作为该处的抬升量，铺满其 footprint 椭圆
        stamped = 0
        for o in bpy.data.collections['ENTITIES'].objects:
            try:
                hx_i = int(o.name[2:], 16)
            except Exception:
                continue
            if not BUILD.search(names.get(hx_i, '')):
                continue
            cx, cy, hx, hy, zmin = cells_for(o)
            hit = bvh.ray_cast(Vector((cx, cy, 2000.0)), Vector((0, 0, -1)), 4000.0)
            if hit[0] is None:
                continue
            d = zmin - hit[0].z
            c0 = max(0, int((cx - hx - 2 - X0) / RES)); c1 = min(W, int((cx + hx + 2 - X0) / RES) + 1)
            r0 = max(0, int((Y1 - (cy + hy + 2)) / RES)); r1 = min(H, int((Y1 - (cy - hy - 2)) / RES) + 1)
            for r in range(r0, r1):
                wy = Y1 - (r + 0.5) * RES
                for c in range(c0, c1):
                    wx = X0 + (c + 0.5) * RES
                    dx = (wx - cx) / (hx + 1.0); dy = (wy - cy) / (hy + 1.0)
                    if dx * dx + dy * dy <= 1.0:
                        delta[r, c] = d
                        cover[r, c] = 1.0
                        stamped += 1
        print('[fit] pad 覆盖 %d 格（%d 栋建筑）' % (int((cover > 0).sum()), stamped and len(pts)))
        # 未覆盖处：邻近扩散（6 遍），再整体轻度平滑，避免台阶
        known = cover > 0
        for _ in range(6):
            num = box_sum(np.where(known, delta, 0.0), 1, passes=1)
            den = box_sum(known.astype(np.float64), 1, passes=1)
            cand = np.divide(num, den, out=np.zeros_like(num), where=den > 1e-6)
            grow = (~known) & (den > 1e-6)
            delta[grow] = cand[grow]
            known = known | grow
        field = box_sum(delta, a.radius, passes=2) / np.maximum(box_sum(known.astype(np.float64), a.radius, passes=2), 1e-6)
        field = field * np.clip(box_sum(cover, 2, passes=2), 0.0, 1.0)
    else:
        acc = np.zeros((H, W)); wgt = np.zeros((H, W))
        for x, y, zmin, g in pts:
            c = int((x - X0) / RES); r = int((Y1 - y) / RES)
            if 0 <= r < H and 0 <= c < W:
                acc[r, c] += (zmin - g); wgt[r, c] += 1.0
        mean_r = np.divide(acc, wgt, out=np.zeros_like(acc), where=wgt > 0)
        num = box_sum(mean_r * wgt, a.radius); den = box_sum(wgt, a.radius)
        field = np.divide(num, den, out=np.zeros_like(num), where=den > 1e-6)
        field = field * np.clip(den / 2.0, 0.0, 1.0)

    field = np.clip(field, -a.max_dz, a.max_dz)
    nz = np.abs(field) > 1e-6
    print('[fit] 校正场: 生效格 %d  中位 %+.2f m  P5 %+.2f  P95 %+.2f' % (
        int(nz.sum()), np.median(field[nz]) if nz.any() else 0.0,
        np.percentile(field[nz], 5) if nz.any() else 0.0, np.percentile(field[nz], 95) if nz.any() else 0.0))

    me = ter.data
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64); me.vertices.foreach_get('co', co); co = co.reshape(n, 3)
    M = np.array(ter.matrix_world)
    wx = co @ M[:3, :3].T + M[:3, 3]
    fx = np.clip((wx[:, 0] - X0) / RES - 0.5, 0, W - 2)
    fy = np.clip((Y1 - wx[:, 1]) / RES - 0.5, 0, H - 2)
    x0 = np.floor(fx).astype(np.int64); y0 = np.floor(fy).astype(np.int64)
    tx = fx - x0; ty = fy - y0
    f = (field[y0, x0] * (1 - tx) * (1 - ty) + field[y0, x0 + 1] * tx * (1 - ty)
         + field[y0 + 1, x0] * (1 - tx) * ty + field[y0 + 1, x0 + 1] * tx * ty)
    print('[fit] 受影响顶点 %d / %d (%.1f%%)' % (int((np.abs(f) > 1e-6).sum()), n, 100 * (np.abs(f) > 1e-6).mean()))

    wx[:, 2] += f
    Minv = np.linalg.inv(M)
    co2 = wx @ Minv[:3, :3].T + Minv[:3, 3]
    me.vertices.foreach_set('co', co2.astype(np.float32).ravel())
    me.update()
    bpy.context.view_layer.update()

    bvh2 = BVHTree.FromObject(ter, bpy.context.evaluated_depsgraph_get())
    after = []
    for x, y, zmin, _ in pts:
        hit = bvh2.ray_cast(Vector((x, y, 2000.0)), Vector((0, 0, -1)), 4000.0)
        if hit[0] is not None:
            after.append(zmin - hit[0].z)
    after = np.array(after)
    print('[fit] 改后: 中位 %+.2f m  MAE %.2f  浮>0.5 %.1f%%  埋<-0.5 %.1f%%  贴地 %.1f%%' % (
        np.median(after), np.abs(after).mean(), 100 * (after > 0.5).mean(),
        100 * (after < -0.5).mean(), 100 * (np.abs(after) <= 0.5).mean()))

    if not a.dry:
        if not a.out:
            a.out = bpy.data.filepath
        bpy.ops.wm.save_as_mainfile(filepath=a.out)
        print('[fit] saved %s (%.2f GB)' % (a.out, os.path.getsize(a.out) / 1e9))


if __name__ == '__main__':
    main()
