"""解析 RDR2 官方地图区划 `data/levels/rdr3/mapzones.meta`。

产物 `export/levels/world/zones.json`：
  { "states":[{name,type,polygons:[[[x,y],...]],bbox,cx,cy}...],
    "regions":[...], "towns":[...], "water":[...] }

说明：hull 的 z 恒为 0（区划是 2D 俯视多边形），坐标为 RDR2 世界坐标（米）。
"""
import os
import re
import json

ROOT = r'D:/BrainMaker/大镖客2解包分析'
SRC = os.path.join(ROOT, 'work/worldmeta/data/levels/rdr3/mapzones.meta')
OUT = os.path.join(ROOT, 'export/levels/world/zones.json')

ITEM_RE = re.compile(r'<Item>(.*?)</Item>', re.S)
NAME_RE = re.compile(r'<Name>([^<]+)</Name>')
TYPE_RE = re.compile(r'<Type>([^<]+)</Type>')
HULL_RE = re.compile(r'<ZoneAreaHull[^>]*>(.*?)</ZoneAreaHull>', re.S)
BB_RE = re.compile(
    r'<min x="([-\d.]+)" y="([-\d.]+)"[^>]*/>\s*<max x="([-\d.]+)" y="([-\d.]+)"', re.S)


def parse():
    d = open(SRC, encoding='utf-8').read()
    # 顶层 Zones 容器里的 Item 才是 zone（ZoneAreas 内也有 <Item>，靠"是否含 <Name>"过滤）
    zones = []
    for m in ITEM_RE.finditer(d):
        blk = m.group(1)
        nm = NAME_RE.search(blk)
        if not nm:
            continue
        name = nm.group(1).strip()
        typ = (TYPE_RE.search(blk).group(1).strip() if TYPE_RE.search(blk) else 'REGION')
        polys = []
        for h in HULL_RE.finditer(blk):
            pts = []
            for line in h.group(1).strip().splitlines():
                t = line.split()
                if len(t) >= 2:
                    try:
                        pts.append([round(float(t[0]), 1), round(float(t[1]), 1)])
                    except ValueError:
                        pass
            if len(pts) >= 3:
                polys.append(pts)
        bb = BB_RE.search(blk)
        if bb:
            x0, y0, x1, y1 = (float(bb.group(i)) for i in (1, 2, 3, 4))
        elif polys:
            xs = [p[0] for poly in polys for p in poly]
            ys = [p[1] for poly in polys for p in poly]
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        else:
            continue
        zones.append({
            'name': name, 'type': typ, 'bbox': [x0, y0, x1, y1],
            'cx': round((x0 + x1) / 2, 1), 'cy': round((y0 + y1) / 2, 1),
            'polygons': polys,
        })
    return zones


if __name__ == '__main__':
    zones = parse()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    by = {}
    for z in zones:
        by.setdefault(z['type'], []).append(z)
    types = sorted(by, key=lambda k: -len(by[k]))
    print('zones:', len(zones), '| types:', [(t, len(by[t])) for t in types])
    for t in types:
        print(f'  [{t}]', ', '.join(z['name'] for z in by[t][:40]))
    json.dump({'zones': zones}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False,
              separators=(',', ':'))
    print('->', OUT)
