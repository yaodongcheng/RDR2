#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""过场相机「跨页拼接」→ 完整轨迹 + 真实分镜表

为什么必须拼
------------
`.yad` 是按页存的：同一个过场的相机轨迹被切成每页 ≤16 秒。
实测 wnt1_ext：page1 末位姿 (X=-20.98) == page2 首位姿 (X=-20.98)，page2 末 (-17.01) == page3 首 (-17.01)。
所以「按页解码」只能拿到碎片；把首尾位姿接起来，才能得到完整机位时间线。

算法
----
1. 每页里挑「相机候选」（骨骼 ≤45 且同时有位移轨/旋转轨），取首帧与末帧位姿（位置 + 四元数）
2. 建链：A 的末位姿 ≈ B 的首位姿（位置 < 0.6 m，四元数夹角 < 8°）→ A→B 相接
3. 取最长链 = 这条过场的相机主线；链内总时长 = 过场时长
4. 链内相邻两段的**接缝**分两类：
     位姿连续  → 同一镜头的运镜（不算切）
     位姿跳变  → 真实切镜（因为不允许跳变才能接上，跳变处必然是两条不同链）
   所以：切点 = 链与链之间的断点（用「无法接上」来判定）

输出
----
    export/story/cutscene/camera_stitched/<pack>/<cutscene>.json
    export/story/cutscene/camera_stitched_index.csv
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
import cutscene_camera as CC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'story', 'cutscene_all', 'extracted')
OUT = os.path.join(ROOT, 'export', 'story', 'cutscene')
FPS = 30.0

POS_TOL = 0.6        # 位置接缝容差（米）
ANG_TOL = 8.0        # 朝向接缝容差（度）


def pose_at(c, which):
    """取一条动画的首帧/末帧 (pos, quat)"""
    tk = c['tracks']
    pos_t = next((k for k in tk if len(tk[k]) == 3 and
                  max(max(abs(x) for x in v) for v in tk[k]) > 1.5), None)
    rot_t = next((k for k in tk if 2 <= len(tk[k]) <= 3 and k != pos_t and
                  max(max(abs(x) for x in v) for v in tk[k]) <= 1.01), None)
    if pos_t is None:
        return None, None
    idx = 0 if which == 'first' else -1
    pos = [tk[pos_t][0][idx], tk[pos_t][1][idx]]
    quat = None
    if rot_t is not None:
        vals = [tk[rot_t][i][idx] for i in range(len(tk[rot_t]))]
        x, y = vals[0], vals[1]
        z = vals[2] if len(vals) > 2 else 0.0
        quat = (x, y, z, math.sqrt(max(0.0, 1.0 - x * x - y * y - z * z)))
    return pos, quat


def link_ok(a_end, b_start):
    pa, qa = a_end
    pb, qb = b_start
    if pa is None or pb is None:
        return False
    if math.dist(pa, pb) > POS_TOL:
        return False
    if qa and qb and CC.quat_angle_deg(qa, qb) > ANG_TOL:
        return False
    return True


def segment_of(c, frm, to):
    """把一条动画按 跳变 再切细：返回段列表（每段内部位姿连续）"""
    tk = c['tracks']
    pos_t = next((k for k in tk if len(tk[k]) == 3 and
                  max(max(abs(x) for x in v) for v in tk[k]) > 1.5), None)
    rot_t = next((k for k in tk if 2 <= len(tk[k]) <= 3 and k != pos_t and
                  max(max(abs(x) for x in v) for v in tk[k]) <= 1.01), None)
    n = c['frames']
    segs = []
    start = 0
    for f in range(1, n):
        jump = 0.0
        if pos_t is not None:
            jump = math.dist((tk[pos_t][0][f - 1], tk[pos_t][1][f - 1]),
                             (tk[pos_t][0][f], tk[pos_t][1][f]))
        ang = 0.0
        if rot_t is not None:
            def qq(i):
                vals = [tk[rot_t][j][i] for j in range(len(tk[rot_t]))]
                x, y = vals[0], vals[1]
                z = vals[2] if len(vals) > 2 else 0.0
                return (x, y, z, math.sqrt(max(0.0, 1 - x * x - y * y - z * z)))
            ang = CC.quat_angle_deg(qq(f - 1), qq(f))
        if jump > 1.5 or ang > 25.0:
            segs.append((start, f - 1))
            start = f
    segs.append((start, n - 1))
    out = []
    for a, b in segs:
        if b < a:
            continue
        i0, i1 = (0 if a == 0 else a), b
        pos0 = [tk[pos_t][0][a], tk[pos_t][1][a]] if pos_t is not None else None
        pos1 = [tk[pos_t][0][b], tk[pos_t][1][b]] if pos_t is not None else None
        mv = 0.0
        if pos_t is not None:
            xs = tk[pos_t][0][a:b + 1]
            ys = tk[pos_t][1][a:b + 1]
            mv = max(max(xs) - min(xs), max(ys) - min(ys))
        quat0 = None
        if rot_t is not None:
            vals = [tk[rot_t][j][a] for j in range(len(tk[rot_t]))]
            x, y = vals[0], vals[1]
            z = vals[2] if len(vals) > 2 else 0.0
            quat0 = [round(x, 4), round(y, 4), round(z, 4),
                     round(math.sqrt(max(0.0, 1 - x * x - y * y - z * z)), 4)]
        out.append(dict(frame0=a, frame1=b, dur=round((b - a + 1) / FPS, 3),
                        pos0=[round(pos0[0], 3), round(pos0[1], 3)] if pos0 else None,
                        pos1=[round(pos1[0], 3), round(pos1[1], 3)] if pos1 else None,
                        quat0=quat0, move=round(mv, 3)))
    return out


_DUR = None


def known_duration(cutscene):
    global _DUR
    if _DUR is None:
        _DUR = {}
        for f in glob.glob(os.path.join(OUT, 'structure', 'cuts_*.json')):
            d = json.load(open(f, encoding='utf-8'))
            for sc in d.get('scenes', []):
                _DUR[sc['cutscene']] = sc.get('duration_s') or 0
    return _DUR.get(cutscene) or 0


def process(pack_dir, cutscene):
    files = sorted(glob.glob(os.path.join(pack_dir, cutscene + '-*.yad')),
                   key=lambda p: int(re.search(r'-(\d+)\.yad$', p).group(1)))
    nodes = []
    for f in files:
        for c in CC.scan_block(f):
            if c['bones'] > 45:
                continue
            pos, rot = CC.camera_signature(c)
            if pos < 1:          # 旋转轨可能缺失，只要有位移轨就收
                continue
            first = pose_at(c, 'first')
            last = pose_at(c, 'last')
            if first[0] is None or last[0] is None:
                continue
            nodes.append(dict(page=int(re.search(r'-(\d+)\.yad$', f).group(1)),
                              dur=c['dur'], bones=c['bones'], start=first, end=last,
                              frames=c['frames'], raw=c))
    if not nodes:
        return None
    # 去重：同一过场里常见「同一段轨迹被复制到多页」（起点终点都一样），
    # 直接按 (起点, 终点, 时长) 折叠，否则会被拼成一条假的超长链
    # 容差 0.1 m / 0.5 s：同一台机位在相邻页里重复出现时，坐标会有 0.01~0.05 m 的抖动
    uniq = []
    for n in sorted(nodes, key=lambda x: -x['dur']):
        p0 = n['start'][0] or [0, 0]
        dup = False
        for m in uniq:
            q0 = m['start'][0] or [0, 0]
            if (abs(p0[0] - q0[0]) < 0.1 and abs(p0[1] - q0[1]) < 0.1
                    and abs(n['dur'] - m['dur']) < 0.6):
                dup = True
                break
        if not dup:
            uniq.append(n)
    nodes = uniq
    # 建链：贪心从「没人能接在前面」的节点开始
    used = [False] * len(nodes)
    chains = []
    # 优先长段做起点
    order = sorted(range(len(nodes)), key=lambda i: -nodes[i]['dur'])
    for i in order:
        if used[i]:
            continue
        chain = [i]
        used[i] = True
        extended = True
        while extended:
            extended = False
            tail = nodes[chain[-1]]['end']
            best, bestd = None, 1e9
            for j in range(len(nodes)):
                if used[j]:
                    continue
                if link_ok(tail, nodes[j]['start']):
                    d = math.dist(tail[0], nodes[j]['start'][0])
                    if d < bestd:
                        best, bestd = j, d
            if best is not None:
                chain.append(best)
                used[best] = True
                extended = True
        chains.append(chain)
    chains.sort(key=lambda ch: -sum(nodes[i]['dur'] for i in ch))
    main = chains[0]
    # 截断：链总长不应超过该过场的真实时长（防止把重复机位串成超长链）
    limit = known_duration(cutscene) or 90.0
    acc, trimmed = 0.0, []
    for i in main:
        if acc + nodes[i]['dur'] > limit * 1.15 and trimmed:
            break
        trimmed.append(i)
        acc += nodes[i]['dur']
    main = trimmed
    total = round(sum(nodes[i]['dur'] for i in main), 2)
    segs = []
    t = 0.0
    for i in main:
        for s in segment_of(nodes[i]['raw'], 0, 0):
            s2 = dict(s)
            s2['t0'] = round(t, 2)
            s2['page'] = nodes[i]['page']
            segs.append(s2)
            t += s['dur']
    return dict(cutscene=cutscene, pack=os.path.basename(pack_dir),
                pages=len(files), nodes=len(nodes), chains=len(chains),
                duration=total, n_segments=len(segs), segments=segs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pack', default=None)
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()
    packs = ([os.path.join(SRC, args.pack)] if args.pack
             else sorted(d for d in glob.glob(os.path.join(SRC, 'cuts_*')) if os.path.isdir(d)))
    rows = []
    for d in packs:
        cids = sorted({os.path.basename(f).rsplit('-', 1)[0]
                       for f in glob.glob(os.path.join(d, '*.yad'))})
        ok = 0
        outdir = os.path.join(OUT, 'camera_stitched', os.path.basename(d))
        os.makedirs(outdir, exist_ok=True)
        for cid in cids:
            r = process(d, cid)
            if not r:
                continue
            json.dump(r, open(os.path.join(outdir, cid + '.json'), 'w', encoding='utf-8'),
                      ensure_ascii=False)
            ok += 1
            rows.append(dict(pack=r['pack'], cutscene=cid, duration=r['duration'],
                             pages=r['pages'], nodes=r['nodes'], chains=r['chains'],
                             segments=r['n_segments']))
        print('%-16s 过场 %2d  拼接成功 %2d' % (os.path.basename(d), len(cids), ok))
    if args.all or not args.pack:
        with open(os.path.join(OUT, 'camera_stitched_index.csv'), 'w', encoding='utf-8-sig',
                  newline='') as f:
            w = csv.DictWriter(f, fieldnames=['pack', 'cutscene', 'duration', 'pages', 'nodes',
                                              'chains', 'segments'])
            w.writeheader()
            w.writerows(rows)
        print('\n合计 %d 个过场拼接完成，总时长 %.1f 分钟' % (
            len(rows), sum(r['duration'] for r in rows) / 60))


if __name__ == '__main__':
    main()
