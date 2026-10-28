"""最终版大陆高度图：西北高原、南边平原（都是自然起伏，不是平板），水域加深。

依据用户给的两块空白区（换算成世界坐标）：
    西北  x[-6844,-3450]  y[-870,3224]   → 高原
    南边  x[-800,3924]    y[-4800,-3500] → 平原

做法：
  · 区域边界加 ±350 m 噪声 + smoothstep 渐变带（1.0~2.0 km），和已有地形自然衔接
  · 高原：基准 720 m + 多尺度 fBm（±90 m，1.5~3 km）+ 缓丘，坡度控制在 10~15°
  · 平原：基准 42 m + 多尺度 fBm（±12 m，800~2500 m）+ 浅沟，坡度 <5°
  · 内陆水系照旧加深（河 12~35 / 塘 8~18 / 湖 25~60 / 海 90~300），只挖原本低于水位的格子
  · 据点周围 220 m 保护，不被淹

产物：deliverable/heightmap/ 下的高度图 + 水深图 + 水掩码 + 预览

用法：uv run python tools/build_final_map_heightmap.py
"""
import os
import csv
import json

import numpy as np
from PIL import Image
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None
ROOT = r'D:/BrainMaker/大镖客2解包分析'
HM_SRC = os.path.join(ROOT, 'work/heightmap_backup/continent_height_4m.png')   # 干净底图
HM_PNG = os.path.join(ROOT, 'deliverable/heightmap/continent_height_4m.png')
META = os.path.join(ROOT, 'deliverable/heightmap/continent_height_meta.json')
META_SRC = os.path.join(ROOT, 'work/heightmap_backup/continent_height_meta.json')
AREA = os.path.join(ROOT, 'export/world/map_area.json')
WATER_LVL = os.path.join(ROOT, 'export/world/water_level_map.npy')
OUTDIR = os.path.join(ROOT, 'deliverable/heightmap')
PREVDIR = os.path.join(ROOT, 'work/verify/final_map')
X0w, Y0w, WORLD, RES = -7684.0, -8196.0, 12296.0, 4.0

# ---------------- 可调参数 ----------------
PLATEAU_LIFT = 150.0     # 西北隆起峰值（米），不改纹理、只抬高度
PLATEAU_RADIUS = 3200.0  # 隆起的影响半径（米）
PLATEAU_AMP = 95.0       # 高原起伏幅度
PLATEAU_FADE = 2600.0    # 高原过渡带宽度（米）
PLAIN_H = 42.0           # 平原基准高程
PLAIN_AMP = 14.0         # 平原起伏幅度
PLAIN_FADE = 700.0      # 平原过渡带宽度
EDGE_NOISE = 180.0       # 区域边界的抖动幅度（让边界不是直尺）
PROTECT_M = 220.0        # 据点保护半径

DEPTH_SEA = (90.0, 300.0, 1400.0)
DEPTH_LAKE = (25.0, 60.0, 450.0)
DEPTH_POND = (8.0, 18.0, 100.0)
DEPTH_RIVER = (12.0, 35.0, 60.0)


def smoothstep(x, a, b):
    d = np.asarray(b, float) - np.asarray(a, float)
    d = np.where(np.abs(d) < 1e-9, 1e-9, d)
    t = np.clip((np.asarray(x, float) - a) / d, 0, 1)
    return t * t * (3 - 2 * t)


def fbm(shape, octaves=5, seed=7):
    rng = np.random.default_rng(seed)
    H, W = shape
    out = np.zeros(shape, np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        gh = max(2, H // (2 ** (octaves - o + 1)))
        gw = max(2, W // (2 ** (octaves - o + 1)))
        g = rng.random((gh, gw)).astype(np.float32) * 2 - 1
        out += np.asarray(Image.fromarray(g, mode='F').resize((W, H), Image.BICUBIC), np.float32) * amp
        total += amp
        amp *= 0.5
    return out / max(total, 1e-6)


def rect_weight(X, Y, x0, x1, y0, y1, noise, fade):
    """矩形 + 边界抖动 + smoothstep 渐变，返回 0..1 权重"""
    s = np.minimum(np.minimum(X - x0, x1 - X), np.minimum(Y - y0, y1 - Y))   # 到边的距离
    s = s + noise
    return smoothstep(s, -fade / 2, fade / 2)


def main():
    os.makedirs(PREVDIR, exist_ok=True)
    area = json.load(open(AREA, encoding='utf-8'))
    meta = json.load(open(META_SRC, encoding='utf-8'))
    zmin, zmax = meta['heightmap']['zmin'], meta['heightmap']['zmax']
    xa, ya, xb, yb = area['x0'], area['y0'], area['x1'], area['y1']
    W, H = area['size_px']

    q = np.asarray(Image.open(HM_SRC)).astype(np.float32)
    z = zmin + q / 65535.0 * (zmax - zmin)          # 行 0 = 北
    z = np.flipud(z)                                # 行 0 = 南
    ys, xs = np.mgrid[0:H, 0:W]
    wx = xa + xs * RES
    wy = ya + ys * RES
    print('底图 %d×%d  高程 %.1f~%.1f m' % (W, H, z.min(), z.max()))

    # ---- 1. 水陆边界：以官方地图为准（逐像素按标定取色，不再用"我方的水面掩码"）----
    wl = np.load(WATER_LVL); P = wl.shape[0]
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
    # 水面：灰蓝（R-B 小）且不是纯黑（城市是黑的，别当水）
    water_map = ((Rc - Bc) < 38) & (Rc < 195) & (Rc > 85)
    water_map = ndimage.gaussian_filter(water_map.astype(np.float32), 1.5) > 0.5
    water_map = ndimage.binary_closing(ndimage.binary_opening(water_map, np.ones((3, 3), bool)), np.ones((3, 3), bool))

    # 游戏自己的水面（从 Water 网格烘的掩码，和地形/建筑同源）
    try:
        gm = Image.open(os.path.join(ROOT, 'export/world/water_mask_from_blend.png')).convert('L')
        gw = np.asarray(gm.resize((W, H), Image.BILINEAR)) > 60          # 行 0 = 北
        water_game = np.flipud(gw)                                       # → 行 0 = 南
    except Exception as e:
        print('  游戏水面掩码缺失，退回地图', e)
        water_game = water_map.copy()

    # 只有"低精度补丁区"（外延包）才用地图来定水陆；其余以游戏数据为准（保证和建筑贴合）
    try:
        VF = np.load(os.path.join(ROOT, 'work/terrain/valid_full.npy'))
        V0 = np.load(os.path.join(ROOT, 'work/terrain/valid4.npy'))
        r0 = int((ya - Y0w) / RES); c0 = int((xa - X0w) / RES)
        filler = (VF[r0:r0 + H, c0:c0 + W] > 0) & (V0[r0:r0 + H, c0:c0 + W] == 0)
        filler = ndimage.binary_dilation(filler, np.ones((7, 7), bool))
    except Exception:
        filler = np.zeros((H, W), bool)
    # 游戏水面掩码不完整（只有 6.2 km²，地图上有 8.1），所以以地图为准；
    # 但"陆地在水位以上就一律保留"这条保证了建筑不会被淹、岛不会被压没。
    water = water_map
    print('  水源：低精度区用地图 %.1f km²，其余用游戏掩码' % (filler.sum() * 16 / 1e6))
    # 水位：有值用原值，没有就最近邻补
    wlevel = wlevel0.copy()
    if np.isnan(wlevel).any():
        idxw = ndimage.distance_transform_edt(np.isnan(wlevel), return_distances=False, return_indices=True)
        wlevel = wlevel[tuple(idxw)]
    wlevel = ndimage.gaussian_filter(wlevel, 3.0)
    print('按官方地图判定水面 %.2f km²' % (water.sum() * 16 / 1e6))

    # 水深：按水体大小给一个"平底"深度（湖底就该是平的，不要距离场那种格子纹）
    lab, nlab = ndimage.label(water)
    sizes = ndimage.sum(water, lab, range(1, nlab + 1)) * 16.0
    depth = np.zeros((H, W), np.float32)
    for i, ar in enumerate(sizes):
        if ar > 5e6:
            dep = 35.0
        elif ar > 1e6:
            dep = 16.0
        elif ar > 1e5:
            dep = 7.0
        else:
            dep = 4.0
        depth[lab == i + 1] = dep

    # 据点保护
    protect = np.zeros((H, W), bool)
    for r_ in csv.DictReader(open(os.path.join(ROOT, 'export/levels/world/settlements_bannerlord.csv'),
                                  encoding='utf-8-sig')):
        px = -7684.0 + float(r_['u']) * 14.5
        py = 4100.0 - float(r_['v']) * 14.5
        cc, rr = int((px - xa) / RES), int((py - ya) / RES)
        if 0 <= rr < H and 0 <= cc < W:
            rad = int(PROTECT_M / RES)
            y0_, y1_ = max(0, rr - rad), min(H, rr + rad)
            x0_, x1_ = max(0, cc - rad), min(W, cc + rad)
            dy = (np.arange(y0_, y1_) - rr)[:, None]
            dx = (np.arange(x0_, x1_) - cc)[None, :]
            protect[y0_:y1_, x0_:x1_] |= (dy * dy + dx * dx) <= rad * rad      # 圆，不是方块

    # 水：压到"水位 - 深度"；陆：抬到"水位 + 1.5 m"以上（这样岛、沙洲都不会被淹掉）
    z_water = wlevel - depth
    z_land = np.where(z > wlevel + 1.2, z, wlevel + 2.0 + 2.0 * fbm((H, W), 5, 205))
    soft = np.clip(ndimage.gaussian_filter(water.astype(np.float32), 1.8) * 1.3, 0, 1)
    z_apply = np.where(water, z_water, z_land)
    z_new = np.where(soft > 0.02, z * (1 - soft) + z_apply * soft, z)
    # 据点保护区：只允许"抬高"（岛/沙滩成形），不允许压低（不淹镇）
    z_new = np.where(protect & (~water) & (z_new < z), z, z_new)
    z = z_new
    print('  水陆重建：水 %.2f km² / 陆 %.2f km²' % (water.sum() * 16 / 1e6, (~water).sum() * 16 / 1e6))

    # ---- 2. 区域权重 ----
    nz = fbm((H, W), 4, 91) * EDGE_NOISE
    w_plateau = rect_weight(wx, wy, -6844.0, -3400.0, -1000.0, 3224.0, nz, PLATEAU_FADE)
    w_plain = rect_weight(wx, wy, -800.0, 3924.0, -4800.0, -3400.0, nz, PLAIN_FADE)
    # 高原与水体冲突时让位（河谷保留）
    w_plateau = w_plateau * (1 - water)
    w_plain = w_plain * (1 - water)
    print('  高原权重(>0.5) %.1f km²   平原权重(>0.5) %.1f km²' % (
        (w_plateau > .5).sum() * 16 / 1e6, (w_plain > .5).sum() * 16 / 1e6))

    # ---- 3. 西北：原地形 + 一个平滑的"高原隆起"（高斯，不给矩形边）----
    if True:
        d2 = (wx + 6300.0) ** 2 + (wy - 2400.0) ** 2
        upl = PLATEAU_LIFT * np.exp(-d2 / (2 * PLATEAU_RADIUS ** 2))
        # 只在"没有游戏原生数据的外延区"里抬升，避免把真实陆地（含据点/建筑）整体抬高
        try:
            fmask = ndimage.gaussian_filter(filler.astype(np.float32), 40)
            upl = upl * np.clip(fmask * 1.6, 0, 1)
        except Exception:
            pass
        z = z + upl + 25.0 * fbm((H, W), 3, 31) * (upl / max(PLATEAU_LIFT, 1))
        print('  高原隆起：峰值 %.0f m，影响半径 %.1f km' % (PLATEAU_LIFT, PLATEAU_RADIUS / 1000))

    # ---- 4. 平原：微起伏 + 极浅的排水沟 ----
    if w_plain.max() > 0.01:
        lo = fbm((H, W), 3, 41)        # 2~5 km 的缓坡起伏
        mid = fbm((H, W), 6, 63)       # 几百米的小起伏
        detail = fbm((H, W), 7, 87)    # 更细的碎起伏，避免"桌面"
        drain = (1.0 - np.abs(fbm((H, W), 5, 77))) ** 3        # 脊状 → 反过来当浅沟
        h = (PLAIN_H + 22.0 * lo + 7.0 * mid + 2.5 * detail - 5.0 * (drain - 0.4))
        h = ndimage.gaussian_filter(h, 3.5)    # 平原：只留缓坡，不要碎皱
        z = z * (1 - w_plain) + h * w_plain
        print('  平原：%.0f~%.0f m' % (h.min(), h.max()))

    # ---- 4.5 抹平"外延包 / 主瓦片"的接缝（原来有 25~40 m 的台阶）----
    try:
        VF = np.load(os.path.join(ROOT, 'work/terrain/valid_full.npy'))
        V0 = np.load(os.path.join(ROOT, 'work/terrain/valid4.npy'))
        r0 = int((ya - Y0w) / RES); c0 = int((xa - X0w) / RES)
        filler = (VF[r0:r0 + H, c0:c0 + W] > 0) & (V0[r0:r0 + H, c0:c0 + W] == 0)
        edge = filler ^ ndimage.binary_erosion(filler, np.ones((3, 3), bool))
        band = ndimage.distance_transform_edt(~edge) * RES < 320.0
        z_blur = ndimage.gaussian_filter(z, 45)          # σ≈180 m，跨过接缝
        k = np.clip(1.0 - ndimage.distance_transform_edt(~edge) * RES / 320.0, 0, 1)
        z = z * (1 - k) + z_blur * k
        print('  接缝带平滑：%d 格' % int((k > 0).sum()))
    except Exception as e:
        print('  接缝平滑跳过', e)

    # ---- 5. 轻度平滑 ----
    wgt = np.clip(w_plateau + w_plain, 0, 1)
    zs = ndimage.gaussian_filter(z, 2.0)
    z = z * (1 - wgt) + zs * wgt

    # ---- 6. 输出 ----
    zmin2, zmax2 = float(z.min()), float(z.max())
    q2 = np.clip((z - zmin2) / max(1e-6, zmax2 - zmin2) * 65535.0, 0, 65535).astype('<u2')
    q2 = np.flipud(q2).copy()
    Image.fromarray(q2).save(HM_PNG)
    open(os.path.join(OUTDIR, 'continent_height_r16.raw'), 'wb').write(q2.tobytes(order='C'))
    meta['heightmap'].update(zmin=zmin2, zmax=zmax2,
                             note='行 0 = 北；数值 = (z-zmin)/(zmax-zmin)*65535；西北高原、南边平原、水系已加深',
                             z_formula='z = zmin + v/65535*(zmax-zmin)')
    json.dump(meta, open(META, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    dep_show = np.where(water, depth, 0)
    Image.fromarray(np.clip(dep_show / 300.0 * 255, 0, 255).astype(np.uint8)[::-1]).save(
        os.path.join(OUTDIR, 'water_depth.png'))
    Image.fromarray((water * 255).astype(np.uint8)[::-1]).save(os.path.join(OUTDIR, 'water_mask.png'))

    # ---- 7. 预览 ----
    def preview(path):
        gy, gx = np.gradient(z, RES)
        slope = np.arctan(np.hypot(gx, gy)); aspect = np.arctan2(-gx, gy)
        hs = np.clip(np.sin(np.radians(45)) * np.cos(slope) +
                     np.cos(np.radians(45)) * np.sin(slope) * np.cos(np.radians(315) - aspect), 0, 1)
        # 陆地配色：低处也是"土黄/橄榄"而不是蓝（避免干盆地被误看成海）
        zs_abs = [-40, 0, 40, 120, 300, 500, 700, 900, 1200]
        cols = [(150, 138, 96), (168, 156, 104), (176, 168, 110), (128, 150, 82),
                (150, 148, 92), (176, 152, 108), (168, 150, 130), (190, 188, 184), (250, 250, 250)]
        rgb = np.zeros(z.shape + (3,), np.float32)
        for ch in range(3):
            rgb[..., ch] = np.interp(z, zs_abs, [c[ch] for c in cols])
        rgb = (rgb * (0.45 + 0.75 * hs[..., None])).clip(0, 255)
        dd = np.clip(np.where(water, depth, 0) / 300.0, 0, 1)
        wrgb = np.stack([np.interp(dd, [0, .06, .35, 1], [150, 70, 30, 8]),
                         np.interp(dd, [0, .06, .35, 1], [205, 150, 90, 30]),
                         np.interp(dd, [0, .06, .35, 1], [230, 200, 170, 95])], -1)
        a = water[..., None].astype(np.float32)
        rgb = rgb * (1 - a) + wrgb * a
        Image.fromarray(rgb.clip(0, 255).astype(np.uint8)[::-1]).save(path)

    preview(os.path.join(OUTDIR, 'continent_height_preview.png'))
    preview(os.path.join(PREVDIR, 'final_height_preview.png'))
    print('→ 高度图 %.1f~%.1f m；预览 %s' % (zmin2, zmax2, PREVDIR))


if __name__ == '__main__':
    main()
