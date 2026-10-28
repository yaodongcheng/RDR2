# -*- coding: utf-8 -*-
"""把 ENTITIES 按用途分类，并重建为「分类 × 地块」的集合树，供 Blender 里逐个开关。

分类顺序（先命中先归属，避免抢类）：
    铁路 → 植被 → 岩石 → 载具 → 建筑 → 建筑部件 → 道路/地面贴花 → 道具 → 未分类

为什么先铁路：`railroadtie`（枕木）也含 tie，`r_c_` 地块不能被当成道具。
为什么植被在建筑前：`p_tree_*` 归植被，不能因为含 `p_` 就进道具。

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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
AUDIT = os.path.join(ROOT, 'export/world/classify_unmatched.csv')

# 分类：(key, 中文名, 正则)  —— 顺序即优先级
RULES = [
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
    ('veg', '植被', re.compile(
        r'p_tree|_tree|bush|shrub|p_fern|_fern|p_grass|_grass|p_plant|_plant|cactus|p_palm|'
        # `vine`/`ivy` 前面不能紧跟字母：旧写法把 `cal_privy_01`（厕所）分进了植被（TODO #8）。
        # 用 `(?<![a-z])` 而不是 `\b`：`p_ivy_01` / `ragwort_vine` 里前面是下划线，
        # `\b` 不成立（下划线算单词字符），会把真的常春藤/藤蔓也漏掉。
        r'p_reed|_reed|lily|(?<![a-z])vine|(?<![a-z])ivy|foliage|weed|sapling|flower', re.I)),
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
        buckets[k].append(o)
        if k == 'unknown':
            unmatched[n.split('/')[-1] if n else '(names.txt 查不到)'] += 1

    total = len(objs)
    print('[cls] 分类结果：')
    for key, zh, _ in RULES + [('unknown', '未分类', None)]:
        c = len(buckets.get(key, []))
        print('[cls]   %-8s %-10s %6d  %5.1f%%' % (key, zh, c, 100.0 * c / max(1, total)))
    print('[cls]   %-8s %-10s %6d' % ('TOTAL', '', total))

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
    for key, zh, _ in RULES + [('unknown', '未分类', None)]:
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

    if a.out:
        bpy.ops.wm.save_as_mainfile(filepath=a.out)
        print('[cls] saved %s (%.2f GB)' % (a.out, os.path.getsize(a.out) / 1e9))


if __name__ == '__main__':
    main()
