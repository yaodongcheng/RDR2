# -*- coding: utf-8 -*-
"""把游戏里**全部**铁路 RPF 包抽出来（源侧闭环，不按"以前抽过哪些"猜）。

为什么要重写这个：2026-10-30 发现安尼斯堡整条铁路缺失，根因是
`roughly 20 个铁路包只抽了 4 个`，而当时的目录结构（`raw/rails_extract/<缩写>/`）
根本看不出"哪个包抽过、哪个没抽过"。

本脚本的做法：
  1. 用 `rdr2rpf.exe find <levels_i.rpf> rails` 从**游戏目录表**枚举全部铁路包（权威清单）；
  2. 逐个抽到 `raw/rails_all/<包名>/`，并在 `<包名>/.done` 里记录包大小；
  3. 已存在 `.done` 且大小一致的跳过（可反复执行）。

    python tools/extract_all_rail_packs.py --list
    python tools/extract_all_rail_packs.py
"""
import os
import re
import sys
import glob
import json
import time
import shutil
import argparse
import subprocess

ROOT = r'D:/BrainMaker/大镖客2解包分析'
GAME = r'H:/EPICGAMES/RedDeadRedemption2'
RP = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe')
OUT = os.path.join(ROOT, 'raw/rails_all')
LOGS = r'D:/BrainMaker/_logs'


def run_rpf(args, log):
    """走 run.cmd（沙箱下直接起管道会 Access denied）。与 PowerShell 里那条命令同构。"""
    line = ' '.join(['"%s"' % a for a in [RP] + list(args)])
    subprocess.run('cmd /c tools\\run.cmd "%s" %s' % (log, line), cwd=ROOT, capture_output=True)


def list_packs():
    packs = {}
    os.makedirs(LOGS, exist_ok=True)
    for i in range(8):
        lv = os.path.join(GAME, 'levels_%d.rpf' % i)
        if not os.path.exists(lv):
            continue
        log = os.path.join(LOGS, 'rail_enum_%d.log' % i)
        run_rpf(['find', lv, 'rails'], log)
        if not os.path.exists(log):
            continue
        for ln in open(log, encoding='utf-8', errors='ignore'):
            m = re.match(r'\s*(\d+)\s+(\S.*)$', ln)
            if not m:
                continue
            path = m.group(2).strip()
            if path.lower().endswith('.rpf') and 'rails' in path.lower():
                packs[path] = dict(size=int(m.group(1)), lv=lv)
    return packs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()

    packs = list_packs()
    print('[src] 游戏目录表里的铁路包 %d 个，共 %.1f MB'
          % (len(packs), sum(v['size'] for v in packs.values()) / 1e6))
    for p in sorted(packs):
        print('   %-58s %7.1f MB' % (p, packs[p]['size'] / 1e6))
    if a.list:
        return

    os.makedirs(OUT, exist_ok=True)
    ok = skip = fail = 0
    t0 = time.time()
    for n, (path, meta) in enumerate(sorted(packs.items()), 1):
        base = os.path.basename(path)[:-4]
        dst = os.path.join(OUT, base)
        done = os.path.join(dst, '.done')
        if os.path.exists(done) and open(done).read().strip() == str(meta['size']):
            skip += 1
            continue
        shutil.rmtree(dst, ignore_errors=True)
        os.makedirs(dst, exist_ok=True)
        log = os.path.join(LOGS, 'rail_pack_%s.log' % base)
        run_rpf(['extract', meta['lv'], dst, path], log)
        inner = glob.glob(os.path.join(dst, '**', '*.rpf'), recursive=True)
        if not inner:
            print('[%2d/%d] %-42s ✗ 内层 rpf 没出来' % (n, len(packs), base))
            fail += 1
            continue
        run_rpf(['extract', inner[0], dst, ''], os.path.join(LOGS, 'rail_inner_%s.log' % base))
        nf = sum(len(fs) for _, _, fs in os.walk(dst)) - 2
        with open(done, 'w') as f:
            f.write(str(meta['size']))
        print('[%2d/%d] %-42s %4d 个文件  (%.1f 分)'
              % (n, len(packs), base, nf, (time.time() - t0) / 60))
        ok += 1
    print('[src] 抽出 %d / 跳过 %d / 失败 %d → %s' % (ok, skip, fail, OUT))


if __name__ == '__main__':
    main()
