#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把任务对白按“对话组”拆开，并归属到步骤。

原理：
  - 脚本里用字符串触发对话组，如 "WNT1_SHORT"、"WNT1_BANT3"；
  - 字幕在任务音频库 `<id>aud.yldb` 里按 `WNT1_SHORT_1`、`_2` … 编号；
  - 触发所在函数如果等于某一步的目标函数/阶段函数，就归属到该步骤；
    否则放进“环境/条件对白”桶。
"""
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from yldb_keys import Yldb  # noqa: E402

W = lambda *p: os.path.join(ROOT, *p)
SRC = W('work/script_probe/script_src')
LANG = W('work/story/lang/chinesesimp')

COND_HINT = ('BANT', 'GREET', 'EXTRA', 'TAUNT', 'AMBIENT', 'SHOUT', 'CHAT', 'IDLE')


def clean(t):
    if not t:
        return ''
    t = re.sub(r'~[A-Za-z_]+[^~]*~', '', t)
    return re.sub(r'\s+', ' ', t).strip()


def parse_fns(lines):
    defs = []
    for i, l in enumerate(lines):
        m = re.match(r'^(?:void|int|float|bool|vector3|var|struct<[^>]*>)\s+(func_\d+)\s*\(', l)
        if m:
            defs.append((i, m.group(1)))
    return defs


def fn_at(defs, line):
    cur = '?'
    for i, n in defs:
        if i <= line:
            cur = n
        else:
            break
    return cur


def main():
    recs = json.load(open(W('export/levels/world/missions_story.json'), encoding='utf-8'))
    steps_all = json.load(open(W('export/levels/world/mission_steps.json'), encoding='utf-8'))
    mapping = json.load(open(W('work/script_probe/script_map_raw.json'), encoding='utf-8'))
    banks = {r['mission_id']: r['audio_bank'] for r in
             csv.DictReader(open(W('export/levels/world/mission_dialogue_index.csv'), encoding='utf-8-sig'))}

    out = {}
    total_conv = 0
    total_lines = 0
    for r in recs:
        mid = r['id']
        if mid not in mapping or mid not in steps_all:
            continue
        bank = banks.get(mid)
        if not bank:
            continue
        p = os.path.join(LANG, bank)
        if not os.path.exists(p):
            continue
        y = Yldb(p)
        s = open(os.path.join(SRC, mapping[mid][1]), encoding='utf-8', errors='ignore').read()
        lines = s.split('\n')
        defs = parse_fns(lines)
        steps = steps_all[mid]['steps']
        by_step = {}
        unassigned = []

        literals = sorted(set(re.findall(r'"([A-Z][A-Z0-9_]{2,40})"', s)))
        for k in literals:
            if not y.get(k + '_1'):
                continue
            texts = []
            n = 1
            while n <= 80:
                t = y.get(f'{k}_{n}')
                if not t:
                    break
                texts.append(clean(t))
                n += 1
            if not texts:
                continue
            pos = s.find('"' + k + '"')
            ln = s.count('\n', 0, pos) + 1
            fn = fn_at(defs, ln - 1)
            line_txt = lines[ln - 1] if 0 <= ln - 1 < len(lines) else ''
            conditional = ('if (' in line_txt or any(h in k for h in COND_HINT))
            conv = {'name': k, 'lines': texts, 'fn': fn, 'line': ln, 'conditional': conditional}
            target = None
            for st in steps:
                if fn in (st['fn'], st['caller']):
                    target = st['step']
                    break
            if target:
                by_step.setdefault(target, []).append(conv)
            else:
                unassigned.append(conv)
            total_conv += 1
            total_lines += len(texts)

        if not by_step and not unassigned:
            continue
        out[mid] = {'bank': bank, 'steps': by_step, 'unassigned': unassigned}

    json.dump(out, open(W('export/levels/world/mission_dialogues.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    rows = []
    for mid, v in out.items():
        for step, convs in v['steps'].items():
            for c in convs:
                rows.append({'mission_id': mid, 'step': step, 'conversation': c['name'],
                             'conditional': 'Y' if c['conditional'] else 'N',
                             'lines': len(c['lines']), 'first_line': c['lines'][0] if c['lines'] else ''})
        for c in v['unassigned']:
            rows.append({'mission_id': mid, 'step': '', 'conversation': c['name'],
                         'conditional': 'Y' if c['conditional'] else 'N',
                         'lines': len(c['lines']), 'first_line': c['lines'][0] if c['lines'] else ''})
    if rows:
        with open(W('export/levels/world/mission_dialogues.csv'), 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
    print('对话归属 %d 个任务，%d 个对话组，%d 行' % (len(out), total_conv, total_lines))


if __name__ == '__main__':
    main()
