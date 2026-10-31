# -*- coding: utf-8 -*-
"""整片大陆俯视拍照（地形 + 可见网格；默认隐藏类与贴花关掉）。

    blender -b <blend> -P tools/_unbuffer.py -P tools/_probe_tile_atlas.py -- \
        [--out <png>] [--res 4096] [--texture]

产物：整图正方形俯视图（World 范围 12296×12296 m）。
本脚本只负责渲染；地块编号/网格线由 `_probe_tile_labels.py` 画。
"""
import os
import sys

import bpy

argv = sys.argv
ARGS = argv[argv.index('--') + 1:] if '--' in argv else []
OUT = r'D:/BrainMaker/大镖客2解包分析/deliverable/blender/regions_support/continent_top.png'
RES = 4096
TEXTURE = False
if '--out' in ARGS:
    OUT = ARGS[ARGS.index('--out') + 1]
if '--res' in ARGS:
    RES = int(ARGS[ARGS.index('--res') + 1])
if '--texture' in ARGS:
    TEXTURE = True
WATER_Z = None
NO_WATER = '--no-water' in ARGS
if '--water-z' in ARGS:
    WATER_Z = float(ARGS[ARGS.index('--water-z') + 1])
os.makedirs(os.path.dirname(OUT), exist_ok=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blender_tour as tour  # noqa: E402

# 启动器默认可见性 + 贴花关（与用户平时看到的一致）
tour.apply_defaults()
tour.cat_show('decal', False)
print('[top] visibility: default hidden + decal off')

# 关掉水面 / 临时改水位（只改这次渲染，不存盘）
if NO_WATER:
    w = bpy.data.objects.get('Water')
    if w is not None:
        w.hide_render = True
        w.hide_viewport = True
    print('[top] water off')
if WATER_Z is not None:
    w = bpy.data.objects.get('Water')
    if w is None:
        print('[top] WARNING: no Water object')
    else:
        z0 = min(v.co.z for v in w.data.vertices)
        w.location.z = WATER_Z - z0
        print('[top] water z -> %.2f' % WATER_Z)

sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'STUDIO'
sh.color_type = 'TEXTURE' if TEXTURE else 'MATERIAL'
sh.show_shadows = False
sh.show_cavity = False
sh.show_object_outline = False
sh.background_type = 'VIEWPORT'
sh.background_color = (0.12, 0.13, 0.14)
sc.render.resolution_x = RES
sc.render.resolution_y = RES
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = 'Standard'

# 世界范围（与 H4/manifest 一致）
X0, X1 = -7684.0, 4612.0
Y0, Y1 = -8196.0, 4100.0
cx, cy = (X0 + X1) / 2, (Y0 + Y1) / 2
span = max(X1 - X0, Y1 - Y0)

cd = bpy.data.cameras.new('topcam')
cd.type = 'ORTHO'
cd.ortho_scale = span
cd.clip_start = 0.1
cd.clip_end = 20000.0
cam = bpy.data.objects.new('topcam', cd)
sc.collection.objects.link(cam)
sc.camera = cam
cam.location = (cx, cy, 2000.0)
cam.rotation_euler = (0.0, 0.0, 0.0)

sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print('[top] wrote %s  %dx%d  span=%.0f  color=%s'
      % (OUT, RES, RES, span, sh.color_type))
