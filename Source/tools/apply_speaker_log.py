#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「运行时采集日志」合并成说话人标注 + 音频切片清单。

用途：静态资源里没有逐句说话人（已确认），但只要你开着游戏正常玩一遍，
用一个 hook 记录「时间 + 说话 ped + 正在播的台词键」，就能 100% 还原。

日志格式（CSV，带表头，字段顺序可任意，按表头识别）：
    t_ms,ped,line_key,conv_group
    12345,cs_dutch_ms1,WNT1_BANT_1,WNT1_BANT
    13980,player_zero,WNT1_BANT_2,WNT1_BANT

也接受简化格式：`line_key,ped`（只要这两列）。

用法：
    uv run python tools/apply_speaker_log.py raw/capture/wnt1.csv
    # -> export/story/speaker_overrides.json（自动并进查看器）
    # -> export/story/capture_segments.csv（音频切片清单：起始/结束时间 + 台词键）

如果同时有整段录音（OBS 录的 wav），可用 --audio 指定，脚本会按 t_ms 切片：
    uv run python tools/apply_speaker_log.py raw/capture/wnt1.csv --audio raw/capture/wnt1.wav
"""
import argparse
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY = os.path.join(ROOT, 'export', 'story')

PED_CN = {
    'player_zero': '亚瑟', 'player_three': '约翰', 'cs_arthur': '亚瑟', 'cs_john': '约翰',
    'cs_dutch': '达奇', 'cs_micah': '迈卡', 'cs_abigail': '阿比盖尔', 'cs_sadie': '莎迪',
    'cs_charles': '查尔斯', 'cs_bill': '比尔', 'cs_javier': '哈维尔', 'cs_hosea': '何西阿',
    'cs_uncle': '大叔', 'cs_jack': '杰克', 'cs_karen': '凯伦', 'cs_tilly': '蒂莉',
    'cs_strauss': '施特劳斯', 'cs_pearson': '皮尔逊', 'cs_grimshaw': '格里姆肖',
    'cs_molly': '莫莉', 'cs_sean': '西恩', 'cs_lenny': '蓝尼', 'cs_swanson': '斯旺森',
}


def cn_of(ped):
    p = (ped or '').strip().lower()
    p = re.sub(r'_(ms|fs)\d+$', '', p)
    for k, v in PED_CN.items():
        if p.startswith(k):
            return v
    return ped.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log')
    ap.add_argument('--audio', help='可选：整段录音（wav），按 log 的 t_ms 切片')
    ap.add_argument('--out', default=os.path.join(STORY, 'speaker_overrides.json'))
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.log, encoding='utf-8-sig')))
    if not rows:
        print('empty log'); return
    cols = {c.lower().strip(): c for c in rows[0].keys()}

    def col(*names):
        for n in names:
            if n in cols:
                return cols[n]
        return None

    c_t = col('t_ms', 'time_ms', 'ms', 't')
    c_ped = col('ped', 'speaker', 'ped_model', 'actor')
    c_key = col('line_key', 'key', 'line', 'lineid')
    if not c_key:
        print('日志缺少 line_key 列'); sys.exit(1)

    # 解析 line_key -> group + 序号
    ov = {}
    if os.path.exists(args.out):
        ov = json.load(open(args.out, encoding='utf-8'))
    segs = []
    last_t = None
    parsed = []
    for r in rows:
        key = (r.get(c_key) or '').strip()
        m = re.match(r'^(.*)_(\d+)$', key)
        if not m:
            continue
        group, n = m.group(1), int(m.group(2))
        ped = cn_of(r.get(c_ped) or '') if c_ped else ''
        t = int(float(r.get(c_t))) if c_t and r.get(c_t) else None
        parsed.append((t, key, group, n, ped))
        if ped:
            ov.setdefault(group.split('_')[0].upper(), {})  # 占位，下面按任务重写

    # 任务 ID 推断：取 group 里第一个下划线前的部分（WNT1_BANT -> WNT1）
    ov = {}
    for t, key, group, n, ped in parsed:
        mid = group.split('_')[0].upper()
        ov.setdefault(mid, {}).setdefault(group, {})[str(n)] = ped

    json.dump(ov, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'-> {args.out}  ({sum(len(g) for m in ov.values() for g in m.values())} 句已标注)')

    # 切片清单（t 差 = 句长；最后一句用 3s 兜底）
    out_csv = os.path.join(STORY, 'capture_segments.csv')
    with open(out_csv, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['start_ms', 'end_ms', 'line_key', 'speaker', 'mission'])
        for i, (t, key, group, n, ped) in enumerate(parsed):
            if t is None:
                continue
            end = parsed[i + 1][0] if i + 1 < len(parsed) and parsed[i + 1][0] else t + 3000
            w.writerow([t, end, key, ped, group.split('_')[0].upper()])
    print(f'-> {out_csv}')

    if args.audio:
        try:
            from pydub import AudioSegment  # 可选依赖
        except ImportError:
            print('未安装 pydub，跳过切片（uv pip install pydub 后重跑）'); return
        audio = AudioSegment.from_file(args.audio)
        d = os.path.join(STORY, 'audio')
        os.makedirs(d, exist_ok=True)
        n_ok = 0
        for i, (t, key, group, n, ped) in enumerate(parsed):
            if t is None:
                continue
            end = parsed[i + 1][0] if i + 1 < len(parsed) and parsed[i + 1][0] else t + 3000
            seg = audio[t:end]
            p = os.path.join(d, f'{group}_{n}.wav')
            seg.export(p, format='wav')
            n_ok += 1
        print(f'-> {d}  ({n_ok} 段音频)')


if __name__ == '__main__':
    main()
