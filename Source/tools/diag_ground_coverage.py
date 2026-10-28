"""诊断：地面色图/地形掩码到底缺了哪些地形瓦片（以及缺口的世界 bbox）。

输出：
  - 全量瓦片清单（来自 levels_*.rpf 目录列表） vs 已烘进地面色图的瓦片
  - 每个缺失瓦片的世界 bbox、是否连片
用法：
  uv run python tools/diag_ground_coverage.py
"""
import os
import re
import sys
import glob
import json

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))

GAME = r'H:/EPICGAMES/RedDeadRedemption2'
X0, Y0, WORLD = -7684.0, -8196.0, 12296.0
Y_NORTH = Y0 + WORLD


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


def all_tiles():
    """levels_*.rpf 里所有 levels/rdr3/terrain/<area>/<tile>_.rpf"""
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'work/terrain/list_levels_*.txt'))):
        lv = os.path.basename(f)[:-4].replace('list_', '')  # levels_4
        for line in open(f, encoding='utf-8', errors='ignore'):
            m = re.search(r'levels/rdr3/terrain/([^/]+)/([^/]+_[^/]*)\.rpf\s*$', line.strip())
            if not m:
                continue
            area, tile = m.group(1), m.group(2)
            out.setdefault(tile, []).append((lv, area + '/' + tile))
    return out


def tile_boxes():
    import ymap_entities
    name_by_hash = {}
    with open(os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt'),
              encoding='latin1', errors='ignore') as f:
        for line in f:
            n = line.strip()
            if n:
                name_by_hash[joaat(n)] = n
    pos = {}
    for f in glob.glob(os.path.join(ROOT, 'export/levels/map_metadata/**/*_strm_0.ymap'), recursive=True):
        try:
            _s, _z, es = ymap_entities.extract(f)
        except Exception:
            continue
        for e in es:
            n = name_by_hash.get(e[0], '')
            if '__hd_0_' in n:
                pos[n] = (e[1], e[2])
    out = {}
    for n, (x, y) in pos.items():
        t = n.split('__hd_0_')[0]
        b = out.setdefault(t, [1e9, 1e9, -1e9, -1e9])
        b[0] = min(b[0], x); b[1] = min(b[1], y)
        b[2] = max(b[2], x); b[3] = max(b[3], y)
    return {k: (v[0] - 32, v[1] - 32, v[2] + 32, v[3] + 32) for k, v in out.items()}


def main():
    tiles = all_tiles()
    boxes = tile_boxes()
    m = np.asarray(Image.open(os.path.join(ROOT, 'export/world/world_ground_mask.png')).convert('L'))
    MH, MW = m.shape
    print('瓦片包 %d（去重后），有 bbox 的 %d' % (len(tiles), len(boxes)))
    only_pack = sorted(set(tiles) - set(boxes))
    print('有包但无 bbox（metadata 没抽/摆放没找到）：%d' % len(only_pack))
    for t in only_pack[:40]:
        print('   ', t, tiles[t][:2])

    rows = []
    for t, (x0, y0, x1, y1) in sorted(boxes.items()):
        px0 = int((x0 - X0) / WORLD * MW); px1 = int((x1 - X0) / WORLD * MW)
        py0 = int((Y_NORTH - y1) / WORLD * MH); py1 = int((Y_NORTH - y0) / WORLD * MH)
        px0, px1 = max(0, px0), min(MW, px1)
        py0, py1 = max(0, py0), min(MH, py1)
        if px1 <= px0 or py1 <= py0:
            cov = -1.0
        else:
            sub = m[py0:py1, px0:px1]
            cov = float((sub > 10).mean()) if sub.size else -1.0
        rows.append((t, cov, (x0, y0, x1, y1)))

    bad = [r for r in rows if r[1] < 0.05]
    print('\n瓦片总数 %d，掩码覆盖 <5%% 的 %d 个：' % (len(rows), len(bad)))
    for t, cov, b in bad:
        print('   %-14s cov=%6.1f%%  x[%.0f,%.0f] y[%.0f,%.0f]' % (t, cov * 100, b[0], b[2], b[1], b[3]))

    # 整块掩码的缺口连通域（1 px = 1 m），列出 > 50 万 m² 的
    from scipy import ndimage
    hole = (m <= 10)
    hole[:, :] &= True
    lab, n = ndimage.label(hole)
    sizes = ndimage.sum(hole, lab, range(1, n + 1))
    idx = np.argsort(sizes)[::-1][:15]
    print('\n最大空洞连通域：')
    for i in idx:
        if sizes[i] < 200000:
            continue
        ys, xs = np.where(lab == i + 1)
        bw = (xs.min(), xs.max(), ys.min(), ys.max())
        print('  #%d area=%.0f m²  x[%.0f,%.0f] y[%.0f,%.0f]  (px %s)' % (
            i + 1, sizes[i], X0 + bw[0], X0 + bw[1], Y_NORTH - bw[3], Y_NORTH - bw[2], bw))


if __name__ == '__main__':
    main()
