# -*- coding: utf-8 -*-
"""给室内包名 → 查它在 ymap 里的 MLO 实例（世界位置/朝向），解除"室内批量化"的阻塞。

## 背景

夏洛蒂家（`roc_house_int`）当年是靠 `roc_hse_int_lod` 这个 ymap 实例顶替的，
因此文档一度认为"其他房子不一定有同类 LOD 实例 → 逐栋手工"。
2026-10-27 实测：**144 个室内包里 133 个在 tiles 里有精确同名 MLO 实例**（`<pkg>` 或 `<pkg>_lod` 或 `<pkg>_main`），
3 个只有模糊匹配，8 个完全没有。⇒ 室内可以批量，不必逐栋手工。

## 用法

    uv run python tools/locate_interior_mlo.py                    # 全量统计
    uv run python tools/locate_interior_mlo.py roc_house_int      # 查单个
    uv run python tools/locate_interior_mlo.py --json out.json    # 导出映射表给批量装配用

输出字段：pkg / match（exact|lod|main|fuzzy|none）/ 实例名 / 世界坐标 / 四元数(x,y,z,w) / yaw° / scale /
最近的宿主建筑（名字 + 距离），宿主建筑用来交叉校验 MLO 是否落在正确的房子里。
"""
import os
import sys
import json
import glob
import math
import argparse
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
PKGS = os.path.join(ROOT, 'export/world/interior_pkgs.txt')

import re
BUILD = re.compile(r'_ext_|building|_house|house_|cabin|barn|church|store|saloon|bank|hotel|manor|stable|station|shed|shack', re.I)


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF


def load_names():
    d = {}
    with open(NAMES, encoding='latin1', errors='ignore') as f:
        for l in f:
            n = l.strip()
            if n:
                d.setdefault(joaat(n), n.lower())
    return d


def yaw_of(q):
    x, y, z, w = q
    return math.degrees(math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))


def load_entities(names):
    """返回 [(name, x,y,z, qx,qy,qz,qw, sx, sz)] 只保留可命名实体。"""
    out = []
    for p in sorted(glob.glob(os.path.join(TILES, '*.json'))):
        for e in json.load(open(p, encoding='utf-8')):
            n = names.get(e[0])
            if n:
                out.append((n.split('/')[-1], e[1], e[2], e[3], e[4], e[5], e[6], e[7], e[8], e[9]))
    return out


def classify(pkg, by_name):
    """exact / lod / main / fuzzy / none"""
    for suffix, tag in (('', 'exact'), ('_lod', 'lod'), ('_main', 'main')):
        e = by_name.get(pkg + suffix)
        if e:
            return tag, e
    base = pkg[:-4] if pkg.endswith('_int') else pkg
    for n, e in by_name.items():
        if 'int' in n and (n.startswith(base) or base.startswith(n)):
            return 'fuzzy', e
    return 'none', None


def nearest_building(ents, x, y, limit=400):
    best = None
    for n, ex, ey, ez, *_ in ents:
        if not BUILD.search(n) or re.search(r'(^|_)int($|_)', n):
            continue
        d = math.hypot(ex - x, ey - y)
        if d < limit and (best is None or d < best[0]):
            best = (d, n, ex, ey, ez)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('packages', nargs='*')
    ap.add_argument('--pkgs', default=PKGS)
    ap.add_argument('--json', default='')
    ap.add_argument('--list-only', action='store_true')
    a = ap.parse_args()

    names = load_names()
    ents = load_entities(names)
    by_name = {}
    for e in ents:
        by_name.setdefault(e[0], e)
    if not os.path.exists(a.pkgs):
        raise SystemExit('缺包名清单: %s' % a.pkgs)
    pkgs = [l.strip() for l in open(a.pkgs, encoding='utf-8') if l.strip()]
    targets = a.packages or pkgs

    res = {}
    stat = collections.Counter()
    for pkg in targets:
        tag, e = classify(pkg, by_name)
        stat[tag] += 1
        row = {'pkg': pkg, 'match': tag}
        if e:
            row.update({'inst': e[0], 'pos': [round(e[1], 2), round(e[2], 2), round(e[3], 2)],
                        'quat': [e[4], e[5], e[6], e[7]], 'yaw': round(yaw_of(e[4:8]), 1),
                        'scale': [e[8], e[9]]})
            nb = nearest_building(ents, e[1], e[2])
            row['note'] = '宿主=自身（MLO 实例名本身像建筑，已按 _int 排除）' if False else None
            if nb:
                row['host'] = {'name': nb[1], 'dist': round(nb[0], 1),
                               'pos': [round(nb[2], 1), round(nb[3], 1), round(nb[4], 1)]}
        res[pkg] = row
        if a.packages:
            print(json.dumps(row, ensure_ascii=False))
    if a.json:
        json.dump(res, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('wrote', a.json)
    if not a.packages:
        print('室内包 %d：精确 %d / lod %d / main %d / 模糊 %d / 无 %d' % (
            len(targets), stat['exact'], stat['lod'], stat['main'], stat['fuzzy'], stat['none']))
        ok = stat['exact'] + stat['lod'] + stat['main']
        print('可直接批量定位：%d / %d = %.0f%%' % (ok, len(targets), 100.0 * ok / max(1, len(targets))))
        miss = [p for p, r in res.items() if r['match'] in ('fuzzy', 'none')]
        print('需人工：', miss)


if __name__ == '__main__':
    main()
