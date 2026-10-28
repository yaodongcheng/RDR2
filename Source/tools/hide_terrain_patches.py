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

    victims = []
    parked = []
    for o in (ents.all_objects if ents else bpy.context.scene.objects):
        n = o.name.lower()
        if '__hd_0_' in n or o.get('hide_tag') == 'terrain_cell':
            victims.append(o)
        elif o.get('hide_tag') == 'parked_offmap':
            parked.append(o)
    print('[hide] 地形 patch 命中 %d / 地图外占位盒 %d' % (len(victims), len(parked)))
    if not victims and not parked:
        return

    print('[hide] 归入 %s：%d 个（视口+渲染都关）' % (COL, _move(victims, COL)))
    print('[hide] 归入 %s：%d 个（视口+渲染都关）' % (COL_PARKED, _move(parked, COL_PARKED)))

    # 顺便抽样确认命名
    samp = [o.name for o in bpy.context.scene.objects][:8]
    print('[hide] 命名抽样:', samp)
    named = sum(1 for o in bpy.context.scene.objects if not o.name.startswith('e_'))
    print('[hide] 原名对象 %d / 全部 %d' % (named, len(bpy.context.scene.objects)))

    p = bpy.data.filepath
    bpy.ops.wm.save_mainfile()
    print('[hide] saved %.2f GB' % (os.path.getsize(p) / 1e9))


if __name__ == '__main__':
    main()
