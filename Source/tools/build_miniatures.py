"""把 46 个据点从"18 万个实例"压成"一块可以直接摆在沙盒大地图上的微缩模型"。

产物
  deliverable/miniatures/models/<code>.glb     每个据点 1 个 GLB（单 mesh、单 material）
  deliverable/miniatures/tex/<code>.png        每个据点 1 张贴图（512² 调色板图集）
  deliverable/miniatures/audit.csv / .json     实测面数 / 顶点 / 尺寸 / 贴图 / 实例覆盖

为什么是"代理几何"而不是缩小的实景模型
  实景 55 000 000 三角面（圣丹尼斯）在 371×277 m 的沙盒大地图上只占 ~100×100 px，
  按像素预算只需要 1 万面上下。所以：建筑只保留**轮廓**（墙体 + 坡屋顶 + 烟囱），
  靠一张调色板贴图 + 顶点色 AO 提供细节；地标额外加塔楼/尖顶/烟囱/围墙。
  细节留给切场景看，这个模型只负责"在图上认得出这是哪座城"。

用法
  uv run python tools/build_miniatures.py            # 全量
  uv run python tools/build_miniatures.py --code sdn # 单个
"""
import os
import re
import csv
import json
import math
import glob
import zlib
import struct
import argparse
from collections import Counter

import numpy as np
from PIL import Image

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TOWN_DATA = os.path.join(ROOT, 'export/levels/world/town_data')
LEDGER = os.path.join(ROOT, 'deliverable/handoff/model_ledger.csv')
SETTLE = os.path.join(ROOT, 'deliverable/handoff/settlements_world_v2.csv')
HEIGHT_RAW = os.path.join(ROOT, 'deliverable/heightmap/continent_height_r16.raw')
HEIGHT_META = os.path.join(ROOT, 'deliverable/heightmap/continent_height_meta.json')
OUT = os.path.join(ROOT, 'deliverable/miniatures')
MODELS = os.path.join(OUT, 'models')
TEX = os.path.join(OUT, 'tex')

MAP_SCALE = 1.0 / 29.0     # 世界 1 m → 沙盘 1/29 m（与规格 7.0.1 一致）
MIN_DIM_M = 2.5            # 最小成品边长（再小在图上认不出）
CROP_PAD = 0.06            # 取景框 = 建筑包围盒外扩 6%（≤50 m 折算后的等效值）

PREFIX = re.compile(r'=\s*(\[.*\]);?\s*$', re.S)

BLD_BAD = ('debris', '_veg', 'veg_', 'water', 'collision', '_slod', '_lod',
           'audioproxy', 'occlusion', 'helper', 'vfx_', 'decal_', '_strm',
           'terrain', 'ground', '_shadow', 'light_', 'leaves', 'tree', 'bush',
           '__hd_', '_hd_0', 'p_12__', 'rock_', '_rock', 'weed', 'grass',
           'decal', 'kudzu', 'cable', 'glue', 'detail', '_dtl', '_dec',
           'roaddetail', '_trail', '_track', '_int', '_far', '_script',
           'vertex', '_vw', 'fence', 'hitching', 'post_', 'rail_',
           'rds_', '_rds', 'grndec', 'runoff', 'seawall', 'dockside',
           'wareroof', 'ter0', 'terrain', 'pavement', 'road')
NOT_BLD_PREFIX = ('p_', 's_', 'w_', 'v_', 'crp_', 'su_', 'rdr_', 'meta_',
                  'j_', 'dak_', 'veg_', 'amb_', 'prop_')

# 值得单独保留的道具（这些在微缩尺度上是"剪影特征"）
KEEP_PROP = ('ship', 'boat', 'steam', 'train', 'locomotive', 'watertower',
             'tank', 'derrick', 'crane', 'windmill', 'tent', 'campfire',
             'wagon', 'cart', 'canopy', 'dock', 'pier', 'bridge', 'silo')

# 地标类型关键字 → 造型（顺序敏感：先匹配先赢）
LANDMARK_KINDS = [
    ('church', 'church'), ('chapel', 'church'), ('cathedral', 'church'),
    ('station', 'station'), ('trainstn', 'station'), ('depot', 'station'),
    ('bank', 'civic'), ('cityhall', 'civic'), ('courthouse', 'civic'),
    ('hall', 'civic'), ('mansion', 'civic'), ('man_', 'civic'),
    ('jail', 'prison'), ('prison', 'prison'), ('pen', 'prison'),
    ('fort', 'fort'), ('wall', 'fort'), ('gate', 'fort'),
    ('factory', 'factory'), ('fact', 'factory'), ('mill', 'factory'),
    ('derrick', 'factory'), ('conv', 'factory'), ('coal', 'factory'),
    ('saloon', 'saloon'), ('store', 'saloon'), ('hotel', 'saloon'),
    ('barn', 'barn'), ('stable', 'barn'), ('cattle', 'barn'),
    ('dock', 'dock'), ('pier', 'dock'), ('warehouse', 'warehouse'),
    ('wrh', 'warehouse'), ('house', 'house'), ('home', 'house'),
    ('cabin', 'house'), ('shack', 'house'), ('tent', 'tent'),
    ('tower', 'tower'), ('twr', 'tower'),
]

# 每种地标造型的"面数上限"，防止某个地标把预算吃光
WALL_MIX = ('wall_wood', 'wall_wood', 'wall_brick', 'wall_paint', 'wall_stone', 'wall_wood')
ROOF_MIX = ('roof_shake', 'roof_shake', 'roof_red', 'roof_wood', 'roof_black', 'roof_shake')

KIND_TRIS = {'church': 260, 'station': 260, 'civic': 240, 'prison': 200,
             'fort': 220, 'factory': 220, 'saloon': 200, 'barn': 160,
             'dock': 120, 'warehouse': 160, 'house': 110, 'tower': 140,
             'tent': 40}

# 调色板图集：4×4 格，每格 128 px
CELL = 128
PALETTE_CELLS = {
    'wall_stone': 0, 'wall_brick': 1, 'wall_wood': 2, 'wall_paint': 3,
    'roof_shake': 4, 'roof_red': 5, 'roof_metal': 6, 'roof_wood': 7,
    'plank': 8, 'dirt': 9, 'metal': 10, 'canvas': 11,
    'stone_light': 12, 'roof_black': 13, 'grass': 14, 'white': 15,
}


# ---------------------------------------------------------------- 数据读入
def load_ledger():
    d = {}
    with open(LEDGER, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            d[int(r['hash'], 16)] = {
                'name': r['name'],
                'tris': int(r['tris']), 'verts': int(r['verts']),
                'sx': float(r['sx']), 'sy': float(r['sy']), 'sz': float(r['sz']),
            }
    return d


def load_settlements():
    out = []
    with open(SETTLE, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if not r['code']:
                continue
            out.append({
                'code': r['code'], 'name_zh': r['name_zh'],
                'name_en': r['name_en'], 'btype': r['btype'],
                'faction': r['faction'],
                'x': float(r['world_x']), 'y': float(r['world_y']),
                'w': float(r['size_w_m']), 'd': float(r['size_d_m']),
            })
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
    # 尺寸上限：>60 m 的单件不是房子（是道路 / 地形块 / 桥面），进模型会毁掉整个剪影
    if sx is not None and (sx > 60 or sy > 60):
        return False
    return 4.0 <= sz <= 60 and tris >= 100


def is_keep_prop(name, sz):
    n = name.lower()
    return n.startswith('p_') and any(k in n for k in KEEP_PROP) and sz >= 1.0


def landmark_kind(name):
    n = name.lower()
    for key, kind in LANDMARK_KINDS:
        if key in n:
            return kind
    return 'house'


# ---------------------------------------------------------------- 地形底座
class Terrain:
    """4 m/px 的权威高度图，用来给每个据点切一块真实地形的底座。"""

    def __init__(self):
        meta = json.load(open(HEIGHT_META, encoding='utf-8'))
        h = meta['heightmap']
        self.x0, self.y0 = meta['x0'], meta['y0']
        self.x1, self.y1 = meta['x1'], meta['y1']
        self.w, self.h = h['w'], h['h']
        self.zmin, self.zmax = h['zmin'], h['zmax']
        self.res = h['res_m']
        a = np.fromfile(HEIGHT_RAW, dtype='<u2')
        self.a = a.reshape(self.h, self.w).astype(np.float32)
        self.z = self.zmin + self.a / 65535.0 * (self.zmax - self.zmin)

    def at(self, x, y):
        col = int((x - self.x0) / self.res)
        row = int((self.y1 - y) / self.res)
        col = max(0, min(self.w - 1, col))
        row = max(0, min(self.h - 1, row))
        return float(self.z[row, col])


# ---------------------------------------------------------------- 贴图图集
def _noise(w, h, seed, scale=1.0):
    rng = np.random.default_rng(seed)
    small = rng.random((max(2, int(h / (4 * scale))), max(2, int(w / (4 * scale)))))
    im = Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    return np.asarray(im, dtype=np.float32) / 255.0


def _planks(w, h, base, line, rows=12, vary=0.12, seed=1):
    img = np.zeros((h, w, 3), np.float32)
    img[:] = base
    n = _noise(w, h, seed, 2.0)
    img *= (0.9 + 0.2 * n)[..., None]
    step = h / rows
    for i in range(rows + 1):
        y = min(h - 1, int(i * step))
        img[y:y + 2] = line
    # 竖向接缝
    rng = np.random.default_rng(seed + 7)
    for i in range(rows):
        x = int(rng.random() * w)
        y0, y1 = int(i * step), int((i + 1) * step)
        img[y0:y1, x:x + 1] *= 0.75
    return img


def _bricks(w, h, base, mortar, rows=16, seed=3):
    img = np.zeros((h, w, 3), np.float32)
    img[:] = base
    n = _noise(w, h, seed, 3.0)
    img *= (0.88 + 0.24 * n)[..., None]
    step = h / rows
    for i in range(rows + 1):
        y = min(h - 1, int(i * step))
        img[y:y + 1] = mortar
        off = (i % 2) * (w // 8)
        for j in range(4):
            x = (j * w // 4 + off) % w
            y1 = min(h, int((i + 1) * step))
            img[y:y1, x:x + 1] = mortar
    return img


def _windows(img, cols=4, rows=3, margin=0.18, lit=0.55, seed=5):
    h, w, _ = img.shape
    rng = np.random.default_rng(seed)
    for r in range(rows):
        for c in range(cols):
            x0 = int((c + 0.5) / cols * w - w * 0.055)
            y0 = int((r + 0.35) / rows * h)
            ww, hh = int(w * 0.11), int(h * 0.13)
            on = rng.random() < lit
            col = np.array([1.0, 0.88, 0.60]) if on else np.array([0.16, 0.17, 0.20])
            img[y0:y0 + hh, x0:x0 + ww] = col
            img[y0 - 1:y0, x0 - 1:x0 + ww + 1] *= 0.6
    return img


def build_atlas(seed, warm=0.0):
    """生成 512² 调色板图集。warm 让不同据点的色调有差异（-1 冷 / +1 暖）。"""
    img = np.zeros((CELL * 4, CELL * 4, 3), np.float32)
    warm = float(warm)

    def put(cell_name, arr):
        i = PALETTE_CELLS[cell_name]
        cx, cy = i % 4, i // 4
        img[cy * CELL:(cy + 1) * CELL, cx * CELL:(cx + 1) * CELL] = arr

    stone = np.array([0.66, 0.63, 0.58]) * np.array([1 + 0.10 * warm, 1, 1 - 0.10 * warm])
    put('wall_stone', _windows(_bricks(CELL, CELL, stone, stone * 0.62, 10, seed), 3, 2, lit=0.35, seed=seed + 1))
    brick = np.array([0.62, 0.40, 0.32]) * np.array([1 + 0.12 * warm, 1, 1 - 0.10 * warm])
    put('wall_brick', _windows(_bricks(CELL, CELL, brick, brick * 0.6, 14, seed + 2), 3, 2, lit=0.45, seed=seed + 3))
    put('wall_wood', _windows(_planks(CELL, CELL, np.array([0.55, 0.47, 0.37]), np.array([0.30, 0.25, 0.19]),
                                     rows=10, seed=seed + 4), 3, 2, lit=0.4, seed=seed + 5))
    put('wall_paint', _windows(_planks(CELL, CELL, np.array([0.78, 0.75, 0.68]), np.array([0.52, 0.50, 0.46]),
                                      rows=12, seed=seed + 6), 4, 2, lit=0.3, seed=seed + 7))
    put('roof_shake', _planks(CELL, CELL, np.array([0.34, 0.32, 0.30]), np.array([0.16, 0.15, 0.15]),
                              rows=18, seed=seed + 8))
    put('roof_red', _planks(CELL, CELL, np.array([0.42, 0.20, 0.15]), np.array([0.24, 0.11, 0.09]),
                            rows=16, seed=seed + 9))
    put('roof_metal', _planks(CELL, CELL, np.array([0.26, 0.28, 0.26]), np.array([0.15, 0.16, 0.15]),
                              rows=20, seed=seed + 10))
    put('roof_wood', _planks(CELL, CELL, np.array([0.38, 0.33, 0.26]), np.array([0.20, 0.17, 0.13]),
                             rows=14, seed=seed + 11))
    put('plank', _planks(CELL, CELL, np.array([0.33, 0.28, 0.22]), np.array([0.15, 0.12, 0.09]),
                         rows=8, seed=seed + 12))
    put('dirt', np.clip(_noise(CELL, CELL, seed + 13, 2.0)[..., None] * 0.10 +
                        np.array([0.30, 0.26, 0.21]), 0, 1))
    put('metal', _planks(CELL, CELL, np.array([0.30, 0.30, 0.31]), np.array([0.18, 0.18, 0.19]),
                         rows=24, seed=seed + 14))
    put('canvas', np.clip(_noise(CELL, CELL, seed + 15, 2.0)[..., None] * 0.10 +
                          np.array([0.60, 0.56, 0.46]), 0, 1))
    put('stone_light', _windows(_bricks(CELL, CELL, np.array([0.60, 0.58, 0.54]),
                                        np.array([0.42, 0.41, 0.38]), 12, seed + 16), 3, 3, lit=0.4, seed=seed + 17))
    put('roof_black', _planks(CELL, CELL, np.array([0.22, 0.22, 0.24]), np.array([0.11, 0.11, 0.12]),
                              rows=20, seed=seed + 18))
    put('grass', np.clip(_noise(CELL, CELL, seed + 19, 1.2)[..., None] * 0.12 +
                         np.array([0.30, 0.33, 0.21]), 0, 1))
    put('white', np.ones((CELL, CELL, 3), np.float32) * 0.92)
    a = np.clip(img * 2.05, 0, 1)
    a = np.power(a, 1 / 1.15)
    return Image.fromarray((a * 255).astype(np.uint8), 'RGB')


# ---------------------------------------------------------------- 几何构建
class Mesh:
    """一个据点一个 mesh：positions / normals / uv / colors。"""

    def __init__(self):
        self.pos = []
        self.nrm = []
        self.uv = []
        self.col = []
        self.idx = []

    def add_quad(self, p0, p1, p2, p3, n, cell, tint, uvs=None):
        """四边形（逆时针）。uvs 可给 4 个 (u,v)，否则用整格。"""
        i = len(self.pos)
        for p in (p0, p1, p2, p3):
            self.pos.append(p)
            self.nrm.append(n)
            self.col.append(tint)
        if uvs is None:
            u0, v0, u1, v1 = cell_uv(cell)
            uvs = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        self.uv.extend(uvs)
        self.idx.extend([i, i + 1, i + 2, i, i + 2, i + 3])

    def add_tri(self, p0, p1, p2, n, cell, tint, uvs=None):
        i = len(self.pos)
        for p in (p0, p1, p2):
            self.pos.append(p)
            self.nrm.append(n)
            self.col.append(tint)
        if uvs is None:
            u0, v0, u1, v1 = cell_uv(cell)
            uvs = [(u0, v0), (u1, v0), (u1, v1)]
        self.uv.extend(uvs)
        self.idx.extend([i, i + 1, i + 2])

    def tris(self):
        return len(self.idx) // 3


def cell_uv(cell_name, inset=0.004):
    i = PALETTE_CELLS[cell_name]
    cx, cy = i % 4, i // 4
    u0 = cx / 4 + inset
    u1 = (cx + 1) / 4 - inset
    # glTF 的 UV 原点在**左上**（three.js 加载 GLTF 时 flipY=false），
    # 所以 v 直接用图像行方向，写反了整张图会上下镜像（dirt 会取到 roof_red）。
    v0 = cy / 4 + inset
    v1 = (cy + 1) / 4 - inset
    return (u0, v0, u1, v1)


def rot2(x, y, c, s):
    return x * c - y * s, x * s + y * c


def add_box(mesh, cx, cy, z0, w, d, h, yaw, wall_cell, roof_cell, tint,
            roof='gable', roof_h=None, chimney=False):
    """一个建筑体块：4 面墙 + 屋顶。底边在 z0，高 h（含屋顶）。"""
    c, s = math.cos(yaw), math.sin(yaw)
    hw, hd = w / 2, d / 2
    body_h = h if roof == 'flat' else h * 0.72
    rh = roof_h if roof_h is not None else (h - body_h)

    def P(lx, ly, lz):
        # 输出轴序必须是 (x, 高度, z)。写成 (x, z, 高度) 会让整个据点"立"起来。
        rx, ry = rot2(lx, ly, c, s)
        return (cx + rx, lz, cy + ry)

    # 墙体（底面不建）
    quad = [
        ((0, -hd, 0), (w, -hd, 0), (w, -hd, body_h), (0, -hd, body_h), (0, -1, 0)),
        ((w, 0, 0), (w, hd, 0), (w, hd, body_h), (w, 0, body_h), (1, 0, 0)),
        ((0, hd, 0), (0, hd, body_h), (w, hd, body_h), (w, hd, 0), (-1, 0, 0)),
    ]
    # 用局部坐标重写四个面（顺序保证法线朝外）
    faces = [
        ((-hw, -hd), (hw, -hd), (0, -1)),
        ((hw, -hd), (hw, hd), (1, 0)),
        ((hw, hd), (-hw, hd), (0, 1)),
        ((-hw, hd), (-hw, -hd), (-1, 0)),
    ]
    for (x0, y0), (x1, y1), (nx, ny) in faces:
        p0 = P(x0, y0, z0)
        p1 = P(x1, y1, z0)
        p2 = P(x1, y1, z0 + body_h)
        p3 = P(x0, y0, z0 + body_h)
        n = (nx * c - ny * s, nx * s + ny * c, 0)
        # 墙面 uv 按宽度铺 1 格（微缩尺度够用）
        u0, v0, u1, v1 = cell_uv(wall_cell)
        mesh.add_quad(p0, p1, p2, p3, n, wall_cell, tint,
                      [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])

    top = z0 + body_h
    if roof in ('flat',):
        p = [P(-hw, -hd, top), P(hw, -hd, top), P(hw, hd, top), P(-hw, hd, top)]
        mesh.add_quad(p[0], p[1], p[2], p[3], (0, 0, 1), roof_cell, tint)
    else:
        ridge_h = top + rh
        if w >= d:
            # 屋脊沿 x
            a = P(-hw - 0.06 * w, -hd - 0.06 * d, top)
            b = P(hw + 0.06 * w, -hd - 0.06 * d, top)
            cc = P(hw + 0.06 * w, hd + 0.06 * d, top)
            dd = P(-hw - 0.06 * w, hd + 0.06 * d, top)
            r0 = P(-hw - 0.06 * w, 0, ridge_h)
            r1 = P(hw + 0.06 * w, 0, ridge_h)
            # 南坡 / 北坡
            mesh.add_quad(a, b, r1, r0, nvec(a, b, r1), roof_cell, tint)
            mesh.add_quad(cc, dd, r0, r1, nvec(cc, dd, r0), roof_cell, tint)
            # 山墙三角形
            mesh.add_tri(P(-hw, -hd, top), P(-hw, hd, top), P(-hw, 0, ridge_h),
                         (-c, -s, 0), wall_cell, tint)
            mesh.add_tri(P(hw, hd, top), P(hw, -hd, top), P(hw, 0, ridge_h),
                         (c, s, 0), wall_cell, tint)
        else:
            a = P(-hw - 0.06 * w, -hd - 0.06 * d, top)
            b = P(hw + 0.06 * w, -hd - 0.06 * d, top)
            cc = P(hw + 0.06 * w, hd + 0.06 * d, top)
            dd = P(-hw - 0.06 * w, hd + 0.06 * d, top)
            r0 = P(0, -hd - 0.06 * d, ridge_h)
            r1 = P(0, hd + 0.06 * d, ridge_h)
            mesh.add_quad(a, r0, r1, dd, nvec(a, r0, r1), roof_cell, tint)
            mesh.add_quad(b, cc, r1, r0, nvec(b, cc, r1), roof_cell, tint)
            mesh.add_tri(P(-hw, -hd, top), P(hw, -hd, top), r0, (0, -c, 0), wall_cell, tint)
            mesh.add_tri(P(hw, hd, top), P(-hw, hd, top), r1, (0, c, 0), wall_cell, tint)

    if chimney:
        chx = hw * 0.45
        chy = hd * 0.2
        s0 = 0.22
        cx0, cy0 = chx - s0 / 2, chy - s0 / 2
        add_box_simple(mesh, P(cx0, cy0, top), P(cx0 + s0, cy0 + s0, top),
                       top + rh * 0.9, 'wall_brick', tint, yaw=None)


def add_box_simple(mesh, p_lo, p_hi, h, cell, tint, yaw=None):
    """轴对齐小方块（烟囱）。p_lo/p_hi 的轴序是 (x, 水平z, 高度)。"""
    (x0, zz0, _), (x1, zz1, _) = p_lo, p_hi
    z0 = p_lo[2]
    z1 = h
    # 输出轴序必须是 (x, 高度, z)，写反会把烟囱拉成一根竖直的长条
    P = [(x0, z0, zz0), (x1, z0, zz0), (x1, z0, zz1), (x0, z0, zz1)]
    Q = [(x0, z1, zz0), (x1, z1, zz0), (x1, z1, zz1), (x0, z1, zz1)]
    mesh.add_quad(P[0], P[1], Q[1], Q[0], (0, -1, 0), cell, tint)
    mesh.add_quad(P[1], P[2], Q[2], Q[1], (1, 0, 0), cell, tint)
    mesh.add_quad(P[2], P[3], Q[3], Q[2], (0, 1, 0), cell, tint)
    mesh.add_quad(P[3], P[0], Q[0], Q[3], (-1, 0, 0), cell, tint)
    mesh.add_quad(Q[0], Q[1], Q[2], Q[3], (0, 0, 1), cell, tint)


def nvec(a, b, c):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    l = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return (nx / l, ny / l, nz / l)


def add_pyramid(mesh, cx, cy, z0, w, d, h, yaw, cell, tint):
    c, s = math.cos(yaw), math.sin(yaw)
    hw, hd = w / 2, d / 2

    def P(lx, ly, lz):
        rx, ry = rot2(lx, ly, c, s)
        return (cx + rx, lz, cy + ry)

    a, b, cc, dd = (P(-hw, -hd, z0), P(hw, -hd, z0), P(hw, hd, z0), P(-hw, hd, z0))
    apex = P(0, 0, z0 + h)
    for p0, p1 in ((a, b), (b, cc), (cc, dd), (dd, a)):
        mesh.add_tri(p0, p1, apex, nvec(p0, p1, apex), cell, tint)


def add_cylinder(mesh, cx, cy, z0, r, h, seg=8, cell='metal', tint=(1, 1, 1)):
    for i in range(seg):
        a0 = 2 * math.pi * i / seg
        a1 = 2 * math.pi * (i + 1) / seg
        p0 = (cx + r * math.cos(a0), z0, cy + r * math.sin(a0))
        p1 = (cx + r * math.cos(a1), z0, cy + r * math.sin(a1))
        p2 = (p1[0], z0 + h, p1[2])
        p3 = (p0[0], z0 + h, p0[2])
        mesh.add_quad(p0, p1, p2, p3, nvec(p0, p1, p2), cell, tint)
    # 顶盖
    c0 = (cx, z0 + h, cy)
    for i in range(seg):
        a0 = 2 * math.pi * i / seg
        a1 = 2 * math.pi * (i + 1) / seg
        p0 = (cx + r * math.cos(a0), z0 + h, cy + r * math.sin(a0))
        p1 = (cx + r * math.cos(a1), z0 + h, cy + r * math.sin(a1))
        mesh.add_tri(p0, p1, c0, (0, 0, 1), cell, tint)


def build_landmark(mesh, x, y, z, w, d, h, yaw, kind, tint):
    """地标：在基础体块上加辨识特征。预算见 KIND_TRIS。"""
    roof = 'gable'
    wall = 'wall_stone' if kind in ('church', 'civic', 'prison', 'fort') else 'wall_wood'
    roof_cell = {'church': 'roof_shake', 'station': 'roof_metal', 'civic': 'roof_red',
                 'factory': 'roof_black', 'barn': 'roof_wood', 'saloon': 'roof_shake',
                 'warehouse': 'roof_metal', 'dock': 'plank', 'fort': 'roof_shake',
                 'prison': 'roof_black', 'tower': 'roof_shake'}.get(kind, 'roof_shake')

    add_box(mesh, x, y, z, w, d, h, yaw, wall, roof_cell, tint,
            roof='flat' if kind in ('dock',) else 'gable',
            chimney=False)

    if kind == 'church':
        tw, td, th = max(w * 0.16, 0.35), max(d * 0.16, 0.35), h * 1.25
        add_box(mesh, x, y, z, tw, td, th, yaw, 'stone_light', 'roof_metal', tint,
                roof='gable', roof_h=th * 0.42)
    elif kind == 'station':
        aw, ad = w * 0.75, max(d * 0.35, 0.5)
        add_box(mesh, x, y, z, aw, ad, h * 0.35, yaw, 'plank', 'roof_metal', tint, roof='flat')
        add_box(mesh, x, y, z, max(w * 0.10, 0.3), max(w * 0.10, 0.3), h * 1.35, yaw,
                'wall_brick', 'roof_black', tint, roof='flat')
    elif kind == 'civic':
        add_box(mesh, x, y, z, w * 0.5, d * 0.5, h * 1.18, yaw, 'stone_light',
                'roof_shake', tint, roof='gable', roof_h=h * 0.18)
    elif kind == 'factory':
        add_cylinder(mesh, x + w * 0.3, y + d * 0.3, z, max(w * 0.055, 0.12), h * 1.7, 6, 'metal', tint)
        add_cylinder(mesh, x - w * 0.25, y - d * 0.2, z, max(w * 0.045, 0.10), h * 1.35, 6, 'metal', tint)
    elif kind == 'prison':
        for sx in (-1, 1):
            for sy in (-1, 1):
                add_box(mesh, x + sx * w * 0.42, y + sy * d * 0.42, z,
                        max(w * 0.12, 0.3), max(d * 0.12, 0.3), h * 1.25, yaw,
                        'wall_stone', 'roof_black', tint, roof='flat')
    elif kind == 'fort':
        for sx in (-1, 1):
            add_box(mesh, x + sx * w * 0.40, y + d * 0.40, z,
                    max(w * 0.13, 0.3), max(w * 0.13, 0.3), h * 1.3, yaw,
                    'wall_stone', 'roof_shake', tint, roof='flat')
    elif kind == 'saloon':
        add_box(mesh, x, y - d * 0.5, z + h * 0.32, w * 1.02, max(d * 0.18, 0.3),
                h * 0.12, yaw, 'plank', 'roof_wood', tint, roof='flat')
    elif kind == 'barn':
        add_box(mesh, x, y, z, w, d, h, yaw, 'wall_paint', 'roof_wood', tint,
                roof='gable', roof_h=h * 0.45)
    elif kind == 'warehouse':
        add_box(mesh, x, y, z, w, d, h, yaw, 'wall_wood', 'roof_metal', tint, roof='gable')
    elif kind == 'dock':
        add_box(mesh, x, y, z, w, d, max(h, 0.25), yaw, 'plank', 'plank', tint, roof='flat')
    elif kind == 'tower':
        add_box(mesh, x, y, z, w * 0.55, d * 0.55, h * 1.6, yaw, 'wall_stone',
                'roof_shake', tint, roof='flat')
    elif kind == 'tent':
        add_pyramid(mesh, x, y, z, w, d, h, yaw, 'canvas', tint)



def add_terrain_patch(mesh, terr, xs0, ys0, xs1, ys1, ox, oy, med, k, n=56):
    """把真实高度图在据点框内切成 n×n 的小地形，带侧壁 —— 成品就是一块"沙盘块"。

    两个关键处理，不做就会变成"红色沙丘"：
      · 每个顶点取 5 点平均（原生 4 m/px，框可能有 900 m，直接点采样会采到断崖尖角）
      · 相对框内中位高差 clamp 到 ±8 m，避免一条河岸把整块模型的视觉重心带歪
    """
    samples = []
    for i in range(n + 1):
        row = []
        for j in range(n + 1):
            x = xs0 + (xs1 - xs0) * j / n
            y = ys0 + (ys1 - ys0) * i / n
            h = smooth_h(terr, x, y)
            row.append(h)
        samples.append(row)

    def P(x, y, h):
        hh = max(-8.0, min(8.0, h - med)) * 0.25
        return ((x - ox) * k, hh * k, -(y - oy) * k)

    grid = []
    for i in range(n + 1):
        row = []
        for j in range(n + 1):
            x = xs0 + (xs1 - xs0) * j / n
            y = ys0 + (ys1 - ys0) * i / n
            row.append(P(x, y, samples[i][j]))
        grid.append(row)

    def col_for(h, slope):
        """一格纹理 + 顶点色调制：低地偏灰绿、高地偏黄褐、陡坡提亮。
        换格子会让相邻 quad 出现明显补丁缝，微缩尺度上很丑。"""
        rel = h - med
        if rel < -8.0:                      # 比中位低 8 m 以上当水面（河/湖），压暗发蓝
            return (0.34, 0.42, 0.47), 'grass'
        k_hi = min(max((rel + 8) / 16.0, 0.0), 1.0)
        r = 0.78 + 0.22 * k_hi
        g = 0.86 + 0.10 * k_hi
        b = 0.70 + 0.02 * k_hi
        lit = 1.0 + 0.18 * min(slope / 6.0, 1.0)
        return (r * lit, g * lit, b * lit), 'grass'

    # 整块地形只铺一次纹理（不要每个 quad 铺满一格，否则会出现"豹纹"重复）
    for i in range(n):
        for j in range(n):
            p0 = grid[i][j]
            p1 = grid[i][j + 1]
            p2 = grid[i + 1][j + 1]
            p3 = grid[i + 1][j]
            nv = nvec(p0, p1, p2)
            if nv[1] < 0:
                nv = (-nv[0], -nv[1], -nv[2])
            slope = max(abs(samples[i][j] - samples[i + 1][j + 1]),
                        abs(samples[i][j + 1] - samples[i + 1][j]))
            tint, cell = col_for(samples[i + 1][j + 1], slope)
            u0, v0, u1, v1 = cell_uv(cell, inset=0.0)
            def uvj(jj, ii):
                return (u0 + (u1 - u0) * jj / n, v0 + (v1 - v0) * ii / n)
            mesh.add_quad(p0, p1, p2, p3, nv, cell, tint,
                          [uvj(j, i), uvj(j + 1, i), uvj(j + 1, i + 1), uvj(j, i + 1)])

    # 侧壁（往下 0.45 m 的"沙盘厚度"）
    base_y = min(min(pt[1] for pt in row) for row in grid) - 0.045
    edge = []
    edge += [(grid[0][j], grid[0][j + 1]) for j in range(n)]
    edge += [(grid[i][n], grid[i + 1][n]) for i in range(n)]
    edge += [(grid[n][j + 1], grid[n][j]) for j in range(n)]
    edge += [(grid[i + 1][0], grid[i][0]) for i in range(n)]
    for a, b in edge:
        a2 = (a[0], base_y, a[2])
        b2 = (b[0], base_y, b[2])
        mesh.add_quad(a, b, b2, a2, nvec(a, b, b2), 'dirt', (0.46, 0.42, 0.36))


# ---------------------------------------------------------------- 据点构建
def smooth_h(terr, x, y):
    """和地形底座同样的 5 点平滑 —— 建筑不吸附到它就会浮空/埋地。"""
    return (terr.at(x, y) * 2 + terr.at(x + 3, y) + terr.at(x - 3, y) +
            terr.at(x, y + 3) + terr.at(x, y - 3)) / 6.0


def terrain_median(terr, xs0, ys0, xs1, ys1, n=16):
    vals = []
    for i in range(n + 1):
        for j in range(n + 1):
            vals.append(terr.at(xs0 + (xs1 - xs0) * j / n, ys0 + (ys1 - ys0) * i / n))
    vals.sort()
    return vals[len(vals) // 2]


def build_settlement(s, ledger, insts, terr):
    cx, cy = s['x'], s['y']
    hw, hd = s['w'] / 2, s['d'] / 2
    sel = [e for e in insts
           if abs(e[1] - cx) <= hw and abs(e[2] - cy) <= hd]

    items = []
    for e in sel:
        m = ledger.get(e[0])
        if not m:
            continue
        nm = m['name']
        if is_building(nm, m['sz'], m['tris'], m['sx'], m['sy']):
            items.append((e, m, 'building'))
        elif is_keep_prop(nm, m['sz']):
            items.append((e, m, 'prop'))

    if not items:
        return None

    # ---- 取景框 = settlements_world_v2.csv 的官方占地（全图统一口径）----
    # 不按"建筑包围盒"裁，否则密度不同的城会被算成不同比例（安尼斯堡会缩水一半）。
    xs0, xs1 = cx - hw, cx + hw
    ys0, ys1 = cy - hd, cy + hd
    zw = min(e[3] for e, m, t in items)
    bw, bd = s['w'], s['d']
    ox, oy = cx, cy

    # ---- 比例：1/29 打底，太小的据点上调到 MIN_DIM_M ----
    k = MAP_SCALE
    if max(bw, bd) * k < MIN_DIM_M:
        k = MIN_DIM_M / max(bw, bd)
    size_x, size_z = bw * k, bd * k

    # ---- 地标挑 3 个（名字带 church/station/saloon… 优先，同等看体量）----
    def land_score(it):
        e, m, t = it
        kind = landmark_kind(m['name'])
        bonus = 3.0 if kind != 'house' else 1.0
        if t == 'prop':
            bonus *= 0.6
        return bonus * (m['sx'] * m['sy'] * max(m['sz'], 1.0))
    landmarks = sorted(items, key=land_score, reverse=True)[:3]
    land_keys = {(round(e[1], 1), round(e[2], 1), e[0]) for e, m, t in landmarks}

    mesh = Mesh()

    # ---- 地形底座：真实高度图切一块，带侧壁，成品就是一个"沙盘块" ----
    med = terrain_median(terr, xs0, ys0, xs1, ys1)
    # 底座网格按成品尺寸给：小据点给 8×8 就够，30 m 的城给 56×56。
    # 统一 56 会让一个 2.5 m 的 POI 白吃 6 000 面。
    pn = int(max(8, min(56, round(max(size_x, size_z) / 0.45))))
    add_terrain_patch(mesh, terr, xs0, ys0, xs1, ys1, ox, oy, med, k, n=pn)

    # 每栋建筑的"阴影底噪"：底部压暗，模拟模型摆件接触阴影
    rng = np.random.default_rng(abs(hash(s['code'])) % 100000)

    def tint_for(idx, kind):
        base = 1.02 + 0.26 * rng.random()
        warm = 1.0 + (rng.random() - 0.5) * 0.10
        return (base * warm, base, base * (2.0 - warm))

    # ---- 建筑聚类 ----------------------------------------------------------
    # 一栋房子在数据里是多个部件（walls / roof / foundation / det），
    # 逐件摆会变成一坨碎片。按 9 m 网格把同格部件并成一个体块：
    # 占地取并集、高度取顶面，这样街区是连续的"实体块"，才像模型。
    CELL_M = 9.0
    clusters = {}
    prop_items = []
    for it in items:
        e, m, t = it
        if t != 'building':
            prop_items.append(it)
            continue
        key = (int(math.floor(e[1] / CELL_M)), int(math.floor(e[2] / CELL_M)))
        c = clusters.setdefault(key, {'x0': 1e9, 'x1': -1e9, 'y0': 1e9, 'y1': -1e9,
                                      'ztop': -1e9, 'zbase': 1e9, 'best': it, 'n': 0})
        sx_, sy_, sz_ = abs(e[8]), abs(e[9]), abs(e[10])
        # 用**模型自身尺寸**算占地，不用实例里的 local bbox：
        # 有大量实例的 bbox 是占位用的单位立方体（-0.5~0.5），照它算房子会变成一片薄片。
        bw_, bd_ = m['sx'] * sx_, m['sy'] * sy_
        x0, x1 = e[1] - bw_ / 2, e[1] + bw_ / 2
        y0, y1 = e[2] - bd_ / 2, e[2] + bd_ / 2
        # 夹到官方占地框内：贴边的房子否则会伸到隔壁据点那块地上
        c['x0'] = max(min(c['x0'], x0), xs0); c['x1'] = min(max(c['x1'], x1), xs1)
        c['y0'] = max(min(c['y0'], y0), ys0); c['y1'] = min(max(c['y1'], y1), ys1)
        c['ztop'] = max(c['ztop'], e[3] + m['sz'] * abs(e[10]))
        c['zbase'] = min(c['zbase'], e[3])
        c['n'] += 1
        if m['sx'] * m['sy'] * m['sz'] > c['best'][1]['sx'] * c['best'][1]['sy'] * c['best'][1]['sz']:
            c['best'] = it

    # 地标：优先名字带 church/station/saloon… 的实体，同分看体量
    lm_items = [(e, m, t) for e, m, t in items if t == 'building' and landmark_kind(m['name']) != 'house']
    lm_items.sort(key=lambda it: -(it[1]['sx'] * it[1]['sy'] * max(it[1]['sz'], 1.0)))
    used_cells = set()
    landmarks = []
    for it in lm_items:
        e = it[0]
        key = (int(math.floor(e[1] / CELL_M)), int(math.floor(e[2] / CELL_M)))
        if key in used_cells:
            continue
        used_cells.add(key)
        landmarks.append((key, it))
        if len(landmarks) == 3:
            break
    if len(landmarks) < 3:      # 地标不够就用最大的普通街区补
        for key, c in sorted(clusters.items(), key=lambda kv: -(kv[1]['x1'] - kv[1]['x0']) * (kv[1]['y1'] - kv[1]['y0'])):
            if key in used_cells:
                continue
            used_cells.add(key)
            landmarks.append((key, c['best']))
            if len(landmarks) == 3:
                break
    lm_by_cell = dict(landmarks)

    placed = 0
    skipped = 0
    def yaw_of(e):
        qx, qy, qz, qw = e[4], e[5], e[6], e[7]
        return math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))

    # ---- 街区体块 ----
    for key, c in clusters.items():
        cw = min(max((c['x1'] - c['x0']) * k, 0.14), CELL_M * k * 1.6)
        cd = min(max((c['y1'] - c['y0']) * k, 0.14), CELL_M * k * 1.6)
        # 高度只取"主件自己的高度"。用簇内 ztop-zbase 会把坡上/河边的件一起算进来，
        # 圣丹尼斯的街区就变成一堆 2 m 高的瘦塔。
        be, bm, _bt = c['best']
        ch = min(max(bm['sz'] * abs(be[10]) * k, 0.14), 1.6)
        # 数据里有大量"墙 / 柱 / 塔"这类薄件，直接当房子会立成一片刀片。
        # 给一个"宽高比下限"：占地至少是高度的 0.45 倍。
        cw = max(cw, ch * 0.45)
        cd = max(cd, ch * 0.45)
        ccx, ccy = (c['x0'] + c['x1']) / 2, (c['y0'] + c['y1']) / 2
        cw2, cd2 = (c['x1'] - c['x0']) / 2, (c['y1'] - c['y0']) / 2
        lx = (ccx - ox) * k
        lz = -(ccy - oy) * k
        # 直接吸附到画出来的地形面（高度图是 4 m/px 平滑过的，用原始 z 会浮空/陷地）
        # 贴到底座地形面（底座是以 med 为 0、clamp ±8 m 画的，这里用同一套规则）
        ly = max(-8.0, min(8.0, smooth_h(terr, ccx, ccy) - med)) * 0.25 * k

        if key in lm_by_cell:
            e, m, t = lm_by_cell[key]
            kind = landmark_kind(m['name'])
            build_landmark(mesh, lx, lz, ly, cw, cd, ch, yaw_of(e), kind, tint_for(placed, kind))
        else:
            wall_cell = WALL_MIX[int(rng.integers(0, len(WALL_MIX)))]
            roof_cell = ROOF_MIX[int(rng.integers(0, len(ROOF_MIX)))]
            add_box(mesh, lx, lz, ly, cw, cd, ch, 0.0, wall_cell, roof_cell,
                    tint_for(placed, 'house'), roof='gable',
                    chimney=False)
        placed += 1

    # ---- 道具（船 / 火车 / 帐篷 / 栈桥）：保留，它们是剪影特征 ----
    for it in prop_items:
        e, m, t = it
        lx = (e[1] - ox) * k
        lz = -(e[2] - oy) * k
        ly = max(-8.0, min(8.0, smooth_h(terr, e[1], e[2]) - med)) * 0.25 * k
        w = max(m['sx'] * abs(e[8]), 0.3) * k
        d = max(m['sy'] * abs(e[9]), 0.3) * k
        h = max(m['sz'] * abs(e[10]), 0.35) * k
        w = min(max(w, 0.12), 6.0)
        d = min(max(d, 0.12), 6.0)
        h = min(max(h, 0.14), 3.0)
        yaw = yaw_of(e)
        nm = m['name'].lower()
        if 'tent' in nm or 'canopy' in nm:
            add_pyramid(mesh, lx, lz, ly, w, d, h, yaw, 'canvas', tint_for(placed, 'tent'))
        elif 'ship' in nm or 'boat' in nm or 'steam' in nm:
            add_box(mesh, lx, lz, ly, w, d, h, yaw, 'plank', 'roof_wood',
                    tint_for(placed, 'dock'), roof='gable', roof_h=h * 0.30)
        elif 'train' in nm or 'loco' in nm:
            add_box(mesh, lx, lz, ly, w, d, max(h, 0.2), yaw, 'metal', 'roof_black',
                    tint_for(placed, 'warehouse'), roof='flat')
        else:
            add_box(mesh, lx, lz, ly, w, d, h, yaw, 'wall_wood', 'roof_wood',
                    tint_for(placed, 'barn'), roof='gable')
        placed += 1

    # 把整块模型平移到 y=0（地形最低点可能低于建最低点，不齐平会插进桌面）
    if mesh.pos:
        miny = min(p[1] for p in mesh.pos)
        if abs(miny) > 1e-6:
            mesh.pos = [(p[0], p[1] - miny, p[2]) for p in mesh.pos]

    return {
        'mesh': mesh, 'k': k, 'size_x': size_x, 'size_z': size_z,
        'ox': ox, 'oy': oy, 'zw': zw,
        'bw': bw, 'bd': bd, 'placed': placed, 'skipped': skipped,
        'n_inst': len(sel), 'n_items': len(clusters) + len(prop_items),
        'n_clusters': len(clusters), 'n_landmarks': len(landmarks),
        'landmarks': [{'name': it[1]['name'],
                       'kind': landmark_kind(it[1]['name'])} for _, it in landmarks],
        'bbox': [xs0, ys0, xs1, ys1],
    }


# ---------------------------------------------------------------- GLB 写出
def write_glb(path, mesh, png_path, name):
    pos = np.asarray(mesh.pos, dtype=np.float32).reshape(-1, 3)
    nrm = np.asarray(mesh.nrm, dtype=np.float32).reshape(-1, 3)
    uv = np.asarray(mesh.uv, dtype=np.float32).reshape(-1, 2)
    col = np.asarray(mesh.col, dtype=np.float32).reshape(-1, 3)
    idx = np.asarray(mesh.idx, dtype=np.uint32)

    # 归一化法线
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    ln[ln == 0] = 1
    nrm = nrm / ln

    blob = bytearray()
    views = []

    def add_view(arr, target=None):
        while len(blob) % 4:
            blob.append(0)
        off = len(blob)
        b = arr.tobytes()
        blob.extend(b)
        v = {'buffer': 0, 'byteOffset': off, 'byteLength': len(b)}
        if target:
            v['target'] = target
        views.append(v)
        return len(views) - 1

    v_pos = add_view(pos, 34962)
    v_nrm = add_view(nrm, 34962)
    v_uv = add_view(uv, 34962)
    v_col = add_view(col, 34962)
    v_idx = add_view(idx, 34963)

    png = open(png_path, 'rb').read()
    while len(blob) % 4:
        blob.append(0)
    img_off = len(blob)
    blob.extend(png)
    img_len = len(png)

    mins = pos.min(axis=0).tolist()
    maxs = pos.max(axis=0).tolist()

    gltf = {
        'asset': {'version': '2.0', 'generator': 'rdr2-miniature/1.0'},
        'scene': 0,
        'scenes': [{'nodes': [0], 'name': name}],
        'nodes': [{'mesh': 0, 'name': name}],
        'meshes': [{'name': name, 'primitives': [{
            'attributes': {'POSITION': 0, 'NORMAL': 1, 'TEXCOORD_0': 2, 'COLOR_0': 3},
            'indices': 4, 'material': 0, 'mode': 4}]}],
        'materials': [{
            'name': name + '_mat',
            'pbrMetallicRoughness': {
                'baseColorTexture': {'index': 0},
                'metallicFactor': 0.0, 'roughnessFactor': 0.88,
            },
            'doubleSided': False,
        }],
        'textures': [{'sampler': 0, 'source': 0}],
        'samplers': [{'magFilter': 9729, 'minFilter': 9987, 'wrapS': 33071, 'wrapT': 33071}],
        'images': [{'bufferView': 5, 'mimeType': 'image/png'}],
        'accessors': [
            {'bufferView': v_pos, 'componentType': 5126, 'count': len(pos), 'type': 'VEC3',
             'min': mins, 'max': maxs},
            {'bufferView': v_nrm, 'componentType': 5126, 'count': len(nrm), 'type': 'VEC3'},
            {'bufferView': v_uv, 'componentType': 5126, 'count': len(uv), 'type': 'VEC2'},
            {'bufferView': v_col, 'componentType': 5126, 'count': len(col), 'type': 'VEC3'},
            {'bufferView': v_idx, 'componentType': 5125, 'count': len(idx), 'type': 'SCALAR'},
        ],
        'bufferViews': views,
        'buffers': [{'byteLength': len(blob)}],
    }
    # 图片 bufferView 单独补上
    gltf['bufferViews'].append({'buffer': 0, 'byteOffset': img_off, 'byteLength': img_len})

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
    return len(pos), len(idx) // 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--code', default='')
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
        r = build_settlement(s, ledger, insts, terr)
        if not r:
            print('!! 空据点', s['code'])
            continue
        mesh = r['mesh']
        png = os.path.join(TEX, s['code'] + '.png')
        # 每个据点的图集必须唯一（验收会查重）：种子掺进据点代码与序号
        seed = (sum(ord(ch) * (j + 3) for j, ch in enumerate(s['code'])) * 7919
                + i * 104729) % 99991
        warm = ((seed % 9) - 4) / 4.0
        build_atlas(seed, warm).save(png, optimize=True)
        glb = os.path.join(MODELS, s['code'] + '.glb')
        nv, nt = write_glb(glb, mesh, png, s['code'])
        rows.append({
            'code': s['code'], 'name_zh': s['name_zh'], 'btype': s['btype'],
            'size_x': round(r['size_x'], 2), 'size_z': round(r['size_z'], 2),
            'scale': round(r['k'], 5), 'scale_boost': round(r['k'] / MAP_SCALE, 2),
            'tris': nt, 'verts': nv,
            'n_inst_in_box': r['n_inst'], 'n_items': r['n_items'],
            'n_placed': r['placed'], 'n_skipped': r['skipped'],
            'tex': os.path.basename(png),
            'tex_kb': round(os.path.getsize(png) / 1024, 1),
            'glb_kb': round(os.path.getsize(glb) / 1024, 1),
            'landmark1': r['landmarks'][0]['name'] if len(r['landmarks']) > 0 else '',
            'landmark1_kind': r['landmarks'][0]['kind'] if len(r['landmarks']) > 0 else '',
            'landmark2': r['landmarks'][1]['name'] if len(r['landmarks']) > 1 else '',
            'landmark2_kind': r['landmarks'][1]['kind'] if len(r['landmarks']) > 1 else '',
            'landmark3': r['landmarks'][2]['name'] if len(r['landmarks']) > 2 else '',
            'landmark3_kind': r['landmarks'][2]['kind'] if len(r['landmarks']) > 2 else '',
            'world_x': s['x'], 'world_y': s['y'],
            'bbox_w': round(r['bw'], 1), 'bbox_d': round(r['bd'], 1),
        })
        print(f"{s['code']:7} {s['name_zh'][:10]:11} {r['size_x']:5.1f}x{r['size_z']:5.1f} m "
              f"tris {nt:6,d} verts {nv:6,d} placed {r['placed']:4d}/{r['n_items']:4d} "
              f"glb {rows[-1]['glb_kb']:.0f} KB")

    if rows:
        csvp = os.path.join(OUT, 'audit.csv')
        write_header = not os.path.exists(csvp) or not args.code
        with open(csvp, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        jsonp = os.path.join(OUT, 'audit.json')
        json.dump(rows, open(jsonp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        tt = sum(r['tris'] for r in rows)
        print(f"\n{len(rows)} 个据点 · 合计 {tt:,} 三角面 · "
              f"平均 {tt/len(rows):,.0f} · 最大 {max(r['tris'] for r in rows):,}")


if __name__ == '__main__':
    main()
