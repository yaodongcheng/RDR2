"""微缩模型 v5：街区积木（用户要的"乐高化"）。

规则
  1. 只认建筑，道具/贴花/道路全丢；
  2. 按 30 m 网格把相邻建筑并成"街区"（街区就是现实里的一个 block）；
  3. 每个街区出一块积木：占地＝街区并集，高度＝街区内最高建筑的 95 分位，
     高楼再叠一层收进 15% 的"上段"，做出台阶感；
  4. 颜色按街区里最主要的贴图命中调色板（墙色 + 屋顶色），单材质顶点色；
  5. 底座一块街道色薄板。

为什么不做"每栋房子一块"
  943 栋小房子拼一起就是用户说的"全都是小房子"；并成几十个街区，
  远看才有 GoT 开场那种"城市模型"的量感。

用法
  uv run python tools/build_miniatures_blocks.py --code sdn
  uv run python tools/build_miniatures_blocks.py
"""
import os
import csv
import json
import math
import glob
import struct
import argparse
import importlib.util

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
_s = importlib.util.spec_from_file_location('lg', os.path.join(HERE, 'build_miniatures_lego.py'))
LG = importlib.util.module_from_spec(_s)
_s.loader.exec_module(LG)

OUT = os.path.join(ROOT, 'deliverable/miniatures')
MODELS = os.path.join(OUT, 'models')
MAP_SCALE = 1.0 / 29.0
MIN_DIM_M = 2.5
CELL = 30.0          # 街区网格（实景米）

WALL = [(0.88, 0.84, 0.74), (0.82, 0.70, 0.54), (0.72, 0.58, 0.44),
        (0.86, 0.83, 0.76), (0.78, 0.70, 0.56), (0.62, 0.46, 0.36)]
ROOF = [(0.56, 0.26, 0.20), (0.28, 0.31, 0.34), (0.46, 0.38, 0.28),
        (0.34, 0.38, 0.32), (0.60, 0.36, 0.26), (0.42, 0.30, 0.24)]


def add_box(P, C, I, x0, x1, y0, y1, z0, z1, wc, rc):
    b = len(P)
    # 轴序必须是 (x, 高度, z)；写成 (x, z, 高度) 整座城会"立"起来（踩过两次）
    for (x, zz, hgt) in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)):
        P.append((x, hgt, zz))
        C.append(wc)
    C[b + 4:b + 8] = [rc] * 4          # 顶面用屋顶色
    for (a, bb, c) in ((0, 1, 2), (0, 2, 3), (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2),
                       (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0), (4, 6, 5), (4, 7, 6)):
        I.append((b + a, b + bb, b + c))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--code', default='')
    args = ap.parse_args()

    os.makedirs(MODELS, exist_ok=True)
    ledger = LG.load_ledger()
    settles = LG.load_settlements()
    insts = LG.load_instances()
    terr = LG.Terrain()

    rows = []
    for i, s in enumerate(settles):
        if args.code and s['code'] != args.code:
            continue
        hw, hd = s['w'] / 2, s['d'] / 2
        sel = [e for e in insts if abs(e[1] - s['x']) <= hw and abs(e[2] - s['y']) <= hd]

        cells = {}
        blds = 0
        for e in sel:
            m = ledger.get(e[0])
            if not m:
                continue
            if not LG.feature_score(m['name'], m['sx'], m['sy'], m['sz'], m['tris']):
                continue
            if m['sx'] * abs(e[8]) > 110 or m['sz'] * abs(e[10]) > 95:
                continue
            blds += 1
            key = (int(math.floor(e[1] / CELL)), int(math.floor(e[2] / CELL)))
            b = cells.setdefault(key, {'x0': 1e9, 'x1': -1e9, 'y0': 1e9, 'y1': -1e9,
                                       'zmin': 1e9, 'heights': [], 'tex': {}})
            w = m['sx'] * abs(e[8])
            d = m['sy'] * abs(e[9])
            b['x0'] = min(b['x0'], e[1] - w / 2)
            b['x1'] = max(b['x1'], e[1] + w / 2)
            b['y0'] = min(b['y0'], e[2] - d / 2)
            b['y1'] = max(b['y1'], e[2] + d / 2)
            b['zmin'] = min(b['zmin'], e[3])
            b['heights'].append(min(m['sz'] * abs(e[10]), 60.0))
            b['tex'][e[0]] = b['tex'].get(e[0], 0) + 1

        blocks = [b for b in cells.values() if len(b['heights']) >= 2]
        if not blocks:
            print('!! 空', s['code'])
            continue

        xs = [(b['x0'], b['x1']) for b in blocks]
        bxs0 = min(v[0] for v in xs); bxs1 = max(v[1] for v in xs)
        bys0 = min(b['y0'] for b in blocks); bys1 = max(b['y1'] for b in blocks)
        cxw, cyw = (bxs0 + bxs1) / 2, (bys0 + bys1) / 2
        k = MAP_SCALE
        if max(bxs1 - bxs0, bys1 - bys0) * k < MIN_DIM_M:
            k = MIN_DIM_M / max(bxs1 - bxs0, bys1 - bys0, 1.0)

        P, C, I = [], [], []
        for b in blocks:
            # 夹在官方占地框内：街区并集会比据点框大出半栋楼，不夹就会压到隔壁
            hx_lim = hw * k
            hz_lim = hd * k
            lx0 = max((b['x0'] - cxw) * k, -hx_lim)
            lx1 = min((b['x1'] - cxw) * k, hx_lim)
            lz0 = max(-(b['y1'] - cyw) * k, -hz_lim)
            lz1 = min(-(b['y0'] - cyw) * k, hz_lim)
            if lx1 - lx0 < 0.02 or lz1 - lz0 < 0.02:
                continue
            # 统一落在 0 平面：地形高差 40 m 在 1/29 后还有 1.4 m，各块各用各的地面高度会"悬空"
            gy = 0.0
            # 1/29 下真实层高只剩 0.3 m，一眼看过去全是薄板；竖向放大 1.7 倍才读得出体量
            hh = float(np.percentile(b['heights'], 90)) * k * 1.7
            hh = max(hh, 0.12)
            # 暖色为主（奶油/砂/砖），冷色偶发，别一片蓝粉
            order = [0, 1, 2, 4, 0, 1, 3, 2, 5, 1]
            pal = order[int(abs(hash(tuple(b['tex'].keys())))) % len(order)]
            wc = WALL[pal]
            rc = ROOF[pal % len(ROOF)]

            if hh > 0.5:      # 高楼：上段收进 15%，做出台阶
                zm = gy + hh * 0.62
                add_box(P, C, I, lx0, lx1, lz0, lz1, gy, zm, wc, wc)
                ix = (lx1 - lx0) * 0.15
                iz = (lz1 - lz0) * 0.15
                add_box(P, C, I, lx0 + ix, lx1 - ix, lz0 + iz, lz1 - iz, zm, gy + hh, wc, rc)
            else:
                add_box(P, C, I, lx0, lx1, lz0, lz1, gy, gy + hh, wc, rc)

        # 底座：必须贴在最低的那块积木下面，否则整城会"悬空"
        miny = min(v[1] for v in P)
        mx = (min(v[0] for v in P) + max(v[0] for v in P)) / 2
        mz = (min(v[2] for v in P) + max(v[2] for v in P)) / 2
        # 底座不外扩：直接压在街区并集上（外扩会让成品超过官方占地，验收会判不合格）
        hx = (max(v[0] for v in P) - min(v[0] for v in P)) / 2
        hz = (max(v[2] for v in P) - min(v[2] for v in P)) / 2
        b0 = len(P)
        for (dx, dz) in ((-1, -1), (-1, 1), (1, 1), (1, -1)):
            P.append((mx + dx * hx, miny - 0.03, mz + dz * hz))
            C.append((0.52, 0.48, 0.40))
        I.append((b0, b0 + 1, b0 + 2))
        I.append((b0, b0 + 2, b0 + 3))

        Pa = np.asarray(P, np.float32)
        Pa[:, 1] -= Pa[:, 1].min()
        p = os.path.join(MODELS, s['code'] + '.glb')
        nv, nt = LG.write_glb(p, Pa, C, I, s['code'])
        print(f"{s['code']:7} {s['name_zh'][:10]:11} 建筑 {blds:4d} → 街区 {len(blocks):3d}  "
              f"面 {nt:6,d}  {hx*2:.1f}x{hz*2:.1f} m")
        rows.append({'code': s['code'], 'name_zh': s['name_zh'], 'btype': s['btype'],
                     'size_x': round(hx * 2, 2), 'size_z': round(hz * 2, 2),
                     'scale': round(k, 5), 'scale_boost': round(k / MAP_SCALE, 2),
                     'tris': nt, 'verts': nv, 'n_tex': 0, 'n_inst_in_box': len(sel),
                     'n_items': blds, 'n_placed': len(blocks), 'n_skipped': 0,
                     'tex': '', 'tex_kb': 0,
                     'glb_kb': round(os.path.getsize(p) / 1024, 1),
                     'landmark1': '', 'landmark1_kind': '', 'landmark2': '', 'landmark2_kind': '',
                     'landmark3': '', 'landmark3_kind': '',
                     'world_x': s['x'], 'world_y': s['y'],
                     'bbox_w': s['w'], 'bbox_d': s['d']})

    if rows and not args.code:
        with open(os.path.join(OUT, 'audit.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        json.dump(rows, open(os.path.join(OUT, 'audit.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        t = sum(r['tris'] for r in rows)
        print(f'\n{len(rows)} 个据点 · 合计 {t:,} 面 · 最大 {max(r["tris"] for r in rows):,}')


if __name__ == '__main__':
    main()
