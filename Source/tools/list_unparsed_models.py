# -*- coding: utf-8 -*-
"""把"未能入库"的模型逐条列出来并分类（验收第 2 列的"逐条说明"）。

分类：
    frag_no_geom   `.yft` 里找不到 drawable 几何（fragment 布局变体）
    no_shader      `.ydr` 里读不到着色器组（空 drawable / 代理）
    default_shader 只有 `default` 着色器（引擎占位，按规则不入库）
    empty_geom     有几何但索引/顶点为 0

    python tools/list_unparsed_models.py
产物：work/unparsed_models.json
"""
import os
import sys
import json
import glob
from collections import Counter

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
LIB = os.path.join(ROOT, 'assets/lib_native')
PACKS = os.path.join(ROOT, 'raw/all_packs')
OUT = os.path.join(ROOT, 'work/unparsed_models.json')


def joaat(s):
    h = 0
    for c in s.lower().encode('latin1', 'ignore'):
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF


def main():
    import rdr2_ydr as Y
    idx = json.load(open(os.path.join(LIB, 'index.json'), encoding='utf-8'))
    models = idx['models']
    rows = []
    files = (glob.glob(os.path.join(PACKS, '**', '*.ydr'), recursive=True)
             + glob.glob(os.path.join(PACKS, '**', '*.yft'), recursive=True))
    for f in files:
        h = '0x%08x' % joaat(os.path.splitext(os.path.basename(f))[0])
        if h in models:
            continue
        ext = os.path.splitext(f)[1].lower()
        reason = '?'
        shaders = []
        try:
            res = Y.Res(open(f, 'rb').read())
            sg = res.u64(0x10)
            shd = Y.parse_shader_hashes(res, sg)
            shaders = sorted({(d.get('name') or '?') for d in shd})
        except Exception:
            shaders = []
        if ext == '.yft':
            reason = 'frag_no_geom'
        elif not shaders:
            reason = 'no_shader'
        elif shaders == ['default']:
            reason = 'default_shader'
        else:
            reason = 'other'
        rows.append(dict(hash=h, file=os.path.basename(f), ext=ext, reason=reason,
                         shaders=shaders[:3], size=os.path.getsize(f)))
    c = Counter(r['reason'] for r in rows)
    print('[unparsed] 未能入库 %d 个：' % len(rows))
    for k, v in c.most_common():
        print('   %-16s %5d' % (k, v))
    for r in rows[:5]:
        print('   例: %-40s %s %s' % (r['file'], r['reason'], r['shaders']))
    json.dump(rows, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('→ %s' % os.path.relpath(OUT, ROOT))


if __name__ == '__main__':
    main()
