# -*- coding: utf-8 -*-
"""盘点游戏包里 `.ytd`（贴图字典）和 `.ydd`（drawable 字典）的数量与体积。

只读 TOC（`rdr2rpf hashindex`），不解压。用来回答两件事：

1. 贴图还缺 36.2% 的名字 → 需要从哪些包抽 ytd？抽多少 GB？
2. `real_ytyp` 3,061 个 hash 找不到 drawable → 包里到底有没有 `.ydd`？有多少？

    python tools/rpf_inventory.py --exts ytd,ydd
"""
import os
import sys
import json
import time
import argparse
import subprocess
from collections import defaultdict

ROOT = r'D:/BrainMaker/大镖客2解包分析'
GAME = r'H:/EPICGAMES/RedDeadRedemption2'
DLL = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.dll')
OUTDIR = os.path.join(ROOT, 'work/rpf_inv')
REPORT = os.path.join(ROOT, 'work/rpf_inventory.json')
# 2026-11-01：包表改成直接扫游戏目录。旧版硬编码 19 个包，
# 漏了 textures_0 / textures_1 / anim_0 / movies_0 / appdata0_update ——
# 后果是 extract_ytd_all 从没跑过 textures_0，27% 的贴图（5,875 张）一直没抽。
def list_packs():
    out = []
    for f in sorted(os.listdir(GAME)):
        if f.lower().endswith('.rpf') and os.path.isfile(os.path.join(GAME, f)):
            out.append(os.path.splitext(f)[0])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exts', nargs='+', default=['ydr,yft,ydd,ytd,ybn'],
                    help='扩展名（空格或逗号分隔）：ydr,yft,ydd,ytd,ybn')
    ap.add_argument('--packs', nargs='+', default=None, help='默认扫游戏目录下全部顶层 .rpf')
    ap.add_argument('--depth', type=int, default=8)
    a = ap.parse_args()
    exts = ';'.join(t for x in a.exts for t in x.replace(';', ',').split(',') if t)
    os.makedirs(OUTDIR, exist_ok=True)

    packs = a.packs or list_packs()
    inv = {}
    t0 = time.time()
    for pk in packs:
        arc = os.path.join(GAME, pk + '.rpf')
        if not os.path.exists(arc):
            print('[inv] 跳过（不存在）%s' % pk)
            continue
        tsv = os.path.join(OUTDIR, '%s.tsv' % pk)
        r = subprocess.run(['dotnet', DLL, 'hashindex', arc, tsv, exts, str(a.depth)],
                           capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if r.returncode != 0:
            print('[inv] %-14s 失败 rc=%d %s' % (pk, r.returncode, (r.stderr or '').strip()[-160:]))
            continue
        per = defaultdict(lambda: [0, 0])
        n = 0
        if os.path.exists(tsv):
            with open(tsv, encoding='utf-8', errors='replace') as f:
                f.readline()
                for line in f:
                    c = line.rstrip('\n').split('\t')
                    if len(c) < 4:
                        continue
                    ext = c[3].strip().lower()
                    try:
                        sz = int(c[2])
                    except ValueError:
                        sz = 0
                    per[ext][0] += 1
                    per[ext][1] += sz
                    n += 1
        inv[pk] = {k: {'n': v[0], 'mb': round(v[1] / 2**20, 1)} for k, v in per.items()}
        print('[inv] %-14s 条目 %6d  %s（%.0fs）'
              % (pk, n, ', '.join('%s %d/%.0fMB' % (k, v[0], v[1] / 2**20) for k, v in per.items()),
                 time.time() - t0))

    tot = defaultdict(lambda: [0, 0])
    for pk, d in inv.items():
        for ext, v in d.items():
            tot[ext][0] += v['n']
            tot[ext][1] += v['mb']
    print('[inv] 合计: %s' % ', '.join('%s %d 个 / %.1f GB'
                                       % (k, v[0], v[1] / 1024) for k, v in tot.items()))
    json.dump(inv, open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('[inv] 报告 %s' % REPORT)


if __name__ == '__main__':
    main()
