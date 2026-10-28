# -*- coding: utf-8 -*-
"""把游戏所有 RPF（含嵌套）里的 drawable 条目索引成 TSV：`archive \t hash \t size \t ext \t name`。

用 `rdr2rpf hashindex`（C#，原地读嵌套 TOC，不解包、不落中间 57 GB）。

    uv run python tools/rpf_index.py                      # 默认全量（levels_0..7 + packs + data …）
    uv run python tools/rpf_index.py --rpf levels_1        # 单包
    uv run python tools/rpf_index.py --merge               # 只把分片合并成 all.tsv

产物：`work/rpf_index/<pack>.tsv`（分片）+ `work/rpf_index/all.tsv`（合并）。
可断点续跑：已存在且非空的包直接跳过（--force 重跑）。
"""
import os
import sys
import time
import argparse
import subprocess

ROOT = r'D:/BrainMaker/大镖客2解包分析'
GAME = r'H:/EPICGAMES/RedDeadRedemption2'
DLL = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.dll')
OUT = os.path.join(ROOT, 'work/rpf_index')

PACKS = (['levels_%d' % i for i in range(8)]
         + ['packs_0', 'packs_1', 'data_0', 'common_0', 'hd_0', 'rowpack_0',
            'update_1', 'update_2', 'update_3', 'update_4', 'shaders_x64'])


def merge():
    allp = os.path.join(OUT, 'all.tsv')
    n = 0
    with open(allp, 'w', encoding='utf-8', newline='') as w:
        for pk in PACKS:
            p = os.path.join(OUT, pk + '.tsv')
            if not os.path.exists(p) or os.path.getsize(p) == 0:
                continue
            with open(p, encoding='utf-8') as f:
                for line in f:
                    w.write(line)
                    n += 1
    print('[index] 合并 %d 行 -> %s（%.1f MB）'
          % (n, allp, os.path.getsize(allp) / 1e6))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rpf', nargs='+', default=PACKS)
    ap.add_argument('--exts', default='ydr,yft')
    ap.add_argument('--depth', type=int, default=6)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--merge', action='store_true')
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    if a.merge:
        merge()
        return

    t0 = time.time()
    for pk in a.rpf:
        arc = os.path.join(GAME, pk + '.rpf')
        out = os.path.join(OUT, pk + '.tsv')
        if not os.path.exists(arc):
            print('[index] 没有 %s，跳过' % arc)
            continue
        if os.path.exists(out) and os.path.getsize(out) > 0 and not a.force:
            print('[index] %s 已有（%.1f MB），跳过' % (pk, os.path.getsize(out) / 1e6))
            continue
        t1 = time.time()
        r = subprocess.run(['dotnet', DLL, 'hashindex', arc, out, a.exts, str(a.depth)],
                           capture_output=True, text=True, encoding='utf-8', errors='ignore')
        tail = (r.stderr or '').strip().splitlines()
        print('[index] %-14s rc=%d %s（%.0fs）'
              % (pk, r.returncode, tail[-1] if tail else '', time.time() - t1))
        for ln in tail[:-1]:
            if 'not RPF8' in ln or 'fail' in ln.lower():
                print('        ' + ln)
    print('[index] 全部结束，用时 %.1f 分钟' % ((time.time() - t0) / 60))
    merge()


if __name__ == '__main__':
    main()
