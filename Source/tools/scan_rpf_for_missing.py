# -*- coding: utf-8 -*-
"""递归扫描游戏 RPF，把「场景里缺模型的实体 hash」在游戏包里找出来。

思路：RPF 的 `list` 会打印每个条目的路径（有名）或 `0xHASH`（无名）。
本工具：
  1) 算出「实体有、库没有」的 hash 集合；
  2) 从顶层 rpf 开始，解析 TOC：
     · 遇到 .ydr/.yft → 用文件名算 joaat 或直接读 `0xHASH`，命中集合就记下来
     · 遇到 .rpf → 解到临时目录，继续递归（限制深度/数量）
  3) 输出清单 `export/world/rpf_found_missing.tsv`

用法：
    uv run python tools/scan_rpf_for_missing.py --rpf levels_2 --max-nested 400
    uv run python tools/scan_rpf_for_missing.py --extract      # 把命中的抽到 raw_missing/
"""
import os
import re
import sys
import json
import glob
import time
import shutil
import argparse
import subprocess

ROOT = r'D:/BrainMaker/大镖客2解包分析'
GAME = r'H:/EPICGAMES/RedDeadRedemption2'
DOTNET = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.dll')
TMP = os.path.join(os.environ.get('TEMP', ROOT), 'rdr2_scan')
OUT_TSV = os.path.join(ROOT, 'export/world/rpf_found_missing.tsv')
RAW_MISSING = os.path.join(ROOT, 'raw/_missing')


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF


LINE = re.compile(r'^\s*(\d+)\s+res=\d+\s+comp=\S+\s+(.+?)\s*$')


def listing(archive):
    r = subprocess.run(['dotnet', DOTNET, 'list', archive], capture_output=True, text=True,
                       encoding='utf-8', errors='ignore')
    out = []
    for ln in r.stdout.splitlines():
        m = LINE.match(ln)
        if not m:
            continue
        size, path = int(m.group(1)), m.group(2)
        name = os.path.basename(path)
        if name.lower().startswith('0x'):
            try:
                h = int(name[2:].split('.')[0], 16)
            except Exception:
                continue
        else:
            h = joaat(os.path.splitext(name)[0])
        out.append((h, name, path, size))
    return out


def extract_entry(archive, pattern, outdir):
    subprocess.run(['dotnet', DOTNET, 'extract', archive, outdir, pattern],
                   capture_output=True, text=True, encoding='utf-8', errors='ignore')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rpf', default='levels_2')
    ap.add_argument('--max-nested', type=int, default=400)
    ap.add_argument('--depth', type=int, default=3)
    ap.add_argument('--extract', action='store_true')
    a = ap.parse_args()

    lib = {int(k, 16) for k in json.load(open(os.path.join(ROOT, 'assets/lib_native/index.json'),
                                             encoding='utf-8'))['models']}
    ent = set()
    for p in glob.glob(os.path.join(ROOT, 'export/world/continent/tiles/*.json')):
        if p.endswith('.bak'):
            continue
        for e in json.load(open(p, encoding='utf-8')):
            ent.add(e[0])
    missing = ent - lib
    print('[scan] 实体缺模型 %d' % len(missing))

    top = os.path.join(GAME, a.rpf + '.rpf')
    if not os.path.exists(top):
        raise SystemExit('找不到 ' + top)

    os.makedirs(TMP, exist_ok=True)
    found = {}          # hash -> (archive, path, size)
    queue = [(top, 0)]
    seen_arch = set()
    nested_done = 0
    t0 = time.time()

    while queue:
        arc, depth = queue.pop(0)
        if arc in seen_arch:
            continue
        seen_arch.add(arc)
        try:
            ents = listing(arc)
        except Exception as e:
            print('[scan] 读取失败 %s (%s)' % (os.path.basename(arc), e))
            continue
        for h, name, path, size in ents:
            lo = name.lower()
            if lo.endswith(('.ydr', '.yft')) and h in missing and h not in found:
                found[h] = (arc, path, size)
                if a.extract:
                    os.makedirs(RAW_MISSING, exist_ok=True)
                    extract_entry(arc, name, RAW_MISSING)
            elif lo.endswith('.rpf') and depth < a.depth and nested_done < a.max_nested:
                outdir = os.path.join(TMP, 'n%d' % nested_done)
                os.makedirs(outdir, exist_ok=True)
                extract_entry(arc, name, outdir)
                for dp, _, fs in os.walk(outdir):
                    for f in fs:
                        if f.lower().endswith('.rpf'):
                            queue.append((os.path.join(dp, f), depth + 1))
                nested_done += 1
                if nested_done % 20 == 0:
                    print('[scan] 已展开 %d 个嵌套 rpf，命中 %d，用时 %.0fs' % (
                        nested_done, len(found), time.time() - t0))
        shutil.rmtree(os.path.join(TMP, 'n%d' % (nested_done - 1)), ignore_errors=True)

    rows = sorted(((hex(h), p, s) for h, (arc, p, s) in found.items()))
    with open(OUT_TSV, 'w', encoding='utf-8') as f:
        f.write('hash\tentry\tsize\n')
        for h, p, s in rows:
            f.write('%s\t%s\t%d\n' % (h, p, s))
    print('[scan] 命中 %d 个缺失模型，清单 %s，用时 %.0fs' % (len(rows), OUT_TSV, time.time() - t0))
    if a.extract:
        n = len(glob.glob(os.path.join(RAW_MISSING, '**', '*.y*'), recursive=True))
        print('[scan] 已抽取到 raw/_missing: %d 个文件' % n)
    for h, p, s in rows[:10]:
        print('[scan]   %s %s' % (h, p))


if __name__ == '__main__':
    main()
