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
    'lod', 'lod_out', 'terrain_lod', 'terrain_cell', 'underground', 'watertile', 'placeholder',
    'rail', 'rail_decal', 'struct', 'road', 'track_decal', 'ruin', 'decal', 'bldg_decal',
    'int_decal', 'int_proxy',
    'veg', 'stone', 'rock',
    'veh', 'bldg', 'part', 'junk', 'prop', 'unknown',
)

# 默认隐藏（构建时 collection + 眼睛都关）；decal 由启动器额外关
# int_decal = 室内地面贴花（2026-11-05 用户裁定：和室外 decal 分开）。
# 判定不走名字（室内件全是 i_<hash>），由 scene_interiors.py 按模型贴图名现场判；
# 当前贴图 alpha 还没接，会画成实心片 ⇒ 默认隐藏，面板可单独勾开。
# int_proxy = 室内阴影 / 反射代理（2026-11-05 用户裁定：单独成类，别混进「室内」）。
# 同样判不出名字，由 scene_interiors.py 按**模型名**判（proxy/shadow/shdw/shd_/shad_ 一整族，
# 全量 326 件）；它们只参与投影与镜面，摆出来就是盖在屋顶/墙上的一块空壳。
# track_decal = 脚印车辙（高度图贴花，2026-11-05 用户裁定：和 road 路面贴花分开）。
DEFAULT_HIDDEN = ('lod', 'terrain_lod', 'terrain_cell', 'underground', 'watertile',
                  'placeholder', 'veg', 'stone', 'road', 'track_decal', 'int_decal', 'int_proxy',
                  'bldg_decal')

# 技术类：内容纠错不覆盖（junc 硬规则除外）
TECHNICAL = ('lod', 'underground')

# 道路 / 废墟 判定词（分类与对账共用）
ROAD = re.compile(
    r'(?<!b)road|junc|(?<![a-z])jun\d|track_dec|(?<![a-z])rut(?![a-z])|'
    r'wheel_mud|horse_mud|foot_mud|sidewalk|roadway', re.I)
RUIN = re.compile(r'ruin', re.I)

# 盆栽/花艺：跳过 veg 与 bldg/part（它们是道具）
PLANT = re.compile(r'plantpot|p_pot_|flowerarng|planter', re.I)

# 建筑贴花里混着**地面**类写法（车辙 `_mudtrack_dcl` / 踏板 `_footboards_dcl` / 路面）：
# 这些仍归「地面贴花」。命中此表的 `_dcl` 跳过 bldg_decal，落回 LEFTOVER 的 decal。
BLDG_DECAL_GROUND = re.compile(r'mud|track|foot|road|street|path|ground|puddle|skid|sidewalk', re.I)

# ── 主规则表（书写顺序 = 优先级）─────────────────────────────────────
RULES = [
    # 2026-11-01 用户裁定：**地形远景块**要从「远景碎片」里分出来（原来是混在一类的）。
    # 命名 = `<网格前缀>_<行>_<列>_slod<N>`（如 `nopq_92_95_slod4`），是地形自己的超低级替身。
    # 🔴 2026-11-04 更正：**带 `_area_` 的不是地形**（`nopq_11_14_area_slod4` 等）——
    # 实测贴图是建筑图集（`_ab`）、里面带栏杆件，是**建筑/道具的整区合并 LOD**，
    # 必须留在 `lod`（远景碎片），不能当地形。terrain_lod 只认不带 `area_` 的写法。
    ('terrain_lod', '地形远景块', re.compile(r'^[a-z]{2,6}_\d+_\d+_slod\d*$', re.I)),
    ('lod', '远景碎片', re.compile(
        r'_area_slod|_em_slod|_dslod|_slod|_lod(?=\d|_|$)|_l\d(?=_|$)', re.I)),
    ('terrain_cell', '地形块', re.compile(r'__hd_0_|^outg?_[a-z]_\d+_hd_\d+', re.I)),
    ('underground', '地下停放', re.compile(r'tempbox|_damn(?![a-z])', re.I)),
    ('watertile', '水面块', re.compile(
        r'^a_water|water_fntn|water_pool|waterfountain|groun2fntn|font_water|_water$', re.I)),
    ('placeholder', '占位代理', re.compile(
        r'donotdelete|dontdelete|emitterdummy|placeholder|_occ_|occ_test_box|'
        r'proxy|amb_pun|cubedelete|fakeintdummy|cover_coll|helper', re.I)),
    # 2026-11-01 用户裁定：铁轨**本体**与铁轨**贴花**分成两类（同 road / decal 的先例），
    # 且**不跟 decal 走** —— 贴花是轨面/枕木/栈桥的油渍·炭化层，归 decal 会被启动器一起关掉、画面掉一层。
    # 判定 = 名字里**同时**有「铁路上下文」和「贴花上下文」（纯 `track_decal` **不算**：
    # 实测 58 个里 5 个 `bla_road_track_decal_*` 是土路车辙、39 个 `l_XX_YY_track_decal` 是地形瓦片上的杂草贴花）。
    # 必须排在 rail 之前。
    ('rail_decal', '铁路贴花', re.compile(
        r'(?=.*(?:rail[_-]?decal|railroad[_-]?decal|railr|rrcross|crossing|_r_[abc]_|b_r_|'
        r'sle\d|sleeper|tres(?:tle|sle)|railroad|track_?switch|point_switch|_rhd_|_rails))'
        r'.*(?:decal|_dec(?![a-z])|_dcl(?=\d|_|$))', re.I)),
    ('rail', '铁路', re.compile(
        r'railr|rrcross|crossing|crossb|_r_c_|_r_b_|_rc_\d|sleeper|sle\d|railroadtie|trestle|tressle|\btun(nel)?\b|'
        r'\._r_|_rails|railroad|tie0?\d|track_?switch|'
        r'maintrack|northtrack|southtrack|minetrack|rail_?buffer|coatrack|_rhd_\d|'
        r'point_switch|'
        r'b_r_', re.I)),
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
        r'decal|grndec|ground_dec|puddle|dirt|dust|gravel|skid|stain|mudstain|trackmark|'
        # 🔴 2026-11-05：`oil` / `rut` 原来是**裸子串** —— `boiler`(锅炉)、`oildrum`(油桶)、
        #    `strut`(支撑) 全被扫成"地面贴花"（用户实测整栋 `ann_boilerhse` 成了地面贴花）。
        #    现在只认油污/油渍语境，rut 只认独立词。实测全库 279 个名字因此改类。
        r'(?<![a-z])rut(?![a-z])|patch|mud_|'
        r'oil_?(slick|spill|stain|puddle)|oilslick|'
        r'blood|gore|road_?mark|sidewalk|roadway|_road|path_|trail_|'
        r'ground_?decal|grounddecal|shadow|shad_|_decl\d|codemarkings', re.I)),
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
    # 2026-11-05 用户裁定：**建筑贴花**单独成类，和「地面贴花」分开。
    # `<名>_dcl` / `_dcls` = 贴在建筑**墙面/屋顶**上的污垢层（实测瓦伦丁银行
    # `val_bank_dcl01`：材质 mud_floor / mudgrime / grimewall / dirt_grunge_drip，包住整栋 13.8×25.9×6.4 m）。
    # 原先 `_dcl` 只在 LEFTOVER 兜底里认 ⇒ 名字带 bank / shed / stable 的会先被 `bldg` 抢走，
    # 结果污垢层跟着建筑一起显示（屋顶"花斑"）。
    # 地面类的（车辙/踏板/路面）仍归「地面贴花」—— 守卫见 classify_name 里的 BLDG_DECAL_GROUND。
    ('bldg_decal', '建筑贴花', re.compile(r'_dcls?(?=\d|_|$)', re.I)),
    ('bldg', '建筑', re.compile(
        r'(?<!arch)_ext(?=_|$)|bldg|building|church|chapel|saloon|store|shop|bank|hotel|barn|shed|cabin|'
        # 2026-11-05：`boilerhse`（锅炉房，hse = house 缩写）原来谁都不认，
        #   被 decal 的裸 `oil` 子串抓走 ⇒ 整栋房子成了"地面贴花"（用户实测）。
        r'boilerhse|'
        r'stable|station|factory|warehouse|school|office|theater|theatre|jail|sheriff|'
        r'depot|mill|livery|blacksmith|inn|infirmary|mansion|manor|house|home\d|courthouse|'
        r'postoffice|storefront|res_?\d\d|shack|cabin|dock_?house|bunkhouse|bathhouse|'
        r'undertaker|gunsmith|tailor|butcher|doctor|photo|newspaper|'
        # 2026-11-04 黑水镇 72 个 unknown 复盘补的词（都是当时漏网的写法）：
        #   `_ext` 原来只认 `_ext_`（后跟下划线），`bla_bakery_ext` 这种**结尾**写法全漏；
        #   restaurant / bakery / cafe / cityhall / hardware / lawyer / fishmonger / slum /
        #   corner02 / construction / barber 不在表里；`res01` 认、`res_01` 不认。
        r'restaurant|bakery|cafe|city_?hall|hardware|hardare|lawyer|fishmonger|slum|'
        r'corner\d|construction|barber|(^|_)news(?=_|$)|'
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
        r'scaf+old|ladder|fencepen|pen\d|hitching|trough|gutter|shutter|chimney|'
        r'foundation|support|brace|joist|stud|veranda|canopy|pergola|trellis|woodboard|board\d|'
        r'buildsite|backrail|_awn\d|_hoist|hoist_|_pipes$|_tarp$|walkway|ctwalk|_winclosed|'  # 2026-11-01 用户样本
        # 2026-11-05：`conv<N>` = 矿场输送带（安尼斯堡 ann_05_conv06b 等 14 个），原来谁都不认 → unknown。
        #   `struct` 按 2026-10-31 裁定只放桥，所以归「建筑部件」。
        r'conv\d|conveyor|'
        r'glue|_outerwall|_shell$|_shell_|parklights|arch_?ext', re.I)),   # 2026-11-04：scaf+old 兼容数据里的拼写 scafold
    ('junk', '杂物堆', re.compile(
        r'debris|debirs|rubble|trash|garbage|junk|scrap|cloth|cotton|bale|bundle|sugarcane|cane_|'
        r'inv_|_stks|twgs|twig|branch|leaves|leaf_|pile|papers|newspaper|sack|rags|wdbrds|oldrailcamp|'
        r'burial|plane\d*$', re.I)),
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
        r'cableconnect|bulb|emitter|'
        # 2026-11-04 黑水镇 unknown 复盘：赛马跳栏 / 市政人像（fman）/ 无名散件 objectNNN / 环境零散件
        r'horsejump|_fman\d*|object\d{3}|^amb_', re.I)),
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
# 2026-11-04 用户裁定：远景碎片按「活动区外/内」分成两类。
# 名字规则永远判不出 lod_out —— 它由场景裁剪按几何（是否在活动区内）改标，
# 大陆/旧分区里这个类永远为空，不受影响。
ALL_CLASSES.append(('lod_out', '远景碎片·区外'))
# 2026-11-05：室内地面贴花。名字规则判不出（室内件全是 i_<hash>），
# 由 scene_interiors.py 按模型贴图名判定后直接写 cls_key，这里只登记类名。
ALL_CLASSES.append(('int_decal', '室内地面贴花'))
# 2026-11-05：建筑贴花（墙面/屋顶的污垢层）。名字规则能判（`_dcl`），但必须排在 bldg 之前。
ALL_CLASSES.append(('bldg_decal', '建筑贴花'))
# 2026-11-05：室内阴影 / 反射代理。同样名字规则判不出，由 scene_interiors.py 按模型名直接写 cls_key。
ALL_CLASSES.append(('int_proxy', '室内阴影代理'))
# 2026-11-05：泥地脚印/车辙（高度图贴花）。由纠错表按「名字 + _height_ 贴图」判定，
# 和 road（路面贴花，如 val_03_road_d_19）分开开关。
ALL_CLASSES.append(('track_decal', '脚印车辙'))
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
        if key == 'bldg_decal' and BLDG_DECAL_GROUND.search(b):
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


# 🔴 2026-11-05：远景 LOD 的**贴图兜底**。名字表（names.txt）里查不到名字的实例会被判成
# `unknown` ⇒ 可见 ⇒ 压在 HD 本体上。实测瓦伦丁谷仓：`e_f005a86d`（0xf005a86d 不在名字表里）
# 的包围盒与 `val_01_aucbarns_barn3` 几乎完全重合，屋顶因此多一块深色斑；
# 而它的材质名 `alb_val_barn3_lod_ab` 是铁证。全量：瓦伦丁 607 个 unknown 里 **517 个**材质名带 `_lod`。
# 复用 `lod` 那条名字正则去匹配贴图名，**只在已经判成 unknown 时才兜**（不覆盖已正确分类的件）。
LOD_RX = next(rx for _k, _zh, rx in RULES if _k == 'lod')


def apply_texture_lod(k, tex_names):
    """已经是 `unknown` 的件，再看贴图名像不像远景 LOD；像就归 `lod`（默认隐藏）。"""
    if k != 'unknown':
        return k
    for t in (tex_names or ()):
        if t and LOD_RX.search(t):
            return 'lod'
    return k


def apply_corrections(k, name, tex_names, corrections, verbose=True):
    """纠错层；lod/underground 技术类豁免。

    🔴 2026-11-05 修正语义：**同时写了 pattern 和 texture_pattern 的行 = 两者都要命中（AND）**；
    只写一个的行，按那一个判。
    修之前是「任一命中」（OR），导致第 3 行（`^e_` + `kudz`）把所有 hash 名对象
    （`e_*`）都判成 veg —— 瓦伦丁 635 个无名对象全中招，城镇街区 LOD 因此被藏起来。
    全表 339 行里只有这一行同时写了两个字段，改成 AND 是安全的。
    """
    if not corrections:
        return k
    txs = tex_names or []
    for rx, trx, tgt, cid, reason in corrections:
        hit_n = bool(rx is not None and name and rx.search(name))
        hit_t = bool(trx is not None and any(trx.search(t) for t in txs if t))
        if rx is not None and trx is not None:
            hit = hit_n and hit_t
        elif rx is not None:
            hit = hit_n
        else:
            hit = hit_t
        if hit:
            if k in TECHNICAL:
                return k
            if verbose and k != tgt:
                print('[cls] 纠错 #%s %s：%s -> %s（%s）' % (cid, name, k, tgt, reason))
            return tgt
    return k
