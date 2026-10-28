#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把一段录屏预处理成「可读的字幕拼图」，供人工/视觉模型逐句读。

步骤：
  1. ffmpeg 按 1 fps 抽帧（可选时间段）
  2. 纯 numpy 判「这一帧有没有字幕行」
  3. 连续相同字幕去重
  4. 每 5 句拼成一张竖图 montage/m_XX.png（带时间戳角标）
  5. 生成 manifest_template.csv（start/end/speaker/text/frame）

用法：
  uv run python tools/prep_montage.py "录屏/带说话人录屏.mp4" --start 282 --end 600 --tag b2
"""
import argparse
import csv
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from split_capture_audio import FFMPEG  # noqa: E402

OUTBASE = os.path.join(ROOT, 'raw', 'capture', 'batches')


def has_text(a):
    h, w = a.shape
    b = a[int(h * 0.60):int(h * 0.95), int(w * 0.08):int(w * 0.92)]
    rr = (b > 190).sum(axis=1)
    mx = int(rr.max()) if rr.size else 0
    if mx < 3 or mx > 60:
        return False
    y = int(np.argmax(rr))
    line = (b[y] > 190).astype(np.int8)
    return int((np.diff(line) != 0).sum()) >= 8


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('--start', type=float, default=0)
    ap.add_argument('--end', type=float, default=0)
    ap.add_argument('--tag', default='b1')
    ap.add_argument('--per', type=int, default=5, help='每张拼图放几句')
    args = ap.parse_args()

    out = os.path.join(OUTBASE, args.tag)
    frames = os.path.join(out, 'frames')
    os.makedirs(frames, exist_ok=True)
    dur = args.end - args.start if args.end > args.start else 0
    cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-y']
    if args.start:
        cmd += ['-ss', str(args.start)]
    if dur:
        cmd += ['-t', str(dur)]
    cmd += ['-i', args.video, '-vf', 'fps=1,scale=960:-1',
            os.path.join(frames, 'f_%05d.png')]
    subprocess.run(cmd, check=True)

    files = sorted(os.listdir(frames))
    picks = []
    prev = None
    for i, fn in enumerate(files):
        p = os.path.join(frames, fn)
        a = np.asarray(Image.open(p).convert('L'), dtype=np.uint8)
        if not has_text(a):
            continue
        if prev is not None and prev.shape == a.shape and np.abs(a.astype(np.int16) - prev).mean() < 6:
            continue
        prev = a.astype(np.int16)
        t = args.start + i
        picks.append((t, p))
    print(f'{len(files)} 帧 → {len(picks)} 条候选字幕')

    mdir = os.path.join(out, 'montage')
    os.makedirs(mdir, exist_ok=True)
    for gi in range(0, len(picks), args.per):
        chunk = picks[gi:gi + args.per]
        ims = []
        for t, p in chunk:
            im = Image.open(p).convert('RGB')
            ImageDraw.Draw(im).text((6, 6), f'{int(t)//60}:{int(t)%60:02d}', fill=(255, 60, 60))
            ims.append(im)
        w = max(i.width for i in ims)
        h = sum(i.height for i in ims)
        canvas = Image.new('RGB', (w, h), (0, 0, 0))
        y = 0
        for im in ims:
            canvas.paste(im, (0, y))
            y += im.height
        canvas.save(os.path.join(mdir, f'm_{gi//args.per+1:02d}.png'))
    with open(os.path.join(out, 'manifest_template.csv'), 'w', newline='',
              encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['start', 'end', 'speaker', 'text'])
        for t, _ in picks:
            w.writerow([t, t + 2, '', ''])
    print(f'-> {mdir}（{len(range(0,len(picks),args.per))} 张拼图）')
    print(f'-> {out}/manifest_template.csv')


if __name__ == '__main__':
    main()
