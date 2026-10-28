"""Extract entity list from an RDR2 .ymap (RAGE Meta, magic 0x50524430)."""
import struct, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rage_meta import parse, SYS

# entity structure signature: entries with (Hash@8) + (float3@32) + (float4@48) + (float@64) + (float@68)
def find_entity_struct(d, structs):
    for nh, nm, size, cnt, ep in structs:
        offs = {}
        for e in range(cnt):
            o = (ep - SYS) + e * 16
            _, doff, dt = struct.unpack_from('<iiB', d, o)
            offs.setdefault(doff, set()).add(dt)
        if (8 in offs and 0x4A in offs[8]) and (32 in offs and 0x33 in offs[32]) \
           and (48 in offs and 0x34 in offs[48]) and (64 in offs and 0x21 in offs[64]):
            return nh, size
    return None, None


def extract(path):
    d = open(path, 'rb').read()[16:]
    structs, blocks = parse(d)
    nh, size = find_entity_struct(d, structs)
    if nh is None:
        return None, None, []
    ents = []
    for bnh, dl, dp in blocks:
        if bnh == nh and dl >= size and dl % size == 0:
            base = dp - SYS
            for i in range(dl // size):
                o = base + i * size
                arch = struct.unpack_from('<I', d, o + 8)[0]
                px, py, pz = struct.unpack_from('<3f', d, o + 32)
                qx, qy, qz, qw = struct.unpack_from('<4f', d, o + 48)
                sxy, sz = struct.unpack_from('<2f', d, o + 64)
                if not (-20000 < px < 20000 and -20000 < py < 20000): continue
                ents.append([arch, round(px, 2), round(py, 2), round(pz, 2),
                             round(qx, 4), round(qy, 4), round(qz, 4), round(qw, 4),
                             round(sxy, 3), round(sz, 3)])
    return hex(nh), size, ents


if __name__ == '__main__':
    import glob
    root = sys.argv[1]; pat = sys.argv[2]; out = sys.argv[3]
    allents = []; files = 0
    for f in sorted(glob.glob(os.path.join(root, '**', pat), recursive=True)):
        sig, size, ents = extract(f)
        if ents:
            files += 1; allents += ents
            print(f"  {os.path.basename(f)}: struct={sig} size={size} entities={len(ents)}")
    json.dump(allents, open(out, 'w'), separators=(',', ':'))
    print(f"total {len(allents)} entities from {files} ymap files -> {out}")
