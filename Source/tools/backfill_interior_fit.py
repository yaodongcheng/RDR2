# -*- coding: utf-8 -*-
"""回填室内对位台账：把**所有已建场景**的室内包一次性写进 `docs/世界与地编/interior_fit.csv`。

    python -X utf8 tools/backfill_interior_fit.py

数据来源（都不需要开 Blender）：
  · `_logs/scene_<id>.log` 里的 `[int] <pkg>  N 件  @(x, y)` —— 摆了哪些包、多少件；
  · 同日志的 `套合到宿主：水平 (+x, +y) / 竖直 +z` 或 `按人工修正表绝对定位 (...)` —— 位移与贴合方式；
  · `parse_interior_mlo`（唯一口径）—— 朝向来源、LOD 原始 yaw、最终 yaw、宿主名。
"""
import glob
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_interior_mlo as PM  # noqa: E402

ROOT = r'D:/BrainMaker/大镖客2解包分析'
LOGDIR = os.path.join(ROOT, '_logs')
SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(SRC, 'docs', '世界与地编', 'interior_fit.csv')

RE_PKG = re.compile(r'^\[int\]\s+(\S+)\s+(\d+) 件\s+@\(')
RE_FIT = re.compile(r'\[int\]\s+(\S+)\s+套合到宿主：水平 \(([+-][\d.]+), ([+-][\d.]+)\) / 竖直 ([+-][\d.]+) m')
RE_MAN = re.compile(r'\[int\]\s+(\S+)\s+按人工修正表绝对定位 \(([+-][\d.]+), ([+-][\d.]+), ([+-][\d.]+)\)')


def yaw(e):
    import math
    qx, qy, qz, qw = e[4:8]
    return math.degrees(math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz)))


def main():
    nm = PM.load_names()
    tl = PM.tiles()
    idx = PM.mlo_index(names=nm, tile_list=tl)
    rows = []
    for path in sorted(glob.glob(os.path.join(LOGDIR, 'scene_*.log'))):
        sid = os.path.basename(path)[6:-4]
        try:
            txt = io.open(path, encoding='utf-8', errors='replace').read()
        except Exception:
            continue
        fits = {m.group(1): ('%.2f' % float(m.group(2)), '%.2f' % float(m.group(3)),
                             '%.2f' % float(m.group(4))) for m in RE_FIT.finditer(txt)}
        mans = {m.group(1): ('%.2f' % float(m.group(2)), '%.2f' % float(m.group(3)),
                             '%.2f' % float(m.group(4))) for m in RE_MAN.finditer(txt)}
        seen = set()
        for line in txt.splitlines():
            m = RE_PKG.match(line.strip())
            if not m:
                continue
            pkg, n = m.group(1), int(m.group(2))
            if pkg in seen:
                continue
            seen.add(pkg)
            raw = PM.pick_instance(idx, pkg)
            inst = PM.find_mlo_instance(pkg, names=nm, tile_list=tl)
            host = PM.host_for(pkg, idx, raw) if raw is not None else None
            if pkg in idx:
                orient = 'exact'
            elif (pkg + '_main') in idx:
                orient = 'main'
            else:
                orient = 'lod+host' if host is not None else 'lod_only'
            dx = dy = dz = ''
            fit = ''
            if pkg in mans:
                dx, dy, dz = mans[pkg]
                fit = 'manual'
            elif pkg in fits:
                dx, dy, dz = fits[pkg]
                fit = 'auto'
            rows.append({
                'scene': sid, 'pkg': pkg,
                'host': (nm.get(int(host[0]), '') if host else ''),
                'orient': orient,
                'lod_yaw': ('%.2f' % yaw(raw)) if raw is not None else '',
                'yaw': ('%.2f' % yaw(inst)) if inst is not None else '',
                'dx': dx, 'dy': dy, 'dz': dz, 'fit': fit,
                'clear_m': '', 'objects': n,
            })
    fields = ['scene', 'pkg', 'host', 'orient', 'lod_yaw', 'yaw', 'dx', 'dy', 'dz',
              'fit', 'clear_m', 'objects']
    rows.sort(key=lambda r: (r['scene'], r['pkg']))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, 'w', encoding='utf-8', newline='') as f:
        f.write(','.join(fields) + '\n')
        for r in rows:
            f.write(','.join(str(r[k]) for k in fields) + '\n')
    scenes = len({r['scene'] for r in rows})
    print('回填完成：%d 行 / %d 个场景 -> %s' % (len(rows), scenes, OUT))


if __name__ == '__main__':
    main()
