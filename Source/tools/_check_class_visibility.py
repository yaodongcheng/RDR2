# -*- coding: utf-8 -*-
"""查 continent blend 里各分类集合的真实可见性状态。

为什么需要：`classify_entities.py` 用 `col.hide_viewport/hide_render` 设默认隐藏，
但这是 **Collection 的全局开关**；视口里真正生效的是 **LayerCollection 的眼睛**。
两者不一致时，manifest 说"已隐藏"，打开却看得见（2026-10-30 用户现场踩到）。

    blender -b <任意 continent_v*.blend> -P tools/_check_class_visibility.py
"""
import bpy

print('=== 分类集合可见性 ===')
vl = bpy.context.view_layer
root = vl.layer_collection
lcs = {lc.name: lc for lc in root.children}


def walk(lc, depth=0):
    yield lc, depth
    for c in lc.children:
        yield from walk(c, depth + 1)


allc = {}
for lc, d in walk(root):
    allc[lc.name] = lc

for col in bpy.data.collections:
    if not col.name.startswith('C_'):
        continue
    lc = allc.get(col.name)
    n = len(col.all_objects)
    print('%-26s 对象 %6d | Collection.hide_viewport=%-5s hide_render=%-5s | LayerCollection: exclude=%-5s hide_viewport=%-5s'
          % (col.name, n, col.hide_viewport, col.hide_render,
             (lc.exclude if lc else 'n/a'), (lc.hide_viewport if lc else 'n/a')))

# 抽样看对象自身
for nm in ('C_lod_远景碎片', 'C_terrain_cell_地形块', 'C_veg_植被', 'C_stone_石块', 'C_decal_道路地面贴花'):
    col = bpy.data.collections.get(nm)
    if not col:
        print('（找不到集合 %s）' % nm)
        continue
    obs = list(col.all_objects)[:5]
    print('%s 前 5 个对象 hide_get: %s' % (nm, [o.name + '=' + str(o.hide_get()) for o in obs]))
print('=== 完 ===')
