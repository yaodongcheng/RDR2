# -*- coding: utf-8 -*-
"""导出**原版最精细**的地形宏观色图：按 512 m 瓦片、保持源分辨率 2048²（0.25 m/px）。

## 为什么是"分块"而不是"一张大图"

RDR2 的地形色图本来就是**一块 512 m 一个 `<tile>_t`（2048²）**，天生分块：
  · 拼成整张 = 491 × 2048² = **49,184² = 7.3 GB 原始像素**，一张图谁都读不动；
  · 引擎（含骑砍2）也只可能按区域流式取块。
所以"最精细"的正确交付形态 = **原样分块 + 一张世界坐标清单**，要拼再说。

## 产物

    deliverable/terrain_tiles/<tile>.png     每块 2048×2048（0.25 m/px），无损 PNG
    deliverable/terrain_tiles/tiles_manifest.csv
         tile, x0, y0, x1, y1, px, m_per_px

世界坐标约定与全图管线一致：X 东 / Y 北 / Z 上，单位米（origin -7684, -8196，world 12296 m）。

    python tools/export_terrain_tiles.py                 # 全量导出
    python tools/export_terrain_tiles.py --limit 8       # 试跑
    python tools/export_terrain_tiles.py --stitch 2      # 顺带拼一张 2 px/m 的整图（可选）

数据来自已解包的 `work/all_packs/<tile>_/<tile>_.ytd`（= `raw/...`），
**不重新解包游戏**；某块缺图会记进 `tiles_manifest.csv` 的 note 列。
"""
import argparse
import csv
import glob
import io
import os
import sys
import time

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TOOLS = os.path.join(ROOT, 'tools')
OUT = os.path.join(ROOT, 'deliverable/terrain_tiles')
sys.path.insert(0, TOOLS)

import numpy as np                      # noqa: E402
from PIL import Image                   # noqa: E402
Image.MAX_IMAGE_PIXELS = None


def tile_bboxes():
    """tile 名 → 世界 bbox（米）。与 build_world_ground.py 同一套推导（__hd_0_ 实体 + ±32 m 边距）。"""
    import build_world_ground as B
    return B.tile_bboxes()


def find_tile_ytd(tile):
    """在已解包池里找 `<tile>_.ytd`（work/all_packs 下按名字分目录）。"""
    for pat in (os.path.join(ROOT, 'work/all_packs/%s_/%s_.ytd' % (tile, tile)),
                os.path.join(ROOT, 'work/all_packs/**/%s_.ytd' % tile)):
        hit = glob.glob(pat, recursive=True)
        if hit:
            return hit[0]
    # 退化：索引里按 `<tile>_t` 反查文件
    try:
        import json
        idx = json.load(io.open(os.path.join(ROOT, 'work/tex_name_index.json'), encoding='utf-8'))
        e = idx.get(tile.lower() + '_t')
        if e:
            return os.path.join(ROOT, e['f'].replace('/', os.sep))
    except Exception:
        pass
    return None


def decode_tile(ytd_path, tile):
    """从 .ytd 里取出 `<tile>_t`，返回 (PIL.Image, w, h) 或 (None, 原因)。"""
    from rdr2_ytd import Ytd
    from ytd_to_png import decode_one
    want = (tile.lower() + '_t',)
    with open(ytd_path, 'rb') as f:
        y = Ytd(f.read())
    for t in y.textures():
        n = (t.get('name') or '').lower()
        if n not in want:
            continue
        blob = y.gfx[t['gfx_off']:t['gfx_off'] + max(4096, t['w'] * t['h'] * 4)]
        im, _fmt = decode_one(blob, t['w'], t['h'], t['fmt'])
        if im is None:
            return None, 'decode-failed'
        return im.convert('RGB'), None
    return None, 'no-%s_t' % tile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--stitch', type=float, default=0.0,
                    help='顺带拼整图，单位「每米像素」（2 = 0.5 m/px，1 = 1 m/px；0 = 不拼）')
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    print('[tiles] 推 world bbox ...')
    bbox = tile_bboxes()
    print('[tiles] 地形瓦片 %d 个' % len(bbox))
    items = sorted(bbox.items())
    if a.limit:
        items = items[:a.limit]

    rows = []
    ok = miss = 0
    t0 = time.time()
    for i, (tile, (x0, y0, x1, y1)) in enumerate(items):
        ytd = find_tile_ytd(tile)
        note = ''
        w = h = 0
        if not ytd:
            note = 'no-ytd'
        else:
            im, why = decode_tile(ytd, tile)
            if im is None:
                note = why or 'decode-failed'
            else:
                w, h = im.size
                im.save(os.path.join(a.out, '%s.png' % tile), 'PNG', optimize=False)
                ok += 1
        if note:
            miss += 1
        rows.append([tile, round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1), w, h,
                     round((x1 - x0) / w, 4) if w else '', note])
        if (i + 1) % 50 == 0:
            el = time.time() - t0
            print('[tiles] %d/%d  成功 %d 缺 %d  %.1f/s  剩 ~%.0f 分'
                  % (i + 1, len(items), ok, miss, (i + 1) / el,
                     (len(items) - i - 1) / max(1e-9, (i + 1) / el) / 60), flush=True)

    man = os.path.join(a.out, 'tiles_manifest.csv')
    with io.open(man, 'w', encoding='utf-8-sig', newline='') as f:
        w_ = csv.writer(f)
        w_.writerow(['tile', 'x0', 'y0', 'x1', 'y1', 'w', 'h', 'm_per_px', 'note'])
        w_.writerows(rows)
    sz = sum(os.path.getsize(os.path.join(a.out, f)) for f in os.listdir(a.out)
             if f.endswith('.png'))
    print('[tiles] 完成：成功 %d / 缺 %d；PNG 合计 %.2f GB → %s'
          % (ok, miss, sz / 1e9, a.out))
    print('[tiles] 清单 %s' % man)

    if a.stitch and ok:
        stitch(a, items, a.out)


def stitch(a, items, srcdir):
    """按「每米像素」拼一张整图（内存够才建议；49184² = 7.3 GB）。"""
    ppm = a.stitch
    W = int(round(12296 * ppm))
    print('[stitch] %s px/m → %d×%d' % (ppm, W, W))
    canvas = Image.new('RGB', (W, W), (0, 0, 0))
    X0, Y0 = -7684.0, -8196.0
    YN = Y0 + 12296.0
    n = 0
    for tile, (x0, y0, x1, y1) in items:
        p = os.path.join(srcdir, '%s.png' % tile)
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert('RGB')
        tw = max(1, int(round((x1 - x0) * ppm)))
        th = max(1, int(round((y1 - y0) * ppm)))
        im = im.resize((tw, th), Image.LANCZOS)
        px = int(round((x0 - X0) * ppm))
        py = int(round((YN - y1) * ppm))
        canvas.paste(im, (px, py))
        n += 1
        if n % 100 == 0:
            print('[stitch] %d 块 ...' % n, flush=True)
    out = os.path.join(srcdir, 'stitched_%gpxm.png' % ppm)
    canvas.save(out, 'PNG', compress_level=3)
    print('[stitch] SAVED %s %.2f GB' % (out, os.path.getsize(out) / 1e9))


if __name__ == '__main__':
    main()
