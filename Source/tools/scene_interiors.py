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

_NAMES = None
_TILES = None


def _names():
    global _NAMES
    if _NAMES is None:
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
    ent = bpy.data.collections.get('ENTITIES')
    parent = ent if ent is not None else bpy.context.scene.collection
    c = bpy.data.collections.get(COL)
    if c is None:
        c = bpy.data.collections.new(COL)
        parent.children.link(c)
    return c


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
    ax0, ay0 = cx - scene['aw'] / 2, cy - scene['ah'] / 2
    ax1, ay1 = cx + scene['aw'] / 2, cy + scene['ah'] / 2

    col = _col()
    matcache, meshcache = {}, {}
    placed = made = 0
    for rec in ok:
        pkg = rec['pkg']
        inst = find_mlo(pkg)
        if inst is None:
            continue
        if not (ax0 <= inst[1] <= ax1 and ay0 <= inst[2] <= ay1):
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

        # 世界 → 场景局部；四元数取共轭（与 instantiate_interiors / willard 同口径）
        P = Vector((inst[1] - cx, inst[2] - cy, inst[3]))
        q = Quaternion((inst[7], -inst[4], -inst[5], -inst[6]))

        n_pkg = 0
        for e in ents:
            hx = hex(e['h'])
            m = models.get(hx)
            if not m:
                continue
            try:
                me = BC.load_model_mesh(LIB, m, texmeta, matcache, meshcache)
            except Exception:
                continue
            if not me:
                continue
            ob = bpy.data.objects.new('i_%s' % hx[2:], me)
            ob.location = P + (q @ Vector(e['p']))
            ob.rotation_mode = 'QUATERNION'
            lq = Quaternion((e['q'][3], -e['q'][0], -e['q'][1], -e['q'][2]))
            ob.rotation_quaternion = q @ lq
            ob['cls_key'] = 'part'
            ob['int_pkg'] = pkg
            # 子集合按地块分（与世界坐标一致，重建/裁剪时对数方便）
            tid = tour._tile_of(ob.location.x + cx, ob.location.y + cy)
            sub = next((s for s in col.children if s.get('tile') == tid), None)
            if sub is None:
                sub = bpy.data.collections.new('int|%s' % tid)
                sub['tile'] = tid
                sub['cat'] = 'int'
                col.children.link(sub)
            sub.objects.link(ob)
            n_pkg += 1
        if n_pkg:
            placed += 1
            made += n_pkg
            if verbose:
                print('[int] %-24s %4d 件  @(%.1f, %.1f)' % (pkg, n_pkg, inst[1], inst[2]))

    print('[int] 室内：%d 个包 / %d 个对象（活动区 %.0f×%.0f）'
          % (placed, made, scene['aw'], scene['ah']))
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
