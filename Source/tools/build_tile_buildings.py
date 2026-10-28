"""按 2000 m 分区，把**该块里的所有建筑/道具**导出成 glTF（圣丹尼斯同款管线）。

和 `build_settlement_previews.py` 的区别：
  · 输入不是"据点半径"，而是分区 bbox（默认 2000 m）
  · 一个块可能跨多个 area 目录，全部抽出来合并

产物：export/world/tiles/<tileId>/tiles/*.gltf + textures/ + tiles.json
      export/world/tiles/<tileId>/meta.json   （实体数 / 模型数 / 体积）

用法：
  uv run python tools/build_tile_buildings.py --only wild2000_05_03
  uv run python tools/build_tile_buildings.py --all --skip-existing
"""
import os
import re
import sys
import json
import glob
import time
import shutil
import argparse
import subprocess

ROOT = r'D:/BrainMaker/大镖客2解包分析'
GAME = r'H:/EPICGAMES/RedDeadRedemption2'
RP = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe')
WORK = os.path.join(ROOT, 'work/tileb')
OUT = os.path.join(ROOT, 'export/world/tiles')
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import plan_town  # noqa: E402

SKIP_PACK = ('_vfx', '_lod_combine', '_collision', 'audioproxy', '_decals', '_shad')


def build_index():
    idx = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'work/terrain/list_levels_*.txt'))):
        m = re.search(r'list_levels_(\d)\.txt$', f)
        if not m:
            continue
        lv = os.path.join(GAME, 'levels_%s.rpf' % m.group(1))
        for line in open(f, encoding='utf-8', errors='ignore'):
            mm = re.match(r'\s+(\d+)\s+res=\S+\s+comp=\S+\s+(\S.*)$', line)
            if mm:
                idx[mm.group(2).strip()] = (lv, int(mm.group(1)))
    return idx


def run(cmd, log=None):
    t = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
    dt = time.time() - t
    if log:
        with open(log, 'a', encoding='utf-8') as f:
            f.write('$ %s\n%s\n%s\n' % (' '.join(cmd), p.stdout[-1500:], p.stderr[-1500:]))
    return p.returncode, p.stdout + p.stderr, dt


def extract_entry(levels, path, dest):
    os.makedirs(dest, exist_ok=True)
    run([RP, 'extract', levels, dest, path])
    base = os.path.basename(path)
    cand = glob.glob(os.path.join(dest, '**', base), recursive=True)
    got = cand[0] if cand else None
    if got and got.endswith('.rpf'):
        sub = dest + '_x'
        os.makedirs(sub, exist_ok=True)
        run([RP, 'extract', got, sub, ''])
        return sub
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--skip-existing', action='store_true')
    ap.add_argument('--maxs', type=int, default=192)
    ap.add_argument('--limit', type=int, default=0, help='只处理前 N 个（试跑用）')
    a = ap.parse_args()

    grid = json.load(open(os.path.join(ROOT, 'export/world/tiles_2000.json'), encoding='utf-8'))
    want = {x.strip() for x in a.only.split(',') if x.strip()}
    tiles = [t for t in grid['tiles'] if (a.all or t['id'] in want)]
    if a.limit:
        tiles = tiles[:a.limit]
    if not tiles:
        print('没有选中分区')
        return

    idx = build_index()
    box = plan_town.tile_bboxes()
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    log = os.path.join(WORK, 'batch.log')

    for n, t in enumerate(tiles, 1):
        tid = t['id']
        outdir = os.path.join(OUT, tid)
        if a.skip_existing and os.path.exists(os.path.join(outdir, 'meta.json')):
            print('[%d/%d] %s 已存在，跳过' % (n, len(tiles), tid))
            continue
        b = t['world']
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        r = ((b[2] - b[0]) ** 2 + (b[3] - b[1]) ** 2) ** 0.5 / 2 + 40
        t0 = time.time()
        print('[%d/%d] %s  (%.0f,%.0f) r=%.0f' % (n, len(tiles), tid, cx, cy, r))

        # 该块覆盖的 area 目录（四角 + 中心，去重）
        adirs = set()
        for (px, py) in [(b[0], b[1]), (b[2], b[1]), (b[0], b[3]), (b[2], b[3]), (cx, cy)]:
            ad, _ = plan_town.area_dir_for(px, py, box)
            if ad:
                adirs.add(ad)
        packs = [p for p in idx
                 if any('/area/%s/' % ad in p for ad in adirs)
                 and not any(k in p for k in SKIP_PACK)]
        print('   area %s → %d 个包' % (','.join(sorted(adirs)), len(packs)))

        tdir = os.path.join(WORK, tid)
        models = os.path.join(tdir, 'models')
        os.makedirs(models, exist_ok=True)
        for p in packs:
            lv, _ = idx[p]
            sub = extract_entry(lv, p, os.path.join(tdir, 'tmp'))
            for f in glob.glob(os.path.join(sub, '**', '*.ydr'), recursive=True) + \
                     glob.glob(os.path.join(sub, '**', '*.yft'), recursive=True):
                shutil.copy2(f, models)

        ydr = ','.join([models,
                        os.path.join(ROOT, 'work/sdn/props'),
                        os.path.join(ROOT, 'work/sdn/props2')])
        ytd = ','.join([os.path.join(ROOT, 'work/sdn/gtxd/txd'),
                        os.path.join(ROOT, 'export/models')])
        cmd = [sys.executable, os.path.join(ROOT, 'tools/export_sdn_gltf.py'),
               '--cx', str(cx), '--cy', str(cy), '--r', str(r),
               '--ydr', ydr, '--ytd', ytd, '--chunk', '160',
               '--maxs', str(a.maxs), '--out', outdir]
        rc, outp, dt = run(cmd, log)
        if rc != 0:
            print('   ! 导出失败', outp[-300:])
            continue
        tdir2 = os.path.join(outdir, 'tiles')
        if os.path.isdir(tdir2):
            files = sorted(os.path.basename(f) for f in glob.glob(os.path.join(tdir2, '*.gltf')))
            json.dump({'files': files}, open(os.path.join(tdir2, 'tiles.json'), 'w'))
        m = re.search(r'实例 (\d+) 个.*模型 (\d+) 个', outp)
        size = sum(os.path.getsize(f) for f in glob.glob(os.path.join(outdir, '**', '*'), recursive=True)
                   if os.path.isfile(f))
        json.dump(dict(id=tid, cx=cx, cy=cy, r=r,
                       instances=int(m.group(1)) if m else None,
                       models=int(m.group(2)) if m else None,
                       bytes=size, seconds=round(time.time() - t0, 1)),
                  open(os.path.join(outdir, 'meta.json'), 'w'), ensure_ascii=False, indent=1)
        print('   -> %s 实例 / %s 模型 / %.0f MB / %.0fs' %
              (m.group(1) if m else '?', m.group(2) if m else '?', size / 1e6, time.time() - t0))
        # 清理临时解包目录（只保留 ydr/yft）
        shutil.rmtree(os.path.join(tdir, 'tmp'), ignore_errors=True)
        shutil.rmtree(os.path.join(tdir, 'tmp_x'), ignore_errors=True)


if __name__ == '__main__':
    main()
