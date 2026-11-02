# -*- coding: utf-8 -*-
"""用 `export/world/water_level_map_2lv.npy` 重建**两级**水面（Water_Main / Water_West）。在 Blender 里跑。

🔴 2026-11-02 起改为直接调用 `tools/water_two_levels.py`：
   圣路易斯河瀑布两侧水位差约 62 m，单级水面会把西边的新奥斯汀盆地淹掉。
   旧行为（读单级 `water_level_map.npy`、8 m 网格、一个 `Water` 对象）已废弃。
"""
import bpy
import os
import sys

ROOT = r'D:/BrainMaker/大镖客2解包分析'
if os.path.join(ROOT, 'tools') not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, 'tools'))

import water_two_levels as W

if __name__ == '__main__':
    made = W.build(step=32.0, mat=W.water_material())
    print('[W] %s' % ', '.join('%s %d 面' % (k, len(v.data.polygons)) for k, v in made.items()))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'deliverable/blender/continent/continent.blend'))
    print('[W] saved')
