# -*- coding: utf-8 -*-
"""行为检查（真 blend）：show_all / apply_defaults / cat_show / only / full
的可见性行为对不对（不存盘）。与 `_check_class_visibility.py`（只查存盘态）互补。

    blender -b <blend> -P tools/_unbuffer.py -P tools/_check_tour_behavior.py
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blender_tour as tour   # noqa: E402


def dump(tag):
    print('--- %s' % tag)
    for k, zh, c in tour.cats():
        lc = tour._layer_col(c.name)
        print('   %-12s %-6s data=%-5s eye=%-5s' %
              (k, zh, c.hide_viewport, lc.hide_viewport if lc else 'n/a'))


dump('AS SAVED')
tour.show_all()
dump('AFTER show_all（期望：全部 False）')
tour.apply_defaults()
dump('AFTER apply_defaults（期望：lod/terrain_cell/veg/stone=True）')

tour.cat_show('terrain_cell', True)
lc = tour._layer_col('C_terrain_cell_地形块')
print('cat_show(terrain_cell, True) -> eye=%s data=%s'
      % (lc.hide_viewport, bpy.data.collections['C_terrain_cell_地形块'].hide_viewport))
tour.cat_show('terrain_cell', False)

tour.only('wild2000_05_00')
print('--- only() 之后，默认隐藏类应为 True（不被改成可见）')
for k, zh, c in tour.cats():
    if k in tour.DEFAULT_HIDDEN:
        print('   %-12s data=%-5s' % (k, c.hide_viewport))

# full() 会调 textured()（缩 8k 张贴图，很慢）和 follow()（注册持久 timer，
# 后台模式下会让进程永不退出）。这里换成空实现，只验 full() 的隐藏逻辑。
tour.textured = lambda *a, **k: None
tour.follow = lambda *a, **k: None
tour.full()
print('--- full() 之后（默认隐藏类应仍为 True）')
for k, zh, c in tour.cats():
    lc = tour._layer_col(c.name)
    print('   %-12s data=%-5s eye=%-5s' % (k, c.hide_viewport, lc.hide_viewport if lc else 'n/a'))
print('=== 完（未存盘）===')
