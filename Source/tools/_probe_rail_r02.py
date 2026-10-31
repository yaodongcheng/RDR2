# -*- coding: utf-8 -*-
"""近景：jklm_1518b_r_02（3075,1511）——看枕木片到底渲染成什么样。

    blender -b <blend> -P tools/_unbuffer.py -P tools/_probe_rail_r02.py
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

cd = bpy.data.cameras.new('r02cam')
cam = bpy.data.objects.new('r02cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam


def shot(tag, loc, target, ortho=None, lens=60):
    cam.location = loc
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    else:
        cd.type = 'PERSP'
        cd.lens = lens
    d = mathutils.Vector(target) - cam.location
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(OUT, tag + '.png')
    bpy.ops.render.render(write_still=True)
    print('[r02] wrote', sc.render.filepath)


# 俯视 40 m（覆盖轨道 + 两侧枕木片）
shot('r02_top', (3072, 1512, 160), (3072, 1512, 0), ortho=40)
# 贴轨斜视（能看清轨间有没有一根根横木）
shot('r02_along', (3040, 1470, 62), (3090, 1540, 53), lens=45)
print('[r02] done')
