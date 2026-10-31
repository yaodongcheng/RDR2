# -*- coding: utf-8 -*-
"""在 v12 里实测：安尼斯堡一带的铁路**是不是被地形埋了**。

对每个名字带 rail 的网格，取它世界包围盒的中心 (x,y)，从上往下打一条射线：
  · 第一个命中的是 Terrain，且命中高度 > 这个铁路件的最高点 ⇒ 被地形盖住（看不见）
  · 第一个命中的是它自己 ⇒ 露在地表
另报：隐藏状态、世界 bbox 的 z 范围、与地形的高差。

    blender -b <continent_v12.blend> -P tools/_unbuffer.py -P tools/_probe_ann_view.py -- --x 2884 --y 1348 --r 900
"""
import bpy
import sys
import math

argv = sys.argv
ARGS = argv[argv.index('--') + 1:] if '--' in argv else []


def arg(name, default):
    if name in ARGS:
        i = ARGS.index(name)
        if i + 1 < len(ARGS):
            return float(ARGS[i + 1])
    return default


CX = arg('--x', 2884.0)
CY = arg('--y', 1348.0)
R = arg('--r', 900.0)
R2 = R * R

dg = bpy.context.evaluated_depsgraph_get()
scene = bpy.context.scene


def ray_down(x, y):
    """从 (x,y,+3000) 向下打，返回 (命中对象名, 命中 z)；没命中返回 (None, None)。"""
    from mathutils import Vector
    hit, loc, nrm, idx, ob, mw = scene.ray_cast(dg, Vector((x, y, 3000.0)), Vector((0, 0, -1)))
    if not hit:
        return None, None
    return (ob.name if ob else None), loc.z


rows = []
for ob in bpy.data.objects:
    if ob.type != 'MESH':
        continue
    if 'rail' not in ob.name.lower():
        continue
    x, y = ob.location.x, ob.location.y
    if (x - CX) ** 2 + (y - CY) ** 2 > R2:
        continue
    bb = [ob.matrix_world @ __import__('mathutils').Vector(c) for c in ob.bound_box]
    zmin = min(v.z for v in bb)
    zmax = max(v.z for v in bb)
    cx = sum(v.x for v in bb) / 8.0
    cy = sum(v.y for v in bb) / 8.0
    hit_ob, hit_z = ray_down(cx, cy)
    buried = (hit_ob is not None and hit_ob != ob.name and hit_z > zmax + 0.05)
    rows.append(dict(name=ob.name, cat=ob.get('cat') or '', hid=bool(ob.hide_render or ob.hide_viewport),
                     zmin=zmin, zmax=zmax, hit=hit_ob, hitz=hit_z, buried=buried,
                     x=x, y=y))

print('=== 半径 %.0f m 内名字带 rail 的网格 %d 个 ===' % (R, len(rows)))
nb = sum(1 for r in rows if r['buried'])
nh = sum(1 for r in rows if r['hid'])
print('  被地形盖住 %d / 隐藏 %d' % (nb, nh))
from collections import Counter
print('  命中体分类:', Counter((r['hit'] or '(无)') for r in rows).most_common(6))

print('\n=== 被地形盖住的（按埋深排序，前 25）===')
for r in sorted([r for r in rows if r['buried']], key=lambda t: -(t['hitz'] - t['zmax']))[:25]:
    print('  %-40s cat=%-8s 顶=%.2f 地形=%.2f 埋深=%.2f  %s'
          % (r['name'][:40], r['cat'], r['zmax'], r['hitz'], r['hitz'] - r['zmax'],
             'HIDDEN' if r['hid'] else ''))

print('\n=== 露在地表的（前 15）===')
for r in [r for r in rows if not r['buried']][:15]:
    print('  %-40s cat=%-8s 顶=%.2f 命中=%s@%.2f %s'
          % (r['name'][:40], r['cat'], r['zmax'], r['hit'], r['hitz'] if r['hitz'] is not None else -1,
             'HIDDEN' if r['hid'] else ''))

# 直接看 ann_02_rails_* 是否在
print('\n=== ann_02_rails_* ===')
for nm in ('ann_02_rails_01_01', 'ann_02_rails_02', 'ann_02_rails_03', 'ann_02_rails_04'):
    o = bpy.data.objects.get(nm)
    if not o:
        print('  %-24s 不在场景里' % nm)
        continue
    bb = [o.matrix_world @ __import__('mathutils').Vector(c) for c in o.bound_box]
    print('  %-24s z=[%.2f,%.2f]  loc=(%.1f,%.1f,%.1f) hide=%s' %
          (nm, min(v.z for v in bb), max(v.z for v in bb),
           o.location.x, o.location.y, o.location.z, o.hide_render))
