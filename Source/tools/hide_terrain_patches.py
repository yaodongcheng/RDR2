# -*- coding: utf-8 -*-
"""把地形 patch 网格（__hd_0_）归到独立集合并默认隐藏 —— 它们与 H4 地形完全重叠，
两套贴图叠加会画出满屏花花绿绿的格子，而且 3 万个对象会拖垮视口。

    blender -b <blend> -P tools/hide_terrain_patches.py
"""
import bpy, os

COL = 'HIDDEN_TERRAIN_CELL'


def main():
    ents = bpy.data.collections.get('ENTITIES')
    print('[hide] ENTITIES 对象', len(ents.all_objects) if ents else 0)

    victims = []
    for o in (ents.all_objects if ents else bpy.context.scene.objects):
        n = o.name.lower()
        if '__hd_0_' in n or o.get('hide_tag') == 'terrain_cell':
            victims.append(o)
    print('[hide] 地形 patch 命中 %d' % len(victims))
    if not victims:
        return

    col = bpy.data.collections.get(COL)
    if col is None:
        col = bpy.data.collections.new(COL)
        bpy.context.scene.collection.children.link(col)
    for o in victims:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)
    col.hide_viewport = True
    col.hide_render = True
    print('[hide] 已归入 %s 并关闭可见性（视口+渲染）' % COL)

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
