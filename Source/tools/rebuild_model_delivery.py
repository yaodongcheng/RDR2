# -*- coding: utf-8 -*-
"""按**当前** asset_inventory_models.csv 重排模型交付：

- import=1 的模型 → deliverable/models/
- in_scenes=1 且 import!=1 → deliverable/models_extra/
- 已交付但分类变了的：移动 TRF + 改清单
- 新出现的：从 .mdl 导出单档 TRF
- 旧清单里有、新清单里没有的：移到 _scratch/obsolete_models（不留在交付里）

产物：
  deliverable/models/*.trf
  deliverable/models_extra/*.trf
  deliverable/manifests/models_export.csv        （基础列；材质列由 merge_model_master 重建）
  deliverable/manifests/models_export_extra.csv
  控制台统计。
"""
import csv
import io
import json
import os
import shutil
import sys

RDR2 = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(RDR2, 'assets/lib_native')
D = os.path.join(RDR2, 'deliverable')
M = os.path.join(D, 'manifests')
MODELS = os.path.join(D, 'models')
EXTRA = os.path.join(D, 'models_extra')
OBS = os.path.join(RDR2, '_scratch/obsolete_models')
INV = os.path.join(M, 'asset_inventory_models.csv')
MAN_IMP = os.path.join(M, 'models_export.csv')
MAN_EXT = os.path.join(M, 'models_export_extra.csv')

# 复用导出器（LWN Scripts）
_HERE = os.path.dirname(os.path.abspath(__file__))
_MODULES = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, os.path.join(_MODULES, 'LivingWorldNpcs', 'Scripts'))
import export_rdr2_trf_mdl as E  # noqa: E402


def read_rows(p):
    return list(csv.DictReader(io.open(p, encoding='utf-8-sig')))


def base_row(r):
    return [r['name'], r['model_hash'], r['mdl'], r['name'] + '.trf',
            r['faces'], r.get('bytes', '')]


def main():
    inv = read_rows(INV)
    target = {}
    for r in inv:
        h = (r.get('model_hash') or '').lower()
        if not h:
            continue
        if r.get('import') == '1':
            target[h] = ('models', r)
        elif r.get('in_scenes') == '1':
            target[h] = ('extra', r)

    old = {}
    for folder, man in (('models', MAN_IMP), ('extra', MAN_EXT)):
        if os.path.exists(man):
            for r in read_rows(man):
                h = (r.get('model_hash') or '').lower()
                if h:
                    old[h] = (folder, r)

    idx = json.load(io.open(os.path.join(LIB, 'index.json'), encoding='utf-8'))
    tex_names = {i: (t.get('n') or '') for i, t in enumerate(idx['tex'])}

    os.makedirs(MODELS, exist_ok=True)
    os.makedirs(EXTRA, exist_ok=True)
    os.makedirs(OBS, exist_ok=True)
    os.makedirs(M, exist_ok=True)

    out = {'models': [], 'extra': []}
    moved = exported = obsolete = 0
    fail = []
    for i, (h, (folder, r)) in enumerate(target.items(), 1):
        name = r['name']
        dst_dir = MODELS if folder == 'models' else EXTRA
        dst = os.path.join(dst_dir, name + '.trf')
        src = None
        if h in old:
            ofolder, orow = old[h]
            for cand in ((MODELS if ofolder == 'models' else EXTRA), MODELS, EXTRA):
                p = os.path.join(cand, (orow.get('name') or name) + '.trf')
                if os.path.exists(p):
                    src = p
                    break
        if os.path.exists(dst):
            # 已就位；若同名不同 hash 冲突，先报错
            moved += 0
        elif src:
            if os.path.dirname(src) != dst_dir:
                shutil.move(src, dst)
                moved += 1
            else:
                # 同一目录但名字不同
                shutil.move(src, dst)
                moved += 1
        else:
            try:
                meshes = E.read_mdl(os.path.join(LIB, r['mdl']), tex_names)
                if not meshes:
                    raise ValueError('no submesh')
                for j, m in enumerate(meshes):
                    m.mesh_name = name if len(meshes) == 1 else '%s.%d' % (name, j)
                E.export_trf_file(meshes, dst)
                exported += 1
            except Exception as e:
                fail.append((name, repr(e)))
                continue
        out[folder].append([name, r['model_hash'], r['mdl'], name + '.trf',
                            r['faces'], os.path.getsize(dst)])
        if i % 500 == 0:
            print('[rebuild] %d/%d moved=%d exported=%d fail=%d' %
                  (i, len(target), moved, exported, len(fail)), flush=True)

    # 旧清单中已不在新目标的：移出交付
    target_h = set(target)
    for h, (folder, r) in old.items():
        if h in target_h:
            continue
        name = r.get('name') or ''
        src = os.path.join(MODELS if folder == 'models' else EXTRA, name + '.trf')
        if os.path.exists(src):
            shutil.move(src, os.path.join(OBS, os.path.basename(src)))
            obsolete += 1

    for folder, path in (('models', MAN_IMP), ('extra', MAN_EXT)):
        with io.open(path, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(['name', 'model_hash', 'mdl', 'trf', 'faces', 'bytes'])
            w.writerows(out[folder])

    print('[rebuild] done: models=%d extra=%d moved=%d exported=%d obsolete=%d fail=%d' %
          (len(out['models']), len(out['extra']), moved, exported, obsolete, len(fail)))
    for x in fail[:10]:
        print('  FAIL', x)


if __name__ == '__main__':
    main()
