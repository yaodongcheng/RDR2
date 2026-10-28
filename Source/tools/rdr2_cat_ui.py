# -*- coding: utf-8 -*-
r"""在 Blender 右侧 N 面板加一个「RDR2 分类」页：每类一个开关 + 植被隐藏集合开关。

依赖集合树：ENTITIES/C_<key>_<中文名>/<key>|<tile>
用法：被 tools/blender_autoload.py 自动注册（打开 continent.blend 即可看到）。
手动注册：Text Editor 里跑
    import sys; sys.path.append(r"D:\BrainMaker\大镖客2解包分析\tools"); import rdr2_cat_ui as u; u.register()
"""
import bpy

ATTR = 'rdr2_cats'
_registered = {'ok': False}


def _cats():
    """返回 [(attr, key, 中文名, collection)]，按集合名解析。"""
    ent = bpy.data.collections.get('ENTITIES')
    out = []
    if ent is None:
        return out
    for c in ent.children:
        if not c.name.startswith('C_'):
            continue
        # C_<key>_<zh>
        parts = c.name.split('_', 2)
        key = parts[1] if len(parts) > 1 else c.name
        zh = parts[2] if len(parts) > 2 else key
        out.append(('cat_' + key, key, zh, c))
    return out


def _update(self, context):
    for attr, key, zh, col in _cats():
        try:
            vis = bool(getattr(self, attr))
        except Exception:
            continue
        col.hide_viewport = not vis
        col.hide_render = not vis


WATER_BASE_Z = 40.5     # 单平面的建模高度（RDR2 water.xml 真值）


def _upd_water_z(self, context):
    w = bpy.data.objects.get('Water')
    if w is None:
        return
    w.location.z = float(self.water_z) - WATER_BASE_Z


def _upd_water(self, context):
    w = bpy.data.objects.get('Water')
    if w is None:
        return
    vis = bool(self.show_water)
    w.hide_viewport = not vis
    w.hide_render = not vis


HIDDEN_VEG = 'HIDDEN_VEG'   # 植被隐藏集合（strip_vegetation --mode hide 的产物）


def _upd_veg(self, context):
    """植被开关：只改集合可见性，对象/网格一直在，属于「隐藏不删」。"""
    col = bpy.data.collections.get(HIDDEN_VEG)
    if col is None:
        return
    vis = bool(self.show_veg)
    col.hide_viewport = not vis
    col.hide_render = not vis


def register():
    if _registered['ok']:
        return
    cats = _cats()
    if not cats:
        print('[cat-ui] 没有 C_* 分类集合，先跑 tools/classify_entities.py --apply')
        return

    _w = bpy.data.objects.get('Water')
    _vg = bpy.data.collections.get(HIDDEN_VEG)
    ann = {'space_mode': bpy.props.EnumProperty(
        name='显示范围', default='all',
        items=[('all', '全图', ''), ('tile', '当前地块', '')]),
        'water_z': bpy.props.FloatProperty(
            name='水位高度', default=WATER_BASE_Z, min=-80.0, max=800.0,
            step=10, precision=1, update=_upd_water_z),
        'show_veg': bpy.props.BoolProperty(
            name='植被（隐藏集合）', default=(not _vg.hide_viewport) if _vg else False,
            update=_upd_veg),
        'show_water': bpy.props.BoolProperty(
        name='水面', default=(not _w.hide_viewport) if _w else False, update=_upd_water)}
    for attr, key, zh, col in cats:
        # 默认值 = 该集合当前是否可见（否则面板会与真实状态不一致）
        ann[attr] = bpy.props.BoolProperty(name=zh, default=not col.hide_viewport, update=_update)
    PG = type('RDR2_CatSettings', (bpy.types.PropertyGroup,), {'__annotations__': ann})
    bpy.utils.register_class(PG)
    bpy.types.Scene.rdr2_cats = bpy.props.PointerProperty(type=PG)

    class RDR2_OT_preset(bpy.types.Operator):
        bl_idname = 'rdr2.cat_preset'
        bl_label = '分类预设'
        bl_options = {'REGISTER', 'UNDO'}
        mode: bpy.props.StringProperty()

        def execute(self, context):
            s = context.scene.rdr2_cats
            cats = _cats()
            for attr, key, zh, col in cats:
                if self.mode == 'all':
                    v = True
                elif self.mode == 'none':
                    v = False
                elif self.mode == 'manmade':
                    v = key in ('bldg', 'part', 'rail', 'veh', 'prop')
                elif self.mode == 'clean':
                    v = key not in ('decal', 'junk', 'veg', 'unknown')
                else:
                    v = True
                setattr(s, attr, v)
                col.hide_viewport = not v
                col.hide_render = not v
            return {'FINISHED'}

    class RDR2_OT_sync(bpy.types.Operator):
        bl_idname = 'rdr2.cat_sync'
        bl_label = '刷新状态'
        bl_options = {'REGISTER'}

        def execute(self, context):
            n = sync()
            self.report({'INFO'}, '已同步 %d 项' % n)
            return {'FINISHED'}

    class RDR2_OT_space(bpy.types.Operator):
        bl_idname = 'rdr2.cat_space'
        bl_label = '显示范围'
        bl_options = {'REGISTER', 'UNDO'}
        mode: bpy.props.StringProperty()

        def execute(self, context):
            import blender_tour as tour
            try:
                context.scene.rdr2_cats.space_mode = self.mode
            except Exception:
                pass
            if self.mode == 'all':
                tour.follow_tile(False)
                tour.stream(False)
                tour.show_all()
            elif self.mode == 'tile':
                a = next((v for v in tour._views() if v.spaces.active.region_3d), None)
                if a is None:
                    self.report({'WARNING'}, '没有 3D 视口')
                    return {'CANCELLED'}
                from mathutils import Vector
                r = a.spaces.active.region_3d
                mat = r.view_matrix.inverted()
                cam = mat.translation.copy()
                d = (mat.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
                # 从相机沿视线打一条射线，命中什么就按它的位置算地块
                dg = context.evaluated_depsgraph_get()
                hit, loc = False, None
                try:
                    res = context.scene.ray_cast(dg, cam, d, distance=20000.0)
                    hit, loc = bool(res[0]), res[1]
                except Exception:
                    pass
                if not hit or loc is None:
                    loc = cam + d * 800.0        # 没打到东西：取视线前方 800 m
                    print('[space] 射线未命中，退化为视线前方 800 m')
                tour.follow_tile(False)
                tour.stream(False)
                tid = tour._tile_of(loc.x, loc.y)
                n = tour.only(tid)
                if n is not None and n < 0:
                    self.report({'WARNING'}, '该地块没有对象，保持当前显示')
                else:
                    self.report({'INFO'}, '已切到 %s（%d 对象）' % (tid, n))
            return {'FINISHED'}

    class RDR2_PT_cats(bpy.types.Panel):
        bl_label = 'RDR2 分类开关'
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'
        bl_category = 'RDR2'

        def draw(self, context):
            lay = self.layout
            s = getattr(context.scene, ATTR, None)
            if s is None:
                lay.label(text='未初始化')
                return
            row = lay.row(align=True)
            row.operator('rdr2.cat_preset', text='全开').mode = 'all'
            row.operator('rdr2.cat_preset', text='全关').mode = 'none'
            lay.operator('rdr2.cat_sync', text='刷新状态（手动改过 Outliner 后点我）')
            lay.separator()
            lay.label(text='显示范围（地块级）')
            row = lay.row(align=True)
            row.operator('rdr2.cat_space', text='⏹ 全图',
                         depress=(s.space_mode == 'all')).mode = 'all'
            row.operator('rdr2.cat_space', text='当前地块（手动）',
                         depress=(s.space_mode == 'tile')).mode = 'tile'
            lay.separator()
            row = lay.row(align=True)
            row.operator('rdr2.cat_preset', text='只看人造物').mode = 'manmade'
            row.operator('rdr2.cat_preset', text='去杂物/贴花').mode = 'clean'
            lay.separator()
            lay.label(text='环境')
            lay.prop(s, 'show_water', text='水面（Water）', toggle=True)
            lay.prop(s, 'water_z', text='水位高度 (m)', slider=True)
            if bpy.data.collections.get(HIDDEN_VEG) is not None:
                nv = len(bpy.data.collections[HIDDEN_VEG].all_objects)
                lay.prop(s, 'show_veg', text='植被 (%d，隐藏不删)' % nv, toggle=True)
            lay.separator()
            col = lay.column(align=True)
            for attr, key, zh, c in _cats():
                n = len(c.all_objects)
                col.prop(s, attr, text='%s  (%d)' % (zh, n), toggle=True)

    bpy.utils.register_class(RDR2_OT_preset)
    bpy.utils.register_class(RDR2_OT_sync)
    bpy.utils.register_class(RDR2_OT_space)
    bpy.utils.register_class(RDR2_PT_cats)
    # 注册后再强制对齐一次（防止 property 默认值与集合状态不符）
    sync()
    _registered['ok'] = True
    print('[cat-ui] 面板已注册：3D 视图按 N → 「RDR2」页签（%d 类）' % len(cats))


def sync():
    """把属性面板的状态与集合的真实可见性对齐（从集合 → 属性）。"""
    sc = bpy.context.scene
    pg = getattr(sc, ATTR, None)
    if pg is None:
        return 0
    n = 0
    for attr, key, zh, col in _cats():
        try:
            vis = not col.hide_viewport
            if bool(getattr(pg, attr)) != vis:
                setattr(pg, attr, vis)
                n += 1
        except Exception:
            pass
    w = bpy.data.objects.get('Water')
    if w is not None:
        try:
            vis = not w.hide_viewport
            if bool(pg.show_water) != vis:
                pg.show_water = vis
                n += 1
            z = WATER_BASE_Z + w.location.z
            if abs(float(pg.water_z) - z) > 0.05:
                pg.water_z = z
                n += 1
        except Exception:
            pass
    vg = bpy.data.collections.get(HIDDEN_VEG)
    if vg is not None:
        try:
            vis = not vg.hide_viewport
            if bool(pg.show_veg) != vis:
                pg.show_veg = vis
                n += 1
        except Exception:
            pass
    return n


def unregister():
    try:
        bpy.utils.unregister_class(bpy.types.RDR2_PT_cats)
    except Exception:
        pass
    _registered['ok'] = False
