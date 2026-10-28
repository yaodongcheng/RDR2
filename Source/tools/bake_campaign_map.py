"""烘「骑砍2 大地图」：把 RDR2 12296 m 世界压到 848×848 单位。

两套尺度（这是关键，之前混了）：
  · 大地图（campaign）：848 × 848 单位 ≈ 12296 m ⇒ 1 单位 = 14.50 m
  · 场景（settlement / wilderness）：848 × 848 单位 = 848 m 实景 ⇒ 1 单位 = 1 m

产出：
  campaign_height.r16 / .png   848² 或 4096² 高程（归一化 uint16）
  campaign_color.png           2048² 俯视颜色
  campaign.json                世界↔大地图 变换参数、据点坐标

用法：
  uv run python tools/bake_campaign_map.py --out work/campaign
"""
import os
import json
import argparse
import numpy as np
from PIL import Image

ROOT = r'D:/BrainMaker/大镖客2解包分析'
H4 = os.path.join(ROOT, 'work/terrain/H4.npy')
X0, Y0, RES = -7684.0, -8196.0, 4.0
GROUND_JSON = os.path.join(ROOT, 'export/levels/world/blender/terrain/sdn_ground.json')
GROUND_PNG = os.path.join(ROOT, 'export/levels/world/blender/terrain/sdn_ground.png')
WORLD = 12296.0
MAP = 848.0
SCALE = WORLD / MAP          # m per campaign unit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'work/campaign'))
    ap.add_argument('--res', type=int, default=848, help='大地图高程分辨率')
    ap.add_argument('--color-res', type=int, default=2048)
    ap.add_argument('--min', type=float, default=-7684.0)
    ap.add_argument('--miny', type=float, default=-8196.0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    H = np.load(H4)
    # 大地图像素 → 世界坐标
    u = np.linspace(0, MAP, a.res)
    xs = a.min + u * SCALE
    ys = (a.miny + WORLD) - u * SCALE          # 行 0 = 北
    XX, YY = np.meshgrid(xs, ys)
    fx = np.clip((XX - X0) / RES, 0, H.shape[1] - 1.001)
    fy = np.clip((YY - Y0) / RES, 0, H.shape[0] - 1.001)
    x0 = fx.astype(int); y0 = fy.astype(int)
    tx = fx - x0; ty = fy - y0
    Z = (H[y0, x0] * (1 - tx) * (1 - ty) + H[y0, x0 + 1] * tx * (1 - ty)
         + H[y0 + 1, x0] * (1 - tx) * ty + H[y0 + 1, x0 + 1] * tx * ty).astype(np.float32)

    zmin, zmax = float(Z.min()), float(Z.max())
    span = max(1e-6, zmax - zmin)
    Hn = np.clip((Z - zmin) / span * 65535, 0, 65535).astype('<u2')
    Hn.tofile(os.path.join(a.out, 'campaign_height.r16'))
    Image.fromarray(((Hn.astype(np.float32) / 65535) * 255).astype(np.uint8)).resize(
        (a.color_res, a.color_res)).save(os.path.join(a.out, 'campaign_height.png'))

    # 颜色：有覆盖区就裁，否则按高度着色
    color = None
    if os.path.exists(GROUND_JSON):
        meta = json.load(open(GROUND_JSON, encoding='utf-8'))
        gx0, gy0, gx1, gy1 = meta['region']
        img = Image.open(GROUND_PNG)
        canvas = Image.new('RGB', (a.color_res, a.color_res), (60, 66, 52))
        # 覆盖区换算到大地图像素
        px0 = int((gx0 - a.min) / WORLD * a.color_res); px1 = int((gx1 - a.min) / WORLD * a.color_res)
        top = int(((a.miny + WORLD) - gy1) / WORLD * a.color_res)
        bot = int(((a.miny + WORLD) - gy0) / WORLD * a.color_res)
        crop = img.crop((0, 0, img.size[0], img.size[1])).resize((max(1, px1 - px0), max(1, bot - top)), Image.LANCZOS)
        canvas.paste(crop, (px0, top))
        color = np.asarray(canvas)
        print('  color: 已贴入 sdn_ground 覆盖区（其余为底色）')
    if color is None:
        t = np.clip((Z - zmin) / span, 0, 1)[..., None]
        color = (np.array([90, 100, 70]) * (1 - t) + np.array([170, 165, 160]) * t).astype(np.uint8)
        color = np.asarray(Image.fromarray(color).resize((a.color_res, a.color_res)))
    Image.fromarray(color).save(os.path.join(a.out, 'campaign_color.png'))

    # 据点：世界坐标 → 大地图坐标
    towns = json.load(open(os.path.join(ROOT, 'export/levels/world/towns.json'), encoding='utf-8'))['towns']
    out_towns = []
    for t in towns:
        x, y = t.get('cx'), t.get('cy')
        if x is None:
            continue
        cu = (x - a.min) / SCALE
        cv = ((a.miny + WORLD) - y) / SCALE
        if -50 <= cu <= MAP + 50 and -50 <= cv <= MAP + 50:
            out_towns.append(dict(name=t.get('name'), code=t.get('code'), u=round(cu, 2), v=round(cv, 2)))

    json.dump(dict(world_m=WORLD, map_units=MAP, scale_m_per_unit=round(SCALE, 3),
                   world_origin=[a.min, a.miny], res=a.res, z=[zmin, zmax],
                   towns=out_towns),
              open(os.path.join(a.out, 'campaign.json'), 'w'), ensure_ascii=False, indent=1)
    print('campaign %d² 高程 %.1f~%.1f m，比例 1 单位 = %.2f m' % (a.res, zmin, zmax, SCALE))
    print('据点落图 %d 个 -> %s' % (len(out_towns), os.path.join(a.out, 'campaign.json')))


if __name__ == '__main__':
    main()
