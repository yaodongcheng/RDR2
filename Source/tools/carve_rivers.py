# -*- coding: utf-8 -*-
"""大地图专用：在 `01_plateau_plain`（原生 H4 + 自然界过渡）基础上做**河床加深**。

旧脚本 `build_final_map_heightmap.py` 的四个问题（本脚本逐条改掉）：
  1. **水陆边界**用的是官方地图 JPEG 的颜色启发式（`water_map`），而算出来的游戏掩码
     `water_game` **根本没被使用**（最后一行 `water = water_map`）。→ 本脚本直接用交付的
     `deliverable/heightmap/water_mask.png`（8.10 km²，逐像素）。
  2. **水位只有一套**：读 `water_level_map.npy`（西南河与海被并成同一连通域 → 42.1 m），
     再高斯平滑；没有东西两块水面的概念。→ 本脚本按分割线分两块：西 −22 / 东 40.5，
     **各自在自己范围内加深**。
  3. **把陆地抬到水位 +2 m**（`z_land = where(z > wlevel+1.2, z, wlevel+2+fbm)`）——
     这条把西盆地的低地全部填平，是"高度失真"的主因。→ 本脚本**只降低水格、陆地一律不动**。
  4. **平底深度写死**（35/16/7/4 m）且无条件赋值，会把已经更低的河床**抬高**。
     → 本脚本按水体面积给深度，但只取 `z = min(z, 水位-深度)`，**绝不抬高**；
     并且**高山湖跳过**（水体自身高程高于区域水位 +20 m 就不挖，否则会把山顶湖挖成深坑）。

只用于**大地图**；子场景仍用 100% 原生 H4（`scene_terrain_core` 已优先 NATIVE_HFILE）。

用法：
    python tools/carve_rivers.py
    python tools/carve_rivers.py --split-x -1000 --dry-run
"""
import argparse
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None
ROOT = r'D:/BrainMaker/大镖客2解包分析'
DELIV = os.path.join(ROOT, 'deliverable')
SRC_DIR = os.path.join(DELIV, 'terrain', 'stages', '01_plateau_plain')
SRC_PNG = os.path.join(SRC_DIR, 'height_16bit_4m.png')
SRC_META = os.path.join(SRC_DIR, 'meta.json')
MASK = os.path.join(DELIV, 'heightmap', 'water_mask.png')
OUT_DIR = os.path.join(DELIV, 'terrain', 'stages', '02_river_carve')
SETTLE = os.path.join(DELIV, 'handoff', 'settlements_world_v2.csv')

X0, Y1 = -6844.0, 3224.0
RES = 4.0
Z_EAST = 40.5
Z_WEST = -22.0
PROTECT_M = 0.0          # 0 = 不做据点保护（否则据点附近的水格刻不到水位以下，俯视图会出现非蓝斑）
FEATHER_SIGMA = 1.8

# 深度按水体面积（m²）分档：海 / 湖 / 塘 / 河
DEPTHS = ((5e6, 35.0), (1e6, 16.0), (1e5, 7.0), (0.0, 4.0))


def depth_for(area_m2):
    for lim, d in DEPTHS:
        if area_m2 > lim:
            return d
    return DEPTHS[-1][1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--height', default=SRC_PNG)
    ap.add_argument('--meta', default=SRC_META)
    ap.add_argument('--mask', default=MASK)
    ap.add_argument('--out-dir', default=OUT_DIR)
    ap.add_argument('--split-x', type=float, default=-1000.0,
                    help='东西水面分割线（世界 x）：西侧 -22 / 东侧 40.5')
    ap.add_argument('--protect', type=float, default=PROTECT_M)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    meta = json.load(open(a.meta, encoding='utf-8'))
    h = meta['height']
    zmin, zmax = h['zmin'], h['zmax']
    q = np.asarray(Image.open(a.height), dtype=np.float32)
    z = zmin + q / 65535.0 * (zmax - zmin)
    H, W = z.shape
    print('[carve] height %s %dx%d  z %.1f..%.1f' % (os.path.basename(a.height), W, H, z.min(), z.max()))

    mask_img = Image.open(a.mask).convert('L')
    if mask_img.size != (W, H):
        raise SystemExit('water mask size %s != height %s' % (mask_img.size, (W, H)))
    mask = np.asarray(mask_img) > 128
    print('[carve] water %.2f km2' % (mask.sum() * RES * RES / 1e6))

    xs = X0 + np.arange(W) * RES
    west = (xs < a.split_x)[None, :] & np.ones((H, 1), bool)
    level = np.where(west, Z_WEST, Z_EAST).astype(np.float32)

    # ---- 水深：按河道宽度（宽=湖/海 最深 35 m，窄=河 4 m 起）----
    dist = ndimage.distance_transform_edt(mask) * RES
    width = 2.0 * dist
    depth = np.clip(width * 0.04, 4.0, 35.0)

    side_level = np.where(west, np.float32(Z_WEST), np.float32(Z_EAST)).astype(np.float32)
    target = side_level - depth

    # 据点保护
    protect = np.zeros((H, W), bool)
    if os.path.exists(SETTLE):
        import csv
        for r in csv.DictReader(open(SETTLE, encoding='utf-8-sig')):
            try:
                px, py = float(r['world_x']), float(r['world_y'])
            except (ValueError, KeyError):
                continue
            cc = int((px - X0) / RES); rr = int((Y1 - py) / RES)
            if not (0 <= rr < H and 0 <= cc < W):
                continue
            rad = int(a.protect / RES)
            r0, r1 = max(0, rr - rad), min(H, rr + rad)
            c0, c1 = max(0, cc - rad), min(W, cc + rad)
            dy = (np.arange(r0, r1) - rr)[:, None]
            dx = (np.arange(c0, c1) - cc)[None, :]
            protect[r0:r1, c0:c1] |= (dy * dy + dx * dx) <= rad * rad

    # 水网内：压到「区域水位 − 深度」（只降不抬）；这样每个水格都在水平面之下
    carve = mask & ~protect
    z_new = np.where(carve, np.minimum(z, target), z)

    # 水网外、低于水位的陆地：最小抬升到 水位 +1 m（否则水平面会在那里「出水」）
    fill = (~mask) & (z_new < side_level) & (~protect)
    z_new = np.where(fill, side_level + 1.0, z_new)

    # 水格边缘羽化（只作用在水格上，别把填出来的陆地又抹回去）
    soft = np.clip(ndimage.gaussian_filter(carve.astype(np.float32), FEATHER_SIGMA) * 1.3, 0, 1)
    z_feather = z * (1 - soft) + z_new * soft
    z_new = np.where(carve, z_feather, z_new)
    # 保险：羽化后仍必须**全部**在水位以下，否则俯视图会在水网边缘露出非蓝细线
    z_new = np.where(mask, np.minimum(z_new, side_level - 0.5), z_new)
    print('[carve] fill land below level: %.2f km2' % (fill.sum() * RES * RES / 1e6))

    # 统计
    for name, sel in (('west', mask & west), ('east', mask & ~west)):
        if sel.sum() == 0:
            continue
        print('[carve] %s water: before med %.1f  after med %.1f  (level %.1f)' % (
            name, float(np.median(z[sel])), float(np.median(z_new[sel])),
            Z_WEST if name == 'west' else Z_EAST))
    print('[carve] changed cells: %d (%.1f%%)  z %.1f..%.1f' % (
        int((np.abs(z_new - z) > 1e-3).sum()), 100.0 * (np.abs(z_new - z) > 1e-3).mean(),
        z_new.min(), z_new.max()))

    if a.dry_run:
        print('[carve] DRY RUN OK')
        return

    os.makedirs(a.out_dir, exist_ok=True)
    zmin2, zmax2 = float(z_new.min()), float(z_new.max())
    q2 = np.clip((z_new - zmin2) / max(1e-6, zmax2 - zmin2) * 65535.0, 0, 65535).astype('<u2')
    Image.fromarray(q2).save(os.path.join(a.out_dir, 'height_16bit_4m.png'))
    open(os.path.join(a.out_dir, 'height_r16.raw'), 'wb').write(q2.tobytes(order='C'))
    Image.fromarray((mask * 255).astype(np.uint8)).save(os.path.join(a.out_dir, 'water_mask.png'))
    dd = np.where(mask, np.maximum(0.0, z - z_new), 0)
    Image.fromarray(np.clip(dd / 300.0 * 255, 0, 255).astype(np.uint8)).save(
        os.path.join(a.out_dir, 'water_depth.png'))

    out_meta = {
        'stage': '02_river_carve',
        'world': meta.get('world'),
        'row0': 'north', 'col0': 'west',
        'height': {'file': 'height_16bit_4m.png', 'px': [W, H], 'm_per_px': RES,
                   'zmin': zmin2, 'zmax': zmax2},
        'source': os.path.basename(a.height),
        'params': {'split_x': a.split_x, 'z_east': Z_EAST, 'z_west': Z_WEST,
                   'protect_m': a.protect, 'feather_sigma': FEATHER_SIGMA,
                   'depths': 'sea 35 / lake 16 / pond 7 / river 4 (only lower, never raise)'},
        'water': {'mask': 'water_mask.png', 'area_km2': round(float(mask.sum() * RES * RES / 1e6), 2),
                  'west_level': Z_WEST, 'east_level': Z_EAST},
        'note': '大地图专用；陆地一律不动；子场景仍用原生 H4',
    }
    json.dump(out_meta, open(os.path.join(a.out_dir, 'meta.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('[carve] -> %s  z %.1f..%.1f' % (a.out_dir, zmin2, zmax2))


if __name__ == '__main__':
    main()
