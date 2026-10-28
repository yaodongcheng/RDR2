import struct, sys, os

path = sys.argv[1]
sz = os.path.getsize(path)
with open(path, 'rb') as f:
    head = f.read(16 + 256 + 24*40)

magic, entry_count, names_length = struct.unpack_from('<III', head, 0)
tag, plat = struct.unpack_from('<HH', head, 12)
print(f"FILE {os.path.basename(path)}  size={sz:,}")
print(f"magic={magic:#010x} entry_count={entry_count} names_length={names_length} tag={tag:#06x} plat={plat:#06x}")

entries_start = 16 + 256
print("--- first 24 entries (24-byte interpretation, rage-rpf layout) ---")
for i in range(24):
    off = entries_start + i*24
    if off+24 > len(head): break
    q0, q8, q10 = struct.unpack_from('<QQQ', head, off)
    hash_ = q0 & 0xFFFFFFFF
    enc_config = (q0 >> 32) & 0xFF
    enc_key_id = (q0 >> 40) & 0xFF
    ext_id = (q0 >> 48) & 0xFF
    is_resource = (q0 >> 56) & 1
    on_disk = ((q8 & 0xFFFFFFF) << 4) & 0xFFFFFFFF
    byte_off = (((q8 >> 28) & 0x7FFFFFFF) << 4) & 0xFFFFFFFF
    comp = (q8 >> 59) & 0x1F
    print(f"[{i:3}] hash={hash_:08X} enc_cfg={enc_config:02x} keyid={enc_key_id:02x} ext={ext_id:02x} res={is_resource} disk={on_disk:>12,} off={byte_off:>14,} comp={comp} q10={q10:016X}")

print("--- first 24 entries (16-byte interpretation) ---")
for i in range(24):
    off = entries_start + i*16
    if off+16 > len(head): break
    a, b, c, d = struct.unpack_from('<IIII', head, off)
    print(f"[{i:3}] a={a:08X} b={b:08X} c={c:08X} d={d:08X}")
