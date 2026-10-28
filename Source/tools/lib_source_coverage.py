# -*- coding: utf-8 -*-
"""P2 摸底：库里 55,608 个模型 hash，有多少能在 RPF 索引里直接找到 drawable 源？

RPF 索引 `work/rpf_index/all.tsv` 的列（`rdr2rpf hashindex` 输出）：archive, hash, size, ext, name
这里的 hash = **drawable 条目 hash**（本行条目自己的 hash，不含目录路径影响）。
如果模型的 archetype hash 与之相同，就能按条目 hash 精确抽出源文件 → 解析出真实贴图名/几何。
"""
import os
import re
import json
from collections import Counter

ROOT = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(ROOT, 'assets/lib_native')
TSV = os.path.join(ROOT, 'work/rpf_index/all.tsv')
OUT = os.path.join(ROOT, 'work/lib_source_coverage.json')

idx = json.load(open(os.path.join(LIB, 'index.json'), encoding='utf-8'))
models = idx['models']
lib_h = {int(k, 16) for k in models}
print('库内模型 %d' % len(lib_h))

ent = {}          # hash -> (archive, size, ext, name)
per_arc = Counter()
with open(TSV, encoding='utf-8', errors='replace') as f:
    head = f.readline().rstrip('\n').split('\t')
    print('TSV 表头：', head)
    for line in f:
        c = line.rstrip('\n').split('\t')
        if len(c) < 4:
            continue
        try:
            h = int(c[1], 16)
        except ValueError:
            continue
        ext = c[3].strip().lower()
        ent.setdefault(h, (c[0], c[2], ext, c[4] if len(c) > 4 else ''))
        per_arc[c[0]] += 1

print('RPF 条目 %d（唯一 hash %d）' % (sum(per_arc.values()), len(ent)))
hit = lib_h & set(ent)
print('库 hash ∩ 条目 hash = %d（%.1f%%）' % (len(hit), 100.0 * len(hit) / len(lib_h)))

ext_by_hit = Counter(ent[h][2] for h in hit)
print('命中条目扩展名:', dict(ext_by_hit.most_common(10)))

# 按顶层包分一下，方便"分批抽"
arc_by_hit = Counter(ent[h][0] for h in hit)
print('命中按包:', dict(arc_by_hit.most_common(12)))

miss = lib_h - set(ent)
json.dump({'lib': len(lib_h), 'hit': len(hit), 'miss': len(miss),
           'hits': ['0x%08x' % h for h in sorted(hit)],
           'ext': dict(ext_by_hit)},
          open(OUT, 'w', encoding='utf-8'), indent=1)
print('明细 %s' % OUT)

# 另外看看：没命中的那些，是不是 .ydd 里的（索引里 ydd 条目有多少）
ydd = sum(1 for h, v in ent.items() if v[2] in ('ydd',))
print('索引里 .ydd 条目 %d' % ydd)
