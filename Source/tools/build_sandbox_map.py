"""给"权力的游戏开场风格"沙盒大地图烘焙底图：高度 + 地面彩图 + 据点摆放表。

为什么不让网页自己读原始数据
  原始高度图 2 692×2 006、地面彩图 12 296²（213 MB），网页加载会很慢。
  这里一次性降采样成"够看"的尺寸，网页只读 3 个小文件。

产物（deliverable/miniatures/map/data/）
  terrain.i16       384×286 int16 高度（真实米）
  terrain_color.jpg 1024×763 地面彩图（压暗/去饱和，配暗色桌面）
  map.json          地理范围、高程范围
  settlements.js    46 个据点的世界坐标 / 朝向 / 成品尺寸
"""
import os
import json
import csv
import numpy as np
from PIL import Image, ImageEnhance

ROOT = r'D:/BrainMaker/大镖客2解包分析'
HEIGHT_RAW = os.path.join(ROOT, 'deliverable/heightmap/continent_height_r16.raw')
HEIGHT_META = os.path.join(ROOT, 'deliverable/heightmap/continent_height_meta.json')
GROUND = os.path.join(ROOT, 'export/world/world_ground_final.png')
GROUND2 = os.path.join(ROOT, 'export/world/world_color_4096.png')
SETTLE = os.path.join(ROOT, 'deliverable/handoff/settlements_world_v2.csv')
AUDIT = os.path.join(ROOT, 'deliverable/miniatures/audit.json')
OUT = os.path.join(ROOT, 'deliverable/miniatures/map/data')

W, H = 384, 286          # 地形网格（≈28 m 一格，1/29 后 ≈1 m 一格）
MAP_SCALE = 1.0 / 29.0


def main():
    os.makedirs(OUT, exist_ok=True)
    meta = json.load(open(HEIGHT_META, encoding='utf-8'))
    hm = meta['heightmap']
    x0, x1, y0, y1 = meta['x0'], meta['x1'], meta['y0'], meta['y1']
    hw, hh = hm['w'], hm['h']
    zmin, zmax = hm['zmin'], hm['zmax']

    raw = np.fromfile(HEIGHT_RAW, dtype='<u2').reshape(hh, hw).astype(np.float32)
    z = zmin + raw / 65535.0 * (zmax - zmin)

    # 双线性采样到 W×H
    out = np.zeros((H, W), np.float32)
    for i in range(H):
        gy = (y1 - (y0 + (y1 - y0) * i / (H - 1))) / 4.0
        for j in range(W):
            gx = (x0 + (x1 - x0) * j / (W - 1) - meta['x0']) / 4.0
            gx = min(max(int(gx), 0), hw - 1)
            gyv = min(max(int(gy), 0), hh - 1)
            out[i, j] = z[gyv, gx]

    out.astype('<i2').tofile(os.path.join(OUT, 'terrain.i16'))

    # 地面彩图：12 296² 太大，按 8 倍块降采样后再 resize
    color = None
    if os.path.exists(GROUND):
        try:
            im = Image.open(GROUND).convert('RGB')
            # px = x + 7684, py = 4100 - y
            px0, px1 = int(x0 + 7684), int(x1 + 7684)
            py0, py1 = int(4100 - y1), int(4100 - y0)
            crop = im.crop((max(0, px0), max(0, py0), min(im.width, px1), min(im.height, py1)))
            crop = crop.resize((1024, int(1024 * H / W)), Image.LANCZOS)
            color = crop
            print('ground from world_ground_final', im.size, '->', crop.size)
        except Exception as e:
            print('ground fail', e)
    if color is None and os.path.exists(GROUND2):
        im = Image.open(GROUND2).convert('RGB')
        color = im.resize((1024, int(1024 * H / W)), Image.LANCZOS)
        print('ground from world_color_4096', im.size)

    if color is not None:
        color = ImageEnhance.Color(color).enhance(0.72)
        color = ImageEnhance.Brightness(color).enhance(0.86)
        color = ImageEnhance.Contrast(color).enhance(1.12)
        color.save(os.path.join(OUT, 'terrain_color.jpg'), quality=88, optimize=True)

    json.dump({'x0': x0, 'x1': x1, 'y0': y0, 'y1': y1, 'w': W, 'h': H,
               'zmin': float(out.min()), 'zmax': float(out.max()),
               'scale': MAP_SCALE},
              open(os.path.join(OUT, 'map.json'), 'w', encoding='utf-8'), indent=1)

    # 据点摆放表
    audit = {r['code']: r for r in json.load(open(AUDIT, encoding='utf-8'))}
    rows = []
    with open(SETTLE, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if not r['code'] or r['code'] not in audit:
                continue
            x, y = float(r['world_x']), float(r['world_y'])
            col = int((x - x0) / (x1 - x0) * (W - 1))
            row = int((y1 - y) / (y1 - y0) * (H - 1))
            col = min(max(col, 0), W - 1)
            row = min(max(row, 0), H - 1)
            rows.append({
                'code': r['code'], 'zh': r['name_zh'], 'en': r['name_en'],
                'type': r['btype'], 'faction': r['faction'],
                'x': round(x, 1), 'y': round(y, 1),
                'z': round(float(out[row, col]), 1),
                'w': audit[r['code']]['size_x'], 'd': audit[r['code']]['size_z'],
                'tris': audit[r['code']]['tris'],
            })
    with open(os.path.join(OUT, 'settlements.js'), 'w', encoding='utf-8') as f:
        f.write('window.SETTLEMENTS=')
        json.dump(rows, f, ensure_ascii=False)
        f.write(';\n')
    print(f'{len(rows)} 个据点 → settlements.js')


if __name__ == '__main__':
    main()
