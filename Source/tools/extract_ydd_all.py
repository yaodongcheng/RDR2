# -*- coding: utf-8 -*-
"""把游戏包里所有 `.ydd`（DrawableDictionary，可含多个 drawable）抽到 `work/lib_gtxd/ydd_all/`。

## 为什么

`real_ytyp` 那 3,061 个 hash 有真实 ytyp 定义，但 RPF 里按 hash 找不到 `.ydr/.yft` ——
它们很可能被打包进 `.ydd` 字典（一个字典里放多个 drawable，条目 hash 是**子 drawable 的 hash**，
不是文件名 hash，所以按 hash 找 ydr/yft 永远找不到）。

盘点（`tools/rpf_inventory.py`）：**16,822 个 .ydd / 1.6 GB**。

    python tools/extract_ydd_all.py --dry
    python tools/extract_ydd_all.py
"""
import os
import sys
import json
import time
import shutil
import argparse
import subprocess

ROOT = r'D:/BrainMaker/大镖客2解包分析'
GAME = r'H:/EPICGAMES/RedDeadRedemption2'
DLL = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.dll')
OUT = os.path.join(ROOT, 'work/lib_gtxd/ydd_all')
TMP = os.path.join(ROOT, 'work/_ydd_tmp')
STATE = os.path.join(ROOT, 'work/extract_ydd_state.json')
INV = os.path.join(ROOT, 'work/rpf_inventory.json')
KEY = '.ydd'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--packs', nargs='+', default=[])
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--min', type=int, default=1)
    a = ap.parse_args()

    inv = json.load(open(INV, encoding='utf-8'))
    packs = a.packs or [k for k, v in inv.items() if (v.get(KEY) or {}).get('n', 0) >= a.min]
    print('[y] 计划 %d 个包，ydd 合计 %d 个 / %.1f GB'
          % (len(packs), sum(inv[p][KEY]['n'] for p in packs),
             sum(inv[p][KEY]['mb'] for p in packs) / 1024))
    if a.dry:
        for p in packs:
            print('   %-14s ydd %6d %7.0f MB' % (p, inv[p][KEY]['n'], inv[p][KEY]['mb']))
        return

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    try:
        st = json.load(open(STATE, encoding='utf-8'))
    except Exception:
        st = {'done': {}}
    have = set(f.lower() for f in os.listdir(OUT) if f.lower().endswith('.ydd'))
    print('[y] 已有 ydd %d' % len(have))

    t0 = time.time()
    for pk in packs:
        if pk in st['done']:
            continue
        arc = os.path.join(GAME, pk + '.rpf')
        if not os.path.exists(arc):
            continue
        d = os.path.join(TMP, pk)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)
        r = subprocess.run(['dotnet', DLL, 'extract', arc, d, '.ydd', '--recurse'],
                           capture_output=True, text=True, encoding='utf-8', errors='ignore')
        got = dup = 0
        for dp, _, fs in os.walk(d):
            for f in fs:
                if not f.lower().endswith('.ydd'):
                    continue
                low = f.lower()
                if low in have:
                    dup += 1
                    continue
                have.add(low)
                try:
                    shutil.move(os.path.join(dp, f), os.path.join(OUT, low))
                    got += 1
                except Exception as e:
                    print('   move 失败 %s: %s' % (f, e))
        shutil.rmtree(d, ignore_errors=True)
        st['done'][pk] = '%d new / %d dup' % (got, dup)
        json.dump(st, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False)
        print('[y] %-14s +%d（重复 %d）累计 %d，%.1f 分钟'
              % (pk, got, dup, len(have), (time.time() - t0) / 60))
    print('[y] 完成：ydd %d 个（%.1f 分钟）' % (len(have), (time.time() - t0) / 60))


if __name__ == '__main__':
    main()
