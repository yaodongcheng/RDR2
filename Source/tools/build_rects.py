# -*- coding: utf-8 -*-
"""给 22 个有自己场景的大据点算：
  rect1 = 能走范围 P 里最大的轴对齐矩形（不重叠）
  rect2 = 远景外框 O = T + 2W（包围 rect1）
输出 rects.json
"""
import csv, json, math, os
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union

RDR2 = r"D:\BrainMaker\大镖客2解包分析"
BASE = os.path.join(RDR2, "_scratch", "settlement_plan")

rows = list(csv.DictReader(open(os.path.join(BASE, "settlements_plan.csv"), encoding="utf-8-sig")))
pdata = json.load(open(os.path.join(BASE, "settlements_p.json"), encoding="utf-8"))

def f(x):
    try:
        return float(x)
    except Exception:
        return 0.0

def largest_rect(P, step=5.0):
    b = P.bounds
    nx = max(1, int(math.ceil((b[2] - b[0]) / step)))
    ny = max(1, int(math.ceil((b[3] - b[1]) / step)))
    # 为控制规模，过大的 P 放粗步长
    if nx * ny > 400 * 400:
        step = max(step, math.sqrt((b[2]-b[0])*(b[3]-b[1]) / (400*400)))
        nx = max(1, int(math.ceil((b[2] - b[0]) / step)))
        ny = max(1, int(math.ceil((b[3] - b[1]) / step)))
    # inside matrix
    inside = [[False] * nx for _ in range(ny)]
    for jy in range(ny):
        y = b[1] + (jy + 0.5) * step
        for jx in range(nx):
            x = b[0] + (jx + 0.5) * step
            inside[jy][jx] = P.contains(Point(x, y))
    # histogram max rectangle
    heights = [0] * nx
    best = (0, 0, 0, 0, 0)  # area, x0, y0, x1, y1 (grid indices)
    for jy in range(ny):
        for jx in range(nx):
            heights[jx] = heights[jx] + 1 if inside[jy][jx] else 0
        stack = []
        for jx in range(nx + 1):
            h = heights[jx] if jx < nx else 0
            start = jx
            while stack and stack[-1][1] > h:
                idx, hh = stack.pop()
                start = idx
                area = hh * (jx - idx)
                if area > best[0]:
                    best = (area, idx, jy - hh + 1, jx - 1, jy)
            if not stack or stack[-1][1] < h:
                stack.append((start, h))
    if best[0] == 0:
        return None
    area, gx0, gy0, gx1, gy1 = best
    x0 = b[0] + gx0 * step
    y0 = b[1] + gy0 * step
    x1 = b[0] + (gx1 + 1) * step
    y1 = b[1] + (gy1 + 1) * step
    return (x0, y0, x1, y1)

out = []
for r in rows:
    code = r["code"]
    tier = r["tier"]
    typ = r["rdr2_type"]
    if not (tier in ("city", "castle") or typ == "hideout"):
        continue
    polys = []
    for poly in pdata.get(code, {}).get("P", []):
        if len(poly) >= 3:
            g = Polygon(poly)
            if g.is_valid and g.area > 50:
                polys.append(g)
    if not polys:
        continue
    P = unary_union(polys).buffer(0)
    rect = largest_rect(P)
    if not rect:
        continue
    x0, y0, x1, y1 = rect
    T = int(f(r["scene_T_m"]))
    W = 1200 if tier == "city" else 800 if tier == "castle" else 500
    O = T + 2 * W
    w, h = x1 - x0, y1 - y0
    out.append({
        "code": code, "name": r["name_zh"], "tier": tier, "type": typ,
        "x": f(r["world_x"]), "y": f(r["world_y"]),
        "rect": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
        "rect_w": round(w, 1), "rect_h": round(h, 1),
        "rect_area": round(w * h / 1e6, 4),
        "T": T, "W": W, "O": O,
        "P_area": pdata.get(code, {}).get("P_area_km2", 0),
        "P": pdata.get(code, {}).get("P", []),
    })
    print(f"{code:6} rect {w:6.0f}×{h:6.0f} m  {w*h/1e6:6.3f} km²   P {pdata.get(code, {}).get('P_area_km2', 0):6.3f}  O {O}  T {T}")

json.dump(out, open(os.path.join(BASE, "rects.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved", len(out))
