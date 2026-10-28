#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""为每个任务生成「事后总结 / 剧情回顾」文本（无法播放演出时给玩家看）。

素材全部来自已解数据：
  官方简介（missions_story.desc_zh）
  beat 表里的目标 + 对白（按剧本顺序）
  失败条件

输出 export/story/recaps.json：{ id: {title, chapter, summary, outline:[...], ending} }
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY = os.path.join(ROOT, 'export', 'story')

CHOICE = ('问他', '问她', '接受', '拒绝', '威胁', '给他', '给她', '收下', '离开', '同意', '反驳')


def is_choice(t):
    t = (t or '').strip()
    return any(t.startswith(c) for c in CHOICE) and len(t) <= 24


OV = {}


def spoken(mid, group, idx, text):
    who = (OV.get(mid) or {}).get(group, {}).get(str(idx + 1))
    return f'{who}：{text}' if who else text


def build_from_graph(g, meta, conv):
    stanzas = []
    cur = None
    for n in g['nodes']:
        t = n['type']
        if t == 'objective' and n.get('text'):
            if cur:
                stanzas.append(cur)
            cur = {'obj': n['text'], 'lines': [], 'scene': None}
        elif t == 'dialogue':
            lines = [x for x in conv.get(n['group'], []) if not is_choice(x['zh'])]
            if not lines:
                continue
            if cur is None:
                cur = {'obj': '', 'lines': [], 'scene': None}
            for x in lines[:2]:
                t = spoken(g['id'], n['group'], x['n'] - 1, x['zh'])
                if t not in cur['lines']:
                    cur['lines'].append(t)
            if len(cur['lines']) >= 2:
                stanzas.append(cur)
                cur = {'obj': '', 'lines': [], 'scene': None}
        elif t == 'cutscene' and cur is not None and not cur['scene']:
            cur['scene'] = (n.get('scenes') or [''])[0]
    if cur and (cur['obj'] or cur['lines']):
        stanzas.append(cur)
    # 去掉与上一条完全重复的台词块（分支/复用导致）
    ded = []
    seen_line_sets = []
    for st in stanzas:
        if not (st['obj'] or st['lines']):
            continue
        if ded and st['obj'] and ded[-1]['obj'] == st['obj'] and not st['lines']:
            continue
        if st['lines'] and st['lines'] in seen_line_sets:
            continue
        if st['lines']:
            seen_line_sets.append(st['lines'])
        if ded and st['obj'] and ded[-1]['obj'] == st['obj']:
            ded[-1]['lines'] = ded[-1]['lines'] or st['lines']
            continue
        ded.append(st)
    stanzas = ded[:12]
    ending = ''
    for st in reversed(stanzas):
        if st['lines']:
            ending = st['lines'][-1]
            break
    return {
        'id': g['id'], 'title': meta.get('title_zh') or g['id'],
        'chapter': meta.get('chapter_name') or '', 'category': meta.get('category') or '',
        'summary': (meta.get('desc_zh') or '')[:300],
        'stanzas': stanzas, 'ending': ending,
        'confidence': g.get('confidence'),
        'fail': (meta.get('objectives_all') or {}).get('fails', [])[:5],
        'cast': (meta.get('cast') or [])[:8],
    }


def build(m):
    outline = []
    seen_obj = set()
    for seq in m['sequences']:
        for case in seq['cases']:
            items = []
            for e in case['events']:
                if e['t'] == 'objective' and e.get('zh'):
                    txt = e['zh'].strip()
                    if txt in seen_obj:
                        continue
                    seen_obj.add(txt)
                    items.append(('obj', txt))
                elif e['t'] == 'conv':
                    lines = [x['zh'] for x in m['conversations'].get(e['group'], [])]
                    lines = [l for l in lines if not is_choice(l)]
                    if lines:
                        items.append(('say', lines[0], e['group'], len(lines)))
            # 同一 case 里只保留「目标 + 至少一句台词」
            if any(k == 'obj' for k, *_ in items) and len(items) > 1:
                outline.append([x for x in items if x[0] == 'obj'][:1] +
                               [x for x in items if x[0] == 'say'][:2])
            elif any(k == 'obj' for k, *_ in items):
                outline.append([x for x in items if x[0] == 'obj'][:1])
    # 合并相邻重复
    flat = []
    for step in outline:
        flat.append(step)
    ending = ''
    for step in reversed(flat):
        says = [x for x in step if x[0] == 'say']
        if says:
            ending = says[-1][1]
            break
    return {
        'id': m['id'],
        'title': m.get('title_zh') or m['id'],
        'chapter': m.get('chapter_name') or '',
        'category': m.get('category') or '',
        'summary': (m.get('desc_zh') or '')[:300],
        'outline': flat[:14],
        'ending': ending,
        'fail': (m.get('objectives_all') or {}).get('fails', [])[:5],
        'cast': (m.get('cast') or [])[:8],
    }


def main():
    global OV
    _ovp = os.path.join(STORY, 'speaker_overrides.json')
    OV = json.load(open(_ovp, encoding='utf-8')) if os.path.exists(_ovp) else {}
    meta = {r['id']: r for r in json.load(
        open(os.path.join(ROOT, 'export/levels/world/missions_story.json'), encoding='utf-8'))}
    out = []
    for f in glob.glob(os.path.join(STORY, 'questgraph', '*.json')):
        g = json.load(open(f, encoding='utf-8'))
        b = json.load(open(os.path.join(STORY, 'beats', f"{g['id']}.json"), encoding='utf-8'))
        conv = {k: v for k, v in b['conversations'].items()}
        out.append(build_from_graph(g, meta.get(g['id'], {}), conv))
    order = {'CHAPTER_1': 1, 'CHAPTER_2': 2, 'CHAPTER_3': 3, 'CHAPTER_4': 4, 'CHAPTER_5': 5,
             'CHAPTER_6': 6, 'CHAPTER_7': 7, 'CHAPTER_8': 8}
    out.sort(key=lambda r: (order.get(r['category'], 90), r['title']))
    json.dump(out, open(os.path.join(STORY, 'recaps.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    n = sum(1 for r in out if r['stanzas'])
    print(f'{len(out)} recaps ({n} with outline) -> export/story/recaps.json')


if __name__ == '__main__':
    main()
