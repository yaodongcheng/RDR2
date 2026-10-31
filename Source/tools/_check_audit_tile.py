# -*- coding: utf-8 -*-
"""对账：审计子块的分类必须与 v23 大陆同一地块**完全一致**（至高准则：单一管线/分块即裁剪）。

    python tools/_check_audit_tile.py --tile wild2000_04_02 --audit <manifest jsonl>

比对 [对象数, 每类计数]；不一致 → FAIL（该块不交付）。
"""
import argparse
import collections
import json
import os

ROOT = r'D:/BrainMaker/大镖客2解包分析'
V23 = os.path.join(ROOT, 'deliverable/blender/continent/manifest_continent_v23.jsonl')


def counts(jsonl, tid=None):
    c = collections.Counter()
    n = 0
    with open(jsonl, encoding='utf-8') as f:
        for line in f:
            o = json.loads(line)
            if '_meta' in o:
                continue
            # 场景级对象（Sun/Terrain/Water）没有 tid，两边都不算地块内容
            if not o.get('tid'):
                continue
            if tid is not None and o.get('tid') != tid:
                continue
            n += 1
            c[o.get('c') or 'unknown'] += 1
    return n, c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tile', required=True)
    ap.add_argument('--audit', required=True, help='审计块的 manifest_*.jsonl')
    ap.add_argument('--v23', default=V23)
    a = ap.parse_args()

    n0, c0 = counts(a.v23, a.tile)
    n1, c1 = counts(a.audit)
    print('[check] tile=%s  v23: %d 对象  audit: %d 对象' % (a.tile, n0, n1))
    keys = sorted(set(c0) | set(c1))
    bad = []
    for k in keys:
        if c0.get(k, 0) != c1.get(k, 0):
            bad.append((k, c0.get(k, 0), c1.get(k, 0)))
    if n0 != n1 or bad:
        print('[check] FAIL')
        for k, x, y in bad:
            print('   %-14s v23=%6d audit=%6d' % (k, x, y))
        raise SystemExit(1)
    print('[check] PASS（对象数与 17 类计数逐项一致）')


if __name__ == '__main__':
    main()
