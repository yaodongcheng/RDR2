#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""过场相机提取：从 cuts_*.rpf 的 .yad 里把每个过场的机位曲线解出来。

怎么认出相机
------------
过场动画块里混着很多条动画，用骨骼规模就能分层：

| 骨骼数 | 是什么 | 特征 |
|---|---|---|
| 80~200 | 角色 | 完整人形骨架 |
| 900~1600 | 载具/大型道具 | 骨骼极多 |
| **≤ 8** | **相机 / 道具轨道** | 5 骨轨道 = 位移 3 + 旋转 3 |

再叠加两条：**时长最长的那条**（相机通常覆盖整段过场）、**通道真的有变化**（静止的不是相机）。

通道语义（实测 wnt1_mcs2）
--------------------------
    track 2 → 3 个 IndirectQuantizeFloat：位置 x/y/z（米，如 15.6 / -2.6 / 0.5）
    track 3 → 3 个 IndirectQuantizeFloat：朝向，按四元数虚部校验 x²+y²+z² ≤ 1 后补 w

镜头切点
--------
同一段过场里相机是一条连续曲线，**切镜处会出现单帧大跳**（位置或朝向突变）。
所以切点不用猜，直接从曲线上找跳变 —— 这也是「资产侧」的剪辑点，可与录屏对照。

用法
    uv run python tools/cutscene_camera.py --pack cuts_wnt1
    uv run python tools/cutscene_camera.py --pack cuts_wnt1 --cut 3.0   # 切点跳变阈值（度/米）
    uv run python tools/cutscene_camera.py --all
输出
    export/story/cutscene/camera/<过场>.json
    export/story/cutscene/camera_index.csv
"""
import argparse
import csv
import glob
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ycd_decode as YCD

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'story', 'cutscene_all', 'extracted')
OUT = os.path.join(ROOT, 'export', 'story', 'cutscene')
FPS = 30.0


def quat_from_xyz(x, y, z):
    """四元数虚部 → (x,y,z,w)；若模长 >1 说明不是四元数"""
    m = x * x + y * y + z * z
    if m > 1.0001:
        return None
    return (x, y, z, math.sqrt(max(0.0, 1.0 - m)))


def quat_angle_deg(q1, q2):
    d = abs(sum(a * b for a, b in zip(q1, q2)))
    d = min(1.0, max(-1.0, d))
    return math.degrees(2.0 * math.acos(d))


def scan_block(path):
    """一块 .yad → 每条动画的元信息 + 通道数据（只取 ≤8 骨的候选）"""
    _, body = YCD.load(path)
    out = []
    for base, frames, _sl, dur, _p in YCD.find_animations(body):
        try:
            a = YCD.load_animation(body, base)
        except Exception:
            continue
        nb = len(a['boneids'])
        if nb > 45 or nb == 0:
            continue
        tracks = {}
        for si, s in enumerate(a['seqs']):
            for k, s2 in enumerate(s['animseq']):
                vals = []
                for c in s2.channels:
                    if c is None:
                        continue
                    if getattr(c, 'values', None):
                        vals.append([c.eval_float(f) for f in range(a['frames'])])
                if vals:
                    tracks[k] = vals
        moving = sum(1 for vs in tracks.values() for v in vs if max(v) - min(v) > 0.01)
        out.append(dict(base=base, frames=a['frames'], dur=round(dur, 3), bones=nb,
                        tracks={k: v for k, v in tracks.items()}, moving=moving))
    return out


def camera_signature(c):
    """相机特征（按 track 判，不按单通道）：
    3 通道且量级 >1.5 米 → 位移轨道；3 通道且量级 ≤1 → 旋转轨道。
    相机 = 同时有一条位移轨 + 一条旋转轨。
    """
    pos = rot = 0
    for vs in c['tracks'].values():
        if not (2 <= len(vs) <= 3) or not all(vs):
            continue
        m = max(max(abs(x) for x in v) for v in vs)
        if len(vs) == 3 and m > 1.5:
            pos += 1
        elif m <= 1.01:
            rot += 1          # 旋转轨可能只有 2 个通道（少一个分量）
    return pos, rot


def pick_camera(cands):
    """优先级：位移+旋转都齐 → 通道在动 → 时长最长"""
    best, best_score = None, -1.0
    for c in cands:
        if c['bones'] > 45:
            continue
        if c['moving'] < 0:      # 只排除坏数据
            continue
        pos, rot = camera_signature(c)
        # 只要有「位移轨」就认（旋转轨可能缺失，过场里有不少只存位姿位置的情况）
        if pos < 1:
            continue
        # 静态机位（moving=0）也算：它给的是「这一镜的固定机位」
        score = c['dur'] + min(c['moving'], 12) * 0.5 + (2.0 if rot >= 1 else 0.0)
        if score > best_score:
            best, best_score = c, score
    return best


def extract_camera(cam):
    """→ 每帧 位置(xy) + 四元数(4) + 切点候选

    实测编码：5 根轨道 = [posX, posY, quatW, quatX, quatY] + quatZ
    （第 3 个通道 ≈ sqrt(1-|q|²)，是四元数 w 而不是 z，别当坐标用）
    """
    tracks = cam['tracks']
    keys = sorted(tracks)
    pos_track = next((k for k in keys if len(tracks[k]) == 3 and
                      max(max(abs(x) for x in v) for v in tracks[k]) > 1.5), None)
    rot_track = next((k for k in keys if len(tracks[k]) == 3 and k != pos_track and
                      max(max(abs(x) for x in v) for v in tracks[k]) <= 1.01), None)
    n = cam['frames']
    frames = []
    for f in range(n):
        rec = dict(f=f, t=round(f / FPS, 3))
        if pos_track is not None:
            rec['pos'] = [round(tracks[pos_track][0][f], 4), round(tracks[pos_track][1][f], 4)]
        if rot_track is not None:
            qx, qy, qz = [tracks[rot_track][i][f] for i in range(3)]
            w = math.sqrt(max(0.0, 1.0 - qx * qx - qy * qy - qz * qz))
            rec['quat'] = [round(qx, 4), round(qy, 4), round(qz, 4), round(w, 4)]
        frames.append(rec)
    # 切点候选：位置跳变 > 1.5 m 或 朝向跳变 > 25°
    cuts = [0.0]
    for f in range(1, n):
        a, b = frames[f - 1], frames[f]
        jump = math.dist(a['pos'], b['pos']) if 'pos' in a and 'pos' in b else 0.0
        ang = quat_angle_deg(a['quat'], b['quat']) if 'quat' in a and 'quat' in b else 0.0
        if jump > 1.5 or ang > 25.0:
            cuts.append(round(f / FPS, 3))
    # 切点 = 相机姿态突变处；每段内部姿态基本恒定 → 一段 = 一个「机位/take」
    ivs = [round(cuts[i + 1] - cuts[i], 2) for i in range(len(cuts) - 1)]
    period = None
    if len(ivs) >= 3 and max(ivs) - min(ivs) < 0.05:
        period = ivs[0]
    segs = []
    for i, c0 in enumerate(cuts):
        c1 = cuts[i + 1] if i + 1 < len(cuts) else cam['dur']
        f0 = int(round(c0 * FPS))
        f1 = min(n - 1, int(round(c1 * FPS)) - 1)
        if f1 < f0:
            continue
        ps = [frames[f] for f in range(f0, f1 + 1) if 'pos' in frames[f]]
        qs = [frames[f] for f in range(f0, f1 + 1) if 'quat' in frames[f]]
        # 段内位移幅度：恒定机位=静止，动镜=有位移
        move = 0.0
        if len(ps) > 1:
            xs = [p_['pos'][0] for p_ in ps]
            ys = [p_['pos'][1] for p_ in ps]
            move = round(max(max(xs) - min(xs), max(ys) - min(ys)), 3)
        segs.append(dict(
            i=i, t0=round(c0, 2), dur=round(c1 - c0, 2),
            pos=[round(sum(p_['pos'][0] for p_ in ps) / len(ps), 2),
                 round(sum(p_['pos'][1] for p_ in ps) / len(ps), 2)] if ps else None,
            quat=qs[0]['quat'] if qs else None,
            move=move, static=move < 0.05))
    return dict(frames=frames, cuts=cuts, pos_track=pos_track, rot_track=rot_track,
                period=period, intervals=ivs, segments=segs)


def process_pack(pack_dir, cut_thr=None):
    pack = os.path.basename(pack_dir)
    results = []
    blocks = {}
    for f in sorted(glob.glob(os.path.join(pack_dir, '*.yad'))):
        base = os.path.splitext(os.path.basename(f))[0]
        m = re.match(r'^(.*)-(\d+)$', base)
        if not m:
            continue
        blocks.setdefault(m.group(1), []).append((int(m.group(2)), f))

    for cid, items in sorted(blocks.items()):
        cands = []
        for idx, path in sorted(items):
            try:
                for c in scan_block(path):
                    c['block'] = idx
                    cands.append(c)
            except Exception:
                continue
        cam = pick_camera(cands)
        if not cam:
            results.append(dict(cutscene=cid, pack=pack, camera=None, reason='no-candidate'))
            continue
        ex = extract_camera(cam)
        # 每帧只留 10 个采样点，避免 JSON 过大；但切点保留精确帧
        frames = ex['frames']
        step = max(1, len(frames) // 400)
        thin = frames[::step]
        results.append(dict(
            cutscene=cid, pack=pack, duration=round(cam['dur'], 2),
            frames_n=cam['frames'], bones=cam['bones'], block=cam['block'],
            pos_track=ex['pos_track'], rot_track=ex['rot_track'],
            n_cuts=len(ex['cuts']), cuts=ex['cuts'],
            cut_period=ex['period'],
            cuts_suspect=bool(ex['period']),
            segments=ex['segments'],
            n_static=sum(1 for g in ex['segments'] if g['static']),
            sample=thin,
            shot_durs=[round(ex['cuts'][i + 1] - ex['cuts'][i], 2) for i in range(len(ex['cuts']) - 1)]
                       + [round(cam['dur'] - ex['cuts'][-1], 2)],
        ))
    return dict(pack=pack, cutscenes=results)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pack', default=None)
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()
    os.makedirs(os.path.join(OUT, 'camera'), exist_ok=True)
    packs = ([os.path.join(SRC, args.pack)] if args.pack
             else sorted(d for d in glob.glob(os.path.join(SRC, 'cuts_*')) if os.path.isdir(d)))
    rows = []
    for d in packs:
        res = process_pack(d)
        name = res['pack']
        json.dump(res, open(os.path.join(OUT, 'camera', name + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False)
        ok = [c for c in res['cutscenes'] if c.get('camera') is not False and c.get('duration')]
        print('%-16s 过场 %2d  找到相机 %2d  切点合计 %3d' % (
            name, len(res['cutscenes']), len(ok), sum(c.get('n_cuts', 0) for c in ok)))
        for c in ok:
            rows.append(dict(pack=name, cutscene=c['cutscene'], duration=c['duration'],
                             shots=c['n_cuts'], bones=c['bones'], block=c['block'],
                             shot_durs='/'.join(str(x) for x in c['shot_durs'][:12])))
    if args.all or not args.pack:
        with open(os.path.join(OUT, 'camera_index.csv'), 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['pack', 'cutscene', 'duration', 'shots', 'bones',
                                              'block', 'shot_durs'])
            w.writeheader()
            w.writerows(rows)
        print('\n合计 %d 个过场有相机，%d 个切点' % (len(rows), sum(r['shots'] for r in rows)))


if __name__ == '__main__':
    main()
