# -*- coding: utf-8 -*-
"""把 settlements.json 渲染成 Markdown 表格片段（供人工文档引用，避免手抄数字出错）。"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(ROOT, "export/levels/world/settlements.json"), encoding="utf-8"))
rows = d["settlements"]

EN = {
    "sdn": "Saint Denis", "val": "Valentine", "rho": "Rhodes", "ann": "Annesburg",
    "bla": "Blackwater", "str": "Strawberry", "van": "Van Horn Trading Post",
    "arm": "Armadillo", "tum": "Tumbleweed", "lag": "Lagras", "but": "Butcher Creek",
    "col": "Colter", "wap": "Wapiti", "agu": "Aguasdulces", "man": "Manzanita Post",
    "bra": "Braithwaite Manor", "cal": "Caliga Hall", "ora": "Orange Plantation",
    "mfr": "MacFarlane's Ranch", "eme": "Emerald Ranch", "bee": "Beecher's Hope",
    "pro": "Pronghorn Ranch", "han": "Hanging Dog Ranch", "adl": "Adler Ranch",
    "dow": "Downe's Ranch", "rid": "Ridgewood Farm", "fom": "Fort Mercer",
    "wal": "Wallace Station", "old": "Fort Wallace", "sis": "Sisika Penitentiary",
    "cor": "Cornwall Kerosene & Tar",
    "gap": "Gaptooth Breach", "sha": "Shady Belle", "cle": "Clemens Point",
    "lak": "Lakay", "gua": "Guarma Camp", "mic": "Micah's Hideout", "lnn": "Lonnie's Shack",
    "che": "Chez Porter", "lon": "Lonnie's Shack", "sod": "Sod House",
    "old": "Fort Wallace", "dewclm": "Dewberry Creek", "rat": "Rathskeller Fork",
    "twi": "Twin Rocks",
}
STATE_ZH = {
    "NewHanover": "新汉诺威", "Lemoyne": "莱莫恩", "WestElizabeth": "西伊丽莎白",
    "NewAustin": "新奥斯汀", "Ambarino": "安巴里诺", "Guarma": "瓜马",
}
DIST_ZH = {
    "Heartlands": "心脏地带", "scarlettMeadows": "红宝石草甸", "roanoke": "罗阿诺克岭",
    "greatPlains": "大平原", "bigvalley": "大山谷", "ChollaSprings": "仙人掌泉",
    "GaptoothRidge": "裂齿山脊", "BayouNwa": "巴约泥沼", "GrizzliesWest": "西格里兹里",
    "GrizzliesEast": "东格里兹里", "TallTrees": "高树区", "BluewaterMarsh": "蓝水沼泽",
    "HennigansStead": "亨尼根之地", "RioBravo": "布拉沃河", "Cumberland": "坎伯兰森林",
    "GuarmaD": "瓜马",
}
TIER_TXT = {"大城市": "大城市 3000", "城堡": "城堡 1200", "村庄": "村庄 1000",
            "藏身处": "藏身处 800", "小剧情": "小剧情 100", "野外点位": "野外点位 200"}

# 人工精简备注（表格里放短句，长说明放正文）
SHORT = {
    "sdn": "全图唯一大城；港区+工业区+电车 776 m/火车 868 m 环线",
    "val": "畜牧镇；实测 277×482，已跑通 383 模型/935 实例",
    "rho": "烟草镇；两大家族地盘",
    "ann": "矿业镇；实测 346×308，L2 150 模型/151 实例",
    "bla": "西部枢纽；序章大事件地",
    "str": "全图最小的“有商店”城镇",
    "van": "无治安贸易站；码头+灯塔",
    "arm": "荒漠镇；霍乱疫情设定",
    "tum": "荒漠镇+监狱；边陲感最强",
    "lag": "沼泽渔村；以水路为主",
    "but": "污染村落；支线密集",
    "col": "雪山废弃矿村；序章营地",
    "wap": "印第安保留地帐篷群",
    "agu": "瓜马岛村落（独立地图）",
    "man": "森林边境哨站/贸易点",
    "bra": "宅邸+庭院+林荫道；最接近城堡体量",
    "cal": "大宅+大片农田",
    "ora": "★ 原文档误标 O'Creagh's Run，按 ora_plantation 包更正",
    "mfr": "荒漠牧场；牲口栏+主屋",
    "eme": "草原大牧场；火车站+牲畜拍卖",
    "bee": "终章家园；可建造",
    "pro": "山谷小牧场",
    "han": "山谷牧场；匪帮据点",
    "adl": "雪山孤宅；序章起点",
    "dow": "草原小牧场",
    "rid": "荒漠农场（原表带“?”待核）",
    "fom": "峡谷土堡；体量只够城堡内堡",
    "wal": "★ 原表误标 Fort Wallace；实为火车站，并入野外瓦片",
    "old": "★ 原表误标 Old Bacchus Place?；jail/stable/2×tower 判定为华莱士堡",
    "sis": "河心岛监狱；岛域 744×576",
    "cor": "炼油厂+工人村；工业场景范本",
    "gap": "矿洞群；包络 968×1182 含整座山",
    "sha": "沼泽庄园营地（第 4 章）",
    "cle": "湖岸营地（第 3 章）；含码头",
    "lak": "沼泽村落营地（第 4 章过渡）",
    "gua": "瓜马岛临时营地",
    "mic": "雪山藏身处（mic_hid 包，名称为推断）",
    "che": "山间农舍；可入室",
    "lnn": "★ 原表 lon 是普通包；lnn_lonnie_shack 才是本体（河畔独屋）",
    "sod": "草原独屋；全图最小据点",
    "dewclm": "★ 原表 dew 实为磨坊；dewclm 才是杜伯里溪",
    "rat": "荒漠小驿站",
    "twi": "荒漠小营地",
}

CATS = [
    ("大城市", "① 大城市"), ("城镇", "② 城镇（有商店/银行/酒馆）"),
    ("村庄", "③ 村庄 / 聚落"), ("庄园", "④ 庄园"),
    ("牧场农场", "⑤ 牧场 / 农场"), ("要塞监狱", "⑥ 要塞 / 监狱"),
    ("工矿", "⑦ 工矿"), ("驿站", "⑧ 驿站 / 野外点位"), ("藏身处", "⑨ 营地 / 藏身处"),
    ("小屋农舍", "⑩ 小屋 / 农舍（100 m 小剧情场景）"),
]

out = []
n = 0
for cat, title in CATS:
    sub = [r for r in rows if r["category"] == cat]
    out.append(f"\n### {title}（{len(sub)}）\n")
    out.append("| # | 名称 | 州 · 地区 | 建成区 (m) | 档位 / 场景 | 填充 | 大地图 (u,v) | 资产 | 备注 |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for r in sub:
        n += 1
        st = f'{STATE_ZH.get(r["state"], r["state"])} · {DIST_ZH.get(r["district"], r["district"])}'
        src = {"Z": "", "M": "实测 ", "C": "估 ", "C*": "估* "}.get(r["size_src"], "")
        out.append(
            f'| {n} | **{r["name_zh"]}**<br>{EN.get(r["code"], r["name_en"])} | {st} | '
            f'{src}{r["size_w"]}×{r["size_d"]} | {TIER_TXT[r["tier"]]} | {r["fill_pct"]}% | '
            f'{r["u"]:.0f},{r["v"]:.0f} | {r["asset"]} | {SHORT.get(r["code"], r["note"])} |')

txt = "\n".join(out)
open(os.path.join(ROOT, "work/settlement_tables.md"), "w", encoding="utf-8").write(txt)
print(txt)
