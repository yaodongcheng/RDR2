# -*- coding: utf-8 -*-
"""给「地图框外」的场景生成地形源（高度 + 彩图 + meta）。

现有场景管线只认交付高度图/彩图的**地图框**（x[-6844,3924] y[-4800,3224]）；
瓜玛在框外（y≈-7000），所以单独从 H4.npy / world_ground_final_out.png 生成一套。

产物：`deliverable/terrain/outside/<id>/` 下
  height_16bit_4m.png   4 m/px，行 0 = 北，编码 zmin/zmax 与原版 H4 一致
  color_1m.png          1 m/px，从 world_ground_final_out.png 裁出
  meta.json             世界矩形 + 编码（scene_terrain_core.load_meta 会优先读它）

用法：
    python tools/make_outside_scene_terrain.py --id guarma --rect 240,-8196,2544,-6080
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ROOT = r'D:/BrainMaker/大镖客2解包分析'
H4 = os.path.join(ROOT, 'work/terrain/H4.npy')
GROUND = os.path.join(ROOT, 'export/world/world_ground_final_out.png')
OUTROOT = os.path.join(ROOT, 'deliverable/terrain/outside')

H4_X0, H4_Y0, RES = -7684.0, -8196.0, 4.0
ZMIN, ZMAX = -34.93079376220703, 690.3469848632812
GROUND_X0, GROUND_Y1 = -7684.0, 4100.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', required=True)
    ap.add_argument('--rect', required=True, help='x0,y0,x1,y1（世界米，far 矩形）')
    a = ap.parse_args()
    x0, y0, x1, y1 = [float(v) for v in a.rect.split(',')]
    out = os.path.join(OUTROOT, a.id)
    os.makedirs(out, exist_ok=True)

    # ---- 高度：从 H4 最近邻取值 ----
    H = np.load(H4)
    ny, nx = H.shape
    cols = ((x0 - H4_X0) / RES + np.arange(int(round((x1 - x0) / RES)))).astype(np.int32)
    rows = ((H4_Y0 + (ny - 1) * RES - y1) / RES + np.arange(int(round((y1 - y0) / RES)))).astype(np.int32)
    # H4 行 0 = 南：row = (y - Y0)/4 ；输出行 0 = 北
    rows = ((y1 - H4_Y0) / RES - np.arange(int(round((y1 - y0) / RES)))).astype(np.int32)
    cols = np.clip(cols, 0, nx - 1)
    rows = np.clip(rows, 0, ny - 1)
    z = H[np.ix_(rows, cols)].astype(np.float32)
    q = np.clip((z - ZMIN) / (ZMAX - ZMIN) * 65535.0, 0, 65535).astype('<u2')
    Image.fromarray(q).save(os.path.join(out, 'height_16bit_4m.png'))
    print('[outside] height %dx%d z %.1f..%.1f' % (q.shape[1], q.shape[0], z.min(), z.max()))

    # ---- 彩图：从 12296 全图彩图裁 1 m/px ----
    g = Image.open(GROUND).convert('RGB')
    box = (int(round(x0 - GROUND_X0)), int(round(GROUND_Y1 - y1)),
           int(round(x1 - GROUND_X0)), int(round(GROUND_Y1 - y0)))
    crop = g.crop(box)
    crop.save(os.path.join(out, 'color_1m.png'), compress_level=6)
    print('[outside] color %dx%d box=%s' % (crop.size[0], crop.size[1], box))

    meta = {
        'world': {'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1, 'size_m': [x1 - x0, y1 - y0]},
        'row0': 'north', 'col0': 'west',
        'height': {'file': 'height_16bit_4m.png', 'px': [q.shape[1], q.shape[0]],
                   'm_per_px': RES, 'zmin': ZMIN, 'zmax': ZMAX},
        'color': {'file': 'color_1m.png', 'px': [crop.size[0], crop.size[1]], 'm_per_px': 1.0},
        'note': '地图框外场景（%s）的地形源；由 tools/make_outside_scene_terrain.py 生成' % a.id,
    }
    json.dump(meta, open(os.path.join(out, 'meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('[outside] ->', out)


if __name__ == '__main__':
    main()
