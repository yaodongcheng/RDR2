#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""RDR2 随机遭遇（roadside encounters）模板提取。

和主线不同：随机遭遇**没有专属对白库**，靠通用 ambient speech + 任务模型池 + 行为脚本。
所以要还原它，需要的不是"台词"，而是**模板**：
    在哪出现（哪类地形/道路）、刷几个什么人、什么马、拿什么枪、怎么演（伏击/抢劫/陷阱）

输入  raw/script_full/1491.50/{ambush_,event_,discoverable_}*.c
输出  export/story/encounters.json / .csv / 汇总 md
"""
import json
import os
import re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'raw', 'script_full', '1491.50')
OUT = os.path.join(ROOT, 'export', 'story')

PED = re.compile(r'"([AGS]_[MC]_[MF]_[A-Z0-9_]+)"')
HORSE = re.compile(r'"A_C_[A-Z_0-9]+"')
VEH = re.compile(r'"([A-Z_]*WAGON[A-Z_0-9]*|COACH[A-Z_0-9]*|[A-Z_]*CART[A-Z_0-9]*)"')
WEAP = re.compile(r'"(WEAPON_[A-Z0-9_]+)"')
TASK = re.compile(r'TASK::([A-Z_0-9]+)')
SPEECH = re.compile(r'"(SPEECH_PARAMS_[A-Z_0-9]+)"')
CTX = re.compile(r'"(AMBUSH_[A-Z0-9_]+|SHORT_TIMED_EVENT|EVENT_[A-Z0-9_]+)"')
CASES = re.compile(r'^\s*case\s+(-?\d+)\s*:', re.M)

# 模型名前缀 → 势力/身份（RDR2 ped 命名规则）
FACTION = {
    'UNIBANDITOS': 'Del Lobos 匪帮', 'UNIDUSTER': '农场帮工/乡民', 'UNIRANCHERS': '牧场主',
    'UNIMOUNTAINMEN': '山地人', 'UNIINBRED': '畸形家族（Aberdeen 一类）',
    'UNICRIMINALS': '罪犯/流浪汉', 'UNICORPSE': '尸体', 'UNIEXCONFEDS': '前邦联军',
    'UNICIVILWAR': '内战士兵', 'UNIWARVET': '退伍兵', 'UNICLAY': '粘土矿工',
    'UNIGUARD': '守卫', 'UNILAW': '执法者', 'UNIPINKERTON': '平克顿侦探',
    'UNISAVVY': '边境客', 'UNISKINNER': '剥皮帮', 'UNITOWN': '城镇居民',
    'UNIARTIST': '艺人', 'UNIFARMER': '农夫', 'UNIHUNTER': '猎人',
}


def classify(name):
    n = name.lower()
    for k in ('bridge_trap', 'wagon_bomb', 'wagon_turret', 'sniper', 'lookout', 'road_robbery',
              'road_prec', 'road_attack', 'forest', 'cliff', 'corner', 'tree_line', 'harass',
              'river', 'ride_out', 'hide_cover', 'hso', 'prevent', 'night_rob', 'type1'):
        if k in n:
            return k
    return 'other'


def faction_of(model):
    m = model.upper()
    for k, v in FACTION.items():
        if k in m:
            return v
    if m.startswith('A_C_'):
        return '动物/马'
    return '通用'


PREFIX = {
    'bnd': '匪帮（BND bandit）', 'exc': '前邦联军 / 铁路劫匪（EXC）',
    'inb': '近亲家族 / 猪场一族（INB inbred）', 'odr': '奥德里斯科帮（ODR）',
    'sav': '剥皮帮 / 野蛮人（SAV）', 'pnk': '平克顿侦探（PNK）',
    'rnc': '牧场主（RNC rancher）', 'gen': '通用路人（GEN）',
}


def main():
    files = sorted(f for f in os.listdir(SRC)
                   if f.endswith('.c') and re.match(r'(ambush_|event_|discoverable_)', f))
    out = []
    for f in files:
        txt = open(os.path.join(SRC, f), encoding='utf-8', errors='ignore').read()
        peds = Counter(PED.findall(txt))
        horses = Counter(HORSE.findall(txt))
        vehs = Counter(VEH.findall(txt))
        weaps = Counter(WEAP.findall(txt))
        tasks = Counter(TASK.findall(txt))
        speech = Counter(SPEECH.findall(txt))
        ctx = Counter(CTX.findall(txt))
        fams = Counter(faction_of(m) for m in peds)
        out.append({
            'script': f[:-2],
            'kind': f.split('_')[0],
            'archetype': classify(f),
            'faction': (PREFIX.get(f.split('_')[1], f.split('_')[1])
                        if f.startswith('ambush_') else '—'),
            'spawn_calls': txt.count('CREATE_PED('),
            'lines': txt.count('\n'),
            'ped_models': [m for m, _ in peds.most_common(14)],
            'ped_pool_size': len(peds),
            'ped_factions': [k for k, _ in fams.most_common(4)],
            'horses': [m for m, _ in horses.most_common(5)],
            'vehicles': [m for m, _ in vehs.most_common(4)],
            'weapons': [m for m, _ in weaps.most_common(6)],
            'top_tasks': [k for k, _ in tasks.most_common(8)],
            'speech_ctx': [k for k, _ in speech.most_common(4)],
            'event_ctx': [k for k, _ in ctx.most_common(4)],
            'case_count': len(CASES.findall(txt)),
        })
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, 'encounters.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    import csv
    cols = ['script', 'kind', 'archetype', 'faction', 'lines', 'spawn_calls', 'ped_pool_size',
            'ped_factions', 'ped_models', 'horses', 'vehicles', 'weapons', 'top_tasks',
            'speech_ctx', 'event_ctx', 'case_count']
    with open(os.path.join(OUT, 'encounters.csv'), 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in out:
            w.writerow([';'.join(map(str, r[c])) if isinstance(r[c], list) else r[c] for c in cols])
    print(f'{len(out)} encounter scripts -> {OUT}/encounters.json')


if __name__ == '__main__':
    main()
