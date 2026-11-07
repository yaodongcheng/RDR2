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
    'int_decal', 'int_proxy', 'layout',
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
# layout = 布局白模（Rockstar 地编布局用的 `layout_*` 占位白盒，2026-11-06 用户裁定：
#   **不许删网格**，摆进来但单独成类、默认隐藏）。
DEFAULT_HIDDEN = ('lod', 'terrain_lod', 'terrain_cell', 'underground', 'watertile',
                  'placeholder', 'veg', 'stone', 'road', 'track_decal', 'int_decal', 'int_proxy',
                  'bldg_decal', 'layout')

# 技术类：内容纠错不覆盖（junc 硬规则除外）
TECHNICAL = ('lod', 'underground')

# `e_<8 位十六进制>` / `i_<8 位十六进制>` = 名字表里查不到、由程序合成的哈希名。
#   `e_` = 世界实体（blender_continent 生成），`i_` = 室内件（scene_interiors 生成），
#   `i_<hash>_lay` = 室内布局白模件。**它不是名字**，不能参与按名字的规则
#   （十六进制里的字母会误命中 bed / cab / dec 这类裸词）。
HASH_NAME = re.compile(r'^[ei]_[0-9a-f]{8}(?:_lay)?$', re.I)

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
        # 2026-11-06（用户实机，`bra_vfx_man_window_fire`）：`vfx` = 特效/效果件（火焰、余烬、
        #   水花、灯光代理），是**功能占位**不是常驻模型 —— 画出来就是一张烧着的卡片。
        #   实测全库名字带 vfx 且有模型的只有 113 个，落在可见类的约 75 个。
        #   更早的规则仍优先：`a_water_01_vfx*` 归水面块、`*_vfx*_slod` 归远景碎片、`*_helper` 本就占位。
        # 2026-11-07（用户裁定）：`fakeint` = Rockstar 的"假室内"占位壳（站在外面透过门窗看到的简化室内）。
        #   游戏里它和真室内**不会同时出现**；我们两套都摆 ⇒ 完全重叠、互相穿插。
        #   **算坐标时要用它**（室内对位的水平对中/顶部对齐都以它为参照），但**不用显示**。
        r'vfx|fakeint|proxy|amb_pun|cubedelete|fakeintdummy|cover_coll|helper', re.I)),
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
        # 2026-11-06（用户实机）：`p_08_ftr_regular` / `p_08_ftr_endsum` / `p_13_ftr_burnt`
        # 这类 **地形补片**（142×103 m、约 2 m 厚，贴图全是 `_abte` 地形 albedo：草/路/碎石/焦土）
        # 原来被 `prop` 的裸 `p_` 前缀抓成道具。它们铺在地形上 = 地面贴花。
        # 只认 `p_<数字>_ftr_`：`u_06_ftr_01/02` 是真岩石（48×17×39，不是贴花）；
        # `p_13_ftr_*_bridge_*` 是真桥（struct 规则在前，先接走）；`*_lod/_slod` 也被 lod 先接走。
        r'p_\d+_ftr_|'
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
        # 2026-11-06：`wagonhse`（马车房，建筑）不能被裸 `wagon` 抓走 —— 实测
        # `van_horn_01_wagonhse01` 17×15×12 m 被分进载具。
        # 2026-11-07（用户实机 `cal_carriage_house_ext`）：`carriage` 是裸词 —— 马车**房**
        #   （carriage house）整族被判成"载具"：`bla_carriagehouse_int` / `cal_carriage_house_ext` /
        #   `new_carriagehouse_props` 等。与 `wagon(?!_?hse)` 同一类坑。
        #   守卫只挡"房子"语境（house / hse / _ext），**真车照旧**：`p_guncarriagewreck01x` /
        #   `new_gar_06_carriage02` 仍是载具。实测全库影响 40 个（39 → 建筑、1 → 道具），不产生新的未分类。
        r'wagon(?!_?hse)|cart(?!ridge|stop)|carriage(?!.*(?:house|hse|_ext))|coach|buggy|boat|canoe|skiff|ship|steam|locomotive|'
        r'p_train_|trolley|handcar|barge|raft|stagecoach|hull(?!.*_doors)|canetrain|coupler', re.I)),
    # 2026-10-31 用户样本（区域 #20）：`_em` = 自发光窗片/窗框，归道具
    # 2026-11-06：`_em_hd` 也是同一族（17 个，安尼斯堡/瓦伦丁的自发光窗），原来只认结尾 `_em`。
    # 2026-11-06（瓦伦丁 unknown 复盘）：`val_05__em001` / `val_04__em003_re` 这种 **`_em+数字`**
    #   同样是自发光窗（贴图 `val_win_church_01_em` / `val_cs_curtains_01_em`），补 `\d`。
    ('prop', '道具', re.compile(r'_em(?=_hd|\d|$)', re.I)),
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
        # 2026-11-06（用户实机，圣丹尼斯）：`new_wrh_02_boiler`（14×29×34 m、16 子网格的锅炉房）
        # 不在表里。只认**结尾** `boiler`：`p_boiler01x`（道具）、`agu_boiler_roof/walls/windows`（部件）、
        # `agu_boiler_refblocker`（参考块）都不受影响。
        r'boiler(?=$)|'
        # 2026-11-06：安尼斯堡 44 个 unknown 复盘 —— 三个写法原来是真房子却没人认：
        #   `ann_housing010_d`（18×25×8 m，12 槽屋顶/木墙/窗框）、`ann_storage`（13×13×8）、
        #   `ann_02_locker_room`（19×29×9，29 槽砖墙/门）。
        # `storage` 必须避开：`p_storagebox01x`（箱子=道具）、`_glue` 装饰件（=部件）、`_decal`（=贴花）。
        # `locker_room` 避开 `_d` 结尾：`ann_02_locker_room_d` 是污渍层，要留给贴花兜底去认。
        # 2026-11-06（用户实机）：`apartment` / `residence` / `wagonhse`（马车房）/
        #   `tradingpost` 原来都不在表里 —— apartment 落 unknown、wagonhse 被 veh 的 `wagon` 抢、
        #   tradingpost 被 prop 的 `post` 抢。`tradingpost` 要避开附属件（`_dec` 贴花 / `_deck` 甲板 /
        #   `_dr` / `_bull` 招牌），那些保持原类。
        r'apartment|residence|wagon_?hse|trading_?post(?!.*_(dec|deck|dr|bull))|'
        # 2026-11-06（用户实机，范霍恩）：`townhall`（市政厅）与 `*hse`（house 缩写：
        #   smallhse / bunkhse / farmhse / mayorshse / playerhse / lghthse…）都不在表里。
        #   `hse` 只认「后接数字 / 结尾 / _main」——避开 `bee_hse_int_bath_mirror`（室内镜）、
        #   `roc_hse_bed01_details01`（床）这类室内件；`_veg/_wood` 附件也排除（不是房子本体）。
        r'town_?hall|hse(?=\d|$|_main)(?!.*_(veg|wood)\d*$)|'
        r'housing|locker_room(?!.*_d(?=\d|_|$))|storage(?!box)(?!.*(_glue|decal))|'
        r'stable|station|factory|warehouse|school|office|theater|theatre|jail|sheriff|'
        r'depot|mill|livery|blacksmith|inn|infirmary|mansion|manor|house|home\d|courthouse|'
        # 2026-11-07（用户实机逐条点名，均为 12~19 m、砖/石/木墙+屋顶的真房子）：
        #   `str_01_carpenter`（木工房）· `eme_messhall`（食堂）· `mfr_01_traindep`（火车库）·
        #   `mfr_04_cottage03`（小屋）· `but_01_hou_b`（hou = house 缩写）· `old_capt`（队长宅）·
        #   `twi_01_twr_s_00`（塔楼，只认 `twr_s_` 写法，避开 `pumpstat_twr` 等）·
        #   `gap_01__gap_s_002`（豁牙裂口的房子；注意它原来被 prop 的裸 `p_` 抓走 —— `gap_` 里含 "p_"）·
        #   `gap_01_cartstop`（马车歇脚站，原来被 veh 的 `cart` 抓走）· `str_03_01_frt`（货运房，全库仅此 1 个）。
        r'carpenter|mess_?hall|train_?dep|cottage|(?<![a-z])hou(?![a-z])|(?<![a-z])capt(?![a-z])|'
        r'twr(?=_s_)|gap_s_\d|_\d\d_frt(?=_|$)|cart_?stop|'
        r'postoffice|storefront|res_?\d\d|'
        # 2026-11-06（用户实机，瓦伦丁 `val_05_res_a`）：住宅用**字母**后缀
        #   （`res_a` / `res_c` / `res_d` / `res_e`），原来的 `res_?\d\d` 只认数字 ⇒ 4 栋房子落 unknown。
        #   三条边界都必须有：
        #     · 左 `(?<![a-z])` —— `metaped_textures_a` / `bridge_tres_a` 里都含 "res_a"；
        #     · 右 `(?![a-z_])` —— `val_res_a_int` / `val_res_a_int_shell`（室内部件）、
        #       `val_05_res_a_dcl`（污垢层，要留给 bldg_decal）、`val_05_res_e_veg`（爬藤）都不该吃。
        r'(?<![a-z])res_[a-z](?![a-z_])|'
        # 2026-11-06（用户实机，瓦伦丁）：三个缩写/俗称不在表里 ——
        #   `val_shrffhs`（警长宅）、`val_freightstn`（货运站）、
        #   `val_03_redrest_endlssum` / `room4rent_enlssum`（无尽头之夏商铺/出租公寓，两种拼写）。
        #   尾部 `(?![a-z0-9_])` 挡住道具写法：`p_win_val_shrffhs_01x`（窗）、
        #   `arm_04__dne_arm_freightstn01x`（`01x` = 道具）。`_dtls` 细节件留给 part。
        r'shrffhs(?![a-z0-9_])|freight_?stn(?![a-z0-9_])|'
        r'end?lssum(?!.*_dtls$)|room4rent(?!.*_dtls$)|'
        r'shack|cabin|dock_?house|bunkhouse|bathhouse|'
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
        # 2026-11-06：安尼斯堡 unknown 复盘补的矿场/工业件（全是部件，不是建筑）：
        #   输送带中段 `convmid` / 水管 `waterpipe` / 通风井 `airshaft` / 边缘绳 `edgerope` /
        #   矿井口顶 `mineshaft_top` / 台阶 `steps` / 枪眼窗 `gun_win`。
        r'convmid|water_?pipe|air_?shaft|edgerope|mineshaft_top|steps?(?=_|\d|$)|gun_win|'
        # 2026-11-06（瓦伦丁 unknown 复盘）：
        #   `_lock` / `_lockdown` = 店铺「上锁状态」前脸（门板 + 挂锁 + 百叶窗），不是整栋楼
        #     —— `val_03_rent_lock` / `gen_lock` / `sal_lock_win|dor` / `law_lock` / `val_02_lockdown_law`。
        #     `locker_room` 不受影响（`_lock` 后接 `e`，`(?=_|$)` 挡住）；已判 bldg 的牢房门
        #     （`val_03_jail_lock`）由 bldg 规则先接走。
        #   `pigpen`（猪圈）/ `gallows`（绞架）= 室外小构筑；按 2026-10-31 裁定 struct 只放桥 ⇒ 部件。
        #   `_dtls` = details 细节件（`redrest_endlssum_dtls` 这类），本体在 bldg。
        #   `explo_cable` 只认这一个写法 —— 裸 `cable` 会一次翻 500+ 个 `cablemesh`，别加。
        r'_lock(?=_|$)|_lockdown(?=_|$)|pigpen|gallows|_dtls$|explo_?cable|'
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


def _append_class(key, zh):
    """手工登记类名：**已经在 ALL_CLASSES 里的不许再 append**。

    🔴 2026-11-06 实机教训：`bldg_decal` 在 RULES 里已经有一行，这里又 append 了一次 ⇒
    `classify_entities` 建树时创建了两个同名集合，Blender 把第二个改名成 `.001`，
    对象全进 `.001`，面板上出现「建筑贴花 (0)」+「建筑贴花.001 (15)」两栏。
    `_check_rules.py` 现在会检查重复，构建侧也做了去重兜底。
    """
    if key not in [c[0] for c in ALL_CLASSES]:
        ALL_CLASSES.append((key, zh))
    else:
        print('[rules] WARNING: 类 %s 重复登记，已忽略（规则表里已有）' % key)


# 2026-11-04 用户裁定：远景碎片按「活动区外/内」分成两类。
# 名字规则永远判不出 lod_out —— 它由场景裁剪按几何（是否在活动区内）改标，
# 大陆/旧分区里这个类永远为空，不受影响。
_append_class('lod_out', '远景碎片·区外')
# 2026-11-05：室内地面贴花。名字规则判不出（室内件全是 i_<hash>），
# 由 scene_interiors.py 按模型贴图名判定后直接写 cls_key，这里只登记类名。
_append_class('int_decal', '室内地面贴花')
# 2026-11-05：建筑贴花由 RULES 里那行登记（`_dcl`），**不要再手工 append**（见 _append_class 注释）。
# 2026-11-05：室内阴影 / 反射代理。同样名字规则判不出，由 scene_interiors.py 按模型名直接写 cls_key。
# 2026-11-06：**灯光占位件**（`*_int_lights` / `*_lights`）也收进本类——同样是"不可见的功能代理"，
# 不另开新类（用户裁定：复用已有的默认隐藏室内功能类，别再堆面板）。实机 `rho_sheriff_int_lights`。
_append_class('int_proxy', '室内阴影代理')
# 2026-11-06：布局白模（`layout_walls/floors/ceiling/props`）。室内由 scene_interiors 写 cls_key，
# 室外由 apply_texture_layout 按贴图判；**不删网格，只归类 + 默认隐藏**（用户裁定）。
_append_class('layout', '布局白模')
# 2026-11-05：泥地脚印/车辙（高度图贴花）。由纠错表按「名字 + _height_ 贴图」判定，
# 和 road（路面贴花，如 val_03_road_d_19）分开开关。
_append_class('track_decal', '脚印车辙')
_append_class('unknown', '未分类')


def classify_name(name):
    """名字层判定（RULES → LEFTOVER）；返回类 key 或 'unknown'。

    🔴 2026-11-07（用户实机 `cal` 体检发现）：**哈希名 `e_<8 位十六进制>` 不是名字，一律判 unknown** ——
       以前它照样跑规则，十六进制里碰巧出现的英文字母会误命中裸词。实测：
       `e_2adbed14` 因为含 "bed" 被判成「道具（床）」、`e_3dbedbf4` 同理 ——
       于是它们绕过了后面的「贴图名带 `_lod` → 远景碎片」兜底，LOD 壳露在画面里。
    """
    if not name:
        return 'unknown'
    b = re.sub(r'\.\d{3}$', '', name.split('/')[-1])
    if HASH_NAME.match(b):
        return 'unknown'          # 哈希名：不参与任何按名字的规则（贴图/位置兜底照跑）
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


# ── 建筑贴花：后缀 + 贴图证据（2026-11-06）────────────────────────────
# 用户实测 `ann_05_conv06a_dc` 被判成「建筑部件」，但它 17 个槽的 albedo 全是
# `nbx_overlays_*` / `nbx_overlay_*` / `nbx_signs_notices` / `ironrust` —— 是一层污渍贴花。
# 旧规则只认 `_dcl`（2026-11-05 立的），`_dc` / `_dec` / `_det_dec` 都漏了。
# 🔴 **不能只按后缀判**：48 个 `_dc` 里 5 个是真建筑（`her_01_shack_01_dc` 用的是木墙贴图，
#    0% 污渍层），一刀切会把真房子藏掉。
# 判据 = 名字带贴花后缀 **且** 模型 albedo 有半数以上是污渍/贴花图。
# `_d` 更含糊（327 个名字，里面有真房子 `ann_housing010_d`）⇒ **只对 unknown 兜底**。
DECAL_SUFFIX = re.compile(r'(?:_dc|_dec|_det_dec)(?=\d|_|$)', re.I)
DECAL_SUFFIX_WEAK = re.compile(r'_d(?=\d|_|$)', re.I)
DECAL_TEX = re.compile(
    r'overlay|decal|_dc_|grime|grunge|rust|stain|moss|dirt|mud|poster|splatter|drip|'
    r'puddle|smudge|nails|woodchip|scratch|signs?_notices|branding', re.I)
# 地面语境的（河水/碎石坡/路面）仍归「地面贴花」，别混进建筑贴花。
DECAL_GROUND = re.compile(r'river|scree|road|street|path|ground|mud|track|trail|sand|snow', re.I)
_TEX_DECAL_EXCLUDE = (
    'bldg_decal', 'int_decal', 'decal', 'rail_decal', 'track_decal',
    'lod', 'lod_out', 'terrain_cell', 'terrain_lod', 'underground',
    'watertile', 'placeholder', 'int_proxy', 'road')


def apply_texture_decal(k, name, tex_names):
    """名字带贴花后缀 + 贴图多半是污渍层 → 建筑贴花（地面语境 → 地面贴花）。

    在执行顺序里放在 `apply_corrections` **之前**：纠错清单是人工裁定，应当能覆盖它。
    """
    if not name or k in _TEX_DECAL_EXCLUDE:
        return k
    if not DECAL_SUFFIX.search(name):
        # 单 `_d` 只兜 unknown（真房子也可能是 `_d` 结尾，交给贴图证据把关）。
        if not (k == 'unknown' and DECAL_SUFFIX_WEAK.search(name)):
            return k
    txs = [t for t in (tex_names or ()) if t]
    if not txs:
        return k
    hits = sum(1 for t in txs if DECAL_TEX.search(t))
    if hits * 2 < len(txs):
        return k
    return 'decal' if DECAL_GROUND.search(name) else 'bldg_decal'


# 2026-11-06：MLO 的 **layout 白模**（`layout_walls/floors/ceiling/props`）。
# 实测 `ann_04_players_int` / `rho_sal_outhouse*` 等 5 个世界实例：整件都是白模贴图，
# 在场景里就是一整块白板（用户实机截图）。全部贴图都是 layout_* → 占位代理（默认隐藏）。
# 混血模型（真实木地板 + layout_floors）不在这里处理：室内侧按子网格丢（scene_interiors），
# 世界侧保留真实子网格。
LAYOUT_TEX = re.compile(r'^(?:alb_)?layout_(?:walls|floors|ceiling|props)$', re.I)


def apply_texture_layout(k, tex_names):
    """整件模型的所有贴图都是 `layout_*` → `layout`（布局白模，默认隐藏）。

    🔴 2026-11-06 用户裁定：**不准删网格** —— 只归类 + 默认隐藏。
    """
    txs = [t for t in (tex_names or ()) if t]
    if not txs or k in ('lod', 'underground'):
        return k
    if all(LAYOUT_TEX.match(t) for t in txs):
        return 'layout'
    return k


# ── 贴图兜底：名字完全看不出来，但材质是「建筑布料」────────────────────
# 2026-11-06（用户实机，`val_05_res_a` 一类）：名字判不出的房子靠贴图认。
# 实测分辨力（瓦伦丁，过半槽位命中才算）：
#   unknown 19/58 = 33% · bldg 31% · prop 4% · part 4% · junk 1% · veh 0%
# ⇒ 能分开但不够干净，所以**只对 unknown 生效**，再加三道闸：
#   ① 尺寸（占地 ≥6×6 m 且高 ≥3 m）—— 小件、贴片、窗片一律不碰；
#   ② 建筑布料过半；
#   ③ 植被贴图（苔藓/爬藤/树枝）过半则否决 —— `val_05_res_e_veg` 就是反例。
# 结果只会把 unknown 挪到 bldg，**两者都可见**，不会让任何东西凭空消失。
BLDG_FABRIC = re.compile(
    r'wall|roof|shingle|plaster|brick|chimney|floorboard|woodplank|exteriorwall|curtain', re.I)
_VEG_TEX = re.compile(r'moss|ivy|branch|foliage|grass|leaf|leaves|bark|tree|bush|fern|reed', re.I)


def apply_texture_bldg(k, tex_names, size=None):
    """名字判不出 + 尺寸够大 + 贴图过半是墙/瓦/砖/梁 → `bldg`。

    `size` = (x, y, z) 米（对象的世界尺寸）；不传则不做兜底。
    """
    if k != 'unknown' or not size:
        return k
    try:
        dx, dy = float(size[0]), float(size[1])
        dz = float(size[2]) if len(size) > 2 else 0.0
    except Exception:
        return k
    if min(dx, dy) < 6.0 or dz < 3.0:
        return k
    txs = [t for t in (tex_names or ()) if t]
    if not txs:
        return k
    # 🔴 必须先给 LOD 让路：hash 命名的远景壳贴图名叫 `bla_west_res_wall_lod_ab` /
    #   `p_fence_wall01x_post_lod_abal` —— 名字里既有 "wall" 又是大件，会被误判成建筑。
    #   这些件原本由后面的 apply_texture_lod 收进 `lod`（默认隐藏），
    #   这里抢先接走 = 远景壳重新露出来（2026-11-06 实测：黑水镇 3 个 · 瓦伦丁 1 个）。
    if any(LOD_RX.search(t) for t in txs):
        return k
    hits = sum(1 for t in txs if BLDG_FABRIC.search(t))
    veg = sum(1 for t in txs if _VEG_TEX.search(t))
    if hits * 2 < len(txs) or veg * 2 >= len(txs):
        return k
    return 'bldg'


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
