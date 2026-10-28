# -*- coding: utf-8 -*-
"""按 **RPF 条目 hash** 从游戏包里抽 drawable（TODO §0.5 第 2 步的落地工具）。

## 为什么不是"按名字找"

`tiles/*.json` 存 archetype hash；`assets/lib_native` 存 model hash（= joaat(.ydr 名)）。
对 4.9 万个"名字查不到"的 archetype，没有名字可查 —— 但 **RPF 条目自己带 hash**，
所以只要索引里有这个 hash，就能定位到"哪个包、哪个条目"，不依赖名字。

索引由 `tools/rpf_index.py` 生成（`rdr2rpf hashindex`，原地读嵌套 TOC，不解整包）。

## 用法

    uv run python tools/rpf_index.py                       # 先建索引（几分钟）
    python tools/extract_by_hash.py --dry                  # 看还能抽多少
    python tools/extract_by_hash.py                        # 抽到 raw/_missing
    python tools/extract_by_hash.py --what-if-file x.txt   # 指定 hash 清单（每行一个 hex）

产物：`raw/_missing/<文件名或 0xhash>.ydr`，清单 `work/extract_by_hash_report.json`。
"""
import os
import sys
import json
import glob
import time
import argparse
import subprocess
from collections import Counter, defaultdict

ROOT = r'D:/BrainMaker/大镖客2解包分析'
GAME = r'H:/EPICGAMES/RedDeadRedemption2'
DLL = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.dll')
IDX = os.path.join(ROOT, 'work/rpf_index/all.tsv')
LIB = os.path.join(ROOT, 'assets/lib_native/index.json')
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
OUT = os.path.join(ROOT, 'raw/_missing')
LISTDIR = os.path.join(ROOT, 'work/rpf_hashlists')
REPORT = os.path.join(ROOT, 'work/extract_by_hash_report.json')


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF


def name_hash(path):
    base = os.path.splitext(os.path.basename(path))[0]
    if base.lower().startswith('0x'):
        try:
            return int(base[2:], 16)
        except ValueError:
            return None
    return joaat(base)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--what-if-file', default='')
    ap.add_argument('--limit-per-pack', type=int, default=0)
    a = ap.parse_args()

    lib = {int(k, 16) for k in json.load(open(LIB, encoding='utf-8'))['models']}
    ent = Counter()
    for p in glob.glob(os.path.join(TILES, '*.json')):
        for e in json.load(open(p, encoding='utf-8')):
            ent[e[0]] += 1
    missing = {h for h in ent if h not in lib}

    idx = {}
    with open(IDX, encoding='utf-8') as f:
        for line in f:
            arc, hs, size, ext, nm = line.rstrip('\n').split('\t')
            idx.setdefault(int(hs, 16), (arc, nm, int(size), ext))

    have = set()
    for p in glob.glob(os.path.join(a.out, '**', '*'), recursive=True):
        if os.path.isfile(p) and p.lower().endswith(('.ydr', '.yft')):
            h = name_hash(p)
            if h is not None:
                have.add(h)

    if a.what_if_file:
        want = set()
        for ln in open(a.what_if_file, encoding='utf-8'):
            t = ln.strip()
            if t:
                want.add(int(t, 16))
        todo = {h for h in want if h in idx and h not in have}
    else:
        todo = {h for h in missing if h in idx and h not in have}

    print('[x] 缺模型 %d（实例 %d）；索引可命中 %d；已抽过 %d；**本次待抽 %d**（实例 %d）'
          % (len(missing), sum(ent[h] for h in missing),
             len([h for h in missing if h in idx]), len([h for h in missing if h in idx and h in have]),
             len(todo), sum(ent.get(h, 0) for h in todo)))
    if not todo:
        return

    per = defaultdict(list)
    for h in todo:
        per[idx[h][0].split('::')[0]].append(h)
    print('[x] 分布：%s' % ', '.join('%s:%d' % (k.replace('.rpf', ''), len(v))
                                     for k, v in sorted(per.items(), key=lambda kv: -len(kv[1]))))

    if a.dry:
        for h in sorted(todo)[:8]:
            print('   0x%08x  %-46s %8d B %s' % (h, idx[h][1], idx[h][2], idx[h][0]))
        print('[x] dry-run，未抽')
        return

    os.makedirs(a.out, exist_ok=True)
    os.makedirs(LISTDIR, exist_ok=True)
    t0 = time.time()
    got = Counter()
    for pack, hs in sorted(per.items()):
        arc = os.path.join(GAME, pack)
        if not os.path.exists(arc):
            print('[x] 缺少 %s' % arc)
            continue
        lp = os.path.join(LISTDIR, os.path.splitext(pack)[0] + '.txt')
        with open(lp, 'w', encoding='utf-8') as f:
            for h in sorted(hs):
                f.write('0x%08x\n' % h)
        r = subprocess.run(['dotnet', DLL, 'extracthash', arc, lp, a.out],
                           capture_output=True, text=True, encoding='utf-8', errors='ignore')
        tail = (r.stderr or '').strip().splitlines()
        print('[x] %-14s rc=%d %s（%.0fs）'
              % (pack, r.returncode, tail[-1] if tail else '', time.time() - t0))
        got[pack] = len(hs)

    n = 0
    for p in glob.glob(os.path.join(a.out, '**', '*'), recursive=True):
        if os.path.isfile(p) and p.lower().endswith(('.ydr', '.yft')):
            n += 1
    print('[x] 结束：请求 %d 个 hash，目录现有 %d 个模型文件，用时 %.1f 分'
          % (len(todo), n, (time.time() - t0) / 60))
    json.dump({'requested': len(todo), 'per_pack': dict(got),
               'files_total': n, 'minutes': round((time.time() - t0) / 60, 1)},
              open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
