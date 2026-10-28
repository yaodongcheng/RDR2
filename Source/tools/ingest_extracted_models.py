# -*- coding: utf-8 -*-
"""把 `raw/_missing/` 里抽出来的 .ydr/.yft **增量**入库到 assets/lib_native。

前提：`tools/extract_missing_from_game.py` 已经把游戏包里命中的模型抽到 `raw/_missing`。

做的事（与 `add_rail_to_lib.py` 同一套转换，不另起管线）：
  1. 备份 `index.json` → `index_before_ingest_<时间>.json`（**只在不存在时备份**，绝不覆盖旧备份）；
  2. 预填已有贴图表（避免重复写盘/编号错乱）；
  3. 每个文件：`dump_model_lib.load_any` → `write_model`（写 `<hh>/<hash>.mdl` + 贴图）；
  4. 合并进 index.json（已存在的 hash 直接跳过），每 200 个存一次盘（断电/被杀不至于全丢）。

用法：
    uv run python tools/ingest_extracted_models.py --dry            # 只统计能入库多少
    uv run python tools/ingest_extracted_models.py                  # 正式入库
    uv run python tools/ingest_extracted_models.py --dir raw/_missing --maxs 512
    uv run python tools/ingest_extracted_models.py --limit 200      # 先小批验证

入库完成后重建才能生效：
    blender -b --python tools/_unbuffer.py -P tools/blender_continent.py -- \
        --out .../continent_v7.blend --lib <abs>/assets/lib_native --rails --full
"""
import os
import sys
import json
import time
import glob
import shutil
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))

LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')
REPORT = os.path.join(ROOT, 'work/ingest_report.json')
DEFAULT_DIR = os.path.join(ROOT, 'raw/_missing')


def name_hash(fname):
  base = os.path.splitext(os.path.basename(fname))[0]
  if base.lower().startswith('0x'):
    try:
      return int(base[2:], 16)
    except Exception:
      return None
  h = 0
  for c in base.lower().encode():
    h = (h + c) & 0xFFFFFFFF
    h = (h + (h << 10)) & 0xFFFFFFFF
    h ^= h >> 6
  h = (h + (h << 3)) & 0xFFFFFFFF
  h ^= h >> 11
  return (h + (h << 15)) & 0xFFFFFFFF


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument('--dir', default=DEFAULT_DIR)
  ap.add_argument('--maxs', type=int, default=512)
  ap.add_argument('--limit', type=int, default=0)
  ap.add_argument('--dry', action='store_true')
  ap.add_argument('--save-every', type=int, default=200)
  a = ap.parse_args()

  import dump_model_lib as D     # 延后导入：它要 numpy/PIL

  files = [f for f in glob.glob(os.path.join(a.dir, '**', '*'), recursive=True)
           if os.path.isfile(f) and f.lower().endswith(('.ydr', '.yft'))]
  print('[ing] %s 下模型文件 %d 个' % (a.dir, len(files)))

  idx = json.load(open(INDEX, encoding='utf-8'))
  models = idx['models']
  tex_meta = idx.get('tex', [])
  before_models, before_tex = len(models), len(tex_meta)
  print('[ing] 现有模型 %d，贴图 %d' % (before_models, before_tex))

  todo, seen = [], {}
  for f in files:
    h = name_hash(f)
    if h is None:
      continue
    hx = '0x%08x' % h
    if hx in models:
      continue
    if hx in seen:          # 同名 hash 只入库一次
      continue
    seen[hx] = f
    todo.append((hx, f))
  print('[ing] 待入库 %d（已在库/重复 %d）' % (len(todo), len(files) - len(todo)))

  if a.dry or not todo:
    for hx, f in todo[:8]:
      print('    ', hx, os.path.basename(f))
    print('[ing] dry-run，不改库')
    return

  bak = os.path.join(LIB, 'index_before_ingest_%s.json' % time.strftime('%Y%m%d_%H%M'))
  if not os.path.exists(bak):
    shutil.copy2(INDEX, bak)
    print('[ing] 已备份 %s' % os.path.basename(bak))

  tex = D.Tex(LIB, a.maxs)
  for t in tex_meta:
    tex.by_name[t['n'].lower()] = t['id']
    tex.meta.append(t)
  print('[ing] 贴图预填 %d 条' % len(tex.meta))

  t0 = time.time()
  done = skipped = 0
  bad = []
  items = todo[:a.limit] if a.limit else todo
  for i, (hx, f) in enumerate(items, 1):
    try:
      M = D.load_any(f)
    except Exception as e:
      bad.append((os.path.basename(f), 'load: %s' % e))
      skipped += 1
      continue
    if not M:
      bad.append((os.path.basename(f), 'load 返回 None（无几何/格式不支持）'))
      skipped += 1
      continue
    try:
      e = D.write_model(M, int(hx, 16), LIB, tex)
    except Exception as ex:
      bad.append((os.path.basename(f), 'write: %s' % ex))
      skipped += 1
      continue
    if not e:
      bad.append((os.path.basename(f), 'write_model 返回 None（几何为空）'))
      skipped += 1
      continue
    models[hx] = {k: e[k] for k in ('f', 'b', 's')}
    done += 1
    if done % a.save_every == 0:
      json.dump(dict(models=models, tex=tex.meta), open(INDEX, 'w', encoding='utf-8'),
                separators=(',', ':'))
      el = time.time() - t0
      rate = done / max(1e-9, el) * 60
      print('  %5d/%d  入库 %d  贴图 %d  %.0f 个/分  剩 ~%.0f 分'
            % (i, len(items), done, len(tex.meta), rate,
               (len(items) - i) / max(1e-9, rate) / 60))

  json.dump(dict(models=models, tex=tex.meta), open(INDEX, 'w', encoding='utf-8'),
            separators=(',', ':'))
  el = (time.time() - t0) / 60
  print('[ing] 完成：入库 %d，跳过 %d，用时 %.1f 分' % (done, skipped, el))
  print('[ing] 模型 %d → %d（+%d），贴图 %d → %d（+%d）'
        % (before_models, len(models), len(models) - before_models,
           before_tex, len(tex.meta), len(tex.meta) - before_tex))
  os.makedirs(os.path.dirname(REPORT), exist_ok=True)
  json.dump({'dir': a.dir, 'files': len(files), 'todo': len(todo), 'ingested': done,
             'skipped': skipped, 'models_before': before_models,
             'models_after': len(models), 'tex_before': before_tex,
             'tex_after': len(tex.meta), 'minutes': round(el, 1),
             'failed': bad[:200]},
            open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
  print('[ing] 报告 %s' % REPORT)


if __name__ == '__main__':
  main()
