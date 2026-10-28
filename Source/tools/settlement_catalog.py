# -*- coding: utf-8 -*-
"""据点清单生成器：把 towns.json / zones.json / campaign.json / L2 实测 合并成一份可交付清单。

输出：
  work/settlement_catalog.json   机器可读全量
  export/levels/world/settlements.csv
  export/levels/world/settlements.json

口径：
  - 官方 zone 范围（TOWN/REGION）优先，作为"规划范围"；
  - 实体聚类包络（towns.json bbox）作为"含周边道具/地形的松散包络"；
  - 建成区实测（gltf 实例）只对已还原的 3 个镇有值，用于校准"包络 vs 真实建成区"的倍率。
"""
import json, os, csv, math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ---------- 点落多边形 ----------
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


def zone_size(z):
    b = z["bbox"]
    return abs(b[2] - b[0]), abs(b[3] - b[1])


def main():
    towns = load_json(W("export/levels/world/towns.json"))["towns"]
    zones = load_json(W("export/levels/world/zones.json"))["zones"]
    camp = load_json(W("work/campaign/campaign.json"))
    uv = {t["code"]: (t["u"], t["v"]) for t in camp["towns"]}

    states = [z for z in zones if z["type"] == "STATE"]
    districts = [z for z in zones if z["type"] == "DISTRICT"]
    ztown = {z["name"].lower(): z for z in zones if z["type"] in ("TOWN", "REGION")}

    rows = []
    for t in towns:
        if t.get("grid"):
            continue
        pt = (t["cx"], t["cy"])
        st = next((z["name"] for z in states if in_zone(pt, z)), "")
        di = next((z["name"] for z in districts if in_zone(pt, z)), "")
        b = t["bbox"]
        cw, cd = abs(b[3] - b[0]), abs(b[4] - b[1])
        # 官方 zone 近似匹配：按 code 前缀 / 名称
        cand = None
        for key in (t["code"], t["name"].lower().replace(" ", ""), t["name"].lower().split()[0]):
            if key in ztown:
                cand = ztown[key]
                break
        if cand is None:
            for k, z in ztown.items():
                if k.startswith(t["code"]) or t["code"].startswith(k[:3]):
                    cand = z
                    break
        zw, zd = zone_size(cand) if cand else (None, None)
        u, v = uv.get(t["code"], (None, None))
        rows.append({
            "code": t["code"], "name": t["name"], "zh": t["zh"], "n": t["n"],
            "state": st, "district": di,
            "cx": round(t["cx"], 1), "cy": round(t["cy"], 1), "cz": round(t["cz"], 1),
            "cluster_w": round(cw), "cluster_d": round(cd),
            "zone": cand["name"] if cand else "", "zone_w": round(zw) if zw else None,
            "zone_d": round(zd) if zd else None,
            "u": u, "v": v, "major": bool(t.get("major")),
        })

    with open(W("work/settlement_catalog.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    for r in sorted(rows, key=lambda r: -r["n"]):
        zs = f'{r["zone_w"]}x{r["zone_d"]}' if r["zone_w"] else "-"
        print(f'{r["code"]:>7} {r["zh"]:<12} {r["state"][:14]:<14} {r["district"][:16]:<16} '
              f'cluster={r["cluster_w"]:>4}x{r["cluster_d"]:<4} zone={zs:>9} uv=({r["u"]},{r["v"]})')


if __name__ == "__main__":
    main()
