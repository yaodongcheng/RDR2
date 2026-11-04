# -*- coding: utf-8 -*-
r"""把「只放远景碎片」的 blend 按片区拆成子集合（一个据点 / 一块野地 / 一个瓜玛场景一个集合）。

    blender -b "...\continent_lod_split_v23.blend" -P tools\_unbuffer.py -P tools\group_lod_blend.py -- \
        --csv "D:\BrainMaker\大镖客2解包分析\deliverable\handoff\lod_fragments.csv" \
        --groups "D:\BrainMaker\大镖客2解包分析\deliverable\handoff\lod_groups.json"

输入：
  · 当前 blend 里的父集合（默认 `ONLY_lod_远景碎片`）—— 里面的对象会被移到子集合
  · `lod_fragments.csv` —— 每个碎片的 `group_type / group_id / hash / wx,wy,wz`
  · `lod_groups.json` —— 组的中文名（用来起可读的集合名）

产物（存回同一个 blend）：
  ONLY_lod_远景碎片/
    ├── S_<code>_<中文名>      据点（城镇 prefab 用）
    ├── W_<wild_id>            野地
    ├── G_<code>_<中文名>      瓜玛
    └── X_未匹配_<n>           对不上分组表的（地形区块等，日志里逐个打印）

匹配键 = `(hash, x, y, z)` 四舍五入到 **0.1 m**（CSV 的 wx/wy/wz 就是实例位置，
与 Blender 里对象的 location 同源；实测逐条对得上）。

幂等：重跑会先删掉父集合下所有 `S_/W_/G_/X_` 子集合（只删这些前缀，不碰别的东西），
再把对象重新归位 —— 不会产生重复集合。**不在任何集合里的对象会被 Blender 存盘时清掉**，
所以删除旧子集合之前先把对象挂回父集合。

不匹配的处置：不进任何场景 —— 落在 `X_未匹配`，日志打印前 30 个（正常应只剩
`nopq_xx_yy_area_slod4` 这类**地形远景块**，它们本来就不该进城镇 prefab）。
"""

import argparse
import csv
import json
import os
import sys

import bpy

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--csv', required=True)
ap.add_argument('--groups', required=True)
ap.add_argument('--parent', default='ONLY_lod_远景碎片')
ap.add_argument('--out', default='')
a = ap.parse_args(ARGS)

GROUP_PREFIX = ('S_', 'W_', 'G_', 'M_', 'X_')


def key_of(h, x, y, z):
    return (int(h, 16) if isinstance(h, str) else int(h),
            round(float(x), 1), round(float(y), 1), round(float(z), 1))


# ---------------------------------------------------------------- 读分组表
frag_group = {}
frag_part = {}          # part_key → 组（跨据点整块拆出来的部件，位置/哈希都和父块相同，不能按坐标匹配）
with open(a.csv, encoding='utf-8-sig', newline='') as fp:
    for r in csv.DictReader(fp):
        g = (r['group_type'], r['group_id'], r['scene_name'], r['sub_group'])
        if r.get('part_key'):
            frag_part[r['part_key']] = g
        else:
            frag_group[key_of(r['hash'], r['wx'], r['wy'], r['wz'])] = g

group_name = {}
with open(a.groups, encoding='utf-8') as fp:
    gj = json.load(fp)
for g in gj['groups']:
    group_name[(g['group_type'], g['group_id'])] = g.get('name_zh') or ''

print('[group] 分组表 %d 条 · 组 %d 个' % (len(frag_group), len(group_name)))

# ---------------------------------------------------------------- 找父集合
parent = bpy.data.collections.get(a.parent)
if parent is None:
    raise SystemExit('[group] 找不到父集合 %s；现有：%s'
                     % (a.parent, [c.name for c in bpy.data.collections]))

# 收集对象：父集合直属 + 旧子集合里的
objs = list(parent.objects)
restored = 0
for ch in list(parent.children):
    for ob in ch.objects:
        objs.append(ob)
        if ob.name not in parent.objects:
            parent.objects.link(ob)
            restored += 1
# 去重
seen = set()
uniq = []
for ob in objs:
    if ob.name not in seen:
        seen.add(ob.name)
        uniq.append(ob)
objs = uniq
print('[group] 父集合下对象 %d 个（其中从旧子集合挂回 %d 个）' % (len(objs), restored))

# 删旧子集合（只删本脚本起的前缀）
removed = 0
for ch in list(parent.children):
    if ch.name.startswith(GROUP_PREFIX):
        bpy.data.collections.remove(ch)
        removed += 1
print('[group] 删旧子集合 %d 个' % removed)

# ---------------------------------------------------------------- 建新子集合
def col_name(gtype, gid, zh):
    if gtype == 'settlement':
        return 'S_%s_%s' % (gid, zh) if zh else 'S_%s' % gid
    if gtype == 'wild':
        return 'W_%s' % gid
    if gtype == 'guarma':
        return 'G_%s_%s' % (gid, zh) if zh else 'G_%s' % gid
    if gtype == 'span':
        return 'M_跨据点区块'
    return 'X_未匹配'


buckets = {}
unmatched = []
for ob in objs:
    h = ob.get('hash')
    if not h:
        unmatched.append((ob, 'no-hash'))
        continue
    pk = ob.get('part_key')
    g = frag_part.get(pk) if pk else None
    if g is None:
        k = key_of(h, ob.location.x, ob.location.y, ob.location.z)
        g = frag_group.get(k)
    if g is None:
        unmatched.append((ob, '%s %.1f %.1f %.1f'
                          % (h, ob.location.x, ob.location.y, ob.location.z)))
        continue
    gtype, gid, scene, sub = g
    buckets.setdefault((gtype, gid), []).append(ob)

made = {}
for (gtype, gid), lst in sorted(buckets.items(), key=lambda kv: (kv[0][0] != 'settlement',
                                                                 kv[0][0] != 'wild',
                                                                 kv[0][0] != 'guarma', kv[0][1])):
    name = col_name(gtype, gid, group_name.get((gtype, gid), ''))
    col = bpy.data.collections.new(name)
    parent.children.link(col)
    for ob in lst:
        col.objects.link(ob)
        try:
            parent.objects.unlink(ob)
        except Exception:
            pass
    made[name] = len(lst)

if unmatched:
    col = bpy.data.collections.new('X_未匹配_%d' % len(unmatched))
    parent.children.link(col)
    for ob, why in unmatched:
        col.objects.link(ob)
        try:
            parent.objects.unlink(ob)
        except Exception:
            pass
    made[col.name] = len(unmatched)
    print('[group] ⚠ 未匹配 %d 个（前 30）：' % len(unmatched))
    for ob, why in unmatched[:30]:
        print('    %-55s %s' % (ob.name, why))

# ---------------------------------------------------------------- 打印 + 存盘
print('[group] 父集合直属剩余 %d 个 · 子集合 %d 个' % (len(parent.objects), len(made)))
for name, n in sorted(made.items(), key=lambda kv: (-kv[1], kv[0])):
    print('    %-40s %4d' % (name, n))

try:
    bpy.context.preferences.filepaths.save_version = 0
except Exception:
    pass
out = a.out or bpy.data.filepath
bpy.ops.wm.save_as_mainfile(filepath=out)
print('[group] SAVED %s %.2f GB' % (out, os.path.getsize(out) / 1e9))
print('[group] VERDICT → %s' % ('PASS' if not unmatched else 'CHECK（未匹配 %d 个）' % len(unmatched)))
