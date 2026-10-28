"""把全世界 18.4 万个实体（房子 / 道具 / 植被 / 载具…）按 2000 m 分区切开，供"分区地图"浏览。

数据源：export/levels/world/town_data/*.js
  每条 = [archetypeHash, x, y, z, qx,qy,qz,qw, sx,sy,sz, minx,miny,minz, maxx,maxy,maxz]
  （min/max 是**已含旋转**的世界轴对齐包围盒，所以直接画矩形就是它的占地）

产物：
  export/world/etiles/<tileId>.json   { id, bbox, n, e:[[hash, x, y, z, x0,y0,x1,y1], ...] }
  export/world/etiles/index.json      { tiles:[{id, n, bytes}], total }

用法：uv run python tools/build_entity_tiles.py
"""
import os
import re
import glob
import json
from collections import defaultdict

ROOT = r'D:/BrainMaker/大镖客2解包分析'
SRC = os.path.join(ROOT, 'export/levels/world/town_data')
OUT = os.path.join(ROOT, 'export/world/etiles')
X0, Y0, WORLD = -7684.0, -8196.0, 12296.0
TILE = 2000.0
GRID = os.path.join(ROOT, 'export/world/tiles_2000.json')

NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
BAD = ('_slod', '_lod', '_proxy', '_strm', '_collision', '_hd_', 'audioproxy',
       'occlusion', '_shad', 'helper', 'vfx_', 'decal_', '_em_')


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
    """hash → 模型名；用来剔除 LOD/代理/地形块（它们按 64 m 网格铺满全图）"""
    d = {}
    for n in open(NAMES, encoding='latin1'):
        n = n.strip()
        if n:
            d[joaat(n)] = n
    return d


PREFIX = re.compile(r'window\.RDR2_TOWNS\["[^"]+"\]=(.*);\s*$', re.S)


def qrot(q, v):
    """四元数旋转向量"""
    x, y, z, w = q
    vx, vy, vz = v
    # t = q × v
    tx = 2 * (y * vz - z * vy)
    ty = 2 * (z * vx - x * vz)
    tz = 2 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty),
            vy + w * ty + (z * tx - x * tz),
            vz + w * tz + (x * ty - y * tx))


def world_aabb(x, y, z, q, bb):
    """局部包围盒 8 角点 → 旋转后的世界 AABB（x/y 平面）"""
    bx0, by0, bz0, bx1, by1, bz1 = bb
    xs, ys = [], []
    for cx in (bx0, bx1):
        for cy in (by0, by1):
            for cz in (bz0, bz1):
                rx, ry, rz = qrot(q, (cx, cy, cz))
                xs.append(x + rx); ys.append(y + ry)
    return min(xs), min(ys), max(xs), max(ys)


def main():
    os.makedirs(OUT, exist_ok=True)
    meta = json.load(open(GRID, encoding='utf-8'))
    gx0, gy1 = meta['grid_origin']
    n = meta['grid'][0]

    names = load_names()
    buckets = defaultdict(list)
    total = 0
    dropped = 0
    for f in glob.glob(os.path.join(SRC, '*.js')):
        s = open(f, encoding='utf-8', errors='ignore').read()
        m = PREFIX.search(s)
        if not m:
            continue
        for e in json.loads(m.group(1)):
            h = int(e[0])
            nm = names.get(h, '')
            if nm and any(k in nm for k in BAD):
                dropped += 1
                continue
            x, y, z = float(e[1]), float(e[2]), float(e[3])
            q = (float(e[4]), float(e[5]), float(e[6]), float(e[7]))   # 四元数
            bb = (float(e[-6]), float(e[-5]), float(e[-4]),
                  float(e[-3]), float(e[-2]), float(e[-1]))
            x0, y0, x1, y1 = world_aabb(x, y, z, q, bb)
            hgt = max(0.0, bb[5] - bb[2])
            # 64/128 m 的整块 = 地形块 / 遮挡代理，不是房子，直接丢掉
            if (x1 - x0) >= 60 or (y1 - y0) >= 60:
                dropped += 1
                continue
            # 退化（没有 archetype）时给个 1 m 的盒子
            if x1 - x0 < 0.3:
                x0, x1 = x - 0.5, x + 0.5
            if y1 - y0 < 0.3:
                y0, y1 = y - 0.5, y + 0.5
            if not (x1 > x0 and y1 > y0):
                x0, x1 = x - 0.5, x + 0.5
                y0, y1 = y - 0.5, y + 0.5
            i = int((x - gx0) // TILE)
            j = int((gy1 - y) // TILE)
            if not (0 <= i < n and 0 <= j < n):
                continue
            buckets[(i, j)].append([h, round(x, 1), round(y, 1), round(z, 1),
                                    round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1),
                                    round(hgt, 1)])
            total += 1

    idx = {'total': total, 'tile_m': TILE, 'tiles': []}
    for (i, j), arr in sorted(buckets.items()):
        tid = 'wild2000_%02d_%02d' % (i, j)
        p = os.path.join(OUT, tid + '.json')
        json.dump({'id': tid, 'i': i, 'j': j, 'n': len(arr), 'e': arr},
                  open(p, 'w'), separators=(',', ':'))
        idx['tiles'].append({'id': tid, 'n': len(arr), 'bytes': os.path.getsize(p)})

    idx['count'] = len(idx['tiles'])
    json.dump(idx, open(os.path.join(OUT, 'index.json'), 'w'), separators=(',', ':'))
    print('实体 %d 个（剔除 LOD/代理 %d），分布到 %d 个分区；单区最多 %d 个' %
          (total, dropped, idx['count'], max(t['n'] for t in idx['tiles'])))
    print('  ->', OUT)


if __name__ == '__main__':
    main()
