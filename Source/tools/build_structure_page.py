#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""过场结构浏览器：653 个过场 → 每个过场的 (part,take,shot) 分镜清单与出场演员。

数据来源
    export/story/cutscene/structure/<pack>.json   （clip 名拆出来的结构）
    export/story/cutscene/camera_stitched/...     （相机段，有就带上）

产物
    export/story/cutscene/structure.html
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CS = os.path.join(ROOT, 'export', 'story', 'cutscene')
OUT = os.path.join(CS, 'structure.html')
TPL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cutscene_structure_template.html')


def main():
    scenes = []
    for f in sorted(glob.glob(os.path.join(CS, 'structure', 'cuts_*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        for s in d.get('scenes', []):
            # 按 (part, take, shot) 归并演员
            groups = {}
            for sh in s.get('shots', []):
                key = 'shot_%d' % sh['shot']
                groups[key] = dict(shot=sh['shot'], camera=sh['camera'],
                                   actors=sh['actors'][:24], n=sh['n_actors'])
            scenes.append(dict(
                pack=s['pack'], mission=s['mission'], cutscene=s['cutscene'],
                duration=s.get('duration_s'), capped=bool(s.get('duration_capped')),
                clips=s['clips'], shots=s.get('n_shots'),
                camera_clips=s.get('n_camera_clips', 0),
                actors=s.get('actors', [])[:40], n_actors=s.get('n_actors'),
                parts=s.get('parts', []), takes=s.get('takes', []),
                groups=sorted(groups.values(), key=lambda g: g['shot']),
                cam=None,
            ))
    # 相机段
    for f in glob.glob(os.path.join(CS, 'camera_stitched', '*', '*.json')):
        d = json.load(open(f, encoding='utf-8'))
        for sc in scenes:
            if sc['cutscene'] == d['cutscene'] and sc['pack'] == d['pack']:
                segs = [x for x in d.get('segments', []) if x['dur'] >= 0.3]
                sc['cam'] = dict(duration=d.get('duration'), n=len(segs),
                                 segs=[dict(t0=s['t0'], dur=s['dur'], pos=s.get('pos0'),
                                            move=s['move']) for s in segs][:24])
    scenes.sort(key=lambda x: (x['mission'], x['cutscene']))
    tpl = open(TPL, encoding='utf-8').read()
    payload = json.dumps(dict(scenes=scenes), ensure_ascii=False).replace('</', '<\\/')
    open(OUT, 'w', encoding='utf-8').write(tpl.replace('/*__DATA__*/', payload))
    print('写入 %s：%d 个过场 (%.1f KB)' % (OUT, len(scenes), os.path.getsize(OUT) / 1024))


if __name__ == '__main__':
    main()
