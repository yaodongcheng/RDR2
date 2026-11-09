# -*- coding: utf-8 -*-
"""算每个据点的可走多边形 P 和领地边界（按建成区边界采样的 Voronoi）。

P = 建成区（官方 TOWN 多边形，没有则用 bbox 椭圆）+ 外扩边距
    ∩ 本据点领地（到其他据点**建成区边界**更近的区域）
    ∩ 场景地形方框 T（并进野外的用宿主 2304 m 方框）

输出：_scratch/settlement_plan/settlements_p.json
"""
import csv, json, math, os
import numpy as np
from shapely.geometry import Point, Polygon, MultiPolygon, MultiPoint, LineString, box
from shapely.ops import unary_union, voronoi_diagram
from shapely.strtree import STRtree

RDR2 = r"D:\BrainMaker\大镖客2解包分析"
BASE = os.path.join(RDR2, "_scratch", "settlement_plan")

rows = list(csv.DictReader(open(os.path.join(BASE, "settlements_plan.csv"), encoding="utf-8-sig")))
wild = list(csv.DictReader(open(os.path.join(BASE, "wild_anchors.csv"), encoding="utf-8-sig")))
wild_by_id = {w["wid"]: w for w in wild}
zones = json.load(open(os.path.join(RDR2, "export/levels/world/zones.json"), encoding="utf-8"))["zones"]

ZONE_MAP = {
    "StDenis": "sdn", "Rhodes": "rho", "Butcher": "but", "Armadillo": "arm",
    "Tumbleweed": "tum", "Braithwaite": "bra", "Caliga": "cal", "BeechersHope": "bee",
}
zone_by_code = {}
for z in zones:
    if z.get("type") != "TOWN":
        continue
    code = ZONE_MAP.get(z.get("name"))
    if code:
        polys = []
        for p in z.get("polygons", []):
            if len(p) >= 3:
                try:
                    g = Polygon(p)
                    if not g.is_valid:
                        g = g.buffer(0)
                    if g.area > 100:
                        polys.append(g)
                except Exception:
                    pass
        if polys:
            zone_by_code[code] = unary_union(polys)

def f(x):
    try:
        return float(x)
    except Exception:
        return 0.0

MARGIN = {"town": 150.0, "castle": 120.0, "village": 80.0, "camp": 80.0, "poi": 60.0, "hideout": 60.0}

X0, X1 = -6844.0, 3924.0
Y0, Y1 = -4800.0, 3224.0
ENV = box(X0 - 500, Y0 - 500, X1 + 500, Y1 + 500)

def ellipse(x, y, a, b, n=64):
    pts = []
    for k in range(n):
        ang = 2 * math.pi * k / n
        pts.append((x + a * math.cos(ang), y + b * math.sin(ang)))
    return Polygon(pts)

def boundary_samples(geom, code, step=12.0):
    """沿建成区外边界采样，每 ~step 米一个点。"""
    out = []
    geoms = []
    if geom.geom_type == "Polygon":
        geoms = [geom]
    elif geom.geom_type == "MultiPolygon":
        geoms = list(geom.geoms)
    for g in geoms:
        if g.is_empty or len(g.exterior.coords) < 3:
            continue
        line = LineString(g.exterior.coords)
        L = line.length
        if L <= 0:
            continue
        n = max(4, int(round(L / step)))
        for k in range(n):
            p = line.interpolate(k / n, normalized=True)
            out.append((p.x, p.y, code))
    if not out:
        out.append((geom.centroid.x, geom.centroid.y, code))
    return out

def simplify_polys(g, tol=2.0, min_area=50):
    if g.is_empty:
        return []
    if g.geom_type == "Polygon":
        g = g.simplify(tol)
        if g.is_empty or g.area < min_area:
            return []
        return [[[round(x, 1), round(y, 1)] for x, y in g.exterior.coords]]
    if g.geom_type == "MultiPolygon":
        out = []
        for p in g.geoms:
            out.extend(simplify_polys(p, tol, min_area))
        return out
    if g.geom_type == "GeometryCollection":
        out = []
        for p in g.geoms:
            out.extend(simplify_polys(p, tol, min_area))
        return out
    return []

# 建成区（不含 margin）
built = {}
for r in rows:
    code = r["code"]
    x, y = f(r["world_x"]), f(r["world_y"])
    if code in zone_by_code:
        built[code] = zone_by_code[code]
    else:
        built[code] = ellipse(x, y, max(8.0, f(r["size_w"]) / 2.0), max(8.0, f(r["size_d"]) / 2.0))

# 采样 + Voronoi
samples = []
for code, g in built.items():
    samples.extend(boundary_samples(g, code))
print("samples", len(samples))

pts = MultiPoint([(x, y) for x, y, _ in samples])
vor = voronoi_diagram(pts, envelope=ENV)
cells = list(vor.geoms)
print("cells", len(cells))
tree = STRtree(cells)

by_code = {code: [] for code in built}
miss = 0
for x, y, code in samples:
    pnt = Point(x, y)
    cand = tree.query(pnt)
    found = False
    for idx in cand:
        cell = cells[int(idx)]
        if cell.covers(pnt):
            by_code[code].append(cell)
            found = True
            break
    if not found:
        # 落在边界上/数值误差：取第一个 covers(buffer(0.5))
        for idx in cand:
            cell = cells[int(idx)]
            if cell.buffer(0.5).covers(pnt):
                by_code[code].append(cell)
                found = True
                break
    if not found:
        miss += 1
print("miss", miss)

territory = {}
for code, cs in by_code.items():
    if cs:
        valid = []
        for c in cs:
            if c.is_empty:
                continue
            if not c.is_valid:
                c = c.buffer(0)
            if not c.is_empty:
                valid.append(c)
        territory[code] = unary_union(valid).buffer(0)
    else:
        # 兜底：点周围 1 km
        p = built[code].centroid
        territory[code] = box(p.x - 500, p.y - 500, p.x + 500, p.y + 500)

out = {}
print(f"{'code':7}{'P km2':>9}{'P max':>8}{'T':>6}{'R':>6}{'terr':>8}  note")
for r in rows:
    code = r["code"]
    x, y = f(r["world_x"]), f(r["world_y"])
    btype = r["rdr2_type"]
    margin = MARGIN.get(btype, 80.0)
    host = r["embed_into"] or ""
    b = built[code]
    if code in zone_by_code:
        bm = b.buffer(margin, join_style=1, resolution=16)
        kind = "official"
    else:
        bm = ellipse(x, y, max(8.0, f(r["size_w"]) / 2.0) + margin,
                     max(8.0, f(r["size_d"]) / 2.0) + margin)
        kind = "ellipse"
    T = float(r["scene_T_m"])
    if host and host in wild_by_id:
        hx, hy = f(wild_by_id[host]["x"]), f(wild_by_id[host]["y"])
        sq = box(hx - 2304 / 2, hy - 2304 / 2, hx + 2304 / 2, hy + 2304 / 2)
    else:
        sq = box(x - T / 2, y - T / 2, x + T / 2, y + T / 2)
    terr = territory[code].intersection(ENV).buffer(0)
    P = bm.intersection(terr).intersection(sq).buffer(0)
    area = P.area
    bb = P.bounds if not P.is_empty else (0, 0, 0, 0)
    pmax = max(bb[2] - bb[0], bb[3] - bb[1])
    out[code] = {
        "P": simplify_polys(P),
        "cell": simplify_polys(terr, tol=4.0),
        "P_area_km2": round(area / 1e6, 4),
        "P_max_m": round(pmax, 0),
        "kind": kind,
        "cell_area_km2": round(terr.area / 1e6, 3),
    }
    print(f"{code:7}{area/1e6:9.3f}{pmax:8.0f}{T:6.0f}{f(r['backdrop_R_m']):6.0f}{terr.area/1e6:8.2f}  {kind}")

json.dump(out, open(os.path.join(BASE, "settlements_p.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved", os.path.join(BASE, "settlements_p.json"))
