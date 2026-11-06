# -*- coding: utf-8 -*-
"""找楼梯：列出世界里和某个室内包里，名字含 stair 的件及其 z 范围。

    blender -b <scene.blend> -P tools/_unbuffer.py -P tools/_probe_stairs.py -- cor_factb_int
"""
import bpy
import sys
from mathutils import Vector

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
PKG = ARGS[0] if ARGS else ''


def zr(o):
    zs = [(o.matrix_basis @ Vector(c)).z for c in o.bound_box]
    xs = [(o.matrix_basis @ Vector(c)).x for c in o.bound_box]
    ys = [(o.matrix_basis @ Vector(c)).y for c in o.bound_box]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


print('[st] 世界侧（名字含 stair）：')
for o in bpy.data.objects:
    if o.type == 'MESH' and 'stair' in o.name.lower():
        x0, x1, y0, y1, z0, z1 = zr(o)
        print('[st]   %-28s z[%.2f, %.2f]  x[%.1f, %.1f] y[%.1f, %.1f]' % (o.name, z0, z1, x0, x1, y0, y1))

print('[st] 室内包 %s（名字含 stair）：' % PKG)
for o in bpy.data.objects:
    if o.type == 'MESH' and o.get('int_pkg') == PKG and 'stair' in o.name.lower():
        x0, x1, y0, y1, z0, z1 = zr(o)
        print('[st]   %-28s z[%.2f, %.2f]  x[%.1f, %.1f] y[%.1f, %.1f]' % (o.name, z0, z1, x0, x1, y0, y1))
print('[st] === DONE ===')
