"""生成"补完版"地形输入：合并外延地形后的掩码 + 地面贴图。

⚠️ 朝向约定（踩过坑，写死在这里）：
  work/terrain/H4*.npy / valid*.npy   row 0 = 南（y = Y0 + row*4）
  export/world/*.png（掩码/色图）     row 0 = 北（图像习惯）
  blender_continent.terrain() 采样掩码时已按 (ny-1-rows) 做翻转。

产物：
  export/world/world_ground_mask.png.bak          原掩码备份
  export/world/world_ground_mask_full.png         主 + 外延 掩码（北朝上）
  export/world/world_ground_final_out.png         主色图 + 外延色图（北朝上）
"""
import os
import shutil

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ROOT = r'D:/BrainMaker/大镖客2解包分析'
W = 12296


def main():
    main_mask = np.asarray(Image.open(os.path.join(ROOT, 'export/world/world_ground_mask.png')).convert('L')) > 10  # north-up
    valid_full = np.load(os.path.join(ROOT, 'work/terrain/valid_full.npy'))   # south-up
    valid_main = np.load(os.path.join(ROOT, 'work/terrain/valid4.npy'))       # south-up

    out_h = (valid_full > 0) & (valid_main == 0)                              # south-up
    print('外延高程格 %d (%.2f km²)' % (out_h.sum(), out_h.sum() * 16 / 1e6))
    out_h_nu = np.flipud(np.asarray(Image.fromarray((out_h * 255).astype(np.uint8)).resize((W, W), Image.NEAREST)) > 128)
    # 高程有的地方也算"有数据"：主瓦片的色图边缘偶尔缺一条（149 m），但高程是齐的
    valid_nu = np.flipud(np.asarray(Image.fromarray(((valid_full > 0) * 255).astype(np.uint8)).resize((W, W), Image.NEAREST)) > 128)
    mask_nu = main_mask | out_h_nu | valid_nu
    print('掩码覆盖 主 %.2f%% → 全 %.2f%%  新增 %.2f km²' % (
        100 * main_mask.mean(), 100 * mask_nu.mean(), (mask_nu & ~main_mask).sum() / 1e6))
    Image.fromarray((mask_nu * 255).astype(np.uint8)).save(os.path.join(ROOT, 'export/world/world_ground_mask_full.png'))

    base = np.asarray(Image.open(os.path.join(ROOT, 'export/world/world_ground_final.png')).convert('RGB')).copy()
    add = np.asarray(Image.open(os.path.join(ROOT, 'export/world/world_ground_out.png')).convert('RGB')).astype(np.float32)
    has_add = add.max(axis=2) > 8
    # 主瓦片有数据的地方保持原色；只在"主掩码没覆盖 + 外延有色"的地方贴
    sel = has_add & (~main_mask) & mask_nu
    print('贴外延色 %d px (%.2f km²)' % (sel.sum(), sel.sum() / 1e6))

    # 接缝处理：① 先把外延色亮度对齐主色图边缘 ② 再在 40 m 内做线性羽化
    from scipy import ndimage
    dist = ndimage.distance_transform_edt(~main_mask)
    alpha = np.clip(dist / 40.0, 0.0, 1.0).astype(np.float32)
    edge_out = sel & (alpha > 0.95)
    edge_main = ndimage.binary_dilation(main_mask, np.ones((9, 9), bool)) & (~main_mask)
    if edge_out.any() and edge_main.any():
        m_out = add[edge_out].mean(0)
        m_main = base[edge_main].astype(np.float32).mean(0)
        ratio = np.clip(m_main / np.maximum(m_out, 1.0), 0.65, 1.6)
        print('  接缝亮度比 %s (外延 %s → 主图 %s)' % (ratio.round(2), m_out.round(0), m_main.round(0)))
        add = np.clip(add * ratio[None, None, :], 0, 255)
    a3 = alpha[..., None]
    mix = base.astype(np.float32) * (1 - a3) + add * a3
    base = np.where(sel[..., None], mix, base.astype(np.float32)).clip(0, 255).astype(np.uint8)
    Image.fromarray(base).save(os.path.join(ROOT, 'export/world/world_ground_final_out.png'), optimize=True)
    print('→ world_ground_mask_full.png / world_ground_final_out.png')


if __name__ == '__main__':
    main()
