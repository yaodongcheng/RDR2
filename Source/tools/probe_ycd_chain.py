# -*- coding: utf-8 -*-
"""探针：从 .ycd 字典条目出发，递归展开指针链，找「帧数 / 时长 / .yad 页引用」

用法
    uv run python tools/probe_ycd_chain.py <ycd> <clip名> [--depth 3]

输出每一层的字段；对「像帧数」「像时长」「像页号」的值单独标出来。
"""
import argparse
import re
import struct
import sys

SYS = 0x50000000


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h


def load(path):
    d = open(path, 'rb').read()
    return d[16:] if d[:4] == b'RSC8' else d


def ptr(body, off):
    if off < 0 or off + 8 > len(body):
        return None
    v = struct.unpack_from('<Q', body, off)[0]
    if SYS <= v < SYS + len(body):
        return v - SYS
    return None


def show(body, off, level, maxlevel, seen, tag=''):
    ind = '  ' * level
    print('%s@%#07x %s' % (ind, off, tag))
    for i in range(0, 0x40, 4):
        o = off + i
        if o + 4 > len(body):
            break
        u = struct.unpack_from('<I', body, o)[0]
        f = struct.unpack_from('<f', body, o)[0]
        mark = ''
        if 5 <= u <= 3000 and abs(f - u / 30.0) < 0.4:
            mark = '  <== 像 frames/dur'
        elif 0.3 <= f <= 60 and abs(f - round(f, 2)) < 1e-3:
            mark += '  <== 像秒'
        elif SYS <= u < SYS + len(body):
            mark += '  -> ptr %#x' % (u - SYS)
        print('%s  +%#04x u=%10d f=%9.3f%s' % (ind, i, u, f, mark))
    if level >= maxlevel:
        return
    for i in range(0, 0x40, 8):
        p = ptr(body, off + i)
        if p is not None and p not in seen:
            seen.add(p)
            show(body, p, level + 1, maxlevel, seen, tag='(ptr +%#x)' % i)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ycd')
    ap.add_argument('clip')
    ap.add_argument('--depth', type=int, default=2)
    args = ap.parse_args()
    body = load(args.ycd)
    h = joaat(args.clip)
    pat = struct.pack('<I', h)
    hits = [m.start() for m in re.finditer(re.escape(pat), body)]
    print('clip=%s  joaat=%#x  命中 %d 处' % (args.clip, h, len(hits)))
    for o in hits[:2]:
        print('\n=== 条目 @%#x ===' % o)
        seen = {o}
        for i in range(-0x10, 0x18, 8):
            p = ptr(body, o + i)
            if p is not None:
                show(body, p, 1, args.depth, seen, tag='(entry ptr %+d)' % i)


if __name__ == '__main__':
    main()
