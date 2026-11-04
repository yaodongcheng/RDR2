# -*- coding: utf-8 -*-
"""扫描 56 张场景 blend，导出**对象摆放清单**（交接 TODO-4），顺带收集用到的模型 hash（TODO-3 的输入）。

产物：
  deliverable/blender/scenes/placement_<id>.jsonl
      一行一个对象：name / hash / model_hash / cls / ring / loc / quat / scale / bbox /
      hide_tag / part_key / split_of / int_pkg / tile
  deliverable/handoff/mesh_usage.csv
      一行一个模型 hash：被多少张场景用到、实例总数、出现的对象名样例

用法（一次进程跑完 56 张，别一张开一个 Blender）：
    blender -b --factory-startup -P tools\\_unbuffer.py -P tools\\export_scene_placements.py -- \
        --dir "...\\deliverable\\blender\\scenes" --out-csv "...\\deliverable\\handoff\\mesh_usage.csv"
"""
import argparse
import csv
import json
import os
import sys

import bpy
from mathutils import Vector

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--dir', default=r'D:/BrainMaker/大镖客2解包分析/deliverable/blender/scenes')
ap.add_argument('--out-csv', default=r'D:/BrainMaker/大镖客2解包分析/deliverable/handoff/mesh_usage.csv')
ap.add_argument('--only', default='', help='只跑这些 id，逗号分隔')
a = ap.parse_args(ARGS)

only = set(x.strip() for x in a.only.split(',') if x.strip())
blends = sorted(f for f in os.listdir(a.dir) if f.endswith('.blend'))
if only:
    blends = [f for f in blends if f[:-6] in only]

usage = {}      # model_hash -> {'scenes': set, 'n': int, 'names': set}


def world_matrix(o):
    return o.matrix_world if o.parent else o.matrix_basis


def bb_of(o, mw):
    mn = Vector((1e18,) * 3)
    mx = Vector((-1e18,) * 3)
    for c in o.bound_box:
        p = mw @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], p[i])
            mx[i] = max(mx[i], p[i])
    return mn, mx


for bi, fn in enumerate(blends, 1):
    sid = fn[:-6]
    path = os.path.join(a.dir, fn)
    print('[place] (%d/%d) %s' % (bi, len(blends), sid), flush=True)
    try:
        bpy.ops.wm.open_mainfile(filepath=path)
    except Exception as e:
        print('[place] 打开失败 %s：%s' % (sid, e), flush=True)
        continue
    try:
        bpy.context.view_layer.update()
    except Exception:
        pass

    rows = []
    for o in bpy.context.scene.objects:
        if o.type != 'MESH':
            continue
        if o.name.startswith(('Terrain', 'Water')):
            continue
        mw = world_matrix(o)
        loc = mw.translation
        quat = mw.to_quaternion()
        scale = mw.to_scale()
        try:
            mn, mx = bb_of(o, mw)
            bb = [round(v, 2) for v in (mn.x, mn.y, mn.z, mx.x, mx.y, mx.z)]
        except Exception:
            bb = None
        h = o.get('hash')
        model_hash = o.get('split_of') or h
        rows.append({
            'n': o.name,
            'hash': h,
            'model_hash': model_hash,
            'cls': o.get('cls_key'),
            'ring': 1 if o.get('ring') else 0,
            'loc': [round(v, 3) for v in loc],
            'quat': [round(v, 5) for v in quat],
            'scale': [round(v, 5) for v in scale],
            'bb': bb,
            'hide_tag': o.get('hide_tag'),
            'part_key': o.get('part_key'),
            'split_of': o.get('split_of'),
            'int_pkg': o.get('int_pkg'),
            'tile': o.get('tile'),
        })
        key = model_hash
        if key:
            u = usage.setdefault(key, {'scenes': set(), 'n': 0, 'names': set()})
            u['scenes'].add(sid)
            u['n'] += 1
            if len(u['names']) < 4:
                u['names'].add(o.name)

    outp = os.path.join(a.dir, 'placement_%s.jsonl' % sid)
    with open(outp, 'w', encoding='utf-8') as fp:
        for r in rows:
            fp.write(json.dumps(r, ensure_ascii=False) + '\n')
    print('[place]   %d 个对象 -> %s' % (len(rows), os.path.basename(outp)), flush=True)

os.makedirs(os.path.dirname(a.out_csv), exist_ok=True)
with open(a.out_csv, 'w', encoding='utf-8-sig', newline='') as fp:
    wr = csv.writer(fp)
    wr.writerow(['model_hash', 'scenes', 'instances', 'scene_list', 'name_samples'])
    for h, u in sorted(usage.items(), key=lambda kv: -kv[1]['n']):
        wr.writerow([h, len(u['scenes']), u['n'], '|'.join(sorted(u['scenes'])),
                     '|'.join(sorted(u['names']))])
print('[place] 用到的模型 hash：%d 个 -> %s' % (len(usage), a.out_csv), flush=True)
