# -*- coding: utf-8 -*-
"""把水面压到地形以下：凡是「水面 z > 地形 z - 0.05」的顶点，统一压到地形下方 5 cm。

## 为什么

水位是从参考图/水体掩码重建的，个别区域会算高（实测圣丹尼斯西南桥一带：
水面 **42.75 m**、地形 40.3~41.1 m、桥面 40 m ⇒ 整个桥被水盖住）。

## 用法

    blender -b <blend> -P tools/clamp_water.py -- [--out <out.blend>] [--dry]

做法：把 Terrain 顶点按 4 m 网格栅格化成高度图（numpy 向量化），
再对 Water 顶点做最近格采样比较，超出的压到 `terrain - sink`。不改拓扑，所以不会破面。
"""
import bpy
import os
import sys
import json
import argparse
import numpy as np


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='')
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--gap', type=float, default=0.05)
    ap.add_argument('--sink', type=float, default=2.0,
                    help='被判定为"淹到地面以上"的顶点压到 terrain - sink 米（默认 2，足够看不见）')
    a = ap.parse_args(argv())

    ter = bpy.data.objects.get('Terrain')
    water = bpy.data.objects.get('Water')
    if ter is None or water is None:
        raise SystemExit('缺 Terrain / Water')

    # 1) Terrain → 4 m 高度栅格
    tv = np.empty(len(ter.data.vertices) * 3, dtype=np.float64)
    ter.data.vertices.foreach_get('co', tv)
    tv = tv.reshape(-1, 3)
    M = np.array(ter.matrix_world)
    tw = tv @ M[:3, :3].T + M[:3, 3]
    X0, Y1, RES = -7684.0, 3224.0, 4.0
    W, H = 2692, 2006
    ix = np.clip(((tw[:, 0] - X0) / RES).astype(np.int64), 0, W - 1)
    iy = np.clip(((Y1 - tw[:, 1]) / RES).astype(np.int64), 0, H - 1)
    acc = np.zeros((H, W)); cnt = np.zeros((H, W))
    np.add.at(acc, (iy, ix), tw[:, 2])
    np.add.at(cnt, (iy, ix), 1.0)
    tz = np.divide(acc, cnt, out=np.full_like(acc, np.nan), where=cnt > 0)
    print('[water] 地形栅格: 有值格 %d / %d' % (int((cnt > 0).sum()), W * H))

    # 2) Water 顶点采样地形
    wv = np.empty(len(water.data.vertices) * 3, dtype=np.float64)
    water.data.vertices.foreach_get('co', wv)
    wv = wv.reshape(-1, 3)
    Mw = np.array(water.matrix_world)
    ww = wv @ Mw[:3, :3].T + Mw[:3, 3]
    wx = np.clip(((ww[:, 0] - X0) / RES).astype(np.int64), 0, W - 1)
    wy = np.clip(((Y1 - ww[:, 1]) / RES).astype(np.int64), 0, H - 1)
    g = tz[wy, wx]
    bad = np.isfinite(g) & (ww[:, 2] > g - a.gap)
    print('[water] 顶点 %d，高于地形的 %d (%.1f%%)' % (len(ww), int(bad.sum()), 100 * bad.mean()))
    if bad.any():
        print('[water] 超出量: 中位 %+.2f m  P95 %+.2f m  max %+.2f m' % (
            np.median(ww[bad, 2] - g[bad]), np.percentile(ww[bad, 2] - g[bad], 95),
            (ww[bad, 2] - g[bad]).max()))
    if a.dry:
        return

    ww[bad, 2] = g[bad] - a.sink
    Minv = np.linalg.inv(Mw)
    wv2 = ww @ Minv[:3, :3].T + Minv[:3, 3]
    water.data.vertices.foreach_set('co', wv2.astype(np.float32).ravel())
    water.data.update()
    bpy.context.view_layer.update()
    print('[water] 已压低 %d 个顶点' % int(bad.sum()))

    out = a.out or bpy.data.filepath
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print('[water] saved %s (%.2f GB)' % (out, os.path.getsize(out) / 1e9))


if __name__ == '__main__':
    main()
