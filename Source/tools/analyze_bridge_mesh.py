# -*- coding: utf-8 -*-
"""只查几何：圣丹尼斯西南桥梁 + 铁轨的网格是否连续（不碰水位、不渲染）。

数据源：export/world/continent/tiles/*.json（实例）+ continent/models.json（hash→ydr 名）
       + lib_native/index.json（模型局部 bbox）
"""
import json, os, math, glob
import numpy as np

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
MODELS = os.path.join(ROOT, 'export/world/continent/models.json')
IDX = os.path.join(ROOT, 'export/world/lib_native/index.json')
BX, BY = 2140.0, -1250.0
RADIUS = 900.0

KW = {
    'rail':  ('rail', 'track', 'train', 'ties', 'sleeper', 'switch'),
    'bridge': ('bridge', 'truss', 'girder', 'trestle', 'viaduct', 'pier', 'strut', 'abutment', 'span'),
}

def load():
    mods = json.load(open(MODELS, encoding='utf-8'))
    idx = json.load(open(IDX, encoding='utf-8'))['models']
    ents = []
    for f in sorted(glob.glob(os.path.join(TILES, '*.json'))):
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
            x, y, z = e[1], e[2], e[3]
            if abs(x - BX) > RADIUS or abs(y - BY) > RADIUS:
                continue
            ents.append((int(e[0]), x, y, z, os.path.basename(f)))
    return mods, idx, ents

def name_of(h, mods):
    p = mods.get('0x%08x' % (h & 0xffffffff)) or mods.get('0x%x' % h)
    return os.path.basename(p) if p else None, p

def main():
    mods, idx, ents = load()
    print('桥区 %.0f m 内实例 %d 个' % (RADIUS, len(ents)))
    groups = {k: [] for k in KW}
    named = 0
    for h, x, y, z, tile in ents:
        nm, _ = name_of(h, mods)
        if not nm:
            continue
        named += 1
        low = nm.lower()
        for g, kws in KW.items():
            if any(k in low for k in kws):
                groups[g].append((nm, x, y, z, h))
    print('能查到模型名 %d 个' % named)
    for g, rows in groups.items():
        print('\n=== %s：%d 件 ===' % (g, len(rows)))
        for r in rows[:15]:
            print('   %-46s (%7.1f,%8.1f,%6.2f)' % (r[0][:46], r[1], r[2], r[3]))
        if len(rows) > 15:
            print('   ...')

    # 铁轨连续性：主方向投影 + 间隙
    rails = groups['rail']
    if len(rails) > 5:
        P = np.array([[r[1], r[2]] for r in rails])
        c = P - P.mean(0)
        w, v = np.linalg.eigh(c.T @ c)
        d = v[:, np.argmax(w)]           # 主方向
        t = c @ d
        o = np.argsort(t)
        t = t[o]
        gaps = np.diff(t)
        print('\n=== 铁轨走向 ===')
        print('主方向 (%.3f, %.3f)  长度 %.0f m' % (d[0], d[1], t.max() - t.min()))
        print('相邻间距: 中位 %.2f m  P95 %.2f  最大 %.2f' % (
            np.median(gaps), np.percentile(gaps, 95), gaps.max()))
        big = [(float(t[i]), float(gaps[i])) for i in range(len(gaps)) if gaps[i] > 25]
        print('大间隙(>25 m) %d 处:' % len(big))
        for tt, gg in big[:15]:
            print('   沿轴 %8.1f m 处空 %.1f m' % (tt, gg))
        # 铁轨 z 剖面
        zz = np.array([r[3] for r in rails])[o]
        print('铁轨 z: min %.2f max %.2f（沿轴 z 变化 %.2f）' % (zz.min(), zz.max(), zz.max() - zz.min()))
        print('沿轴 z 采样:', [round(float(v_), 1) for v_ in zz[::max(1, len(zz)//12)]])

if __name__ == '__main__':
    main()
