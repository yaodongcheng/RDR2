# -*- coding: utf-8 -*-
"""查 continent blend 里分类集合的**挂载关系**与可见性（P0 定位用）。

要回答三个问题：
  1. `C_*` 集合是不是都挂在 `ENTITIES` 下（`cats()` 依赖这个）
  2. 有没有集合被**重复挂载**（同时挂在 ENTITIES 和 Scene Collection 上）——
     重复挂载时，关一个父级藏不住，这正是"设了隐藏却还看得见"的经典原因
  3. 有没有对象**直接挂在 ENTITIES 上**（没被 unlink 干净 → 被父集合带出来）

    blender -b <任意 continent_v*.blend> -P tools/_check_class_links.py
"""
import bpy

ent = bpy.data.collections.get('ENTITIES')
sc = bpy.context.scene.collection
print('=== 1. 集合挂载 ===')
print('ENTITIES 存在:', bool(ent), '| ENTITIES 直接挂的对象:', len(ent.objects) if ent else 'n/a')

for col in bpy.data.collections:
    if not col.name.startswith('C_') and '|' not in col.name:
        continue
    # Collection 没有 users_collection（那是 Object 的属性）。
    # `bpy_prop_collection.__contains__` 只吃**字符串**，传 Collection 对象会 TypeError
    # （2026-10-30 第二次修）—— 用 .get(name) 反查父级 + 场景根。
    parents = [p.name for p in bpy.data.collections if p.children.get(col.name) is not None]
    if bpy.context.scene.collection.children.get(col.name) is not None:
        parents.append('Scene Collection')
    print('%-30s 父级数=%d 父级=%s users=%d hide_viewport=%s' %
          (col.name, len(parents), parents or '（无，孤儿集合）', col.users, col.hide_viewport))

print('=== 2. 直接挂在 ENTITIES 上的对象（应为 0）===')
if ent:
    direct = list(ent.objects)[:10]
    print('  前 10 个:', [o.name for o in direct] or '（空，正确）')

print('=== 3. C_ 顶层集合的对象是否都在自己名下 ===')
for nm in ('C_lod_远景碎片', 'C_terrain_cell_地形块', 'C_veg_植被', 'C_stone_石块'):
    col = bpy.data.collections.get(nm)
    if not col:
        print('  找不到', nm)
        continue
    subs = [c.name for c in col.children]
    print('  %s: 子集合 %d 个（前3 %s）, all_objects=%d' %
          (nm, len(subs), subs[:3], len(col.all_objects)))

print('=== 4. 视层里这些集合是否存在 ===')
vl = bpy.context.view_layer
names = {lc.name for lc in vl.layer_collection.children}
print('  视层顶层集合:', sorted(names))
print('=== 完 ===')
