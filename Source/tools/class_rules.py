# -*- coding: utf-8 -*-
"""分类规则的**唯一真身**（纯 Python，不 import bpy）。

谁要判定/校验分类，一律从这里 import：
  · `tools/classify_entities.py`（Blender 构建）
  · `tools/_check_region.py`（区域裁剪对账）
  · `tools/_check_rules.py`（规则自检）
  · `tools/class_registry.py`（向后兼容，只做转出口）

## 判定顺序（固定）
  RULES（名字）→ LEFTOVER（兜底名字）→ 几何兜底（调用方做）→ 纠错清单 → HARD_RULES
  硬规则顺序：ruin → junc（junc 最后赢）
"""
import csv
import io
import os
import re

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from veg_rules import VEG, VEG_EXCLUDE  # noqa: E402

ROOT = r'D:/BrainMaker/大镖客2解包分析'

# 类表（顺序只影响报告打印；判定优先级看 RULES）
CLASSES = (
    'lod', 'terrain_cell', 'underground', 'watertile', 'placeholder',
    'rail', 'struct', 'road', 'ruin', 'decal', 'veg', 'stone', 'rock',
    'veh', 'bldg', 'part', 'junk', 'prop', 'unknown',
)

# 默认隐藏（构建时 collection + 眼睛都关）；decal 由启动器额外关
DEFAULT_HIDDEN = ('lod', 'terrain_cell', 'underground', 'watertile', 'placeholder', 'veg', 'stone', 'road')

# 技术类：内容纠错不覆盖（junc 硬规则除外）
TECHNICAL = ('lod', 'underground')

# 道路 / 废墟 判定词（分类与对账共用）
ROAD = re.compile(
    r'(?<!b)road|junc|(?<![a-z])jun\d|track_dec|(?<![a-z])rut(?![a-z])|'
    r'wheel_mud|horse_mud|foot_mud|sidewalk|roadway', re.I)
RUIN = re.compile(r'ruin', re.I)

# 盆栽/花艺：跳过 veg 与 bldg/part（它们是道具）
PLANT = re.compile(r'plantpot|p_pot_|flowerarng|planter', re.I)

# ── 主规则表（书写顺序 = 优先级）─────────────────────────────────────
RULES = [
    ('lod', '远景碎片', re.compile(
        r'_area_slod|_em_slod|_dslod|_slod|_lod(?=\d|_|$)|_l\d(?=_|$)', re.I)),
    ('terrain_cell', '地形块', re.compile(r'__hd_0_|^outg?_[a-z]_\d+_hd_\d+', re.I)),
    ('underground', '地下停放', re.compile(r'tempbox|_damn(?![a-z])', re.I)),
    ('watertile', '水面块', re.compile(
        r'^a_water|water_fntn|water_pool|waterfountain|groun2fntn|font_water|_water$', re.I)),
    ('placeholder', '占位代理', re.compile(
        r'donotdelete|dontdelete|emitterdummy|placeholder|_occ_|occ_test_box|'
        r'proxy|amb_pun|cubedelete|fakeintdummy|cover_coll|helper', re.I)),
    ('rail', '铁路', re.compile(
        r'railr|rrcross|crossing|crossb|_r_c_|_r_b_|_rc_\d|sleeper|sle\d|railroadtie|trestle|tressle|\btun(nel)?\b|'
        r'\._r_|_rails|railroad|tie0?\d|track_?switch|'
        r'maintrack|northtrack|southtrack|minetrack|rail_?buffer|coatrack|_rhd_\d|'
        r'point_switch|'
        r'rail[_-]?decal|track[_-]?decal|'
        r'b_r_|_r_[abc]_dec', re.I)),
    ('struct', '桥梁结构', re.compile(
        # 🔴 2026-10-31 用户裁定：struct **只放桥/栈桥相关**；码头/船坞/挡墙/筒仓已挪到
        #    bldg / part（见下面两条规则）。别再往这里加通用构筑物。
        r'bridge|_bri(?!ck)|viaduct|trestle|drawbridge|abutment|_truss|girder|culvert', re.I)),
    # 2026-10-31：从 struct 拆出来的通用构筑物。**必须排在 decal/veg 之前**，
    # 否则名字里带草/树等词的码头会被 veg 抢走（实测 88 个）。
    ('bldg', '建筑', re.compile(
        r'dock(?!_?rope)|wharf|pier\d|pier(?![a-z])|silo|watertower|tank\d', re.I)),
    ('part', '建筑部件', re.compile(r'retaining|_slope(_dec)?', re.I)),
    ('road', '道路', ROAD),
    ('ruin', '废墟', RUIN),
    ('decal', '地面贴花', re.compile(
        r'decal|grndec|ground_dec|puddle|dirt|dust|gravel|skid|stain|mudstain|trackmark|rut|patch|mud_|'
        r'oil(slick)?|blood|gore|road_?mark|sidewalk|roadway|_road|path_|trail_|'
        r'ground_?decal|grounddecal|shadow|shad_|_decl\d', re.I)),
    ('veg', '植被', VEG),
    ('stone', '石块', re.compile(
        r'wallstone|rubble|cobble|gravelpile|rockpile|stonepile|boulder|'
        r'rock_?stones|ruin_?stone|rock_?chunk', re.I)),
    ('rock', '岩石地形', re.compile(
        r'rock|boulder|cliff|stone_|outcrop|sandstone|gravelpile|_cliff', re.I)),
    ('veh', '载具', re.compile(
        r'wagon|cart(?!ridge)|carriage|coach|buggy|boat|canoe|skiff|ship|steam|locomotive|'
        r'p_train_|trolley|handcar|barge|raft|stagecoach|hull(?!.*_doors)|canetrain|coupler', re.I)),
    # 2026-10-31 用户样本（区域 #20）：`_em` = 自发光窗片/窗框，归道具
    ('prop', '道具', re.compile(r'_em$', re.I)),
    ('bldg', '建筑', re.compile(
        r'_ext_|bldg|building|church|chapel|saloon|store|shop|bank|hotel|barn|shed|cabin|'
        r'stable|station|factory|warehouse|school|office|theater|theatre|jail|sheriff|'
        r'depot|mill|livery|blacksmith|inn|infirmary|mansion|manor|house|home\d|courthouse|'
        r'postoffice|storefront|res\d\d|shack|cabin|dock_?house|bunkhouse|bathhouse|'
        r'undertaker|gunsmith|tailor|butcher|doctor|photograph|newspaper|'
        # 2026-10-31 用户样本（区域 #20）：街区建筑/公寓/牢房/仓库/车站/工厂/水塔/凉亭
        r'apts(?!.*(sign|_dec(?![a-z])|decals|_em$))|'
        r'cellblock(?!.*(_dec(?![a-z])|decals|_em$))|'
        r'blds(?!.*(_dec(?![a-z])|decals|_em$))|'
        r'trainstn(?!.*(poles|_dec(?![a-z])|decals|_em$))|'
        r'refiner(?!.*_dec(?![a-z]))|water_?twr|(^|_)ware$|gazebo|napol|'
        # 街区地址式建筑：new_com_01_207_decatur / new_frn02_1139chartres / new_mrk_01_1238_002
        r'^new_(com|frn|mrk)(?:_?\d+)*_\d{3,}'
        r'(?!.*(_dec(?![a-z])|decals|_det\d*$|_em$|_d$|sign|balc|stair|rail|top))|'
        # 2026-11-01 用户裁定：tower / build / kitchen / coop / tabacco 这类明显词缀
        r'tower|kitchen(?!.*(_glue|_decal))|coops?$|tabacco|(?<!wh)build(?!site)|'
        r'watertank|powerplant|lookout(?!.*ladder)', re.I)),
    ('part', '建筑部件', re.compile(
        r'wall|roof|porch|fence|fencing|gate|door|window|stair|balustr|railing|rail_?post|rail$|'
        r'deck|beam|pillar|column|framing|trim|awning|sign_?post|boardwalk|plank|lumber|'
        r'scaffold|ladder|fencepen|pen\d|hitching|trough|gutter|shutter|chimney|'
        r'foundation|support|brace|joist|stud|veranda|canopy|pergola|trellis|woodboard|board\d|'
        r'buildsite|backrail|_awn\d|_hoist|hoist_|_pipes$|_tarp$|walkway|ctwalk|_winclosed|'  # 2026-11-01 用户样本
        r'_glue|_outerwall|_shell$|_shell_', re.I)),
    ('junk', '杂物堆', re.compile(
        r'debris|debirs|rubble|trash|garbage|junk|scrap|cloth|cotton|bale|bundle|sugarcane|cane_|'
        r'inv_|_stks|twgs|twig|branch|leaves|leaf_|pile|papers|newspaper|sack|rags|wdbrds|oldrailcamp', re.I)),
    ('prop', '道具', re.compile(
        r'barrel|crate|box\d|chair|table|lamp|lantern|bucket|bottle|wheel|crate|tool|'
        r'anvil|sack|stove|bed|desk|shelf|cabinet|piano|safe|cash|register|counter|'
        r'bench|crate|barrel|trough|coffin|grave|headstone|cross_?mark|post|pole|'
        r'sign|banner|flag|crate|bucket|pump|well|hitching|cart|saddle|rug|curtain|'
        r'p_|^s_|marker|cookfire|tin\d|crate\d|hay|stump|splitwood|woodsplit|'
        # 2026-10-31 用户样本：阳台 / 场景零散 props（含 props 即道具；
        # debris/道路/码头/站台/马车等更具体的词由前面的规则先接走）
        r'balcony|balc(?!o)|props|'
        # 2026-11-01：售货亭 / 摊 / 篷布 / 线缆接头 / 灯珠 / 发光片
        r'shut(?![a-z])|booth|kiosk|newsstand|_items$|fizzlod|hdfizz|spiderdream|tent|_prop$|'
        r'cableconnect|bulb|emitter', re.I)),
]

# 兜底：只对前面全没中的对象生效
LEFTOVER = [
    ('road', re.compile(
        r'_rds(?=_|$)|(?<![a-z])road(?=_|$)|(?<![a-z])street(?=_|$)|roadway', re.I)),
    ('decal', re.compile(
        r'_rds(?=_|$)|_dec(?=\d|_|$)|_dcl(?=\d|_|$)|_ground(?=_|$)|'
        r'(?<![a-z])street(?=_|$)|(?<![a-z])road(?=_|$)|(?<![a-z])path(?=_|$)', re.I)),
    ('prop', re.compile(r'p_pot_|plantpot|flowerarng|p_cs_|dressing|planter', re.I)),
]

ALL_CLASSES = []
for _k, _zh, _rx in RULES:
    if _k not in [c[0] for c in ALL_CLASSES]:
        ALL_CLASSES.append((_k, _zh))
ALL_CLASSES.append(('unknown', '未分类'))


def classify_name(name):
    """名字层判定（RULES → LEFTOVER）；返回类 key 或 'unknown'。"""
    if not name:
        return 'unknown'
    b = re.sub(r'\.\d{3}$', '', name.split('/')[-1])
    for key, _, rx in RULES:
        if key == 'veg' and VEG_EXCLUDE.search(b):
            continue
        if key in ('bldg', 'part') and PLANT.search(b):
            continue
        if rx.search(b):
            return key
    for key, rx in LEFTOVER:
        if rx.search(b):
            return key
    return 'unknown'


def apply_hard_rules(k, name):
    """硬规则（纠错之后执行）：ruin，然后 junc（junc 最后赢）。"""
    if name and 'ruin' in name.lower() and k not in TECHNICAL:
        k = 'ruin'
    if name and 'junc' in name.lower():
        k = 'road'
    return k


def load_corrections(path):
    """读纠错 CSV → [(name_rx|None, tex_rx|None, target, id, reason)]。"""
    out = []
    if not path:
        return out
    p = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if not os.path.exists(p):
        print('[rules] WARNING: 纠错清单不存在 %s' % p)
        return out
    with io.open(p, encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            pat = (row.get('pattern') or '').strip()
            tex = (row.get('texture_pattern') or '').strip()
            tgt = (row.get('target_class') or '').strip()
            if tgt and (pat or tex):
                out.append((
                    re.compile(pat, re.I) if pat else None,
                    re.compile(tex, re.I) if tex else None,
                    tgt,
                    (row.get('id') or '').strip(),
                    (row.get('reason') or '').strip()))
    print('[rules] 纠错清单 %d 条：%s' % (len(out), p))
    return out


def apply_corrections(k, name, tex_names, corrections, verbose=True):
    """纠错层：名字或材质任一命中即生效；lod/underground 技术类豁免。"""
    if not corrections:
        return k
    txs = tex_names or []
    for rx, trx, tgt, cid, reason in corrections:
        hit = bool(rx and name and rx.search(name))
        if not hit and trx is not None:
            hit = any(trx.search(t) for t in txs if t)
        if hit:
            if k in TECHNICAL:
                return k
            if verbose and k != tgt:
                print('[cls] 纠错 #%s %s：%s -> %s（%s）' % (cid, name, k, tgt, reason))
            return tgt
    return k
