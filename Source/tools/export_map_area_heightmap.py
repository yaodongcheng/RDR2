"""定义"大陆 = 官方地图范围"，并把这块范围导出成高度图（16 bit）。

为什么是这个范围
----------------
`地图下载/大陆地图.jpg` 是游戏内地图（14592×11264），四周是纸边。
按"非纸边内容"的包围盒取到地图框（5000 宽缩略图上 x 146..4804 / y 388..3851），
再用 `地图下载/配准结果.json` 的相似变换反算到世界坐标，得到：

    x ∈ [-6840, 3920]   y ∈ [-4796, 3224]     10760 × 8020 m

这个框天然排除瓜玛岛（瓜玛在 y≈-7000，框外），所以"大陆不含瓜玛"是裁剪的副产物。

产物（deliverable/heightmap/）
------------------------------
    continent_height_4m.png     16 bit 灰度，1 px = 4 m，值 = (z-zmin)/(zmax-zmin)*65535
    continent_height_r16.raw    同尺寸 16 bit 小端原始数据（引擎直读用）
    continent_height_meta.json  origin / 分辨率 / z 范围 / 尺寸
    continent_height_preview.png 彩色高程 + 山影（只是给人看的）

用法：
    uv run python tools/export_map_area_heightmap.py
"""
import os
import json

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ROOT = r'D:/BrainMaker/大镖客2解包分析'
H4 = os.path.join(ROOT, 'work/terrain/H4_full.npy')
OUTDIR = os.path.join(ROOT, 'deliverable/heightmap')
AREA = os.path.join(ROOT, 'export/world/map_area.json')

# 官方地图内容框（5000 宽缩略图上的像素）
MAP_PX = (146, 388, 4804, 3851)
MAP_PX_FULL = (5000, 3916)
X0w, Y0w, WORLD, SCALE = -7684.0, -8196.0, 12296.0, 14.5
RES = 4.0


def map_area():
    """官方地图内容框 → 世界矩形（轴对齐 bbox，对齐到 4 m 栅格）。"""
    fit = json.load(open(os.path.join(ROOT, '地图下载/配准结果.json'), encoding='utf-8'))
    a, c, tx, ty = fit['a'], fit['c'], fit['tx'], fit['ty']
    ym1 = 4100.0
    k = 1400.0 / MAP_PX_FULL[0]
    det = a * a + c * c

    def m2w(mx, my):
        px, py = mx - tx, my - ty
        u = (a * px + c * py) / det
        v = (-c * px + a * py) / det
        return X0w + u * SCALE, ym1 - v * SCALE

    x0, y0, x1, y1 = MAP_PX
    pts = np.array([m2w(X * k, Y * k) for X in (x0, x1) for Y in (y0, y1)])
    bx0 = np.floor(pts[:, 0].min() / RES) * RES
    bx1 = np.ceil(pts[:, 0].max() / RES) * RES
    by0 = np.floor(pts[:, 1].min() / RES) * RES
    by1 = np.ceil(pts[:, 1].max() / RES) * RES
    return dict(x0=float(bx0), x1=float(bx1), y0=float(by0), y1=float(by1),
                res_m=RES, src_map='地图下载/大陆地图.jpg',
                src_px_bbox=list(MAP_PX), src_px_size=list(MAP_PX_FULL),
                registration='地图下载/配准结果.json')


def load_height(area):
    H = np.load(H4)                       # 4 m，行 0 = 南
    nx, ny = H.shape[1], H.shape[0]

    def idx(v, o):
        return int(round((v - o) / RES))
    c0, c1 = idx(area['x0'], X0w), idx(area['x1'], X0w)
    r0, r1 = idx(area['y0'], Y0w), idx(area['y1'], Y0w)
    c0, c1 = max(0, c0), min(nx, c1)
    r0, r1 = max(0, r0), min(ny, r1)
    return H[r0:r1, c0:c1].astype(np.float32)


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    area = map_area()
    area['size_px'] = [int(round((area['x1'] - area['x0']) / RES)),
                       int(round((area['y1'] - area['y0']) / RES))]
    area['size_m'] = [area['x1'] - area['x0'], area['y1'] - area['y0']]
    json.dump(area, open(AREA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('地图范围  世界 x[%.0f,%.0f] y[%.0f,%.0f]  %.0f × %.0f m  栅格 %d × %d @ %.0f m' % (
        area['x0'], area['x1'], area['y0'], area['y1'],
        area['size_m'][0], area['size_m'][1], area['size_px'][0], area['size_px'][1], RES))

    Z = load_height(area)                 # 行 0 = 南
    zmin, zmax = float(Z.min()), float(Z.max())
    q = np.clip((Z - zmin) / max(1e-6, zmax - zmin) * 65535.0, 0, 65535).astype('<u2')
    # 统一成"北在上"：PNG/RAW 行 0 = 北（和权重图、预览图一致，也和所有人看地图的习惯一致）
    q = np.flipud(q).copy()

    png = os.path.join(OUTDIR, 'continent_height_4m.png')
    Image.fromarray(q).save(png)          # 模式 I;16
    open(os.path.join(OUTDIR, 'continent_height_r16.raw'), 'wb').write(q.tobytes(order='C'))

    meta = dict(**area, heightmap=dict(
        file_16bit='continent_height_4m.png', file_raw='continent_height_r16.raw',
        res_m=RES, w=area['size_px'][0], h=area['size_px'][1],
        zmin=zmin, zmax=zmax,
        row0='north',
        note='PNG/RAW 行 0 = 北（世界 y 最大），列 0 = 西；数值 = (z-zmin)/(zmax-zmin)*65535',
        pixel_to_world='x = x0 + col*4 ; y = y1 - row*4',
        z_formula='z = zmin + v/65535*(zmax-zmin)'))
    json.dump(meta, open(os.path.join(OUTDIR, 'continent_height_meta.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    # 预览：高程分层设色 + 山影；并和"游戏地形色图"并排，用来核对朝向/范围
    gy, gx = np.gradient(Z, RES)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = np.radians(315), np.radians(45)
    hs = np.clip(np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect), 0, 1)
    stops_z = [zmin, zmin + 0.06 * (zmax - zmin), zmin + 0.25 * (zmax - zmin),
               zmin + 0.5 * (zmax - zmin), zmin + 0.72 * (zmax - zmin), zmax]
    stops_c = [(46, 84, 52), (70, 120, 62), (128, 150, 82), (168, 152, 110), (200, 198, 196), (255, 255, 255)]
    rgb = np.zeros(Z.shape + (3,), np.float32)
    for ch in range(3):
        rgb[..., ch] = np.interp(Z, stops_z, [c[ch] for c in stops_c])
    rgb = (rgb * (0.45 + 0.75 * hs[..., None])).clip(0, 255).astype(np.uint8)
    Image.fromarray(rgb[::-1]).save(os.path.join(OUTDIR, 'continent_height_preview.png'))

    # 并排核对：左=高度图，右=游戏地形色图（同一范围、同一栅格）
    try:
        col = Image.open(os.path.join(ROOT, 'export/world/world_ground_final_out.png')).convert('RGB')
        # 色图 1 px = 1 m（12296²），高度图 1 px = 4 m → 两边换算不同
        px0 = int(round(area['x0'] - X0w)); px1 = int(round(area['x1'] - X0w))
        py_n0 = int(round(Y0w + WORLD - area['y1'])); py_n1 = int(round(Y0w + WORLD - area['y0']))
        sub = col.crop((px0, py_n0, px1, py_n1)).resize((area['size_px'][0], area['size_px'][1]), Image.LANCZOS)
        W2 = area['size_px'][0] // 2
        himg = Image.fromarray(rgb[::-1]).resize((W2, int(W2 * Z.shape[0] / Z.shape[1])), Image.LANCZOS)
        cimg = sub.resize((W2, himg.size[1]), Image.LANCZOS)
        sheet = Image.new('RGB', (W2 * 2 + 8, himg.size[1]), (20, 20, 20))
        sheet.paste(himg, (0, 0)); sheet.paste(cimg, (W2 + 8, 0))
        sheet.save(os.path.join(OUTDIR, 'continent_height_vs_color.png'))
        print('→ continent_height_vs_color.png（左=高度图 右=地形色图，用来核对范围/朝向）')
    except Exception as e:
        print('并排核对图失败:', e)

    print('→ %s  %d×%d  高程 %.1f~%.1f m' % (png, area['size_px'][0], area['size_px'][1], zmin, zmax))
    print('→ preview / r16 / meta 都在 deliverable/heightmap/')


if __name__ == '__main__':
    main()
