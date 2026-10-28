# -*- coding: utf-8 -*-
"""用**游戏自己的本地化文本**做中英对照 —— 不再手翻地名/人名。

数据源：`data_0.rpf → data/lang/{american,chinesesimp}_rel.rpf → global.yldb`
（已抽到 `raw/lang/en/global.yldb` 与 `raw/lang/zh/global.yldb`；没有就用下面的命令重抽）

    cd tools/rdr2rpf/bin/Release/net9.0
    ./rdr2rpf.exe extract "H:/EPICGAMES/RedDeadRedemption2/data_0.rpf" <out> "chinesesimp_rel"
    ./rdr2rpf.exe extract "H:/EPICGAMES/RedDeadRedemption2/data_0.rpf" <out> "american_rel"

`.yldb` 结构（与 `yldb_keys.py` 同一套）：
    哈希表项 16 B：[u32 hash][pad][u32 node_ptr][pad]，node = 0x50000000 + 文件内偏移
    字符串   ：node+0x20 = str_ptr，node+0x28 = 字节长度；数据在 str_ptr - 0x50000000 + 0x10
两种语言用**同一个 hash**，所以可以直接配对，不需要知道 key 名。

用法：
  uv run python tools/official_name_map.py --lookup "Horseshoe Overlook" "Fort Mercer"
  uv run python tools/official_name_map.py --csv deliverable/handoff/settlements_world_v2.csv \
      --col name_en --out deliverable/handoff/official_names_settlements.csv
"""
import os
import csv
import sys
import struct
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EN = os.path.join(ROOT, 'raw/lang/en/global.yldb')
ZH = os.path.join(ROOT, 'raw/lang/zh/global.yldb')
BASE = 0x50000000


def scan(path):
    """→ {hash: string}（同一 hash 只保留第一条）"""
    d = open(path, 'rb').read()
    n = len(d)
    out = {}
    for off in range(0, n - 16, 4):
        h, pad1, node, pad2 = struct.unpack_from('<IIII', d, off)
        if pad1 or pad2 or not (BASE <= node < BASE + n):
            continue
        o = node - BASE
        if o + 0x30 > n:
            continue
        sp = struct.unpack_from('<I', d, o + 0x20)[0]
        ln = struct.unpack_from('<I', d, o + 0x28)[0]
        if not (BASE <= sp < BASE + n) or ln == 0 or ln > 4000:
            continue
        s = sp - BASE + 0x10
        if s + ln > n:
            continue
        raw = d[s:s + ln].lstrip(b'\x00').rstrip(b'\x00')
        try:
            t = raw.decode('utf-8')
        except UnicodeDecodeError:
            continue
        if t.strip():
            out.setdefault(h, t)
    return out


class NameMap:
    def __init__(self):
        self.en = scan(EN)
        self.zh = scan(ZH)
        self.by_lower = {}
        for h, t in self.en.items():
            self.by_lower.setdefault(t.strip().lower(), h)

    def zh_of(self, en_name):
        h = self.by_lower.get((en_name or '').strip().lower())
        return self.zh.get(h, '') if h else ''

    def pair(self, en_name):
        h = self.by_lower.get((en_name or '').strip().lower())
        if not h:
            return ('', '')
        return (self.en.get(h, ''), self.zh.get(h, ''))

    def search(self, kw, limit=20):
        kw = kw.lower()
        out = []
        for h, t in self.en.items():
            if kw in t.lower() and len(t) < 90:
                out.append((t, self.zh.get(h, '')))
                if len(out) >= limit:
                    break
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lookup', nargs='*', default=[])
    ap.add_argument('--search', default='')
    ap.add_argument('--csv', default='')
    ap.add_argument('--col', default='name_en')
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    nm = NameMap()
    if a.search:
        for en, zh in nm.search(a.search):
            print('%-44s | %s' % (en, zh))
    if a.lookup:
        for en in a.lookup:
            e, z = nm.pair(en)
            print('%-44s | %s' % (en, z or '<游戏文本里没有>'))
    if a.csv:
        rows = list(csv.DictReader(open(a.csv, encoding='utf-8-sig')))
        out = []
        for r in rows:
            en = r.get(a.col, '')
            e, z = nm.pair(en)
            out.append(dict(code=r.get('code', ''), en=en, zh_official=z,
                            status='官方' if z else '无官方文本'))
        if a.out:
            with open(a.out, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.DictWriter(f, fieldnames=['code', 'en', 'zh_official', 'status'])
                w.writeheader()
                w.writerows(out)
            print('->', a.out)
        for o in out:
            print('%-8s %-30s %s' % (o['code'], o['en'], o['zh_official'] or '<无>'))


if __name__ == '__main__':
    main()
