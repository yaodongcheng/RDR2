#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""逐镜时长（估算）——把 `.yad` 分页时长对到镜头上

原理
----
1. `.ycd` 里扫描 32 字节记录表，收集 clip 哈希 → 时长（同一 hash 取最小值为「基础时长」）
2. 每个 `.yad` 分页里出现的哈希集合 → 该页的时长集合 → 取最小值为该页时长
3. 一页 = 一个候选镜头素材；时长相同的多页 = 同一镜头的多个 take

判定（保守）
------------
    去重后的「非 16 s 封顶」页时长个数 == 镜头数  → 判定为可信（ok）
    否则                                          → 只给「候选时长集合」，不硬配到镜号

输出
    export/story/cutscene/shot_durations.json
    export/story/cutscene/shot_durations.csv

用法
    uv run python tools/extract_shot_durations.py --pack cuts_wnt1
    uv run python tools/extract_shot_durations.py --all
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
CAP = 16.03          # 单页上限（秒）


def body(path):
    d = open(path, 'rb').read()
    return d[16:] if d[:4] == b'RSC8' else d


def clip_durations(b):
    """扫描所有 32 字节记录 → {hash: min_dur}"""
    out = {}
    N = len(b)
    for st in range(0, N - STRIDE, 0x10):
        v = struct.unpack_from('<Q', b, st)[0]
        if not (SYS <= v < SYS + N):
            continue
        t = v - SYS
        if t + 0x34 > N:
            continue
        rate = struct.unpack_from('<f', b, t + 0x30)[0]
        if not (0.2 < rate < 4.0):
            continue
        h = struct.unpack_from('<I', b, t + 8)[0]
        d = struct.unpack_from('<f', b, t + 0x28)[0]
        if h and 0.3 < d < 60:
            if h not in out or d < out[h]:
                out[h] = d
    return out


def yad_uniform_dur(data):
    """分页内所有动画的众数时长（没有 clip 哈希时的兜底）"""
    try:
        import ycd_decode as Y
        b = data[16:] if data[:4] == b'RSC8' else data
        ds = [round(a[3], 2) for a in Y.find_animations(b)]
        if not ds:
            return None
        from collections import Counter
        return Counter(ds).most_common(1)[0][0]
    except Exception:
        return None


def page_durations(ycd_path, page_paths):
    b = body(ycd_path)
    cd = clip_durations(b)
    pages = []
    for f in page_paths:
        data = open(f, 'rb').read()
        ds = [d for h, d in cd.items() if struct.pack('<I', h) in data]
        src = 'clip'
        dur = round(min(ds), 2) if ds else None
        if dur is None:
            dur = yad_uniform_dur(data)
            src = 'yad'
        pages.append(dict(page=int(re.search(r'-(\d+)\.yad$', f).group(1)),
                          dur=dur, src=src,
                          variants=sorted({round(d, 2) for d in ds})[:6]))
    pages.sort(key=lambda x: x['page'])
    return pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pack', default=None)
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()

    # 结构表：镜头数
    shots = {}
    for f in glob.glob(os.path.join(OUT, 'structure', 'cuts_*.json')):
        d = json.load(open(f, encoding='utf-8'))
        for s in d.get('scenes', []):
            shots[s['cutscene']] = s['n_shots']

    packs = ([os.path.join(SRC, args.pack)] if args.pack
             else sorted(d for d in glob.glob(os.path.join(SRC, 'cuts_*')) if os.path.isdir(d)))
    res, rows = {}, []
    for pd in packs:
        pack = os.path.basename(pd)
        for f in sorted(glob.glob(os.path.join(pd, '*.ycd'))):
            prefix = os.path.splitext(os.path.basename(f))[0]
            # 过场 ID 以 clip 名为准（.ycd 文件名可能不一致）
            try:
                import cutscene_structure as CS2
                _names = [m.group(1).decode('latin1') for m in CS2.CLIP_RX.finditer(open(f, 'rb').read())]
                _ids = CS2.ids_from_clips(_names)
            except Exception:
                _ids = []
            cid = _ids[0] if _ids else prefix
            pages = page_durations(f, glob.glob(os.path.join(pd, prefix + '-*.yad')))
            if not pages:
                continue
            durs = [p['dur'] for p in pages if p['dur']]
            noncap = sorted({d for d in durs if abs(d - CAP) > 0.15})
            n_shots = shots.get(cid)
            ok = (n_shots is not None and len(noncap) == n_shots)
            res[cid] = dict(pack=pack, shots=n_shots, ok=ok,
                            page_durs=[p['dur'] for p in pages],
                            distinct=noncap, n_pages=len(pages))
            rows.append(dict(pack=pack, cutscene=cid, shots=n_shots, pages=len(pages),
                             distinct=len(noncap), ok='Y' if ok else '',
                             shot_durs='/'.join(str(x) for x in noncap)))
    json.dump(res, open(os.path.join(OUT, 'shot_durations.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, 'shot_durations.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['pack', 'cutscene', 'shots', 'pages', 'distinct', 'ok',
                                          'shot_durs'])
        w.writeheader()
        w.writerows(rows)
    ok = sum(1 for r in rows if r['ok'] == 'Y')
    print('过场 %d；「去封顶后时长个数 == 镜头数」判定可信 %d 个 (%.0f%%)' % (
        len(rows), ok, 100 * ok / max(1, len(rows))))
    print('→', os.path.join(OUT, 'shot_durations.csv'))


if __name__ == '__main__':
    main()
