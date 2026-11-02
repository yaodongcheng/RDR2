# -*- coding: utf-8 -*-
"""把地形（高程 / 材质色图）**对齐到官方地图图片的像素框**，产出可直接叠图的两张图。

两套参照：

1. **大陆** —— 有配准（`地图下载/配准结果.json`，5 个控制点，RMS 1.9 px）。
   官方地图内容框 = `大陆地图_缩略.jpg`(5000×3916) 上的 (146,388)-(4804,3851)，
   对应世界矩形见 `export/world/map_area.json`。已验证：世界(2555,-1151)=圣丹尼斯
   正好落在缩略图的 "SAINT DENIS" 上。

2. **瓜玛** —— 🔴 官方地图（`瓜玛岛.jpg`，4556×5678）**没有配准数据**，而且它是手绘风的
   美术地图（纸边 + 示意海岸线），不能靠轮廓自动对齐。需要人工给 2 个以上对应点：

       python tools/make_map_aligned_terrain.py --guarma-pts "px,py,wx,wy;px,py,wx,wy"

   点怎么取：先跑 `--guarma-grid`，它会生成一张带像素坐标网格的瓜玛地图，
   你在地图上读出「阿瓜多切斯」和「瓜玛营」的像素坐标（世界坐标已知：
   阿瓜多切斯 (1364.0, -6992.5) / 瓜玛营 (1426.3, -7328.9)，见
   `deliverable/handoff/settlements_world.csv`）。

产物（`deliverable/terrain/on_map/`）：

    mainland_height.png / mainland_color.png   裁到官方地图内容框，直接叠图（同像素网格）
    mainland_overlay.png                       50% 叠在官方缩略图上（自检对齐）
    guarma_height.png / guarma_color.png / guarma_overlay.png   （给了控制点才出）
    meta.json                                  各图的像素↔世界换算
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = r'D:/BrainMaker/大镖客2解包分析'
H4 = os.path.join(ROOT, 'raw/terrain/H4.npy')
COLOR = os.path.join(ROOT, 'export/world/world_ground_final.png')
MAPDIR = os.path.join(ROOT, '地图下载')
OUT = os.path.join(ROOT, 'deliverable/terrain/on_map')

X0w, Y0w, WORLD, SCALE, YM1, RES = -7684.0, -8196.0, 12296.0, 14.5, 4100.0, 4.0
MAP_PX = (146, 388, 4804, 3851)      # 缩略图上的地图内容框
MAP_PX_FULL = (5000, 3916)


# ---------------------------------------------------------------- 世界 ↔ 图
def load_fit():
    return json.load(open(os.path.join(MAPDIR, '配准结果.json'), encoding='utf-8'))


def m2w(mx, my, fit):
    """1400 宽图上的像素 → 世界坐标"""
    a, c, tx, ty = fit['a'], fit['c'], fit['tx'], fit['ty']
    px, py = mx - tx, my - ty
    det = a * a + c * c
    u = (a * px + c * py) / det
    v = (-c * px + a * py) / det
    return X0w + u * SCALE, YM1 - v * SCALE


def w2m(x, y, fit):
    """世界坐标 → 1400 宽图上的像素"""
    a, c, tx, ty = fit['a'], fit['c'], fit['tx'], fit['ty']
    u = (x - X0w) / SCALE
    v = (YM1 - y) / SCALE
    px = a * u - c * v
    py = c * u + a * v
    return px + tx, py + ty


def mainland_rect(fit):
    """官方地图内容框（缩略 px）→ 世界矩形 + 每像素米数。"""
    k = 1400.0 / MAP_PX_FULL[0]
    x0, y0, x1, y1 = MAP_PX
    xs, ys = [], []
    for X in (x0, x1):
        for Y in (y0, y1):
            wx, wy = m2w(X * k, Y * k, fit)
            xs.append(wx)
            ys.append(wy)
    W = dict(x0=min(xs), x1=max(xs), y0=min(ys), y1=max(ys))
    W['m_per_px'] = (W['x1'] - W['x0']) / (x1 - x0)
    return W


# ---------------------------------------------------------------- 采样
def sample_height(world_rect, w, h):
    H = np.load(H4).astype(np.float32)
    ny, nx = H.shape
    xs = np.linspace(world_rect['x0'], world_rect['x1'], w)
    ys = np.linspace(world_rect['y1'], world_rect['y0'], h)     # 行 0 = 北
    ci = np.clip(((xs - X0w) / RES).astype(np.int32), 0, nx - 1)
    ri = np.clip(((ys - Y0w) / RES).astype(np.int32), 0, ny - 1)
    z = H[np.ix_(ri, ci)]
    zmin, zmax = float(np.nanmin(H)), float(np.nanmax(H))
    g = np.clip((z - zmin) / max(1e-6, zmax - zmin) * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(g, 'L').convert('RGB'), (zmin, zmax)


def sample_color(world_rect, w, h, src=None):
    im = Image.open(src or COLOR).convert('RGB')
    cw, ch = im.size
    box = ((world_rect['x0'] - X0w) / WORLD * cw, (YM1 - world_rect['y1']) / WORLD * ch,
           (world_rect['x1'] - X0w) / WORLD * cw, (YM1 - world_rect['y0']) / WORLD * ch)
    return im.crop(tuple(int(round(v)) for v in box)).resize((w, h), Image.LANCZOS)


def overlay(base_img, ours, box, alpha=0.5, title=''):
    """把我们的图按 box=(l,t,r,b) 半透明叠到官方地图上（自检对齐用）。"""
    b = base_img.convert('RGB').copy()
    layer = ours.convert('RGB').resize((box[2] - box[0], box[3] - box[1]), Image.LANCZOS)
    a = np.asarray(layer, np.float32)
    sub = np.asarray(b.crop(box), np.float32)
    b.paste(Image.fromarray((sub * (1 - alpha) + a * alpha).astype(np.uint8), 'RGB'), box[:2])
    return b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--scale', type=float, default=1.0,
                    help='输出相对官方内容框的倍数（1 = 4658×3463，2 = 两倍）')
    ap.add_argument('--guarma-pts', default='', help='"px,py,wx,wy;…" 瓜玛对应点')
    ap.add_argument('--color', default=COLOR,
                    help='材质彩图来源（默认 world_ground_final.png；'
                         '补全版用 deliverable/terrain/tiles/color_completed_1pxm.png）')
    ap.add_argument('--guarma-grid', action='store_true', help='只生成带坐标网格的瓜玛地图')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    meta = {}

    # ---------- 瓜玛标点辅助图
    if a.guarma_grid or not a.guarma_pts:
        g = Image.open(os.path.join(MAPDIR, '瓜玛岛.jpg')).convert('RGB')
        from PIL import ImageDraw
        d = ImageDraw.Draw(g)
        step = 200
        for x in range(0, g.size[0], step):
            d.line([(x, 0), (x, g.size[1])], fill=(200, 60, 60), width=2)
            d.text((x + 4, 6), str(x), fill=(200, 30, 30))
        for y in range(0, g.size[1], step):
            d.line([(0, y), (g.size[0], y)], fill=(200, 60, 60), width=2)
            d.text((6, y + 2), str(y), fill=(200, 30, 30))
        p = os.path.join(a.out, 'guarma_grid.png')
        g.save(p, 'PNG')
        print('[map] 瓜玛网格图 → %s（读点用：像素坐标已标在格线上）' % p)

    # ---------- 大陆
    fit = load_fit()
    R = mainland_rect(fit)
    W = int(round((MAP_PX[2] - MAP_PX[0]) * a.scale))
    Hh = int(round((MAP_PX[3] - MAP_PX[1]) * a.scale))
    print('[map] 大陆内容框 %dx%d px，世界 %.0f..%.0f / %.0f..%.0f（%.3f m/px）'
          % (W, Hh, R['x0'], R['x1'], R['y0'], R['y1'], R['m_per_px'] / a.scale))
    h_img, zr = sample_height(R, W, Hh)
    c_img = sample_color(R, W, Hh, a.color)
    h_img.save(os.path.join(a.out, 'mainland_height.png'), 'PNG')
    c_img.save(os.path.join(a.out, 'mainland_color.png'), 'PNG')
    base = Image.open(os.path.join(MAPDIR, '大陆地图_缩略.jpg')).convert('RGB')
    if a.scale != 1.0:
        base = base.resize((int(base.size[0] * a.scale), int(base.size[1] * a.scale)), Image.LANCZOS)
    box = tuple(int(round(v * a.scale)) for v in MAP_PX)
    overlay(base, c_img, box, 0.5).save(os.path.join(a.out, 'mainland_overlay.png'), 'PNG')
    meta['mainland'] = dict(world=R, canvas_px=[W, Hh], paste_box_px=list(box),
                            src_map='地图下载/大陆地图_缩略.jpg', map_px=MAP_PX,
                            zmin=zr[0], zmax=zr[1],
                            note='height = 线性灰度(0=zmin,255=zmax)；color = 原始材质色图')
    print('[map] 大陆：mainland_{height,color,overlay}.png')

    # ---------- 瓜玛（需要控制点）
    if a.guarma_pts:
        pts = []
        for tok in a.guarma_pts.split(';'):
            if not tok.strip():
                continue
            px, py, wx, wy = [float(v) for v in tok.split(',')]
            pts.append((px, py, wx, wy))
        if len(pts) < 2:
            print('[map] 瓜玛控制点不足 2 个，跳过')
        else:
            # 最小二乘：世界 = s*像素 + t（等比、不旋转）
            P = np.array([[p[0], p[1], 1.0] for p in pts])
            Xw = np.array([p[2] for p in pts])
            Yw = np.array([p[3] for p in pts])
            sx = np.linalg.lstsq(P, Xw, rcond=None)[0]
            sy = np.linalg.lstsq(P, Yw, rcond=None)[0]
            s = (abs(sx[0]) + abs(sy[1])) / 2.0
            print('[map] 瓜玛拟合：s≈%.4f m/px  残差 x%.1f y%.1f m'
                  % (s, float(np.abs(P @ sx - Xw).max()), float(np.abs(P @ sy - Yw).max())))
            g = Image.open(os.path.join(MAPDIR, '瓜玛岛.jpg')).convert('RGB')
            px0, py0 = 0, 0
            px1, py1 = g.size
            Gw = dict(x0=sx[0] * px0 + sx[1] * py0 + sx[2], x1=sx[0] * px1 + sx[1] * py1 + sx[2],
                      y0=sy[0] * px0 + sy[1] * py1 + sy[2], y1=sy[0] * px1 + sy[1] * py0 + sy[2],
                      m_per_px=abs(s))
            Gw['x0'], Gw['x1'] = min(Gw['x0'], Gw['x1']), max(Gw['x0'], Gw['x1'])
            Gw['y0'], Gw['y1'] = min(Gw['y0'], Gw['y1']), max(Gw['y0'], Gw['y1'])
            gw, gh = g.size
            gh_img, _ = sample_height(Gw, gw, gh)
            gc_img = sample_color(Gw, gw, gh, a.color)
            gh_img.save(os.path.join(a.out, 'guarma_height.png'), 'PNG')
            gc_img.save(os.path.join(a.out, 'guarma_color.png'), 'PNG')
            overlay(g, gc_img, (0, 0, gw, gh), 0.5).save(os.path.join(a.out, 'guarma_overlay.png'), 'PNG')
            meta['guarma'] = dict(world=Gw, canvas_px=[gw, gh], pts=pts,
                                  src_map='地图下载/瓜玛岛.jpg',
                                  note='按用户给的对应点做等比+平移拟合（无旋转）')
            print('[map] 瓜玛：guarma_{height,color,overlay}.png')
    else:
        print('[map] 瓜玛未给控制点 → 先看 guarma_grid.png 取点，再用 --guarma-pts 重跑')

    json.dump(meta, open(os.path.join(a.out, 'meta.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('[map] meta → %s' % os.path.join(a.out, 'meta.json'))


if __name__ == '__main__':
    main()
