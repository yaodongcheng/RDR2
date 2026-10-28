"""把我们的高度图/水面和官方地图贴到一起，检查陆地/水域是否对得上。

产物（deliverable/map_check/）
    check_1_side_by_side.png  左=高度图 右=官方地图（同一范围、同一比例）
    check_2_overlay.png       官方地图 + 我方水面(蓝) + 冲突区(红=该有水没水 / 绿=不该有水却有)
    check_3_conflict.png      纯冲突图 + 图例
    check_4_coast_dist.png    我方海岸线到官方海岸线的距离热力图
    check_summary.json        面积统计

坐标：全部用"官方地图像素(1400 宽)"作为公共坐标系，再统一放大到 2692 宽输出。
"""
import os
import json

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None
ROOT = r'D:/BrainMaker/大镖客2解包分析'
OUT = os.path.join(ROOT, 'deliverable/map_check')
HM = os.path.join(ROOT, 'deliverable/heightmap/continent_height_4m.png')
META = os.path.join(ROOT, 'deliverable/heightmap/continent_height_meta.json')
WMASK = os.path.join(ROOT, 'deliverable/heightmap/water_mask.png')
REF_WATER = os.path.join(ROOT, 'docs/世界与地编/img/ref_water_mask_1400.png')
REF_MAP = os.path.join(ROOT, '地图下载/大陆地图_缩略.jpg')
# 地图内容框：以 5000 宽的缩略图为基准
BOX5000 = (146, 388, 4804, 3851)
BOX1400 = tuple(v * 1400 / 5000 for v in BOX5000)

W = 2692          # 输出宽（= 高度图宽）
CELL_M = 4.0      # 每像素米数


def main():
    os.makedirs(OUT, exist_ok=True)
    meta = json.load(open(META, encoding='utf-8'))
    H = meta['size_px'][1]
    zmin, zmax = meta['heightmap']['zmin'], meta['heightmap']['zmax']

    # ---- 统一到 1400 坐标系 → 输出尺寸 ----
    x0, y0, x1, y1 = BOX5000
    scale = W / (x1 - x0)
    Hout = int(round((y1 - y0) * scale))

    def crop_box(img, box, resample=Image.LANCZOS):
        k = img.size[0] / (5000.0 if box is BOX5000 else 1400.0)
        return img.crop(tuple(int(round(v * k)) for v in box)).resize((W, Hout), resample)

    ref = crop_box(Image.open(REF_MAP).convert('RGB'), BOX5000)
    ref_water = np.asarray(crop_box(Image.open(REF_WATER).convert('L'), BOX1400, Image.NEAREST)) > 60
    our_water = np.asarray(Image.open(WMASK).convert('L').resize((W, Hout), Image.NEAREST)) > 128
    q = np.asarray(Image.open(HM).resize((W, Hout), Image.LANCZOS)).astype(np.float32)
    z = zmin + q / 65535.0 * (zmax - zmin)

    area_px = (CELL_M ** 2)
    # 先给 2 px（8 m）容差，把重采样造成的"描边"排除，只看真正对不上的地方
    ref_d2 = ndimage.binary_dilation(ref_water, np.ones((5, 5), bool))
    our_d2 = ndimage.binary_dilation(our_water, np.ones((5, 5), bool))
    miss = ref_water & ~our_d2         # 官方是水、我们没有（容差外）
    extra = our_water & ~ref_d2        # 官方没水、我们却有（容差外）
    print('官方水面 %.2f km²  我方水面 %.2f km²  该有水却没有 %.2f km²  不该有水却有 %.2f km²' % (
        ref_water.sum() * area_px / 1e6, our_water.sum() * area_px / 1e6,
        miss.sum() * area_px / 1e6, extra.sum() * area_px / 1e6))
    inter = (ref_water & our_water).sum()
    print('IoU %.3f  官方水体被覆盖 %.1f%%' % (
        inter / max(1, (ref_water | our_water).sum()), 100 * inter / max(1, ref_water.sum())))

    # ---- 1. 并排 ----
    gy, gx = np.gradient(z, CELL_M)
    slope = np.arctan(np.hypot(gx, gy)); aspect = np.arctan2(-gx, gy)
    hs = np.clip(np.sin(np.radians(45)) * np.cos(slope) +
                 np.cos(np.radians(45)) * np.sin(slope) * np.cos(np.radians(315) - aspect), 0, 1)
    grey = (70 + 175 * hs * np.clip((z - z.min()) / (z.max() - z.min()) * 0.6 + 0.4, 0, 1)).clip(0, 255).astype(np.uint8)
    left = np.dstack([grey, grey, grey])
    left[our_water] = [40, 110, 200]
    sheet = Image.new('RGB', (W * 2 + 10, Hout), (25, 25, 25))
    sheet.paste(Image.fromarray(left), (0, 0))
    sheet.paste(ref, (W + 10, 0))
    d = ImageDraw.Draw(sheet)
    d.text((12, 10), 'OUR HEIGHTMAP (water=blue)', fill=(255, 255, 0))
    d.text((W + 22, 10), 'OFFICIAL MAP', fill=(255, 255, 0))
    sheet.resize((sheet.size[0] // 2, sheet.size[1] // 2), Image.LANCZOS).save(os.path.join(OUT, 'check_1_side_by_side.png'))

    # ---- 2. 叠加 ----
    ov = np.asarray(ref).astype(np.float32)
    ov = ov * 0.93 + 255 * 0.07                                  # 底图保持清楚
    ov[our_water] = ov[our_water] * 0.55 + np.array([40, 110, 200]) * 0.45
    ov[miss] = [235, 40, 40]
    ov[extra] = [30, 170, 80]
    # 我方海岸线描蓝，官方海岸线描红，方便看偏差
    def _edges(m):
        return m & ~ndimage.binary_erosion(m, np.ones((3, 3), bool))
    ov[_edges(our_water)] = [20, 70, 220]
    ov[_edges(ref_water)] = [230, 30, 30]
    Image.fromarray(ov.clip(0, 255).astype(np.uint8)).save(os.path.join(OUT, 'check_2_overlay.png'))

    # ---- 3. 纯冲突图 ----
    cf = np.full((Hout, W, 3), 250, np.uint8)
    cf[ref_water] = [205, 225, 240]
    cf[our_water] = [150, 190, 225]
    cf[miss] = [220, 40, 40]
    cf[extra] = [30, 160, 70]
    img = Image.fromarray(cf)
    dr = ImageDraw.Draw(img)
    items = [('grey-blue = both water', (150, 190, 225)),
             ('RED  official water / we say LAND', (220, 40, 40)),
             ('GREEN official land / we say WATER', (30, 160, 70))]
    for i, (t, c) in enumerate(items):
        dr.rectangle([14, 16 + i * 26, 34, 34 + i * 26], fill=c)
        dr.text((42, 18 + i * 26), t, fill=(20, 20, 20))
    img.save(os.path.join(OUT, 'check_3_conflict.png'))

    # ---- 4. 海岸线距离 ----
    def edges(m):
        er = ndimage.binary_erosion(m, np.ones((3, 3), bool))
        return m & ~er
    e_ref = edges(ref_water); e_our = edges(our_water)
    dist = ndimage.distance_transform_edt(~e_ref) * CELL_M
    dsel = dist[e_our] if e_our.any() else np.array([0])
    print('我方海岸线 → 官方海岸线：中位 %.0f m  P75 %.0f  P90 %.0f' % (
        np.median(dsel), np.percentile(dsel, 75), np.percentile(dsel, 90)))
    # 热力图：地图上面叠加距离
    heat = (np.asarray(ref).astype(np.float32) * 0.45 + 140).clip(0, 255)
    dn = np.clip(dist / 800.0, 0, 1)
    hot = np.stack([255 * dn, 255 * (1 - dn) * (1 - dn), 40 * (1 - dn)], -1)
    m2 = e_our | e_ref
    heat[m2] = heat[m2] * 0.3 + hot[m2] * 0.7
    Image.fromarray(heat.clip(0, 255).astype(np.uint8)).save(os.path.join(OUT, 'check_4_coast_dist.png'))

    # ---- 5. 把冲突聚成"地点清单" ----
    xa, yb = meta['x0'], meta['y1']
    def clusters(mask, name, min_km2=0.02, top=12):
        lab, n = ndimage.label(mask)
        if n == 0:
            return []
        sizes = ndimage.sum(mask, lab, range(1, n + 1)) * area_px / 1e6
        order = np.argsort(sizes)[::-1]
        out = []
        for i in order[:top]:
            if sizes[i] < min_km2:
                break
            ys_, xs_ = np.nonzero(lab == i + 1)
            cx = xa + xs_.mean() * CELL_M
            cy = yb - ys_.mean() * CELL_M
            out.append(dict(kind=name, area_km2=round(float(sizes[i]), 3),
                            world=[round(float(cx)), round(float(cy))],
                            bbox=[round(float(xa + xs_.min() * CELL_M)), round(float(yb - ys_.max() * CELL_M)),
                                  round(float(xa + xs_.max() * CELL_M)), round(float(yb - ys_.min() * CELL_M))]))
        return out
    spots = clusters(miss, 'official_water_we_land') + clusters(extra, 'official_land_we_water')
    # 给每个冲突点标上最近的据点名，方便人去现场看
    try:
        import csv as _csv
        names = []
        for r in _csv.DictReader(open(os.path.join(ROOT, 'export/levels/world/settlements_bannerlord.csv'),
                                      encoding='utf-8-sig')):
            names.append((r.get('name_zh') or r['code'],
                          -7684.0 + float(r['u']) * 14.5, 4100.0 - float(r['v']) * 14.5))
        for sp in spots:
            cx, cy = sp['world']
            nm, d = min(((n, ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5) for n, x, y in names), key=lambda t: t[1])
            sp['nearest'] = nm
            sp['nearest_m'] = int(d)
    except Exception as e:
        print('据点名匹配失败', e)
    spots.sort(key=lambda d: -d['area_km2'])
    print('主要冲突点（面积 km² / 世界坐标）：')
    for sp in spots[:10]:
        print('  %-24s %.3f km²  (%d, %d)  最近据点：%s %d m' % (
            sp['kind'], sp['area_km2'], sp['world'][0], sp['world'][1],
            sp.get('nearest', '?'), sp.get('nearest_m', 0)))

    summary = dict(
        official_water_km2=float(ref_water.sum() * area_px / 1e6),
        our_water_km2=float(our_water.sum() * area_px / 1e6),
        missing_water_km2=float(miss.sum() * area_px / 1e6),
        extra_water_km2=float(extra.sum() * area_px / 1e6),
        water_iou=float(inter / max(1, (ref_water | our_water).sum())),
        coast_dist_median_m=float(np.median(dsel)),
        coast_dist_p90_m=float(np.percentile(dsel, 90)),
        size=[W, Hout], px_m=CELL_M,
        clusters=spots,
    )
    json.dump(summary, open(os.path.join(OUT, 'check_summary.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('→', OUT)


if __name__ == '__main__':
    main()
