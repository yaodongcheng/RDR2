# -*- coding: utf-8 -*-
"""从 v23 清单画「全图分类图」+「无贴图覆盖图」，用于快速审计错分。

    python tools/_probe_class_map.py [--manifest <jsonl>] [--out <dir>]

产物：
  audit_classes.png   按分类着色（默认隐藏类画成浅灰）
  audit_noalbedo.png  同上，但「无可用 albedo」的对象用红框标出
  audit_legend.json   颜色/类名/对象数
  audit_noalbedo.csv  无贴图对象清单（名字/类/坐标/地块/贴图/原因）
"""
import argparse
import collections
import csv
import json
import os

from PIL import Image, ImageDraw

ROOT = r'D:/BrainMaker/大镖客2解包分析'
MANIFEST = os.path.join(ROOT, 'deliverable/blender/continent/manifest_continent_v23.jsonl')
OUT = os.path.join(ROOT, 'export/world/audit')

# 世界范围（与 H4 一致）
X0, Y0, RES = -7684.0, -8196.0, 4.0
W = int((4612.0 - X0) / RES) + 1
H = int((4100.0 - Y0) / RES) + 1

COLORS = {
    'prop': (78, 121, 167), 'part': (242, 142, 43), 'junk': (225, 87, 89),
    'rock': (118, 183, 178), 'bldg': (89, 161, 79), 'struct': (237, 201, 72),
    'veh': (176, 122, 161), 'rail': (255, 157, 167), 'unknown': (156, 117, 95),
    'decal': (186, 176, 172),
    'lod': (205, 205, 205), 'terrain_cell': (225, 225, 225),
    'underground': (190, 190, 190), 'watertile': (170, 190, 210),
    'placeholder': (210, 170, 210), 'veg': (140, 190, 140), 'stone': (170, 170, 170),
    'light': (255, 255, 255), 'terrain': (240, 240, 240), 'water': (120, 160, 200),
}
HIDDEN = {'lod', 'terrain_cell', 'underground', 'watertile', 'placeholder', 'veg', 'stone'}


def px(x, y):
    return ((x - X0) / RES, (4100.0 - y) / RES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', default=MANIFEST)
    ap.add_argument('--out', default=OUT)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    import numpy as np
    d = json.load(open(os.path.join(ROOT, 'work/needed_tex_names.json'), encoding='utf-8'))
    have = set(d['have'])

    img = Image.new('RGB', (W, H), (250, 250, 248))
    draw = ImageDraw.Draw(img)
    img2 = Image.new('RGB', (W, H), (250, 250, 248))
    draw2 = ImageDraw.Draw(img2)

    cnt = collections.Counter()
    rows = []
    with open(a.manifest, encoding='utf-8') as f:
        for line in f:
            o = json.loads(line)
            if '_meta' in o:
                continue
            k = o.get('c') or 'unknown'
            cnt[k] += 1
            p = o.get('p') or [0, 0, 0]
            bb = o.get('bb')
            col = COLORS.get(k, (255, 0, 255))
            if k in HIDDEN:
                col = tuple(min(255, int(c * 0.35 + 255 * 0.65)) for c in col)
            noalb = not any(t in have for t in (o.get('t') or []))
            if bb:
                cx = (bb[0] + bb[3]) / 2
                cy = (bb[1] + bb[4]) / 2
                local = abs(cx - p[0]) > 50 or abs(cy - p[1]) > 50
            else:
                local = True
            if bb and not local:
                x0, y0 = px(bb[0], bb[4])
                x1, y1 = px(bb[3], bb[1])
                if x1 < x0:
                    x0, x1 = x1, x0
                if y1 < y0:
                    y0, y1 = y1, y0
                r = (x0, y0, max(x0 + 1, x1), max(y0 + 1, y1))
                draw.rectangle(r, fill=col)
                draw2.rectangle(r, fill=col)
                if noalb:
                    draw2.rectangle(r, outline=(220, 0, 0), width=1)
            else:
                x, y = px(p[0], p[1])
                r = (x - 3, y - 3, x + 3, y + 3)
                draw.rectangle(r, fill=col)
                draw2.rectangle(r, fill=col)
                if noalb:
                    draw2.rectangle((x - 5, y - 5, x + 5, y + 5), outline=(220, 0, 0), width=1)
            if noalb:
                rows.append([o.get('n'), k, round(p[0], 1), round(p[1], 1), o.get('tid') or '',
                             '|'.join(o.get('t') or []), 'no_slot' if not o.get('t') else 'name_missing_img'])

    img.save(os.path.join(a.out, 'audit_classes.png'))
    img2.save(os.path.join(a.out, 'audit_noalbedo.png'))
    json.dump({'colors': COLORS, 'counts': cnt, 'size': [W, H], 'res_m': RES},
              open(os.path.join(a.out, 'audit_legend.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    with open(os.path.join(a.out, 'audit_noalbedo.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['name', 'class', 'x', 'y', 'tile', 'textures', 'reason'])
        w.writerows(rows)
    print('[map] %s  %dx%d  classes=%s  no_albedo=%d'
          % (a.out, W, H, dict(cnt), len(rows)))


if __name__ == '__main__':
    main()
