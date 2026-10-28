#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「结构表」与「相机解析」合成一张分镜总表。

一行 = 一个过场：

    pack / cutscene / mission        归属
    duration_s                       过场时长（.yad 帧数 / 30fps）
    shots                            镜头数（clip 名里 (part,take,shot) 组合）
    clips                            clip 总数
    cam_found                        是否解出相机
    cam_duration                     相机轨迹总时长（跨页拼接后）
    cam_segments                     相机段数（每段 = 一个固定/运镜机位）
    cam_static                       其中固定机位的段数
    avg_shot_s                       平均每镜时长 = duration_s / shots
    seg_per_shot                     相机段数 / 镜头数（≈1 说明段≈镜头；>1 说明混了 take）

输出：export/story/cutscene/shot_table.csv  + shot_table.json
用法：uv run python tools/build_shot_table.py
"""
import csv
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CS = os.path.join(ROOT, 'export', 'story', 'cutscene')
OUT_CSV = os.path.join(CS, 'shot_table.csv')
OUT_JSON = os.path.join(CS, 'shot_table.json')


def load_structure():
    rows = {}
    for f in glob.glob(os.path.join(CS, 'structure', 'cuts_*.json')):
        d = json.load(open(f, encoding='utf-8'))
        for s in d.get('scenes', []):
            rows[s['cutscene']] = s
    return rows


def load_camera():
    """相机：优先跨页拼接结果，回落按页结果"""
    cam = {}
    for f in glob.glob(os.path.join(CS, 'camera_stitched', '*', '*.json')):
        d = json.load(open(f, encoding='utf-8'))
        segs = d.get('segments') or []
        cam[d['cutscene']] = dict(
            duration=d.get('duration'), segments=len(segs),
            static=sum(1 for s in segs if s.get('move', 1) < 0.05),
            chains=d.get('chains'), pages=d.get('pages'), src='stitched')
    if not cam:
        for f in glob.glob(os.path.join(CS, 'camera', 'cuts_*.json')):
            d = json.load(open(f, encoding='utf-8'))
            for c in d.get('cutscenes', []):
                if not c.get('duration'):
                    continue
                cam[c['cutscene']] = dict(
                    duration=c['duration'], segments=len(c.get('segments') or []),
                    static=c.get('n_static'), chains=None, pages=None, src='page')
    return cam


def main():
    st = load_structure()
    cam = load_camera()
    rows = []
    for cid, s in sorted(st.items()):
        shots = max(1, s['n_shots'])
        c = cam.get(cid) or {}
        dur = s.get('duration_s') or 0
        rows.append(dict(
            pack=s['pack'], cutscene=cid, mission=s['mission'],
            duration_s=round(float(dur), 2), shots=s['n_shots'],
            clips=s['clips'], actors=s['n_actors'],
            cam_found='Y' if c else '',
            camera_clips=s.get('n_camera_clips', ''),
            dur_capped='Y' if s.get('duration_capped') else '',
            cam_duration=c.get('duration') or '',
            cam_segments=c.get('segments') or '',
            cam_static=c.get('static') if c else '',
            avg_shot_s=round(float(dur) / shots, 2) if dur else '',
            seg_per_shot=round((c.get('segments') or 0) / shots, 2) if c else '',
        ))
    with open(OUT_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    json.dump(rows, open(OUT_JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    n_cam = sum(1 for r in rows if r['cam_found'])
    tot = sum(r['duration_s'] for r in rows) / 60
    one = sum(1 for r in rows if r['seg_per_shot'] != '' and abs(float(r['seg_per_shot']) - 1) < 0.15)
    print('分镜总表：%d 个过场 / %d 个镜头 / %.1f 分钟；其中有相机 %d 个' % (
        len(rows), sum(r['shots'] for r in rows), tot, n_cam))
    print('「相机段数 ≈ 镜头数」的过场：%d 个（这批可以认为每段就是一个镜头）' % one)
    print('→', OUT_CSV)


if __name__ == '__main__':
    main()
