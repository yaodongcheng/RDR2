"""按骑砍2 规格烘一块野外场景瓦片：848 m × 848 m，高度图 4096²。

产出（每块）：
  <name>_height.r16   uint16 小端，4096×4096（骑砍2 常用原始高度图）
  <name>_height.png   16-bit 灰度（可视化/校验）
  <name>_color.png    4096² 地面颜色（有覆盖的区域来自 RDR2 地形颜色图）
  <name>.json         元数据（世界范围、高程 min/max、分辨率）

用法：
  uv run python tools/bake_scene_tile.py --cx 2200 --cy -900 --out work/scenes
"""
import os
import sys
import json
import argparse
import numpy as np
from PIL import Image

ROOT = r'D:/BrainMaker/大镖客2解包分析'
H4 = os.path.join(ROOT, 'work/terrain/H4.npy')
X0, Y0, RES = -7684.0, -8196.0, 4.0
GROUND_JSON = os.path.join(ROOT, 'export/levels/world/blender/terrain/sdn_ground.json')
GROUND_PNG = os.path.join(ROOT, 'export/levels/world/blender/terrain/sdn_ground.png')
SIZE = 4096
SCENE = 848.0


def sample_bilinear(H, xs, ys):
    """双线性采样 H4（世界坐标 → 高程）"""
    fx = (xs - X0) / RES
    fy = (ys - Y0) / RES
    x0 = np.floor(fx).astype(np.int64); y0 = np.floor(fy).astype(np.int64)
    x1 = np.clip(x0 + 1, 0, H.shape[1] - 1); y1 = np.clip(y0 + 1, 0, H.shape[0] - 1)
    x0 = np.clip(x0, 0, H.shape[1] - 1); y0 = np.clip(y0, 0, H.shape[0] - 1)
    tx = np.clip(fx - x0, 0, 1); ty = np.clip(fy - y0, 0, 1)
    return (H[y0, x0] * (1 - tx) * (1 - ty) + H[y0, x1] * tx * (1 - ty)
            + H[y1, x0] * (1 - tx) * ty + H[y1, x1] * tx * ty)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cx', type=float, required=True)
    ap.add_argument('--cy', type=float, required=True)
    ap.add_argument('--size', type=float, default=SCENE)
    ap.add_argument('--res', type=int, default=SIZE)
    ap.add_argument('--out', default=os.path.join(ROOT, 'work/scenes'))
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    H = np.load(H4)
    half = a.size / 2
    x0w, y0w = a.cx - half, a.cy - half
    x1w, y1w = a.cx + half, a.cy + half

    xs = np.linspace(x0w, x1w, a.res)
    ys = np.linspace(y1w, y0w, a.res)        # 行 0 = 北
    XX, YY = np.meshgrid(xs, ys)
    Z = sample_bilinear(H, XX, YY).astype(np.float32)

    zmin, zmax = float(Z.min()), float(Z.max())
    print('scene %.0fx%.0f m  高程 %.2f ~ %.2f m  (跨度 %.2f)' % (a.size, a.size, zmin, zmax, zmax - zmin))

    # 高度图：归一化到 uint16（0..65535），元数据里保留 zmin/zmax
    span = max(1e-6, zmax - zmin)
    Hn = np.clip((Z - zmin) / span * 65535.0, 0, 65535).astype('<u2')

    name = 'wild_%d_%d' % (int(np.floor(a.cx / SCENE)), int(np.floor(a.cy / SCENE)))
    p_r16 = os.path.join(a.out, name + '_height.r16')
    Hn.tofile(p_r16)

    p_png = os.path.join(a.out, name + '_height.png')
    Image.fromarray(((Hn.astype(np.float32) / 65535.0) * 255).astype(np.uint8)).save(p_png)

    # 颜色：若该范围落在已烘的 sdn_ground 覆盖区内就裁切，否则用按高度上色
    color = None
    if os.path.exists(GROUND_JSON) and os.path.exists(GROUND_PNG):
        meta = json.load(open(GROUND_JSON, encoding='utf-8'))
        gx0, gy0, gx1, gy1 = meta['region']
        if x0w >= gx0 and y0w >= gy0 and x1w <= gx1 and y1w <= gy1:
            img = Image.open(GROUND_PNG)
            W, Hh = img.size
            px0 = int((x0w - gx0) / (gx1 - gx0) * W); px1 = int((x1w - gx0) / (gx1 - gx0) * W)
            top = int((gy1 - y1w) / (gy1 - gy0) * Hh); bot = int((gy1 - y0w) / (gy1 - gy0) * Hh)
            color = np.asarray(img.crop((px0, top, px1, bot)).convert('RGB').resize((a.res, a.res), Image.LANCZOS))
            print('  color: 取自 sdn_ground 覆盖区')
    if color is None:
        # 高度渐变占位（沙→草→岩）
        t = np.clip((Z - zmin) / span, 0, 1)[..., None]
        lo = np.array([120, 110, 85]); mid = np.array([88, 105, 60]); hi = np.array([150, 150, 145])
        color = (lo * (1 - np.clip(t * 2, 0, 1)) + mid * np.clip(t * 2, 0, 1) * (t < 0.5)
                 + mid * (1 - np.clip((t - 0.5) * 2, 0, 1)) * (t >= 0.5)
                 + hi * np.clip((t - 0.5) * 2, 0, 1)).astype(np.uint8)
        print('  color: 高度渐变占位（该区域无颜色图）')
    p_color = os.path.join(a.out, name + '_color.png')
    Image.fromarray(color).save(p_color)

    json.dump(dict(name=name, size_m=a.size, res=a.res,
                   world=[x0w, y0w, x1w, y1w], z=[zmin, zmax],
                   height_r16=os.path.basename(p_r16), height_png=os.path.basename(p_png),
                   color_png=os.path.basename(p_color),
                   rdr2_source='H4.npy 4m + <tile>_t 0.25m/px'),
              open(os.path.join(a.out, name + '.json'), 'w'), indent=1)
    print('  -> %s  (%.1f MB)' % (name, os.path.getsize(p_r16) / 1048576))


if __name__ == '__main__':
    main()
