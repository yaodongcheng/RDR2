# -*- coding: utf-8 -*-
"""把**所有** `.ytd`（贴图字典）从游戏包抽到 `work/lib_gtxd/txd_all/`（扁平、按文件名去重）。

## 为什么要全抽

`rebind_textures` 用的池只有 3 个目录 / 6,431 个名字；源模型引用的贴图名有 **36.2% 不在里面**
（见 `tools/tex_coverage.py`）。这些名字的 ytd 大多躺在 **props 包的内部**
（`levels/rdr3/props/generic/p_xxx.rpf` 里直接就有 `.ytd`），不是只放在 `*_txd.rpf` 里 ——
所以按包名过滤（`--only txd`）抽不到。

`rdr2rpf` 的 `extract <pack> <out> .ytd --recurse` 会自己下钻嵌套包，这里只做：
逐个顶层包 → 调用 → 把嵌套目录里的 `.ytd` 拍平到 OUT（同名跳过）→ 记录进度可续跑。

    python tools/extract_ytd_all.py --dry
    python tools/extract_ytd_all.py                       # 全量（约 41 GB）
    python tools/extract_ytd_all.py --packs levels_3      # 单包
"""
import os
import sys
import json
import time
import shutil
import argparse
import subprocess
from collections import Counter

ROOT = r'D:/BrainMaker/大镖客2解包分析'
GAME = r'H:/EPICGAMES/RedDeadRedemption2'
DLL = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.dll')
OUT = os.path.join(ROOT, 'work/lib_gtxd/txd_all')
TMP = os.path.join(ROOT, 'work/_ytd_tmp')
STATE = os.path.join(ROOT, 'work/extract_ytd_state.json')
INV = os.path.join(ROOT, 'work/rpf_inventory.json')
EXIST_DIRS = ['work/lib_gtxd/txd', 'work/lib_gtxd/txd_world', 'work/lib_gtxd/txd_game',
              'work/sdn/gtxd/txd', 'work/sdn/gtxd/txd_int', 'work/towns', OUT]


def existing_names():
    s = set()
    for d in EXIST_DIRS:
        p = d if os.path.isabs(d) else os.path.join(ROOT, d)
        if not os.path.isdir(p):
            continue
        for dp, _, fs in os.walk(p):
            for f in fs:
                if f.lower().endswith('.ytd'):
                    s.add(f.lower())
    return s


def load_state():
    try:
        return json.load(open(STATE, encoding='utf-8'))
    except Exception:
        return {'done': {}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--packs', nargs='+', default=[])
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--min-ytd', type=int, default=1)
    a = ap.parse_args()

    inv = json.load(open(INV, encoding='utf-8'))
    packs = a.packs or [k for k, v in inv.items()
                        if (v.get('.ytd') or {}).get('n', 0) >= a.min_ytd]
    print('[x] 计划 %d 个包，ytd 合计 %d 个 / %.1f GB'
          % (len(packs), sum(inv[p]['.ytd']['n'] for p in packs),
             sum(inv[p]['.ytd']['mb'] for p in packs) / 1024))
    if a.dry:
        for p in packs:
            print('   %-14s ytd %6d  %7.0f MB' % (p, inv[p]['.ytd']['n'], inv[p]['.ytd']['mb']))
        return

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    st = load_state()
    have = existing_names()
    print('[x] 已有 ytd 名字 %d' % len(have))

    t0 = time.time()
    for pk in packs:
        if pk in st['done']:
            print('[x] %s 已完成（%s），跳过' % (pk, st['done'][pk]))
            continue
        arc = os.path.join(GAME, pk + '.rpf')
        if not os.path.exists(arc):
            print('[x] 缺 %s' % arc)
            continue
        d = os.path.join(TMP, pk)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)
        r = subprocess.run(['dotnet', DLL, 'extract', arc, d, '.ytd', '--recurse'],
                           capture_output=True, text=True, encoding='utf-8', errors='ignore')
        got = dup = 0
        for dp, _, fs in os.walk(d):
            for f in fs:
                if not f.lower().endswith('.ytd'):
                    continue
                low = f.lower()
                if low in have:
                    dup += 1
                    continue
                have.add(low)
                dst = os.path.join(OUT, low)
                try:
                    shutil.move(os.path.join(dp, f), dst)
                    got += 1
                except Exception as e:
                    print('   move 失败 %s: %s' % (f, e))
        shutil.rmtree(d, ignore_errors=True)
        st['done'][pk] = '%d new / %d dup' % (got, dup)
        json.dump(st, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False)
        print('[x] %-14s +%d（重复 %d）累计 %d，%.0f 分钟  %s'
              % (pk, got, dup, len(have), (time.time() - t0) / 60,
                 (r.stderr or '').strip().splitlines()[-1:] or ''))
    print('[x] 完成：ytd %d 个，目录 %s（%.0f 分钟）'
          % (len(have), OUT, (time.time() - t0) / 60))


if __name__ == '__main__':
    main()
