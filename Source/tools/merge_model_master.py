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
        if not e:
            out.append([r.get('name', ''), r.get('model_hash', ''), r.get('mdl', ''),
                        r.get('trf', ''), r.get('faces', ''), r.get('bytes', ''),
                        0, 0, '', '', 0])
            continue
        mats = e['materials'] or ['no_tex']
        status = e['statuses'][0] if len(mats) == 1 else 'multi'
        out.append([r.get('name', ''), r.get('model_hash', ''), r.get('mdl', ''),
                    r.get('trf', ''), r.get('faces', ''), r.get('bytes', ''),
                    e['slots'], len(mats), '|'.join(mats), status, e['no_tex']])

    with io.open(EXPORT, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        w.writerows(out)
    print('models %d -> %s（字段: %s）' % (len(out), EXPORT, ','.join(FIELDS)))


if __name__ == '__main__':
    main()
