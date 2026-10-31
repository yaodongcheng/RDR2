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

# 盆栽 / 花艺 / 花槽 —— 是**道具**。分类时要抢在 bldg/part 之前把它们让给 prop 规则，
# 否则 `p_plantpotwallnbx02x` 会被 part 的 `wall` 接走（2026-10-30 v20 实测 30 个）。
PLANT = re.compile(r'plantpot|p_pot_|flowerarng|planter', re.I)

# 数据根：与 blender_continent.py 保持一致（写死，别按 __file__ 推——
# 从 Source\tools 启动时会推成 Source，找不到 work/terrain/H4.npy）。
ROOT = r'D:/BrainMaker/大镖客2解包分析'
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
AUDIT = os.path.join(ROOT, 'export/world/classify_unmatched.csv')

# 地表贴图-几何 的判据（2026-10-29 用户口径：平、不竖直、又大又薄、贴着地面）
H4 = os.environ.get('RDR2_H4', os.path.join(ROOT, 'work/terrain/H4.npy'))
X0, Y0, RES = -7684.0, -8196.0, 4.0
GEOM_MIN_AREA = 10.0     # 水平面积 >= 10 m²（小件不算地面）
GEOM_MAX_DZ = 1.5        # 绝对厚度 <= 1.5 m（排除 6~12 m 的"平顶大块"，那是台地不是贴花）
GEOM_MAX_RATIO = 0.06    # 厚度/长边 <= 0.06（确保是横着的，不是竖着的墙面）
GEOM_MAX_GAP = 1.0       # 底面离地 <= 1.0 m
GEOM_SKIP = re.compile(
    r'water|litter|debris|trash|rubbish|'
    # 2026-10-30：平的大件不一定是贴花。站台/地板/走道/楼梯/甲板被"贴地兜底"判成 decal
    # 后会被启动器默认藏掉（实测 27 个，如 arm_01_platform 843 m²、ben_01_floor_d 2,513 m²、
    # cor_walkway 4,172 m²）——这些是实体地板，必须留在可见类里。
    r'platform|floor|walkway|stairs?(?![a-z])|deck(?![a-z])|pier(?![a-z])|wharf|dock(?![a-z])',
    re.I)

# 分类：(key, 中文名, 正则)  —— 顺序即优先级
RULES = [
    # 前两类是"结构性"的，必须先吃：否则 `j_1114_r_a_rai_lod13` 会被 rail 抢走，
    # 远景碎片就永远清不干净。
    ('lod', '远景碎片', re.compile(
        r'_area_slod|_em_slod|_dslod|_slod|_lod(?=\d|_|$)|_l\d(?=_|$)', re.I)),
    # 地形块：游戏自带的地表高度块，和我们的 Terrain 重复、高度对不上 → 默认隐藏。
    # 三族都要收（全部 1024 m 见方，实测都压在地图内/边缘，与高度图冲突）：
    #   ① `a_03__hd_0_0_1`（**双下划线** + hd_0，64 m 小块，3 万多个）
    #   ② `out_b_04_hd_05`（外围地形，85 个在场景里）
    #   ③ `outg_a_03_hd_03`（外围地形另一套，71 个在场景里）
    # 2026-10-30 用户报 `out_c_05_hd_13`"怎么还有"—— 原先这族归 unknown、可见。
    ('terrain_cell', '地形块', re.compile(r'__hd_0_|^outg?_[a-z]_\d+_hd_\d+', re.I)),
    # 地下 / 停放件（2026-10-30 用户裁定：**分类成「地下」并默认隐藏**）。
    # 这些是关卡里"停用"的辅助物，游戏不渲染，装进场景就是地底下的东西：
    #   `wld_tempbox3` 等 4 个停在 (761,1822,-1001.7)；`q_11_damn` 停在原点 z=-200。
    # 另有两条兜底（见 main()）：`tag=parked_offmap`、位置 **z < -80 m**（海床最低才 -34.9 m）。
    ('underground', '地下停放', re.compile(r'tempbox|_damn(?![a-z])', re.I)),
    # 水面块（2026-10-30）：`a_water_lan_b_014` 这类游戏水面瓦片，和我们那张 z=40.5 的单水面
    # 同高打架，用户报"水面上奇怪的东西"。全部归这里、默认隐藏（含带贴图的瀑布/冰面）。
    ('watertile', '水面块', re.compile(r'^a_water', re.I)),
    # 占位 / 代理（2026-10-30）：游戏不渲染的音频代理、遮挡盒、阴影代理、cube 占位。
    #   34 个 `*_audiobox_donotdelete` / `*emitterdummy*`、`*_occ_placeholderbox*`、
    #   `amb_pun_00`（1 m 立方体）、`h_16p_cubedelete001`、`*_proxy`（shadow/audio proxy）。
    ('placeholder', '占位代理', re.compile(
        r'donotdelete|dontdelete|emitterdummy|placeholder|_occ_|occ_test_box|'
        r'proxy|amb_pun|cubedelete', re.I)),
    ('rail', '铁路', re.compile(
        r'railr|cross|_r_c_|_r_b_|_rc_\d|sleeper|sle\d|railroadtie|trestle|tressle|\btun(nel)?\b|'
        r'\._r_|_rails|railroad|tie0?\d|track_?switch|'
        # 2026-10-30 补：站内/矿道轨道、道床、挡车器、煤矿轨（原先漏判成 decal/unknown/prop）。
        # 注意**不要**用泛化的 `_r_[abc]_`：那样会把 `*_r_a_tres*`（木栈桥）和
        # `*_r_a_bri*`（铁路桥）从 bldg/struct 抢进 rail，两类就空了（实测 170 个）。
        r'maintrack|northtrack|southtrack|minetrack|rail_?buffer|coatrack|_rhd_\d|'
        # 2026-10-30 三修：**枕木/道砟是独立的地面片**（`*_rail_decal_*` / `*_track_decal_*`，
        # 贴图就是 `railroad_sleeper*`），原来全归 decal → 启动器一关 decal 就"铁轨上没有枕木"。
        r'rail[_-]?decal|track[_-]?decal|'
        r'b_r_|_r_[abc]_dec', re.I)),
    ('struct', '桥梁结构', re.compile(
        r'bridge|_bri\d|viaduct|trestle|drawbridge|abutment|retaining|pier\d|wharf|dock(?!house)|'
        r'_slope(_dec)?|_truss|girder|culvert|watertower|silo|tank\d', re.I)),
    ('decal', '道路地面贴花', re.compile(
        r'decal|grndec|ground_dec|puddle|dirt|dust|gravel|skid|stain|mudstain|trackmark|rut|patch|mud_|'
        r'oil(slick)?|blood|gore|road_?mark|sidewalk|roadway|_road|path_|trail_|'
        r'ground_?decal|grounddecal|shadow|shad_', re.I)),
    ('veg', '植被', VEG),
    # 2026-10-30 用户要求新增：**石块**（散落的墙石 / 碎石堆 / 鹅卵石 / 大块石），默认隐藏。
    # 起因：瓜尔马海岸一小片地上叠了 2 块墙石 + 5 堆碎石 + 8 堆甘蔗渣，
    #       在 Solid 无贴图视图里像"一坨爆炸的尖刺"，用户要求单独归一类并默认藏起来。
    # 必须排在 `rock`（岩石地形）之前：`wallstone` 否则会被 rock 先吃掉。
    # 🔴 只收"散件"：泛化的 `_stone`/`stone_` 会把塔（`agu_tower_stone_*`）、
    #    石头房（`scr_01_stonehs_roof/wall/ext`）、巨石阵（`wll_stonehenge*`）一起
    #    吞进默认隐藏 —— 2026-10-30 v17 实测误伤 19 个，所以这里只认"碎/堆/块"词。
    ('stone', '石块', re.compile(
        r'wallstone|rubble|cobble|gravelpile|rockpile|stonepile|boulder|'
        r'rock_?stones|ruin_?stone|rock_?chunk', re.I)),
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
    # ⚠️ `plantpot` 必须在这里也写一份：只从 veg 排除的话，`p_plantpotwallnbx02x`
    #    会被 `part` 的 `wall` 规则先接走（30 个实例，v19 实测），类别标成"建筑部件"。
    ('prop', re.compile(r'p_pot_|plantpot|flowerarng|p_cs_|dressing|planter', re.I)),
]

# 收集所有类（去重，保持 RULES 的顺序）—— 建集合/打印都用它
ALL_CLASSES = []
for _k, _zh, _rx in RULES:
    if _k not in [c[0] for c in ALL_CLASSES]:
        ALL_CLASSES.append((_k, _zh))
ALL_CLASSES.append(('unknown', '未分类'))

# 默认隐藏的类（对应"归类不搬走、整类藏起来"的规范）
# 🔴 唯一一份在 class_registry.py（write_manifest / report_manifest / tour 都 import 它）。
#    2026-10-30 加 `stone`：用户要求「石块」整类默认隐藏（瓜尔马海岸那堆墙石/碎石）。
from class_registry import DEFAULT_HIDDEN


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
    # 🔴 先剥掉 Blender 的 `.001` 重复后缀：`_lod$` / `_dec$` 这类**行尾正则**
    # 遇到 `.001` 会失配（2026-10-30 实测：79 个 LOD 会被判成 rock 而显示出来）。
    # names.txt 有名字时不会带后缀，但查不到 hash 时用的是对象名，必须防这一手。
    b = re.sub(r'\.\d{3}$', '', name.split('/')[-1])
    for key, _, rx in RULES:
        if key == 'veg' and VEG_EXCLUDE.search(b):
            continue                # 盆栽/花艺是道具，不是植被
        # 盆栽/花艺/花槽：`p_plantpotwallnbx02x` 这类会先被 part 的 `wall` 抢走
        # （2026-10-30 v20 实测 30 个仍标成"建筑部件"）→ 跳过 bldg/part，交给后面的 prop 规则。
        if key in ('bldg', 'part') and PLANT.search(b):
            continue
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
        # 属性/位置兜底（2026-10-30 用户裁定）：
        #   ① `tag=parked_offmap`（关卡停用件）
        #   ② **完全埋在地表之下 ≥10 m** —— 判据（用户口径，考虑地形不是平面）：
        #      在对象占地范围取 9 个点读地形高度，取**最低**的那个；若
        #          「最低地形 − 对象最高点 > 10 m」  →  整个在土里 → 「地下停放」。
        #      取最低点 = "连脚下最低的那块地都比它高 10 m"，坡上的房子/岩石不会被误判；
        #      反过来，**只要对象最高点高过地表（露出地面），就一律不算**。
        #      这一条同时取代旧的 `|x|<1`（原点停放）和 `z<-80`（绝对地板）两条 ——
        #      原点那批（地面 102 m、物件 z=0）和 tempbox（地面 242、物件 −1001）都满足它。
        if o.get('hide_tag') == 'parked_offmap':
            k = 'underground'
        else:
            try:
                # 已按语义定死的两类不参与：地形块/远景（本身就是重复件，各自有类）
                if k not in ('terrain_cell', 'lod', 'watertile'):
                    bb = world_bbox(o)                      # x0,y0,z0,x1,y1,z1
                    loc = o.location
                    # world_bbox 对"顶点烘进世界坐标"的件会返回局部值 → 退回 位置+局部包围盒
                    if abs((bb[0] + bb[3]) / 2 - loc.x) > 50 or abs((bb[1] + bb[4]) / 2 - loc.y) > 50:
                        top = loc.z + max(c[2] for c in o.bound_box)
                        rx = max(0.5, min(64.0, o.dimensions.x / 2))
                        ry = max(0.5, min(64.0, o.dimensions.y / 2))
                    else:
                        top = bb[5]
                        rx = min(max((bb[3] - bb[0]) / 2, 0.5), 64.0)
                        ry = min(max((bb[4] - bb[1]) / 2, 0.5), 64.0)
                    vals = []
                    for dx in (-rx, 0.0, rx):
                        for dy in (-ry, 0.0, ry):
                            g = ground_z(loc.x + dx, loc.y + dy)
                            if g is not None:
                                vals.append(g)
                    if vals and min(vals) - top > 10.0:
                        k = 'underground'
            except Exception:
                pass
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
    #
    # 2026-10-30 补：`Collection.hide_viewport`（全局开关）与视层眼睛
    # `LayerCollection.hide_viewport` 是**两套状态**，只设前者时用户实测仍可能看见
    # （见 docs/AGENTS.md §4 那条坑）。这里两套一起设，别只设一半。
    _vl_root = bpy.context.view_layer.layer_collection

    def _find_layer(name, node):
        if node.name == name:
            return node
        for ch in node.children:
            r = _find_layer(name, ch)
            if r is not None:
                return r
        return None

    for key in DEFAULT_HIDDEN:
        col = ccols.get(key)
        if col is None:
            continue
        col.hide_viewport = True
        col.hide_render = True
        lc = _find_layer(col.name, _vl_root)
        if lc is not None:
            lc.hide_viewport = True
        n = len(col.all_objects)
        if n:
            print('[cls] 「%s」%d 个 → 整类默认隐藏（collection+眼睛；对象仍在类里，N 面板可切回）'
                  % (dict(ALL_CLASSES)[key], n))

    if a.out:
        bpy.ops.wm.save_as_mainfile(filepath=a.out)
        print('[cls] saved %s (%.2f GB)' % (a.out, os.path.getsize(a.out) / 1e9))


if __name__ == '__main__':
    main()
