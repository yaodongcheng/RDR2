# -*- coding: utf-8 -*-
"""抽查：把室内布局按「MLO 实例变换」摆到世界，看是否落在宿主建筑里。

输出每包的「室内 bbox 是否被最近的大建筑 bbox 包住」+ 四边间隙。
用法：uv run python tools/audit_interior_placement.py [--n 8]
"""
import os, sys, json, glob, math, re, argparse, itertools
# 数据工程（raw/export/work/assets）不在仓库里 —— 与其它工具同一口径，可用 RDR2_ROOT 覆盖
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get('RDR2_ROOT') or r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, HERE)
import numpy as np
import parse_interior_mlo as PM

LIB = os.path.join(ROOT, 'assets/lib_native', 'index.json')
_BAD_NAME = re.compile(r'_(em|decal|dec|d|det|dcl)(\.\d+)?$', re.I)
# LOD/合并块不能当宿主：它们的 bbox 是"整片区域"（实测 banker 的宿主选到了 val_02__em_slod）
_LOD_NAME = re.compile(r'(_slod|_dslod|_lod\d*|_lod_|_area_slod)(\.\d+)?$', re.I)
# 🔴 2026-11-05：小道具/环境件也不能当宿主。它们的 bbox 会"恰好"包住室内，从而拿到 tier 0
# 把真建筑挤掉，而名字降级压不过 tier。实测：str_mayorshouse_int 的宿主选成了
# `str_03_mayorwindow`（一扇窗）、str_dressingroom_int 选成 `str_03_mill01_ext_dcl`（贴花）、
# str_genst_int 选成 `str_03_debrispile01`（碎石堆）；地形高度块（`j_11__hd_0_-2_3`）与
# 电缆网格（`cablemesh…_hvlit`）同样会中招。⇒ 直接排除，不是降级。
_PROP_NAME = re.compile(
    r'(window|debris|fence|sign|post|lamp|track|road|decal|cablemesh|_hd_0_)|^(out|outg)_', re.I)

# 🔴 2026-11-04：原来 `load_mlo()` 每个包都重读一遍 names.txt + 全部 90 个 tile json
# （278 个包 = 7 GB 重复解析，跑一次要十几分钟）。改成进程内缓存，一次装好复用。
_NAMES = None
_TILES = None


def _names():
    global _NAMES
    if _NAMES is None:
        _NAMES = {}
        for l in open(os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt'),
                      encoding='latin1', errors='ignore'):
            n = l.strip()
            if n:
                _NAMES.setdefault(PM.joaat(n), n.lower())
    return _NAMES


def _tiles():
    """全部 tile 实体合并成一张表（hash/x/y/z/quat…）。只读一次。"""
    global _TILES
    if _TILES is None:
        _TILES = []
        for p in sorted(glob.glob(os.path.join(ROOT, 'export/world/continent/tiles/*.json'))):
            if p.endswith('.bak'):
                continue
            try:
                _TILES.extend(json.load(open(p, encoding='utf-8')))
            except Exception:
                continue
    return _TILES


def load_mlo(pkg):
    names = _names()
    want = [pkg, pkg + '_lod', pkg + '_main']
    for e in _tiles():
        n = names.get(e[0])
        if not n:
            continue
        if n.split('/')[-1] in want:
            return e, names
    return None, names


def quat_mat(q):
    x, y, z, w = q
    return np.array([
        [1 - 2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
        [2*(x*y+z*w), 1 - 2*(x*x+z*z), 2*(y*z-x*w)],
        [2*(x*z-y*w), 2*(y*z+x*w), 1 - 2*(x*x+y*y)]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=10)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--only', default='', help='只跑这些前缀（逗号分隔，如 bla）')
    ap.add_argument('--json', default='')
    a = ap.parse_args()
    lib = json.load(open(LIB, encoding='utf-8'))['models']
    # 2026-11-01：室内包已并入 raw/all_packs（<包名>/ 平铺，与旧 raw/_interiors 布局一致），
    # 只取 *_int 包，其余包没有 .ytyp 会在下面被跳过。
    _all = sorted(d for d in os.listdir(os.path.join(ROOT, 'raw/all_packs')) if d.endswith('_int'))
    if a.only:
        pre = tuple(x.strip() for x in a.only.split(',') if x.strip())
        _all = [p for p in _all if p.startswith(pre)]
    pkgs = _all if a.all else _all[:a.n]
    results = []
    print('%-22s %-6s %-9s %-9s %s' % ('包', '件数', '室内尺寸', '宿主尺寸', '四边间隙/是否包住'))
    for pkg in pkgs:
        yp = os.path.join(ROOT, 'raw/all_packs', pkg, pkg + '.ytyp')
        if not os.path.exists(yp):
            cand = glob.glob(os.path.join(ROOT, 'raw/all_packs', pkg, '*.ytyp'))
            if not cand:
                continue
            yp = cand[0]
        lay = PM.parse_ytyp(yp)
        ents = lay['entities'] if isinstance(lay, dict) else lay
        inst, names = load_mlo(pkg)
        if not inst:
            print('%-22s 无 MLO 实例' % pkg)
            continue
        P = np.array([inst[1], inst[2], inst[3]])
        # MLO 实例：**不取共轭**（2026-11-05 实锤：实例与普通实体的旋向相反；见 scene_interiors.py）
        R = quat_mat((inst[4], inst[5], inst[6], inst[7]))
        mn = np.array([1e18]*3); mx = np.array([-1e18]*3)
        used = 0
        for e in ents:
            m = lib.get(hex(e['h']))
            if not m:
                continue
            b = m['b']
            for cx in (b[0], b[3]):
                for cy in (b[1], b[4]):
                    for cz in (b[2], b[5]):
                        w = P + R @ (np.array(e['p']) + np.array([cx, cy, cz]))
                        mn = np.minimum(mn, w); mx = np.maximum(mx, w)
            used += 1
        # 宿主：40 m 内、bbox 单轴 ≥ 4 m 的实体里挑一个。
        # 🔴 2026-11-04 改判据：以前只按「名字前缀 + 最近」，会挑到 `_em`/`_decal` 这类
        #    同名附属件、或隔壁小屋（黑水镇裁缝铺就这么判错的）。现在：
        #    ① 先要**包得住**（四边间隙都 ≥ -1.5），里面挑面积最小的（贴合的那栋）；
        #    ② 都包不住 → 取四边间隙最好（最不偏）的那个；
        #    ③ 同档再比名字前缀、距离。名字存进结果，地图页/实拍对照要用。
        base = pkg[:-4] if pkg.endswith('_int') else pkg
        cands = []
        for e in _tiles():
            m = lib.get(hex(e[0]))
            if not m:
                continue
            b = m['b']
            if not b or max(b[3]-b[0], b[4]-b[1]) < 4:
                continue
            d = math.hypot(e[1]-inst[1], e[2]-inst[2])
            if d > 40:
                continue
            hm = np.array([e[1]+b[0], e[2]+b[1], e[3]+b[2]])
            hx = np.array([e[1]+b[3], e[2]+b[4], e[3]+b[5]])
            gaps = (mn[0]-hm[0], hx[0]-mx[0], mn[1]-hm[1], hx[1]-mx[1])
            n = (names.get(e[0], '') or '').split('/')[-1]
            if _LOD_NAME.search(n) or _PROP_NAME.search(n):
                continue
            nm_hit = bool(n) and (base in n)
            area = float((hx[0]-hm[0]) * (hx[1]-hm[1]))
            # 宿主不能是"整片合并块"：面积超过室内的 4 倍（且 >600 m²）就不算包住
            int_area = max(1.0, float((mx[0]-mn[0]) * (mx[1]-mn[1])))
            fits = area <= max(600.0, 4.0 * int_area)
            if all(g >= 0 for g in gaps) and fits:
                tier, w = 0, area                  # 真正包住 → 取最贴合（面积最小）的
            elif all(g >= -1.5 for g in gaps) and fits:
                tier, w = 1, area                  # 容差内 → 同上
            else:
                tier, w = 2, -min(gaps)            # 都包不住 → 取最不偏的
            # 名字质量：能认出来的真建筑 > 同名附属件（_em/_decal/_dec/_d/_det）> 无名块
            q = 0 if (n and not _BAD_NAME.search(n)) else (1 if n else 2)
            key = (tier, q, w, d)
            cands.append((key, e, b, gaps, tier <= 1, n))
        if not cands:
            print('%-22s %-6d %6.1fx%-5.1f 宿主未找到' % (pkg, used, mx[0]-mn[0], mx[1]-mn[1]))
            continue
        cands.sort(key=lambda t: t[0])
        _k, e, b, gaps, inside, hostname = cands[0]
        d = _k[-1]
        hm = np.array([e[1]+b[0], e[2]+b[1], e[3]+b[2]])
        hx = np.array([e[1]+b[3], e[2]+b[4], e[3]+b[5]])
        print('%-22s %-6d %5.1fx%-5.1f %5.1fx%-5.1f  L%+.1f R%+.1f D%+.1f U%+.1f  %s' % (
            pkg, used, mx[0]-mn[0], mx[1]-mn[1], hx[0]-hm[0], hx[1]-hm[1], *gaps,
            'OK' if inside else '偏出'))
        results.append({'pkg': pkg, 'items': used, 'inside': bool(inside),
                        'host': hostname,
                        'gaps': [round(float(g), 2) for g in gaps],
                        'interior': [round(float(mn[0]), 1), round(float(mn[1]), 1),
                                     round(float(mx[0]), 1), round(float(mx[1]), 1)]})


    if a.json:
        json.dump(results, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('写出', a.json)


if __name__ == '__main__':
    main()
