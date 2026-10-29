# -*- coding: utf-8 -*-
"""Colour patchwork with a MAGENTA background so 'no geometry' cannot be confused
with the Terrain (which is also grey)."""
import bpy
from mathutils import Vector

GROUPS = [
    ('terrain', ('Terrain',), (0.02, 0.02, 0.02)),
    ('park', ('new_gar06_park_terrain',), (0.15, 0.75, 0.25)),
    ('tera', ('new_18_ter_a_02', 'new_18_ter_a_03'), (0.95, 0.55, 0.10)),
    ('curb', ('new_gar_08_ground_cur', 'new_gar_bron_ground01'), (0.20, 0.45, 0.95)),
    ('bldg', ('new_gar_07_mansiona', 'new_gar_07_decal2'), (0.95, 0.35, 0.75)),
    ('rds', ('new_gar_rds_008',), (0.90, 0.15, 0.15)),
    ('rdsb', ('new_gar_rds_00', 'new_gar_rds_006'), (0.35, 0.85, 0.25)),
]

sc = bpy.context.scene
a = bpy.data.objects.get('new_gar_rds_008')
cs = [a.matrix_world @ Vector(c) for c in a.bound_box]
xs = [v.x for v in cs]; ys = [v.y for v in cs]; zs = [v.z for v in cs]
cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
span = max(max(xs) - min(xs), max(ys) - min(ys))

groups, used = [], set()
for tag, pats, col in GROUPS:
    objs = [o for o in bpy.data.objects
            if o.type == 'MESH' and o.name not in used
            and any(o.name == p or o.name.startswith(p) for p in pats)]
    used.update(o.name for o in objs)
    if objs:
        groups.append((tag, objs, col))

tmp = bpy.data.collections.new('TMP_RENDER')
sc.collection.children.link(tmp)
for _t, objs, _c in groups:
    for o in objs:
        tmp.objects.link(o)


def find_lc(name, lc):
    for c in lc.children:
        if c.collection.name == name:
            return c
        r = find_lc(name, c)
        if r is not None:
            return r
    return None


find_lc('ENTITIES', bpy.context.view_layer.layer_collection).exclude = True
for nm in ('Water', 'Sun'):
    o = bpy.data.objects.get(nm)
    if o:
        o.hide_render = True

for tag, objs, col in groups:
    m = bpy.data.materials.new('grp_' + tag)
    m.use_nodes = True
    m.diffuse_color = (col[0], col[1], col[2], 1.0)
    bs = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bs.inputs['Base Color'].default_value = (col[0], col[1], col[2], 1.0)
    for o in objs:
        o.data.materials.clear()
        o.data.materials.append(m)
    print('[g] %-8s %2d objs rgb%s' % (tag, len(objs), col))

cd = bpy.data.cameras.new('G_Cam')
cam = bpy.data.objects.new('G_Cam', cd)
sc.collection.objects.link(cam)
cam.location = (cx, cy, max(zs) + 150.0)
cam.rotation_euler = (0.0, 0.0, 0.0)
cd.type = 'ORTHO'; cd.ortho_scale = span * 1.1
cd.clip_start = 0.1; cd.clip_end = 20000.0
sc.camera = cam
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'FLAT'; sh.color_type = 'MATERIAL'
sh.show_shadows = False; sh.show_cavity = False; sh.show_object_outline = False
sh.background_type = 'VIEWPORT'
sh.background_color = (1.0, 0.0, 1.0)
sc.render.resolution_x = 900; sc.render.resolution_y = 900
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = 'D:/BrainMaker/_G9_patch.png'
bpy.ops.render.render(write_still=True)
print('[g] wrote D:/BrainMaker/_G9_patch.png')
