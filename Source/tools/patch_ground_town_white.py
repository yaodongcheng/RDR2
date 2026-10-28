# -*- coding: utf-8 -*-
"""修「城区地面发白」：把地面色图里**城区内接近纯白（无数据）**的像素换成合成色图的值。

## 为什么会白（实测，不是猜）

`world_ground_final.png` 是把游戏地形瓦片的真色图 `<tile>_t`（2048²/512 m）按格子拼起来的。
RDR2 **城区的街面不是地形色图**——那块地面在游戏里由路面/人行道/场地模型盖住，
所以地形色图本身在城区就是一片接近纯白（实测圣丹尼斯 (2434,−1207) 处 **RGB 236,240,240**）。
我们的场景里网格之间有缝，露出来就是白地。

## 修法（只用已有数据，不发明颜色）

对 46 个据点框内、且**三通道都 > 0.85 且三通道极差 < 0.06**（=无数据白）的像素，
换成**已有合成色图** `world_color_4096.png` 的同位置颜色 × 0.88（压一点，和周边地形一致）。
合成色图本来就是本项目的地形底图（`blender_continent.py` 拿它做顶点色），
城区那圈本来就有既定的中性色调，所以这不是"猜颜色"，是把两套既有数据接上。

原图备份为 `world_ground_final_raw.png`（只备份一次，后续重跑都以 raw 为输入）。

    python tools/patch_ground_town_white.py --probe      # 只看统计
    python tools/patch_ground_town_white.py             # 就地修（先备份）
"""
import os
import csv
import json
import time
import shutil
import argparse

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = r'D:/BrainMaker/大镖客2解包分析'
GROUND = os.path.join(ROOT, 'export/world/world_ground_final.png')
GROUND_RAW = os.path.join(ROOT, 'export/world/world_ground_final_raw.png')
COLOR = os.path.join(ROOT, 'export/world/world_color_4096.png')
META = os.path.join(ROOT, 'export/world/world_meta.json')
SETTLE = os.path.join(ROOT, 'deliverable/handoff/settlements_world_v2.csv')
REPORT = os.path.join(ROOT, 'export/world/ground_town_patch_report.json')

X0, Y0, W = -7684.0, -8196.0, 12296.0


def spots():
    out = []
    if not os.path.exists(SETTLE):
        return out
    for s in csv.DictReader(open(SETTLE, encoding='utf-8-sig')):
        try:
            cx, cy = float(s['world_x']), float(s['world_y'])
            hw, hd = float(s['size_w_m']) / 2, float(s['size_d_m']) / 2
        except Exception:
            continue
        out.append((s['code'], cx, cy, hw, hd))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--probe', action='store_true')
    ap.add_argument('--thresh', type=float, default=0.85)
    ap.add_argument('--spread', type=float, default=0.06)
    ap.add_argument('--dim', type=float, default=0.88)
    a = ap.parse_args()

    src = GROUND_RAW if os.path.exists(GROUND_RAW) else GROUND
    print('[ground] 输入 %s（%.0f MB）' % (src, os.path.getsize(src) / 1e6))
    t0 = time.time()
    im = Image.open(src).convert('RGB')
    gw, gh = im.size
    print('[ground] 尺寸 %dx%d' % (gw, gh))
    g = np.asarray(im, dtype=np.uint8)
    print('[ground] 读入 %.0fs' % (time.time() - t0))

    col = np.asarray(Image.open(COLOR).convert('RGB').resize((gw, gh), Image.BILINEAR),
                     dtype=np.uint8)
    print('[ground] 合成色图对齐 %.0fs' % (time.time() - t0))

    gx = (np.arange(gw, dtype=np.float64) + 0.5) / gw * W + X0
    gy = Y0 + W - (np.arange(gh, dtype=np.float64) + 0.5) / gh * W

    near = (g.min(axis=2).astype(np.int16) > int(a.thresh * 255)) & \
           ((g.max(axis=2).astype(np.int16) - g.min(axis=2).astype(np.int16)) <
            int(a.spread * 255))
    print('[ground] 全图"无数据白"像素 %d（%.2f%%）'
          % (int(near.sum()), 100.0 * near.mean()))

    mask = np.zeros((gh, gw), bool)
    rows = []
    for code, cx, cy, hw, hd in spots():
        j0 = max(0, int((cx - hw - X0) / W * gw))
        j1 = min(gw, int((cx + hw - X0) / W * gw) + 1)
        i0 = max(0, int((Y0 + W - (cy + hd)) / W * gh))
        i1 = min(gh, int((Y0 + W - (cy - hd)) / W * gh) + 1)
        if j1 <= j0 or i1 <= i0:
            continue
        sub = near[i0:i1, j0:j1]
        n = int(sub.sum())
        tot = int(sub.size)
        mask[i0:i1, j0:j1] |= sub
        rows.append(dict(code=code, box_px=tot, white_px=n,
                         white_pct=round(100.0 * n / max(1, tot), 2)))
    rows.sort(key=lambda r: -r['white_px'])
    print('[ground] 据点框内"无数据白"合计 %d 像素' % int(mask.sum()))
    for r in rows[:8]:
        print('        %-5s 框内 %8d px，其中白 %7d（%.1f%%）'
              % (r['code'], r['box_px'], r['white_px'], r['white_pct']))

    if a.probe:
        print('[ground] probe，不写盘')
        return

    n = int(mask.sum())
    if n:
        repl = (col.astype(np.float32) * a.dim).clip(0, 255).astype(np.uint8)
        g2 = g.copy()
        g2[mask] = repl[mask]
        if not os.path.exists(GROUND_RAW):
            shutil.copy2(GROUND, GROUND_RAW)
            print('[ground] 原图备份 → %s' % os.path.basename(GROUND_RAW))
        Image.fromarray(g2).save(GROUND, 'PNG', optimize=True)
        print('[ground] 已替换 %d 像素，写回 %s（%.0f MB，%.0fs）'
              % (n, GROUND, os.path.getsize(GROUND) / 1e6, time.time() - t0))
    json.dump(dict(input=os.path.basename(src), replaced_px=n,
                   white_px_map=int(near.sum()), threshold=a.thresh,
                   spread=a.spread, dim=a.dim, per_settlement=rows),
              open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('[ground] 报告 %s' % REPORT)


if __name__ == '__main__':
    main()
