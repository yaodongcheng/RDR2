"""微缩模型 v2：用**游戏里的真实建筑网格**做，不再拿方块代理。

和 v1 的区别
  v1：每个街区塞一个"盒 + 坡屋顶"代理，远看是纸片。
  v2：逐实例加载 assets/lib_native 里真实的 .mdl，按模型自身尺寸做顶点聚类减面
      （保留 L 形、门廊、坡屋顶、教堂尖顶这些真实剪影），颜色取**该模型自己的贴图**，
      最后按据点合并成一个 mesh。

流程
  选实例 → 每栋加载真实网格 → 顶点色取自贴图 → 顶点聚类减面到目标面数
  → 按据点合并（+ 地形底座）→ 写 GLB（顶点色 + 一张 512² 颗粒贴图）

预算
  每栋目标面数 = clamp(占地 m² × d, 16, 900)，d 由据点分档决定；
  合并后若超上限，d 自动下调重算（最多 4 轮）。

用法
  uv run python tools/build_miniatures_real.py --code sdn
  uv run python tools/build_miniatures_real.py
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
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location('rdr2_mdl', os.path.join(HERE, 'rdr2_mdl.py'))
MDL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MDL)

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
PREFIX = re.compile(r'=\s*(\[.*\]);?\s*$', re.S)

# 面数上限（与规格 7.0.1 分档一致）
TIER_CAP = {'town': 260000, 'castle': 130000, 'village': 90000,
            'camp': 70000, 'poi': 70000, 'hideout': 70000}

BLD_BAD = ('debris', '_veg', 'veg_', 'water', 'collision', '_slod', '_lod',
           'audioproxy', 'occlusion', 'helper', 'vfx_', 'decal_', '_strm',
           'terrain', 'ground', '_shadow', 'light_', 'leaves', 'tree', 'bush',
           '__hd_', '_hd_0', 'p_12__', 'weed', 'grass',
           'decal', 'kudzu', 'cable', 'glue', 'detail', '_dtl', '_dec',
           'roaddetail', '_trail', '_track', '_int', '_far', '_script',
           'vertex', '_vw', 'fence', 'hitching', 'post_', 'rail_',
           'rds_', '_rds', 'grndec', 'runoff', 'seawall', 'dockside',
           'wareroof', 'ter0', 'terrain', 'pavement', 'road')
NOT_BLD_PREFIX = ('p_', 's_', 'w_', 'v_', 'crp_', 'su_', 'rdr_', 'meta_',
                  'j_', 'dak_', 'veg_', 'amb_', 'prop_')
KEEP_PROP = ('ship', 'boat', 'steam', 'train', 'locomotive', 'watertower',
             'tank', 'derrick', 'crane', 'windmill', 'tent', 'campfire',
             'wagon', 'cart', 'canopy', 'dock', 'pier', 'bridge', 'silo')


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
            out.append({'code': r['code'], 'name_zh': r['name_zh'], 'name_en': r['name_en'],
                        'btype': r['btype'], 'faction': r['faction'],
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


def is_building(name, sz, tris, sx=None, sy=None):
    n = name.lower()
    if any(b in n for b in BLD_BAD):
        return False
    if n.startswith(NOT_BLD_PREFIX):
        return False
    if sx is not None and (sx > 80 or sy > 80):
        return False
    return 2.5 <= sz <= 80 and tris >= 40


def is_keep_prop(name, sz):
    n = name.lower()
    return n.startswith('p_') and any(k in n for k in KEEP_PROP) and sz >= 1.0


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
        c = int((x - self.x0) / 4)
        r = int((self.y1 - y) / 4)
        c = max(0, min(self.w - 1, c))
        r = max(0, min(self.h - 1, r))
        return float(self.z[r, c])

    def smooth(self, x, y):
        return (self.at(x, y) * 2 + self.at(x + 3, y) + self.at(x - 3, y) +
                self.at(x, y + 3) + self.at(x, y - 3)) / 6.0


# ---------------------------------------------------------------- 减面
def cluster_decimate(pos, col, idx, cell):
    """顶点聚类减面：按 cell 网格合并顶点，丢掉退化三角形。返回 (pos, col, idx)。"""
    if len(pos) == 0 or len(idx) == 0 or cell <= 0:
        return pos, col, idx
    q = np.floor(pos / cell).astype(np.int64)
    q -= q.min(0)
    dims = q.max(0) + 1
    key = (q[:, 0] * dims[1] + q[:, 1]) * dims[2] + q[:, 2]
    uniq, inv = np.unique(key, return_inverse=True)
    n = len(uniq)
    cnt = np.bincount(inv, minlength=n).astype(np.float32)
    npos = np.zeros((n, 3), np.float64)
    ncol = np.zeros((n, 3), np.float64)
    np.add.at(npos, inv, pos)
    np.add.at(ncol, inv, col)
    npos /= cnt[:, None]
    ncol /= cnt[:, None]
    f = inv[idx]
    good = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])
    f = f[good]
    if len(f) == 0:
        return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.float32), np.zeros((0, 3), np.int64)
    return npos.astype(np.float32), ncol.astype(np.float32), f.astype(np.int64)


def keep_largest(pos, col, idx, target):
    """按"面面积"保留最大的 target 个三角面。

    为什么不用顶点聚类：建筑是**薄壳**（墙只有一层皮），聚类把壳的顶点平均到格子里，
    出来是一堆尖片（实测 4 万面的教堂聚到 200 面就成了一地碎玻璃）。
    按面积裁面则是"留下墙和屋顶的大面、丢掉窗框栏杆"，剪影能保住。
    """
    if len(idx) <= target:
        return pos, col, idx
    v0, v1, v2 = pos[idx[:, 0]], pos[idx[:, 1]], pos[idx[:, 2]]
    area = np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)
    keep = np.argpartition(-area, target)[:target]
    f = idx[keep]
    used = np.unique(f)
    remap = np.full(len(pos), -1, np.int64)
    remap[used] = np.arange(len(used))
    return pos[used], col[used], remap[f]


def keep_largest_uv(pos, uv, idx, target):
    """按面面积保留最大的 target 个面，同时保住 UV（所以能贴回真实贴图）。"""
    if len(idx) <= target:
        return pos, uv, idx
    v0, v1, v2 = pos[idx[:, 0]], pos[idx[:, 1]], pos[idx[:, 2]]
    area = np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)
    keep = np.argpartition(-area, target)[:target]
    f = idx[keep]
    used = np.unique(f)
    remap = np.full(len(pos), -1, np.int64)
    remap[used] = np.arange(len(used))
    return pos[used], uv[used], remap[f]



def box_roof(w, d, h, uv_rect):
    """用真实包围盒做一个带贴图的实体块 + 坡屋顶。

    参数都是"沙盘米"。uv_rect = (u0, v0, u1, v1) 指向图集里这张贴图的格子。
    """
    u0, v0, u1, v1 = uv_rect
    hw, hd = w / 2, d / 2
    body = h * (0.58 + 0.16 * ((int(abs(w) * 1000) % 7) / 7.0))
    roof_h = h - body

    V, T, UVv, Cc = [], [], [], []

    def quad(p0, p1, p2, p3, uvs, tint=(1.0, 1.0, 1.0)):
        i = len(V)
        V.extend([p0, p1, p2, p3])
        UVv.extend(uvs)
        Cc.extend([tint] * 4)
        T.append((i, i + 1, i + 2))
        T.append((i, i + 2, i + 3))

    # 四面墙
    quad((-hw, 0, -hd), (hw, 0, -hd), (hw, body, -hd), (-hw, body, -hd),
         [(u0, v1), (u1, v1), (u1, v0), (u0, v0)])
    quad((hw, 0, -hd), (hw, 0, hd), (hw, body, hd), (hw, body, -hd),
         [(u0, v1), (u1, v1), (u1, v0), (u0, v0)])
    quad((hw, 0, hd), (-hw, 0, hd), (-hw, body, hd), (hw, body, hd),
         [(u0, v1), (u1, v1), (u1, v0), (u0, v0)])
    quad((-hw, 0, hd), (-hw, 0, -hd), (-hw, body, -hd), (-hw, body, hd),
         [(u0, v1), (u1, v1), (u1, v0), (u0, v0)])

    # 屋顶（两坡）
    ow = hw * 1.08
    od = hd * 1.08
    r = body + roof_h
    if w >= d:
        a = (-ow, body, -od); b = (ow, body, -od)
        c = (ow, body, od); dd = (-ow, body, od)
        r0 = (-ow, r, 0); r1 = (ow, r, 0)
        quad(a, b, r1, r0, [(u0, v1), (u1, v1), (u1, v0), (u0, v0)], (0.62, 0.58, 0.55))
        quad(c, dd, r0, r1, [(u0, v1), (u1, v1), (u1, v0), (u0, v0)])
        # 山墙三角
        i = len(V)
        V.extend([(-hw, body, -hd), (-hw, body, hd), (-hw, r, 0)])
        UVv.extend([(u0, v1), (u1, v1), (u0, v0)])
        Cc.extend([(1.0, 1.0, 1.0)] * 3)
        T.append((i, i + 1, i + 2))
        i = len(V)
        V.extend([(hw, body, hd), (hw, body, -hd), (hw, r, 0)])
        UVv.extend([(u0, v1), (u1, v1), (u0, v0)])
        Cc.extend([(1.0, 1.0, 1.0)] * 3)
        T.append((i, i + 1, i + 2))
    else:
        a = (-ow, body, -od); b = (ow, body, -od)
        c = (ow, body, od); dd = (-ow, body, od)
        r0 = (0, r, -od); r1 = (0, r, od)
        quad(a, r0, r1, dd, [(u0, v1), (u0, v1), (u1, v0), (u1, v0)], (0.62, 0.58, 0.55))
        quad(b, c, r1, r0, [(u0, v1), (u1, v1), (u1, v0), (u0, v0)], (0.62, 0.58, 0.55))
        i = len(V)
        V.extend([(-hw, body, -hd), (hw, body, -hd), (0, r, -hd)])
        UVv.extend([(u0, v1), (u1, v1), (u0, v0)])
        Cc.extend([(1.0, 1.0, 1.0)] * 3)
        T.append((i, i + 1, i + 2))
        i = len(V)
        V.extend([(hw, body, hd), (-hw, body, hd), (0, r, hd)])
        UVv.extend([(u0, v1), (u1, v1), (u0, v0)])
        Cc.extend([(1.0, 1.0, 1.0)] * 3)
        T.append((i, i + 1, i + 2))

    V = np.asarray(V, np.float32)
    T = np.asarray(T, np.int64)
    # 统一朝外
    v0, v1_, v2 = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    n = np.cross(v1_ - v0, v2 - v0)
    mid = (v0 + v1_ + v2) / 3.0
    ctr = np.array([0, body * 0.45, 0], np.float32)
    flip = (n * (mid - ctr)).sum(1) < 0
    T[flip] = T[flip][:, [0, 2, 1]]
    return V, np.asarray(UVv, np.float32), np.asarray(Cc, np.float32), T



ATLAS_N = 8
ATLAS_CELL = 128   # 8×8 × 128 = 1024²，够用且单城贴图 ~200 KB
ATLAS_SIZE = ATLAS_N * ATLAS_CELL
FALLBACK_CELL = ATLAS_N * ATLAS_N - 1


def atlas_plan(items):
    """统计这批实例用到的贴图，取使用量最大的 63 张做 8×8 图集，其余落到第 64 格。"""
    use = {}
    for (e, m, t) in items:
        for (tid, vc, ic, *_r) in _sub_ranges(e[0]):
            if tid == 0xFFFFFFFF or vc == 0 or ic == 0:
                continue
            use[tid] = use.get(tid, 0) + ic
    top = [k for k, _ in sorted(use.items(), key=lambda kv: -kv[1])[:ATLAS_N * ATLAS_N - 1]]
    return {tid: i for i, tid in enumerate(top)}, len(top)


def atlas_build(cells, seed):
    img = Image.new('RGB', (ATLAS_SIZE, ATLAS_SIZE), (110, 104, 92))
    rng = np.random.default_rng(seed)
    for tid, i in cells.items():
        p = os.path.join(MDL.LIB, 'tex', '%04d.png' % tid)
        cx, cy = i % ATLAS_N, i // ATLAS_N
        if os.path.exists(p):
            im = Image.open(p).convert('RGB').resize((ATLAS_CELL, ATLAS_CELL), Image.LANCZOS)
        else:
            a = (rng.random((ATLAS_CELL, ATLAS_CELL, 3)) * 40 + 90).astype(np.uint8)
            im = Image.fromarray(a, 'RGB')
        img.paste(im, (cx * ATLAS_CELL, cy * ATLAS_CELL))
    i = FALLBACK_CELL
    cx, cy = i % ATLAS_N, i // ATLAS_N
    img.paste(Image.new('RGB', (ATLAS_CELL, ATLAS_CELL), (146, 138, 118)),
              (cx * ATLAS_CELL, cy * ATLAS_CELL))
    return img


# ---------------------------------------------------------------- 模型缓存
_GEO_CACHE = {}


def model_geo(h, texids_ok=None):
    if h in _GEO_CACHE:
        return _GEO_CACHE[h]
    g = MDL.load_mdl(h)
    _GEO_CACHE[h] = g
    return g


def instance_geo(h, scale_x, scale_y, scale_z, quat, target_tris, cells):
    """把一个实例的真实网格 → 沙盘坐标 + 图集 UV + 已裁面。"""
    g = model_geo(h)
    if g is None:
        return None
    pos, nrm, uv, idx, tids, vtex = g
    if len(idx) == 0:
        return None

    # UV 重映射到图集格子
    cuv = np.zeros((len(uv), 2), np.float32)
    for tid in np.unique(vtex):
        sel = vtex == tid
        ci = cells.get(int(tid), FALLBACK_CELL)
        cx, cy = ci % ATLAS_N, ci // ATLAS_N
        cuv[sel, 0] = (cx + np.clip(uv[sel, 0], 0, 0.9999)) / ATLAS_N
        cuv[sel, 1] = (cy + np.clip(uv[sel, 1], 0, 0.9999)) / ATLAS_N

    pos = pos * np.array([scale_x, scale_y, scale_z], np.float32)
    qx, qy, qz, qw = quat
    yaw = math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))
    c, s_ = math.cos(yaw), math.sin(yaw)
    x = pos[:, 0] * c - pos[:, 1] * s_
    y = pos[:, 0] * s_ + pos[:, 1] * c
    pos = np.stack([x, y, np.clip(pos[:, 2], -5, 80)], axis=1)

    if target_tris and len(idx) > target_tris:
        pos, cuv, idx = keep_largest_uv(pos, cuv, idx, target_tris)
    return pos.astype(np.float32), cuv.astype(np.float32), idx.astype(np.int64)


def _sub_ranges(h):
    """读 .mdl 头部的子网格表（只取 texId/vCount/iCount，够用）。"""
    if h in _SUB_CACHE:
        return _SUB_CACHE[h]
    p = MDL.mdl_path(h)
    out = []
    if os.path.exists(p):
        with open(p, 'rb') as f:
            d = f.read(36 + 7 * 4 * 64)
        if d[:8] == MDL.MAGIC:
            nsub, = struct.unpack_from('<I', d, 8)
            for i in range(min(nsub, 64)):
                out.append(MDL.SUB.unpack_from(d, 36 + i * MDL.SUB.size))
    _SUB_CACHE[h] = out
    return out


_SUB_CACHE = {}
_MEAN_CACHE = {}
_BBOX_CACHE = {}
_DOM_CACHE = {}


def model_dominant_tex(h):
    """模型用得最多的那张贴图（按三角形数），用来给体块上色。"""
    if h in _DOM_CACHE:
        return _DOM_CACHE[h]
    best, best_ic = 0xFFFFFFFF, -1
    for (tid, vc, ic, *_r) in _sub_ranges(h):
        if ic > best_ic:
            best, best_ic = tid, ic
    _DOM_CACHE[h] = best
    return best


def model_bbox(h):
    """真实网格的包围盒（米）。ledger 里那份 bbox 对不少模型是错的（能到 1200 m），
    必须以 .mdl 里的顶点为准。"""
    if h in _BBOX_CACHE:
        return _BBOX_CACHE[h]
    g = model_geo(h)
    if g is None:
        _BBOX_CACHE[h] = None
        return None
    pos = g[0]
    bb = (pos.min(0), pos.max(0))
    _BBOX_CACHE[h] = bb
    return bb


def model_mean_color(h):
    if h in _MEAN_CACHE:
        return _MEAN_CACHE[h]
    tot = np.zeros(3, np.float64)
    wsum = 0.0
    for (tid, vc, ic, *_r) in _sub_ranges(h):
        if vc == 0 or ic == 0:
            continue
        tex = MDL.load_tex(tid) if tid != 0xFFFFFFFF else None
        if tex is None:
            continue
        tot += tex.reshape(-1, 3).mean(0) * vc
        wsum += vc
    c = (tot / wsum) if wsum else np.array([0.45, 0.42, 0.38])
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)   # sRGB→线性
    _MEAN_CACHE[h] = c.astype(np.float32)
    return _MEAN_CACHE[h]


# ---------------------------------------------------------------- 颗粒贴图
def grain_tex(seed, warm=0.0):
    rng = np.random.default_rng(seed)
    n = rng.random((64, 64)).astype(np.float32)
    im = Image.fromarray((n * 255).astype(np.uint8)).resize((512, 512), Image.BICUBIC)
    a = np.asarray(im, dtype=np.float32) / 255.0
    a = 0.90 + a * 0.20                      # 0.90~1.10 的明暗扰动
    rgb = np.stack([a * (1 + 0.03 * warm), a, a * (1 - 0.03 * warm)], axis=2)
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8), 'RGB')


# ---------------------------------------------------------------- 地形底座
def add_plinth(P, UV, C, I, terr, xs0, ys0, xs1, ys1, ox, oy, med, k, n):
    def P3(x, y):
        h = terr.smooth(x, y)
        rel = max(-8.0, min(8.0, h - med)) * 0.25
        return ((x - ox) * k, rel * k, -(y - oy) * k)

    grid = []
    for i in range(n + 1):
        row = []
        for j in range(n + 1):
            row.append(P3(xs0 + (xs1 - xs0) * j / n, ys0 + (ys1 - ys0) * i / n))
        grid.append(row)

    base = len(P)
    for i in range(n + 1):
        for j in range(n + 1):
            P.append(grid[i][j])
            cx_, cy_ = FALLBACK_CELL % ATLAS_N, FALLBACK_CELL // ATLAS_N
            UV.append(((cx_ + 0.5) / ATLAS_N, (cy_ + 0.5) / ATLAS_N))
            C.append((1.0, 1.0, 1.0))

    for i in range(n):
        for j in range(n):
            a = base + i * (n + 1) + j
            b = a + 1
            c_ = a + (n + 1)
            d = c_ + 1
            for tri in ((a, c_, b), (b, c_, d)):
                p0, p1, p2 = P[tri[0]], P[tri[1]], P[tri[2]]
                nx = (p1[1] - p0[1]) * (p2[2] - p0[2]) - (p1[2] - p0[2]) * (p2[1] - p0[1])
                ny = (p1[2] - p0[2]) * (p2[0] - p0[0]) - (p1[0] - p0[0]) * (p2[2] - p0[2])
                if ny < 0:
                    I.append((tri[0], tri[2], tri[1]))
                else:
                    I.append(tri)

    # 侧壁
    base2 = len(P)
    skirt_y = min(min(p[1] for p in row) for row in grid) - 0.05
    edge = []
    for j in range(n):
        edge.append((grid[0][j], grid[0][j + 1]))
        edge.append((grid[n][j + 1], grid[n][j]))
    for i in range(n):
        edge.append((grid[i + 1][0], grid[i][0]))
        edge.append((grid[i][n], grid[i + 1][n]))
    for a_, b_ in edge:
        o = len(P)
        P.extend([a_, b_, (b_[0], skirt_y, b_[2]), (a_[0], skirt_y, a_[2])])
        for v in range(4):
            cx_, cy_ = FALLBACK_CELL % ATLAS_N, FALLBACK_CELL // ATLAS_N
            UV.append(((cx_ + 0.5) / ATLAS_N, (cy_ + 0.5) / ATLAS_N))
            C.append((0.55, 0.50, 0.45))
            C.append((1.0, 1.0, 1.0))
        I.append((o, o + 1, o + 2))
        I.append((o, o + 2, o + 3))


# ---------------------------------------------------------------- GLB
def write_glb(path, P, UV, C, I, png_path, name):
    pos = np.asarray(P, np.float32).reshape(-1, 3)
    uv = np.asarray(UV, np.float32).reshape(-1, 2)
    col = np.asarray(C, np.float32).reshape(-1, 3)
    idx = np.asarray(I, np.int64).reshape(-1, 3)

    # 平法线（微缩件平着色更像"雕出来的模型"）
    v0, v1, v2 = pos[idx[:, 0]], pos[idx[:, 1]], pos[idx[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    n = n / ln

    np_, nu, nn, ncol, ni = [], [], [], [], []
    off = 0
    for t in range(len(idx)):
        np_.append(v0[t]); np_.append(v1[t]); np_.append(v2[t])
        for v in (0, 1, 2):
            nu.append(uv[idx[t, v]])
            nn.append(n[t])
            ncol.append(col[idx[t, v]])
        ni.extend([off, off + 1, off + 2])
        off += 3

    P2 = np.asarray(np_, np.float32)
    N2 = np.asarray(nn, np.float32)
    U2 = np.asarray(nu, np.float32)
    C2 = np.asarray(ncol, np.float32)
    I2 = np.asarray(ni, np.uint32).reshape(-1, 3)

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

    vp = add(P2, 34962)
    vn = add(N2, 34962)
    vu = add(U2, 34962)
    vc = add(C2, 34962)
    vi = add(I2.reshape(-1), 34963)
    png = open(png_path, 'rb').read()
    while len(blob) % 4:
        blob.append(0)
    ioff = len(blob)
    blob.extend(png)
    views.append({'buffer': 0, 'byteOffset': ioff, 'byteLength': len(png)})
    img_view = len(views) - 1

    gltf = {
        'asset': {'version': '2.0', 'generator': 'rdr2-miniature-v3/1.0'},
        'scene': 0, 'scenes': [{'nodes': [0], 'name': name}],
        'nodes': [{'mesh': 0, 'name': name}],
        'meshes': [{'name': name, 'primitives': [{
            'attributes': {'POSITION': 0, 'NORMAL': 1, 'TEXCOORD_0': 2, 'COLOR_0': 3},
            'indices': 4, 'material': 0, 'mode': 4}]}],
        'materials': [{'name': name + '_mat', 'pbrMetallicRoughness': {
            'baseColorTexture': {'index': 0}, 'metallicFactor': 0.0,
            'roughnessFactor': 0.92}, 'doubleSided': False}],
        'textures': [{'sampler': 0, 'source': 0}],
        'samplers': [{'magFilter': 9729, 'minFilter': 9987,
                      'wrapS': 33071, 'wrapT': 33071}],
        'images': [{'bufferView': img_view, 'mimeType': 'image/png'}],
        'accessors': [
            {'bufferView': vp, 'componentType': 5126, 'count': len(P2), 'type': 'VEC3',
             'min': P2.min(0).tolist(), 'max': P2.max(0).tolist()},
            {'bufferView': vn, 'componentType': 5126, 'count': len(N2), 'type': 'VEC3'},
            {'bufferView': vu, 'componentType': 5126, 'count': len(U2), 'type': 'VEC2'},
            {'bufferView': vc, 'componentType': 5126, 'count': len(C2), 'type': 'VEC3'},
            {'bufferView': vi, 'componentType': 5125, 'count': len(I2.reshape(-1)), 'type': 'SCALAR'},
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
    return len(P2), len(I2)


def build_one(s, ledger, insts, terr, density):
    cx, cy = s['x'], s['y']
    hw, hd = s['w'] / 2, s['d'] / 2
    xs0, xs1 = cx - hw, cx + hw
    ys0, ys1 = cy - hd, cy + hd
    sel = [e for e in insts if abs(e[1] - cx) <= hw and abs(e[2] - cy) <= hd]

    items = []
    for e in sel:
        m = ledger.get(e[0])
        if not m:
            continue
        if is_building(m['name'], m['sz'], m['tris'], m['sx'], m['sy']):
            items.append((e, m, 'b'))
        elif is_keep_prop(m['name'], m['sz']):
            items.append((e, m, 'p'))
    if not items:
        return None

    # 取景框 = 建成区包围盒（外扩 8%），不用官方占地：官方框里一半是空地/河道，
    # 结果就是一坨小房子散在草坪上。缩放仍按 1/29，只是不把空地也做进来。
    bxs = [(e[1], e[2]) for e, _m, _t in items]
    bx0 = min(v[0] for v in bxs); bx1 = max(v[0] for v in bxs)
    by0 = min(v[1] for v in bxs); by1 = max(v[1] for v in bxs)
    padx = max(12.0, (bx1 - bx0) * 0.08)
    pady = max(12.0, (by1 - by0) * 0.08)
    xs0 = max(xs0, bx0 - padx); xs1 = min(xs1, bx1 + padx)
    ys0 = max(ys0, by0 - pady); ys1 = min(ys1, by1 + pady)
    s = dict(s)
    s['w'] = xs1 - xs0
    s['d'] = ys1 - ys0

    med = sorted(terr.smooth(xs0 + (xs1 - xs0) * i / 8, ys0 + (ys1 - ys0) * j / 8)
                 for i in range(9) for j in range(9))[40]

    k = MAP_SCALE
    if max(s['w'], s['d']) * k < MIN_DIM_M:
        k = MIN_DIM_M / max(s['w'], s['d'])
    size_x, size_z = s['w'] * k, s['d'] * k
    ox, oy = (xs0 + xs1) / 2, (ys0 + ys1) / 2

    cells, n_tex = atlas_plan(items)

    # 地标：名字带 church/station/... 的、或体量最大的 40 个，多给面
    def lm_score(it):
        e_, m_, t_ = it
        nm = m_['name'].lower()
        bonus = 1.0
        for kw in ('church', 'station', 'saloon', 'bank', 'hall', 'mansion',
                   'mill', 'jail', 'factory', 'hotel', 'store', 'theatre',
                   'wrh', 'warehouse'):
            if kw in nm:
                bonus = 2.4
                break
        return m_['sx'] * m_['sy'] * max(m_['sz'], 1.0) * bonus
    # 只让"名字明确是地标"的前 8 个用真实网格；其余体块化。
    # 真实网格按面积裁面后是薄壳，40 个一起上会把预算吃光还全是栅栏。
    named = [(e, m, t) for (e, m, t) in items if lm_score((e, m, t)) > 0 and any(
        kw in m['name'].lower() for kw in ('church', 'station', 'saloon', 'bank',
                                           'hall', 'mansion', 'mill', 'jail',
                                           'factory', 'hotel', 'store', 'theatre'))]
    landmark_keys = {(e[0], round(e[1], 1), round(e[2], 1))
                     for e, _m, _t in sorted(named, key=lm_score, reverse=True)[:8]}

    P, UV, C, I = [], [], [], []
    placed = 0
    for (e, m, t) in items:
        q = (e[4], e[5], e[6], e[7])
        sx, sy, sz = abs(e[8]), abs(e[9]), abs(e[10])
        bb = model_bbox(e[0])
        if bb is not None:
            w = (bb[1][0] - bb[0][0]) * sx
            d = (bb[1][1] - bb[0][1]) * sy
            h = (bb[1][2] - bb[0][2]) * sz
        else:
            w, d, h = m['sx'] * sx, m['sy'] * sy, m['sz'] * sz
        area = min(max(w, 7.0), 26.0) * min(max(d, 7.0), 26.0)
        lm = (e[0], round(e[1], 1), round(e[2], 1)) in landmark_keys
        target = int(max(60, min(2400 if lm else 1200,
                                 area * 1.5 * density * (2.2 if lm else 1.0))))

        lx = (e[1] - ox) * k
        lz = -(e[2] - oy) * k
        ly = (e[3] - med) * k

        # 真实网格按面积裁面后会变成"绿色玻璃条"这种鬼东西（薄壳裁面必然出条带），
        # 所以统一走体块；地标靠"加一层塔身"来做出教堂/车站的辨识度。
        geo = None

        if geo is not None:
            gpos, guv, gidx = geo
            base = len(P)
            P.extend(np.stack([lx + gpos[:, 0] * k, ly + gpos[:, 2] * k,
                               lz - gpos[:, 1] * k], axis=1).tolist())
            UV.extend(guv.tolist())
            C.extend([(0.92, 0.92, 0.92)] * len(gpos))
            I.extend((gidx + base).tolist())
        else:
            # 普通房子：真实包围盒 + 坡屋顶的实心块（尺寸夹到"一栋房"的范围）
            tid = model_dominant_tex(e[0])
            ci = cells.get(int(tid), FALLBACK_CELL)
            cx_, cy_ = ci % ATLAS_N, ci // ATLAS_N
            uv_rect = (cx_ / ATLAS_N + 0.002, cy_ / ATLAS_N + 0.002,
                       (cx_ + 1) / ATLAS_N - 0.002, (cy_ + 1) / ATLAS_N - 0.002)
            bw = min(max(w, 7.0), 26.0) * k
            bd = min(max(d, 7.0), 26.0) * k
            bh = min(max(h, 4.0), 13.0) * k
            parts = [(0.0, 0.0, bw, bd, bh)]
            if not lm and ((placed * 2654435761) % 100) < 30:
                # 侧翼：贴着主体的一个小体块，模拟 L 形/带偏房的房子
                aw = bw * 0.55
                ad = bd * 0.55
                ah = bh * 0.82
                if bw >= bd:
                    parts.append((bw * 0.5, bd * 0.12, aw, ad, ah))
                else:
                    parts.append((bw * 0.12, bd * 0.5, aw, ad, ah))
            nm = m['name'].lower()
            if lm and any(k in nm for k in ('church', 'station', 'mill', 'jail', 'factory')):
                # 地标加一座塔（教堂钟楼 / 车站塔楼 / 工厂烟囱），这是"认得出"的关键
                tw = bw * 0.32
                td = bd * 0.32
                th = bh * 1.9 + 0.02
                parts.append((-bw * 0.28, -bd * 0.28, tw, td, th))

            yaw = math.atan2(2 * (e[7] * e[6] + e[4] * e[5]),
                             1 - 2 * (e[5] * e[5] + e[6] * e[6]))
            c, sn = math.cos(yaw), math.sin(yaw)
            for (ox_, oz_, pw, pd, ph) in parts:
                gV, gUV, gC, gT = box_roof(pw, pd, ph, uv_rect)
                x = gV[:, 0] * c - gV[:, 2] * sn
                z = gV[:, 0] * sn + gV[:, 2] * c
                base = len(P)
                P.extend(np.stack([lx + x + ox_ * c - oz_ * sn,
                                   ly + gV[:, 1],
                                   lz + z + ox_ * sn + oz_ * c], axis=1).tolist())
                UV.extend(gUV.tolist())
                C.extend(gC.tolist())
                I.extend((gT + base).tolist())
        placed += 1

    if not P:
        return None

    pn = int(max(8, min(56, round(max(size_x, size_z) / 0.45))))
    add_plinth(P, UV, C, I, terr, xs0, ys0, xs1, ys1, ox, oy, med, k, pn)

    P = np.asarray(P, np.float32)
    P[:, 1] -= P[:, 1].min()
    return {'P': P.tolist(), 'UV': UV, 'I': I, 'k': k,
            'size_x': size_x, 'size_z': size_z,
            'placed': placed, 'n_items': len(items), 'n_tex': n_tex, 'cells': cells,
            'C': C}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--code', default='')
    ap.add_argument('--density', type=float, default=1.0)
    args = ap.parse_args()

    os.makedirs(MODELS, exist_ok=True)
    os.makedirs(TEX, exist_ok=True)
    ledger = load_ledger()
    settles = load_settlements()
    insts = load_instances()
    terr = Terrain()

    rows = []
    for i, s in enumerate(settles):
        if args.code and s['code'] != args.code:
            continue
        cap = TIER_CAP.get(s['btype'], 70000)
        best = None
        density = args.density
        hw, hd = s['w'] / 2, s['d'] / 2
        n_box = len([e for e in insts if abs(e[1] - s['x']) <= hw and abs(e[2] - s['y']) <= hd])
        for attempt in range(4):
            r = build_one(s, ledger, insts, terr, density)
            if r is None:
                break
            n_tri = len(r['I'])
            print(f'   [{s["code"]}] attempt {attempt} density={density:.3f} '
                  f'tris={n_tri:,} cap={cap:,}')
            best = r
            if n_tri <= cap:
                break
            density *= max(0.25, cap / n_tri * 0.9)
        if best is None:
            print('!! 空据点', s['code'])
            continue

        seed = (sum(ord(ch) * (j + 3) for j, ch in enumerate(s['code'])) * 7919 + i * 104729) % 99991
        png = os.path.join(TEX, s['code'] + '.png')
        atlas_build(best['cells'], seed).save(png, optimize=True)
        glb = os.path.join(MODELS, s['code'] + '.glb')
        nv, nt = write_glb(glb, best['P'], best['UV'], best['C'], best['I'], png, s['code'])
        rows.append({
            'code': s['code'], 'name_zh': s['name_zh'], 'btype': s['btype'],
            'size_x': round(best['size_x'], 2), 'size_z': round(best['size_z'], 2),
            'scale': round(best['k'], 5), 'scale_boost': round(best['k'] / MAP_SCALE, 2),
            'tris': nt, 'verts': nv, 'n_tex': best['n_tex'],
            'n_inst_in_box': n_box,
            'n_items': best['n_items'], 'n_placed': best['placed'], 'n_skipped': 0,
            'tex': s['code'] + '.png', 'tex_kb': round(os.path.getsize(png) / 1024, 1),
            'glb_kb': round(os.path.getsize(glb) / 1024, 1),
            'landmark1': '', 'landmark1_kind': '', 'landmark2': '', 'landmark2_kind': '',
            'landmark3': '', 'landmark3_kind': '',
            'world_x': s['x'], 'world_y': s['y'],
            'bbox_w': s['w'], 'bbox_d': s['d'],
        })
        print(f"{s['code']:7} {s['name_zh'][:10]:11} {best['size_x']:5.1f}x{best['size_z']:5.1f} m "
              f"tris {nt:7,d} 贴图 {best['n_tex']:2d} 放置 {best['placed']:4d}/{best['n_items']:4d} "
              f"glb {rows[-1]['glb_kb']:.0f} KB")

    if rows and not args.code:
        with open(os.path.join(OUT, 'audit.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        json.dump(rows, open(os.path.join(OUT, 'audit.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        t = sum(r['tris'] for r in rows)
        print(f"\n{len(rows)} 个据点 · 合计 {t:,} 面 · 平均 {t // max(1, len(rows)):,} · "
              f"最大 {max(r['tris'] for r in rows):,}")


if __name__ == '__main__':
    main()
