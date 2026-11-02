# -*- coding: utf-8 -*-
"""两级水面：在 blend 里建 **Water_Main / Water_West / Water_Alpine** 三个对象。

每一级的水位都是**可调旋钮**（和旧版 `make_water_dynamic()` 同一套做法）：
    选中 Water_Main（或 Water_West）→ 物体属性 → 自定义属性 `water_level`
    改数值，水面**立刻**升降（网格顶点 z=0，对象整体按 `water_level` 移动）。
    默认：Water_Main **40.5 m** / Water_West **−22 m**。
Water_Alpine 是高山小湖（58~243 m），各湖保留自己的水位，不跟旋钮联动。

为什么要两级（2026-11-02 用户实机确认）
    圣路易斯河（瀑布以西，新奥斯汀盆地）水面比主水系（平铁湖 / 海岸）低约 62 m，
    实机里就是那道瀑布。原来的「一个平面 40.5」会把西盆地整个淹掉。

水位来源：`export/world/water_level_map_2lv.npy`（2048²，行 0=南，NaN=陆地）
    · 主水系 40.5 m（`water.xml` 真值）
    · 西盆地 −22 m（岸线中位 −16.8，按主水系「岸线 45.5→水面 40.5」同样扣 5 m）
    · 高山小湖各自保留岸线中位高度（58~243 m），否则会被压到 40.5 埋掉
    ⚠️ 这几个数是**初值**，准不准以实机为准 —— 直接用旋钮调。

为什么默认 32 m 网格
    2026-10-28 用户否掉了 8 m / 28.5 万四边形 + 半透明的版本（视口 overdraw 卡顿）。
    32 m 约 1 万四边形，形状仍可辨认，视口不卡。

用法（Blender 里跑）：
    blender -b <blend> -P tools/water_two_levels.py
    blender -b <blend> -P tools/water_two_levels.py -- --save-as <out.blend> --step 32
不带 --save-as 就原地保存。
"""
import os
import sys

import bpy
import numpy as np

ROOT = r'D:/BrainMaker/大镖客2解包分析'
LVP = os.path.join(ROOT, 'export/world/water_level_map_2lv.npy')
LVP_OLD = os.path.join(ROOT, 'export/world/water_level_map.npy')
X0, Y0, WORLD = -7684.0, -8196.0, 12296.0
P = 2048
RES = WORLD / P
SPLIT = 5.0                 # 低于这个高度算「西盆地」
MAIN_M, WEST_M = 40.5, -22.0
NAMES = ('Water_Main', 'Water_West')


# ------------------------------------------------------------------ 公共小工具
def water_objects():
    """所有水面网格对象：旧版单对象 `Water` + 新版 `Water_Main` / `Water_West`。"""
    out = []
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        if o.name == 'Water' or o.name.startswith('Water_'):
            out.append(o)
    return out


def water_material():
    for o in water_objects():
        if o.data and o.data.materials:
            return o.data.materials[0]
    for nm in ('water', 'Water'):
        m = bpy.data.materials.get(nm)
        if m:
            return m
    return None


def remove_water():
    for o in water_objects():
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if me and me.users == 0:
            bpy.data.meshes.remove(me)


# ------------------------------------------------------------------ 建网格
def _mesh(name, co, quads, mat):
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.get(name)
    if me:
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co))
    me.vertices.foreach_set('co', co.ravel())
    me.loops.add(quads.size)
    me.loops.foreach_set('vertex_index', quads.ravel())
    me.polygons.add(len(quads))
    me.polygons.foreach_set('loop_start', np.arange(0, quads.size, 4, dtype=np.int32))
    me.update()
    if mat:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def add_level_knob(ob, level, lo, hi, soft_lo, soft_hi, desc):
    """给水面挂「水面高度」旋钮：自定义属性 `water_level` + 驱动器 → location.z。

    和旧版 `blender_rebuild_ground.make_water_dynamic()` 同一套做法：
    网格顶点 z=0，对象整体按 `water_level` 上下移动 ⇒ 在 N 面板改数值，水面立刻升降。
    """
    ob['water_level'] = float(level)
    try:
        ob.id_properties_ui('water_level').update(
            min=float(lo), max=float(hi), soft_min=float(soft_lo), soft_max=float(soft_hi),
            description=desc)
    except Exception:
        pass
    ob.location = (0.0, 0.0, float(level))
    fc = ob.driver_add('location', 2)
    drv = fc.driver
    drv.type = 'SCRIPTED'
    var = drv.variables.new()
    var.name = 'lvl'
    var.type = 'SINGLE_PROP'
    var.targets[0].id_type = 'OBJECT'
    var.targets[0].id = ob
    var.targets[0].data_path = '["water_level"]'
    drv.expression = 'lvl'
    print('[W] %s 旋钮：object["water_level"] = %.1f m（改它，水面立刻升降）' % (ob.name, level))


def build(step=32.0, box=None, mat=None, level_path=LVP, split=SPLIT, alpine_lo=50.0):
    """建 Water_Main / Water_West（先删掉所有旧水面对象）。

    box = (x0, x1, y0, y1) 时只保留四角都在框内的四边形（给裁剪脚本用）。
    返回 {对象名: 对象}；某个分类没有面则不建该对象。
    """
    if mat is None:
        mat = water_material()
    if mat is None:
        mat = bpy.data.materials.new('water')

    if not os.path.exists(level_path):                 # 没有两级图就退回旧图，只建一个主水面
        print('[W] 缺少 %s，退回 %s 单级' % (level_path, LVP_OLD))
        level_path = LVP_OLD
    lvl = np.load(level_path)
    wet = ~np.isnan(lvl)
    s = max(1, int(round(step / RES)))
    rows = np.arange(0, P - s, s)
    cols = np.arange(0, P - s, s)
    W4 = (wet[np.ix_(rows, cols)] & wet[np.ix_(rows, cols + s)] &
          wet[np.ix_(rows + s, cols)] & wet[np.ix_(rows + s, cols + s)])
    Lv = lvl[np.ix_(rows, cols)].astype(np.float32)
    ny, nx = len(rows), len(cols)
    X, Y = np.meshgrid(X0 + cols * RES, Y0 + rows * RES, indexing='xy')
    idx2 = np.arange(ny * nx, dtype=np.int32).reshape(ny, nx)
    a_ = idx2[:-1, :-1].ravel(); b_ = idx2[:-1, 1:].ravel()
    c_ = idx2[1:, :-1].ravel(); d_ = idx2[1:, 1:].ravel()
    q_all = np.stack([a_, b_, d_, c_], axis=1)

    west = W4 & (Lv < split)
    main = W4 & (Lv >= split) & (Lv <= alpine_lo)
    alpine = W4 & (Lv > alpine_lo)
    print('[W] step %.0f m：西盆地 %d 四边形 / 主水系 %d 四边形 / 高山湖 %d 四边形'
          % (step, west[:-1, :-1].sum(), main[:-1, :-1].sum(), alpine[:-1, :-1].sum()))

    # 先按分类取四边形，再做框裁剪（顺序反了会让布尔掩膜长度对不上）
    west_q = q_all[west[:-1, :-1].ravel()]
    main_q = q_all[main[:-1, :-1].ravel()]
    alpine_q = q_all[alpine[:-1, :-1].ravel()]
    if box is not None:
        x0, x1, y0, y1 = box
        cx = X.ravel(); cy = Y.ravel()
        inside = (cx >= x0) & (cx <= x1) & (cy >= y0) & (cy <= y1)
        west_q = west_q[inside[west_q].all(axis=1)]
        main_q = main_q[inside[main_q].all(axis=1)]
        alpine_q = alpine_q[inside[alpine_q].all(axis=1)]
        print('[W] 框内：西盆地 %d / 主水系 %d / 高山湖 %d'
              % (len(west_q), len(main_q), len(alpine_q)))

    # (对象名, 四边形, 平面高度 or None=保留各顶点水位, 旋钮范围(硬/软))
    groups = (
        ('Water_Main', main_q, MAIN_M, (20.0, 80.0, 38.0, 46.0),
         '主水系水面高度（m）。改这个数值，水面立刻升降（默认 %.1f，water.xml 真值）' % MAIN_M),
        ('Water_West', west_q, WEST_M, (-45.0, 5.0, -30.0, -15.0),
         '西盆地（瀑布以西）水面高度（m）。改这个数值，水面立刻升降（默认 %.1f）' % WEST_M),
        ('Water_Alpine', alpine_q, None, None,
         '高山小湖：各湖保留自己的水位，不跟主水系旋钮联动'),
    )
    made = {}
    for name, quads, flat_z, rng, desc in groups:
        if len(quads) == 0:
            print('[W] %s：没有四边形，跳过' % name)
            continue
        used = np.unique(quads)
        remap = np.full(idx2.size, -1, np.int64)
        remap[used] = np.arange(len(used))
        zcol = np.zeros(len(used), np.float32) if flat_z is not None else Lv.ravel()[used]
        co = np.stack([X.ravel()[used], Y.ravel()[used], zcol], axis=1).astype(np.float32)
        ob = _mesh(name, co, remap[quads], mat)
        made[name] = ob
        if flat_z is not None:
            add_level_knob(ob, flat_z, *rng, desc)
        print('[W] %-12s quads %7d  verts %7d  z %.1f ~ %.1f'
              % (name, len(quads), len(co), float(co[:, 2].min()), float(co[:, 2].max())))

    old = bpy.data.objects.get('Water')                # 旧的单平面对象
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
        print('[W] 旧单平面 Water 已删除')
    return made


def main():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    step = 32.0
    if '--step' in a:
        step = float(a[a.index('--step') + 1])
    build(step=step)
    out = os.path.join(ROOT, 'deliverable/blender/continent/continent.blend')
    if '--save-as' in a:
        out = a[a.index('--save-as') + 1]
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print('[W] saved ->', out)


if __name__ == '__main__':
    main()
