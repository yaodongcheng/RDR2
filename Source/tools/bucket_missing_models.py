# -*- coding: utf-8 -*-
"""把"缺模型的实体 hash"分桶，回答"这 5 万个到底是什么"。

分桶规则（按名字）：
    lod_combine / _lod / _slod   → LOD 合并块（引擎运行时合并，磁盘无独立文件）
    tempbox / proxy / _vfx       → 占位/代理（游戏不渲染）
    terrain / _r_c_ / hd_        → 地表分块（H4 已替代）
    其余                          → **真缺口**，必须逐条看

    python tools/bucket_missing_models.py --json D:/BrainMaker/_logs/missing_bucket.json
"""
import os
import sys
import json
import glob
import argparse
from collections import Counter, defaultdict

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
LIB = os.path.join(ROOT, 'assets/lib_native')
PACKS_DIR = os.path.join(ROOT, 'raw/all_packs')
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')


def joaat(s):
    h = 0
    for c in s.lower().encode('latin1', 'ignore'):
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF


def bucket(nm):
    l = (nm or '').lower()
    if not l:
        return '无名'
    if 'lod_combine' in l or l.endswith('_lod') or '_lod' in l or '_slod' in l:
        return 'LOD 合并块'
    if 'tempbox' in l or 'proxy' in l or '_vfx' in l or 'audioproxy' in l:
        return '占位/代理'
    if '_r_c_' in l or 'terrain' in l or l.startswith('hd_') or '__hd_' in l:
        return '地表分块'
    if 'shadow' in l:
        return '阴影代理'
    return '真缺口'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', default='')
    a = ap.parse_args()

    import ymap_entities as Y
    idx = json.load(open(os.path.join(LIB, 'index.json'), encoding='utf-8'))
    models = idx['models']
    name_of = {}
    for ln in open(NAMES, encoding='latin1', errors='ignore'):
        n = ln.strip()
        if n and not n.startswith('#'):
            name_of.setdefault(joaat(n), n)

    cnt = Counter()
    refs = Counter()
    real = defaultdict(int)
    for f in glob.glob(os.path.join(PACKS_DIR, '**', '*.ymap'), recursive=True):
        try:
            sig, size, es = Y.extract(f)
        except Exception:
            es = []
        for e in es:
            h = int(e[0]) & 0xFFFFFFFF
            if ('0x%08x' % h) in models:
                continue
            nm = name_of.get(h, '')
            b = bucket(nm)
            cnt[b] += 1
            if b == '真缺口':
                real[nm or ('0x%08x' % h)] += 1
    for b, c in cnt.items():
        pass
    print('缺模型实体 %d 条，按桶：' % sum(cnt.values()))
    for k, v in cnt.most_common():
        print('   %-14s %6d' % (k, v))
    print('\n真缺口 %d 个不同名字（前 30，按引用次数）：' % len(real))
    for n, c in sorted(real.items(), key=lambda kv: -kv[1])[:30]:
        print('   %-52s x%d' % (n[:52], c))
    if a.json:
        json.dump(dict(buckets=dict(cnt), real=dict(sorted(real.items(), key=lambda kv: -kv[1]))),
                  open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('→ %s' % a.json)


if __name__ == '__main__':
    main()
