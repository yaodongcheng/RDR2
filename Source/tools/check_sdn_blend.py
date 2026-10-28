# -*- coding: utf-8 -*-
"""查 sdn.blend：分块(TILE_*)布局 + 桥/铁路对象的真实世界位置（用 bbox，不用 origin）。"""
import bpy, os, re, collections
from mathutils import Vector

RE_BRIDGE = re.compile(r'bridge|_bri\d|_bri_|trestle|_tres|truss|girder|viaduct', re.I)
RE_RAIL = re.compile(r'_r_c_|_r_b_|railroad|_rails|rrcross|sle\d\d|\._r_', re.I)


def wbb(o):
    mn = Vector((1e18,) * 3); mx = Vector((-1e18,) * 3)
    for c in o.bound_box:
        p = o.matrix_world @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], p[i]); mx[i] = max(mx[i], p[i])
    return mn, mx


print('[sdn] 对象 %d' % len(bpy.context.scene.objects))
tiles = {}
for c in bpy.data.collections:
    if not c.name.startswith('TILE_RDR2_Zup'):
        continue
    objs = [o for o in c.objects if o.type == 'MESH']
    if not objs:
        continue
    mn = Vector((1e18,) * 3); mx = Vector((-1e18,) * 3)
    for o in objs:
        a, b = wbb(o)
        for i in range(3):
            mn[i] = min(mn[i], a[i]); mx[i] = max(mx[i], b[i])
    tiles[c.name] = (len(objs), mn, mx)

print('[sdn] TILE 集合 %d 个，按 x 排序:' % len(tiles))
for n, (cnt, mn, mx) in sorted(tiles.items(), key=lambda kv: (kv[1][1].x, kv[1][1].y)):
    print('   %-20s obj %-5d  x[%7.0f,%7.0f] y[%7.0f,%7.0f] z[%6.1f,%6.1f]' % (
        n, cnt, mn.x, mx.x, mn.y, mx.y, mn.z, mx.z))

# 桥 / 铁路
br, rl = [], []
for o in bpy.context.scene.objects:
    if o.type != 'MESH':
        continue
    mn, mx = wbb(o)
    c = (mn + mx) / 2
    if RE_BRIDGE.search(o.name):
        br.append((o.name, c.x, c.y, c.z, mn.z, mx.z, max(mx.x - mn.x, mx.y - mn.y)))
    elif RE_RAIL.search(o.name):
        rl.append((o.name, c.x, c.y, c.z, mn.z, mx.z, max(mx.x - mn.x, mx.y - mn.y)))
print('\n[sdn] 桥类 %d 个，铁路类 %d 个' % (len(br), len(rl)))
print('[sdn] 桥（按 x 排序）:')
for r in sorted(br, key=lambda x: x[1])[:30]:
    print('    %-40s c=(%7.1f,%8.1f,%6.1f) z[%6.1f,%6.1f] 跨度%.0f' % (r[0][:40], r[1], r[2], r[3], r[4], r[5], r[6]))
print('[sdn] 铁路（按 x 排序，前 30）:')
for r in sorted(rl, key=lambda x: x[1])[:30]:
    print('    %-40s c=(%7.1f,%8.1f,%6.1f) z[%6.1f,%6.1f]' % (r[0][:40], r[1], r[2], r[3], r[4], r[5]))
