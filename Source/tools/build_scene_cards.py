#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""场次卡：把「过场结构 + 台词」合成可直接用于叙事的卡片。

一张卡 = 一个过场，包含：
    · 所属任务 / 在任务里的播放顺序 / 过场时长 / 镜头数
    · 每镜：镜头号、相机是否存在、出场角色（中文名）、道具
    · 台词：顺序、说话人（中文）、原文

数据来源
    export/story/cutscene/structure/<包>.json     结构（分镜槽 / 演员 / 道具）
    export/story/beats/<任务>.json                 对话组台词 + 顺序
    export/story/speaker_overrides.json            每句说话人
    export/story/cutscene/mission_timeline.json    任务内播放顺序

输出
    export/story/cutscene/scene_cards.json
    export/story/cutscene/scene_cards.html
"""
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CS = os.path.join(ROOT, 'export', 'story', 'cutscene')
STORY = os.path.join(ROOT, 'export', 'story')
BEATS = os.path.join(STORY, 'beats')

# 模型名 → 中文名（用 project 里现成的映射，缺的保留原名）
NAME_MAP = {}
ALIAS = {}


def load_names():
    idx = os.path.join(ROOT, 'export', 'npc', 'index.csv')
    if os.path.exists(idx):
        import csv
        for r in csv.DictReader(open(idx, encoding='utf-8-sig')):
            nm = (r.get('name') or '').strip()
            cn = (r.get('cn_name') or '').strip()
            if nm and cn:
                NAME_MAP.setdefault(nm, cn)
                base = re.sub(r'_[mf]s\d+$', '', nm)     # cs_abe_ms1 → cs_abe
                NAME_MAP.setdefault(base, cn)
    return NAME_MAP


def zh(model):
    """cs_dutch → 达奇·范德林德（取不到就保留原名）"""
    m = NAME_MAP.get(model)
    if m:
        return m
    base = model.split('_ms')[0].split('_fs')[0]
    return NAME_MAP.get(base, model)


def humanize(model):
    """cs_tomdickens → Tom Dickens（没中文名时的兜底，至少可读）"""
    m = re.sub(r'^(cs_|u_m_m_|u_f_m_|s_m_|s_f_|player_|mp_|g_m_|g_f_)', '', model)
    m = re.sub(r'_[mf]s\d+$', '', m)
    parts = re.split(r'[_.]', m)
    return ' '.join(p.capitalize() for p in parts if p) or model


def actor_zh(model):
    n = zh(model)
    if n == model:                      # 没有中文名 → 用可读的英文名
        return humanize(model)
    return n.split('·')[0] if '·' in n else n


def alias_map():
    """脚本里的过场名（WNT1_INT_CABIN）→ 资产里的真实 id（wnt1_int_col）"""
    import sys as _s
    _s.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cutscene_structure import ids_from_clips, CLIP_RX
    out = {}
    for f in glob.glob(os.path.join(ROOT, 'work', 'story', 'cutscene_all', 'extracted',
                                    'cuts_*', '*.ycd')):
        data = open(f, 'rb').read()
        ids = ids_from_clips([m.group(1).decode('latin1') for m in CLIP_RX.finditer(data)])
        if ids:
            out[os.path.splitext(os.path.basename(f))[0].upper()] = ids[0].upper()
    return out


def structure():
    out = {}
    for f in os.listdir(os.path.join(CS, 'structure')):
        if not f.startswith('cuts_'):
            continue
        d = json.load(open(os.path.join(CS, 'structure', f), encoding='utf-8'))
        for s in d.get('scenes', []):
            out[s['cutscene'].upper()] = s
    return out


def beats():
    out = {}
    for f in os.listdir(BEATS):
        if not f.endswith('.json'):
            continue
        b = json.load(open(os.path.join(BEATS, f), encoding='utf-8'))
        out[b['id']] = b
    return out


def script_to_mission():
    """winter1 → WNT1（script_map.json 是 任务码 → [脚本文件, ...]）"""
    p = os.path.join(STORY, 'script_map.json')
    out = {}
    if os.path.exists(p):
        d = json.load(open(p, encoding='utf-8'))
        for mid, v in d.items():
            f = v[0] if isinstance(v, list) and v else ''
            if f:
                out[os.path.splitext(f)[0]] = mid
    return out


def find_beat(bt, mission):
    """任务 id 可能带尾数字（RABI21 vs RABI1），做前缀兜底"""
    if mission in bt:
        return bt[mission]
    cands = [k for k in bt if mission.startswith(k) or k.startswith(mission)]
    if cands:
        return bt[max(cands, key=len)]
    return {}


def main():
    load_names()
    st = structure()
    global ALIAS
    ALIAS = alias_map()
    s2m = script_to_mission()
    bt = beats()
    ov = json.load(open(os.path.join(STORY, 'speaker_overrides.json'), encoding='utf-8'))
    mt = json.load(open(os.path.join(CS, 'mission_timeline.json'), encoding='utf-8'))

    cards = []
    for script, seq in mt.items():
        mission = None
        for it in seq['cutscenes']:
            key = it['name'].upper()
            s = st.get(key) or st.get(ALIAS.get(key, ''))
            if not s:
                continue
            mission = mission or s['mission']
            b = find_beat(bt, s2m.get(script, s['mission']))
            convs = b.get('conversations') or {}
            conv = convs.get(it['name'])
            if conv is None:            # 名字对不上时按前缀找最接近的对话组
                cand = [g for g in convs if g.upper().startswith(it['name'].upper()[:10])]
                conv = convs[cand[0]] if len(cand) == 1 else []
            lines = []
            for ln in (conv or []):
                sp = (ov.get(s['mission'], {}).get(it['name']) or {}).get(str(ln['n'])) \
                    or (ov.get(s['mission'], {}).get('*') or {}).get(str(ln['n'])) or ''
                lines.append(dict(n=ln['n'], speaker=sp, zh=ln['zh']))
            shots = []
            for sh in s.get('shots', []):
                actors = [actor_zh(a) for a in sh['actors'] if a.startswith(('cs_', 'player_'))]
                props = [a for a in sh['actors'] if a.startswith(('p_', 's_', 'w_', 'v_'))]
                shots.append(dict(shot=sh['shot'], camera=sh['camera'],
                                  actors=actors, props=props[:8]))
            props_all = {p for sh in shots for p in sh['props']}
            weapons = [p for p in props_all if p.startswith('w_')]
            if weapons:
                tone = '战斗/对峙'
            elif any(('whiskey' in p or 'bottle' in p or 'beer' in p or 'wine' in p
                      or 'cigarette' in p or 'cigar' in p or 'matchstick' in p
                      or 'ashbucket' in p) for p in props_all):
                tone = '交谈/休整'
            elif any(p.startswith('p_c_horse') or 'horse' in p for p in props_all):
                tone = '赶路'
            else:
                tone = '其他'
            cards.append(dict(
                tone=tone, weapons=sorted(weapons)[:4],
                script=script, mission=s['mission'], cutscene=it['name'],
                order=it['order'], duration=it.get('duration') or s.get('duration_s'),
                shots_n=s['n_shots'], clips=s['clips'],
                shots=shots, lines=lines,
                cast=sorted({a for sh in shots for a in sh['actors']}),
                props=sorted({p for sh in shots for p in sh['props']}),
            ))
    json.dump(cards, open(os.path.join(CS, 'scene_cards.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    n_lines = sum(len(c['lines']) for c in cards)
    n_cast = len({a for c in cards for a in c['cast']})
    print('场次卡 %d 张 / 台词 %d 句 / 去重角色 %d 个' % (len(cards), n_lines, n_cast))
    print('示例:', [(c['cutscene'], c['cast'][:4], len(c['lines'])) for c in cards[:3]])


if __name__ == '__main__':
    main()
