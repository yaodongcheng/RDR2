"""整块大陆 · 统一实体索引（全局资产库方案的输入层）。

数据源：export/levels/world/town_data/*.js（全量精细实体，184,593 条）
        —— map_metadata 里 4228 个 ymap 全是 lod_combine 代理，不能当精细层用。

实例表里只有 (hash, 变换, 尺寸档)，几何体统一由全局资产库提供 —— 这是"兼顾存储"
的关键：同一个 archetype 在整块大陆上只存一份几何。

产物：
  export/world/continent/tiles/<tileId>.json   [[hash, x,y,z, qx,qy,qz,qw, sxy,sz, cls], ...]
  export/world/continent/index.json            统计 + 每块数量 + 用到的 hash 清单
  work/world_analysis/model_need.json          hash → 名字 / 引用次数（资产库要抽的模型清单）

尺寸档 cls：3 = ≥8 m（建筑主体）2 = 4~8 m  1 = 1.5~4 m（结构/道具）0 = <1.5 m（小物件）

用法：
  uv run python tools/build_continent_index.py
"""
import os
import re
import glob
import json
from collections import defaultdict, Counter

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TOWN = os.path.join(ROOT, 'export/levels/world/town_data')
OUT = os.path.join(ROOT, 'export/world/continent')
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')

X0, Y0, WORLD = -7684.0, -8196.0, 12296.0
TILE = 2000.0


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xffffffff
        h = h + (h << 10) & 0xffffffff
        h ^= h >> 6
    h = (h + (h << 3)) & 0xffffffff
    h ^= h >> 11
    h = (h + (h << 15)) & 0xffffffff
    return h


def load_name_by_hash():
    m = {}
    with open(NAMES, encoding='latin1', errors='ignore') as f:
        for n in f:
            n = n.strip()
            if n and not n.startswith('#'):
                m[joaat(n)] = n
    return m


def load_entities():
    """读出所有 area 的实体，返回 [hash, x,y,z, qx,qy,qz,qw, sxy,sz, cls]。"""
    ents = []
    seen = set()
    dup = 0
    files = 0
    for f in sorted(glob.glob(os.path.join(TOWN, '*.js'))):
        txt = open(f, encoding='utf-8', errors='ignore').read()
        m = re.search(r'RDR2_TOWNS\["([^"]+)"\]\s*=\s*(\[\[.*\]\])\s*;?\s*$', txt, re.S)
        if not m:
            continue
        data = json.loads(m.group(2))
        files += 1
        for e in data:
            h, x, y, z = e[0], e[1], e[2], e[3]
            if not (X0 <= x <= X0 + WORLD and Y0 <= y <= Y0 + WORLD):
                continue
            key = (h, round(x, 1), round(y, 1), round(z, 1))
            if key in seen:
                dup += 1
                continue
            seen.add(key)
            # 16 字段布局：0 hash / 1-3 pos / 4-7 quat / 8 sxy / 9 sz / 10-12 bbox min / 13-15 bbox max
            dx, dy, dz = e[13] - e[10], e[14] - e[11], e[15] - e[12]
            s = max(dx, dy, dz)
            cls = 3 if s >= 8 else 2 if s >= 4 else 1 if s >= 1.5 else 0
            ents.append([h, round(x, 1), round(y, 1), round(z, 1),
                         e[4], e[5], e[6], e[7],
                         e[8] if abs(e[8]) > 1e-6 else 1.0,
                         e[9] if abs(e[9]) > 1e-6 else 1.0, cls])
    print('area 文件 %d，实体 %d（跨文件重复 %d）' % (files, len(ents), dup))
    return ents


def main():
    os.makedirs(os.path.join(OUT, 'tiles'), exist_ok=True)
    name_by_hash = load_name_by_hash()
    print('名字表 %d 条' % len(name_by_hash))

    ents = load_entities()
    uniq = {e[0] for e in ents}
    named = sum(1 for h in uniq if h in name_by_hash)
    print('唯一 archetype %d，可命名 %d (%.1f%%)' % (len(uniq), named, 100.0 * named / max(1, len(uniq))))

    cnt = Counter(e[0] for e in ents)
    tiles = defaultdict(list)
    for e in ents:
        i = int((e[1] - X0) // TILE)
        j = int((Y0 + WORLD - e[2]) // TILE)
        tiles['wild2000_%02d_%02d' % (i, j)].append(e)

    tlist = []
    for tid, ts in sorted(tiles.items()):
        ts.sort(key=lambda e: (-e[10], -cnt[e[0]]))
        p = os.path.join(OUT, 'tiles', tid + '.json')
        json.dump(ts, open(p, 'w'), separators=(',', ':'))
        tlist.append(dict(id=tid, n=len(ts), uniq=len({e[0] for e in ts}),
                          bytes=os.path.getsize(p)))
        print('  %s  %6d 实体 / %5d 模型 / %5.0f KB' % (tid, len(ts),
                                                      len({e[0] for e in ts}),
                                                      os.path.getsize(p) / 1024))

    # 尺寸档统计（决定"要还原到什么精细度"）
    byc = Counter(e[10] for e in ents)
    json.dump(dict(total=len(ents), tiles=len(tlist), uniq=len(uniq), named=named,
                   tile_m=TILE, classes={'>=8m': byc[3], '4-8m': byc[2],
                                         '1.5-4m': byc[1], '<1.5m': byc[0]},
                   tile_list=tlist),
              open(os.path.join(OUT, 'index.json'), 'w'), ensure_ascii=False, indent=1)

    need = {hex(h): dict(name=name_by_hash.get(h, ''), n=cnt[h]) for h in uniq}
    json.dump(need, open(os.path.join(ROOT, 'work/world_analysis/model_need.json'), 'w'),
              ensure_ascii=False, indent=0)
    print('尺寸档 %s' % dict(byc))
    print('→ %s  %d 块 / %.1f MB 实例' % (OUT, len(tlist), sum(t['bytes'] for t in tlist) / 1e6))
    print('→ model_need.json  %d 个待抽模型 / %.1f MB' % (
        len(need), os.path.getsize(os.path.join(ROOT, 'work/world_analysis/model_need.json')) / 1e6))


if __name__ == '__main__':
    main()
