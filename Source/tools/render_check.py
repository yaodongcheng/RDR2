# -*- coding: utf-8 -*-
"""给 continent blend 渲几张俯视检查图（不依赖人开 GUI）。

为什么用 Workbench：147k 对象、6.8 GB 场景，用 Cycles 渲一张要几分钟到几十分钟；
Workbench 的 TEXTURE 颜色模式直接显示材质贴图，几秒出图，足够判断"贴图对不对/黑不黑"。

    blender -b <blend> --python tools/render_check.py -- --out work/verify --tag v8

产物：<out>/<tag>_park.png（公园）、<tag>_city.png（圣丹尼斯中心）、<tag>_wide.png（宽景）
"""
import bpy
import os
import sys
import math
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'

SHOTS = {
    # 名字: (中心 x, 中心 y, 正交宽度 m, 分辨率)
    'park': (2470.0, -1200.0, 420.0, (760, 760)),
    'city': (2560.0, -1450.0, 900.0, (900, 900)),
    'wide': (2400.0, -1200.0, 2600.0, (1100, 1100)),
}


def argv():
  a = sys.argv
  return a[a.index('--') + 1:] if '--' in a else []


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument('--out', default=os.path.join(ROOT, 'work/verify'))
  ap.add_argument('--tag', default='shot')
  ap.add_argument('--only', default='')
  a = ap.parse_args(argv())
  os.makedirs(a.out, exist_ok=True)

  sc = bpy.context.scene
  sc.render.engine = 'BLENDER_WORKBENCH'
  sh = sc.display.shading
  sh.light = 'STUDIO'
  sh.color_type = 'TEXTURE'
  sh.show_shadows = False
  sh.show_cavity = False
  sc.render.film_transparent = False
  sc.view_settings.view_transform = 'Standard'

  cam_data = bpy.data.cameras.new('shot_cam')
  cam_data.type = 'ORTHO'
  cam = bpy.data.objects.new('shot_cam', cam_data)
  sc.collection.objects.link(cam)
  sc.camera = cam

  # 世界光源（Workbench 不吃灯，但保留不影响）
  for name, (cx, cy, width, res) in SHOTS.items():
    if a.only and a.only != name:
      continue
    cam_data.ortho_scale = width
    cam.location = (cx, cy, 900.0)
    cam.rotation_euler = (0.0, 0.0, 0.0)     # 俯视：相机 -Z 朝下
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = os.path.join(a.out, '%s_%s.png' % (a.tag, name))
    print('[shot] 渲染 %s → %s' % (name, sc.render.filepath))
    bpy.ops.render.render(write_still=True)
    print('[shot] 完成 %s' % name)


if __name__ == '__main__':
  main()
