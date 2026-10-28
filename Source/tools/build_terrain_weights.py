"""生成"卡拉迪亚式"地形材质权重图（7 层）—— v2：与最终高度图同源。

⚠️ 先说清楚：这些权重是**推断**的，不是从游戏里直接导出的分层数据。
   依据只有三样：游戏烘好的地形色图（颜色/饱和度）、最终高度图的高程（坡度/海拔）、
   最终高度图带的水面掩码。阈值都写在下面常量里，觉得哪一层不对改数字重跑即可。

v2 改了什么（2026-10-22 晚）：
  1. 高程不再读 work/terrain/H4_full.npy（原始解包高程，没有西北高原/南边平原/水深加深），
     改为直接读交付物 deliverable/heightmap/continent_height_4m.png + meta 的 zmin/zmax。
     → 雪线、坡度、沙地判据从此和"引擎里真正吃到的地形"完全一致。
  2. 水面不再读 export/world/water_level_map.npy（游戏水面），改为读交付物
     deliverable/heightmap/water_mask.png —— 也就是地形真正被挖成水面的那些格子。
     → 权重图的水面与地形水体 **逐像素一致**（IoU = 1.000），不会再出现
       "地形是水、权重说是草"。
  3. 算坡度时先把水域用最近邻陆地高程填平（water → 最近陆地），避免"水深加深"造出的
     12~300 m 湖底陡壁被当成岩壁，把整条岸线染成山岩。

七层：草地 grass / 针叶林 conifer / 山岩 rock / 泥土 dirt / 阔叶林 broadleaf / 河湖 water / 雪地 snow

产物（deliverable/terrain_weights/）
    w_<layer>.png          8 bit，1 px = 4 m，**行 0 = 北**（与高度图同网格同朝向）
    weights_preview.png    图例配色合成图
    weights_rgb_1/2/3.png  压成 RGB 便于塞进引擎（R草G针叶B岩 / R泥G阔叶B水 / 雪单通道）
    weights_vs_heightmap.png  高度图 vs 权重图 vs 水面差异（自检用）
    weights_meta.json      阈值/规则/统计/坐标约定

用法：
    uv run python tools/build_terrain_weights.py
"""
import os
import json

import numpy as np
from PIL import Image
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None
ROOT = r'D:/BrainMaker/大镖客2解包分析'
AREA = os.path.join(ROOT, 'export/world/map_area.json')
HM_PNG = os.path.join(ROOT, 'deliverable/heightmap/continent_height_4m.png')
HM_META = os.path.join(ROOT, 'deliverable/heightmap/continent_height_meta.json')
WMASK = os.path.join(ROOT, 'deliverable/heightmap/water_mask.png')
WDEPTH = os.path.join(ROOT, 'deliverable/heightmap/water_depth.png')
COLOR = os.path.join(ROOT, 'export/world/world_ground_final_out.png')
OUTDIR = os.path.join(ROOT, 'deliverable/terrain_weights')

X0w, Y0w, WORLD = -7684.0, -8196.0, 12296.0
RES = 4.0

# ---------------- 可调阈值 ----------------
SNOW_Z0 = 255.0                     # 雪线（米）基准：地面上"雪白"的地方从这开始积雪（Colter 307 m 在游戏里已在雪线上）
SNOW_SPAN = 150.0                   # 雪线以上的过渡高度：基准 +150 m 处全雪
SNOW_WHITE_SHIFT = 70.0             # 地面本身越白（低饱和高亮度），雪线越低，最多下移这么多
SNOW_REGION_BOOST = 0.30            # Grizzlies / 西北高原的加成（不做硬饱和，否则会出方块白斑）
SNOW_S = 0.30                       # 饱和度低于这个算"雪白"
ROCK_SLOPE0, ROCK_SLOPE1 = 24.0, 44.0   # 坡度（度）
ROCK_V = 0.42                       # 亮度低于这个且低饱和 → 岩
DIRT_RED = 0.02                     # R-G 超过这个算红土/沙
CONIF_V = 0.40                      # 针叶林：偏暗
CONIF_Z0, CONIF_Z1 = 60.0, 200.0    # 针叶林偏好中高海拔
BROAD_S = 0.40                      # 阔叶林：饱和度高
BROAD_Y = 200.0                     # 阔叶林偏好南边（y < 200 m）

LEGEND = [
    ('grass', '草地', (127, 174, 78)),
    ('conifer', '针叶林', (47, 93, 58)),
    ('rock', '山岩', (138, 138, 134)),
    ('dirt', '泥土/沙土', (169, 130, 90)),
    ('broadleaf', '阔叶林', (79, 143, 69)),
    ('water', '河湖', (47, 111, 168)),
    ('snow', '雪地', (242, 246, 248)),
]


def smoothstep(x, a, b):
    d = np.asarray(b, dtype=np.float64) - np.asarray(a, dtype=np.float64)
    d = np.where(np.abs(d) < 1e-6, 1e-6, d)
    t = np.clip((np.asarray(x, dtype=np.float64) - a) / d, 0, 1)
    return t * t * (3 - 2 * t)


def clamp01(x):
    return np.clip(x, 0, 1)


def load():
    """返回 (area, Z, RGB, wet)，全部 **行 0 = 南**，与 4 m 世界栅格对齐。"""
    area = json.load(open(AREA, encoding='utf-8'))
    W, H = area['size_px']
    hm = json.load(open(HM_META, encoding='utf-8'))['heightmap']
    zmin, zmax = hm['zmin'], hm['zmax']

    # ---- 高程：最终高度图（PNG 行 0 = 北）----
    q = np.asarray(Image.open(HM_PNG)).astype(np.float32)
    if q.shape != (H, W):
        raise SystemExit('高度图尺寸 %s 与 area %s 不一致，先重跑 build_final_map_heightmap.py'
                         % (q.shape, (H, W)))
    Z = zmin + q / 65535.0 * (zmax - zmin)
    Z = np.flipud(Z)                                  # → 行 0 = 南

    # ---- 水面：最终高度图自带的水面掩码（同一套挖水逻辑）----
    wet = np.flipud(np.asarray(Image.open(WMASK).convert('L')) > 127)

    # ---- 色图 1 px = 1 m，行 0 = 北 → 裁同一范围、缩到 4 m 网格 → 行 0 = 南 ----
    col = Image.open(COLOR).convert('RGB')
    pxn0 = int(round(area['x0'] - X0w)); pxn1 = pxn0 + int(round(area['x1'] - area['x0']))
    pyn0 = int(round(Y0w + WORLD - area['y1'])); pyn1 = pyn0 + int(round(area['y1'] - area['y0']))
    sub = col.crop((pxn0, pyn0, pxn1, pyn1)).resize((W, H), Image.BOX)
    RGB = np.asarray(sub).astype(np.float32) / 255.0
    RGB = np.flipud(RGB)                              # 行 0 = 南，与 Z 一致

    print('高程源 %s  z %.1f~%.1f m' % (os.path.basename(HM_PNG), zmin, zmax))
    print('水面源 %s  %.2f km²' % (os.path.basename(WMASK), wet.sum() * RES * RES / 1e6))
    return area, Z, RGB, wet


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    area, Z, RGB, wet = load()
    H, W = Z.shape
    R, G, B = RGB[..., 0], RGB[..., 1], RGB[..., 2]
    V = RGB.max(axis=2)
    S = np.where(V > 1e-4, (V - RGB.min(axis=2)) / np.maximum(V, 1e-4), 0)
    GXc = G - np.maximum(R, B)                # 绿偏
    RX = R - G                                # 红偏

    # ---- 坡度：先把水域用"最近陆地高程"填平，再求梯度 ----
    # （最终高度图把河湖压成平底、海压到 -300 m，不填的话每条岸线都是 20~80° 假陡壁，
    #   整条水岸会被判成山岩）
    if wet.any() and (~wet).any():
        idx = ndimage.distance_transform_edt(wet, return_distances=False, return_indices=True)
        Z_slope = Z[tuple(idx)]
    else:
        Z_slope = Z
    gy, gx = np.gradient(Z_slope, RES)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))

    # ---- 区域先验（RDR2 地图分区；边界 150 m 羽化，改这里就能挪区域）----
    ygrid = np.linspace(area['y0'], area['y1'], H)[:, None] * np.ones((1, W))
    xgrid = np.ones((H, 1)) * np.linspace(area['x0'], area['x1'], W)[None, :]

    def rect(x0, x1, y0, y1, feather=150.0):
        return (smoothstep(xgrid, x0 - feather, x0 + feather) * smoothstep(xgrid, x1 + feather, x1 - feather) *
                smoothstep(ygrid, y0 - feather, y0 + feather) * smoothstep(ygrid, y1 + feather, y1 - feather))

    REGIONS = {
        'grizzlies': rect(-3600, 1200, 1700, 3300),      # 西北雪山（Grizzlies West/East）
        'nwplateau': rect(-6844, -3400, -1000, 3224),    # 西北人工高原（外延区，海拔 400~690 m）
        'bigvalley': rect(-3600, -1700, 0, 1800),        # 西侧 Big Valley 针叶林
        'talltrees': rect(-2700, -1100, -1700, 100),     # 西南 Tall Trees 针叶/阔叶混交
        'greatplains': rect(-2500, -500, -1500, 300),    # 中西部大草原
        'heartlands': rect(-1300, 2100, -700, 1750),     # 中部 Heartlands 草原
        'cumberland': rect(-500, 1300, 600, 1850),       # 中北 Cumberland 森林
        'roanoke': rect(1900, 3800, 150, 2900),          # 东北 Roanoke 针叶林山地
        'lemoyne': rect(800, 2700, -2400, -600),         # 南部 Scarlett Meadows 草/阔叶
        'bayou': rect(1800, 3100, -1700, -200),          # 东南 Bayou 沼泽林
        'newaustin': rect(-6900, -2500, -4800, -1100),   # 西南 New Austin 荒漠
        'splain': rect(-800, 3924, -4800, -3400),        # 南边人工平原（外延区）
    }

    # ---- 1) 雪：海拔为主、地面白度微调、区域只做加成（不硬饱和）----
    # ⚠️ 不要写成 1.1*region*smoothstep(...) 那种：那会让整个区域先验矩形被压成"纯白雪块"，
    #    边界是矩形的，在权重图上就是一块白色补丁。这里雪线跟地形等高线走，区域只把雪线压低一点。
    white = smoothstep(SNOW_S, 0.12, S) * smoothstep(0.36, 0.46, V)
    line = SNOW_Z0 + SNOW_WHITE_SHIFT * (1 - white)
    snow = clamp01(smoothstep(Z, line, line + SNOW_SPAN) *
                   (1 + SNOW_REGION_BOOST * (REGIONS['grizzlies'] + REGIONS['nwplateau'])))
    snow = snow * (1 - wet)

    # ---- 2) 岩：陡坡 / 高海拔低饱和 ----
    rock_c = clamp01((slope - ROCK_SLOPE0) / (ROCK_SLOPE1 - ROCK_SLOPE0))
    rock_c = np.maximum(rock_c, 0.9 * smoothstep(0.24, 0.10, S) * smoothstep(ROCK_V, 0.26, V))
    rock = rock_c * (1 - snow) * (0.15 + 0.85 * (REGIONS['grizzlies'] + REGIONS['roanoke'] +
                                                REGIONS['newaustin'] + REGIONS['nwplateau']))

    # ---- 3) 泥土/沙土：New Austin 荒漠 + 红土 + 低洼沙地 ----
    dirt_c = clamp01((RX - DIRT_RED) / 0.06)
    sand = smoothstep(0.28, 0.36, S) * smoothstep(0.44, 0.52, V) * smoothstep(140, 40, Z)
    dirt = (0.55 * dirt_c + 0.5 * sand) * (1 - snow) * (1 - 0.5 * rock)
    dirt = np.maximum(dirt, 1.15 * REGIONS['newaustin'] * (1 - snow) * smoothstep(0.40, 0.18, slope / 100))

    # ---- 4) 针叶林：暗绿 + 山地/北侧 ----
    conifer_c = smoothstep(CONIF_V, 0.24, V) * smoothstep(0.22, 0.34, S)
    conifer = (0.9 * conifer_c + 1.15 * REGIONS['roanoke'] + 1.05 * REGIONS['bigvalley'] +
               0.85 * REGIONS['cumberland'] + 0.6 * REGIONS['talltrees'] +
               0.7 * REGIONS['grizzlies'] * smoothstep(Z, 330, 140) +
               0.45 * REGIONS['nwplateau'] * smoothstep(Z, 520, 330))
    conifer = conifer * (1 - snow) * (1 - 0.7 * rock) * smoothstep(50, 34, slope)

    # ---- 5) 阔叶林：饱和绿 + 南部 ----
    broad_c = smoothstep(0.42, 0.56, S) * smoothstep(0.34, 0.44, V)
    broadleaf = (0.9 * broad_c + 0.85 * REGIONS['lemoyne'] + 1.0 * REGIONS['bayou'] +
                 0.6 * REGIONS['talltrees'] + 0.35 * REGIONS['heartlands'] * smoothstep(0.42, 0.56, S))
    broadleaf = broadleaf * (1 - snow) * (1 - 0.7 * rock) * (1 - 0.4 * dirt) * smoothstep(46, 30, slope)

    # ---- 6) 草地：草原分区 + 绿偏兜底 ----
    grass_c = clamp01((GXc + 0.005) / 0.05)
    grass = (0.9 * REGIONS['heartlands'] + 0.85 * REGIONS['greatplains'] +
             0.35 * grass_c + 0.22)
    grass = grass * (1 - snow) * (1 - rock) * (1 - 0.75 * dirt) * (1 - 0.8 * conifer) * (1 - 0.8 * broadleaf)
    grass = np.maximum(grass, 0.10 * (1 - snow) * (1 - rock) * (1 - wet))

    # ---- 7) 钳位：所有层必须先压回 [0,1] 再互相压制 ----
    # 区域加成叠加后 rock 可能到 2 以上，若不钳位，下面 (1-rock) / (1-0.7*rock) 会变负，
    # 导致草/针叶出现负权重、山岩归一化后 >1（引擎混合会失真）。
    grass = clamp01(grass)
    conifer = clamp01(conifer)
    rock = clamp01(rock)
    dirt = clamp01(dirt)
    broadleaf = clamp01(broadleaf)
    snow = clamp01(snow)

    w = dict(grass=grass, conifer=conifer, rock=rock, dirt=dirt,
             broadleaf=broadleaf, water=wet.astype(np.float32) * 1.0, snow=snow)
    # 水面压掉其它层
    for k in w:
        if k != 'water':
            w[k] = w[k] * (1 - w['water'])
    tot = sum(w.values()) + 1e-6
    for k in w:
        w[k] = w[k] / tot
    tot_after = sum(w.values())            # 归一化后应恒为 1

    stats = {}
    for k, zh, col in LEGEND:
        a = (w[k] * 255).round().astype(np.uint8)
        Image.fromarray(a[::-1]).save(os.path.join(OUTDIR, 'w_%s.png' % k))
        stats[k] = dict(mean=float(w[k].mean()), max=float(w[k].max()),
                        cover5=float((w[k] > 0.05).mean()))

    # 合成预览（按权重混合图例色）
    prev = np.zeros((H, W, 3), np.float32)
    for k, zh, col in LEGEND:
        prev += w[k][..., None] * np.array(col, np.float32) / 255.0
    Image.fromarray((prev.clip(0, 1) * 255).astype(np.uint8)[::-1]).save(
        os.path.join(OUTDIR, 'weights_preview.png'))

    # 压成两张 RGB 便于进引擎（每通道一层，8 bit）
    order = [k for k, _, _ in LEGEND]

    def pack(names):
        out = np.zeros((H, W, 3), np.uint8)
        for i, k in enumerate(names):
            out[..., i] = (w[k] * 255).round().astype(np.uint8)
        return out
    Image.fromarray(pack(order[:3])[::-1]).save(os.path.join(OUTDIR, 'weights_rgb_1.png'))   # R草 G针叶 B岩
    Image.fromarray(pack(order[3:6])[::-1]).save(os.path.join(OUTDIR, 'weights_rgb_2.png'))  # R泥 G阔叶 B水
    Image.fromarray(((w['snow'] * 255).round().astype(np.uint8))[::-1]).save(
        os.path.join(OUTDIR, 'weights_rgb_3_snow.png'))

    # ---- 自检图：高度设色 / 权重合成 / 水面差异 ----
    def shade(zz):
        gy2, gx2 = np.gradient(zz, RES)
        sl = np.arctan(np.hypot(gx2, gy2)); asp = np.arctan2(-gx2, gy2)
        hs = np.clip(np.sin(np.radians(45)) * np.cos(sl) +
                     np.cos(np.radians(45)) * np.sin(sl) * np.cos(np.radians(315) - asp), 0, 1)
        zs_abs = [-40, 0, 40, 120, 300, 500, 700, 900]
        cols = [(150, 138, 96), (168, 156, 104), (176, 168, 110), (128, 150, 82),
                (150, 148, 92), (176, 152, 108), (168, 150, 130), (235, 238, 242)]
        rgb = np.zeros(zz.shape + (3,), np.float32)
        for ch in range(3):
            rgb[..., ch] = np.interp(zz, zs_abs, [c[ch] for c in cols])
        return (rgb * (0.45 + 0.75 * hs[..., None])).clip(0, 255).astype(np.uint8)

    hm_rgb = shade(Z)
    hm_rgb[wet] = np.array([40, 90, 150], np.uint8)     # 水面上色
    wdiff = np.zeros((H, W, 3), np.uint8)
    wdiff[wet] = (47, 111, 168)                          # 权重判的水
    wdiff[wet & (w['water'] < 0.5)] = (255, 0, 0)
    wdiff[(~wet) & (w['water'] >= 0.5)] = (255, 255, 0)
    prev8 = (prev.clip(0, 1) * 255).astype(np.uint8)
    sheet = np.concatenate([hm_rgb, prev8, wdiff], axis=1)
    Image.fromarray(sheet[::-1]).save(os.path.join(OUTDIR, 'weights_vs_heightmap.png'))

    # ---- 自检数值 ----
    iou = float(((w['water'] >= 0.5) & wet).sum() / max(1, ((w['water'] >= 0.5) | wet).sum()))
    land = ~wet
    checks = dict(
        water_iou_vs_heightmap=iou,
        water_area_km2=float(wet.sum() * RES * RES / 1e6),
        land_frac_above_snowline=float((Z[land] > SNOW_Z0).mean()),
        snow_on_land_mean=float(w['snow'][land].mean()),
        rock_on_land_mean=float(w['rock'][land].mean()),
        weight_sum_min=float(tot_after.min()), weight_sum_max=float(tot_after.max()),
        negative_cells=int(sum((w[k] < -1e-6).sum() for k in w)),
        layer_max=max(float(w[k].max()) for k in w),
        z_range=[float(Z.min()), float(Z.max())],
        slope_mean_deg=float(slope[land].mean()),
    )

    meta = dict(area=area, layers=[{'key': k, 'zh': zh, 'rgb': col} for k, zh, col in LEGEND],
                res_m=RES, size=[W, H], row0='north',
                pixel_to_world='x = %g + col*%g ; y = %g - row*%g' % (area['x0'], RES, area['y1'], RES),
                heightmap=dict(file=os.path.relpath(HM_PNG, ROOT),
                               zmin=float(Z.min()), zmax=float(Z.max()),
                               z_formula=json.load(open(HM_META, encoding='utf-8'))['heightmap'].get('z_formula')),
                water=dict(file=os.path.relpath(WMASK, ROOT), area_km2=checks['water_area_km2'],
                           note='水面层 = 最终高度图的水面掩码，逐像素一致'),
                thresholds=dict(SNOW_Z0=SNOW_Z0, SNOW_SPAN=SNOW_SPAN,
                                SNOW_WHITE_SHIFT=SNOW_WHITE_SHIFT, SNOW_REGION_BOOST=SNOW_REGION_BOOST,
                                SNOW_S=SNOW_S,
                                ROCK_SLOPE0=ROCK_SLOPE0, ROCK_SLOPE1=ROCK_SLOPE1, ROCK_V=ROCK_V,
                                DIRT_RED=DIRT_RED, CONIF_V=CONIF_V, CONIF_Z0=CONIF_Z0, CONIF_Z1=CONIF_Z1,
                                BROAD_S=BROAD_S, BROAD_Y=BROAD_Y),
                stats=stats, checks=checks,
                note='权重由 地形色图 + 最终高度图高程/坡度 + 最终高度图水面掩码 推断，非游戏原生分层数据')
    json.dump(meta, open(os.path.join(OUTDIR, 'weights_meta.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    print('栅格 %d×%d @ %.0f m' % (W, H, RES))
    for k, zh, _ in LEGEND:
        print('  %-9s %-6s 均值 %.3f  最大 %.2f  覆盖(>5%%) %.1f%%' % (
            k, zh, stats[k]['mean'], stats[k]['max'], 100 * stats[k]['cover5']))
    print('自检：水面 IoU %.4f  权重和 %.6f~%.6f  单层最大 %.3f  负值格 %d  陆地坡度均值 %.2f°' % (
        iou, checks['weight_sum_min'], checks['weight_sum_max'], checks['layer_max'],
        checks['negative_cells'], checks['slope_mean_deg']))
    print('→ deliverable/terrain_weights/')


if __name__ == '__main__':
    main()
