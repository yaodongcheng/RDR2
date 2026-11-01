# -*- coding: utf-8 -*-
"""资产覆盖对账：**游戏包里有几个 vs 磁盘上有几个**。

判据（唯一标准）：
    五类 `.ydr/.ydd/.yft/.ytd/.ybn` 的唯一名覆盖率都 ≥ 99.9% → PASS

数据来源：
    游戏侧 `work/rpf_inv/<顶层包>.tsv`（由 `tools/rpf_inventory.py` 产出，只读 TOC 不解包）
    磁盘侧 扫 `raw/ deliverable/ export/ assets/ archive/`

匹配口径：
    按**文件名**（含扩展名）大小写不敏感匹配，取 basename —— TOC 里的名字可能带目录前缀
    （例：`levels/rdr3/minimap/val_saloon_int_main.ydd`），磁盘上却是平铺的。
    "有" 只代表磁盘上存在这个文件，**不代表已经被解析**。

用法：
    python tools/census_coverage.py
    python tools/census_coverage.py --json out.json --top 8
    python tools/census_coverage.py --exts ydr ytd

    # 全流程（先盘点再对账）
    python tools/rpf_inventory.py --exts ydr,yft,ydd,ytd,ybn,ymap,ytyp
    python tools/census_coverage.py
"""
import os
import sys
import json
import glob
import argparse
from collections import Counter, defaultdict

ROOT = r'D:/BrainMaker/大镖客2解包分析'
INV_DIR = os.path.join(ROOT, 'work/rpf_inv')
DISK_ROOTS = ['raw', 'deliverable', 'export', 'assets', 'archive']
DEFAULT_EXTS = ['.ydr', '.ydd', '.yft', '.ytd', '.ybn']
PASS_RATE = 99.9


def scan_disk(exts):
    have = {e: set() for e in exts}
    sizes = {e: set() for e in exts}
    for top in DISK_ROOTS:
        base = os.path.join(ROOT, top)
        if not os.path.isdir(base):
            continue
        for dp, _, fs in os.walk(base):
            for f in fs:
                lf = f.lower()
                for e in exts:
                    if lf.endswith(e):
                        have[e].add(lf)
                        try:
                            sizes[e].add(os.path.getsize(os.path.join(dp, f)))
                        except OSError:
                            pass
    return have, sizes


def read_inventory(exts, inv_dir):
    game = {e: set() for e in exts}
    sizes = {e: {} for e in exts}
    bypack = {e: Counter() for e in exts}
    files = sorted(glob.glob(os.path.join(inv_dir, '*.tsv')))
    if not files:
        print('[census] 缺盘点文件：先跑 python tools/rpf_inventory.py --exts ydr,yft,ydd,ytd,ybn')
        return None, None, None
    for path in files:
        pk = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding='utf-8', errors='replace') as fh:
            fh.readline()
            for ln in fh:
                c = ln.rstrip('\n').split('\t')
                if len(c) < 5:
                    continue
                ext = c[3].strip().lower()
                if ext not in game:
                    continue
                nm = os.path.basename(c[4].strip().lower())
                if not nm:
                    continue
                game[ext].add(nm)
                sizes[ext].setdefault(nm, int(c[2]) if c[2].strip().isdigit() else 0)
                bypack[ext][pk] += 1
    return game, sizes, bypack


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exts', nargs='+', default=DEFAULT_EXTS)
    ap.add_argument('--inv', default=INV_DIR)
    ap.add_argument('--json', default='')
    ap.add_argument('--top', type=int, default=6)
    a = ap.parse_args()

    exts = [e if e.startswith('.') else '.' + e for e in a.exts]
    game, gsize, bypack = read_inventory(exts, a.inv)
    if game is None:
        return 2
    disk, dsize = scan_disk(exts)

    print('%-6s %10s %10s %8s %9s' % ('ext', '游戏唯一', '磁盘覆盖', '缺', '覆盖率'))
    out = {}
    ok = True
    for e in exts:
        g, d = game[e], disk[e]
        miss = g - d
        rate = 100.0 * len(g & d) / len(g) if g else 100.0
        # 名字对不上、但磁盘上有同字节数的文件 → 疑似"同一张图换了名字"（哈希名池）
        renamed = sum(1 for n in miss if gsize[e].get(n) in dsize[e])
        out[e] = dict(game=len(g), covered=len(g & d), missing=len(miss),
                      renamed_like=renamed, rate=round(rate, 3), extra_on_disk=len(d - g))
        print('%-6s %10d %10d %8d %8.2f%%' % (e, len(g), len(g & d), len(miss), rate))
        if rate < PASS_RATE:
            ok = False

    # 缺失最多的来源包
    for e in exts:
        miss = game[e] - disk[e]
        if not miss:
            continue
        c = Counter()
        for path in sorted(glob.glob(os.path.join(a.inv, '*.tsv'))):
            pk = os.path.splitext(os.path.basename(path))[0]
            with open(path, encoding='utf-8', errors='replace') as fh:
                fh.readline()
                for ln in fh:
                    col = ln.rstrip('\n').split('\t')
                    if len(col) < 5 or col[3].strip().lower() != e:
                        continue
                    if os.path.basename(col[4].strip().lower()) in miss:
                        c[pk] += 1
        note = ''
        if out[e]['renamed_like']:
            note = '（其中 %d 个磁盘上有同字节数文件 = 疑似改名副本）' % out[e]['renamed_like']
        print('  %-5s 缺件来源：%s%s' % (e, ' · '.join('%s %d' % kv for kv in c.most_common(a.top)), note))

    print()
    print('RESULT: %s（判据：五类覆盖率均 ≥ %.1f%%）' % ('PASS' if ok else 'FAIL', PASS_RATE))
    if a.json:
        json.dump(out, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('[census] 写入 %s' % a.json)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
