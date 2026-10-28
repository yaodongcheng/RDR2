#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把一段游戏录音切成「一句一个文件」，并按台词顺序对到 beat 表上。

为什么走这条路：RDR2 的过场语音是「整场一包」的 ADAT/Vorbis（包里没有台词键），
逐句音频没法直接从包里切；但**录一遍游戏**得到的就是逐句连着说的音频，
按静音切就能还原成一句一个文件。

流程
  1. ffmpeg 解码成 16 kHz 单声道
  2. 能量 VAD：找语音段（自适应阈值 + 合并短停顿 + 丢弃过短/过长）
  3. 段数 == 该对话组的句数 → 按顺序命名 <组>_<序号>.wav（查看器自动出现播放器）
  4. 段数不符 → 输出对照表，人工确认后再用 --force 强配

用法
  uv run python tools/split_capture_audio.py rec.wav --group WNT1_BANT
  uv run python tools/split_capture_audio.py rec.wav --group WNT1_BANT --force
  uv run python tools/split_capture_audio.py rec.wav --list      # 只打印切出来的段
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY = os.path.join(ROOT, 'export', 'story')
FFMPEG = os.environ.get('FFMPEG') or 'ffmpeg'
if not os.path.isabs(FFMPEG) and FFMPEG == 'ffmpeg':
    _c = os.path.join(os.environ.get('USERPROFILE', ''), 'AppData/Roaming/com.brainmaker.client/cowork-updates/ffmpeg-binary/ffmpeg.exe')
    if os.path.exists(_c):
        FFMPEG = _c
SR = 16000


def decode(path, tmp):
    out = os.path.join(tmp, '_mono16.wav')
    cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-i', path,
           '-ac', '1', '-ar', str(SR), out]
    subprocess.run(cmd, check=True)
    with wave.open(out, 'rb') as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return data


def vad(x, frame=0.02, hop=0.01, min_speech=0.30, min_gap=0.28, pad=0.08):
    """能量 VAD：返回 [(start, end)] 秒"""
    fl = int(frame * SR)
    hl = int(hop * SR)
    n = max(0, 1 + (len(x) - fl) // hl)
    if n <= 0:
        return []
    rms = np.array([np.sqrt(np.mean(x[i * hl:i * hl + fl] ** 2) + 1e-12) for i in range(n)])
    db = 20 * np.log10(rms + 1e-9)
    # 自适应阈值：底噪（10 分位）+ 8 dB，且不低于 -55 dB
    thr = max(np.percentile(db, 10) + 8, -55)
    mask = db > thr
    segs = []
    i = 0
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            segs.append([i * hop, j * hop])
            i = j
        else:
            i += 1
    # 合并短停顿
    merged = []
    for s in segs:
        if merged and s[0] - merged[-1][1] < min_gap:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    # 过滤 + 前后留白
    out = []
    for s, e in merged:
        if e - s < min_speech:
            continue
        out.append((max(0, s - pad), min(len(x) / SR, e + pad)))
    return out


def load_lines(group):
    """从 beat 表里找该对话组的句数（跨任务搜）"""
    for f in glob.glob(os.path.join(STORY, 'beats', '*.json')):
        b = json.load(open(f, encoding='utf-8'))
        if group in b['conversations']:
            return b['id'], [x['zh'] for x in b['conversations'][group]]
    return None, []


def write_wav(path, x):
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('audio')
    ap.add_argument('--group', help='对话组名，如 WNT1_BANT')
    ap.add_argument('--outdir', default=os.path.join(STORY, 'audio'))
    ap.add_argument('--force', action='store_true', help='段数不匹配也强行按顺序配')
    ap.add_argument('--list', action='store_true', help='只列段，不写文件')
    args = ap.parse_args()

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        x = decode(args.audio, tmp)

    segs = vad(x)
    print(f'切出 {len(segs)} 段，总时长 {len(x)/SR:.1f}s')
    for i, (s, e) in enumerate(segs):
        print(f'  #{i+1}  {s:6.2f}s → {e:6.2f}s  ({e-s:.2f}s)')

    if args.list or not args.group:
        return

    mid, lines = load_lines(args.group)
    if not lines:
        print(f'!! 找不到对话组 {args.group}')
        return
    print(f'对话组 {args.group}：{len(lines)} 句（{mid}）')
    if len(segs) != len(lines):
        print(f'!! 段数 {len(segs)} ≠ 句数 {len(lines)}')
        if not args.force:
            print('   建议：确认录音里只含这一段对话；或加 --force 强配')
            return
    os.makedirs(args.outdir, exist_ok=True)
    n = min(len(segs), len(lines))
    for i in range(n):
        s, e = segs[i]
        clip = x[int(s * SR):int(e * SR)]
        p = os.path.join(args.outdir, f'{args.group}_{i+1}.wav')
        write_wav(p, clip)
    print(f'-> {args.outdir}  ({n} 个文件)')
    print('  重建查看器：uv run python tools/build_story_viewer.py')


if __name__ == '__main__':
    main()
