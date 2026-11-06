# -*- coding: utf-8 -*-
"""体检：**室内 MLO 落位**与宿主外壳是否对齐（只读、不依赖 Blender）。

判据（一条就够）：室内 `*_shell` 模型的墙向，应当等于宿主外壳模型的墙向。
墙向用「水平长边的 4θ 矢量平均」估计（墙向周期 90°，长度加权），并给出纯度过滤噪声模型。

对每个 `*_int` 包：
    world_shell = local_shell + MLO实例 yaw        ← 实例**不取共轭**（2026-11-05 实锤）
    world_ext   = local_ext   - 外壳实例 yaw       ← 普通 ymap 实体**取共轭**（沿用原口径）
    Δ = wrap90(world_shell - world_ext)

输出 PASS / FAIL：
    · 可判样本（有 shell、两侧纯度 ≥ 0.85、|实例 yaw| ≥ 2°）里
      |Δ| ≤ 2° 的比例 ≥ 85%  → PASS
    · 同时跑一条**负面测试**（把实例四元数改回取共轭），必须掉到 <20% 才算检查有分辨力。

用法：
    python tools/_check_interior_align.py            # 全量
    python tools/_check_interior_align.py --only val # 只看前缀
    python tools/_check_interior_align.py -v         # 打印每个包
"""
import os
import sys
import json
import glob
import math
import argparse

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get('RDR2_ROOT') or r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, HERE)

import parse_interior_mlo as PM   # noqa: E402
from rdr2_mdl import load_mdl     # noqa: E402

LIB = os.path.join(ROOT, 'assets/lib_native')
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
PACKS = os.path.join(ROOT, 'raw/all_packs')
AUDIT = os.path.join(ROOT, 'export/world/interior_placement_audit.json')

MIN_PURITY = 0.85
MIN_YAW = 2.0          # 实例转角太小 → 两种口径分不开，不参与判定
TOL = 2.0              # 单包合格线（度）
PASS_RATIO = 0.85

_NAMES = None


def names():
    global _NAMES
    if _NAMES is None:
        _NAMES = {}
        for line in open(os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt'),
                         encoding='latin1', errors='ignore'):
            n = line.strip()
            if n:
                _NAMES.setdefault(PM.joaat(n), n.lower())
    return _NAMES


def tiles():
    out = []
    for p in sorted(glob.glob(os.path.join(TILES, '*.json'))):
        if p.endswith('.bak'):
            continue
        try:
            out.extend(json.load(open(p, encoding='utf-8')))
        except Exception:
            continue
    return out


def yaw(q):
    """(x,y,z,w) → 绕 Z 的 yaw（度）。"""
    x, y, z, w = q
    return math.degrees(math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))


_WD = {}


def wall_dir(h, min_len=0.4, max_verts=80000):
    """模型局部墙向 → (角度 mod 90, 纯度)；纯度低说明不是矩形墙（雕塑/地形/杂物）。"""
    if h in _WD:
        return _WD[h]
    md = load_mdl(h)
    res = None
    if md is not None:
        pos, nrm, uv, idx, tex, vtex = md
        if len(pos) <= max_verts:
            e = np.concatenate([idx[:, [0, 1]], idx[:, [1, 2]], idx[:, [2, 0]]], axis=0)
            e = np.unique(np.sort(e, axis=1), axis=0)
            d = pos[e[:, 1]] - pos[e[:, 0]]
            ln = np.linalg.norm(d, axis=1)
            m = (ln > min_len) & (np.abs(d[:, 2]) < 0.05 * ln)
            if m.sum() >= 20:
                th = np.arctan2(d[m, 1], d[m, 0])
                w = ln[m]
                v = (w * np.exp(4j * th)).sum()
                res = (math.degrees(np.angle(v)) / 4.0, float(abs(v) / w.sum()))
    _WD[h] = res
    return res


def wrap90(a):
    return (a + 45.0) % 90.0 - 45.0


def collect(only=''):
    nm = names()
    tl = tiles()
    # 宿主名 → 实例（与构建同一份索引实现）
    byname = PM.build_mlo_index(nm, tl)
    audit = {x['pkg']: x for x in json.load(open(AUDIT, encoding='utf-8'))}

    pkgs = sorted(d for d in os.listdir(PACKS) if d.endswith('_int'))
    if only:
        pre = tuple(x.strip() for x in only.split(',') if x.strip())
        pkgs = [p for p in pkgs if p.startswith(pre)]

    rows, skipped = [], 0
    for pkg in pkgs:
        yp = os.path.join(PACKS, pkg, pkg + '.ytyp')
        if not os.path.exists(yp):
            c = glob.glob(os.path.join(PACKS, pkg, '*.ytyp'))
            if not c:
                continue
            yp = c[0]
        # 唯一口径：与构建/审计同一个函数（精确 → _main → _lod）
        inst = PM.find_mlo_instance(pkg, names=nm, tile_list=tl)
        if inst is None:
            skipped += 1
            continue
        iy = yaw(inst[4:8])
        if abs(iy) < MIN_YAW:
            skipped += 1
            continue
        try:
            ents = PM.parse_ytyp(yp)
        except Exception:
            skipped += 1
            continue
        shell = None
        for e in ents:
            n = nm.get(e['h'], '')
            if n.endswith('_shell') or '_int_shell' in n:
                shell = e
                break
        if shell is None:
            skipped += 1
            continue
        sa = wall_dir(shell['h'])
        if sa is None or sa[1] < MIN_PURITY:
            skipped += 1
            continue
        host = (audit.get(pkg) or {}).get('host') or ''
        he = byname.get(host)
        if he is None:
            skipped += 1
            continue
        ea = wall_dir(he[0])
        if ea is None or ea[1] < MIN_PURITY:
            skipped += 1
            continue
        ey = yaw(he[4:8])
        # 生产口径：实例直接用；外壳取共轭
        d_ok = wrap90((sa[0] + iy) - (ea[0] - ey))
        # 负面测试：实例也取共轭（2026-11-05 前的写法）
        d_bad = wrap90((sa[0] - iy) - (ea[0] - ey))
        rows.append({'pkg': pkg, 'host': host, 'i_local': sa[0], 'i_yaw': iy,
                     'e_local': ea[0], 'e_yaw': ey, 'd': d_ok, 'd_bad': d_bad})
    return rows, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    ap.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args()

    rows, skipped = collect(a.only)
    if not rows:
        print('[check] 无可判样本（universe 里没有可用的 shell/宿主对）')
        print('[check] 结论：SKIP')
        return 2

    d = np.abs(np.array([r['d'] for r in rows]))
    db = np.abs(np.array([r['d_bad'] for r in rows]))
    ok = (d <= TOL).mean()
    bad_ok = (db <= TOL).mean()

    if a.verbose:
        print('%-26s %-26s %8s %8s %8s %8s %7s %7s'
              % ('包', '宿主', 'i_local', 'i_yaw', 'e_local', 'e_yaw', 'Δ', 'Δ(旧)'))
        for r in sorted(rows, key=lambda r: -abs(r['d'])):
            print('%-26s %-26s %+8.2f %+8.2f %+8.2f %+8.2f %+7.2f %+7.2f'
                  % (r['pkg'], r['host'], r['i_local'], r['i_yaw'],
                     r['e_local'], r['e_yaw'], r['d'], r['d_bad']))

    print('[check] 可判样本 %d（跳过 %d 个包：无实例/无 shell/纯度不足/转角<%.0f°）'
          % (len(rows), skipped, MIN_YAW))
    print('[check] 现口径 |Δ| 中位 %.2f° / 均值 %.2f° / 最大 %.2f° ；≤%.0f° 占 %.0f%%'
          % (np.median(d), d.mean(), d.max(), TOL, 100 * ok))
    print('[check] 负面测试（实例取共轭）|Δ| 中位 %.2f° ；≤%.0f° 占 %.0f%%（必须 <20%%）'
          % (np.median(db), TOL, 100 * bad_ok))

    passed = ok >= PASS_RATIO and bad_ok < 0.20
    if passed:
        print('[check] 结论：PASS —— MLO 实例四元数按「不取共轭」装配，室内与外壳墙向一致')
        return 0
    print('[check] 结论：FAIL —— 见上表最差的几行（先查宿主是否被审计表认错）')
    return 1


if __name__ == '__main__':
    sys.exit(main())
