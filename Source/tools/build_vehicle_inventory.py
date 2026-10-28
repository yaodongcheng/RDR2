# -*- coding: utf-8 -*-
"""载具清单：`vehicles.rpf`（663 项 / 216 个 .yft）→ 结构化清单。

产出：
  export/levels/world/vehicle_inventory.csv
  export/levels/world/vehicle_inventory.json

字段：name / category / kind / tris / verts / geoms / bbox(m) / textures /
      has_model（能不能解析出 drawable）/ note

分类规则写在 TYPE_RULES 里，**按名字前缀**判定，可复查。
"""
import os
import re
import sys
import json
import csv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import rdr2_ydr as Y            # noqa: E402
from export_vehicle_gltf import find_drawable_base   # noqa: E402

SRC = os.path.join(ROOT, "raw/vehicles/out")
OUTDIR = os.path.join(ROOT, "export/levels/world")

# 顺序有意义：先判武器载具，再判船/火车/车
TYPE_RULES = [
    ("武器载具", r"gatling|maxim|cannon|hotchkiss|breach_cannon"),
    ("船/舰", r"boat|ship|canoe|pirogue|keelboat|skiff|tug|turbine|smuggler"),
    ("火车", r"caboose|coalcar|coalhopper|boxcar|flatcar|passenger|steamer|baggage|"
            r"sleeper|refrigeratorcar|dining|observation|opensleeper|armoured|"
            r"midland|north|private|winter|ghosttrain|coal_wagon|armoredcar"),
    ("有轨电车", r"trolley"),
    ("飞行器", r"balloon"),
    ("马车/货运车", r"wagon|cart|coach|buggy|chuck|utilliwag|minecart|handcart|"
                 r"stagecoach|supplywagon|oilwagon|logwagon|armysupplywagon"),
]

ZH = {
    "武器载具": "武器载具/炮车",
    "船/舰": "船/舰",
    "火车": "火车车厢",
    "有轨电车": "有轨电车",
    "飞行器": "飞行器",
    "马车/货运车": "马车/货运车",
    "其他": "其他",
}


def classify(name):
    base = name.replace("_hi", "")
    for cat, pat in TYPE_RULES:
        if re.search(pat, base):
            return cat
    return "其他"


def probe(path):
    """→ (tris, verts, geoms, bbox) 或 None"""
    try:
        res = Y.Res(open(path, 'rb').read())
    except Exception:
        return None
    base = find_drawable_base(res)
    if base is None:
        return None
    tris = verts = geoms = 0
    mn = [1e30] * 3
    mx = [-1e30] * 3
    for mo in Y.pointer_list(res, res.u64(base + 0x50)):
        for gp in Y.parse_model_geoms(res, mo):
            g = Y.parse_geometry(res, gp)
            if not g or not g.get('vb'):
                continue
            geoms += 1
            verts += g['vb']['count']
            if g.get('ib'):
                tris += len(Y.read_indices(res, g['ib'])) // 3
            pos = Y.read_positions(res, g['vb'])   # 扁平 float 列表
            for k in range(0, len(pos) - 2, 3):
                for i in range(3):
                    v = pos[k + i]
                    if v < mn[i]:
                        mn[i] = v
                    if v > mx[i]:
                        mx[i] = v
    if not verts:
        return None
    size = [round(mx[i] - mn[i], 3) for i in range(3)]
    return tris, verts, geoms, size


def main():
    rows = []
    files = sorted(f for f in os.listdir(SRC) if f.endswith(".yft"))
    for i, f in enumerate(files):
        name = os.path.splitext(f)[0]
        p = os.path.join(SRC, f)
        r = probe(p)
        cat = classify(name)
        row = dict(name=name, category=cat, category_zh=ZH[cat],
                   lod="hi" if name.endswith("_hi") else "base",
                   tris="", verts="", geoms="", size_x="", size_y="", size_z="",
                   bytes=os.path.getsize(p), has_model="N",
                   note="")
        if r:
            row.update(tris=r[0], verts=r[1], geoms=r[2],
                       size_x=r[3][0], size_y=r[3][1], size_z=r[3][2], has_model="Y")
        else:
            row["note"] = "解析不出 drawable（贴图/LOD 残片或格式例外）"
        rows.append(row)
        if (i + 1) % 30 == 0:
            print(f"{i+1}/{len(files)}", flush=True)

    os.makedirs(OUTDIR, exist_ok=True)
    cols = list(rows[0].keys())
    with open(os.path.join(OUTDIR, "vehicle_inventory.csv"), "w", newline="",
              encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    json.dump(rows, open(os.path.join(OUTDIR, "vehicle_inventory.json"), "w",
                         encoding="utf-8"), ensure_ascii=False, indent=1)

    from collections import Counter
    c = Counter(r["category"] for r in rows if r["lod"] == "base")
    print("base 载具:", sum(c.values()), dict(c))
    print("可解析:", sum(1 for r in rows if r["has_model"] == "Y"))


if __name__ == "__main__":
    main()
