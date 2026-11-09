# -*- coding: utf-8 -*-
"""把 44 块领地合并成 22 个区域（一个大据点 = 一个 scene）。

规则：
  1. 22 个大据点（9 城 + 11 堡 + 2 藏身处）是 22 个种子，各自保留自己的领地。
  2. 22 个小据点（11 村 + 5 营地 + 6 点位）的领地，按“相邻格子最短路”并入最近的大据点。
  3. 区域 P = 并进来的所有格子 union；区域之间不重叠（格子本身不重叠）。
  4. 场景 T = 以 大据点为中心、覆盖整个区域 P 的方形，+300 m 留边，256 对齐。

输出：
  _scratch/settlement_plan/regions.csv
  _scratch/settlement_plan/regions_table.md
  _scratch/settlement_plan/regions_map.png
"""
import csv, json, math, os, heapq
from shapely.geometry import Polygon, MultiPolygon, Point, box
from shapely.ops import unary_union
from PIL import Image, ImageDraw, ImageFont

RDR2 = r"D:\BrainMaker\大镖客2解包分析"
BASE = os.path.join(RDR2, "_scratch", "settlement_plan")
OUT = BASE

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

info = {}
cells = {}
for r in rows:
    code = r["code"]
    info[code] = {
        "name": r["name_zh"], "tier": r["tier"], "type": r["rdr2_type"],
        "x": f(r["world_x"]), "y": f(r["world_y"]),
    }
    polys = []
    for poly in pdata.get(code, {}).get("cell", []):
        if len(poly) >= 3:
            g = Polygon(poly)
            if g.is_valid and g.area > 100:
                polys.append(g)
    if polys:
        cells[code] = unary_union(polys).buffer(0)
    else:
        cells[code] = Point(info[code]["x"], info[code]["y"]).buffer(200)

codes = list(info.keys())
# 大据点 = city / castle / hideout；其余为小据点
big = [c for c in codes if info[c]["tier"] in ("city", "castle") or info[c]["type"] == "hideout"]
small = [c for c in codes if c not in big]
print("big", len(big), "small", len(small))

# 邻接（共享边界）
neighbors = {c: [] for c in codes}
for i, a in enumerate(codes):
    for b in codes[i + 1:]:
        ga, gb = cells[a], cells[b]
        if ga.distance(gb) < 2.0 or ga.buffer(1).intersects(gb):
            neighbors[a].append(b)
            neighbors[b].append(a)
print("neighbors", {c: len(v) for c, v in neighbors.items() if len(v) == 0})

# 多源 Dijkstra：按相邻格子的中心距离累加
region_of = {c: c for c in big}
region_cells = {c: [c] for c in big}
pq = []
for seed in big:
    for nb in neighbors[seed]:
        if nb in region_of:
            continue
        d = Point(info[seed]["x"], info[seed]["y"]).distance(cells[nb].centroid)
        heapq.heappush(pq, (d, seed, nb))
while pq:
    d, seed, node = heapq.heappop(pq)
    if node in region_of:
        continue
    region_of[node] = seed
    region_cells[seed].append(node)
    for nb in neighbors[node]:
        if nb not in region_of:
            nd = d + cells[node].centroid.distance(cells[nb].centroid)
            heapq.heappush(pq, (nd, seed, nb))
# 兜底：不相邻的孤岛（如小岛）按最近距离并入
for c in codes:
    if c not in region_of:
        seed = min(big, key=lambda b: cells[c].distance(cells[b]))
        region_of[c] = seed
        region_cells[seed].append(c)
print("assigned", len(region_of), "of", len(codes))

# 区域 P / bbox / T
regions = []
for seed in big:
    codes_in = region_cells[seed]
    geom = unary_union([cells[c] for c in codes_in]).buffer(0)
    area = geom.area / 1e6
    b = geom.bounds
    cx, cy = info[seed]["x"], info[seed]["y"]
    half = max(abs(cx - b[0]), abs(cx - b[2]), abs(cy - b[1]), abs(cy - b[3]))
    T = int(math.ceil((2 * half + 300) / 256.0) * 256)
    T = max(768, T)
    smalls = [c for c in codes_in if c != seed]
    regions.append({
        "seed": seed, "name": info[seed]["name"], "tier": info[seed]["tier"], "type": info[seed]["type"],
        "codes": codes_in, "smalls": smalls, "geom": geom, "area": area,
        "bbox": b, "T": T, "cx": cx, "cy": cy,
    })

regions.sort(key=lambda r: ({"city": 0, "castle": 1, "village": 2}.get(r["tier"], 3), -r["area"]))
def simp(g, tol=2.0):
    if g.is_empty:
        return []
    if g.geom_type == "Polygon":
        g = g.simplify(tol)
        return [[[round(x, 1), round(y, 1)] for x, y in g.exterior.coords]] if g.area > 100 else []
    if g.geom_type == "MultiPolygon":
        out = []
        for p in g.geoms:
            out.extend(simp(p, tol))
        return out
    if g.geom_type == "GeometryCollection":
        out = []
        for p in g.geoms:
            out.extend(simp(p, tol))
        return out
    return []

regions_json = []
for r in regions:
    regions_json.append({
        "seed": r["seed"], "name": r["name"], "tier": r["tier"], "type": r["type"],
        "small_codes": r["smalls"], "small_names": [info[c]["name"] for c in r["smalls"]],
        "codes": r["codes"], "area_km2": round(r["area"], 3),
        "bbox": [round(v, 1) for v in r["bbox"]], "T_whole": r["T"],
        "P": simp(r["geom"]),
    })
json.dump(regions_json, open(os.path.join(OUT, "regions.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("regions.json", len(regions_json))


# CSV
with open(os.path.join(OUT, "regions.csv"), "w", encoding="utf-8-sig", newline="") as fh:
    wr = csv.writer(fh)
    wr.writerow(["seed", "name", "tier", "type", "area_km2", "bbox_x0", "bbox_y0", "bbox_x1", "bbox_y1", "scene_T_m", "smalls", "codes"])
    for r in regions:
        wr.writerow([r["seed"], r["name"], r["tier"], r["type"], round(r["area"], 3),
                     round(r["bbox"][0], 1), round(r["bbox"][1], 1), round(r["bbox"][2], 1), round(r["bbox"][3], 1),
                     r["T"], "、".join(info[c]["name"] for c in r["smalls"]), "|".join(r["codes"])])

# Markdown table
lines = []
lines.append("| # | 区域（大据点） | 层级 | 并入的小据点 | P 面积 km² | 区域 bbox (m) | 场景 T 估算 (m) |")
lines.append("|---:|---|---|---|---:|---|---:|")
for i, r in enumerate(regions, 1):
    names = "、".join(info[c]["name"] for c in r["smalls"]) or "—"
    b = r["bbox"]
    lines.append(f'| {i} | {r["name"]} `{r["seed"]}` | {r["tier"]} | {names} | {r["area"]:.2f} | {b[2]-b[0]:.0f} × {b[3]-b[1]:.0f} | **{r["T"]}** |')
open(os.path.join(OUT, "regions_table.md"), "w", encoding="utf-8").write("\n".join(lines))
print("table written")
print("saved", os.path.join(OUT, "regions.csv"))

# ---------- 地图 ----------
meta = json.load(open(os.path.join(RDR2, "deliverable/terrain/on_map/meta.json"), encoding="utf-8"))["mainland"]["world"]
BOX_L, BOX_T, BOX_R, BOX_B = 146, 388, 4804, 3851
overlay = Image.open(os.path.join(RDR2, "deliverable/terrain/on_map/mainland_overlay.png")).convert("RGBA")
OW, OH = overlay.size
MX0, MX1, MY0, MY1 = meta["x0"], meta["x1"], meta["y0"], meta["y1"]
BW, BH = BOX_R - BOX_L, BOX_B - BOX_T

def w2p(x, y):
    return (BOX_L + (x - MX0) / (MX1 - MX0) * BW,
            BOX_T + (MY1 - y) / (MY1 - MY0) * BH)

img = overlay.copy()
layer = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
d = ImageDraw.Draw(layer, "RGBA")
# 调色板
PALETTE = [
    (214, 39, 40), (255, 127, 14), (44, 160, 44), (31, 119, 180), (148, 103, 189),
    (140, 86, 75), (227, 119, 194), (188, 189, 34), (23, 190, 207), (174, 199, 232),
    (255, 187, 120), (152, 223, 138), (197, 176, 213), (196, 156, 148), (247, 182, 210),
    (199, 199, 199), (219, 219, 141), (158, 218, 229), (255, 152, 150), (255, 204, 130),
    (176, 220, 170), (190, 174, 212),
]
# 区域填充
for i, r in enumerate(regions):
    col = PALETTE[i % len(PALETTE)]
    geom = r["geom"]
    geoms = [geom] if geom.geom_type == "Polygon" else list(geom.geoms) if geom.geom_type == "MultiPolygon" else []
    for g in geoms:
        pts = [w2p(x, y) for x, y in g.exterior.coords]
        if len(pts) >= 3:
            d.polygon(pts, fill=(*col, 95), outline=(*col, 255))
# 区域边界/格子边界
for i, r in enumerate(regions):
    col = PALETTE[i % len(PALETTE)]
    for c in r["codes"]:
        g = cells[c]
        geoms = [g] if g.geom_type == "Polygon" else list(g.geoms) if g.geom_type == "MultiPolygon" else []
        for gg in geoms:
            pts = [w2p(x, y) for x, y in gg.exterior.coords]
            if len(pts) >= 3:
                d.line(pts + [pts[0]], fill=(255, 255, 255, 150), width=2)

# 字体
FONT = r"C:\Windows\Fonts\msyh.ttc"
def font(sz, bold=False):
    return ImageFont.truetype(FONT, sz)

def halo(xy, s, sz, fill=(20, 16, 12), halo_c=(255, 255, 255), w=3):
    fnt = font(sz)
    for dx in (-w, 0, w):
        for dy in (-w, 0, w):
            d.text((xy[0] + dx, xy[1] + dy), s, font=fnt, fill=halo_c)
    d.text(xy, s, font=fnt, fill=fill)

# 大据点标记 + 名字
for r in regions:
    x, y = w2p(r["cx"], r["cy"])
    if r["tier"] == "city":
        d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=(255, 210, 70), outline=(20, 16, 12), width=3)
    elif r["tier"] == "castle":
        d.polygon([(x, y - 9), (x + 9, y), (x, y + 9), (x - 9, y)], fill=(95, 175, 255), outline=(20, 16, 12))
    else:
        d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(110, 220, 120), outline=(20, 16, 12), width=2)
    halo((x + 13, y - 12), r["name"], 30, (20, 16, 12))

# 小据点名字
for c in small:
    x, y = w2p(info[c]["x"], info[c]["y"])
    d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(40, 30, 20), outline=(255, 250, 240), width=1)
    halo((x + 8, y - 9), info[c]["name"], 20, (40, 30, 20))

# 标题
d.rectangle([0, 0, OW, 96], fill=(28, 24, 18, 235))
halo((28, 18), "22 个区域 = 22 个 scene（大据点 + 并入的小据点）", 52, (250, 246, 236), halo_c=(28, 24, 18))
# 图例
d.rectangle([60, 120, 1160, 250], fill=(250, 246, 236, 230), outline=(30, 24, 18), width=2)
halo((80, 130), "彩色块 = 区域 P（不重叠，一个区域一个 scene）", 26, (30, 24, 18))
halo((80, 170), "白线 = 据点领地边界；黄星 = 城市；蓝菱 = 城堡；绿点 = 藏身处", 24, (30, 24, 18))
halo((80, 208), "小黑点 = 并入的小据点；远景外框可重叠，图上不画", 24, (30, 24, 18))

out = Image.alpha_composite(img, layer).convert("RGB")
out.save(os.path.join(OUT, "regions_map.png"))
print("map saved", out.size)
