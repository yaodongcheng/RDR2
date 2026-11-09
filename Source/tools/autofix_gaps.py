# -*- coding: utf-8 -*-
"""自动补缝：把野地矩形之间的窄缝用「延伸邻近矩形的一条边」补掉，并修正据点的微小重叠。

读 scene_specs.json（= 当前生效的矩形）→ 计算缺口 → 逐块扩展最合适的边 → 写回 scene_overrides.json。
"""
import json, itertools, os

import numpy as np
from PIL import Image
from scipy.ndimage import (binary_closing, binary_fill_holes, binary_opening,
                           label, uniform_filter)
from shapely.geometry import LineString, box
from shapely.ops import polygonize, unary_union
from skimage import measure

RDR2 = r"D:\BrainMaker\大镖客2解包分析"
BASE = os.path.join(RDR2, "_scratch", "settlement_plan")

specs = json.load(open(os.path.join(BASE, "scene_specs.json"), encoding="utf-8"))

# ---- 地图区多边形（与 build_scene_division.py 同一套判定）
Image.MAX_IMAGE_PIXELS = None
meta = json.load(open(os.path.join(RDR2, "deliverable/terrain/on_map/meta.json"),
                      encoding="utf-8"))["mainland"]
thumb = np.asarray(Image.open(os.path.join(RDR2, *meta["src_map"].split("/"))).convert("RGB")).astype(np.float32)
g = thumb.mean(2)
mu = uniform_filter(g, 7)
sd = np.sqrt(np.maximum(uniform_filter(g * g, 7) - mu * mu, 0))
parch = (sd < 3.0) & (np.abs(thumb - np.array([210.0, 182.0, 143.0])).max(2) < 28)
cont = ~parch
cont = binary_opening(cont, structure=np.ones((3, 3)))
cont = binary_closing(cont, structure=np.ones((9, 9)))
cont = binary_fill_holes(cont)
lab, _ = label(cont)
sz = np.bincount(lab.ravel()); sz[0] = 0
cont = lab == sz.argmax()
mask = np.array(Image.open(os.path.join(RDR2, "deliverable/terrain/water_mask.png")))
H, Wd = mask.shape
bx0, by0, bx1, by1 = [float(v) for v in meta["paste_box_px"]]
u = bx0 + (np.arange(Wd) + 0.5) / Wd * (bx1 - bx0)
v = by0 + (np.arange(H) + 0.5) / H * (by1 - by0)
UU, VV = np.meshgrid(u, v)
inmap = cont[np.clip(VV.astype(int), 0, cont.shape[0] - 1), np.clip(UU.astype(int), 0, cont.shape[1] - 1)]
lines = []
for ct in measure.find_contours(np.pad(inmap.astype(np.uint8), 2), 0.5):
    if len(ct) < 4:
        continue
    pts = np.column_stack([-6844 + (ct[:, 1] - 2) * 4, 3224 - (ct[:, 0] - 2) * 4])
    if not np.allclose(pts[0], pts[-1]):
        pts = np.vstack([pts, pts[:1]])
    lines.append(LineString(pts))
keep = []
for f in polygonize(lines):
    rp = f.representative_point()
    col = max(0, min(Wd - 1, int(round((rp.x + 6844) / 4))))
    row = max(0, min(H - 1, int(round((3224 - rp.y) / 4))))
    if inmap[row, col]:
        keep.append(f)
LAND = unary_union(keep).buffer(0).simplify(2.0).buffer(0)

# ---- 当前矩形
WR = {}
for w in specs["wilds"]:
    r = w["P"][0]
    xs = [q[0] for q in r]; ys = [q[1] for q in r]
    WR[w["id"]] = [min(xs), min(ys), max(xs), max(ys)]
print("wilds", len(WR))


def gap_geom():
    u2 = unary_union([box(*r) for r in WR.values()])
    return LAND.difference(u2).buffer(0)


def pieces(gm, min_area=200.0):
    if gm.is_empty:
        return []
    gs = [gm] if gm.geom_type == "Polygon" else list(getattr(gm, "geoms", []))
    return sorted([x for x in gs if x.area >= min_area], key=lambda x: -x.area)


for it in range(60):
    gs = pieces(gap_geom())
    if not gs:
        break
    gap = gs[0]
    if gap.area < 200:
        break
    gb = gap.bounds
    MAX_EXT = 300.0          # 每条边最多延伸 300 m（只补“缝”，不改大格局）
    cands_all = []           # (added_area, covered_area, wid, new_rect)
    for wid, r in WR.items():
        cands = []
        if gb[2] > r[2] + 1 and gb[0] >= r[0] - 1 and gb[2] - r[2] <= MAX_EXT:
            cands.append([r[0], r[1], gb[2], r[3]])                    # 右
        if gb[0] < r[0] - 1 and gb[2] <= r[2] + 1 and r[0] - gb[0] <= MAX_EXT:
            cands.append([gb[0], r[1], r[2], r[3]])                    # 左
        if gb[3] > r[3] + 1 and gb[1] >= r[1] - 1 and gb[3] - r[3] <= MAX_EXT:
            cands.append([r[0], r[1], r[2], gb[3]])                    # 上
        if gb[1] < r[1] - 1 and gb[3] <= r[3] + 1 and r[1] - gb[1] <= MAX_EXT:
            cands.append([r[0], gb[1], r[2], r[3]])                    # 下
        for nr in cands:
            nb = box(*nr)
            covered = gap.intersection(nb).area
            if covered <= 0:
                continue
            added = nb.area - box(*r).area
            cands_all.append((added, covered, wid, nr))
    if not cands_all:
        print(f"  [skip] 缺口 {gap.area/1e6:.4f} km² 超过 300 m，不是缝（中心 {gap.centroid.x:.0f},{gap.centroid.y:.0f}）")
        break
    full = [c for c in cands_all if c[1] >= gap.area - 1]
    if full:
        _, _, wid, nr = min(full, key=lambda c: c[0])
    else:
        _, cov, wid, nr = max(cands_all, key=lambda c: c[1])
        print(f"  部分补 {wid}：覆盖 {cov / gap.area * 100:.0f}%")
    WR[wid] = nr
    print(f"  补 {wid}: ({nr[0]:.0f},{nr[1]:.0f})-({nr[2]:.0f},{nr[3]:.0f})  剩余缺口 {gap_geom().area/1e6:.3f} km²")

final_gap = gap_geom().area / 1e6
print(f"补完：未覆盖 {final_gap:.4f} km²")

# ---- 据点微小重叠：重叠区窄轴取中线
SR = {}
for p in specs["settlements"]:
    r = p["P"][0]
    xs = [q[0] for q in r]; ys = [q[1] for q in r]
    SR[p["code"]] = [min(xs), min(ys), max(xs), max(ys)]
fixed_s = {}
for a, b in itertools.combinations(list(SR), 2):
    A, B = SR[a], SR[b]
    ix0, iy0 = max(A[0], B[0]), max(A[1], B[1])
    ix1, iy1 = min(A[2], B[2]), min(A[3], B[3])
    if ix1 - ix0 <= 0 or iy1 - iy0 <= 0:
        continue
    area = (ix1 - ix0) * (iy1 - iy0)
    if area > 100000:
        print(f"  [settle] {a}/{b} 重叠 {area/1e6:.3f} km²，太大，跳过")
        continue
    if (ix1 - ix0) <= (iy1 - iy0):
        mid = (ix0 + ix1) / 2
        if A[0] <= B[0]:
            A[2] = mid; B[0] = mid
        else:
            B[2] = mid; A[0] = mid
    else:
        mid = (iy0 + iy1) / 2
        if A[1] <= B[1]:
            A[3] = mid; B[1] = mid
        else:
            B[3] = mid; A[1] = mid
    fixed_s[a] = SR[a]; fixed_s[b] = SR[b]
    print(f"  [settle] {a}/{b} 重叠 {area:.0f} m² → 对切到中线")

# ---- 写回 overrides
ovr_path = os.path.join(BASE, "scene_overrides.json")
ovr = json.load(open(ovr_path, encoding="utf-8"))
final = []
for w in specs["wilds"]:
    wid = w["id"]
    r = WR[wid]
    final.append({"id": wid,
                  "rect": [round(v, 1) for v in r],
                  "x": round((r[0] + r[2]) / 2, 1),
                  "y": round((r[1] + r[3]) / 2, 1),
                  "T": w.get("T", 3072), "W": w.get("W", 1000)})
ovr["wilds_final"] = final
ovr["wilds"] = {}                      # 全部并进 final，避免重复套用
for code, r in fixed_s.items():
    ovr.setdefault("settlements", {})[code] = {
        "rect": [round(v, 1) for v in r],
        "T": int(next(p for p in specs["settlements"] if p["code"] == code)["T"]),
        "W": int(next(p for p in specs["settlements"] if p["code"] == code)["W"]),
    }
json.dump(ovr, open(ovr_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("写回 scene_overrides.json：wilds_final", len(final), "据点修补", len(fixed_s))
