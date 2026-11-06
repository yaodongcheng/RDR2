# -*- coding: utf-8 -*-
"""体检：把某个室内包整体上移 N 米后，还有多少顶点高于建筑（会不会透出屋顶）。

    blender -b <scene.blend> -P tools/_unbuffer.py -P tools/_probe_clearance.py -- <pkg> <host> [额外dz]

输出：房间壳 bbox / 越界顶点数 / 最大越界 / 超 0.1 m 的顶点占比。
判据：越界顶点越少、最大越界越小 = 越不容易穿顶。
"""
import bpy
import sys
from mathutils import Vector

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
PKG = ARGS[0] if len(ARGS) > 0 else ''
HOST = ARGS[1] if len(ARGS) > 1 else ''
DZ = float(ARGS[2]) if len(ARGS) > 2 else 0.0
CELL = 1.0
MARGIN = 0.10


def pts(o, dz=0.0):
    m = o.matrix_basis
    return [(m @ v.co) + Vector((0, 0, dz)) for v in o.data.vertices]


host = bpy.data.objects.get(HOST)
if host is None:
    print('[cl] 找不到宿主', HOST)
    sys.exit(1)
bv = pts(host)
cap = {}
for p in bv:
    k = (int(p.x // CELL), int(p.y // CELL))
    if p.z > cap.get(k, -1e9):
        cap[k] = p.z

pkg_objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.get('int_pkg') == PKG]
if not pkg_objs:
    print('[cl] 包里没有对象', PKG)
    sys.exit(1)

tot = 0
over_n = 0
over_max = 0.0
big = 0
for o in pkg_objs:
    for p in pts(o, DZ):
        k = (int(p.x // CELL), int(p.y // CELL))
        c = -1e9
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                v = cap.get((k[0] + dx, k[1] + dy))
                if v is not None and v > c:
                    c = v
        if c < -1e8:
            continue
        tot += 1
        o_ = p.z - (c - MARGIN)
        if o_ > 0:
            over_n += 1
            over_max = max(over_max, o_)
            if o_ > 0.1:
                big += 1

# 房间壳（占地最大的那件）的 z 范围
main = max(pkg_objs, key=lambda o: (o.dimensions.x * o.dimensions.y))
zs = [(main.matrix_basis @ Vector(c)).z + DZ for c in main.bound_box]
print('[cl] %s +dz=%.2f m：判定顶点 %d，越界 %d（%.2f%%），其中 >0.1m 的 %d 个，最大越界 %.2f m'
      % (PKG, DZ, tot, over_n, 100.0 * over_n / max(1, tot), big, over_max))
print('[cl] 房间壳 %s z[%.2f, %.2f]（原点 z %.2f）'
      % (main.name, min(zs), max(zs), main.matrix_basis.to_translation().z + DZ))
print('[cl] === DONE ===')
