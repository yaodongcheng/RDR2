# -*- coding: utf-8 -*-
"""把「铁路网实例」并进 tiles（`export/world/continent/tiles/*.json`）。

数据源：本轮从 `levels_2.rpf` 补抽的三个铁路包
        `raw/rails_extract/{jklma,jklmb,fghia}/**/*.ymap`
产物：对应 `wild2000_XX_YY.json` 追加实例行（**先备份**到 `tiles_before_rail_<ts>/`）

行格式与 `build_continent_index.py` 完全一致（11 列）：
    [hash, x,y,z, qx,qy,qz,qw, sxy, sz, cls]

按 `-cls, -频次` 排序的既有顺序不动，新行追加在末尾（构建时每个 tile 全量遍历，顺序无所谓）。

    python tools/merge_rail_entities.py --dry
    python tools/merge_rail_entities.py
"""
import os
import sys
import json
import time
import glob
import shutil
import argparse
from collections import Counter, defaultdict
from datetime import datetime

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
LIB = os.path.join(ROOT, 'assets/lib_native')
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
PACKS = [os.path.join(ROOT, 'raw/rails_extract', d) for d in ('jklma', 'jklmb', 'fghia')]
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')

X0, Y0, WORLD, TILE = -7684.0, -8196.0, 12296.0, 2000.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--keep-lod', action='store_true', help='连 _lod/_slod 一起并（默认跳过，构建时也会隐藏）')
    ap.add_argument('--packs', nargs='*', default=None, help='默认三包；给 raw/rails_all 就是全量')
    a = ap.parse_args()

    import ymap_entities as Y

    packs = a.packs or PACKS

    def joaat(s):
        h = 0
        for c in s.lower().encode('latin1', 'ignore'):
            h = (h + c) & 0xFFFFFFFF
            h = (h + (h << 10)) & 0xFFFFFFFF
            h ^= h >> 6
        h = (h + (h << 3)) & 0xFFFFFFFF
        h ^= h >> 11
        return (h + (h << 15)) & 0xFFFFFFFF

    name_of = {}
    for ln in open(NAMES, encoding='latin1', errors='ignore'):
        n = ln.strip()
        if n and not n.startswith('#'):
            name_of.setdefault(joaat(n), n)

    idx = json.load(open(os.path.join(LIB, 'index.json'), encoding='utf-8'))
    models = idx['models']

    ents = []
    for p in packs:
        for f in sorted(glob.glob(os.path.join(p, '**', '*.ymap'), recursive=True)):
            sig, size, es = Y.extract(f)
            if es:
                print('  %-38s %4d 条' % (os.path.basename(f), len(es)))
                ents += es
    print('[merge] 新实例 %d 条' % len(ents))

    skipped_lod = 0
    rows = []
    seen = set()
    dup = 0
    for e in ents:
        h = int(e[0]) & 0xFFFFFFFF
        nm = name_of.get(h, '')
        low = nm.lower()
        if not a.keep_lod and ('_lod' in low or '_slod' in low):
            skipped_lod += 1
            continue
        hx = '0x%08x' % h
        m = models.get(hx)
        if not m:
            continue
        x, y, z = e[1], e[2], e[3]
        b = m['b']
        s = max(b[3] - b[0], b[4] - b[1], b[5] - b[2])
        cls = 3 if s >= 8 else 2 if s >= 4 else 1 if s >= 1.5 else 0
        key = (h, round(x, 1), round(y, 1), round(z, 1))
        if key in seen:
            dup += 1
            continue
        seen.add(key)
        rows.append([h, round(x, 1), round(y, 1), round(z, 1),
                     e[4], e[5], e[6], e[7],
                     e[8] if abs(e[8]) > 1e-6 else 1.0,
                     e[9] if abs(e[9]) > 1e-6 else 1.0, cls])
    print('[merge] 跳过 _lod/_slod %d / 内重复 %d / 最终 %d 条' % (skipped_lod, dup, len(rows)))

    # 按位置分 tile
    bytile = defaultdict(list)
    for r in rows:
        i = int((r[1] - X0) // TILE)
        j = int((Y0 + WORLD - r[2]) // TILE)
        bytile['wild2000_%02d_%02d' % (i, j)].append(r)
    print('[merge] 落进 %d 个 tile：%s' % (
        len(bytile), ', '.join('%s+%d' % (k, len(v)) for k, v in sorted(bytile.items()))))

    if a.dry:
        return

    bakdir = os.path.join(ROOT, 'export/world/continent/tiles_before_rail_%s'
                          % datetime.now().strftime('%Y%m%d_%H%M'))
    os.makedirs(bakdir, exist_ok=True)
    added = 0
    for tid, rs in sorted(bytile.items()):
        p = os.path.join(TILES, tid + '.json')
        cur = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else []
        have = {(int(r[0]) & 0xFFFFFFFF, round(r[1], 1), round(r[2], 1)) for r in cur}
        new = []
        for r in rs:
            k = (r[0], r[1], r[2])
            if k in have:
                continue
            have.add(k)
            new.append(r)
        if not new:
            continue
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(bakdir, tid + '.json'))
        json.dump(cur + new, open(p, 'w', encoding='utf-8'), separators=(',', ':'))
        added += len(new)
        print('  %s  %5d → %5d (+%d)' % (tid, len(cur), len(cur) + len(new), len(new)))
    print('[merge] 追加 %d 条；备份在 %s' % (added, os.path.relpath(bakdir, ROOT)))


if __name__ == '__main__':
    main()
