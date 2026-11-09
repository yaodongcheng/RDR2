# -*- coding: utf-8 -*-
"""野外气泡：2,200 m 六边形布点，每个 3,072 m 场景；小据点并进最近气泡。"""
import csv, json, math, os
import numpy as np
from PIL import Image
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

RDR2 = r"D:\BrainMaker\大镖客2解包分析"
BASE = os.path.join(RDR2, "_scratch", "settlement_plan")

def read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

rows = read_csv(os.path.join(BASE, "settlements_plan.csv"))
pdata = json.load(open(os.path.join(BASE, "settlements_p.json"), encoding="utf-8"))

def f(x):
    try:
        return float(x)
    except Exception:
        return 0.0

info = {r["code"]: {"name": r["name_zh"], "tier": r["tier"], "type": r["rdr2_type"],
                    "x": f(r["world_x"]), "y": f(r["world_y"])} for r in rows}
big = [c for c in info if info[c]["tier"] in ("city", "castle") or info[c]["type"] == "hideout"]
small = [c for c in info if c not in big]

# 大据点紧凑 P（用于避免气泡中心落在城市/据点里）
big_P = []
for c in big:
    for poly in pdata.get(c, {}).get("P", []):
        if len(poly) >= 3:
            g = Polygon(poly)
            if g.is_valid:
                big_P.append(g)
BIG_UNION = unary_union(big_P).buffer(0) if big_P else Point(0, 0).buffer(0)

# 水面掩码
X0, X1, Y0, Y1 = -6844.0, 3924.0, -4800.0, 3224.0
wm = np.array(Image.open(os.path.join(RDR2, "deliverable/terrain/water_mask.png")))
WM_H, WM_W = wm.shape
MPP = 4.0

def land_frac(x, y, radius_m=200):
    c = int(round((x - X0) / MPP)); r = int(round((Y1 - y) / MPP))
    rad = int(radius_m / MPP)
    c0, c1 = max(0, c - rad), min(WM_W, c + rad)
    r0, r1 = max(0, r - rad), min(WM_H, r + rad)
    if c1 <= c0 or r1 <= r0:
        return 0.0
    return float((wm[r0:r1, c0:c1] < 128).mean())

SPACING = 2200.0
HEX_R = SPACING / math.sqrt(3.0)
T = 3072
W = 1000
O = T + 2 * W
def hex_centers():
    dx = SPACING
    dy = 1.5 * HEX_R
    ncol = int((X1 - X0) // dx) + 2
    nrow = int((Y1 - Y0) // dy) + 2
    pts = []
    for j in range(nrow):
        for i in range(ncol):
            x = X0 + (i + 0.5) * dx + (dx / 2 if j % 2 else 0)
            y = Y1 - (j + 0.5) * dy
            if X0 <= x <= X1 and Y0 <= y <= Y1:
                pts.append((x, y))
    return pts

bubbles = []
for x, y in hex_centers():
    if land_frac(x, y) < 0.02:
        continue
    bubbles.append({"id": "wild_%02d" % (len(bubbles) + 1), "x": round(x, 1), "y": round(y, 1),
                    "land": round(land_frac(x, y), 3), "T": T, "W": W, "O": O,
                    "small_codes": [], "small_names": []})

# 小据点并进最近气泡
for c in small:
    sx, sy = info[c]["x"], info[c]["y"]
    best = min(bubbles, key=lambda b: (b["x"] - sx) ** 2 + (b["y"] - sy) ** 2)
    dx = abs(best["x"] - sx); dy = abs(best["y"] - sy)
    best["small_codes"].append(c)
    best["small_names"].append(info[c]["name"])
    if dx > T / 2 or dy > T / 2:
        print("OUTSIDE", c, info[c]["name"], "dist", round(math.hypot(dx, dy), 0), best["id"])

json.dump(bubbles, open(os.path.join(BASE, "bubbles.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("bubbles", len(bubbles), "assigned smalls", sum(len(b["small_codes"]) for b in bubbles))
for b in bubbles:
    print(b["id"], b["x"], b["y"], "land", b["land"], "->", "、".join(b["small_names"]) or "—")
