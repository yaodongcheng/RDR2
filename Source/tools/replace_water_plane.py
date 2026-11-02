# -*- coding: utf-8 -*-
"""把已有 blend 里的水面换成**两级水面**（Water_Main 40.5 m / Water_West −22 m）。

历史：
  · 原水面是 2048² 采样 → 285,550 quads / 57 万三角面 / 半透明 → 视口 overdraw 卡顿；
  · 之后改成「一张平面 40.5」 —— 但 2026-11-02 实机确认圣路易斯河瀑布两侧水位差约 62 m，
    单平面会把西边的新奥斯汀盆地整个淹掉。
  ⇒ 现在统一走 `tools/water_two_levels.py`（32 m 网格、两个对象）。

用法：blender -b <blend> -P tools/replace_water_plane.py
"""
import bpy
import os
import sys

ROOT = r'D:/BrainMaker/大镖客2解包分析'
if os.path.join(ROOT, 'tools') not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, 'tools'))

import water_two_levels as W


def main():
    mat = W.water_material()
    if mat is None:
        mat = bpy.data.materials.new('water')
        mat.use_nodes = True
    made = W.build(step=32.0, mat=mat)
    print('[water] 已替换为两级水面：%s'
          % ', '.join('%s %d 面' % (k, len(v.data.polygons)) for k, v in made.items()))
    p = bpy.data.filepath
    bpy.ops.wm.save_mainfile()
    print('[water] saved %.2f GB' % (os.path.getsize(p) / 1e9))


main()
