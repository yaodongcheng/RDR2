"""提取 outskirts 地形包（out_*），并算出每包的 world bbox。

outskirt 包结构（与主地形 <letter>_<row>_ 不同）：
  out_a_01.rpf
    ├── out_a_01.ytd              地形色图（一片 4×4 个 1024 m patch）
    ├── out_a_01_hd_01..16.ydr    16 个 patch，各自 1024 m，17×17 顶点
    └── out_a_01.ymap             摆放：archetype=<patch 名>，position=patch 中心（z=基准高程）

用法：
  uv run python tools/extract_outskirts.py --list      # 只看 bbox
  uv run python tools/extract_outskirts.py             # 全量提取 + bbox
"""
import os
import re
import sys
import glob
import json
import shutil
import argparse
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = r'D:/BrainMaker/大镖客2解包分析'
GAME = r'H:/EPICGAMES/RedDeadRedemption2'
RP = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe')
OUT = os.path.join(ROOT, 'work/outskirts')
PACKS = os.path.join(OUT, 'packs')
INNER = os.path.join(OUT, 'inner')


def names_map():
    p = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
    d = {}
    for line in open(p, encoding='latin1', errors='ignore'):
        n = line.strip()
        if not n:
            continue
        h = 0
        for c in n.lower().encode():
            h = (h + c) & 0xffffffff
            h = (h + (h << 10)) & 0xffffffff
            h ^= h >> 6
        h = (h + (h << 3)) & 0xffffffff
        h ^= h >> 11
        h = (h + (h << 15)) & 0xffffffff
        d[h] = n
    return d


def out_names():
    s = set()
    for f in glob.glob(os.path.join(ROOT, 'work/terrain/list_levels_*.txt')):
        for line in open(f, encoding='utf-8', errors='ignore'):
            m = re.search(r'(levels/rdr3/terrain/outskirts/(out_[a-z0-9_]+)\.rpf)\s*$', line.strip())
            if m:
                s.add((m.group(2), m.group(1)))
    return sorted(s)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    os.makedirs(PACKS, exist_ok=True)
    os.makedirs(INNER, exist_ok=True)
    import ymap_entities
    nm = names_map()
    boxes = {}
    for name, path in out_names():
        d = os.path.join(INNER, name)
        ymaps = glob.glob(os.path.join(d, '*.ymap'))
        if not ymaps:
            rp = os.path.join(PACKS, name + '.rpf')
            if not os.path.exists(rp):
                run([RP, 'extract', os.path.join(GAME, 'levels_6.rpf'), PACKS, path])
                found = glob.glob(os.path.join(PACKS, '**', name + '.rpf'), recursive=True)
                if not found:
                    print('  !! 未取到', name)
                    continue
                rp = found[0]
            os.makedirs(d, exist_ok=True)
            run([RP, 'extract', rp, d, ''])
            ymaps = glob.glob(os.path.join(d, '*.ymap'))
        xs, ys = [], []
        for y in ymaps:
            try:
                _s, _z, es = ymap_entities.extract(y)
            except Exception:
                continue
            for e in es:
                n = nm.get(e[0], '')
                if '_hd_' in n and n.startswith(name):
                    xs.append(e[1]); ys.append(e[2])
        if xs:
            boxes[name] = [min(xs) - 512, min(ys) - 512, max(xs) + 512, max(ys) + 512, len(xs)]
    json.dump(boxes, open(os.path.join(OUT, 'bbox.json'), 'w'), indent=1)
    print('包 %d 个，有摆放的 %d' % (len(out_names()), len(boxes)))
    for k, v in sorted(boxes.items()):
        print('  %-10s x[%7.0f,%7.0f] y[%7.0f,%7.0f] patches=%d' % (k, v[0], v[2], v[1], v[3], v[4]))


if __name__ == '__main__':
    main()
