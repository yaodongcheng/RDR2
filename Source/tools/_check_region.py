# -*- coding: utf-8 -*-
"""对账：区域裁剪 blend 的分类必须与 v23 大陆同一地块一致（含纠错清单与硬规则）。

    python tools/_check_region.py --tile wild2000_04_02 --audit <manifest jsonl>

判定：对象数 + 每类计数逐项一致 → PASS。
v23 侧按**当前规则**重算名字层（几何兜底保留存盘类），
再套用同一份纠错清单和硬规则——与 classify_entities 共用 class_rules。
"""
import argparse
import collections
import csv
import json
import os
import sys

ROOT = r'D:/BrainMaker/大镖客2解包分析'
V23 = os.path.join(ROOT, 'deliverable/blender/continent/manifest_continent_v23.jsonl')
CORR = os.path.join(ROOT, 'deliverable/blender/regions_support/region_corrections.csv')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from class_rules import (  # noqa: E402
    TECHNICAL, classify_name, apply_corrections, apply_hard_rules, load_corrections,
)

_IDX = {}
_TEX = {}


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
                tag = o.get('tag') or ''
                # 构建期的属性兜底（与 classify_entities 一致）：地形块 / 停放件
                if tag == 'terrain_cell':
                    k = 'terrain_cell'
                elif tag == 'parked_offmap':
                    k = 'underground'
                else:
                    kn = classify_name(nm)
                    # 名字层能判定、且不是技术类 → 用当前规则；unknown 时保留存盘类（可能是几何兜底）
                    if kn != 'unknown' and k not in TECHNICAL:
                        k = kn
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
    a = ap.parse_args()

    corr = load_corrections(a.corrections)
    n0, c0 = counts(a.v23, a.tile, corr)
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
    print('[check] PASS（对象数与 %d 类计数逐项一致）' % len(keys))


if __name__ == '__main__':
    main()
