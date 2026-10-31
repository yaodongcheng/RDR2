# -*- coding: utf-8 -*-
"""源侧覆盖率核查：**游戏目录表里有多少个包，我们抽了几个，哪些一个文件都没产出**。

## 为什么必须有这个脚本（2026-10-30 教训）

那一轮我们给出过"所有可见物品都抽全了"的结论，依据是**场景内部自洽**：
150,933 个实例每个都能在模型库里找到模型、剩下的 hash 归类为 LOD 合并块。
但漏掉的是**上游**：`levels_rdr3.rpf` 里 18 个铁路包只抽了 4 个，
剩下 14 个连实例都没进清单 —— 场景再自洽也发现不了"清单本身不全"。
安尼斯堡那条从南到北的铁路就这么没了，而空目录 `raw/rails_extract/jklm_15_18_rails_a_rpf/`
一直摆在那里，我把它当成"不需要的东西"跳过了。

⇒ 判断"抽全没有"只能问源：**目录表 → 逐个包 → 有没有产出**。
本脚本就是那张表，一条命令跑完，不需要人肉逐米检查。

## 用法

    python tools/audit_source_coverage.py                 # 只看 area/rails/terrain 三类（场景相关）
    python tools/audit_source_coverage.py --all           # 所有嵌套包都列
    python tools/audit_source_coverage.py --extract-missing   # 打印可执行的补抽命令

判据：某个包在 `raw/`、`work/`、`export/` 任一树下有同名目录且里面 ≥1 个文件，算"抽过"；
否则算"没抽"。`.done` 标记（`extract_all_rail_packs.py` 写的）优先采信。
"""
import os
import re
import sys
import glob
import json
import argparse
import subprocess
from collections import Counter, defaultdict

ROOT = r'D:/BrainMaker/大镖客2解包分析'
GAME = r'H:/EPICGAMES/RedDeadRedemption2'
RP = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe')
LOGS = r'D:/BrainMaker/_logs'
SCAN_ROOTS = ['raw', 'work', 'export', 'assets']

SCENE_CATS = ('area', 'rails', 'terrain')


def run_rpf(args, log):
    line = ' '.join(['"%s"' % a for a in [RP] + list(args)])
    subprocess.run('cmd /c tools\\run.cmd "%s" %s' % (log, line), cwd=ROOT, capture_output=True)


def enumerate_packs():
    """levels_*.rpf → 全部嵌套 .rpf 条目（路径 + 大小 + 所在包）。"""
    os.makedirs(LOGS, exist_ok=True)
    packs = {}
    for i in range(8):
        lv = os.path.join(GAME, 'levels_%d.rpf' % i)
        if not os.path.exists(lv):
            continue
        log = os.path.join(LOGS, 'audit_toc_%d.log' % i)
        if not os.path.exists(log) or os.path.getsize(log) < 200:
            run_rpf(['find', lv, '.rpf'], log)
        for ln in open(log, encoding='utf-8', errors='ignore'):
            m = re.match(r'\s*(\d+)\s+(\S.*)$', ln)
            if not m:
                continue
            path = m.group(2).strip()
            if path.lower().endswith('.rpf'):
                packs[path] = dict(size=int(m.group(1)), lv='levels_%d.rpf' % i)
    return packs


def index_extracted():
    """磁盘上所有"包名 → 文件数"。包名 = 目录名去掉 _rpf / _x 后缀。"""
    have = {}
    for root in SCAN_ROOTS:
        base = os.path.join(ROOT, root)
        if not os.path.isdir(base):
            continue
        for dp, dns, fns in os.walk(base):
            name = os.path.basename(dp)
            short = re.sub(r'(_rpf|_x|__rpf)$', '', name)
            if fns:
                have[short] = have.get(short, 0) + len(fns)
    return have


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--extract-missing', action='store_true')
    a = ap.parse_args()

    if not os.path.isdir(GAME):
        raise SystemExit('找不到游戏目录：%s' % GAME)
    packs = enumerate_packs()
    have = index_extracted()
    print('游戏 levels_*.rpf 里的嵌套包 **%d 个**（%.1f GB 压缩）'
          % (len(packs), sum(v['size'] for v in packs.values()) / 1e9))

    bycat = defaultdict(list)
    for p, m in packs.items():
        # levels/rdr3/area/rails/xxx.rpf → area/rails
        parts = p.split('/')
        cat = '/'.join(parts[2:4]) if len(parts) > 3 else '/'.join(parts[2:3])
        bycat[cat].append(p)

    cats = sorted(bycat) if a.all else [c for c in sorted(bycat)
                                        if any(c.startswith(x) for x in SCENE_CATS)]
    miss_total = []
    print('\n%-28s %5s %6s %6s %8s' % ('类别', '总数', '抽过', '没抽', '缺的 MB'))
    for c in cats:
        ps = bycat[c]
        miss = [p for p in ps if os.path.basename(p)[:-4] not in have]
        miss_total += miss
        print('%-28s %5d %6d %6d %8.1f'
              % (c, len(ps), len(ps) - len(miss), len(miss),
                 sum(packs[p]['size'] for p in miss) / 1e6))

    if miss_total:
        print('\n=== 没抽过的包（%d 个）===' % len(miss_total))
        for p in sorted(miss_total):
            print('   %-64s %7.1f MB' % (p, packs[p]['size'] / 1e6))
        if a.extract_missing:
            print('\n补抽命令（逐个执行，或写进脚本循环）：')
            for p in sorted(miss_total):
                lv = packs[p]['lv']
                print('  rdr2rpf.exe extract "%s\\%s" <输出目录> "%s"  然后解内层'
                      % (GAME, lv, p))
    else:
        print('\n✓ 场景相关的嵌套包全部有产出（不代表每个包内容都对，但不会有"整包没抽"）')


if __name__ == '__main__':
    main()
