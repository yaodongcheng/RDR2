# -*- coding: utf-8 -*-
"""把各区域预览里已经解析好的贴图 PNG 收进统一贴图池（按名字）。

## 为什么

`tools/export_sdn_gltf.py` 那条按名字解析的导出管线，已经在
`export/previews/<区域>/textures/` 里留下了 **7,911 张按贴图名命名的 PNG**（2,917 个唯一名字）。
它们的名字就是 albedo 名，正是 continent 管线缺的那批。

本脚本做两件事：
  1. 搬运：`export/previews/*/textures/<name>.png` → `work/lib_gtxd/txd_prev/<name>.png`（留档）
  2. **登记进 index**（`--index`）：把 PNG 复制成 `assets/lib_native/tex/<id>.png` 并追加到
     `index.json` 的 tex 表 —— 这样 `rebind_textures.py` 按名字就能直接命中，不需要再解 ytd。

    uv run python tools/harvest_preview_textures.py --index [--dry]
"""
import os
import sys
import glob
import json
import shutil
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
SRC = os.path.join(ROOT, 'export/previews')
DST = os.path.join(ROOT, 'work/lib_gtxd/txd_prev')
LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument('--dry', action='store_true')
  ap.add_argument('--index', action='store_true',
                  help='同时把 PNG 登记进 assets/lib_native/index.json 的 tex 表')
  a = ap.parse_args()

  os.makedirs(DST, exist_ok=True)
  have = set(f.lower() for f in os.listdir(DST))
  files = glob.glob(os.path.join(SRC, '*', 'textures', '*.png'))
  print('[harv] 预览贴图 %d 个（唯一名 %d），池内已有 %d'
        % (len(files), len(set(os.path.basename(f).lower() for f in files)), len(have)))
  moved = 0
  for f in files:
    base = os.path.basename(f)
    k = base.lower()
    if k in have:
      continue
    if a.dry:
      moved += 1
      continue
    shutil.copy2(f, os.path.join(DST, base))
    have.add(k)
    moved += 1
  print('[harv] %s %d 张 → %s（池内现在 %d 张）'
        % ('将收录' if a.dry else '收录', moved, DST, len(have)))

  if not a.index or a.dry:
    return

  d = json.load(open(INDEX, encoding='utf-8'))
  tex = d['tex']
  by_name = {t['n'].lower(): t['id'] for t in tex}
  added = 0
  for base in sorted(os.listdir(DST)):
    name = os.path.splitext(base)[0]
    if name.lower() in by_name:
      continue
    tid = len(tex)
    fn = '%04d.png' % tid
    shutil.copy2(os.path.join(DST, base), os.path.join(LIB, 'tex', fn))
    tex.append({'id': tid, 'n': name, 'f': 'tex/' + fn})
    by_name[name.lower()] = tid
    added += 1
  if added:
    json.dump(d, open(INDEX, 'w', encoding='utf-8'), separators=(',', ':'))
  print('[harv] 登记进 index.tex：+%d（贴图总数 %d）' % (added, len(tex)))


if __name__ == '__main__':
  main()
