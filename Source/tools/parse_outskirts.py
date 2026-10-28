"""解析 outskirts 包（out_*）的地形，产出高程/范围，并可预览。

  uv run python tools/parse_outskirts.py --pack out_b_05 --png work/verify/out_b_05.png
"""
import os
import sys
import glob
import json
import argparse

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = r'D:/BrainMaker/大镖客2解包分析'
INNER = os.path.join(ROOT, 'work/outskirts/inner')


def names_map():
    p = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
    d = {}
    for line in open(p, encoding='latin1', errors='ignore'):
        n = line.strip()
        if not n:
            continue
        h = 0
        for c in n.lower().encode():
            h = (h + c) & 0xffffffff
            h = (h + (h << 10)) & 0xffffffff
            h ^= h >> 6
        h = (h + (h << 3)) & 0xffffffff
        h ^= h >> 11
        h = (h + (h << 15)) & 0xffffffff
        d[h] = n
    return d


def patch_index(pack):
    """patch 名 → (cx, cy, z0)"""
    import ymap_entities
    nm = names_map()
    idx = {}
    for y in glob.glob(os.path.join(INNER, pack, '*.ymap')):
        try:
            _s, _z, es = ymap_entities.extract(y)
        except Exception:
            continue
        for e in es:
            n = nm.get(e[0], '')
            if n.startswith(pack) and '_hd_' in n and not n.endswith(('_lod', '_slod')):
                idx[n] = (e[1], e[2], e[3])
    return idx


def parse_pack(pack, res=4.0):
    """返回 (z 栅格, 覆盖掩码, x0, y0, res)，坐标系与世界一致。"""
    import rdr2_ydr as Y
    idx = patch_index(pack)
    boxes = []
    files = sorted(glob.glob(os.path.join(INNER, pack, '*_hd_*.ydr')))
    files = [f for f in files if not f.endswith(('_lod.ydr', '_slod.ydr'))]
    pts = []
    for f in files:
        stem = os.path.basename(f)[:-4]
        p = idx.get(stem)
        if not p:
            # 后备：从同名前缀推（名字可能带大小写差异）
            cand = [k for k in idx if k.lower() == stem.lower()]
            if not cand:
                continue
            p = idx[cand[0]]
        try:
            res_ = Y.Res(open(f, 'rb').read())
            _info, meshes = Y.extract_at(res_, 0, 'high')
        except Exception as e:
            print('  parse fail', stem, e)
            continue
        for m in meshes:
            a = np.asarray(m['positions'], dtype='float64').reshape(-1, 3)
            a[:, 0] += p[0]; a[:, 1] += p[1]; a[:, 2] += p[2]
            pts.append(a)
    if not pts:
        return None
    allp = np.concatenate(pts, 0)
    x0, y0 = allp[:, 0].min(), allp[:, 1].min()
    x1, y1 = allp[:, 0].max(), allp[:, 1].max()
    W = int(round((x1 - x0) / res)) + 1
    H = int(round((y1 - y0) / res)) + 1
    acc = np.zeros((H, W), np.float64)
    cnt = np.zeros((H, W), np.int32)
    c = np.round((allp[:, 0] - x0) / res).astype(np.int32)
    r = np.round((allp[:, 1] - y0) / res).astype(np.int32)
    ok = (c >= 0) & (c < W) & (r >= 0) & (r < H)
    np.add.at(acc, (r[ok], c[ok]), allp[ok, 2])
    np.add.at(cnt, (r[ok], c[ok]), 1)
    z = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan)
    return z, cnt > 0, x0, y0, res


def hillshade(z, mask, path, px=1):
    gy, gx = np.gradient(np.nan_to_num(z, nan=np.nanmedian(z)))
    az, alt = np.radians(315), np.radians(45)
    slope = np.arctan(np.hypot(gx / px, gy / px) * 2)
    aspect = np.arctan2(-gx, gy)
    hs = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    hs = np.clip(hs, 0, 1)
    img = (hs * 255).astype(np.uint8)
    img[~mask] = 0
    Image.fromarray(img[::-1]).save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pack', required=True)
    ap.add_argument('--png', default='')
    ap.add_argument('--res', type=float, default=4.0)
    a = ap.parse_args()
    out = parse_pack(a.pack, a.res)
    if out is None:
        print('no data')
        return
    z, mask, x0, y0, res = out
    print('%s  x[%.0f,%.0f] y[%.0f,%.0f]  %.1f m/px  cover %.1f%%  z[%.1f,%.1f] mean %.1f' % (
        a.pack, x0, x0 + z.shape[1] * res, y0, y0 + z.shape[0] * res, res,
        100 * mask.mean(), np.nanmin(z), np.nanmax(z), np.nanmean(z)))
    if a.png:
        os.makedirs(os.path.dirname(a.png), exist_ok=True)
        hillshade(z, mask, a.png)
        print('→', a.png)


if __name__ == '__main__':
    main()
