"""用**建筑底座**推"局部地形校准场"，产出据点的 4 m 精地形补丁。

为什么需要：游戏在城镇脚下**不放地形 patch**（被建筑取代），我们那份 4 m 全局高程图在镇区里
是插值补出来的，与真实地面能差 ±20 m ⇒ 建筑会明显"陷进地里/悬空"。
（本项目笔记 §0.6 #18 早就记过这个坑：地形基准不要用常量，要用建筑底座推局部校准场。）

做法：把该据点所有实例的**实体 z**（实测与地面差的中位数仅 +0.4 m）当作地面采样点 →
在补丁网格上求均值 → 空洞扩散 → 平滑 → 再用**径向权重**与原始 4 m 地形混合
（镇中心完全用校准场，向外平滑过渡回真实地形）。

用法：uv run python tools/build_town_hpatch.py --code ann --town work/ann/town.json --out work/ann/hpatch.json
"""
import os
import sys
import json
import base64
import io
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image

ROOT = r'D:/BrainMaker/大镖客2解包分析'
H4 = os.path.join(ROOT, 'work/terrain/H4.npy')
TERRAIN_H = os.path.join(ROOT, 'export/levels/world/terrain_h.json')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--code', required=True)
    ap.add_argument('--town', required=True, help='town.json（含 insts）')
    ap.add_argument('--out', required=True)
    ap.add_argument('--half', type=float, default=500.0)
    ap.add_argument('--res', type=float, default=4.0)
    ap.add_argument('--core', type=float, default=0.0, help='镇中心完全用校准场的半径（0=自动）')
    a = ap.parse_args()

    tm = json.load(open(TERRAIN_H, encoding='utf-8'))
    X0, Y0, RES = tm['x0'], tm['y0'], 4.0
    H = np.load(H4)                                   # 3075², 4 m, row↔y

    d = json.load(open(a.town, encoding='utf-8'))
    insts = d['insts']
    cx = sum(i[1] for i in insts) / len(insts)
    cy = sum(i[2] for i in insts) / len(insts)
    rad = max(np.hypot(i[1] - cx, i[2] - cy) for i in insts)
    core = a.core or (rad * 1.15)
    R = min(a.half, core + 150.0)               # 校准场只覆盖镇子附近，别外推太远
    print(f'{a.code}: 中心 ({cx:.0f},{cy:.0f}) 镇半径 {rad:.0f} m → 补丁 ±{R:.0f} m，'
          f'校准核心半径 {core:.0f} m')

    half = R
    n = int(half * 2 / a.res) + 1
    px0, py0 = cx - half, cy - half
    # 原始 4 m 地形
    cc = np.clip(((px0 + np.arange(n) * a.res) - X0) / RES, 0, 3074).astype(int)
    rr = np.clip(((py0 + np.arange(n) * a.res) - Y0) / RES, 0, 3074).astype(int)
    base = H[np.ix_(rr, cc)].astype('float64')

    # ★ 只修正"残余偏移"（建筑底座 z − 该点原始地形），而不是直接插值绝对高度
    #   这样能保留地形自身的大形（山坡、河谷），不会把镇子抹成一块平板
    def base_at(x, y):
        c = int(round((x - px0) / a.res)); r = int(round((y - py0) / a.res))
        c = min(max(c, 0), n - 1); r = min(max(r, 0), n - 1)
        return base[r, c]
    acc = np.zeros((n, n)); cnt = np.zeros((n, n))
    for it in insts:
        c = int(round((it[1] - px0) / a.res)); r = int(round((it[2] - py0) / a.res))
        if 0 <= c < n and 0 <= r < n:
            acc[r, c] += (it[3] - base_at(it[1], it[2])); cnt[r, c] += 1
    print(f'  底座采样点 {int((cnt > 0).sum())} / {n*n} 格')
    # ★ 残余场用 **IDW（反距离加权）** 重建：样本稀疏时比"扩散+大核平滑"保真得多
    #   （实测：扩散+平滑会把修正量稀释掉，拟合反而变差）
    sy, sx = np.where(cnt > 0)
    vals = (acc[cnt > 0] / cnt[cnt > 0]).astype('float64')
    print(f'  底座样本 {len(vals)} 个，残余中位 {np.median(vals):+.1f} m')
    Yg, Xg = np.mgrid[0:n, 0:n]
    d2 = (Xg[..., None] - sx) ** 2 + (Yg[..., None] - sy) ** 2        # (n,n,S)
    wgt = 1.0 / np.maximum(d2, 4.0)                                   # 至少 2 m，避免奇点
    fld = (wgt * vals).sum(-1) / wgt.sum(-1)
    dmin = np.sqrt(d2.min(-1))
    fld *= np.exp(-(dmin / 120.0) ** 2)                               # 离样本 >~150 m 处不修正

    # 径向权重混合
    yy, xx = np.mgrid[0:n, 0:n]
    wx = px0 + xx * a.res - cx
    wy = py0 + yy * a.res - cy
    dist = np.hypot(wx, wy)
    w = np.clip((R - dist) / max(1.0, R - core), 0.0, 1.0)
    w = w * w * (3 - 2 * w)                    # smoothstep
    Z = base + fld * w                          # ★ 地形大形 + 加权残余修正

    lo, hi = float(Z.min()), float(Z.max())
    q = np.clip((Z - lo) / max(1e-6, hi - lo) * 65535, 0, 65535).astype('<u2')
    rgba = np.zeros((n, n, 4), dtype='uint8')
    rgba[..., 0] = (q >> 8) & 0xFF
    rgba[..., 1] = q & 0xFF
    rgba[..., 3] = 255
    b = io.BytesIO(); Image.fromarray(rgba, 'RGBA').save(b, 'PNG', optimize=True)
    out = dict(b64=base64.b64encode(b.getvalue()).decode(),
               x0=px0, y0=py0, x1=px0 + (n - 1) * a.res, y1=py0 + (n - 1) * a.res,
               zmin=lo, zmax=hi, n=n)
    json.dump(out, open(a.out, 'w'), separators=(',', ':'))
    print(f'  → {a.out}  {n}² @{a.res:g}m  高程 {lo:.0f}~{hi:.0f} m  '
          f'({len(out["b64"])/1024:.0f} KB base64)')


if __name__ == '__main__':
    main()
