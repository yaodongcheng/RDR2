#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把相机解析结果汇总成一页「过场相机俯视图」查看器。

优先读「跨页拼接」结果 camera_stitched/<pack>/<cutscene>.json（轨迹已接成一条）；
没有时回落 camera/<pack>.json（按页解出的碎片）。

产物：export/story/cutscene/camera.html
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, 'export', 'story', 'cutscene')
CAM = os.path.join(OUT_DIR, 'camera')
STITCH = os.path.join(OUT_DIR, 'camera_stitched')
OUT = os.path.join(OUT_DIR, 'camera.html')
TPL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cutscene_camera_template.html')


def load_stitched():
    items = []
    for f in sorted(glob.glob(os.path.join(STITCH, '*', '*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        segs = []
        for i, s in enumerate(d.get('segments', [])):
            pos = s.get('pos0')
            if pos is None:
                continue
            segs.append(dict(i=i, t0=s['t0'], dur=s['dur'],
                             pos=[round(pos[0], 2), round(pos[1], 2)],
                             quat=s.get('quat0'),
                             static=s['move'] < 0.05, move=s['move'], page=s.get('page')))
        if not d.get('duration') or not segs:
            continue
        items.append(dict(cutscene=d['cutscene'], pack=d['pack'], duration=d['duration'],
                          bones=None, block=None, segments=segs,
                          pages=d.get('pages'), chains=d.get('chains')))
    return items


def load_fragments():
    items = []
    for f in sorted(glob.glob(os.path.join(CAM, 'cuts_*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        for c in d.get('cutscenes', []):
            if not c.get('duration') or not c.get('segments'):
                continue
            items.append(dict(
                cutscene=c['cutscene'], pack=d['pack'], duration=c['duration'],
                bones=c['bones'], block=c.get('block'),
                segments=[dict(i=s['i'], t0=s['t0'], dur=s['dur'], pos=s['pos'],
                               quat=s['quat'], static=s['static'], move=s['move'])
                          for s in c['segments']],
            ))
    return items


def main():
    items = load_stitched() or load_fragments()
    items.sort(key=lambda x: (x['pack'], x['cutscene']))
    tpl = open(TPL, encoding='utf-8').read()
    payload = json.dumps(dict(cutscenes=items), ensure_ascii=False).replace('</', '<\\/')
    open(OUT, 'w', encoding='utf-8').write(tpl.replace('/*__DATA__*/', payload))
    n_seg = sum(len(x['segments']) for x in items)
    print('写入 %s：%d 个过场 / %d 段  (%.1f KB)' % (
        OUT, len(items), n_seg, os.path.getsize(OUT) / 1024))


if __name__ == '__main__':
    main()
