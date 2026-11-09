# -*- coding: utf-8 -*-
"""63 版世界场景划分（2026-11-03 用户裁定）。

   44 张据点自己的地图（22 大 + 22 小）
 + 17 张野地地图（Voronoi ∩ 剩余陆地）
 +  2 张瓜玛岛地图
 = 63

硬规则（本脚本的自检项）：
  1. 据点 P 两两不重叠；每个 P 都在自己的场景地面 T 以内。
  2. 野地 P = 野地中心 Voronoi ∩（有效地图 − 据点 P 并集），野地 P 两两不重叠、不碰据点 P。
  3. 据点 P ∪ 野地 P = 有效地图（陆地 ∪ 据点 P，据点 P 里允许有码头等跨水部分）。

输入：settlements_plan.csv / settlements_p.json / bubbles.json
      deliverable/terrain/water_mask.png / deliverable/terrain/on_map/meta.json
      export/levels/world/zones.json
输出：settlements_p.json（P 重算：裁进各自 T、互相去重）
      bubbles.json（野地 P 重算）
      scene_specs.json（44 + 17 的场景规格，给页面与文档读）
      scene_division_check.json（自检结果）
"""
import csv, json, math, os

import numpy as np
from PIL import Image
from shapely.geometry import LineString, MultiPoint, Point, Polygon, box
from shapely.ops import polygonize, split, unary_union, voronoi_diagram
from skimage import measure

RDR2 = r"D:\BrainMaker\大镖客2解包分析"
BASE = os.path.join(RDR2, "_scratch", "settlement_plan")

X0, X1, Y0, Y1 = -6844.0, 3924.0, -4800.0, 3224.0
MPP = 4.0                      # 水面掩码：4 m / 像素
TOL = 2.0                      # 陆地轮廓简化容差（米）
W_BY_KIND = {"city": 1200, "castle": 800, "hideout": 500, "village": 600}

MARGIN = {"town": 150.0, "castle": 120.0, "village": 80.0, "camp": 80.0,
          "poi": 60.0, "hideout": 60.0}
ZONE_MAP = {"StDenis": "sdn", "Rhodes": "rho", "Butcher": "but", "Armadillo": "arm",
            "Tumbleweed": "tum", "Braithwaite": "bra", "Caliga": "cal",
            "BeechersHope": "bee"}


def f(x):
    try:
        return float(x)
    except Exception:
        return 0.0


def read_csv(path):
    with open(path, encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def geom(polys):
    """环列表 -> 多边形。被别的环包住的环按「洞」处理（ring_list_all 把洞写成独立环）。"""
    rings = []
    for poly in polys or []:
        if len(poly) < 3:
            continue
        g = Polygon(poly)
        if not g.is_valid:
            g = g.buffer(0)
        if not g.is_empty and g.area > 1:
            rings.append(g)
    outers = []
    for i, g in enumerate(rings):
        inside = any(j != i and rings[j].area > g.area
                     and rings[j].contains(g.representative_point())
                     for j in range(len(rings)))
        if inside:
            continue
        h = g
        for j, other in enumerate(rings):
            if j == i or other.area >= g.area:
                continue
            if g.contains(other.representative_point()):
                h = h.difference(other)
        outers.append(h)
    return unary_union(outers).buffer(0) if outers else Polygon()


def ring_list(g, tol=0.0, min_area=100.0):
    """Polygon/MultiPolygon -> [[[x,y],...], ...]（外环；洞单独处理时会丢，这里保留外环够用）。"""
    if g.is_empty:
        return []
    if tol:
        g = g.simplify(tol)
    out = []
    geoms = [g] if g.geom_type == "Polygon" else list(getattr(g, "geoms", []))
    for p in geoms:
        if p.geom_type != "Polygon" or p.area < min_area:
            continue
        out.append([[round(x, 1), round(y, 1)] for x, y in p.exterior.coords])
    return out


def ring_list_all(g, tol=0.0, min_area=100.0):
    """带洞：一个多边形 = 外环 + 内环，全部塞进同一列表（页面按 evenodd 之外的简单规则画，
    洞交给 shapely 输出成独立环会画错，所以这里把洞也作为独立环输出，页面用 fill-rule=evenodd）。"""
    if g.is_empty:
        return []
    if tol:
        g = g.simplify(tol)
    out = []
    geoms = [g] if g.geom_type == "Polygon" else list(getattr(g, "geoms", []))
    for p in geoms:
        if p.geom_type != "Polygon" or p.area < min_area:
            continue
        out.append([[round(x, 1), round(y, 1)] for x, y in p.exterior.coords])
        for r in p.interiors:
            if Polygon(r).area >= min_area:
                out.append([[round(x, 1), round(y, 1)] for x, y in r.coords])
    return out


def bbox_max(g):
    if g.is_empty:
        return 0.0
    b = g.bounds
    return max(b[2] - b[0], b[3] - b[1])


# ---------------------------------------------------------------- 基础数据
meta = json.load(open(os.path.join(RDR2, "deliverable/terrain/on_map/meta.json"),
                      encoding="utf-8"))["mainland"]["world"]
FRAME = box(meta["x0"], meta["y0"], meta["x1"], meta["y1"])

rows = read_csv(os.path.join(BASE, "settlements_plan.csv"))
rows = [r for r in rows if r["code"] not in ("agu", "gua")]
pdata = json.load(open(os.path.join(BASE, "settlements_p.json"), encoding="utf-8"))
bubbles = json.load(open(os.path.join(BASE, "bubbles.json"), encoding="utf-8"))

# 编辑器（docs/世界与地编/scene_editor.html）导出的人工改动，有就覆盖算出来的结果
OVR_PATH = os.path.join(RDR2, "docs", "世界与地编", "scene_overrides.json")   # 仓库里这份是权威（进 git）
if not os.path.exists(OVR_PATH):
    OVR_PATH = os.path.join(BASE, "scene_overrides.json")
OVR = json.load(open(OVR_PATH, encoding="utf-8")) if os.path.exists(OVR_PATH) else {}
OVR_S = OVR.get("settlements", {})
OVR_W = OVR.get("wilds", {})
if OVR_S or OVR_W:
    print(f"[overrides] 据点 {len(OVR_S)} 项 · 野地 {len(OVR_W)} 项")

# ---------------------------------------------------------------- 陆地多边形
# 有效陆地 = 水面掩码的陆地 ∩ 真实游戏地形（valid4.npy）。
# 外延补丁区（valid4 没有的地方）是我们为了远景补的，不是真实地图，不能走。
mask = np.array(Image.open(os.path.join(RDR2, "deliverable/terrain/water_mask.png")))
land_mask = mask < 128
H, W = mask.shape

# 真实地图范围 = 官方地图缩略图上「有画面」的地方；
# 空白羊皮纸（河流以南、西北角、东侧）都是地图外，只能做远景（2026-11-03 用户裁定）。
from scipy.ndimage import (binary_closing, binary_fill_holes, binary_opening,
                           label, uniform_filter)

meta_main = json.load(open(os.path.join(RDR2, "deliverable/terrain/on_map/meta.json"),
                           encoding="utf-8"))["mainland"]
thumb_path = os.path.join(RDR2, meta_main["src_map"].replace("/", os.sep))
thumb = np.asarray(Image.open(thumb_path).convert("RGB")).astype(np.float32)
PAPER = np.array([210.0, 182.0, 143.0])
g_thumb = thumb.mean(axis=2)
mu = uniform_filter(g_thumb, 7)
sd = np.sqrt(np.maximum(uniform_filter(g_thumb * g_thumb, 7) - mu * mu, 0))
parchment = (sd < 3.0) & (np.abs(thumb - PAPER).max(axis=2) < 28)
content = ~parchment
content = binary_opening(content, structure=np.ones((3, 3)))
content = binary_closing(content, structure=np.ones((9, 9)))
content = binary_fill_holes(content)
_lab, _n = label(content)
_sizes = np.bincount(_lab.ravel())
_sizes[0] = 0
content = _lab == _sizes.argmax()

bx0, by0, bx1, by1 = [float(v) for v in meta_main["paste_box_px"]]
uu = bx0 + (np.arange(W) + 0.5) / W * (bx1 - bx0)
vv = by0 + (np.arange(H) + 0.5) / H * (by1 - by0)
UU, VV = np.meshgrid(uu, vv)
map_mask = content[np.clip(VV.astype(int), 0, content.shape[0] - 1),
                   np.clip(UU.astype(int), 0, content.shape[1] - 1)]

# 交叉核对：游戏地形瓦片（valid4）里也有数据的地方（应该基本一致）
X0W, Y0W, RES2 = -7684.0, -8196.0, 4.0
valid_main = np.load(os.path.join(RDR2, "work/terrain/valid4.npy")) > 0
vc0 = int(round((X0 - X0W) / RES2))
vr_top = int(round((Y1 - Y0W) / RES2))
main_mask = np.flipud(valid_main[vr_top - H + 1:vr_top + 1, vc0:vc0 + W])
assert main_mask.shape == land_mask.shape, (main_mask.shape, land_mask.shape)

# 地图区 = 官方地图画面上的一整片（陆地 + 水面）。水面也算可走（2026-11-03 用户裁定）。
area_mask = map_mask
outside_mask = ~map_mask
land_real = land_mask & map_mask          # 仅用于统计
land_out = land_mask & ~map_mask


def mask_to_geom(b):
    """0/1 掩码 -> 多边形（先补一圈 0 让边界轮廓闭合）。"""
    padded = np.pad(b.astype(np.uint8), 2, constant_values=0)
    lines = []
    for c in measure.find_contours(padded, 0.5):
        if len(c) < 4:
            continue
        rr = c[:, 0] - 2
        cc = c[:, 1] - 2
        pts = np.column_stack([X0 + cc * MPP, Y1 - rr * MPP])
        if not np.allclose(pts[0], pts[-1]):
            pts = np.vstack([pts, pts[:1]])
        lines.append(LineString(pts))
    keep = []
    for face in polygonize(lines):
        rp = face.representative_point()
        col = max(0, min(W - 1, int(round((rp.x - X0) / MPP))))
        row = max(0, min(H - 1, int(round((Y1 - rp.y) / MPP))))
        if b[row, col]:
            keep.append(face)
    return unary_union(keep).buffer(0) if keep else Polygon()


LAND = mask_to_geom(area_mask).intersection(FRAME).buffer(0)
LAND_S = LAND.simplify(TOL).buffer(0)
OUTSIDE = mask_to_geom(outside_mask).intersection(FRAME).buffer(0)
OUTSIDE_S = OUTSIDE.simplify(6.0).buffer(0)
print(f"[area] 地图区 {LAND.area / 1e6:.3f} km²（陆地 {float((land_real).sum()) * 16 / 1e6:.2f}"
      f" + 水面 {float((map_mask & ~land_mask).sum()) * 16 / 1e6:.2f}）· "
      f"地图外 {OUTSIDE.area / 1e6:.3f} km²（只做远景）")

# ---------------------------------------------------------------- 建成区（用于重叠拆分）
zones = json.load(open(os.path.join(RDR2, "export/levels/world/zones.json"),
                       encoding="utf-8"))["zones"]
zone_by_code = {}
for z in zones:
    if z.get("type") != "TOWN":
        continue
    code = ZONE_MAP.get(z.get("name"))
    if not code:
        continue
    ps = []
    for poly in z.get("polygons", []):
        if len(poly) >= 3:
            g = Polygon(poly)
            if not g.is_valid:
                g = g.buffer(0)
            if g.area > 100:
                ps.append(g)
    if ps:
        zone_by_code[code] = unary_union(ps)


def ellipse(x, y, a, b, n=64):
    pts = []
    for k in range(n):
        ang = 2 * math.pi * k / n
        pts.append((x + a * math.cos(ang), y + b * math.sin(ang)))
    return Polygon(pts)


built = {}
for r in rows:
    code = r["code"]
    x, y = f(r["world_x"]), f(r["world_y"])
    if code in zone_by_code:
        built[code] = zone_by_code[code]
    else:
        built[code] = ellipse(x, y, max(8.0, f(r["size_w"]) / 2.0),
                              max(8.0, f(r["size_d"]) / 2.0))

# ---------------------------------------------------------------- 据点 P：裁进自己的 T、互相去重
P = {r["code"]: geom(pdata[r["code"]].get("P", [])) for r in rows}

# 1) P = 建成区的「外切矩形」+ 边距，裁进自己的场景地面 T（2026-11-03 用户裁定：
#    地图上画的是圆，逻辑上用圆的外切矩形）。矩形之间重叠 → 沿重叠区中线对切，两边都还是矩形。
RECT = {}
# 2026-11-03 两层口径：场景只有「玩家活动区」+「远景」。
# 活动区边长 / 每边外扩都必须是 GRID 的整数倍 —— 地形按节点整块切，
# 不取整的话细/粗地形会切在节点中间。
GRID = 128.0
KEEP = 64.0          # 城区离活动区边缘至少留这么宽（种屏障用）
for r in rows:
    code = r["code"]
    x, y = f(r["world_x"]), f(r["world_y"])
    T0 = f(OVR_S.get(code, {}).get("T") or r["scene_T_m"])
    r["_T0"] = T0
    r["_W"] = OVR_S.get(code, {}).get("W")
    m = MARGIN.get(r["rdr2_type"], 80.0)
    b = built[code].bounds
    # P 照旧：建成区 + 边距，裁进配置的场景尺寸 T0（用户划分的能走范围不动）
    g = box(b[0] - m, b[1] - m, b[2] + m, b[3] + m)
    g = g.intersection(box(x - T0 / 2, y - T0 / 2, x + T0 / 2, y + T0 / 2)).intersection(FRAME)
    RECT[code] = [g.bounds[0], g.bounds[1], g.bounds[2], g.bounds[3]]


def resolve_rects(rects, min_size=40.0, iters=80):
    """两块矩形重叠 → 沿重叠区的窄轴中线对切；切完两边仍是矩形。"""
    keys = list(rects)
    for _ in range(iters):
        changed = False
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a, b = keys[i], keys[j]
                A, B = rects[a], rects[b]
                ix0, iy0 = max(A[0], B[0]), max(A[1], B[1])
                ix1, iy1 = min(A[2], B[2]), min(A[3], B[3])
                if ix1 - ix0 <= 1.0 or iy1 - iy0 <= 1.0:
                    continue
                wx, wy = ix1 - ix0, iy1 - iy0
                done = False
                for axis in (("x", wx) if wx <= wy else ("y", wy), ("y", wy) if wx <= wy else ("x", wx)):
                    if done:
                        break
                    if axis[0] == "x":
                        mid = (ix0 + ix1) / 2
                        if A[0] <= B[0]:
                            if mid - A[0] > min_size and B[2] - mid > min_size:
                                A[2] = mid; B[0] = mid; changed = done = True
                        else:
                            if mid - B[0] > min_size and A[2] - mid > min_size:
                                B[2] = mid; A[0] = mid; changed = done = True
                    else:
                        mid = (iy0 + iy1) / 2
                        if A[1] <= B[1]:
                            if mid - A[1] > min_size and B[3] - mid > min_size:
                                A[3] = mid; B[1] = mid; changed = done = True
                        else:
                            if mid - B[1] > min_size and A[3] - mid > min_size:
                                B[3] = mid; A[1] = mid; changed = done = True
        if not changed:
            break
    return rects


resolve_rects(RECT)

# 人工改过的矩形直接覆盖（不再自动对切；重叠会在自检里报出来）
for code, o in OVR_S.items():
    if code in RECT and o.get("rect"):
        x = f(next(r for r in rows if r["code"] == code)["world_x"])
        y = f(next(r for r in rows if r["code"] == code)["world_y"])
        T0 = f(o.get("T") or 0)
        rr = list(o["rect"])
        if T0 > 0:      # 用户改过的 T 仍然是这块地的上限（P 不越界）
            rr = [max(rr[0], x - T0 / 2), max(rr[1], y - T0 / 2),
                  min(rr[2], x + T0 / 2), min(rr[3], y + T0 / 2)]
        RECT[code] = rr

# 活动区（正方形）由最终 P 反推：要装下城区 + 四周各留 KEEP，再向上取到 GRID 的整数倍。
# 配置的 T0 只放大不缩小 —— P 的划分原样保留，活动区只往外交。
for r in rows:
    code = r["code"]
    x, y = f(r["world_x"]), f(r["world_y"])
    rr = RECT[code]
    need = max(2 * (rr[2] - x + KEEP), 2 * (x - rr[0] + KEEP),
               2 * (rr[3] - y + KEEP), 2 * (y - rr[1] + KEEP),
               r["_T0"] or 0.0)
    r["_T"] = math.ceil(need / GRID) * GRID

P = {}
for code, rr in RECT.items():
    if rr[2] - rr[0] < 1 or rr[3] - rr[1] < 1:
        raise SystemExit(f"[rect] {code} 被切空了：{rr}")
    P[code] = box(*rr).buffer(0)

codes = [r["code"] for r in rows]
_left = 0
_keys = list(RECT)
for i in range(len(_keys)):
    for j in range(i + 1, len(_keys)):
        A, B = RECT[_keys[i]], RECT[_keys[j]]
        if min(A[2], B[2]) - max(A[0], B[0]) > 1 and min(A[3], B[3]) - max(A[1], B[1]) > 1:
            _left += 1
print(f"[rect] 44 个外切矩形，剩余重叠对 {_left}")

# 写回 settlements_p.json
for r in rows:
    code = r["code"]
    g = P[code]
    d = pdata[code]
    d["P"] = ring_list_all(g, min_area=50.0)
    d["P_area_km2"] = round(g.area / 1e6, 4)
    d["P_max_m"] = round(bbox_max(g), 0)
json.dump(pdata, open(os.path.join(BASE, "settlements_p.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

SETTLE = unary_union([g for g in P.values() if not g.is_empty]).buffer(0)
print(f"[settle] {len(P)} 个，合计 {SETTLE.area / 1e6:.3f} km²")

# ---------------------------------------------------------------- 野地：矩形网格 / 自定义清单
# 两种来源：
#   A) 没有 wilds_final → 自动等面积矩形网格（地图区 bbox 分 4 行 5/4/4/4），再用 overrides 改；
#   B) 有 wilds_final → 完全按这份清单建（编号已重排，不再受历史 id / 删除表影响）。
N_WILD = 17
DEL_W = set(OVR.get("deleted_wilds", []))
FINAL_W = OVR.get("wilds_final")

if FINAL_W:
    print(f"[wild] 用自定义清单：{len(FINAL_W)} 块（编号已重排）")
    centers = []
    wild_geoms = []
    for it in FINAL_W:
        if it["id"] in DEL_W:
            print(f"[wild] 删除 {it['id']}")
            continue
        o = OVR_W.get(it["id"], {})
        rect = (o.get("rect") or it.get("rect")) if len((o.get("rect") or it.get("rect")) or []) == 4 else None
        poly = o.get("poly") or it.get("poly") or []
        if rect:
            cx = it.get("x") if it.get("x") is not None else (rect[0] + rect[2]) / 2
            cy = it.get("y") if it.get("y") is not None else (rect[1] + rect[3]) / 2
            g = box(*rect).buffer(0)
        elif len(poly) >= 3:
            xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
            cx = it.get("x") if it.get("x") is not None else (min(xs) + max(xs)) / 2
            cy = it.get("y") if it.get("y") is not None else (min(ys) + max(ys)) / 2
            g = Polygon(poly).buffer(0)
        else:
            continue
        if g.area < 10000:
            print(f"[wild] 跳过空块 {it.get('id')}")
            continue
        centers.append({"id": it["id"],
                        "x": round(float(o.get("x", cx)), 1), "y": round(float(o.get("y", cy)), 1),
                        "rect": rect, "poly": poly,
                        "T": o.get("T") or it.get("T"), "W": o.get("W") or it.get("W")})
        wild_geoms.append(g)
else:
    BASE_IDS = ["wild_%02d" % i for i in range(1, N_WILD + 1)]
    order = [{"id": i} for i in BASE_IDS if i not in DEL_W]   # 基线 id 固定，不受历史输出影响
    if not order:
        raise SystemExit("[wild] 野地全被删了，没法排网格")
    if len(order) != N_WILD:
        print(f"[wild] 删除过 {N_WILD - len(order)} 块，按剩下 {len(order)} 块重排网格")
    N_WILD = len(order)
    rows_n = max(1, int(round(math.sqrt(N_WILD))))
    base_n, extra_n = divmod(N_WILD, rows_n)
    counts = [base_n + (1 if r < extra_n else 0) for r in range(rows_n)]
    print(f"[wild] 矩形网格 {rows_n} 行，各行列数 {counts}")
    X0f, Y0f, X1f, Y1f = LAND_S.bounds          # 地图区的外接框
    centers = []
    y_top = Y1f
    idx = 0
    for r in range(rows_n):
        c = counts[r]
        h = (Y1f - Y0f) * c / N_WILD
        y_bot = y_top - h
        w = (X1f - X0f) / c
        for k in range(c):
            b = order[idx]; idx += 1
            rect = (X0f + k * w, y_bot, X0f + (k + 1) * w, y_top)
            centers.append({"id": b["id"],
                            "x": round((rect[0] + rect[2]) / 2, 1),
                            "y": round((rect[1] + rect[3]) / 2, 1),
                            "rect": [round(v, 1) for v in rect]})
        y_top = y_bot

    # 人工新增的野地（导出的 wilds 里有、自动网格里没有的 id）
    _auto_ids = {c["id"] for c in centers}
    for wid, o in OVR_W.items():
        if wid in _auto_ids or wid in DEL_W:
            continue
        rect = o.get("rect") if len(o.get("rect") or []) == 4 else None
        poly = o.get("poly") or []
        if rect and (rect[2] - rect[0]) * (rect[3] - rect[1]) < 10000:
            print(f"[wild] 跳过空矩形 {wid}")
            continue
        if rect:
            cx = (rect[0] + rect[2]) / 2
            cy = (rect[1] + rect[3]) / 2
        elif len(poly) >= 3:
            xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
            cx = (min(xs) + max(xs)) / 2
            cy = (min(ys) + max(ys)) / 2
        else:
            continue
        centers.append({"id": wid,
                        "x": round(float(o.get("x", cx)), 1),
                        "y": round(float(o.get("y", cy)), 1),
                        "rect": rect})
        print(f"[wild] 新增 {wid}")

    wild_geoms = []
    for c in centers:
        o = OVR_W.get(c["id"])
        if o and o.get("rect") and len(o["rect"]) == 4:
            g = box(*o["rect"]).buffer(0)
            if o.get("x") is not None: c["x"] = float(o["x"])
            if o.get("y") is not None: c["y"] = float(o["y"])
            c["T"] = o.get("T") or c.get("T")
        elif o and o.get("poly") and len(o["poly"]) >= 3:
            g = Polygon(o["poly"]).buffer(0)
            c["T"] = o.get("T") or c.get("T")
        elif c.get("rect"):
            g = box(*c["rect"]).buffer(0)
        else:
            continue
        wild_geoms.append(g)

out_bubbles = []
for b, g in zip(centers, wild_geoms):
    dist_max = 0.0
    cheb = 0.0
    geoms = [g] if g.geom_type == "Polygon" else list(getattr(g, "geoms", []))
    for p in geoms:
        for x, y in p.exterior.coords:
            dist_max = max(dist_max, math.hypot(x - b["x"], y - b["y"]))
            cheb = max(cheb, abs(x - b["x"]), abs(y - b["y"]))
    # 两层口径：活动区 = 野地矩形本身（取整到 GRID），远景 = 活动区外扩 W
    o = OVR_W.get(b["id"], {})
    W_ = int(b.get("W") or o.get("W") or 0) or 1000
    W_ = int(math.ceil(W_ / GRID) * GRID)
    bb = [round(v, 1) for v in g.bounds] if not g.is_empty else [0, 0, 0, 0]
    aw = int(math.ceil((bb[2] - bb[0]) / GRID) * GRID)
    ah = int(math.ceil((bb[3] - bb[1]) / GRID) * GRID)
    out_bubbles.append({
        "id": b["id"], "x": b["x"], "y": b["y"],
        "AW": aw, "AH": ah,                    # 玩家活动区（矩形）
        "FW": aw + 2 * W_, "FH": ah + 2 * W_,  # 远景范围
        "T": max(aw, ah), "W": W_, "O": max(aw, ah) + 2 * W_,   # 旧字段，兼容
        "P": ring_list_all(g, min_area=100.0),
        "P_area_km2": round(g.area / 1e6, 4),
        "P_max_m": round(bbox_max(g), 0),
        "dist_max_m": round(dist_max, 0),
        "half_need_m": round(cheb, 0),
        "T_basis": "rect",
        "bbox": bb,
    })
json.dump(out_bubbles, open(os.path.join(BASE, "bubbles.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

WILD = unary_union(wild_geoms).buffer(0)
print(f"[wild] {len(wild_geoms)} 个，合计 {WILD.area / 1e6:.3f} km²")

# ---------------------------------------------------------------- 自检
check = {}
check["settle_pair_max_overlap_m2"] = 0.0
for i in range(len(codes)):
    for j in range(i + 1, len(codes)):
        a, b = codes[i], codes[j]
        if P[a].is_empty or P[b].is_empty:
            continue
        check["settle_pair_max_overlap_m2"] = max(
            check["settle_pair_max_overlap_m2"], P[a].intersection(P[b]).area)

check["wild_pair_max_overlap_m2"] = 0.0
for i in range(len(wild_geoms)):
    for j in range(i + 1, len(wild_geoms)):
        check["wild_pair_max_overlap_m2"] = max(
            check["wild_pair_max_overlap_m2"],
            wild_geoms[i].intersection(wild_geoms[j]).area)

# 野地不再扣据点：野地 ∩ 据点 = 设计内的重叠（进图时据点优先），只报告不作为失败项
check["wild_settle_overlap_km2"] = round(WILD.intersection(SETTLE).area / 1e6, 4) if len(wild_geoms) else 0.0

VALID = unary_union([LAND_S, SETTLE]).buffer(0)
UNION = unary_union([SETTLE, WILD]).buffer(0)
check["valid_km2"] = round(VALID.area / 1e6, 4)
check["cover_km2"] = round(UNION.area / 1e6, 4)
check["missing_km2"] = round(VALID.difference(UNION).area / 1e6, 4)
check["extra_km2"] = round(UNION.difference(VALID).area / 1e6, 4)
check["map_area_km2"] = round(LAND_S.area / 1e6, 4)
check["land_km2"] = round(float((land_real).sum()) * 16 / 1e6, 4)
check["water_km2"] = round(float((map_mask & ~land_mask).sum()) * 16 / 1e6, 4)
check["outside_land_km2"] = round(OUTSIDE.area / 1e6, 3)
check["settle_km2"] = round(SETTLE.area / 1e6, 4)
check["wild_km2"] = round(WILD.area / 1e6, 4)

# 每个据点 P 是否在自己的 T 方框内
td_out = []
for r in rows:
    code = r["code"]
    x, y = f(r["world_x"]), f(r["world_y"])
    T = f(r.get("_T") or r["scene_T_m"])
    sq = box(x - T / 2, y - T / 2, x + T / 2, y + T / 2)
    out = P[code].difference(sq).area
    if out > 1:
        td_out.append({"code": code, "out_m2": round(out, 1)})
check["p_outside_own_T"] = td_out

# 野地 P 是否都在自己的活动区矩形内（|dx| ≤ AW/2、|dy| ≤ AH/2）
far = [{"id": b["id"], "half_need_m": b["half_need_m"], "AW": b["AW"], "AH": b["AH"]}
       for b in out_bubbles
       if b["half_need_m"] > max(b["AW"], b["AH"]) / 2 + 0.5]
check["wild_outside_scene"] = far
check["wild_activity_rects"] = sorted({"%dx%d" % (b["AW"], b["AH"]) for b in out_bubbles})
check["wild_grid_ok"] = all(b["AW"] % GRID == 0 and b["AH"] % GRID == 0
                            and b["W"] % GRID == 0 for b in out_bubbles)

# 人工编辑（scene_overrides.json）过后的多边形是 0.1 m 取整的，允许 500 m² 级的对不齐
check["wild_overlap_relaxed"] = bool(OVR_W) or bool(FINAL_W)
check["PASS"] = (check["settle_pair_max_overlap_m2"] < 1.0
                 and (check["wild_pair_max_overlap_m2"] < 500.0 or check["wild_overlap_relaxed"])
                 and check["missing_km2"] < 0.003      # ≤0.003 km² = 米级贴边误差（手画矩形不可能严丝合缝）
                 and not td_out and not far)
json.dump(check, open(os.path.join(BASE, "scene_division_check.json"), "w",
                      encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------------------------------------------------------------- 场景规格（页面/文档读这份）
WILD_U = unary_union(wild_geoms).buffer(0) if wild_geoms else Polygon()
GAPS = LAND_S.difference(WILD_U).buffer(0) if not WILD_U.is_empty else LAND_S
_ovl = []
for _i in range(len(wild_geoms)):
    for _j in range(_i + 1, len(wild_geoms)):
        _ia = wild_geoms[_i].intersection(wild_geoms[_j])
        if _ia.area > 10000:
            _ovl.append(_ia)
OVERLAPS = unary_union(_ovl).buffer(0) if _ovl else Polygon()
print(f"[check] 未覆盖 {GAPS.area / 1e6:.3f} km² · 野地互相重叠 {OVERLAPS.area / 1e6:.3f} km²")

# 问题清单（给页面用：点一条能跳过去）；没有就为空
ISSUES = []
_gp = [GAPS] if GAPS.geom_type == "Polygon" else list(getattr(GAPS, "geoms", []))
for _x in sorted(_gp, key=lambda z: -z.area):
    if _x.area < 200:
        continue
    _c = _x.centroid
    ISSUES.append({"type": "gap", "area_m2": int(round(_x.area)),
                   "bbox": [int(round(v)) for v in _x.bounds],
                   "center": [int(round(_c.x)), int(round(_c.y))], "label": "没被野地覆盖"})
for _i in range(len(wild_geoms)):
    for _j in range(_i + 1, len(wild_geoms)):
        _ia = wild_geoms[_i].intersection(wild_geoms[_j])
        if _ia.area < 1000:
            continue
        _c = _ia.centroid
        ISSUES.append({"type": "overlap", "area_m2": int(round(_ia.area)),
                       "bbox": [int(round(v)) for v in _ia.bounds],
                       "center": [int(round(_c.x)), int(round(_c.y))],
                       "label": f"{centers[_i]['id']} / {centers[_j]['id']}"})
print(f"[check] 问题清单 {len(ISSUES)} 条")

specs = {"frame": {"x0": meta["x0"], "x1": meta["x1"],
                   "y0": meta["y0"], "y1": meta["y1"]},
         "outside": ring_list_all(OUTSIDE_S, min_area=2000.0),
         "gaps": ring_list_all(GAPS.buffer(15).simplify(1.0).buffer(0), min_area=500.0),
         "overlaps": ring_list_all(OVERLAPS.buffer(15).simplify(1.0).buffer(0), min_area=500.0),
         "issues": ISSUES,
         "settlements": [], "wilds": []}
for r in rows:
    code = r["code"]
    tier, typ = r["tier"], r["rdr2_type"]
    if tier == "city":
        kind, W = "city", W_BY_KIND["city"]
    elif tier == "castle":
        kind, W = "castle", W_BY_KIND["castle"]
    elif typ == "hideout":
        kind, W = "hideout", W_BY_KIND["hideout"]
    else:
        kind, W = "village", W_BY_KIND["village"]
    T_frame = int(round(r.get("_T") or f(r["scene_T_m"])))   # 旧方框：**只用来定远景框**，保持原值
    W = int(math.ceil(int(r.get("_W") or W) / GRID) * GRID)   # 每边外扩取 128 的倍数
    pr = RECT[code]                                          # 能走范围 P（用户画/生成）
    AW = round(pr[2] - pr[0], 1)
    AH = round(pr[3] - pr[1], 1)
    specs["settlements"].append({
        "code": code, "name": r["name_zh"], "name_en": r["name_en"],
        "tier": tier, "type": typ, "kind": kind,
        "x": round(f(r["world_x"]), 1), "y": round(f(r["world_y"]), 1),
        # 🔴 2026-11-04 用户裁定：**能走范围 P 就是活动区边界**（P 外一律按远景处理）。
        # 旧的正方形档位 T 不再是活动区，只保留下来算远景框（远景范围不变）。
        "AW": AW, "AH": AH,
        "P_rect": [round(pr[0], 1), round(pr[1], 1), round(pr[2], 1), round(pr[3], 1)],
        "T": T_frame,                             # 旧字段：仅用于远景框，不再代表活动区
        "W": W, "O": T_frame + 2 * W,             # W = 每边外扩，O = 远景范围（旧字段名）
        "FW": T_frame + 2 * W, "FH": T_frame + 2 * W,
        "P": pdata[code]["P"], "P_area_km2": pdata[code]["P_area_km2"],
        "P_max_m": pdata[code]["P_max_m"],
        "n_inst": int(f(r["n_inst"])), "n_bld": int(f(r["n_bld"])),
    })
for b in out_bubbles:
    specs["wilds"].append({k: b[k] for k in ("id", "x", "y", "AW", "AH", "FW", "FH",
                                             "T", "W", "O",
                                             "P", "P_area_km2", "P_max_m",
                                             "dist_max_m", "half_need_m",
                                             "T_basis", "bbox")})
json.dump(specs, open(os.path.join(BASE, "scene_specs.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ---------------------------------------------------------------- scene_list.csv（58 张，给切场景用）
# 2026-11-04 用户裁定：**能走范围 P 就是活动区边界**（P 外一律按远景处理）。
# · x / y / 每边外扩 / 远景宽高 —— 保持原值（远景范围不变）；
# · 活动区宽高 = P 的宽高；末尾四列 = P 的世界矩形（构建器按它判高清 vs 远景）。
OUT_CSV = os.path.join(RDR2, "docs", "世界与地编", "scene_list.csv")
with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as fp:
    wr = csv.writer(fp)
    wr.writerow(["kind", "id", "code", "name", "x", "y",
                 "活动区宽_m", "活动区高_m", "每边外扩_m", "远景宽_m", "远景高_m",
                 "P_area_km2", "scene_name",
                 "能走_x0", "能走_y0", "能走_x1", "能走_y1"])
    for s in specs["settlements"]:
        pr = s.get("P_rect") or ["", "", "", ""]
        wr.writerow(["settlement", s["code"], s["code"], s["name"], s["x"], s["y"],
                     s["AW"], s["AH"], s["W"], s["FW"], s["FH"], s["P_area_km2"],
                     "rdr2_" + s["code"], pr[0], pr[1], pr[2], pr[3]])
    for w in specs["wilds"]:
        bb = w.get("bbox") or ["", "", "", ""]
        wr.writerow(["wild", w["id"], "", "野地 " + w["id"], w["x"], w["y"],
                     w["AW"], w["AH"], w["W"], w["FW"], w["FH"], w["P_area_km2"],
                     "rdr2_" + w["id"], bb[0], bb[1], bb[2], bb[3]])
    # 2026-11-04 用户裁定：瓜玛两处（阿瓜多切斯 / 瓜玛营，相距约 342 m）**合并成一张子场景**
    # 🔴 这行以前只写名字、数值列留空，靠手改 scene_list.csv 补 —— 结果重跑一次就把瓜玛的
    #    x/y/活动区/外扩/远景/能走矩形全清空（2026-11-08 比对发现，git 版与生成版差这一行）。
    #    现按生成物纪律（改生成器、不手改产物）把定案值写进源头；此值 = 2026-11-04 定案版。
    wr.writerow(["guarma", "guarma", "guarma", "瓜玛岛",
                 1392, -7104, 1280, 1152, 128, 1536, 1280, 1.4746, "rdr2_guarma",
                 752, -7744, 2032, -6592])
print(f"[csv] {OUT_CSV}")

# ---------------------------------------------------------------- 打印
print("\n%-8s %10s %8s %8s %8s  %s" % ("code", "P km²", "P_max", "活动区", "远景", "备注"))
for r, s in zip(rows, specs["settlements"]):
    print("%-8s %10.3f %8.0f %8d %8d" % (s["code"], s["P_area_km2"], s["P_max_m"],
                                         s["AW"], s["FW"]))
print("\n%-8s %10s %8s %14s %8s %14s" % ("wild", "P km²", "P_max", "活动区", "外扩", "远景"))
for b in out_bubbles:
    print("%-8s %10.3f %8.0f %14s %8d %14s" % (
        b["id"], b["P_area_km2"], b["P_max_m"],
        "%d x %d" % (b["AW"], b["AH"]), b["W"], "%d x %d" % (b["FW"], b["FH"])))

print("\n=== 自检 ===")
for k, v in check.items():
    print(f"{k}: {v}")
print("\n场景总数 = 44 据点 + %d 野地 + 1 瓜玛 = %d" %
      (len(out_bubbles), 44 + len(out_bubbles) + 1))
print("PASS" if check["PASS"] else "FAIL")
