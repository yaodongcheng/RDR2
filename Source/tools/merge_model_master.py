# -*- coding: utf-8 -*-
"""把「模型文件表」和「模型→材质汇总」合并成一张模型主表。

输入：
  deliverable/manifests/models_export.csv      name/hash/mdl/trf/faces/bytes
  deliverable/manifests/model_materials.csv    逐槽明细（model/trf_mesh/slot/material...）

输出（覆盖 models_export.csv）：
  name, model_hash, mdl, trf, faces, bytes,
  slots, material_count, materials, material_status, no_tex_slots

说明：
  · 这是**模型级主表**；逐槽的三件套仍在 `model_materials.csv`（不把文件信息重复 63k 行）。
  · `materials` 用 `|` 分隔；`material_status` 单材质时取该材质状态，多材质 = `multi`。
  · 幂等：可反复运行。

用法：
    python tools/merge_model_master.py
"""
import csv
import collections
import io
import os

RDR2 = r'D:/BrainMaker/大镖客2解包分析'
MANIFESTS = os.path.join(RDR2, 'deliverable/manifests')
EXPORT = os.path.join(MANIFESTS, 'models_export.csv')
DETAIL = os.path.join(MANIFESTS, 'model_materials.csv')

FIELDS = ['name', 'model_hash', 'mdl', 'trf', 'faces', 'bytes',
          'slots', 'material_count', 'materials', 'material_status', 'no_tex_slots']


def main():
    base = list(csv.DictReader(io.open(EXPORT, encoding='utf-8-sig')))
    # 🔴 2026-11-10：保留清单里已有的其它列（fbx / trf_faces / lod_levels …）。
    # 原来只写 FIELDS 11 列，重跑会把 LOD 与 FBX 列整片冲掉。
    fields = list(base[0].keys()) if base else list(FIELDS)
    for fld in FIELDS:
        if fld not in fields:
            fields.append(fld)
    by_hash = {}
    for r in base:
        by_hash[(r.get('model_hash') or '').lower()] = r

    agg = collections.defaultdict(lambda: {
        'materials': [], 'statuses': [], 'slots': 0, 'no_tex': 0})
    for r in csv.DictReader(io.open(DETAIL, encoding='utf-8-sig')):
        h = (r.get('model_hash') or '').lower()
        e = agg[h]
        e['slots'] += 1
        mat = (r.get('material') or 'no_tex').strip()
        if mat not in e['materials']:
            e['materials'].append(mat)
        e['statuses'].append((r.get('material_status') or '').strip())
        if mat == 'no_tex':
            e['no_tex'] += 1

    out = []
    for h, r in by_hash.items():
        e = agg.get(h)
        row = dict(r)
        if not e:
            row.update({'slots': 0, 'material_count': 0, 'materials': '',
                        'material_status': '', 'no_tex_slots': 0})
            out.append(row)
            continue
        mats = e['materials'] or ['no_tex']
        status = e['statuses'][0] if len(mats) == 1 else 'multi'
        row.update({'slots': e['slots'], 'material_count': len(mats),
                    'materials': '|'.join(mats), 'material_status': status,
                    'no_tex_slots': e['no_tex']})
        out.append(row)

    with io.open(EXPORT, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(out)
    print('models %d -> %s（字段: %s）' % (len(out), EXPORT, ','.join(fields)))


if __name__ == '__main__':
    main()
