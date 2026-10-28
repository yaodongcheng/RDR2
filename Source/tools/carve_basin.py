# -*- coding: utf-8 -*-
"""把指定区域的地形挖成"水盆"，让水面能落在地形以下（修"水淹桥/湾消失"）。

## 用法

    blender -b <blend> -P tools/carve_basin.py -- \
        --center 2140 -1250 --radius 620 --water 38.6 --depth 2.5 [--out <blend>] [--dry]

半径内地形压到 `water - depth`，`radius ~ radius+ramp` 之间线性过渡。
"""
import bpy
import sys
import os
import argparse
import numpy as np


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--center', nargs=2, type=float, required=True)
    ap.add_argument('--radius', type=float, default=620.0)
    ap.add_argument('--ramp', type=float, default=150.0)
    ap.add_argument('--water', type=float, required=True, help='该区域目标水位')
    ap.add_argument('--depth', type=float, default=2.5, help='河床比水位低多少米')
    ap.add_argument('--out', default='')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args(argv())

    ter = bpy.data.objects['Terrain']
    n = len(ter.data.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    ter.data.vertices.foreach_get('co', co)
    co = co.reshape(n, 3)
    M = np.array(ter.matrix_world)
    w = co @ M[:3, :3].T + M[:3, 3]
    cx, cy = a.center
    d = np.hypot(w[:, 0] - cx, w[:, 1] - cy)
    inside = d <= a.radius
    ramp = np.clip((a.radius + a.ramp - d) / max(1e-6, a.ramp), 0.0, 1.0)
    bed = a.water - a.depth
    want = bed + (w[:, 2] - bed) * (1.0 - ramp)
    mask = inside & (want < w[:, 2] - 0.02)
    print('[basin] 区域顶点 %d，需要挖的 %d' % (int(inside.sum()), int(mask.sum())))
    if mask.any():
        print('[basin] 区域内地形 z 中位 %.2f → 压到 %.2f（最大降 %.2f）' % (
            float(np.median(w[inside, 2])), bed, float((w[mask, 2] - want[mask]).max())))
    if a.dry or not mask.any():
        return
    w[mask, 2] = want[mask]
    Minv = np.linalg.inv(M)
    co2 = w @ Minv[:3, :3].T + Minv[:3, 3]
    ter.data.vertices.foreach_set('co', co2.astype(np.float32).ravel())
    ter.data.update()
    bpy.context.view_layer.update()
    out = a.out or bpy.data.filepath
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print('[basin] saved %s (%.2f GB)' % (out, os.path.getsize(out) / 1e9))


if __name__ == '__main__':
    main()
