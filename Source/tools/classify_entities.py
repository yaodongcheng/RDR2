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
import csv
import argparse
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from veg_rules import VEG, VEG_EXCLUDE          # 植被判定唯一一份（strip_vegetation 也用这个）
from class_registry import ROAD, RUIN            # 道路/废墟判定词（RULES 里要用，必须在 RULES 之前）

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
from class_rules import (  # noqa: E402
    RULES, LEFTOVER, PLANT, ALL_CLASSES,
    classify_name, apply_hard_rules, load_corrections, apply_corrections,
)

# 默认隐藏的类（对应"归类不搬走、整类藏起来"的规范）
# 🔴 唯一一份在 class_registry.py（write_manifest / report_manifest / tour 都 import 它）。
#    2026-10-30 加 `stone`：用户要求「石块」整类默认隐藏（瓜尔马海岸那堆墙石/碎石）。
from class_rules import DEFAULT_HIDDEN


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--out', default='')
    ap.add_argument('--corrections', default='',
                    help='人工纠错清单 CSV（pattern,target_class,reason）；最后应用于每个对象')
    a = ap.parse_args(argv())

    overrides = load_corrections(a.corrections)

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
        k = classify_name(n)
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
        tex_names = [m.name for m in getattr(o.data, 'materials', []) if m]
        k = apply_corrections(k, n, tex_names, overrides)
        k = apply_hard_rules(k, n)
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
