#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成「常驻角色名单」+「ped 模型目录」+「环境人群模型集/刷新规则」三套 CSV。

对应交接：`docs/世界与地编/RDR2_NPC名单与环境人群表.md`

输入（都在本仓库）：
  raw/script_full/1491.50/init_all_sp.c                       950 条 func_34 注册
  raw/sdn/ai/data/ai/ambientpedmodelsets.meta                 971 个 CAmbientModelSet
  _scratch/perschar_roster/toc_metapeds*.txt                  5 个 metapeds*.rpf 的 TOC
      ↑ 缺了会自动用 rdr2rpf list 现生成（需要 raw/npc/meta/.../metapeds*.rpf 在位）
输出：deliverable/manifests/
  perschar_roster.csv  perschar_by_zone.csv
  ped_model_catalog.csv
  ambient_modelsets.csv  ambient_modelsets_summary.csv  ambient_by_group.csv

用法：
  python tools/perschar_lists.py
验收：roster 950 行 / 949 唯一槽位 / 5 空槽；modelsets 2,462 行；模型 1,272 行
"""
import csv
import os
import re
import struct
import subprocess
import tempfile
import collections

ROOT = r'D:/BrainMaker/大镖客2解包分析'
SCRIPT = os.path.join(ROOT, 'raw/script_full/1491.50/init_all_sp.c')
META = os.path.join(ROOT, 'raw/sdn/ai/data/ai/ambientpedmodelsets.meta')
# 中间产物（rpf 目录清单缓存）**不落在项目里**，只写系统临时目录
SCRATCH = os.path.join(tempfile.gettempdir(), 'rdr2_perschar_toc')
OUT = os.path.join(ROOT, 'deliverable/manifests')
NAMES_TXT = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
RP_TOOL = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe')
METAPED_DIR = os.path.join(ROOT, 'raw/npc/meta/packs/base/data/metapeds')
METAPED_PACKS = ('metapeds', 'metapeds_sd', 'metapeds_val', 'metapeds_rhd', 'metapeds_asb')

# ---------------------------------------------------------------------------
# 区域 id → 名字
#   证据列（src）三档：
#     script:<文件>      该据点脚本里写死 `Global_1888801[<id>].f_4`（最硬）
#     prefix+code        前缀与本项目据点编码一致（ORA/APF/CHE/WAL/CLE…）
#     prefix+group       perschar 前缀与 ambientpedmodelsets 的 AIMemoryGroup 对得上
#     推断               只有间接线索（如 long_update 的 "ea_logCampRestrict"）
#   官方中文来源：deliverable/manifests/official_names_settlements.csv（.yldb 官方译名）
# ---------------------------------------------------------------------------
ZONE_INFO = {
    -1:  ('',      '',                          '无区域校验',            'func_34 跳过区间检查'),
    3:   ('lag',   'Lagras',                    '拉格拉斯',              'script:lagras.c'),
    5:   ('sdn',   'Saint Denis',               '圣丹尼斯',              'script:saintdenis.c'),
    6:   ('ora',   'Orange Plantation',         '奥兰治种植园',          'prefix+code'),
    9:   ('sha',   'Shady Belle',               '谢迪贝莱',              'script:hideout_shadybelle.c'),
    11:  ('',      'EA Lumber Camp',            '伐木营',                '推断:long_update ea_logCampRestrict'),
    22:  ('pro',   'Pronghorn Ranch',           '叉角羚牧场',            'script:pronghornranch.c'),
    26:  ('str',   'Strawberry',                '草莓镇',                'script:strawberry.c'),
    28:  ('wal',   'Wallace Station',           '华莱士车站',            'prefix+code'),
    32:  ('sis',   'Sisika Penitentiary',       '西西卡监狱',            'script:sisikapenitentiary.c'),
    35:  ('old',   'Fort Wallace',              '华莱士堡',              'script:oldfortwallace.c'),
    37:  ('bee',   "Beecher's Hope",            '比彻之愿',              'script:beechershope.c'),
    38:  ('bla',   'Blackwater',                '黑水镇',                'script:blackwater.c'),
    42:  ('che',   'Chez Porter',               '切兹波特',              'prefix+code'),
    56:  ('wap',   'Wapiti',                    '瓦匹缇',                'script:wapiti.c'),
    57:  ('agu',   'Aguasdulces',               '阿瓜多切斯',            'script:aguasdulces.c'),
    65:  ('cor',   'Cornwall Kerosene & Tar',   '康沃尔煤焦油厂',        'script:cornwallkerosene.c'),
    68:  ('dow',   "Downe's Ranch",             '唐斯牧场',              'script:downsranch.c'),
    69:  ('eme',   'Emerald Ranch',             '翡翠牧场',              'script:emeraldranch.c'),
    76:  ('val',   'Valentine',                 '瓦伦丁',                'script:valentine.c'),
    77:  ('abe',   'Aberdeen Pig Farm',         '阿伯丁猪场',            'prefix+code'),
    78:  ('ann',   'Annesburg',                 '安尼斯堡',              'script:annesburg.c'),
    82:  ('but',   'Butcher Creek',             '布彻河村',              'script:butchercreek.c'),
    92:  ('van',   'Van Horn Trading Post',     '范霍恩贸易站',          'script:vanhorntradingpost.c'),
    93:  ('bra',   'Braithwaite Manor',         '布雷斯韦特庄园',        'script:braithwaitemanor.c'),
    95:  ('cal',   'Caliga Hall',               '卡利加种植园',          'script:caligahall.c'),
    97:  ('cle',   'Clemens Point',             '克莱蒙斯岬',            'prefix+code'),
    105: ('rho',   'Rhodes',                    '罗兹',                  'script:rhodes.c'),
    110: ('man',   'Manzanita Post',            '石兰贸易站',            'script:manzanitapost.c'),
    115: ('tum',   'Tumbleweed',                '风滚草镇',              'script:tumbleweed.c'),
    120: ('arm',   'Armadillo',                 '犰狳镇',                'script:armadillo.c'),
    124: ('rid',   'Ridgewood Farm',            '脊木农场',              'script:ridgewoodfarm.c'),
    126: ('mfr',   "MacFarlane's Ranch",        '麦克法兰牧场',          'prefix+group MACFARLANESRANCH_RESIDENTS'),
    128: ('',      'EA Ranch Camp',             '牧场营地',              '推断:EA_RCAMP 命名'),
}

# ---------------------------------------------------------------------------
# 词素 → 中文（角色语义翻译，**不是**游戏内官方称号）
#   专有名词（人名/地名片段）故意保留原文，宁可留英文也不硬造译名
# ---------------------------------------------------------------------------
TOKEN_ZH = {
    # —— 职业 / 身份 ——
    'WORKER': '工人', 'WAREHOUSE_WORKER': '仓库工人', 'CITY_WORKER': '市政工人',
    'RANCHHAND': '牧场雇工', 'FARMHAND': '农工', 'FARMER': '农夫',
    'RANCHER': '牧场主', 'RANCH': '牧场', 'OWNER': '老板', 'SHOPKEEPER': '店主',
    'GENSHOPKEEPER': '杂货店主', 'POSTMASTER': '邮政所长', 'CLERK': '职员',
    'TRAIN_CLERK': '铁路职员', 'OFFICIAL': '官员', 'BOSS': '头目', 'CHIEF': '长官',
    'SUPERVISOR': '监工', 'FOREMAN': '工头', 'KEEPER': '看守',
    'GROUNDS_KEEPER': '园丁', 'GARDENER': '园丁', 'CARETAKER': '看护',
    'BARTENDER': '酒保', 'BARBER': '理发师', 'DOCTOR': '医生', 'GUNSMITH': '枪匠',
    'BUTCHER': '屠夫', 'BLACKSMITH': '铁匠', 'UNDERTAKER': '殡仪师',
    'TAILOR': '裁缝', 'PHOTOGRAPHER': '摄影师', 'ARTIST': '画家',
    'PIANO_PLAYER': '钢琴师', 'PIANO': '钢琴', 'PLAYER': '演奏者',
    'MUSICIAN': '乐手', 'TRUMPET': '小号', 'HARMONICA': '口琴',
    'VENDOR': '小贩', 'NEWSPAPER_VENDOR': '报童', 'TICKET_VENDOR': '售票员',
    'AUCTION': '拍卖', 'AUCTIONEER': '拍卖师', 'SHERIFF': '警长', 'SHERRIF': '警长',
    'DEPUTY': '副警长', 'POLICE': '警察', 'OFFICER': '军官', 'ENLISTED': '士兵',
    'GUARD': '守卫', 'GATE_GUARD': '门卫', 'BANK_GUARD': '银行守卫',
    'BOAT_GUARD': '船上卫兵', 'HOUSE_GUARD': '宅邸守卫', 'MANOR_GUARD': '庄园守卫',
    'PRISONER': '囚犯', 'PROSTITUTE': '妓女', 'HEAD_PROSTITUTE': '老鸨',
    'DRUNK': '醉汉', 'DRINKER': '酒客', 'GAMBLER': '赌徒', 'GRIEFER': '闹事者',
    'SQUATTER': '占屋者', 'TRAPPER': '捕兽人', 'FISHERMAN': '渔夫',
    'TOURIST': '游客', 'PATRON': '顾客', 'TENANT': '佃户', 'RESIDENT': '居民',
    'HOMEOWNER': '房主', 'TRAINWORKER': '铁路工人', 'TRAINSTATIONWORKER': '车站工人',
    'MINER': '矿工', 'MINE': '矿场', 'CHOPPER': '伐木工', 'LUMBER': '木材',
    'TIMBER': '木料', 'LOADER': '装卸工', 'CARRIER': '搬运工', 'DELIVERY': '送货',
    'DELIVERY_MAN': '送货员', 'MAID': '女佣', 'CLEANER': '清洁工',
    'HOTEL_CLEANER': '旅店清洁工', 'SALOON_CLEANER': '酒馆清洁工',
    'SWEEPER': '清扫工', 'RAKER': '耙草工', 'CHEF': '厨师', 'SOUP': '汤',
    'KITCHEN': '厨房', 'SUPPLY': '补给', 'FREIGHT': '货运', 'CARRIAGE': '马车',
    'WAGON': '货车', 'DRIVER': '车夫', 'RIDER': '骑手', 'HORSE_RIDER': '骑手',
    'HANDYMAN': '杂工', 'HANDYMANS_WIFE': '杂工妻子', 'HELPER': '帮手',
    'ASSISTANT': '助理', 'MANAGER': '经理', 'BANK_MANAGER': '银行经理',
    'MAYOR': '市长', 'TELLER': '出纳', 'POST': '驿', 'LIVERY': '马房',
    'HORSESHOP': '马匹店', 'STABLE': '马厩', 'STABLE_HAND': '马夫',
    'HERD': '牧群', 'PRONGHORN': '叉角羚', 'LAMBERT': '兰伯特',
    'MEDICINEMAN': '巫医', 'SHAMAN': '萨满', 'HEADBRAVE': '勇士首领',
    'SIOUXCHEF': '苏族首领', 'ENLISTED2': '士兵', 'SOLITARY': '独居者',
    'SCAVENGER': '拾荒者', 'ROAMING': '游荡', 'FRIENDLY': '友善',
    # —— 场所 / 分区 ——
    'DOCK': '码头', 'DOCKS': '码头', 'SLUMS': '贫民窟', 'SLUM': '贫民窟',
    'SLUMS_MARKET': '贫民窟市场', 'MARKET': '市场', 'FRENCHMARKET': '法国市场',
    'FRENCH': '法国', 'CHINATOWN': '唐人街', 'TOWN': '镇', 'CITY': '城',
    'LOWERCLASS': '下层阶级', 'MIDDLECLASS': '中产阶级', 'UPPERCLASS': '上层阶级',
    'UPPER_AND_MIDDLE_CLASS': '中上层阶级', 'RURAL': '乡间', 'OUTSKIRTS': '郊外',
    'WILDERNESS': '荒野', 'VALLEY': '山谷', 'PLAINS': '平原', 'PARK': '公园',
    'GARDEN': '花园', 'FIELD': '田地', 'COURTYARD': '庭院', 'MANSION': '宅邸',
    'MANOR': '庄园', 'HOUSE': '房屋', 'HMSTD': '宅地', 'SHACK': '棚屋',
    'TENT': '帐篷', 'BRIDGE': '桥', 'PLANT': '种植园', 'FARM': '农场',
    'ORANGE': '橙', 'COTTON': '棉花', 'COAL': '煤', 'OIL': '石油', 'WOOD': '木',
    'CHURCH': '教堂', 'CEMETERY': '墓地', 'STATION': '车站', 'TRAIN': '火车',
    'BOAT': '船', 'MAIN': '主', 'CENTER': '中心', 'STRIP': '街', 'WALL': '墙',
    'PART': '部分', 'RES': '驻地', 'COM': '社区', 'GEN': '通用',
    'BAR': '酒吧', 'PARLOR': '会客厅', 'HOTEL': '旅店', 'SALOON': '酒馆',
    'STORE': '商店', 'GENERAL_STORE': '杂货铺', 'GROCERY': '杂货',
    'SHOP': '店', 'SHOW': '演出', 'AUCTION_BOSS': '拍卖行老板',
    # —— 关系 / 家庭 ——
    'WIFE': '妻子', 'HUSBAND': '丈夫', 'SON': '儿子', 'DAUGHTER': '女儿',
    'FATHER': '父亲', 'MOTHER': '母亲', 'BROTHER': '兄弟', 'SISTER': '姐妹',
    'GRANDMOTHER': '祖母', 'GRANDFATHER': '祖父', 'LADY': '女士',
    'MAN': '男子', 'WOMAN': '女子', 'MALE': '男', 'FEMALE': '女',
    'TEEN': '少年', 'GIRL': '女孩', 'OLDER': '年长', 'OLD': '老',
    'LAZY': '懒汉', 'SICK': '病人', 'WIDOW': '寡妇', 'FRIEND': '朋友',
    'SHOP_OWNER': '店主', 'HOMEOWNER': '房主', 'WELCOME': '迎宾',
    # —— 动物 ——
    'DOG': '狗', 'CAT': '猫', 'HORSE': '马', 'HORSES': '马', 'COW': '牛',
    'COWS': '牛', 'BULL': '公牛', 'OX': '牛', 'OXEN': '牛', 'PIG': '猪',
    'PIGS': '猪', 'SHEEP': '绵羊', 'LAMB': '羊羔', 'GOAT': '山羊', 'GOATS': '山羊',
    'CHICKEN': '鸡', 'CHICKENS': '鸡', 'ROOSTER': '公鸡', 'ROOSTERS': '公鸡',
    'MULE': '骡', 'DONKEY': '驴', 'DEER': '鹿', 'BUFFALO': '野牛',
    'BEAR': '熊', 'WOLVES': '狼', 'COUGAR': '美洲狮', 'PANTHER': '黑豹',
    'RAVEN': '渡鸦', 'MFR': '麦克法兰',
    # —— 其它 ——
    'CIVIL': '平民', 'CIV': '平民', 'CONSTRUCTION': '建造', 'CONSTR': '建造',
    'DEMO': '拆除', 'CORNWALL': '康沃尔', 'CASTILLE': '卡斯蒂尔',
    'CALIGA': '卡利加', 'GRAYS': '格雷家', 'BRA': '布雷斯韦特',
    'LH': 'LH', 'CORPSE': '尸体', 'EXOTIC': '异域', 'TRAPPER2': '捕兽人',
    'KICK': 'KICK', 'NEG': 'NEG', 'CHOP': '砍', 'CLAY': '克莱', 'CLIVE': '克莱夫',
    'SWANSON': '斯旺森', 'GEDDES': '盖迪斯', 'LANIK': '拉尼克', 'DELL': '戴尔',
    'SOD': '草皮', 'THOMASDOWN': '托马斯·唐斯', 'EDITHDOWN': '伊迪丝·唐斯',
    'ARCHIEDOWN': '阿奇·唐斯', 'LOVE': '爱', 'TRIANGLE': '三角',
    'POST': '驿', 'STAT': '站', 'BRIDGE2': '桥', 'GENERAL': '杂货', 'BANK': '银行',
    # —— 补充（2026-11-02 第二版：把残留英文压下去）——
    'LCMP': '伐木营', 'RCAMP': '牧场营地', 'IND': '印第安', 'HAND': '雇工',
    'WHITE': '白人', 'BLACK': '黑人', 'GATE': '门', 'GANG': '帮派',
    'RID': '脊木', 'DAIRY': '奶牛场', 'LARGE': '大型', 'NORTH': '北',
    'WEST': '西', 'RESIDENTIAL': '住宅区', 'RESIDENTS': '居民',
    'FENCE': '销赃人', 'HANDYMANS': '杂工的', 'FLOWER': '花卉',
    'ENTHUSIAST': '爱好者', 'SHADY': '谢迪', 'GOOD': '好', 'TIME': '时光',
    'TEEN1': '少年1', 'TEEN2': '少年2', 'DELIVERY1': '送货1',
    'DELIVERY2': '送货2', 'DELIVERY3': '送货3', 'F': '女', 'M': '男',
    'PERSCHAR': '', 'SLUMSMARKET': '贫民窟市场', 'NEWSPAPER': '报纸',
    'CARMODY': '卡莫迪', 'HILLHAVEN': '山丘港', 'GRANGER': '格兰杰',
    'LARNED': '拉尼德', 'HILL': '山丘', 'GUTHRIE': '格思里',
    'RIDGEWOOD': '脊木', 'DOWNS': '唐斯', 'MACFARLANE': '麦克法兰',
    # —— 区域前缀作为「第二词素」时也译出来（GLO_BLW_… / GLO_RHD_SDN_… 这种）——
    'SDN': '圣丹尼斯', 'VAL': '瓦伦丁', 'RHD': '罗兹', 'BLW': '黑水镇',
    'VHT': '范霍恩', 'ASB': '安尼斯堡', 'STR': '草莓镇', 'TUM': '风滚草镇',
    'ARM': '犰狳镇', 'BUT': '布彻河村', 'BRA': '布雷斯韦特', 'CGH': '卡利加',
    'LAG': '拉格拉斯', 'ORA': '奥兰治', 'WAP': '瓦匹缇', 'EMR': '翡翠牧场',
    'SIS': '西西卡', 'COR': '康沃尔', 'OFW': '华莱士堡', 'MAN': '石兰',
    'CHE': '切兹波特', 'WAL': '华莱士车站', 'PRO': '叉角羚', 'DOW': '唐斯',
    'BEE': '比彻之愿', 'CLE': '克莱蒙斯岬', 'SHA': '谢迪贝莱', 'AGU': '阿瓜多切斯',
    'HRT': '心田', 'BGV': '大谷', 'GRT': '大平原', 'ROA': '罗诺克',
    'MACLEAN': '麦克林', 'HAGEN': '哈根', 'FLATNECK': '扁颈', 'PAINTED': '彩绘',            # 只是"常驻角色"后缀标记，译出来反而是噪音
    'LAMBERT2': '兰伯特', 'EDITH': '伊迪丝', 'PARK2': '公园',
}

# 多词合并（在逐词翻译前先做最长匹配，读起来更像人话）
PHRASE_ZH = {
    ('GENERAL', 'STORE'): '杂货铺',
    ('TRAIN', 'CLERK'): '铁路职员',
    ('BANK', 'MANAGER'): '银行经理',
    ('BANK', 'GUARD'): '银行守卫',
    ('AUCTION', 'BOSS'): '拍卖行老板',
    ('AUCTION', 'HANDYMAN'): '拍卖行杂工',
    ('AUCTION', 'HAND'): '拍卖行帮工',
    ('DOCK', 'WORKER'): '码头工人',
    ('DOCK', 'COTTON'): '码头棉花工',
    ('DOCK', 'LUMBER'): '码头木材工',
    ('DOCK', 'CONSTR'): '码头建筑工',
    ('DOCK', 'CONSTRUCTION'): '码头建筑工',
    ('DOCK', 'CIVIL'): '码头平民',
    ('DOCK', 'BOAT', 'GUARD'): '码头船卫',
    ('GROUNDS', 'KEEPER'): '园丁',
    ('PIANO', 'PLAYER'): '钢琴师',
    ('NEWSPAPER', 'VENDOR'): '报童',
    ('TICKET', 'VENDOR'): '售票员',
    ('TRAIN', 'STATION', 'WORKER'): '车站工人',
    ('TRAINSTATIONWORKER',): '车站工人',
    ('SHOP', 'OWNER'): '店主',
    ('GENERAL', 'STORE', 'OWNER'): '杂货铺老板',
    ('HORSE', 'SHOP'): '马匹店',
    ('SLUMS', 'MARKET'): '贫民窟市场',
    ('FRENCH', 'MARKET'): '法国市场',
    ('HEAD', 'PROSTITUTE'): '老鸨',
    ('HOTEL', 'CLEANER'): '旅店清洁工',
    ('HOTEL', 'OWNER'): '旅店老板',
    ('SALOON', 'CLEANER'): '酒馆清洁工',
    ('UPPER', 'CLASS'): '上层阶级',
    ('TOWN', 'DRUNK'): '镇上的醉汉',
    ('TOWN', 'WORKER'): '镇上的工人',
    ('TOWN', 'DOG'): '镇上的狗',
    ('SHERIFF', 'HELPER'): '警长助手',
    ('SLUM', 'BARTENDER'): '贫民窟酒保',
    ('DELIVERY', 'MAN'): '送货员',
    ('FLOWER', 'ENTHUSIAST'): '花卉爱好者',
    ('GOOD', 'TIME', 'GIRL'): '陪酒女',
    ('SHADY', 'BELLE'): '谢迪贝莱',
    ('HANDYMANS', 'WIFE'): '杂工妻子',
    ('RESIDENTIAL', 'SHEEP'): '住宅区绵羊',
    ('CARMODY', 'DELL'): '卡莫迪戴尔',
    ('HILL', 'HAVEN', 'RANCH'): '山丘港牧场',
}


def name_zh(name, zone_zh):
    """name → 可读中文：区域·角色（角色内多词已合并）"""
    toks = name.split('_')
    pre = toks[0]
    # 首词素一般是区域前缀（SDN_/ASB_…）→ 丢掉；但下面这些「地名本身的首词」要留着
    KEEP = ('CARMODY', 'HILL', 'MACLEAN', 'HAGEN', 'GRANGER', 'PAINTED', 'FLATNECK',
            'LARNED', 'GUTHRIE', 'RIDGEWOOD', 'DOWNS', 'MACFARLANE')
    body = toks if (pre in KEEP or pre in ('', 'ILO')) else toks[1:]
    parts = []
    i = 0
    while i < len(body):
        if body[i].isdigit():
            parts.append(body[i])
            i += 1
            continue
        for span in (3, 2):
            key = tuple(body[i:i + span])
            if span <= len(body) - i and key in PHRASE_ZH:
                parts.append(PHRASE_ZH[key])
                i += span
                break
        else:
            t = body[i]
            zh_t = TOKEN_ZH.get(t)
            if zh_t is None:
                # FARMHAND4 / OFFICER2 / SON1 这类「词干+序号」
                m = re.fullmatch(r'([A-Z][A-Z0-9_]*?)(\d+)', t)
                if m and m.group(1) in TOKEN_ZH:
                    zh_t = TOKEN_ZH[m.group(1)] + m.group(2)
            if zh_t is None:
                zh_t = t                      # 专有名词（人名/未定前缀）保留原文
            if zh_t:
                parts.append(zh_t)
            i += 1
    role = '·'.join(parts)
    if zone_zh and zone_zh != '无区域校验':
        if role == zone_zh:                      # EA_LCMP_* → 伐木营·伐木营·工头 这种重复要去掉
            return zone_zh
        if role.startswith(zone_zh + '·'):
            return role
        return '%s·%s' % (zone_zh, role)
    return role


# ---------------------------------------------------------------------------
# 真名：`_SET_PLAYER_HAS_DISCOVERED_CHARACTER_NAME_SP()` 的**人物名键**
#
#   perschar 槽位只有**职能名**（`VAL_SHERIFF`）。真实姓名走另一套「人物名键」，
#   由悬赏海报 / 任务触发 `PLAYER::_SET_PLAYER_HAS_DISCOVERED_CHARACTER_NAME_SP()` 解锁。
#   一共 3 个命名空间（2026-11-02 实测）：`DISCOVERABLE_NAME_*` 90 个、`ALLY_*` 6 个、`COMP_*` 2 个。
#   英文名 = 脚本里的 GXT 注释（`/* GXT: Sheriff Malloy */`）；中文名 = `global.yldb`（官方译名）。
# ---------------------------------------------------------------------------
# 手工挂接：perschar 槽位 → (人物名键, 证据)
# 证据都是**官方文本自己写出来的**「某镇 + 某职务 + 某人名」，不是我看名字猜的
REAL_NAMES = {
    # perschar: (人物名键, 全名英文, 全名中文, 证据)
    'VAL_SHERIFF': ('DISCOVERABLE_NAME_CURTIS_MALLOY', 'Curtis Malloy', '柯蒂斯·马洛伊',
                    'global.yldb「C·马洛伊警长。瓦伦丁警长办公室」+ main.c「Letter to Curtis from M」'),
    'SDN_POLICE_CHIEF': ('DISCOVERABLE_NAME_BENJAMIN_LAMBERT', 'Benjamin Lambert', '本杰明·兰伯特',
                         'global.yldb「发自圣丹尼斯警长办公室…B·兰伯特」「兰伯特警长…有轨电车站」'),
    'BLW_POLICE_CHIEF': ('DISCOVERABLE_NAME_OSWALD_DUNBAR', 'Oswald Dunbar', '奥斯瓦尔德·邓巴',
                         'global.yldb「O·邓巴警长，黑水镇警局」'),
    'STR_SHERIFF': ('DISCOVERABLE_NAME_VERNON_FARLEY', 'Vernon Farley', '弗农·法利',
                    'global.yldb「V·法利…所有赏金都由草莓镇警局警长支付」'),
    'RHD_SHERIFF': ('ALLY_LEIGHGRAY', 'Leigh Gray', '利·格雷',
                    '脚本 GXT「Sheriff Gray」+ 官方中文「格雷警长」「追上利」「利死了」「格雷家族」；罗兹即 Gray 家地盘'),
    'RHD_DEPUTY': ('ALLY_ARCHIBALD', 'Archibald MacGregor', '阿奇伯德·麦格雷戈',
                   'fud1aud.yldb「这是我的副手，阿奇伯德·麦格雷戈」+ GXT「Deputy MacGregor」'),
    # 槽位名把 SHERIFF 拼成了 SHERRIF（少一个 F），grep "TBL_SHERIFF" 会漏掉它
    'TBL_SHERRIF': ('DISCOVERABLE_NAME_SHERIFF_FREEMAN', 'Samuel Freeman', '萨缪尔·弗里曼',
                    '风滚草镇警长 is Freeman：global.yldb 城镇介绍「风滚草镇由专横，严苛的弗里曼警长统治着」、'
                    '悬赏信落款「弗里曼警长，风滚草镇警长办公室」、整支支线 spd_sheriffoftumbleweed.c（CS_SHERIFFFREEMAN）；'
                    '⚠️ 名 Samuel 来自外部资料（用户提供），数据里只有姓'),
}
# 外部资料补充的全名（**游戏数据里没有**，单独标来源；别混进上面那张实证表）
EXTRA_FULL_NAMES = {
    'DISCOVERABLE_NAME_SHERIFF_FREEMAN': (
        'Samuel Freeman', '萨缪尔·弗里曼',
        '用户提供（2026-11-02）；游戏数据里只出现过姓 Freeman —— '
        '已搜 1,639 个脚本 / names.txt 29.4 万条 / global.yldb 21,733 条，均无 Samuel'),
}
REAL_NAME_SKIP = {'BANK_TELLER'}     # 机械匹配到的通用称呼，不算真名


def parse_discoverable():
    """扫全部脚本 → {KEY: {en, n, files}}；中文从 global.yldb 取"""
    import official_name_map as onm
    en_map = onm.scan(onm.EN)
    zh_map = onm.scan(onm.ZH)
    pat = re.compile(r'_SET_PLAYER_HAS_DISCOVERED_CHARACTER_NAME_SP\([^;]*?'
                     r'GET_HASH_KEY\("([A-Z][A-Z0-9_]+)"\s*/\* GXT: (.*?)\s*\*/', re.S)
    out = {}
    d = os.path.dirname(SCRIPT)
    for fn in sorted(os.listdir(d)):
        if not fn.endswith('.c'):
            continue
        txt = open(os.path.join(d, fn), encoding='utf-8', errors='replace').read()
        for m in pat.finditer(txt):
            key, gxt = m.group(1), m.group(2)
            e = out.setdefault(key, {'en': gxt, 'n': 0, 'files': set()})
            e['n'] += 1
            e['files'].add(fn)
    for key, e in out.items():
        h = joaat(key)
        e['zh'] = zh_map.get(h) or ''
        e['zh_en_from_yldb'] = en_map.get(h) or ''
    return out


def real_name_of(name, dn):
    """perschar 名 → (人物名键, 证据)；先查手工表，再试「去区域前缀」机械匹配"""
    if name in REAL_NAMES:
        k, _en, _zh, why = REAL_NAMES[name]
        return (k, why)
    toks = name.split('_')
    for i in (1, 2):
        suffix = '_'.join(toks[i:])
        if suffix in REAL_NAME_SKIP:
            continue
        cand = 'DISCOVERABLE_NAME_' + suffix
        if cand in dn:
            return (cand, '机械匹配：去掉区域前缀后与 DISCOVERABLE 键同名')
    return ('', '')


def ensure_toc():
    """TOC 不存在就现跑 rdr2rpf list（只读 TOC，不抽内容，秒级）"""
    os.makedirs(SCRATCH, exist_ok=True)
    for p in METAPED_PACKS:
        dst = os.path.join(SCRATCH, 'toc_%s.txt' % p)
        if os.path.exists(dst):
            continue
        rpf = os.path.join(METAPED_DIR, '%s.rpf' % p)
        if not os.path.exists(rpf) or not os.path.exists(RP_TOOL):
            print('[warn] 缺 %s 或缺 rdr2rpf，跳过 %s' % (rpf, p))
            continue
        with open(dst, 'w', encoding='utf-8', errors='replace') as f:
            subprocess.run([RP_TOOL, 'list', rpf], stdout=f,
                           stderr=subprocess.STDOUT, check=False)
        print('[toc] %s' % dst)


def joaat(s):
    h = 0
    for ch in s.lower():
        h = (h + ord(ch)) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h


# ---------------------------------------------------------------- perschar 名单
RE_ROSTER = re.compile(r'func_34\((.*?),\s*joaat\("([^"]+)"\),\s*(-?\d+),\s*(.*?)\);')


def parse_zone_ranges(txt):
    """func_146：区域 id → [start, end]。start=第一个 uParam1；end=该 case 里 uParam2 的最大值
    （锁定版/线上版只会把区间收窄，取最大即单人完整区间）。"""
    m = re.search(r'int func_146\(int iParam0,.*?\n\{', txt, re.S)
    start = m.end()
    body = txt[start:start + 60000]
    ranges = {}
    for cm in re.finditer(r'case (\d+):(.*?)break;', body, re.S):
        zid = int(cm.group(1))
        blk = cm.group(2)
        s = re.search(r'\*uParam1 = (-?\d+);', blk)
        ends = [int(x) for x in re.findall(r'\*uParam2 = (-?\d+);', blk)]
        if s and ends:
            ranges[zid] = (int(s.group(1)), max(ends))
    return ranges


def eval_flags(raw):
    """把 `0` / `256` / `(1 << 22)` / `(1 << 20) | 2` 这类表达式算成整数"""
    expr = raw.replace('(', '').replace(')', '')
    total = 0
    for part in expr.split('|'):
        part = part.strip()
        m = re.fullmatch(r'1\s*<<\s*(\d+)', part)
        if m:
            total |= 1 << int(m.group(1))
        elif re.fullmatch(r'\d+', part):
            total |= int(part)
    return total


def flag_meaning(bits):
    out = []
    if 8 in bits:
        out.append('bit8(未知,动物共用)')
    if 20 in bits:
        out.append('shop/service')
    if 21 in bits:
        out.append('law')
    if 22 in bits:
        out.append('allow-out-of-range')
    return '|'.join(out)


def bits_of(v):
    return [b for b in range(32) if v & (1 << b)]


def lo_hi_bad(r, ranges):
    rng = ranges.get(r['zone'])
    if not rng:
        return False
    return not (rng[0] <= r['index'] <= rng[1])


def load_roster():
    txt = open(SCRIPT, encoding='utf-8', errors='replace').read()
    ranges = parse_zone_ranges(txt)
    rows = []
    for m in RE_ROSTER.finditer(txt):
        idx = eval_flags(m.group(1))
        line = txt.count('\n', 0, m.start()) + 1
        rows.append({
            'index': idx,
            'index_expr': ('' if m.group(1).strip().isdigit() else m.group(1).strip()),
            'name': m.group(2),
            'zone': int(m.group(3)),
            'flags_raw': m.group(4).strip(),
            'flags': eval_flags(m.group(4)),
            'line': line,
        })
    return rows, ranges


# ---------------------------------------------------------------- 环境人群
RE_SET = re.compile(r'<Item type="CAmbientModelSet">(.*?)</Item>\s*(?=<Item type="CAmbientModelSet">|<Item type="CAmbientModelSet"|\Z)', re.S)


def parse_modelsets():
    txt = open(META, encoding='utf-8', errors='replace').read()
    # 用行号定位，保证 source_line 可用
    sets = []
    pos = 0
    lines = txt.split('\n')
    # 手工扫描：以 <Item type="CAmbientModelSet"> 起，到下一个同级 <Item type="CAmbientModelSet"> 或结尾
    starts = [i for i, l in enumerate(lines) if 'type="CAmbientModelSet"' in l]
    starts.append(len(lines))
    for k in range(len(starts) - 1):
        a, b = starts[k], starts[k + 1]
        blk = '\n'.join(lines[a:b])
        name_m = re.search(r'<Name>([^<]+)</Name>', blk)
        if not name_m:
            continue
        dist = re.search(r'<SpawnDistance value="([0-9.]+)"', blk)
        grp = re.search(r'<AIMemoryGroup>([^<]+)</AIMemoryGroup>', blk)
        models = []
        for mm in re.finditer(r'<Item>\s*<Name>([^<]+)</Name>(.*?)</Item>', blk, re.S):
            body = mm.group(2)
            lod = re.search(r'<LoadOut>([^<]*)</LoadOut>', body)
            outfit = re.search(r'<Outfit>([^<]*)</Outfit>', body)
            rarity = re.search(r'<RarityLevel>([^<]*)</RarityLevel>', body)
            prob = re.search(r'<Probability value="([0-9.]+)"', body)
            tod = re.search(r'<TimeOfDay>([^<]+)</TimeOfDay>', body)
            models.append({
                'model': mm.group(1).strip(),
                'probability': prob.group(1) if prob else '',
                'loadout': lod.group(1).strip() if lod else '',
                'outfit': outfit.group(1).strip() if outfit else '',
                'rarity': rarity.group(1).strip() if rarity else '',
                'time_of_day': tod.group(1).strip() if tod else '',
            })
        sets.append({
            'set': name_m.group(1).strip(),
            'spawn_distance': dist.group(1) if dist else '',
            'group': grp.group(1).strip() if grp else '',
            'models': models,
            'line': a + 1,
        })
    return sets


# ---------------------------------------------------------------- metaped 目录
RE_TOC = re.compile(r'\s*(\d+)\s+res=\d+\s+comp=(\S+)\s+(\S+)\.ymt\s*$')


def load_metapeds():
    out = []
    for fn in sorted(os.listdir(SCRATCH)):
        if not fn.startswith('toc_metapeds'):
            continue
        pkg = fn[len('toc_'):-4]
        for line in open(os.path.join(SCRATCH, fn), encoding='utf-8', errors='replace'):
            m = RE_TOC.match(line)
            if m:
                out.append({'model': m.group(3), 'package': pkg,
                            'size': int(m.group(1)), 'comp': m.group(2)})
    return out


def model_kind(n):
    nl = n.lower()
    if nl.startswith('cs_') or nl.startswith('player_'):
        return 'cutscene/player'
    if re.match(r'a_[mfo]_', nl):
        return 'ambient human'
    if re.match(r'^(s|g|u|mp|re|mes|rcsp)_[mfo]_', nl):
        return 'scripted/gang/unique'
    if re.match(r'^a_f_|^a_m_', nl):
        return 'ambient'
    if re.match(r'^a_c_', nl):
        return 'animal'
    if re.match(r'^(a|s|g|u)_[a-z]_', nl):
        return 'other'
    return 'other'


def main():
    os.makedirs(OUT, exist_ok=True)
    ensure_toc()
    roster, ranges = load_roster()
    dn = parse_discoverable()          # 95 个「真名」键（GXT 英文 + yldb 官方中文）
    names = {}
    with open(NAMES_TXT, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if line:
                names[joaat(line)] = line

    # 每区的前缀画像
    zone_prefix = collections.defaultdict(collections.Counter)
    for r in roster:
        pre = r['name'].split('_')[0]
        zone_prefix[r['zone']][pre] += 1

    # ---- perschar_roster.csv
    fields = ['index', 'index_expr', 'name', 'name_zh', 'role_zh',
              'real_name_en', 'real_name_zh', 'full_name_en', 'full_name_zh',
              'real_name_evidence',
              'zone_id', 'zone_code', 'zone_name_en', 'zone_name_zh', 'zone_name_source',
              'zone_min', 'zone_max', 'in_zone_range',
              'zone_top_prefix', 'zone_name_counts', 'flags_raw', 'flags_dec',
              'flag_bits', 'flag_meaning', 'source_line', 'note']
    with open(os.path.join(OUT, 'perschar_roster.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        seen = collections.Counter(r['name'] for r in roster)
        for r in sorted(roster, key=lambda x: x['index']):
            lo, hi = ranges.get(r['zone'], ('', ''))
            zone = ZONE_INFO.get(r['zone'], ('', '', '未定', ''))
            zcode, zen, zzh, zsrc = zone
            if not zzh:
                zzh = '未定'
            if r['zone'] == -1:
                ok = True
                zr = 'n/a(zone=-1 不做区间校验)'
            else:
                ok = (lo != '' and lo <= r['index'] <= hi)
                zr = 'Y' if ok else 'N'
            cnt = zone_prefix[r['zone']]
            note = []
            if not ok:
                if r['flags'] & (1 << 22):
                    note.append('超出区区间，但带 1<<22 豁免 ⇒ 仍注册')
                else:
                    note.append('超出区区间且无豁免 ⇒ 运行时被 func_34 丢弃')
            if seen[r['name']] > 1:
                note.append('同名跨区复用×%d' % seen[r['name']])
            if r['zone'] != -1 and r['zone'] not in ranges:
                note.append('func_146 里没有该区区间')
            if cnt and not r['name'].startswith(tuple(p for p, _ in cnt.most_common(3))):
                note.append('命名不合本区前缀（疑似错位/复用）')
            if zzh == '未定' and cnt:
                zzh_disp = '未定（前缀 %s）' % cnt.most_common(1)[0][0]
                zh = name_zh(r['name'], '')
            else:
                zzh_disp = zzh
                zh = name_zh(r['name'], zzh if zzh != '未定' else '')
            rk, rn_why = real_name_of(r['name'], dn)
            rn = dn.get(rk, {})
            rn_en, rn_zh = rn.get('en', ''), rn.get('zh', '')
            full = REAL_NAMES.get(r['name'])
            full_en, full_zh = (full[1], full[2]) if full else ('', '')
            role_only = name_zh(r['name'], '')
            if rn_zh:                       # 有官方真名 ⇒ 直接用它（比职能名可读得多）
                zh = ('%s·%s' % (zzh_disp, rn_zh)) if (zzh_disp and zzh_disp not in ('未定', '无区域校验')
                                                       and not zzh_disp.startswith('未定')) else rn_zh
            w.writerow({
                'index': r['index'], 'index_expr': r.get('index_expr', ''),
                'name': r['name'], 'name_zh': zh,
                'role_zh': role_only,
                'real_name_en': rn_en, 'real_name_zh': rn_zh,
                'full_name_en': full_en, 'full_name_zh': full_zh,
                'real_name_evidence': rn_why,
                'zone_id': r['zone'],
                'zone_code': zcode, 'zone_name_en': zen, 'zone_name_zh': zzh_disp,
                'zone_name_source': zsrc,
                'zone_min': lo, 'zone_max': hi, 'in_zone_range': zr,
                'zone_top_prefix': cnt.most_common(1)[0][0] if cnt else '',
                'zone_name_counts': ' '.join('%s×%d' % (p, c) for p, c in cnt.most_common(4)),
                'flags_raw': r['flags_raw'], 'flags_dec': r['flags'],
                'flag_bits': ' '.join(str(b) for b in bits_of(r['flags'])),
                'flag_meaning': flag_meaning(bits_of(r['flags'])),
                'source_line': r['line'], 'note': '; '.join(note),
            })

    # ---- perschar_by_zone.csv
    with open(os.path.join(OUT, 'perschar_by_zone.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['zone_id', 'zone_code', 'zone_name_en', 'zone_name_zh', 'zone_name_source',
                    'zone_min', 'zone_max', 'registered', 'shop', 'law',
                    'top_prefixes', 'sample_names_zh', 'sample_names'])
        for zid in sorted(set([r['zone'] for r in roster])):
            rows = [r for r in roster if r['zone'] == zid]
            lo, hi = ranges.get(zid, ('', ''))
            cnt = collections.Counter(r['name'].split('_')[0] for r in rows)
            zcode, zen, zzh, zsrc = ZONE_INFO.get(zid, ('', '', '未定', ''))
            if zzh == '未定' and cnt:
                zzh = '未定（前缀 %s）' % cnt.most_common(1)[0][0]
            ordered = sorted(rows, key=lambda x: x['index'])
            w.writerow([zid, zcode, zen, zzh or '未定', zsrc, lo, hi, len(rows),
                        sum(1 for r in rows if r['flags'] & (1 << 20)),
                        sum(1 for r in rows if r['flags'] & (1 << 21)),
                        ' '.join('%s×%d' % (p, c) for p, c in cnt.most_common(5)),
                        ', '.join(name_zh(r['name'], zzh if zzh != '未定' else '')
                                  for r in ordered[:4]),
                        ', '.join(r['name'] for r in ordered[:6])])

    # ---- ped_model_catalog.csv（含「被多少环境模型集引用」）
    sets = parse_modelsets()
    used = collections.Counter()
    for s in sets:
        for m in s['models']:
            used[m['model'].lower()] += 1
    mps = load_metapeds()
    with open(os.path.join(OUT, 'ped_model_catalog.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['model', 'package', 'kind', 'rpf_entry_size', 'compression',
                    'name_hash', 'used_by_n_modelsets'])
        for m in sorted(mps, key=lambda x: (x['package'], x['model'])):
            w.writerow([m['model'], m['package'], model_kind(m['model']),
                        m['size'], m['comp'], '0x%08X' % joaat(m['model']),
                        used.get(m['model'].lower(), 0)])

    # ---- ambient_modelsets.csv（长表）
    with open(os.path.join(OUT, 'ambient_modelsets.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['set_name', 'ai_memory_group', 'spawn_distance', 'model', 'probability',
                    'loadout', 'outfit', 'rarity', 'time_of_day', 'set_source_line'])
        for s in sets:
            if not s['models']:
                w.writerow([s['set'], s['group'], s['spawn_distance'], '', '', '', '', '',
                            '', s['line']])
            for m in s['models']:
                w.writerow([s['set'], s['group'], s['spawn_distance'], m['model'],
                            m['probability'], m['loadout'], m['outfit'], m['rarity'],
                            m['time_of_day'], s['line']])

    # ---- ambient_modelsets_summary.csv
    with open(os.path.join(OUT, 'ambient_modelsets_summary.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['set_name', 'ai_memory_group', 'spawn_distance', 'num_models',
                    'models', 'outfits', 'rarities', 'source_line'])
        for s in sets:
            w.writerow([s['set'], s['group'], s['spawn_distance'], len(s['models']),
                        ' | '.join(m['model'] for m in s['models']),
                        ' | '.join(sorted(set(m['outfit'] for m in s['models'] if m['outfit']))),
                        ' | '.join(sorted(set(m['rarity'] for m in s['models'] if m['rarity']))),
                        s['line']])

    # ---- ambient_by_group.csv
    g = collections.defaultdict(lambda: {'sets': 0, 'models': 0, 'dist': collections.Counter()})
    for s in sets:
        k = s['group'] or '(none)'
        g[k]['sets'] += 1
        g[k]['models'] += len(s['models'])
        g[k]['dist'][s['spawn_distance']] += 1
    with open(os.path.join(OUT, 'ambient_by_group.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['ai_memory_group', 'num_sets', 'num_model_entries', 'spawn_distance_mix'])
        for k, v in sorted(g.items(), key=lambda kv: -kv[1]['sets']):
            w.writerow([k, v['sets'], v['models'],
                        ' '.join('%sm×%d' % (d, c) for d, c in sorted(v['dist'].items()))])

    # ---- discoverable_names.csv（「真名」表：95 条）
    dn_users = collections.defaultdict(list)
    for r in roster:
        k, _ = real_name_of(r['name'], dn)
        if k:
            dn_users[k].append(r['name'])
    with open(os.path.join(OUT, 'character_names.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['key', 'namespace', 'name_en', 'name_zh', 'name_zh_source',
                    'full_name_en', 'full_name_zh', 'full_name_source', 'n_refs',
                    'scripts', 'perschar_slots'])
        for k in sorted(dn, key=lambda x: (x.split('_')[0], dn[x]['en'])):
            e = dn[k]
            ex = EXTRA_FULL_NAMES.get(k, ('', '', ''))
            w.writerow([k, k.split('_')[0], e['en'], e['zh'],
                        'global.yldb' if e['zh'] else '',
                        ex[0], ex[1], ex[2] if ex[0] else '', e['n'],
                        ' '.join(sorted(e['files'])[:5]),
                        ' '.join(dn_users.get(k, []))])

    # ---- 控制台汇总
    print('perschar 注册    :', len(roster), '（去重名 %d）' % len(set(r['name'] for r in roster)))
    print('区域数            :', len(set(r['zone'] for r in roster)), '有区间定义:', len(ranges))
    bad = [r for r in roster if r['zone'] != -1 and lo_hi_bad(r, ranges)]
    print('索引越界          :', len(bad),
          '（其中带 1<<22 豁免 = %d）' % sum(1 for b in bad if b['flags'] & (1 << 22)),
          [b['name'] for b in bad][:8])
    print('zone=-1（不校验）  :', sum(1 for r in roster if r['zone'] == -1))
    print('模型集            :', len(sets), '模型条目:', sum(len(s['models']) for s in sets))
    print('空模型集          :', sum(1 for s in sets if not s['models']))
    print('metaped 模型      :', len(mps), '去重:', len(set(m['model'] for m in mps)))
    print('被环境人群用到    :', len(used), '个模型名')
    print('人物名键          :', len(dn), '（DISCOVERABLE/ALLY/COMP 三套；有中文 %d）'
          % sum(1 for v in dn.values() if v['zh']))
    print('→', OUT)


if __name__ == '__main__':
    main()
