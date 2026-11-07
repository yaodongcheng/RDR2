# -*- coding: utf-8 -*-
"""生成《场景水位表》：每张场景导进骑砍2 时的水面高度（**不依赖 blend，不用重建**）。

    python -X utf8 tools/gen_scene_water_md.py

口径（2026-11-07 用户裁定）：
  · 全图**只有两个水位** —— 主水系 **40.5 m** / 西盆地 **−22 m**（以大地图高度图为参考）；
  · 每个场景按「远景框内两大水系各自的**面积占比**」二选一，占比大的赢；
  · 两个都不足 5%（范围里只有高山湖或没有水）→ **不铺水面**。

输出（都是**生成物，禁止手改**）：
  · `docs/世界与地编/场景水位表.md`（人看）
  · `docs/世界与地编/scene_water.csv`（导入脚本读：id,name,kind,water_level）
"""
import csv
import io
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scene_bounds import clamp_scene_to_map  # noqa: E402

RDR2 = r'D:/BrainMaker/大镖客2解包分析'
SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(SRC, 'docs', '世界与地编')
OUT_MD = os.path.join(DOCS, '场景水位表.md')
OUT_CSV = os.path.join(DOCS, 'scene_water.csv')
WATER_NPY = os.path.join(RDR2, 'export/world/water_level_map_2lv.npy')

MAIN, WEST, MIN_SHARE = 40.5, -22.0, 0.05


def shares(x, y, fw, fh):
    lvl = np.load(WATER_NPY)
    X0, Y0, WORLD = -7684.0, -8196.0, 12296.0
    P = lvl.shape[0]
    res = WORLD / P
    fx0, fy0, fx1, fy1 = x - fw / 2, y - fh / 2, x + fw / 2, y + fh / 2
    c0 = int(np.clip(round((fx0 - X0) / res), 0, P - 1))
    c1 = int(np.clip(round((fx1 - X0) / res), 0, P - 1))
    r0 = int(np.clip(round((fy0 - Y0) / res), 0, P - 1))
    r1 = int(np.clip(round((fy1 - Y0) / res), 0, P - 1))
    v = lvl[min(r0, r1):max(r0, r1) + 1, min(c0, c1):max(c0, c1) + 1]
    v = v[np.isfinite(v)]
    if v.size == 0:
        return 0.0, 0.0
    return (float((np.abs(v - MAIN) < 0.6).sum()) / v.size,
            float((np.abs(v - WEST) < 0.6).sum()) / v.size)


def main():
    rows = []
    for r in csv.DictReader(io.open(os.path.join(DOCS, 'scene_list.csv'), encoding='utf-8-sig')):
        if not (r.get('活动区宽_m') or '').strip():
            continue
        p = None
        try:
            v = [float((r.get(k) or '').strip())
                 for k in ('能走_x0', '能走_y0', '能走_x1', '能走_y1')]
            if v[2] > v[0] and v[3] > v[1]:
                p = tuple(v)
        except Exception:
            p = None
        sc = clamp_scene_to_map({'id': r['id'], 'x': float(r['x']), 'y': float(r['y']),
                                 'fw': float(r['远景宽_m']), 'fh': float(r['远景高_m']),
                                 'p': p}, verbose=False)
        m, w = shares(sc['x'], sc['y'], sc['fw'], sc['fh'])
        if max(m, w) < MIN_SHARE:
            lvl, why = None, '范围里只有高山湖（或无水）'
        else:
            lvl = MAIN if m >= w else WEST
            why = '主水系' if lvl == MAIN else '西盆地'
        rows.append({'id': r['id'], 'name': r.get('name') or '',
                     'kind': '据点' if r.get('kind') == 'settlement' else '野地',
                     'level': '' if lvl is None else ('%.1f' % lvl),
                     'why': why, 'main': m * 100, 'west': w * 100,
                     'fw': sc['fw'], 'fh': sc['fh']})

    rows.sort(key=lambda r: (r['kind'] != '据点', r['id']))
    L = ['# 场景水位表（导入骑砍2 用）', '',
         '> **生成物，禁止手改** —— `python -X utf8 tools/gen_scene_water_md.py` 重跑。',
         '> 口径：**全图只有两个水位** —— 主水系 **40.5 m** / 西盆地 **−22 m**（以大地图高度图为参考）；',
         '> 场景按远景框内两大水系的面积占比二选一；两个都不足 5% ⇒ **不铺水面**（`—`）。',
         '> ⚠️ blend 里的水面只是占位，**以此表为准**。机器可读版：`scene_water.csv`。', '',
         '| 场景 | 中文名 | 类型 | **水位 (m)** | 依据 | 主系占比 | 西盆占比 | 远景框 |',
         '|---|---|---|---:|---|---:|---:|---|']
    for r in rows:
        L.append('| `%s` | %s | %s | **%s** | %s | %.1f%% | %.1f%% | %.0f×%.0f |'
                 % (r['id'], r['name'], r['kind'],
                    r['level'] if r['level'] else '—', r['why'],
                    r['main'], r['west'], r['fw'], r['fh']))
    io.open(OUT_MD, 'w', encoding='utf-8').write('\n'.join(L) + '\n')

    with io.open(OUT_CSV, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['id', 'name', 'kind', 'water_level'])
        for r in rows:
            w.writerow([r['id'], r['name'], r['kind'], r['level']])
    n_main = sum(1 for r in rows if r['level'] == '%.1f' % MAIN)
    n_west = sum(1 for r in rows if r['level'] == '%.1f' % WEST)
    n_none = sum(1 for r in rows if not r['level'])
    print('已写 %s（%d 行）与 %s' % (OUT_MD, len(rows), OUT_CSV))
    print('  40.5 m：%d 张 · -22 m：%d 张 · 不铺：%d 张' % (n_main, n_west, n_none))


if __name__ == '__main__':
    main()
