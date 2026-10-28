# -*- coding: utf-8 -*-
"""RDR2 → 骑砍2 落地表：据点层级 / 村庄依附 / 势力归属 / 具名 NPC 名册。

输出：
  export/levels/world/settlements_bannerlord.csv
  export/levels/world/settlements_bannerlord.json
  export/levels/world/npc_roster.csv
  export/levels/world/factions.json
"""
import json, os, csv, math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)

FACTIONS = {
    "US":   {"zh": "联邦秩序", "en": "United States", "color": "#2f6fd0",
             "desc": "联邦政府 + 平克顿侦探社 + 地方镇公所；代表‘法律与秩序’"},
    "COR":  {"zh": "康沃尔工业帝国", "en": "Cornwall United", "color": "#d08a1e",
             "desc": "铁路/煤油/矿业资本；安尼斯堡与煤油厂是它的核心资产"},
    "LEM":  {"zh": "莱莫恩庄园联盟", "en": "Lemoyne Planters", "color": "#8e3b46",
             "desc": "南方老钱：布莱斯韦特 + 格雷两大家族 + 圣丹尼斯勃朗特黑帮"},
    "VDL":  {"zh": "范德林德帮", "en": "Van der Linde Gang", "color": "#2e9e5b",
             "desc": "玩家势力；没有城镇，只有随章节迁移的营地"},
    "OUT":  {"zh": "边陲匪帮联盟", "en": "Frontier Outlaws", "color": "#6b4a8f",
             "desc": "奥德里斯科尔/德尔·洛博/默弗里/剥皮兄弟/莱莫恩掠夺者/夜行人"},
    "WAP":  {"zh": "瓦匹缇部落", "en": "Wapiti Tribe", "color": "#c25b2a",
             "desc": "印第安保留地；落雨与飞鹰的部落"},
    "GUA":  {"zh": "瓜玛军政府", "en": "Guarma Junta", "color": "#1f9e9e",
             "desc": "富萨尔的军事独裁 + 赫尔克里领导的反抗军"},
    "FREE": {"zh": "自由市镇", "en": "Free Towns", "color": "#8a8f98",
             "desc": "无王国、无治安的独立据点（范霍恩）"},
}

# code: (type, bound_to, faction, clan, owner, note)
BIND = {
    # ── 城市 Town（10）────────────────────────────────────────
    "sdn":  ("town", "", "LEM", "勃朗特家族", "安吉洛·勃朗特", "名义上市政自治，实际是勃朗特黑帮的地盘"),
    "val":  ("town", "", "US", "瓦伦丁镇公所", "瓦伦丁警长（马洛伊）", "畜牧镇；联邦法律只到警长这一级"),
    "rho":  ("town", "", "LEM", "格雷家族", "利·格雷", "格雷与布莱斯韦特两家争夺的烟草镇"),
    "ann":  ("town", "", "COR", "康沃尔公司", "利维提克斯·康沃尔", "公司镇；矿工、铁路、煤油都归康沃尔"),
    "bla":  ("town", "", "US", "黑水镇公所", "黑水镇警察局长", "西部交通枢纽；平克顿在此活动频繁"),
    "str":  ("town", "", "US", "草莓镇公所", "草莓镇警长", "山谷小镇；全镇只有一条主街"),
    "van":  ("town", "", "FREE", "范霍恩自由民", "无（无治安）", "无警长、无银行，码头由帮派抽税"),
    "arm":  ("town", "", "US", "犰狳镇公所", "犰狳镇副警长", "荒漠镇；霍乱疫情后人口锐减"),
    "tum":  ("town", "", "US", "风滚草镇公所", "弗里曼警长", "荒漠镇+监狱；边陲秩序的最后据点"),
    "agu":  ("town", "", "GUA", "富萨尔军政府", "阿尔贝托·富萨尔", "瓜玛岛唯一集镇，军政府驻地"),
    # ── 城堡 Castle（8）──────────────────────────────────────
    "bra":  ("castle", "", "LEM", "布莱斯韦特家族", "凯瑟琳·布雷斯韦特", "宅邸+庭院+林荫道，可当 1200 城堡主体"),
    "cal":  ("castle", "", "LEM", "格雷家族", "塔维什·格雷", "大宅+农田，格雷家族的根基"),
    "old":  ("castle", "", "US", "联邦军", "门罗上尉", "华莱士堡；联邦军在边境的唯一常驻要塞"),
    "fom":  ("castle", "", "OUT", "德尔·洛博帮", "德尔·洛博帮首领（未具名）", "峡谷土堡，被德尔·洛博帮占据"),
    "sis":  ("castle", "", "US", "西西卡监狱", "西西卡典狱长（未具名）", "河心岛监狱；只能坐船进入"),
    "han":  ("castle", "", "OUT", "奥德里斯科尔帮", "科尔姆·奥德里斯科", "大山谷的 fortified ranch，奥德里斯科尔据点"),
    "cor":  ("castle", "", "COR", "康沃尔公司", "利维提克斯·康沃尔", "炼油厂+工人村，围墙+烟囱，工业城堡"),
    "wap":  ("castle", "", "WAP", "瓦匹缇部落", "落雨", "印第安保留地；帐篷+围栏，按‘部落城堡’处理"),
    # ── 村庄 Village（20，全部有主）──────────────────────────
    "lag":  ("village", "sdn", "LEM", "圣丹尼斯市政", "拉格拉斯村长（未具名）", "沼泽渔村，向圣丹尼斯供鱼"),
    "ora":  ("village", "bra", "LEM", "布莱斯韦特家族", "奥兰治种植园管事（未具名）", "距庄园 1291m，但叙事上是布莱斯韦特家的种植园（同一势力），保留依附"),
    "lon":  ("poi", "", "LEM", "格雷家族", "朗尼（未具名）", "34×35m 独屋，非聚落，改为野外点位"),
    "dewclm": ("village", "rho", "LEM", "格雷家族", "露莓溪农户（未具名）", "罗兹外围的溪边农舍"),
    "eme":  ("castle", "", "US", "翡翠牧场", "翡翠牧场主（未具名）", "距瓦伦丁 1772m，不强行依附；大牧场+车站，升级为城堡"),
    "dow":  ("village", "val", "US", "唐恩家族", "唐斯牧场主（未具名）", "草原小牧场"),
    "man":  ("village", "bla", "US", "曼萨尼塔贸易站", "曼萨尼塔站长（未具名）", "高树区边境哨站"),
    "bee":  ("village", "bla", "US", "马斯顿家族", "约翰·马斯顿", "终章家园；可建造"),
    "wal":  ("village", "str", "US", "中央铁路公司", "华莱士车站站长（未具名）", "火车站；站房+月台"),
    "pro":  ("village", "str", "US", "叉角羚牧场", "叉角羚牧场主（未具名）", "山谷小牧场"),
    "mfr":  ("castle", "", "US", "麦克法兰家族", "麦克法兰牧场主（未具名）", "距犰狳镇 1271m，不强行依附；加固牧场，升级为城堡"),
    "roc":  ("poi", "", "LEM", "布莱斯韦特家族", "夏洛蒂·贝尔福", "威拉德之息；夏洛蒂线唯一场景"),
    "hso":  ("camp", "", "VDL", "范德林德帮", "达奇·范德林德", "马掌望台；第 2 章营地"),
    "abe":  ("poi", "", "FREE", "阿伯丁家族", "阿伯丁兄妹（未具名）", "阿伯丁猪场；黑店支线"),
    "twi":  ("poi", "", "OUT", "德尔·洛博帮", "双子岩营地（未具名）", "荒漠小营地，非聚落，改为野外点位"),
    "rid":  ("village", "arm", "US", "脊木农场", "脊木农场主（未具名）", "荒漠农场"),
    "rat":  ("poi", "", "FREE", "岔路酒馆自由民", "岔路酒馆店主（未具名）", "荒漠小驿站，非聚落，改为野外点位"),
    "col":  ("camp", "", "VDL", "范德林德帮", "达奇·范德林德", "第 1 章营地；雪山废弃矿村，之后废弃"),
    "adl":  ("castle", "", "US", "阿德勒家族", "阿德勒先生", "距华莱士堡 1493m，不强行依附；雪山孤宅，升级为小型城堡"),
    "che":  ("village", "old", "US", "波特家族", "切斯·波特（未具名）", "山间农舍，可入室"),
    "sod":  ("poi", "", "COR", "康沃尔公司", "草皮屋住户（未具名）", "15×14m 独屋，非聚落，改为野外点位"),
    "but":  ("village", "ann", "COR", "康沃尔公司", "布彻河村村长（未具名）", "被矿场污染的村落"),
    "gua":  ("village", "agu", "GUA", "瓜玛反抗军", "赫尔克里", "瓜玛岛临时营地/反抗军落脚点"),
    # ── 玩家营地（3）─────────────────────────────────────────
    "cle":  ("camp", "", "VDL", "范德林德帮", "达奇·范德林德", "第 3 章营地；湖岸+码头"),
    "sha":  ("camp", "", "VDL", "范德林德帮", "达奇·范德林德", "第 4 章营地；沼泽庄园"),
    "lak":  ("camp", "", "VDL", "范德林德帮", "达奇·范德林德", "第 4 章过渡营地；沼泽村落"),
    # ── 藏身处（2）───────────────────────────────────────────
    "mic":  ("hideout", "", "OUT", "迈卡帮", "迈卡·贝尔", "迈卡藏身处"),
    "gap":  ("hideout", "", "OUT", "德尔·洛博帮", "德尔·洛博帮首领（未具名）", "荒漠矿洞，帮派据点"),
}

NPC = [
    # id, en, cn, tier, faction, clan, home, role, confidence
    # ── 范德林德帮 ────────────────────────────────────────────
    ("player_zero", "Arthur Morgan", "亚瑟·摩根", "S", "VDL", "范德林德帮", "范德林德营地（随章节迁移）", "主角", "高"),
    ("player_three", "John Marston", "约翰·马斯顿", "S", "VDL", "马斯顿家族", "营地 → 比彻之愿", "主角/尾声", "高"),
    ("cs_dutch_ms1", "Dutch van der Linde", "达奇·范德林德", "A", "VDL", "范德林德帮", "营地（随章节）", "帮派首领", "高"),
    ("cs_hoseamatthews_ms1", "Hosea Matthews", "何西阿·马修斯", "A", "VDL", "范德林德帮", "营地（随章节）", "军师", "高"),
    ("cs_micahbell_ms1", "Micah Bell", "迈卡·贝尔", "A", "VDL", "迈卡帮", "营地 → 迈卡藏身处", "内鬼/最终反派", "高"),
    ("cs_mrsadler_fs1", "Sadie Adler", "莎迪·阿德勒", "A", "VDL", "范德林德帮", "营地 → 比彻之愿", "战力", "高"),
    ("cs_abigailroberts_fs1", "Abigail Roberts", "艾比盖尔·罗伯茨", "A", "VDL", "马斯顿家族", "营地 → 比彻之愿", "约翰之妻", "高"),
    ("cs_billwilliamson_ms1", "Bill Williamson", "比尔·威廉姆森", "A", "VDL", "范德林德帮", "营地 → 边陲匪帮", "尾声反派", "高"),
    ("cs_javierescuella_ms1", "Javier Escuella", "哈维尔·埃斯奎拉", "A", "VDL", "范德林德帮", "营地 → 边陲匪帮", "尾声反派", "高"),
    ("cs_charlessmith_ms1", "Charles Smith", "查尔斯·史密斯", "A", "VDL", "范德林德帮", "营地（随章节）", "猎人/战力", "高"),
    ("cs_lenny_ms1", "Lenny Summers", "蓝尼·萨莫斯", "A", "VDL", "范德林德帮", "营地（随章节）", "战力", "高"),
    ("cs_sean_ms1", "Sean MacGuire", "西恩·麦奎尔", "A", "VDL", "范德林德帮", "营地（随章节）", "战力", "高"),
    ("cs_kieran_ms1", "Kieran Duffy", "基兰·达菲", "A", "VDL", "范德林德帮", "营地（随章节）", "马夫", "高"),
    ("cs_jackmarston_ms1", "Jack Marston (young)", "杰克·马斯顿（幼年）", "A", "VDL", "马斯顿家族", "营地（随章节）", "阿比盖尔之子", "高"),
    ("cs_jackmarston_teen_ms1", "Jack Marston (teen)", "杰克·马斯顿（少年）", "A", "VDL", "马斯顿家族", "比彻之愿", "尾声", "高"),
    ("cs_uncle_ms1", "Uncle", "大叔", "A", "VDL", "范德林德帮", "营地 → 比彻之愿", "常驻配角", "高"),
    ("cs_susangrimshaw_fs1", "Susan Grimshaw", "苏珊·格里姆肖", "A", "VDL", "范德林德帮", "营地（随章节）", "管家", "高"),
    ("cs_tilly_fs1", "Tilly Jackson", "蒂莉·杰克逊", "A", "VDL", "范德林德帮", "营地（随章节）", "帮派成员", "高"),
    ("cs_marybeth_fs1", "Mary-Beth Gaskill", "玛丽-贝丝·加斯基尔", "A", "VDL", "范德林德帮", "营地（随章节）", "帮派成员", "高"),
    ("cs_karen_fs1", "Karen Jones", "凯伦·琼斯", "A", "VDL", "范德林德帮", "营地（随章节）", "帮派成员", "高"),
    ("cs_mollyoshea_fs1", "Molly O'Shea", "莫莉·奥谢", "A", "VDL", "范德林德帮", "营地（随章节）", "达奇情人", "高"),
    ("cs_leostrauss_ms1", "Leopold Strauss", "利奥波德·施特劳斯", "A", "VDL", "范德林德帮", "营地（随章节）", "放贷者", "高"),
    ("cs_mrpearson_ms1", "Simon Pearson", "西蒙·皮尔逊", "A", "VDL", "范德林德帮", "营地（随章节）", "厨子/屠夫", "高"),
    ("cs_revswanson_ms1", "Reverend Swanson", "斯旺森牧师", "A", "VDL", "范德林德帮", "营地（随章节）", "牧师", "高"),
    ("cs_josiahtrelawny_ms1", "Josiah Trelawny", "约西亚·特里劳尼", "A", "VDL", "范德林德帮", "营地/圣丹尼斯", "骗子/销赃", "高"),
    ("cs_daveycallender_ms1", "Davey Callender", "戴维·卡伦德", "B", "VDL", "范德林德帮", "犁刀村", "第一章阵亡", "高"),
    ("cs_mradler_ms1", "Mr. Adler", "阿德勒先生", "B", "CIV", "阿德勒家族", "阿德勒牧场", "莎迪之夫", "高"),
    # ── 联邦 / 平克顿 ─────────────────────────────────────────
    ("cs_miltonandrews_ms1", "Andrew Milton", "安德鲁·米尔顿", "B", "US", "平克顿侦探社", "黑水镇 / 圣丹尼斯", "平克顿探员", "高"),
    ("cs_edgarross_ms1", "Edgar Ross", "埃德加·罗斯", "B", "US", "平克顿侦探社", "黑水镇 / 圣丹尼斯", "平克顿探员", "高"),
    ("cs_archerfordham_ms1", "Archer Fordham", "阿彻·福德姆", "D", "US", "平克顿侦探社", "黑水镇", "平克顿探员", "中"),
    ("cs_captainmonroe_ms1", "Captain Monroe", "门罗上尉", "B", "US", "联邦军", "华莱士堡", "驻军军官", "高"),
    ("cs_sherifffreeman_ms1", "Sheriff Freeman", "弗里曼警长", "D", "US", "风滚草镇公所", "风滚草镇", "警长", "高"),
    ("cs_valsheriff_ms1", "Sheriff Malloy", "瓦伦丁警长（马洛伊）", "D", "US", "瓦伦丁镇公所", "瓦伦丁", "警长", "中"),
    ("cs_strsheriff_01_ms1", "Strawberry Sheriff", "草莓镇警长", "D", "US", "草莓镇公所", "草莓镇", "警长", "中"),
    ("cs_nbxpolicechiefformal_ms1", "Blackwater Police Chief", "黑水镇警察局长", "D", "US", "黑水镇公所", "黑水镇", "警察局长", "中"),
    ("cs_asbdeputy_01_ms1", "Armadillo Deputy", "犰狳镇副警长", "D", "US", "犰狳镇公所", "犰狳镇", "副警长", "中"),
    # ── 康沃尔 ───────────────────────────────────────────────
    ("cs_leviticuscornwall_ms1", "Leviticus Cornwall", "利维提克斯·康沃尔", "B", "COR", "康沃尔公司", "安尼斯堡 / 煤油厂", "铁路大亨", "高"),
    ("cs_cornwalltrainconductor_ms1", "Cornwall Conductor", "康沃尔列车长", "D", "COR", "康沃尔公司", "铁路线", "列车长", "中"),
    # ── 莱莫恩：布莱斯韦特 ────────────────────────────────────
    ("cs_catherinebraithwaite_fs1", "Catherine Braithwaite", "凯瑟琳·布雷斯韦特", "B", "LEM", "布莱斯韦特家族", "布雷斯韦特庄园", "族长", "高"),
    ("cs_penelopebraithwaite_fs1", "Penelope Braithwaite", "佩内洛普·布雷斯韦特", "B", "LEM", "布莱斯韦特家族", "布雷斯韦特庄园", "家族千金", "高"),
    ("cs_bartholomewbraithwaite_ms1", "Bartholomew Braithwaite", "巴塞洛缪·布莱斯韦特", "B", "LEM", "布莱斯韦特家族", "布雷斯韦特庄园", "家族成员", "高"),
    ("cs_garethbraithwaite_ms1", "Gareth Braithwaite", "加雷斯·布莱斯韦特", "D", "LEM", "布莱斯韦特家族", "布雷斯韦特庄园", "家族成员", "中"),
    ("cs_geraldbraithwaite_ms1", "Gerald Braithwaite", "杰拉尔德·布莱斯韦特", "D", "LEM", "布莱斯韦特家族", "布雷斯韦特庄园", "家族成员", "中"),
    ("cs_braithwaitebutler_ms1", "Braithwaite Butler", "布莱斯韦特管家", "D", "LEM", "布莱斯韦特家族", "布雷斯韦特庄园", "管家", "中"),
    # ── 莱莫恩：格雷 ─────────────────────────────────────────
    ("cs_tavishgray_ms1", "Tavish Gray", "塔维什·格雷", "B", "LEM", "格雷家族", "卡利加种植园", "族长", "高"),
    ("cs_leighgray_ms1", "Leigh Gray", "利·格雷", "B", "LEM", "格雷家族", "卡利加种植园 / 罗兹", "罗兹警长后台", "高"),
    ("cs_beaugray_ms1", "Beau Gray", "鲍·格雷", "B", "LEM", "格雷家族", "卡利加种植园", "家族少爷", "高"),
    ("cs_adamgray_ms1", "Adam Gray", "亚当·格雷", "D", "LEM", "格雷家族", "卡利加种植园", "家族成员", "中"),
    ("cs_iangray_ms1", "Ian Gray", "伊恩·格雷", "D", "LEM", "格雷家族", "卡利加种植园", "家族成员", "中"),
    ("cs_jockgray_ms1", "Jock Gray", "乔克·格雷", "D", "LEM", "格雷家族", "卡利加种植园", "家族成员", "中"),
    ("cs_scottgray_ms1", "Scott Gray", "斯科特·格雷", "D", "LEM", "格雷家族", "卡利加种植园", "家族成员", "中"),
    # ── 圣丹尼斯黑帮 ─────────────────────────────────────────
    ("cs_bronte_ms1", "Angelo Bronte", "安吉洛·勃朗特", "B", "LEM", "勃朗特家族", "圣丹尼斯", "黑帮头目", "高"),
    ("cs_brontesbutler_ms1", "Bronte's Butler", "勃朗特管家", "D", "LEM", "勃朗特家族", "圣丹尼斯", "管家", "中"),
    # ── 瓦匹缇 ───────────────────────────────────────────────
    ("cs_rainsfall_ms1", "Rains Fall", "落雨", "B", "WAP", "瓦匹缇部落", "瓦匹缇", "酋长", "高"),
    ("cs_eagleflies_ms1", "Eagle Flies", "飞鹰", "B", "WAP", "瓦匹缇部落", "瓦匹缇", "战士首领", "高"),
    ("cs_paytah_ms1", "Paytah", "佩塔赫", "B", "WAP", "瓦匹缇部落", "瓦匹缇", "战士", "高"),
    ("cs_wapitiboy_ms1", "Wapiti Boy", "瓦匹缇少年", "D", "WAP", "瓦匹缇部落", "瓦匹缇", "部落少年", "中"),
    # ── 瓜玛 ─────────────────────────────────────────────────
    ("cs_fussar_ms1", "Alberto Fussar", "阿尔贝托·富萨尔", "B", "GUA", "富萨尔军政府", "阿瓜多切斯", "军政府长官", "高"),
    ("cs_hercule_ms1", "Hercule", "赫尔克里", "B", "GUA", "瓜玛反抗军", "瓜玛营", "反抗军领袖", "高"),
    ("cs_leon_ms1", "Leon", "利昂", "B", "GUA", "瓜玛反抗军", "瓜玛营", "反抗军成员", "高"),
    ("cs_gloria_fs1", "Gloria", "格洛丽亚", "B", "GUA", "瓜玛反抗军", "瓜玛营", "反抗军成员", "高"),
    # ── 边陲匪帮 ─────────────────────────────────────────────
    ("cs_colmodriscoll_ms1", "Colm O'Driscoll", "科尔姆·奥德里斯科", "B", "OUT", "奥德里斯科尔帮", "垂犬牧场 / 六点木屋", "帮派首领", "高"),
    ("cs_cleet_ms1", "Cleet", "克里特", "B", "OUT", "迈卡帮", "河狸岩洞 / 雪山", "迈卡手下", "高"),
    ("cs_joe_ms1", "Joe", "乔", "B", "OUT", "迈卡帮", "河狸岩洞 / 雪山", "迈卡手下", "高"),
    ("cs_henrilemiux_ms1", "Henri Lemieux", "亨利·勒米厄", "B", "LEM", "圣丹尼斯市政", "圣丹尼斯", "圣丹尼斯市长", "高"),
    ("cs_guidomartelli_ms1", "Guido Martelli", "圭多·马泰利", "D", "LEM", "勃朗特家族", "圣丹尼斯", "勃朗特手下", "中"),
    ("cs_jimcalloway_ms1", "Jim \"Boy\" Calloway", "吉姆·“小子”·卡洛威", "C", "CIV", "传奇枪手", "瓦伦丁", "传奇枪手/任务发布者", "高"),
    ("cs_hamish_ms1", "Hamish Sinclair", "哈米什·辛克莱", "C", "CIV", "无", "奥克里夫潭（未收录）", "退伍老兵/钓鱼", "高"),
    ("cs_jamie_ms1", "Jamie Linton", "杰米·林顿", "C", "CIV", "林顿家族", "瓦伦丁", "玛丽之弟", "高"),
    ("cs_archiedown_ms1", "Archie Downes", "阿奇·唐斯", "C", "CIV", "唐斯家族", "唐斯农场（瓦伦丁近郊）", "唐斯之子", "高"),
    ("cs_brotherdorkins_ms1", "Brother Dorkins", "道金斯修士", "C", "CIV", "教会", "圣丹尼斯", "修士", "高"),
    ("cs_mysteriousstranger_ms1", "The Mysterious Stranger", "神秘陌生人", "C", "CIV", "无", "野外/圣丹尼斯", "神秘事件", "中"),
    ("cs_senorandreascolon_ms1", "Señor Andreas Colon", "安德烈亚斯·科隆", "D", "GUA", "瓜玛军政府", "阿瓜多切斯", "瓜玛士绅", "中"),
    ("cs_creolecaptain_ms1", "Creole Captain", "克里奥尔船长", "D", "GUA", "瓜玛军政府", "阿瓜多切斯", "船长", "中"),
    # ── 支线补充（名字可识别、常驻地待核）──────────────────────
    ("cs_drhiggins_ms1", "Dr. Higgins", "希金斯医生", "D", "CIV", "无", "待核", "医生", "中"),
    ("cs_drmalcolmmacintosh_ms1", "Dr. Malcolm Macintosh", "马尔科姆·麦金托什医生", "D", "CIV", "无", "待核", "医生", "中"),
    ("cs_sddoctor_01_ms1", "Saint Denis Doctor", "圣丹尼斯医生", "D", "CIV", "无", "圣丹尼斯", "医生", "高"),
    ("cs_creoledoctor_ms1", "Creole Doctor", "克里奥尔医生", "D", "CIV", "无", "瓜玛/莱莫恩", "医生", "中"),
    ("cs_sdpriest_ms1", "Saint Denis Priest", "圣丹尼斯神父", "D", "CIV", "教会", "圣丹尼斯", "神父", "中"),
    ("cs_obediahhinton_ms1", "Obediah Hinton", "俄巴底亚·辛顿", "D", "CIV", "无", "待核", "陌生人任务", "中"),
    ("cs_norrisforsythe_ms1", "Norris Forsythe", "诺里斯·福赛思", "D", "CIV", "无", "待核", "陌生人任务", "中"),
    ("cs_marshall_thurwell_ms1", "Marshal Thurwell", "瑟韦尔警长", "D", "US", "联邦执法", "待核", "警长", "中"),
    ("cs_lucanapoli_ms1", "Luca Napoli", "卢卡·拿波里", "D", "LEM", "勃朗特家族", "圣丹尼斯", "黑帮成员", "低"),
    ("cs_levisimon_ms1", "Levi Simon", "利维·西蒙", "D", "CIV", "无", "待核", "支线人物", "低"),
    ("cs_dalemaroney_ms1", "Dale Maroney", "戴尔·马罗尼", "D", "CIV", "无", "待核", "支线人物", "低"),
    ("cs_theodorelevin_ms1", "Theodore Levin", "西奥多·莱文", "D", "CIV", "无", "圣丹尼斯", "商人", "低"),
    ("cs_timothydonahue_ms1", "Timothy Donahue", "提莫西·多纳休", "D", "CIV", "无", "待核", "支线人物", "低"),
    ("cs_mrs_calhoun_fs1", "Mrs. Calhoun", "卡尔霍恩夫人", "D", "CIV", "无", "待核", "支线人物", "低"),
    ("cs_reverendfortheringham_ms1", "Reverend Fortheringham", "福瑟林厄姆牧师", "D", "CIV", "教会", "待核", "牧师", "低"),
    ("cs_cassidy_ms1", "Cassidy", "卡西迪", "D", "CIV", "无", "待核", "枪手/支线", "低"),
    ("cs_gilbertknightly_ms1", "Gilbert Knightly", "吉尔伯特·奈特利", "D", "CIV", "无", "待核", "支线人物", "低"),
    ("cs_hectorhollowes_ms1", "Hector Hollowes", "赫克托·霍洛斯", "D", "CIV", "无", "待核", "支线人物", "低"),
    ("cs_abemaclean_ms1", "Abe MacLean", "阿贝·麦克莱恩", "D", "CIV", "无", "待核", "支线人物", "低"),
    ("cs_tomdickens_ms1", "Tom Dickens", "汤姆·狄更斯", "D", "CIV", "无", "待核", "支线人物", "低"),
    ("cs_angusgeddes_ms1", "Angus Geddes", "安格斯·格迪斯", "D", "CIV", "格迪斯家族", "待核", "支线人物", "低"),
    ("cs_davidgeddes_ms1", "David Geddes", "大卫·格迪斯", "D", "CIV", "格迪斯家族", "待核", "支线人物", "低"),
    ("cs_ansel_atherton_ms1", "Ansel Atherton", "安塞尔·阿瑟顿", "D", "CIV", "无", "待核", "支线人物", "低"),
    ("cs_abe_ms1", "Abe", "阿贝", "D", "CIV", "无", "待核", "支线人物", "低"),
    # ── 平民 / 支线 ──────────────────────────────────────────
    ("cs_marylinton_fs1", "Mary Linton", "玛丽·灵顿", "B", "CIV", "林顿家族", "瓦伦丁", "亚瑟旧爱", "高"),
    ("cs_mrlinton_ms1", "Mr. Linton", "林顿先生", "D", "CIV", "林顿家族", "瓦伦丁", "玛丽之父", "中"),
    ("cs_thomasdown_ms1", "Thomas Downes", "托马斯·唐斯", "B", "CIV", "唐斯家族", "唐斯农场（瓦伦丁近郊）", "收债对象", "高"),
    ("cs_edithdown_fs1", "Edith Downes", "伊迪丝·唐斯", "B", "CIV", "唐斯家族", "瓦伦丁 → 安尼斯堡", "唐斯遗孀", "中"),
    ("cs_sistercalderon_fs1", "Sister Calderón", "卡尔德隆修女", "B", "CIV", "教会", "圣丹尼斯", "修女", "高"),
    ("cs_hobartcrawley_ms1", "Hobart Crawley", "霍巴特·克劳利", "B", "CIV", "克劳利家族", "安尼斯堡", "断手老兵", "中"),
    ("cs_brendacrawley_fs1", "Brenda Crawley", "布伦达·克劳利", "D", "CIV", "克劳利家族", "安尼斯堡", "家属", "低"),
    ("cs_famousgunslinger_05_fs1", "Black Belle", "黑衣美人", "C", "CIV", "传奇枪手", "莱莫恩（斯嘉丽草甸）", "退役枪手", "高"),
    ("cs_famousgunslinger_01_ms1", "Legendary Gunslinger 01", "传奇枪手 01", "C", "CIV", "传奇枪手", "新汉诺威", "任务目标", "低"),
    ("cs_famousgunslinger_02_ms1", "Legendary Gunslinger 02", "传奇枪手 02", "C", "CIV", "传奇枪手", "安巴里诺", "任务目标", "低"),
    ("cs_famousgunslinger_03_ms1", "Legendary Gunslinger 03", "传奇枪手 03", "C", "CIV", "传奇枪手", "莱莫恩", "任务目标", "低"),
    ("cs_famousgunslinger_04_ms1", "Legendary Gunslinger 04", "传奇枪手 04", "C", "CIV", "传奇枪手", "新奥斯汀", "任务目标", "低"),
    ("cs_famousgunslinger_06_ms1", "Legendary Gunslinger 06", "传奇枪手 06", "C", "CIV", "传奇枪手", "各地", "任务目标", "低"),
    ("cs_crackpotinventor_ms1", "Marco Dragic", "马尔科·德拉吉奇", "C", "CIV", "德拉吉奇", "莱莫恩实验室", "疯狂发明家", "中"),
    ("cs_frankmonster_ms1", "Dragic's Creation", "德拉吉奇的造物", "C", "CIV", "德拉吉奇", "莱莫恩实验室", "机器人", "中"),
    ("cs_francis_sinclair_ms1", "Francis Sinclair", "弗朗西斯·辛克莱", "C", "CIV", "辛克莱", "斯嘉丽草甸小屋", "时间旅行彩蛋", "中"),
    ("cs_evelynmiller_ms1", "Evelyn Miller", "艾夫林·米勒", "C", "CIV", "无", "罗诺克山脊", "作家", "中"),
    ("cs_albertmason_ms1", "Albert Mason", "阿尔伯特·梅森", "C", "CIV", "无", "野外（随任务移动）", "摄影师", "中"),
    ("cs_frenchartist_ms1", "Charles Châtenay", "查尔斯·夏特奈", "C", "CIV", "无", "圣丹尼斯", "法国画家", "高"),
    ("cs_exoticcollector_ms1", "Algernon Wasp", "阿尔杰农·沃斯普", "C", "CIV", "无", "圣丹尼斯", "标本收藏家", "高"),
    ("cs_dinoboneslady_fs1", "Deborah MacGuiness", "黛博拉·麦克吉尼斯", "C", "CIV", "无", "野外（恐龙骨点）", "古生物学者", "中"),
    ("cs_magnifico_ms1", "Magnifico", "马尼菲科", "C", "CIV", "马戏团", "巡回马戏团", "马戏团主", "中"),
    ("cs_gavin_ms1", "Gavin", "加文", "C", "CIV", "无", "黑水镇（待核）", "未解之谜", "低"),
    ("cs_vampire_ms1", "Saint Denis Vampire", "圣丹尼斯吸血鬼", "C", "CIV", "无", "圣丹尼斯", "夜间事件", "高"),
    ("cs_edmundlowry_ms1", "Edmund Lowry Jr.", "小艾德蒙·劳里", "C", "OUT", "连环杀手", "瓦伦丁（待核）", "连环杀手", "低"),
    ("cs_mickey_ms1", "Mickey", "米基", "C", "CIV", "无", "瓦伦丁", "断腿老兵", "高"),
    ("cs_chelonianmaster_01_ms1", "Chelonian Master", "龟甲教教主", "C", "CIV", "龟甲教", "野外", "邪教领袖", "中"),
    ("cs_sunworshipper_ms1", "Sun Worshipper", "太阳崇拜者", "C", "CIV", "太阳教", "野外", "邪教", "低"),
    ("cs_wrobel_ms1", "Wrobel", "沃贝尔", "C", "CIV", "无", "瓦伦丁近郊", "收债对象", "中"),
    ("cs_giant_ms1", "The Giant", "巨人", "C", "CIV", "无", "野外", "隐士", "低"),
    ("cs_swampweirdosonny_ms1", "Sonny", "桑尼", "C", "OUT", "沼泽怪人", "拉格拉斯", "沼泽事件", "中"),
    ("cs_johnthebaptisingmadman_ms1", "John the Baptising Madman", "施洗狂人", "C", "CIV", "无", "达科他河", "河边传教", "中"),
    ("cs_nicholastimmins_ms1", "Nicholas Timmins", "尼古拉斯·蒂明斯", "C", "CIV", "无", "圣丹尼斯", "艺术圈", "中"),
    ("cs_wintonholmes_ms1", "Winton Holmes", "温顿·霍姆斯", "C", "CIV", "无", "圣丹尼斯", "记者", "中"),
    ("cs_agnesdowd_fs1", "Agnes Dowd", "阿格尼丝·多德", "C", "CIV", "无", "露莓溪", "沼泽女鬼", "中"),
    ("cs_princessisabeau_fs1", "Princess Isabeau", "伊莎博公主", "C", "CIV", "马戏团", "巡回马戏团", "演出角色", "低"),
    ("cs_missmarjorie_fs1", "Miss Marjorie", "玛乔丽小姐", "C", "CIV", "马戏团", "巡回马戏团", "马戏团长", "中"),
    ("cs_operasinger_fs1", "Opera Singer", "歌剧演员", "C", "CIV", "无", "圣丹尼斯剧院", "歌剧演员", "中"),
    ("cs_soothsayer_fs1", "Soothsayer", "占卜师", "C", "CIV", "无", "野外", "占卜彩蛋", "低"),
    ("cs_aberdeenpigfarmer_ms1", "Aberdeen Pig Farmer", "阿伯丁农夫", "B", "OUT", "阿伯丁家族", "阿伯丁猪场", "黑店", "高"),
    ("cs_aberdeensister_fs1", "Aberdeen Sister", "阿伯丁姐妹", "D", "OUT", "阿伯丁家族", "阿伯丁猪场", "黑店同伙", "中"),
    ("cs_professorbell_ms1", "Professor Bell", "贝尔教授", "D", "CIV", "无", "圣丹尼斯（待核）", "学者", "低"),
    ("cs_mrsfellows_fs1", "Mrs. Fellows", "费洛斯夫人", "D", "CIV", "费洛斯家族", "新汉诺威（待核）", "支线人物", "低"),
    ("cs_baptiste_ms1", "Baptiste", "巴普蒂斯特", "D", "CIV", "无", "圣丹尼斯（待核）", "支线人物", "低"),
]


def main():
    data = json.load(open(W("export/levels/world/settlements.json"), encoding="utf-8"))["settlements"]
    by = {r["code"]: r for r in data}

    out = []
    for code, r in by.items():
        if code not in BIND:
            raise SystemExit("missing BIND: " + code)
        typ, bound, fac, clan, owner, note = BIND[code]
        bw = bd = None
        if bound:
            o = by[bound]
            bw = round(math.hypot(r["cx"] - o["cx"], r["cy"] - o["cy"]))
        if bound:
            rule = "≤800m 正常" if bw <= 800 else ("800~1200m 同势力远郊" if bw <= 1200 else ">1200m 叙事确认")
        elif typ == "castle":
            rule = "独立城堡（不依附）"
        elif typ == "poi":
            rule = "野外点位（不参与村庄经济）"
        else:
            rule = "营地/藏身处（不依附）"
        out.append({
            "code": code, "name_zh": r["name_zh"], "name_en": r["name_en"],
            "category": r["category"], "size_w": r["size_w"], "size_d": r["size_d"],
            "u": r["u"], "v": r["v"], "cx": r["cx"], "cy": r["cy"],
            "btype": typ, "bound_to": bound, "bound_name": by[bound]["name_zh"] if bound else "",
            "bound_dist_m": bw, "dist_rule": rule,
            "faction": fac, "faction_zh": FACTIONS[fac]["zh"],
            "clan": clan, "owner": owner, "note": note,
        })

    order = {"town": 0, "castle": 1, "village": 2, "camp": 3, "poi": 4, "hideout": 5}
    out.sort(key=lambda x: (order[x["btype"]], x["faction"], x["name_zh"]))

    cols = ["code", "name_zh", "name_en", "btype", "bound_to", "bound_name", "bound_dist_m", "dist_rule",
            "faction", "faction_zh", "clan", "owner", "size_w", "size_d", "u", "v", "note"]
    with open(W("export/levels/world/settlements_bannerlord.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in out:
            w.writerow({k: r.get(k, "") for k in cols})
    with open(W("export/levels/world/settlements_bannerlord.json"), "w", encoding="utf-8") as f:
        json.dump({"factions": FACTIONS, "settlements": out}, f, ensure_ascii=False, indent=1)

    # NPC（rank 来自 story_rank.json；has_model 已逐个核对过 export/npc）
    rank = {}
    for k, v in json.load(open(W("work/npc/story_rank.json"), encoding="utf-8")).items():
        if not k.startswith("_"):
            rank[k] = v.get("rank")
    npc_cols = ["id", "name_en", "name_zh", "tier", "faction", "faction_zh", "clan",
                "home", "role", "confidence", "rank", "has_model"]
    with open(W("export/levels/world/npc_roster.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=npc_cols)
        w.writeheader()
        for n in NPC:
            i, en, cn, tier, fac, clan, home, role, conf = n
            w.writerow({"id": i, "name_en": en, "name_zh": cn, "tier": tier,
                        "faction": fac, "faction_zh": FACTIONS.get(fac, {"zh": "平民/支线"})["zh"],
                        "clan": clan, "home": home, "role": role, "confidence": conf,
                        "rank": rank.get(i, ""), "has_model": "Y"})
    with open(W("export/levels/world/factions.json"), "w", encoding="utf-8") as f:
        json.dump(FACTIONS, f, ensure_ascii=False, indent=1)

    from collections import Counter
    print("settlements", len(out), Counter(x["btype"] for x in out))
    print("by faction", Counter(x["faction_zh"] for x in out))
    print("villages without owner", [x["code"] for x in out if x["btype"] == "village" and not x["bound_to"]])
    print("npc", len(NPC), Counter(n[4] for n in NPC))
    print("npc confidence", Counter(n[8] for n in NPC))
    for b in ("town", "castle"):
        print(b, [(x["name_zh"], x["faction_zh"]) for x in out if x["btype"] == b])


if __name__ == "__main__":
    main()
