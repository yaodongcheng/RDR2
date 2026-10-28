# -*- coding: utf-8 -*-
"""给 6106 件服饰批量出缩略图（96×144，透明底），供 `viewer/clothing.html` 显示。

为什么不用 Blender 逐件渲染：6106 件 × 1~2 s = 2~4 小时，不现实。
这里直接在 Python 里做**点云投影**：
  · `.ydd` 解析出顶点/法线（rdr2_npc_export.parse_ped，约 30 ms/件）
  · 正交投影到正面（x 横 / y 纵），顶点按 2×2 泼溅，再按法线做一次简单明暗
  · 颜色 = 该部件 albedo 贴图的平均色（带 alpha 加权），贴图解码结果按 (文件, entry) 缓存
效果：能看清"这件是什么形状、什么颜色"，不是精修渲染，但足够挑衣服。

产物：
  export/viewer/clothing_thumbs/<slot>/<file>.png
  export/viewer/clothing_thumbs/index.json     （file → 缩略图路径）

用法：
  uv run python tools/build_clothing_thumbs.py            # 全部
  uv run python tools/build_clothing_thumbs.py --limit 40 # 先试 40 件
"""
import os
import io
import sys
import json
import time
import argparse
import re
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rdr2_npc_export as E

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = [('generic', 'raw/npc/models/generic'),
       ('player', 'raw/npc/models/player'),
       ('cutscene', 'raw/npc/models/cutscene')]
OUT = os.path.join(ROOT, 'export/viewer/clothing_thumbs')
W, H = 96, 144
SS = 3   # 超采样倍数
TEXIDX = os.path.join(ROOT, 'raw/npc/index/tex_index.json')

_idx = None
_col_cache = {}


def tex_index():
    global _idx
    if _idx is None:
        _idx = E.load_tex_index(TEXIDX)
    return _idx


def color_of(albedo):
    """albedo 名字 → 平均色（0..1）。解码失败就返回中性灰。"""
    if not albedo:
        return np.array([0.55, 0.53, 0.50])
    k = albedo.lower()
    if k in _col_cache:
        return _col_cache[k]
    ent = tex_index().get(k)
    col = np.array([0.55, 0.53, 0.50])
    if ent:
        try:
            png, w, h, _n = E.decode_ytd_entry(*ent)
            if png:
                im = Image.open(io.BytesIO(png)).convert('RGBA')
                a = np.asarray(im, dtype=np.float32) / 255.0
                wgt = a[..., 3:4]
                s = float(wgt.sum())
                if s > 1e-3:
                    col = (a[..., :3] * wgt).reshape(-1, 3).sum(0) / s
                # tint 遮罩贴图（彩虹/纯绿）平均出来是荧光绿，直接当颜色会让整页发绿；
                # 统一降成中性灰（真配色在 assets_tints.ymt 里，暂不可得）
                if re.search(r'_c\d+_999_ab$', albedo or '', re.I) or E._looks_like_tint_mask(png):
                    g = float(col.mean()) * 1.55
                    col = np.array([g * 1.02, g * 0.99, g * 0.95])
        except Exception:
            pass
    _col_cache[k] = col
    return col


def render(ped):
    verts, norms, cols = [], [], []
    for p in ped['parts']:
        c = color_of(p.get('albedo'))
        for g in p['geoms']:
            pos = np.asarray(g['pos'], dtype=np.float32).reshape(-1, 3)
            nrm = np.asarray(g['nrm'], dtype=np.float32).reshape(-1, 3) if g.get('nrm') else np.zeros_like(pos)
            if len(nrm) != len(pos):
                nrm = np.zeros_like(pos)
            verts.append(pos)
            norms.append(nrm)
            cols.append(np.tile(c, (len(pos), 1)))
    if not verts:
        return None
    V = np.vstack(verts)
    N = np.vstack(norms)
    C = np.vstack(cols)
    # 归一化：按 x/y 包围盒等比铺满
    x, y = V[:, 0], V[:, 1]
    x0, x1, y0, y1 = x.min(), x.max(), y.min(), y.max()
    span = max(x1 - x0, y1 - y0, 1e-3)
    Ws, Hs = W * SS, H * SS
    sx = (x - (x0 + x1) / 2) / span * (Ws - 12 * SS) + Ws / 2
    sy = Hs - 6 * SS - (y - y0) / span * (Hs - 12 * SS)
    px = sx.astype(np.int32)
    py = sy.astype(np.int32)

    # 简单明暗：法线朝观察者 + 上左光
    L = np.array([-0.4, 0.5, 0.75], dtype=np.float32)
    L /= np.linalg.norm(L)
    lam = np.clip((N * L).sum(1), 0, 1)
    shade = 0.55 + 0.55 * lam
    rgb = np.clip(C * shade[:, None], 0, 1)

    img = np.zeros((Hs, Ws, 4), dtype=np.uint8)
    # 3×3 泼溅：模型顶点在硬边处大量重合（4597 个顶点只有 ~1300 个不同屏幕位置），
    # 只泼 1~2 px 会得到"点阵"而不是剪影。
    r = SS * 3   # 最终分辨率上约 3 px（顶点在屏幕上的间距就是 4~5 px）
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            xx = np.clip(px + dx, 0, Ws - 1)
            yy = np.clip(py + dy, 0, Hs - 1)
            img[yy, xx, :3] = (rgb * 255).astype(np.uint8)
            img[yy, xx, 3] = 255
    return Image.fromarray(img, 'RGBA').resize((W, H), Image.BOX)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    mapping = {}
    n = 0
    t0 = time.time()
    for _src, rel in SRC:
        d = os.path.join(ROOT, rel)
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.ydd'):
                continue
            if a.limit and n >= a.limit:
                break
            try:
                ped = E.parse_ped(os.path.join(d, fn))
            except Exception:
                continue
            img = render(ped)
            if img is None:
                continue
            base = fn[:-4]
            slot = base.split('_')[0] or 'other'
            os.makedirs(os.path.join(OUT, slot), exist_ok=True)
            img.save(os.path.join(OUT, slot, base + '.png'))
            mapping[fn] = 'clothing_thumbs/%s/%s.png' % (slot, base)
            n += 1
            if n % 500 == 0:
                print('  %d … %.0fs' % (n, time.time() - t0), flush=True)
    json.dump(mapping, open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    print('done', n, 'thumbs in %.0fs' % (time.time() - t0), '→', OUT)


if __name__ == '__main__':
    main()
