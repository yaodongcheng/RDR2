# -*- coding: utf-8 -*-
"""sdn.blend 俯视图（Workbench，快）。默认出两张：
   top_all  —— 全景，看清"原点那坨" vs 实地
   top_city —— 只框圣丹尼斯实地 x2200~2850 y-1400~-950
"""
import bpy, os, sys, math
from mathutils import Vector

ROOT = r'D:/BrainMaker/大镖客2解包分析'
OUT = os.path.join(ROOT, 'deliverable/blender/continent/shots')


def cam_ortho(cx, cy, span, res):
    c = bpy.data.cameras.new('c')
    c.type = 'ORTHO'
    c.ortho_scale = span
    c.clip_start = 1.0
    c.clip_end = 10000.0
    o = bpy.data.objects.new('c', c)
    bpy.context.scene.collection.objects.link(o)
    o.location = (cx, cy, 2000.0)
    o.rotation_euler = (0.0, 0.0, 0.0)      # 正下方看，+Y 朝上=北
    return o, res


def setup():
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'MATERIAL'
    sh.show_shadows = True
    sh.show_cavity = True
    sc.render.film_transparent = False
    try:
        sc.view_settings.view_transform = 'Standard'
    except Exception:
        pass


def render(cam, w, h, path):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('SHOT ->', path)


def main():
    os.makedirs(OUT, exist_ok=True)
    setup()
    # 全景：覆盖 x -300~2950, y -1500~200
    c1, _ = cam_ortho(1325, -650, 3400, None)
    render(c1, 2000, 1000, os.path.join(OUT, 'sdn_top_all.png'))
    # 实地城区
    c2, _ = cam_ortho(2528, -1172, 760, None)
    render(c2, 1600, 1200, os.path.join(OUT, 'sdn_top_city.png'))
    # 原点那坨特写
    c3, _ = cam_ortho(0, -20, 320, None)
    render(c3, 1200, 1200, os.path.join(OUT, 'sdn_top_origin.png'))


main()
