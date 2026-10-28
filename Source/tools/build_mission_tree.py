#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把任务组织成树：总任务 → 大步骤（阶段函数）→ 小步骤（switch case）→ 具体执行（事件）。"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)
SRC = W('work/script_probe/script_src')

DEF_RX = re.compile(r'^(?:void|int|float|bool|var|[Vv]ector3|struct<[^>]*>)\s+(func_\d+)\s*\(')
CASE_RX = re.compile(r'^\s*case (\d+):')


def parse_funcs(lines):
    defs = []
    for i, l in enumerate(lines):
        m = DEF_RX.match(l)
        if m:
            defs.append((i, m.group(1)))
    rng = {}
    for j, (st, n) in enumerate(defs):
        en = defs[j + 1][0] if j + 1 < len(defs) else len(lines)
        rng[n] = (st, en)
    return rng


def main():
    steps_all = json.load(open(W('export/levels/world/mission_steps.json'), encoding='utf-8'))
    events_all = json.load(open(W('export/levels/world/mission_events.json'), encoding='utf-8'))
    dlg_all = json.load(open(W('export/levels/world/mission_dialogues.json'), encoding='utf-8'))
    mapping = json.load(open(W('work/script_probe/script_map_raw.json'), encoding='utf-8'))
    for k, v in {'RCLDN2': 'rcm_calderon2.c', 'RBNP21': 'rcm_beau_and_penelope21.c'}.items():
        if os.path.exists(os.path.join(SRC, v)):
            mapping[k] = [5, v]

    out = {}
    for mid, data in steps_all.items():
        if mid not in events_all or mid not in mapping:
            continue
        lines = open(os.path.join(SRC, mapping[mid][1]), encoding='utf-8', errors='ignore').read().split('\n')
        rng = parse_funcs(lines)
        ev_steps = events_all[mid]['steps']
        tree_steps = []
        for st in data['steps']:
            host = st['caller'] if st.get('caller') in rng else st['fn']
            if host not in rng:
                continue
            s0, e0 = rng[host]
            body = lines[s0:e0]
            cases = []
            sw = next((i for i, l in enumerate(body) if l.strip().startswith('switch (')), None)
            if sw is not None:
                starts = [(i, int(m.group(1))) for i, l in enumerate(body) if (m := CASE_RX.match(l))]
                for j, (ci, num) in enumerate(starts):
                    ce = starts[j + 1][0] if j + 1 < len(starts) else len(body)
                    cases.append({'label': 'case %d' % num, 'start': s0 + ci + 1, 'end': s0 + ce})
            evs = [dict(e) for e in ev_steps.get(str(st['step']), [])]
            # 并入对白对话组：触发行落在 case 范围内
            dlg = dlg_all.get(mid, {}).get('steps', {}).get(str(st['step']), [])
            CHOICE_VERBS = ('问', '说', '告诉', '回答', '答应', '拒绝', '威胁', '劝', '请', '帮',
                            '去', '跟', '拿', '给', '放', '检查', '搜', '救', '杀', '付', '买', '卖')
            for c in dlg:
                for li, line in enumerate(c['lines'], 1):
                    body = line.strip('。！？ ')
                    is_choice = (len(body) <= 14 and body.startswith(CHOICE_VERBS)
                                 and not any(x in body for x in ('我', '你', '亚瑟', '迈卡', '达奇', '先生', '伙计', '我们')))
                    kind = '选项候选' if is_choice else '台词'
                    evs.append({
                        'seq': 0, 'call_line': c['line'], 'src_line': c['line'], 'fn': c.get('fn', ''),
                        'type': '对白', 'action': c['name'], 'actor': '',
                        'speaker': ('玩家（选项）' if kind == '选项候选' else ''),
                        'args': line, 'lines': c['lines'], 'line_no': li, 'kind': kind,
                        'value': 'S', 'why': '任务对白',
                        'cond': '条件触发' if c.get('conditional') else '',
                    })
            evs.sort(key=lambda e: (e['call_line'], 0 if e['type'] != '对白' else 1))
            for i, e in enumerate(evs, 1):
                e['seq'] = i
            if cases:
                for c in cases:
                    c['events'] = [e for e in evs if c['start'] <= e['call_line'] < c['end']]
                placed = {id(e) for c in cases for e in c['events']}
                pre = [e for e in evs if e['call_line'] < cases[0]['start'] and id(e) not in placed]
                if pre:
                    cases.insert(0, {'label': '前置', 'start': s0 + 1, 'end': cases[0]['start'], 'events': pre})
                    placed |= {id(e) for e in pre}
                rest = [e for e in evs if id(e) not in placed]
                # 对白触发在目标函数里：归到“前置”（阶段初始化）
                dlg_match = [e for e in rest if e['type'] == '对白' and e.get('fn') in (st['fn'], st['caller'])]
                if dlg_match:
                    rest = [e for e in rest if e not in dlg_match]
                    if cases and cases[0]['label'] == '前置':
                        cases[0]['events'] += dlg_match
                    else:
                        cases.insert(0, {'label': '前置', 'start': 0, 'end': 0, 'events': dlg_match})
                if rest:
                    label = '对白' if all(e['type'] == '对白' for e in rest) else '其他'
                    cases.append({'label': label, 'start': 0, 'end': 0, 'events': rest})
            else:
                cases = [{'label': '主体', 'start': s0 + 1, 'end': e0, 'events': evs}]
            tree_steps.append({
                'step': st['step'], 'objectives': st['objectives'], 'fn': st['fn'],
                'caller': st['caller'], 'call_line': st['call_line'],
                'events': len(evs),
                'cases': [{'label': c['label'], 'line': c['start'], 'events': c['events']} for c in cases],
            })
        if tree_steps:
            out[mid] = {'script': mapping[mid][1], 'steps': tree_steps}

    json.dump(out, open(W('export/levels/world/mission_tree.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('任务树 %d 个任务；节点 %d 步 / %d 小步' % (
        len(out), sum(len(v['steps']) for v in out.values()),
        sum(len(s['cases']) for v in out.values() for s in v['steps'])))


if __name__ == '__main__':
    main()
