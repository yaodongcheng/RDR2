# -*- coding: utf-8 -*-
"""把 ENTITIES 按用途分类，并重建为「分类 × 地块」的集合树，供 Blender 里逐个开关。

分类顺序（先命中先归属，避免抢类）：
    铁路 → 植被 → 岩石 → 载具 → 建筑 → 建筑部件 → 道路/地面贴花 → 道具
    → 地表贴图-名字 → 地表贴图-几何 → 未分类

为什么先铁路：`railroadtie`（枕木）也含 tie，`r_c_` 地块不能被当成道具。
为什么植被在建筑前：`p_tree_*` 归植被，不能因为含 `p_` 就进道具。

后两类（2026-10-29 新增，只从「未分类」里捞，不影响任何既有归属）：
    · `decal_name` 地表贴图-名字：名字带 `_rds/_dec/_dcl/_ground/street/road/path`
    · `decal_geom` 地表贴图-几何：名字没线索，但**平 + 薄 + 大 + 贴着地面**（见 is_ground_decal）

用法：
    blender -b <blend> -P tools/classify_entities.py -- --report          # 只统计，不动物件
    blender -b <blend> -P tools/classify_entities.py -- --apply --out <out.blend>
"""
import bpy
import os
import re
import sys
import json
import argparse
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from veg_rules import VEG, VEG_EXCLUDE          # 植被判定唯一一份（strip_vegetation 也用这个）

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
AUDIT = os.path.join(ROOT, 'export/world/classify_unmatched.csv')

# 地表贴图-几何 的判据（2026-10-29 用户口径：平、不竖直、又大又薄、贴着地面）
H4 = os.environ.get('RDR2_H4', os.path.join(ROOT, 'work/terrain/H4.npy'))
X0, Y0, RES = -7684.0, -8196.0, 4.0
GEOM_MIN_AREA = 10.0     # 水平面积 >= 10 m²（小件不算地面）
GEOM_MAX_DZ = 1.5        # 绝对厚度 <= 1.5 m（排除 6~12 m 的"平顶大块"，那是台地不是贴花）
GEOM_MAX_RATIO = 0.06    # 厚度/长边 <= 0.06（确保是横着的，不是竖着的墙面）
GEOM_MAX_GAP = 1.0       # 底面离地 <= 1.0 m
GEOM_SKIP = re.compile(r'water|litter|debris|trash|rubbish', re.I)

# 分类：(key, 中文名, 正则)  —— 顺序即优先级
RULES = [
    # 前两类是"结构性"的，必须先吃：否则 `j_1114_r_a_rai_lod13` 会被 rail 抢走，
    # 远景碎片就永远清不干净。
    ('lod', '远景碎片', re.compile(
        r'_area_slod|_em_slod|_dslod|_slod|_lod(?=\d|_|$)|_l\d(?=_|$)', re.I)),
    ('terrain_cell', '地形块', re.compile(r'__hd_0_', re.I)),
    ('rail', '铁路', re.compile(
        r'railr|cross|_r_c_|_r_b_|_rc_\d|sleeper|railroadtie|trestle|\btun(nel)?\b|'
        r'\._r_|_rails|railroad|tie0?\d|track_?switch', re.I)),
    ('struct', '桥梁结构', re.compile(
        r'bridge|_bri\d|viaduct|trestle|drawbridge|abutment|retaining|pier\d|wharf|dock(?!house)|'
        r'_slope(_dec)?|_truss|girder|culvert|watertower|silo|tank\d', re.I)),
    ('decal', '道路地面贴花', re.compile(
        r'decal|grndec|ground_dec|puddle|dirt|dust|gravel|skid|stain|mudstain|trackmark|rut|patch|mud_|'
        r'oil(slick)?|blood|gore|road_?mark|sidewalk|roadway|_road|path_|trail_|'
        r'ground_?decal|grounddecal|shadow|shad_', re.I)),
    ('veg', '植被', VEG),
    ('rock', '岩石地形', re.compile(
        r'rock|boulder|cliff|stone_|outcrop|sandstone|gravelpile|_cliff', re.I)),
    ('veh', '载具', re.compile(
        r'wagon|cart(?!ridge)|carriage|coach|buggy|boat|canoe|skiff|ship|steam|locomotive|'
        r'p_train_|trolley|handcar|barge|raft|stagecoach', re.I)),
    ('bldg', '建筑', re.compile(
        r'_ext_|bldg|building|church|chapel|saloon|store|shop|bank|hotel|barn|shed|cabin|'
        r'stable|station|factory|warehouse|school|office|theater|theatre|jail|sheriff|'
        r'depot|mill|livery|blacksmith|inn|mansion|manor|house|home\d|courthouse|'
        r'postoffice|storefront|res\d\d|shack|cabin|dock_?house|bunkhouse|bathhouse|'
        r'undertaker|gunsmith|tailor|butcher|doctor|photograph|newspaper', re.I)),
    ('part', '建筑部件', re.compile(
        r'wall|roof|porch|fence|fencing|gate|door|window|stair|balustr|railing|rail_?post|'
        r'deck|beam|pillar|column|framing|trim|awning|sign_?post|boardwalk|plank|lumber|'
        r'scaffold|ladder|fencepen|pen\d|hitching|trough|gutter|shutter|chimney|'
        r'foundation|support|brace|joist|stud|veranda|canopy|pergola|trellis|woodboard|board\d|'
        r'_glue|_outerwall|_shell$|_shell_', re.I)),
    ('junk', '杂物堆', re.compile(
        r'debris|debirs|rubble|trash|garbage|junk|scrap|cloth|cotton|bale|bundle|sugarcane|cane_|'
        r'inv_|_stks|twgs|twig|branch|leaves|leaf_|pile|papers|newspaper|sack|rags', re.I)),
    ('prop', '道具', re.compile(
        r'barrel|crate|box\d|chair|table|lamp|lantern|bucket|bottle|wheel|crate|tool|'
        r'anvil|sack|stove|bed|desk|shelf|cabinet|piano|safe|cash|register|counter|'
        r'bench|crate|barrel|trough|coffin|grave|headstone|cross_?mark|post|pole|'
        r'sign|banner|flag|crate|bucket|pump|well|hitching|cart|saddle|rug|curtain|'
        r'p_|^s_|marker|cookfire|tin\d|crate\d|hay|stump|splitwood|woodsplit', re.I)),
]

# 「兜底规则」：只对**前面一条都没中**的对象生效（= 原本会落到 unknown 的）。
# 用它可以给已有类别补 token，而**不会抢走任何既有归属**。
# 2026-10-29：道路/地面贴花的补充 token 放这里 —— 既不新建类别（同一个东西只有一个类），
# 也不会因为它们排在 prop 之后而漏掉。
LEFTOVER = [
    ('decal', re.compile(
        r'_rds(?=_|$)|_dec(?=\d|_|$)|_dcl(?=\d|_|$)|_ground(?=_|$)|'
        r'(?<![a-z])street(?=_|$)|(?<![a-z])road(?=_|$)|(?<![a-z])path(?=_|$)', re.I)),
    # 盆栽 / 花艺 / 装饰件：植被判定把它们排除了，它们本来就是**道具**
    ('prop', re.compile(r'p_pot_|flowerarng|p_cs_|dressing|planter', re.I)),
]

# 收集所有类（去重，保持 RULES 的顺序）—— 建集合/打印都用它
ALL_CLASSES = []
for _k, _zh, _rx in RULES:
    if _k not in [c[0] for c in ALL_CLASSES]:
        ALL_CLASSES.append((_k, _zh))
ALL_CLASSES.append(('unknown', '未分类'))

# 默认隐藏的类（对应"归类不搬走、整类藏起来"的规范）
DEFAULT_HIDDEN = ('lod', 'terrain_cell', 'veg')


# ── 地表贴图-几何：判据实现 ──────────────────────────────────────────
_H4C = None


def ground_z(x, y):
    """该 (x,y) 的地形高程（H4，4 m/px）。取不到返回 None。"""
    global _H4C
    if _H4C is None:
        import numpy as np
        _H4C = np.load(H4)
    r = int(round((y - Y0) / RES))
    c = int(round((x - X0) / RES))
    if 0 <= r < _H4C.shape[0] and 0 <= c < _H4C.shape[1]:
        return float(_H4C[r, c])
    return None


def world_bbox(o):
    """世界坐标包围盒 (x0,y0,z0,x1,y1,z1)。"""
    from mathutils import Vector
    m = o.matrix_world
    cs = [m @ Vector(c) for c in o.bound_box]
    xs = [v.x for v in cs]
    ys = [v.y for v in cs]
    zs = [v.z for v in cs]
    return min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)


def is_ground_decal(o, name):
    """平（不竖直）+ 又大又薄 + 底面贴着地面 → 地表贴图。

    用户口径（2026-10-29）：①平的不是竖着的 ②又大又薄 ③坐标和地面很接近。
    四道门任意一道不过就不是；水面/垃圾/碎石按名字直接排掉（几何上也平，会误判）。
    """
    if GEOM_SKIP.search(name.split('/')[-1]):
        return False
    try:
        x0, y0, z0, x1, y1, z1 = world_bbox(o)
    except Exception:
        return False
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    if dx * dy < GEOM_MIN_AREA:          # 太小：是物件不是地面
        return False
    if dz > GEOM_MAX_DZ:                 # 太厚：台地/大块
        return False
    if dz / max(dx, dy, 1e-6) > GEOM_MAX_RATIO:   # 竖直的：墙面/牌子
        return False
    g = ground_z((x0 + x1) / 2, (y0 + y1) / 2)
    if g is None or abs(z0 - g) > GEOM_MAX_GAP:   # 不贴地：悬空
        return False
    return True


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF


def load_names():
    d = {}
    with open(NAMES, encoding='latin1', errors='ignore') as f:
        for l in f:
            n = l.strip()
            if n:
                d.setdefault(joaat(n), n.lower())
    return d


def classify(name):
    if not name:
        return 'unknown'
    b = name.split('/')[-1]
    for key, _, rx in RULES:
        if key == 'veg' and VEG_EXCLUDE.search(b):
            continue                # 盆栽/花艺是道具，不是植被
        if rx.search(b):
            return key
    for key, rx in LEFTOVER:        # 兜底：只对前面都没中的生效
        if rx.search(b):
            return key
    return 'unknown'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--out', default='')
    a = ap.parse_args(argv())

    names = load_names()
    ent = bpy.data.collections.get('ENTITIES')

    # ---- 先把旧版"垃圾桶"里的对象请回 ENTITIES（2026-10-29）----
    # 旧做法把植被/地形块/远景碎片**搬出** ENTITIES 放进 HIDDEN_*，
    # 于是这里根本看不到它们、也就没法重新分类。新版不搬对象，所以先归位。
    LEGACY = ('HIDDEN_VEG', 'HIDDEN_LOD', 'HIDDEN_TERRAIN_CELL', 'HIDDEN_PARKED')
    restored = 0
    for lname in LEGACY:
        lc = bpy.data.collections.get(lname)
        if lc is None:
            continue
        for o in list(lc.objects):
            lc.objects.unlink(o)
            if o.name not in ent.objects:
                ent.objects.link(o)
            restored += 1
        bpy.data.collections.remove(lc)
    if restored:
        print('[cls] 已把旧隐藏集合里的 %d 个对象请回 ENTITIES，重新参与分类' % restored)

    objs = list(ent.all_objects)
    print('[cls] ENTITIES 对象 %d' % len(objs))

    buckets = collections.defaultdict(list)
    unmatched = collections.Counter()
    for o in objs:
        hx_s = o.get('hash')
        try:
            hx = int(hx_s, 16) if hx_s else int(o.name[2:].split('.')[0], 16)
        except Exception:
            buckets['unknown'].append(o)
            unmatched['(无 hash 属性且名字不是 e_<hash>)'] += 1
            continue
        n = names.get(hx, '') or o.name
        k = classify(n)
        # 属性判定（名字判不出来，但对象身上带着标签）
        if o.get('hide_tag') == 'terrain_cell':
            k = 'terrain_cell'
        elif k == 'unknown' and is_ground_decal(o, n):
            k = 'decal'             # 平/薄/大/贴地的地面 —— 归到既有的「道路地面贴花」
        buckets[k].append(o)
        if k == 'unknown':
            unmatched[n.split('/')[-1] if n else '(names.txt 查不到)'] += 1

    total = len(objs)
    print('[cls] 分类结果：')
    for key, zh in ALL_CLASSES:
        c = len(buckets.get(key, []))
        print('[cls]   %-12s %-10s %6d  %5.1f%%' % (key, zh, c, 100.0 * c / max(1, total)))
    print('[cls]   %-12s %-10s %6d' % ('TOTAL', '', total))

    if unmatched:
        print('[cls] 未分类里最常见的名字（TOP15）：')
        for n, c in unmatched.most_common(15):
            print('[cls]   %-46s %d' % (n, c))
    # 审计文件
    os.makedirs(os.path.dirname(AUDIT), exist_ok=True)
    with open(AUDIT, 'w', encoding='utf-8') as f:
        f.write('name,count\n')
        for n, c in unmatched.most_common():
            f.write('%s,%d\n' % (n.replace(',', ' '), c))
    print('[cls] 未分类明细已写 %s' % AUDIT)

    if not a.apply:
        return

    # ---- 重建集合树：ENTITIES/<C_key>/<T_tid> ----
    for c in list(ent.children):
        bpy.data.collections.remove(c)
    # 复用 tour 的分区规则
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import blender_tour as tour

    made = 0
    ccols = {}
    for key, zh in ALL_CLASSES:
        col = bpy.data.collections.new('C_%s_%s' % (key, zh))
        ent.children.link(col)
        ccols[key] = col
    for key, objs_ in buckets.items():
        parent = ccols[key]
        tiles = collections.defaultdict(list)
        for o in objs_:
            tiles[tour._tile_of(o.location.x, o.location.y)].append(o)
        for tid, lst in tiles.items():
            sub = bpy.data.collections.new('%s|%s' % (key, tid))
            sub['tile'] = tid
            sub['cat'] = key
            parent.children.link(sub)
            for o in lst:
                sub.objects.link(o)
                made += 1
    # 清掉顶层直接挂载
    for o in list(ent.objects):
        ent.objects.unlink(o)
    print('[cls] 已重建集合树，归位 %d 个对象，分类 %d 组' % (made, len(buckets)))

    # ---- 默认隐藏：**整类设可见性开关，不搬对象**（2026-10-29 规范）----
    # 一个对象只属于一个类；"藏起来"是这个类的一个属性，不是把它挪进垃圾桶。
    for key in DEFAULT_HIDDEN:
        col = ccols.get(key)
        if col is None:
            continue
        col.hide_viewport = True
        col.hide_render = True
        n = len(col.all_objects)
        if n:
            print('[cls] 「%s」%d 个 → 整类默认隐藏（对象仍在类里，N 面板可切回）'
                  % (dict(ALL_CLASSES)[key], n))

    if a.out:
        bpy.ops.wm.save_as_mainfile(filepath=a.out)
        print('[cls] saved %s (%.2f GB)' % (a.out, os.path.getsize(a.out) / 1e9))


if __name__ == '__main__':
    main()
