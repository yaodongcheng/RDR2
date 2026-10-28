#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""RDR2 `.yldb` 的 key(joaat) -> 字符串 查询。

实测结构（2026-10-19，global.yldb）：

  hash 表项（在文件里搜 4 字节 joaat 哈希即可命中）：
      +0x00  u32 hash
      +0x04  pad
      +0x08  u32 node_ptr      （虚拟地址，基址 0x50000000）
      +0x0c  pad
  node（文件偏移 n = node_ptr - 0x50000000）：
      +0x20  u32 str_ptr      （字符串区起点，内联时 = node+0x20）
      +0x28  u32 len          （UTF-8 字节数，含结尾 \\0）
  字符串：**数据在 str_ptr + 0x10**，读 len 字节。
      （内联时 str_ptr = node+0x20 ⇒ 数据在 node+0x30，两种情形同一条公式。）

用法：
  uv run python tools/yldb_keys.py --yldb work/story/lang/chinesesimp/global.yldb WNT1 WNT1_DESC
"""
import argparse
import os
import struct
import sys

BASE = 0x50000000


def joaat(name: str) -> int:
    h = 0
    for ch in name.lower():
        h = (h + ord(ch)) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h


class Yldb:
    def __init__(self, path):
        self.data = open(path, 'rb').read()

    def _cstr(self, off, limit=4096):
        s = off
        end = self.data.find(b'\x00', s)
        if end < 0 or end - s > limit:
            end = min(s + limit, len(self.data))
        return self.data[s:end].decode('utf-8', 'replace')

    def get(self, key, default=None):
        h = joaat(key)
        packed = struct.pack('<I', h)
        off = self.data.find(packed)
        if off < 0:
            return default
        node = struct.unpack('<I', self.data[off + 8:off + 12])[0]
        if not (BASE <= node < BASE + len(self.data)):
            return default
        n = node - BASE
        if n + 0x30 > len(self.data):
            return default
        sp = struct.unpack('<I', self.data[n + 0x20:n + 0x24])[0]
        ln = struct.unpack('<I', self.data[n + 0x28:n + 0x2c])[0]
        if not (BASE <= sp < BASE + len(self.data)):
            return default
        # 字符串数据固定在 str_ptr + 0x10（内联时 str_ptr = node+0x20 → node+0x30）
        s = sp - BASE + 0x10
        raw = self.data[s:s + max(ln, 1)].lstrip(b'\x00')
        return raw.rstrip(b'\x00').decode('utf-8', 'replace')

    def get_first(self, keys, default=None):
        for k in keys:
            v = self.get(k)
            if v:
                return v
        return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--yldb', required=True)
    ap.add_argument('keys', nargs='*')
    a = ap.parse_args()
    y = Yldb(a.yldb)
    for k in a.keys:
        print('%s\t%s' % (k, y.get(k, '<miss>')))


if __name__ == '__main__':
    main()
