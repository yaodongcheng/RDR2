"""全图地形垂向偏差修正。

问题：`H4.npy` 高程与 ymap 实体 z 存在**局部变化**的偏差（抽样：野外中位 −6.51 m、据点内 −0.48 m），
导致大量物件埋进地形或悬空。

做法：按 500 m 网格统计「实体底面 z − H4 地形 z」的中位数，做成平滑修正场，加到 H4 上。

  H4_adj = H4 + smooth(median(dz per cell))

用法：
  uv run python tools/fix_terrain_offset.py            # 生成 raw/terrain/H4_adj.npy
  uv run python tools/fix_terrain_offset.py --report   # 只看偏差分布
然后用：
  RDR2_H4=raw/terrain/H4_adj.npy blender -b -P tools/blender_continent.py -- ...
"""
import os
import sys
import json
import glob
import argparse

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H4 = os.path.join(ROOT, 'raw/terrain/H4.npy')
OUT = os.path.join(ROOT, 'raw/terrain/H4_adj.npy')
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
LIB = os.path.join(ROOT, 'assets/lib_native/index.json')
X0, Y0, RES = -7684.0, -8196.0, 4.0
CELL = 500.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cell', type=float, default=CELL)
    a = ap.parse_args()

    H = np.load(H4)
    ny, nx = H.shape
    lib = json.load(open(LIB, encoding='utf-8'))['models']

    def gz(x, y):
        c = int((x - X0) / RES); r = int((y - Y0) / RES)
        if 0 <= r < ny and 0 <= c < nx:
            return float(H[r, c])
        return None

    cells = {}
    n = 0
    for f in glob.glob(os.path.join(TILES, '*.json')):
        for e in json.load(open(f, encoding='utf-8')):
            if e[10] < 2:            # 只看 ≥4 m 的件
                continue
            m = lib.get(hex(e[0]))
            if not m:
                continue
            zmin = e[3] + m['b'][2]
            g = gz(e[1], e[2])
            if g is None:
                continue
            i = int((e[1] - X0) // a.cell); j = int((e[2] - Y0) // a.cell)
            cells.setdefault((i, j), []).append(zmin - g)
            n += 1

    print('采样 %d 个实体，覆盖 %d 个 %.0fm 网格' % (n, len(cells), a.cell))
    dz = np.array([np.median(v) for v in cells.values()])
    print('偏差分位: P5 %.2f  P25 %.2f  P50 %.2f  P75 %.2f  P95 %.2f'
          % tuple(np.percentile(dz, [5, 25, 50, 75, 95])))

    if a.report:
        return

    # 建场
    ni = int((nx * RES) / a.cell) + 2
    nj = int((ny * RES) / a.cell) + 2
    field = np.full((nj, ni), np.nan, np.float32)
    for (i, j), v in cells.items():
        if 0 <= j < nj and 0 <= i < ni:
            field[j, i] = np.median(v)

    # 多遍盒式模糊（忽略 NaN）→ 抹平台阶
    def blur(arr, k):
        tot = np.zeros_like(arr); cnt = np.zeros_like(arr)
        r = k // 2
        for dj in range(-r, r + 1):
            for di in range(-r, r + 1):
                sl = np.roll(np.roll(arr, dj, axis=0), di, axis=1)
                v = ~np.isnan(sl)
                tot += np.where(v, sl, 0.0); cnt += v
        return np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan)

    for _ in range(3):
        field = blur(field, 3)

    # 双线性采样到全分辨率
    fy = (np.arange(ny) * RES + Y0 - Y0) / a.cell
    fx = (np.arange(nx) * RES + X0 - X0) / a.cell
    FY, FX = np.meshgrid(fy, fx, indexing='ij')
    j0 = np.clip(np.floor(FY).astype(np.int32), 0, nj - 2)
    i0 = np.clip(np.floor(FX).astype(np.int32), 0, ni - 2)
    ty = (FY - j0).astype(np.float32); tx = (FX - i0).astype(np.float32)
    f = field[j0, i0] * (1 - tx) * (1 - ty) + field[j0, i0 + 1] * tx * (1 - ty) \
        + field[j0 + 1, i0] * (1 - tx) * ty + field[j0 + 1, i0 + 1] * tx * ty
    f = np.where(np.isnan(f), 0.0, f).astype(np.float32)
    f = np.clip(f, -15.0, 15.0)      # 防止极端值把地形拉爆

    H2 = (H + f).astype(np.float32)
    np.save(OUT, H2)
    print('地形修正: 平均 %+.2f m，范围 %+.2f ~ %+.2f m' % (f.mean(), f.min(), f.max()))
    print('wrote', OUT)


if __name__ == '__main__':
    main()
