"""把 assets/lib_native/index.json（52 539 个网格）+ names.txt 合成一张"全量模型台账"。

为什么需要它
  deliverable/handoff/model_manifest.csv 只有 10 893 条，而据点里 55% 的实例引用的 hash
  不在里面（那份清单是按"有名字有分类"筛过的）。做微缩模型必须知道**每一个**实例的
  占地和高度，所以改用 lib_native 的 bbox + 子网格索引数算：
      tris   = Σ(icount) / 3
      size_* = bbox max − min
      name   = names.txt 里 joaat 反查（拿不到就留空，只影响分类不影响几何）

产物
  deliverable/handoff/model_ledger.csv    hash,name,tris,verts,sx,sy,sz,tex_id
"""
import os
import csv
import json

ROOT = r'D:/BrainMaker/大镖客2解包分析'
INDEX = os.path.join(ROOT, 'assets/lib_native/index.json')
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
OUT = os.path.join(ROOT, 'deliverable/handoff/model_ledger.csv')


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


def main():
    names = {}
    with open(NAMES, encoding='latin1') as f:
        for n in f:
            n = n.strip()
            if n:
                names[joaat(n)] = n

    idx = json.load(open(INDEX))['models']
    rows = []
    for k, v in idx.items():
        h = int(k, 16)
        b = v['b']
        tris = sum(s[2] for s in v['s']) // 3
        verts = sum(s[1] for s in v['s'])
        rows.append({
            'hash': k,
            'name': names.get(h, ''),
            'tris': tris,
            'verts': verts,
            'sx': round(b[3] - b[0], 4),
            'sy': round(b[4] - b[1], 4),
            'sz': round(b[5] - b[2], 4),
            'tex_id': v['s'][0][0] if v['s'] else -1,
        })
    with open(OUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    named = sum(1 for r in rows if r['name'])
    print(f'{OUT}: {len(rows):,} 个模型（有名 {named:,} / 无名 {len(rows)-named:,}）')


if __name__ == '__main__':
    main()
