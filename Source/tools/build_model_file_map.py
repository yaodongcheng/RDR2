# -*- coding: utf-8 -*-
"""把磁盘上散落的 `.ydr/.yft` 按 **joaat(文件名)** 汇总成 `hash -> 路径` 映射。

`work/model_file_map.json` 是 `rebind_textures` / `rebind_models_from_sources` 的输入，
之前只有 19,780 条（来自 export/models 与 raw 的旧扫描）。本轮从游戏包按 RPF 条目 hash
抽出了 `raw/_libsrc/` 里的 2.7 万个源文件，必须重新汇总，否则重绑会漏掉它们。

    python tools/build_model_file_map.py --dirs raw/_libsrc raw export/models work/sdn/models
"""
import os
import sys
import json
import glob
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
OUT = os.path.join(ROOT, 'work/model_file_map.json')
DEFAULT_DIRS = ['raw/_libsrc', 'raw/_missing', 'export/models', 'raw', 'work/sdn/models',
                'work/lib_models']


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
    ap.add_argument('--dirs', nargs='+', default=DEFAULT_DIRS)
    a = ap.parse_args()

    old = {}
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding='utf-8'))
        except Exception:
            old = {}
    m = {k: v for k, v in old.items() if os.path.exists(v)}
    print('[map] 旧映射 %d（有效 %d）' % (len(old), len(m)))

    added = 0
    scanned = 0
    for d in a.dirs:
        p = d if os.path.isabs(d) else os.path.join(ROOT, d)
        if not os.path.isdir(p):
            continue
        for f in glob.glob(os.path.join(p, '**', '*'), recursive=True):
            if not os.path.isfile(f):
                continue
            low = f.lower()
            if not low.endswith(('.ydr', '.yft')):
                continue
            scanned += 1
            base = os.path.splitext(os.path.basename(f))[0]
            if base.lower().startswith('0x'):
                try:
                    h = int(base[2:], 16)
                except ValueError:
                    continue
            else:
                h = joaat(base)
            k = '0x%08x' % h
            # 优先 raw/_libsrc（本轮新抽的、来源最确定）
            if k not in m:
                m[k] = f
                added += 1
        print('[map] %-24s 累计扫描 %d，映射 %d（+%d）' % (d, scanned, len(m), added))

    json.dump(m, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    print('[map] 写入 %s：%d 条（新增 %d），%.1f MB'
          % (OUT, len(m), added, os.path.getsize(OUT) / 2**20))


if __name__ == '__main__':
    main()
