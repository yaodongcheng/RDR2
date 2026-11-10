# -*- coding: utf-8 -*-
"""生成「模型 → 材质」对照表（每个 TRF 子网格对应哪个材质）。

已有两张表：
  · material_textures.csv      材质 → albedo / normal / ma
  · models_export.csv          模型 → TRF 文件
本脚本输出逐槽明细：
  · model_materials.csv           一行 = 一个模型的一个子网格（= TRF 里一个 mesh）
  · 模型级汇总（文件 + 材质）合并进 `models_export.csv`（由 `merge_model_master.py` 生成）

字段：
  model / model_hash / trf / trf_mesh / slot / material / albedo / normal / ma /
  faces / verts / material_status

口径：
  · slot 顺序 = `.mdl` 子网格顺序（与 TRF 的 `<model>.<i>` 一一对应）；
  · 跳过 vc/ic 为 0 的子网格（与 `export_rdr2_trf_mdl.py` 一致）；
  · 材质名 = albedo 贴图名；无 albedo = `no_tex`。

用法：
    python tools/build_model_material_table.py
"""
import csv
import collections
import io
import json
import os

RDR2 = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(RDR2, 'assets/lib_native')
MANIFESTS = os.path.join(RDR2, 'deliverable/manifests')
INDEX = os.path.join(LIB, 'index.json')
IMPORT = os.path.join(MANIFESTS, 'asset_import_models.csv')
EXPORT = os.path.join(MANIFESTS, 'models_export.csv')
MATS = os.path.join(MANIFESTS, 'material_textures.csv')
OUT = os.path.join(MANIFESTS, 'model_materials.csv')


def main():
    idx = json.load(io.open(INDEX, encoding='utf-8'))
    models, tex = idx['models'], idx['tex']

    trf_of = {}
    for man in (EXPORT, os.path.join(MANIFESTS, 'models_export_extra.csv')):
        if not os.path.exists(man):
            continue
        for r in csv.DictReader(io.open(man, encoding='utf-8-sig')):
            try:
                trf_of[int(r['model_hash'], 16)] = r.get('trf') or ''
            except (KeyError, ValueError):
                continue

    status_of = {}
    if os.path.exists(MATS):
        for r in csv.DictReader(io.open(MATS, encoding='utf-8-sig')):
            status_of[r['material']] = r.get('status') or ''

    # 🔴 2026-11-10：口径从「只做导入子集」改成「两份交付清单全做」。
    # 原因：打包（stage_rdr2_models）会把 models_extra 里场景用到的模型也装进批次，
    # 而它们原来在材质表里没有行 → 建不出材质 → 编辑器「Unable to find material」弹窗。
    rows = []
    for man in (EXPORT, os.path.join(MANIFESTS, 'models_export_extra.csv')):
        if os.path.exists(man):
            rows.extend(csv.DictReader(io.open(man, encoding='utf-8-sig')))

    out = []
    stat = collections.Counter()
    for r in rows:
        h = r.get('model_hash') or ''
        model = r.get('name') or h
        m = models.get(h)
        trf = trf_of.get(int(h, 16), '') if h else ''
        if not trf:
            trf = model + '.trf'
        if not m:
            out.append([model, h, trf, model, -1, 'no_tex', '', '', '', 0, 0, 'no alb'])
            stat['no index'] += 1
            continue
        st = m.get('st') or []
        valid = []
        for i, sub in enumerate(m.get('s') or []):
            if not sub:
                continue
            tid, vc, ic = sub[0], sub[1], sub[2]
            if vc <= 0 or ic <= 0:
                continue
            valid.append((i, sub))
        n = len(valid)
        for vi, (i, sub) in enumerate(valid):
            tid, vc, ic = sub[0], sub[1], sub[2]
            alb = tex[tid]['n'] if isinstance(tid, int) and 0 <= tid < len(tex) else ''
            nt = mt = -1
            if i < len(st) and st[i]:
                nt, mt = st[i][0], st[i][1]
            nm = tex[nt]['n'] if isinstance(nt, int) and 0 <= nt < len(tex) else ''
            ma = tex[mt]['n'] if isinstance(mt, int) and 0 <= mt < len(tex) else ''
            material = alb or 'no_tex'
            mesh_name = model if n == 1 else '%s.%d' % (model, vi)
            out.append([model, h, trf, mesh_name, vi, material, alb, nm, ma,
                        ic // 3, vc, status_of.get(material, '')])
            stat['slots'] += 1

    with io.open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['model', 'model_hash', 'trf', 'trf_mesh', 'slot',
                    'material', 'albedo', 'normal', 'ma', 'faces', 'verts',
                    'material_status'])
        w.writerows(out)
    print('slots %d -> %s（模型级汇总见 models_export.csv）' % (len(out), OUT))
    print('slot stats:', dict(stat))


if __name__ == '__main__':
    main()
