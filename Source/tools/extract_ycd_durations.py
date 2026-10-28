#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从 .ycd 里抽出「clip 时长表」，并标出它落在哪个 .yad 分页。

原理（本轮实测）
----------------
`.ycd` 体里有一个 32 字节步长的根表（wnt1_mcs2 在 0x77cb0）：

    { ptr(8) | 0(4) | flags(4) | 0(4) | f32 duration | 0(8) }

`ptr` 指向 clip 结构体，结构体里有：

    +0x08  u32  clip 哈希      ← 在 .yad 的某一页里能命中
    +0x28  f32  时长
    +0x2c  f32  时长 × 2       （同一镜的长版本 / 整段 take）
    +0x30  f32  播放速率（多为 1.0）

于是「clip 时长 ↔ .yad 分页」可以对上，虽然还没连到 clip 名。

输出
    export/story/cutscene/ycd_durations/<pack>.json
    export/story/cutscene/ycd_durations_index.csv

用法
    uv run python tools/extract_ycd_durations.py --pack cuts_wnt1
    uv run python tools/extract_ycd_durations.py --all
"""
import argparse
import csv
import glob
import json
import os
import re
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'story', 'cutscene_all', 'extracted')
OUT = os.path.join(ROOT, 'export', 'story', 'cutscene')
SYS = 0x50000000
STRIDE = 0x20


def body_of(path):
    d = open(path, 'rb').read()
    return d[16:] if d[:4] == b'RSC8' else d


def rd_ptr(b, o):
    if o < 0 or o + 8 > len(b):
        return None
    v = struct.unpack_from('<Q', b, o)[0]
    if SYS <= v < SYS + len(b):
        return v - SYS
    return None


def find_root_table(b, page_durs=None):
    """根表 = 一串 32 字节记录（ptr + flags + f32 时长）。

    一个 .ycd 里可能有多处满足格式，用「时长能否对上 .yad 分页的时长」来选最可信的那处。
    """
    page_durs = page_durs or set()
    best, best_score, best_n = None, -1, 0
    for start in range(0, max(0, len(b) - STRIDE * 8), 0x10):
        n, score = 0, 0
        o = start
        while o + STRIDE <= len(b) and n < 500:
            t = rd_ptr(b, o)
            if t is None or t + 0x34 > len(b):
                break
            d = struct.unpack_from('<f', b, t + 0x28)[0]
            r = struct.unpack_from('<f', b, t + 0x30)[0]
            if not (0.3 < d < 60) or not (0.2 < r < 4.0):
                break
            if any(abs(d - pd) < 0.2 for pd in page_durs):
                score += 1
            n += 1
            o += STRIDE
        if n >= 2 and (score, n) > (best_score, best_n):
            best, best_score, best_n = start, score, n
    return best, best_n


def extract(ycd, pages, page_durs=frozenset()):
    b = body_of(ycd)
    page_durs = set()
    for name, data in pages.items():
        # 分页内动画时长（和 extract 的结构无关，只用「页里最常见的 f32 时长」当参考）
        pass
    start, n = find_root_table(b, page_durs)
    if not start or n < 2:
        return None
    recs = []
    for i in range(n):
        o = start + i * STRIDE
        t = rd_ptr(b, o)
        h = struct.unpack_from('<I', b, t + 8)[0]
        d = struct.unpack_from('<f', b, t + 0x28)[0]
        d2 = struct.unpack_from('<f', b, t + 0x2c)[0]
        rate = struct.unpack_from('<f', b, t + 0x30)[0]
        page = None
        if h:
            pat = struct.pack('<I', h)
            for name, data in pages.items():
                if pat in data:
                    page = name
                    break
        recs.append(dict(i=i, hash='%08x' % h, dur=round(d, 2), dur2=round(d2, 2),
                         rate=round(rate, 2), page=page))
    return dict(table_offset=start, count=n, clips=recs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pack', default=None)
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()
    packs = ([os.path.join(SRC, args.pack)] if args.pack
             else sorted(d for d in glob.glob(os.path.join(SRC, 'cuts_*')) if os.path.isdir(d)))
    outdir = os.path.join(OUT, 'ycd_durations')
    os.makedirs(outdir, exist_ok=True)
    rows = []
    for d in packs:
        pack = os.path.basename(d)
        pages = {}
        page_durs = set()
        for f in glob.glob(os.path.join(d, '*.yad')):
            data = open(f, 'rb').read()
            pages[os.path.basename(f)] = data
            try:
                import ycd_decode as Y
                for a in Y.find_animations(data[16:] if data[:4] == b'RSC8' else data):
                    page_durs.add(round(a[3], 1))
            except Exception:
                pass
        res = {}
        for f in sorted(glob.glob(os.path.join(d, '*.ycd'))):
            cid = os.path.splitext(os.path.basename(f))[0]
            r = extract(f, pages, page_durs)
            if r:
                res[cid] = r
                for c in r['clips']:
                    rows.append(dict(pack=pack, cutscene=cid, i=c['i'], hash=c['hash'],
                                     dur=c['dur'], dur2=c['dur2'], rate=c['rate'],
                                     page=c['page'] or ''))
        json.dump(res, open(os.path.join(outdir, pack + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False)
        tot = sum(len(r['clips']) for r in res.values())
        mapped = sum(1 for cid, r in res.items() for c in r['clips'] if c['page'])
        print('%-16s 过场 %2d  clip 时长 %3d  能落到分页 %3d' % (pack, len(res), tot, mapped))
    if args.all or not args.pack:
        with open(os.path.join(OUT, 'ycd_durations_index.csv'), 'w', encoding='utf-8-sig',
                  newline='') as f:
            w = csv.DictWriter(f, fieldnames=['pack', 'cutscene', 'i', 'hash', 'dur', 'dur2',
                                              'rate', 'page'])
            w.writeheader()
            w.writerows(rows)
        print('\n合计 %d 条 clip 时长；落页 %d 条' % (len(rows), sum(1 for r in rows if r['page'])))


if __name__ == '__main__':
    main()
