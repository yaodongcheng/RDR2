# -*- coding: utf-8 -*-
"""按**当前**清单重建贴图交付索引，并补齐缺失贴图。

- import=1 → textures/（优先），否则 textures_extra/
- 非 import（场景用到）→ textures_extra/
- 已存在的文件不搬（blend 路径已指向原目录），索引里记实际 dest
- 缺失的从贴图池复制
- blend 路径兜底补入的（textures_export_fallback.csv）并入 extra 索引

产物：
  deliverable/textures/…
  deliverable/textures_extra/…
  deliverable/manifests/textures_export.csv
  deliverable/manifests/textures_export_extra.csv
"""
import csv
import io
import os
import shutil

RDR2 = r'D:/BrainMaker/大镖客2解包分析'
D = os.path.join(RDR2, 'deliverable')
M = os.path.join(D, 'manifests')
POOL = os.path.join(D, 'blender/continent/tex')
TEX = os.path.join(D, 'textures')
EXTRA = os.path.join(D, 'textures_extra')
INV = os.path.join(M, 'asset_inventory_textures.csv')
IMP = os.path.join(M, 'asset_import_textures.csv')
OUT_IMP = os.path.join(M, 'textures_export.csv')
OUT_EXT = os.path.join(M, 'textures_export_extra.csv')
FALLBACK = os.path.join(M, 'textures_export_fallback.csv')


def rows(p):
    return list(csv.DictReader(io.open(p, encoding='utf-8-sig'))) if os.path.exists(p) else []


def role_of(r):
    t = set((r.get('type') or '').split('|'))
    n = (r.get('name') or '').lower()
    if 'nm' in t or n.endswith('_nm'):
        return 'nm'
    if 'ma' in t or n.endswith(('_ma', '_mb')):
        return 'ma'
    return 'alb'


def find(name, role):
    for base in (TEX, EXTRA):
        p = os.path.join(base, role, name + '.png')
        if os.path.exists(p):
            return p
    return None


def main():
    inv = rows(INV)
    imp_ids = {r['tex_id'] for r in rows(IMP)}
    out_i, out_e = [], []
    copied = 0
    for r in inv:
        tid, name, role = r['tex_id'], r['name'], role_of(r)
        is_imp = tid in imp_ids
        p = find(name, role)
        if not p:
            base = TEX if is_imp else EXTRA
            p = os.path.join(base, role, name + '.png')
            os.makedirs(os.path.dirname(p), exist_ok=True)
            src = os.path.join(POOL, r['file'].split('/')[-1])
            if os.path.exists(src):
                shutil.copy2(src, p)
                copied += 1
            else:
                continue
        d = p.replace(os.sep, '/')
        row = [tid, name, role, ('blender/continent/' + r['file']).replace(os.sep, '/'),
               d, os.path.getsize(p)]
        (out_i if is_imp else out_e).append(row)

    # blend 兜底补入的、且不在 inventory 的贴图 → extra 索引
    inv_ids = {r['tex_id'] for r in inv}
    seen = set()
    for r in rows(FALLBACK):
        tid = r.get('tex_id')
        if not tid or tid in inv_ids or tid in seen:
            continue
        seen.add(tid)
        name = r.get('name') or ''
        role = r.get('role') or 'alb'
        p = find(name, role)
        if p:
            out_e.append([tid, name, role, '', p.replace(os.sep, '/'), os.path.getsize(p)])

    for path, data in ((OUT_IMP, out_i), (OUT_EXT, out_e)):
        with io.open(path, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(['tex_id', 'name', 'role', 'source', 'dest', 'bytes'])
            w.writerows(data)
    print('import textures %d / extra %d / copied %d' % (len(out_i), len(out_e), copied))


if __name__ == '__main__':
    main()
