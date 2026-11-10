# -*- coding: utf-8 -*-
"""把清单里的哈希名（`0x...` / `e_<hash>`）修成真名，并同步重命名 TRF / FBX。

背景（2026-11-08 → 2026-11-09）：
  - `0x...`：bigmap-only 模型没场景名，真名在 `model_ledger.csv` / `lod_fragments.csv`；
  - `e_<hash>`：RDR2 的 names.txt 缺父名（只有 `X_children`），真名要用
    `name_source.load_names()` 从 `*_children` 反推（2026-11-05 加的，之前没回灌到模型表）。
    本轮实测：`models_export.csv` 630 个 `e_` 名，其中 **157 个能恢复真名**（如
    `e_042e1353` → `bla_blk01_slod`），其余 473 个名字源里也没有。

处理的表：
  - `models_export.csv`         : name / trf / fbx
  - `asset_import_models.csv`   : name
  - `asset_inventory_models.csv`: name
  - `mesh_usage.csv`            : name_samples（`|` 或 `;` 分隔的 token）
  - `model_materials.csv`       : model / trf / trf_mesh

文件：
  - `deliverable/models/<旧名>.trf` → `<真名>.trf`，并改写 TRF 内部 part 名
    （`<名>.<子网格序>` / `<名>.lod<N>.<子网格序>`）—— 只改文件名不改 part 名，
    导入出来的 MetaMesh 还是旧名，必须一起改（旧工具漏了这一步）。
  - `deliverable/models/<旧名>.fbx` → `<真名>.fbx`（存在才改）
  - 报告写 `manifests/model_name_fix.csv`（按 file+old 去重，保留历史行）

用法：
    python tools/fix_model_names.py            # dry-run（只打印）
    python tools/fix_model_names.py --apply    # 真正改名/写表
"""
import argparse
import csv
import io
import os
import re
import sys

RDR2 = r'D:/BrainMaker/大镖客2解包分析'
HANDOFF = os.path.join(RDR2, 'deliverable/manifests')
MODELS = os.path.join(RDR2, 'deliverable/models')

HASH_RE = re.compile(r'^0x[0-9a-fA-F]+$')
E_RE = re.compile(r'^e_([0-9a-f]{8})$', re.I)
EXTS = ('.trf', '.fbx')


def load_names():
    """hash(int) → 真名。三层来源合并（先到先得）。"""
    m = {}

    def add(h, n):
        if not n:
            return
        h = (h or '').strip()
        if not h:
            return
        try:
            m.setdefault(int(h, 16), n.strip())
        except Exception:
            pass

    p = os.path.join(HANDOFF, 'model_ledger.csv')
    if os.path.isfile(p):
        for r in csv.DictReader(io.open(p, encoding='utf-8-sig')):
            add(r.get('hash', ''), r.get('name', ''))
    p = os.path.join(HANDOFF, 'lod_fragments.csv')
    if os.path.isfile(p):
        for r in csv.DictReader(io.open(p, encoding='utf-8-sig')):
            add(r.get('model_hash') or r.get('hash') or '', r.get('name', ''))
    try:
        sys.path.insert(0, os.path.join(RDR2, 'tools'))
        from name_source import load_names as _parent_names
        for h, n in _parent_names().items():
            m.setdefault(int(h), (n or '').strip())
    except Exception as e:
        print('WARN: name_source 不可用（%r）' % e)
    return m


def real_of(cell, row, names):
    """单元格 → 真名（带原扩展名）。不是哈希名或查不到则 None。"""
    n = (cell or '').strip()
    ext = ''
    for e in EXTS:
        if n.lower().endswith(e):
            ext = n[-len(e):]
            n = n[:-len(e)]
            break
    h = None
    if HASH_RE.match(n):
        try:
            h = int(n, 16)
        except Exception:
            return None
    else:
        m = E_RE.match(n)
        if not m:
            return None
        h = int(m.group(1), 16)
    if h is None:
        return None
    real = names.get(h)
    return (real + ext) if real else None


def rewrite_simple(path, names, cols, apply):
    if not os.path.isfile(path):
        return 0, []
    rows = list(csv.DictReader(io.open(path, encoding='utf-8-sig')))
    if not rows:
        return 0, []
    fields = list(rows[0].keys())
    changed = []
    for r in rows:
        for col in cols:
            if col not in r:
                continue
            real = real_of(r.get(col), r, names)
            if real:
                changed.append((col, r.get(col), real))
                r[col] = real
    if apply:
        with io.open(path, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    return len(changed), changed


def rewrite_name_samples(path, names, apply):
    """mesh_usage.csv 的 name_samples（`|`/`;` 分隔 token）。"""
    if not os.path.isfile(path):
        return 0
    rows = list(csv.DictReader(io.open(path, encoding='utf-8-sig')))
    if not rows:
        return 0
    fields = list(rows[0].keys())
    n = 0
    for r in rows:
        s = r.get('name_samples') or ''
        if not s:
            continue
        out = []
        changed = False
        for tok in re.split(r'([|;])', s):
            real = real_of(tok, r, names) if tok.strip() else None
            if real:
                out.append(real)
                changed = True
                n += 1
            else:
                out.append(tok)
        if changed:
            r['name_samples'] = ''.join(out)
    if apply:
        with io.open(path, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    return n


def rename_assets(names, apply):
    """重命名 TRF/FBX + 改写 TRF 内部 part 名。"""
    out = []
    for fn in sorted(os.listdir(MODELS)):
        if not fn.lower().endswith('.trf'):
            continue
        old = fn[:-4]
        real = real_of(old, {'model_hash': ''}, names)
        if not real:
            continue
        old_trf = os.path.join(MODELS, fn)
        new_trf = os.path.join(MODELS, real + '.trf')
        if os.path.exists(new_trf) and os.path.abspath(new_trf) != os.path.abspath(old_trf):
            out.append((old, real, 'SKIP: target exists'))
            continue
        if apply:
            txt = io.open(old_trf, encoding='utf-8', errors='replace', newline='').read()
            txt2 = re.sub(r'(?m)^' + re.escape(old) + r'(\.\d+|\.lod\d+\.\d+) 0 ',
                          real + r'\1 0 ', txt)
            with io.open(old_trf, 'w', encoding='utf-8', newline='') as f:
                f.write(txt2)
            os.rename(old_trf, new_trf)
        out.append((old, real, 'renamed'))
        old_fbx = os.path.join(MODELS, old + '.fbx')
        new_fbx = os.path.join(MODELS, real + '.fbx')
        if os.path.isfile(old_fbx) and not os.path.exists(new_fbx):
            if apply:
                os.rename(old_fbx, new_fbx)
            out.append((old + '.fbx', real + '.fbx', 'renamed'))
    return out


def write_report(rows, apply):
    p = os.path.join(HANDOFF, 'model_name_fix.csv')
    old_rows = []
    if os.path.isfile(p):
        old_rows = list(csv.DictReader(io.open(p, encoding='utf-8-sig')))
    seen = {(r.get('file'), r.get('old')) for r in old_rows}
    for fn, h, old, new, st in rows:
        if (fn, old) not in seen:
            old_rows.append({'file': fn, 'hash': h, 'old': old, 'new': new, 'trf': st})
            seen.add((fn, old))
    if apply:
        with io.open(p, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['file', 'hash', 'old', 'new', 'trf'])
            w.writeheader()
            w.writerows(old_rows)
    return len(old_rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    names = load_names()
    print('名字表 %d 条（含 name_source 反推）' % len(names))

    specs = [
        ('models_export.csv', ['name', 'trf', 'fbx']),
        ('asset_import_models.csv', ['name']),
        ('asset_inventory_models.csv', ['name']),
        ('model_materials.csv', ['model', 'trf', 'trf_mesh']),
    ]
    report = []
    for fn, cols in specs:
        p = os.path.join(HANDOFF, fn)
        n, ch = rewrite_simple(p, names, cols, a.apply)
        print('%-30s 改名 %d 处' % (fn, n))
        for col, old, new in ch[:4]:
            print('    %s: %s -> %s' % (col, old, new))
        if len(ch) > 4:
            print('    ... 共 %d 处' % len(ch))
        if fn == 'models_export.csv':
            for col, old, new in ch:
                if col == 'name':
                    report.append([fn, '', old, new, ''])

    n = rewrite_name_samples(os.path.join(HANDOFF, 'mesh_usage.csv'), names, a.apply)
    print('%-30s 改名 %d 处' % ('mesh_usage.csv', n))

    ren = rename_assets(names, a.apply)
    print('资产重命名 %d 条（TRF/FBX）' % len(ren))
    for old, new, st in ren[:8]:
        print('    %s -> %s (%s)' % (old, new, st))
    if len(ren) > 8:
        print('    ... 共 %d 条' % len(ren))
    for old, new, st in ren:
        if st == 'renamed':
            report.append(['models_export.csv', '', old, new, 'renamed'])

    print('报告累计 %d 行' % write_report(report, a.apply))
    if not a.apply:
        print('（dry run；加 --apply 才写入/改名）')


if __name__ == '__main__':
    main()
