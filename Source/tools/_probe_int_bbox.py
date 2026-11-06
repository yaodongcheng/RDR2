# -*- coding: utf-8 -*-
"""列出某个室内包里**超出宿主包围盒**的件，用于解释「套合后仍超出宿主」告警。

    blender -b <scene.blend> -P tools/_unbuffer.py -P tools/_probe_int_bbox.py -- cor_factb_int cor_factoryes
"""
import bpy
import sys
from mathutils import Vector

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
PKG = ARGS[0] if ARGS else ''
HOST = ARGS[1] if len(ARGS) > 1 else ''


def bb(o):
    xs, ys, zs = [], [], []
    for c in o.bound_box:
        w = o.matrix_basis @ Vector(c)
        xs.append(w.x); ys.append(w.y); zs.append(w.z)
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


host = bpy.data.objects.get(HOST)
if host is None:
    print('[bb] 找不到宿主', HOST)
    sys.exit(1)
hx0, hx1, hy0, hy1, hz0, hz1 = bb(host)
print('[bb] 宿主 %s  x[%.2f, %.2f] y[%.2f, %.2f] z[%.2f, %.2f]'
      % (HOST, hx0, hx1, hy0, hy1, hz0, hz1))

rows = []
for o in bpy.data.objects:
    if o.type != 'MESH' or o.get('int_pkg') != PKG:
        continue
    x0, x1, y0, y1, z0, z1 = bb(o)
    out = max(hx0 - x0, x1 - hx1, hy0 - y0, y1 - hy1, hz0 - z0, z1 - hz1)
    rows.append((out, o.name))
rows.sort(reverse=True)
print('[bb] 包 %s 共 %d 件；超出宿主最多的 8 件：' % (PKG, len(rows)))
for out, n in rows[:8]:
    print('[bb]   %-22s 超出 %+.2f m' % (n, out))
print('[bb] === DONE ===')
