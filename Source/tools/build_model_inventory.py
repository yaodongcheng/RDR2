# -*- coding: utf-8 -*-
"""导出武器/道具模型清单。"""
import os, csv, re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)

ITEM_CAT = {
    "p_valuable": "贵重物品", "p_food": "食物", "s_pickups": "地面拾取物",
    "int_lootable": "可搜刮物", "p_plant": "植物/草药", "p_hunting": "狩猎/皮毛",
    "p_drink": "酒水", "int_doctor_office": "医疗用品", "p_store": "商店道具",
    "s_cards": "香烟卡",
}
WEP_CAT = [
    ("revolver_", "左轮手枪"), ("pistol_", "手枪"), ("rifle_", "步枪"),
    ("repeater_", "连发步枪"), ("shotgun_", "霰弹枪"), ("sniper_", "狙击枪"),
    ("bow_", "弓"), ("melee_", "近战"), ("throwable_", "投掷物"),
    ("lasso_", "套索"), ("fishingrod_", "钓竿"), ("ammo_", "弹药"),
    ("kit_", "工具"),
]


def main():
    # 武器
    wroot = W("export/weapons/models")
    wrows = []
    for r, _, files in os.walk(wroot):
        for fn in files:
            ext = fn.rsplit(".", 1)[-1].lower()
            if ext not in ("ydr", "ydd", "yft", "ytd"):
                continue
            base = re.sub(r"\+hi.*$", "", fn)
            base = re.sub(r"\.(ydr|ydd|yft|ytd)$", "", base)
            base = re.sub(r"_\d+$", "", base)
            base = re.sub(r"\d+$", "", base)
            norm = base[2:] if base.startswith("w_") else base
            cat = next((zh for pre, zh in WEP_CAT if norm.startswith(pre)), "其他")
            wrows.append({"file": os.path.relpath(os.path.join(r, fn), ROOT).replace("\\", "/"),
                          "base": base, "category": cat,
                          "kind": "model" if ext in ("ydr", "ydd", "yft") else "texture"})
    with open(W("export/levels/world/weapon_models.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "base", "category", "kind"])
        w.writeheader(); w.writerows(sorted(wrows, key=lambda x: (x["category"], x["base"], x["kind"])))

    # 道具
    iroot = W("export/items/models")
    irows = []
    for pkg in sorted(os.listdir(iroot)):
        pdir = os.path.join(iroot, pkg)
        if not os.path.isdir(pdir):
            continue
        for r, _, files in os.walk(pdir):
            for fn in files:
                ext = fn.rsplit(".", 1)[-1].lower()
                if ext not in ("ydr", "ydd", "yft", "ytd"):
                    continue
                base = re.sub(r"\+hi.*$", "", fn)
                base = re.sub(r"\.(ydr|ydd|yft|ytd)$", "", base)
                irows.append({"package": pkg, "category": ITEM_CAT.get(pkg, pkg),
                              "file": os.path.relpath(os.path.join(r, fn), ROOT).replace("\\", "/"),
                              "base": base,
                              "kind": "model" if ext in ("ydr", "ydd", "yft") else "texture"})
    with open(W("export/levels/world/item_models.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["package", "category", "file", "base", "kind"])
        w.writeheader(); w.writerows(sorted(irows, key=lambda x: (x["package"], x["base"], x["kind"])))

    print("weapon files", len(wrows), "models", sum(1 for x in wrows if x["kind"] == "model"),
          "textures", sum(1 for x in wrows if x["kind"] == "texture"))
    print("weapon bases", len(set(x["base"] for x in wrows)))
    c = defaultdict(int)
    for x in irows:
        c[(x["package"], x["category"])] += 1
    print("item files", len(irows), "models", sum(1 for x in irows if x["kind"] == "model"),
          "textures", sum(1 for x in irows if x["kind"] == "texture"))
    for (p, cat), n in sorted(c.items()):
        print(f"  {p:<20} {cat:<10} {n}")


if __name__ == "__main__":
    main()
