# -*- coding: utf-8 -*-
"""RDR2 据点/城镇清单：curated 主表 + 实测尺寸 + 地形统计 + 正式化档位映射。

输出：
  export/levels/world/settlements.csv
  export/levels/world/settlements.json
  work/settlement_stats.txt   （供写文档引用）
"""
import json, os, csv, math
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)

H = np.load(W("work/terrain/H4.npy"))
V = np.load(W("work/terrain/valid4.npy"))
X0, Y0, RES = -7684.0, -8196.0, 4.0
WORLD_M, MAP_U, M_PER_U = 12296.0, 848.0, 14.5


def terrain_stats(cx, cy, span):
    s = min(max(span, 60), 1400)
    c0 = int((cx - s / 2 - X0) / RES); c1 = int((cx + s / 2 - X0) / RES)
    r0 = int((cy - s / 2 - Y0) / RES); r1 = int((cy + s / 2 - Y0) / RES)
    c0, r0 = max(0, c0), max(0, r0)
    c1, r1 = min(H.shape[1], c1), min(H.shape[0], r1)
    h = H[r0:r1, c0:c1]; v = V[r0:r1, c0:c1].astype(bool)
    if h.size == 0 or not v.any():
        return {}
    gy, gx = np.gradient(h, RES)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))[v]
    hh = h[v]
    return {
        "z_min": round(float(hh.min()), 1), "z_max": round(float(hh.max()), 1),
        "z_range": round(float(hh.max() - hh.min()), 1),
        "slope_mean": round(float(slope.mean()), 1),
        "flat8": round(float((slope < 8).mean() * 100), 1),
        "valid": round(float(v.mean() * 100), 1),
    }


# code, en, zh, category, tier, size_w, size_d, size_src, asset, note
# size_src: Z=官方 zone, M=实测建成区, C=实体聚类包络(估)
MASTER = [
    # ── 大城市 ────────────────────────────────────────────────
    ("sdn", "Saint Denis", "圣丹尼斯", "大城市", "大城市", 862, 955, "Z", "A 整城",
     "全图唯一大城；含港口/工业区/剧场/银行，电车 776 m 环线、火车 868 m 环线"),
    # ── 城镇（有商店/银行/酒馆）────────────────────────────────
    ("val", "Valentine", "瓦伦丁", "城镇", "村庄", 363, 501, "Z", "A 街区",
     "畜牧小镇；实测建成区 277×482（zone 的 80%），已跑通 383 模型/935 实例"),
    ("rho", "Rhodes", "罗兹", "城镇", "村庄", 398, 443, "Z", "C 灰盒", "烟草镇，两大家族地盘"),
    ("ann", "Annesburg", "安尼斯堡", "城镇", "村庄", 403, 408, "Z", "B 真模型",
     "矿业镇；实测建成区 346×308，L2 150 模型/151 实例"),
    ("bla", "Blackwater", "黑水镇", "城镇", "村庄", 436, 440, "Z", "C 灰盒", "西部交通枢纽，序章大事件地"),
    ("str", "Strawberry", "草莓镇", "城镇", "村庄", 177, 195, "Z", "C 灰盒", "山谷小镇，全图最小的“有商店”城镇"),
    ("van", "Van Horn Trading Post", "范霍恩贸易站", "城镇", "村庄", 183, 281, "Z", "C 灰盒", "无治安的贸易站，码头+灯塔"),
    ("arm", "Armadillo", "犰狳镇", "城镇", "村庄", 221, 209, "Z", "C 灰盒", "荒漠镇，霍乱疫情设定"),
    ("tum", "Tumbleweed", "风滚草镇", "城镇", "村庄", 314, 273, "Z", "C 灰盒", "荒漠镇+监狱，边陲感最强"),
    # ── 村庄 / 聚落 ───────────────────────────────────────────
    ("lag", "Lagras", "拉格拉斯", "村庄", "村庄", 209, 184, "Z", "C 灰盒", "沼泽渔村，水路为主"),
    ("but", "Butcher Creek", "屠夫溪", "村庄", "村庄", 150, 222, "Z", "C 灰盒", "污染村落，支线密集"),
    ("col", "Colter", "科尔特", "村庄", "村庄", 144, 101, "C", "C 灰盒", "雪山废弃矿村，序章营地"),
    ("wap", "Wapiti", "瓦匹提", "村庄", "村庄", 164, 222, "Z", "C 灰盒", "印第安保留地营地，帐篷群"),
    ("agu", "Aguasdulces", "阿瓜斯杜尔塞斯", "村庄", "村庄", 423, 383, "C", "C 灰盒", "瓜马岛村落（独立地图）"),
    ("man", "Manzanita Post", "曼萨尼塔哨站", "村庄", "村庄", 131, 238, "Z", "C 灰盒", "森林边境哨站/贸易点"),
    # ── 庄园 ─────────────────────────────────────────────────
    ("bra", "Braithwaite Manor", "布雷斯韦特庄园", "庄园", "城堡", 495, 471, "Z", "C 灰盒",
     "主体宅邸+庭院+林荫道，最接近“城堡”体量的复合庄园"),
    ("cal", "Caliga Hall", "卡利加庄园", "庄园", "城堡", 515, 537, "Z", "C 灰盒", "庄园+大片农田，南北战争式大宅"),
    ("ora", "Orange Plantation", "奥兰治庄园", "庄园", "村庄", 176, 163, "C", "C 灰盒",
     "★ 原文档误标为 O'Creagh's Run；按 ymap 包名 ora_plantation 更正"),
    # ── 牧场 / 农场 ───────────────────────────────────────────
    ("mfr", "MacFarlane's Ranch", "麦克法兰牧场", "牧场农场", "村庄", 218, 153, "C", "C 灰盒", "荒漠牧场，牲口栏+主屋"),
    ("eme", "Emerald Ranch", "翡翠牧场", "牧场农场", "村庄", 284, 289, "Z", "C 灰盒", "草原大牧场，火车站+牲畜拍卖"),
    ("bee", "Beecher's Hope", "比彻之愿", "牧场农场", "村庄", 139, 139, "Z", "C 灰盒", "终章家园，可建造"),
    ("pro", "Pronghorn Ranch", "叉角羚牧场", "牧场农场", "村庄", 79, 122, "C", "C 灰盒", "山谷小牧场"),
    ("han", "Hanging Dog Ranch", "吊狗牧场", "牧场农场", "村庄", 129, 271, "C", "C 灰盒", "山谷牧场，匪帮据点"),
    ("adl", "Adler Ranch", "阿德勒牧场", "牧场农场", "村庄", 94, 86, "C", "C 灰盒", "雪山孤宅，序章起点"),
    ("dow", "Downe's Ranch", "唐恩牧场", "牧场农场", "村庄", 106, 60, "C", "C 灰盒", "草原小牧场"),
    ("rid", "Ridgewood Farm", "里奇伍德农场", "牧场农场", "村庄", 122, 123, "C", "C 灰盒", "荒漠农场（原表带“?”待核）"),
    # ── 要塞 / 监狱 ───────────────────────────────────────────
    ("fom", "Fort Mercer", "默瑟堡", "要塞监狱", "城堡", 111, 119, "C", "C 灰盒", "峡谷土堡，木墙+门楼；实测仅 111 m，属“小剧情场景”体量"),
    ("old", "Fort Wallace", "华莱士堡", "要塞监狱", "城堡", 120, 120, "C*", "C 灰盒",
     "★ 原表误标 Old Bacchus Place?；old_01 室内件为 jail/stable/storage/2×tower + 位置在 Cumberland，判定为华莱士堡"),
    ("sis", "Sisika Penitentiary", "西西卡监狱", "要塞监狱", "城堡", 311, 240, "C", "C 灰盒", "河心岛监狱；岛域 744×576，建成区 311×240"),
    # ── 驿站（野外点位，不单独开场景）────────────────────────
    ("wal", "Wallace Station", "华莱士车站", "驿站", "野外点位", 82, 158, "C", "C 灰盒",
     "★ 原表误标 Fort Wallace；wal_train_ 室内件确认是火车站。建议并入 848 野外瓦片，不单独开场景"),
    # ── 工矿 ─────────────────────────────────────────────────
    ("cor", "Cornwall Kerosene & Tar", "康沃尔煤油厂", "工矿", "村庄", 541, 512, "Z", "C 灰盒", "炼油厂+工人村，工业场景范本"),
    ("gap", "Gaptooth Breach", "裂齿矿洞", "工矿", "藏身处", 150, 150, "C*", "C 灰盒",
     "荒漠矿洞群；聚类包络 968×1182 含整座山，实际矿口/工棚约 150 m"),
    # ── 营地 / 藏身处 ─────────────────────────────────────────
    ("sha", "Shady Belle", "谢迪贝莱", "藏身处", "藏身处", 191, 190, "C", "C 灰盒", "沼泽庄园营地（第 4 章），ymap 包 sha_mansion"),
    ("cle", "Clemens Point", "克莱门斯据点", "藏身处", "藏身处", 196, 505, "C", "C 灰盒", "湖岸营地（第 3 章），含码头"),
    ("lak", "Lakay", "拉凯", "藏身处", "藏身处", 106, 82, "C", "C 灰盒", "沼泽村落营地（第 4 章过渡），有祭坛+码头棚屋"),
    ("gua", "Guarma Camp", "瓜马营地", "藏身处", "藏身处", 120, 120, "C", "C 灰盒", "瓜马岛临时营地（gua_cmp_01）"),
    ("mic", "Micah's Hideout", "雪山藏身处", "藏身处", "藏身处", 165, 55, "C", "C 灰盒", "雪山藏身处（mic_hid 包；游戏内名按包名推断）"),
    # ── 小屋 / 农舍（100 m 小剧情场景）────────────────────────
    ("che", "Chez Porter", "波特小屋", "小屋农舍", "小剧情", 48, 53, "C", "C 灰盒", "山间农舍，可入室"),
    ("lnn", "Lonnie's Shack", "朗尼小屋", "小屋农舍", "小剧情", 60, 60, "C*", "C 灰盒",
     "★ 原表 lon 是 Big Valley 的普通包；lnn_01 室内件 lnn_lonnie_shack 才是本体（巴约泥沼，包络 583×208 含沼泽）"),
    ("sod", "Sod House", "草皮屋", "小屋农舍", "小剧情", 15, 14, "C", "C 灰盒", "草原独屋，全图最小据点"),
    ("dewclm", "Dewberry Creek", "杜伯里溪", "小屋农舍", "小剧情", 44, 59, "C", "C 灰盒",
     "★ 原表 dew 实为 dew_mill（磨坊）；dewclm 才是杜伯里溪营地"),
    ("rat", "Rathskeller Fork", "鼠窖岔口", "小屋农舍", "小剧情", 80, 74, "C", "C 灰盒", "荒漠小驿站"),
    ("twi", "Twin Rocks", "双岩", "小屋农舍", "小剧情", 55, 55, "C", "C 灰盒", "荒漠小营地"),
]

def pip(pt, poly):
    x, y = pt
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i][0], poly[i][1]
        xj, yj = poly[j][0], poly[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def in_zone(pt, zone):
    return any(pip(pt, poly) for poly in zone.get("polygons", []) if len(poly) >= 3)


CAT_ORDER = ["大城市", "城镇", "村庄", "庄园", "牧场农场", "要塞监狱", "工矿", "驿站", "藏身处", "小屋农舍"]
SCENE = {"大城市": 3000, "城堡": 1200, "村庄": 1000, "藏身处": 800, "小剧情": 100, "野外点位": 200}


def main():
    camp = json.load(open(W("work/campaign/campaign.json"), encoding="utf-8"))
    zones = json.load(open(W("export/levels/world/zones.json"), encoding="utf-8"))["zones"]
    states = [z for z in zones if z["type"] == "STATE"]
    districts = [z for z in zones if z["type"] == "DISTRICT"]
    uv_old = {t["code"]: (t["u"], t["v"]) for t in camp["towns"]}
    rows = []
    for code, en, zh, cat, tier, sw, sd, src, asset, note in MASTER:
        # 圣丹尼斯用官方 zone 中心（聚类中心偏 300 m）
        if code == "sdn":
            cx, cy = 2555.0, -1151.0
        else:
            cx, cy = uv_old[code][0], uv_old[code][1]
            cx = X0 + cx * M_PER_U
            cy = 4100.0 - cy * M_PER_U
        u = (cx - X0) / M_PER_U
        v = (4100.0 - cy) / M_PER_U
        st = terrain_stats(cx, cy, max(sw, sd))
        state = next((z["name"] for z in states if in_zone((cx, cy), z)), "")
        district = next((z["name"] for z in districts if in_zone((cx, cy), z)), "")
        scene = SCENE[tier]
        equiv = round(math.sqrt(sw * sd))
        fill = round(equiv / scene * 100)
        rows.append({
            "code": code, "name_en": en, "name_zh": zh, "category": cat, "tier": tier,
            "state": state, "district": district,
            "scene_m": scene, "size_w": sw, "size_d": sd, "equiv_m": equiv, "size_src": src,
            "fill_pct": fill, "cx": round(cx, 0), "cy": round(cy, 0), "cz": st.get("z_min", 0),
            "u": round(u, 1), "v": round(v, 1),
            "z_range": st.get("z_range"), "slope_mean": st.get("slope_mean"),
            "flat8": st.get("flat8"), "asset": asset, "note": note,
        })

    # 邻近距离（大地图单位）
    pts = [(r["code"], r["u"], r["v"]) for r in rows]
    for r in rows:
        d = sorted(math.hypot(r["u"] - u, r["v"] - v) for c, u, v in pts if c != r["code"])
        r["nn_u"] = round(d[0], 1)
        r["nn_m"] = round(d[0] * M_PER_U)

    rows.sort(key=lambda r: (CAT_ORDER.index(r["category"]), -r["equiv_m"]))

    os.makedirs(W("export/levels/world"), exist_ok=True)
    with open(W("export/levels/world/settlements.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": {"world_m": WORLD_M, "map_units": MAP_U,
                            "m_per_unit": M_PER_U, "count": len(rows)},
                   "settlements": rows}, f, ensure_ascii=False, indent=1)

    cols = ["code", "name_zh", "name_en", "state", "district", "category", "tier", "scene_m", "size_w", "size_d",
            "size_src", "equiv_m", "fill_pct", "cx", "cy", "u", "v", "z_range", "slope_mean", "flat8",
            "nn_u", "nn_m", "asset", "note"]
    with open(W("export/levels/world/settlements.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})

    # 统计
    from collections import Counter
    print("总数", len(rows))
    print("按档位", Counter(r["tier"] for r in rows))
    print("按类别", Counter(r["category"] for r in rows))
    for t in ["大城市", "城堡", "村庄", "藏身处", "小剧情"]:
        sub = [r for r in rows if r["tier"] == t]
        if sub:
            print(f'  {t}({len(sub)}): 等效边长 {min(r["equiv_m"] for r in sub)}~'
                  f'{max(r["equiv_m"] for r in sub)} m, '
                  f'填充率 {min(r["fill_pct"] for r in sub)}~{max(r["fill_pct"] for r in sub)}%')
    import statistics
    print("最近邻(大地图单位) 中位 %.1f 最小 %.1f 最大 %.1f" % (
        statistics.median(r["nn_u"] for r in rows), min(r["nn_u"] for r in rows),
        max(r["nn_u"] for r in rows)))
    print("最近邻(米) 中位 %.0f" % statistics.median(r["nn_m"] for r in rows))
    towns = [r for r in rows if r["category"] == "城镇"]
    print("9 城镇互相最近邻 中位 %.1f u (%.0f m)" % (
        statistics.median(r["nn_u"] for r in towns), statistics.median(r["nn_m"] for r in towns)))


if __name__ == "__main__":
    main()
