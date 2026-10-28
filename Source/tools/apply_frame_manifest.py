#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「逐句截图清单」变成说话人标注 + 音频切片。

输入：extract_subtitle_frames.py 生成的 manifest.csv，人工（或视觉模型）填好
      seg, start, end, speaker, text, frame

做的事：
  1. 用 text 去 beat 表里找最匹配的台词（同任务内优先）
  2. 命中 → 写 speaker_overrides.json（查看器直接显示"谁说的"）
  3. 同时按 start/end 从录屏切出 <组>_<序号>.wav（查看器出现播放器）

用法：
  uv run python tools/apply_frame_manifest.py "raw/capture/frames/<视频名>/manifest.csv"
  ... --audio "录屏/xxx.mp4"       # 顺便切音频
  ... --mission WNT1               # 限定在某任务里匹配
"""
import argparse
import csv
import difflib
import glob
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY = os.path.join(ROOT, 'export', 'story')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from split_capture_audio import decode, write_wav, SR  # noqa: E402


def load_lines(mission=None):
    out = []
    for f in glob.glob(os.path.join(STORY, 'beats', '*.json')):
        b = json.load(open(f, encoding='utf-8'))
        if mission and b['id'].upper() != mission.upper():
            continue
        for g, lines in b['conversations'].items():
            for x in lines:
                out.append({'mission': b['id'], 'group': g, 'n': x['n'], 'zh': x['zh']})
    return out


def norm(s):
    return ''.join(ch for ch in (s or '') if ch not in '，。！？、,.!?…“”"\' ')


def both(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('manifest')
    ap.add_argument('--audio', help='录屏/录音文件，用来切句')
    ap.add_argument('--mission', help='限定任务')
    ap.add_argument('--threshold', type=float, default=0.62)
    args = ap.parse_args()

    rows = [r for r in csv.DictReader(open(args.manifest, encoding='utf-8-sig'))
            if (r.get('text') or '').strip()]
    if not rows:
        print('manifest 里没有填 text 的行'); return

    pool = load_lines(args.mission)
    ov_path = os.path.join(STORY, 'speaker_overrides.json')
    ov = json.load(open(ov_path, encoding='utf-8')) if os.path.exists(ov_path) else {}
    matched, unmatched = [], []

    for r in rows:
        best, score = None, 0.0
        for c in pool:
            s = both(r['text'], c['zh'])
            if s > score:
                best, score = c, s
        if best and score >= args.threshold:
            ov.setdefault(best['mission'], {}).setdefault(best['group'], {})[
                str(best['n'])] = (r.get('speaker') or '').strip()
            matched.append((r, best, score))
        else:
            unmatched.append((r, best, score))

    json.dump(ov, open(ov_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'匹配 {len(matched)} 条，未匹配 {len(unmatched)} 条 -> {ov_path}')
    for r, b, s in matched[:10]:
        print(f"  ✓ {r.get('speaker')}: {r['text'][:18]}  ->  {b['mission']}/{b['group']}_{b['n']} ({s:.2f})")
    for r, b, s in unmatched[:10]:
        print(f"  ? {r['text'][:18]}  (最近 {b['zh'][:14] if b else '-'} {s:.2f})")

    # 未匹配到的、但读出了 speaker+text 的，作为「现场采集」单独存档
    cap_path = os.path.join(STORY, 'captured.json')
    cap = json.load(open(cap_path, encoding='utf-8')) if os.path.exists(cap_path) else []
    src = os.path.splitext(os.path.basename(args.manifest))[0]
    added = 0
    for r, b, s_ in unmatched:
        sp = (r.get('speaker') or '').strip()
        tx = (r.get('text') or '').strip()
        if not sp or not tx:
            continue
        cap.append({'speaker': sp, 'text': tx, 'start': r['start'], 'end': r['end'],
                    'source': os.path.basename(args.manifest), 'note': '未匹配到剧本台词'})
        added += 1
    if added:
        json.dump(cap, open(cap_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'-> {cap_path}（新增 {added} 条现场采集）')

    if args.audio:
        outdir = os.path.join(STORY, 'audio')
        os.makedirs(outdir, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            x = decode(args.audio, tmp)
        n = 0
        for r, b, _ in matched:
            s, e = float(r['start']), float(r['end'])
            write_wav(os.path.join(outdir, f"{b['group']}_{b['n']}.wav"),
                      x[int(s * SR):int(e * SR)])
            n += 1
        # 未匹配的也切出来，放 _captured/
        cd = os.path.join(outdir, '_captured')
        m = 0
        for r, b, _ in unmatched:
            if not (r.get('speaker') or '').strip():
                continue
            os.makedirs(cd, exist_ok=True)
            s0, e0 = float(r['start']), float(r['end'])
            name = f"cap_{int(float(r['start'])*100):05d}.wav"
            write_wav(os.path.join(cd, name), x[int(s0 * SR):int(e0 * SR)])
            m += 1
        print(f'-> {outdir} 切出 {n} 段（另有 {m} 段现场采集在 _captured/）')
        print('  重建查看器：uv run python tools/build_story_viewer.py')


if __name__ == '__main__':
    main()
