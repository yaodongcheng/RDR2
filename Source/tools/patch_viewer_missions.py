#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 missions_story.json 的中文标题/简介/挑战/角色名合并进查看器 data.json。"""
import csv
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)


def main():
    data = json.load(open(W('export/viewer/data.json'), encoding='utf-8'))
    story = {r['id']: r for r in json.load(open(W('export/levels/world/missions_story.json'), encoding='utf-8'))}
    objs = json.load(open(W('export/levels/world/mission_objectives.json'), encoding='utf-8'))
    scripts = json.load(open(W('export/levels/world/mission_scripts.json'), encoding='utf-8'))
    sched = json.load(open(W('export/levels/world/mission_schedule.json'), encoding='utf-8'))
    steps = json.load(open(W('export/levels/world/mission_steps.json'), encoding='utf-8'))
    dlg = json.load(open(W('export/levels/world/mission_dialogues.json'), encoding='utf-8'))
    events = json.load(open(W('export/levels/world/mission_events.json'), encoding='utf-8'))
    tree = json.load(open(W('export/levels/world/mission_tree.json'), encoding='utf-8'))
    roster = {}
    for r in csv.DictReader(open(W('export/levels/world/npc_roster.csv'), encoding='utf-8-sig')):
        roster[r['id']] = r['name_zh'] or r['name_en'] or r['id']
    roster['player_zero'] = '亚瑟·摩根'
    roster['player_three'] = '约翰·马斯顿'

    def cast_name(c):
        if c in roster:
            return roster[c]
        if c.startswith('cs_genstory'):
            return '通用剧情角色'
        if c.startswith('cs_'):
            return '（角色型）' + re.sub(r'_(ms1|fs1)$', '', c[3:])
        return c

    n = 0
    for m in data['missions']:
        s = story.get(m['id'])
        if not s:
            continue
        m['title'] = s['title_zh'] or s['title_en'] or ''
        m['title_en'] = s['title_en']
        m['desc'] = s['desc_zh'] or s['desc_en'] or ''
        m['chapter'] = s['chapter']
        m['chapter_name'] = s['chapter_name']
        m['order'] = s['order']
        m['challenges'] = s['challenges']
        m['cutscene_clips'] = s.get('cutscene_clips', 0)
        m['cast_names'] = [cast_name(c) for c in m.get('cast', [])]
        o = objs.get(m['id'])
        m['objectives'] = o['objective'] if o else []
        m['fail_conditions'] = o['fail'] if o else []
        sv = scripts.get(m['id'])
        if sv:
            m['script_file'] = sv['script']
            m['script_lines'] = sv['lines']
            m['script_funcs'] = sv['funcs']
            m['script_objectives'] = [x['text'] for x in sv['objectives']]
            m['script_fails'] = [x['text'] for x in sv['fails']]
            m['script_spawn'] = sv['spawn']
            m['script_cutscenes'] = sv['cutscenes'][:3]
        sv2 = sched.get(m['id'])
        if sv2:
            m['schedule_spawn'] = sv2['spawn_counts']
            m['schedule_task_calls'] = sum(sv2['task_counts'].values())
            m['schedule_task_types'] = len(sv2['task_counts'])
            m['schedule_task_top'] = [[k, v] for k, v in list(sv2['task_counts'].items())[:8]]
            st = [x for x in sv2['stages'] if x['spawns'] + x['tasks'] > 0]
            m['schedule_stages'] = [{'fn': x['fn'], 'objectives': x['objectives'][:2],
                                     'keys': x['keys'][:2], 'spawns': x['spawns'],
                                     'tasks': x['tasks']} for x in st[:6]]
            m['schedule_anim'] = sv2['anim_calls']
            m['schedule_density'] = sv2['density']
        sv3 = steps.get(m['id'])
        if sv3:
            m['steps'] = [{'n': x['step'], 'objective': (x['objectives'][0] if x['objectives'] else x['fn']),
                           'objectives': x['objectives'], 'tasks': x['tasks'], 'spawns': x['spawns'],
                           'caller': x['caller'] or x['fn']}
                          for x in sv3['steps']]
        dx = dlg.get(m['id'])
        if dx:
            m['dialogue_steps'] = {str(k): [{'name': c['name'], 'lines': c['lines'][:20],
                                             'conditional': c['conditional']} for c in v]
                                   for k, v in dx['steps'].items()}
            m['dialogue_unassigned'] = [{'name': c['name'], 'lines': c['lines'][:20],
                                         'conditional': c['conditional']} for c in dx['unassigned']]
        tr = tree.get(m['id'])
        if tr:
            m['tree'] = [{'step': x['step'], 'objectives': x['objectives'], 'events': x['events'],
                          'cases': [{'label': c['label'], 'events': [{'seq': e['seq'], 'type': e['type'],
                                                                     'action': e['action'], 'args': e['args'][:120],
                                                                     'lines': e.get('lines', [])[:12],
                                                                     'kind': e.get('kind',''), 'speaker': e.get('speaker',''),
                                                                     'value': e.get('value',''), 'actor': e.get('actor',''),
                                                                     'cond': e.get('cond','')[:60]} for e in c['events'][:90]]}
                                    for c in x['cases']]} for x in tr['steps']]
        ex = events.get(m['id'])
        if ex:
            m['step_events'] = {str(k): [{'seq': e['seq'], 'type': e['type'], 'actor': e.get('actor', ''),
                                          'action': e['action'], 'args': e['args'][:160],
                                          'value': e.get('value', ''), 'why': e.get('why', ''),
                                          'cond': e['cond'][:80]} for e in v[:80]]
                                for k, v in ex['steps'].items()}
        n += 1

    data['missions'].sort(key=lambda m: (0 if m.get('chapter') else 1,
                                         m.get('chapter') or 99,
                                         m.get('order') or 99, m['id']))
    json.dump(data, open(W('export/viewer/data.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print('merged', n, 'missions')


if __name__ == '__main__':
    main()
