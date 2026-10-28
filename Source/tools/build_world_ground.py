"""把全图地形的**真色图**（`<tile>_t`，2048²/512 m）烘成一张世界地面贴图。

这是补上"和 sdn.blend 差在哪"的最后一块：
  sdn.blend 的地面用的是 0.5 m/px 的真地形色图，而整图版一直用的是 3 m/px 的合成色图。

做法：地形瓦片包（levels/rdr3/terrain/<area>/<tile>_.rpf）里带 `<tile>_.ytd`，
      内含 `<tile>_t`（2048²，覆盖 512 m）。按瓦片世界 bbox 贴进全局画布。

产物：
  export/world/world_ground_{px}.png    全局地面色图
  export/world/world_ground_meta.json   分辨率 / 覆盖瓦片数 / 缺图列表

用法：
  uv run python tools/build_world_ground.py --pxm 1 --limit 12     # 试跑
  uv run python tools/build_world_ground.py --pxm 1                # 全量
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

import numpy as np
from PIL import Image

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))

GAME = r'H:/EPICGAMES/RedDeadRedemption2'
RP = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe')
TMP = os.path.join(ROOT, 'work/ground_bake')
OUT = os.path.join(ROOT, 'export/world')
META = os.path.join(ROOT, 'export/world/world_meta.json')

X0, Y0, WORLD = -7684.0, -8196.0, 12296.0
Y_NORTH = Y0 + WORLD


def tile_bboxes():
    """地形瓦片名 → 世界 bbox（从 strm ymap 的 __hd_0_ 实体推出来）"""
    import ymap_entities
    name_by_hash = {}
    with open(os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt'),
              encoding='latin1', errors='ignore') as f:
        for line in f:
            n = line.strip()
            if n:
                h = 0
                for c in n.lower().encode():
                    h = (h + c) & 0xffffffff
                    h = h + (h << 10) & 0xffffffff
                    h ^= h >> 6
                h = (h + (h << 3)) & 0xffffffff
                h ^= h >> 11
                h = (h + (h << 15)) & 0xffffffff
                name_by_hash[h] = n
    pos = {}
    for f in glob.glob(os.path.join(ROOT, 'export/levels/map_metadata/**/*_strm_0.ymap'), recursive=True):
        try:
            _s, _z, es = ymap_entities.extract(f)
        except Exception:
            continue
        for e in es:
            n = name_by_hash.get(e[0], '')
            if '__hd_0_' in n:
                pos[n] = (e[1], e[2])
    out = {}
    for n, (x, y) in pos.items():
        t = n.split('__hd_0_')[0]
        b = out.setdefault(t, [1e9, 1e9, -1e9, -1e9])
        b[0] = min(b[0], x); b[1] = min(b[1], y)
        b[2] = max(b[2], x); b[3] = max(b[3], y)
    return {k: (v[0] - 32, v[1] - 32, v[2] + 32, v[3] + 32) for k, v in out.items()}


def pack_map():
    """tile 名 → (levels 文件, 包路径)"""
    idx = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'work/terrain/list_levels_*.txt'))):
        m = re.search(r'list_levels_(\d)\.txt$', f)
        if not m:
            continue
        lv = os.path.join(GAME, 'levels_%s.rpf' % m.group(1))
        for line in open(f, encoding='utf-8', errors='ignore'):
            mm = re.match(r'\s+(\d+)\s+res=\S+\s+comp=\S+\s+(\S.*)$', line)
            if not mm:
                continue
            p = mm.group(2).strip()
            if '/terrain/' in p and p.endswith('_.rpf'):
                idx[os.path.basename(p)[:-5]] = (lv, p)
    return idx


def extract_tile_tex(levels, path, tile):
    from rdr2_ytd import Ytd
    from ytd_to_png import decode_one
    work = os.path.join(TMP, 'p')
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work, exist_ok=True)
    subprocess.run([RP, 'extract', levels, work, path], capture_output=True)
    rpfs = glob.glob(os.path.join(work, '**', '*.rpf'), recursive=True)
    inner = os.path.join(work, 'inner')
    os.makedirs(inner, exist_ok=True)
    for r in rpfs:
        subprocess.run([RP, 'extract', r, inner, ''], capture_output=True)
    for ytd in glob.glob(os.path.join(inner, '*.ytd')):
        if os.path.basename(ytd).lower() not in (tile + '_.ytd',) and not \
                os.path.basename(ytd).lower().startswith(tile + '_'):
            continue
        try:
            y = Ytd(open(ytd, 'rb').read())
        except Exception:
            continue
        for t in y.textures():
            nm = (t['name'] or '').lower()
            if nm in (tile + '_t', tile + '_t_hd'):
                blob = y.gfx[t['gfx_off']:t['gfx_off'] + max(4096, t['w'] * t['h'] * 4)]
                im, _fmt = decode_one(blob, t['w'], t['h'], t['fmt'])
                if im is not None:
                    return im.convert('RGB')
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pxm', type=float, default=1.0, help='每米像素')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()

    pxm = a.pxm
    W = int(round(WORLD * pxm))
    print('canvas %d x %d (%.1f m/px)' % (W, W, 1.0 / pxm))

    boxes = tile_bboxes()
    packs = pack_map()
    todo = [(t, boxes[t]) for t in sorted(packs) if t in boxes]
    if a.limit:
        todo = todo[:a.limit]
    print('可烘瓦片 %d / 世界瓦片 %d / 包 %d' % (len(todo), len(boxes), len(packs)))

    canvas = np.zeros((W, W, 3), np.uint8)
    mask = np.zeros((W, W), bool)
    ok = miss = 0
    t0 = time.time()
    for n, (t, bb) in enumerate(todo, 1):
        lv, p = packs[t]
        im = extract_tile_tex(lv, p, t)
        if im is None:
            miss += 1
            print('  [%d/%d] %-10s 无 _t' % (n, len(todo), t))
            continue
        x0, y0, x1, y1 = bb
        pw = max(1, int(round((x1 - x0) * pxm)))
        ph = max(1, int(round((y1 - y0) * pxm)))
        im = im.resize((pw, ph), Image.LANCZOS)
        px = int(round((x0 - X0) * pxm))
        py = int(round((Y_NORTH - y1) * pxm))
        arr = np.asarray(im)
        x2, y2 = min(W, px + pw), min(W, py + ph)
        if x2 <= px or y2 <= py:
            continue
        canvas[py:y2, px:x2] = arr[:y2 - py, :x2 - px]
        mask[py:y2, px:x2] = True
        ok += 1
        if n % 20 == 0:
            print('  [%d/%d] %.0f%%  %.1f 分' % (n, len(todo), 100.0 * ok / n, (time.time() - t0) / 60))
    shutil.rmtree(TMP, ignore_errors=True)

    print('覆盖瓦片 %d，缺 %d，覆盖像素 %.1f%%' % (ok, miss, 100.0 * mask.mean()))
    out = os.path.join(OUT, 'world_ground_%s.png' % str(pxm).replace('.', 'p'))
    Image.fromarray(canvas).save(out, optimize=True)
    meta = json.load(open(META, encoding='utf-8'))
    meta['ground_px'] = W
    meta['ground_pxm'] = pxm
    meta['ground_png'] = os.path.basename(out)
    json.dump(meta, open(META, 'w'), ensure_ascii=False, indent=1)
    print('→ %s  %.0f MB' % (out, os.path.getsize(out) / 1e6))


if __name__ == '__main__':
    main()
