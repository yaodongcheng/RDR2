# -*- coding: utf-8 -*-
"""给磁盘上所有 `.ytd` 建一张 **名字 → 贴图位置** 的索引（只存描述符，不存文件内容）。

## 为什么不用现成的 `EX.TexLib`

`TexLib` 把每个 ytd 的**整个文件字节**留在 `self.idx` 里（`(y, t)` 持着 `y`）。
`work/lib_gtxd/txd_game` 有 19,058 个 ytd / **28.65 GB**，一装进内存就爆。
本工具只记 `(文件路径, sys_size, gfx_off, w, h, fmt)`，按需再读文件解一张，
峰值内存 = 单个 ytd。

## 为什么要建它

源模型里引用的贴图名有 **45.9% 不在** `rebind_textures` 用的那个池（3 个目录 / 6,431 名）里 ——
因为池根本没包含 `txd_world`(646 个 / 3.58 GB) 和 `txd_game`(19,058 个 / 28.65 GB)。
建完索引就能回答："这些名字到底在磁盘上有没有图"。

## 用法

    python tools/tex_index_ytd.py                 # 扫全部默认目录
    python tools/tex_index_ytd.py --dirs A B --out x.json

产物 `work/tex_name_index.json`：
    {"<名字小写>": {"f": 相对路径, "sys": n, "gfx": n, "w": n, "h": n, "fmt": n, "size": n}}
同名的取 **面积最大** 的那张（与 `TexLib` 的选择口径一致）。
"""
import os
import re
import sys
import json
import time
import glob
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import rdr2_ytd as T

OUT = os.path.join(ROOT, 'work/tex_name_index.json')
DEFAULT_DIRS = [
    'work/lib_gtxd/txd',
    'work/lib_gtxd/txd_world',
    'work/lib_gtxd/txd_game',
    'work/lib_gtxd/txd_all',
    'work/sdn/gtxd/txd',
    'work/sdn/gtxd/txd_int',
    'work/towns',
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dirs', nargs='+', default=DEFAULT_DIRS)
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--max-files', type=int, default=0)
    a = ap.parse_args()

    files = []
    for d in a.dirs:
        p = d if os.path.isabs(d) else os.path.join(ROOT, d)
        files += glob.glob(os.path.join(p, '**', '*.ytd'), recursive=True)
    if a.max_files:
        files = files[:a.max_files]
    files = sorted(set(files))
    total_gb = sum(os.path.getsize(f) for f in files) / 2**30
    print('[ti] 待扫 ytd %d 个 / %.2f GB' % (len(files), total_gb))

    idx = {}
    bad = 0
    empty = 0
    t0 = time.time()
    for i, f in enumerate(files):
        try:
            data = open(f, 'rb').read()
        except Exception:
            bad += 1
            continue
        try:
            y = T.Ytd(data)
            texs = y.textures_any()
            sys_size = y.sys_size
        except Exception:
            bad += 1
            continue
        if not texs:
            empty += 1
        rel = os.path.relpath(f, ROOT).replace('\\', '/')
        for t in texs:
            nm = (t.get('name') or '').strip().lower()
            if not nm:
                continue
            area = t['w'] * t['h']
            cur = idx.get(nm)
            if cur is None or area > cur['w'] * cur['h']:
                idx[nm] = dict(f=rel, sys=sys_size, gfx=t['gfx_off'],
                               w=t['w'], h=t['h'], fmt=t['fmt'], size=t.get('size', 0))
        del data, y, texs
        if (i + 1) % 2000 == 0:
            print('[ti] %d/%d  名字 %d（%.0fs）' % (i + 1, len(files), len(idx), time.time() - t0))

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(idx, open(a.out, 'w', encoding='utf-8'), separators=(',', ':'))
    mb = os.path.getsize(a.out) / 2**20
    print('[ti] 完成：ytd %d（坏 %d / 0 纹理 %d）→ 唯一名字 %d，%.1f MB，%.1f 分钟'
          % (len(files), bad, empty, len(idx), mb, (time.time() - t0) / 60))


if __name__ == '__main__':
    main()
