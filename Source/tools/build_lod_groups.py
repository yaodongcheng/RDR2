# -*- coding: utf-8 -*-
"""远景碎片（`lod`）→ 据点 / 野地 / 瓜玛 的自动分配与分组。

## 这份数据给谁用

骑砍2 大地图上的据点是用一个 **prefab（低模实体）** 表示的。本脚本把大镖客 2
大陆上所有「远景碎片」（建筑/道具/铁路的 `_lod/_slod` 合并替身，即分类里的 `lod`）
按空间位置**分给 44 个据点 / 12 块野地 / 2 个瓜玛场景**，输出每组的实例清单
（位置、旋转、缩放、模型、贴图、三角面数），供骑砍2 侧拼「城镇 prefab」。

## 分配规则（2026-11-03 用户裁定）

1. 碎片包围盒中心落在某据点的「能走范围」多边形（`scene_specs.json` 的 `P`）里
   → 归该据点（`via=inside`）。
2. 否则，若碎片类型是**建筑类**（建筑/道具、室内、大区块，**排除铁路与植被**），
   且碎片**包围盒**与「据点 P 矩形外扩 64 m」相交 → 归该据点（`via=halo64`）。
   目的：把压在据点边界上的街区补回城镇轮廓，又不把铁路/树林算进城镇。
   （用包围盒相交而不是中心点距离 —— 大块合并 LOD 的中心常在界外几十米，
   但整个街区压在城镇边上，用中心点会漏掉镇子本体；实测多收 13 个、最大 189 m。）
2.5. **大区块（`block`）跨多个据点** → 不归任何据点，进 `span` 组「跨据点区块」。
   判据：与 ≥2 个据点 P 的重叠都 ≥ max(自身面积 5%, 10,000 m²)。
   （2026-11-04 实测：`new_area_slod4` 是圣丹尼斯整片区域的合并 LOD，同时盖住
   sdn 36.5% / sis 10.4% / lak 7.5%，按中心判会整块算给圣丹尼斯，把监狱岛带进它的 prefab。）
3. 否则，中心落在某块野地的 `P` 里 → 归该野地（`via=wild_inside`；多块重叠取中心最近）。
4. 否则，中心落在某块野地的**远景范围**（`FW/FH`）里 → 归该野地（`via=wild_far`）。
5. 否则，离瓜玛两个据点中心 ≤ 2,500 m → 归最近的那个瓜玛场景（`via=guarma`）。
6. 都不满足 → `group_type=none`（只做背景，不属于任何场景）。

> 据点 `P` 互不重叠；野地矩形**故意**覆盖据点（野地场景里据点用远景碎片表现，
> 见 `docs/世界与地编/RDR2_据点分级与场景边界方案.md` §1.0）。所以「先据点后野地」。

## 数据源（全部只读）

* `export/world/continent/tiles/*.json` —— 实例 [hash,x,y,z,qx,qy,qz,qw,sxy,sz,cls]
* `assets/lib_native/index.json` —— 模型局部包围盒 `b`、子网格 `s`、贴图槽 `st`、贴图名
* `deliverable/blender/continent/manifest_continent_v23.jsonl` —— 对象名 + 分类 + 哈希 + 位置
* `deliverable/blender/regions_support/*/manifest_*.jsonl` —— 22 个区域的补充记录（v23 之后新入库的模型）
* `_scratch/settlement_plan/scene_specs.json` —— 据点/野地的 `P` 多边形与尺寸
* `docs/世界与地编/scene_list.csv` —— 场景 id 与 `scene_name`
* `deliverable/manifests/settlements_world_v2.csv` —— 瓜玛两个据点的世界坐标

世界包围盒 = 模型局部包围盒 8 个角 × 缩放 → 按**四元数共轭**旋转 → 加实例位置。
（共轭是因为场景装配时 `rotation_quaternion = (w, -x, -y, -z)`，见 README §4；
本脚本已用 22 个区域 manifest 的 Blender 世界包围盒逐条对过，误差 < 0.01 m。）

## 输出

* `deliverable/manifests/lod_fragments.csv` —— 一行一个碎片（主表，供拼 prefab）
* `deliverable/manifests/lod_groups.json`  —— 每组汇总（数量/面数/包围盒/子组/成员 id）
* `_scratch/lod_groups/lod_groups_check.json` —— 自检数字（对账 + 覆盖）
* `_scratch/lod_groups/lod_groups_map.png`    —— 分组核对图（可选，`--no-map` 关）

## 用法

    python tools/build_lod_groups.py                 # 全量重算 + 出图
    python tools/build_lod_groups.py --strict        # 关掉 64 m 近邻（对照用）
    python tools/build_lod_groups.py --halo 0        # 同上
    python tools/build_lod_groups.py --no-map        # 只出数据，不出图
"""

import argparse
import collections
import csv
import json
import math
import os
import re
import statistics

ROOT = r'D:/BrainMaker/大镖客2解包分析'
SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TILES = os.path.join(ROOT, 'export/world/continent/tiles')
LIB_INDEX = os.path.join(ROOT, 'assets/lib_native/index.json')
CONT_MAN = os.path.join(ROOT, 'deliverable/blender/continent/manifest_continent_v23.jsonl')
REG_DIR = os.path.join(ROOT, 'deliverable/blender/regions_support')
SPEC = os.path.join(ROOT, '_scratch/settlement_plan/scene_specs.json')
SCENE_CSV = os.path.join(ROOT, 'docs/世界与地编/scene_list.csv')
SETTLE_CSV = os.path.join(ROOT, 'deliverable/manifests/settlements_world_v2.csv')
# 2026-11-08：高度源改为大地图模式（三选一）。必须与所选 map 模式一致。
STAGE = '02_river_carve'
HEIGHT_RAW = os.path.join(ROOT, 'deliverable/terrain/stages', STAGE, 'height_r16.raw')
HEIGHT_META = os.path.join(ROOT, 'deliverable/terrain/stages', STAGE, 'meta.json')

OUT_CSV = os.path.join(ROOT, 'deliverable/manifests/lod_fragments.csv')
OUT_JSON = os.path.join(ROOT, 'deliverable/manifests/lod_groups.json')
OUT_PARTS = os.path.join(ROOT, 'deliverable/manifests/lod_split_parts.json')
OUT_DIR = os.path.join(ROOT, '_scratch/lod_groups')
OUT_CHECK = os.path.join(OUT_DIR, 'lod_groups_check.json')
OUT_MAP = os.path.join(OUT_DIR, 'lod_groups_map.png')

HALO_DEFAULT = 64.0          # 据点边界外的近邻半径（米）
GUARMA_MAX_M = 2500.0        # 瓜玛碎片离据点中心的最大距离
SPAN_MIN_RATIO = 0.05        # 大区块「跨据点」判据：与某据点重叠 ≥ 自身面积 5%
SPAN_MIN_ABS = 10000.0       # ……且 ≥ 10,000 m²（小碎片贴边不算）

# 顶层分类（按当前 class_rules）；本脚本只要 lod，terrain_lod 单独排除。
# 🔴 `*_area_slod*`（如 nopq_11_14_area_slod4）是**建筑/道具的整区合并 LOD**，不是地形，
#    归 lod（2026-11-04 用户当场纠正：贴图是建筑图集、里面带栏杆件）。


# --------------------------------------------------------------------------- 名字/分类
def base_name(n):
    """"new_police_int_lod.001" → "new_police_int_lod"（去掉 Blender 重名后缀）。"""
    return re.sub(r'\.\d{3,}$', '', n or '')


def is_terrain_lod(name):
    try:
        import sys
        if os.path.join(SRC, 'tools') not in sys.path:
            sys.path.insert(0, os.path.join(SRC, 'tools'))
        from class_rules import classify_name
        return classify_name(name) == 'terrain_lod'
    except Exception:
        return bool(re.match(r'^[a-z]{2,6}_\d+_\d+_slod\d*$', name, re.I))


def is_lod_name(name):
    """当前名字规则判成 `lod`（远景碎片）的，才算碎片候选。

    🔴 不只看 manifest 的 `c == 'lod'`：v23 有 2 个建筑/道具 LOD 因为是 64×64 m
    被构建期的几何规则打成了 `terrain_cell`（`bac01_combo_slod` / `two_01__two01_combo08_slod`），
    名字规则仍然判 `lod` —— 2026-11-04 用户确认它们是建筑，必须收进来。
    """
    if is_terrain_lod(name):
        return False
    try:
        from class_rules import classify_name
        return classify_name(name) == 'lod'
    except Exception:
        return bool(re.search(r'_slod|_lod(?=\d|_|$)|_l\d(?=_|$)', name, re.I))


RAIL_RE = re.compile(
    r'(_rails?\b|_rails?_|_rai_|_r_[abc]_|_rc_|rail|lod_ties|_?sle\d|tres|rrc|crossing|track)', re.I)
VEG_RE = re.compile(
    r'(kudzu|kudzo|tree|bush|shrub|grass|cactus|palm|fern|vine|plant|flower|weed|scarecrow)', re.I)
INT_RE = re.compile(r'_int(?!er)', re.I)


def sub_group(name):
    """给组内碎片打类型标签（供 prefab 拼装时分桶）。

    建筑/道具 · 室内 · 铁路与地形格 · 植被 · 大区块
    """
    nl = name.lower()
    if INT_RE.search(nl):
        return 'interior'
    if RAIL_RE.search(nl):
        return 'rail'
    if VEG_RE.search(nl):
        return 'veg'
    if '_area_slod' in nl:
        return 'block'
    return 'bldg'


SUB_GROUP_ZH = {
    'bldg': '建筑/道具',
    'interior': '室内',
    'rail': '铁路与地形格',
    'veg': '植被',
    'block': '大区块',
}


# --------------------------------------------------------------------------- 几何
def quat_matrix(qx, qy, qz, qw):
    """RDR2 四元数 (x,y,z,w) → 场景用的旋转矩阵。

    🔴 场景装配用的是**共轭** (w,-x,-y,-z)，见 deliverable/blender/README.md §4
    （p_fence04bx 21 段栅栏：原样 1.65 m → 共轭 0.56 m）。
    """
    qx, qy, qz = -qx, -qy, -qz
    n = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw) or 1.0
    x, y, z, w = qx / n, qy / n, qz / n, qw / n
    return ((1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
            (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
            (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)))


def world_bbox(inst, bb):
    """实例 + 模型局部包围盒 → 世界 AABB（6 个数）。"""
    R = quat_matrix(inst[4], inst[5], inst[6], inst[7])
    sxy = inst[8] if len(inst) > 8 and inst[8] else 1.0
    sz = inst[9] if len(inst) > 9 and inst[9] else 1.0
    mn = [1e18, 1e18, 1e18]
    mx = [-1e18, -1e18, -1e18]
    for i in range(8):
        lx = (bb[0] if i & 1 else bb[3]) * sxy
        ly = (bb[1] if i & 2 else bb[4]) * sxy
        lz = (bb[2] if i & 4 else bb[5]) * sz
        px = R[0][0] * lx + R[0][1] * ly + R[0][2] * lz + inst[1]
        py = R[1][0] * lx + R[1][1] * ly + R[1][2] * lz + inst[2]
        pz = R[2][0] * lx + R[2][1] * ly + R[2][2] * lz + inst[3]
        for j, v in enumerate((px, py, pz)):
            if v < mn[j]:
                mn[j] = v
            if v > mx[j]:
                mx[j] = v
    return mn + mx


def _pip(px, py, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            xin = (x2 - x1) * (py - y1) / (y2 - y1) + x1
            if px < xin:
                inside = not inside
    return inside


def poly_rect(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def dist_rect(px, py, r):
    dx = max(r[0] - px, 0.0, px - r[2])
    dy = max(r[1] - py, 0.0, py - r[3])
    return math.hypot(dx, dy)


def rect_overlap(a, b):
    """两个轴对齐矩形 (x0,y0,x1,y1) 的重叠面积（m²）。"""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


# --------------------------------------------------------------------------- 数据载入
def load_tiles():
    """tile → {(hash, x, y, z): 实例行}。跳过 `.json.bak`。"""
    tiles = {}
    for fn in sorted(os.listdir(TILES)):
        if not fn.endswith('.json'):
            continue
        tid = fn[:-5]
        with open(os.path.join(TILES, fn), encoding='utf-8') as fp:
            rows = json.load(fp)
        tiles[tid] = {(r[0], round(r[1], 1), round(r[2], 1), round(r[3], 1)): r for r in rows}
    return tiles


def load_index():
    with open(LIB_INDEX, encoding='utf-8') as fp:
        idx = json.load(fp)
    return idx['models'], {t['id']: t['n'] for t in idx.get('tex', [])}


# ---------------------------------------------------------------------------
# 名字补充（2026-11-05）
# v23 manifest 里有一批对象名是 `e_<hash>`（构建期 names.txt 缺父名，见
# tools/name_source.py）。它们其实是 `val_02_slod` / `bla_blk01_slod` 这类
# **街区 LOD**：模型在库、实例在场景，只是名字丢了 ⇒ 进不了远景分组。
# 这里在读取清单时按 hash 反查补充名；查得到就用真名参与判定。
_E_NAME = re.compile(r'^e_([0-9a-f]{8})$', re.I)
_NAME_MAP = None


def _names():
    global _NAME_MAP
    if _NAME_MAP is None:
        try:
            import sys as _sys
            _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from name_source import load_names
            _NAME_MAP = load_names()
        except Exception:
            _NAME_MAP = {}
    return _NAME_MAP


def resolve_name(n):
    """`e_6e394696` → `val_02_slod`（补充表里查不到就原样返回）。"""
    m = _E_NAME.match(n or '')
    if not m:
        return n
    return _names().get(int(m.group(1), 16), n)


def load_inventory():
    """v23 大陆 manifest + 22 个区域 manifest 的「名字判定为 lod」记录（按名字+位置去重）。"""
    inv = {}
    with open(CONT_MAN, encoding='utf-8') as fp:
        for line in fp:
            r = json.loads(line)
            if '_meta' in r or not r.get('h'):
                continue
            nm = resolve_name(r['n'])
            base = base_name(nm)
            if r.get('c') != 'lod' and not is_lod_name(base):
                continue
            p = r['p']
            inv[(nm, round(p[0], 1), round(p[1], 1))] = {
                'n': nm, 'h': int(r['h'], 16), 'tid': r.get('tid'), 'p': p, 'src': 'v23'}
    extra = 0
    for d in sorted(os.listdir(REG_DIR)):
        sub = os.path.join(REG_DIR, d)
        if not os.path.isdir(sub):
            continue
        for fn in os.listdir(sub):
            if not (fn.startswith('manifest_') and fn.endswith('.jsonl')):
                continue
            tid = fn[len('manifest_'):-len('.jsonl')].split('_', 1)[1]
            with open(os.path.join(sub, fn), encoding='utf-8') as fp:
                for line in fp:
                    r = json.loads(line)
                    if '_meta' in r or not r.get('h'):
                        continue
                    nm = resolve_name(r['n'])
                    base = base_name(nm)
                    if r.get('c') != 'lod' and not is_lod_name(base):
                        continue
                    p = r['p']
                    k = (nm, round(p[0], 1), round(p[1], 1))
                    if k in inv:
                        continue
                    inv[k] = {'n': nm, 'h': int(r['h'], 16), 'tid': tid,
                              'p': p, 'src': 'region'}
                    extra += 1
    return list(inv.values()), extra


def load_specs():
    with open(SPEC, encoding='utf-8') as fp:
        spec = json.load(fp)
    settle = spec['settlements']
    wilds = spec['wilds']
    for s in settle:
        s['rect'] = poly_rect(s['P'][0])
    for w in wilds:
        w['rect'] = poly_rect(w['P'][0])
        w['far_rect'] = (w['x'] - w['FW'] / 2.0, w['y'] - w['FH'] / 2.0,
                         w['x'] + w['FW'] / 2.0, w['y'] + w['FH'] / 2.0)
    return settle, wilds


def load_scene_names():
    """code/id → scene_name（来自 scene_list.csv）。"""
    out = {}
    with open(SCENE_CSV, encoding='utf-8-sig', newline='') as fp:
        for r in csv.DictReader(fp):
            key = (r.get('id') or r.get('code') or '').strip()
            if key:
                out[key] = (r.get('scene_name') or '').strip()
            code = (r.get('code') or '').strip()
            if code:
                out[code] = (r.get('scene_name') or '').strip()
    return out


def load_guarma():
    out = []
    with open(SETTLE_CSV, encoding='utf-8-sig', newline='') as fp:
        for r in csv.DictReader(fp):
            if r.get('code') in ('agu', 'gua'):
                out.append({'code': r['code'], 'name_zh': r.get('name_zh', ''),
                            'name_en': r.get('name_en', ''),
                            'x': float(r['world_x']), 'y': float(r['world_y'])})
    return out


class Ground(object):
    """高度图取地面 z（x = x0 + col*4 ; y = y1 - row*4 ; 行 0 = 北）。"""

    def __init__(self):
        try:
            import numpy as np
        except Exception:
            self.arr = None
            return
        raw = json.load(open(HEIGHT_META, encoding='utf-8'))
        meta, world = raw['height'], raw['world']
        self.x0 = float(world['x0'])
        self.y1 = float(world['y1'])
        self.res = meta['m_per_px']
        self.w, self.h = meta['px']
        self.zmin = meta['zmin']
        self.zmax = meta['zmax']
        self.arr = np.fromfile(HEIGHT_RAW, dtype='<u2')
        if self.arr.size != self.w * self.h:
            self.arr = None
            return
        self.arr = self.arr.reshape(self.h, self.w)

    def z(self, x, y):
        if self.arr is None:
            return 0.0
        col = int(round((x - self.x0) / self.res))
        row = int(round((self.y1 - y) / self.res))
        col = max(0, min(self.w - 1, col))
        row = max(0, min(self.h - 1, row))
        v = float(self.arr[row, col])
        return self.zmin + v / 65535.0 * (self.zmax - self.zmin)


# --------------------------------------------------------------------------- 主流程
def merge_split_parts(frags, parts_path, settle, wilds):
    """用 `split_span_blocks.py` 实测的拆分件替换掉跨据点的整块。

    拆分件已经带好归属（settlement / wild），这里只做替换 + 沿用父块的模型信息
    （hash / mdl / 变换 / 贴图），几何数据（tris / verts / bb）用拆分实测值。
    """
    with open(parts_path, encoding='utf-8') as fp:
        doc = json.load(fp)
    entries = {}
    for p in doc.get('parents', []):
        entries[(p['hash'], p['name'])] = p
    by_code = {s['code']: s for s in settle}
    by_wild = {w['id']: w for w in wilds}

    out = []
    n_parents = n_parts = 0
    for f in frags:
        entry = entries.get((f['hash'], f['name'])) if f.get('via') == 'span' else None
        if entry is None:
            out.append(f)
            continue
        n_parents += 1
        for pt in entry.get('parts', []):
            o = dict(f)
            o.pop('span', None)
            o.update({
                'name': pt['name'], 'part_key': pt['part_key'],
                'tris': int(pt['tris']), 'verts': int(pt['verts']), 'subs': int(pt.get('subs', 1)),
                'bb': [float(v) for v in pt['bb']],
                'tex_a': pt.get('tex_a', f['tex_a']),
                'tex_n': pt.get('tex_n', f['tex_n']),
                'tex_m': pt.get('tex_m', f['tex_m']),
                'via': 'split', 'settle': None, 'wild': None, 'guarma': None,
            })
            bb = o['bb']
            o['cx'] = (bb[0] + bb[3]) / 2.0
            o['cy'] = (bb[1] + bb[4]) / 2.0
            if pt.get('group_type') == 'settlement' and pt.get('group_id') in by_code:
                o['settle'] = by_code[pt['group_id']]
            elif pt.get('group_type') == 'wild' and pt.get('group_id') in by_wild:
                o['wild'] = by_wild[pt['group_id']]
            out.append(o)
            n_parts += 1
    return out, n_parents, n_parts


def build(halo=HALO_DEFAULT, verbose=True, parts_path=OUT_PARTS):
    tiles = load_tiles()
    models, tex_names = load_index()
    inv, extra = load_inventory()
    settle, wilds = load_specs()
    scenes = load_scene_names()
    guarma = load_guarma()
    ground = Ground()

    if verbose:
        print('[lod] 实例 %d · 模型 %d · manifest marshal %d（区域补充 %d）'
              % (sum(len(v) for v in tiles.values()), len(models), len(inv), extra))

    frags = []
    n_terrain = n_unresolved = n_joined_other_tile = 0
    for r in inv:
        name = base_name(r['n'])
        if is_terrain_lod(name):
            n_terrain += 1
            continue
        h = r['h']
        pos = r['p']
        key = (h, round(pos[0], 1), round(pos[1], 1), round(pos[2], 1))
        inst = tiles.get(r['tid'], {}).get(key)
        if inst is None:
            for tid, kv in tiles.items():
                if key in kv:
                    inst = kv[key]
                    r['tid'] = tid
                    n_joined_other_tile += 1
                    break
        m = models.get('0x%08x' % h)
        if inst is None or m is None:
            n_unresolved += 1
            continue
        bb = world_bbox(inst, m['b'])
        sub = m['s']
        st = m.get('st') or []
        albedo = []
        normal = []
        ma = []
        for i, s in enumerate(sub):
            tid = s[0]
            if tid >= 0 and tid in tex_names:
                nm = tex_names[tid]
                if nm not in albedo:
                    albedo.append(nm)
            if i < len(st):
                pair = st[i] or []
                if len(pair) > 0 and pair[0] >= 0 and pair[0] in tex_names:
                    if tex_names[pair[0]] not in normal:
                        normal.append(tex_names[pair[0]])
                if len(pair) > 1 and pair[1] >= 0 and pair[1] in tex_names:
                    if tex_names[pair[1]] not in ma:
                        ma.append(tex_names[pair[1]])
        frags.append({
            'name': name,
            'hash': '0x%08x' % h,
            'mdl': m['f'],
            'tile': r['tid'],
            'src': r['src'],
            'wx': inst[1], 'wy': inst[2], 'wz': inst[3],
            'qx': inst[4], 'qy': inst[5], 'qz': inst[6], 'qw': inst[7],
            'sxy': inst[8] if len(inst) > 8 and inst[8] else 1.0,
            'sz': inst[9] if len(inst) > 9 and inst[9] else 1.0,
            'bb': bb,
            'cx': (bb[0] + bb[3]) / 2.0,
            'cy': (bb[1] + bb[4]) / 2.0,
            'tris': sum(s[2] for s in sub) // 3,
            'verts': sum(s[1] for s in sub),
            'subs': len(sub),
            'tex_a': '|'.join(albedo),
            'tex_n': '|'.join(normal),
            'tex_m': '|'.join(ma),
            'sub_group': sub_group(name),
            'part_key': '',
        })

    # ---- 分配
    for o in frags:
        o['settle'] = None
        o['wild'] = None
        o['guarma'] = None
        o['via'] = ''

    def settle_inside(o):
        for s in settle:
            if _pip(o['cx'], o['cy'], s['P'][0]):
                return s
        return None

    def nearest_settle(o, radius=None):
        best = None
        bd = 1e18
        for s in settle:
            d = dist_rect(o['cx'], o['cy'], s['rect'])
            if radius is not None and d > radius:
                continue
            if d < bd:
                bd = d
                best = s
        return best, bd

    def halo_settle(o, halo):
        """近邻判定：碎片包围盒与「据点 P 矩形外扩 halo」相交，且类型是建筑类。

        🔴 为什么不用「中心点到矩形距离 ≤ halo」：大块合并 LOD 的中心可能在界外
        几十米，但整个街区压在城镇边上（实测圣丹尼斯 3 个 `newru02pr_combo*`、
        Sod House 的 `sbc_shack_b_c_slod` 105×72 m）—— 用中心点会把这些镇子本体漏掉。
        多收的程度有限（实测 +13 个），且都带尺寸上限（最大的 189 m，没有把 1 km 级
        地形块卷进来）。多个据点都够得着时，取中心离各自 P 最近的。
        """
        cands = []
        for s in settle:
            r = (s['rect'][0] - halo, s['rect'][1] - halo,
                 s['rect'][2] + halo, s['rect'][3] + halo)
            bb = o['bb']
            if bb[3] < r[0] or bb[0] > r[2] or bb[4] < r[1] or bb[1] > r[3]:
                continue
            cands.append((dist_rect(o['cx'], o['cy'], s['rect']), s))
        if not cands:
            return None, 1e18
        cands.sort(key=lambda x: x[0])
        return cands[0][1], cands[0][0]

    def wild_inside(o):
        cands = [w for w in wilds if _pip(o['cx'], o['cy'], w['P'][0])]
        if not cands:
            return None
        return min(cands, key=lambda w: (w['x'] - o['cx']) ** 2 + (w['y'] - o['cy']) ** 2)

    def wild_far(o):
        cands = [w for w in wilds
                 if w['far_rect'][0] <= o['cx'] <= w['far_rect'][2]
                 and w['far_rect'][1] <= o['cy'] <= w['far_rect'][3]]
        if not cands:
            return None
        return min(cands, key=lambda w: (w['x'] - o['cx']) ** 2 + (w['y'] - o['cy']) ** 2)

    n_halo = 0
    for o in frags:
        # 🔴 合并 LOD 本身就跨据点 → 不能整块算给某一个据点。
        # 2026-11-04 实测：`new_area_slod4` 是圣丹尼斯**整片区域**的合并 LOD，
        # 同时盖住 sdn 36.5% / sis 10.4%（西西卡监狱 51% 的 P）/ lak 7.5%（拉凯 100% 的 P）。
        # 按「中心在谁的范围」会整块算给圣丹尼斯 → 圣丹尼斯的 prefab 里混进监狱岛。
        # 这类块先标 `span`，再由 `split_span_blocks.py` 按据点 P 矩形切开。
        bb = o['bb']
        foot = (bb[0], bb[1], bb[3], bb[4])          # 只取 XY（bb 是 6 个数，带 z）
        fa = max(1e-9, (foot[2] - foot[0]) * (foot[3] - foot[1]))
        strong = []
        for s in settle:
            a = rect_overlap(foot, s['rect'])
            if a >= max(SPAN_MIN_RATIO * fa, SPAN_MIN_ABS):
                strong.append((a, s))
        is_area = '_area_slod' in o['name'].lower()
        # 整区合并块（`*_area_slod*`）只要压到据点就拆（哪怕只压 1 个）——
        # 它天生是「整片区域的建筑 LOD」，2 km 见方，不能整块塞进一个小镇。
        # 普通碎片要跨 ≥2 个据点才拆。
        if strong and (is_area or len(strong) >= 2):
            strong.sort(key=lambda x: -x[0])
            o['via'] = 'span'
            o['span'] = [(s['code'], a / fa) for a, s in strong]
            continue
        s = settle_inside(o)
        if s is not None:
            o['settle'] = s
            o['via'] = 'inside'
            continue
        if halo > 0 and o['sub_group'] in ('bldg', 'interior', 'block'):
            s2, d = halo_settle(o, halo)
            if s2 is not None:
                o['settle'] = s2
                o['assign_dist'] = d
                o['via'] = 'halo%d' % int(halo)
                n_halo += 1
                continue
        w = wild_inside(o)
        if w is not None:
            o['wild'] = w
            o['via'] = 'wild_inside'
            continue
        w = wild_far(o)
        if w is not None:
            o['wild'] = w
            o['via'] = 'wild_far'
            continue
        best_g = None
        bd = 1e18
        for g in guarma:
            d = math.hypot(o['cx'] - g['x'], o['cy'] - g['y'])
            if d < bd:
                bd = d
                best_g = g
        if best_g is not None and bd <= GUARMA_MAX_M:
            o['guarma'] = best_g
            o['via'] = 'guarma'
            o['assign_dist'] = bd
            continue
        o['via'] = 'none'

    # ---- 跨据点整块：如果已经有实测拆分件（split_span_blocks.py 产出），用它替换整块
    n_split_parents = n_split_parts = 0
    if parts_path and os.path.exists(parts_path):
        frags, n_split_parents, n_split_parts = merge_split_parts(frags, parts_path, settle, wilds)
        if n_split_parents:
            if verbose:
                print('[lod] 拆分件替换：%d 个跨据点整块 → %d 个部件'
                      % (n_split_parents, n_split_parts))

    # ---- 每个碎片到最近据点的距离（不论分到哪，都留一列给人看）
    for o in frags:
        _, nd = nearest_settle(o)
        o['dist_settle'] = nd
        if 'assign_dist' not in o:
            o['assign_dist'] = 0.0 if o['settle'] is not None else None

    # ---- 野地背景列：所有碎片（含已归据点的）落在哪块野地的 P / 远景里
    for o in frags:
        w = wild_inside(o) or wild_far(o)
        o['wild_scene'] = w['id'] if w else ''

    # ---- 组与锚点
    groups = []
    for s in settle:
        groups.append({'type': 'settlement', 'id': s['code'],
                       'name_zh': s.get('name', ''), 'name_en': s.get('name_en', ''),
                       'scene': scenes.get(s['code'], ''),
                       'x': s['x'], 'y': s['y'], 'z': ground.z(s['x'], s['y']),
                       'z_src': 'heightmap', 'members': []})
    for w in wilds:
        groups.append({'type': 'wild', 'id': w['id'],
                       'name_zh': w.get('name_zh', ''), 'name_en': '',
                       'scene': scenes.get(w['id'], ''),
                       'x': w['x'], 'y': w['y'], 'z': ground.z(w['x'], w['y']),
                       'z_src': 'heightmap', 'members': []})
    for g in guarma:
        groups.append({'type': 'guarma', 'id': g['code'], 'name_zh': g['name_zh'],
                       'name_en': g['name_en'], 'scene': scenes.get(g['code'], ''),
                       'x': g['x'], 'y': g['y'], 'z': 0.0, 'z_src': 'sea_level',
                       'members': []})
    groups.append({'type': 'span', 'id': 'span', 'name_zh': '跨据点区块', 'name_en': '',
                   'scene': '', 'x': 0.0, 'y': 0.0, 'z': 0.0, 'z_src': 'none', 'members': []})
    groups.append({'type': 'none', 'id': 'none', 'name_zh': '无场景', 'name_en': '',
                   'scene': '', 'x': 0.0, 'y': 0.0, 'z': 0.0, 'z_src': 'none', 'members': []})

    by_id = {(g['type'], g['id']): g for g in groups}
    for o in frags:
        if o['via'] == 'span':
            g = by_id[('span', 'span')]
        elif o['settle'] is not None:
            g = by_id[('settlement', o['settle']['code'])]
        elif o['wild'] is not None:
            g = by_id[('wild', o['wild']['id'])]
        elif o['guarma'] is not None:
            g = by_id[('guarma', o['guarma']['code'])]
        else:
            g = by_id[('none', 'none')]
        o['group'] = g
        g['members'].append(o)

    # 瓜玛没有大陆高度图 → 组锚点 z 用组内碎片底面的中位数
    for g in groups:
        if g['type'] == 'guarma' and g['members']:
            g['z'] = statistics.median(o['bb'][2] for o in g['members'])
            g['z_src'] = 'median_bbox_min'
    # 跨据点区块：锚点取组内碎片中心的中位数（本来就不属于某一个点）
    for g in groups:
        if g['type'] == 'span' and g['members']:
            g['x'] = statistics.median((o['bb'][0] + o['bb'][3]) / 2 for o in g['members'])
            g['y'] = statistics.median((o['bb'][1] + o['bb'][4]) / 2 for o in g['members'])
            g['z'] = ground.z(g['x'], g['y'])
            g['z_src'] = 'heightmap'

    # ---- 编号 + 局部坐标（相对组锚点）
    for g in groups:
        g['members'].sort(key=lambda o: (o['name'], o['wx'], o['wy']))
        for i, o in enumerate(g['members'], 1):
            o['frag_id'] = '%s_f%04d' % (g['id'], i)
            o['gx'] = o['wx'] - g['x']
            o['gy'] = o['wy'] - g['y']
            o['gz'] = o['wz'] - g['z']

    return {
        'frags': frags, 'groups': groups, 'tiles': tiles, 'models': models,
        'n_terrain': n_terrain, 'n_unresolved': n_unresolved,
        'n_other_tile': n_joined_other_tile, 'n_halo': n_halo, 'extra': extra,
        'n_split_parents': n_split_parents, 'n_split_parts': n_split_parts,
        'halo': halo, 'ground': ground,
    }


# --------------------------------------------------------------------------- 自检
def check_bboxes(data):
    """用 22 个区域 manifest 的 Blender 世界包围盒反验我们的算法（判据 ≤ 0.05 m）。"""
    tiles = data['tiles']
    models = data['models']
    diffs = []
    for d in sorted(os.listdir(REG_DIR)):
        sub = os.path.join(REG_DIR, d)
        if not os.path.isdir(sub):
            continue
        for fn in os.listdir(sub):
            if not (fn.startswith('manifest_') and fn.endswith('.jsonl')):
                continue
            tid = fn[len('manifest_'):-len('.jsonl')].split('_', 1)[1]
            with open(os.path.join(sub, fn), encoding='utf-8') as fp:
                for line in fp:
                    r = json.loads(line)
                    if r.get('c') != 'lod' or not r.get('h'):
                        continue
                    h = int(r['h'], 16)
                    p = r['p']
                    inst = tiles.get(tid, {}).get(
                        (h, round(p[0], 1), round(p[1], 1), round(p[2], 1)))
                    m = models.get('0x%08x' % h)
                    if inst is None or m is None:
                        continue
                    bb = world_bbox(inst, m['b'])
                    diffs.append(max(abs(bb[i] - r['bb'][i]) for i in range(6)))
    if not diffs:
        return {'n': 0, 'max': None, 'median': None, 'pass': False}
    diffs.sort()
    return {'n': len(diffs), 'max': round(diffs[-1], 4),
            'median': round(diffs[len(diffs) // 2], 4),
            'pass': diffs[-1] <= 0.05}


# --------------------------------------------------------------------------- 输出
CSV_FIELDS = [
    'frag_id', 'part_key', 'group_type', 'group_id', 'scene_name', 'sub_group', 'sub_group_zh',
    'name', 'hash', 'mdl', 'tris', 'verts', 'submeshes', 'tile',
    'wx', 'wy', 'wz', 'qx', 'qy', 'qz', 'qw', 'sxy', 'sz',
    'gx', 'gy', 'gz',
    'bb_min_x', 'bb_min_y', 'bb_min_z', 'bb_max_x', 'bb_max_y', 'bb_max_z',
    'size_x', 'size_y', 'size_z',
    'tex_albedo', 'tex_normal', 'tex_ma',
    'wild_scene', 'assign_via', 'spans', 'assign_dist_m', 'dist_settle_m',
]


def write_csv(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8-sig', newline='') as fp:
        w = csv.DictWriter(fp, fieldnames=CSV_FIELDS)
        w.writeheader()
        for o in data['frags']:
            g = o['group']
            bb = o['bb']
            w.writerow({
                'frag_id': o['frag_id'],
                'part_key': o.get('part_key', ''),
                'group_type': g['type'], 'group_id': g['id'], 'scene_name': g['scene'],
                'sub_group': o['sub_group'],
                'sub_group_zh': SUB_GROUP_ZH.get(o['sub_group'], ''),
                'name': o['name'], 'hash': o['hash'], 'mdl': o['mdl'],
                'tris': o['tris'], 'verts': o['verts'], 'submeshes': o['subs'],
                'tile': o['tile'],
                'wx': round(o['wx'], 3), 'wy': round(o['wy'], 3), 'wz': round(o['wz'], 3),
                'qx': round(o['qx'], 6), 'qy': round(o['qy'], 6),
                'qz': round(o['qz'], 6), 'qw': round(o['qw'], 6),
                'sxy': round(o['sxy'], 4), 'sz': round(o['sz'], 4),
                'gx': round(o['gx'], 3), 'gy': round(o['gy'], 3), 'gz': round(o['gz'], 3),
                'bb_min_x': round(bb[0], 2), 'bb_min_y': round(bb[1], 2), 'bb_min_z': round(bb[2], 2),
                'bb_max_x': round(bb[3], 2), 'bb_max_y': round(bb[4], 2), 'bb_max_z': round(bb[5], 2),
                'size_x': round(bb[3] - bb[0], 2), 'size_y': round(bb[4] - bb[1], 2),
                'size_z': round(bb[5] - bb[2], 2),
                'tex_albedo': o['tex_a'], 'tex_normal': o['tex_n'], 'tex_ma': o['tex_m'],
                'wild_scene': o['wild_scene'], 'assign_via': o['via'],
                'spans': ';'.join('%s:%.1f%%' % (c, r * 100.0) for c, r in o.get('span', [])),
                'assign_dist_m': round(o['assign_dist'], 1) if o.get('assign_dist') is not None else '',
                'dist_settle_m': round(o['dist_settle'], 1),
            })


def group_summary(g):
    mem = g['members']
    if mem:
        bb = [min(o['bb'][i] for o in mem) for i in (0, 1, 2)] + \
             [max(o['bb'][i] for o in mem) for i in (3, 4, 5)]
    else:
        bb = []
    subs = collections.Counter(o['sub_group'] for o in mem)
    return {
        'group_type': g['type'], 'group_id': g['id'],
        'scene_name': g['scene'], 'name_zh': g['name_zh'], 'name_en': g['name_en'],
        'anchor_world': [round(g['x'], 2), round(g['y'], 2), round(g['z'], 2)],
        'anchor_z_source': g['z_src'],
        'count': len(mem),
        'tris': sum(o['tris'] for o in mem),
        'verts': sum(o['verts'] for o in mem),
        'unique_models': len({o['hash'] for o in mem}),
        'bbox_world': [round(v, 2) for v in bb],
        'sub_groups': {k: subs[k] for k in SUB_GROUP_ZH if subs.get(k)},
        'assign_via': dict(collections.Counter(o['via'] for o in mem)),
        'fragments': [o['frag_id'] for o in mem],
    }


def write_json(data, path, check):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    groups = [group_summary(g) for g in data['groups']]
    used = [g for g in groups if g['count'] > 0]
    out = {
        'meta': {
            'generated_by': 'tools/build_lod_groups.py',
            'built_at': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
            'purpose': '远景碎片 → 据点/野地/瓜玛 分组；骑砍2 侧据此拼城镇 prefab',
            'rules': {
                'source_class': 'lod（class_rules 当前规则；terrain_lod 与 '
                                '<网格前缀>_<行>_<列>_area_slod 已排除）',
                'settlement_primary': '碎片包围盒中心落在据点 P（能走范围）多边形内',
                'settlement_halo_m': data['halo'],
                'settlement_halo_method': '碎片包围盒与据点 P 矩形外扩 halo 相交（不是中心点距离）',
                'settlement_halo_kinds': ['bldg', 'interior', 'block'],
                'span_block': 'block 类碎片若与 ≥2 个据点 P 的重叠均 ≥ max(自身面积 5%, 10,000 m²) '
                              '→ 归 span 组（跨据点区块），不归任何据点',
                'wild_primary': '中心落在野地 P 内（多块重叠取中心最近）',
                'wild_fallback': '中心落在野地远景范围 FW/FH 内（取中心最近）',
                'guarma_max_m': GUARMA_MAX_M,
                'local_coords': 'gx/gy/gz = 世界坐标 − 组锚点（锚点 z 见 anchor_z_source）',
            },
            'counts': {
                'fragments': len(data['frags']),
                'settlement': sum(g['count'] for g in groups if g['group_type'] == 'settlement'),
                'wild': sum(g['count'] for g in groups if g['group_type'] == 'wild'),
                'guarma': sum(g['count'] for g in groups if g['group_type'] == 'guarma'),
                'none': sum(g['count'] for g in groups if g['group_type'] == 'none'),
                'halo_assigned': data['n_halo'],
                'split_parents': data['n_split_parents'],
                'split_parts': data['n_split_parts'],
                'excluded_terrain_lod': data['n_terrain'],
                'unresolved_no_model': data['n_unresolved'],
                'region_only_records': data['extra'],
            },
            'check': check,
            'data_sources': {
                'instances': 'export/world/continent/tiles/*.json',
                'models': 'assets/lib_native/index.json',
                'names': 'deliverable/blender/continent/manifest_continent_v23.jsonl + regions_support/*',
                'scenes': '_scratch/settlement_plan/scene_specs.json + docs/世界与地编/scene_list.csv',
                'heightmap': 'deliverable/terrain/stages/%s/height_r16.raw' % STAGE,
            },
        },
        'groups': groups,
        'groups_with_fragments': len(used),
    }
    with open(path, 'w', encoding='utf-8') as fp:
        json.dump(out, fp, ensure_ascii=False, indent=1)


def write_map(data, path):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon as MplPolygon
    except Exception as e:
        print('[lod] 跳过出图（%s）' % e)
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # 核对图上有中文，必须挂 CJK 字体，否则一屏方框
    matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    matplotlib.rcParams['axes.unicode_minus'] = False
    fig, ax = plt.subplots(figsize=(18, 13), dpi=150)
    ax.set_facecolor('#f4f1e8')

    # 野地 / 据点的 P 多边形直接重载 spec（底图用）
    settle, wilds = load_specs()
    for w in wilds:
        ax.add_patch(MplPolygon(w['P'][0], closed=True, fill=True, facecolor='#dff0d8',
                                edgecolor='#7a9a6a', linewidth=0.8, alpha=0.55, zorder=1))
    for s in settle:
        ax.add_patch(MplPolygon(s['P'][0], closed=True, fill=False, edgecolor='#3a6ea5',
                                linewidth=1.0, zorder=2))

    colors = {'settlement': '#1f4e9c', 'wild': '#2e8b3d', 'guarma': '#d2691e',
              'span': '#8e44ad', 'none': '#c0392b'}
    labels = {'settlement': '据点（城镇 prefab 组）', 'wild': '野地（背景组）',
              'guarma': '瓜玛', 'span': '跨据点区块（不归属单个据点）', 'none': '无场景'}
    for t in ('wild', 'settlement', 'guarma', 'span', 'none'):
        pts = [o for o in data['frags'] if o['group']['type'] == t]
        if not pts:
            continue
        ax.scatter([o['cx'] for o in pts], [o['cy'] for o in pts],
                   s=[max(2.0, min(40.0, o['tris'] / 500.0)) for o in pts],
                   c=colors[t], alpha=0.75, linewidths=0, label='%s · %d' % (labels[t], len(pts)),
                   zorder=3)
    for s in settle:
        ax.text(s['x'], s['y'], s['code'], fontsize=8, ha='center', va='center',
                color='#12305e', zorder=4,
                bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.65))
    ax.set_xlim(-6844, 3924)
    ax.set_ylim(-4800, 3224)
    ax.set_aspect('equal')
    ax.set_xlabel('world X (m)')
    ax.set_ylabel('world Y (m)')
    ax.set_title('RDR2 → Bannerlord: 远景碎片分组（%d 个碎片 / %d 组）'
                 % (len(data['frags']), sum(1 for g in data['groups'] if g['members'])))
    ax.legend(loc='lower right', fontsize=9, framealpha=0.9)
    ax.grid(True, color='#dddddd', linewidth=0.5)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    print('[lod] 核对图 -> %s' % path)
    return True


# --------------------------------------------------------------------------- 入口
def main(argv=None):
    ap = argparse.ArgumentParser(description='远景碎片 → 据点/野地/瓜玛 分组')
    ap.add_argument('--halo', type=float, default=HALO_DEFAULT,
                    help='据点边界外的近邻半径（米，默认 64；0 = 严格包含）')
    ap.add_argument('--strict', action='store_true', help='等同 --halo 0')
    ap.add_argument('--no-map', action='store_true', help='不出核对图')
    ap.add_argument('--csv', default=OUT_CSV)
    ap.add_argument('--json', default=OUT_JSON)
    ap.add_argument('--parts', default=OUT_PARTS,
                    help='split_span_blocks.py 产出的拆分件 JSON（不存在则保留整块 span）')
    a = ap.parse_args(argv)
    halo = 0.0 if a.strict else a.halo

    data = build(halo=halo, parts_path=a.parts)
    check = {'bbox_vs_region_manifests': check_bboxes(data)}

    # 覆盖统计
    per_type = collections.Counter(o['group']['type'] for o in data['frags'])
    per_sub = collections.Counter(o['sub_group'] for o in data['frags'])
    empty_settle = [g['id'] for g in data['groups']
                    if g['type'] == 'settlement' and not g['members']]
    check['counts'] = {'by_group_type': dict(per_type), 'by_sub_group': dict(per_sub),
                       'settlements_total': sum(1 for g in data['groups'] if g['type'] == 'settlement'),
                       'settlements_with_fragments': sum(
                           1 for g in data['groups'] if g['type'] == 'settlement' and g['members']),
                       'settlements_empty': empty_settle,
                       'halo_assigned': data['n_halo'],
                       'split_parents': data['n_split_parents'],
                       'split_parts': data['n_split_parts'],
                       'grouped': sum(len(g['members']) for g in data['groups'])}
    check['pass'] = (check['bbox_vs_region_manifests']['pass']
                     and check['counts']['grouped'] == len(data['frags']))

    write_csv(data, a.csv)
    write_json(data, a.json, check)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_CHECK, 'w', encoding='utf-8') as fp:
        json.dump(check, fp, ensure_ascii=False, indent=1)
    if not a.no_map:
        write_map(data, OUT_MAP)

    print('[lod] manifest 记录 %d → 可用碎片 %d（排除地形远景 %d / 无模型 %d / 跨块匹配 %d）'
          % (len(data['frags']) + data['n_terrain'] + data['n_unresolved'],
             len(data['frags']), data['n_terrain'], data['n_unresolved'], data['n_other_tile']))
    print('[lod] 分配：据点 %d（近邻 %d）· 野地 %d · 瓜玛 %d · 无场景 %d'
          % (per_type.get('settlement', 0), data['n_halo'], per_type.get('wild', 0),
             per_type.get('guarma', 0), per_type.get('none', 0)))
    print('[lod] 类型：%s' % ', '.join('%s %d' % (SUB_GROUP_ZH[k], per_sub[k])
                                       for k in SUB_GROUP_ZH if per_sub.get(k)))
    print('[lod] 据点覆盖 %d/%d；无碎片的据点：%s'
          % (check['counts']['settlements_with_fragments'],
             check['counts']['settlements_total'], ','.join(empty_settle) or '无'))
    bb = check['bbox_vs_region_manifests']
    print('[lod] 包围盒反验（区域 manifest %d 条）：最大误差 %.3f m → %s'
          % (bb['n'], bb['max'] or 0, 'PASS' if bb['pass'] else 'FAIL'))
    print('[lod] 输出：%s / %s / %s' % (a.csv, a.json, OUT_CHECK))
    print('[lod] VERDICT → %s' % ('PASS' if check['pass'] else 'FAIL'))
    return 0 if check['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
