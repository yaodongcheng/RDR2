"""Export vegetation (trees/bushes/rocks) models + their instance placements.

发现：RDR2 的植被**不在 ymap 实体里**，而是独立的 **instance placement** 系统：
  `levels/rdr3/terrain/instance_placement/<grid>_instance_placement.rpf`
里面是 `*_trees_*.ymap` / `*_grass_*.ymap`（每格 N 个实例）。
模型本体在 HD 植被包 `hd/levels/rdr3/props/vegetation/*.rpf`（`p_tree_*` / `rdr_bush_*` / `hea_rock_*`）。

用法: python export_veg_meshes.py
输出: export/levels/town/valentine_veg_meshes.json + valentine_veg_instances.json
"""
import os, sys, json, glob

ROOT = r"D:/BrainMaker/大镖客2解包分析"
sys.path.insert(0, os.path.join(ROOT, "tools"))
from rdr2_ydr import extract as ydr_extract, extract_frag

RADIUS = float(os.environ.get("VEG_RADIUS", "700"))


def main():
    town = os.path.join(ROOT, "export/levels/town")
    trees = json.load(open(os.path.join(town, "veg_instances.json")))

    files = {}
    for f in glob.glob(os.path.join(ROOT, "export/models/veg/*/*")):
        base = os.path.splitext(os.path.basename(f))[0]
        h = 0
        for c in base.lower().encode():
            h = (h + c) & 0xffffffff
            h = (h + (h << 10)) & 0xffffffff
            h ^= (h >> 6)
        h = (h + (h << 3)) & 0xffffffff
        h ^= (h >> 11)
        h = (h + (h << 15)) & 0xffffffff
        files.setdefault(h, []).append(f)

    # 裁剪实例
    VT = json.load(open(os.path.join(town, "valentine.json")))
    cx = sum(e[1] for e in VT) / len(VT); cy = sum(e[2] for e in VT) / len(VT)
    import math
    keep = [e for e in trees if math.hypot(e[1] - cx, e[2] - cy) <= RADIUS]
    keep_h = set(e[0] for e in keep)
    print(f"veg instances: {len(trees)} -> within {RADIUS}m: {len(keep)}  archetypes {len(keep_h)}")

    out = {}
    ok = fail = 0
    for h in keep_h:
        if h not in files:
            fail += 1; continue
        f = files[h][0]
        try:
            info, ms = (ydr_extract(f) if f.endswith('.ydr') else extract_frag(f))
            pos = []; idx = []; b = 0
            for m in ms:
                pos += m['positions']; idx += [i + b for i in m['indices']]; b += m['vertex_count']
            if not idx:
                fail += 1; continue
            out[str(h)] = dict(name=os.path.splitext(os.path.basename(f))[0], p=pos, i=idx,
                               vc=b, tc=len(idx) // 3)
            ok += 1
        except Exception:
            fail += 1
    json.dump(out, open(os.path.join(town, "valentine_veg_meshes.json"), 'w'), separators=(',', ':'))
    json.dump(keep, open(os.path.join(town, "valentine_veg_instances.json"), 'w'), separators=(',', ':'))
    tv = sum(m['vc'] for m in out.values()); tt = sum(m['tc'] for m in out.values())
    print(f"veg models ok={ok} fail={fail} verts={tv} tris={tt}  instances={len(keep)}")
    print("->", os.path.getsize(os.path.join(town, "valentine_veg_meshes.json")) // 1024, "KB")


if __name__ == '__main__':
    main()
