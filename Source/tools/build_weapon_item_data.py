# -*- coding: utf-8 -*-
"""任务目标 + 武器数值/模型资产 导出。

输出：
  export/levels/world/goals_sp_missions.csv
  export/levels/world/weapons_mp.csv
  export/levels/world/weapon_assets.csv
"""
import os, csv, re, subprocess, xml.etree.ElementTree as ET
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)


def goals():
    r = ET.parse(W("work/meta/common/data/stats_and_challenges/goals_sp_missions.meta")).getroot()
    rows = []
    for g in r.find("goals"):
        name = g.findtext("name")
        sp = g.find("scoreParam")
        stat = compare = desired = ""
        if sp is not None:
            inner = sp.find("scoreParam")
            if inner is not None:
                compare = inner.findtext("compareType") or ""
                ss = inner.find("scoreSource")
                if ss is not None:
                    stat = ss.findtext("statId/BaseId") or ""
                dg = inner.find("desiredGoal")
                desired = dg.get("value") if dg is not None else ""
        ui = g.find("uiInfo")
        label = ui.findtext("pauseMenuDescriptionLabel") if ui is not None else ""
        rows.append({"goal": name, "stat": stat, "compare": compare,
                     "desired": desired, "label": label})
    with open(W("export/levels/world/goals_sp_missions.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["goal", "stat", "compare", "desired", "label"])
        w.writeheader(); w.writerows(rows)
    print("goals", len(rows))


def weapons_mp():
    p = W("work/items/meta/packs/base/data/ai/weapons_mp.meta")
    r = ET.parse(p).getroot()
    rows = []
    for x in r.findall("CWeaponInfo"):
        name = x.findtext("Name") or ""
        hd = x.find("WeaponHeadShotDistance")
        acc = x.find("AccuracyFalloffRangeStart")
        def v(node, tag):
            n = node.find(tag) if node is not None else None
            return n.get("value") if n is not None else ""
        fall = []
        f = x.find("DamageFallOffDistances")
        if f is not None:
            for it in f.findall("Item"):
                fall.append(f'{v(it,"Distance")}:{v(it,"Damage")}')
        rows.append({
            "weapon": name,
            "hs_min_ai": v(hd, "MinHeadShotDistanceAI"),
            "hs_max_ai": v(hd, "MaxHeadShotDistanceAI"),
            "hs_min_player": v(hd, "MinHeadShotDistancePlayer"),
            "hs_max_player": v(hd, "MaxHeadShotDistancePlayer"),
            "damage_falloff": "|".join(fall),
            "acc_falloff_start": v(x, "AccuracyFalloffRangeStart"),
            "acc_falloff_end": v(x, "AccuracyFalloffRangeEnd"),
            "acc_falloff_min": v(x, "AccuracyFalloffMin"),
            "lock_on_range": v(x, "LockOnRange"),
        })
    with open(W("export/levels/world/weapons_mp.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("weapons_mp", len(rows))


CAT = [
    ("revolver_", "左轮手枪"), ("pistol_", "手枪"), ("rifle_", "步枪"),
    ("repeater_", "连发步枪"), ("shotgun_", "霰弹枪"), ("sniper_", "狙击枪"),
    ("bow_", "弓"), ("melee_", "近战"), ("throwable_", "投掷物"),
    ("lasso_", "套索"), ("fishingrod_", "钓竿"), ("ammo_", "弹药"),
    ("kit_", "工具"), ("sp_", "特殊"),
]


def weapon_assets():
    rp = W("tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe")
    rpf = W("work/weapons/packs/base/models/weapons.rpf")
    out = subprocess.run([rp, "list", rpf], capture_output=True, text=True, timeout=120).stdout
    assets = []
    for l in out.split("\n"):
        m = re.search(r"(\S+\.(?:ydr|ydd|ytd|yft))$", l.strip())
        if not m:
            continue
        fn = m.group(1)
        base = re.sub(r"\+hi.*$", "", fn)
        base = re.sub(r"\.(ydr|ydd|ytd|yft)$", "", base)
        base = re.sub(r"_\d+$", "", base)
        base = re.sub(r"\d+$", "", base)
        norm = base[2:] if base.startswith("w_") else base
        cat = next((zh for pre, zh in CAT if norm.startswith(pre)), "其他")
        assets.append({"asset": fn, "base": base, "category": cat, "model": 1 if fn.endswith((".ydr", ".ydd", ".yft")) else 0})
    # 按 base 聚合
    agg = defaultdict(lambda: {"count": 0, "models": 0, "category": "", "assets": []})
    for a in assets:
        k = a["base"]
        agg[k]["count"] += 1
        agg[k]["models"] += a["model"]
        agg[k]["category"] = a["category"]
        agg[k]["assets"].append(a["asset"])
    rows = [{"base": k, "category": v["category"], "asset_count": v["count"],
             "model_count": v["models"], "assets": ";".join(sorted(v["assets"]))} for k, v in agg.items()]
    rows.sort(key=lambda x: (x["category"], x["base"]))
    with open(W("export/levels/world/weapon_assets.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["base", "category", "asset_count", "model_count", "assets"])
        w.writeheader(); w.writerows(rows)
    print("weapon assets", len(assets), "unique base", len(rows))


if __name__ == "__main__":
    goals()
    weapons_mp()
    weapon_assets()
