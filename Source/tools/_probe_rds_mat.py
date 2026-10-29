# -*- coding: utf-8 -*-
"""Per-material-slot colour map of new_gar_rds_008 (index-preserving)."""
import bpy
import numpy as np
from mathutils import Vector

NAME = 'new_gar_rds_008'
RADIUS = 220.0
PALETTE = [(0.90, 0.15, 0.15), (0.95, 0.55, 0.10), (0.95, 0.90, 0.20), (0.35, 0.85, 0.25),
           (0.15, 0.75, 0.75), (0.20, 0.45, 0.95), (0.65, 0.35, 0.95), (0.95, 0.35, 0.75),
           (0.95, 0.95, 0.95), (0.05, 0.05, 0.05)]

ob = bpy.data.objects.get(NAME)
me = ob.data
mi = np.empty(len(me.polygons), np.int32)
me.polygons.foreach_get('material_index', mi)

cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
xs = [v.x for v in cs]; ys = [v.y for v in cs]; zs = [v.z for v in cs]
cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2

# hide neighbours first (before we touch materials)
r2 = RADIUS * RADIUS
for o in bpy.data.objects:
    if o.type != 'MESH' or o is ob:
        continue
    dx = o.location.x - cx; dy = o.location.y - cy
    if dx * dx + dy * dy <= r2:
        o.hide_render = True

old = [m.name if m else '?' for m in me.materials]
me.materials.clear()
for i, nm in enumerate(old):
    m = bpy.data.materials.new('slot%02d' % i)
    m.use_nodes = True
    c = PALETTE[i % len(PALETTE)]
    m.diffuse_color = (c[0], c[1], c[2], 1.0)
    bs = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bs.inputs['Base Color'].default_value = (c[0], c[1], c[2], 1.0)
    me.materials.append(m)
    print('   slot %2d rgb%s = %s' % (i, c, nm))
me.polygons.foreach_set('material_index', mi)      # <-- restore (clear() clamps to 0)
me.update()

sc = bpy.context.scene
cd = bpy.data.cameras.new('M_Cam')
cam = bpy.data.objects.new('M_Cam', cd)
sc.collection.objects.link(cam)
cam.location = (cx, cy, max(zs) + 120.0)
cam.rotation_euler = (0.0, 0.0, 0.0)
cd.type = 'ORTHO'
cd.ortho_scale = max(max(xs) - min(xs), max(ys) - min(ys)) * 1.1
cd.clip_start = 0.1
cd.clip_end = 20000.0
sc.camera = cam
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'FLAT'; sh.color_type = 'MATERIAL'
sh.show_shadows = False; sh.show_cavity = False; sh.show_object_outline = False
sc.render.resolution_x = 1200; sc.render.resolution_y = 900
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = 'D:/BrainMaker/_rds_008_mat.png'
bpy.ops.render.render(write_still=True)
print('#### wrote D:/BrainMaker/_rds_008_mat.png')
