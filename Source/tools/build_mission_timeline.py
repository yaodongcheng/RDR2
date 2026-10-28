#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""任务级过场时间轴：脚本里的播放顺序 × 资产里的过场时长

数据来源
--------
1. **播放顺序**：任务脚本（`raw/script_full/1491.50/*.c`）里的过场表调用
        func_NNN(uParam0, idA, idB, n1, n2, n3, n4, n5, "WNT1_MCS2", 2, -1);
   —— 参数里的字符串就是过场名，按出现顺序即该任务的过场播放顺序
2. **过场时长 / 镜头数**：`structure/<包>.json`（来自 cuts_*.rpf）

输出
    export/story/cutscene/mission_timeline.json
    export/story/cutscene/mission_timeline.csv
"""
import csv
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'raw', 'script_full', '1491.50')
CS = os.path.join(ROOT, 'export', 'story', 'cutscene')

PAT = re.compile(r'(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*'
                 r'"([A-Z0-9_]{3,40})"\s*,\s*(-?\d+)\s*,\s*(-?\d+)')


def script_orders():
    out = {}
    for f in glob.glob(os.path.join(SCRIPTS, '*.c')):
        txt = open(f, encoding='utf-8', errors='ignore').read()
        hits = PAT.findall(txt)
        if not hits:
            continue
        seq = []
        for h in hits:
            item = dict(name=h[5], marks=[int(x) for x in h[:5]], flag=int(h[6]))
            if not seq or seq[-1]['name'] != item['name']:
                seq.append(item)
        out[os.path.basename(f)[:-2]] = seq
    return out


def alias_map():
    """`.ycd` 文件名 → clip 名里真实过场 ID（两者常常不一致）"""
    import sys as _s
    _s.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cutscene_structure import ids_from_clips, CLIP_RX
    out = {}
    for f in glob.glob(os.path.join(ROOT, 'work', 'story', 'cutscene_all', 'extracted',
                                    'cuts_*', '*.ycd')):
        data = open(f, 'rb').read()
        ids = ids_from_clips([m.group(1).decode('latin1') for m in CLIP_RX.finditer(data)])
        base = os.path.splitext(os.path.basename(f))[0].upper()
        if ids:
            out[base] = ids[0]
    return out


def structures():
    d = {}
    for f in glob.glob(os.path.join(CS, 'structure', 'cuts_*.json')):
        j = json.load(open(f, encoding='utf-8'))
        for s in j.get('scenes', []):
            d[s['cutscene'].upper()] = dict(cutscene=s['cutscene'], pack=s['pack'],
                                            mission=s['mission'],
                                            duration=s.get('duration_s'),
                                            shots=s['n_shots'], clips=s['clips'],
                                            capped=bool(s.get('duration_capped')))
    return d


def main():
    orders = script_orders()
    st = structures()
    alias = alias_map()
    out, rows = {}, []
    for mission, seq in sorted(orders.items()):
        items, t = [], 0.0
        for i, it in enumerate(seq):
            key = it['name'].upper()
            s = (st.get(key) or st.get(alias.get(key, '').upper())
                 or st.get(key.replace('_MCS_', '_MCS')))
            dur = (s or {}).get('duration') or 0
            items.append(dict(order=i, name=it['name'], duration=dur,
                              shots=(s or {}).get('shots'), clips=(s or {}).get('clips'),
                              in_assets=bool(s), start=round(t, 2),
                              marks=it['marks'], flag=it['flag']))
            t += dur
        out[mission] = dict(script=mission, cutscenes=items,
                            total=round(t, 2), n=len(items),
                            matched=sum(1 for x in items if x['in_assets']))
        for x in items:
            rows.append(dict(script=mission, order=x['order'], cutscene=x['name'],
                             start=x['start'], duration=x['duration'], shots=x['shots'],
                             in_assets='Y' if x['in_assets'] else ''))
    json.dump(out, open(os.path.join(CS, 'mission_timeline.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    with open(os.path.join(CS, 'mission_timeline.csv'), 'w', encoding='utf-8-sig',
              newline='') as f:
        w = csv.DictWriter(f, fieldnames=['script', 'order', 'cutscene', 'start',
                                          'duration', 'shots', 'in_assets'])
        w.writeheader()
        w.writerows(rows)
    n_match = sum(1 for r in rows if r['in_assets'])
    print('脚本 %d 个 / 过场引用 %d 条，其中能在资产里对上 %d 条 (%.0f%%)' % (
        len(out), len(rows), n_match, 100 * n_match / max(1, len(rows))))
    print('示例 winter1:', [(x['name'], x['duration']) for x in out.get('winter1', {}).get('cutscenes', [])][:6])


if __name__ == '__main__':
    main()
