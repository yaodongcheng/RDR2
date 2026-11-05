# -*- coding: utf-8 -*-
r"""从大陆 blend 里**只留下指定分类**（按名字重新判定，不看 blend 里的旧集合），另存一个新 blend。

    blender -b "D:\...\continent_v23.blend" -P tools\_unbuffer.py -P tools\extract_class_blend.py -- \
        --keep lod,terrain_lod --out "...\deliverable\blender\continent\continent_lod_split_v23.blend"

为什么按名字判定：v23 是**旧规则**建出来的，里面的集合把「地形远景块」混在 `lod` 里；
按当前 `class_rules.classify_name()` 重新分类，才能立刻看到拆分效果（不用重跑大陆）。

产物（2026-11-01 建、2026-11-03 归位）：
`deliverable/blender/continent/continent_lod_split_v23.blend`
= `ONLY_lod_远景碎片` 2,261 + `ONLY_terrain_lod_地形远景块` 31，全可见，世界坐标。

坑（都在实现里规避了）：
  1. 🔴 不要逐个删对象（18 万个会跑几小时）→ 删集合 + orphans_purge 批量清；
  2. 🔴 先建好挂在场景上的空集合、把要留的对象装进去，**再**删其它集合；
     否则整条链没人引用，purge 会把目标对象也一起清掉（实测 2290 个全没了）；
  3. 🔴 保存前安全闸：留下的对象少于目标一半就 ABORT，不写空文件；
  4. 🔴 贴图是**相对路径**，另存到别的目录会全部失效（实测搬到 continent/ 后 761 张全找不到）
     → 保存前按「源文件的绝对路径 → 相对 out 目录」重算一遍（见第 5 步）。
"""
import argparse
import os
import sys

import bpy

TOOLS = os.path.dirname(os.path.abspath(__file__))
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--keep', action='append', default=[],
                help='类 key，可重复给（--keep lod --keep terrain_lod）；也接受逗号/加号分隔')
ap.add_argument('--out', required=True)
a = ap.parse_args(ARGS)
import re as _re
keys = []
for v in a.keep:
    keys += [k.strip() for k in _re.split(r'[,+]', v) if k.strip()]
if not keys:
    keys = ['lod', 'terrain_lod']
print('[cls_blend] 保留类：%s' % keys)

sys.path.insert(0, TOOLS)
from class_rules import classify_name, apply_hard_rules, ALL_CLASSES  # noqa: E402

# 2026-11-05：v23 里有一批对象名是 `e_<hash>`（构建期 names.txt 缺父名）。
# 它们其实是 `val_02_slod` / `bla_blk01_slod` 这类**街区 LOD**，模型在库、实例在场景，
# 只是名字丢了 ⇒ 按 `e_xxx` 判不成 lod ⇒ 抽不进远景包。这里按 hash 反查补充名再判定。
_NAMES = {}
try:
    from name_source import load_names as _load_names
    _NAMES = _load_names()
except Exception:
    pass
_E_NAME = _re.compile(r'^e_([0-9a-f]{8})$', _re.I)


def resolve_name(n):
    m = _E_NAME.match(n or '')
    if not m:
        return n
    return _NAMES.get(int(m.group(1), 16), n)


ZH = dict(ALL_CLASSES)
print('[cls_blend] 文件：%s' % bpy.data.filepath)
print('[cls_blend] 原始：对象 %d / 集合 %d' % (len(bpy.data.objects), len(bpy.data.collections)))

# ---- 1. 按名字重新分类，挑出目标
groups = {k: [] for k in keys}
for ob in bpy.data.objects:
    try:
        nm = resolve_name(ob.name)
        k = apply_hard_rules(classify_name(nm), nm)
    except Exception:
        continue
    if k in groups:
        groups[k].append(ob)
for k in keys:
    print('[cls_blend] %-12s %d 个' % (k, len(groups[k])))
n_target = sum(len(v) for v in groups.values())
if n_target == 0:
    print('[cls_blend] 一个都没选中，退出')
    raise SystemExit(1)

# ---- 2. 先建挂在场景上的集合，把目标对象装进去
sc = bpy.context.scene.collection
outs = {}
for k in keys:
    name = 'ONLY_%s_%s' % (k, ZH.get(k, k))
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if col.name not in [x.name for x in sc.children]:
        sc.children.link(col)
    outs[k] = col
    for ob in groups[k]:
        try:
            col.objects.link(ob)
        except Exception:
            pass
    print('[cls_blend] %s → %d 个对象' % (col.name, len(col.objects)))

# ---- 3. 删掉其它集合 → 对象失去引用 → purge 批量清
n_col = len(bpy.data.collections)
keep_cols = {c.name for c in outs.values()}
for c in list(bpy.data.collections):
    if c.name not in keep_cols:
        bpy.data.collections.remove(c)
print('[cls_blend] 删集合 %d 个，剩 %d' % (n_col - len(bpy.data.collections), len(bpy.data.collections)))

for i in range(8):
    before = (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.materials), len(bpy.data.images))
    removed = bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    after = (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.materials), len(bpy.data.images))
    print('[cls_blend] purge #%d 去掉 %s → 对象%d 网格%d 材质%d 图像%d' % (i + 1, removed, *after))
    if removed == 0 or after == before or after[0] < n_target:
        break

print('[cls_blend] 最终：对象%d 网格%d 材质%d 图像%d'
      % (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.materials), len(bpy.data.images)))
if len(bpy.data.objects) < 0.5 * n_target:
    print('[cls_blend] ABORT：目标 %d 个，现在只剩 %d 个 —— 不保存' % (n_target, len(bpy.data.objects)))
    raise SystemExit(2)

# ---- 4. 全部可见
for c in outs.values():
    c.hide_viewport = False
    c.hide_render = False

def unhide_lc(lc):
    lc.exclude = False
    lc.hide_viewport = False
    for ch in lc.children:
        unhide_lc(ch)

for lc in bpy.context.view_layer.layer_collection.children:
    lc.exclude = False
    lc.hide_viewport = False
    unhide_lc(lc)
bpy.context.view_layer.update()

# ---- 5. 贴图相对路径重算（相对新的 out 目录；不重算 = 搬到别的目录后全部失效）
out_dir = os.path.dirname(os.path.abspath(a.out))
n_img = 0
for img in bpy.data.images:
    if img.source != 'FILE' or not img.filepath:
        continue
    abs_path = bpy.path.abspath(img.filepath)
    if not os.path.exists(abs_path):
        print('[cls_blend] ⚠ 贴图不存在，跳过：%s' % abs_path)
        continue
    img.filepath = '//' + os.path.relpath(abs_path, out_dir).replace('\\', '/')
    n_img += 1
print('[cls_blend] 贴图相对路径重算 %d 张（相对 %s）' % (n_img, out_dir))

os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
try:
    bpy.context.preferences.filepaths.save_version = 0
except Exception:
    pass
bpy.ops.wm.save_as_mainfile(filepath=a.out, compress=False)
print('[cls_blend] SAVED %s %.2f GB' % (a.out, os.path.getsize(a.out) / 1e9))
