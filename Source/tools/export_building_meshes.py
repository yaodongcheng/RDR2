"""Export RDR2 building meshes (.ydr) that are referenced by the Valentine entity set.

Mapping: entity archetype hash == joaat(<ydr file name>)   (verified: all 32 val_01_ models
matched fields +88 / +112 of the .ytyp archetype struct).

Usage: python export_building_meshes.py
Output: export/levels/town/valentine_meshes.json
"""
import os, sys, json, glob, struct

ROOT = r"D:/BrainMaker/大镖客2解包分析"
sys.path.insert(0, os.path.join(ROOT, "tools"))
from rdr2_ydr import extract as ydr_extract


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xffffffff
        h = (h + (h << 10)) & 0xffffffff
        h ^= (h >> 6)
    h = (h + (h << 3)) & 0xffffffff
    h ^= (h >> 11)
    h = (h + (h << 15)) & 0xffffffff
    return h


def main():
    town = os.path.join(ROOT, "export/levels/town")
    ents = json.load(open(os.path.join(town, "valentine.json")))
    used = {}
    for e in ents:
        used[e[0]] = used.get(e[0], 0) + 1

    # 非"建筑本体"的资源：路面 / LOD / 贴花 / 占位 / 道具 / 植被 / 音频代理…
    EXCLUDE = ('_em_slod', '_slod', 'audioproxy', 'vfx_', 'helper', 'lights_holder',
               '_decal', 'decal', '_props_', 'props_debris', 'footboards', '_dcl', '_veg',
               '_shad', 'magiclantern_dec', 'aucb_dec', 'resf_dec', '_em00',
               '_int_', '_lod', 'pr_combo', 'audioemitter', 'glue_02', 'rds_hay')

    ydr_files = glob.glob(os.path.join(ROOT, "export/models/buildings*/*/**/*.ydr"), recursive=True)
    out = {}
    parsed = 0
    skipped = 0
    for f in ydr_files:
        name = os.path.splitext(os.path.basename(f))[0]
        if any(s in name for s in EXCLUDE):
            continue
        hh = joaat(name)
        if hh not in used:
            continue
        try:
            info, meshes = ydr_extract(f)
        except Exception:
            continue
        if not meshes:
            continue
        parsed += 1
        # 只保留 high LOD，合并为单一 mesh（positions + indices），
        # 同时按**每个几何体的 albedo 贴图**切出索引区间组（grp）供多材质渲染
        pos = []
        idx = []
        base = 0
        grp = []          # [ [texName, indexStart, indexCount], ... ]
        tnames = set()
        for m in meshes:
            if m['lod'] != 'high':
                continue
            p = m['positions']
            pos.extend(p)
            start = len(idx)
            idx.extend([i + base for i in m['indices']])
            base += m['vertex_count']
            t = m.get('tex')
            if t:
                tnames.add(t)
            grp.append([t or '', start, len(idx) - start])
        if not idx:
            continue
        out[str(hh)] = {
            "name": name,
            # 相对 ydr 局部原点（= 包围盒中心 0,0,0 附近）
            "p": [round(v, 3) for v in pos],
            "i": idx,
            "vc": base,
            "tc": len(idx) // 3,
            "bbox": [info['bbox_min'], info['bbox_max']],
            "grp": grp,
            "texs": sorted(tnames),
        }

    path = os.path.join(town, "valentine_meshes.json")
    json.dump(out, open(path, "w"), separators=(',', ':'))
    tot_v = sum(m['vc'] for m in out.values())
    tot_t = sum(m['tc'] for m in out.values())
    covered = sum(used[k] for k in map(int, out.keys()) if k in used)
    print(f"ydr scanned={len(ydr_files)} parsed(matched)={parsed}")
    print(f"models exported={len(out)}  total verts={tot_v}  tris={tot_t}")
    print(f"valentine entities covered={covered}/{len(ents)}  ({len(out)} distinct archetypes)")
    print("wrote", path, round(os.path.getsize(path) / 1024 / 1024, 2), "MB")


if __name__ == '__main__':
    main()
