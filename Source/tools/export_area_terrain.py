"""Extract the game's own terrain/area LOD meshes (`.ydd` slod) and pair them with
their placement entities from `jklm_7_10_area_lod.ymap`.

用途：heightmap.dat 的垂直基准与 .ymap 世界坐标对不上（差 ~129 m，且局部形状不吻合），
所以查看器改用【游戏自己的 area_slod4 网格】当真实地面 —— 它的摆放实体 z≈97~146，
与 Valentine 实体的地面 z 同一基准，罩得住小镇。

用法: python export_area_terrain.py
输出: export/levels/town/valentine_terrain_meshes.json
"""
import os, sys, json, glob

ROOT = r"D:/BrainMaker/大镖客2解包分析"
sys.path.insert(0, os.path.join(ROOT, "tools"))
from rdr2_ydr import Res, parse_drawable_dictionary, extract_at


def main():
    town = os.path.join(ROOT, "export/levels/town")
    import math
    VT = json.load(open(os.path.join(town, "valentine.json")))
    tcx = sum(e[1] for e in VT) / len(VT); tcy = sum(e[2] for e in VT) / len(VT)
    RAD = float(os.environ.get("TERRAIN_RADIUS", "1400"))
    print(f"town center=({tcx:.0f},{tcy:.0f})  radius={RAD}")
    by_h = {}
    inst = []
    n1 = n2 = 0
    for f in ("arealod_all_entities.json", "lod_all_entities.json"):
        fp = os.path.join(town, f)
        if not os.path.exists(fp):
            continue
        for e in json.load(open(fp)):
            if math.hypot(e[1] - tcx, e[2] - tcy) > RAD:
                continue
            inst.append(e)
            by_h.setdefault(e[0], e)
            if f.startswith("area"): n1 += 1
            else: n2 += 1
    print(f"terrain placement (within {RAD}m): {len(inst)} instances / {len(by_h)} distinct archetypes")
    json.dump(inst, open(os.path.join(town, "terrain_instances.json"), "w"), separators=(",", ":"))

    BIG = float(os.environ.get("TERRAIN_MIN_EXT", "250"))
    NEAR = float(os.environ.get("TERRAIN_NEAR", "850"))
    MIND = {}
    for e in inst:
        d = math.hypot(e[1] - tcx, e[2] - tcy)
        MIND[e[0]] = min(MIND.get(e[0], 9e9), d)
    print(f"big(mesh ext>={BIG}) 全留；小物件只留 {NEAR}m 内")
    out = {}
    files = glob.glob(os.path.join(ROOT, "export/models/area_lod_ydd*/*.ydd"))
    for p in files:
        name = os.path.basename(p)
        try:
            res = Res(open(p, 'rb').read())
            ents = parse_drawable_dictionary(res)
        except Exception:
            continue
        for h, off in ents:
            if h not in by_h or h in out:
                continue
            try:
                info, ms = extract_at(res, off, 'high')
            except Exception:
                continue
            pos = []; idx = []; b = 0
            mn = [1e9] * 3; mx = [-1e9] * 3
            for m in ms:
                pos += m['positions']
                idx += [i + b for i in m['indices']]
                b += m['vertex_count']
                for k in range(m['vertex_count']):
                    for c in range(3):
                        v = m['positions'][k * 3 + c]
                        mn[c] = min(mn[c], v); mx[c] = max(mx[c], v)
            if not idx:
                continue
            ext = max(mx[0] - mn[0], mx[1] - mn[1])
            if ext < BIG:
                if MIND.get(h, 9e9) > NEAR:
                    continue
            out[h] = dict(name=name, p=pos, i=idx, vc=b, tc=len(idx) // 3,
                          bbox=[round(v, 2) for v in mn + mx])
            print(f"  {name:44s} hash={h:>12} verts={b:>6} tris={len(idx)//3:>6} bbox={[round(v) for v in mn+mx]}")

    path = os.path.join(town, os.environ.get("TERR_OUT", "valentine_terrain_meshes.json"))
    json.dump(out, open(path, 'w'), separators=(',', ':'))
    tv = sum(m['vc'] for m in out.values()); tt = sum(m['tc'] for m in out.values())
    print(f"terrain meshes={len(out)} verts={tv} tris={tt}")
    print("wrote", path, round(os.path.getsize(path) / 1024 / 1024, 2), "MB")


if __name__ == '__main__':
    main()
