# -*- coding: utf-8 -*-
"""How big is new_gar_rds_008, how much of it really carries a texture,
and three isolated renders so a human can look at it.

    blender -b <blend> --python tools/_unbuffer.py -P tools/_probe_rds_sizes.py

Writes D:/BrainMaker/_rds_008_tex.png  (textured)
       D:/BrainMaker/_rds_008_mat.png  (one flat colour per material slot)
       D:/BrainMaker/_rds_008_uv.png   (green=real texture, yellow=UV too small,
                                        red=UV degenerate)
"""
import bpy
import numpy as np
from mathutils import Vector

NAME = 'new_gar_rds_008'
RADIUS = 220.0

ob = bpy.data.objects.get(NAME)
me = ob.data
print('')
print('#### %s  verts=%d polys=%d loops=%d' % (NAME, len(me.vertices), len(me.polygons), len(me.loops)))

# ---------- world bbox ----------
cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
xs = [v.x for v in cs]
ys = [v.y for v in cs]
zs = [v.z for v in cs]
x0, x1, y0, y1, z0, z1 = min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
print('#### bbox  X %.1f..%.1f (%.1f m)   Y %.1f..%.1f (%.1f m)   Z %.1f..%.1f (%.1f m)'
      % (x0, x1, x1 - x0, y0, y1, y1 - y0, z0, z1, z1 - z0))
print('#### bbox footprint = %.0f m2' % ((x1 - x0) * (y1 - y0)))

# ---------- triangles ----------
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

poly_of_tri = np.empty(nt, np.int32)
me.loop_triangles.foreach_get('polygon_index', poly_of_tri)
mi = np.empty(len(me.polygons), np.int32)
me.polygons.foreach_get('material_index', mi)
tri_mat = mi[poly_of_tri]

trl = np.empty(nt * 3, np.int32)
me.loop_triangles.foreach_get('loops', trl)
uv = np.empty(len(me.loops) * 2, np.float32)
me.uv_layers.active.data.foreach_get('uv', uv)
uv = uv.reshape(-1, 2)
uvt = uv[trl.reshape(-1, 3)]
uv_ar = 0.5 * np.abs((uvt[:, 1, 0] - uvt[:, 0, 0]) * (uvt[:, 2, 1] - uvt[:, 0, 1])
                     - (uvt[:, 2, 0] - uvt[:, 0, 0]) * (uvt[:, 1, 1] - uvt[:, 0, 1]))

texels = np.zeros(nt, np.float32)
for i, m in enumerate(me.materials):
    sel = tri_mat == i
    if not sel.any() or m is None:
        continue
    w = h = 512
    for n in (m.node_tree.nodes if m.use_nodes else []):
        if n.type == 'TEX_IMAGE' and n.image and n.image.size[0]:
            w, h = n.image.size
            break
    texels[sel] = uv_ar[sel] * w * h

tot = ar.sum()
print('#### total surface area = %.1f m2   (triangles %d)' % (tot, nt))
print('')
print('%-52s %9s %9s' % ('material slot', 'area m2', 'share'))
for i, m in enumerate(me.materials):
    sel = tri_mat == i
    a = ar[sel].sum()
    print('  slot %2d %-44s %9.1f %8.1f%%' % (i, (m.name if m else '?')[:44], a, 100 * a / tot))

bad = uv_ar <= 1e-12
tiny = (~bad) & (texels < 4.0)
ok = ~bad & ~tiny
print('')
print('#### 面积按“贴图是否真的起作用”分：')
print('  正常带贴图 (>4 texel/三角) : %8.1f m2  %5.1f%%' % (ar[ok].sum(), 100 * ar[ok].sum() / tot))
print('  UV 太小 (<4 texel/三角)    : %8.1f m2  %5.1f%%' % (ar[tiny].sum(), 100 * ar[tiny].sum() / tot))
print('  UV 退化 (面积=0, 采样单点) : %8.1f m2  %5.1f%%' % (ar[bad].sum(), 100 * ar[bad].sum() / tot))
uv_span = (uvt[:, :, 0].min(), uvt[:, :, 0].max(), uvt[:, :, 1].min(), uvt[:, :, 1].max())
print('#### UV 总跨度  u %.3f..%.3f   v %.3f..%.3f' % uv_span)

# ---------- camera ----------
sc = bpy.context.scene
cam_data = bpy.data.cameras.new('SZ_Cam')
cam = bpy.data.objects.new('SZ_Cam', cam_data)
sc.collection.objects.link(cam)
cam.location = (cx, cy, z1 + 120.0)
cam.rotation_euler = (0.0, 0.0, 0.0)
cam_data.type = 'ORTHO'
cam_data.ortho_scale = max(x1 - x0, y1 - y0) * 1.1
cam_data.clip_start = 0.1
cam_data.clip_end = 20000.0
sc.camera = cam
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.resolution_x = 1200
sc.render.resolution_y = 900
sc.render.image_settings.file_format = 'PNG'
sh = sc.display.shading
sh.light = 'FLAT'
sh.show_shadows = False
sh.show_cavity = False
sh.show_object_outline = False

# hide everything else nearby (only what can enter the frame)
r2 = RADIUS * RADIUS
hidden = 0
for o in bpy.data.objects:
    if o.type != 'MESH' or o is ob:
        continue
    dx = o.location.x - cx
    dy = o.location.y - cy
    if dx * dx + dy * dy <= r2:
        o.hide_render = True
        hidden += 1
print('#### hidden neighbours: %d' % hidden)


def shot(path, color_type):
    sh.color_type = color_type
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('#### wrote', path)


shot('D:/BrainMaker/_rds_008_tex.png', 'TEXTURE')

# ---------- per-slot colour map ----------
PALETTE = [(0.90, 0.15, 0.15), (0.95, 0.55, 0.10), (0.95, 0.90, 0.20), (0.35, 0.85, 0.25),
           (0.15, 0.75, 0.75), (0.20, 0.45, 0.95), (0.65, 0.35, 0.95), (0.95, 0.35, 0.75),
           (0.55, 0.55, 0.55), (0.10, 0.10, 0.10)]
old = list(me.materials)
me.materials.clear()
for i, m in enumerate(old):
    nm = bpy.data.materials.new('slot%02d' % i)
    nm.use_nodes = True
    c = PALETTE[i % len(PALETTE)]
    nm.diffuse_color = (c[0], c[1], c[2], 1.0)
    bs = next(n for n in nm.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bs.inputs['Base Color'].default_value = (c[0], c[1], c[2], 1.0)
    me.materials.append(nm)
    print('   legend slot %2d -> rgb%s  %s' % (i, c, m.name if m else '?'))
shot('D:/BrainMaker/_rds_008_mat.png', 'MATERIAL')

# ---------- UV validity map ----------
me.materials.clear()
for nm, c in (('uv_ok', (0.15, 0.75, 0.25)), ('uv_tiny', (0.95, 0.85, 0.15)),
              ('uv_bad', (0.90, 0.10, 0.10))):
    m = bpy.data.materials.new(nm)
    m.use_nodes = True
    m.diffuse_color = (c[0], c[1], c[2], 1.0)
    bs = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bs.inputs['Base Color'].default_value = (c[0], c[1], c[2], 1.0)
    me.materials.append(m)
tripoly = np.empty(nt, np.int32)
me.loop_triangles.foreach_get('polygon_index', tripoly)
newmi = mi.copy()
# polygon -> bucket (a polygon's triangles agree, pick the worst)
poly_bucket = np.zeros(len(me.polygons), np.int8)
poly_bucket[tripoly[ok]] = 0
poly_bucket[tripoly[tiny]] = 1
poly_bucket[tripoly[bad]] = 2
me.polygons.foreach_set('material_index', poly_bucket.astype(np.int32))
me.update()
shot('D:/BrainMaker/_rds_008_uv.png', 'MATERIAL')
print('#### done')
