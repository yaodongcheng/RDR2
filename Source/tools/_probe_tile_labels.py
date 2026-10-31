# -*- coding: utf-8 -*-
"""把地块编号画到整图俯视底图上（编号 = 排序后的 1..N，旁边附 tile id 与对象数）。

    python tools/_probe_tile_labels.py --img <俯视图.png> [--out <带编号.png>]

产物：带编号图 + `tile_legend.csv`
"""
import argparse
import collections
import csv
import json
import os
import re

from PIL import Image, ImageDraw, ImageFont

ROOT = r'D:/BrainMaker/大镖客2解包分析'
MANIFEST = os.path.join(ROOT, 'deliverable/blender/continent/manifest_continent_v23.jsonl')
X0, X1, Y0, Y1 = -7684.0, 4612.0, -8196.0, 4100.0


def font(size, bold=False):
    for p in (r'C:/Windows/Fonts/msyhbd.ttc' if bold else r'C:/Windows/Fonts/msyh.ttc',
              r'C:/Windows/Fonts/arialbd.ttf' if bold else r'C:/Windows/Fonts/arial.ttf'):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--img', default=os.path.join(ROOT, 'deliverable/blender/regions_support/continent_top.png'))
    ap.add_argument('--manifest', default=MANIFEST)
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    out = a.out or a.img.replace('.png', '_labeled.png')

    tiles = collections.defaultdict(lambda: [1e18, 1e18, -1e18, -1e18, 0])
    with open(a.manifest, encoding='utf-8') as f:
        for line in f:
            o = json.loads(line)
            if '_meta' in o:
                continue
            t, p = o.get('tid'), o.get('p')
            if not t or not p:
                continue
            e = tiles[t]
            e[0] = min(e[0], p[0]); e[1] = min(e[1], p[1])
            e[2] = max(e[2], p[0]); e[3] = max(e[3], p[1]); e[4] += 1

    def key(t):
        # 编号按「从上到下、从左到右」数：wild2000_<列>_<行>
        m = re.match(r'wild2000_(\d+)_(\d+)', t)
        return (int(m.group(2)), int(m.group(1))) if m else (99, 99, t)

    ids = sorted(tiles, key=key)
    idx = {t: i for i, t in enumerate(ids, 1)}

    im = Image.open(a.img).convert('RGBA')
    W, H = im.size

    def px(x, y):
        return ((x - X0) / (X1 - X0) * W, (Y1 - y) / (Y1 - Y0) * H)

    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    # 2000 m 网格线
    for gx in range(int(X0), int(X1) + 1, 2000):
        p = px(gx, Y1)
        d.line([(p[0], 0), (p[0], H)], fill=(255, 255, 255, 60), width=1)
    for gy in range(int(Y0), int(Y1) + 1, 2000):
        p = px(X0, gy)
        d.line([(0, p[1]), (W, p[1])], fill=(255, 255, 255, 60), width=1)

    f_big = font(max(14, W // 150), bold=True)
    f_small = font(max(9, W // 320))
    for t in ids:
        x0, y0, x1, y1, n = tiles[t]
        p0 = px(x0, y1)
        p1 = px(x1, y0)
        d.rectangle([p0, p1], outline=(255, 255, 255, 150), width=max(1, W // 2000))
        cx, cy = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        big = '#%d' % idx[t]
        small = t.replace('wild2000_', '')
        cnt = '{:,}'.format(n)
        bw = max(d.textlength(big, font=f_big), d.textlength(small, font=f_small),
                 d.textlength(cnt, font=f_small)) + 8
        bh = (f_big.size + 2 * f_small.size) + 10
        box = [cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2]
        d.rounded_rectangle(box, radius=4, fill=(0, 0, 0, 165))
        d.text((cx, box[1] + 2), big, font=f_big, fill=(255, 235, 120, 255), anchor='ma')
        d.text((cx, box[1] + f_big.size + 4), small, font=f_small, fill=(255, 255, 255, 230), anchor='ma')
        d.text((cx, box[1] + f_big.size + f_small.size + 6), cnt, font=f_small,
               fill=(190, 220, 255, 230), anchor='ma')

    Image.alpha_composite(im, ov).convert('RGB').save(out)
    with open(os.path.join(os.path.dirname(out), 'tile_legend.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['number', 'tile_id', 'objects', 'x0', 'y0', 'x1', 'y1'])
        for t in ids:
            e = tiles[t]
            w.writerow([idx[t], t, e[4]] + [round(v, 1) for v in e[:4]])
    print('[labels] %s  tiles=%d  legend=%s' % (out, len(ids), os.path.dirname(out)))


if __name__ == '__main__':
    main()
