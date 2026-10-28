# -*- coding: utf-8 -*-
"""在"桥/结构"下方把地形挖成河床，让水面留在原位 —— 修「桥被水淹没」。

## 背景（2026-10-27 实测）

圣丹尼斯西南铁路桥一带：水面 **42.75 m**、地形 40.3~41.1 m、桥面 40 m。
水面比地面高 1.6~2.6 m ⇒ 整座桥被水盖住，看起来"水下面有很深的东西"。
根因是我们的地形（从参考图重建）**没有把河床挖出来**。

直接把水压下去会让河消失（已经验证过）。正确做法是：**在桥下挖出河床**，
让水面留在原高度，桥面自然露在水上。

## 用法

    blender -b <blend> -P tools/carve_water_channel.py -- [--out <out.blend>] [--radius 90] [--depth 2.5] [--dry]

只影响「水面高于地形」且「离桥梁/结构对象 ≤ radius」的地形顶点，其它地方一律不动。
"""
import bpy
import os
import sys
import math
import argparse
import numpy as np


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='')
    ap.add_argument('--radius', type=float, default=90.0)
    ap.add_argument('--depth', type=float, default=2.5)
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args(argv())

    ter = bpy.data.objects['Terrain']
    water = bpy.data.objects['Water']
    ent = bpy.data.collections['ENTITIES']

    # 结构（桥）位置
    xs = []
    for c in ent.children:
        if not c.name.startswith('C_struct'):
            continue
        for sub in c.children:
            for o in sub.all_objects:
                xs.append((o.location.x, o.location.y))
    print('[carve] 桥梁/结构对象 %d 个' % len(xs))
    if not xs:
        print('[carve] 没有结构对象，退出')
        return
    P = np.array(xs, dtype=np.float64)

    X0, Y1, RES = -7684.0, 3224.0, 4.0
    W, H = 2692, 2006

    def grid_xyz(obj):
        v = np.empty(len(obj.data.vertices) * 3, dtype=np.float64)
        obj.data.vertices.foreach_get('co', v)
        v = v.reshape(-1, 3)
        M = np.array(obj.matrix_world)
        return v @ M[:3, :3].T + M[:3, 3], v, M

    tw, tv, Mt = grid_xyz(ter)
    ww, wv, Mw = grid_xyz(water)

    ix = np.clip(((tw[:, 0] - X0) / RES).astype(np.int64), 0, W - 1)
    iy = np.clip(((Y1 - tw[:, 1]) / RES).astype(np.int64), 0, H - 1)
    acc = np.zeros((H, W)); cnt = np.zeros((H, W))
    np.add.at(acc, (iy, ix), tw[:, 2]); np.add.at(cnt, (iy, ix), 1.0)
    tz = np.divide(acc, cnt, out=np.full_like(acc, np.nan), where=cnt > 0)

    # 水面栅格（有水的格子）
    wx = np.clip(((ww[:, 0] - X0) / RES).astype(np.int64), 0, W - 1)
    wy = np.clip(((Y1 - ww[:, 1]) / RES).astype(np.int64), 0, H - 1)
    wacc = np.zeros((H, W)); wcnt = np.zeros((H, W))
    np.add.at(wacc, (wy, wx), ww[:, 2]); np.add.at(wcnt, (wy, wx), 1.0)
    wz = np.divide(wacc, wcnt, out=np.full_like(wacc, np.nan), where=wcnt > 0)

    # 需要挖的格：有水面 且 水面高于地形 且 离桥足够近
    flood = np.isfinite(wz) & np.isfinite(tz) & (wz > tz - 0.05)
    near = np.zeros((H, W), dtype=bool)
    R = a.radius
    for px, py in P:
        c0 = max(0, int((px - R - X0) / RES)); c1 = min(W, int((px + R - X0) / RES) + 1)
        r0 = max(0, int((Y1 - (py + R)) / RES)); r1 = min(H, int((Y1 - (py - R)) / RES) + 1)
        if c1 <= c0 or r1 <= r0:
            continue
        cc = (np.arange(c0, c1) + 0.5) * RES + X0
        rr = Y1 - (np.arange(r0, r1) + 0.5) * RES
        d2 = (cc[None, :] - px) ** 2 + (rr[:, None] - py) ** 2
        near[r0:r1, c0:c1] |= (d2 <= R * R)
    carve = flood & near
    print('[carve] 需要挖的格: %d （全图淹水格 %d 的 %.1f%%）' % (
        int(carve.sum()), int(flood.sum()), 100.0 * carve.sum() / max(1, flood.sum())))
    if a.dry or not carve.any():
        return

    # 目标高度 = 水面 - depth
    target = np.where(carve, wz - a.depth, np.nan)

    # 对地形顶点：只降不升
    cur = tz[iy, ix]
    want = target[iy, ix]
    m = np.isfinite(want) & (tw[:, 2] > want + 0.02)
    print('[carve] 受影响地形顶点: %d' % int(m.sum()))
    tw[m, 2] = want[m]
    Minv = np.linalg.inv(Mt)
    tv2 = tw @ Minv[:3, :3].T + Minv[:3, 3]
    ter.data.vertices.foreach_set('co', tv2.astype(np.float32).ravel())
    ter.data.update()
    bpy.context.view_layer.update()

    out = a.out or bpy.data.filepath
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print('[carve] saved %s (%.2f GB)' % (out, os.path.getsize(out) / 1e9))


if __name__ == '__main__':
    main()
