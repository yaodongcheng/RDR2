import os, csv, struct, collections

ROOT = r"D:/BrainMaker/大镖客2解包分析"
EXPORT = os.path.join(ROOT, "export")
OUT = os.path.join(ROOT, "inventory.csv")
RSC8 = 0x38435352

rows = []
for dirpath, dirs, files in os.walk(EXPORT):
    for fn in files:
        p = os.path.join(dirpath, fn)
        rel = os.path.relpath(p, EXPORT).replace("\\", "/")
        cat = rel.split("/")[0]
        if rel.startswith("levels/"):
            cat = "levels/" + rel.split("/")[1]
        sz = os.path.getsize(p)
        with open(p, 'rb') as f: head = f.read(16)
        magic = struct.unpack_from('<I', head, 0)[0] if len(head) >= 4 else 0
        rows.append((cat, rel, os.path.splitext(fn)[1].lower(), sz, "RSC8" if magic == RSC8 else hex(magic)))

rows.sort(key=lambda r: (r[0], r[1]))
bycat = collections.Counter(r[0] for r in rows)
char = collections.Counter(r[2] for r in rows)
print("rows:", len(rows))
print("by category:", dict(bycat))

with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["category", "relative_path", "ext", "size_bytes", "magic"])
    for r in rows:
        w.writerow(r)
print("wrote", OUT)
print("\ntop extensions:")
for e, n in char.most_common(15):
    print(f"  {e:8} {n}")
