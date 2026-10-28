import os, struct, json, collections

ROOT = r"D:/BrainMaker/大镖客2解包分析/export"
RSC8 = 0x38435352

cats = collections.defaultdict(lambda: {"count":0, "bytes":0, "rsc8":0, "other":0, "nosig":0})
ext_stats = collections.defaultdict(lambda: [0,0])
bad = []

for dirpath, dirs, files in os.walk(ROOT):
    for fn in files:
        p = os.path.join(dirpath, fn)
        rel = os.path.relpath(p, ROOT).replace("\\","/")
        top = rel.split("/")[0]
        if rel.startswith("animations"): cat="animations"
        elif rel.startswith("models"): cat="models"
        elif rel.startswith("levels/map_metadata"): cat="map_metadata"
        elif rel.startswith("levels/collision"): cat="collision"
        else: cat="other"
        sz = os.path.getsize(p)
        c = cats[cat]; c["count"]+=1; c["bytes"]+=sz
        ext = os.path.splitext(fn)[1].lower() or "(none)"
        ext_stats[ext][0]+=1; ext_stats[ext][1]+=sz
        with open(p,'rb') as f: head=f.read(16)
        if len(head)>=4:
            magic = struct.unpack_from('<I', head, 0)[0]
            if magic==RSC8: c["rsc8"]+=1
            else:
                c["other"]+=1
                if len(bad)<12: bad.append((rel, hex(magic)))
        else:
            c["nosig"]+=1

print("=== category summary ===")
tot=0
for k,v in sorted(cats.items()):
    print(f"{k:14} files={v['count']:7} bytes={v['bytes']:>14,} RSC8={v['rsc8']:7} non-RSC8={v['other']}")
    tot+=v['bytes']
print(f"TOTAL bytes={tot:,}  ({tot/1024/1024:.1f} MB)")

print("\n=== extension breakdown ===")
for ext,(n,b) in sorted(ext_stats.items(), key=lambda x:-x[1][0])[:20]:
    print(f"{ext:8} {n:7} {b:>14,}")

print("\n=== sample non-RSC8 (expected: none for resource files) ===")
for r,m in bad: print(" ", r, m)
