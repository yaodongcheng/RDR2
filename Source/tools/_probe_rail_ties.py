# -*- coding: utf-8 -*-
"""近景：枕木到底有没有（选两处：有 dec 片的 / 没片的）。

    blender -b <blend> -P tools/_unbuffer.py -P tools/_probe_rail_ties.py
"""
import os
import sys

import bpy
import mathutils

OUT = r'D:/BrainMaker/_railcheck'
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blender_tour as tour   # noqa: E402

tour.apply_defaults()
for k in ('decal', 'underground', 'watertile', 'placeholder'):
    tour.cat_show(k, False)

sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'STUDIO'
sh.color_type = 'TEXTURE'
sh.show_shadows = False
sh.show_cavity = True
sc.render.resolution_x = 1000
sc.render.resolution_y = 1000
sc.view_settings.view_transform = 'Standard'

cd = bpy.data.cameras.new('cc')
cam = bpy.data.objects.new('cc', cd)
sc.collection.objects.link(cam)
sc.camera = cam


def shot(tag, loc, target, ortho):
    cam.location = loc
    cd.type = 'ORTHO'
    cd.ortho_scale = ortho
    d = mathutils.Vector(target) - cam.location
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(OUT, tag + '.png')
    bpy.ops.render.render(write_still=True)
    print('[rc] wrote', sc.render.filepath)


# A：有 dec 片的位置（j_1518_r_a_dec_01 在 2856,1171）
shot('tie_A_with_dec', (2856, 1171, 140), (2856, 1171, 0), 26)
# B：没 dec 片的位置（主线中段，2890,1290 附近）
shot('tie_B_no_dec', (2890, 1290, 160), (2890, 1290, 0), 26)
print('[rc] done')
