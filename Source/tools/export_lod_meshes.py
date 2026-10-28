"""Extract LOD meshes from RDR2 `.ydd` (DrawableDictionary) for Valentine entities.

背景：Valentine 2263 个实体里，只有 ~180 个 archetype 能在 `.ydr` 模型库中找到；
其中 431 个实体对应的 archetype 哈希出现在 `<area>_slod_children.ydd` 这些 LOD 字典里。
本工具把这些 LOD 网格抽出来并落成 JSON，供查看器把「灰盒」换成真实（低模）几何。

用法: python export_lod_meshes.py
输出: export/levels/town/valentine_lod_meshes.json
"""
import os, sys, json, glob, collections

ROOT = r"D:/BrainMaker/大镖客2解包分析"
sys.path.insert(0, os.path.join(ROOT, "tools"))
from rdr2_ydr import extract_ydd


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
    E = json.load(open(os.path.join(town, "valentine.json")))
    want = collections.Counter(e[0] for e in E)

    have = set()
    for f in glob.glob(os.path.join(ROOT, "export/models/buildings*/*/**/*.ydr"), recursive=True):
        have.add(joaat(os.path.splitext(os.path.basename(f))[0]))
    need = set(h for h in want if h not in have)
    print(f"valentine archetypes={len(want)}  already covered by .ydr={len(have & set(want))}  need={len(need)}")

    ydd = sorted(glob.glob(os.path.join(ROOT, "export/models/area_lod_ydd*/*.ydd")))
    print("ydd files:", len(ydd))

    out = {}
    scanned = 0
    import numpy as np
    need_arr = np.array(sorted(need), dtype='<u4')
    for p in ydd:
        raw = open(p, 'rb').read()
        arr = np.frombuffer(raw, dtype='<u4')
        fnd = set(arr[np.isin(arr, need_arr)].tolist())
        if not fnd:
            continue
        scanned += 1
        got = extract_ydd(p, 'high', want_hashes=fnd)
        for h, m in got.items():
            if h in out:
                continue
            out[h] = m
    print("ydds with hits:", scanned, " models extracted:", len(out))

    # 打包（int16 量化由查看器构建脚本负责，这里存原始 float）
    path = os.path.join(town, "valentine_lod_meshes.json")
    json.dump(out, open(path, 'w'), separators=(',', ':'))
    tv = sum(m['vc'] for m in out.values())
    tt = sum(m['tc'] for m in out.values())
    cov = sum(want[h] for h in out)
    print(f"models={len(out)} verts={tv} tris={tt} entities covered={cov}/{len(E)}")
    print("wrote", path, round(os.path.getsize(path) / 1024 / 1024, 2), "MB")


if __name__ == '__main__':
    main()
