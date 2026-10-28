# -*- coding: utf-8 -*-
"""给所有 `.ydd`（DrawableDictionary）建"**子 drawable 的 hash → (文件, body 偏移)**"索引。

## 为什么需要

`real_ytyp` 那 3,061 个 hash 有真实 ytyp 定义，但按 hash 在 RPF 条目里找不到 `.ydr/.yft` ——
因为它们被**打包进 `.ydd` 字典**：字典文件的条目 hash 是"子 drawable 的 hash"，
和文件名 hash 不是一回事，所以"按 hash 找 ydr"永远找不到。

索引建好后就能回答：这 3,061 个 hash 里有多少真的躺在 `.ydd` 里、在哪个文件、哪个偏移。

    python tools/ydd_index.py
    python tools/ydd_index.py --out work/ydd_index.json
"""
import os
import sys
import json
import time
import argparse
import glob

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import rdr2_ydr as Y

OUT = os.path.join(ROOT, 'work/ydd_index.json')
DIRS = ['work/lib_gtxd/ydd_all']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dirs', nargs='+', default=DIRS)
    ap.add_argument('--out', default=OUT)
    a = ap.parse_args()

    files = []
    for d in a.dirs:
        p = d if os.path.isabs(d) else os.path.join(ROOT, d)
        files += glob.glob(os.path.join(p, '**', '*.ydd'), recursive=True)
    files = sorted(set(files))
    print('[yd] ydd %d 个' % len(files))

    idx = {}
    bad = 0
    empty = 0
    total = 0
    t0 = time.time()
    for i, f in enumerate(files):
        try:
            res = Y.Res(open(f, 'rb').read())
            ents = Y.parse_drawable_dictionary(res)
        except Exception:
            bad += 1
            continue
        if not ents:
            empty += 1
        rel = os.path.relpath(f, ROOT).replace('\\', '/')
        for h, off in ents:
            total += 1
            k = '0x%08x' % h
            if k not in idx:
                idx[k] = [rel, off]
        if (i + 1) % 2000 == 0:
            print('[yd] %d/%d  子 drawable %d（唯一 %d，%.0fs）'
                  % (i + 1, len(files), total, len(idx), time.time() - t0))

    json.dump(idx, open(a.out, 'w', encoding='utf-8'), separators=(',', ':'))
    print('[yd] 完成：文件 %d（坏 %d / 空字典 %d）→ 子 drawable %d / 唯一 hash %d，%.1f MB，%.1f 分钟'
          % (len(files), bad, empty, total, len(idx),
             os.path.getsize(a.out) / 2**20, (time.time() - t0) / 60))


if __name__ == '__main__':
    main()
