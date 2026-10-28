"""Export prop meshes (`.ydr` / `.yft`) for Valentine entities from the prop packs.

发现：Valentine 的 2263 个实体里，除了建筑（`.ydr`）与 LOD（`.ydd`），剩下大量是**道具**——
它们不在 town 自己的 area rpf 里，而在 `levels_3.rpf` 下的 149 个 **props 包**
（`levels/rdr3/props/{generic,vegetation,structure,areas,lev_des,...}/*.rpf`），
且多为 **`.yft`（fragment）**，所以之前只扫 `.ydr` 时全漏了。

`.yft` 的 drawable 挂在 fragment 头的若干指针上（+0x20 通常为主 drawable），
用 `rdr2_ydr.extract_frag()` 解析。

用法: python export_prop_meshes.py
输出: export/levels/town/valentine_prop_meshes.json
"""
import os, sys, json, glob

ROOT = r"D:/BrainMaker/大镖客2解包分析"
sys.path.insert(0, os.path.join(ROOT, "tools"))
from rdr2_ydr import extract as ydr_extract, extract_frag


def gather(name, idx):
    pos = []; idxs = []; b = 0
    for m in idx:
        pos += m['positions']
        idxs += [i + b for i in m['indices']]
        b += m['vertex_count']
    if not idxs:
        return None
    return dict(name=name, p=pos, i=idxs, vc=b, tc=len(idxs) // 3)


def main():
    town = os.path.join(ROOT, "export/levels/town")
    hits = json.load(open("C:/Users/yaodongcheng/AppData/Local/Temp/prop_hits.json"))
    want = {}
    for pack, items in hits.items():
        for nm, h in items:
            if nm.endswith('.ytd'):
                continue
            want[nm] = h

    out = {}
    ok = fail = 0
    for nm, h in want.items():
        found = glob.glob(os.path.join(ROOT, "export/models/props/*/" + nm))
        if not found:
            fail += 1; continue
        f = found[0]
        try:
            if nm.endswith('.ydr'):
                info, ms = ydr_extract(f)
            else:
                info, ms = extract_frag(f)
            mm = gather(os.path.splitext(nm)[0], ms)
            if not mm:
                fail += 1; continue
            out[str(h)] = mm
            ok += 1
        except Exception:
            fail += 1
    path = os.path.join(town, "valentine_prop_meshes.json")
    json.dump(out, open(path, 'w'), separators=(',', ':'))
    tv = sum(m['vc'] for m in out.values()); tt = sum(m['tc'] for m in out.values())
    print(f"props ok={ok} fail={fail}  verts={tv} tris={tt}")
    print("wrote", path, round(os.path.getsize(path) / 1024 / 1024, 2), "MB")


if __name__ == '__main__':
    main()
