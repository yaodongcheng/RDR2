# -*- coding: utf-8 -*-
"""给 terrain/stages/ 出对比图：两级并排（高度/彩图）+ 逐级差量。

    python tools/make_terrain_stage_compare.py

2026-11-02：管线只剩 00_raw / 01_plateau_plain 两级（「水域加深」「统一水位修正」都去掉了）。
"""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None
ROOT = r'D:/BrainMaker/大镖客2解包分析'
ST = os.path.join(ROOT, 'deliverable/terrain/stages')
OUT = os.path.join(ST, '_compare')
STAGES = ['00_raw', '01_plateau_plain']
LABEL = {'00_raw': '0 原始', '01_plateau_plain': '1 高原/平原'}
W = 1000          # 每格宽度


def load_h(p):
    m = json.load(open(os.path.join(os.path.dirname(p), 'meta.json'), encoding='utf-8'))
    z = m['height']
    q = np.asarray(Image.open(p), np.uint16).astype(np.float32)
    return z['zmin'] + q / 65535.0 * (z['zmax'] - z['zmin'])


def _font(size=22):
    """中文标签要 CJK 字体，PIL 默认位图字体画出来是方框。"""
    for p in (r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf',
              r'C:\Windows\Fonts\arial.ttf'):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return None


FONT = _font(22)
FONT_S = _font(18)


def sheet(items, out, cmap=None, title=''):
    ims = []
    for name, im in items:
        h = int(W * im.size[1] / im.size[0])
        im = im.convert('RGB').resize((W, h), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, W - 1, 32], fill=(0, 0, 0))
        d.text((8, 5), LABEL.get(name, name), fill=(255, 255, 255), font=FONT)
        ims.append(im)
    H = max(i.size[1] for i in ims)
    pad = 30 if title else 0
    s = Image.new('RGB', (W * len(ims), H + pad), (20, 20, 20))
    for i, im in enumerate(ims):
        s.paste(im, (i * W, 0))
    if title:
        ImageDraw.Draw(s).text((8, H + 4), title, fill=(255, 255, 255), font=FONT_S)
    s.save(out, 'PNG', compress_level=6)
    print('[cmp] %s %dx%d' % (out, s.size[0], s.size[1]))


def gray(z):
    z0, z1 = float(z.min()), float(z.max())
    g = np.clip((z - z0) / max(1e-6, z1 - z0) * 255, 0, 255).astype(np.uint8)
    return Image.fromarray(g, 'L')


def main():
    os.makedirs(OUT, exist_ok=True)
    Z = {s: load_h(os.path.join(ST, s, 'height_16bit_4m.png')) for s in STAGES}
    sheet([(s, gray(Z[s])) for s in STAGES], os.path.join(OUT, 'stages_height.png'),
          title='高度（黑=低 白=高，同一套线性归一化，未分级）')
    sheet([(s, Image.open(os.path.join(ST, s, 'color_1m.png'))) for s in STAGES],
          os.path.join(OUT, 'stages_color.png'), title='地形材质图（第 1 级只重上色被改动过的区域）')

    # 逐级差量（抬升=红 / 下挖=蓝）
    diffs = []
    for a, b in zip(STAGES, STAGES[1:]):
        d = Z[b] - Z[a]
        rgb = np.zeros(d.shape + (3,), np.uint8)
        pos = np.clip(d / 50.0, 0, 1); neg = np.clip(-d / 50.0, 0, 1)
        rgb[..., 0] = (pos * 255).astype(np.uint8)
        rgb[..., 2] = (neg * 255).astype(np.uint8)
        rgb[..., 1] = ((1 - pos - neg).clip(0, 1) * 90).astype(np.uint8)
        diffs.append((b, Image.fromarray(rgb, 'RGB')))
    sheet(diffs, os.path.join(OUT, 'diff_00_01.png'),
          title='差量：红=抬升 / 蓝=下挖（满量程 ±50 m）')


if __name__ == '__main__':
    main()
