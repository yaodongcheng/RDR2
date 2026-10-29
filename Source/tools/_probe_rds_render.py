# -*- coding: utf-8 -*-
"""One-shot A/B render: does new_gar_rds_008 cover the whole street, or only part of it?

Only objects **near** the camera are toggled (toggling 150k objects takes forever and
is pointless -- anything outside the ortho box is off-screen anyway).

    blender -b <blend> --python tools/_unbuffer.py -P tools/_probe_rds_render.py

Writes D:/BrainMaker/_rds_A.png (everything) / _rds_B.png (only new_gar_rds*)
/ _rds_C.png (only new_gar_rds_008*).
"""
import bpy
from mathutils import Vector

RADIUS = 250.0
PREFIX_ALL = 'new_gar_rds'
PREFIX_ONE = 'new_gar_rds_008'

ob = bpy.data.objects.get('new_gar_rds_008')
if ob is None:
    raise SystemExit('new_gar_rds_008 not found')

cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
xs = [v.x for v in cs]
ys = [v.y for v in cs]
zs = [v.z for v in cs]
cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
size = max(max(xs) - min(xs), max(ys) - min(ys))
print('[rds] centre=(%.1f, %.1f) size=%.1f' % (cx, cy, size))

sc = bpy.context.scene
cam_data = bpy.data.cameras.new('RDS_Cam')
cam = bpy.data.objects.new('RDS_Cam', cam_data)
sc.collection.objects.link(cam)
cam.location = (cx, cy, max(zs) + 150.0)
cam.rotation_euler = (0.0, 0.0, 0.0)          # looks down -Z
cam_data.type = 'ORTHO'
cam_data.ortho_scale = max(size * 1.6, 80.0)
cam_data.clip_start = 0.1
cam_data.clip_end = 20000.0
sc.camera = cam

sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'FLAT'
sh.color_type = 'TEXTURE'
sh.show_shadows = False
sh.show_cavity = False
sh.show_object_outline = False
sc.render.resolution_x = 1000
sc.render.resolution_y = 750
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'
sc.render.film_transparent = False

r2 = RADIUS * RADIUS
near = []
for o in bpy.data.objects:
    if o.type != 'MESH':
        continue
    dx = o.location.x - cx
    dy = o.location.y - cy
    if dx * dx + dy * dy <= r2:
        near.append(o)
print('[rds] nearby meshes to toggle: %d (of %d)' % (len(near), len(bpy.data.objects)))


def shoot(prefix, path, toggle):
    n = 0
    if toggle:
        for o in near:
            want = o.name.startswith(prefix) if prefix else True
            o.hide_render = not want
            n += want
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('[rds] wrote %s  (%d shown)' % (path, n))


shoot('', 'D:/BrainMaker/_rds_A.png', False)
shoot(PREFIX_ALL, 'D:/BrainMaker/_rds_B.png', True)
shoot(PREFIX_ONE, 'D:/BrainMaker/_rds_C.png', True)
print('[rds] done')
