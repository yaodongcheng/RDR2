"""整图覆盖率审计 —— 回答"大陆是否 100% 还原了所有建筑网格"。

产物：控制台表格（结论见 docs/世界与地编/RDR2_整图覆盖率核查_20261026.md）

用法：uv run python tools/audit_continent_coverage.py

口径说明：
  - tiles/*.json 存的是 archetype hash；lib_native 的 key 是 model hash。
    两者只在"archetype 名 == model 名"时相等，所以不能直接求 hash 交集算覆盖率。
    本脚本按「能在 names.txt 反查出名字的 archetype」分类统计，未命名单列。
"""
import os
import re
import csv
import glob
import json
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
LIB_IDX = os.path.join(ROOT, 'assets/lib_native/index.json')
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
SETTLE = os.path.join(ROOT, 'deliverable/handoff/settlements_world_v2.csv')


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xffffffff
        h = (h + (h << 10)) & 0xffffffff
        h ^= h >> 6
    h = (h + (h << 3)) & 0xffffffff
    h ^= h >> 11
    h = (h + (h << 15)) & 0xffffffff
    return h


RULES = [
    ('植被/树', re.compile(r'tree|bush|shrub|grass|fern|plant|cactus|palm|pine|oak|willow|stump|reed|lily|vine|weed|foliage|canopy|hedge|flower|moss', re.I)),
    ('LOD/代理', re.compile(r'slod|_lod|_proxy|_strm|heighttrack|_em_|occlusion', re.I)),
    ('VFX/特效', re.compile(r'_vfx|decal|_shad|helper|_fx_', re.I)),
    ('室内', re.compile(r'_int($|_)|interior', re.I)),
    ('建筑/结构', re.compile(r'_ext_|building|_house|house_|cabin|barn|church|store|saloon|bank|hotel|shed|shack|manor|stable|station|factory|warehouse|roof|porch|fence|wall|dock|bridge|tower|door|window|stairs|platform|sidewalk|road', re.I)),
]


def load_names():
    d = {}
    with open(NAMES, encoding='latin1', errors='ignore') as f:
        for n in f:
            n = n.strip()
            if n and not n.startswith('#'):
                d[joaat(n)] = n
    return d


def load_lib():
    idx = json.load(open(LIB_IDX, encoding='utf-8'))
    return {int(h, 16) for h in idx['models'].keys()}


def load_entities():
    ents = []
    for f in sorted(glob.glob(os.path.join(TILES, '*.json'))):
        ents.extend(json.load(open(f, encoding='utf-8')))
    return ents


def classify(name):
    if not name:
        return '未命名'
    for k, r in RULES:
        if r.search(name):
            return k
    return '其他/道具'


def main():
    nm = load_names()
    lib = load_lib()
    ents = load_entities()
    print('名字表 %d 条 / 库模型 %d 个 / 实体 %d 个' % (len(nm), len(lib), len(ents)))

    world = collections.Counter(e[0] for e in ents)
    uniq = len(world)
    named = sum(1 for h in world if h in nm)
    print('唯一 archetype %d，可命名 %d (%.1f%%)' % (uniq, named, 100.0 * named / uniq))

    # ---- 分类覆盖
    res = collections.defaultdict(lambda: [0, 0, 0])
    for h, c in world.items():
        cat = classify(nm.get(h))
        res[cat][0] += c
        res[cat][2] += 1
        if h in lib:
            res[cat][1] += c
    print('\n%-12s %9s %9s %8s %8s' % ('类别', '实例', '已装', '覆盖率', 'hash数'))
    for k, (a, o, hc) in sorted(res.items(), key=lambda kv: -kv[1][0]):
        print('%-12s %9d %9d %7.1f%% %8d' % (k, a, o, 100.0 * o / max(1, a), hc))
    ta = sum(v[0] for v in res.values())
    to = sum(v[1] for v in res.values())
    print('%-12s %9d %9d %7.1f%%' % ('合计', ta, to, 100.0 * to / ta))

    # ---- 未命名分布
    anon = [e for e in ents if e[0] not in nm]
    anon3 = [e for e in anon if e[10] == 3]
    print('\n未命名实例 %d；其中 ≥8m 大件 %d' % (len(anon), len(anon3)))
    for tag, arr in (('全部未命名', anon), ('≥8m 大件', anon3)):
        zneg = sum(1 for e in arr if e[3] < 0)
        zlow = sum(1 for e in arr if e[3] < 50)
        act = [e for e in arr if -3000 <= e[1] <= 3000 and -2500 <= e[2] <= 2500]
        print('  [%s] z<0: %d / z<50: %d / 主要活动区内: %d' % (tag, zneg, zlow, len(act)))

    # ---- 据点内缺口
    if os.path.exists(SETTLE):
        rows = []
        for s in csv.DictReader(open(SETTLE, encoding='utf-8-sig')):
            cx, cy = float(s['world_x']), float(s['world_y'])
            hw, hd = float(s['size_w_m']) / 2, float(s['size_d_m']) / 2
            big = [e for e in ents if e[10] == 3 and abs(e[1] - cx) <= hw and abs(e[2] - cy) <= hd]
            nb = sum(1 for e in big if e[0] not in nm)
            rows.append((nb, s['code'], s['name_zh'], len(big)))
        print('\n== 据点内未命名大件（严格框）TOP 12 ==')
        print('%-7s %-14s %8s %8s' % ('code', 'name', '未命名', '大件总数'))
        for nb, code, name, tot in sorted(rows, reverse=True)[:12]:
            print('%-7s %-14s %8d %8d' % (code, name, nb, tot))

    # ---- 夏洛蒂的家
    print('\n== 威拉德之息（夏洛蒂的家）逐项校验 ==')
    idx = json.load(open(LIB_IDX, encoding='utf-8'))['models']
    for name in ['roc_01_ext_home01', 'roc_shed_01', 'roc_leanto',
                 'roc_01_ext_well', 'roc_01_garden01_nice', 'roc_01_gravefresh']:
        h = joaat(name)
        k = hex(h)
        m = idx.get(k)
        tris = sum(i // 3 for _, v, i in m['s']) if m else 0
        inst = [e for e in ents if e[0] == h]
        print('  %-24s %s  lib=%-5s tris=%-6d 实例=%d' % (name, k, bool(m), tris, len(inst)))
        for e in inst[:1]:
            print('      pos=(%.1f, %.1f, %.1f) cls=%d' % (e[1], e[2], e[3], e[10]))


if __name__ == '__main__':
    main()
