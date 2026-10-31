# -*- coding: utf-8 -*-
"""给物体加「分类」下拉框（只在 Blender 内用；改完保存 blend，离线脚本就能读到）。

    blender -b <blend> -P tools/blender_class_ui.py        # 单次注册（也可由 autoload 自动调）

- 属性：`Object.cls_ui`，EnumProperty；**默认「（未改）」**，不会把没碰过的对象算成某一类
- 面板：物体属性 →「分类（LWN）」，显示当前 `cls` / `cls_key`，下面是下拉
- 选了之后：`cls_ui_key`（字符串 key）由 update 回调写入；保存后离线读 `ob.get('cls_ui_key')`
  （`cls_ui` 本身在运行时属性里存的是枚举下标，别直接当字符串用）
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from class_rules import ALL_CLASSES
except Exception as _e:      # pragma: no cover
    print('[classui] 读 class_rules 失败:', _e)
    ALL_CLASSES = []

KEEP = '__keep__'
ITEMS = [(KEEP, '（未改）', '')] + [(k, zh, '') for k, zh in ALL_CLASSES]


def _on_update(self, context):
    """把下拉选中的 key 另存成字符串，离线脚本直接读 cls_ui_key。

    🔴 必须读 `self.cls_ui`（属性值），不能读 `self.get('cls_ui')`——
    回调里原始 ID 值还是旧的（2026-10-31 实测）。
    """
    try:
        v = self.cls_ui
    except Exception:
        v = KEEP
    self['cls_ui_key'] = v if v else KEEP


class LWN_PT_class_ui(bpy.types.Panel):
    bl_label = '分类（LWN）'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'

    def draw(self, context):
        ob = context.object
        if ob is None:
            return
        col = self.layout.column()
        col.label(text='当前：%s（%s）' % (ob.get('cls', '?'), ob.get('cls_key', '?')))
        col.prop(ob, 'cls_ui', text='改为')


def register():
    if not ITEMS:
        return
    if not hasattr(bpy.types.Object, 'cls_ui'):
        bpy.types.Object.cls_ui = bpy.props.EnumProperty(
            name='分类', items=ITEMS, default=KEEP, update=_on_update)
    if not hasattr(bpy.types, 'LWN_PT_class_ui'):
        bpy.utils.register_class(LWN_PT_class_ui)
    print('[classui] 已注册：物体属性 →「分类（LWN）」下拉（%d 类 + 未改）' % (len(ITEMS) - 1))


def unregister():
    try:
        if hasattr(bpy.types, 'LWN_PT_class_ui'):
            bpy.utils.unregister_class(LWN_PT_class_ui)
    except Exception:
        pass


if __name__ == '__main__':
    register()
