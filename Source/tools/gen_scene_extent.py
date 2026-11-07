# -*- coding: utf-8 -*-
"""生成《场景边界》JSON：官方地图画面区 + 地形数据有效区（世界坐标）。

    python -X utf8 tools/gen_scene_extent.py

为什么要它：远景框（P 每边外扩）会**超出**这两个边界 —— 超出地图画面区 = 建到没有地图的地方；
超出地形数据区 = 采样只能取边缘值（假地面）。构建与预览都读这一份。

数据来源（现算，不落中间文件）：
  · 地图画面区：`deliverable/terrain/on_map/meta.json` 的缩略图 + 羊皮纸掩码（与 build_scene_division 同一套）
  · 地形数据区：`work/terrain/valid4.npy` 的有效网格 bbox
输出：`docs/世界与地编/scene_extent.json`（**生成物，禁止手改**）
"""
import json
import os

import numpy as np
from PIL import Image
from scipy.ndimage import (binary_closing, binary_fill_holes, binary_opening,
                           label, uniform_filter)

RDR2 = r'D:/BrainMaker/大镖客2解包分析'
SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(SRC, 'docs', '世界与地编', 'scene_extent.json')

X0, Y1, MPP = -6844.0, 3224.0, 4.0          # 与 build_scene_division.py 同一套
X0W, Y0W, RES = -7684.0, -8196.0, 4.0       # valid4 网格原点


def map_area_bbox():
    meta = json.load(open(os.path.join(RDR2, 'deliverable/terrain/on_map/meta.json'),
                          encoding='utf-8'))['mainland']
    mask = np.array(Image.open(os.path.join(RDR2, 'deliverable/heightmap/water_mask.png')))
    H, W = mask.shape
    thumb = np.asarray(Image.open(os.path.join(
        RDR2, meta['src_map'].replace('/', os.sep))).convert('RGB')).astype(np.float32)
    paper = np.array([210.0, 182.0, 143.0])
    g = thumb.mean(axis=2)
    mu = uniform_filter(g, 7)
    sd = np.sqrt(np.maximum(uniform_filter(g * g, 7) - mu * mu, 0))
    c = ~((sd < 3.0) & (np.abs(thumb - paper).max(axis=2) < 28))
    c = binary_opening(c, np.ones((3, 3)))
    c = binary_closing(c, np.ones((9, 9)))
    c = binary_fill_holes(c)
    lab, _ = label(c)
    sz = np.bincount(lab.ravel())
    sz[0] = 0
    c = lab == sz.argmax()
    bx0, by0, bx1, by1 = [float(v) for v in meta['paste_box_px']]
    uu = bx0 + (np.arange(W) + 0.5) / W * (bx1 - bx0)
    vv = by0 + (np.arange(H) + 0.5) / H * (by1 - by0)
    UU, VV = np.meshgrid(uu, vv)
    mm = c[np.clip(VV.astype(int), 0, c.shape[0] - 1), np.clip(UU.astype(int), 0, c.shape[1] - 1)]
    rows = np.where(mm.any(axis=1))[0]
    cols = np.where(mm.any(axis=0))[0]
    return [X0 + cols.min() * MPP, Y1 - (rows.max() + 1) * MPP,
            X0 + (cols.max() + 1) * MPP, Y1 - rows.min() * MPP]


def terrain_bbox():
    v = np.load(os.path.join(RDR2, 'work/terrain/valid4.npy'))
    rows = np.where(v.any(axis=1))[0]
    cols = np.where(v.any(axis=0))[0]
    return [X0W + cols.min() * RES, Y0W + (v.shape[0] - rows.max() - 1) * RES,
            X0W + (cols.max() + 1) * RES, Y0W + (v.shape[0] - rows.min()) * RES]


def main():
    d = {'map': [round(v, 1) for v in map_area_bbox()],
         'terrain': [round(v, 1) for v in terrain_bbox()],
         'note': '地图画面区 = 官方地图有画的那片；地形数据区 = H4 有效网格。远景框不得超出。'
                 ' 生成物，重跑 python -X utf8 tools/gen_scene_extent.py'}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print('map    x[%.0f, %.0f] y[%.0f, %.0f]' % tuple(d['map']))
    print('terrain x[%.0f, %.0f] y[%.0f, %.0f]' % tuple(d['terrain']))
    print('已写：%s' % OUT)


if __name__ == '__main__':
    main()
