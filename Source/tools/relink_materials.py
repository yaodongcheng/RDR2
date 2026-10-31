# -*- coding: utf-8 -*-
"""按当前 `index.json` 重新给已有 blend 的网格挂材质（漫反射 + 法线 + 高光/ORM）。

## 为什么需要

blend 里的材质是**建库那一刻**的快照：
- 2026-10-29 之前按 `tid` 建（`m_<tid>`），贴图池一扩就串号；
- 2026-10-29 改成 `alb_<名字>`，但**只有 albedo**；
- 2026-10-30 起 `index.json` 的 `models[h].st` 记录了每个槽位的法线/高光 id，
  已存盘的 blend 不会自动跟着变 —— 要么重建，要么用本脚本重挂。

本脚本用对象自带的 `ob['hash']` 查当前 `s` + `st`，把每个网格的材质槽重挂一遍
（只改材质引用，不碰网格/变换/隐藏状态），缺的材质按需创建。

    blender -b <blend> --python tools/_unbuffer.py -P tools/relink_materials.py [-- --dry]

判定：末尾打印「换材质槽 N 个」；`换 0 个` 说明当前 blend 已经是最新的。
"""
import bpy
import os
import sys
import json
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')
if os.path.join(ROOT, 'tools') not in sys.path:
  sys.path.insert(0, os.path.join(ROOT, 'tools'))

import mat_rdr2  # noqa: E402


def argv():
  a = sys.argv
  return a[a.index('--') + 1:] if '--' in a else []


def load_index():
  d = json.load(open(INDEX, encoding='utf-8'))
  tex = d['tex']
  n = 0
  for t in tex:
    try:
      n = max(n, int(t['id']))
    except Exception:
      pass
  table = [None] * (n + 1)
  for t in tex:
    try:
      table[int(t['id'])] = t
    except Exception:
      pass
  return d['models'], table


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument('--dry', action='store_true')
  ap.add_argument('--limit', type=int, default=0)
  a = ap.parse_args(argv())

  models, tex = load_index()
  print('[relink] 库内模型 %d，贴图 %d' % (len(models), len(tex)))

  cache = {}
  done = 0
  changed = 0
  mism = 0
  miss_hash = 0
  miss_model = 0
  st_models = 0
  for ob in bpy.data.objects:
    if ob.type != 'MESH':
      continue
    hx = ob.get('hash')
    if not hx:
      miss_hash += 1
      continue
    e = models.get(hx)
    if not e:
      miss_model += 1
      continue
    s = e.get('s') or []
    st = e.get('st') or []
    if st:
      st_models += 1
    me = ob.data
    # 目标槽：**一个子网格一个槽，槽序 == 子网格序**（2026-10-29 起构建不再做槽去重）。
    # 老 blend（去重版）的槽数会 ≠ 子网格数 → 走 `mism` 分支跳过，不硬挂（避免又串号）。
    targets = []
    for i, (tid, _vc, _ic) in enumerate(s):
      pair = st[i] if 0 <= i < len(st) else None
      ntid = pair[0] if pair else -1
      mtid = pair[1] if pair else -1
      targets.append(mat_rdr2.get_or_make(tid, ntid, mtid, tex, LIB, cache))
    if a.dry:
      done += 1
      continue
    cur = list(me.materials)
    if len(cur) != len(targets):
      mism += 1
      continue
    for i, m in enumerate(targets):
      if m is None:          # 库无此模型 → 保留原有材质，不清空
        continue
      if cur[i] is not m:
        me.materials[i] = m
        changed += 1
    done += 1
    if a.limit and done >= a.limit:
      break

  print('[relink] 处理网格 %d（其中 %d 个模型带 st），换材质槽 %d 个；长度不匹配跳过 %d，'
        '无 hash %d，库无此模型 %d；新建材质 %d 种'
        % (done, st_models, changed, mism, miss_hash, miss_model, len(cache)))
  if a.dry:
    print('[relink] dry-run，不存盘')
    return
  out = bpy.data.filepath
  bpy.ops.wm.save_as_mainfile(filepath=out)
  print('[relink] saved %s (%.2f GB)' % (out, os.path.getsize(out) / 1e9))


if __name__ == '__main__':
  main()
