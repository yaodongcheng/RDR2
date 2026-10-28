# -*- coding: utf-8 -*-
"""不开 Blender 也能核对构建结果 —— 读 manifest，出 AGENTS.md §3 要求的那一行数字。

    ENTITIES <n> / 12 类 <k>/12 / 植被 <n> / 缺模型 <n>/<总实体> / 贴图 <n> → PASS|FAIL

用法：
    uv run python tools/report_manifest.py                      # 默认读 continent 目录的 manifest.json
    uv run python tools/report_manifest.py --manifest <path>
    uv run python tools/report_manifest.py --find new_gar06_park_terrain   # 按贴图名/对象名/hash 查
    uv run python tools/report_manifest.py --class rail --limit 10
    uv run python tools/report_manifest.py --tile wild2000_04_02
"""
import os
import sys
import json
import glob
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
DEF_MANIFEST = os.path.join(ROOT, 'deliverable/blender/continent/manifest.json')
LIB = os.path.join(ROOT, 'assets/lib_native/index.json')
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
CLASSES = ('rail', 'struct', 'decal', 'veg', 'rock', 'veh', 'bldg', 'part',
           'junk', 'prop', 'int', 'unknown')


def missing_models():
  """缺模型实体数：实体表 hash 集合 - 模型库 hash 集合（与构建时的判断同一口径）。"""
  lib = json.load(open(LIB, encoding='utf-8'))
  have = lib['models']
  ent = set()
  for p in glob.glob(os.path.join(TILES, '*.json')):
    if p.endswith('.bak'):
      continue
    for e in json.load(open(p, encoding='utf-8')):
      ent.add('0x%08x' % e[0])
  miss = sum(1 for h in ent if h not in have)
  return miss, len(ent), len(lib.get('tex', []))


def iter_objects(path):
  with open(path, encoding='utf-8') as f:
    for line in f:
      line = line.strip()
      if not line:
        continue
      try:
        rec = json.loads(line)
      except Exception:
        continue
      if '_meta' in rec:
        continue
      yield rec


def show(rec):
  t = ','.join(rec.get('t', []))
  print('  %-46s %-16s %-9s %s%s%s'
        % (rec.get('n', '')[:46], rec.get('h', ''), rec.get('c', ''),
           '' if rec.get('hid') else '显示 ', t,
           ' [无albedo]' if rec.get('nt') else ''))


def main(argv=None):
  ap = argparse.ArgumentParser()
  ap.add_argument('--manifest', default=DEF_MANIFEST)
  ap.add_argument('--find', default='')
  ap.add_argument('--class', dest='cls', default='')
  ap.add_argument('--tile', default='')
  ap.add_argument('--limit', type=int, default=20)
  a = ap.parse_args(argv)

  if not os.path.exists(a.manifest):
    raise SystemExit('找不到 %s（先跑构建，或 --manifest 指到别处）' % a.manifest)
  s = json.load(open(a.manifest, encoding='utf-8'))
  jl = os.path.join(os.path.dirname(os.path.abspath(a.manifest)), s.get('objects_file', ''))

  miss, ent_total, tex_total = missing_models()
  cls = s.get('classes', {})
  k = s.get('classes_n', len(cls))
  veg_miss = s.get('veg_should_delete', s.get('veg_left', 0))
  ok = (s.get('entities', 0) > 0 and k >= 10 and veg_miss == 0)
  print('ENTITIES %d / 12 类 %d/12 / 植被类 %d（应删未删 %d）/ 缺模型 %d/%d (%.1f%%) / 贴图 %d → %s'
        % (s.get('entities', 0), k, s.get('veg_left', 0), veg_miss, miss, ent_total,
           100.0 * miss / max(1, ent_total), tex_total, 'PASS' if ok else 'FAIL'))

  print('\n以下全部来自清单，不需要打开 blend：')
  print('  blend        %s（%.2f GB，%s）' % (s.get('blend', ''), s.get('blend_size_gb', 0),
                                            s.get('built', '')))
  print('  对象         %d（ENTITIES %d，隐藏 %d，其中地形 patch %d）'
        % (s.get('objects', 0), s.get('entities', 0), s.get('hidden', 0),
           s.get('hidden_terrain', 0)))
  print('  材质/贴图    材质 %d，实际用到的贴图 %d 张'
        % (s.get('materials') or 0, s.get('textures_used') or 0))
  print('  无 albedo    %d 个对象（ntex_* 兜底纯色，贴图核对要单独看）' % s.get('no_albedo_objects', 0))
  bb = s.get('world_bbox')
  if bb and bb[0] < 1e17:
    print('  世界包围盒   x %.0f~%.0f  y %.0f~%.0f  z %.1f~%.1f'
          % (bb[0], bb[3], bb[1], bb[4], bb[2], bb[5]))
  print('  分类         %s' % ', '.join('%s:%d' % (c, cls[c]) for c in CLASSES if c in cls))
  print('  缺失分类     %s' % (', '.join(c for c in CLASSES if c not in cls) or '（无）'))
  print('  植被         veg 类 %d（仍在 ENTITIES 可见）/ 已隐藏 %d（HIDDEN_VEG，可切回）/ 未处理 %d'
        % (s.get('veg_left', 0), s.get('veg_hidden', 0), veg_miss))

  if a.find or a.cls or a.tile:
    if not os.path.exists(jl):
      raise SystemExit('找不到对象清单 %s' % jl)
    pat = a.find.lower()
    n = 0
    print('\n查询 %s' % ' '.join(x for x in (['find=' + a.find] if a.find else [])
                                  + (['class=' + a.cls] if a.cls else [])
                                  + (['tile=' + a.tile] if a.tile else [])))
    for rec in iter_objects(jl):
      if a.cls and rec.get('c') != a.cls:
        continue
      if a.tile and rec.get('tid') != a.tile:
        continue
      if pat:
        blob = (rec.get('n', '') + ' ' + rec.get('h', '') + ' '
                + ' '.join(rec.get('t', []))).lower()
        if pat not in blob:
          continue
      show(rec)
      n += 1
      if n >= a.limit:
        print('  ...（%d 条上限，用 --limit 调大）' % a.limit)
        break
    if n == 0:
      print('  （无命中）')
  return 0


if __name__ == '__main__':
  sys.exit(main())
