# -*- coding: utf-8 -*-
"""从 update_1.rpf 的 common/data/missions.meta 生成任务清单，并对照过场包覆盖。

输出：
  export/levels/world/missions.csv
  export/levels/world/mission_stats.json
"""
import xml.etree.ElementTree as ET
import re, os, csv, json
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)


def main():
    root = ET.parse(W("work/meta/common/data/missions.meta")).getroot()
    ms = list(root.find("Missions"))

    # 过场包索引
    txt = open(W("export/story/cutscene_index.txt"), encoding="utf-8", errors="ignore").read()
    cuts = set(re.findall(r"cuts_([a-z0-9]+)\.rpf", txt))
    extracted = set()
    for d in os.listdir(W("export/story/cutscene")):
        if d.startswith("cuts_"):
            extracted.add(d[5:])

    rows = []
    for m in ms:
        mid = m.findtext("MissionId")
        cat = m.findtext("Category")
        typ = m.findtext("MissionType")
        desc = m.findtext("Description")
        tex = m.findtext("TextureName")
        ign = m.find("IgnoreForProgressPercent").get("value")
        key = (mid or "").lower()
        # 过场包代码可能是 mid 去掉尾号 / 前缀匹配
        pkg = ""
        for c in cuts:
            if key == c or key.startswith(c) or c.startswith(key):
                pkg = c
                break
        rows.append({
            "mission_id": mid, "category": cat, "mission_type": typ,
            "description_key": desc, "texture": tex, "ignore_progress": ign,
            "cutscene_pkg": pkg,
            "cutscene_indexed": "Y" if pkg else "N",
            "cutscene_extracted": "Y" if pkg in extracted else "N",
        })

    rows.sort(key=lambda r: (r["category"], r["mission_id"]))
    with open(W("export/levels/world/missions.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # 分类统计
    CAT = {
        "CHAPTER_1": "主线 第1章", "CHAPTER_2": "主线 第2章", "CHAPTER_3": "主线 第3章",
        "CHAPTER_4": "主线 第4章", "CHAPTER_5": "主线 第5章", "CHAPTER_6": "主线 第6章",
        "CHAPTER_7": "尾声 上", "CHAPTER_8": "尾声 下",
        "RANDOM_CHARACTER": "随机事件/陌生人", "RANDOM_STORY_CHARACTER": "随机剧情角色",
        "BOUNTY_HUNTING": "赏金任务", "ENDLESS_SUMMER": "线上/无尽夏日",
        "ITEM_REQUEST": "物品请求", "RECIPE": "配方（非剧情）",
    }
    by = Counter(r["category"] for r in rows)
    main_n = sum(v for k, v in by.items() if k.startswith("CHAPTER"))
    story_n = by.get("RANDOM_CHARACTER", 0) + by.get("RANDOM_STORY_CHARACTER", 0) + by.get("BOUNTY_HUNTING", 0)
    stats = {
        "total": len(rows),
        "main_story": main_n,
        "side_story": story_n,
        "item_request": by.get("ITEM_REQUEST", 0),
        "recipe": by.get("RECIPE", 0),
        "endless_summer": by.get("ENDLESS_SUMMER", 0),
        "by_category": {CAT.get(k, k): v for k, v in by.items()},
        "cutscene_pkgs_indexed": len(cuts),
        "cutscene_pkgs_extracted": len(extracted),
        "missions_with_cutscene_pkg": sum(1 for r in rows if r["cutscene_indexed"] == "Y"),
        "missions_with_cutscene_extracted": sum(1 for r in rows if r["cutscene_extracted"] == "Y"),
    }
    json.dump(stats, open(W("export/levels/world/mission_stats.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("missions", len(rows))
    for k, v in by.most_common():
        print(f"  {CAT.get(k,k):<20} {v}")
    print("main", main_n, "side", story_n)
    print("cutscene pkgs", len(cuts), "extracted", len(extracted),
          "missions matched", stats["missions_with_cutscene_pkg"])


if __name__ == "__main__":
    main()
