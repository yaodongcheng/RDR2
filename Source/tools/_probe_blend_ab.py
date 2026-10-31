# -*- coding: utf-8 -*-
"""任意两个 blend 同机位 A/B 对照渲染（默认 v22 / v23）：
启动器同款可见性下的近景 + "只留 rail 类"的骨架图。

    blender -b --factory-startup -P tools/_probe_blend_ab.py -- \
        [--a <blendA>] [--b <blendB>] [--out <dir>]
"""
import argparse
import os
import sys

import bpy
import mathutils

OUT = r'D:/BrainMaker/_railcheck'
_argv = sys.argv
_ARGS = _argv[_argv.index('--') + 1:] if '--' in _argv else []
_ap = argparse.ArgumentParser()
_ap.add_argument('--a', default=r'D:/BrainMaker/大镖客2解包分析/deliverable/blender/continent/continent_v22.blend')
_ap.add_argument('--b', default=r'D:/BrainMaker/大镖客2解包分析/deliverable/blender/continent/continent_v23.blend')
_ap.add_argument('--out', default=OUT)
_a = _ap.parse_args(_ARGS)
OUT = _a.out
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BLENDS = [(os.path.basename(p).replace('continent_', '').replace('.blend', ''), p)
          for p in (_a.a, _a.b)]


def prep():
    import blender_tour as tour
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
    sc.render.resolution_y = 900
    sc.view_settings.view_transform = 'Standard'
    cam_data = bpy.data.cameras.new('abcam')
    cam = bpy.data.objects.new('abcam', cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return tour, sc, cam, cam_data


def shot(sc, cam, cam_data, tag, loc, target, ortho):
    cam.location = loc
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = ortho
    d = mathutils.Vector(target) - cam.location
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(OUT, tag + '.png')
    bpy.ops.render.render(write_still=True)
    print('[ab] wrote', sc.render.filepath)


for ver, path in BLENDS:
    bpy.ops.wm.open_mainfile(filepath=path)
    tour, sc, cam, cam_data = prep()
    # A. 启动器可见性下的近景
    shot(sc, cam, cam_data, 'ab_%s_normal' % ver, (2872, 1205, 140), (2872, 1205, 0), 90)
    # B. 只留 rail 类（其余类全关）—— 看轨道骨架连不连
    for k, zh, c in tour.cats():
        c.hide_viewport = (k != 'rail')
        c.hide_render = (k != 'rail')
        lc = tour._layer_col(c.name)
        if lc is not None:
            lc.hide_viewport = (k != 'rail')
    shot(sc, cam, cam_data, 'ab_%s_railonly' % ver, (2880, 1270, 400), (2880, 1270, 0), 300)
    print('[ab] %s done' % ver)

print('[ab] all done')
