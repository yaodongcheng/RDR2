# -*- coding: utf-8 -*-
"""合成场景单元测试（不加载 7.8 GB）：只验分类集合名解析 + 可见性函数。

    blender -b --factory-startup -P tools/_check_tour_vis_unit.py
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blender_tour as tour   # noqa: E402

SPECS = [('lod', '远景碎片'), ('terrain_cell', '地形块'), ('underground', '地下停放'),
         ('watertile', '水面块'), ('placeholder', '占位代理'),
         ('veg', '植被'), ('stone', '石块'), ('prop', '道具'), ('decal', '地面贴花')]

# 合成场景必须覆盖 DEFAULT_HIDDEN 的全部类；以后加类忘了补这里，要在这里炸掉
_missing = [k for k in tour.DEFAULT_HIDDEN if k not in [x[0] for x in SPECS]]
assert not _missing, 'SPECS 缺默认隐藏类：%s（补进 SPECS 再跑）' % _missing

ent = bpy.data.collections.new('ENTITIES')
bpy.context.scene.collection.children.link(ent)
for k, zh in SPECS:
    c = bpy.data.collections.new('C_%s_%s' % (k, zh))
    ent.children.link(c)
    sub = bpy.data.collections.new('%s|wild2000_05_00' % k)
    sub['tile'] = 'wild2000_05_00'
    sub['cat'] = k
    c.children.link(sub)
    me = bpy.data.meshes.new('m_%s' % k)
    ob = bpy.data.objects.new('o_%s' % k, me)
    sub.objects.link(ob)

print('cats() ->', [(k, zh) for k, zh, c in tour.cats()])
assert ('terrain_cell' in [k for k, _, _ in tour.cats()]), 'key 解析仍然错（terrain_cell）'


def state():
    return {k: c.hide_viewport for k, zh, c in tour.cats()}


tour.show_all()
print('show_all ->', state())
assert not any(state().values()), state()

tour.apply_defaults()
s = state()
print('apply_defaults ->', s)
for k in tour.DEFAULT_HIDDEN:
    assert s[k] is True, '%s 应为隐藏：%s' % (k, s)
assert s['prop'] is False and s['decal'] is False, s

tour.cat_show('terrain_cell', True)
assert state()['terrain_cell'] is False, 'cat_show(terrain_cell) 无效'
tour.cat_show('terrain_cell', False)

tour.only('wild2000_05_00')
s = state()
print('only() ->', s)
for k in tour.DEFAULT_HIDDEN:
    assert s[k] is True, 'only() 把 %s 改成可见了：%s' % (k, s)

tour.textured = lambda *a, **k: None
tour.follow = lambda *a, **k: None
tour.full()
s = state()
print('full() ->', s)
for k in tour.DEFAULT_HIDDEN:
    assert s[k] is True, 'full() 放出了 %s：%s' % (k, s)

print('=== UNIT OK ===')
