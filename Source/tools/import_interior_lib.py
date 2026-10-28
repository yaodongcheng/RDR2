# -*- coding: utf-8 -*-
"""把解出来的室内包（raw/_interiors/**）里的 .ydr 批量导入 lib_native（增量，不覆盖）。

室内模型不是「ymap 实体」，所以不会被 add_missing_models.py 命中；
它们要靠 MLO 布局摆放，先把模型入库才能做装配。

用法：
    uv run python tools/import_interior_lib.py --report
    uv run python tools/import_interior_lib.py --apply
"""
import os
import sys
import json
import time
import glob
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import dump_model_lib as DL   # noqa: E402

LIB = os.path.join(ROOT, 'assets/lib_native')
SRC = os.path.join(ROOT, 'raw/_interiors')


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args()

    idx = json.load(open(os.path.join(LIB, 'index.json'), encoding='utf-8'))
    have = {int(k, 16) for k in idx['models']}
    files = [p for p in glob.glob(os.path.join(SRC, '**', '*.ydr'), recursive=True)]
    todo = []
    for p in files:
        h = joaat(os.path.splitext(os.path.basename(p))[0])
        if h not in have:
            todo.append((h, p))
    print('[int] .ydr 文件 %d，库里没有的 %d' % (len(files), len(todo)))
    if a.report or not a.apply:
        for h, p in todo[:10]:
            print('[int]   %s %s' % (hex(h), os.path.basename(p)))
        return

    tex = DL.Tex(LIB, 512)
    added = skipped = 0
    t0 = time.time()
    for h, p in todo:
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
        except Exception:
            skipped += 1
    idx['tex'] = tex.meta
    json.dump(idx, open(os.path.join(LIB, 'index.json'), 'w'), separators=(',', ':'))
    print('[int] 新增室内模型 %d（跳过 %d），库总数 %d，用时 %.0fs' % (
        added, skipped, len(idx['models']), time.time() - t0))


if __name__ == '__main__':
    main()
