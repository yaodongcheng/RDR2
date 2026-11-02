# -*- coding: utf-8 -*-
"""把地形彩图的**空洞**用官方地图的颜色补上（比旧的 128 m 粗格渐变清楚得多）。

## 为什么

`world_ground_1p0.png` 里有一部分像素是纯黑（游戏把地表挖空 / 地图框外没有瓦片）。
旧补法是 `combine_ground.py`：128 m 粗网格取中位色 + 8 邻域扩散 → 出来是一大片平滑色块，
看着像"打了马赛克"。而**官方地图**（`地图下载/大陆地图_缩略.jpg`）在这些位置是画了内容的
（框内是地形画，框外是羊皮纸底），颜色/纹理都更像样。

## 做法

1. 原生瓦片重拼 → `deliverable/terrain_tiles/stitched_1pxm.png`（1 px/m，12296²）；
2. 用 `配准结果.json` 把官方地图重采样到**同一世界网格**（框外填羊皮纸色）；
3. 合成：**原生优先**；空洞处用官方图，并在边界做羽化过渡（默认 40 px）；
4. 输出 `deliverable/terrain_tiles/color_completed_1pxm.png`。

    python tools/fill_terrain_color_from_map.py
    python tools/fill_terrain_color_from_map.py --feather 60 --out <路径>
"""
import argparse
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None

ROOT = r'D:/BrainMaker/大镖客2解包分析'
NATIVE = os.path.join(ROOT, 'deliverable/terrain_tiles/stitched_1pxm.png')
MAPDIR = os.path.join(ROOT, '地图下载')
THUMB = os.path.join(MAPDIR, '大陆地图_缩略.jpg')
FIT = os.path.join(MAPDIR, '配准结果.json')
OUT = os.path.join(ROOT, 'deliverable/terrain_tiles/color_completed_1pxm.png')

X0w, Y0w, WORLD, SCALE, YM1 = -7684.0, -8196.0, 12296.0, 14.5, 4100.0
MAP_PX = (146, 388, 4804, 3851)          # 缩略图上的地图内容框
MAP_PX_FULL = (5000, 3916)
PARCHMENT = np.array([222, 194, 157], np.float32)   # 官方地图纸边色


def w2map_px(x, y, fit, k):
    """世界坐标 → 缩略图像素（配准结果的反变换）"""
    a, c, tx, ty = fit['a'], fit['c'], fit['tx'], fit['ty']
    u = (x - X0w) / SCALE
    v = (YM1 - y) / SCALE
    px = a * u - c * v
    py = c * u + a * v
    return (px + tx) / k, (py + ty) / k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--native', default=NATIVE)
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--feather', type=int, default=40, help='空洞边界羽化像素（1 px = 1 m）')
    ap.add_argument('--method', default='terrain', choices=['coarse', 'weights', 'terrain', 'nearest', 'map'],
                    help='terrain = 按高程×坡度取样真实像素（默认，像真地形）；nearest = 周围原生色扩散（雾状）；map = 用官方地图颜色')
    ap.add_argument('--blur', type=float, default=48.0, help='nearest 模式下的扩散柔化半径（米）')
    a = ap.parse_args()

    nat = np.asarray(Image.open(a.native).convert('RGB'))
    H, W = nat.shape[:2]
    print('[fill] 原生拼图 %dx%d，近黑 %.1f%%' % (W, H, 100 * (nat.max(2) < 10).mean()))

    fit = json.load(open(FIT, encoding='utf-8'))
    k = 1400.0 / MAP_PX_FULL[0]
    thumb = Image.open(THUMB).convert('RGB')

    # ---- 官方地图 → 世界网格（每行/列算一次坐标，再双线性采样）
    xs = X0w + np.arange(W) + 0.5
    ys = YM1 - np.arange(H) - 0.5
    u = (xs - X0w) / SCALE
    vv = (YM1 - ys) / SCALE
    a_, c_, tx, ty = fit['a'], fit['c'], fit['tx'], fit['ty']
    # 配准的逆变换（见 export_map_area_heightmap.m2w）：
    #   u = (a*px + c*py)/det , v = (-c*px + a*py)/det , det = a²+c²
    #   ⇒ px = a*u - c*v , py = c*u + a*v   （det 已约掉，别再除）
    px_x = a_ * u
    py_x = c_ * u
    px_y = -c_ * vv
    py_y = a_ * vv
    mpx = (px_x[None, :] + px_y[:, None] + tx) / k
    mpy = (py_x[None, :] + py_y[:, None] + ty) / k

    print('[fill] 官方图像素范围 px %.1f..%.1f  py %.1f..%.1f'
          % (mpx.min(), mpx.max(), mpy.min(), mpy.max()))
    from scipy.ndimage import map_coordinates
    sig = np.stack([mpy, mpx])
    off = np.zeros((H, W, 3), np.float32)
    for ch in range(3):
        off[..., ch] = map_coordinates(np.asarray(thumb, np.float32)[..., ch], sig,
                                       order=1, mode='constant', cval=0.0)

    # 框外（= 画布外或地图纸边）一律用羊皮纸色
    outside = ((mpx < 0) | (mpx > thumb.size[0] - 1) |
               (mpy < 0) | (mpy > thumb.size[1] - 1))
    off[outside] = PARCHMENT

    # ---- 空洞掩码（先算，后面的色差校正和羽化都要用）
    # 🔴 羽化只能作用在**空洞边界**上：把原始 mask 直接高斯模糊会把城里那些小碎洞
    #    也抹开，整张图被官方图糊上一层（2026-11-02 实测：地图内部整体发白）。
    #    做法：先只保留「大规模空洞」（连通域 ≥ 2 万像素）享受羽化，小碎洞直接就地替换。
    hole = nat.max(2) < 10
    print('[fill] 空洞 %.1f%%' % (100 * hole.mean()))
    lab, n = ndimage.label(hole)
    if n:
        sizes = ndimage.sum(hole, lab, range(1, n + 1))
        big = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= 20000])
    else:
        big = hole
    print('[fill] 大空洞 %.1f%%（连通域 %d 个，≥2 万像素的才羽化）' % (100 * big.mean(), n))

    # ---- 色差校正：官方图是"美术风"，和原生地形色不一样；按**大空洞边界带**统计均值差，
    #      按洞内距离衰减地补回去，接缝就不突兀。
    if a.method == 'map' and big.any():
        ring = ndimage.binary_dilation(big, iterations=12) & ~big
        if ring.any():
            nat_m = nat[ring].astype(np.float32).mean(0)
            off_m = off[ring].mean(0)
            d = nat_m - off_m
            print('[fill] 边界色差 原生 %s  官方 %s  → 补偿 %s'
                  % ([int(v) for v in nat_m], [int(v) for v in off_m], [int(v) for v in d]))
            dist = ndimage.distance_transform_edt(big)
            far = max(64.0, float(np.percentile(dist[big], 95)))
            ramp = np.clip(1.0 - dist / far, 0.25, 1.0)          # 深处也保留 25%
            off = off + d[None, None, :] * ramp[..., None]

    # ---- method=nearest：不用官方图，直接把原生色「扩散」进空洞（边界无缝、无方格）
    if a.method == 'nearest':
        idx = ndimage.distance_transform_edt(hole, return_distances=False, return_indices=True)
        ext = nat[idx[0], idx[1]].astype(np.float32)
        sig = max(8.0, a.blur)
        ext = ndimage.gaussian_filter(ext, (sig, sig, 0))
        off = ext

    # ---- method=coarse：**照抄 build_terrain_heightmap 的补洞算法**（用户口径）
    #   粗层（max/256 格 → 1 m 图上约 48 m）做 nan 感知均值 → 8 邻域迭代扩散填满
    #   → 双线性上采样回 1 m，只填空洞格。和高度图完全是同一套参数、同一套行为。
    if a.method == 'coarse':
        H, W = hole.shape
        sc = max(1, int(round(max(W, H) / 256.0)))
        Wc, Hc = (W + sc - 1) // sc, (H + sc - 1) // sc
        natf = nat.astype(np.float64)
        valf = (~hole).astype(np.float64)
        # 块均值：先按块求和再除（等同 BOX 重采样，但不用 PIL 的 F 模式）
        def blocksum(A):
            pad = np.zeros((Hc * sc, Wc * sc) + A.shape[2:], np.float64)
            pad[:H, :W] = A
            return pad.reshape(Hc, sc, Wc, sc, *A.shape[2:]).sum(axis=(1, 3))
        s_sum = blocksum(natf * valf[..., None])
        s_cnt = blocksum(valf)
        coarse = np.where(s_cnt[..., None] > 0, s_sum / np.maximum(s_cnt, 1e-9)[..., None],
                          np.nan)
        print('[fill] coarse: %dx%d 网格（%d m）' % (Wc, Hc, sc))
        for it in range(600):
            nanm = np.isnan(coarse[..., 0])
            if not nanm.any():
                break
            v = np.nan_to_num(coarse)
            k = (~nanm).astype(np.float64)
            acc = np.zeros_like(v); wt = np.zeros_like(k)
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                acc += np.roll(np.roll(v * k[..., None], dr, 0), dc, 1)
                wt += np.roll(np.roll(k, dr, 0), dc, 1)
            fillm = nanm & (wt > 0)
            coarse[fillm] = (acc / np.maximum(wt, 1e-9)[..., None])[fillm]
        print('[fill] coarse: 扩散 %d 轮后仍空 %d 格' % (it + 1, int(np.isnan(coarse[..., 0]).sum())))
        coarse = np.nan_to_num(coarse)
        # 双线性上采样到 1 m 图
        from scipy.ndimage import zoom as _z
        up = _z(coarse, (H / float(Hc), W / float(Wc), 1), order=1)[:H, :W]
        off = np.clip(up, 0, 255)

    # ---- method=weights：**用骑砍2那套 7 层材质权重合成颜色**（与游戏里看到的同源）
    # 游戏端根本不吃彩色大图：它吃 heightmap + 7 张 layer mask（`deliverable/terrain_weights/`）。
    # 所以空洞处最"对"的补法 = 按同一份权重把 7 层调色板混出来，而不是编一个填充。
    if a.method == 'weights':
        WDIR = os.path.join(ROOT, 'deliverable/terrain_weights')
        meta = json.load(open(os.path.join(WDIR, 'weights_meta.json'), encoding='utf-8'))
        area = meta['area']
        rw, rh = meta['size']
        H, W = hole.shape
        # 权重网格（4 m，行0=北）→ 本图坐标（1 px = 1 m，行0=北；全图原点 -7684/-8196）
        mix = np.zeros((H, W, 3), np.float32)
        tot = np.zeros((H, W), np.float32)
        for L in meta['layers']:
            key = L['key']
            fp = os.path.join(WDIR, 'w_%s.png' % key)
            if not os.path.exists(fp):
                continue
            wgt = np.asarray(Image.open(fp).convert('L'), np.float32) / 255.0
            # 权重网格 → 世界 → 本图行列
            xs = area['x0'] + (np.arange(rw) + 0.5) * area['res_m']
            ys = area['y1'] - (np.arange(rh) + 0.5) * area['res_m']
            ci = np.clip(((xs - X0w)).astype(np.int32), 0, W - 1)
            ri = np.clip(((YM1 - ys)).astype(np.int32), 0, H - 1)
            # 粗网格铺到 1 m 图（最近邻即可，权重本身是 4 m 平滑场）
            rep = np.repeat(np.repeat(wgt, 4, axis=0), 4, axis=1)[:rh * 4, :rw * 4]
            canvas = np.zeros((H, W), np.float32)
            r0, c0 = int(ri[0]), int(ci[0])
            hh = min(rep.shape[0], H - r0); ww = min(rep.shape[1], W - c0)
            if hh > 0 and ww > 0:
                canvas[r0:r0 + hh, c0:c0 + ww] = rep[:hh, :ww]
            col = np.array(L['rgb'], np.float32)
            mix += canvas[..., None] * col[None, None, :]
            tot += canvas
        ext = np.where(tot[..., None] > 1e-6, mix / np.maximum(tot, 1e-6)[..., None],
                       nat.astype(np.float32))
        print('[fill] 权重合成色就绪（%d 层）' % len(meta['layers']))
        off = np.clip(ext, 0, 255)

    # ---- method=terrain：**按地形补**（推荐）
    # 空洞处虽然没有彩图，但**高程是有的**（H4 全填满）。做法分两步：
    #   ① 底子：按「高程 × 坡度」分类（雪/岩/草/土），每类的颜色取**真实像素的均值**；
    #   ② 颗粒：每 64×64 一块，从同类真实区域里搬一块高频细节（去低频后只有纹理），
    #      叠到底子上 —— 有结构、有颗粒，不是噪点也不是雾。
    if a.method == 'terrain':
        from scipy.ndimage import zoom as _zoom
        H4 = np.load(os.path.join(ROOT, 'raw/terrain/H4.npy')).astype(np.float32)
        H, W = hole.shape
        # 🔴 H4 行 0 = 南，彩图行 0 = 北 → 必须翻转（2026-11-02 踩：不翻转会把雪判到沙漠上）
        zg = np.flipud(_zoom(H4, H / float(H4.shape[0]), order=1)[:H, :W])
        gy, gx = np.gradient(zg, 1.0)
        sl = np.hypot(gx, gy)
        del gy, gx
        zmin, zmax = float(zg.min()), float(zg.max())

        # 四个地形类（阈值按**米**和**坡度 m/m**，别拿归一化值比）
        rng_z = max(1e-6, zmax - zmin)
        low = zg < zmin + 0.18 * rng_z          # 低地（草/土）
        high = zg > zmin + 0.55 * rng_z         # 高地（岩/雪）
        steep = sl > 0.55                       # 陡坡
        snow = (zg > zmin + 0.72 * rng_z) & (sl < 0.75)
        cls = np.zeros_like(zg, np.uint8)       # 0 草/低地
        cls[~low & ~steep] = 1                  # 1 中高地带（土/灌木）
        cls[steep | (high & ~snow)] = 2         # 2 岩
        cls[snow] = 3                           # 3 雪

        flat_c = cls.ravel()
        natf = nat.reshape(-1, 3).astype(np.float32)
        validf = ~hole.ravel()
        base = np.zeros((4, 3), np.float32)
        for c in range(4):
            m = validf & (flat_c == c)
            base[c] = natf[m].mean(0) if m.sum() > 500 else natf[validf].mean(0)
        print('[fill] 地形类底色 低地%s 中高%s 岩%s 雪%s'
              % tuple(str([int(v) for v in base[i]]) for i in range(4)))

        # 低频底子
        ext = np.empty_like(nat)
        for c in range(4):
            ext[cls == c] = base[c]

        # 高频颗粒：每 64×64 从同类真实区域搬一块（只取高频 = 原图 - 局部均值）
        from scipy.ndimage import uniform_filter
        hi = nat.astype(np.float32) - uniform_filter(nat.astype(np.float32), (7, 7, 1))
        rng = np.random.default_rng(11)
        PS = 64
        src_by_cls = {c: np.flatnonzero(validf & (flat_c == c)) for c in range(4)}
        for by in range(0, H, PS):
            for bx in range(0, W, PS):
                blk_hole = hole[by:by + PS, bx:bx + PS]
                if blk_hole.mean() < 0.35:
                    continue
                c = int(np.bincount(cls[by:by + PS, bx:bx + PS].ravel(), minlength=4).argmax())
                cand = src_by_cls.get(c)
                if cand is None or len(cand) < PS * PS:
                    cand = src_by_cls.get(0)
                if cand is None or len(cand) < PS * PS:
                    continue
                bh, bw = blk_hole.shape
                gy0 = int(rng.integers(0, max(1, H - bh))); gx0 = int(rng.integers(0, max(1, W - bw)))
                patch = hi[gy0:gy0 + bh, gx0:gx0 + bw]
                m3 = blk_hole[..., None]
                ext[by:by + PS, bx:bx + PS] = np.where(
                    m3, ext[by:by + PS, bx:bx + PS] + patch, ext[by:by + PS, bx:bx + PS])
        off = np.clip(ext, 0, 255)
        del zg, sl, cls, hi, ext

    wgt = hole.astype(np.float32)
    if a.feather > 0 and big.any():
        edge_soft = ndimage.gaussian_filter(big.astype(np.float32), a.feather / 2.0)
        # 🔴 羽化带必须落在**洞外**才起作用：以前写成 np.where(big, …) 把外圈全丢了，
        #    接缝是硬直角（2026-11-02 实测）。
        #    nearest 模式下 off 是整幅的"最近原生色扩散"，所以洞外半格混合也不会串色。
        wgt = np.clip(np.maximum(hole.astype(np.float32), edge_soft), 0, 1)
        if a.method == 'map':
            wgt = np.where(hole, wgt, 0.0)     # map 模式只在洞内用（洞外是官方图，会串色）
    out = nat.astype(np.float32) * (1 - wgt[..., None]) + off * wgt[..., None]
    out = np.clip(out, 0, 255).astype(np.uint8)

    Image.fromarray(out).save(a.out, 'PNG', compress_level=6)
    print('[fill] SAVED %s %.2f GB' % (a.out, os.path.getsize(a.out) / 1e9))

    bad2 = (out.max(2) < 10)
    print('[fill] 补后近黑 %.2f%%' % (100 * bad2.mean()))


if __name__ == '__main__':
    main()
