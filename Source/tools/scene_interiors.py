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

# ── 室内对位台账（2026-11-06 用户要求："单独列一个 csv 记录每个据点每个建筑的情况，方便调整或反查"）──
# ① 自动生成（**生成物，禁止手改**）：每张场景的每个室内包一行 —— 朝向来源 / 位移 / 贴合方式 / 越界。
#    放仓库 docs 下（2026-11-06 用户要求：这份表要进 git，方便反查"这栋为什么歪了"）。
FIT_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'docs', '世界与地编', 'interior_fit.csv')
# ② 人工修正（**手维护**）：pkg,dx,dy,dz,note —— 在自动结果之上再叠加，用来微调单个建筑。
FIT_OVERRIDES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'docs', '世界与地编', 'interior_fit_overrides.csv')


def _load_fit_overrides():
    """→ {pkg: (dx, dy, dz, yaw|None)} —— **绝对覆盖**：文件里写了，就完全用它的值，不再自动套合。

    `yaw` 是**绝对朝向（度）**：填了就把整包绕**包原点（MLO 实例位置）的竖轴**转到这个角度；
    留空 = 保留自动算出的朝向。位置与朝向都是整包一起变（见 `_apply_package_fit`）。
    """
    out = {}
    if not os.path.exists(FIT_OVERRIDES):
        return out
    try:
        import csv as _csv
        with open(FIT_OVERRIDES, encoding='utf-8-sig', newline='') as f:
            for r in _csv.DictReader(f):
                p = (r.get('pkg') or '').strip()
                if not p or p.startswith('#'):
                    continue
                try:
                    yaw = r.get('yaw')
                    yaw = float(yaw) if (yaw or '').strip() else None
                    out[p] = (float(r.get('dx') or 0), float(r.get('dy') or 0),
                              float(r.get('dz') or 0), yaw)
                except Exception:
                    continue
    except Exception as e:
        print('[int] 读修正表失败（忽略）：%s' % e)
    return out


def _apply_package_fit(pkg_objs, pivot, ddx, ddy, ddz, dyaw_deg):
    """整包一起动：先绕 `pivot` 的**竖轴（世界 Z）**转 `dyaw_deg`，再平移。

    `pivot` = MLO 实例位置（场景局部坐标）。这是"包原点"，不是每个件自己的原点 ——
    所以所有件保持相对关系，像刚体一样旋转。
    """
    if abs(dyaw_deg) > 1e-9:
        rad = math.radians(dyaw_deg) * 0.5
        qz = Quaternion((math.cos(rad), 0.0, 0.0, math.sin(rad)))
        pv = Vector((pivot[0], pivot[1], pivot[2]))
        for o in pkg_objs:
            rel = o.location - pv
            o.location = pv + (qz @ rel)
            o.rotation_quaternion = qz @ o.rotation_quaternion
    for o in pkg_objs:
        o.location.x += ddx
        o.location.y += ddy
        o.location.z += ddz


def _append_fit_override(pkg, dx, dy, dz, note):
    """把某个包的**当前自动结果**追加进修正表（该包已有行就跳过，绝不覆盖用户改过的行）。

    直接以追加模式写一行，**不重写整个文件** —— 否则注释行会被 csv 读成数据再写回去、
    变成 `# 说明,,,,` 的碎片（2026-11-06 实测踩过）。
    """
    try:
        if os.path.exists(FIT_OVERRIDES):
            import csv as _csv
            with open(FIT_OVERRIDES, encoding='utf-8-sig', newline='') as f:
                for r in _csv.DictReader(f):
                    if (r.get('pkg') or '').strip() == pkg:
                        return
        os.makedirs(os.path.dirname(FIT_OVERRIDES), exist_ok=True)
        write_header = not os.path.exists(FIT_OVERRIDES)
        with open(FIT_OVERRIDES, 'a', encoding='utf-8', newline='') as f:
            if write_header:
                f.write('pkg,dx,dy,dz,note\n')
            f.write('%s,%.2f,%.2f,%.2f,%s\n' % (pkg, dx, dy, dz, note))
    except Exception as e:
        print('[int] 写修正表失败（忽略）：%s' % e)


def _write_fit_rows(scene_id, rows):
    """把这场景的行写进台账：删掉本场景旧行，再追加新行（其余场景原样保留）。"""
    import csv as _csv
    keep = []
    if os.path.exists(FIT_CSV):
        try:
            with open(FIT_CSV, encoding='utf-8-sig', newline='') as f:
                keep = [r for r in _csv.DictReader(f) if r.get('scene') != scene_id]
        except Exception:
            keep = []
    fields = ['scene', 'pkg', 'host', 'orient', 'lod_yaw', 'yaw', 'dx', 'dy', 'dz',
              'fit', 'clear_m', 'objects']
    os.makedirs(os.path.dirname(FIT_CSV), exist_ok=True)
    with open(FIT_CSV, 'w', encoding='utf-8', newline='') as f:
        w = _csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        w.writeheader()
        for r in sorted(keep, key=lambda x: (x.get('scene') or '', x.get('pkg') or '')):
            w.writerow({k: r.get(k, '') for k in fields})
        for r in sorted(rows, key=lambda x: x['pkg']):
            w.writerow(r)
    print('[int] 对位台账已更新：%s（本场景 %d 行）' % (FIT_CSV, len(rows)))
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

# 有 `*_fakeint`（游戏自带的房间占位）时，室内顶相对占位件顶的余量（米）。
# 🔴 2026-11-06 用户实机定案：`cor_factb_int` 手动把原点调到 121.20 目视合适 ⇒ 余量 0.00。
#    想整体再降，就把这个数调大（每 0.1 = 降 10 cm）。
FAKEINT_TOP_MARGIN = 0.00


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


def _roof_clearance_drop(room_objs, build_obj, margin=0.10, cell=1.0):
    """室内顶到屋顶外时，需要**整体下移多少**（米，≥0）。

    🔴 2026-11-06 用户原则（写死）：**室内件任意一个点往上，都必须能找到建筑的一个点** ——
       否则就是"透出屋顶"。做法：
       ① 把建筑顶点按 1 m 网格分箱，取每格（含 8 邻域）的**最高 z** 当作该处天花板上限；
       ② 室内每个顶点超过上限 `margin` 的部分都是违规，取最大违规量作为下移量。
    返回 0 表示没顶出去。
    """
    try:
        import numpy as np
    except Exception:
        return 0.0
    if build_obj is None or build_obj.type != 'MESH':
        return 0.0
    bm = build_obj.matrix_basis
    bv = np.array([(bm @ v.co)[:] for v in build_obj.data.vertices], dtype=np.float64)
    if len(bv) < 50:
        return 0.0
    rm = [(o.matrix_basis, np.array([(o.matrix_basis @ v.co)[:] for v in o.data.vertices],
                                    dtype=np.float64))
          for o in room_objs if o is not None and o.type == 'MESH' and len(o.data.vertices)]
    if not rm:
        return 0.0
    # 建筑顶点分箱：格子 → 最高 z
    bx = np.floor(bv[:, 0] / cell).astype(np.int64)
    by = np.floor(bv[:, 1] / cell).astype(np.int64)
    cap = {}
    for x, y, z in zip(bx.tolist(), by.tolist(), bv[:, 2].tolist()):
        if z > cap.get((x, y), -1e9):
            cap[(x, y)] = z
    if not cap:
        return 0.0
    overs = []
    for _m, rv in rm:
        if not len(rv):
            continue
        rx = np.floor(rv[:, 0] / cell).astype(np.int64).tolist()
        ry = np.floor(rv[:, 1] / cell).astype(np.int64).tolist()
        rz = rv[:, 2].tolist()
        for x, y, z in zip(rx, ry, rz):
            c = -1e9
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    v = cap.get((x + dx, y + dy))
                    if v is not None and v > c:
                        c = v
            if c < -1e8:
                continue                     # 该处建筑没有采样点，不敢判断
            over = z - (c - margin)
            if over > 0:
                overs.append(over)
    if not overs:
        return 0.0
    # 🔴 2026-11-06（用户："下沉太多了"）：取 **99 分位**而不是最大值 ——
    #   包里的单个高道具（烟囱/管束）能顶出 0.95 m，按最大值会把整包压下去 1 m，
    #   地板跟着沉，反而更难看。99 分位 = 忽略极个别尖点后的整体越界量。
    if len(overs) < 50:
        return float(max(overs))
    return float(np.percentile(np.asarray(overs), 99))


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
    warn_orient = 0          # 朝向**未校验**的包（只有 LOD 实例且找不到宿主），见下方 WARN
    scene_id = scene.get('id') or scene.get('name') or '?'
    fit_rows = []            # 对位台账（本场景每包一行）
    ovr_fit = _load_fit_overrides()
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
        # 对位台账（每包一行，最后写进 interior_fit.csv）
        _row = {'scene': scene_id, 'pkg': pkg, 'host': '', 'orient': '',
                'lod_yaw': '', 'yaw': '', 'dx': '', 'dy': '', 'dz': '',
                'fit': '', 'clear_m': '', 'objects': ''}
        _raw = PM.pick_instance(_idx0, pkg)
        _row['lod_yaw'] = '%.2f' % _inst_yaw(_raw) if _raw else ''
        _row['orient'] = ('exact' if pkg in _idx0 else
                          ('main' if (pkg + '_main') in _idx0 else 'lod_only'))
        _ov_host = None
        if pkg not in _idx0 and (pkg + '_main') not in _idx0:
            # 宿主优先级：审计表的 host（真正承载房间的墙体/构件）→ `host_for`（显式对位或同词干外壳）。
            # 🔴 2026-11-06（用户实机 `cor.blend`）：这里原来只认「审计 host + 同词干」，
            #   不认识 `HOST_OVERRIDE` ⇒ `cor_factb_int` 的 `_ov_host` 一直是 None，
            #   于是**朝向被修好了、水平/竖直径向套合却整段没跑**，室内壳浮在厂房外面。
            _hn = (rec.get('host') or '').lower()
            _ov_host = _idx0.get(_hn) if _hn else None
            if _ov_host is None:
                _ov_host = PM.host_for(pkg, _idx0, inst)
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
            else:
                # 🔴 2026-11-06（用户："难道每次都要我肉眼检查？"）：**静默用 LOD 朝向 = 定时炸弹**
                #   实测 `cor_factb_int` 就是这样歪了 80° 而日志全绿（审计 host 空、同词干也匹配不到）。
                #   只有「连宿主都找不到」才报 —— 找得到宿主时 `find_mlo_instance` 已经改过朝向了
                #   （`cor_factb_int` 走 HOST_OVERRIDE，这里没有 *_shell 件也不会误报）。
                if PM.host_for(pkg, _idx0, inst) is None:
                    _why = ('找不到宿主外壳（审计 host 为空、同词干也没匹配）'
                            if _ov_host is None else '室内包里找不到 *_shell 件')
                    print('[int][WARN] %-24s 只有 LOD 实例、%s ⇒ 朝向**未校验**（当前 %+.1f°，LOD 朝向不可信）'
                          % (pkg, _why, _inst_yaw(inst)))
                    warn_orient += 1
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

            # 🔴 2026-11-06（用户："既然知道模型名，为什么 blend 里还是哈希名？可读性太差"）：
            #   以前一律 `i_<hash>`。现在：**查得到模型名就用模型名**（`cor_factb_shell_int`），
            #   查不到才退回 `i_<hash>`。哈希仍写进 `ob['hash']`，按哈希反查不受影响。
            _nm_clean = re.sub(r'[\\/]', '_', (_mn or '').strip())
            _obname = _nm_clean or ('i_%s' % hx[2:])
            if me_real:
                ob = bpy.data.objects.new(_obname, me_real)
                ob['hash'] = hx
                ob['int_model'] = _mn or ''
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
                ob2 = bpy.data.objects.new(_obname + '_lay', me_lay)
                ob2['hash'] = hx
                ob2['int_model'] = _mn or ''
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
        _ovr = ovr_fit.get(pkg)          # 人工修正表：**绝对覆盖**（有值就用它，不再自动套合）
        if pkg_objs and _ovr is not None:
            _dx, _dy, _dz, _yaw_abs = _ovr
            # 旋转的**中心轴** = 包原点（MLO 实例位置的竖轴），整包刚体式一起转。
            _pivot = (inst[1] - cx, inst[2] - cy, inst[3])
            _dyaw = 0.0 if _yaw_abs is None else (_yaw_abs - _inst_yaw(inst))
            _apply_package_fit(pkg_objs, _pivot, _dx, _dy, _dz, _dyaw)
            _row['dx'], _row['dy'], _row['dz'] = '%.2f' % _dx, '%.2f' % _dy, '%.2f' % _dz
            _row['fit'] = 'manual'
            _h_ov = PM.host_for(pkg, _idx, inst)
            _row['host'] = _names().get(int(_h_ov[0]), '') if _h_ov else '—'
            if _yaw_abs is not None:
                _row['yaw'] = '%.2f' % _yaw_abs
                inst = list(inst)
                _r = math.radians(_yaw_abs) * 0.5
                inst[4], inst[5], inst[6], inst[7] = 0.0, 0.0, math.sin(_r), math.cos(_r)
            print('[int] %-24s 按人工修正表绝对定位 (%+.2f, %+.2f, %+.2f)%s'
                  % (pkg, _dx, _dy, _dz,
                     ('，朝向 %.2f°（绕包原点竖轴整包转）' % _yaw_abs) if _yaw_abs is not None else ''))
        elif pkg_objs and pkg not in _idx and (pkg + '_main') not in _idx and _ov_host is not None:
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
                _stem = PM.host_for(pkg, _idx, inst)
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
                # 🔴 2026-11-06（用户实机 `cor.blend`）：**优先拿游戏自带的 `*_fakeint` 当贴合目标** ——
                #   那是 Rockstar 标记「房间应该摆在哪」的占位件（`cor_factoryes_fakeint`），
                #   比厂房外壳准得多。实测只用外壳时 X 方向差 5.2 m（外壳贴着整栋，房间只在其中一跨）。
                _wall_target = _hobj
                _tot_dx = _tot_dy = 0.0     # 记录**总位移**（对中 + 求解器），供台账/人工修正表用
                _fi = bpy.data.objects.get((_hname or '') + '_fakeint')
                _fi_box = None
                if _fi is not None and _fi.type == 'MESH':
                    _wall_target = _fi
                    if _fi is not _hobj:
                        _build_objs.append(_fi)
                    # 🔴 先按 fakeint 的**包围盒对中**粗定位，再交给求解器微调。
                    #   求解器搜索半径只有 ±1.5 m（`span`），实测这里需要 5.2 m，
                    #   只靠它会原地不动（score 从 5.6 涨到 8.8 但位置几乎没变）。
                    _fb = _obj_mesh_bbox(_fi)
                    if _fb:
                        _fi_box = _fb
                        _cdx = ((_fb['xmin'] + _fb['xmax']) - (_pb['xmin'] + _pb['xmax'])) / 2.0
                        _cdy = ((_fb['ymin'] + _fb['ymax']) - (_pb['ymin'] + _pb['ymax'])) / 2.0
                        _tot_dx += _cdx
                        _tot_dy += _cdy
                        for _o in pkg_objs:
                            _o.location.x += _cdx
                            _o.location.y += _cdy
                        bpy.context.view_layer.update()
                        _pb = _objs_world_bbox(pkg_objs) or _pb
                        print('[int] %-24s 贴合目标改用 %s（游戏自带的假室内占位）：先对中 (%+.2f, %+.2f)'
                              % (pkg, _fi.name, _cdx, _cdy))
                _ov = _overlap_shift(pkg_objs, _wall_target, _build_objs)
                if _ov is not None:
                    _dx, _dy, _sc = _ov
                    print('[int] %-24s 面积重合率最优位移 (%+.2f, %+.2f) score %.3f'
                          % (pkg, _dx, _dy, _sc))
                _hroom = _pb['zmax'] - _pb['zmin']
                _fr = _floor_roof_planes(_stem_obj, pkg_objs) if _stem_obj is not None else None
                if _fi_box is not None:
                    # 🔴 2026-11-06（用户实机三轮回合定案）：**顶部对齐 fakeint**，
                    #   余量 = 0（室内顶 = 占位件顶）。用户手动把 `i_8435e65c` 的原点从 120.90
                    #   调到 **121.20** 后目视"差不多了"，换算成这里的余量就是 0.00。
                    #   注意：机械判据（`_roof_clearance_drop`）在这档会报更多越界顶点
                    #   （0.17% / 最深 0.76 m），但都在屋顶板厚度内 —— **以实机目视为准**。
                    _dz = (_fi_box['zmax'] - FAKEINT_TOP_MARGIN) - _pb['zmax']
                    print('[int] %-24s 顶部对齐 %s：室内顶 = 占位顶 −%.2f m，位移 %+.2f m'
                          % (pkg, _fi.name, FAKEINT_TOP_MARGIN, _dz))
                elif _fr:
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
                # 🔴 用户原则（2026-11-06）：**室内件任意一点往上，都必须能碰到建筑的点**。
                #   这里只**报警不自动下移** —— 实测按最大值要下移 0.95 m（用户："下沉太多"），
                #   按 99 分位也要 0.8 m；而顶部对齐 fakeint 后只差一点点。自动下移会把地板带沉。
                _drop = _roof_clearance_drop(pkg_objs, _hobj)
                if _drop > 0.05:
                    print('[int] WARNING %-20s 仍有 %.2f m 顶点高于建筑（尖角可能埋进屋顶板厚里；'
                          '要强压就调大 FAKEINT_TOP_MARGIN）' % (pkg, _drop))
                _row['host'] = _names().get(int(_host[0]), '')
                _row['dx'] = '%.2f' % (_tot_dx + _dx)
                _row['dy'] = '%.2f' % (_tot_dy + _dy)
                _row['dz'] = '%.2f' % _dz
                _row['clear_m'] = '%.2f' % _drop
                _row['fit'] = ('fakeint' if _fi_box is not None
                               else ('floor' if _fr else 'bbox'))
                _row['orient'] = ('lod+host' if PM.host_for(pkg, _idx, inst) else 'lod_only')
                print('[int] %-24s 套合到宿主：水平 (%+.2f, %+.2f) / 竖直 %+.2f m（仅 _lod 包；宿主 %s）'
                      % (pkg, _dx, _dy, _dz, _names().get(int(_host[0]), '')))
                # 自检：套合后仍超出宿主 bbox 就报警（不静默通过）
                # ⚠️ 只看**房间壳**，不看整包 317 件 —— 实测 `cor_factb_details05`（32×31×8.7 m 的
                #    管线/设备细节件）本来就该伸到厂房外 10.7 m，拿它当判据会天天误报；
                #    房间壳 `i_8435e65c` 实际在宿主内 0.85 m。
                bpy.context.view_layer.update()
                _chk = pkg_objs
                if _shell_h is not None:
                    _sn2 = _names().get(int(_shell_h)) or ''
                    _so = bpy.data.objects.get(_sn2) if _sn2 else None
                    if _so is not None:
                        _chk = [_so]
                # 逐件算越界，**按件数**判：单个细节件伸到房外是正常的
                # （实测 `cor_factb_details05` 越界 10.7 m，但那是管线/设备件），
                # 只有超过总件数 1%（且至少 2 件）才说明整包没套上。
                _out_n = 0
                _out_max = 0.0
                for _o in _chk:
                    _bb = _objs_world_bbox([_o])
                    if not _bb:
                        continue
                    _o1 = max(_hb['xmin'] - _bb['xmin'], _bb['xmax'] - _hb['xmax'],
                              _hb['ymin'] - _bb['ymin'], _bb['ymax'] - _hb['ymax'],
                              _hb['zmin'] - _bb['zmin'], _bb['zmax'] - _hb['zmax'])
                    if _o1 > 0.25:
                        _out_n += 1
                        _out_max = max(_out_max, _o1)
                if _out_n >= 2 and _out_n > max(1, len(_chk) * 0.01):
                    print('[int] WARNING %s 套合后仍有 %d/%d 件超出宿主（最大 %.2f m）'
                          % (pkg, _out_n, len(_chk), _out_max))
        # 记下**构建时的位置**：在 Blender 里手动挪完之后，用 `tools/interior_pkg_tool.py`
        # 就能算出"你挪了多少"，直接生成要粘进修正表的那一行。
        for _o in pkg_objs:
            _o['built_loc'] = tuple(round(v, 4) for v in _o.location)
        # 把**自动对位的结果**搬进人工修正表：只在该包还没有行时追加，
        # 绝不覆盖用户改过的行（用户改过 = 以后永远按他的值走）。
        if pkg_objs and _ovr is None and _row['dx'] not in ('', None):
            try:
                _append_fit_override(pkg, float(_row['dx']), float(_row['dy']),
                                     float(_row['dz']), 'auto:%s' % (_row['fit'] or ''))
            except Exception:
                pass
        if n_pkg:
            placed += 1
            made += n_pkg
            _row['yaw'] = '%.2f' % _inst_yaw(inst)
            _row['objects'] = n_pkg
            fit_rows.append(_row)
            if verbose:
                print('[int] %-24s %4d 件  @(%.1f, %.1f)' % (pkg, n_pkg, inst[1], inst[2]))

    print('[int] 室内：%d 个包 / %d 个对象（活动区 %.0f×%.0f）'
          % (placed, made, scene['aw'], scene['ah']))
    print('[int] 其中地面贴花 %d 件 → 「室内地面贴花」类（默认隐藏）' % decals)
    print('[int] 其阴影代理壳 %d 件 → 「室内阴影代理」类（默认隐藏，勾开可看；含灯光占位）' % proxies)
    print('[int] 布局白模 %d 件 → 「布局白模」类（默认隐藏，勾开可看）' % layouts)
    print('[int] 远景圈跳过 %d 个包（活动区 P 外，一律不放室内）' % skipped_out)
    if warn_orient:
        print('[int][WARN] 共 %d 个包的室内朝向**未校验**（只有 LOD 实例且找不到宿主）'
              ' —— 这批包必须人工确认或补 HOST_OVERRIDE' % warn_orient)
    try:
        _write_fit_rows(scene_id, fit_rows)
    except Exception as e:
        print('[int] 对位台账写入失败（不影响场景）：%s' % e)
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
