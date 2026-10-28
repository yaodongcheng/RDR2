"""Minimal RAGE Meta parser (magic 0x50524430) — for RDR2 .ymap/.ytyp/.ymt.

Header (from CodeWalker Meta.cs), offsets are into the RSC8 body:
 +0x10 magic u32 = 0x50524430
 +0x14 u16 platform (0x79 = PC)
 +0x16 u8 HasEncryptedStrings, +0x17 u8
 +0x18 u32 unk
 +0x1C i32 RootBlockIndex
 +0x20 u64 StructureInfosPointer
 +0x28 u64 EnumInfosPointer
 +0x30 u64 DataBlocksPointer
 +0x38 u64 NamePointer
 +0x40 u64 EncryptedStringsPointer
 +0x48 i16 StructureInfosCount
 +0x4A i16 EnumInfosCount
 +0x4C i16 DataBlocksCount
 +0x4E i16 unk
StructureInfo (32B): +0x00 u32 nameHash, +0x04 u32 key, +0x08 u32, +0x0C u32,
                    +0x10 u64 entriesPtr, +0x18 i32 size, +0x1C i16 unk, +0x1E i16 entriesCount
DataBlock (16B):     +0x00 u32 nameHash, +0x04 i32 dataLength, +0x08 u64 dataPtr
"""
import struct, sys

SYS = 0x50000000
META_MAGIC = 0x50524430


def joaat(s):
    h = 0
    for ch in s.encode('utf-8', 'replace'):
        h = (h + ch) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= (h >> 6)
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= (h >> 11)
    return (h + (h << 15)) & 0xFFFFFFFF


def load_names(path):
    m = {}
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            n = line.strip()
            if n:
                m.setdefault(joaat(n), n)
    return m


def parse(d, names=None):
    if struct.unpack_from('<I', d, 16)[0] != META_MAGIC:
        raise RuntimeError("not a Meta file")
    # RDR2 layout (measured): 0x20 root(i64), 0x28 structPtr, 0x30 enumPtr, 0x38 dataBlocksPtr,
    # 0x40 namePtr, 0x48 u16 structCount, 0x4A u16 enumCount, 0x4C u16 dataBlockCount
    sptr = struct.unpack_from('<Q', d, 0x28)[0]
    eptr = struct.unpack_from('<Q', d, 0x30)[0]
    dptr = struct.unpack_from('<Q', d, 0x38)[0]
    nptr = struct.unpack_from('<Q', d, 0x40)[0]
    sc, ec, dc, _ = struct.unpack_from('<HHHH', d, 0x48)
    print(f"Meta: structures={sc} enums={ec} datablocks={dc}")
    if nptr:
        off = nptr - SYS
        e = d.find(b'\x00', off)
        print("  Meta name:", d[off:e].decode('latin1'))
    structs = []
    for i in range(sc):
        o = (sptr - SYS) + i * 32
        nh, key, u8, uc = struct.unpack_from('<IIII', d, o)
        ep, size, u1c, cnt = struct.unpack_from('<QihH', d, o + 0x10)
        nm = names.get(nh) if names else None
        structs.append((nh, nm, size, cnt, ep))
    blocks = []
    for i in range(dc):
        o = (dptr - SYS) + i * 16
        nh = struct.unpack_from('<I', d, o)[0]
        dl = struct.unpack_from('<i', d, o + 4)[0]
        dp = struct.unpack_from('<Q', d, o + 8)[0]
        blocks.append((nh, dl, dp))
    return structs, blocks


if __name__ == '__main__':
    names = load_names(r"D:/BrainMaker/大镖客2解包分析/tools/rdr2rpf/src/names.txt")
    print("names loaded:", len(names))
    fn = sys.argv[1]
    d = open(fn, 'rb').read()[16:]
    structs, blocks = parse(d, names)
    print("\n--- structures ---")
    for nh, nm, size, cnt, ep in structs:
        print(f"  hash={nh:#010x} name={nm} size={size} entries={cnt}")
    print("\n--- data blocks ---")
    for nh, dl, dp in blocks[:12]:
        print(f"  hash={nh:#010x} name={names.get(nh)} len={dl} ptr={dp:#x}")
    print(f"  ... total {len(blocks)} blocks")
