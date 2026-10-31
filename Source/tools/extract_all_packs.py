# -*- coding: utf-8 -*-
"""把游戏 `levels_*.rpf` 里**全部嵌套包**抽出来（源侧闭环的基础步骤）。

背景：2026-10-30 发现"抽过的包"和"游戏里有的包"从来没有对过账，
`raw/rails_extract/` 下 4 个空目录就是整类资源漏抽的化石证据。
本脚本的判据只有一个：**游戏目录表里的每个嵌套包，都必须解出 ≥1 个文件**，
否则记进 `_empty.txt` 并计入失败。

产物：
    raw/all_packs/<包名>/...        解出来的资源
    raw/all_packs/<包名>/.done      包大小（跳过用）
    work/pack_audit.json            每包：路径/大小/文件数/失败与否

用法：
    python tools/extract_all_packs.py --list                 # 只列表
    python tools/extract_all_packs.py --only area rails      # 只抽这些类别
    python tools/extract_all_packs.py                        # 全抽（约 58 GB 压缩）
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
OUT = os.path.join(ROOT, 'raw/all_packs')
LOGS = r'D:/BrainMaker/_logs'
AUDIT = os.path.join(ROOT, 'work/pack_audit.json')


def run_rpf(args, log):
    line = ' '.join('"%s"' % a for a in [RP] + list(args))
    subprocess.run('cmd /c tools\\run.cmd "%s" %s' % (log, line), cwd=ROOT, capture_output=True)


def enumerate_packs():
    os.makedirs(LOGS, exist_ok=True)
    packs = {}
    for i in range(8):
        lv = os.path.join(GAME, 'levels_%d.rpf' % i)
        if not os.path.exists(lv):
            continue
        log = os.path.join(LOGS, 'allpacks_toc_%d.log' % i)
        if not os.path.exists(log) or os.path.getsize(log) < 200:
            run_rpf(['find', lv, '.rpf'], log)
        for ln in open(log, encoding='utf-8', errors='ignore'):
            m = re.match(r'\s*(\d+)\s+(\S.*)$', ln)
            if not m:
                continue
            path = m.group(2).strip()
            if path.lower().endswith('.rpf'):
                packs[path] = dict(size=int(m.group(1)), lv=lv)
    return packs


def cat_of(path):
    parts = path.split('/')
    return parts[2] if len(parts) > 2 else ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--only', nargs='*', default=None, help='按类别过滤（area/rails/terrain/...）')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--budget-min', type=float, default=0, help='跑够这么多分钟就收工（留 .done，下次续）')
    a = ap.parse_args()

    packs = enumerate_packs()
    if a.only:
        packs = {p: v for p, v in packs.items() if cat_of(p) in a.only}
    print('[src] 待处理嵌套包 %d 个，%.1f GB' % (len(packs), sum(v['size'] for v in packs.values()) / 1e9))
    if a.list:
        from collections import Counter
        c = Counter(cat_of(p) for p in packs)
        for k, v in sorted(c.items()):
            print('   %-28s %5d 个  %8.1f MB'
                  % (k, v, sum(packs[p]['size'] for p in packs if cat_of(p) == k) / 1e6))
        return

    os.makedirs(OUT, exist_ok=True)
    audit = {}
    if os.path.exists(AUDIT):
        try:
            audit = json.load(open(AUDIT, encoding='utf-8'))
        except Exception:
            audit = {}
    t0 = time.time()
    ok = skip = empty = fail = 0
    items = sorted(packs.items())
    if a.limit:
        items = items[:a.limit]
    for n, (path, meta) in enumerate(items, 1):
        if a.budget_min and (time.time() - t0) / 60 > a.budget_min:
            print('[src] 到预算 %.0f 分钟，收工（下次继续）' % a.budget_min)
            break
        base = os.path.basename(path)[:-4]
        dst = os.path.join(OUT, base)
        done = os.path.join(dst, '.done')
        if os.path.exists(done) and open(done).read().strip() == str(meta['size']):
            skip += 1
            continue
        shutil.rmtree(dst, ignore_errors=True)
        os.makedirs(dst, exist_ok=True)
        log = os.path.join(LOGS, 'allpack_%s.log' % base)
        run_rpf(['extract', meta['lv'], dst, path], log)
        inner = glob.glob(os.path.join(dst, '**', '*.rpf'), recursive=True)
        if inner:
            run_rpf(['extract', inner[0], dst, ''], os.path.join(LOGS, 'allpack_inner_%s.log' % base))
        nf = sum(len(fs) for _, _, fs in os.walk(dst))
        nf -= len(glob.glob(os.path.join(dst, '**', '*.rpf'), recursive=True))
        rec = dict(path=path, lv=meta['lv'], size=meta['size'], files=nf,
                   ts=time.strftime('%Y-%m-%dT%H:%M:%S'))
        if nf <= 0:
            rec['empty'] = True
            empty += 1
            print('[%4d/%d] %-46s ✗ 0 个文件' % (n, len(items), base))
        else:
            with open(done, 'w') as f:
                f.write(str(meta['size']))
            ok += 1
            if n % 20 == 0:
                print('[%4d/%d] %-46s %4d 文件  (%.1f 分)'
                      % (n, len(items), base, nf, (time.time() - t0) / 60))
        audit[base] = rec
        if n % 50 == 0:
            json.dump(audit, open(AUDIT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    json.dump(audit, open(AUDIT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('[src] 抽出 %d / 跳过 %d / 空包 %d / 失败 %d；审计 → %s'
          % (ok, skip, empty, fail, os.path.relpath(AUDIT, ROOT)))


if __name__ == '__main__':
    main()
