# -*- coding: utf-8 -*-
"""Blender 分区流式加载（按摄像机距离显隐分块）。

用法：
  1. 在 Blender 里打开 sdn.blend
  2. 顶部切到 Scripting 工作区 → 选中左侧文本块 zone_stream.py → 点 ▶ Run Script（Alt+P）
  3. 按 N 打开侧栏 → 「分块加载」面板 → 勾选 Enable，调半径（默认 350 m）
  4. 播放/漫游时，只有摄像机附近的块会显示，远处的自动隐藏（数据仍在内存，但不再绘制）

说明：Blender 没有真正的"卸载"，这里做的是 **视口/渲染可见性剔除**，
能大幅降低绘制调用和显存压力；内存占用不变。
"""
import bpy
import math
from mathutils import Vector

TILE_PREFIX = "TILE_"
DEFAULT_RADIUS = 350.0


def _root_of(o):
    r = o
    while r.parent:
        r = r.parent
    return r


def build_collections():
    """把每个 glTF 分块（根 Empty 及其子物体）收进独立 Collection。"""
    # 已有分块集合就跳过
    if any(c.name.startswith(TILE_PREFIX) for c in bpy.data.collections):
        return
    roots = {}
    for o in bpy.data.objects:
        if o.type == 'EMPTY' and o.parent is None:
            roots[o.name] = []
    for o in bpy.data.objects:
        if o.parent is None and o.type != 'EMPTY':
            continue
        r = _root_of(o)
        if r.name in roots:
            roots[r.name].append(o)
    n = 0
    for rname, objs in roots.items():
        if not objs:
            continue
        col = bpy.data.collections.new(TILE_PREFIX + rname)
        bpy.context.scene.collection.children.link(col)
        for o in objs:
            # 从原集合移除
            for c in list(o.users_collection):
                try:
                    c.objects.unlink(o)
                except Exception:
                    pass
            col.objects.link(o)
        n += 1
    print("built tile collections:", n)


def tile_centers():
    out = {}
    for c in bpy.data.collections:
        if not c.name.startswith(TILE_PREFIX):
            continue
        vs = [o.matrix_world.translation for o in c.objects if o.type == 'MESH']
        if not vs:
            continue
        x = sum(v.x for v in vs) / len(vs)
        y = sum(v.y for v in vs) / len(vs)
        z = sum(v.z for v in vs) / len(vs)
        out[c.name] = Vector((x, y, z))
    return out


def _cam_pos():
    for area in bpy.context.screen.areas if bpy.context.screen else []:
        if area.type == 'VIEW_3D':
            sp = area.spaces.active
            r3d = sp.region_3d
            if r3d:
                return r3d.view_location.copy(), r3d.view_distance
    try:
        cam = bpy.context.scene.camera
        if cam:
            return cam.matrix_world.translation.copy(), 0.0
    except Exception:
        pass
    return None, 0.0


_state = {"enable": True, "radius": DEFAULT_RADIUS, "centers": {}}


def _tick():
    if not _state["enable"]:
        return 0.4
    pos, dist = _cam_pos()
    if pos is None:
        return 0.4
    r = _state["radius"] + dist * 0.6
    centers = _state["centers"]
    for name, c in centers.items():
        col = bpy.data.collections.get(name)
        if not col:
            continue
        vis = (c - pos).length <= r
        # 只影响视口；渲染时默认全开（避免出图缺块）
        if col.hide_viewport != (not vis):
            col.hide_viewport = not vis
    return 0.35


class ZONE_OT_build(bpy.types.Operator):
    bl_idname = "zone.build"
    bl_label = "重建分块集合"
    def execute(self, context):
        build_collections()
        _state["centers"] = tile_centers()
        self.report({'INFO'}, "分块 %d 个" % len(_state["centers"]))
        return {'FINISHED'}


class ZONE_OT_toggle(bpy.types.Operator):
    bl_idname = "zone.toggle"
    bl_label = "开/关分块加载"
    def execute(self, context):
        _state["enable"] = not _state["enable"]
        if not _state["enable"]:
            for c in bpy.data.collections:
                if c.name.startswith(TILE_PREFIX):
                    c.hide_viewport = False
                    c.hide_render = False
        self.report({'INFO'}, "分块加载 " + ("开" if _state["enable"] else "关"))
        return {'FINISHED'}


class ZONE_PT_panel(bpy.types.Panel):
    bl_label = "分块加载（按距离）"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "分块加载"
    def draw(self, context):
        l = self.layout
        l.prop(context.scene, "zone_radius", text="半径 (m)")
        l.label(text="只影响视口，不影响渲染")
        l.operator("zone.toggle", text=("关闭" if _state["enable"] else "开启"))
        l.operator("zone.build", text="重建分块集合")
        l.label(text="块数: %d" % len(_state["centers"]))
        l.label(text="提示: 远块隐藏后，视口会明显变快")


def register():
    bpy.types.Scene.zone_radius = bpy.props.FloatProperty(
        name="Radius", default=DEFAULT_RADIUS, min=50, max=3000, step=50,
        update=lambda s, c: _state.__setitem__("radius", s.zone_radius))
    bpy.utils.register_class(ZONE_OT_build)
    bpy.utils.register_class(ZONE_OT_toggle)
    bpy.utils.register_class(ZONE_PT_panel)
    build_collections()
    _state["centers"] = tile_centers()
    _state["radius"] = bpy.context.scene.zone_radius
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, persistent=True)
    print("zone_stream registered, tiles:", len(_state["centers"]))


def unregister():
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    for c in (ZONE_PT_panel, ZONE_OT_toggle, ZONE_OT_build):
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            pass


if __name__ == "__main__":
    register()
