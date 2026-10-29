# -*- coding: utf-8 -*-
"""Render the ground-covering neighbours of new_gar_rds_008 one by one, then all
together as a colour patchwork -- so a human can judge whether they tile completely.

    blender -b <blend> --python tools/_unbuffer.py -P tools/_probe_ground.py

Same camera as _rds_008_* shots (centred on new_gar_rds_008's bbox).
Writes D:/BrainMaker/_g1..g6_*.png
"""
import bpy
from mathutils import Vector

ANCHOR = 'new_gar_rds_008'
GROUPS = [
    ('g1_terrain', 'Terrain', (0.55, 0.55, 0.55)),
    ('g2_park', 'new_gar06_park_terrain', (0.15, 0.75, 0.25)),
    ('g3_tera', 'new_18_ter_a', (0.95, 0.55, 0.10)),
    ('g4_other', ('new_gar_08_ground_cur', 'new_gar_bron_ground01',
                  'new_gar_07_mansiona', 'new_gar_07_decal2'), (0.20, 0.45, 0.95)),
    ('g5_rds008', 'new_gar_rds_008', (0.90, 0.15, 0.15)),
]

anchor = bpy.data.objects.get(ANCHOR)
cs = [anchor.matrix_world @ Vector(c) for c in anchor.bound_box]
xs = [v.x for v in cs]
ys = [v.y for v in cs]
zs = [v.z for v in cs]
cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
half = max(max(xs) - min(xs), max(ys) - min(ys)) * 0.55
ZTOP = max(zs) + 120.0
print('[g] centre=(%.1f, %.1f) half=%.1f' % (cx, cy, half))


def match(o, pat):
    if isinstance(pat, (tuple, list)):
        return any(o.name == p or o.name.startswith(p) for p in pat)
    return o.name == pat or o.name.startswith(pat)


# ---- hide everything that cannot enter the frame (bbox intersect), except our groups
keep = []
for o in bpy.data.objects:
    if o.type != 'MESH':
        continue
    if any(match(o, g[1]) for g in GROUPS):
        keep.append(o)
        continue
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    if (max(v.x for v in bb) < cx - half or min(v.x for v in bb) > cx + half
            or max(v.y for v in bb) < cy - half or min(v.y for v in bb) > cy + half):
        o.hide_render = True
    else:
        o.hide_render = True        # in frame but not one of the groups -> still hidden
print('[g] kept %d objects: %s' % (len(keep), sorted({o.name for o in keep})[:12]))

# ---- camera / render
sc = bpy.context.scene
cd = bpy.data.cameras.new('G_Cam')
cam = bpy.data.objects.new('G_Cam', cd)
sc.collection.objects.link(cam)
cam.location = (cx, cy, ZTOP)
cam.rotation_euler = (0.0, 0.0, 0.0)
cd.type = 'ORTHO'
cd.ortho_scale = half * 2.0
cd.clip_start = 0.1
cd.clip_end = 20000.0
sc.camera = cam
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'FLAT'
sh.show_shadows = False
sh.show_cavity = False
sh.show_object_outline = False
sc.render.resolution_x = 900
sc.render.resolution_y = 900
sc.render.image_settings.file_format = 'PNG'


def shoot(path, color_type):
    sh.color_type = color_type
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('[g] wrote', path)


# --- individual shots, textured
for tag, pat, _col in GROUPS:
    for o in keep:
        o.hide_render = not match(o, pat)
    shoot('D:/BrainMaker/_%s_tex.png' % tag, 'TEXTURE')

# --- colour patchwork of all groups (008 included)
me_cache = {}
for tag, pat, col in GROUPS:
    for o in keep:
        if not match(o, pat):
            continue
        m = bpy.data.materials.get('grp_' + tag)
        if m is None:
            m = bpy.data.materials.new('grp_' + tag)
            m.use_nodes = True
            m.diffuse_color = (col[0], col[1], col[2], 1.0)
            bs = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
            bs.inputs['Base Color'].default_value = (col[0], col[1], col[2], 1.0)
        me_cache[o.name] = (len(o.data.materials), list(o.data.materials))
        o.data.materials.clear()
        o.data.materials.append(m)
        print('[g] %-34s -> %s rgb%s' % (o.name, tag, col))

for o in keep:
    o.hide_render = False
shoot('D:/BrainMaker/_g6_patch.png', 'MATERIAL')
print('[g] done')
