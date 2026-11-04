# -*- coding: utf-8 -*-
"""场景裁剪对账：切出来的场景 blend 清单 vs v23 大陆清单（同一套规则复算）。

    python tools/_check_scene.py --scene sdn \
        --manifest <PROJ>\\_scratch\\scene_cut\\manifest_sdn.jsonl \
        [--csv docs/世界与地编/scene_list.csv] \
        [--v23 <PROJ>\\deliverable\\blender\\continent\\manifest_continent_v23.jsonl]

规则与 tools/blender_cut_scene.py 完全一致：
  远景范围外 → 删；与玩家活动区相交 → 留；只在远景那一圈 → 只留 lod。

判定：两边的「活动区/远景 × 每类计数」逐项一致 → PASS。
不一致时打印差项 + 前若干个对不上的对象名（v23 清单里有一批包围盒是局部坐标，
会表现为"v23 有、场景没有"或反之 —— 这类要人工确认，不算静默通过）。
"""

import argparse
import collections
import csv
import json
import os
import re

ROOT = r"D:/BrainMaker/大镖客2解包分析"
V23 = os.path.join(ROOT, "deliverable/blender/continent/manifest_continent_v23.jsonl")
CSV_DEF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "docs", "世界与地编", "scene_list.csv")
SUF = re.compile(r"\.\d{3,}$")


def read_scene(path, sid):
    with open(path, encoding="utf-8-sig", newline="") as fp:
        for r in csv.DictReader(fp):
            if r.get("id") == sid or r.get("code") == sid:
                n = lambda k: float((r.get(k) or "0").strip() or 0)
                return {"x": n("x"), "y": n("y"), "aw": n("活动区宽_m"), "ah": n("活动区高_m"),
                        "fw": n("远景宽_m"), "fh": n("远景高_m")}
    raise SystemExit("[check] 找不到场景 %s" % sid)


def hit(bb, r):
    x0, y0, _, x1, y1, _ = bb
    return not (x1 < r[0] or x0 > r[2] or y1 < r[1] or y0 > r[3])


def side(sc):
    x, y = sc["x"], sc["y"]
    return ((x - sc["aw"] / 2, y - sc["ah"] / 2, x + sc["aw"] / 2, y + sc["ah"] / 2),
            (x - sc["fw"] / 2, y - sc["fh"] / 2, x + sc["fw"] / 2, y + sc["fh"] / 2))


def expected_from_v23(sc):
    act, far = side(sc)
    ca, cr = collections.Counter(), collections.Counter()
    names = {}
    n_bad = 0
    with open(V23, encoding="utf-8") as fp:
        for line in fp:
            o = json.loads(line)
            if "_meta" in o:
                continue
            bb = o.get("bb")
            if not bb or len(bb) != 6:
                continue
            if bb[3] - bb[0] <= 0 and bb[4] - bb[1] <= 0:
                n_bad += 1
                continue
            if not hit(bb, far):
                continue
            k = o.get("c") or "unknown"
            nm = SUF.sub("", o.get("n") or "")
            if hit(bb, act):
                ca[k] += 1; names.setdefault(nm, "act")
            elif k == "lod":
                cr[k] += 1; names.setdefault(nm, "ring")
    return ca, cr, names, n_bad


def actual_from_manifest(path):
    ca, cr = collections.Counter(), collections.Counter()
    names = {}
    with open(path, encoding="utf-8") as fp:
        for line in fp:
            o = json.loads(line)
            k = o.get("c") or "unknown"
            nm = SUF.sub("", o.get("n") or "")
            if o.get("ring"):
                cr[k] += 1; names[nm] = "ring"
            else:
                ca[k] += 1; names[nm] = "act"
    return ca, cr, names


def main():
    global V23
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--csv", default=CSV_DEF)
    ap.add_argument("--v23", default=V23)
    a = ap.parse_args()
    V23 = a.v23

    sc = read_scene(a.csv, a.scene)
    ea, er, en, n_bad = expected_from_v23(sc)
    aa, ar, an = actual_from_manifest(a.manifest)
    print("[check] 场景 %s   活动区 %.0f×%.0f   远景 %.0f×%.0f"
          % (a.scene, sc["aw"], sc["ah"], sc["fw"], sc["fh"]))
    print("[check] v23 期望：活动区 %d · 远景 %d（无包围盒跳过 %d）"
          % (sum(ea.values()), sum(er.values()), n_bad))
    print("[check] 场景实际：活动区 %d · 远景 %d"
          % (sum(aa.values()), sum(ar.values())))

    bad = []
    for tag, e, g in (("活动区", ea, aa), ("远景", er, ar)):
        for k in sorted(set(e) | set(g)):
            if e.get(k, 0) != g.get(k, 0):
                bad.append((tag, k, e.get(k, 0), g.get(k, 0)))
    if bad:
        print("[check] 类计数差：")
        for tag, k, x, y in sorted(bad, key=lambda t: -abs(t[2] - t[3])):
            print("   %-6s %-14s v23=%6d 场景=%6d" % (tag, k, x, y))

    only_e = [n for n in en if n not in an]
    only_a = [n for n in an if n not in en]
    print("[check] 名字差：v23 有场景没有 %d · 场景有 v23 没有 %d" % (len(only_e), len(only_a)))
    for n in only_e[:15]:
        print("   - 缺 %s" % n)
    for n in only_a[:15]:
        print("   + 多 %s" % n)

    if not bad and not only_e and not only_a:
        print("[check] PASS（活动区/远景 × 每类计数与 v23 逐项一致）")
        return
    print("[check] FAIL / 待人工确认")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
