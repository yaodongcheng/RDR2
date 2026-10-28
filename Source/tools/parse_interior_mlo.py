"""解析 RDR2 室内 MLO 布局（ytyp 里的 144 字节 entity 块）。

背景：室内件的**摆放**不在 rpf 的同名 ymap 里，而在同包的 `<name>.ytyp`：

  levels/rdr3/interiors/<name>_int.rpf
      ├── <name>_int.ytyp        ← MLO 定义 + 455 个 entity（pos / rot / parentIndex）
      ├── roc_hse_int_shell_main.ydr
      └── ...

ytyp 内 144 字节 entity 的布局与 ymap 的 CMapEntity 一致：

    +8    uint32  archetype hash
    +32   float3  position（**室内局部坐标**，±100 m 内）
    +48   float4  rotation (x,y,z,w)      ← 注意要取共轭才能和 Blender 对齐
    +132  uint16  parentIndex（65535 = 无父）

用法：
  uv run python tools/parse_interior_mlo.py raw/_scratch/roc_ytyp/roc_house_int.ytyp
  uv run python tools/parse_interior_mlo.py <ytyp> --out interior_layout.json
"""
import os
import sys
import json
import struct
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from rage_meta import parse, SYS  # noqa: E402

ENTITY_STRUCT = 0xce501483   # 144 字节 entity
ENTITY_SIZE = 144


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


def load_names():
    d = {}
    p = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
    with open(p, encoding='latin1') as f:
        for n in f:
            n = n.strip()
            if n:
                d[joaat(n)] = n
    return d


def parse_ytyp(path):
    d = open(path, 'rb').read()[16:]
    structs, blocks = parse(d)
    out = []
    for bnh, dl, dp in blocks:
        if bnh != ENTITY_STRUCT or dl % ENTITY_SIZE:
            continue
        base = dp - SYS
        for i in range(dl // ENTITY_SIZE):
            o = base + i * ENTITY_SIZE
            h = struct.unpack_from('<I', d, o + 8)[0]
            px, py, pz = struct.unpack_from('<3f', d, o + 32)
            qx, qy, qz, qw = struct.unpack_from('<4f', d, o + 48)
            parent = struct.unpack_from('<H', d, o + 132)[0]
            if not (-100 < px < 100 and -100 < py < 100 and -100 < pz < 100):
                continue
            out.append({'h': h, 'p': [round(px, 3), round(py, 3), round(pz, 3)],
                        'q': [round(qx, 4), round(qy, 4), round(qz, 4), round(qw, 4)],
                        'parent': parent})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ytyp')
    ap.add_argument('--out', default='')
    a = ap.parse_args()

    ents = parse_ytyp(a.ytyp)
    names = load_names()
    lib = json.load(open(os.path.join(ROOT, 'assets/lib_native/index.json'), encoding='utf-8'))['models']

    uniq = {}
    for e in ents:
        uniq.setdefault(e['h'], 0)
        uniq[e['h']] += 1
    missing = [h for h in uniq if hex(h) not in lib]
    print('entity %d，唯一模型 %d，能命名 %d，模型在库 %d，缺 %d'
          % (len(ents), len(uniq), sum(1 for h in uniq if h in names),
             len(uniq) - len(missing), len(missing)))
    if missing:
        print('缺失模型（前 15）:')
        for h in missing[:15]:
            print('   0x%08x %-32s x%d' % (h, names.get(h, '<无名>'), uniq[h]))

    if a.out:
        json.dump({'ytyp': os.path.basename(a.ytyp), 'entities': ents}, open(a.out, 'w'), separators=(',', ':'))
        print('wrote', a.out)


if __name__ == '__main__':
    main()
