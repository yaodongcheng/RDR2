# -*- coding: utf-8 -*-
"""把地形 patch 网格（__hd_0_）归到独立集合并默认隐藏 —— 它们与 H4 地形完全重叠，
两套贴图叠加会画出满屏花花绿绿的格子，而且 3 万个对象会拖垮视口。

2026-10-29 追加：`hide_tag == 'parked_offmap'` 的物件（RDR2 关卡设计师放在
z ≈ −1002 m 的 `tempbox` 占位盒）归到 `HIDDEN_PARKED`。它们本来就在地图外 1 km，
显示出来只会在视口里变成远处几个灰盒子（TODO #9）。

    blender -b <blend> -P tools/hide_terrain_patches.py
"""
import bpy
import os

COL = 'HIDDEN_TERRAIN_CELL'
COL_PARKED = 'HIDDEN_PARKED'


def _move(objs, colname):
    """把 objs 挪进 colname 集合并关可见性；返回移动数。"""
    if not objs:
        return 0
    col = bpy.data.collections.get(colname)
    if col is None:
        col = bpy.data.collections.new(colname)
        bpy.context.scene.collection.children.link(col)
    for o in objs:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)
    col.hide_viewport = True
    col.hide_render = True
    return len(objs)


def main():
    ents = bpy.data.collections.get('ENTITIES')
    print('[hide] ENTITIES 对象', len(ents.all_objects) if ents else 0)

    # 2026-10-29 规范：地形块已经是分类里的一类（C_terrain_cell_地形块），
    # 隐藏 = 给这个类设"默认不显示"，**不搬对象**。
    cols = [c for c in ents.children if c.name.startswith('C_terrain_cell_')] if ents else []
    if cols and all(c.hide_viewport for c in cols):
        print('[hide] 地形块已经是隐藏状态，跳过（省一次 7 GB 存盘）')
        return
    n = 0
    for c in cols:
        c.hide_viewport = True
        c.hide_render = True
        n += len(c.all_objects)
    if cols:
        print('[hide] 「地形块」%d 个 → 整类默认隐藏（仍在类里）' % n)
    else:
        print('[hide] 没找到 C_terrain_cell_* —— 先跑 classify_entities.py --apply')

    # 地图外占位盒（z ≈ −1002 m 的 tempbox）：TODO #9 里就 2 个，单独关掉这两个对象即可，
    # 不值得为它们开一个类/垃圾桶。
    parked = [o for o in (ents.all_objects if ents else []) if o.get('hide_tag') == 'parked_offmap']
    for o in parked:
        o.hide_viewport = True
        o.hide_render = True
    if parked:
        print('[hide] 地图外占位盒 %d 个 → 单独关闭（%s）'
              % (len(parked), ', '.join(o.name for o in parked[:4])))

    p = bpy.data.filepath
    bpy.ops.wm.save_mainfile()
    print('[hide] saved %.2f GB' % (os.path.getsize(p) / 1e9))


if __name__ == '__main__':
    main()
