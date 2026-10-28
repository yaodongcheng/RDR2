# -*- coding: utf-8 -*-
"""把「武器装了哪些部件」写进 export/viewer/site.json，查看器 HUD 里直接显示。

数据源：export/levels/world/weapon_assembly.csv（export_weapon_assembled.py 产出）
只给 site.json 里列出的那 45 把武器补 parts 字段，不动其他内容。

    python tools/patch_viewer_weapon_parts.py
"""
import os, csv, json, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "export/viewer/site.json")
CSV = os.path.join(ROOT, "export/levels/world/weapon_assembly.csv")

PARTS_ZH = {
    "grip1": "木托/护木", "grip2": "木托/护木(样式2)", "grip3": "木托/护木(样式3)",
    "grip4": "握把(样式4)", "grip5": "握把(样式5)",
    "stock1": "枪托", "sight1": "准星", "sight2": "准星(样式2)",
    "clip1": "弹仓", "mag1": "弹仓",
    "barrel1": "枪管", "barrel2": "枪管(长)",
}


def main():
    rows = {}
    if os.path.exists(CSV):
        for r in csv.DictReader(open(CSV, encoding="utf-8-sig")):
            rows[r["base"]] = [p for p in (r.get("parts") or "").split(";") if p]
    d = json.load(open(SITE, encoding="utf-8"))

    # 列表里混进了"部件"（如 w_shotgun_doublebarrel01_mag1 被当成一把枪）→ 剔掉
    COMP = re.compile(r'_(grip\d|sight\d|clip\d?|mag\d|barrel\d+|wrap\d|stock\d|bullet|strap\d*|inner\d*)$')
    before = len(d.get("weapons", []))
    d["weapons"] = [w for w in d.get("weapons", []) if not COMP.search(w["id"])]

    # 同名不同枪 → 加后缀区分
    RENAME = {
        "w_rifle_binoculars01": "望远镜（步枪用）",
        "w_sp_bowarrow_arrow": "箭（箭矢本体）",
        "w_sp_bowarrow": "箭（带弓）",
    }
    for w in d.get("weapons", []):
        if w["id"] in RENAME:
            w["name"] = RENAME[w["id"]]
    print("武器列表 %d → %d（剔掉部件 %d）" % (before, len(d["weapons"]), before - len(d["weapons"])))

    hit = 0
    for w in d.get("weapons", []):
        parts = rows.get(w["id"]) or []
        w["parts"] = parts
        w["parts_zh"] = [PARTS_ZH.get(p, p) for p in parts]
        if parts:
            hit += 1
    assembled = sum(1 for v in rows.values() if v)
    d.setdefault("meta", {})["weapon_assembled"] = assembled
    d["meta"]["weapons"] = len(d["weapons"])
    d["meta"]["built_at"] = d["meta"].get("built_at", "")
    json.dump(d, open(SITE, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("weapons in site:", len(d.get("weapons", [])), "带部件:", hit, "装配过的模型:", assembled)


if __name__ == "__main__":
    main()
