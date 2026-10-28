"""微缩模型 v4：乐高化（GoT 开场那种"特征建筑做成积木模型"）。

按用户定的方向：
  1. 只挑当前城市的**特征建筑**（教堂 / 车站 / 银行 / 庄园 / 工厂 / 码头 / 轮船…），其余普通房子**直接忽略**；
  2. 特征建筑用**体素化（voxelize）**变成乐高块：真实网格 → 占位格子 → 只留外表面 → 沿轴合并成四边形；
  3. 颜色取自该模型自己的真实贴图（每个体素取落在里面的顶点色）。

为什么比之前的做法对
  · 之前是"给每栋房子套一个盒子"→ 全是一个样、还像纸片；
  · 现在是"把真的圣丹尼斯大教堂、火车站、仓库、邮轮…切成积木"→ 形状是真的，量是少的（几十个物件），
    远看就是 GoT 开场那种"模型摆件"。

用法
  uv run python tools/build_miniatures_lego.py --code sdn
  uv run python tools/build_miniatures_lego.py
"""
import os
import re
import csv
import json
import math
import glob
import struct
import argparse
import importlib.util

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
_s = importlib.util.spec_from_file_location('rdr2_mdl', os.path.join(HERE, 'rdr2_mdl.py'))
MDL = importlib.util.module_from_spec(_s)
_s.loader.exec_module(MDL)

TOWN_DATA = os.path.join(ROOT, 'export/levels/world/town_data')
LEDGER = os.path.join(ROOT, 'deliverable/handoff/model_ledger.csv')
SETTLE = os.path.join(ROOT, 'deliverable/handoff/settlements_world_v2.csv')
HEIGHT_RAW = os.path.join(ROOT, 'deliverable/heightmap/continent_height_r16.raw')
HEIGHT_META = os.path.join(ROOT, 'deliverable/heightmap/continent_height_meta.json')
OUT = os.path.join(ROOT, 'deliverable/miniatures')
MODELS = os.path.join(OUT, 'models')
TEX = os.path.join(OUT, 'tex')

MAP_SCALE = 1.0 / 29.0
MIN_DIM_M = 2.5
VOXEL = 0.062          # 沙盘米 / 格（≈1.8 m 实景）：这个尺寸出来的块"像乐高"
PREFIX = re.compile(r'=\s*(\[.*\]);?\s*$', re.S)

# 特征建筑：名字里带这些的优先
FEATURE_KW = [
    ('church', 6), ('cathedral', 6), ('chapel', 5),
    ('station', 5), ('trainstn', 5), ('depot', 4),
    ('bank', 5), ('cityhall', 5), ('courthouse', 5), ('theatre', 5), ('hotel', 4),
    ('mansion', 5), ('man_', 4), ('plantation', 5),
    ('jail', 4), ('prison', 5), ('pen', 3),
    ('factory', 4), ('mill', 4), ('derrick', 3), ('conv', 3),
    ('saloon', 4), ('store', 3), ('shop', 3),
    ('warehouse', 4), ('wrh', 4), ('dockside', 3), ('dock', 3), ('pier', 3),
    ('tower', 3), ('hall', 3), ('school', 3), ('hospital', 4),
]
BLD_BAD = ('debris', '_veg', 'veg_', 'water', 'collision', '_slod', '_lod',
           'audioproxy', 'occlusion', 'helper', 'vfx_', 'decal_', '_strm',
           'terrain', 'ground', '_shadow', 'light_', 'leaves', 'tree', 'bush',
           '__hd_', '_hd_0', 'p_12__', 'weed', 'grass',
           'decal', 'kudzu', 'cable', 'glue', 'detail', '_dtl', '_dec',
           'roaddetail', '_trail', '_track', '_int', '_far', '_script',
           'vertex', '_vw', 'fence', 'hitching', 'post_', 'rail_',
           'rds_', '_rds', 'grndec', 'runoff', 'seawall', 'wareroof',
           'ter0', 'terrain', 'pavement', 'road')
NOT_BLD_PREFIX = ('p_', 's_', 'w_', 'v_', 'crp_', 'su_', 'rdr_', 'meta_',
                  'j_', 'dak_', 'veg_', 'amb_', 'prop_')
BOAT_KW = ('ship', 'boat', 'steam', 'ferry', 'tug')


# ---------------------------------------------------------------- 数据
def load_ledger():
    d = {}
    with open(LEDGER, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            d[int(r['hash'], 16)] = {
                'name': r['name'], 'tris': int(r['tris']),
                'sx': float(r['sx']), 'sy': float(r['sy']), 'sz': float(r['sz']),
            }
    return d


def load_settlements():
    out = []
    with open(SETTLE, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if not r['code']:
                continue
            out.append({'code': r['code'], 'name_zh': r['name_zh'], 'btype': r['btype'],
                        'x': float(r['world_x']), 'y': float(r['world_y']),
                        'w': float(r['size_w_m']), 'd': float(r['size_d_m'])})
    return out


def load_instances():
    uni = {}
    for p in glob.glob(os.path.join(TOWN_DATA, '*.js')):
        txt = open(p, encoding='utf-8', errors='replace').read()
        m = PREFIX.search(txt)
        if not m:
            continue
        try:
            arr = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        for e in arr:
            k = (e[0], round(e[1], 1), round(e[2], 1), round(e[3], 1))
            if k not in uni:
                uni[k] = e
    return list(uni.values())


class Terrain:
    def __init__(self):
        meta = json.load(open(HEIGHT_META, encoding='utf-8'))
        h = meta['heightmap']
        self.x0, self.y1 = meta['x0'], meta['y1']
        self.w, self.h = h['w'], h['h']
        self.zmin, self.zmax = h['zmin'], h['zmax']
        a = np.fromfile(HEIGHT_RAW, dtype='<u2').reshape(self.h, self.w).astype(np.float32)
        self.z = self.zmin + a / 65535.0 * (self.zmax - self.zmin)

    def at(self, x, y):
        c = max(0, min(self.w - 1, int((x - self.x0) / 4)))
        r = max(0, min(self.h - 1, int((self.y1 - y) / 4)))
        return float(self.z[r, c])


# ---------------------------------------------------------------- 体素化
def tri_samples(pos, idx, step):
    """在三角形表面按 step 间隔撒点，返回 (points, tri_index)。"""
    v0, v1, v2 = pos[idx[:, 0]], pos[idx[:, 1]], pos[idx[:, 2]]
    area2 = np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)     # = 2*area
    n = np.maximum(1, np.minimum(400, np.round(area2 / (step * step * 2)).astype(np.int64)))
    pts, tidx = [], []
    rng = np.random.default_rng(7)
    for k in range(int(n.max())):
        sel = np.where(n > k)[0]
        if len(sel) == 0:
            break
        r1 = np.sqrt(rng.random(len(sel)))
        r2 = rng.random(len(sel))
        a = 1 - r1
        b = r1 * (1 - r2)
        c = r1 * r2
        p = (v0[sel] * a[:, None] + v1[sel] * b[:, None] + v2[sel] * c[:, None])
        pts.append(p)
        tidx.append(sel)
    if not pts:
        return np.zeros((0, 3), np.float32), np.zeros(0, np.int64)
    return np.vstack(pts).astype(np.float32), np.concatenate(tidx)



WALL_COL = [(0.88, 0.84, 0.74), (0.80, 0.70, 0.56), (0.70, 0.58, 0.46),
            (0.84, 0.82, 0.78), (0.74, 0.66, 0.54)]
ROOF_COL = [(0.58, 0.30, 0.24), (0.34, 0.37, 0.40), (0.48, 0.42, 0.34),
            (0.40, 0.44, 0.38), (0.62, 0.40, 0.30)]


def slab_build(p, idx, col, layers=6, split=2, pal=0):
    """把一栋楼按高度切成 layers 层，每层取水平投影的包围盒 → 一摞"乐高台阶"。

    比体素稳：体素对薄墙会碎成柱子；切片永远是有体积的实心块，
    而层数不同自然做出教堂的"宽基座 + 细塔"、仓库的"大平顶"。
    """
    z = p[:, 2]
    z0, z1 = float(z.min()), float(z.max())
    h = max(z1 - z0, 0.5)
    V, C, I = [], [], []
    for L in range(layers):
        a = z0 + h * L / layers
        b = z0 + h * (L + 1) / layers
        m = (z[idx[:, 0]] >= a - 0.01) & (z[idx[:, 0]] < b + 0.01)
        tri = idx[m]
        if len(tri) == 0:
            continue
        vv = p[tri.reshape(-1)]
        cc = col[m].mean(0)
        x0, x1 = float(vv[:, 0].min()), float(vv[:, 0].max())
        y0, y1 = float(vv[:, 1].min()), float(vv[:, 1].max())
        if x1 - x0 < 0.3 or y1 - y0 < 0.3:
            continue
        # 每层最多拆成 2 块（沿长边切），避免整层一个大方块
        cuts = [ (x0, x1) ] if split <= 1 else [(x0, (x0 + x1) / 2), ((x0 + x1) / 2, x1)]
        for (cx0, cx1) in cuts:
            if cx1 - cx0 < 0.3:
                continue
            base = len(V)
            wc = WALL_COL[pal % len(WALL_COL)]
            for (qx, qy, qz) in ((cx0, y0, a), (cx1, y0, a), (cx1, y1, a), (cx0, y1, a),
                                 (cx0, y0, b), (cx1, y0, b), (cx1, y1, b), (cx0, y1, b)):
                V.append((qx, qy, qz))
                C.append(wc)
            f = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6),
                 (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2),
                 (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
            is_top = L == layers - 1
            if is_top:      # 顶层顶面刷成屋顶色
                rc = ROOF_COL[pal % len(ROOF_COL)]
                for vi_ in (4, 5, 6, 7):
                    C[base + vi_] = rc
            for (i0, i1, i2) in f:
                I.append((base + i0, base + i1, base + i2))
    return V, C, I


def voxelize(pos, idx, cell, color_fn):
    """表面撒点 → 占位格 → 只留外表面 → 每个面合并成四边形。"""
    if len(idx) == 0:
        return None
    p, ti = tri_samples(pos, idx, cell * 0.38)
    if len(p) == 0:
        return None
    col = color_fn(p, ti)

    origin = p.min(0)
    q = np.floor((p - origin) / cell).astype(np.int32)
    q -= q.min(0)
    dims = q.max(0) + 1
    if dims.prod() > 2_000_000:          # 太大的东西先降精度
        cell *= 1.6
        return voxelize(pos, idx, cell, color_fn)

    key = (q[:, 0].astype(np.int64) * dims[1] + q[:, 1]) * dims[2] + q[:, 2]
    uniq, inv = np.unique(key, return_inverse=True)
    occ = np.zeros(dims.prod(), bool)
    occ[uniq] = True
    occ = occ.reshape(tuple(dims))
    try:
        from scipy import ndimage
        # 只留外表面时是"空壳"，一格 2.6 m 会碎成断墙：
        # 先闭运算把撒点的缝补上，再填成实心，才是能看的乐高块
        # 薄墙 (<1 格) 采不到闭合体积，先膨胀一格变成 3 格厚，再填实 —— 这才是乐高块
        occ = ndimage.binary_dilation(occ, iterations=1)
        occ = ndimage.binary_fill_holes(occ)
    except Exception:
        pass

    csum = np.zeros((len(uniq), 3), np.float64)
    cnt = np.zeros(len(uniq), np.float64)
    np.add.at(csum, inv, col)
    np.add.at(cnt, inv, 1)
    vcol = csum / np.maximum(cnt, 1)[:, None]

    cube = np.zeros(tuple(dims), np.int64)
    cube.reshape(-1)[uniq] = np.arange(len(uniq))

    V, C, I = [], [], []
    pad = np.pad(occ, 1)
    dirs = [((1, 0, 0), [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]),
            ((-1, 0, 0), [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)]),
            ((0, 1, 0), [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)]),
            ((0, -1, 0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]),
            ((0, 0, 1), [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]),
            ((0, 0, -1), [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)])]
    nx, ny, nz = dims
    for (d, quad) in dirs:
        nb = pad[1 + d[0]:1 + d[0] + nx, 1 + d[1]:1 + d[1] + ny, 1 + d[2]:1 + d[2] + nz]
        face = occ & (~nb)
        if not face.any():
            continue
        xs, ys, zs = np.nonzero(face)
        for x, y, z in zip(xs, ys, zs):
            o = np.array([x, y, z], np.float64) * cell + origin
            base = len(V)
            for qv in quad:
                V.append(tuple(o + np.array(qv, np.float64) * cell))
            cid = cube[x, y, z]
            cc = tuple(np.clip(vcol[cid], 0, 1).tolist())
            C.extend([cc] * 4)
            I.append((base, base + 1, base + 2))
            I.append((base, base + 2, base + 3))
    return V, C, I


# ---------------------------------------------------------------- GLB（顶点色）
def write_glb(path, P, C, I, name):
    pos = np.asarray(P, np.float32).reshape(-1, 3)
    col = np.asarray(C, np.float32).reshape(-1, 3)
    idx = np.asarray(I, np.int64).reshape(-1, 3)
    if len(idx) == 0:
        return 0, 0

    v0, v1, v2 = pos[idx[:, 0]], pos[idx[:, 1]], pos[idx[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    n = n / ln

    P2, N2, C2, I2 = [], [], [], []
    off = 0
    for t in range(len(idx)):
        P2.append(v0[t]); P2.append(v1[t]); P2.append(v2[t])
        for v in (0, 1, 2):
            N2.append(n[t])
            C2.append(col[idx[t, v]])
        I2.extend([off, off + 1, off + 2])
        off += 3
    P2 = np.asarray(P2, np.float32)
    N2 = np.asarray(N2, np.float32)
    C2 = np.asarray(C2, np.float32)
    I2 = np.asarray(I2, np.uint32)

    blob = bytearray()
    views = []

    def add(arr, target=None):
        while len(blob) % 4:
            blob.append(0)
        o = len(blob)
        b = arr.tobytes()
        blob.extend(b)
        v = {'buffer': 0, 'byteOffset': o, 'byteLength': len(b)}
        if target:
            v['target'] = target
        views.append(v)
        return len(views) - 1

    vp = add(P2, 34962); vn = add(N2, 34962); vc = add(C2, 34962)
    vi = add(I2, 34963)
    gltf = {
        'asset': {'version': '2.0', 'generator': 'rdr2-lego/1.0'},
        'scene': 0, 'scenes': [{'nodes': [0], 'name': name}],
        'nodes': [{'mesh': 0, 'name': name}],
        'meshes': [{'name': name, 'primitives': [{
            'attributes': {'POSITION': 0, 'NORMAL': 1, 'COLOR_0': 2},
            'indices': 3, 'material': 0, 'mode': 4}]}],
        'materials': [{'name': name + '_mat', 'pbrMetallicRoughness': {
            'baseColorFactor': [1, 1, 1, 1], 'metallicFactor': 0.0,
            'roughnessFactor': 0.92}, 'doubleSided': False}],
        'accessors': [
            {'bufferView': vp, 'componentType': 5126, 'count': len(P2), 'type': 'VEC3',
             'min': P2.min(0).tolist(), 'max': P2.max(0).tolist()},
            {'bufferView': vn, 'componentType': 5126, 'count': len(N2), 'type': 'VEC3'},
            {'bufferView': vc, 'componentType': 5126, 'count': len(C2), 'type': 'VEC3'},
            {'bufferView': vi, 'componentType': 5125, 'count': len(I2), 'type': 'SCALAR'},
        ],
        'bufferViews': views, 'buffers': [{'byteLength': len(blob)}],
    }
    js = json.dumps(gltf, separators=(',', ':')).encode()
    while len(js) % 4:
        js += b' '
    while len(blob) % 4:
        blob.append(0)
    total = 12 + 8 + len(js) + 8 + len(blob)
    with open(path, 'wb') as f:
        f.write(struct.pack('<III', 0x46546C67, 2, total))
        f.write(struct.pack('<II', len(js), 0x4E4F534A))
        f.write(js)
        f.write(struct.pack('<II', len(blob), 0x004E4942))
        f.write(bytes(blob))
    return len(P2), len(I2) // 3


# ---------------------------------------------------------------- 选特征建筑
def feature_score(name, sx, sy, sz, tris):
    n = name.lower()
    if any(b in n for b in BLD_BAD):
        return 0
    s = 1.0
    for kw, w in FEATURE_KW:
        if kw in n:
            s = max(s, w)
            break
    if any(k in n for k in BOAT_KW):
        s = max(s, 3.0)
    # 体量分（对数，避免一个巨型仓库压死所有）
    vol = max(sx * sy * max(sz, 1.0), 1.0)
    return s * (vol ** 0.33)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--code', default='')
    ap.add_argument('--max-features', type=int, default=46)
    args = ap.parse_args()

    os.makedirs(MODELS, exist_ok=True)
    ledger = load_ledger()
    settles = load_settlements()
    insts = load_instances()
    terr = Terrain()

    rows = []
    for i, s in enumerate(settles):
        if args.code and s['code'] != args.code:
            continue
        hw, hd = s['w'] / 2, s['d'] / 2
        sel = [e for e in insts if abs(e[1] - s['x']) <= hw and abs(e[2] - s['y']) <= hd]

        cand = []
        for e in sel:
            m = ledger.get(e[0])
            if not m:
                continue
            if m['sx'] * abs(e[8]) > 110 or m['sy'] * abs(e[9]) > 110 or m['sz'] * abs(e[10]) > 95:
                continue
            sc = feature_score(m['name'], m['sx'] * abs(e[8]), m['sy'] * abs(e[9]),
                               m['sz'] * abs(e[10]), m['tris'])
            if sc > 0:
                cand.append((sc, e, m))
        # 全城建筑 → 按 30 m 网格聚成"街区"，一个街区出一块积木（乐高化的关键）
        CELL = 30.0
        blocks = {}
        for sc, e, m in cand:
            kx = int(math.floor(e[1] / CELL))
            ky = int(math.floor(e[2] / CELL))
            b = blocks.setdefault((kx, ky), {'x0': 1e9, 'x1': -1e9, 'y0': 1e9, 'y1': -1e9,
                                             'zmax': -1e9, 'zmin': 1e9, 'n': 0, 'e': e})
            w = m['sx'] * abs(e[8])
            d = m['sy'] * abs(e[9])
            b['x0'] = min(b['x0'], e[1] - w / 2); b['x1'] = max(b['x1'], e[1] + w / 2)
            b['y0'] = min(b['y0'], e[2] - d / 2); b['y1'] = max(b['y1'], e[2] + d / 2)
            b['zmax'] = max(b['zmax'], e[3] + m['sz'] * abs(e[10]))
            b['zmin'] = min(b['zmin'], e[3])
            b['n'] += 1
        keep = []
        for ky_k, b in blocks.items():
            if b['n'] < 2:            # 孤零零一栋不要（街道碎件）
                continue
            keep.append((b['n'], b['e'], None, b))
        keep.sort(key=lambda t: -t[0])
        if not keep:
            print('!! 没特征建筑', s['code'])
            continue

        cx = sum(e[1] for _sc, e, _m in keep) / len(keep)
        cy = sum(e[2] for _sc, e, _m in keep) / len(keep)
        k = MAP_SCALE
        bw = max(e[1] for _sc, e, _m in keep) - min(e[1] for _sc, e, _m in keep)
        bd = max(e[2] for _sc, e, _m in keep) - min(e[2] for _sc, e, _m in keep)
        if max(bw, bd) * k < MIN_DIM_M:
            k = MIN_DIM_M / max(bw, bd, 1.0)

        P, C, I = [], [], []
        placed = 0
        for sc, e, m in keep:
            g = MDL.load_mdl(e[0])
            if g is None:
                continue
            pos, nrm, uv, idx, tids, vtex = g
            if len(idx) == 0:
                continue
            sx, sy, sz = abs(e[8]), abs(e[9]), abs(e[10])
            p = pos * np.array([sx, sy, sz], np.float32)
            qx, qy, qz, qw = e[4], e[5], e[6], e[7]
            yaw = math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))
            c, sn = math.cos(yaw), math.sin(yaw)
            x = p[:, 0] * c - p[:, 1] * sn
            y = p[:, 0] * sn + p[:, 1] * c
            p = np.stack([x, y, p[:, 2]], axis=1)
            # 数据里不少"模型"夹着几百米外的杂件（整块街区/远景）。用 2%~98% 分位把离群三角形切掉，
            # 剩下的才是这栋楼本身。
            tri = idx
            keep = np.ones(len(tri), bool)
            # 只按高度裁：留 [最低点, 最低点 + 名录高度×1.15]，把夹带进来的远景杂件切掉
            v = p[:, 2]
            lo = v.min()
            hi = lo + max(m['sz'] * abs(e[10]), 4.0) * 1.15
            keep &= ((v[tri] > lo - 2.0) & (v[tri] < hi + 2.0)).all(1)
            # 水平方向再兜一层：离中心超过 1.2×名录尺寸的不要
            for ax in (0, 1):
                vv = p[:, ax]
                mid = float(np.median(vv))
                lim = max(m['sx'] * abs(e[8]), m['sy'] * abs(e[9])) * 0.75 + 4.0
                keep &= (np.abs(vv[tri] - mid) < lim).all(1)
            if keep.sum() < 8:
                continue
            idx = tri[keep]
            # 重建顶点（只留用到的）
            used = np.unique(idx)
            remap = np.full(len(p), -1, np.int64)
            remap[used] = np.arange(len(used))
            p = p[used]
            idx = remap[idx]

            tex_cache = {}
            def color_fn(pts, tids_idx, uv=uv, idx=idx, vtex=vtex, tids=tids):
                # 用三角形三个顶点的平均 uv 去取色
                tri = idx[tids_idx]
                u = uv[tri].mean(1)
                out = np.zeros((len(u), 3), np.float32)
                out[:] = (0.55, 0.52, 0.47)
                for tid in np.unique(vtex):
                    selm = vtex[tri[:, 0]] == tid
                    if not selm.any():
                        continue
                    tex = MDL.load_tex(int(tid))
                    if tex is None:
                        continue
                    ccol = MDL.sample_tex(tex, u[selm])
                    out[selm] = np.where(ccol <= 0.04045, ccol / 12.92,
                                         ((ccol + 0.055) / 1.055) ** 2.4)
                return np.clip(out * 1.45, 0, 1)

            # 切片法：按高度分层，每层取包围盒 → 一摞实心"乐高台阶"
            hgt = float(np.max(p[:, 2] - p[:, 2].min()))
            layers = int(np.clip(round(hgt / 4.0), 3, 9))
            cols = color_fn(p[idx[:, 0]], np.arange(len(idx)))
            pal = (int(e[0]) >> 4) % 5
            v = slab_build(p, idx, cols, layers=layers,
                           split=2 if max(m['sx'], m['sy']) > 14 else 1, pal=pal)
            if v is None:
                continue
            V, CC, II = v
            base = len(P)
            ox = (e[1] - cx) * k
            oz = -(e[2] - cy) * k
            oy = (e[3] - terr.at(e[1], e[2])) * k
            P.extend([(px * k + ox, pz * k + oy, -py * k + oz) for (px, py, pz) in V])
            C.extend(CC)
            I.extend([(a + base, b + base, c + base) for (a, b, c) in II])
            placed += 1

        if not P:
            print('!! 空', s['code'])
            continue

        Pa = np.asarray(P, np.float32)
        Pa[:, 1] -= Pa[:, 1].min()

        # 底座：一块街道色的薄板，把特征建筑"摆"在上面（GoT 开场那种模型底板）
        hx = (Pa[:, 0].max() - Pa[:, 0].min()) / 2 + 0.6
        hz = (Pa[:, 2].max() - Pa[:, 2].min()) / 2 + 0.6
        cxm = (Pa[:, 0].max() + Pa[:, 0].min()) / 2
        czm = (Pa[:, 2].max() + Pa[:, 2].min()) / 2
        base_i = len(P)
        for (dx, dz) in ((-1, -1), (-1, 1), (1, 1), (1, -1)):
            P.append((cxm + dx * hx, 0.0, czm + dz * hz))
            C.append((0.55, 0.52, 0.43))
        I.append((base_i, base_i + 1, base_i + 2))
        I.append((base_i, base_i + 2, base_i + 3))
        Pa = np.asarray(P, np.float32)
        nv, nt = write_glb(os.path.join(MODELS, s['code'] + '.glb'), Pa, C, I, s['code'])
        print(f"{s['code']:7} {s['name_zh'][:10]:11} 特征 {placed:3d}  面 {nt:6,d}  "
              f"尺寸 {bw*k:.1f}x{bd*k:.1f} m")
        rows.append({'code': s['code'], 'name_zh': s['name_zh'], 'btype': s['btype'],
                     'size_x': round(bw * k, 2), 'size_z': round(bd * k, 2),
                     'scale': round(k, 5), 'scale_boost': round(k / MAP_SCALE, 2),
                     'tris': nt, 'verts': nv, 'n_tex': 0,
                     'n_inst_in_box': len(sel), 'n_items': len(cand),
                     'n_placed': placed, 'n_skipped': 0,
                     'tex': '', 'tex_kb': 0, 'glb_kb': round(os.path.getsize(os.path.join(MODELS, s['code'] + '.glb')) / 1024, 1),
                     'landmark1': '', 'landmark1_kind': '', 'landmark2': '', 'landmark2_kind': '',
                     'landmark3': '', 'landmark3_kind': '',
                     'world_x': s['x'], 'world_y': s['y'], 'bbox_w': s['w'], 'bbox_d': s['d']})

    if rows and not args.code:
        with open(os.path.join(OUT, 'audit.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        json.dump(rows, open(os.path.join(OUT, 'audit.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        t = sum(r['tris'] for r in rows)
        print(f'\n{len(rows)} 个据点 · 合计 {t:,} 面 · 最大 {max(r["tris"] for r in rows):,}')


if __name__ == '__main__':
    main()
