# -*- coding: utf-8 -*-
r"""把「跨据点」的合并 LOD 按据点 P 矩形切开（远景碎片 → 城镇 prefab 的第 2 步）。

背景：远景碎片里有一批**合并块**（`*_area_slod*`、`*_combo*_slod`）天生跨多个据点。
2026-11-04 实测 `new_area_slod4`（1,288 × 1,108 m）同时盖住：
  sdn 36.5% / sis 10.4%（西西卡监狱 51% 的 P）/ lak 7.5%（拉凯 100% 的 P）
整块算给圣丹尼斯 = 圣丹尼斯的 prefab 里混进监狱岛。所以按**据点能走范围 P 矩形**切开，
每个据点拿自己那块；剩下的（水域/野外）给野地场景。

    blender -b "...\continent_lod_split_v23.blend" -P tools\_unbuffer.py -P tools\split_span_blocks.py -- \
        --csv "...\deliverable\manifests\lod_fragments.csv" \
        --spec "...\_scratch\settlement_plan\scene_specs.json" \
        --out-parts "...\deliverable\manifests\lod_split_parts.json"

输入约定：
  · CSV 里 `assign_via == 'span'` 的行 = 待拆的整块；`spans` 列 = `sdn:36.5%;sis:10.4%;...`
  · 拆分件是**新对象**（同一 hash、同一世界变换），名字 `<父名>__split_<据点code>` / `__split_rest`
  · 每个拆分件带自定义属性 `part_key = "<hash>|<group_id>"`，`split_of = "<父hash>"`

产物：
  1. blend 里：原整块删除，换成若干拆分件（挂在父集合 `ONLY_lod_远景碎片` 下，
     随后跑 `group_lod_blend.py` 归位到各据点集合）
  2. `lod_split_parts.json`：拆分件的实测几何（tris/verts/bb/贴图），
     给 `build_lod_groups.py --parts` 合并进分组表

🔴 切的是**网格顶点**（bmesh bisect），不是只改归属；切线处会新增顶点/三角面。
"""

import argparse
import csv
import datetime
import json
import os
import sys

import bpy
import bmesh
from mathutils import Vector

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--csv', required=True)
ap.add_argument('--spec', required=True)
ap.add_argument('--out-parts', required=True)
ap.add_argument('--parent', default='ONLY_lod_远景碎片')
a = ap.parse_args(ARGS)


def key_of(h, x, y, z):
    return (int(h, 16) if isinstance(h, str) else int(h),
            round(float(x), 1), round(float(y), 1), round(float(z), 1))


def load_spec_rects(path):
    with open(path, encoding='utf-8') as fp:
        spec = json.load(fp)
    out = {}
    for s in spec['settlements']:
        xs = [p[0] for p in s['P'][0]]
        ys = [p[1] for p in s['P'][0]]
        out[s['code']] = (min(xs), min(ys), max(xs), max(ys))
    return out


def clip_mesh(ob, rect, keep_inside):
    """按世界坐标矩形裁网格。keep_inside=True 保留矩形内，False 切掉矩形内。"""
    mw = ob.matrix_world
    mwi = mw.inverted()
    nmat = mwi.to_3x3().transposed()
    flip = -1.0 if mw.determinant() < 0 else 1.0
    planes = [((rect[0], 0, 0), (1, 0, 0)), ((rect[2], 0, 0), (-1, 0, 0)),
              ((0, rect[1], 0), (0, 1, 0)), ((0, rect[3], 0), (0, -1, 0))]
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    for pco, pno in planes:
        co = mwi @ Vector(pco)
        no = (nmat @ Vector(pno)).normalized() * flip
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        # 实测（blender 5.2，立方体 x∈[-1,1] + plane_no=+x）：clear_outer 去掉**法线正侧**，
        # clear_inner 去掉法线负侧。这里的法线指向矩形内部 ⇒ 保留内部 = clear_inner。
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-4, plane_co=co, plane_no=no,
                               clear_outer=(not keep_inside), clear_inner=keep_inside)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return len(ob.data.vertices) > 0


def measure(ob):
    me = ob.data
    mw = ob.matrix_world
    mn = [1e18, 1e18, 1e18]
    mx = [-1e18, -1e18, -1e18]
    for v in me.vertices:
        p = mw @ v.co
        for i in range(3):
            if p[i] < mn[i]:
                mn[i] = p[i]
            if p[i] > mx[i]:
                mx[i] = p[i]
    tris = sum(max(0, len(p.vertices) - 2) for p in me.polygons)
    return mn + mx, tris, len(me.vertices), len(me.materials)


def copy_object(src, name):
    ob = src.copy()
    ob.data = src.data.copy()
    ob.name = name
    ob.data.name = name
    parent.objects.link(ob)          # 先挂父集合，拆分件随后由 group_lod_blend 归位
    return ob


# ---------------------------------------------------------------- 读 span 行
rows = []
with open(a.csv, encoding='utf-8-sig', newline='') as fp:
    for r in csv.DictReader(fp):
        if r.get('assign_via') != 'span':
            continue
        rows.append(r)
print('[split] 待拆整块 %d 个' % len(rows))
rects = load_spec_rects(a.spec)

parent = bpy.data.collections.get(a.parent)
if parent is None:
    raise SystemExit('[split] 找不到父集合 %s' % a.parent)

# 对象索引：hash + location
index = {}
for ob in bpy.data.objects:
    h = ob.get('hash')
    if not h:
        continue
    index[key_of(h, ob.location.x, ob.location.y, ob.location.z)] = ob

doc = {'source_blend': bpy.data.filepath,
       'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
       'parents': []}
# 增量：已有部件表里的父块保留（之前切过的整块，其原对象已不在 blend 里，不能再切一次）
if os.path.exists(a.out_parts):
    try:
        old = json.load(open(a.out_parts, encoding='utf-8'))
        doc['parents'] = old.get('parents', [])
        print('[split] 已有部件表：%d 个父块（保留）' % len(doc['parents']))
    except Exception as e:
        print('[split] 旧部件表读不了，忽略：%s' % e)

for r in rows:
    k = key_of(r['hash'], r['wx'], r['wy'], r['wz'])
    ob = index.get(k)
    if ob is None:
        print('[split] ⚠ 找不到对象 %s %s' % (r['name'], k))
        continue
    spans = []
    for tok in (r.get('spans') or '').split(';'):
        tok = tok.strip()
        if not tok:
            continue
        code, pct = tok.split(':')
        spans.append((code, pct))
    strong = [(c, p) for c, p in spans if c in rects]
    print('[split] %s：%d 个据点份 + 余量（%s）' % (r['name'], len(strong),
                                                ', '.join('%s %s' % x for x in strong)))
    parts = []
    made = []

    def emit(src_ob, name, part_key, group_type, group_id):
        bb, tris, verts, mats = measure(src_ob)
        if tris <= 0 or verts <= 0:
            bpy.data.objects.remove(src_ob, do_unlink=True)
            return None
        src_ob['part_key'] = part_key
        src_ob['split_of'] = r['hash']
        if src_ob.name not in parent.objects:
            parent.objects.link(src_ob)
        parts.append({
            'part_key': part_key, 'group_type': group_type, 'group_id': group_id,
            'name': name, 'tris': tris, 'verts': verts,
            'subs': int(r.get('submeshes') or 1),
            'bb': [round(v, 3) for v in bb],
            'tex_a': r.get('tex_albedo', ''), 'tex_n': r.get('tex_normal', ''),
            'tex_m': r.get('tex_ma', ''),
        })
        made.append(src_ob)
        return src_ob

    for code, pct in strong:
        part = copy_object(ob, '%s__split_%s' % (r['name'], code))
        ok = clip_mesh(part, rects[code], keep_inside=True)
        bb = measure(part)[0]
        inside = (bb[0] >= rects[code][0] - 1 and bb[2] <= rects[code][2] + 1 and
                  bb[1] >= rects[code][1] - 1 and bb[3] <= rects[code][3] + 1)
        if not ok:
            bpy.data.objects.remove(part, do_unlink=True)
            print('[split]   %s：裁完是空的，跳过' % code)
            continue
        if not inside:
            print('[split]   ⚠ %s 裁完 bbox 超出矩形：%s vs %s —— 检查 clear 方向'
                  % (code, [round(v) for v in (bb[0], bb[1], bb[2], bb[3])],
                     [round(v) for v in rects[code]]))
        emit(part, part.name, '%s|%s' % (r['hash'], code), 'settlement', code)

    # 余量：切掉所有据点矩形
    rest = copy_object(ob, '%s__split_rest' % r['name'])
    rest_kept = True
    for code, pct in strong:
        if len(rest.data.vertices) == 0:
            break
        clip_mesh(rest, rects[code], keep_inside=False)
    if len(rest.data.vertices) > 0:
        wid = r.get('wild_scene') or ''
        if emit(rest, rest.name, '%s|rest' % r['hash'],
                'wild' if wid else 'none', wid or 'none') is None:
            rest_kept = False
    else:
        bpy.data.objects.remove(rest, do_unlink=True)
        rest_kept = False
        print('[split]   余量为空（整块被据点盖满）')

    # 删原块（只有真的切出东西才删；切空了保留原块，避免丢数据）
    if not parts:
        print('[split]   ⚠ 一个部件都没切出来，保留原块')
        if rest_kept:
            bpy.data.objects.remove(rest, do_unlink=True)
        continue
    bpy.data.objects.remove(ob, do_unlink=True)
    doc['parents'] = [p for p in doc['parents']
                      if not (p['hash'] == r['hash'] and p['name'] == r['name'])]
    doc['parents'].append({'hash': r['hash'], 'name': r['name'], 'parts': parts})
    print('[split]   → %d 个拆分件' % len(parts))

os.makedirs(os.path.dirname(a.out_parts), exist_ok=True)
with open(a.out_parts, 'w', encoding='utf-8') as fp:
    json.dump(doc, fp, ensure_ascii=False, indent=1)
print('[split] 部件表 -> %s（%d 个父块）' % (a.out_parts, len(doc['parents'])))

try:
    bpy.context.preferences.filepaths.save_version = 0
except Exception:
    pass
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print('[split] SAVED %s %.2f GB'
      % (bpy.data.filepath, os.path.getsize(bpy.data.filepath) / 1e9))
print('[split] VERDICT → %s' % ('PASS' if all(p['parts'] for p in doc['parents']) else 'CHECK'))
