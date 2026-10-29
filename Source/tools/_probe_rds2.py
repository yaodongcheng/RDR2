# -*- coding: utf-8 -*-
"""Per-slot surface area / normal orientation for the two road objects.

    blender -b <blend> --python tools/_unbuffer.py -P tools/_probe_rds2.py
"""
import bpy
import numpy as np

TARGETS = ('new_gar_rds_008', 'new_gar_rds_006b_decal', 'new_gar_rds_008_decal')


def area_stats(o):
    me = o.data
    me.calc_loop_triangles()
    nv = len(me.vertices)
    co = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    nt = len(me.loop_triangles)
    tri = np.empty(nt * 3, np.int32)
    me.loop_triangles.foreach_get('vertices', tri)
    tri = tri.reshape(-1, 3)
    p = co[tri]                                    # (nt,3,3)
    e1 = p[:, 1] - p[:, 0]
    e2 = p[:, 2] - p[:, 0]
    ar = 0.5 * np.linalg.norm(np.cross(e1, e2), axis=1)
    nrm = np.cross(e1, e2)
    ns = np.linalg.norm(nrm, axis=1)
    up = (nrm[:, 2] > 0) & (ns > 1e-9)

    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get('material_index', mi)
    # polygon -> its triangles share the same material
    poly_of_tri = np.empty(nt, np.int32)
    me.loop_triangles.foreach_get('polygon_index', poly_of_tri)
    tri_mat = mi[poly_of_tri]

    print('  %-26s tris=%d  total_area=%.1f m2  up-facing=%.1f%%'
          % (o.name, nt, ar.sum(), 100.0 * up.mean() if nt else 0))
    tot = ar.sum() or 1.0
    for i, m in enumerate(me.materials):
        sel = tri_mat == i
        a = ar[sel].sum()
        if not sel.any():
            continue
        print('     slot %2d %-46s area=%9.1f m2 (%5.1f%%)  tris=%-5d up=%4.1f%%'
              % (i, (m.name if m else '?')[:46], a, 100.0 * a / tot, int(sel.sum()),
                 100.0 * up[sel].mean()))


for t in TARGETS:
    print('')
    print('#### %s' % t)
    for o in [x for x in bpy.data.objects if x.name.startswith(t) and x.type == 'MESH']:
        area_stats(o)
