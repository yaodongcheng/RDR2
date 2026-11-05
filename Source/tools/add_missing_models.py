# -*- coding: utf-8 -*-
"""把「raw 里已有、但没进模型库」的模型补进 lib_native（增量，不覆盖已有 index）。

🔴 本工具是本项目**唯一**的「模型入库」入口 —— 遇到"模型缺失"先想想是不是没跑它，
   **不要提议重新从 RPF 抽取**（raw/all_packs 已是全量解包产物，见 docs/AGENTS.md §0.1）。
   ⚠️ 下面的 `SKIP` 正则**故意排除** LOD / 阴影 / 反射 / 代理类（`slod|_lod|shadow|reflection|prox`）
   —— 当初只为补"可见"模型。要补远景 LOD 时必须先加开关放开这一组，否则它们永远进不来。

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
# 🔴 2026-11-05：远景 LOD 单独一组。默认仍排除（补进**场景**会变杂物），
# `--include-lod` 时才放行 —— 放过之后它们只会经**远景库**进场景
# （`build_entities` 在场景模式下对 `lod` 类是直接跳过的），不会污染活动区。
LOD_KEYS = re.compile(r'slod|_lod', re.I)


def _skipped(path, include_lod):
    b = os.path.basename(path)
    if include_lod:
        b = LOD_KEYS.sub('', b)      # 先摘掉 lod 关键词，其余排除规则照旧
    return bool(SKIP.search(b))


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF


def collect(include_lod=False):
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
              and not _skipped(p, include_lod)]
    return have, missing, hits, usable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--include-lod', action='store_true',
                    help='连远景 LOD 一起补（默认排除；它们只会经远景库进场景）')
    a = ap.parse_args()

    have, missing, hits, usable = collect(a.include_lod)
    print('[add] 库里已有 %d；实体缺模型 %d；raw 命中 %d；可用 %d（include_lod=%s）' % (
        len(have), len(missing), len(hits), len(usable), a.include_lod))
    if a.report or not a.apply:
        for h, p in usable[:15]:
            print('[add]   %s %s' % (hex(h), os.path.basename(p)))
        return

    idx = json.load(open(os.path.join(LIB, 'index.json'), encoding='utf-8'))
    tex = DL.Tex(LIB, 512)
    # 🔴 2026-11-05：必须**接着现有贴图表往下加**。`DL.Tex()` 默认从空表开始，
    # 直接 `idx['tex'] = tex.meta` 会把整张 tex 表换成"本次新增的那几张"
    #（最高原则 §6.4 记过这个事故：tex 表被更小的池覆盖 ⇒ 全图贴图错位、32.5% 子网格越界）。
    tex.meta = list(idx.get('tex') or [])
    for _i, _e in enumerate(tex.meta):
        _n = (_e or {}).get('n')
        if _n:
            tex.by_name.setdefault(_n.lower(), _i)
    print('[add] 贴图表接续：已有 %d 条' % len(tex.meta))
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
