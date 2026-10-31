# -*- coding: utf-8 -*-
"""任意区域俯视 A/B 出图（全场景 vs 隐藏地形），Workbench，秒级渲染。

用来在**不重新构建**的前提下，快速看某个坐标附近的实际情况（铁路/道路贴花在不在、有没有被地形埋掉）。

    blender -b <blend> -P tools/_unbuffer.py -P tools/_probe_area_shot.py -- \
        --x 2884 --y 1348 --w 1200 --tag ann

产物：`D:/BrainMaker/_test/ann/<tag>_full.png`（含地形）
      `D:/BrainMaker/_test/ann/<tag>_noterrain.png`（隐藏 Terrain，看几何本体）
"""
import bpy
import os
import sys
import argparse

argv = sys.argv
ARGS = argv[argv.index('--') + 1:] if '--' in argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--x', type=float, default=2884.0)
ap.add_argument('--y', type=float, default=1348.0)
ap.add_argument('--w', type=float, default=900.0)
ap.add_argument('--tag', default='ann')
ap.add_argument('--out', default=r'D:/BrainMaker/_test/ann')
ap.add_argument('--res', type=int, default=1400)
a = ap.parse_args(ARGS)
os.makedirs(a.out, exist_ok=True)

sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'STUDIO'
sh.color_type = 'TEXTURE'
sh.show_shadows = True
sh.show_cavity = True
sc.view_settings.view_transform = 'Standard'
sc.render.resolution_x = sc.render.resolution_y = a.res
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'

cam_d = bpy.data.cameras.new('area_cam')
cam_d.type = 'ORTHO'
cam_d.ortho_scale = a.w
cam_d.clip_start = 0.1
cam_d.clip_end = 20000.0
cam = bpy.data.objects.new('area_cam', cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
cam.location = (a.x, a.y, 2000.0)
cam.rotation_euler = (0.0, 0.0, 0.0)

# 只渲这一块：远处对象从渲染里摘掉（省时间）
near, far = 0, 0
r2 = (a.w * 0.9) ** 2
for ob in bpy.data.objects:
    if ob.type != 'MESH':
        continue
    dx = ob.location.x - a.x
    dy = ob.location.y - a.y
    if dx * dx + dy * dy <= r2:
        near += 1
    elif not ob.hide_render:
        ob.hide_render = True
        far += 1
print('[shot] 近处 %d 个，摘掉远处 %d 个' % (near, far))

sc.render.filepath = os.path.join(a.out, '%s_full.png' % a.tag)
bpy.ops.render.render(write_still=True)
print('[shot] 写入 %s' % sc.render.filepath)

ter = bpy.data.objects.get('Terrain')
if ter:
    ter.hide_render = True
# 2026-10-30 修：场景里的地形不是单个 `Terrain` 对象，而是 `terrain_cell` 分类集合
# （v16：30,683 个对象）。以前只找对象名，隐藏了个寂寞 —— 两张图 sha256 完全相同。
hid = 0
for c in bpy.data.collections:
    if 'terrain' in c.name.lower():
        for ob in c.all_objects:
            if not ob.hide_render:
                ob.hide_render = True
                hid += 1
print('[shot] 额外隐藏地形对象 %d 个（集合名：%s）'
      % (hid, [c.name for c in bpy.data.collections if 'terrain' in c.name.lower()]))
sc.render.filepath = os.path.join(a.out, '%s_noterrain.png' % a.tag)
bpy.ops.render.render(write_still=True)
print('[shot] 写入 %s' % sc.render.filepath)
