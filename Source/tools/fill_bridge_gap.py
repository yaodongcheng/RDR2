# -*- coding: utf-8 -*-
"""补齐桥梁缺口：把「西侧引桥」整组沿桥轴复制，填进引桥与主桥之间的空隙。

## 背景（2026-10-27 实测）

圣丹尼斯西南铁路桥沿桥轴排列后：
    西侧引桥   −256.6 ~ −193.2  (63.4 m)
    ← 缺口 →  −193.2 ~ −55.5   (137.7 m，tiles 里 4 个实体在模型库里没有)
    主桁架     −55.5 ~ +16.8

## 做法

1. 用「两侧的 struct 构件」拟合桥轴（PCA）；
2. 取西侧引桥那一组（投影落在 [west_lo, west_hi]）作为**供体**；
3. 复制供体 2 份，沿桥轴依次铺开，末端刚好接到主桁架起点；
4. 每份沿整体均匀缩放 `spacing/span`（≈1.09），让接缝严丝合缝；
5. 归入 `C_struct_桥梁结构` 的对应地块子集合。

用法：
    blender -b <blend> -P tools/fill_bridge_gap.py -- [--out <out.blend>] [--dry]
"""
import bpy
import os
import sys
import math
import argparse
import numpy as np
from mathutils import Vector, Matrix

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import blender_tour as tour

CX, CY = 2190.9, -1339.1     # 桥心（用户截图定位的那座）
RADIUS = 220.0


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if a.index('--') < len(a) else []


def proj_range(o, c, axis):
    M = o.matrix_world
    cs = [M @ Vector(cc) for cc in o.bound_box]
    pr = [((p.x - c[0]) * axis[0] + (p.y - c[1]) * axis[1]) for p in cs]
    return min(pr), max(pr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args(argv())

    cats = {k: col for k, zh, col in tour.cats()}
    struct = cats.get('struct')
    if struct is None:
        raise SystemExit('没有 C_struct 分类')

    objs = [o for o in struct.all_objects
            if math.hypot(o.location.x - CX, o.location.y - CY) < RADIUS]
    if len(objs) < 5:
        raise SystemExit('桥区结构件太少: %d' % len(objs))

    pts = np.array([[o.location.x, o.location.y] for o in objs])
    c = pts.mean(0)
    _u, _s, vt = np.linalg.svd(pts - c, full_matrices=False)
    axis = vt[0]
    print('[fill] 桥轴方向 = (%.3f, %.3f)' % (axis[0], axis[1]))

    segs = [(proj_range(o, c, axis), o) for o in objs]
    segs.sort(key=lambda t: t[0][0])
    west = [o for (r, o) in segs if r[1] < -150]
    east = [o for (r, o) in segs if r[0] > -100]
    if not west or not east:
        raise SystemExit('找不到西侧/东侧组')
    w_lo = min(proj_range(o, c, axis)[0] for o in west)
    w_hi = max(proj_range(o, c, axis)[1] for o in west)
    e_lo = min(proj_range(o, c, axis)[0] for o in east)
    span = w_hi - w_lo
    gap = e_lo - w_hi
    print('[fill] 供体 %d 件，跨度 %.1f m；缺口 %.1f m（%.1f → %.1f）' % (
        len(west), span, gap, w_hi, e_lo))
    if gap < 10:
        print('[fill] 缺口已经很小，无需补')
        return
    n = max(1, int(round(gap / span)))          # 需要几份
    spacing = gap / float(n)
    scale = spacing / span
    print('[fill] 铺 %d 份，间距 %.1f m，缩放 %.3f' % (n, spacing, scale))

    if a.dry:
        return

    made = 0
    for k in range(1, n + 1):
        off = spacing * k
        for o in west:
            ob = o.copy()
            ob.data = o.data
            ob.location = o.location + Vector((axis[0] * off, axis[1] * off, 0.0))
            ob.scale = (o.scale.x * scale, o.scale.y * scale, o.scale.z * scale)
            tid = tour._tile_of(ob.location.x, ob.location.y)
            sub = next((s for s in struct.children if s.get('tile') == tid), None)
            if sub is None:
                sub = bpy.data.collections.new('struct|%s' % tid)
                sub['tile'] = tid
                sub['cat'] = 'struct'
                struct.children.link(sub)
            sub.objects.link(ob)
            made += 1
    print('[fill] 新增桥段构件 %d 个' % made)
    out = a.out or bpy.data.filepath
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print('[fill] saved %s (%.2f GB)' % (out, os.path.getsize(out) / 1e9))


if __name__ == '__main__':
    main()
