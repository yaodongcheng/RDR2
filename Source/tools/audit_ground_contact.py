# -*- coding: utf-8 -*-
"""数值化验收「贴地/浮空/陷地」：任意 blend 都能跑，不再靠肉眼。

对每个网格对象取世界 bbox 的最低点 `zmin`，在它 (x,y) 处垂直打射线到地形，
统计 `dz = zmin - terrain_z`：

    dz >  0.5  浮空
    |dz|<=0.5  贴地
    dz < -0.5  陷地（被地形埋住）

用法：
    blender -b <blend> -P tools/audit_ground_contact.py -- --out work/ground.json [--top 15]
    blender -b <blend> -P tools/audit_ground_contact.py -- --out work/ground.json --only-building

产物：JSON（总体统计 + 最差的 20 个对象），并打印一行 `GROUND n=… median=… 贴地=…%`。
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

# 与 fit_terrain_to_buildings.py 同一套"建筑类"判据
BUILD = re.compile(r'_ext_|building|_house|house_|cabin|barn|church|store|saloon|bank|hotel|shed|'
                   r'shack|manor|stable|station|factory|warehouse|roof|porch|wall|dock|tower', re.I)
SKIP = re.compile(r'^(Terrain|Water|Sun|Cam)', re.I)


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def pick_terrain():
    """地形对象：优先名字叫 Terrain；否则顶点数最多的那个网格。"""
    t = bpy.data.objects.get('Terrain')
    if t is not None and t.type == 'MESH':
        return t
    best = None
    for o in bpy.context.scene.objects:
        if o.type != 'MESH' or o.data is None:
            continue
        n = len(o.data.vertices)
        if best is None or n > best[0]:
            best = (n, o)
    return best[1] if best else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='')
    ap.add_argument('--top', type=int, default=15)
    ap.add_argument('--only-building', action='store_true')
    ap.add_argument('--max-dz', type=float, default=2000.0, help='射线长度上限（m）')
    ap.add_argument('--bbox', nargs='+', default=[],
                    help='只统计这个范围内的对象：x0 y0 x1 y1（或一个 "x0,y0,x1,y1"）')
    a = ap.parse_args(argv())

    bb = None
    if a.bbox:
        parts = []
        for tok in a.bbox:
            parts.extend(t for t in tok.replace(';', ',').split(',') if t.strip())
        v = [float(x) for x in parts]
        if len(v) == 4:
            bb = (min(v[0], v[2]), min(v[1], v[3]), max(v[0], v[2]), max(v[1], v[3]))
            print('[gc] bbox x[%.0f,%.0f] y[%.0f,%.0f]' % bb)

    ter = pick_terrain()
    if ter is None:
        raise SystemExit('找不到地形对象')
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(ter, dg)
    print('[gc] 地形对象 %s（%d verts）' % (ter.name, len(ter.data.vertices) if ter.data else 0))

    rows = []
    for o in bpy.context.scene.objects:
        if o.type != 'MESH' or o.data is None or o is ter:
            continue
        if SKIP.match(o.name):
            continue
        if a.only_building and not BUILD.search(o.name.lower()):
            continue
        try:
            M = o.matrix_world
            cs = [M @ Vector(c) for c in o.bound_box]
            zmin = min(v.z for v in cs)
            xs = [v.x for v in cs]
            ys = [v.y for v in cs]
            cx = 0.5 * (min(xs) + max(xs))
            cy = 0.5 * (min(ys) + max(ys))
        except Exception:
            continue
        if bb and not (bb[0] <= cx <= bb[2] and bb[1] <= cy <= bb[3]):
            continue
        hit = bvh.ray_cast(Vector((cx, cy, zmin + a.max_dz)), Vector((0, 0, -1)), 2 * a.max_dz)
        if hit[0] is None:
            continue
        rows.append(dict(name=o.name, x=round(cx, 2), y=round(cy, 2),
                         zmin=round(zmin, 3), ground=round(hit[0].z, 3),
                         dz=round(zmin - hit[0].z, 3)))

    if not rows:
        print('[gc] 没有可比对的对象')
        return
    d = np.array([r['dz'] for r in rows])
    n = len(d)
    res = dict(blend=bpy.data.filepath, terrain=ter.name, n=n,
               median=round(float(np.median(d)), 3),
               mean=round(float(d.mean()), 3),
               mae=round(float(np.abs(d).mean()), 3),
               floating=dict(n=int((d > 0.5).sum()), pct=round(100.0 * (d > 0.5).mean(), 1)),
               contact=dict(n=int((np.abs(d) <= 0.5).sum()),
                            pct=round(100.0 * (np.abs(d) <= 0.5).mean(), 1)),
               sunk=dict(n=int((d < -0.5).sum()), pct=round(100.0 * (d < -0.5).mean(), 1)),
               worst=sorted(rows, key=lambda r: -abs(r['dz']))[:20])
    print('GROUND n=%d median=%+.2f m  MAE=%.2f  浮空>0.5m=%.1f%%  贴地|d|<=0.5=%.1f%%  陷地<-0.5m=%.1f%%'
          % (n, res['median'], res['mae'], res['floating']['pct'],
             res['contact']['pct'], res['sunk']['pct']))
    print('[gc] 偏差最大的 %d 个：' % min(a.top, len(rows)))
    for r in res['worst'][:a.top]:
        print('   %-44s dz=%+7.2f  zmin=%.2f ground=%.2f' % (r['name'][:44], r['dz'],
                                                            r['zmin'], r['ground']))
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        json.dump(res, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('[gc] 写入 %s' % a.out)


if __name__ == '__main__':
    main()
