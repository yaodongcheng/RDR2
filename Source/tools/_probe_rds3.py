# -*- coding: utf-8 -*-
"""Who actually covers the ground inside new_gar_rds_008's bounding box?

Casts a downward ray per grid cell and tallies the FIRST hit object.

    blender -b <blend> --python tools/_unbuffer.py -P tools/_probe_rds3.py
"""
import bpy
from mathutils import Vector
from collections import Counter

NAME = 'new_gar_rds_008'
NX, NY = 60, 90        # 5,400 rays

o = bpy.data.objects.get(NAME)
if o is None:
    raise SystemExit('%s not found' % NAME)
cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
xs = [v.x for v in cs]
ys = [v.y for v in cs]
zs = [v.z for v in cs]
x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
z_start = max(zs) + 200.0

dg = bpy.context.evaluated_depsgraph_get()
scene = bpy.context.scene
counter = Counter()
nohit = 0
for i in range(NX):
    x = x0 + (i + 0.5) * (x1 - x0) / NX
    for j in range(NY):
        y = y0 + (j + 0.5) * (y1 - y0) / NY
        hit = scene.ray_cast(dg, Vector((x, y, z_start)), Vector((0.0, 0.0, -1.0)), distance=1000.0)
        ok = hit[0]
        if not ok:
            nohit += 1
            continue
        counter[hit[4].name if hit[4] else '(none)'] += 1

total = NX * NY
print('')
print('#### rays=%d  bbox=%.1f x %.1f m  z_start=%.1f' % (total, x1 - x0, y1 - y0, z_start))
print('#### no hit: %d (%.1f%%)' % (nohit, 100.0 * nohit / total))
for name, n in counter.most_common(20):
    print('   %-42s %6d  %5.1f%%' % (name, n, 100.0 * n / total))
fam = sum(n for k, n in counter.items() if k.startswith('new_gar_rds'))
print('#### new_gar_rds* 合计: %d (%.1f%%)' % (fam, 100.0 * fam / total))
