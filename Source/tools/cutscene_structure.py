#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""过场结构表：从 181 个 cuts_*.rpf 解出的 .ycd 里，把「过场 → 镜头 → 出场演员」盘出来。

不依赖深度解码：过场的 clip 名本身就是结构说明——
    <演员>_<dual|face>_<过场ID>_p<段>_t<条>_shot<镜号>.clip
例：
    u_m_m_bht_benedictallbright_dual_bou1_mcs1_p1a1_t03_shot_2
    exportcamera_bou1_mcs1_p1a1_t03_shot_1          ← 相机
    player_zero_face_bou1_ext_p1_t06_shot_1

所以只要正确切出 4 段：演员 / 过场ID / 段与条 / 镜号，就能还原
「一个过场有几个镜头、每个镜头里有谁、相机在第几镜」。

输入  work/story/cutscene_all/extracted/cuts_<任务>/*.ycd/.yad
输出  export/story/cutscene/structure/<包>.json     每个包一份
      export/story/cutscene/structure_all.json     全量
      export/story/cutscene/structure_index.csv    一行一个过场（便于排序/筛选）

用法
  uv run python tools/cutscene_structure.py
  uv run python tools/cutscene_structure.py --pack cuts_wnt1   # 只跑一个包
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ycd_decode as YCD   # 复用已有的 .ycd/.yad 解帧器

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'story', 'cutscene_all', 'extracted')
OUT = os.path.join(ROOT, 'export', 'story', 'cutscene')

CLIP_RX = re.compile(rb'pack:/([A-Za-z0-9_]+?)\.clip')
SHOT_RX = re.compile(r'_shot_?(\d+)$')
TAKE_RX = re.compile(r'_t(\d+)')
PART_RX = re.compile(r'_p(\d+)([a-z]\d*)?')
# 演员名后面这些后缀不是演员
KIND_SUFFIX = ('_dual', '_face', '_body')


def ids_from_clips(names):
    """从 clip 名反推过场 ID。

    clip 名形如 `<演员>_<dual|face>_<过场ID>_p<段>..._t<条>_shot<镜>`，
    但 **.ycd 文件名不一定等于过场 ID**（例：`wnt1_int_cabin.ycd` 里的 clip 叫 `wnt1_int_col`）。
    做法：取第一个 `_p<数字>` 之前的部分，在各条 clip 里求「公共后缀 token」，就是过场 ID。
    """
    prefixes = []
    for n in names:
        m = re.split(r'_p\d', n, maxsplit=1)
        if len(m) == 2:
            prefixes.append(m[0].split('_'))
    if not prefixes:
        return []
    common = list(prefixes[0])
    for toks in prefixes[1:]:
        k = 0
        while k < min(len(common), len(toks)) and common[-1 - k] == toks[-1 - k]:
            k += 1
        common = common[len(common) - k:] if k else []
        if not common:
            break
    # 去掉可能被吃进来的 dual/face 之类后缀
    while common and common[0] in ('dual', 'face', 'body'):
        common = common[1:]
    return ['_'.join(common)] if common else []


def cutscene_ids(pack_dir):
    """兜底：用 .ycd 文件名（旧逻辑）"""
    ids = [os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(pack_dir, '*.ycd'))]
    return sorted(set(ids), key=len, reverse=True)


def parse_clip(name, ids):
    """拆一个 clip 名 → dict(actor, cutscene, part, take, shot)"""
    hit = None
    for cid in ids:                      # 最长优先，避免 wnt1_ext 抢走 wnt1_ext2
        if cid in name:
            hit = cid
            break
    if not hit:
        return None
    head, tail = name.split(hit, 1)
    actor = head.rstrip('_')
    for suf in KIND_SUFFIX:
        if actor.endswith(suf):
            actor = actor[:-len(suf)]
            break
    shot = SHOT_RX.search(name)
    take = TAKE_RX.search(tail)
    part = PART_RX.search(tail)
    return dict(actor=actor or '?', cutscene=hit,
                part=(part.group(1) + (part.group(2) or '')) if part else '',
                take=int(take.group(1)) if take else None,
                shot=int(shot.group(1)) if shot else None)


def scan_pack(pack_dir):
    pack = os.path.basename(pack_dir)
    ids = list(cutscene_ids(pack_dir))
    # 用 clip 名补上真实 ID（文件名对不上时靠这个）
    for ycdf in glob.glob(os.path.join(pack_dir, '*.ycd')):
        data = open(ycdf, 'rb').read()
        names = [m.group(1).decode('latin1') for m in CLIP_RX.finditer(data)]
        ids += ids_from_clips(names)
    ids = sorted(set(ids), key=len, reverse=True)
    scenes = defaultdict(lambda: dict(id=None, mission=None, clips=0, actors=set(),
                                      combos=set(), camera_combos=set(), camera_names=set(),
                                      shots=defaultdict(lambda: dict(actors=set(), takes=set(),
                                                             camera=False, props=set())),
                                      parts=set(), takes=set()))
    yads = defaultdict(list)
    for f in glob.glob(os.path.join(pack_dir, '*.yad')):
        base = os.path.splitext(os.path.basename(f))[0]
        m = re.match(r'^(.*)-(\d+)$', base)
        if m:
            yads[m.group(1)].append(int(m.group(2)))

    # ---- .yad：每块里含若干动画段，帧数 / 30fps = 秒 ----
    yad_stat = {}
    for f in glob.glob(os.path.join(pack_dir, '*.yad')):
        base = os.path.splitext(os.path.basename(f))[0]
        m = re.match(r'^(.*)-(\d+)$', base)
        if not m:
            continue
        cid, idx = m.group(1), int(m.group(2))
        try:
            _, body = YCD.load(f)
            anims = YCD.find_animations(body)
            clips = []
            for base, fr, sl, du, _p in anims:
                try:
                    a = YCD.load_animation(body, base)
                    nb = len(a['boneids'])
                    nseq = sum(len(x['animseq']) for x in a['seqs'])
                except Exception:
                    nb, nseq = -1, -1
                clips.append(dict(frames=fr, dur=round(du, 3), bones=nb, animseqs=nseq))
            durs = [c['dur'] for c in clips]
            yad_stat.setdefault(cid, []).append(dict(
                idx=idx, n_anims=len(clips),
                max_frames=max([c['frames'] for c in clips] or [0]),
                max_dur=round(max(durs), 3) if durs else 0.0,
                total_frames=sum(c['frames'] for c in clips),
                clips=sorted(clips, key=lambda c: -c['dur'])))
        except Exception as e:
            yad_stat.setdefault(cid, []).append(dict(idx=idx, error=str(e)[:40]))

    id2ycd = {}
    for f in glob.glob(os.path.join(pack_dir, '*.ycd')):
        data = open(f, 'rb').read()
        _ycdprefix = os.path.splitext(os.path.basename(f))[0]
        for _m in CLIP_RX.finditer(data):
            pass
        for _id in ids_from_clips([m.group(1).decode('latin1') for m in CLIP_RX.finditer(data)]):
            id2ycd.setdefault(_id, _ycdprefix)
        for m in CLIP_RX.finditer(data):
            raw_name = m.group(1).decode('latin1')
            info = parse_clip(raw_name, ids)
            if not info:
                continue
            sc = scenes[info['cutscene']]
            sc['id'] = info['cutscene']
            sc['mission'] = info['cutscene'].split('_')[0].upper()
            sc['clips'] += 1
            sc['actors'].add(info['actor'])
            if info['part']:
                sc['parts'].add(info['part'])
            if info['take'] is not None:
                sc['takes'].add(info['take'])
            if info['shot'] is not None:
                key = (info['part'], info['take'], info['shot'])
                sc['combos'].add(key)
                sh = sc['shots'][info['shot']]
                if info['actor'].startswith('exportcamera'):
                    sh['camera'] = True
                    sc['camera_combos'].add(key)
                    sc['camera_names'].add(raw_name)
                else:
                    sh['actors'].add(info['actor'])

    out = []
    for cid, sc in scenes.items():
        _yk = id2ycd.get(cid, cid)
        if _yk != cid and _yk in yad_stat and cid not in yad_stat:
            yad_stat[cid] = yad_stat[_yk]
        shots = []
        for n in sorted(sc['shots']):
            d = sc['shots'][n]
            shots.append(dict(shot=n, camera=bool(d['camera']),
                              actors=sorted(d['actors']), n_actors=len(d['actors'])))
        out.append(dict(
            pack=pack, mission=sc['mission'], cutscene=cid,
            clips=sc['clips'],
            parts=sorted(sc['parts']),
            takes=sorted(sc['takes']),
            n_shots=max(len(sc['combos']), len(sc['camera_combos'])),
            n_camera_shots=len(sc['camera_combos']),
            n_camera_clips=len(sc['camera_names']),
            n_actors=len(sc['actors']),
            actors=sorted(sc['actors']),
            shots=shots,
            yad_files=sorted(yads.get(cid, [])),
            n_yad=len(yads.get(cid, [])),
            yad_blocks=sorted(yad_stat.get(cid, []), key=lambda x: x['idx']),
            duration_s=round(max([b.get('max_dur', 0) for b in yad_stat.get(cid, [])] or [0]), 2),
            duration_capped=abs(max([b.get('max_dur', 0) for b in yad_stat.get(cid, [])] or [0]) - 16.0) < 0.05,
            camera_clips=sorted([a for a in sc['actors'] if a.startswith('exportcamera')]),
            anim_durs=sorted([round(c['dur'], 2) for b in yad_stat.get(cid, [])
                              for c in b.get('clips', [])], reverse=True)[:40],
            anim_bones=sorted(set([c['bones'] for b in yad_stat.get(cid, [])
                                   for c in b.get('clips', []) if c['bones'] > 0])),
        ))
    out.sort(key=lambda x: x['cutscene'])
    return dict(pack=pack, scenes=out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pack', default=None, help='只跑一个包，如 cuts_wnt1')
    args = ap.parse_args()
    dirs = ([os.path.join(SRC, args.pack)] if args.pack
            else sorted(d for d in glob.glob(os.path.join(SRC, 'cuts_*')) if os.path.isdir(d)))
    os.makedirs(os.path.join(OUT, 'structure'), exist_ok=True)
    all_rows, index = [], []
    for d in dirs:
        res = scan_pack(d)
        json.dump(res, open(os.path.join(OUT, 'structure', res['pack'] + '.json'), 'w',
                            encoding='utf-8'), ensure_ascii=False, indent=1)
        all_rows.append(res)
        for sc in res['scenes']:
            index.append(dict(pack=sc['pack'], mission=sc['mission'], cutscene=sc['cutscene'],
                              clips=sc['clips'], shots=sc['n_shots'],
                              camera_shots=sc['n_camera_shots'], actors=sc['n_actors'],
                              takes=len(sc['takes']), yad=sc['n_yad'],
                              duration_s=sc['duration_s']))
        print('%-16s 过场 %2d  镜头 %3d  演员 %3d' % (
            res['pack'], len(res['scenes']), sum(s['n_shots'] for s in res['scenes']),
            sum(s['n_actors'] for s in res['scenes'])))

    json.dump(all_rows, open(os.path.join(OUT, 'structure_all.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, 'structure_index.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['pack', 'mission', 'cutscene', 'clips', 'shots',
                                          'camera_shots', 'actors', 'takes', 'yad', 'duration_s'])
        w.writeheader()
        w.writerows(index)
    print('\n合计: %d 个包 / %d 个过场 / %d 个镜头 / %d 条 clip' % (
        len(all_rows), len(index), sum(x['shots'] for x in index), sum(x['clips'] for x in index)))
    print('输出:', os.path.join(OUT, 'structure_all.json'), '+ structure_index.csv + structure/*.json')


if __name__ == '__main__':
    main()
