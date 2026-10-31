# -*- coding: utf-8 -*-
"""对账：区域裁剪 blend 的分类必须与 v23 大陆同一地块一致（含纠错清单与硬规则）。

    python tools/_check_region.py --tile wild2000_04_02 --audit <manifest jsonl>
    python tools/_check_region.py --tile ... --audit ... --allow-stale-underground

判定：对象数 + 每类计数逐项一致 → PASS。
v23 侧按**当前规则**重算名字层（几何兜底保留存盘类），
再套用同一份纠错清单和硬规则——与 classify_entities 共用 class_rules。

🔴 `--allow-stale-underground`（2026-10-31）：v23 清单里有 2,312 个对象的包围盒
   是**局部坐标**（构建时矩阵没求值），埋深判定因此把一批对象误判成 underground。
   区域侧用当前代码 + 已求值矩阵，是可信的一方。区域检查期用这个开关，把
   「underground 的差额**全部**平移到其他类」解释为旧数据遗留、降级为警告；
   其它任何差额仍然 FAIL。**大陆最终重跑之后必须去掉开关做严检。**
"""
import argparse
import collections
import csv
import json
import os
import re
import sys

import numpy as np

ROOT = r'D:/BrainMaker/大镖客2解包分析'
V23 = os.path.join(ROOT, 'deliverable/blender/continent/manifest_continent_v23.jsonl')
CORR = os.path.join(ROOT, 'deliverable/blender/regions_support/region_corrections.csv')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from class_rules import (  # noqa: E402
    TECHNICAL, classify_name, apply_corrections, apply_hard_rules, load_corrections,
)

_IDX = {}
_TEX = {}

# ---- 与 classify_entities 同口径的几何兜底（对账侧离线复算）----
# H4 高程图常量来自 blender_continent.py（那个模块 import bpy，不能在这里直接用）。
H4 = os.path.join(ROOT, 'work/terrain/H4.npy')
X0, Y0, RES = -7684.0, -8196.0, 4.0
GEOM_MIN_AREA = 10.0
GEOM_MAX_DZ = 1.5
GEOM_MAX_RATIO = 0.06
GEOM_MAX_GAP = 1.0
# 🔴 对账复算要留安全边距：清单里的包围盒只保留两位小数，临界对象会被四舍五入翻面
#    （2026-10-31 实测：l_09ftr_burial_after_* 真实 ratio 略大于 0.06 → 构建期 unknown，
#      用清单值算成 0.0585 → 误判 decal）。只在"明显是贴花"时才翻。
GEOM_SAFE_RATIO = 0.05
GEOM_SAFE_GAP = 0.8
GEOM_SKIP = re.compile(
    r'water|litter|debris|trash|rubbish|'
    r'platform|floor|walkway|stairs?(?![a-z])|deck(?![a-z])|pier(?![a-z])|wharf|dock(?![a-z])',
    re.I)
_H4 = None


def ground_z(x, y):
    global _H4
    if _H4 is None:
        _H4 = np.load(H4)
    r = int(round((y - Y0) / RES))
    c = int(round((x - X0) / RES))
    if 0 <= r < _H4.shape[0] and 0 <= c < _H4.shape[1]:
        return float(_H4[r, c])
    return 0.0


def is_ground_decal(o, name):
    """复算「平/薄/大/贴地 → decal」（只在名字判不出时用，与构建期同阈值）。

    2026-10-31：区域 #20 的 `nopq_15_18_ra_rcross_010bd1` 被区域判 decal、
    v23 存盘 unknown —— 旧 `cross` 规则不再认它，几何兜底必须在对账侧一起算。
    """
    if GEOM_SKIP.search(name.split('/')[-1]):
        return False
    bb = o.get('bb')
    if not bb or len(bb) != 6:
        return False
    x0, y0, z0, x1, y1, z1 = bb
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    if dx * dy < GEOM_MIN_AREA:
        return False
    if dz > GEOM_MAX_DZ:
        return False
    if dz / max(dx, dy, 1e-6) > GEOM_SAFE_RATIO:
        return False
    g = ground_z((x0 + x1) / 2, (y0 + y1) / 2)
    if abs(z0 - g) > GEOM_SAFE_GAP:
        return False
    return True


def model_textures(h):
    if h in _TEX:
        return _TEX[h]
    if not _IDX:
        try:
            _IDX.update(json.load(open(os.path.join(ROOT, 'assets/lib_native/index.json'), encoding='utf-8')))
        except Exception:
            _IDX['models'] = {}
            _IDX['tex'] = []
    out = []
    e = (_IDX.get('models') or {}).get(h)
    if e:
        tex = _IDX.get('tex') or []
        for s in (e.get('s') or []):
            tid = s[0]
            if isinstance(tid, int) and 0 <= tid < len(tex):
                out.append(tex[tid].get('n') or '')
    _TEX[h] = out
    return out


def counts(jsonl, tid=None, corr=()):
    c = collections.Counter()
    n = 0
    with open(jsonl, encoding='utf-8') as f:
        for line in f:
            o = json.loads(line)
            if '_meta' in o:
                continue
            if not o.get('tid'):
                continue
            if tid is not None and o.get('tid') != tid:
                continue
            n += 1
            k = o.get('c') or 'unknown'
            if tid is not None:
                nm = o.get('n') or ''
                # 🔴 先去掉 Blender 重名后缀（.001 / .1000）：构建期 classify_entities 用的是
                #    names.txt 的正名，对账侧带着后缀会让 `$` 锚定的纠错正则漏匹配
                #    （2026-10-31 实测：19 个 rho_*/brokensticks_* 因此对不上）
                nm = re.sub(r'\.\d{3,}$', '', nm)
                tag = o.get('tag') or ''
                # 构建期的属性兜底（与 classify_entities 一致）：地形块 / 停放件
                if tag == 'terrain_cell':
                    k = 'terrain_cell'
                elif tag == 'parked_offmap':
                    k = 'underground'
                else:
                    kn = classify_name(nm)
                    # 名字层能判定、且不是技术类 → 用当前规则；unknown 时保留存盘类
                    if kn != 'unknown' and k not in TECHNICAL:
                        k = kn
                    elif kn == 'unknown' and k not in ('underground', 'decal'):
                        # 几何兜底只可能产出 underground / decal；其余存盘类都是旧规则遗留
                        # （2026-10-31：旧 `cross` 规则把 n_07__river_cross 留在 rail）
                        k = 'unknown'
                    # 几何兜底补判 decal（v23 存盘值可能来自旧规则，名字已判不出）
                    if k == 'unknown' and is_ground_decal(o, nm):
                        k = 'decal'
                txs = list(o.get('t') or []) + model_textures(o.get('h'))
                k = apply_corrections(k, nm, txs, corr, verbose=False)
                k = apply_hard_rules(k, nm)
            c[k] += 1
    return n, c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tile', required=True)
    ap.add_argument('--audit', required=True, help='审计块的 manifest_*.jsonl')
    ap.add_argument('--v23', default=V23)
    ap.add_argument('--corrections', default=CORR)
    ap.add_argument('--allow-stale-underground', action='store_true',
                    help='把「v23 多出的 underground 恰好等于其他类多出的总量」降级为警告'
                         '（v23 有一批对象包围盒是局部坐标，埋深判定失真）')
    a = ap.parse_args()

    corr = load_corrections(a.corrections)
    print('[check] baseline = %s' % os.path.basename(a.v23))
    n0, c0 = counts(a.v23, a.tile, corr)
    n1, c1 = counts(a.audit)
    print('[check] tile=%s  v23: %d 对象  audit: %d 对象' % (a.tile, n0, n1))
    keys = sorted(set(c0) | set(c1))
    d_ug = c0.get('underground', 0) - c1.get('underground', 0)
    surplus_other = sum(max(0, c1.get(k, 0) - c0.get(k, 0)) for k in keys if k != 'underground')
    deficit_other = sum(max(0, c0.get(k, 0) - c1.get(k, 0)) for k in keys if k != 'underground')
    stale_ok = bool(a.allow_stale_underground and d_ug > 0
                    and surplus_other == d_ug and deficit_other == 0)
    bad = []
    for k in keys:
        if c0.get(k, 0) == c1.get(k, 0):
            continue
        if stale_ok and (k == 'underground' or c1.get(k, 0) > c0.get(k, 0)):
            continue
        bad.append((k, c0.get(k, 0), c1.get(k, 0)))
    if n0 != n1 or bad:
        print('[check] FAIL')
        for k, x, y in bad:
            print('   %-14s v23=%6d audit=%6d' % (k, x, y))
        raise SystemExit(1)
    if stale_ok:
        print('[check] 警告：v23 多出 underground %d 个（旧包围盒失真），已按其他类平移核对' % d_ug)
    print('[check] PASS（对象数与 %d 类计数逐项一致）' % len(keys))


if __name__ == '__main__':
    main()
