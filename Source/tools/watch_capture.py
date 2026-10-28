#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""录音看门狗：进游戏录，录完自动切句、自动对台词、自动进查看器。

用法
    # 1) 开着这个脚本（会一直盯着 raw/capture/）
    uv run python tools/watch_capture.py --mission WNT1

    # 2) 进游戏，OBS 录一段对话，停止录制（文件落到 raw/capture/）
    #    → 脚本自动：解码 → VAD 切句 → 在该任务的对白组里挑最匹配的一组 → 命名落盘
    #    → 若匹配不唯一，落到 raw/capture/pending/ 并打印候选

    # 只跑一次（处理已有文件）：
    uv run python tools/watch_capture.py --once

匹配原理
    录音切出的段数 ≈ 对话组句数、总时长 ≈ 句数 × 2.6s。
    在候选组里取误差最小者；误差很接近时判为“不确定”，交人工确认（--group 指定）。
"""
import argparse
import csv
import glob
import json
import os
import subprocess
import sys
import tempfile
import time
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY = os.path.join(ROOT, 'export', 'story')
CAPTURE = os.path.join(ROOT, 'raw', 'capture')
AUDIO_OUT = os.path.join(STORY, 'audio')
FFMPEG = os.environ.get('FFMPEG', 'ffmpeg')
SR = 16000
EXTS = ('.wav', '.mp3', '.m4a', '.flac', '.mp4', '.mkv', '.mov', '.avi')

sys.path.insert(0, os.path.join(ROOT, 'tools'))
from split_capture_audio import decode, vad, write_wav  # noqa: E402


def conv_index(mission=None):
    """{mid: {group: [每句字数]}}（字数用来预测每句时长，做相关性匹配）"""
    out = {}
    for f in glob.glob(os.path.join(STORY, 'beats', '*.json')):
        b = json.load(open(f, encoding='utf-8'))
        mid = b['id']
        if mission and mid.upper() != mission.upper():
            continue
        d = {}
        for g, lines in b['conversations'].items():
            if len(lines) >= 2:
                d[g] = [max(1, len(x['zh'])) for x in lines]
        out[mid] = d
    return out


def guess(segs, cands):
    """用「句数 + 总时长 + 每句时长与字数的相关性」三条线索挑对话组"""
    durs = np.array([e - s for s, e in segs], dtype=np.float32)
    dur = float(durs.sum())
    rows = []
    for g, chars in cands.items():
        n = len(chars)
        est = n * 2.6
        score = abs(len(segs) - n) * 4.0 + abs(dur - est) / 6.0
        if n == len(segs) and n >= 3:
            exp = np.array(chars, dtype=np.float32) / 5.5
            a = durs - durs.mean()
            b = exp - exp.mean()
            denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-6
            corr = float(np.dot(a, b) / denom)
            score += (1.0 - corr) * 6.0
        rows.append((score, g, n))
    rows.sort()
    if not rows:
        return None, []
    best = rows[0]
    close = [r for r in rows if r[0] - best[0] < 1.0]
    if len(close) > 1:
        return None, close[:4]
    return best, rows[:4]


def process(path, cands, out_dir, dry=False):
    with tempfile.TemporaryDirectory() as tmp:
        x = decode(path, tmp)
    segs = vad(x)
    dur = sum(e - s for s, e in segs)
    if not segs:
        return {'file': os.path.basename(path), 'status': 'no-speech'}
    best, top = guess(segs, cands)
    rec = {'file': os.path.basename(path), 'segments': len(segs),
           'duration': round(dur, 2), 'match': None, 'candidates': top[:4]}
    if not best:
        rec['status'] = 'ambiguous'
        best = top[0] if top else None
        if not best:
            return rec
        rec['status'] = 'low-confidence'
    _, g, n = best
    rec['match'] = g
    target = out_dir if rec.get('status') != 'low-confidence' else os.path.join(
        os.path.dirname(path), 'pending', os.path.splitext(os.path.basename(path))[0])
    if not dry:
        os.makedirs(target, exist_ok=True)
        for i in range(min(len(segs), n)):
            s, e = segs[i]
            write_wav(os.path.join(target, f'{g}_{i+1}.wav'), x[int(s * SR):int(e * SR)])
        rec['written'] = min(len(segs), n)
        rec['target'] = target
        json.dump(rec, open(os.path.join(target, '_report.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=CAPTURE)
    ap.add_argument('--mission', help='只在该任务的对白组里匹配')
    ap.add_argument('--group', help='直接指定对话组（跳过自动匹配）')
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--interval', type=float, default=5.0)
    ap.add_argument('--dry', action='store_true')
    args = ap.parse_args()

    idx = conv_index(args.mission)
    if args.mission:
        cands = {}
        for mid, d in idx.items():
            cands.update(d)
    else:
        cands = {}
        for mid, d in idx.items():
            for g, n in d.items():
                cands[g] = n
    if args.group:
        cands = {args.group: cands.get(args.group, 0)}

    os.makedirs(args.dir, exist_ok=True)
    print(f'盯着 {args.dir}（候选对话组 {len(cands)} 个）')
    done = set(glob.glob(os.path.join(args.dir, '*.done')))
    seen = {os.path.splitext(p)[0] for p in done}
    results = []
    while True:
        files = [p for p in glob.glob(os.path.join(args.dir, '*'))
                 if p.lower().endswith(EXTS) and os.path.splitext(p)[0] not in seen]
        for p in files:
            if not os.path.getsize(p):
                continue
            print(f'\n[新的] {os.path.basename(p)}')
            try:
                rec = process(p, cands, AUDIO_OUT, dry=args.dry)
            except Exception as e:  # noqa: BLE001
                print('  处理失败：', e)
                continue
            print('  ', json.dumps(rec, ensure_ascii=False))
            results.append(rec)
            seen.add(os.path.splitext(p)[0])
            open(os.path.splitext(p)[0] + '.done', 'w').close()
            if rec.get('written'):
                subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'build_story_viewer.py')],
                               cwd=ROOT, check=False)
                print('   查看器已重建')
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
