# -*- coding: utf-8 -*-
"""视觉验收：用「启动器同款可见性」渲安尼斯堡一带的铁路，看轨道是否连续、枕木在不在。

    blender -b <blend> -P tools/_unbuffer.py -P tools/_probe_rail_wide.py

产物：D:/BrainMaker/_railcheck/<tag>_top.png / _oblique.png / _wide.png
"""
import os
import sys

import bpy
import mathutils

OUT = r'D:/BrainMaker/_railcheck'
os.makedirs(OUT, exist_ok=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blender_tour as tour   # noqa: E402

# 1) 复刻启动器默认可见性：默认隐藏类全关 + 贴花关
tour.apply_defaults()
tour.cat_show('decal', False)
tour.cat_show('underground', False)
tour.cat_show('watertile', False)
tour.cat_show('placeholder', False)
print('[rv] 可见性已按启动器设置')

# 2) Workbench 贴图着色
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'STUDIO'
sh.color_type = 'TEXTURE'
sh.show_shadows = False
sh.show_cavity = True
sc.render.resolution_x = 1000
sc.render.resolution_y = 900
sc.render.film_transparent = False
sc.view_settings.view_transform = 'Standard'

cam_data = bpy.data.cameras.new('vcam')
cam = bpy.data.objects.new('vcam', cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


def look_at(target):
    d = mathutils.Vector(target) - cam.location
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def shot(tag, loc, target, ortho=None):
    cam.location = loc
    if ortho:
        cam_data.type = 'ORTHO'
        cam_data.ortho_scale = ortho
    else:
        cam_data.type = 'PERSP'
        cam_data.lens = 50
    look_at(target)
    sc.render.filepath = os.path.join(OUT, tag + '.png')
    bpy.ops.render.render(write_still=True)
    print('[rv] wrote', sc.render.filepath)


# 断口在 (2868,1192) 一带，往北到站场 y≈1340
shot('top', (2880, 1230, 500), (2880, 1230, 0), ortho=320)
shot('oblique', (2810, 1080, 95), (2895, 1245, 45))
shot('wide', (2880, 1280, 700), (2880, 1280, 0), ortho=560)
print('[rv] done')
