# -*- coding: utf-8 -*-
"""近景验收：轨面 + 枕木（启动器同款可见性）。

    blender -b <blend> -P tools/_unbuffer.py -P tools/_probe_rail_close.py
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
sc.render.resolution_x = 1100
sc.render.resolution_y = 900
sc.view_settings.view_transform = 'Standard'

cam_data = bpy.data.cameras.new('vcam2')
cam = bpy.data.objects.new('vcam2', cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


def shot(tag, loc, target, ortho=None, lens=50):
    cam.location = loc
    if ortho:
        cam_data.type = 'ORTHO'
        cam_data.ortho_scale = ortho
    else:
        cam_data.type = 'PERSP'
        cam_data.lens = lens
    d = mathutils.Vector(target) - cam.location
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(OUT, tag + '.png')
    bpy.ops.render.render(write_still=True)
    print('[rv2] wrote', sc.render.filepath)


# 断口正上方（rails_106 北端 2880,1200）
shot('close_top', (2872, 1200, 120), (2872, 1200, 0), ortho=60)
# 贴着轨道往北看
shot('close_along', (2850, 1160, 50), (2895, 1260, 44), lens=60)
# 站场/岔区
shot('close_yard', (2890, 1300, 110), (2890, 1300, 0), ortho=90)
print('[rv2] done')
