#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""批量分镜构图：470 个过场 × 每个相机段一张俯视构图，做成可翻阅的分镜集。

数据
    camera_stitched/<包>/<过场>.json   相机段（pos0 + quat0 + dur + t0）
    scene_cards.json                   每个过场的分镜槽（出场角色）

画法（前端 canvas 实时画，避免把 2039 张图预渲染进 HTML）
    相机 = 金色圆点 + 朝向线；视锥 = 半透明扇形；
    角色 = 按台词顺序在镜头前方扇形排开（**启发式摆放，不是真实站位**）

产物
    export/story/cutscene/storyboard_all.html
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CS = os.path.join(ROOT, 'export', 'story', 'cutscene')
OUT = os.path.join(CS, 'storyboard_all.html')


def main():
    cards = {}
    p = os.path.join(CS, 'scene_cards.json')
    if os.path.exists(p):
        for c in json.load(open(p, encoding='utf-8')):
            cards.setdefault(c['cutscene'].lower(), c)

    # 兜底：没有场次卡的过场，直接用结构表里的分镜槽（含演员）
    struct = {}
    for f in glob.glob(os.path.join(CS, 'structure', 'cuts_*.json')):
        d = json.load(open(f, encoding='utf-8'))
        for sc in d.get('scenes', []):
            struct[sc['cutscene'].lower()] = sc

    items = []
    for f in sorted(glob.glob(os.path.join(CS, 'camera_stitched', '*', '*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        segs = [s for s in (d.get('segments') or []) if s.get('pos0')]
        if not segs:
            continue
        card = cards.get(d['cutscene'].lower()) or {}
        shots = {s['shot']: s for s in (card.get('shots') or [])}
        if not shots:
            sc = struct.get(d['cutscene'].lower()) or {}
            shots = {s['shot']: dict(shot=s['shot'], camera=s.get('camera'),
                                     actors=[a for a in s['actors'] if a.startswith(('cs_', 'player_'))],
                                     props=[a for a in s['actors'] if a.startswith(('p_', 's_', 'w_'))])
                     for s in (sc.get('shots') or [])}
        items.append(dict(
            cutscene=d['cutscene'], pack=d['pack'], duration=d.get('duration'),
            script=card.get('script'), cast=card.get('cast') or [],
            lines=len(card.get('lines') or []),
            segments=[dict(t0=s['t0'], dur=s['dur'], pos=s['pos0'], quat=s.get('quat0'),
                           actors=(shots.get(i + 1) or {}).get('actors') or [],
                           props=((shots.get(i + 1) or {}).get('props') or [])[:5])
                      for i, s in enumerate(segs)],
        ))
    items.sort(key=lambda x: (x['script'] or '', x['cutscene']))
    payload = json.dumps(items, ensure_ascii=False).replace('</', '<\\/')
    tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'storyboard_all_template.html')
    open(OUT, 'w', encoding='utf-8').write(open(tpl, encoding='utf-8').read().replace('/*__DATA__*/', payload))
    print('写入 %s：%d 个过场 / %d 段 (%.1f KB)' % (
        OUT, len(items), sum(len(x['segments']) for x in items),
        os.path.getsize(OUT) / 1024))


if __name__ == '__main__':
    main()
