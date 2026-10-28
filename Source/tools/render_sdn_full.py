# -*- coding: utf-8 -*-
"""sdn_full.blend 验收渲染：全城俯视 + 桥特写 + 斜视。"""
import bpy, os
from mathutils import Vector

OUT = r'D:/BrainMaker/大镖客2解包分析/deliverable/blender/sdn_full/shots'


def setup():
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'
    sh.show_shadows = True; sh.show_cavity = True
    try:
        sc.view_settings.view_transform = 'Standard'
    except Exception:
        pass


def cam(loc, look, lens=None, ortho=None):
    c = bpy.data.cameras.new('c')
    if ortho:
        c.type = 'ORTHO'; c.ortho_scale = ortho
    else:
        c.lens = lens
    c.clip_start = 0.5; c.clip_end = 30000
    o = bpy.data.objects.new('c', c)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def render(c, w, h, p):
    sc = bpy.context.scene
    sc.camera = c
    sc.render.resolution_x = w; sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    print('SHOT ->', p)


def main():
    os.makedirs(OUT, exist_ok=True)
    setup()
    # 1 全城俯视（含桥）
    render(cam((2243, -1302, 2000), (2243, -1302, 0), ortho=1950), 2000, 1400,
           os.path.join(OUT, 'full_top_all.png'))
    # 2 桥区俯视
    render(cam((1676, -875, 1200), (1676, -875, 0), ortho=460), 1600, 1200,
           os.path.join(OUT, 'full_top_bridge.png'))
    # 3 桥斜视（从东南高处看桥跨水）
    render(cam((1880, -700, 120), (1600, -900, 45), lens=32), 1600, 900,
           os.path.join(OUT, 'full_persp_bridge.png'))
    # 4 城区斜视
    render(cam((2750, -1400, 190), (2500, -1150, 45), lens=45), 1600, 1000,
           os.path.join(OUT, 'full_persp_city.png'))


main()
