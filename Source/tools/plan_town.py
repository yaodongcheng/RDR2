"""给定城镇名，输出"还原这个镇"所需的全部参数与命令（方法论的可执行版）。

用法：
  uv run python tools/plan_town.py --zone valentine
  uv run python tools/plan_town.py --list
"""
import os, sys, re, glob, json, argparse
from collections import defaultdict

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))


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


def tile_bboxes():
    """terrain patch 名 → 世界 bbox（用于把任意坐标映射到 area 目录）"""
    import ymap_entities
    names = open(os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt'),
                 encoding='latin1').read().splitlines()
    nh = {}
    for n in names:
        n = n.strip()
        if n:
            nh[joaat(n)] = n
    box = {}
    for f in glob.glob(os.path.join(ROOT, 'export/levels/map_metadata/**/*_strm_0.ymap'), recursive=True):
        try:
            _s, _z, es = ymap_entities.extract(f)
        except Exception:
            continue
        for e in es:
            n = nh.get(e[0], '')
            m = re.match(r'([a-z]+)_(\d+)__hd_0_-?\d+_-?\d+$', n)
            if not m:
                continue
            if not (1 <= int(m.group(2)) <= 26):
                continue
            k = (m.group(1), int(m.group(2)))
            b = box.get(k)
            x, y = e[1], e[2]
            if b is None:
                box[k] = [x - 32, y - 32, x + 32, y + 32]
            else:
                b[0] = min(b[0], x - 32); b[1] = min(b[1], y - 32)
                b[2] = max(b[2], x + 32); b[3] = max(b[3], y + 32)
    return box


def area_dir_for(cx, cy, box):
    """把坐标映射到 terrain tile → area 目录；命中不到就取最近 tile。"""
    hit = None
    for (L, R), b in box.items():
        if b[0] - 10 <= cx <= b[2] + 10 and b[1] - 10 <= cy <= b[3] + 10:
            hit = (L, R)
            break
    if hit is None:
        best = None
        for (L, R), b in box.items():
            dx = max(b[0] - cx, 0, cx - b[2])
            dy = max(b[1] - cy, 0, cy - b[3])
            d = (dx * dx + dy * dy) ** 0.5
            if best is None or d < best[0]:
                best = (d, (L, R))
        hit = best[1] if best else None
    if hit is None:
        return None, None
    L, R = hit
    li = 'abcdefghijklmnopqrstuvwxyz'.index(L)
    g0 = 0 if li < 5 else 5 + ((li - 5) // 4) * 4
    start = 'abcdefghijklmnopqrstuvwxyz'[g0:g0 + 4]
    r0 = ((R - 3) // 4) * 4 + 3
    return f'{start}_{r0:02d}_{r0+3:02d}', (L, R)


ALIAS = {
    'valentine': ['valentine', 'val'], 'annesburg': ['ann', 'annesburg'],
    'blackwater': ['blackwater', 'bla'], 'rhodes': ['rhodes', 'rho'],
    'armadillo': ['armadillo', 'arm'], 'tumbleweed': ['tumbleweed', 'tum'],
    'strawberry': ['strawberry', 'str'], 'vanhorn': ['vanhorn', 'van'],
    'beechershope': ['beechers', 'bee'], 'lakay': ['lakay', 'lak'],
    'guarma': ['guarma'], 'sisika': ['sisika', 'sis'],
    'colter': ['colter'], 'caliga': ['cal', 'caliga'],
    'braithwaite': ['braithwaite', 'bra'], 'butcher': ['butcher'],
    'stdenis': ['saintdenis', 'sdn'], 'shady': ['shady'],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--zone', default='')
    ap.add_argument('--r', type=float, default=0, help='覆盖半径（默认 = 半跨度 + 60 m）')
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()

    zones = json.load(open(os.path.join(ROOT, 'export/levels/world/zones.json'), encoding='utf-8'))['zones']
    towns = [z for z in zones if z['type'] in ('TOWN', 'REGION')]
    if a.list or not a.zone:
        print('可用城镇：')
        for z in towns:
            print('  %-16s %-8s center=(%.0f,%.0f)' % (z['name'], z['type'], z['cx'], z['cy']))
        return

    key = a.zone.lower()
    z = next((x for x in towns if x['name'].lower() == key), None)
    if z is None:
        z = next((x for x in towns if key in x['name'].lower()), None)
    if z is None:
        print('找不到', a.zone); return

    b = z['bbox']
    spanx, spany = abs(b[2] - b[0]), abs(b[3] - b[1])
    cx, cy = z['cx'], z['cy']
    r = a.r or (max(spanx, spany) / 2 + 60)

    box = tile_bboxes()
    adir, tile = area_dir_for(cx, cy, box)

    names = ALIAS.get(z['name'].lower(), [z['name'].lower()[:3]])
    listing = ''
    for f in glob.glob(os.path.join(ROOT, 'work/terrain/list_levels_*.txt')):
        listing += open(f, encoding='utf-8', errors='ignore').read()
    gtxd = []
    for n in names:
        gtxd += re.findall(r'levels/rdr3/gtxd/(gtxd_%s(?:_[a-z0-9]+)?\.rpf)' % re.escape(n), listing)
    interiors = []
    for n in names:
        interiors += re.findall(r'levels/rdr3/interiors/([a-z0-9_]*%s[a-z0-9_]*_int\.rpf)' % n, listing)

    print('=' * 64)
    print('目标：%s（%s）' % (z['name'], z['type']))
    print('  中心      : (%.0f, %.0f)' % (cx, cy))
    print('  包围盒    : %.0f x %.0f m' % (spanx, spany))
    print('  建议半径  : %.0f m' % r)
    print('  terrain tile: %s    area 目录: %s' % (tile, adir))
    print('  共享贴图包: %s' % (', '.join(sorted(set(gtxd))) if gtxd else '（需在 levels_*.rpf 里找 gtxd_*.rpf）'))
    print('  室内包    : %s' % (', '.join(sorted(set(interiors))) if interiors else '（需先抽 interiors/*.rpf）'))
    print('-' * 64)
    print('步骤（与圣丹尼斯完全相同的管线）：')
    print('''
  1) 抽城市模型
     rdr2rpf extract <game>/levels_2.rpf work/<code>/models "levels/rdr3/area/%s/<pack>.rpf"
  2) 抽该镇共享贴图（关键，解决缺图/紫墙）
     rdr2rpf extract <game>/levels_2.rpf work/<code>/gtxd "levels/rdr3/gtxd/gtxd_%s.rpf"
  3) 导出真模型（不焊接 + 全贴图）
     uv run python tools/export_sdn_gltf.py --cx %.0f --cy %.0f --r %.0f \
         --ydr work/<code>/models --chunk 160 --maxs 512 --out export/.../<code>
  4) 地形颜色（20 个瓦片 → 4096²）
     uv run python tools/build_sdn_terrain_tex.py   （改 REGION 为 %s 的包围盒）
  5) 地面/水面/天空
     blender -b <blend> -P tools/blender_rebuild_ground.py -- --water-level <该镇水位>
     blender -b <blend> -P tools/blender_setup_sky.py
  6) 验收（必须做）
     - 建筑命中率：tools/audit_sdn_coverage.py（把 bbox 换成该镇）
     - 贴图缺失数：export 日志里的「缺 N 张」
     - 页面/渲染：shots 三视图
''' % (adir or '<area>', names[0], cx, cy, r, z['name']))


if __name__ == '__main__':
    main()
