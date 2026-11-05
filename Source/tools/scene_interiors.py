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
PROXY_NAME = re.compile(r'(proxy|shadow|shdw|shd_|shad_)', re.I)

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
    """包名 → MLO 实例实体 [hash, x, y, z, qx, qy, qz, qw]。"""
    names = _names()
    want = (pkg, pkg + '_lod', pkg + '_main')
    for e in _tiles():
        n = names.get(e[0])
        if n and n.split('/')[-1] in want:
            return e
    return None


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
        q = Quaternion((inst[7], inst[4], inst[5], inst[6]))

        n_pkg = 0
        for e in ents:
            # 🔴 必须补零成 0x%08x：模型库的键是 8 位。用 hex() 时 0x00418731 会变成
            # `0x418731`，查不到 ⇒ 静默丢掉。实测室内件里 **2,597 / 47,791** 的哈希有前导零，
            # 其中 **2,495 个模型其实在库里**（家具/门/碎石堆…），一直被吞（最高原则 §6.4）。
            hx = '0x%08x' % e['h']
            m = models.get(hx)
            if not m:
                continue
            try:
                # 2026-11-05：传模型名 → 无 albedo 的件按名字自动配色（ntex_palette）。
                _mn = _names().get(int(hx, 16), '')
                me = BC.load_model_mesh(LIB, m, texmeta, matcache, meshcache, name_hint=_mn)
            except Exception:
                continue
            if not me:
                continue
            ob = bpy.data.objects.new('i_%s' % hx[2:], me)
            ob.location = P + (q @ Vector(e['p']))
            ob.rotation_mode = 'QUATERNION'
            lq = Quaternion((e['q'][3], -e['q'][0], -e['q'][1], -e['q'][2]))
            ob.rotation_quaternion = q @ lq
            is_dec = _is_decal(m, texmeta)
            # 名字规则：`i_<hash>` 判不出是什么件，只能问模型名（`<包>_shadow` 这类）。
            is_proxy = bool(PROXY_NAME.search(_mn or ''))
            key = 'int_proxy' if is_proxy else ('int_decal' if is_dec else 'part')
            ob['cls_key'] = key
            ob['int_pkg'] = pkg
            # 子集合按地块分（与世界坐标一致，重建/裁剪时对数方便）
            tid = tour._tile_of(ob.location.x + cx, ob.location.y + cy)
            parent = _col_proxy() if is_proxy else (_col_decal() if is_dec else col)
            tag = 'int_proxy' if is_proxy else ('int_decal' if is_dec else 'int')
            sub = next((s for s in parent.children if s.get('tile') == tid), None)
            if sub is None:
                sub = bpy.data.collections.new('%s|%s' % (tag, tid))
                sub['tile'] = tid
                sub['cat'] = key
                parent.children.link(sub)
            sub.objects.link(ob)
            if is_proxy:
                proxies += 1
            if is_dec:
                decals += 1
            n_pkg += 1
        if n_pkg:
            placed += 1
            made += n_pkg
            if verbose:
                print('[int] %-24s %4d 件  @(%.1f, %.1f)' % (pkg, n_pkg, inst[1], inst[2]))

    print('[int] 室内：%d 个包 / %d 个对象（活动区 %.0f×%.0f）'
          % (placed, made, scene['aw'], scene['ah']))
    print('[int] 其中地面贴花 %d 件 → 「室内地面贴花」类（默认隐藏）' % decals)
    print('[int] 其阴影代理壳 %d 件 → 「室内阴影代理」类（默认隐藏，勾开可看）' % proxies)
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
