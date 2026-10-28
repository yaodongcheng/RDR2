# -*- coding: utf-8 -*-
"""从本地化语音索引里提取「店主 / 医生 / 警长」等服务类 NPC 的语音库，并按城镇归类。

输出：
  export/levels/world/service_npcs.csv
  export/levels/world/service_matrix.json
"""
import re, os, csv, json
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)

TOWNS = {
    "val": ("val", "瓦伦丁"), "rhd": ("rho", "罗兹"), "arm": ("arm", "犰狳镇"),
    "asb": ("arm", "犰狳镇"), "str": ("str", "草莓镇"), "blw": ("bla", "黑水镇"),
    "nbx": ("sdn", "圣丹尼斯"), "sd": ("sdn", "圣丹尼斯"), "tum": ("tum", "风滚草镇"),
    "vht": ("van", "范霍恩贸易站"), "wal": ("wal", "华莱士车站"), "wap": ("wap", "瓦匹提"),
    "mfr": ("mfr", "麦克法兰牧场"), "rwf": ("rid", "里奇伍德农场"),
    "rkf": ("", "牧场（未定位）"), "hhr": ("", "牧场（未定位）"), "psh": ("", "牧场（未定位）"),
    "lag": ("lag", "拉格拉斯"), "emr": ("eme", "翡翠牧场"),
    "dor": ("", "农户（未定位）"), "lrs": ("", "农户（未定位）"),
}

SERVICE = {
    "genstoreowner": "综合商店老板", "generalstoreowner": "综合商店老板",
    "gunsmith": "枪匠", "doctor": "医生", "bartender": "酒保",
    "hotelowner": "旅馆老板", "barber": "理发师", "butcher": "肉铺老板",
    "sheriff": "警长", "sherriff": "警长", "policechief": "警察局长",
    "trainstationworker": "车站职员", "stationclerk": "车站职员",
    "freightstationowner": "货运站老板", "welcomecenter": "游客中心",
    "undertaker": "殡仪师", "exoticshopkeeper": "异国商店老板",
    "shadydealer": "黑市商人", "official": "部落官员", "rancher": "牧场主",
    "mother": "村民（母亲）", "father": "村民（父亲）",
    "homesteadhusband": "农户（丈夫）", "homesteadtenant": "农户（佃户）",
}
GENERIC = {
    "tailor": "裁缝", "barber": "理发师", "bankclerk": "银行职员",
    "liveryworker": "马厩伙计", "trainstationworker": "车站职员",
    "genconductor": "列车员", "marketvendor": "摊贩", "unibutchers": "肉铺老板",
    "freelance_undertaker": "殡仪师", "shop": "商店（通用）",
}


def main():
    lines = open(W("export/story/lang_index.txt"), encoding="utf-8", errors="ignore").read().split("\n")
    names = sorted(set(m.group(1) for l in lines if (m := re.search(r"([0-9A-Za-z_]+)\.yldb", l))))

    rows = []
    for n in names:
        m = re.match(r"^\d+_u_([mf])_([mo])_(.+?)(?:_\d+)?$", n)
        if m:
            body = re.sub(r"_\d+$", "", m.group(3))
            for code in sorted(TOWNS, key=len, reverse=True):
                if body.startswith(code):
                    svc = body[len(code):]
                    if svc in SERVICE:
                        rows.append({
                            "town_code": TOWNS[code][0], "town_zh": TOWNS[code][1],
                            "service": SERVICE[svc], "voice_bank": n, "unique": "Y",
                            "raw": svc,
                        })
                    break
            continue
        m2 = re.match(r"^\d+_s_[mf]_[mo]_(.+?)(?:_[a-z]+_?\d*)?$", n)
        if m2:
            body = m2.group(1)
            for k, zh in GENERIC.items():
                if body.startswith(k):
                    rows.append({"town_code": "", "town_zh": "全图通用", "service": zh,
                                 "voice_bank": n, "unique": "N", "raw": k})
                    break

    # 去重（同一 town+service+voice_bank）
    seen = set(); uniq = []
    for r in rows:
        k = (r["town_code"], r["service"], r["voice_bank"])
        if k in seen: continue
        seen.add(k); uniq.append(r)
    rows = sorted(uniq, key=lambda r: (r["unique"] != "Y", r["town_zh"], r["service"]))

    with open(W("export/levels/world/service_npcs.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["town_code", "town_zh", "service", "voice_bank", "unique", "raw"])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # 汇总：城镇 × 服务
    matrix = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["unique"] == "Y":
            matrix[r["town_zh"]][r["service"]].append(r["voice_bank"])
    with open(W("export/levels/world/service_matrix.json"), "w", encoding="utf-8") as f:
        json.dump(matrix, f, ensure_ascii=False, indent=1)

    print("rows", len(rows), "unique", sum(1 for r in rows if r["unique"] == "Y"),
          "generic", sum(1 for r in rows if r["unique"] == "N"))
    for town in ["瓦伦丁", "罗兹", "犰狳镇", "草莓镇", "黑水镇", "圣丹尼斯", "风滚草镇", "范霍恩贸易站", "华莱士车站", "瓦匹提"]:
        svcs = matrix.get(town, {})
        print(f"\n{town}（{len(svcs)} 类）")
        for s, banks in svcs.items():
            print(f"  {s}: {', '.join(banks)}")


if __name__ == "__main__":
    main()


# ── 文档用：城镇 × 服务矩阵（✅=有专属语音库；○=有该服务但无专属库；?=待核；—=无）
SERVICES = ["综合商店", "枪店", "医生", "酒馆", "旅馆", "理发", "肉铺", "裁缝",
            "银行", "马厩", "火车站", "警长/警察", "殡仪", "其他"]
MATRIX = {
    "圣丹尼斯":   ["✅", "✅", "✅", "✅", "○", "○", "○", "○", "○", "○", "○", "✅", "○", "✅ 黑市"],
    "瓦伦丁":     ["✅", "✅", "✅", "✅", "✅", "✅", "✅", "—", "○", "○", "○", "✅", "—", "—"],
    "罗兹":       ["✅", "✅", "?",  "✅", "—", "—", "○", "○", "○", "○", "✅", "✅", "—", "—"],
    "安尼斯堡":   ["○", "○", "?",  "○", "—", "—", "—", "—", "—", "○", "○", "○", "—", "—"],
    "黑水镇":     ["✅", "○", "○", "✅", "○", "○", "○", "○", "○", "○", "✅", "✅", "○", "—"],
    "草莓镇":     ["✅", "○", "—", "○", "○", "—", "○", "—", "—", "○", "—", "✅", "—", "—"],
    "范霍恩贸易站": ["○", "○", "—", "✅", "—", "—", "—", "—", "—", "○", "✅", "—", "—", "✅ 异国商店"],
    "犰狳镇":     ["✅", "✅", "?",  "✅", "—", "—", "○", "—", "○", "○", "○", "✅", "✅", "—"],
    "风滚草镇":   ["✅", "✅", "—", "✅", "—", "—", "✅", "—", "—", "○", "—", "✅", "—", "—"],
    "阿瓜斯杜尔塞斯": ["—", "—", "—", "—", "—", "—", "—", "—", "—", "—", "—", "—", "—", "—"],
}
