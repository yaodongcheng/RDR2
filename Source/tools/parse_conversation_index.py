#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""解析全部对话资产（audio/conversations.rpf 下的 18 417 个 .ymt）。

产出「对话索引」：每个对话名 → 它包含的全部台词键、对应的 SpeechContext、来源文件。

原理
  `.ymt` 是 PSIN 容器，字符串池里成对出现：
        <SpeechContext>  e.g. WNT1_HWAB
        <LineKey>        e.g. WNT1_INT_CABIN_2
  按文件内出现顺序配对即可还原「第几句用哪个语音上下文」。

输出
  export/story/conversation_index.json   { 对话名: {file, lines:[[n, ctx], ...]} }
  export/story/conversation_index.csv    扁平表（对话名, 句号, 台词键, 上下文, 文件）
  export/story/conversation_index_stats.json
"""
import glob
import json
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'raw', 'conversations', 'out')
STORY = os.path.join(ROOT, 'export', 'story')

TOK = re.compile(rb'[A-Z0-9_]{3,48}')
LINE = re.compile(r'^([A-Z0-9]+(?:[A-Z0-9_]*?))_(\d{1,3})$')


def parse_file(path):
    d = open(path, 'rb').read()
    toks = [m.group().decode() for m in TOK.finditer(d)]
    # 过滤掉明显不是键的（纯数字、PSIN 分块名）
    toks = [t for t in toks if not t.isdigit() and t not in
            ('PSIN', 'PMAP', 'PSCH', 'PSIG', 'STDN', 'HTAP', 'CHKS')]
    pairs = []
    i = 0
    while i < len(toks) - 1:
        a, b = toks[i], toks[i + 1]
        if LINE.match(b) and not LINE.match(a):
            pairs.append((a, b))
            i += 2
        else:
            i += 1
    return pairs


def main():
    idx = {}
    rows = []
    no_pairs = 0
    files = sorted(glob.glob(os.path.join(SRC, '*.ymt')))
    for p in files:
        fid = os.path.basename(p)[:-4]
        pairs = parse_file(p)
        if not pairs:
            no_pairs += 1
            continue
        convs = defaultdict(dict)
        for ctx, line in pairs:
            m = LINE.match(line)
            if not m:
                continue
            conv, n = m.group(1), int(m.group(2))
            convs[conv][n] = ctx
        for conv, lines in convs.items():
            rec = {
                'file': fid,
                'lines': [[n, lines[n]] for n in sorted(lines)],
            }
            if conv in idx:                      # 同名对话在多文件出现 → 合并
                old = {n for n, _ in idx[conv]['lines']}
                for n, c in rec['lines']:
                    if n not in old:
                        idx[conv]['lines'].append([n, c])
                idx[conv]['lines'].sort(key=lambda x: x[0])
                idx[conv]['files'] = sorted(set(idx[conv].get('files', [idx[conv]['file']]) + [fid]))
            else:
                idx[conv] = rec
                idx[conv]['files'] = [fid]
            for n, c in rec['lines']:
                rows.append([conv, n, f'{conv}_{n}', c, fid])

    json.dump(idx, open(os.path.join(STORY, 'conversation_index.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)
    import csv
    with open(os.path.join(STORY, 'conversation_index.csv'), 'w', newline='',
              encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['conversation', 'line_no', 'line_key', 'speech_context', 'ymt'])
        w.writerows(rows)
    stats = {
        'ymt_files': len(files),
        'ymt_with_pairs': len(files) - no_pairs,
        'ymt_without_pairs': no_pairs,
        'conversations': len(idx),
        'lines': len(rows),
        'lines_per_conv_avg': round(len(rows) / max(len(idx), 1), 1),
    }
    json.dump(stats, open(os.path.join(STORY, 'conversation_index_stats.json'), 'w',
                          encoding='utf-8'), ensure_ascii=False, indent=1)
    print(stats)


if __name__ == '__main__':
    main()
