# -*- coding: utf-8 -*-
"""用新的全量 ytd 索引（49,714 个名字）衡量"源模型引用的贴图名"覆盖率。

输出：还缺哪些名字、缺多少、按前缀聚类（判断该去哪个包抽 ytd）。
"""
import os
import sys
import json
import random
from collections import Counter

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import dump_model_lib as D
import export_sdn_gltf as EX

LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')
TEXIDX = os.path.join(ROOT, 'work/tex_name_index.json')
MODELS = os.path.join(ROOT, 'export/world/continent/models.json')
FILEMAP = os.path.join(ROOT, 'work/model_file_map.json')
OUT = os.path.join(ROOT, 'work/tex_coverage_report.json')

d = json.load(open(INDEX, encoding='utf-8'))
models = d['models']
lib = {int(k, 16) for k in models}

src = {}
for hx, p in json.load(open(MODELS, encoding='utf-8')).items():
    if os.path.exists(p):
        src[int(hx, 16)] = p
if os.path.exists(FILEMAP):
    for hx, p in json.load(open(FILEMAP, encoding='utf-8')).items():
        h = int(hx, 16)
        if h not in src and os.path.exists(p):
            src[h] = p

texidx = json.load(open(TEXIDX, encoding='utf-8'))
print('[cov] ytd 索引名字 %d；本地源 %d' % (len(texidx), len(src)))

cand = sorted(h for h in src if h in lib)
random.seed(3)
sample = random.sample(cand, min(400, len(cand)))
names = Counter()
miss = Counter()
parse_fail = 0
for h in sample:
    try:
        M = D.load_any(src[h])
    except Exception:
        M = None
    if not M or not M.get('geoms'):
        parse_fail += 1
        continue
    for g in M['geoms']:
        nm = (g.get('tex') or '').strip()
        if not nm:
            continue
        k = EX.clean_name(nm).lower()
        names[k] += 1
        if k not in texidx:
            miss[k] += 1

tot = sum(names.values())
print('[cov] 抽样 %d（解析失败 %d）：贴图引用 %d 次 / 唯一名 %d'
      % (len(sample), parse_fail, tot, len(names)))
hit = tot - sum(miss.values())
print('[cov] 索引能命中 %d 次（%.1f%%）；没命中 %d 次 / 唯一 %d 个（%.1f%%）'
      % (hit, 100.0 * hit / max(1, tot), sum(miss.values()), len(miss),
         100.0 * sum(miss.values()) / max(1, tot)))
pref = Counter(k.split('_')[0] for k in miss)
print('[cov] 缺失名字前缀 top: %s' % dict(pref.most_common(15)))
print('[cov] 缺失样例: %s' % [k for k, _ in miss.most_common(20)])
json.dump({'sample': len(sample), 'refs': tot, 'names': len(names),
           'miss_refs': sum(miss.values()), 'miss_names': len(miss),
           'missing': [k for k, _ in miss.most_common(400)]},
          open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('[cov] 报告 %s' % OUT)
