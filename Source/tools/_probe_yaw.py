# -*- coding: utf-8 -*-
"""量两个对象的**世界朝向**（yaw，度），用于核对室内壳与外壳是否对齐。

    blender -b <scene.blend> -P tools/_unbuffer.py -P tools/_probe_yaw.py -- cor_factoryes i_8435e65c

每个参数是一个名字前缀；同前缀多个对象时只报第一个，并注明命中数。
"""
import bpy
import math
import sys
from mathutils import Vector

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def show_all():
    def walk(lc):
        lc.exclude = False
        lc.hide_viewport = False
        for c in lc.children:
            walk(c)
    walk(bpy.context.view_layer.layer_collection)
    bpy.context.view_layer.update()


show_all()

for pre in ARGS:
    # 先按**精确名**找（避免 `cor_factoryes` 把 `_deck/_dtls/_slod` 一起并进来），找不到才按前缀
    exact = [o for o in bpy.data.objects if o.name == pre]
    hits = exact or [o for o in bpy.data.objects if o.name.startswith(pre)]
    if not hits:
        print('[yaw] %-24s 没有命中' % pre)
        continue
    ob = hits[0]
    mw = ob.matrix_world
    # 世界 +X 轴 → 求它在 XY 平面的朝向
    f = (mw.to_3x3() @ Vector((1.0, 0.0, 0.0)))
    yaw = math.degrees(math.atan2(f.y, f.x))
    loc = mw.to_translation()
    print('[yaw] %-22s 命中%2d 位置(%.1f, %.1f, %.1f) 世界yaw=%7.2f°'
          % (ob.name, len(hits), loc.x, loc.y, loc.z, yaw))
    # 世界包围盒（便于核对室内壳与外壳是否套得上）
    xs, ys, zs = [], [], []
    for h in hits:
        if h.type != 'MESH':
            continue
        for c in h.bound_box:
            w = h.matrix_world @ Vector(c)
            xs.append(w.x); ys.append(w.y); zs.append(w.z)
    if xs:
        print('[yaw]   bbox x[%.2f, %.2f] y[%.2f, %.2f] z[%.2f, %.2f]  尺寸 %.1f×%.1f×%.1f'
              % (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs),
                 max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)))
print('[yaw] === DONE ===')
