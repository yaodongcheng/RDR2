# -*- coding: utf-8 -*-
"""把所有可行走 P 裁到真实地图边界（meta.world 的 x0..x1 / y0..y1）。

- settlements_p.json：P / cell / P_area / P_max / cell_area
- bubbles.json：增加 P（3,072 场景 ∩ 真实地图框）/ P_area / P_max
- regions.json：P / area / bbox / T_whole（按裁剪后的 bbox 重算）

边界外的部分 = 扩充区，不可走，只做远景。
"""
import json, math, os, io, csv
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

RDR2 = r"D:\BrainMaker\大镖客2解包分析"
BASE = os.path.join(RDR2, "_scratch", "settlement_plan")
meta = json.load(open(os.path.join(RDR2, "deliverable/terrain/on_map/meta.json"), encoding="utf-8"))["mainland"]["world"]
FRAME = box(meta["x0"], meta["y0"], meta["x1"], meta["y1"])
print("frame", FRAME.bounds)

def simp(g, tol=2.0, min_area=100):
    if g.is_empty:
        return []
    if g.geom_type == "Polygon":
        g = g.simplify(tol)
        return [[[round(x, 1), round(y, 1)] for x, y in g.exterior.coords]] if g.area > min_area else []
    if g.geom_type == "MultiPolygon":
        out = []
        for p in g.geoms:
            out.extend(simp(p, tol, min_area))
        return out
    if g.geom_type == "GeometryCollection":
        out = []
        for p in g.geoms:
            out.extend(simp(p, tol, min_area))
        return out
    return []

def geom(polys):
    ps = []
    for poly in polys or []:
        if len(poly) >= 3:
            g = Polygon(poly)
            if g.is_valid and g.area > 50:
                ps.append(g)
    return unary_union(ps).buffer(0) if ps else Polygon()

def bbox_max(g):
    if g.is_empty:
        return 0
    b = g.bounds
    return max(b[2] - b[0], b[3] - b[1])

# ---- settlements ----
pdata = json.load(open(os.path.join(BASE, "settlements_p.json"), encoding="utf-8"))
for code, d in pdata.items():
    P = geom(d.get("P", [])).intersection(FRAME).buffer(0)
    C = geom(d.get("cell", [])).intersection(FRAME).buffer(0)
    d["P"] = simp(P)
    d["cell"] = simp(C, tol=4.0)
    d["P_area_km2"] = round(P.area / 1e6, 4)
    d["P_max_m"] = round(bbox_max(P), 0)
    d["cell_area_km2"] = round(C.area / 1e6, 3)
json.dump(pdata, open(os.path.join(BASE, "settlements_p.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("settlements clipped; sdn", pdata.get("sdn", {}).get("P_area_km2"))

# ---- bubbles ----
bubbles = json.load(open(os.path.join(BASE, "bubbles.json"), encoding="utf-8"))
for b in bubbles:
    sq = box(b["x"] - b["T"] / 2, b["y"] - b["T"] / 2, b["x"] + b["T"] / 2, b["y"] + b["T"] / 2)
    P = sq.intersection(FRAME).buffer(0)
    b["P"] = simp(P)
    b["P_area_km2"] = round(P.area / 1e6, 4)
    b["P_max_m"] = round(bbox_max(P), 0)
    b["clipped"] = bool(P.area < sq.area - 1)
json.dump(bubbles, open(os.path.join(BASE, "bubbles.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("bubbles clipped", sum(1 for b in bubbles if b["clipped"]), "of", len(bubbles))

# ---- regions ----
regions = json.load(open(os.path.join(BASE, "regions.json"), encoding="utf-8"))
_rows = list(csv.DictReader(open(os.path.join(BASE, "settlements_plan.csv"), encoding="utf-8-sig")))
SEED_XY = {r["code"]: (float(r["world_x"]), float(r["world_y"])) for r in _rows}
for r in regions:
    P = geom(r.get("P", [])).intersection(FRAME).buffer(0)
    r["P"] = simp(P)
    r["area_km2"] = round(P.area / 1e6, 3)
    r["bbox"] = [round(v, 1) for v in P.bounds] if not P.is_empty else [0, 0, 0, 0]
    # 若整区一个 scene 的 T（按裁剪后 bbox + 300 留边，256 对齐）
    seed = r["seed"]
    b = r["bbox"]
    if not P.is_empty:
        sx, sy = SEED_XY.get(seed, ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))
        half = max(abs(sx - b[0]), abs(sx - b[2]), abs(sy - b[1]), abs(sy - b[3]))
        r["T_whole"] = int(math.ceil((2 * half + 300) / 256.0) * 256)
json.dump(regions, open(os.path.join(BASE, "regions.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("regions clipped", len(regions))
