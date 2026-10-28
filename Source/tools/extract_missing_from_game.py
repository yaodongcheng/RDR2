# -*- coding: utf-8 -*-
"""从游戏 RPF 包里把「场景里有、模型库里没有」的 .ydr/.yft 抽出来。

## 为什么

实体表 102,051 个唯一 hash，模型库只有 54,925 → 缺 55,658（54.5%）。这些实体的
网格就在游戏包里，用 hashed 文件名（`0xXXXXXXXX.ydr`）躺着，只是没入库。

## 做法

对每个顶层包（levels_0..7）：
  1. `list <pack>` 拿到条目；`.ydr/.yft` 直接命中就抽；`.rpf` 进待处理队列；
  2. 嵌套包先整包抽到临时目录 → `list` → 若里面有命中，就把**整个嵌套包**抽出来、
     本地只留命中文件、删掉其余（逐个文件抽要 5 万次 dotnet 调用，太慢）；
  3. 命中的 .ydr/.yft 进 `raw/_missing/`；命中 hash 追加到
     `export/world/rpf_found_missing.tsv`；已处理包记进状态文件，可断点续跑。

## 用法（**必须能读 H: 游戏目录**，即 danger-full-access）

    uv run python tools/extract_missing_from_game.py --packs levels_0          # 先小包试
    uv run python tools/extract_missing_from_game.py                          # 默认 levels_0..7
    uv run python tools/extract_missing_from_game.py --packs levels_1,levels_2 --depth 2
"""
import os
import sys
import json
import glob
import time
import shutil
import argparse
import subprocess

ROOT = r'D:/BrainMaker/大镖客2解包分析'
GAME = r'H:/EPICGAMES/RedDeadRedemption2'
DOTNET = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.dll')
LIB = os.path.join(ROOT, 'assets/lib_native/index.json')
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
OUT_DIR = os.path.join(ROOT, 'raw/_missing')
TMP = os.path.join(ROOT, 'work/rpf_tmp')
TSV = os.path.join(ROOT, 'export/world/rpf_found_missing.tsv')
STATE = os.path.join(ROOT, 'work/rpf_extract_state.json')
TEXT_EXT = ('.ydr', '.yft')


def joaat(s):
  h = 0
  for c in s.lower().encode():
    h = (h + c) & 0xFFFFFFFF
    h = (h + (h << 10)) & 0xFFFFFFFF
    h ^= h >> 6
  h = (h + (h << 3)) & 0xFFFFFFFF
  h ^= h >> 11
  return (h + (h << 15)) & 0xFFFFFFFF


def name_hash(fname):
  """0xHASH.ydr → 直接用；有名文件 → joaat(去扩展名)。"""
  base = os.path.splitext(os.path.basename(fname))[0]
  if base.lower().startswith('0x'):
    try:
      return int(base[2:], 16)
    except Exception:
      return None
  return joaat(base)


def run(args, log=True):
  r = subprocess.run(['dotnet', DOTNET] + args, capture_output=True, text=True,
                     encoding='utf-8', errors='ignore')
  if log and r.returncode != 0:
    print('[rpf] %s -> rc=%d %s' % (' '.join(args[:2]), r.returncode,
                                    (r.stderr or '').strip().splitlines()[-1:] or ''))
  return r


LINE = __import__('re').compile(r'^\s*(\d+)\s+res=\d+\s+comp=\S+\s+(.+?)\s*$')


def listing(arc):
  """→ [(path, size)]；解析 `list` 的每一行（格式见 rdr2rpf/Program.cs CmdList）。"""
  r = run(['list', arc])
  out = []
  for ln in r.stdout.splitlines():
    m = LINE.match(ln)
    if not m:
      continue
    out.append((m.group(2).strip(), int(m.group(1))))
  return out


def missing_set():
  idx = json.load(open(LIB, encoding='utf-8'))
  have = set(idx['models'].keys())
  ent = set()
  for p in glob.glob(os.path.join(TILES, '*.json')):
    if p.endswith('.bak'):
      continue
    for e in json.load(open(p, encoding='utf-8')):
      ent.add('0x%08x' % e[0])
  miss = {}
  for h in (ent - have):
    miss[int(h, 16)] = h
  return miss


def load_state():
  try:
    return json.load(open(STATE, encoding='utf-8'))
  except Exception:
    return {'done': [], 'found': []}


def save_state(st):
  os.makedirs(os.path.dirname(STATE), exist_ok=True)
  json.dump(st, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def harvest(src_dir, miss, found, st, keep_dirs=True):
  """把 src_dir 下命中 hash 的 .ydr/.yft 移到 raw/_missing，返回命中数。"""
  n = 0
  total = 0
  for dp, _, fs in os.walk(src_dir):
    for f in fs:
      total += 1
      ext = os.path.splitext(f)[1].lower()
      if ext not in TEXT_EXT:
        continue
      h = name_hash(f)
      if h is None or h not in miss:
        continue
      dst = os.path.join(OUT_DIR, f)
      if os.path.exists(dst):
        continue
      os.makedirs(OUT_DIR, exist_ok=True)
      shutil.move(os.path.join(dp, f), dst)
      found.add(miss[h])
      n += 1
  return n, total


def extract_one(arc, member, outdir):
  """单文件抽取（pattern = 文件名）。"""
  os.makedirs(outdir, exist_ok=True)
  return run(['extract', arc, outdir, os.path.basename(member)])


def do_archive(arc, miss, found, st, depth, max_depth, label):
  """处理一个包：命中就抽，嵌套包递归。返回 (命中数, 扫描条目数)。"""
  t0 = time.time()
  ent = listing(arc)
  if not ent:
    print('[rpf] %s 列表为空/读不了，跳过' % label)
    return 0, 0
  got = 0
  nested = []
  sub = os.path.join(TMP, 'hits')
  shutil.rmtree(sub, ignore_errors=True)
  for path, size in ent:
    lo = path.lower()
    if lo.endswith('.rpf'):
      nested.append((path, size))
    elif lo.endswith(TEXT_EXT):
      h = name_hash(path)
      # 命中才抽；已经抽到过的 hash 不再重复
      if h in miss and miss[h] not in found:
        os.makedirs(sub, exist_ok=True)
        extract_one(arc, path, sub)
  if os.path.isdir(sub):
    n, _ = harvest(sub, miss, found, st)
    got += n
    shutil.rmtree(sub, ignore_errors=True)
  print('[rpf] %-22s 条目 %5d（嵌套 %d）直接命中 %d（%.0fs）'
        % (label, len(ent), len(nested), got, time.time() - t0))

  for path, size in nested:
    if depth >= max_depth:
      continue
    key = '%s::%s' % (os.path.basename(arc), path)
    if key in st['done']:
      continue
    t1 = time.time()
    tmp = os.path.join(TMP, 'nested')
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    extract_one(arc, path, tmp)
    # 抽出来的是单个文件，可能在 tmp 里带路径
    inner = None
    for dp, _, fs in os.walk(tmp):
      for f in fs:
        if f.lower().endswith('.rpf'):
          inner = os.path.join(dp, f)
          break
    if inner is None:
      st['done'].append(key)
      shutil.rmtree(tmp, ignore_errors=True)
      continue
    sub_got, sub_ent = do_archive(inner, miss, found, st, depth + 1, max_depth,
                                  key.split('::')[-1].split('/')[-1])
    got += sub_got
    st['done'].append(key)
    save_state(st)
    shutil.rmtree(tmp, ignore_errors=True)
    print('[rpf]   ↳ %s 命中 %d，累计 %d（%.0fs）'
          % (key.split('::')[-1].split('/')[-1], sub_got, len(found), time.time() - t1))
  return got, len(ent)


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument('--packs', nargs='+',
                  default=['levels_%d' % i for i in range(8)],
                  help='包名列表（空格分隔；默认 levels_0..7）。注意别用逗号：cmd 会按逗号拆参数')
  ap.add_argument('--depth', type=int, default=3)
  ap.add_argument('--max-nested', type=int, default=0, help='0 = 不限')
  ap.add_argument('--reset', action='store_true', help='清空断点状态重来')
  a = ap.parse_args()

  st = load_state()
  if a.reset:
    st = {'done': [], 'found': []}
  found = set(st.get('found', []))
  miss = missing_set()
  print('[rpf] 缺模型 hash %d；已抽出 %d；已完成包 %d'
        % (len(miss), len(glob.glob(os.path.join(OUT_DIR, '*'))), len(st['done'])))
  os.makedirs(TMP, exist_ok=True)
  os.makedirs(OUT_DIR, exist_ok=True)

  t_all = time.time()
  total_got = 0
  for pk in a.packs:
    pk = pk.strip()
    if not pk:
      continue
    arc = os.path.join(GAME, pk + '.rpf')
    if not os.path.exists(arc):
      print('[rpf] 找不到 %s' % arc)
      continue
    if pk in st['done']:
      print('[rpf] %s 已完成，跳过' % pk)
      continue
    got, n = do_archive(arc, miss, found, st, 0, a.depth, pk)
    total_got += got
    st['done'].append(pk)
    st['found'] = sorted(found)
    save_state(st)
    print('[rpf] === %s 完成：本包命中 %d，累计抽出 %d，已用 %.0f 分钟'
          % (pk, got, len(found), (time.time() - t_all) / 60.0))

  # 清单（按 hash 去重追加）
  old = set()
  if os.path.exists(TSV):
    with open(TSV, encoding='utf-8') as f:
      for ln in f.read().splitlines()[1:]:
        if ln.strip():
          old.add(ln.split('\t')[0])
  rows = sorted(found)
  with open(TSV, 'w', encoding='utf-8') as f:
    f.write('hash\tnote\n')
    for h in rows:
      f.write('%s\t%s\n' % (h, 'extracted' if h in old else 'extracted'))
  n_files = len([x for x in glob.glob(os.path.join(OUT_DIR, '**', '*'), recursive=True)
                 if os.path.isfile(x)])
  print('[rpf] 全部完成：抽出 %d 个文件，清单 %s，用时 %.0f 分钟'
        % (n_files, TSV, (time.time() - t_all) / 60.0))


if __name__ == '__main__':
  main()
