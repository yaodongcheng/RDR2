# -*- coding: utf-8 -*-
"""把清单里 `0x...` 的模型名修成真名（ledger / 大地图碎片里查），并同步重命名 TRF。

背景（2026-11-08）：`build_asset_inventory.py` 旧逻辑只从场景 `name_samples` 取名；
**bigmap-only 模型**没有场景名 ⇒ 落到 `0x...`。真名其实在：
  · `model_ledger.csv`（大多数）
  · `lod_fragments.csv`（瓜玛/大地图碎片）

本脚本：
  1. 两表建 hash→name；
  2. 修 `asset_import_models.csv` / `asset_inventory_models.csv` 的 name 列；
  3. 把 `deliverable/models/<0x...>.trf` 重命名成 `<真名>.trf`，同步 `models_export.csv`；
  4. 写 `manifests/model_name_fix.csv` 报告。

用法：
    python tools/fix_model_names.py --apply
    python tools/fix_model_names.py            # 只打印，不改
"""
import argparse
import csv
import io
import os
import re

RDR2 = r'D:/BrainMaker/大镖客2解包分析'
HANDOFF = os.path.join(RDR2, 'deliverable/manifests')
MODELS = os.path.join(RDR2, 'deliverable/models')
HASH_RE = re.compile(r'^0x[0-9a-fA-F]+$')


def load_names():
    m = {}
    p = os.path.join(HANDOFF, 'model_ledger.csv')
    for r in csv.DictReader(io.open(p, encoding='utf-8-sig')):
        try:
            m[int(r['hash'], 16)] = (r.get('name') or '').strip()
        except Exception:
            pass
    p = os.path.join(HANDOFF, 'lod_fragments.csv')
    for r in csv.DictReader(io.open(p, encoding='utf-8-sig')):
        k = r.get('model_hash') or r.get('hash') or ''
        try:
            m.setdefault(int(k, 16), (r.get('name') or '').strip())
        except Exception:
            pass
    return m


def rewrite_csv(path, names, col='name', apply=False):
    rows = list(csv.DictReader(io.open(path, encoding='utf-8-sig')))
    if not rows:
        return 0, []
    fields = list(rows[0].keys())
    changed = []
    for r in rows:
        n = (r.get(col) or '').strip()
        if HASH_RE.match(n):
            try:
                real = names.get(int(r.get('model_hash') or r.get('hash') or n, 16), '')
            except Exception:
                real = ''
            if real:
                changed.append((n, real))
                r[col] = real
    if apply:
        with io.open(path, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    return len(rows), changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    names = load_names()
    print('名字表 %d 条' % len(names))

    report = []
    for fn in ('asset_import_models.csv', 'asset_inventory_models.csv'):
        p = os.path.join(HANDOFF, fn)
        _, ch = rewrite_csv(p, names, apply=a.apply)
        print('%s: 改名 %d' % (fn, len(ch)))
        for old, new in ch:
            report.append([fn, '0x' + old[2:].lower(), old, new, ''])

    # 同步 models_export.csv + 重命名 TRF
    p = os.path.join(HANDOFF, 'models_export.csv')
    if os.path.exists(p):
        rows = list(csv.DictReader(io.open(p, encoding='utf-8-sig')))
        fields = list(rows[0].keys())
        for r in rows:
            n = (r.get('name') or '').strip()
            if not HASH_RE.match(n):
                continue
            try:
                real = names.get(int(r.get('model_hash') or n, 16), '')
            except Exception:
                real = ''
            if not real:
                continue
            old_trf = os.path.join(MODELS, n + '.trf')
            new_trf = os.path.join(MODELS, real + '.trf')
            renamed = False
            if os.path.exists(old_trf) and not os.path.exists(new_trf):
                if a.apply:
                    os.rename(old_trf, new_trf)
                renamed = True
            r['name'] = real
            r['trf'] = real + '.trf'
            report.append(['models_export.csv', r.get('model_hash', ''), n, real,
                           'renamed' if renamed else 'name only'])
        if a.apply:
            with io.open(p, 'w', encoding='utf-8-sig', newline='') as f:
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                w.writerows(rows)

    rp = os.path.join(HANDOFF, 'model_name_fix.csv')
    with io.open(rp, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['file', 'hash', 'old', 'new', 'trf'])
        w.writerows(report)
    print('报告 %d 行 -> %s' % (len(report), rp))
    if not a.apply:
        print('（dry run；加 --apply 才写入/改名）')


if __name__ == '__main__':
    main()
