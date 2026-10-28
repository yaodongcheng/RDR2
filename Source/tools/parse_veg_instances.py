"""Parse RDR2 vegetation instance placements (`*_trees_*.ymap` / `*_grass_*.ymap`).

结论：植被不走 ymap 实体，而在
  `levels/rdr3/terrain/instance_placement/<grid>_instance_placement.rpf`
的 `*_trees_*.ymap` / `*_grass_*.ymap` 里。

这些 ymap 用的**不是**普通实体结构（144B），而是一个 **368 字节** 的记录：
    +0x08  u32     archetype 哈希（== joaat(模型名)，实测 452/452 命中 names.txt）
    +0x90  float3  世界坐标（实测 1913/2328 落在合理世界范围）

用法:
  python parse_veg_instances.py <veg_ymap_dir> <out.json>
"""
import os, sys, struct

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rage_meta import parse, SYS


def world(x, y, z):
    return -1800 < x < 800 and 200 < y < 2000 and 40 < z < 400


def parse_file(path):
    d = open(path, 'rb').read()[16:]
    structs, blocks = parse(d)
    out = []
    for nh, nm, size, cnt, ep in structs:
        if size != 368:
            continue
        for bnh, dl, dp in blocks:
            if bnh != nh or dl < size or dl % size:
                continue
            base = dp - SYS
            for i in range(dl // size):
                o = base + i * size
                if o + size > len(d):
                    break
                h = struct.unpack_from('<I', d, o + 8)[0]
                x, y, z = struct.unpack_from('<3f', d, o + 0x90)
                if not h or not world(x, y, z):
                    continue
                out.append([h, round(x, 2), round(y, 2), round(z, 2)])
    return out


def main():
    import glob, json
    src, out = sys.argv[1], sys.argv[2]
    allv = []
    files = 0
    for f in sorted(glob.glob(os.path.join(src, "*_trees_*.ymap")) + glob.glob(os.path.join(src, "*_grass_*.ymap"))):
        got = parse_file(f)
        if got:
            files += 1
            allv += got
            print(f"  {os.path.basename(f)}: {len(got)}")
    json.dump(allv, open(out, 'w'), separators=(',', ':'))
    print(f"total {len(allv)} vegetation instances from {files} files -> {out}")


if __name__ == '__main__':
    main()
