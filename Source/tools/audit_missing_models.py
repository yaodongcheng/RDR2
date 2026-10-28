# -*- coding: utf-8 -*-
"""把「缺模型」按**能不能装**拆开，给出唯一权威口径（取代"5 万个未命名缺口"的旧说法）。

## 背景（2026-10-29 实测）

旧文档把 **49,778 种 / 50,007 个实例** 叫作「未命名 archetype 缺口」，并把它当成
「补全模型库」的头号目标。本次把每个缺模型 hash 追到源头，结论是**它不是缺口**：

| 桶 | 判据 | 结论 |
|---|---|---|
| `lod_block` | 定义它的 ytyp 文件名含 `lod`，且 bbox 中位 64 m（P90 128 m） | **LOD 合并块**：游戏运行时按子 archetype 现场合并，磁盘上没有 .ydr/.yft；不该按 HD 装 |
| `real_ytyp` | 定义它的是真实 ytyp（非 lod），bbox 中位 7 m | 真实的缺件候选 |
| `rpf_available` | 该 hash 在 `work/rpf_index/all.tsv` 里有 .ydr/.yft | 能抽；但多数是 `_vfx/_slod/_lights/_ph`（无几何） |
| `no_definition` | ytyp 里查不到 | 来源不明（下一轮再查） |

三条实测证据（都能重跑）：

1. `archetype_assetnames.json`：96,141 条 archetype 的 `name` 与 `assetName` **完全相同**（0 条不同）；
2. 96,141 条里 **92.2%** 来自 `*_lod_combine_metadata*` 文件；
3. 抽样 3,001 个未命名实例，**77.5%** 水平距离 <0.5 m 就有一个已装好的具名件（即 LOD 块盖在真几何上）。

用法：

    python tools/audit_missing_models.py              # 打印 + 写 export/world/missing_classified.json
    python tools/audit_missing_models.py --top 20
"""
import os
import re
import csv
import glob
import json
import argparse
from collections import Counter, defaultdict

ROOT = r'D:/BrainMaker/大镖客2解包分析'
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
LIB_IDX = os.path.join(ROOT, 'assets/lib_native/index.json')
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
RPF_IDX = os.path.join(ROOT, 'work/rpf_index/all.tsv')
ARCH = os.path.join(ROOT, 'export/levels/town/archetype_assetnames.json')
SETTLE = os.path.join(ROOT, 'deliverable/handoff/settlements_world_v2.csv')
OUT = os.path.join(ROOT, 'export/world/missing_classified.json')

# 名字里带这些的，本来就没有可渲染几何（VFX/灯光/占位/物理代理/远景 LOD）
NONRENDER = re.compile(
    r'_vfx|vfx_|_lights?\b|lights_|_ph$|_ph_|_occ|_proxy|proxy_|slod|_lod\d|_dslod|_helper|'
    r'_em_|_em\d|audioproxy|_shad|shadowproxy|reflection|_clips|_audio|_scorch|decal', re.I)
INTERIOR = re.compile(r'_int_|_int$|_int\.', re.I)


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
    m = {}
    for line in open(NAMES, encoding='latin1', errors='ignore'):
        n = line.strip()
        if n:
            m.setdefault(joaat(n), n)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=12)
    a = ap.parse_args()

    names = load_names()
    lib = {int(k, 16) for k in json.load(open(LIB_IDX, encoding='utf-8'))['models']}
    arch = {}
    if os.path.exists(ARCH):
        arch = {int(k, 16): v for k, v in json.load(open(ARCH, encoding='utf-8')).items()}
    rpf = {}
    if os.path.exists(RPF_IDX):
        for line in open(RPF_IDX, encoding='utf-8'):
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 5:
                rpf.setdefault(int(parts[1], 16), (parts[0], parts[4], int(parts[2])))

    ents = []
    for p in sorted(glob.glob(os.path.join(TILES, '*.json'))):
        ents.extend(json.load(open(p, encoding='utf-8')))
    world = Counter(e[0] for e in ents)
    missing = {h: c for h, c in world.items() if h not in lib}

    buckets = defaultdict(lambda: {'hashes': 0, 'instances': 0, 'sample': []})
    per_hash = {}
    for h, inst in missing.items():
        name = names.get(h)
        v = arch.get(h)
        dims = None
        src = None
        if v:
            bb = v['bbox']
            dims = [bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]]
            src = v['src']
        if h in rpf:
            b = 'rpf_available'
        elif src and 'lod' in src.lower():
            b = 'lod_block'
        elif src:
            b = 'real_ytyp'
        else:
            b = 'no_definition'
        # 名字明确不可渲染的再细分（只有 rpf_available / real_ytyp 才有名字）
        sub = ''
        if name:
            if NONRENDER.search(name):
                sub = 'nonrender'
            elif INTERIOR.search(name):
                sub = 'interior'
        key = b + ((':' + sub) if sub else '')
        buckets[key]['hashes'] += 1
        buckets[key]['instances'] += inst
        if len(buckets[key]['sample']) < 6:
            buckets[key]['sample'].append(
                dict(h='0x%08x' % h, name=name, src=src,
                     dims=[round(x, 1) for x in dims] if dims else None, inst=inst))
        per_hash[h] = dict(bucket=key, name=name, src=src,
                           dims=[round(x, 1) for x in dims] if dims else None, inst=inst)

    tot_h, tot_i = len(missing), sum(missing.values())
    print('缺模型 %d 个 hash / %d 个实例（库 %d 个模型）' % (tot_h, tot_i, len(lib)))
    print('\n%-22s %8s %10s %6s' % ('桶', 'hash数', '实例数', '占比'))
    for k, v in sorted(buckets.items(), key=lambda kv: -kv[1]['instances']):
        print('%-22s %8d %10d %5.1f%%' % (k, v['hashes'], v['instances'],
                                          100.0 * v['instances'] / max(1, tot_i)))

    # 据点（严格框，与 audit_continent_coverage.py 同口径）
    settle = []
    if os.path.exists(SETTLE):
        for s in csv.DictReader(open(SETTLE, encoding='utf-8-sig')):
            cx, cy = float(s['world_x']), float(s['world_y'])
            hw, hd = float(s['size_w_m']) / 2, float(s['size_d_m']) / 2
            big = [e for e in ents if e[10] == 3 and abs(e[1] - cx) <= hw and abs(e[2] - cy) <= hd]
            mis = [e for e in big if e[0] not in lib]
            lod = [e for e in mis if per_hash.get(e[0], {}).get('bucket', '').startswith('lod_block')]
            real = [e for e in mis if not per_hash.get(e[0], {}).get('bucket', '').startswith('lod_block')]
            settle.append(dict(code=s['code'], name=s.get('name_zh', ''), big=len(big),
                               missing=len(mis), lod=len(lod), real=len(real)))
        settle.sort(key=lambda r: -r['real'])
        print('\n== 据点内"缺模型"拆分（严格框，含 cls=3 大件）TOP %d ==' % a.top)
        print('%-6s %-14s %8s %8s %8s %8s' % ('code', 'name', '大件', '缺模型', '其中LOD', '真缺口'))
        for r in settle[:a.top]:
            print('%-6s %-14s %8d %8d %8d %8d'
                  % (r['code'], r['name'], r['big'], r['missing'], r['lod'], r['real']))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(dict(generated_by='tools/audit_missing_models.py',
                   lib_models=len(lib), total_hashes=tot_h, total_instances=tot_i,
                   buckets={k: v for k, v in buckets.items()},
                   settlements=settle,
                   per_hash={'0x%08x' % h: v for h, v in per_hash.items()}),
              open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\n[audit] 明细写入 %s（%.1f MB）' % (OUT, os.path.getsize(OUT) / 1e6))


if __name__ == '__main__':
    main()
