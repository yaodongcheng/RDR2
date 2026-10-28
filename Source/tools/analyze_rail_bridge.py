# -*- coding: utf-8 -*-
"""RDR2 铁路 / 桥梁资产定位与完整性体检（纯数据，不碰水面、不渲染）。

铁路资产命名：`<tile>_r_c_*`(道砟/轨面块) `<tile>_r_b_sle*`(枕木) `<tile>_r_b_bri*`(桥)
              `<tile>_r_b_tres*`(栈桥/桥墩) `<tile>_r_b_steel*`(钢轨) `*rrcross*`(道岔) `*_tun*`(隧道)
"""
import json, os, glob, collections
import numpy as np

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h & 0xFFFFFFFF


def kind(n):
    l = n.lower()
    if '_bri' in l: return 'BRIDGE'
    if 'steel' in l: return 'STEEL'
    if '_sle' in l: return 'SLEEPER'
    if '_tres' in l: return 'TRESTLE'
    if 'rrcross' in l or '_cross' in l: return 'CROSS'
    if '_tun' in l: return 'TUNNEL'
    if '_r_c_' in l or 'rails_c' in l: return 'CELL'
    if '_r_b_' in l: return 'BED'
    return 'OTHER'


def load(names):
    R = []
    for f in glob.glob(os.path.join(TILES, '*.json')):
        if f.endswith('.bak'):
            continue
        try:
            arr = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(arr, list):
            continue
        for e in arr:
            if not isinstance(e, list) or len(e) < 4:
                continue
            n = names.get(int(e[0]) & 0xffffffff)
            if not n:
                continue
            l = n.lower()
            if not any(k in l for k in ('_r_c_', '_r_b_', 'rails_c', 'rrcross', '_tun', 'trestle')):
                continue
            R.append((n, float(e[1]), float(e[2]), float(e[3])))
    return R


def main():
    names = {}
    for ln in open(NAMES, encoding='latin1', errors='ignore'):
        s = ln.strip()
        if s:
            names.setdefault(joaat(s), s)
    R = load(names)
    print('铁路相关实例 %d' % len(R))
    print('分类:', collections.Counter(kind(r[0]) for r in R).most_common())

    br = [r for r in R if kind(r[0]) == 'BRIDGE']
    print('\n=== BRIDGE %d 件，按 800 m 网格分组 ===' % len(br))
    g = collections.defaultdict(list)
    for r in br:
        g[(int(r[1] // 800) * 800, int(r[2] // 800) * 800)].append(r)
    for k, v in sorted(g.items(), key=lambda kv: -len(kv[1])):
        print('  x[%6d,%6d] y[%6d,%6d]  %3d 件  z[%7.1f,%7.1f]  %s' % (
            k[0], k[0] + 800, k[1], k[1] + 800, len(v),
            min(x[3] for x in v), max(x[3] for x in v),
            sorted(set(x[0] for x in v))[:3]))

    # 圣丹尼斯一带
    for tag, (x0, x1, y0, y1) in {'圣丹尼斯西南': (1900, 3000, -2000, -1000),
                                  '圣丹尼斯全域': (2200, 3200, -1800, -800)}.items():
        sub = [r for r in R if x0 <= r[1] <= x1 and y0 <= r[2] <= y1]
        print('\n=== %s 铁路件 %d ===' % (tag, len(sub)))
        print('  分类:', collections.Counter(kind(r[0]) for r in sub).most_common())
        cc = collections.Counter(r[0] for r in sub)
        for n, cnt in cc.most_common(12):
            ex = [r for r in sub if r[0] == n][:3]
            print('    %-34s %-8s x%-3d z=%s (%7.1f,%8.1f)' % (
                n[:34], kind(n), cnt, [round(r[3], 1) for r in ex], ex[0][1], ex[0][2]))


if __name__ == '__main__':
    main()
