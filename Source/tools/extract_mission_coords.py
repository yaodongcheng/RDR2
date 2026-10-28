#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从反编译任务脚本里挖「世界坐标」，补上 mission_* 数据"有内容没坐标"的缺口。

原理
----
RDR2 的 .ysc 反编译后，脚本里写死的世界位置会以浮点三元组常量出现：
    { 961.3426f, 973.0797f, 142.3945f }
这些是任务布点（NPC 站位 / 场景点 / 生成点），直接就是世界坐标（米）。

坑（2026-10-23 实测，重要）
--------------------------
模板化任务（赏金/随机遭遇）的脚本里带一份**完全相同的坐标常量表**：
`rcm_bh_sd_saloon` / `rcm_bh_blackwater_hunt` / `rcm_bh_laramie_sleeping` 三个脚本
各有 87 个坐标三元组，其中 **85 个完全相同、各 0 个独有**——
这是一份"据点/布告板锚点表"，真正的任务场地坐标**不在脚本里**（由运行时数据表选点）。

所以判据是「**跨脚本重复出现 = 共享锚点，不是任务场地**」：
  1) 统计每个 1 m 量化坐标被多少个脚本包含；
  2) 被 >= --share-min（默认 3）个脚本包含的 → 共享锚点，剔除；
  3) 剩下的是**该脚本独有**的布点，才当作任务场地。
剩下的点太少（< --min-pts）就标记 template_only，不硬凑坐标。

输出
----
export/levels/world/mission_coords.csv    每任务一行（主场地 / 包围盒 / 聚类数 / 最近据点）
export/levels/world/mission_coords.json   同上 + 每簇中心、点数、距主场地距离
export/levels/world/shared_coord_anchors.csv  被剔除的全局共享锚点（本身也有用：布告板/据点锚）

用法
----
uv run python tools/extract_mission_coords.py [--radius 150] [--share 0.25]
"""
import argparse
import csv
import json
import math
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_DIR = os.path.join(ROOT, "raw", "script_full", "1491.50")
OUT_DIR = os.path.join(ROOT, "export", "levels", "world")

BOX = (-6844 - 500, 3924 + 500, -4800 - 500, 3224 + 500)
Z_RANGE = (-120.0, 900.0)

TRIPLET = re.compile(
    r"\{\s*(-?\d+\.\d+)f\s*,\s*(-?\d+\.\d+)f\s*,\s*(-?\d+\.\d+)f\s*\}"
)
QUANT = 1.0  # 坐标量化到 1 m，用于跨脚本比对


def parse_coords(text):
    out = []
    for a, b, c in TRIPLET.findall(text):
        x, y, z = float(a), float(b), float(c)
        if abs(x) < 1.0 and abs(y) < 1.0 and abs(z) < 1.0:
            continue
        if not (BOX[0] <= x <= BOX[1] and BOX[2] <= y <= BOX[3]):
            continue
        if not (Z_RANGE[0] <= z <= Z_RANGE[1]):
            continue
        out.append((x, y, z))
    return out


def qkey(p):
    return (round(p[0] / QUANT), round(p[1] / QUANT))


class UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def cluster(points, radius):
    n = len(points)
    if n == 0:
        return []
    cell = radius
    grid = defaultdict(list)
    for i, (x, y, _z) in enumerate(points):
        grid[(int(math.floor(x / cell)), int(math.floor(y / cell)))].append(i)

    uf = UF(n)
    r2 = radius * radius
    for (gx, gy), idxs in grid.items():
        cand = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cand.extend(grid.get((gx + dx, gy + dy), ()))
        for i in idxs:
            xi, yi, _ = points[i]
            for j in cand:
                if j <= i:
                    continue
                xj, yj, _ = points[j]
                if (xi - xj) ** 2 + (yi - yj) ** 2 <= r2:
                    uf.union(i, j)

    groups = defaultdict(list)
    for i in range(n):
        groups[uf.find(i)].append(i)
    return list(groups.values())


def cluster_stats(pts):
    n = len(pts)
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    cz = sum(p[2] for p in pts) / n
    rad = max(math.hypot(p[0] - cx, p[1] - cy) for p in pts)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    zs = [p[2] for p in pts]
    return {
        "n": n,
        "x": round(cx, 2),
        "y": round(cy, 2),
        "z": round(cz, 2),
        "radius": round(rad, 2),
        "bbox": [round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)],
        "z_range": [round(min(zs), 2), round(max(zs), 2)],
    }


def load_settlements():
    p = os.path.join(ROOT, "deliverable", "handoff", "settlements_world_v2.csv")
    rows = []
    with open(p, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if not r.get("world_x"):
                continue
            rows.append({
                "code": r["code"],
                "name_zh": r["name_zh"],
                "world_x": float(r["world_x"]),
                "world_y": float(r["world_y"]),
            })
    return rows


def nearest_settlement(x, y, settlements):
    best, bestd = None, 1e9
    for s in settlements:
        d = math.hypot(x - s["world_x"], y - s["world_y"])
        if d < bestd:
            best, bestd = s, d
    return best, bestd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=float, default=150.0)
    ap.add_argument("--share-min", type=int, default=3,
                    help="同一量化坐标被多少个脚本包含即视为共享锚点（剔除）")
    ap.add_argument("--min-pts", type=int, default=3)
    args = ap.parse_args()

    scripts = sorted(f for f in os.listdir(SCRIPT_DIR) if f.endswith(".c"))
    per_script = {}
    for fn in scripts:
        try:
            txt = open(os.path.join(SCRIPT_DIR, fn), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        pts = parse_coords(txt)
        if pts:
            per_script[fn] = pts

    n_scripts = len(per_script)
    print(f"含坐标的脚本: {n_scripts} / {len(scripts)}")

    # ---- pass 1: 跨脚本重复出现 = 共享锚点 ----
    appear = defaultdict(int)
    for fn, pts in per_script.items():
        for k in {qkey(p) for p in pts}:
            appear[k] += 1
    thresh = max(2, args.share_min)
    common = {k for k, c in appear.items() if c >= thresh}
    print(f"共享锚点（出现在 >= {thresh} 个脚本）: {len(common)} 个")

    # 共享锚点的代表坐标（取所有脚本里出现过的实际点求均值）
    acc = defaultdict(lambda: [0.0, 0.0, 0.0, 0])
    for fn, pts in per_script.items():
        for p in pts:
            k = qkey(p)
            if k in common:
                a = acc[k]
                a[0] += p[0]; a[1] += p[1]; a[2] += p[2]; a[3] += 1

    settlements = load_settlements()

    with open(os.path.join(OUT_DIR, "mission_scripts.json"), encoding="utf-8") as fh:
        mscripts = json.load(fh)
    script2mission = {}
    for mid, d in mscripts.items():
        s = (d.get("script") or "").strip()
        if s:
            script2mission.setdefault(s, mid)
    with open(os.path.join(OUT_DIR, "missions.csv"), encoding="utf-8-sig") as fh:
        mission_meta = {r["mission_id"]: r for r in csv.DictReader(fh)}

    rows, detail = [], {}
    n_template = 0
    for fn, pts in per_script.items():
        own = [p for p in pts if qkey(p) not in common]
        mid = script2mission.get(fn, "")
        meta = mission_meta.get(mid, {})

        if len(own) < args.min_pts:
            # 模板化脚本：只有共享锚点，没有自己的场地坐标 —— 如实标记，不硬凑
            n_template += 1
            rows.append({
                "script": fn,
                "mission_id": mid,
                "category": meta.get("category", ""),
                "has_own_coords": False,
                "n_points": len(pts),
                "n_own_points": len(own),
                "n_clusters": 0,
                "primary_x": "", "primary_y": "", "primary_z": "",
                "primary_radius_m": "", "primary_points": "",
                "spread_x_m": "", "spread_y_m": "",
                "nearest_settlement": "", "nearest_code": "", "nearest_dist_m": "",
            })
            detail[fn] = {
                "mission_id": mid, "category": meta.get("category", ""),
                "n_points": len(pts), "n_own_points": len(own),
                "template_only": True,
            }
            continue

        groups = cluster(own, args.radius)
        stats = sorted((cluster_stats([own[i] for i in g]) for g in groups), key=lambda s: -s["n"])
        primary = stats[0]
        all_x = [p[0] for p in own]
        all_y = [p[1] for p in own]

        best, bestd = nearest_settlement(primary["x"], primary["y"], settlements)

        rows.append({
            "script": fn,
            "mission_id": mid,
            "category": meta.get("category", ""),
            "has_own_coords": True,
            "n_points": len(pts),
            "n_own_points": len(own),
            "n_clusters": len([s for s in stats if s["n"] >= args.min_pts]),
            "primary_x": primary["x"],
            "primary_y": primary["y"],
            "primary_z": primary["z"],
            "primary_radius_m": primary["radius"],
            "primary_points": primary["n"],
            "spread_x_m": round(max(all_x) - min(all_x), 1),
            "spread_y_m": round(max(all_y) - min(all_y), 1),
            "nearest_settlement": best["name_zh"] if best else "",
            "nearest_code": best["code"] if best else "",
            "nearest_dist_m": round(bestd, 1) if best else "",
        })
        detail[fn] = {
            "mission_id": mid,
            "category": meta.get("category", ""),
            "n_points": len(pts),
            "n_own_points": len(own),
            "template_only": False,
            "primary": primary,
            "clusters": [s for s in stats if s["n"] >= args.min_pts][:20],
        }

    rows.sort(key=lambda r: (r["category"], r["mission_id"] or r["script"]))
    os.makedirs(OUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUT_DIR, "mission_coords.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(OUT_DIR, "mission_coords.json"), "w", encoding="utf-8") as fh:
        json.dump(detail, fh, ensure_ascii=False, indent=1)

    # 共享锚点单独出表（布告板/据点锚，本身也有用）
    anc = []
    for k, (sx, sy, sz, c) in acc.items():
        if c == 0:
            continue
        x, y, z = sx / c, sy / c, sz / c
        best, bestd = nearest_settlement(x, y, settlements)
        anc.append({
            "x": round(x, 2), "y": round(y, 2), "z": round(z, 2),
            "seen_in_scripts": appear[k],
            "nearest_settlement": best["name_zh"], "nearest_dist_m": round(bestd, 1),
        })
    anc.sort(key=lambda a: -a["seen_in_scripts"])
    with open(os.path.join(OUT_DIR, "shared_coord_anchors.csv"), "w",
              encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(anc[0].keys()))
        w.writeheader()
        w.writerows(anc)

    # ---- 汇总 ----
    own_rows = [r for r in rows if r["has_own_coords"]]
    print(f"\n脚本总数 {len(rows)}：可提专属坐标 {len(own_rows)} 个，"
          f"模板化（无专属坐标）{n_template} 个")
    bycat = defaultdict(int)
    for r in rows:
        bycat[r["category"] or "(非任务脚本)"] += 1
    print("\n按 category:")
    for c, n in sorted(bycat.items(), key=lambda x: -x[1]):
        has = sum(1 for r in own_rows if (r["category"] or "(非任务脚本)") == c)
        print(f"  {n:4d}  {c:24s} 其中有专属坐标 {has}")

    print("\n=== 赏金任务（验证：sd→圣丹尼斯 / blk→黑水 / val→瓦伦丁）===")
    for r in rows:
        if r["category"] != "BOUNTY_HUNTING":
            continue
        if not r["has_own_coords"]:
            print(f"  {r['mission_id']:7s} {r['script'][:30]:32s} -> [模板化] 无专属坐标")
            continue
        print(f"  {r['mission_id']:7s} {r['script'][:30]:32s} -> {r['nearest_settlement']:10s}"
              f"{float(r['nearest_dist_m']):>7.0f} m   ({float(r['primary_x']):.0f},{float(r['primary_y']):.0f})"
              f"  pts={r['n_own_points']}")

    print("\n=== 随机角色任务抽样 ===")
    n = 0
    for r in rows:
        if r["category"] in ("RANDOM_CHARACTER", "RANDOM_STORY_CHARACTER"):
            site = (f"{r['nearest_settlement']}{float(r['nearest_dist_m']):>6.0f} m"
                    if r["has_own_coords"] else "[模板化]")
            print(f"  {r['mission_id']:8s} {r['script'][:30]:32s} -> {site}")
            n += 1
            if n >= 12:
                break


if __name__ == "__main__":
    main()
