"""解析 RDR2 植被实例 ymap（368 字节结构）并合并进 continent tiles。

背景：植被不在 `map_metadata/*_lod_combine*` 里，而在
  levels/rdr3/terrain/instance_placement/<area>_instance_placement.rpf
里的 `*_trees_*.ymap` / `*_grass_*.ymap`。

这些 ymap 的实体结构是 **368 字节**（建筑是 144），且 position 在 **+144**（不是 +32）：

    +8    uint32  archetype hash
    +48   float4  rotation（实测多为 0）
    +144  float3  position  ← 世界坐标
    +372?

用法：
  uv run python tools/parse_veg.py --extract-dir raw/_scratch/veg --tile wild2000_05_00
  uv run python tools/parse_veg.py --scan-only            # 只统计
"""
import os
import sys
import json
import glob
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from rage_meta import parse, SYS  # noqa: E402

VEG_STRUCT = 0xba049770
VEG_SIZE = 368
TILE = 2000.0
X0, Y0, WORLD = -7684.0, -8196.0, 12296.0


def load_names():
    def joaat(s):
        h = 0
        for c in s.lower().encode():
            h = (h + c) & 0xffffffff
            h = (h + (h << 10)) & 0xffffffff
            h ^= h >> 6
        h = (h + (h << 3)) & 0xffffffff
        h ^= h >> 11
        h = (h + (h << 15)) & 0xffffffff
        return h
    d = {}
    p = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
    with open(p, encoding='latin1') as f:
        for n in f:
            n = n.strip()
            if n:
                d[joaat(n)] = n
    return d


def scan_ymap(path):
    """→ [[hash, x, y, z], ...]"""
    import struct
    d = open(path, 'rb').read()[16:]
    try:
        structs, blocks = parse(d)
    except Exception:
        return []
    out = []
    for bnh, dl, dp in blocks:
        if bnh != VEG_STRUCT or dl % VEG_SIZE:
            continue
        base = dp - SYS
        for i in range(dl // VEG_SIZE):
            o = base + i * VEG_SIZE
            h = struct.unpack_from('<I', d, o + 8)[0]
            px, py, pz = struct.unpack_from('<3f', d, o + 144)
            if not (-8000 < px < 8000 and -8000 < py < 8000 and -200 < pz < 800):
                continue
            out.append([h, round(px, 1), round(py, 1), round(pz, 1)])
    return out


def tile_of(x, y):
    i = int((x - X0) // TILE)
    j = int((Y0 + WORLD - y) // TILE)
    return 'wild2000_%02d_%02d' % (i, j)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--extract-dir', action='append', default=[])
    ap.add_argument('--tile', default='')
    ap.add_argument('--scan-only', action='store_true')
    a = ap.parse_args()

    dirs = a.extract_dir or [os.path.join(ROOT, 'raw/_scratch/veg'),
                             os.path.join(ROOT, 'raw/_scratch/grass')]
    files = []
    for d in dirs:
        files += sorted(glob.glob(os.path.join(d, '**', '*.ymap'), recursive=True))
    print('植被 ymap:', len(files))

    lib = json.load(open(os.path.join(ROOT, 'assets/lib_native/index.json'), encoding='utf-8'))['models']
    names = load_names()

    per_tile = {}
    total = inlib = 0
    for f in files:
        for e in scan_ymap(f):
            total += 1
            if hex(e[0]) in lib:
                inlib += 1
            per_tile.setdefault(tile_of(e[1], e[2]), []).append(e)
    print('实例 %d，模型在库 %d (%.1f%%)，落在 %d 个 tile' % (total, inlib, 100.0 * inlib / max(1, total), len(per_tile)))
    for t, v in sorted(per_tile.items(), key=lambda kv: -len(kv[1]))[:8]:
        print('   %-16s %d' % (t, len(v)))

    if a.scan_only:
        return

    targets = [a.tile] if a.tile else sorted(per_tile)
    for t in targets:
        ents = per_tile.get(t, [])
        if not ents:
            print('  %s: 无植被' % t)
            continue
        p = os.path.join(ROOT, 'export/world/continent/tiles', t + '.json')
        if not os.path.exists(p):
            print('  %s: tiles 文件不存在' % t)
            continue
        cur = json.load(open(p, encoding='utf-8'))
        seen = {(e[0], round(e[1], 1), round(e[2], 1)) for e in cur}
        added = 0
        for h, x, y, z in ents:
            k = (h, x, y)
            if k in seen:
                continue
            seen.add(k)
            cur.append([h, x, y, z, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 3])
            added += 1
        json.dump(cur, open(p, 'w', encoding='utf-8'), separators=(',', ':'))
        print('  %-16s +%d（原 %d → %d）' % (t, added, len(cur) - added, len(cur)))


if __name__ == '__main__':
    main()
