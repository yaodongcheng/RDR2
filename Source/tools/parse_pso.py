#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PSO / PSIN 解析器（按 CodeWalker 的 Pso.cs 结构实现，RDR2 的 .ymt 同族）。

节（全部大端）：
    PSIN  data        ：实例数据
    PMAP  data map    ：{RootId, Count, Entries[{NameHash, Offset, Unk, Length}]}
    PSCH  schema      ：{Count, Index[{NameHash, Offset}], 每个 Offset 处是 Structure/Enum}
    STDN/STRS/STRE/PSIG/CHKS：字符串/签名/校验（本工具只做透传）

Structure 读取：
    u32 packed = (type<<24) | (unk<<16) | entriesCount
    i32 structLength
    u32 unk
    entries[entriesCount] = {u32 nameHash, u8 type, u8 unk, u16 dataOffset, u32 refKey}

用法：
  uv run python tools/parse_pso.py <file.ymt> [--dump] [--json out.json]
"""
import argparse
import json
import struct
import sys

SECTIONS = {0x5053494E: 'PSIN', 0x504D4150: 'PMAP', 0x50534348: 'PSCH',
            0x53545246: 'STRF', 0x53545253: 'STRS', 0x53545245: 'STRE',
            0x5354444E: 'STDN', 0x50534947: 'PSIG', 0x43484B53: 'CHKS'}

DTYPE = {0x00: 'Bool', 0x01: 'SByte', 0x02: 'UByte', 0x03: 'SShort', 0x04: 'UShort',
         0x05: 'SInt', 0x06: 'UInt', 0x07: 'Float', 0x08: 'Float2', 0x09: 'Float3',
         0x0a: 'Float4', 0x0b: 'String', 0x0c: 'Structure', 0x0d: 'Array',
         0x0e: 'Enum', 0x0f: 'Flags', 0x10: 'Map', 0x14: 'Float3a', 0x15: 'Float4a',
         0x1e: 'HFloat', 0x20: 'Long'}


class R:
    def __init__(self, b, pos=0):
        self.b = b
        self.p = pos

    def u32(self):
        v = struct.unpack_from('>I', self.b, self.p)[0]; self.p += 4; return v

    def i32(self):
        v = struct.unpack_from('>i', self.b, self.p)[0]; self.p += 4; return v

    def u16(self):
        v = struct.unpack_from('>H', self.b, self.p)[0]; self.p += 2; return v

    def i16(self):
        v = struct.unpack_from('>h', self.b, self.p)[0]; self.p += 2; return v

    def u8(self):
        v = self.b[self.p]; self.p += 1; return v


def parse(path):
    data = open(path, 'rb').read()
    sections = {}
    p = 0
    while p + 8 <= len(data):
        tag = struct.unpack_from('>I', data, p)[0]
        ln = struct.unpack_from('>i', data, p + 4)[0]
        name = SECTIONS.get(tag, hex(tag))
        if ln < 8 or p + ln > len(data):
            break
        sections[name] = data[p:p + ln]
        p += ln

    out = {'sections': {k: len(v) for k, v in sections.items()}}

    if 'PMAP' in sections:
        r = R(sections['PMAP'], 8)
        root = r.i32()
        cnt = r.i16()
        unk = r.u16()
        if cnt <= 0:
            cnt = r.i16(); r.i16(); r.i16(); r.i16()
        entries = []
        for _ in range(cnt):
            entries.append({'name': r.u32(), 'offset': r.i32(),
                            'unk': r.i32(), 'length': r.i32()})
        out['pmap'] = {'root': root, 'count': cnt, 'entries': entries}

    if 'PSCH' in sections:
        r = R(sections['PSCH'], 8)
        cnt = r.u32()
        idx = [{'name': r.u32(), 'offset': r.i32()} for _ in range(cnt)]
        structs = []
        for it in idx:
            rr = R(sections['PSCH'], it['offset'])
            packed = rr.u32()
            typ = (packed >> 24) & 0xFF
            ecnt = packed & 0xFFFF
            unk = (packed >> 16) & 0xFF
            if typ == 0:
                slen = rr.i32()
                rr.u32()
                ents = []
                for _ in range(ecnt):
                    ents.append({'name': rr.u32(), 'type': rr.u8(),
                                 'unk': rr.u8(), 'off': rr.u16(), 'ref': rr.u32()})
                structs.append({'name': it['name'], 'type': 'struct',
                                'len': slen, 'fields': ents})
            else:
                ents = []
                for _ in range(ecnt):
                    ents.append({'name': rr.u32(), 'key': rr.i32()})
                structs.append({'name': it['name'], 'type': 'enum', 'entries': ents})
        out['psch'] = structs

    return out, sections


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--json')
    ap.add_argument('--dump', action='store_true')
    args = ap.parse_args()
    info, sections = parse(args.file)
    print('sections:', info['sections'])
    if 'pmap' in info:
        print('PMAP root', info['pmap']['root'], 'entries', info['pmap']['count'])
    if 'psch' in info:
        print('PSCH structures', len(info['psch']))
        if args.dump:
            for s in info['psch'][:12]:
                print(f"  {s['name']:08x} {s['type']} len={s.get('len')} fields={len(s.get('fields',[]))}")
                for f in s.get('fields', [])[:14]:
                    print(f"      {f['name']:08x} {DTYPE.get(f['type'], f['type'])} off={f['off']} ref={f['ref']:08x}")
    if args.json:
        json.dump(info, open(args.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('->', args.json)


if __name__ == '__main__':
    main()
