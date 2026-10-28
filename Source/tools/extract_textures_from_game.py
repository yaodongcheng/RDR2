# -*- coding: utf-8 -*-
"""从游戏 RPF 里把 .ytd（贴图包）抽出来，补全贴图池。

## 为什么

模型有 albedo 名字、但贴图池里没有这个名字 → 绑不上 → 走 `ntex_*` 深色兜底 → 城区一片黑。
抽查 200 个有源模型：424 个 albedo 名，**212 个（50%）池里根本没有**。
池里现有：`work/lib_gtxd/txd` 660 个 ytd / 3.6 GB / 9,373 个名字。

## 做法

对每个包：`list` → `.ytd` 直接抽；`.rpf` 抽出来递归（与抽模型同一套）→ 落到
`work/lib_gtxd/txd_game/`，同名跳过。断点续跑。

    uv run python tools/extract_textures_from_game.py --packs textures_0 packs_0 packs_1 hd_0
    uv run python tools/extract_textures_from_game.py --packs levels_1 levels_2 ...   # 量大
"""
import os
import sys
import json
import time
import shutil
import argparse
import subprocess

ROOT = r'D:/BrainMaker/大镖客2解包分析'
GAME = r'H:/EPICGAMES/RedDeadRedemption2'
DOTNET = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.dll')
OUT = os.path.join(ROOT, 'work/lib_gtxd/txd_game')
TMP = os.path.join(ROOT, 'work/rpf_tmp_tex')
STATE = os.path.join(ROOT, 'work/rpf_tex_state.json')
LINE = __import__('re').compile(r'^\s*(\d+)\s+res=\d+\s+comp=\S+\s+(.+?)\s*$')


def run(args):
  return subprocess.run(['dotnet', DOTNET] + args, capture_output=True, text=True,
                        encoding='utf-8', errors='ignore')


def listing(arc):
  r = run(['list', arc])
  out = []
  for ln in r.stdout.splitlines():
    m = LINE.match(ln)
    if m:
      out.append((m.group(2).strip(), int(m.group(1))))
  return out


def load_state():
  try:
    return json.load(open(STATE, encoding='utf-8'))
  except Exception:
    return {'done': [], 'tex': []}


def save_state(st):
  os.makedirs(os.path.dirname(STATE), exist_ok=True)
  json.dump(st, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False)


def have_names():
  return set(os.path.basename(f).lower() for f in os.listdir(OUT)) if os.path.isdir(OUT) else set()


def extract_tex(arc, sub, outdir):
  """把 arc 里所有 .ytd 抽到 outdir（pattern='.ytd'，一次调用）。"""
  os.makedirs(outdir, exist_ok=True)
  r = run(['extract', arc, outdir, '.ytd'])
  n = 0
  seen = have_names()
  for dp, _, fs in os.walk(outdir):
    for f in fs:
      if not f.lower().endswith('.ytd'):
        continue
      base = os.path.basename(f).lower()
      if base in seen:
        os.remove(os.path.join(dp, f))
        continue
      seen.add(base)
      shutil.move(os.path.join(dp, f), os.path.join(OUT, base))
      n += 1
  shutil.rmtree(outdir, ignore_errors=True)
  return n


def do_archive(arc, st, depth, max_depth, label, t0, only=None):
  ent = listing(arc)
  if not ent:
    return 0
  nested = []
  n = 0
  if any(p.lower().endswith('.ytd') for p, _ in ent):
    # 顶层包（depth==0）总是抽；嵌套包只抽名字里带关键词的（gtxd 之类），
    # 否则会把 metaped_textures_* / ui_* / movies 全抽下来（几十 GB 无用贴图）
    if not only or depth == 0 or any(k in label.lower() for k in only):
      n = extract_tex(arc, None, os.path.join(TMP, 'flat'))
  for p, _ in ent:
    if p.lower().endswith('.rpf'):
      nested.append(p)
  print('[tex] %-24s 条目 %5d（嵌套 %d）抽出 ytd %d，共 %d（%.0f 分钟）'
        % (label, len(ent), len(nested), n, len(have_names()), (time.time() - t0) / 60.0))
  for p in nested:
    if depth >= max_depth:
      continue
    # 只下钻名字命中的嵌套包；不然会抽到一堆 ui_/metaped_/movies 角色贴图
    if only and not any(k in p.lower() for k in only):
      continue
    key = '%s::%s' % (os.path.basename(arc), p)
    if key in st['done']:
      continue
    d = os.path.join(TMP, 'n')
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    run(['extract', arc, d, p.split('/')[-1]])
    inner = None
    for dp, _, fs in os.walk(d):
      for f in fs:
        if f.lower().endswith('.rpf'):
          inner = os.path.join(dp, f)
    if inner:
      n += do_archive(inner, st, depth + 1, max_depth,
                      key.split('::')[-1].split('/')[-1], t0, only)
    st['done'].append(key)
    save_state(st)
    shutil.rmtree(d, ignore_errors=True)
  return n


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument('--packs', nargs='+',
                  default=['textures_0', 'textures_1', 'packs_0', 'packs_1', 'hd_0'])
  ap.add_argument('--depth', type=int, default=4)
  ap.add_argument('--only', default='gtxd',
                  help='只下钻名字含这些关键词的嵌套包（逗号分隔）；顶层包总抽；空字符串 = 不过滤')
  ap.add_argument('--reset', action='store_true')
  ap.add_argument('--out', default='', help='输出目录（默认 work/lib_gtxd/txd_game）')
  a = ap.parse_args()
  only = [x for x in a.only.split(',') if x]
  global OUT, STATE
  if a.out:
    OUT = a.out
    STATE = os.path.join(os.path.dirname(a.out.rstrip('/\\')), 'rpf_tex_state_%s.json'
                         % os.path.basename(a.out.rstrip('/\\')))
    globals()['OUT'] = OUT

  os.makedirs(OUT, exist_ok=True)
  os.makedirs(TMP, exist_ok=True)
  st = load_state()
  if a.reset:
    st = {'done': []}
  t0 = time.time()
  print('[tex] 现有 ytd %d 个；已完成包 %d；过滤词 %s'
        % (len(have_names()), len(st['done']), only or '（不过滤）'))
  for pk in a.packs:
    arc = os.path.join(GAME, pk + '.rpf')
    if not os.path.exists(arc):
      print('[tex] 找不到 %s' % arc)
      continue
    if pk in st['done']:
      print('[tex] %s 已完成，跳过' % pk)
      continue
    got = do_archive(arc, st, 0, a.depth, pk, t0, only)
    st['done'].append(pk)
    save_state(st)
    print('[tex] === %s 完成：+%d，累计 ytd %d（%.0f 分钟）'
          % (pk, got, len(have_names()), (time.time() - t0) / 60.0))
  print('[tex] 全部完成：ytd %d 个，目录 %s' % (len(have_names()), OUT))


if __name__ == '__main__':
  main()
