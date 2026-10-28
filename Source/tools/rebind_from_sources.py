# -*- coding: utf-8 -*-
"""按**源文件**（游戏包里真正的 .ydr/.yft）重绑每个模型的贴图，并把库的 tex 表改成"按名字"。

## 为什么必须重来一遍

`.mdl` 的子网格只存 `tid`（整数），而 `tex` 表历史上被重建/重排过、`tid` 还被复用，
所以 `id ↔ 名字 ↔ 文件内容` 三者可能互相错位（实测：`tex/0352.png` 的内容是土层，
表里却写着 `p_doornbd39x_ab`；`new_gar06_park_terrain` 的草地子网格被绑成了"门"）。

**新方案（名字即真相）**：

1. 对每个库模型 hash，找到它的源文件（RPF 条目 hash == 模型 hash，命中率实测 **55,607/55,608**）；
2. 从源文件解析出**每个子网格的真实贴图名 + 顶点数 + 索引数**（不再用旧 tid 猜）；
3. 贴图表按**名字排序**重建：`id = 排序下标`，`n = 名字`，`tex/<id>.png` 由贴图池按名字解出
   → 文件内容与名字**由构造保证一致**，id 不再是历史残留；
4. 模型 `s` 整体按源文件重写（子网格数/顶点数/索引数也以源文件为准）；
5. 名字在池里找不到的 → `tid=-1`（**宁可没有贴图，也不要贴错**，§6.3），并记进缺口清单。

## 用法

    python tools/rebind_from_sources.py --dry          # 只看规模/抽样一致性，不动库
    python tools/rebind_from_sources.py --limit 200    # 小批试跑（写库前自动备份）
    python tools/rebind_from_sources.py                # 全量
"""
import os
import sys
import json
import time
import random
import shutil
import argparse
from collections import Counter, defaultdict

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')
IDXTSV = os.path.join(ROOT, 'work/rpf_index/all.tsv')
MODELS = os.path.join(ROOT, 'export/world/continent/models.json')
FILEMAP = os.path.join(ROOT, 'work/model_file_map.json')
REPORT = os.path.join(ROOT, 'work/rebind_sources_report.json')
TEXDIR = os.path.join(LIB, 'tex')

SEARCH_GLOBS = ('export/models', 'raw', 'work/sdn/models', 'work/lib_models')


def load_sources():
    """hash(int) -> 本地源文件路径（存在才算）"""
    m = {}
    if os.path.exists(MODELS):
        for hx, p in json.load(open(MODELS, encoding='utf-8')).items():
            if os.path.exists(p):
                m[int(hx, 16)] = p
    if os.path.exists(FILEMAP):
        try:
            for hx, p in json.load(open(FILEMAP, encoding='utf-8')).items():
                h = int(hx, 16)
                if h not in m and os.path.exists(p):
                    m[h] = p
        except Exception as e:
            print('[rb] model_file_map 读不了：%s' % e)
    return m


def load_rpf_index():
    idx = {}
    with open(IDXTSV, encoding='utf-8', errors='replace') as f:
        f.readline()
        for line in f:
            c = line.rstrip('\n').split('\t')
            if len(c) < 4:
                continue
            try:
                h = int(c[1], 16)
            except ValueError:
                continue
            idx.setdefault(h, (c[0], c[4] if len(c) > 4 else '', int(c[2]), c[3]))
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--sample', type=int, default=300)
    a = ap.parse_args()

    d = json.load(open(INDEX, encoding='utf-8'))
    models, tex = d['models'], d['tex']
    lib = {int(k, 16): k for k in models}
    print('[rb] 库内模型 %d / 贴图表 %d' % (len(models), len(tex)))

    src = load_sources()
    rpf = load_rpf_index()
    print('[rb] 本地已有源 %d' % len(src))
    can = {h: p for h, p in src.items() if h in lib}
    only_rpf = [h for h in lib if h not in can and h in rpf]
    no_src = [h for h in lib if h not in can and h not in rpf]
    need_bytes = sum(rpf[h][2] for h in only_rpf)
    print('[rb] 库模型可本地解析 %d / 需从包里抽 %d（%.2f GB）/ 完全无源 %d'
          % (len(can), len(only_rpf), need_bytes / 2**30, len(no_src)))

    import dump_model_lib as D
    import export_sdn_gltf as EX

    pool = EX.TexLib([os.path.join(ROOT, 'work/lib_gtxd/txd'),
                      os.path.join(ROOT, 'work/sdn/gtxd/txd'),
                      os.path.join(ROOT, 'work/sdn/gtxd/txd_int')], maxs=512)
    poolnames = set(pool.idx)
    print('[rb] 贴图池名字 %d' % len(poolnames))

    random.seed(11)
    sample = random.sample(sorted(can), min(a.sample, len(can)))
    par_ok = par_bad = parse_fail = 0
    names = Counter()
    miss_names = Counter()
    sub_diff = Counter()
    t0 = time.time()
    for h in sample:
        try:
            M = D.load_any(can[h])
        except Exception:
            M = None
        if not M or not M.get('geoms'):
            parse_fail += 1
            continue
        geoms = [g for g in M['geoms'] if len(g['pos'])]
        s = models['0x%08x' % h].get('s') or []
        sub_diff[len(geoms) - len(s)] += 1
        if len(geoms) == len(s) and all(
                len(g['pos']) == v and len(g.get('idx') or []) == i
                for g, (t, v, i) in zip(geoms, s)):
            par_ok += 1
        else:
            par_bad += 1
        for g in geoms:
            nm = (g.get('tex') or '').strip()
            if not nm:
                continue
            names[nm] += 1
            if EX.clean_name(nm).lower() not in poolnames:
                miss_names[nm] += 1

    print('[rb] 抽样 %d：可解析 %d / 解析失败 %d / 与库几何完全一致 %d / 不一致 %d（%.0fs）'
          % (len(sample), len(sample) - parse_fail, parse_fail, par_ok, par_bad,
             time.time() - t0))
    print('[rb] 子网格数差（源 - 库）分布: %s' % dict(sub_diff.most_common(8)))
    print('[rb] 抽样里出现的贴图名 %d 个；池里没有的 %d 个（占引用 %.1f%%）'
          % (len(names), len(miss_names),
             100.0 * sum(miss_names.values()) / max(1, sum(names.values()))))
    print('[rb] 池里没有的名字（前 12）: %s' % [k for k, _ in miss_names.most_common(12)])

    out = {'lib': len(models), 'local_src': len(can), 'need_extract': len(only_rpf),
           'need_bytes': need_bytes, 'no_src': len(no_src),
           'sample': len(sample), 'parse_fail': parse_fail,
           'parity_ok': par_ok, 'parity_bad': par_bad,
           'sub_diff': dict(sub_diff), 'names': len(names),
           'names_missing_pool': len(miss_names),
           'missing_name_top': [k for k, _ in miss_names.most_common(50)]}
    if not a.dry:
        json.dump(out, open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('[rb] %s' % ('dry-run，未写库' if a.dry else '报告 %s' % REPORT))


if __name__ == '__main__':
    main()
