# -*- coding: utf-8 -*-
"""把「raw 里已有、但没进模型库」的模型补进 lib_native（增量，不覆盖已有 index）。

## 背景

装配时是「archetype hash → 名字 → 抽 .ydr」。名字查不到的实体就没进库，
但其中有一部分 **.ydr 其实早就解包在 raw/ 里**（本项目 45 GB 解包产物）。
本脚本用「文件名 joaat == 实体 hash」把它们找出来并转成 .mdl：

    实测：缺模型的实体 52,653 个，其中 1,223 个在 raw 里能找到同名文件；
    排除 LOD/代理/VFX/decal 后剩 251 个（166 .ydr + 51 .yft + 34 其它）。

## 用法

    uv run python tools/add_missing_models.py --report      # 只统计
    uv run python tools/add_missing_models.py --apply       # 转换并合并 index.json
"""
import os
import re
import sys
import json
import glob
import time
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import dump_model_lib as DL   # noqa: E402

LIB = os.path.join(ROOT, 'assets/lib_native')
SKIP = re.compile(r'slod|_lod|vfx|prox|_em_|audio|shadow|reflection|_strm|_dec\b|_det\b|milo', re.I)


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF


def collect():
    raw = {}
    for dp, _, fs in os.walk(os.path.join(ROOT, 'raw')):
        for f in fs:
            stem = os.path.splitext(f)[0]
            if stem:
                raw.setdefault(joaat(stem), os.path.join(dp, f))
    idx = json.load(open(os.path.join(LIB, 'index.json'), encoding='utf-8'))
    have = {int(k, 16) for k in idx['models']}
    ent = set()
    for p in glob.glob(os.path.join(ROOT, 'export/world/continent/tiles/*.json')):
        if p.endswith('.bak'):
            continue
        for e in json.load(open(p, encoding='utf-8')):
            ent.add(e[0])
    missing = ent - have
    hits = [(h, raw[h]) for h in missing if h in raw]
    usable = [(h, p) for h, p in hits
              if os.path.splitext(p)[1].lower() in ('.ydr', '.yft')
              and not SKIP.search(os.path.basename(p))]
    return have, missing, hits, usable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args()

    have, missing, hits, usable = collect()
    print('[add] 库里已有 %d；实体缺模型 %d；raw 命中 %d；可用 %d' % (
        len(have), len(missing), len(hits), len(usable)))
    if a.report or not a.apply:
        for h, p in usable[:15]:
            print('[add]   %s %s' % (hex(h), os.path.basename(p)))
        return

    idx = json.load(open(os.path.join(LIB, 'index.json'), encoding='utf-8'))
    tex = DL.Tex(LIB, 512)
    added = skipped = 0
    t0 = time.time()
    for h, p in usable:
        try:
            M = DL.load_any(p)
            if not M:
                skipped += 1
                continue
            e = DL.write_model(M, h, LIB, tex)
            if not e:
                skipped += 1
                continue
            idx['models'][hex(h)] = {k: e[k] for k in ('f', 'b', 's')}
            added += 1
        except Exception as ex:
            skipped += 1
            if skipped <= 5:
                print('[add]   跳过 %s (%s)' % (os.path.basename(p), ex))
    idx['tex'] = tex.meta
    json.dump(idx, open(os.path.join(LIB, 'index.json'), 'w'), separators=(',', ':'))
    print('[add] 新增模型 %d（跳过 %d），库总数 %d，用时 %.1fs' % (
        added, skipped, len(idx['models']), time.time() - t0))


if __name__ == '__main__':
    main()
