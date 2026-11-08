# -*- coding: utf-8 -*-
"""交付包自包含核对：场景并集 ↔ 交付模型/贴图，以及 blend 是否还引用包外路径。

检查项：
  1. 模型：57 张场景用到的 hash 是否都在 `models_export.csv` + `models_export_extra.csv` 里；
  2. 贴图：场景用到的 tex_id 是否都在 `textures_export.csv` + `_extra` + `_fallback` 里；
  3. blend：57 张 `.blend` 里是否还残留 `lib_native`（包外贴图路径）。

输出：
  deliverable/manifests/delivery_reconciliation.json
  控制台摘要。
"""
import csv
import collections
import glob
import io
import json
import os

RDR2 = r'D:/BrainMaker/大镖客2解包分析'
D = os.path.join(RDR2, 'deliverable')
M = os.path.join(D, 'manifests')
LIB = os.path.join(RDR2, 'assets/lib_native/index.json')
SCENES = os.path.join(D, 'blender/scenes')
OUT = os.path.join(M, 'delivery_reconciliation.json')


def hashes(path, col='model_hash'):
    s = set()
    if not os.path.exists(path):
        return s
    for r in csv.DictReader(io.open(path, encoding='utf-8-sig')):
        v = (r.get(col) or '').strip().lower()
        if v:
            s.add(v)
    return s


def main():
    idx = json.load(io.open(LIB, encoding='utf-8'))
    models, tex = idx['models'], idx['tex']
    inv = list(csv.DictReader(io.open(os.path.join(M, 'asset_inventory_models.csv'),
                                      encoding='utf-8-sig')))
    scene_models = {r['model_hash'].lower() for r in inv if r.get('in_scenes') == '1'}
    imp_models = hashes(os.path.join(M, 'models_export.csv'))
    extra_models = hashes(os.path.join(M, 'models_export_extra.csv'))
    delivered_models = imp_models | extra_models
    model_missing = scene_models - delivered_models
    model_extra = delivered_models - scene_models

    # 场景贴图：从场景模型的 s / st / lyr 收集
    def tids(h):
        m = models.get(h)
        out = set()
        if not m:
            return out
        st = m.get('st') or []
        ly = m.get('lyr') or []
        for i, sub in enumerate(m.get('s') or []):
            if sub and isinstance(sub[0], int) and sub[0] >= 0:
                out.add(sub[0])
            if i < len(st) and st[i]:
                for t in st[i]:
                    if isinstance(t, int) and t >= 0:
                        out.add(t)
            if i < len(ly) and ly[i]:
                for t in ly[i]:
                    if isinstance(t, int) and t >= 0:
                        out.add(t)
        return out

    scene_tex = set()
    for h in scene_models:
        scene_tex |= tids(h)

    def tex_ids(path):
        s = set()
        if not os.path.exists(path):
            return s
        for r in csv.DictReader(io.open(path, encoding='utf-8-sig')):
            try:
                s.add(int(r['tex_id']))
            except Exception:
                pass
        return s

    delivered_tex = (tex_ids(os.path.join(M, 'textures_export.csv')) |
                     tex_ids(os.path.join(M, 'textures_export_extra.csv')) |
                     tex_ids(os.path.join(M, 'textures_export_fallback.csv')))
    tex_missing = scene_tex - delivered_tex
    tex_extra = delivered_tex - scene_tex

    # blend 外部路径
    external = []
    for p in sorted(glob.glob(os.path.join(SCENES, '*.blend'))):
        b = open(p, 'rb').read()
        if b'lib_native' in b:
            external.append(os.path.basename(p))

    rep = dict(
        scene_models=len(scene_models),
        delivered_models=len(delivered_models),
        model_missing=len(model_missing),
        model_extra=len(model_extra),
        scene_textures=len(scene_tex),
        delivered_textures=len(delivered_tex),
        texture_missing=len(tex_missing),
        texture_extra=len(tex_extra),
        blend_external_refs=external,
        model_missing_sample=sorted(model_missing)[:20],
        texture_missing_sample=sorted(tex_missing)[:20],
    )
    json.dump(rep, io.open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    print('->', OUT)


if __name__ == '__main__':
    main()
