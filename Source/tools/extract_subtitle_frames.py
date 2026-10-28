#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从录屏里「按台词截帧」，给说话人识别用。

为什么这么做：实测发现 RDR2 的**字幕本身就带说话人名字**（例如画面下方显示
「约翰：继续努力，不是吗？」）。所以只要有带字幕的录屏，就能按每句话截一帧，
从字幕里读出「谁 + 说了什么」——不需要插件、不需要拆音轨。

流程
  1. 对录屏音轨做 VAD，得到每句话的起止时间
  2. 在每句中间截一帧（字幕通常覆盖整句）
  3. 输出 frames/<视频名>/seg_01.png … 和 manifest.csv（待填 speaker / text）

之后用 tools/apply_frame_manifest.py 把填好的 manifest 合成
speaker_overrides.json + 切音频。

用法
  uv run python tools/extract_subtitle_frames.py "录屏/xxx.mp4"
  uv run python tools/extract_subtitle_frames.py "录屏/xxx.mp4" --pad 3   # 字幕上下多留 3%
"""
import argparse
import csv
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from split_capture_audio import decode, vad, FFMPEG, SR  # noqa: E402

OUT = os.path.join(ROOT, 'raw', 'capture', 'frames')


def probe_size(path):
    out = subprocess.run([FFMPEG, '-hide_banner', '-i', path], capture_output=True, text=True,
                         errors='ignore').stderr
    for line in out.split('\n'):
        if 'Video:' in line and 'x' in line:
            import re
            m = re.search(r'(\d{2,5})x(\d{2,5})', line)
            if m:
                return int(m.group(1)), int(m.group(2))
    return 1920, 1080


def has_text(png):
    """粗判该帧字幕区是否有一行文字（不依赖 OCR）：
    - 取画面下方裁剪图中部区域，找白像素最多的那一行
    - 文字：该行白像素数中等（3~40）且**横向跳变很多**（字与字之间有间隙）
    - 进度条/亮边：白像素很多但几乎连续（跳变 <= 6）
    """
    try:
        import numpy as np
        from PIL import Image
    except Exception:
        return True
    a = np.asarray(Image.open(png).convert('L'), dtype=np.uint8)
    h, w = a.shape
    band = a[int(h * 0.30):int(h * 0.90), int(w * 0.15):int(w * 0.85)]
    rows = (band > 190).sum(axis=1)
    mx = int(rows.max()) if rows.size else 0
    if mx < 3 or mx > 45:
        return False
    y = int(np.argmax(rows))
    line = (band[y] > 190).astype(np.int8)
    trans = int((np.diff(line) != 0).sum())
    return trans >= 8


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('--pad', type=float, default=0.0, help='字幕区域上下留白百分比')
    ap.add_argument('--crop-bottom', type=float, default=0.30,
                    help='只保留画面下方多少比例（字幕区），默认 0.30')
    ap.add_argument('--scan', type=float, default=0.0,
                    help='密集扫描：每 N 秒取一帧，只保留有字幕的（0=关闭）')
    args = ap.parse_args()

    stem = os.path.splitext(os.path.basename(args.video))[0]
    outdir = os.path.join(OUT, stem)
    os.makedirs(outdir, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        x = decode(args.video, tmp)
    segs = vad(x)
    print(f'{len(segs)} 段，总时长 {len(x)/SR:.1f}s -> {outdir}')

    w, h = probe_size(args.video)
    top = int(h * (1 - args.crop_bottom))
    crop_h = h - top
    vf = f'crop={w}:{crop_h}:0:{top},scale=1280:-1'

    rows = []
    if args.scan > 0:
        dur = len(x) / SR
        t = 0.0
        idx = 0
        while t < dur:
            p = os.path.join(outdir, f'scan_{int(t*10):05d}.png')
            subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-y',
                            '-ss', f'{t:.2f}', '-i', args.video, '-frames:v', '1',
                            '-vf', vf, p], check=False)
            if os.path.exists(p) and has_text(p):
                idx += 1
                rows.append({'seg': f's{idx}', 'start': round(t, 2), 'end': round(t + args.scan, 2),
                             'speaker': '', 'text': '', 'frame': os.path.basename(p)})
                print(f'  [有字幕] {t:5.1f}s -> {os.path.basename(p)}')
            else:
                try:
                    os.remove(p)
                except OSError:
                    pass
            t += args.scan
        man = os.path.join(outdir, 'manifest_scan.csv')
        with open(man, 'w', newline='', encoding='utf-8-sig') as f:
            wtr = csv.DictWriter(f, fieldnames=['seg', 'start', 'end', 'speaker', 'text', 'frame'])
            wtr.writeheader()
            wtr.writerows(rows)
        print(f'扫描完成：{idx} 帧有字幕 -> {man}')
        return

    for i, (s, e) in enumerate(segs, 1):
        t = (s + e) / 2
        p = os.path.join(outdir, f'seg_{i:02d}.png')
        subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-y',
                        '-ss', f'{t:.3f}', '-i', args.video, '-frames:v', '1',
                        '-vf', vf, p], check=False)
        rows.append({'seg': i, 'start': round(s, 2), 'end': round(e, 2),
                     'speaker': '', 'text': '', 'frame': os.path.basename(p)})
        print(f'  #{i} {s:6.2f}-{e:6.2f}s -> {os.path.basename(p)}')

    man = os.path.join(outdir, 'manifest.csv')
    with open(man, 'w', newline='', encoding='utf-8-sig') as f:
        wtr = csv.DictWriter(f, fieldnames=['seg', 'start', 'end', 'speaker', 'text', 'frame'])
        wtr.writeheader()
        wtr.writerows(rows)
    print(f'-> {man}（填 speaker/text 后跑 apply_frame_manifest.py）')


if __name__ == '__main__':
    main()
