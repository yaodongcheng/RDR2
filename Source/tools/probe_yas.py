# -*- coding: utf-8 -*-
"""探针：把 .yas（animation scene）的 PSIN 实例数据按 PMAP 根结构摊开，找「时间 / clip 引用」

.yas 是 PSIN 家族（和 .ymt 同格式）：PMAP 给出根结构布局，PSCH 给出每个结构的字段。
字段名是哈希、目前解不出名字，但**值**是能读的。目标：
  - 找一串单调递增的 float（0~60 秒）→ 镜头时间轴
  - 找一串哈希（0x5xxx/0x8xxx）→ clip 引用
"""
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_pso as P


def read_struct(sec, off, fields, n=24, depth=0, out=None, maxdepth=2):
    """按字段定义读一个结构（只读标量；遇到指针/嵌套就记下来）"""
    if out is None:
        out = []
    for f in fields:
        fo = off + f['off']
        if fo + 4 > len(sec):
            continue
        v = struct.unpack_from('<i', sec, fo)[0]
        u = struct.unpack_from('<I', sec, fo)[0]
        fl = struct.unpack_from('<f', sec, fo)[0]
        out.append((depth, f['off'], f['type'], f['name'], u, fl))
    return out


def main(path):
    info, sections = P.parse(path)
    psin = sections.get('PSIN')
    psig = sections.get('PSIG')
    print('sections:', {k: len(v) for k, v in sections.items()})
    pmap = info.get('pmap') or {}
    print('PMAP root=%s entries=%s' % (pmap.get('root'), pmap.get('count')))
    entries = pmap.get('entries') or []
    structs = {s['name']: s for s in info.get('psch') or [] if s['type'] == 'struct'}
    print('structs:', len(structs))
    for e in entries[:8]:
        st = structs.get(e['name'])
        name = 'struct_%08x' % e['name']
        nf = len(st['fields']) if st else -1
        print('  entry off=%#x len=%s fields=%d' % (e['offset'], e['length'], nf))
    if not entries or psin is None:
        return
    # 根结构的字段值
    root = entries[pmap['root']] if pmap['root'] < len(entries) else entries[0]
    st = structs.get(root['name'])
    print('\n=== 根结构 %08x @ %#x  字段 %d ===' % (root['name'], root['offset'],
                                                len(st['fields']) if st else 0))
    if st:
        vals = read_struct(psin, root['offset'], st['fields'])
        for depth, off, typ, name, u, fl in vals[:40]:
            tag = ''
            if 0 < fl < 120 and abs(fl - round(fl, 3)) < 1e-6:
                tag = 'time?'
            print('  +%#05x type=%d %08x  u=%#010x  f=%12.3f %s' % (off, typ, name, u, fl, tag))


if __name__ == '__main__':
    main(sys.argv[1])
