# -*- coding: utf-8 -*-
"""按据点/野地/瓜玛生成**大地图 prefab 数据**（交接 TODO-5）。

输入（都是现成的）：
  deliverable/manifests/lod_fragments.csv   一行一个远景碎片（含 gx,gy,gz 相对组锚点）
  deliverable/manifests/lod_groups.json     每组汇总（锚点 / 名称 / 包围盒 / 成员）

产物：
  deliverable/manifests/prefabs/<group_id>.json   一个组一个 prefab
      { group_type, group_id, name_zh, anchor_world, count, tris, verts,
        fragments:[{frag_id,part_key,name,hash,mdl,tris,verts,sub_group,
                    rot:[qx,qy,qz,qw], scale:[sxy,sz], pos_local:[gx,gy,gz],
                    pos_world:[wx,wy,wz], bbox:[...]}] }
  deliverable/manifests/prefabs_index.json        索引 + 自检（组数 / 碎片总数 / 空组）

用法：
    python tools/build_lod_prefabs.py
"""
import argparse
import csv
import datetime
import json
import os

RDR2 = r'D:/BrainMaker/大镖客2解包分析'
HANDOFF = os.path.join(RDR2, 'deliverable/manifests')
CSV_FRAG = os.path.join(HANDOFF, 'lod_fragments.csv')
JSON_GROUPS = os.path.join(HANDOFF, 'lod_groups.json')
OUT_DIR = os.path.join(HANDOFF, 'prefabs')
OUT_IDX = os.path.join(HANDOFF, 'prefabs_index.json')


def fnum(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default=CSV_FRAG)
    ap.add_argument('--groups', default=JSON_GROUPS)
    ap.add_argument('--out', default=OUT_DIR)
    ap.add_argument('--index', default=OUT_IDX)
    a = ap.parse_args()

    meta = json.load(open(a.groups, encoding='utf-8'))
    gmeta = {(g.get('group_type'), g.get('group_id')): g for g in meta.get('groups') or []}

    groups = {}
    with open(a.csv, encoding='utf-8-sig', newline='') as fp:
        for r in csv.DictReader(fp):
            gt = (r.get('group_type') or '').strip()
            gid = (r.get('group_id') or '').strip()
            if not gt or not gid:
                continue
            frag = {
                'frag_id': r.get('frag_id'),
                'part_key': r.get('part_key') or None,
                'name': r.get('name'),
                'hash': r.get('hash'),
                'mdl': r.get('mdl'),
                'tris': int(fnum(r.get('tris'))),
                'verts': int(fnum(r.get('verts'))),
                'sub_group': r.get('sub_group'),
                'rot': [fnum(r.get('qx')), fnum(r.get('qy')), fnum(r.get('qz')), fnum(r.get('qw'))],
                'scale': [fnum(r.get('sxy'), 1.0), fnum(r.get('sz'), 1.0)],
                'pos_local': [fnum(r.get('gx')), fnum(r.get('gy')), fnum(r.get('gz'))],
                'pos_world': [fnum(r.get('wx')), fnum(r.get('wy')), fnum(r.get('wz'))],
                'bbox': [fnum(r.get('bb_min_x')), fnum(r.get('bb_min_y')), fnum(r.get('bb_min_z')),
                         fnum(r.get('bb_max_x')), fnum(r.get('bb_max_y')), fnum(r.get('bb_max_z'))],
                'tex_albedo': r.get('tex_albedo') or '',
                'tex_normal': r.get('tex_normal') or '',
                'tex_ma': r.get('tex_ma') or '',
                'assign_via': r.get('assign_via') or '',
            }
            groups.setdefault((gt, gid), []).append(frag)

    os.makedirs(a.out, exist_ok=True)
    index = []
    total = 0
    bad = []
    for (gt, gid), frags in sorted(groups.items()):
        m = gmeta.get((gt, gid)) or {}
        prefab = {
            'group_type': gt, 'group_id': gid,
            'scene_name': m.get('scene_name'),
            'name_zh': m.get('name_zh'), 'name_en': m.get('name_en'),
            'anchor_world': m.get('anchor_world'),
            'count': len(frags),
            'tris': sum(x['tris'] for x in frags),
            'verts': sum(x['verts'] for x in frags),
            'bbox_world': m.get('bbox_world'),
            'fragments': frags,
        }
        fp = os.path.join(a.out, '%s.json' % gid)
        json.dump(prefab, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        index.append({'group_type': gt, 'group_id': gid, 'name_zh': m.get('name_zh'),
                      'count': len(frags), 'tris': prefab['tris'],
                      'file': os.path.basename(fp)})
        total += len(frags)
        if m.get('count') is not None and int(m['count']) != len(frags):
            bad.append((gid, m['count'], len(frags)))

    # 没有碎片的组（空组）：点名列出，别静默漏
    empty = [{'group_type': k[0], 'group_id': k[1], 'name_zh': v.get('name_zh')}
             for k, v in sorted(gmeta.items()) if not v.get('count')]

    out = {
        'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'source': {'fragments': os.path.relpath(a.csv, RDR2).replace('\\', '/'),
                   'groups': os.path.relpath(a.groups, RDR2).replace('\\', '/')},
        'note': 'local coord = pos_local（相对组锚点，直接用）；rot/scale 与 blend 同口径',
        'groups': index,
        'totals': {'groups': len(index), 'fragments': total},
        'empty_groups': empty,
        'mismatch_vs_lod_groups': bad,
    }
    json.dump(out, open(a.index, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('[prefab] 组 %d · 碎片 %d · 空组 %d' % (len(index), total, len(empty)))
    if bad:
        print('[prefab] ⚠ 与 lod_groups.json 计数不一致：%s' % bad)
    else:
        print('[prefab] ✅ 每组计数与 lod_groups.json 一致')
    for e in empty:
        print('[prefab]   空组（无远景碎片）：%s %s' % (e['group_id'], e.get('name_zh') or ''))
    print('[prefab] 索引 -> %s' % a.index)
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
