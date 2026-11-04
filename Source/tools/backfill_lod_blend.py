# -*- coding: utf-8 -*-
r"""把 v23 抽出时漏掉的远景碎片（区域补充入库的那批）从区域 blend 追加回 lod_split blend。

背景：`continent_lod_split_v23.blend` 是从 **v23** 抽的，而 v23 之后 22 个区域又补建过
（`regions_support/*/manifest_*.jsonl` 比 v23 多出 57 条 lod 记录）。这 57 条在分组表里
有、在 blend 里没有 ⇒ 按片区拆出来的 `S_dewclm` / `S_hso` / `S_sha` 会偏少。

做法：读 `lod_fragments.csv` 求出「表里有、blend 里没有」的键，按 tile 找到对应区域 blend，
用 `bpy.data.libraries.load(link=False)` 按**对象名**追加进来，挂到父集合（随后由
`group_lod_blend.py` 统一归位）。

    blender -b "...\continent_lod_split_v23.blend" -P tools\_unbuffer.py -P tools\backfill_lod_blend.py -- \
        --csv "...\deliverable\handoff\lod_fragments.csv"

贴图路径：区域 blend 与 lod_split 都在 `deliverable/blender/` 下**同一层深**
（`//..\..\..\assets\...`），追加后相对路径仍然有效，不需要重算（实测区域侧 8,139 张全在）。
"""

import argparse
import csv
import glob
import json
import os
import sys

import bpy

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--csv', required=True)
ap.add_argument('--regions', default=r'D:/BrainMaker/大镖客2解包分析/deliverable/blender/regions')
ap.add_argument('--support', default=r'D:/BrainMaker/大镖客2解包分析/deliverable/blender/regions_support')
ap.add_argument('--parent', default='ONLY_lod_远景碎片')
a = ap.parse_args(ARGS)


def key_of(h, x, y, z):
    return (int(h, 16) if isinstance(h, str) else int(h),
            round(float(x), 1), round(float(y), 1), round(float(z), 1))


# ---------------------------------------------------------------- 现有对象
parent = bpy.data.collections.get(a.parent)
if parent is None:
    raise SystemExit('[backfill] 找不到父集合 %s' % a.parent)

have = set()
for ob in bpy.data.objects:
    h = ob.get('hash')
    if h:
        have.add(key_of(h, ob.location.x, ob.location.y, ob.location.z))
print('[backfill] 现有对象 %d（带 hash 的键 %d）' % (len(bpy.data.objects), len(have)))

# ---------------------------------------------------------------- 分组表里缺哪些
rows = []
with open(a.csv, encoding='utf-8-sig', newline='') as fp:
    for r in csv.DictReader(fp):
        k = key_of(r['hash'], r['wx'], r['wy'], r['wz'])
        if k not in have:
            rows.append((k, r['tile'], r['name'], r['group_id']))
print('[backfill] 表里有、blend 里没有：%d 条' % len(rows))
if not rows:
    print('[backfill] 无需补，退出')
    raise SystemExit(0)

by_tile = {}
for k, tile, name, gid in rows:
    by_tile.setdefault(tile, []).append((k, name, gid))
for t, v in by_tile.items():
    print('   %-18s %3d 条' % (t, len(v)))

# tile → 区域 blend
tile2blend = {}
for p in glob.glob(os.path.join(a.regions, '*.blend')):
    base = os.path.basename(p)[:-6]
    if '_' in base:
        tile2blend[base.split('_', 1)[1]] = p

# tile → 区域 manifest（拿 Blender 里的准确对象名，含 .001 后缀）
tile2man = {}
for p in glob.glob(os.path.join(a.support, '*', 'manifest_*.jsonl')):
    base = os.path.basename(p)
    tile2man[base.replace('manifest_', '').replace('.jsonl', '').split('_', 1)[1]] = p

appended_total = 0
for tile, items in sorted(by_tile.items()):
    blend = tile2blend.get(tile)
    man = tile2man.get(tile)
    if not blend or not man:
        print('[backfill] ⚠ %s 没有区域 blend / manifest，跳过 %d 条' % (tile, len(items)))
        continue
    want = {k for k, _, _ in items}
    names = []
    with open(man, encoding='utf-8') as fp:
        for line in fp:
            r = json.loads(line)
            if r.get('c') != 'lod' or not r.get('h'):
                continue
            k = key_of(r['h'], r['p'][0], r['p'][1], r['p'][2])
            if k in want:
                names.append(r['n'])
    if not names:
        print('[backfill] ⚠ %s 在 manifest 里找不到对象名，跳过' % tile)
        continue
    print('[backfill] %s → 从 %s 追加 %d 个' % (tile, os.path.basename(blend), len(names)))
    before = {o.name for o in bpy.data.objects}
    with bpy.data.libraries.load(blend, link=False) as (data_from, data_to):
        missing_names = [n for n in names if n not in data_from.objects]
        if missing_names:
            print('[backfill] ⚠ 源文件里没有这些名字（前 5）：%s' % missing_names[:5])
        data_to.objects = [n for n in names if n in data_from.objects]
    got = [ob for ob in data_to.objects if ob is not None]
    for ob in got:
        if ob.name not in parent.objects:
            parent.objects.link(ob)
    appended_total += len(got)
    print('[backfill]   实际追加 %d 个（新对象 %d）'
          % (len(got), len({o.name for o in bpy.data.objects} - before)))

print('[backfill] 合计追加 %d 个；父集合现有 %d 个' % (appended_total, len(parent.objects)))

try:
    bpy.context.preferences.filepaths.save_version = 0
except Exception:
    pass
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print('[backfill] SAVED %s %.2f GB' % (bpy.data.filepath, os.path.getsize(bpy.data.filepath) / 1e9))
print('[backfill] VERDICT → %s' % ('PASS' if appended_total == len(rows) else 'CHECK'))
