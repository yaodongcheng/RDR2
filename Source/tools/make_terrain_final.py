# -*- coding: utf-8 -*-
"""⚠️ 2026-11-08 已停用（保留代码仅作历史参考）。

`deliverable/terrain/final/` 已改名 `deliverable/terrain/scene_native/`
（它只放**子场景原生 H4**，不是"最终地形"）；彩图归 `deliverable/terrain/color_1m.png`。
本脚本会重建旧 `final/` 并拷入弃用的 `heightmap/continent_height_4m.png`，**不要再用**。

现行生成链：
  · 子场景原生高度 = `tools/build_scene_heightmap_native.py`
  · 三个大地图模式 + 唯一彩图 = `tools/make_terrain_stages.py` / `tools/carve_rivers.py`
"""
import json
import os
import shutil

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = r'D:/BrainMaker/大镖客2解包分析'
H_PNG = os.path.join(ROOT, 'deliverable/heightmap/continent_height_4m.png')
H_META = os.path.join(ROOT, 'deliverable/heightmap/continent_height_meta.json')
COLOR = os.path.join(ROOT, 'export/world/world_ground_final_out.png')
OUT = os.path.join(ROOT, 'deliverable/terrain/final')

X0w, Y0w, WORLD, YM1 = -7684.0, -8196.0, 12296.0, 4100.0


def main():
    raise SystemExit(
        'make_terrain_final.py 已停用（2026-11-08）：'
        'terrain/final/ 已改名 terrain/scene_native/，彩图归 terrain/color_1m.png。\n'
        '  子场景高度 → tools/build_scene_heightmap_native.py\n'
        '  三个大地图模式 + 彩图 → tools/make_terrain_stages.py / tools/carve_rivers.py'
    )
    os.makedirs(OUT, exist_ok=True)
    meta = json.load(open(H_META, encoding='utf-8'))
    x0, y0, x1, y1 = meta['x0'], meta['y0'], meta['x1'], meta['y1']

    # 1) 高度：原样拷贝（就是喂给骑砍2 的那张）
    shutil.copy2(H_PNG, os.path.join(OUT, 'height_4m_16bit.png'))
    shutil.copy2(H_META, os.path.join(OUT, 'height_meta.json'))
    hw, hh = meta['size_px']

    # 2) 彩图：从补全版裁到同一世界框，1 m/px
    cw = int(round(x1 - x0))
    ch = int(round(y1 - y0))
    im = Image.open(COLOR).convert('RGB')
    box = (int(round(x0 - X0w)), int(round(YM1 - y1)),
           int(round(x0 - X0w)) + cw, int(round(YM1 - y1)) + ch)
    im.crop(box).save(os.path.join(OUT, 'color_1m.png'), 'PNG', compress_level=6)
    print('[final] color %dx%d ← %s  裁框 %s' % (cw, ch, os.path.basename(COLOR), box))

    json.dump(dict(
        world=dict(x0=x0, y0=y0, x1=x1, y1=y1, size_m=[x1 - x0, y1 - y0]),
        row0='north', col0='west',
        height=dict(file='height_4m_16bit.png', px=[hw, hh], m_per_px=meta['res_m'],
                    zmin=meta['heightmap'].get('zmin'), zmax=meta['heightmap'].get('zmax'),
                    note='16bit 灰度；值 = (z-zmin)/(zmax-zmin)*65535'),
        color=dict(file='color_1m.png', px=[cw, ch], m_per_px=1.0,
                   src='export/world/world_ground_final_out.png（含 terrain/outskirts 外延补全）'),
        note='两张图同一世界框、同一朝向；彩图 1 m/px 与高度 4 m/px 恰好 4:1 对齐',
    ), open(os.path.join(OUT, 'meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for f in sorted(os.listdir(OUT)):
        print('  %-22s %.1f MB' % (f, os.path.getsize(os.path.join(OUT, f)) / 1e6))


if __name__ == '__main__':
    main()
