# -*- coding: utf-8 -*-
"""Does anything else sit on top of new_gar_rds_008's own surface?

For every triangle of the road mesh: cast a ray straight up from its centroid and
record the FIRST thing it hits (and how far above the road it is).

    blender -b <blend> --python tools/_unbuffer.py -P tools/_probe_above.py

Writes D:/BrainMaker/大镖客2解包分析/export/previews/rds008_20261029/_rds_008_above.png
"""
import bpy
import numpy as np
from mathutils import Vector

NAME = 'new_gar_rds_008'
OUT = 'D:/BrainMaker/大镖客2解包分析/export/previews/rds008_20261029/_rds_008_above.png'

ob = bpy.data.objects.get(NAME)
me = ob.data
mw = ob.matrix_world
me.calc_loop_triangles()
nt = len(me.loop_triangles)
nv = len(me.vertices)
co = np.empty(nv * 3, np.float32)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
tri = np.empty(nt * 3, np.int32)
me.loop_triangles.foreach_get('vertices', tri)
tri = tri.reshape(-1, 3)
p = co[tri]
ar = 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
cen = p.mean(axis=1)                       # local centroids
cen_w = np.array([(mw @ Vector(c)) for c in cen])

dg = bpy.context.evaluated_depsgraph_get()
scene = bpy.context.scene

BUCKETS = [('self', 0), ('<2cm', 1), ('2-30cm', 2), ('30cm-2m', 3), ('>2m', 4), ('clear', 5)]
idx = np.full(nt, 5, np.int32)
dist = np.full(nt, -1.0, np.float32)
hitname = [''] * nt

for i in range(nt):
    o = Vector((cen_w[i][0], cen_w[i][1], cen_w[i][2] + 0.002))
    hit = scene.ray_cast(dg, o, Vector((0.0, 0.0, 1.0)), distance=60.0)
    if not hit[0]:
        idx[i] = 5
        continue
    obj = hit[4]
    d = hit[3]
    dist[i] = d
    hitname[i] = obj.name if obj else '?'
    if obj is ob:
        idx[i] = 0
    elif d < 0.02:
        idx[i] = 1
    elif d < 0.30:
        idx[i] = 2
    elif d < 2.0:
        idx[i] = 3
    else:
        idx[i] = 4

tot = ar.sum()
print('#### %s  triangles=%d  area=%.1f m2' % (NAME, nt, tot))
for tag, k in BUCKETS:
    sel = idx == k
    print('   %-8s %8.1f m2  %5.1f%%  (%d tris)' % (tag, ar[sel].sum(), 100 * ar[sel].sum() / tot, sel.sum()))

from collections import Counter
c = Counter()
for i in range(nt):
    if hitname[i] and idx[i] in (1, 2, 3, 4):
        c[hitname[i]] += ar[i]
print('#### 压在上面的东西（按面积）：')
for n, a in c.most_common(12):
    print('   %-40s %7.1f m2' % (n, a))

# ---------- render the buckets ----------
cols = {'self': (0.10, 0.10, 0.10), '<2cm': (0.90, 0.10, 0.10), '2-30cm': (0.95, 0.60, 0.10),
        '30cm-2m': (0.95, 0.90, 0.20), '>2m': (0.20, 0.45, 0.95), 'clear': (0.15, 0.75, 0.25)}
me.materials.clear()
order = [tag for tag, _k in BUCKETS]
for tag in order:
    m = bpy.data.materials.new('above_' + tag)
    m.use_nodes = True
    m.diffuse_color = cols[tag] + (1.0,)
    bs = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bs.inputs['Base Color'].default_value = cols[tag] + (1.0,)
    me.materials.append(m)
poly_idx = np.empty(len(me.polygons), np.int32)
poly_idx[:] = 5
me.polygons.foreach_get('material_index', poly_idx)
tripoly = np.empty(nt, np.int32)
me.loop_triangles.foreach_get('polygon_index', tripoly)
for tag, k in BUCKETS:
    me.polygons.foreach_set('material_index', poly_idx)   # keep
    for i in np.where(idx == k)[0]:
        poly_idx[tripoly[i]] = order.index(tag)
me.polygons.foreach_set('material_index', poly_idx)
me.update()

sc = scene
cs = [mw @ Vector(c) for c in ob.bound_box]
xs = [v.x for v in cs]
ys = [v.y for v in cs]
zs = [v.z for v in cs]
cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
span = max(max(xs) - min(xs), max(ys) - min(ys))

tmp = bpy.data.collections.new('TMP_RENDER')
sc.collection.children.link(tmp)
tmp.objects.link(ob)


def find_lc(name, lc):
    for c2 in lc.children:
        if c2.collection.name == name:
            return c2
        r = find_lc(name, c2)
        if r is not None:
            return r
    return None


find_lc('ENTITIES', bpy.context.view_layer.layer_collection).exclude = True
for nm in ('Terrain', 'Water', 'Sun'):
    o = bpy.data.objects.get(nm)
    if o:
        o.hide_render = True

cd = bpy.data.cameras.new('A_Cam')
cam = bpy.data.objects.new('A_Cam', cd)
sc.collection.objects.link(cam)
cam.location = (cx, cy, max(zs) + 150.0)
cam.rotation_euler = (0.0, 0.0, 0.0)
cd.type = 'ORTHO'
cd.ortho_scale = span * 1.1
cd.clip_start = 0.1
cd.clip_end = 20000.0
sc.camera = cam
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'FLAT'
sh.color_type = 'MATERIAL'
sh.show_shadows = False
sh.show_cavity = False
sh.show_object_outline = False
sc.render.resolution_x = 900
sc.render.resolution_y = 900
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print('#### wrote', OUT)
