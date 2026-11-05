# -*- coding: utf-8 -*-
"""把模型库里「源格式本来有 alpha、导出却存成 RGB」的贴图补回 alpha。

## 背景（2026-11-05）

现象：`val_dcl_lockdown_saloon`（沙龙的枪战贴花束）在招牌上盖出一块块**灰方块**。
根因不是 Blender 不会处理 alpha，而是**模型库里的贴图 PNG 没有 alpha**：

    源格式（tex_name_index.json）  = 0x4E → DXT5/BC3（有 alpha）
    raw/lib_gtxd/txd_prev/*.png    = RGBA，透明像素 73%~90%（源是对的）
    assets/lib_native/tex/01824.png = **RGB**（导出时丢了 alpha）

模型库是 2026-10-28 建的，当时贴图池/索引还不是现在这一版；当前 `LazyTexLib` 解码
同样的名字会返回 RGBA。全库扫描：39,827 张里 **2,611 张**是「RGB 文件 + 源格式可带 alpha」。

## 做什么

对每张「库文件是 RGB、源格式是 DXT5/BC7 系」的贴图：
  1. 用当前 `LazyTexLib(maxs)` 重新解码；
  2. 解码结果是 RGBA、且 alpha<0.5 的像素 ≥2% → 覆盖写回库 PNG（同尺寸/同路径）；
  3. 否则跳过（源本来就不透明）。

**只改贴图文件，不碰网格/材质**。写完还要跑 `relink_materials.py` 给已建 blend
重挂材质（材质在创建时就把「有没有 alpha」决定死了，换图不会自动接线）。

## 用法

    python -X utf8 tools/refill_lib_tex_alpha.py --dry     # 只统计
    python -X utf8 tools/refill_lib_tex_alpha.py           # 真写

幂等：已经是 RGBA 的文件直接跳过；重复跑不会重复处理。
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

ROOT = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')
TEX_INDEX = os.path.join(ROOT, 'work/tex_name_index.json')

if os.path.join(ROOT, 'tools') not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, 'tools'))

ALPHA_FMT = (0x4C, 0x4D, 0x4E, 0x61, 0x62, 0x63)   # BC3 / BC7 系（可带 alpha）


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true', help='只统计，不写文件')
    ap.add_argument('--maxs', type=int, default=512, help='与建库时一致（默认 512）')
    ap.add_argument('--min-transparent', type=float, default=0.02,
                    help='alpha<0.5 的像素占比达到多少才算「真有透明」（默认 2%%）')
    a = ap.parse_args()

    from lazy_tex import LazyTexLib
    lib = LazyTexLib(a.maxs)
    idx = json.load(open(INDEX, encoding='utf-8'))['tex']
    ti = json.load(open(TEX_INDEX, encoding='utf-8'))

    cand = fixed = 0
    skipped_rgba = skipped_fmt = skipped_alpha = failed = 0
    for t in idx:
        p = os.path.join(LIB, t['f'])
        try:
            mode = Image.open(p).mode
        except Exception:
            failed += 1
            continue
        if mode == 'RGBA':
            skipped_rgba += 1
            continue
        e = ti.get(t['n']) or {}
        try:
            fmt = (int(e.get('fmt') or 0) >> 24) & 0xFF
        except Exception:
            fmt = -1
        if fmt not in ALPHA_FMT:
            skipped_fmt += 1
            continue
        cand += 1
        im, diag = lib.get(t['n'], None)
        if im is None or im.mode != 'RGBA':
            failed += 1
            continue
        al = np.asarray(im)[..., 3]
        if float((al < 128).mean()) < a.min_transparent:
            skipped_alpha += 1
            continue
        if not a.dry:
            im.save(p, 'PNG', optimize=True)
        fixed += 1
        if fixed <= 10:
            print('[alpha] %-52s %s  alpha<128 %.1f%%  (%s)'
                  % (t['n'][:50], 'DRY' if a.dry else 'WRITE',
                     float((al < 128).mean()) * 100, diag))

    print('[alpha] 候选 %d · 补写 %d · 已是 RGBA %d · 源格式无 alpha %d · 解出来仍不透明 %d · 失败 %d'
          % (cand, fixed, skipped_rgba, skipped_fmt, skipped_alpha, failed))
    if a.dry:
        print('[alpha] dry-run，没有写任何文件')


if __name__ == '__main__':
    main()
