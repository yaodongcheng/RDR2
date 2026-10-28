"""重建水位场：以**水岸线高程**作为水面高度，向水域内部扩散。

之前的水位场在圣丹尼斯海湾给出 3 m（实际应 ~40 m），船直接漂在草地上。
原理：水面高度 ≈ 岸边地形高度。所以取"水/陆交界"像素的高程当种子，
向水域内部迭代扩散（邻域平均），得到连通平滑的水面高度。
"""
import os, json
import numpy as np
from PIL import Image

ROOT = r'D:/BrainMaker/大镖客2解包分析'
MASK = os.path.join(ROOT, 'export/world/world_water_2048.png')
OUT = os.path.join(ROOT, 'export/world/world_water_level_2048.r16')
META = os.path.join(ROOT, 'export/world/world_meta.json')
H4 = os.path.join(ROOT, 'work/terrain/H4.npy')

X0, Y0, RES = -7684.0, -8196.0, 4.0

def main():
    meta = json.load(open(META, encoding='utf-8'))
    Z0, Z1 = meta['z']
    m = np.asarray(Image.open(MASK).convert('L')) > 127
    P = m.shape[0]
    H = np.load(H4)
    # 采样到 mask 分辨率
    step = H.shape[0] / P
    idx = (np.arange(P) * step).astype(np.int32).clip(0, H.shape[0] - 1)
    terr = H[np.ix_(idx, idx)].astype(np.float32)
    print('mask', m.shape, 'water %.1f%%' % (100 * m.mean()))

    # 水岸种子：水域像素中，8 邻域含陆地的
    land = ~m
    edge = np.zeros_like(m)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            land_s = np.roll(np.roll(land, dy, 0), dx, 1)
            edge |= m & land_s
    lvl = np.full((P, P), np.nan, np.float32)
    lvl[edge] = terr[edge]
    print('岸线种子 %d 像素' % edge.sum())

    # 向水域内部扩散
    for it in range(400):
        holes = m & np.isnan(lvl)
        if not holes.any():
            break
        acc = np.zeros_like(lvl); cnt = np.zeros_like(lvl)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                s = np.roll(np.roll(lvl, dy, 0), dx, 1)
                ok = ~np.isnan(s)
                acc += np.where(ok, s, 0); cnt += ok
        fill = holes & (cnt > 0)
        lvl[fill] = acc[fill] / cnt[fill]
        if it % 50 == 0:
            print('  it %d 剩余 %d' % (it, int((m & np.isnan(lvl)).sum())))
    lvl[m & np.isnan(lvl)] = np.nanmedian(lvl)
    # 轻微平滑，避免阶梯
    for _ in range(3):
        acc = np.zeros_like(lvl); cnt = np.zeros_like(lvl)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                s = np.roll(np.roll(lvl, dy, 0), dx, 1)
                acc += np.nan_to_num(s); cnt += (~np.isnan(s))
        sm = acc / np.maximum(cnt, 1)
        lvl = np.where(m, sm, lvl)

    # 同一连通水域用**统一水位**（old sdn.blend 就是一片平面），否则水面会起伏
    from collections import deque
    lab = np.zeros((P, P), np.int32)
    cur = 0
    ys, xs = np.nonzero(m)
    for y0, x0 in zip(ys, xs):
        if lab[y0, x0] or not m[y0, x0]:
            continue
        cur += 1
        dq = deque([(y0, x0)])
        lab[y0, x0] = cur
        pix = []
        while dq:
            y, x = dq.popleft()
            pix.append((y, x))
            for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
                yy, xx = y+dy, x+dx
                if 0 <= yy < P and 0 <= xx < P and m[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = cur
                    dq.append((yy, xx))
        if len(pix) < 50:
            continue
        py = np.array([q[0] for q in pix]); px = np.array([q[1] for q in pix])
        # 用中位：抬到 p85 会把城北整片淹掉（实测）；沼泽差异可以接受
        lvl[py, px] = np.median(lvl[py, px]) + 0.2
    print('水域连通块 %d' % cur)

    out = np.zeros((P, P), np.uint16)
    q = (lvl - Z0) / (Z1 - Z0) * 65535.0
    out[m] = np.clip(q[m], 0, 65535).astype(np.uint16)
    out.tofile(OUT)
    print('→', OUT, '水面高程 range %.1f ~ %.1f' % (float(np.nanmin(lvl[m])), float(np.nanmax(lvl[m]))))

if __name__ == '__main__':
    main()
