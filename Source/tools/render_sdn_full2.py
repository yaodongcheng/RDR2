# -*- coding: utf-8 -*-
"""sdn_full2 验收：两条铁路线 + 桥。"""
import bpy, os
from mathutils import Vector
OUT = r'D:/BrainMaker/大镖客2解包分析/deliverable/blender/sdn_full2/shots'


def setup():
    sc = bpy.context.scene
    for e in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
        try:
            sc.render.engine = e; break
        except Exception:
            pass
    try: sc.eevee.taa_render_samples = 24
    except Exception: pass
    try:
        sc.view_settings.view_transform = 'Filmic'
        sc.view_settings.exposure = -0.8
    except Exception: pass
    l = bpy.data.lights.new('sun', 'SUN'); l.energy = 3.0
    o = bpy.data.objects.new('sun', l); sc.collection.objects.link(o)
    o.rotation_euler = (0.85, 0.25, 2.4)
    w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
    for n in w.node_tree.nodes:
        if n.type == 'BACKGROUND':
            n.inputs[0].default_value = (0.66, 0.72, 0.80, 1)
            n.inputs[1].default_value = 1.0


def cam(loc, look, lens=None, ortho=None):
    c = bpy.data.cameras.new('c')
    if ortho:
        c.type = 'ORTHO'; c.ortho_scale = ortho
    else:
        c.lens = lens
    c.clip_start = 0.3; c.clip_end = 30000
    o = bpy.data.objects.new('c', c)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def render(c, w_, h_, p):
    sc = bpy.context.scene
    sc.camera = c
    sc.render.resolution_x = w_; sc.render.resolution_y = h_
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    print('SHOT', p)


def main():
    os.makedirs(OUT, exist_ok=True)
    setup()
    # 1 全景俯视：两条铁路线都在
    render(cam((1900, -1210, 3000), (1900, -1210, 0), ortho=2700), 2000, 1400,
           os.path.join(OUT, 'all_top.png'))
    # 2 r_a 线 俯视
    render(cam((860, -760, 1500), (860, -760, 0), ortho=520), 1600, 1200,
           os.path.join(OUT, 'ra_top.png'))
    # 3 r_a 线 侧视（看它那座桥）
    render(cam((1120, -560, 110), (860, -820, 66), lens=32), 1600, 900,
           os.path.join(OUT, 'ra_side.png'))
    # 4 主桥（对照）
    render(cam((1600, -900, 46), (1510, -745, 52), lens=24), 1600, 900,
           os.path.join(OUT, 'main_bridge.png'))


main()
