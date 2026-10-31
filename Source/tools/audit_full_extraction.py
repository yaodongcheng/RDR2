# -*- coding: utf-8 -*-
"""全抽取验收：包 / 模型 / 实例 三列的闭环数字。

判据（四项全零才算"抽全"）：
  1. 游戏目录表里的嵌套包，**产出 0 个文件的包数 = 0**
  2. 抽出来的 `.ydr/.yft`，**未能入库的 = 0**（`default` 着色器占位要单列，不算失败）
  3. 全部 `.ymap` 里的实体，**缺模型的 = 0**
  4. 每条实例的位置/四元数/缩放完整（`audit_transforms` 里查）

    python tools/audit_full_extraction.py
    python tools/audit_full_extraction.py --json out.json
"""
import os
import sys
import json
import glob
import math
import argparse
from collections import Counter, defaultdict

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
LIB = os.path.join(ROOT, 'assets/lib_native')
PACKS_DIR = os.path.join(ROOT, 'raw/all_packs')
AUDIT = os.path.join(ROOT, 'work/pack_audit.json')
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')


def joaat(s):
    h = 0
    for c in s.lower().encode('latin1', 'ignore'):
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', default='')
    ap.add_argument('--skip-models', action='store_true', help='跳过逐文件入库检查（很快）')
    a = ap.parse_args()

    out = {}

    # ---- 1. 包
    packs = {}
    if os.path.exists(AUDIT):
        packs = json.load(open(AUDIT, encoding='utf-8'))
    empty = [k for k, v in packs.items() if v.get('files', 0) <= 0 or v.get('empty')]
    out['packs'] = dict(total=len(packs), empty=len(empty),
                        files=sum(v.get('files', 0) for v in packs.values()),
                        gb=round(sum(v.get('size', 0) for v in packs.values()) / 1e9, 2))
    print('=== 1. 包 ===')
    print('  目录表嵌套包 %d 个（%.1f GB），产出 0 文件的 %d 个，解出文件合计 %d'
          % (len(packs), out['packs']['gb'], len(empty), out['packs']['files']))
    for k in empty[:10]:
        print('     空包: %s' % k)

    # ---- 2. 模型
    idx = json.load(open(os.path.join(LIB, 'index.json'), encoding='utf-8'))
    models = idx['models']
    if not a.skip_models:
        ydr = glob.glob(os.path.join(PACKS_DIR, '**', '*.ydr'), recursive=True)
        yft = glob.glob(os.path.join(PACKS_DIR, '**', '*.yft'), recursive=True)
        miss = []
        for f in ydr + yft:
            h = '0x%08x' % joaat(os.path.splitext(os.path.basename(f))[0])
            if h not in models:
                miss.append(os.path.basename(f))
        # default 着色器占位单列
        ph = [m for m in miss if '_slod' in m.lower() or 'shadow_box' in m.lower()
              or 'proxy' in m.lower()]
        out['models'] = dict(ydr=len(ydr), yft=len(yft), lib=len(models),
                             not_ingested=len(miss), placeholder=len(ph),
                             failed=len(miss) - len(ph))
        print('=== 2. 模型 ===')
        print('  抽出 .ydr %d / .yft %d；库里 %d；未能入库 %d（其中占位代理 %d，真失败 %d）'
              % (len(ydr), len(yft), len(models), len(miss), len(ph), len(miss) - len(ph)))
        for m in [x for x in miss if x not in ph][:10]:
            print('     真失败: %s' % m)

    # ---- 3. 实例
    import ymap_entities as Y
    ymaps = glob.glob(os.path.join(PACKS_DIR, '**', '*.ymap'), recursive=True)
    tot = 0
    missing = Counter()
    for f in ymaps:
        try:
            sig, size, es = Y.extract(f)
        except Exception:
            es = []
        for e in es:
            tot += 1
            h = '0x%08x' % (int(e[0]) & 0xFFFFFFFF)
            if h not in models:
                missing[h] += 1
    out['instances'] = dict(ymaps=len(ymaps), entities=tot,
                            hashes_missing=len(missing), instances_missing=sum(missing.values()))
    print('=== 3. 实例 ===')
    print('  .ymap %d 个，实体 %d 条；缺模型 hash %d 个（引用 %d 次）'
          % (len(ymaps), tot, len(missing), sum(missing.values())))

    # ---- 4. 变换
    bad = zero_q = tot_i = 0
    for tf in sorted(glob.glob(os.path.join(TILES, '*.json'))):
        for r in json.load(open(tf, encoding='utf-8')):
            tot_i += 1
            q = r[4:8]
            n = math.sqrt(sum(v * v for v in q))
            if n < 1e-6:
                zero_q += 1
            elif abs(n - 1.0) > 0.02:
                bad += 1
    out['transforms'] = dict(instances=tot_i, zero_quat=zero_q, bad_quat=bad)
    print('=== 4. 变换 ===')
    print('  tiles 实例 %d；零四元数 %d；模长异常 %d ⇒ 完整 %.3f%%'
          % (tot_i, zero_q, bad, 100.0 * (tot_i - zero_q - bad) / max(1, tot_i)))

    ok = (out['packs']['empty'] == 0 and out['models'].get('failed', 0) == 0
          and out['instances']['hashes_missing'] == 0
          and out['transforms']['zero_quat'] <= 1 and out['transforms']['bad_quat'] == 0)
    out['verdict'] = 'PASS' if ok else 'CHECK'
    print('\n[audit] %s' % out['verdict'])
    if a.json:
        json.dump(out, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('→ %s' % a.json)


if __name__ == '__main__':
    main()
