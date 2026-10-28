#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""beat 表 → QuestGraph（骑砍2 可执行的任务图）。

输入  export/story/beats/<ID>.json
输出  export/story/questgraph/<ID>.json
      export/story/questgraph_index.csv

节点类型
  objective  目标        -> 骑砍2: Journal 条目 + 完成条件
  dialogue   对白组      -> 骑砍2: 场景内对话（逐句）
  cutscene   演出场景    -> 骑砍2: 镜头/演出（可跳过）
  spawn      生成        -> 骑砍2: 场景摆人

边
  seq     顺序边（case 内 / case 递进）
  jump    case 的 next 指向非相邻 case（分支/回环）
  fail    失败条件（挂在任务级）
"""
import argparse
import csv
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEATS = os.path.join(ROOT, 'export', 'story', 'beats')
OUT = os.path.join(ROOT, 'export', 'story', 'questgraph')


def case_nodes(m, seq_i, case):
    """把一个 case 的事件缩成节点序列（读 beats 原始格式）"""
    nodes = []
    num, c = case['case'], case
    nxt = c.get('next')
    obj_i = 0
    cut = []
    for e in c['events']:
        t = e['t']
        if t == 'objective' and e.get('zh'):
            obj_i += 1
            nodes.append({'type': 'objective', 'text': e['zh'], 'key': e.get('key'),
                          'id': f's{seq_i}c{num}o{obj_i}'})
        elif t == 'conv':
            lines = [x['zh'] for x in m['conversations'].get(e['group'], [])]
            nodes.append({'type': 'dialogue', 'group': e['group'], 'lines': lines,
                          'id': f's{seq_i}c{num}d{e["group"]}'})
        elif t == 'animscene':
            cut.append(e['name'])
        elif t == 'spawn' and e.get('model'):
            nodes.append({'type': 'spawn', 'model': e['model'],
                          'id': f's{seq_i}c{num}p{e["model"]}'})
    if cut:
        nodes.append({'type': 'cutscene', 'scenes': cut, 'id': f's{seq_i}c{num}cut'})
    return num, nxt, nodes


def build(m):
    nodes, edges = [], []
    used = set()
    first_of_case = {}
    prev = None
    seq_i = 0
    for seq in m['sequences']:
        seq_i += 1
        for case in seq['cases']:
            num, nxt, ns = case_nodes(m, seq_i, case)
            if not ns:
                continue
            for n in ns:
                while n['id'] in used:
                    n['id'] = n['id'] + '#2'
                used.add(n['id'])
                n['seq'] = seq['func']
                n['case'] = num
                nodes.append(n)
            first_of_case[(seq_i, num)] = ns[0]['id']
            if prev:
                edges.append({'from': prev, 'to': ns[0]['id'], 'kind': 'seq'})
            for a, b in zip(ns, ns[1:]):
                edges.append({'from': a['id'], 'to': b['id'], 'kind': 'seq'})
            prev = ns[-1]['id']
            # case 的 next 跳转（分支/回环）
            if nxt is not None and nxt >= 0 and nxt != num:
                tgt = first_of_case.get((seq_i, nxt))
                if tgt:
                    edges.append({'from': ns[-1]['id'], 'to': tgt, 'kind': 'jump',
                                  'case': num, 'next': nxt})
    return {
        'id': m['id'], 'title': m.get('title_zh'), 'chapter': m.get('chapter'),
        'category': m.get('category'),
        'confidence': {'cases': 'ordered', 'functions': 'chunked'}.get(
            m['stats'].get('structure'), 'content-only'),
        'nodes': nodes,
        'objectives_catalog': (m.get('objectives_all') or {}).get('objectives', []),
        'edges': edges,
        'fail': (m.get('objectives_all') or {}).get('fails', []),
        'cast': m.get('cast', [])[:24],
        'stats': {
            'nodes': len(nodes),
            'edges': len(edges),
            'objectives': sum(1 for n in nodes if n['type'] == 'objective'),
            'dialogues': sum(1 for n in nodes if n['type'] == 'dialogue'),
            'lines': sum(len(n.get('lines', [])) for n in nodes),
            'cutscenes': sum(1 for n in nodes if n['type'] == 'cutscene'),
            'jumps': sum(1 for e in edges if e['kind'] == 'jump'),
        },
    }


def validate(g):
    ids = {n['id'] for n in g['nodes']}
    dangling = [e for e in g['edges'] if e['from'] not in ids or e['to'] not in ids]
    dup = len(g['nodes']) - len(ids)
    return {'dangling': len(dangling), 'dup_ids': dup}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    rows = []
    bad = 0
    for f in sorted(glob.glob(os.path.join(BEATS, '*.json'))):
        m = json.load(open(f, encoding='utf-8'))
        g = build(m)
        v = validate(g)
        if v['dangling'] or v['dup_ids']:
            bad += 1
            print(f'!! {g["id"]} dangling={v["dangling"]} dup={v["dup_ids"]}')
        g['stats'].update(v)
        json.dump(g, open(os.path.join(args.out, f'{m["id"]}.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        rows.append({'id': g['id'], 'title': g['title'], 'category': g['category'],
                     'confidence': g['confidence'], **g['stats']})
    with open(os.path.join(ROOT, 'export/story/questgraph_index.csv'), 'w',
              newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    tot = {k: sum(r[k] for r in rows) for k in
           ('nodes', 'edges', 'objectives', 'dialogues', 'lines', 'cutscenes', 'jumps')}
    print(f'{len(rows)} graphs -> {args.out}')
    print('total', tot, 'invalid', bad)


if __name__ == '__main__':
    main()
