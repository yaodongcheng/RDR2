# -*- coding: utf-8 -*-
"""RDR2 全量资产清单：**大地图 + 56 张子场景**实际要用到的模型与贴图。

输入（都是现成产物）：
  deliverable/handoff/mesh_usage.csv           56 张场景用到的模型（hash / 实例 / 场景）
  deliverable/handoff/lod_fragments.csv        大地图远景碎片（hash / 组 / 实例）
  deliverable/blender/scenes/placement_*.jsonl 每场景对象（分类 / ring）
  assets/lib_native/index.json                 模型 → 子网格/贴图 id；贴图表

产物（deliverable/handoff/）：
  asset_inventory_models.csv     一行一个模型：hash / 名称 / 面数 / 贴图 / 场景用量 / 大地图用量 / 分类 / 是否需要 LOD
  asset_inventory_textures.csv   一行一张贴图：id / 名称 / 文件 / 类型 / 被多少模型和实例用 / 文件大小
  asset_inventory_scenes.csv     一行一个场景：对象数 / 唯一模型 / 三角面 / 远景数
  asset_inventory_summary.json   汇总（含大地图交付物、已知缺口、旧实验作废说明）

用法：
    python tools/build_asset_inventory.py
"""
import csv
import collections
import json
import os

RDR2 = r'D:/BrainMaker/大镖客2解包分析'
HANDOFF = os.path.join(RDR2, 'deliverable/handoff')
SCENES = os.path.join(RDR2, 'deliverable/blender/scenes')
LIB = os.path.join(RDR2, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')
USAGE = os.path.join(HANDOFF, 'mesh_usage.csv')
FRAG = os.path.join(HANDOFF, 'lod_fragments.csv')
MINI = os.path.join(RDR2, 'deliverable/miniatures')

LOD_MIN_FACES = 2000

# 2026-11-05 用户裁定：除地形/埋地/水面/占位/区内 lod 外，其余类全导
# （贴花 / 道路 / 石块 / 植被也导，先看效果，不一定最终用）。
IMPORT_CLASSES = {
    'bldg', 'part', 'prop', 'junk', 'veg', 'rock', 'stone', 'struct', 'ruin', 'veh',
    'rail', 'rail_decal', 'road', 'decal', 'unknown', 'lod_out',
}
EXCLUDE_CLASSES = {'terrain_cell', 'terrain_lod', 'underground', 'watertile',
                   'placeholder', 'lod'}


def canon(h):
    h = (h or '').strip().lower()
    if h.startswith('0x'):
        try:
            return '0x%08x' % int(h, 16)
        except Exception:
            return h
    return h


def main():
    idx = json.load(open(INDEX, encoding='utf-8'))
    models = idx['models']
    tex = idx['tex']
    print('索引：模型 {:,} / 贴图 {:,}'.format(len(models), len(tex)))

    # ---------- 场景用量 ----------
    scene_use = {}
    for r in csv.DictReader(open(USAGE, encoding='utf-8-sig')):
        h = canon(r.get('model_hash'))
        if not h:
            continue
        scene_use[h] = {
            'instances': int(float(r.get('instances') or 0)),
            'scenes': int(float(r.get('scenes') or 0)),
            'scene_list': r.get('scene_list') or '',
            'names': r.get('name_samples') or '',
        }
    print('场景用到模型：{:,}'.format(len(scene_use)))

    # ---------- 大地图碎片用量 ----------
    bm_use = collections.Counter()
    bm_groups = collections.defaultdict(set)
    bm_parts = set()
    with open(FRAG, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            h = canon(r.get('hash'))
            if not h:
                continue
            bm_use[h] += 1
            bm_groups[h].add(r.get('group_id') or '')
            if r.get('part_key'):
                bm_parts.add(r['part_key'])
    print('大地图碎片模型：{:,}（实例 {:,}）'.format(len(bm_use), sum(bm_use.values())))

    # ---------- 每场景对象/面数 + 每模型分类 ----------
    scene_stats = {}
    model_classes = collections.defaultdict(collections.Counter)

    def model_faces(m):
        if not m:
            return 0
        return sum(int(s[2]) for s in (m.get('s') or []) if len(s) >= 3) // 3

    def model_verts(m):
        if not m:
            return 0
        return sum(int(s[1]) for s in (m.get('s') or []) if len(s) >= 3)

    for fn in sorted(os.listdir(SCENES)):
        if not fn.startswith('placement_') or not fn.endswith('.jsonl'):
            continue
        sid = fn[len('placement_'):-6]
        objs = 0
        hs = set()
        faces = 0
        ring = 0
        imp_objs = 0
        imp_faces = 0
        for line in open(os.path.join(SCENES, fn), encoding='utf-8'):
            r = json.loads(line)
            objs += 1
            h = canon(r.get('model_hash'))
            cls = r.get('cls') or '?'
            if r.get('ring'):
                ring += 1
            if not h:
                continue
            hs.add(h)
            model_classes[h][cls] += 1
            f = model_faces(models.get(h))
            faces += f
            if cls in IMPORT_CLASSES:
                imp_objs += 1
                imp_faces += f
        scene_stats[sid] = {'objects': objs, 'unique_models': len(hs),
                            'faces': faces, 'ring': ring,
                            'import_objects': imp_objs, 'import_faces': imp_faces}

    # ---------- 模型清单 + 贴图用量 ----------
    imp_hashes = set()
    for h in set(scene_use) | set(bm_use):
        cnt = model_classes.get(h)
        if (cnt and any(k in IMPORT_CLASSES for k in cnt)) or (h in bm_use):
            imp_hashes.add(h)

    tex_use = collections.defaultdict(lambda: {'models': set(), 'instances': 0, 'types': set()})
    tex_use_imp = collections.defaultdict(lambda: {'models': set(), 'instances': 0, 'types': set()})

    def add_tex(tid, h, inst, typ, imp):
        try:
            tid = int(tid)
        except Exception:
            return
        if tid < 0 or tid >= len(tex):
            return
        for store in ((tex_use, tex_use_imp) if imp else (tex_use,)):
            u = store[tid]
            u['models'].add(h)
            u['instances'] += inst
            u['types'].add(typ)

    model_rows = []
    all_hashes = sorted(set(scene_use) | set(bm_use))
    for h in all_hashes:
        m = models.get(h)
        imp = 1 if h in imp_hashes else 0
        cnt = model_classes.get(h)
        imp_classes = sorted(k for k in (cnt or {}) if k in IMPORT_CLASSES)
        if m is None:
            model_rows.append([h, '', '', 0, 0, '', '', '', 0, 0, 0, 0, 0, 0, '', 0,
                               imp, '|'.join(imp_classes)])
            continue
        su = scene_use.get(h, {})
        inst = su.get('instances', 0)
        bmi = bm_use.get(h, 0)
        fs = model_faces(m)
        vs = model_verts(m)
        alb, nm, ma = [], [], []
        for i, sub in enumerate(m.get('s') or []):
            if len(sub) >= 3:
                tid = sub[0]
                n = tex[tid]['n'] if 0 <= tid < len(tex) else ''
                if n:
                    alb.append(n)
                    add_tex(tid, h, inst + bmi, 'alb', imp)
            pair = (m.get('st') or [])
            if i < len(pair) and pair[i]:
                nt, mt = pair[i][0], pair[i][1]
                nn = tex[nt]['n'] if 0 <= nt < len(tex) else ''
                if nn:
                    nm.append(nn)
                    add_tex(nt, h, inst + bmi, 'nm', imp)
                mn = tex[mt]['n'] if 0 <= mt < len(tex) else ''
                if mn:
                    ma.append(mn)
                    add_tex(mt, h, inst + bmi, 'ma', imp)
            lyr = (m.get('lyr') or [])
            if i < len(lyr) and lyr[i]:
                for j, tid in enumerate(lyr[i]):
                    if tid is None or int(tid) < 0:
                        continue
                    ln = tex[int(tid)]['n'] if int(tid) < len(tex) else ''
                    if ln:
                        add_tex(int(tid), h, inst + bmi, 'lyr%d' % j, imp)
        cls = ','.join('%s:%d' % (k, v) for k, v in cnt.most_common(4)) if cnt else ''
        name = (su.get('names') or '').split('|')[0] or os.path.splitext(os.path.basename(m.get('f') or ''))[0]
        model_rows.append([
            h, name, m.get('f') or '', fs, vs,
            '|'.join(sorted(set(alb))), '|'.join(sorted(set(nm))), '|'.join(sorted(set(ma))),
            1 if alb else 0,
            1 if h in scene_use else 0, su.get('scenes', 0), inst,
            1 if h in bm_use else 0, bmi,
            cls, 1 if fs >= LOD_MIN_FACES else 0,
            imp, '|'.join(imp_classes),
        ])

    MODEL_HDR = ['model_hash', 'name', 'mdl', 'faces', 'verts',
                 'albedo', 'normal', 'ma', 'has_alb',
                 'in_scenes', 'scenes', 'scene_instances',
                 'in_bigmap', 'bigmap_instances', 'classes', 'needs_lod',
                 'import', 'import_classes']
    with open(os.path.join(HANDOFF, 'asset_inventory_models.csv'), 'w',
              encoding='utf-8-sig', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(MODEL_HDR)
        wr.writerows(model_rows)
    with open(os.path.join(HANDOFF, 'asset_import_models.csv'), 'w',
              encoding='utf-8-sig', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(MODEL_HDR)
        wr.writerows([r for r in model_rows if r[16] == 1])

    # 贴图清单（全量 + 导入子集）
    def write_tex_csv(path, store):
        rows = []
        total = missing = 0
        for tid, u in sorted(store.items(), key=lambda kv: -len(kv[1]['models'])):
            t = tex[tid]
            fp = os.path.join(LIB, t.get('f') or '')
            exists = os.path.exists(fp)
            size = os.path.getsize(fp) if exists else 0
            total += size
            if not exists:
                missing += 1
            rows.append([tid, t.get('n') or '', t.get('f') or '',
                         '|'.join(sorted(u['types'])), len(u['models']), u['instances'],
                         size, 1 if exists else 0])
        with open(path, 'w', encoding='utf-8-sig', newline='') as f:
            wr = csv.writer(f)
            wr.writerow(['tex_id', 'name', 'file', 'type', 'models', 'instances', 'bytes', 'exists'])
            wr.writerows(rows)
        return total, missing

    tex_bytes, tex_missing = write_tex_csv(os.path.join(HANDOFF, 'asset_inventory_textures.csv'), tex_use)
    imp_tex_bytes, imp_tex_missing = write_tex_csv(os.path.join(HANDOFF, 'asset_import_textures.csv'),
                                                   tex_use_imp)

    # 场景清单
    status = {r['id']: r for r in csv.DictReader(open(os.path.join(SCENES, 'scene_build_status.csv'),
                                                      encoding='utf-8'))}
    with open(os.path.join(HANDOFF, 'asset_inventory_scenes.csv'), 'w',
              encoding='utf-8-sig', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(['id', 'name', 'kind', 'objects', 'unique_models', 'faces', 'ring',
                     'import_objects', 'import_faces', 'rooms', 'blend_mb'])
        for sid, s in sorted(scene_stats.items()):
            st = status.get(sid, {})
            wr.writerow([sid, st.get('name') or '', st.get('kind') or '',
                         s['objects'], s['unique_models'], s['faces'], s['ring'],
                         s['import_objects'], s['import_faces'],
                         st.get('rooms') or '', st.get('blend_mb') or ''])

    # 汇总
    mini = []
    if os.path.isdir(os.path.join(MINI, 'models')):
        mini = sorted(os.listdir(os.path.join(MINI, 'models')))
    faces_all = sum(model_faces(models.get(h)) for h in all_hashes)
    summary = {
        'generated_for': 'RDR2 大地图 + 56 张子场景（旧 sdn 实验产物作废，不在统计内）',
        'scenes': {'count': len(scene_stats),
                   'objects': sum(s['objects'] for s in scene_stats.values()),
                   'unique_models': len(scene_use),
                   'faces_instances': sum(s['faces'] for s in scene_stats.values())},
        'big_map': {'fragment_models': len(bm_use), 'fragment_instances': sum(bm_use.values()),
                    'split_parts': len(bm_parts), 'groups': 55,
                    'miniatures': len(mini),
                    'miniature_faces': 84502},
        'models': {'union': len(all_hashes),
                   'scenes_only': len(set(scene_use) - set(bm_use)),
                   'bigmap_only': len(set(bm_use) - set(scene_use)),
                   'both': len(set(scene_use) & set(bm_use)),
                   'needs_lod_ge2000': sum(1 for h in all_hashes
                                           if model_faces(models.get(h)) >= LOD_MIN_FACES),
                   'faces_models_unique': faces_all},
        'textures': {'unique_used': len(tex_use), 'bytes_total': tex_bytes,
                     'missing_files': tex_missing},
        'import': {
            'classes': sorted(IMPORT_CLASSES),
            'excluded_classes': sorted(EXCLUDE_CLASSES),
            'models': len(imp_hashes),
            'needs_lod_ge2000': sum(1 for h in imp_hashes
                                    if model_faces(models.get(h)) >= LOD_MIN_FACES),
            'objects': sum(s['import_objects'] for s in scene_stats.values()),
            'faces_instances': sum(s['import_faces'] for s in scene_stats.values()),
            'textures': len(tex_use_imp),
            'textures_bytes': imp_tex_bytes,
            'textures_missing': imp_tex_missing,
        },
        'note': '旧 sdn 实验（rdr2_sanit_denis / 5,211 FBX / 旧 tpac）全部作废，本清单是唯一导入口径',
    }
    json.dump(summary, open(os.path.join(HANDOFF, 'asset_inventory_summary.json'), 'w',
                            encoding='utf-8'), ensure_ascii=False, indent=1)

    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print('清单 ->', HANDOFF)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
