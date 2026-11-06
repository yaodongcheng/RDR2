# -*- coding: utf-8 -*-
"""把室内 MLO 摆进**场景** blend（场景构建的最后一步）。

背景：`deliverable/terrain` 只切出来地面，建筑都是外壳；真正的室内在
`levels/rdr3/interiors/<包>_int.rpf`，件的位置写在包里的 `<包>.ytyp`（室内局部坐标），
世界位置由 area ymap 里的 `<包>` MLO 实例（pos + quat）决定
（口径与 `merge_interior_into_willard.py` / `instantiate_interiors.py` 完全一致）。

口径（2026-11-04 立）：
  · 只摆**活动区**里的包（远景圈不放室内）；
  · **只摆据点场景**（`scene["kind"] == "settlement"`）：野地场景的活动区是 2~4 km 大矩形，
    里面套着整座城，照着摆会多出几十套（实测 wild_04 = 43 套 / 6465 件 ≈ +2.6 GB），
    而按设计玩家在野地里只能看到据点 LOD、走到边界切进据点场景，室内永远走不进去；
  · 只摆 `export/world/interior_placement_audit.json` 里 **`inside=True`** 的包。
    ⚠️ 不要改成"看四边间隙"（曾经用过 `min(gaps) >= -2.5`）：宿主若匹配到一大片
    合并块（黑水镇裁缝铺就配到了 42×105 m 的路面贴花条），间隙全是正数、照样通过 ——
    `inside` 是审计按「包得住 + 面积不超过室内的 4 倍」判的，才挡得住这种假宿主；
  · 坐标 = **场景局部坐标**（世界 − 场景中心），与 `scene_trim` 的平移口径一致；
  · 集合树 `ENTITIES/C_int_室内/int|<地块>`，面板「RDR2 分类开关」能单独勾。

调用：`blender_continent.py --scene <id> --full` 收尾时自动调 `build(scene)`。
也可单独跑：blender -b <scene.blend> -P tools/scene_interiors.py -- --scene bla
"""

import argparse
import glob
import json
import math
import os
import re
import sys

import bpy
from mathutils import Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import blender_continent as BC          # noqa: E402
import blender_tour as tour             # noqa: E402
import parse_interior_mlo as PM         # noqa: E402

ROOT = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(ROOT, 'assets/lib_native')
AUDIT = os.path.join(ROOT, 'export/world/interior_placement_audit.json')
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
PACKS = os.path.join(ROOT, 'raw/all_packs')
COL = 'C_int_室内'
# 2026-11-05 用户裁定：室内地面贴花单独一类（与室外 `decal` 分开）。
# 室内件的对象名一律是 `i_<hash>`，名字规则判不出 —— 只能看**模型的贴图名**：
# `_dc_` / `decal` / `holepatch` / `drip` / `stain`（实测 vall_dc_sal_holepatch_ab、
# val_dc_floordecal01_nm、val_dc_drip01_al、bla_dr_stain03_ab）。
COL_DECAL = 'C_int_decal_室内地面贴花'
DECAL_TEX = re.compile(r'(_dc_|decal|holepatch|drip|stain)', re.I)
# 2026-11-05：室内包的**阴影 / 反射代理**只参与投影和镜面，不是可见几何。
# 实测瓦伦丁马厩 `val_stable_int_shadow`：143 顶点、无 albedo（靠 ntex_wood 兜底配色），
# 当普通件摆进场景就成了一块盖在屋顶上的空壳 —— 用户目视到的「墙面没对齐」就是它。
# 🔴 命名有一整族，别只匹配 `_shadow`（第一版就这么漏了 90%）：
#   `<包>_shadowproxy`(57) · `_ref_proxy`(34) · `_shadow_proxy`(24) · `_shadow`(9) ·
#   `_shdw_proxy` / `_shd_proxy` / `_shad_proxy` / `_shdw_prxy` / `_shdwprxy` / `_shd_pxy` ·
#   `_refproxy` · `_reflection_proxy` · `_refln_proxy` · `_refle_proxy` · `rfle_proxy` ·
#   `_proxy` · `_shadowbox` ……  全量 251 个室内包里共 **326 件**。
# 判据见 `最高原则` §6.1：`*_proxy*` / 占位代理一律进默认隐藏类。
COL_PROXY = 'C_int_proxy_室内阴影代理'
# 2026-11-06（用户实机）：灯光占位件（`*_int_lights` / `*_lights`）也归本类 —— 同属"不可见的功能代理"。
# 实测 `rho_sheriff_int_lights`（24 顶点、无贴图、材质 ntex_default）被当普通件摆进去就是一块白片。
# 2026-11-06 第二轮：**裸 `_ref`**（`rho_fenceshop_int_ref` 等 302 个模型）也是反射代理，
# 贴图名就是 `*_ref*` / `*_lod*`、单子网格低模 —— 之前只认 `proxy/shadow`，它被当家具显示。
PROXY_NAME = re.compile(
    r'(proxy|shadow|shdw|shd_|shad_|_ref(?=_|$|\d)|(?<![a-z])lights?(?=_|$|\d))', re.I)

# 2026-11-06：MLO 的 **layout 白模**（Rockstar 地编布局用的 `layout_*` 占位白盒）。
# 🔴 用户裁定：**不准删网格** —— 摆进来、单独成类、默认隐藏，N 面板可勾开看。
COL_LAYOUT = 'C_layout_布局白模'

_NAMES = None
_TILES = None


def _names():
    global _NAMES
    if _NAMES is None:
        # 2026-11-05：走 name_source（原表 + 从 `*_children` 反推的父名），
        # 与 blender_continent / classify_entities 同一口径。
        try:
            from name_source import load_names_lower
            _NAMES = load_names_lower()
        except Exception:
            _NAMES = {}
            p = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
            with open(p, encoding='latin1', errors='ignore') as f:
                for line in f:
                    n = line.strip()
                    if n:
                        _NAMES.setdefault(PM.joaat(n), n.lower())
    return _NAMES


def _tiles():
    global _TILES
    if _TILES is None:
        _TILES = []
        for p in sorted(glob.glob(os.path.join(TILES, '*.json'))):
            if p.endswith('.bak'):
                continue
            try:
                _TILES.extend(json.load(open(p, encoding='utf-8')))
            except Exception:
                continue
    return _TILES


def find_mlo(pkg):
    """包名 → MLO 实例实体 [hash, x, y, z, qx, qy, qz, qw]。

    🔴 唯一口径 = `parse_interior_mlo.find_mlo_instance`（精确 → `_main` → `_lod`）。
    2026-11-06 实机：旧实现「先撞到谁算谁」把 `val_bank_int_lod`（yaw −100°）当成银行实例，
    瓦伦丁银行室内转歪；全量 210 个 inside 包里 42 个受影响。
    """
    return PM.find_mlo_instance(pkg, names=_names(), tile_list=_tiles())


def _ytyp(pkg):
    p = os.path.join(PACKS, pkg, pkg + '.ytyp')
    if os.path.exists(p):
        return p
    cand = glob.glob(os.path.join(PACKS, pkg, '*.ytyp'))
    return cand[0] if cand else None


def _col():
    return _col_named(COL)


def _col_decal():
    """室内地面贴花集合（默认隐藏：贴图 alpha 还没接，会画成实心片；N 面板可单独勾开）。"""
    return _col_named(COL_DECAL, hide=True)


def _col_proxy():
    """阴影代理壳集合（默认隐藏：只参与投影，摆出来就是一块盖在屋顶上的空壳）。"""
    return _col_named(COL_PROXY, hide=True)


def _col_layout():
    """布局白模集合（默认隐藏：Rockstar 地编布局用的白盒，不是最终可见几何；N 面板可勾开）。"""
    return _col_named(COL_LAYOUT, hide=True)


def _entity_world_bbox(ent, model):
    """外壳实体 × 模型 bbox → 世界 bbox 范围（普通实体取共轭，与 build_entities 同口径）。"""
    b = model['b']
    q = Quaternion((ent[7], -ent[4], -ent[5], -ent[6]))
    sx, sy, sz = ent[8], ent[8], ent[9]
    xs, ys, zs = [], [], []
    for x in (b[0], b[3]):
        for y in (b[1], b[4]):
            for z in (b[2], b[5]):
                v = q @ Vector((x * sx, y * sy, z * sz))
                xs.append(v.x + ent[1]); ys.append(v.y + ent[2]); zs.append(v.z + ent[3])
    if not xs:
        return None
    return {'xmin': min(xs), 'xmax': max(xs), 'ymin': min(ys), 'ymax': max(ys),
            'zmin': min(zs), 'zmax': max(zs)}


def _objs_world_bbox(objs):
    """一组对象的世界 bbox 范围（用 matrix_basis，避免隐藏集合不求值）。"""
    xs, ys, zs = [], [], []
    for o in objs:
        for c in o.bound_box:
            p = o.matrix_basis @ Vector(c)
            xs.append(p.x); ys.append(p.y); zs.append(p.z)
    if not xs:
        return None
    return {'xmin': min(xs), 'xmax': max(xs), 'ymin': min(ys), 'ymax': max(ys),
            'zmin': min(zs), 'zmax': max(zs)}


def _ent_yaw(e):
    """实体四元数 (x,y,z,w) → yaw（度）。"""
    qx, qy, qz, qw = e[4], e[5], e[6], e[7]
    return math.degrees(math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz)))


def _inst_yaw(inst):
    """实例四元数 [hash,x,y,z,qx,qy,qz,qw] → yaw（度）。"""
    return _ent_yaw([0, 0, 0, 0, inst[4], inst[5], inst[6], inst[7]])


_WALL_CACHE = {}


def _low_wall_dir(h):
    """模型**下半截墙体**方向 → (角度 mod 90, 纯度)。

    🔴 2026-11-06（用户提醒）：夏洛蒂家同款坑 —— **外扩屋檐会污染墙向**。
    整模型水平边做 4θ 平均时，屋檐的长边把方向带偏（甚至让"随便怎么转都看着对"）。
    这里只取下半截（z ≤ z0 + 0.6·高度）的水平边，代表真正的墙体。
    """
    if h in _WALL_CACHE:
        return _WALL_CACHE[h]
    res = None
    try:
        import numpy as np
        import rdr2_mdl
        md = rdr2_mdl.load_mdl(h)
        if md is not None:
            pos, nrm, uv, idx, tex, vtex = md
            z0, z1 = float(pos[:, 2].min()), float(pos[:, 2].max())
            zc = z0 + 0.6 * (z1 - z0)
            e = np.concatenate([idx[:, [0, 1]], idx[:, [1, 2]], idx[:, [2, 0]]], axis=0)
            e = np.unique(np.sort(e, axis=1), axis=0)
            d = pos[e[:, 1]] - pos[e[:, 0]]
            ln = np.linalg.norm(d, axis=1)
            mz = (pos[e[:, 0], 2] + pos[e[:, 1], 2]) * 0.5
            m = (ln > 0.4) & (np.abs(d[:, 2]) < 0.05 * ln) & (mz <= zc)
            if m.sum() >= 20:
                th = np.arctan2(d[m, 1], d[m, 0])
                w = ln[m]
                v = (w * np.exp(4j * th)).sum()
                res = (math.degrees(np.angle(v)) / 4.0, float(abs(v) / w.sum()))
    except Exception:
        res = None
    _WALL_CACHE[h] = res
    return res


def _obj_mesh_bbox(o):
    """Bpy 对象的**真实网格** bbox（场景局部坐标；matrix_basis 避免隐藏集合不求值）。

    🔴 2026-11-06 实机：不要用模型库的 `b`（那是导入时的包围盒，实测 `rho_04_bkdoorshut`
    库 bbox 10.8×10.5，实际网格只有 7.4×7.3 —— 拿错 bbox 套合永远对不上）。
    """
    m = o.matrix_basis
    xs, ys, zs = [], [], []
    for v in o.data.vertices:
        p = m @ v.co
        xs.append(p.x); ys.append(p.y); zs.append(p.z)
    if not xs:
        return None
    return {'xmin': min(xs), 'xmax': max(xs), 'ymin': min(ys), 'ymax': max(ys),
            'zmin': min(zs), 'zmax': max(zs)}


def _overlap_shift(room_objs, wall_obj, build_objs, res=0.15, span=1.5, step=0.10):
    """**面积重合率最大**的水平位移：室内 vs (墙 + 建筑) 的 2D 点掩膜直接网格搜索。

    目标 = 10×(墙点被房间盖住的比例) + 1×(室内点落在建筑内的比例)。
    只对「没有真实例（只有 `_lod`）」的包启用；正常包用游戏实例。
    🔴 2026-11-06 用户实机：墙是 L 形墙带，bbox 居中不是最优 —— 要用真实网格求覆盖。
    """
    try:
        import numpy as np
    except Exception:
        return None

    def pts(objs, stride):
        out = []
        for o in objs:
            if o is None or o.type != 'MESH':
                continue
            m = o.matrix_basis
            vs = o.data.vertices
            for i in range(0, len(vs), stride):
                p = m @ vs[i].co
                out.append((p.x, p.y))
        return np.array(out, dtype=np.float64) if out else np.zeros((0, 2))

    P_room = pts(room_objs, 2)
    P_build = pts(build_objs, 2)
    P_wall = pts([wall_obj], 1)
    if len(P_room) < 50 or len(P_build) < 50 or len(P_wall) < 20:
        return None
    allp = np.vstack([P_room, P_build])
    x0 = allp[:, 0].min() - 3.0; y0 = allp[:, 1].min() - 3.0
    x1 = allp[:, 0].max() + 3.0; y1 = allp[:, 1].max() + 3.0
    nx = int(np.ceil((x1 - x0) / res)) + 1
    ny = int(np.ceil((y1 - y0) / res)) + 1

    def mask(P):
        m = np.zeros((ny, nx), np.float32)
        if len(P):
            ix = np.clip(((P[:, 0] - x0) / res).astype(int), 0, nx - 1)
            iy = np.clip(((P[:, 1] - y0) / res).astype(int), 0, ny - 1)
            m[iy, ix] = 1.0
        return m

    M_room = mask(P_room)
    M_build = mask(P_build)
    # 室内掩膜膨胀一格（点采样 → 近似面积）
    M_room_d = M_room.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            M_room_d = np.maximum(M_room_d, np.roll(np.roll(M_room, dy, 0), dx, 1))

    def cov_wall(dx, dy):
        ix = np.clip(((P_wall[:, 0] - dx - x0) / res).astype(int), 0, nx - 1)
        iy = np.clip(((P_wall[:, 1] - dy - y0) / res).astype(int), 0, ny - 1)
        return float(M_room_d[iy, ix].sum())

    def cov_build(dx, dy):
        ix = np.clip(((P_room[:, 0] + dx - x0) / res).astype(int), 0, nx - 1)
        iy = np.clip(((P_room[:, 1] + dy - y0) / res).astype(int), 0, ny - 1)
        return float(M_build[iy, ix].sum())

    n = int(round(span / step))
    best = None
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            dx, dy = round(i * step, 2), round(j * step, 2)
            s = 10.0 * cov_wall(dx, dy) / max(1, len(P_wall)) \
                + 1.0 * cov_build(dx, dy) / max(1, len(P_room))
            if best is None or s > best[0]:
                best = (s, dx, dy)
    return (best[1], best[2], best[0])


def _dom_plane(z, lo, hi, bins=60, min_n=30):
    """z 直方图里最密的那一层 → 主水平面高度（地板/屋顶用）。

    🔴 2026-11-06 用户实机：bbox 的 zmin/zmax 会被墙脚装饰、屋脊带偏（房间底 80.04 但地板面 80.5；
    建筑 zmin 79.93 但地板面 81.27）。**按"主水平面"对齐**才不会一沉一穿。
    """
    try:
        import numpy as np
    except Exception:
        return None
    z = np.asarray(z, dtype=np.float64)
    sel = z[(z >= lo) & (z <= hi)]
    if len(sel) < min_n:
        return None
    h, edges = np.histogram(sel, bins=bins)
    i = int(np.argmax(h))
    return float((edges[i] + edges[i + 1]) / 2.0)


def _floor_roof_planes(build_obj, room_objs):
    """→ (建筑地板面, 建筑屋顶面, 房间地板面)，都按主水平面统计（在房间 XY 范围内）。"""
    try:
        import numpy as np
    except Exception:
        return None
    if build_obj is None or build_obj.type != 'MESH':
        return None
    xs, ys, rz = [], [], []
    for o in room_objs:
        m = o.matrix_basis
        for v in o.data.vertices:
            p = m @ v.co
            xs.append(p.x); ys.append(p.y); rz.append(p.z)
    if not rz:
        return None
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    bm = build_obj.matrix_basis
    bv = np.array([(bm @ v.co)[:] for v in build_obj.data.vertices])
    if not len(bv):
        return None
    sel = bv[(bv[:, 0] >= x0 - 0.2) & (bv[:, 0] <= x1 + 0.2)
             & (bv[:, 1] >= y0 - 0.2) & (bv[:, 1] <= y1 + 0.2)]
    if len(sel) < 100:
        return None
    bz = sel[:, 2]
    blo, bhi = float(bz.min()), float(bz.max())
    # 固定窗口（不用 bbox 百分比 —— 移位后窗口会换、抓到的平面也跟着换）
    floor_b = _dom_plane(bz, blo, blo + 1.5)
    roof_b = _dom_plane(bz, bhi - 1.0, bhi)
    rz = np.asarray(rz, dtype=np.float64)
    rlo = float(rz.min())
    floor_r = _dom_plane(rz, rlo, rlo + 1.0)
    if floor_b is None or floor_r is None:
        return None
    return (floor_b, roof_b, floor_r)


def _col_named(name, hide=False):
    ent = bpy.data.collections.get('ENTITIES')
    parent = ent if ent is not None else bpy.context.scene.collection
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        parent.children.link(c)
        if hide:
            _hide_col(c)
    return c


def _hide_col(col):
    """整类默认隐藏：数据层 + 视层眼睛两套一起设（与 classify_entities 同口径）。"""
    col.hide_viewport = True
    col.hide_render = True
    root = bpy.context.view_layer.layer_collection
    stack = [root]
    while stack:
        node = stack.pop()
        if node.name == col.name:
            node.hide_viewport = True
            return
        stack.extend(node.children)


def _mat_textures(m, texmeta):
    """模型索引条目 → 它的贴图名列表（`s[0]` 是 texId）。"""
    out = []
    for s in (m.get('s') or []):
        tid = s[0] if s else -1
        if 0 <= tid < len(texmeta):
            e = texmeta[tid] or {}
            n = e.get('n') or ''
            if n:
                out.append(n)
    return out


def _is_decal(m, texmeta):
    # 🔴 2026-11-05：必须**全部**子网格的贴图都是贴花类，才算地面贴花。
    # 原来是「任意一个命中就算」—— 一件家具只要混进一张 `drip`/`stain` 图就被扫进来。
    # 实测威拉德之息：床 `roc_hse_bed01_logs`（23,256 顶点，8 个子网格）里只有 1 个是
    # `roc_int_drip01`，却被归成「室内地面贴花」整类隐藏。
    # 全量分布：911 个有命中的模型里，全部子网格都命中的 205 个（真贴花），
    # 命中比例 ≤0.5 的 594 个（基本都是误判）。
    names = _mat_textures(m, texmeta)
    if not names:
        return False
    return all(DECAL_TEX.search(n) for n in names)


# 🔴 2026-11-06：MLO 的 **layout 白模**（Rockstar 地编布局用的占位壳/家具）。
# 实测 `ann_setlrs_reg_int_shell`（layout_walls/floors/ceiling）与 `_beams`（layout_floors）
# 被当普通室内件摆进去 ⇒ 安尼斯堡房顶上多出两块白板（用户实机截图）。
# 它们不是可见几何，**一律不摆**（不是隐藏，是根本不该进场景）。
LAYOUT_TEX = re.compile(r'^layout_(?:walls|floors|ceiling|props)$', re.I)


def _is_layout_model(m, texmeta):
    """模型的所有子网格贴图都是 `layout_*` → 布局白模，跳过。"""
    names = _mat_textures(m, texmeta)
    return bool(names) and all(LAYOUT_TEX.match(n) for n in names)


def build(scene, save=True, verbose=True):
    """把审计通过、且落在活动区里的室内包摆进当前场景。返回摆放对象数。"""
    # 🔴 只给**据点场景**摆室内。野地场景的活动区是 2~4 km 的大矩形，里面套着整座城，
    # 照着摆会多出几十套（实测 wild_04 = 43 套 / 6465 件 ≈ +2.6 GB），而按设计玩家在野地里
    # 只能看到据点的 LOD 碎片、走到边界会切进据点场景 —— 野地里的室内永远走不进去。
    if (scene.get("kind") or "") != "settlement":
        print("[int] 非据点场景（%s），跳过室内" % (scene.get("kind") or "?"))
        return 0
    if not os.path.exists(AUDIT):
        print('[int] 缺审计表 %s，跳过' % AUDIT)
        return 0
    audit = json.load(open(AUDIT, encoding='utf-8'))
    ok = [x for x in audit if x.get('inside')]
    print('[int] 审计通过（inside=True）：%d / %d 包' % (len(ok), len(audit)))

    idx = json.load(open(os.path.join(LIB, 'index.json'), encoding='utf-8'))
    models, texmeta = idx['models'], idx['tex']

    cx, cy = scene['x'], scene['y']
    # 🔴 2026-11-04：活动区 = 能走范围 P（P 外按远景处理，那里的建筑不建，室内也不摆）。
    if scene.get('p'):
        ax0, ay0, ax1, ay1 = scene['p']
    else:
        ax0, ay0 = cx - scene['aw'] / 2, cy - scene['ah'] / 2
        ax1, ay1 = cx + scene['aw'] / 2, cy + scene['ah'] / 2

    col = _col()
    matcache, meshcache = {}, {}
    placed = made = decals = proxies = 0
    layouts = 0             # layout 白模（不删，单独归类 + 默认隐藏）
    skipped_out = 0          # P 外（= 远景区域）的包：一律不摆
    for rec in ok:
        pkg = rec['pkg']
        inst = find_mlo(pkg)
        if inst is None:
            continue
        if not (ax0 <= inst[1] <= ax1 and ay0 <= inst[2] <= ay1):
            skipped_out += 1
            continue
        yp = _ytyp(pkg)
        if yp is None:
            continue
        try:
            ents = PM.parse_ytyp(yp)
        except Exception as e:
            print('[int] %s 解析失败：%s' % (pkg, e))
            continue
        if isinstance(ents, dict):
            ents = ents.get('entities') or []

        # 世界 → 场景局部
        P = Vector((inst[1] - cx, inst[2] - cy, inst[3]))
        # 🔴 2026-11-05 实锤：**MLO 实例**的四元数方向与普通 ymap 实体相反 —— 这里**不能**取共轭。
        #   判据（tools/_check_interior_align.py）：室内 `*_shell` 墙向 = 宿主外壳墙向。
        #     · 实例取共轭 → 48 个可判包里 |Δ| 中位 29.7°，<2° 只有 2 个；
        #     · 不取共轭   → 中位 0.34°，<2° 有 46 个。
        #   件级（下面 ytyp entity 的 q）**恰好相反**：取共轭 93% 落在 5° 内，不取共轭只有 1%
        #   ⇒ 只有*实例*这一层是反的；件级与大陆外壳仍按原样取共轭。
        #   瓦伦丁马厩：val_stable_int 的 +5.13° 被取共轭成 -5.13°，与 val_03_stable_ext
        #   差出 10.2°（用户 2026-11-05 目视到的"墙面没对齐"）。夏洛蒂家同一根因。
        # 2026-11-06（用户提醒）：只有 `_lod` 的包 —— LOD 朝向不可信，而且**外扩屋檐会让"看着对"骗人**
        # （夏洛蒂家同款）。判据 = **室内墙体与建筑墙体吻合**：用「宿主下半截墙向 − 壳体下半截墙向」
        # 反算实例 yaw；宿主优先取审计表的 `host`（真正承载房间的墙体/构件，如 `rho_04_bkdoorshut`），
        # 没有再退同词干外壳。4θ 墙向有 90° 歧义，用 LOD 原朝向选最近的象限。
        _idx0 = PM.mlo_index(names=_names(), tile_list=_tiles())
        _ov_host = None
        if pkg not in _idx0 and (pkg + '_main') not in _idx0:
            _hn = (rec.get('host') or '').lower()
            _ov_host = _idx0.get(_hn) if _hn else None
            if _ov_host is None:
                _ov_host = PM.stem_exterior(pkg, names=_names(), tile_list=_tiles(), inst=inst)
            _shell_h = None
            for _e in ents:
                _n = (_names().get(_e['h']) or '')
                if re.search(r'_shell(_main)?$', _n, re.I):
                    _shell_h = _e['h']
                    break
            if _ov_host is not None and _shell_h is not None:
                _sa = _low_wall_dir(_shell_h)
                _ea = _low_wall_dir(int(_ov_host[0]))
                if _sa and _ea:
                    _base = _ea[0] - _ent_yaw(_ov_host) - _sa[0]
                    _cur = _inst_yaw(inst)
                    _best = min((_base + 90 * k for k in range(-4, 5)),
                                key=lambda a: abs((a - _cur + 180) % 360 - 180))
                    _rad = math.radians(_best)
                    inst = list(inst)
                    inst[4] = 0.0
                    inst[5] = 0.0
                    inst[6] = math.sin(_rad / 2.0)
                    inst[7] = math.cos(_rad / 2.0)
                    print('[int] %-24s 朝向按墙体校正 %+.2f°（原 LOD %+.2f°；宿主 %s）'
                          % (pkg, _best, _cur, _names().get(int(_ov_host[0]), '')))
        q = Quaternion((inst[7], inst[4], inst[5], inst[6]))

        n_pkg = 0
        pkg_objs = []
        for e in ents:
            # 🔴 必须补零成 0x%08x：模型库的键是 8 位。用 hex() 时 0x00418731 会变成
            # `0x418731`，查不到 ⇒ 静默丢掉。实测室内件里 **2,597 / 47,791** 的哈希有前导零，
            # 其中 **2,495 个模型其实在库里**（家具/门/碎石堆…），一直被吞（最高原则 §6.4）。
            hx = '0x%08x' % e['h']
            m = models.get(hx)
            if not m:
                continue
            # 2026-11-06（用户裁定）：layout 白模**不准删网格**，只归类 + 默认隐藏。
            # 整件都是白模 → 一件「布局白模」；混血（真实木地板 + layout_floors）→ 拆两件：
            # 真几何按原规则（int_proxy / int_decal / part，可见），白模走「布局白模」（隐藏）。
            _subs = m.get('s') or []
            _nlay = sum(1 for s in _subs
                        if isinstance(s[0], int) and 0 <= s[0] < len(texmeta)
                        and LAYOUT_TEX.match((texmeta[s[0]] or {}).get('n') or ''))
            try:
                # 2026-11-05：传模型名 → 无 albedo 的件按名字自动配色（ntex_palette）。
                _mn = _names().get(int(hx, 16), '')
                me_real = None
                if _nlay < len(_subs):
                    me_real = BC.load_model_mesh(LIB, m, texmeta, matcache, meshcache,
                                                 name_hint=_mn, skip_tex=LAYOUT_TEX)
                me_lay = None
                if _nlay:
                    me_lay = BC.load_model_mesh(LIB, m, texmeta, matcache, meshcache,
                                                name_hint=_mn, keep_tex=LAYOUT_TEX)
            except Exception:
                continue
            if not me_real and not me_lay:
                continue
            loc = P + (q @ Vector(e['p']))
            lq = Quaternion((e['q'][3], -e['q'][0], -e['q'][1], -e['q'][2]))
            roq = q @ lq
            tid = tour._tile_of(loc.x + cx, loc.y + cy)

            if me_real:
                ob = bpy.data.objects.new('i_%s' % hx[2:], me_real)
                ob.location = loc
                ob.rotation_mode = 'QUATERNION'
                ob.rotation_quaternion = roq
                is_dec = _is_decal(m, texmeta)
                # 名字规则：`i_<hash>` 判不出是什么件，只能问模型名（`<包>_shadow` / `*_lights` 这类）。
                is_proxy = bool(PROXY_NAME.search(_mn or ''))
                key = 'int_proxy' if is_proxy else ('int_decal' if is_dec else 'part')
                ob['cls_key'] = key
                ob['int_pkg'] = pkg
                # 子集合按地块分（与世界坐标一致，重建/裁剪时对数方便）
                parent = _col_proxy() if is_proxy else (_col_decal() if is_dec else col)
                tag = 'int_proxy' if is_proxy else ('int_decal' if is_dec else 'int')
                sub = next((s for s in parent.children if s.get('tile') == tid), None)
                if sub is None:
                    sub = bpy.data.collections.new('%s|%s' % (tag, tid))
                    sub['tile'] = tid
                    sub['cat'] = key
                    parent.children.link(sub)
                sub.objects.link(ob)
                pkg_objs.append(ob)
                if is_proxy:
                    proxies += 1
                if is_dec:
                    decals += 1
                n_pkg += 1

            if me_lay:
                ob2 = bpy.data.objects.new('i_%s%s' % (hx[2:], '_lay' if me_real else ''), me_lay)
                ob2.location = loc
                ob2.rotation_mode = 'QUATERNION'
                ob2.rotation_quaternion = roq
                ob2['cls_key'] = 'layout'
                ob2['int_pkg'] = pkg
                parent = _col_layout()
                sub = next((s for s in parent.children if s.get('tile') == tid), None)
                if sub is None:
                    sub = bpy.data.collections.new('layout|%s' % tid)
                    sub['tile'] = tid
                    sub['cat'] = 'layout'
                    parent.children.link(sub)
                sub.objects.link(ob2)
                pkg_objs.append(ob2)
                layouts += 1
                n_pkg += 1
        # 2026-11-06（用户实机 rho_fenceshop_int）：只有 `_lod` 的包，LOD 的**高度**也不可信
        # （室内壳顶 86.48 m，建筑顶 84.95 m，冒出去 1.5 m）。按同词干外壳做**竖直套合**：
        # 装得下就贴地板（外壳 zmin + 5 cm），装不下就居中。只作用于「只有 _lod」的包。
        _idx = PM.mlo_index(names=_names(), tile_list=_tiles())
        if pkg_objs and pkg not in _idx and (pkg + '_main') not in _idx and _ov_host is not None:
            _host = _ov_host
            # 🔴 用场景里宿主对象的**真实网格** bbox（不是模型库的 `b`——库 bbox 偏大，
            #    实测 bkdoorshut 库 10.8×10.5 vs 实际 7.4×7.3，拿错就永远对不上）。
            _hname = _names().get(int(_host[0]), '')
            _hobj = bpy.data.objects.get(_hname) if _hname else None
            if _hobj is None and _hname:
                _hn_l = _hname.lower()
                for _o in bpy.data.objects:
                    if _o.name.lower() == _hn_l:
                        _hobj = _o
                        break
            _hb = _obj_mesh_bbox(_hobj) if (_hobj is not None and _hobj.type == 'MESH') else None
            if _hb is None:
                _hm = models.get('0x%08x' % _host[0])
                _hb = _entity_world_bbox(_host, _hm) if _hm else None
                if _hb:
                    # 世界坐标 → 场景局部（x,y 减场景中心）
                    _hb['xmin'] -= cx; _hb['xmax'] -= cx
                    _hb['ymin'] -= cy; _hb['ymax'] -= cy
            _pb = _objs_world_bbox(pkg_objs)
            if _hb and _pb:
                # 水平居中到宿主真实 bbox；竖直装得下贴地板、装不下居中
                _dx = ((_hb['xmin'] + _hb['xmax']) - (_pb['xmin'] + _pb['xmax'])) / 2.0
                _dy = ((_hb['ymin'] + _hb['ymax']) - (_pb['ymin'] + _pb['ymax'])) / 2.0
                # **面积重合率最大**：用真实网格点掩膜直接搜索（用户 2026-11-06 要求）。
                # 墙是 L 形墙带时 bbox 居中不是最优；有真实网格就覆盖上面的 bbox 结果。
                _build_objs = [_hobj] if _hobj is not None else []
                _stem_obj = None
                _stem = PM.stem_exterior(pkg, names=_names(), tile_list=_tiles(), inst=inst)
                if _stem is not None:
                    _sn = _names().get(int(_stem[0]), '')
                    _stem_obj = bpy.data.objects.get(_sn) if _sn else None
                    if _stem_obj is None and _sn:
                        for _o in bpy.data.objects:
                            if _o.name.lower() == _sn.lower():
                                _stem_obj = _o
                                break
                    if _stem_obj is not None and _stem_obj is not _hobj:
                        _build_objs.append(_stem_obj)
                _ov = _overlap_shift(pkg_objs, _hobj, _build_objs)
                if _ov is not None:
                    _dx, _dy, _sc = _ov
                    print('[int] %-24s 面积重合率最优位移 (%+.2f, %+.2f) score %.3f'
                          % (pkg, _dx, _dy, _sc))
                _hroom = _pb['zmax'] - _pb['zmin']
                _fr = _floor_roof_planes(_stem_obj, pkg_objs) if _stem_obj is not None else None
                if _fr:
                    _floor_b, _roof_b, _floor_r = _fr
                    # 竖直：**房间地板面 ↔ 建筑地板面**（主水平面对齐），不再用 bbox 底/顶
                    _dz = _floor_b - _floor_r
                    _top = _pb['zmax'] + _dz
                    if _roof_b is not None and _top > _roof_b - 0.05:
                        print('[int] WARNING %s 对齐地板后顶部 %.2f 高于屋顶面 %.2f（模型尺度差 %.2f m）'
                              % (pkg, _top, _roof_b, _top - (_roof_b - 0.05)))
                elif _hroom <= (_hb['zmax'] - _hb['zmin']):
                    _dz = (_hb['zmin'] + 0.05) - _pb['zmin']
                else:
                    _dz = ((_hb['zmin'] + _hb['zmax']) - (_pb['zmin'] + _pb['zmax'])) / 2.0
                for _o in pkg_objs:
                    _o.location.x += _dx
                    _o.location.y += _dy
                    _o.location.z += _dz
                print('[int] %-24s 套合到宿主：水平 (%+.2f, %+.2f) / 竖直 %+.2f m（仅 _lod 包；宿主 %s）'
                      % (pkg, _dx, _dy, _dz, _names().get(int(_host[0]), '')))
                # 自检：套合后仍超出宿主 bbox 就报警（不静默通过）
                _pb2 = _objs_world_bbox(pkg_objs)
                _out = max(_hb['xmin'] - _pb2['xmin'], _pb2['xmax'] - _hb['xmax'],
                           _hb['ymin'] - _pb2['ymin'], _pb2['ymax'] - _hb['ymax'],
                           _hb['zmin'] - _pb2['zmin'], _pb2['zmax'] - _hb['zmax'])
                if _out > 0.25:
                    print('[int] WARNING %s 套合后仍超出宿主 %.2f m' % (pkg, _out))
        if n_pkg:
            placed += 1
            made += n_pkg
            if verbose:
                print('[int] %-24s %4d 件  @(%.1f, %.1f)' % (pkg, n_pkg, inst[1], inst[2]))

    print('[int] 室内：%d 个包 / %d 个对象（活动区 %.0f×%.0f）'
          % (placed, made, scene['aw'], scene['ah']))
    print('[int] 其中地面贴花 %d 件 → 「室内地面贴花」类（默认隐藏）' % decals)
    print('[int] 其阴影代理壳 %d 件 → 「室内阴影代理」类（默认隐藏，勾开可看；含灯光占位）' % proxies)
    print('[int] 布局白模 %d 件 → 「布局白模」类（默认隐藏，勾开可看）' % layouts)
    print('[int] 远景圈跳过 %d 个包（活动区 P 外，一律不放室内）' % skipped_out)
    if save and made:
        # 🔴 必须 compress=True：`scene_trim` 存出来的是 zstd 压缩的（187 MB），
        # 这里显式写 False 会把整份文件摊成未压缩（922 MB）—— 体积 4 倍，白吓人。
        bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath, compress=True)
        print('[int] saved %s（%.1f MB）'
              % (bpy.data.filepath, os.path.getsize(bpy.data.filepath) / 1e6))
    return made


def _main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument('--scene', required=True)
    a = ap.parse_args(argv)
    import scene_trim
    build(scene_trim.load_scene(a.scene))


if __name__ == '__main__':
    _main()
