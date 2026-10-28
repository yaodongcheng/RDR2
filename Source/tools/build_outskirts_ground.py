"""把"地图外延地形"（terrain/outskirts 的 out_* 包）补进世界高程与地面色图。

背景：主地图的地形瓦片只有 `<letter>_<row>_` 这 480 个，它们只覆盖"地图框内"；
      框外的山体/海岸在 `levels/rdr3/terrain/outskirts/out_*.rpf` 里（每包 4096 m 见方、
      4×4 个 1024 m patch、色图 1024² 即 4 m/px）。之前只收了 480 个主瓦片，
      所以 NW / SE 两块（各 4 km 见方）是空的 —— 这就是"地形虚空"的数据根因之一。

产物：
  work/terrain/H4_full.npy       补完高程（4 m 网格，3074²）
  work/terrain/valid_full.npy    补完有效掩码
  export/world/world_ground_out.png   外延色图（12296²，1 m/px，无数据处黑）
  work/verify/out_cover.png      补了哪些地方

用法：
  uv run python tools/build_outskirts_ground.py
"""
import os
import sys
import glob
import json
import argparse

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = r'D:/BrainMaker/大镖客2解包分析'
INNER = os.path.join(ROOT, 'work/outskirts/inner')
X0, Y0, WORLD, RES = -7684.0, -8196.0, 12296.0, 4.0
GRID = 3075


def names_map():
    p = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
    d = {}
    for line in open(p, encoding='latin1', errors='ignore'):
        n = line.strip()
        if not n:
            continue
        h = 0
        for ch in n.lower().encode():
            h = (h + ch) & 0xffffffff
            h = (h + (h << 10)) & 0xffffffff
            h ^= h >> 6
        h = (h + (h << 3)) & 0xffffffff
        h ^= h >> 11
        h = (h + (h << 15)) & 0xffffffff
        d[h] = n
    return d


def pack_boxes():
    p = os.path.join(ROOT, 'work/outskirts/bbox.json')
    return json.load(open(p)) if os.path.exists(p) else {}


def patch_placements(pack, nm):
    import ymap_entities
    idx = {}
    for y in glob.glob(os.path.join(INNER, pack, '*.ymap')):
        try:
            _s, _z, es = ymap_entities.extract(y)
        except Exception:
            continue
        for e in es:
            n = nm.get(e[0], '').lower()
            if n.startswith(pack) and '_hd_' in n and not n.endswith(('_lod', '_slod')):
                idx[n] = (e[1], e[2], e[3])
    return idx


def heights_of_pack(pack, nm):
    """返回 (pts[N,3] 世界坐标)"""
    import rdr2_ydr as Y
    idx = patch_placements(pack, nm)
    out = []
    for f in glob.glob(os.path.join(INNER, pack, '*.ydr')):
        b = os.path.basename(f).lower()
        if '_hd_' not in b or b.endswith(('_lod.ydr', '_slod.ydr')):
            continue
        stem = b[:-4]
        p = idx.get(stem)
        if p is None:
            continue
        try:
            res = Y.Res(open(f, 'rb').read())
            _i, meshes = Y.extract_at(res, 0, 'high')
        except Exception as e:
            print('   parse fail', stem, e)
            continue
        for m in meshes:
            a = np.asarray(m['positions'], dtype='float64').reshape(-1, 3)
            if not len(a):
                continue
            a[:, 0] += p[0]; a[:, 1] += p[1]; a[:, 2] += p[2]
            out.append(a)
    return np.concatenate(out, 0) if out else None


def color_of_pack(pack):
    """解出 outskirts 的 diffuse 色图（1024²，覆盖整包 4096 m）"""
    from rdr2_ytd import Ytd
    from ytd_to_png import decode_one
    p = os.path.join(INNER, pack, pack + '.ytd')
    if not os.path.exists(p):
        return None
    try:
        y = Ytd(open(p, 'rb').read())
    except Exception:
        return None
    for t in y.textures():
        nm = (t['name'] or '').lower()
        if nm.startswith('outskirts_d'):
            blob = y.gfx[t['gfx_off']:t['gfx_off'] + max(4096, t['w'] * t['h'] * 4)]
            im, _fmt = decode_one(blob, t['w'], t['h'], t['fmt'])
            if im is not None:
                return im.convert('RGB')
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()

    nm = names_map()
    boxes = pack_boxes()
    main_mask = np.asarray(Image.open(os.path.join(ROOT, 'export/world/world_ground_mask.png')).convert('L')) > 10

    H = np.load(os.path.join(ROOT, 'work/terrain/H4.npy'))
    V = np.load(os.path.join(ROOT, 'work/terrain/valid4.npy'))
    global GRID
    GRID = H.shape[0]

    patch_cov = np.zeros((GRID, GRID), bool)
    acc = np.zeros((GRID, GRID), np.float64)
    cnt = np.zeros((GRID, GRID), np.int32)
    color = np.zeros((GRID, GRID, 3), np.uint8)      # 4 m/px 临时画布（和 H4 同网格）
    cmask = np.zeros((GRID, GRID), bool)

    todo = []
    for pack, bb in sorted(boxes.items()):
        x0, y0, x1, y1 = bb[0], bb[1], bb[2], bb[3]
        if x1 < X0 or x0 > X0 + WORLD or y1 < Y0 or y0 > Y0 + WORLD:
            continue
        # 只补"主掩码没数据"的区域才有意义；先看这包里有多少格落在空洞内
        todo.append((pack, bb))
    print('与地图相交的外延包：', [t[0] for t in todo])

    for pack, bb in todo:
        pts = heights_of_pack(pack, nm)
        if pts is None:
            print('  跳过（无地形）', pack)
            continue
        c = np.round((pts[:, 0] - X0) / RES).astype(np.int64)
        r = np.round((pts[:, 1] - Y0) / RES).astype(np.int64)
        ok = (c >= 0) & (c < GRID) & (r >= 0) & (r < GRID)
        np.add.at(acc, (r[ok], c[ok]), pts[ok, 2])
        np.add.at(cnt, (r[ok], c[ok]), 1)
        print('  %s  verts=%d  world bbox x[%.0f,%.0f] y[%.0f,%.0f]' % (
            pack, len(pts), pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max()))
        # 记录 patch 覆盖区域（placement 中心 ±512 m）
        pl = patch_placements(pack, nm)
        for stem, (cx, cy, cz) in pl.items():
            px0 = max(0, int((cx - 512 - X0) / RES)); px1 = min(GRID, int((cx + 512 - X0) / RES) + 1)
            py0 = max(0, int((cy - 512 - Y0) / RES)); py1 = min(GRID, int((cy + 512 - Y0) / RES) + 1)
            if px1 > px0 and py1 > py0:
                patch_cov[py0:py1, px0:px1] = True
        im = color_of_pack(pack)
        if im is not None:
            # 色图覆盖整包 bbox（4096 m）
            px0 = int(round((bb[0] - X0) / RES)); px1 = int(round((bb[2] - X0) / RES))
            py1 = int(round((Y0 + WORLD - bb[1]) / RES)); py0 = int(round((Y0 + WORLD - bb[3]) / RES))
            pw, ph = max(1, px1 - px0), max(1, py1 - py0)
            im2 = im.resize((pw, ph), Image.BILINEAR)
            arr = np.asarray(im2)
            # 只写"主掩码没有"的区域（避免和真地形瓦片打架）
            ys, xs = np.mgrid[0:ph, 0:pw]
            gx = np.clip(px0 + xs, 0, GRID - 1); gy = np.clip(py0 + ys, 0, GRID - 1)
            sub_main = main_mask[gy, gx]
            sel = ~sub_main
            color[gy[sel], gx[sel]] = arr[sel]
            cmask[gy[sel], gx[sel]] = True
        else:
            print('    !! 无色图', pack)

    z = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan)
    # 剔除明显异常的高度（yml 摆放错/解析坏的 patch）
    bad = np.abs(z) > 2000
    if bad.any():
        print('  丢弃异常高度格 %d' % int(bad.sum()))
        z[bad] = np.nan
        cnt[bad] = 0
    got = cnt > 0
    print('外延原始覆盖格 %d (%.2f km²)' % (int(got.sum()), got.sum() * RES * RES / 1e6))

    region = patch_cov
    print('外延 patch 覆盖面积 %.2f km²' % (region.sum() * RES * RES / 1e6))

    # 最近邻填补（patch 顶点间距 ~13 m，4 m 栅格上补洞就是插值，不是凭空造地形）
    from scipy import ndimage
    ind = ndimage.distance_transform_edt(~got, return_distances=False, return_indices=True)
    zfill = z[tuple(ind)]
    # 轻度平滑，去掉最近邻台阶（3 格盒式，只作用在被补的格子上）
    zsm = ndimage.uniform_filter(zfill, 3)
    zfill = np.where(got, zfill, zsm)

    # 合并：只在"主数据缺失 且 外延区域"的地方写
    upd = (V == 0) & region
    Hf = H.copy(); Vf = V.copy()
    Hf[upd] = zfill[upd].astype(np.float32)
    Vf[upd] = 1
    print('高程补洞 %d 格 (%.2f km²)  bbox x[%.0f,%.0f] y[%.0f,%.0f]' % (
        int(upd.sum()), upd.sum() * RES * RES / 1e6,
        X0 + np.nonzero(upd)[1].min() * RES, X0 + np.nonzero(upd)[1].max() * RES,
        Y0 + np.nonzero(upd)[0].min() * RES, Y0 + np.nonzero(upd)[0].max() * RES))

    # 色图：4 m/px 栅格 → 12× 上采样到 1 m/px 后再贴
    out_png = os.path.join(ROOT, 'export/world/world_ground_out.png')
    PX = int(WORLD)
    cm = np.asarray(Image.fromarray((cmask * 255).astype(np.uint8)).resize((PX, PX), Image.NEAREST)) > 128
    cm &= ~main_mask
    rgb = np.asarray(Image.fromarray(color).resize((PX, PX), Image.BILINEAR)).copy()
    rgb[~cm] = 0
    Image.fromarray(rgb).save(out_png)
    print('→ %s  覆盖 %.2f%%' % (out_png, 100 * cm.mean()))

    if not a.dry:
        np.save(os.path.join(ROOT, 'work/terrain/H4_full.npy'), Hf)
        np.save(os.path.join(ROOT, 'work/terrain/valid_full.npy'), Vf)
        print('→ H4_full.npy / valid_full.npy')

    # 预览：哪些格子被补
    prev = np.zeros((GRID // 4 * 2, GRID // 4 * 2, 3), np.uint8)
    sm = np.asarray(Image.fromarray((cmask * 255).astype(np.uint8)).resize(prev.shape[:2], Image.BILINEAR)) > 40
    smu = np.asarray(Image.fromarray((upd * 255).astype(np.uint8)).resize(prev.shape[:2], Image.BILINEAR)) > 40
    prev[..., 0] = np.where(smu, 40, 20); prev[..., 1] = np.where(sm, 160, 20); prev[..., 2] = np.where(smu, 60, 20)
    Image.fromarray(np.flipud(prev)).save(os.path.join(ROOT, 'work/verify/out_cover.png'))
    print('→ work/verify/out_cover.png')


if __name__ == '__main__':
    main()
