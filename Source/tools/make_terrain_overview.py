# -*- coding: utf-8 -*-
"""生成**整体地形预览图**：高程晕渲 + 材质色图，整个正方形一份、可玩区一份。

    python tools/make_terrain_overview.py
    python tools/make_terrain_overview.py --size 6144        # 更大
    python tools/make_terrain_overview.py --out <目录>

产物（默认 `deliverable/terrain_overview/`）：

    overview_height_full.png   整张 12296 m 正方形 · 高程晕渲（含瓜玛/框外，画了可玩区框线）
    overview_color_full.png    同上 · 材质色图（城市"挖空黑块"一眼可见）
    overview_shaded_full.png   同上 · 色图 × 晕渲 叠加（最像地形的一张）
    overview_height_map.png    只裁可玩区（map_area.json）· 高程晕渲
    overview_color_map.png     只裁可玩区 · 材质色图
    overview_shaded_map.png    只裁可玩区 · 叠加
    meta.json                  坐标/尺寸/来源（拼图用得上）

色图来源 `export/world/world_ground_final.png`（1 px/m，含回填）；
高程来源 `raw/terrain/H4.npy`（4 m 栅格，含扩散补洞）。
"""
import argparse
import json
import os

import numpy as np
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None

ROOT = r'D:/BrainMaker/大镖客2解包分析'
H4 = os.path.join(ROOT, 'raw/terrain/H4.npy')
COLOR = os.path.join(ROOT, 'export/world/world_ground_final.png')
AREA = os.path.join(ROOT, 'export/world/map_area.json')
OUT = os.path.join(ROOT, 'deliverable/terrain_overview')

X0, Y0, RES = -7684.0, -8196.0, 4.0      # H4 栅格口径
WORLD = 12296.0


def hypsometric(z):
    """高程着色：水蓝 → 绿 → 黄棕 → 岩灰 → 雪白（0..1 归一化输入）。"""
    stops = [(0.00, (30, 60, 110)), (0.12, (60, 120, 90)), (0.28, (110, 140, 80)),
             (0.45, (150, 130, 90)), (0.62, (140, 125, 110)), (0.80, (170, 170, 165)),
             (1.00, (250, 250, 252))]
    out = np.zeros(z.shape + (3,), np.float32)
    for i in range(len(stops) - 1):
        z0, c0 = stops[i]
        z1, c1 = stops[i + 1]
        m = (z >= z0) & (z <= z1)
        if not m.any():
            continue
        t = ((z[m] - z0) / max(1e-6, z1 - z0))[..., None]
        out[m] = np.array(c0, np.float32) * (1 - t) + np.array(c1, np.float32) * t
    out[z > stops[-1][0]] = stops[-1][1]
    return np.clip(out, 0, 255)


def hillshade(z, res_m, az=315.0, alt=45.0):
    """标准晕渲（光照来自西北）。z 单位米，res_m 每像素米。"""
    gy, gx = np.gradient(z, res_m)
    slope = np.pi / 2 - np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    azr = np.deg2rad(360.0 - az + 90.0)
    altr = np.deg2rad(alt)
    hs = (np.sin(altr) * np.sin(slope)
          + np.cos(altr) * np.cos(slope) * np.cos(azr - aspect))
    return np.clip(hs, 0, 1)


def to_img(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'RGB')


def load_area():
    try:
        d = json.load(open(AREA, encoding='utf-8'))
        return d['x0'], d['y0'], d['x1'], d['y1']
    except Exception:
        return None


def draw_frame(img, box_world, world_rect, col=(255, 40, 40)):
    """在预览图上画出可玩区矩形。"""
    if not box_world:
        return img
    x0, y0, x1, y1 = box_world
    W, H = img.size
    px = W / world_rect[2]
    d = ImageDraw.Draw(img)

    def xy(x, y):
        return ((x - world_rect[0]) * px, (world_rect[3] - y) * px)
    a = xy(x0, y1)
    b = xy(x1, y0)
    d.rectangle([a, b], outline=col, width=max(2, W // 1200))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--size', type=int, default=4096, help='正方形预览边长（像素）')
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--gray', action='store_true',
                    help='顺带出一套**纯灰度**高程预览（overview_height_gray_*.png），'
                         '和原始 16bit 高度图同口径（线性归一化，不加晕渲/不加分色）')
    ap.add_argument('--gray-only', action='store_true', help='只出灰度那两张')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    world_rect = (X0, Y0, X0 + WORLD, Y0 + WORLD)   # x0,y0,x1,y1

    # ---- 高程
    H = np.load(H4).astype(np.float32)
    Hf = np.flipud(H)      # H4 行 0 = 南，图行 0 = 北
    zmin, zmax = float(np.nanmin(Hf)), float(np.nanmax(Hf))
    zn = (Hf - zmin) / max(1e-6, zmax - zmin)
    shade = hillshade(Hf, RES)

    # ---- 纯灰度（与原始 16bit 高度图同口径：线性归一化，不加晕渲、不加分色）
    if a.gray or a.gray_only:
        img_g = to_img(np.repeat((zn * 255.0)[..., None], 3, axis=2))
        img_g = img_g.resize((a.size, a.size), Image.LANCZOS)
        img_g = draw_frame(img_g, load_area(), world_rect)
        p = os.path.join(a.out, 'overview_height_gray_full.png')
        img_g.save(p, 'PNG', compress_level=6)
        print('[ov] %s %dx%d %.1f MB' % (p, a.size, a.size, os.path.getsize(p) / 1e6))
        box0 = load_area()
        if box0:
            bx0, by0, bx1, by1 = box0
            px = img_g.size[0] / (world_rect[2] - world_rect[0])
            c = img_g.crop((int((bx0 - world_rect[0]) * px), int((world_rect[3] - by1) * px),
                            int((bx1 - world_rect[0]) * px), int((world_rect[3] - by0) * px)))
            c = c.resize((a.size, int(a.size * c.size[1] / c.size[0])), Image.LANCZOS)
            p = os.path.join(a.out, 'overview_height_gray_map.png')
            c.save(p, 'PNG', compress_level=6)
            print('[ov] %s %dx%d %.1f MB' % (p, c.size[0], c.size[1], os.path.getsize(p) / 1e6))
    if a.gray_only:
        print('[ov] gray-only，跳过彩色/色图部分')
        return

    base = hypsometric(zn) * (0.35 + 0.65 * shade[..., None])
    hi_res = to_img(base)
    # 4 m 栅格 → 预览边长
    f = a.size / float(hi_res.size[0])
    img_h = hi_res.resize((a.size, a.size), Image.LANCZOS)
    img_h = draw_frame(img_h, load_area(), world_rect)
    p = os.path.join(a.out, 'overview_height_full.png')
    img_h.save(p, 'PNG', compress_level=6)
    print('[ov] %s %dx%d %.1f MB' % (p, a.size, a.size, os.path.getsize(p) / 1e6))

    # ---- 色图
    col = Image.open(COLOR).convert('RGB')
    img_c = col.resize((a.size, a.size), Image.LANCZOS)
    img_c = draw_frame(img_c, load_area(), world_rect)
    p = os.path.join(a.out, 'overview_color_full.png')
    img_c.save(p, 'PNG', compress_level=6)
    print('[ov] %s %dx%d %.1f MB' % (p, a.size, a.size, os.path.getsize(p) / 1e6))

    # ---- 叠加（色图 × 晕渲）
    cs = np.asarray(col.resize((a.size, a.size), Image.LANCZOS), np.float32)
    sh_s = np.asarray(hi_res.resize((a.size, a.size), Image.LANCZOS), np.float32)
    # 用晕渲的亮度当光照系数（保留色的饱和度）
    lum = sh_s.mean(2, keepdims=True) / max(1e-6, sh_s.mean())
    mix = np.clip(cs * np.clip(lum, 0.35, 1.6), 0, 255)
    img_s = draw_frame(to_img(mix), load_area(), world_rect)
    p = os.path.join(a.out, 'overview_shaded_full.png')
    img_s.save(p, 'PNG', compress_level=6)
    print('[ov] %s %dx%d %.1f MB' % (p, a.size, a.size, os.path.getsize(p) / 1e6))

    # ---- 只裁可玩区
    box = load_area()
    if box:
        bx0, by0, bx1, by1 = box
        # 在世界坐标里裁（正方形图边长 a.size）
        def crop_of(img):
            px = img.size[0] / (world_rect[2] - world_rect[0])
            return img.crop((int((bx0 - world_rect[0]) * px), int((world_rect[3] - by1) * px),
                             int((bx1 - world_rect[0]) * px), int((world_rect[3] - by0) * px)))
        for name, im in (('overview_height_map.png', img_h),
                         ('overview_color_map.png', img_c),
                         ('overview_shaded_map.png', img_s)):
            c = crop_of(im)
            c = c.resize((a.size, int(a.size * c.size[1] / c.size[0])), Image.LANCZOS)
            p = os.path.join(a.out, name)
            c.save(p, 'PNG', compress_level=6)
            print('[ov] %s %dx%d %.1f MB' % (p, c.size[0], c.size[1], os.path.getsize(p) / 1e6))

    meta = dict(world_origin=[X0, Y0], world_size_m=WORLD, res_m=RES,
                zmin=zmin, zmax=zmax, preview_px=a.size,
                map_area=box, src_color=os.path.relpath(COLOR, ROOT),
                src_height=os.path.relpath(H4, ROOT),
                note='full = 12296 m 正方形（含瓜玛/框外）；map = 只裁 map_area.json 的可玩区')
    json.dump(meta, open(os.path.join(a.out, 'meta.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('[ov] meta → %s' % os.path.join(a.out, 'meta.json'))


if __name__ == '__main__':
    main()
