"""合成整张 RDR2 世界的**地面颜色图**（用于野外瓦片 / 大地图 / 远景 apron）。

数据源：
  · work/terrain/H4.npy              4 m 真高程（3075²，覆盖 12300 m）
  · export/levels/world/zones.json   87 个官方 zone（STATE / DISTRICT / 水系 / TOWN 多边形）

做法（不依赖每块地形瓦片的 `<tile>_t`，那需要抽 10 GB 贴图）：
  1) 按 STATE 多边形铺**生态底色**（雪原/草原/沼泽/荒漠/森林/热带）
  2) 叠坡度 → 岩石、海拔 → 雪线
  3) 水系多边形（OCEAN/RIVER/LAKE/POND/CREEK/SWAMP）压成水色
  4) TOWN 多边形混入城镇灰
  5) 低频噪声打散，避免大色块

产物：
  export/world/world_color_4096.png   4096² RGB（3 m/px，供瓦片裁切）
  export/world/world_color_2048.png   2048²（网页用）
  export/world/world_height_2048.r16  2048² uint16（网页采样高程）
  export/world/world_meta.json        世界↔像素↔大地图 三套坐标的换算参数
  work/world/world_color_preview.png  晕渲预览（验收用）

用法：uv run python tools/build_world_color.py
"""
import os
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = r'D:/BrainMaker/大镖客2解包分析'
H4 = os.path.join(ROOT, 'work/terrain/H4.npy')
ZONES = os.path.join(ROOT, 'export/levels/world/zones.json')
OUT = os.path.join(ROOT, 'export/world')
WORK = os.path.join(ROOT, 'work/world')

X0, Y0, RES = -7684.0, -8196.0, 4.0        # H4 原点 / 采样间距
WORLD = 12296.0
XM1, YM1 = X0 + WORLD, Y0 + WORLD          # 4612, 4100
MAP = 848.0                                 # 骑砍2 大地图单位
N = 4096                                    # 颜色图分辨率

# 生态底色（sRGB）
STATE_COLOR = {
    'Ambarino':          (118, 122, 112),
    'Lemoyne':           ( 86, 102,  62),
    'NewAustin':         (170, 143, 100),
    'NewHanover':        (118, 126,  74),
    'NuevoParaiso':      (158, 122,  88),
    'WestElizabeth':     ( 88, 106,  66),
    'LowerWestElizabeth':( 96, 112,  70),
    'UpperWestElizabeth':( 84, 100,  62),
    'Guarma':            ( 86, 124,  72),
}
DEFAULT = (104, 110,  86)


def w2px(x, y, n=N):
    """世界坐标 → 像素（行 0 = 北）"""
    px = (x - X0) / WORLD * n
    py = (YM1 - y) / WORLD * n
    return px, py


def raster_zones(n=N):
    """→ (state_rgb[n,n,3], water_mask[n,n], town_mask[n,n])

    州界做 **羽化混合**（每州单独 mask → 高斯羽化），避免大地图上出现生硬色块直线。
    """
    zones = json.load(open(ZONES, encoding='utf-8'))['zones']
    acc = np.zeros((n, n, 3), np.float32)
    wsum = np.zeros((n, n, 1), np.float32)
    for z in zones:
        if z['type'] not in ('STATE',):
            continue
        col = STATE_COLOR.get(z['name'])
        if col is None:
            continue
        m = Image.new('L', (n, n), 0)
        dm = ImageDraw.Draw(m)
        for poly in z.get('polygons') or []:
            pts = [w2px(x, y, n) for x, y in poly]
            if len(pts) >= 3:
                dm.polygon(pts, fill=255)
        a = np.asarray(m.filter(ImageFilter.GaussianBlur(6))).astype(np.float32) / 255.0
        acc += a[..., None] * np.array(col, np.float32)
        wsum += a[..., None]
    # 未被任何州覆盖的区域（地图外的自由地形）回退底色
    base = np.where(wsum > 0.02, acc / np.maximum(wsum, 1e-6), np.array(DEFAULT, np.float32))
    state_img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))

    water = Image.new('L', (n, n), 0)
    dw = ImageDraw.Draw(water)
    swamp = Image.new('L', (n, n), 0)
    dws = ImageDraw.Draw(swamp)
    for z in zones:
        if z['type'] in ('OCEAN', 'RIVER', 'LAKE', 'POND', 'CREEK'):
            for poly in z.get('polygons') or []:
                pts = [w2px(x, y, n) for x, y in poly]
                if len(pts) >= 3:
                    dw.polygon(pts, fill=255)
        elif z['type'] == 'SWAMP':
            for poly in z.get('polygons') or []:
                pts = [w2px(x, y, n) for x, y in poly]
                if len(pts) >= 3:
                    dws.polygon(pts, fill=200)

    town = Image.new('L', (n, n), 0)
    dt = ImageDraw.Draw(town)
    for z in zones:
        if z['type'] == 'TOWN':
            for poly in z.get('polygons') or []:
                pts = [w2px(x, y, n) for x, y in poly]
                if len(pts) >= 3:
                    dt.polygon(pts, fill=170)

    return (np.asarray(state_img).astype(np.float32),
            np.asarray(water).astype(np.float32) / 255.0,
            np.asarray(swamp).astype(np.float32) / 255.0,
            np.asarray(town).astype(np.float32) / 255.0)


def load_height(n=N):
    H = np.load(H4).astype(np.float32)
    img = Image.fromarray(H, mode='F').resize((n, n), Image.BILINEAR)
    Z = np.asarray(img).astype(np.float32)
    # 坡度（m/m），用相邻像素差 / 每像素米数
    mpp = WORLD / n
    gy, gx = np.gradient(Z, mpp)
    slope = np.sqrt(gx * gx + gy * gy)
    return Z, slope, gx, gy


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    print('rasterize zones ...')
    base, water, swamp, town = raster_zones(N)
    print('height + slope ...')
    Z, slope, gx, gy = load_height(N)

    rgb = base.copy()
    # 坡度 → 岩石（陡坡露岩）
    rock = np.clip((slope - 0.55) / 1.6, 0, 1)[..., None]
    rgb = rgb * (1 - rock * 0.75) + np.array([118, 110, 100]) * (rock * 0.75)

    # 海拔 → 雪线（只在 Ambarino 一带高海拔）
    snow = np.clip((Z - 520) / 160, 0, 1)[..., None] * 0.85
    rgb = rgb * (1 - snow) + np.array([228, 231, 236]) * snow

    # 低频噪声（分形值噪声，用缩放的高斯随机场近似）
    rng = np.random.default_rng(7)
    noise = np.zeros((N, N), np.float32)
    for s, w in ((64, 0.55), (128, 0.3), (256, 0.15)):
        f = rng.normal(0, 1, (s, s)).astype(np.float32)
        noise += w * np.asarray(Image.fromarray(f, mode='F').resize((N, N), Image.BICUBIC))
    noise = noise / (np.abs(noise).max() + 1e-6)
    rgb = rgb * (1 + noise[..., None] * 0.10)

    # 水系：水体压暗偏蓝；沼泽偏墨绿
    wcol = np.array([54, 76, 84], np.float32)
    rgb = rgb * (1 - water[..., None] * 0.88) + wcol * (water[..., None] * 0.88)
    scol = np.array([64, 82, 62], np.float32)
    rgb = rgb * (1 - swamp[..., None] * 0.55) + scol * (swamp[..., None] * 0.55)

    # 城镇：混灰（城区地面在游戏里是铺装）
    tcol = np.array([112, 108, 100], np.float32)
    rgb = rgb * (1 - town[..., None] * 0.65) + tcol * (town[..., None] * 0.65)

    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    Image.fromarray(rgb).save(os.path.join(OUT, 'world_color_4096.png'))
    Image.fromarray(rgb).resize((2048, 2048), Image.LANCZOS).save(
        os.path.join(OUT, 'world_color_2048.png'))

    # 高程：uint16 归一化，meta 里存 zmin/zmax
    zmin, zmax = float(Z.min()), float(Z.max())
    span = max(1e-6, zmax - zmin)
    Hn = np.clip((Z - zmin) / span * 65535, 0, 65535).astype('<u2')
    Hn.tofile(os.path.join(OUT, 'world_height_4096.r16'))       # 32 MB，烘场景用
    Hn[::2, ::2].copy().tofile(os.path.join(OUT, 'world_height_2048.r16'))  # 8 MB，网页用

    # 晕渲预览
    nx, ny = -gx, gy
    nl = np.sqrt(nx * nx + ny * ny + 1.0)
    light = np.array([-0.5, -0.45, 0.74], np.float32)
    shade = np.clip((nx * light[0] + ny * light[1] + light[2]) / nl, 0, 1)
    vis = np.clip(rgb.astype(np.float32) * (0.55 + 0.65 * shade[..., None]), 0, 255).astype(np.uint8)
    Image.fromarray(vis).resize((1400, 1400), Image.LANCZOS).save(
        os.path.join(WORK, 'world_color_preview.png'))

    meta = dict(
        world_m=WORLD, origin=[X0, Y0], res_m=RES, z=[zmin, zmax],
        color_px=N, color_m_per_px=round(WORLD / N, 4),
        height_px=4096, height_r16='world_height_2048.r16', height_r16_full='world_height_4096.r16',
        campaign_map_units=MAP, campaign_m_per_unit=round(WORLD / MAP, 4),
        campaign_origin=[X0, Y0 + WORLD],   # 大地图 (0,0) 对应的世界坐标（左上角）
    )
    json.dump(meta, open(os.path.join(OUT, 'world_meta.json'), 'w'), ensure_ascii=False, indent=1)
    print('done  color 4096  height 2048  z %.1f~%.1f m' % (zmin, zmax))
    print('  ->', os.path.join(OUT, 'world_color_4096.png'))
    print('  preview:', os.path.join(WORK, 'world_color_preview.png'))


if __name__ == '__main__':
    main()
