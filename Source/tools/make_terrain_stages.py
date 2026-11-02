# -*- coding: utf-8 -*-
"""地形四级管线：把「原始 → 高原/平原 → 水域加深 → 统一水位陆地修正」逐级出图。

    python tools/make_terrain_stages.py

产物 `deliverable/terrain/stages/<级>/`：

    height_16bit_4m.png   2692×2006 @4 m，16bit（米制：z = zmin + v/65535*(zmax-zmin)）
    color_1m.png          10768×8024 @1 m（RGB；**被该级改动过的地方按高度重新上色**）
    meta.json             本级做了什么 / 参数 / 与上一级的差量

四级：

    00_raw             外延包补过的原始地形（H4_full 裁到地图框），未做任何塑形
    01_plateau_plain   西北高原（基准 720 m + fBm + 150 m 高斯隆起）/ 东南平原（42 m 合成）
    02_water_deepen    水域加深（按官方地图判水面 + 分级水深）
    03_unified_water   统一水位陆地修正（只服务大地图：陆地保底 −24.5 m，≤−15 m 抬 +10 m）

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
H4FULL = os.path.join(ROOT, 'work/terrain/H4_full.npy')
COLOR = os.path.join(ROOT, 'export/world/world_ground_final_out.png')
AREA = os.path.join(ROOT, 'export/world/map_area.json')
X0w, Y0w, WORLD, RES = -7684.0, -8196.0, 12296.0, 4.0
ZMIN, ZMAX = -34.93079376220703, 690.3469848632812

WATER_LEVEL_M = -25.0      # 骑砍2 单水位
LAND_FLOOR_M = -24.5
LIFT_M = 10.0
LIFT_Z_FULL = -15.0
LIFT_Z_ZERO = 15.0


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

    # 彩图：未改动处保持原样；被本级改过的地方按「同高程带的真实像素均值」重新上色
    col = base_color.copy()
    zc = np.repeat(np.repeat(z_north, 4, axis=0), 4, axis=1)[:col.shape[0], :col.shape[1]]
    ch = np.repeat(np.repeat(changed, 4, axis=0), 4, axis=1)[:col.shape[0], :col.shape[1]]
    zb = np.clip(((zc - ZMIN) / (ZMAX - ZMIN) * 64).astype(np.int16), 0, 63)
    flat_z = zb.ravel(); flat_c = col.reshape(-1, 3).astype(np.float32)
    lut = np.zeros((64, 3), np.float32)
    for b in range(64):
        m = (flat_z == b)
        lut[b] = flat_c[m].mean(0) if m.sum() > 200 else np.array([150, 140, 120], np.float32)
    # 平滑 LUT，避免高程带之间出现色阶
    lut = ndimage.uniform_filter1d(lut, 5, axis=0)
    rec = lut[zb]
    col2 = np.where(ch[..., None], rec, col).astype(np.uint8)
    Image.fromarray(col2).save(os.path.join(d, 'color_1m.png'), 'PNG', compress_level=6)

    meta = dict(stage=name, world=dict(x0=B_area['x0'], y0=B_area['y0'],
                                       x1=B_area['x1'], y1=B_area['y1'],
                                       size_m=[B_area['x1'] - B_area['x0'], B_area['y1'] - B_area['y0']]),
                row0='north', col0='west',
                height=dict(file='height_16bit_4m.png', px=list(B_area['size_px']),
                            m_per_px=RES, zmin=zmin, zmax=zmax),
                color=dict(file='color_1m.png', px=[col.shape[1], col.shape[0]], m_per_px=1.0,
                           note='未改动处=world_ground_final_out 原色；改动处按同高程带真实像素均值重上色'),
                changed_px=dict(count=int(changed.sum()), area_km2=round(float(changed.sum()) * 16 / 1e6, 2)),
                **meta_extra)
    json.dump(meta, open(os.path.join(d, 'meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('[stage] %-18s z %.1f~%.1f m  改动 %.2f km2' %
          (name, zmin, zmax, changed.sum() * 16 / 1e6))
    return col2


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
    water, depth, wlevel = water_and_depth(H, W, B_area)
    protect = protect_mask(H, W, B_area)

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

    # ---- 节点 2：水域加深（同一份水源判定 + 分级水深）
    z2 = z1.copy()
    z_water = wlevel - depth
    z_land = np.where(z2 > wlevel + 1.2, z2, wlevel + 2.0 + 2.0 * B.fbm((H, W), 5, 205))
    soft = np.clip(ndimage.gaussian_filter(water.astype(np.float32), 1.8) * 1.3, 0, 1)
    z_apply = np.where(water, z_water, z_land)
    z2 = np.where(soft > 0.02, z2 * (1 - soft) + z_apply * soft, z2)
    z2 = np.where(protect & (~water) & (z2 < z1), z1, z2)
    save_stage('02_water_deepen', np.flipud(z2), base_color,
               dict(note='按官方地图判水面 + 分级水深（河/塘/湖/海），据点 220 m 保护区只抬不压',
                    water_km2=round(float(water.sum()) * 16 / 1e6, 2)),
               np.abs(z2 - z1) > 1.0)

    # ---- 节点 3：统一水位陆地修正（只服务大地图）
    z3 = z2.copy()
    land = ~water
    z3[land] = np.maximum(z3[land], LAND_FLOOR_M)
    t = np.clip((z3 - LIFT_Z_FULL) / (LIFT_Z_ZERO - LIFT_Z_FULL), 0.0, 1.0)
    w_lift = 1.0 - t * t * (3.0 - 2.0 * t)
    z3[land] = z3[land] + (LIFT_M * w_lift)[land]
    save_stage('03_unified_water', np.flipud(z3), base_color,
               dict(note='骑砍2 单水位适配：陆地保底 −24.5 m；≤−15 m 抬满 +10 m，≥+15 m 不抬（按高度）',
                    water_level_m=WATER_LEVEL_M, land_floor_m=LAND_FLOOR_M, lift_m=LIFT_M),
               np.abs(z3 - z2) > 1.0)

    # ---- 与出厂版本对比（出厂 = deliverable/heightmap/continent_height_4m.png）
    try:
        meta = json.load(open(os.path.join(ROOT, 'deliverable/heightmap/continent_height_meta.json'),
                              encoding='utf-8'))
        q = np.asarray(Image.open(os.path.join(ROOT, 'deliverable/heightmap/continent_height_4m.png')),
                       np.uint16).astype(np.float32)
        hz = meta['heightmap']
        zs = hz['zmin'] + q / 65535.0 * (hz['zmax'] - hz['zmin'])
        d = np.abs(zs - np.flipud(z2))
        print('[stage] 节点2 与出厂 continent_height_4m.png 差异：平均 %.2f m / P99 %.2f m / 最大 %.2f m'
              % (d.mean(), np.percentile(d, 99), d.max()))
    except Exception as e:
        print('[stage] 与出厂版本对比跳过：', e)


if __name__ == '__main__':
    main()
