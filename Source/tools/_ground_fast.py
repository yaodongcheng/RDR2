# -*- coding: utf-8 -*-
"""Fast: render only the handful of ground-covering objects around new_gar_rds_008.

No per-object loop over 150k objects. Instead:
  * link the targets into a temp collection at scene root,
  * exclude the whole ENTITIES collection in ONE flag,
  * hide Terrain/Water/Sun,
  * render.

    blender -b <blend> --python tools/_unbuffer.py -P tools/_ground_fast.py
"""
import bpy
from mathutils import Vector

GROUPS = [
    ('terrain', 'Terrain', (0.55, 0.55, 0.55)),
    ('park', 'new_gar06_park_terrain', (0.15, 0.75, 0.25)),
    ('tera', ('new_18_ter_a_02', 'new_18_ter_a_03'), (0.95, 0.55, 0.10)),
    ('curb', ('new_gar_08_ground_cur', 'new_gar_bron_ground01'), (0.20, 0.45, 0.95)),
    ('bldg', ('new_gar_07_mansiona', 'new_gar_07_decal2'), (0.95, 0.35, 0.75)),
    ('rds', 'new_gar_rds_008', (0.90, 0.15, 0.15)),
    ('rdsb', ('new_gar_rds_006', 'new_gar_rds_00'), (0.35, 0.85, 0.25)),
]

sc = bpy.context.scene
anchor = bpy.data.objects.get('new_gar_rds_008')
cs = [anchor.matrix_world @ Vector(c) for c in anchor.bound_box]
xs = [v.x for v in cs]
ys = [v.y for v in cs]
zs = [v.z for v in cs]
cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
span = max(max(xs) - min(xs), max(ys) - min(ys))
print('[g] centre=(%.1f, %.1f) span=%.1f' % (cx, cy, span))


def sel(pat):
    pats = pat if isinstance(pat, (tuple, list)) else (pat,)
    return [o for o in bpy.data.objects
            if o.type == 'MESH' and any(o.name == p or o.name.startswith(p) for p in pats)]


groups = []
_used = set()
for tag, pat, col in GROUPS:
    objs = [o for o in sel(pat) if o.name not in _used]
    _used.update(o.name for o in objs)
    if objs:
        groups.append((tag, objs, col))
targets = [o for _t, objs, _c in groups for o in objs]
print('[g] targets=%d  %s' % (len(targets), [o.name for o in targets]))

tmp = bpy.data.collections.new('TMP_RENDER')
sc.collection.children.link(tmp)
for o in targets:
    tmp.objects.link(o)


def find_lc(name, lc):
    for c in lc.children:
        if c.collection.name == name:
            return c
        r = find_lc(name, c)
        if r is not None:
            return r
    return None


ent = find_lc('ENTITIES', bpy.context.view_layer.layer_collection)
if ent is not None:
    ent.exclude = True
    print('[g] ENTITIES excluded')
for nm in ('Water', 'Sun'):
    o = bpy.data.objects.get(nm)
    if o is not None:
        o.hide_render = True

cd = bpy.data.cameras.new('G_Cam')
cam = bpy.data.objects.new('G_Cam', cd)
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


def show(objs):
    s = set(o.name for o in objs)
    for o in targets:
        o.hide_render = o.name not in s


# 1) textured, everything together (what the eye would see if only these existed)
show(targets)
shoot('D:/BrainMaker/_G0_all_tex.png', 'TEXTURE')

# 2) per-group textured shots
for tag, objs, _c in groups:
    show(objs)
    shoot('D:/BrainMaker/_G_%s_tex.png' % tag, 'TEXTURE')

# 3) colour patchwork
for tag, objs, col in groups:
    m = bpy.data.materials.new('grp_' + tag)
    m.use_nodes = True
    m.diffuse_color = (col[0], col[1], col[2], 1.0)
    bs = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bs.inputs['Base Color'].default_value = (col[0], col[1], col[2], 1.0)
    for o in objs:
        o.data.materials.clear()
        o.data.materials.append(m)
    print('[g] group %-8s %-3d objs rgb%s' % (tag, len(objs), col))
show(targets)
shoot('D:/BrainMaker/_G9_patch.png', 'MATERIAL')
print('[g] done')
