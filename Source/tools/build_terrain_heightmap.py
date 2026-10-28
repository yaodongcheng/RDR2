"""把 RDR2 的**真地形瓦片**拼成世界高程图。

原理（本轮验证）：
  1. 地形不存在 heightmap 里，而是 **480 个瓦片包** `levels/rdr3/terrain/<area>/<letter>_<row>_.rpf`，
     每个包含 64 个 patch：`<letter>_<row>__hd_0_<i>_<j>.ydr`（本地 64m×64m、17×17 顶点、stride 56）。
  2. 每个 patch 的**世界位置**由 `<letter>_<row>__strm_0.ymap` 里的一条实体给出：
        archetype == joaat("<letter>_<row>__hd_0_<i>_<j>")
        position  == (x0, y0, z0)   ← x0/y0 是 patch 中心，**z0 是该 patch 的绝对基准高程**
        实测：i,j 每 +1 → x/y 各 +64 m
  3. 世界高程 = z0 + ydr 本地顶点 z（本地 bbox 只有 ±5 m 的细节起伏）。

用法：
  uv run python tools/build_terrain_heightmap.py [--limit N] [--res 4]
产物：
  export/levels/world/terrain_h.json   元数据
  export/levels/world/terrain_h.png    高程图（16bit：R=高字节 G=低字节）
  work/verify/terrain_preview.png      灰度高程预览（自检用）
"""
import os
import sys
import glob
import json
import struct
import builtins

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image

ROOT = r'D:/BrainMaker/大镖客2解包分析'
META = os.path.join(ROOT, 'export/levels/map_metadata')
YDR = os.path.join(ROOT, 'work/terrain/ydr')
WORLD = os.path.join(ROOT, 'export/levels/world')
PATCH = 64.0          # patch 尺寸（米）
PVERTS = 17           # 每边顶点数（→ 4 m 间距）


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xffffffff
        h = (h + (h << 10)) & 0xffffffff
        h ^= (h >> 6)
    h = (h + (h << 3)) & 0xffffffff
    h ^= (h >> 11)
    h = (h + (h << 15)) & 0xffffffff
    return h


def silent():
    p = builtins.print
    builtins.print = lambda *a, **k: None
    return lambda: setattr(builtins, 'print', p)


# ---------------------------------------------------------------- 1) patch 摆放索引
def build_index():
    import builtins as _b
    _p = _b.print
    _b.print = lambda *a, **k: None
    try:
        import ymap_entities
        idx = {}
        files = sorted(glob.glob(os.path.join(META, '**', '*_strm_0.ymap'), recursive=True))
        for f in files:
            try:
                sig, size, ents = ymap_entities.extract(f)
            except Exception:
                continue
            for e in ents:
                idx[e[0]] = (e[1], e[2], e[3])
    finally:
        _b.print = _p
    print(f'扫 {len(files)} 个 *_strm_0.ymap → {len(idx)} 条 patch 摆放')
    return idx


# ---------------------------------------------------------------- 2) 解析 ydr
def parse_patch(path):
    """返回 (positions: [(x,y,z)...]) —— 本地坐标（patch 中心为原点）。"""
    import rdr2_ydr as Y
    res = Y.Res(open(path, 'rb').read())
    info, meshes = Y.extract_at(res, 0, 'high')
    out = []
    for m in meshes:
        out.extend(m.get('positions') or [])
    return out


# ---------------------------------------------------------------- 3) 主流程
def main():
    args = sys.argv[1:]
    res_m = 4.0
    limit = None
    if '--res' in args:
        res_m = float(args[args.index('--res') + 1])
    if '--limit' in args:
        limit = int(args[args.index('--limit') + 1])

    idx = build_index()
    print(f'patch 摆放索引：{len(idx)} 条')

    files = sorted(glob.glob(os.path.join(YDR, '**', '*.ydr'), recursive=True))
    if limit:
        files = files[:limit]
    print(f'待解析 ydr：{len(files)}')

    # 世界范围（patch 中心 ± PATCH/2 的并集）
    ps = np.array(list(idx.values()), dtype='float64')
    X0 = ps[:, 0].min() - PATCH / 2 - res_m
    X1 = ps[:, 0].max() + PATCH / 2 + res_m
    Y0 = ps[:, 1].min() - PATCH / 2 - res_m
    Y1 = ps[:, 1].max() + PATCH / 2 + res_m
    W = int(round((X1 - X0) / res_m)) + 1
    H = int(round((Y1 - Y0) / res_m)) + 1
    print(f'世界范围 x[{X0:.0f},{X1:.0f}] y[{Y0:.0f},{Y1:.0f}]  '
          f'网格 {W}×{H} @ {res_m} m  ({W*H/1e6:.1f}M 格)')

    cache = os.path.join(ROOT, 'work/terrain/H4.npy')
    if os.path.exists(cache) and '--force' not in args:
        Hm = np.load(cache)
        print(f'复用缓存 {cache}  {Hm.shape}')
        emit(Hm, X0, Y0, X1, Y1, res_m, args)
        return

    acc = np.zeros((H, W), dtype='float64')
    cnt = np.zeros((H, W), dtype='int32')
    miss = 0
    bad = 0
    for i, f in enumerate(files):
        stem = os.path.basename(f)[:-4]
        p = idx.get(joaat(stem))
        if p is None:
            miss += 1
            continue
        try:
            pts = parse_patch(f)
        except Exception:
            bad += 1
            continue
        if not pts:
            bad += 1
            continue
        a = np.asarray(pts, dtype='float64').reshape(-1, 3)
        wx = a[:, 0] + p[0]
        wy = a[:, 1] + p[1]
        wz = a[:, 2] + p[2]
        c = np.round((wx - X0) / res_m).astype('int64')
        r = np.round((wy - Y0) / res_m).astype('int64')
        ok = (c >= 0) & (c < W) & (r >= 0) & (r < H)
        c, r, wz = c[ok], r[ok], wz[ok]
        np.add.at(acc, (r, c), wz)
        np.add.at(cnt, (r, c), 1)
        if (i + 1) % 2000 == 0:
            print(f'  {i+1}/{len(files)}  miss={miss} bad={bad} 已填格 {int((cnt>0).sum())}')
    print(f'解析完：miss={miss}(无摆放) bad={bad}(解析失败) 覆盖格 {int((cnt>0).sum())} / {W*H}')

    Hm = np.full((H, W), np.nan, dtype='float32')
    m = cnt > 0
    Hm[m] = (acc[m] / cnt[m]).astype('float32')
    # 空洞填充：先在粗层扩散填好，再上采样补齐（比在原分辨率上扩散快几百倍）
    npix = int((~m).sum())
    if npix:
        sc = max(1, int(round(max(W, H) / 256)))
        Wc, Hc = (W + sc - 1)//sc, (H + sc - 1)//sc
        v4 = Hm.reshape(1, H, W)
        # nan 感知的块均值
        img = Image.fromarray(np.nan_to_num(v4, nan=0.0)[0], mode='F')
        wimg = Image.fromarray((~np.isnan(v4[0])).astype('float32'), mode='F')
        sm = np.asarray(img.resize((Wc, Hc), Image.BOX), dtype='float64')
        sw = np.asarray(wimg.resize((Wc, Hc), Image.BOX), dtype='float64')
        coarse = np.where(sw > 0, sm / np.maximum(sw, 1e-9), np.nan)
        for _ in range(600):
            if not np.isnan(coarse).any():
                break
            v = np.nan_to_num(coarse, nan=0.0)
            k = (~np.isnan(coarse)).astype('float64')
            s2 = np.zeros_like(v); w2 = np.zeros_like(v)
            for dr, dc in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                s2 += np.roll(np.roll(v*k, dr, 0), dc, 1)
                w2 += np.roll(np.roll(k,   dr, 0), dc, 1)
            f2 = np.isnan(coarse) & (w2 > 0)
            coarse[f2] = (s2/np.maximum(w2, 1e-9))[f2]
        coarse = np.nan_to_num(coarse, nan=0.0)
        up = np.asarray(Image.fromarray(coarse.astype('float32'), mode='F').resize((W, H), Image.BILINEAR),
                        dtype='float32')
        Hm = np.where(np.isnan(Hm), up, Hm)
        print(f'  空洞 {npix} 格 ({npix/(W*H)*100:.3f}%)（掩码写进 PNG 的 B 通道，前端剔除这些三角）')
    Hm = np.nan_to_num(Hm, nan=0.0)
    print('高程统计：min %.1f  max %.1f  mean %.1f  std %.1f' %
          (Hm.min(), Hm.max(), Hm.mean(), Hm.std()))
    np.save(cache, Hm.astype('float32'))
    np.save(cache.replace('H4.npy', 'valid4.npy'), m.astype('uint8'))
    emit(Hm, X0, Y0, X1, Y1, res_m, args)


def emit(Hm, X0, Y0, X1, Y1, res_m, args):
    H, W = Hm.shape
    vcache = os.path.join(ROOT, 'work/terrain/valid4.npy')
    V = np.load(vcache) if os.path.exists(vcache) else np.ones_like(Hm, dtype='uint8')

    # ---- 下采样到显示分辨率（2048 宽）----
    DW = min(int(args[args.index('--dw')+1]) if '--dw' in args else 1024, W)
    DH = int(round(H * DW / W))
    im = Image.fromarray(Hm, mode='F').resize((DW, DH), Image.BOX)
    D = np.asarray(im, dtype='float32')
    vm = np.asarray(Image.fromarray((V * 255).astype('uint8'), mode='L').resize((DW, DH), Image.BOX),
                    dtype='uint8')

    os.makedirs(WORLD, exist_ok=True)
    lo, hi = float(D.min()), float(D.max())
    q = np.clip((D - lo) / max(1e-6, hi - lo) * 65535.0, 0, 65535).astype('<u2')
    rgba = np.zeros((DH, DW, 4), dtype='uint8')
    rgba[..., 0] = (q >> 8) & 0xFF          # R = 高字节
    rgba[..., 1] = q & 0xFF                 # G = 低字节
    rgba[..., 2] = np.where(vm > 128, 255, 0)   # B = 有效性（255=有地形，0=空洞，前端剔除）
    rgba[..., 3] = 255
    Image.fromarray(rgba, 'RGBA').save(os.path.join(WORLD, 'terrain_h.png'), optimize=True)
    json.dump({'W': DW, 'H': DH, 'x0': X0, 'y0': Y0, 'x1': X1, 'y1': Y1,
               'zmin': lo, 'zmax': hi, 'src_res': res_m},
              open(os.path.join(WORLD, 'terrain_h.json'), 'w'))
    print(f'-> terrain_h.png {os.path.getsize(os.path.join(WORLD,"terrain_h.png"))/1048576:.2f} MB '
          f'({DW}×{DH})  高程 {lo:.0f}~{hi:.0f} m')

    g = ((D - lo) / max(1e-6, hi - lo) * 255).astype('uint8')
    Image.fromarray(g[::-1]).save(os.path.join(ROOT, 'work/verify/terrain_preview.png'))  # 预览翻转只为北朝上
    print('-> work/verify/terrain_preview.png')


if __name__ == '__main__':
    main()
