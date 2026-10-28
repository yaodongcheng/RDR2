# -*- coding: utf-8 -*-
"""探针：不假设表偏移，枚举 .ycd 里所有 32 字节记录表，建立 clip 哈希 → 时长 的全量索引

用途：之前只看固定偏移（wnt1_mcs2@0x77cb0），导致 wnt1_mcs1/wnt1_ext 扫不全。
这里把所有候选表都收进来，再按 .yad 分页求「每页基础时长」。
"""
import glob
import os
import re
import struct
import sys

SYS = 0x50000000
STRIDE = 0x20


def body(path):
    d = open(path, 'rb').read()
    return d[16:] if d[:4] == b'RSC8' else d


def rd_ptr(b, o):
    if o < 0 or o + 8 > len(b):
        return None
    v = struct.unpack_from('<Q', b, o)[0]
    return v - SYS if SYS <= v < SYS + len(b) else None


def collect_hashes(b):
    """扫所有起点，收集 (hash, dur)"""
    out = {}
    N = len(b)
    for st in range(0, N - STRIDE, 4):
        t = rd_ptr(b, st)
        if t is None or t + 0x34 > N:
            continue
        rate = struct.unpack_from('<f', b, t + 0x30)[0]
        if not (0.2 < rate < 4.0):
            continue
        h = struct.unpack_from('<I', b, t + 8)[0]
        d = struct.unpack_from('<f', b, t + 0x28)[0]
        d2 = struct.unpack_from('<f', b, t + 0x2c)[0]
        if not h or not (0.3 < d < 60):
            continue
        # 同一 hash 在多个表里重复出现时，保留最小/最大时长
        if h in out:
            lo, hi = out[h]
            out[h] = (min(lo, d), max(hi, max(d, d2)))
        else:
            out[h] = (d, max(d, d2))
    return out


def page_report(pack_dir, cid):
    ycd = os.path.join(pack_dir, cid + '.ycd')
    if not os.path.exists(ycd):
        return None
    b = body(ycd)
    hs = collect_hashes(b)
    pages = {}
    for f in glob.glob(os.path.join(pack_dir, cid + '-*.yad')):
        data = open(f, 'rb').read()
        ds = sorted({round(lo, 2) for h, (lo, hi) in hs.items() if struct.pack('<I', h) in data})
        pages[int(re.search(r'-(\d+)\.yad$', f).group(1))] = ds
    return hs, pages


def main():
    base = 'work/story/cutscene_all/extracted'
    targets = [('cuts_wnt1', 'wnt1_mcs2'), ('cuts_wnt1', 'wnt1_mcs1'),
               ('cuts_wnt1', 'wnt1_ext'), ('cuts_bou1', 'bou1_mcs1')]
    for pack, cid in targets:
        r = page_report(os.path.join(base, pack), cid)
        if not r:
            print(cid, '缺文件')
            continue
        hs, pages = r
        print('== %s  哈希条目 %d  页数 %d' % (cid, len(hs), len(pages)))
        for k in sorted(pages):
            ds = pages[k]
            print('   页%-2d 时长集合 %s' % (k, ds[:8] if ds else '（无）'))


if __name__ == '__main__':
    main()
