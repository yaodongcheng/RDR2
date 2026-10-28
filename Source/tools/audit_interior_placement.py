# -*- coding: utf-8 -*-
"""抽查：把室内布局按「MLO 实例变换」摆到世界，看是否落在宿主建筑里。

输出每包的「室内 bbox 是否被最近的大建筑 bbox 包住」+ 四边间隙。
用法：uv run python tools/audit_interior_placement.py [--n 8]
"""
import os, sys, json, glob, math, argparse, itertools
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import numpy as np
import parse_interior_mlo as PM

LIB = os.path.join(ROOT, 'assets/lib_native', 'index.json')


def load_mlo(pkg):
    names = {}
    for l in open(os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt'), encoding='latin1', errors='ignore'):
        n = l.strip()
        if n:
            names.setdefault(PM.joaat(n), n.lower())
    want = [pkg, pkg + '_lod', pkg + '_main']
    for p in glob.glob(os.path.join(ROOT, 'export/world/continent/tiles/*.json')):
        if p.endswith('.bak'):
            continue
        for e in json.load(open(p, encoding='utf-8')):
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
    ap.add_argument('--json', default='')
    a = ap.parse_args()
    lib = json.load(open(LIB, encoding='utf-8'))['models']
    _all = sorted(os.listdir(os.path.join(ROOT, 'raw/_interiors')))
    pkgs = _all if a.all else _all[:a.n]
    results = []
    print('%-22s %-6s %-9s %-9s %s' % ('包', '件数', '室内尺寸', '宿主尺寸', '四边间隙/是否包住'))
    for pkg in pkgs:
        yp = os.path.join(ROOT, 'raw/_interiors', pkg, pkg + '.ytyp')
        if not os.path.exists(yp):
            cand = glob.glob(os.path.join(ROOT, 'raw/_interiors', pkg, '*.ytyp'))
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
        R = quat_mat((-inst[4], -inst[5], -inst[6], inst[7]))   # 共轭（与全图装配一致）
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
        # 宿主：离 MLO 实例最近、且 bbox 单轴 >6m 的实体
        # 宿主：优先按名字前缀匹配（<pkg 去掉 _int> 出现在建筑名里），其次按距离
        base = pkg[:-4] if pkg.endswith('_int') else pkg
        best = None
        for p in glob.glob(os.path.join(ROOT, 'export/world/continent/tiles/*.json')):
            if p.endswith('.bak'):
                continue
            for e in json.load(open(p, encoding='utf-8')):
                m = lib.get(hex(e[0]))
                if not m:
                    continue
                b = m['b']
                if max(b[3]-b[0], b[4]-b[1]) < 4:
                    continue
                n = names.get(e[0], '')
                nm_hit = bool(n) and (base in n.split('/')[-1])
                d = math.hypot(e[1]-inst[1], e[2]-inst[2])
                if d > 40:
                    continue
                score = (0 if nm_hit else 1, d)
                if best is None or score < best[0]:
                    best = (score, e, b)
        if not best:
            print('%-22s %-6d %6.1fx%-5.1f 宿主未找到' % (pkg, used, mx[0]-mn[0], mx[1]-mn[1]))
            continue
        _sc, e, b = best; d = _sc[1]
        hm = np.array([e[1]+b[0], e[2]+b[1], e[3]+b[2]])
        hx = np.array([e[1]+b[3], e[2]+b[4], e[3]+b[5]])
        gaps = (mn[0]-hm[0], hx[0]-mx[0], mn[1]-hm[1], hx[1]-mx[1])
        inside = all(g >= -1.5 for g in gaps)
        print('%-22s %-6d %5.1fx%-5.1f %5.1fx%-5.1f  L%+.1f R%+.1f D%+.1f U%+.1f  %s' % (
            pkg, used, mx[0]-mn[0], mx[1]-mn[1], hx[0]-hm[0], hx[1]-hm[1], *gaps,
            'OK' if inside else '偏出'))
        results.append({'pkg': pkg, 'items': used, 'inside': bool(inside),
                        'gaps': [round(float(g), 2) for g in gaps],
                        'interior': [round(float(mn[0]), 1), round(float(mn[1]), 1),
                                     round(float(mx[0]), 1), round(float(mx[1]), 1)]})


    if a.json:
        json.dump(results, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('写出', a.json)


if __name__ == '__main__':
    main()
