# -*- coding: utf-8 -*-
"""地形分级管线：只做「原始 → 高原/平原」两级。

    python tools/make_terrain_stages.py

产物 `deliverable/terrain/stages/<级>/`：

    height_16bit_4m.png   2692×2006 @4 m，16bit（米制：z = zmin + v/65535*(zmax-zmin)）
    color_1m.png          10768×8024 @1 m（RGB；**= 原始地形材质，各级相同，不重上色**）
    meta.json             本级做了什么 / 参数 / 与上一级的差量

两级（2026-11-02 起）：

    00_raw             外延包补过的原始地形（H4_full 裁到地图框），未做任何塑形
    01_plateau_plain   西北高原（基准 720 m + fBm + 150 m 高斯隆起）/ 东南平原（42 m 合成）

为什么同一天砍掉「水域加深」和「统一水位陆地修正」两级（用户裁定）：
    RDR2 的水面是**两级**（主水系 40.5 m / 瀑布以西的新奥斯汀盆地 −22 m）。
    · 「水域加深」按单级水位挖/填 → 把圣路易斯河河床从 −28 m 抬到 +7 m（错的）；
    · 「统一水位陆地修正」按「骑砍2 只有一个水面」去垫高干地 → 前提不成立。
    **地形高度本身是对的**（等高线贴着游戏航拍贴图、标高与实体位置对得上），不按水位再动地形。

前两级的函数/参数/噪声种子全部取自 `build_final_map_heightmap.py`（import 复用，不抄第二份）。
"""
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None

import build_final_map_heightmap as B          # 复用：fbm / rect_weight / 常量 / 水源判定口径

ROOT = r'D:/BrainMaker/大镖客2解包分析'
OUT = os.path.join(ROOT, 'deliverable/terrain/stages')
# 唯一地形材质图（三个模式共用；2026-11-08 起不再往各 stage 里各放一份）
COLOR_OUT = os.path.join(ROOT, 'deliverable/terrain/color_1m.png')
H4FULL = os.path.join(ROOT, 'work/terrain/H4_full.npy')
COLOR = os.path.join(ROOT, 'export/world/world_ground_final_out.png')
AREA = os.path.join(ROOT, 'export/world/map_area.json')
X0w, Y0w, WORLD, RES = -7684.0, -8196.0, 12296.0, 4.0
ZMIN, ZMAX = -34.93079376220703, 690.3469848632812

# 2026-11-02 删掉了「骑砍2 单水位」相关的常量（WATER_LEVEL_M / LAND_FLOOR_M / LIFT_*）：
# 水面已确认是两级（主水系 40.5 / 西盆地 −22），不再做按水位的陆地垫高。


# ------------------------------------------------------------------ 地形
def load_raw(area):
    """H4_full 裁到地图框 → (z, x0, y0)  z 为米，**行 0 = 北**"""
    Hf = np.load(H4FULL).astype(np.float32)          # 行 0 = 南（build_terrain_heightmap 口径）
    Hf = np.flipud(Hf)                               # → 行 0 = 北
    x0, y0, x1, y1 = area['x0'], area['y0'], area['x1'], area['y1']
    c0 = int(round((x0 - X0w) / RES)); c1 = c0 + int(area['size_px'][0])
    r0 = int(round((Y0w + WORLD - y1) / RES)); r1 = r0 + int(area['size_px'][1])
    return Hf[r0:r1, c0:c1].copy(), x0, y0


def water_and_depth(H, W, area):
    """照抄 build_final_map_heightmap.main 的水源判定 + 分级水深（返回 行0=南 的布尔/浮点）"""
    xa, ya = area['x0'], area['y0']
    wl = np.load(B.WATER_LVL); P = wl.shape[0]
    li = np.clip(((np.arange(H) * RES + ya - Y0w) / WORLD * P).astype(np.int32), 0, P - 1)
    lj = np.clip(((np.arange(W) * RES + xa - X0w) / WORLD * P).astype(np.int32), 0, P - 1)
    wlevel0 = wl[np.ix_(li, lj)]

    mp = Image.open(os.path.join(ROOT, '地图下载/大陆地图_缩略.jpg')).convert('RGB')
    arr = np.asarray(mp).astype(np.float32)
    kk = mp.size[0] / 1400.0
    fit = json.load(open(os.path.join(ROOT, '地图下载/配准结果.json'), encoding='utf-8'))
    A_, C_, TX_, TY_ = fit['a'], fit['c'], fit['tx'], fit['ty']
    yy, xx = np.mgrid[0:H, 0:W]
    uu = (xa + xx * RES - X0w) / 14.5
    vv = (4100.0 - (ya + yy * RES)) / 14.5
    mx = (A_ * uu - C_ * vv + TX_) * kk
    my = (C_ * uu + A_ * vv + TY_) * kk
    Rc = ndimage.map_coordinates(arr[..., 0], [my, mx], order=1, mode='nearest')
    Bc = ndimage.map_coordinates(arr[..., 2], [my, mx], order=1, mode='nearest')
    water = ((Rc - Bc) < 38) & (Rc < 195) & (Rc > 85)
    water = ndimage.gaussian_filter(water.astype(np.float32), 1.5) > 0.5
    water = ndimage.binary_closing(ndimage.binary_opening(water, np.ones((3, 3), bool)), np.ones((3, 3), bool))

    wlevel = wlevel0.copy()
    if np.isnan(wlevel).any():
        idxw = ndimage.distance_transform_edt(np.isnan(wlevel), return_distances=False, return_indices=True)
        wlevel = wlevel[tuple(idxw)]
    wlevel = ndimage.gaussian_filter(wlevel, 3.0)

    lab, nlab = ndimage.label(water)
    sizes = ndimage.sum(water, lab, range(1, nlab + 1)) * 16.0
    depth = np.zeros((H, W), np.float32)
    for i, ar in enumerate(sizes):
        dep = 35.0 if ar > 5e6 else 16.0 if ar > 1e6 else 7.0 if ar > 1e5 else 4.0
        depth[lab == i + 1] = dep
    return water, depth, wlevel


def protect_mask(H, W, area):
    p = np.zeros((H, W), bool)
    xa, ya = area['x0'], area['y0']
    import csv
    for r_ in csv.DictReader(open(os.path.join(ROOT, 'export/levels/world/settlements_bannerlord.csv'),
                                  encoding='utf-8-sig')):
        px = -7684.0 + float(r_['u']) * 14.5
        py = 4100.0 - float(r_['v']) * 14.5
        cc, rr = int((px - xa) / RES), int((py - ya) / RES)
        if 0 <= rr < H and 0 <= cc < W:
            rad = int(B.PROTECT_M / RES)
            y0_, y1_ = max(0, rr - rad), min(H, rr + rad)
            x0_, x1_ = max(0, cc - rad), min(W, cc + rad)
            dy = (np.arange(y0_, y1_) - rr)[:, None]
            dx = (np.arange(x0_, x1_) - cc)[None, :]
            p[y0_:y1_, x0_:x1_] |= (dy * dy + dx * dx) <= rad * rad
    return p


# ------------------------------------------------------------------ 输出
def save_stage(name, z_north, base_color, meta_extra, changed):
    """z_north 行 0 = 北（米）→ 16bit PNG + 按高度重上色的彩图 + meta"""
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    zmin, zmax = float(z_north.min()), float(z_north.max())
    q = np.clip((z_north - zmin) / max(1e-6, zmax - zmin) * 65535.0, 0, 65535).astype('<u2')
    Image.fromarray(q).save(os.path.join(d, 'height_16bit_4m.png'))
    open(os.path.join(d, 'height_r16.raw'), 'wb').write(q.tobytes(order='C'))

    # 彩图：**直接保留原始地形材质**（2026-11-02 用户裁定）。
    # 为什么不重上色：改动区按「同高程带均值」刷出来是平坦色块 + 硬边界，完全不自然；
    #   试过三种重上色（高程重映射 / 局部色差场 / 按同高程找真实地形重采样 + 平滑偏移场），
    #   都会把真实纹理拉花或留下硬边界。原始彩图本身就是游戏真实地表（雪是雪、沼泽是沼泽），
    #   而这片改动区（西北高原 / 东南平原）原本的色相与新高程并不冲突 —— 保留原色最自然。
    #   如将来要"让颜色随高程变"，只有两条正路：大块真实纹理拼贴（有接缝风险）或手工修图。
    col = base_color.copy()
    # 2026-11-08：彩图只有一份，放在 `deliverable/terrain/color_1m.png`（三个模式完全相同）。
    if not os.path.exists(COLOR_OUT):
        Image.fromarray(col).save(COLOR_OUT, 'PNG', compress_level=6)

    meta = dict(stage=name, world=dict(x0=B_area['x0'], y0=B_area['y0'],
                                       x1=B_area['x1'], y1=B_area['y1'],
                                       size_m=[B_area['x1'] - B_area['x0'], B_area['y1'] - B_area['y0']]),
                row0='north', col0='west',
                height=dict(file='height_16bit_4m.png', px=list(B_area['size_px']),
                            m_per_px=RES, zmin=zmin, zmax=zmax),
                color=dict(file='../color_1m.png', px=[col.shape[1], col.shape[0]], m_per_px=1.0,
                           note='唯一地形材质图，三个模式共用（world_ground_final_out 原色；不按高程重上色）'),
                changed_px=dict(count=int(changed.sum()), area_km2=round(float(changed.sum()) * 16 / 1e6, 2)),
                **meta_extra)
    json.dump(meta, open(os.path.join(d, 'meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('[stage] %-18s z %.1f~%.1f m  改动 %.2f km2' %
          (name, zmin, zmax, changed.sum() * 16 / 1e6))
    return col


def main():
    global B_area
    B_area = json.load(open(AREA, encoding='utf-8'))
    z_n, xa, ya = load_raw(B_area)                     # 行 0 = 北
    H, W = z_n.shape
    print('[stage] 底图 %dx%d（4 m）高程 %.1f~%.1f m' % (W, H, z_n.min(), z_n.max()))

    col_im = Image.open(COLOR).convert('RGB')
    box = (int(round(B_area['x0'] - X0w)), int(round(Y0w + WORLD - B_area['y1'])),
           int(round(B_area['x0'] - X0w)) + W * 4, int(round(Y0w + WORLD - B_area['y1'])) + H * 4)
    base_color = np.asarray(col_im.crop(box), np.uint8)
    print('[stage] 彩图 %s ← %s' % (base_color.shape[1::-1], 'world_ground_final_out.png'))

    z_s = np.flipud(z_n)                               # 行 0 = 南（与 B.main 内部一致）
    water, _depth, _wlevel = water_and_depth(H, W, B_area)   # 只要水面掩膜（高原/平原避开水面）

    # ---- 节点 0
    save_stage('00_raw', z_n, base_color,
               dict(note='外延包补过的原始地形（H4_full 裁到地图框），未做任何塑形'), np.zeros((H, W), bool))

    # ---- 节点 1：高原 + 平原（复刻 build_final_map_heightmap 的 2 / 3 / 4 / 4.5 / 5 步）
    ys, xs = np.mgrid[0:H, 0:W]
    wx = xa + xs * RES
    wy = ya + ys * RES
    nz = B.fbm((H, W), 4, 91) * B.EDGE_NOISE
    w_plateau = B.rect_weight(wx, wy, -6844.0, -3400.0, -1000.0, 3224.0, nz, B.PLATEAU_FADE)
    w_plain = B.rect_weight(wx, wy, -800.0, 3924.0, -4800.0, -3400.0, nz, B.PLAIN_FADE)
    w_plateau = w_plateau * (1 - water)
    w_plain = w_plain * (1 - water)
    z1 = z_s.copy()
    # 高原隆起（只在没有原生数据的外延区抬）
    try:
        VF = np.load(os.path.join(ROOT, 'work/terrain/valid_full.npy'))
        V0 = np.load(os.path.join(ROOT, 'work/terrain/valid4.npy'))
        r0 = int((ya - Y0w) / RES); c0 = int((xa - X0w) / RES)
        filler = (VF[r0:r0 + H, c0:c0 + W] > 0) & (V0[r0:r0 + H, c0:c0 + W] == 0)
        filler = ndimage.binary_dilation(filler, np.ones((7, 7), bool))
    except Exception:
        filler = np.zeros((H, W), bool)
    d2 = (wx + 6300.0) ** 2 + (wy - 2400.0) ** 2
    upl = B.PLATEAU_LIFT * np.exp(-d2 / (2 * B.PLATEAU_RADIUS ** 2))
    upl = upl * np.clip(ndimage.gaussian_filter(filler.astype(np.float32), 40) * 1.6, 0, 1)
    z1 = z1 + upl + 25.0 * B.fbm((H, W), 3, 31) * (upl / max(B.PLATEAU_LIFT, 1))
    # 平原
    if w_plain.max() > 0.01:
        lo = B.fbm((H, W), 3, 41); mid = B.fbm((H, W), 6, 63); detail = B.fbm((H, W), 7, 87)
        drain = (1.0 - np.abs(B.fbm((H, W), 5, 77))) ** 3
        h = B.PLAIN_H + 22.0 * lo + 7.0 * mid + 2.5 * detail - 5.0 * (drain - 0.4)
        h = ndimage.gaussian_filter(h, 3.5)
        z1 = z1 * (1 - w_plain) + h * w_plain
    # 接缝平滑 + 轻度平滑
    try:
        edge = filler ^ ndimage.binary_erosion(filler, np.ones((3, 3), bool))
        dd = ndimage.distance_transform_edt(~edge) * RES
        k = np.clip(1.0 - dd / 320.0, 0, 1)
        z1 = z1 * (1 - k) + ndimage.gaussian_filter(z1, 45) * k
    except Exception:
        pass
    wgt = np.clip(w_plateau + w_plain, 0, 1)
    z1 = z1 * (1 - wgt) + ndimage.gaussian_filter(z1, 2.0) * wgt
    save_stage('01_plateau_plain', np.flipud(z1), base_color,
               dict(note='西北高原（720 m 基准 + fBm + 150 m 高斯隆起，仅外延区）/ 东南平原（42 m 合成）',
                    params=dict(plateau_lift=B.PLATEAU_LIFT, plateau_radius=B.PLATEAU_RADIUS,
                                plain_h=B.PLAIN_H, plain_fade=B.PLAIN_FADE)),
               np.abs(z1 - z_s) > 1.0)

    # 🔴 2026-11-02：**「统一水位陆地修正」整级取消**（用户裁定）。
    #    理由：这里已经明确是**两块不同高度的水位**（主水系 40.5 m / 瀑布以西 −22 m），
    #    按「骑砍2 只有一个水面」去垫高陆地的前提不成立；而且「水域加深」也在同一天去掉了
    #    —— 地形高度本身是对的，管线只保留 00_raw / 01_plateau_plain 两级，不再按水位挖/填。


if __name__ == '__main__':
    main()
