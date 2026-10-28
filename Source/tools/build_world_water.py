"""生成全图**水面**数据：水位栅格 + 水面掩码。

RDR2 的 `waterheight.dat` 还没解（已知 magic `RTAW`），所以这里用近似：
  · 湖泊 / 海 / 池塘 / 沼泽 —— 逐水体取该多边形内高程的 30 分位当**水平面**（真实感最好）
  · 河流 / 溪流 —— 水面贴着河床走（高程 + 0.25 m），避免长距离河道被一个平水位淹没

产物（2048²，与 world_height_2048.r16 同网格、同行序：**行 0 = 南**）：
  export/world/world_water_2048.png        掩码（255 = 有水）
  export/world/world_water_level_2048.r16  水位（uint16，按 zmin/zmax 归一化）
  export/world/world_water.json            zmin/zmax 与统计

用法：uv run python tools/build_world_water.py
"""
import os
import json
import numpy as np
from PIL import Image, ImageDraw

ROOT = r'D:/BrainMaker/大镖客2解包分析'
H4 = os.path.join(ROOT, 'work/terrain/H4.npy')
ZONES = os.path.join(ROOT, 'export/levels/world/zones.json')
META = os.path.join(ROOT, 'export/world/world_meta.json')
OUT = os.path.join(ROOT, 'export/world')
WORK = os.path.join(ROOT, 'work/world')

X0, Y0, RES = -7684.0, -8196.0, 4.0
WORLD = 12296.0
N = 2048

FLAT = ('OCEAN', 'LAKE', 'POND', 'SWAMP')
LINEAR = ('RIVER', 'CREEK')


def w2px(x, y, n=N):
    """世界 → 像素（行 0 = 南，与 r16 一致）"""
    return (x - X0) / WORLD * n, (y - Y0) / WORLD * n


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    H = np.load(H4).astype(np.float32)
    meta = json.load(open(META, encoding='utf-8'))
    zmin, zmax = meta['z']
    span = max(1e-6, zmax - zmin)

    def height(px, py):
        """像素坐标 → 高程（H4 是 4 m 网格，行 0 = 南）"""
        fx = np.clip((px / N * WORLD) / RES, 0, H.shape[1] - 1.001)
        fy = np.clip((py / N * WORLD) / RES, 0, H.shape[0] - 1.001)
        return H[fy.astype(int), fx.astype(int)]

    zones = json.load(open(ZONES, encoding='utf-8'))['zones']
    mask = Image.new('L', (N, N), 0)
    dm = ImageDraw.Draw(mask)
    level = np.zeros((N, N), np.float32)
    filled = np.zeros((N, N), bool)

    stat = {'flat': [], 'linear': []}

    for z in zones:
        t = z['type']
        if t not in FLAT and t not in LINEAR:
            continue
        for poly in z.get('polygons') or []:
            pts = [w2px(x, y) for x, y in poly]
            if len(pts) < 3:
                continue
            # 逐多边形算水位
            tmp = Image.new('L', (N, N), 0)
            ImageDraw.Draw(tmp).polygon(pts, fill=255)
            a = np.asarray(tmp) > 0
            if not a.any():
                continue
            hs = height(*np.nonzero(a)[::-1])
            if t in LINEAR:
                lvl = float(np.percentile(hs, 55))     # 河道：贴近河床
                stat['linear'].append((z['name'], round(lvl, 1)))
            else:
                lvl = float(np.percentile(hs, 35))     # 湖/海：取低处当水面
                stat['flat'].append((z['name'], round(lvl, 1)))
            level[a] = lvl
            filled |= a
            dm.polygon(pts, fill=255)

    # 河流/溪流：水面 = 地形 + 0.25 m（跟着河床走）
    water = np.asarray(mask) > 0
    if water.any():
        yy, xx = np.nonzero(water)
        hh = height(xx, yy)
        lv = level[yy, xx]
        # 对 LINEAR 水体，用「地形 + 0.25」覆盖；判断方式：该点水位与地形差太大
        diff = lv - hh
        follow = np.abs(diff) > 6.0
        lv[follow] = hh[follow] + 0.25
        level[yy, xx] = lv

    Ln = np.clip((level - zmin) / span * 65535, 0, 65535).astype('<u2')
    Ln.tofile(os.path.join(OUT, 'world_water_level_2048.r16'))
    Image.fromarray((water * 255).astype(np.uint8)).save(os.path.join(OUT, 'world_water_2048.png'))

    json.dump(dict(z=[zmin, zmax], px=N, m_per_px=round(WORLD / N, 3),
                   row0='south', flat=stat['flat'][:40], linear=stat['linear'][:40]),
              open(os.path.join(OUT, 'world_water.json'), 'w'), ensure_ascii=False, indent=1)

    # 预览图（叠加在颜色上）
    col = Image.open(os.path.join(OUT, 'world_color_2048.png')).convert('RGB')
    arr = np.asarray(col).astype(np.float32)
    arr[water] = arr[water] * 0.35 + np.array([40, 90, 120]) * 0.65
    Image.fromarray(arr.astype(np.uint8)).resize((1200, 1200), Image.LANCZOS).save(
        os.path.join(WORK, 'world_water_preview.png'))
    print('水面 %.1f%%  湖/海 %d 个  河/溪 %d 个' %
          (water.mean() * 100, len(stat['flat']), len(stat['linear'])))
    print('  ->', os.path.join(OUT, 'world_water_level_2048.r16'))
    print('  preview:', os.path.join(WORK, 'world_water_preview.png'))


if __name__ == '__main__':
    main()
