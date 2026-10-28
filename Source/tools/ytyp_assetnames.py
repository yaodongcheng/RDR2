# -*- coding: utf-8 -*-
"""从 .ytyp 的 archetype 定义里取出「archetype hash ↔ assetName hash + bbox + 来源文件」，
回填成 `export/levels/town/archetype_assetnames.json`（TODO §0.5 第 1 步的修正版）。

## 背景（2026-10-29 实测，推翻了 §0.5 的前提）

旧版 `tools/ytyp_archetypes.py` 把 +88 / +112 两个 hash **混进同一个字典**，
既丢了"谁是 archetype、谁是 asset"这一对关系，也丢了"定义来自哪个 ytyp"。
本次按对读出，得到两个**决定性事实**：

1. 手上这 1,026 个 ytyp **全部是 `*_lod_combine_metadata*`（LOD 合并元数据）**；
2. 其中 **96,605 条 archetype 的 +88 与 +112 完全相等（100%）** ——
   即 `assetName == name`，**没有额外的 assetName 可挖**。

⇒ 「从 ytyp 取 assetName 再回填」这条路走不通，因为数据里就没有第二个名字。
   缺的那 4.9 万个 archetype 是 **LOD 合并块**（bm 尺寸 64/128 m 的瓦片），
   游戏在运行时按子 archetype 现场合并，磁盘上没有对应的 .ydr/.yft。
   证据见 `docs/世界与地编/RDR2_整图覆盖率核查_20261026.md` §10。

## 用法

    uv run python tools/ytyp_assetnames.py                  # 扫默认根，写 json
    uv run python tools/ytyp_assetnames.py --dump 2         # 打印 2 个 ytyp 的 struct 字段
    uv run python tools/ytyp_assetnames.py --report         # 只打印统计，不写盘
"""
import os
import sys
import json
import glob
import struct
import contextlib
import io
import argparse
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rage_meta

ROOT = r'D:/BrainMaker/大镖客2解包分析'
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
YIFF_ROOT = os.path.join(ROOT, 'export/levels/map_metadata')
OUT = os.path.join(ROOT, 'export/levels/town/archetype_assetnames.json')

SYS = rage_meta.SYS


def load_names():
    """names.txt → {joaat(name): name}（首个为准，与 rdr2rpf 的 NamesContainer 一致）"""
    m = {}
    with open(NAMES, encoding='latin1', errors='ignore') as f:
        for line in f:
            n = line.strip()
            if n:
                m.setdefault(rage_meta.joaat(n), n)
    return m


def parse_quiet(d, names=None):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return rage_meta.parse(d, names)


def find_archetype_struct(d, structs):
    """优先按名字 `CBaseArchetypeDef`；否则按形状（float3@32 / float3@48 / Hash@88 / Hash@112）。"""
    for nh, nm, size, cnt, ep in structs:
        if nm and nm.lower() == 'cbasearchetypedef':
            return nh, size
    best = None
    for nh, nm, size, cnt, ep in structs:
        fo = {}
        for e in range(cnt):
            o = (ep - SYS) + e * 16
            _, doff, dt = struct.unpack_from('<iiB', d, o)
            fo.setdefault(doff, set()).add(dt)
        if 32 in fo and 0x33 in fo[32] and 48 in fo and 0x33 in fo[48] \
                and 88 in fo and 0x4A in fo[88] and 112 in fo and 0x4A in fo[112]:
            if best is None or size < best[1]:
                best = (nh, size)
    return best if best else (None, None)


def dump_struct(path, names):
    d = open(path, 'rb').read()[16:]
    structs, blocks = parse_quiet(d, names)
    for nh, nm, size, cnt, ep in structs:
        print(f'  struct {nm or "0x%08x" % nh}  size={size} fields={cnt}')
        for e in range(cnt):
            o = (ep - SYS) + e * 16
            _, doff, dt = struct.unpack_from('<iiB', d, o)
            print(f'    +{doff:<4d} type=0x{dt:02x}')
    print(f'  blocks={len(blocks)}')


def scan(root, names):
    out = {}
    st = Counter()
    files = glob.glob(os.path.join(root, '**', '*.ytyp'), recursive=True)
    for f in files:
        try:
            d = open(f, 'rb').read()[16:]
            structs, blocks = parse_quiet(d, names)
        except Exception:
            st['bad_file'] += 1
            continue
        nh, size = find_archetype_struct(d, structs)
        if nh is None or not size:
            st['no_struct'] += 1
            continue
        short = os.path.basename(f)
        for bnh, dl, dp in blocks:
            if bnh != nh or dl < size or dl % size:
                continue
            base = dp - SYS
            for i in range(dl // size):
                o = base + i * size
                h1 = struct.unpack_from('<I', d, o + 88)[0]
                h2 = struct.unpack_from('<I', d, o + 112)[0]
                if not h1:
                    continue
                mnx, mny, mnz = struct.unpack_from('<3f', d, o + 32)
                mxx, mxy, mxz = struct.unpack_from('<3f', d, o + 48)
                st['rec'] += 1
                if h1 != h2:
                    st['pair_diff'] += 1
                if h1 in out:
                    st['dup_hash'] += 1
                    continue
                out[h1] = {
                    'asset': '0x%08x' % h2,
                    'same': h1 == h2,
                    'bbox': [round(mnx, 1), round(mny, 1), round(mnz, 1),
                             round(mxx, 1), round(mxy, 1), round(mxz, 1)],
                    'src': short,
                }
    print('[ytyp] 文件 %d（坏 %d，无 archetype struct %d）；记录 %d，唯一 hash %d，重复 %d'
          % (len(files), st['bad_file'], st['no_struct'], st['rec'], len(out), st['dup_hash']))
    print('[ytyp] **+88 != +112 的记录：%d**（0 = assetName 与 archetype 名完全相同）'
          % st['pair_diff'])
    srcs = Counter(v['src'] for v in out.values())
    lod = sum(c for s, c in srcs.items() if 'lod' in s.lower())
    print('[ytyp] 定义来源：含 "lod" 的文件 %d 个 / %d 条 archetype（%.1f%%）；其他 %d 个文件'
          % (sum(1 for s in srcs if 'lod' in s.lower()), lod, 100.0 * lod / max(1, len(out)),
             sum(1 for s in srcs if 'lod' not in s.lower())))
    other = [(s, c) for s, c in srcs.most_common() if 'lod' not in s.lower()]
    if other:
        print('[ytyp] 非 lod 文件名样例：%s' % ', '.join('%s(%d)' % t for t in other[:6]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=YIFF_ROOT)
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--dump', type=int, default=0, help='打印前 N 个 ytyp 的 struct 字段')
    ap.add_argument('--report', action='store_true', help='只统计，不写盘')
    a = ap.parse_args()

    names = load_names()
    print('[names] names.txt 唯一 hash %d' % len(names))

    if a.dump:
        for f in sorted(glob.glob(os.path.join(a.root, '**', '*.ytyp'), recursive=True))[:a.dump]:
            print('[dump]', f)
            dump_struct(f, names)
        return

    pairs = scan(a.root, names)
    if a.report:
        return
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump({'0x%08x' % h: v for h, v in pairs.items()},
              open(a.out, 'w', encoding='utf-8'), separators=(',', ':'))
    print('[ytyp] 写入 %s：%d 条（%.1f MB）'
          % (a.out, len(pairs), os.path.getsize(a.out) / 1e6))


if __name__ == '__main__':
    main()
