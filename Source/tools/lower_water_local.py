# -*- coding: utf-8 -*-
"""局部下调水面：把某个水域的水位压到「桥面以下」。

## 为什么

圣丹尼斯西南铁路桥（跨水段）实测：
    栈桥构件 z = 39.2 ~ 42.6
    水面     z = 42.75
⇒ 桥整段泡在水下 0.15~3.55 m，看起来"桥断了/没了"。

这是水位重建的误差（该湾被赋了偏高的水位），不是缺模型。

## 用法

    blender -b <blend> -P tools/lower_water_local.py -- \
        --center 2140 -1250 --radius 620 --target 38.6 [--ramp 200] [--out <blend>]
"""
import bpy
import sys
import json
import argparse
import numpy as np


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--center', nargs=2, type=float, required=True)
    ap.add_argument('--radius', type=float, default=620.0)
    ap.add_argument('--ramp', type=float, default=200.0)
    ap.add_argument('--target', type=float, required=True)
    ap.add_argument('--out', default='')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args(argv())

    water = bpy.data.objects['Water']
    n = len(water.data.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    water.data.vertices.foreach_get('co', co)
    co = co.reshape(n, 3)
    M = np.array(water.matrix_world)
    w = co @ M[:3, :3].T + M[:3, 3]
    cx, cy = a.center

    d = np.hypot(w[:, 0] - cx, w[:, 1] - cy)
    inside = d <= a.radius
    ramp = np.clip((a.radius + a.ramp - d) / max(1e-6, a.ramp), 0.0, 1.0)
    # 只降不升
    want = a.target + (w[:, 2] - a.target) * (1.0 - ramp)
    mask = inside & (want < w[:, 2] - 0.02)
    print('[water] 区域顶点 %d，需要下调的 %d' % (int(inside.sum()), int(mask.sum())))
    if mask.any():
        print('[water] 原水位 中位 %.2f → 目标 %.2f（最大降 %.2f）' % (
            float(np.median(w[inside, 2])), a.target,
            float((w[mask, 2] - want[mask]).max())))
    if a.dry or not mask.any():
        return

    w[mask, 2] = want[mask]
    Minv = np.linalg.inv(M)
    co2 = w @ Minv[:3, :3].T + Minv[:3, 3]
    water.data.vertices.foreach_set('co', co2.astype(np.float32).ravel())
    water.data.update()
    bpy.context.view_layer.update()

    out = a.out or bpy.data.filepath
    bpy.ops.wm.save_as_mainfile(filepath=out)
    import os
    print('[water] saved %s (%.2f GB)' % (out, os.path.getsize(out) / 1e9))


if __name__ == '__main__':
    main()
