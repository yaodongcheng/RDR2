# -*- coding: utf-8 -*-
# ⛔⛔⛔ 已废弃（2026-10-28），不要再用 ⛔⛔⛔
#
# 为什么废弃：
#   1. sdn_full2 的地形本来就是 H4 原生高程（add_terrain 直接读），和 sdn.blend 同源；
#      建筑 z 也是 ymap 原值 —— 两者天然对齐，**根本不需要拟合**。
#   2. 本脚本把它拟合抬高后，公园地面件（park_terrain / glue）被地形顶穿 1.4~1.9 m，
#      画面支离破碎。修了三轮（模糊场 / 栅格封顶 / 射线封顶）都只是给自造的问题打补丁。
#   3. 正确做法：**重装配即恢复**，不跑任何地形拟合。
#
# 保留仅为记录教训。真要跑，加 --i-know-what-im-doing 才会执行。
"""把地形拉到「建筑基底」上，修 sdn_full2 的整片浮空（continent 版见 fit_terrain_to_buildings.py，
那个脚本写死了 ENTITIES 集合 + e_ 前缀对象名，本版改为直接遍历场景，适配 gltf 装配出的 TILE_* 结构）。

## 两遍处理（2026-10-28 修正）

第一遍：按**建筑底**抬/压地形（原逻辑），修整片浮空。
第二遍：**地面件封顶** —— 城市里本来就铺了一层地面件（`*_park_terrain` / `*_glue*` /
`*_ground*` / `*_road*` / `*_sidewalk*`），它们是"最终可见地表"。
第一遍若把它们下面的地形抬过头，草坪就会被地形顶穿（实测圣丹尼斯公园：地形 45.71~46.44
vs 地面件底 44.40，顶穿 1.3~2.0 m，画面支离破碎）。
⇒ 第二遍把落在这些地面件范围内的地形顶点钳到「地面件表面 − 0.15 m」以下。

    blender -b <blend> -P tools/fit_terrain_sdn.py -- [--max-dz 8] [--no-cap] [--dry]
"""
import bpy, numpy as np, math, sys, collections
from mathutils import Vector
from mathutils.bvhtree import BVHTree

CELL = 4.0

# 地面件：城市里铺好的"最终可见地表"，地形不得高过它们
import re as _re
GROUND_RE = _re.compile(
    r'(_terrain$|_terrain\d|_glue|_ground\d*$|_gr_|_road_|roads?_|_sidewalk|_pavement|park_terrain)',
    _re.I)


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def wbb(o):
    mn = Vector((1e18,) * 3); mx = Vector((-1e18,) * 3)
    for c in o.bound_box:
        p = o.matrix_world @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], p[i]); mx[i] = max(mx[i], p[i])
    return mn, mx


def _box1(a, r, axis):
    if axis == 0:
        a = a.T
    n = a.shape[1]
    c = np.concatenate([np.zeros((a.shape[0], 1)), np.cumsum(a, axis=1)], axis=1)
    idx = np.arange(n)
    lo = np.clip(idx - r, 0, n)
    hi = np.clip(idx + r + 1, 0, n)
    out = (c[:, hi] - c[:, lo]) / np.maximum(1, hi - lo)
    return out if axis == 1 else out.T


def box_blur(a, w, r=8):
    for _ in range(3):
        a = _box1(a, r, 0); w = _box1(w, r, 0)
        a = _box1(a, r, 1); w = _box1(w, r, 1)
    return a, w


def main():
    args = argv()
    if '--i-know-what-im-doing' not in args:
        print('[fitsdn] ⛔ 已废弃：sdn_full2 用原生地形，不需要拟合。重装配即可。')
        print('[fitsdn] 若坚持要跑，加 --i-know-what-im-doing')
        return
    max_dz = 8.0
    if '--max-dz' in args:
        max_dz = float(args[args.index('--max-dz') + 1])
    dry = '--dry' in args

    ter = bpy.data.objects['Terrain']
    deps = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(ter, deps)

    # 收集建筑底点
    SKIP = ('_dec', 'decal', '_em', 'slod', 'vfx', 'rail', '_r_c_', '_r_b_', '_r_a_', 'br_', 'debris', 'p_')
    pts = []
    for o in bpy.context.scene.objects:
        if o.type != 'MESH' or o.name == 'Terrain':
            continue
        l = o.name.lower()
        if any(k in l for k in SKIP):
            continue
        mn, mx = wbb(o)
        if max(mx.x - mn.x, mx.y - mn.y) < 4.0:      # 小道具不参与
            continue
        if max(mx.x - mn.x, mx.y - mn.y) > 300:      # 超级大件不参与
            continue
        cx, cy = (mn.x + mx.x) / 2, (mn.y + mx.y) / 2
        hit = bvh.ray_cast(Vector((cx, cy, 2000.0)), Vector((0, 0, -1)), 4000.0)
        if hit[0] is None:
            continue
        pts.append((cx, cy, mn.z - hit[0].z))
    print('[fitsdn] 锚点 %d 个' % len(pts))
    if not pts:
        print('[fitsdn] 无锚点，退出'); return
    a = np.array(pts)
    print('[fitsdn] 原始 残差 中位 %+.2f  均值 %+.2f  MAE %.2f  |r|<=0.5 占 %.1f%%' % (
        np.median(a[:, 2]), a[:, 2].mean(), np.abs(a[:, 2]).mean(),
        100 * (np.abs(a[:, 2]) <= 0.5).mean()))

    # 栅格化
    n = len(ter.data.vertices)
    co = np.empty(n * 3); ter.data.vertices.foreach_get('co', co); co = co.reshape(n, 3)
    M = np.array(ter.matrix_world)
    w = co @ M[:3, :3].T + M[:3, 3]
    x0, y0 = w[:, 0].min(), w[:, 1].min()
    nx = int((w[:, 0].max() - x0) / CELL) + 1
    ny = int((w[:, 1].max() - y0) / CELL) + 1
    F = np.zeros((ny, nx), np.float64)
    W = np.zeros((ny, nx), np.float64)
    ci = np.clip(((a[:, 0] - x0) / CELL).astype(np.int32), 0, nx - 1)
    ri = np.clip(((a[:, 1] - y0) / CELL).astype(np.int32), 0, ny - 1)
    r = np.clip(a[:, 2], -max_dz, max_dz)
    np.add.at(F, (ri, ci), r)
    np.add.at(W, (ri, ci), 1.0)
    blur_r = 2
    if '--blur' in args:
        blur_r = int(args[args.index('--blur') + 1])
    if blur_r > 0:
        F, W = box_blur(F, W, r=blur_r)
    field = np.divide(F, W, out=np.zeros_like(F), where=W > 1e-9)

    # 应用到地形顶点
    ci2 = np.clip(((w[:, 0] - x0) / CELL).astype(np.int32), 0, nx - 1)
    ri2 = np.clip(((w[:, 1] - y0) / CELL).astype(np.int32), 0, ny - 1)
    dz = field[ri2, ci2]
    print('[fitsdn] 地形顶点 %d，改动 %d 个；dz 中位 %+.2f  max %+.2f min %+.2f' % (
        n, int((np.abs(dz) > 0.02).sum()), float(np.median(dz[np.abs(dz) > 0.02])) if (np.abs(dz) > 0.02).any() else 0,
        float(dz.max()), float(dz.min())))
    if dry:
        print('[fitsdn] dry-run'); return

    w2 = w.copy()
    w2[:, 2] += dz
    Minv = np.linalg.inv(M)
    co2 = w2 @ Minv[:3, :3].T + Minv[:3, 3]
    ter.data.vertices.foreach_set('co', co2.astype(np.float32).ravel())
    ter.data.update()
    bpy.context.view_layer.update()
    print('[fitsdn] 第一遍（建筑贴合）完成')

    # ---- 第二遍：地面件封顶（射线打法，不依赖顶点密度） ----
    if '--no-cap' not in args:
        gverts = []
        gpolys = []
        n_g = 0
        base = 0
        for o in bpy.context.scene.objects:
            if o.type != 'MESH' or o.name == 'Terrain':
                continue
            if not GROUND_RE.search(o.name):
                continue
            bb0, bb1 = wbb(o)
            dx, dy = bb1.x - bb0.x, bb1.y - bb0.y
            if max(dx, dy) < 8 or max(dx, dy) > 500:
                continue
            if (bb1.z - bb0.z) > max(dx, dy) * 0.5:
                continue
            me = o.data
            if len(me.vertices) == 0:
                continue
            n_g += 1
            Mo = np.array(o.matrix_world)
            vc = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get('co', vc); vc = vc.reshape(-1, 3)
            vw = vc @ Mo[:3, :3].T + Mo[:3, 3]
            gverts.append(vw)
            me.calc_loop_triangles()
            nt = len(me.loop_triangles)
            tri = np.empty(nt * 3, dtype=np.int64)
            me.loop_triangles.foreach_get('vertices', tri)
            gpolys.append((tri.reshape(nt, 3) + base).ravel())
            base += len(vw)
        print('[fitsdn] 地面件 %d 个参与封顶' % n_g)
        if n_g:
            from mathutils.bvhtree import BVHTree
            V = np.vstack(gverts)
            P = np.concatenate(gpolys).reshape(-1, 3)
            bvh = BVHTree.FromPolygons([Vector(v) for v in V], [tuple(int(i) for i in t) for t in P], all_triangles=True)
            after = w[:, 2] + dz
            n_over = 0
            maxdrop = 0.0
            for i in range(len(w)):
                h = bvh.ray_cast(Vector((w[i, 0], w[i, 1], after[i] + 50.0)), Vector((0, 0, -1)), 200.0)
                if h[0] is None:
                    continue
                cap = h[0].z - 0.15
                if after[i] > cap:
                    dz[i] = cap - w[i, 2]
                    n_over += 1
                    maxdrop = max(maxdrop, after[i] - cap)
            print('[fitsdn] 封顶：%d 个地形顶点被压到地面件下方（最大压 %.2f m）' % (n_over, maxdrop))

    p = bpy.data.filepath
    bpy.ops.wm.save_mainfile()
    print('[fitsdn] saved', p)


main()
