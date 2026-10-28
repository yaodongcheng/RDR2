# -*- coding: utf-8 -*-
"""载具页：`vehicles.rpf` 108 个可载具模型 → three.js 查看器 + 分类清单。

输入：export/levels/world/vehicle_inventory.json（build_vehicle_inventory.py 产出）
      export/viewer/models/vehicles/*.gltf（export_vehicle_gltf.py 产出）
输出：export/vehicles/data.json
      export/vehicles/index.html

中文名按 VEH_ZH 表给；表里没有的退回英文名（**不编造**）。
"""
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORLD = os.path.join(ROOT, "export/levels/world")
OUT = os.path.join(ROOT, "export/vehicles")

# 载具中文名（按资产名）。未列出的保留原名并标 "（未译）"
VEH_ZH = {
    # ---- 武器载具
    "gatling_gun": "加特林机枪（车载/架设）",
    "gatlingmaxim02": "马克沁机枪（架设）",
    "policewagongatling01x": "警用马车·车载加特林",
    "breach_cannon": "攻城炮",
    "hotchkiss_cannon": "哈奇开斯速射炮",
    # ---- 船
    "boatsteam02x": "小型蒸汽船",
    "ship_guama02": "瓜玛大型轮船",
    "ship_nbdguama": "瓜玛沿岸汽船",
    "ship_nbdguama2": "瓜玛沿岸汽船（变体）",
    "tugboat2": "拖船",
    "turbineboat": "涡轮汽船",
    "horseboat": "马渡船（运马平底船）",
    "keelboat": "龙骨船",
    "rcboat": "内河汽船（小）",
    "rowboat": "划艇",
    "rowboatswamp": "沼泽划艇",
    "rowboatswamp02": "沼泽划艇（变体）",
    "canoe": "独木舟",
    "canoetreetrunk": "树皮独木舟",
    "pirogue": "独木舟（皮划）",
    "pirogue2": "独木舟（皮划·变体）",
    "skiff": "小艇",
    "smuggler02": "走私船",
    # ---- 火车
    "northsteamer01x": "北方铁路·机车",
    "privatesteamer01x": "私人列车·机车",
    "wintersteamer": "冬季列车·机车",
    "ghosttrainsteamer": "幽灵列车·机车",
    "steamerdummy": "机车（占位/简单模型）",
    "coal_wagon": "煤水车",
    "coalhopper01x": "漏斗煤车",
    "northcoalcar01x": "北方铁路·煤车",
    "privatecoalcar01x": "私人列车·煤车",
    "wintercoalcar": "冬季列车·煤车",
    "ghosttraincoalcar": "幽灵列车·煤车",
    "caboose01x": "守车",
    "ghosttraincaboose": "幽灵列车·守车",
    "northflatcar01x": "北方铁路·平车",
    "privateflatcar01x": "私人列车·平车",
    "northpassenger01x": "北方铁路·客车",
    "northpassenger03x": "北方铁路·客车（三号）",
    "privatepassenger01x": "私人列车·客车",
    "ghosttrainpassenger": "幽灵列车·客车",
    "midlandboxcar05x": "米德兰铁路·棚车",
    "privateboxcar01x": "私人列车·棚车",
    "privateboxcar02x": "私人列车·棚车（二）",
    "privateboxcar04x": "私人列车·棚车（四）",
    "midlandrefrigeratorcar": "米德兰铁路·冷藏车",
    "privatebaggage01x": "私人列车·行李车",
    "privatedining01x": "私人列车·餐车",
    "privateobservationcar": "私人列车·观景车",
    "privateopensleeper01x": "私人列车·敞开卧铺车",
    "privateopensleeper02x": "私人列车·敞开卧铺车（二）",
    "privaterooms01x": "私人列车·包厢车",
    "privatearmoured": "私人列车·装甲车",
    "armoredcar01x": "装甲车厢（一）",
    "armoredcar03x": "装甲车厢（三）",
    # ---- 有轨电车 / 飞行器
    "trolley01x": "圣丹尼斯有轨电车",
    "hotairballoon01": "热气球",
    # ---- 马车 / 货运车
    "cart01": "平板手推车（一）", "cart02": "平板手推车（二）",
    "cart03": "平板手推车（三）", "cart04": "货运马车（四）",
    "cart05": "货运马车（五）", "cart06": "货运马车（六）",
    "cart07": "货运马车（七）", "cart08": "货运马车（八）",
    "buggy01": "轻便马车（一）", "buggy02": "轻便马车（二）", "buggy03": "轻便马车（三）",
    "coach2": "四轮马车（二）", "coach3": "四轮马车（三）", "coach4": "四轮马车（四）",
    "coach5": "四轮马车（五）", "coach6": "四轮马车（六）",
    "coach3_cutscene": "四轮马车（过场版）",
    "stagecoach001x": "驿站马车（001）", "stagecoach002x": "驿站马车（002）",
    "stagecoach003x": "驿站马车（003）", "stagecoach004x": "驿站马车（004）",
    "stagecoach005x": "驿站马车（005）", "stagecoach006x": "驿站马车（006）",
    "chuckwagon000x": "炊事车（000）", "chuckwagon002x": "炊事车（002）",
    "gatchuck": "炊事车·车载机枪", "gatchuck_2": "炊事车·车载机枪（二）",
    "supplywagon": "补给马车", "supplywagon2": "补给马车（二）",
    "armysupplywagon": "军用补给马车",
    "logwagon": "运木车", "logwagon2": "运木车（二）",
    "oilwagon01x": "运油车（一）", "oilwagon02x": "运油车（二）",
    "coal_wagon": "煤车",
    "policewagon01x": "警用马车",
    "wagonprison01x": "囚车",
    "wagondoc01x": "医生马车",
    "wagondairy01x": "奶车",
    "wagoncircus01x": "马戏团车（一）", "wagoncircus02x": "马戏团车（二）",
    "wagontraveller01x": "旅行者马车",
    "wagonwork01x": "工程马车",
    "wagon02x": "货运马车（02）", "wagon03x": "货运马车（03）",
    "wagon04x": "货运马车（04）", "wagon05x": "货运马车（05）",
    "wagon06x": "货运马车（06）",
    "utilliwag": "工具车",
    "handcart": "手推车", "minecart01x": "矿车",
}

NOTE = {
    "policewagongatling01x": "★ 就是「马车上架着机枪」那台——车厢 + 加特林炮座一体模型",
    "gatchuck": "炊事车底盘 + 车载机枪",
    "gatchuck_2": "炊事车底盘 + 车载机枪（第二套）",
    "gatling_gun": "可单独架在任何车/阵地上的加特林本体",
    "gatlingmaxim02": "马克沁机枪本体",
    "breach_cannon": "攻城炮（架设）",
    "hotchkiss_cannon": "速射炮（架设）",
    "ship_guama02": "最大的一条船（模型尺寸 35 m 级）",
    "trolley01x": "圣丹尼斯有轨电车（已用于 continent.blend 沿轨道跑）",
    "hotairballoon01": "唯一飞行器",
}


def main():
    inv = json.load(open(os.path.join(WORLD, "vehicle_inventory.json"), encoding="utf-8"))
    base = [r for r in inv if r["lod"] == "base"]
    rows = []
    for r in base:
        n = r["name"]
        gltf = os.path.join(ROOT, "export/viewer/models/vehicles", n + ".gltf")
        if not os.path.exists(gltf):
            continue
        rows.append(dict(
            name=n,
            zh=VEH_ZH.get(n, n + "（未译）"),
            cat=r["category"], cat_zh=r["category_zh"],
            tris=int(r["tris"] or 0), verts=int(r["verts"] or 0), geoms=int(r["geoms"] or 0),
            size=[float(r["size_x"] or 0), float(r["size_y"] or 0), float(r["size_z"] or 0)],
            gltf=f"../viewer/models/vehicles/{n}.gltf",
            note=NOTE.get(n, ""),
        ))
    rows.sort(key=lambda x: (x["cat"], x["name"]))
    os.makedirs(OUT, exist_ok=True)
    json.dump(rows, open(os.path.join(OUT, "data.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("vehicles", len(rows))
    from collections import Counter
    print(Counter(r["cat_zh"] for r in rows))


if __name__ == "__main__":
    main()
