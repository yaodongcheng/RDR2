#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""任务逐步骤拆解：按「目标函数被调用的顺序」把任务切成步骤。

原理：
  - 目标文本键（<MID>_OBJ*）落在某个 func_XXXX 里 → 这个函数就是“某一步”；
  - 该函数在主流程里被调用的最早行号，决定步骤顺序；
  - 步骤内的演员调度 = 该函数 + 直接调用的子函数里的 TASK_* / CREATE_*；
  - 步骤内的失败条件 = 同一函数里的 <MID>_FAIL* / LOST / DEAD 文本键。
"""
import csv
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from yldb_keys import Yldb  # noqa: E402

W = lambda *p: os.path.join(ROOT, *p)
SRC = W('work/script_probe/script_src')
LANG = W('work/story/lang/chinesesimp')

TASK_ZH = {
    'TASK_FOLLOW_NAV_MESH_TO_COORD': '沿导航网格走位',
    'TASK_FOLLOW_WAYPOINT_RECORDING': '沿路径点走位',
    'TASK_GO_TO_COORD_ANY_MEANS': '前往坐标',
    'TASK_GO_TO_COORD_WHILE_AIMING_AT_ENTITY': '边瞄准边移动',
    'TASK_PERFORM_SEQUENCE': '执行行为序列',
    'TASK_STAND_STILL': '原地站立',
    'TASK_PAUSE': '等待',
    'TASK_LOOK_AT_ENTITY': '看向实体',
    'TASK_TURN_PED_TO_FACE_ENTITY': '转身面向实体',
    'TASK_PUT_PED_DIRECTLY_INTO_COVER': '进入掩体',
    'TASK_COMBAT_HATED_TARGETS_AROUND_PED': '攻击周围敌人',
    'TASK_COMBAT_PED': '与 ped 战斗',
    'TASK_SWAP_WEAPON': '切换武器',
    'TASK_DISMOUNT_ANIMAL': '下马',
    'TASK_MOUNT_ANIMAL': '上马',
    'TASK_PLAY_ANIM': '播放动画',
    'TASK_USE_SCENARIO_POINT': '使用场景点',
    'TASK_SMART_FLEE_PED': '逃离',
    'TASK_ACHIEVE_HEADING': '转向',
    'TASK_HORSE_ACTION': '马匹动作',
}


def load_yldb(mid):
    base = mid.lower()
    for cand in (base, re.sub(r'\d$', '', base), re.sub(r'\d+$', '', base)):
        p = os.path.join(LANG, cand + '.yldb')
        if os.path.exists(p):
            return Yldb(p)
    return None


def clean(t):
    if not t:
        return ''
    t = re.sub(r'~[A-Za-z_]+(\|[^~]*)?~', '', t)
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
    mapping = json.load(open(W('work/script_probe/script_map_raw.json'), encoding='utf-8'))
    for k, v in {'RCLDN2': 'rcm_calderon2.c', 'RBNP21': 'rcm_beau_and_penelope21.c'}.items():
        if os.path.exists(os.path.join(SRC, v)):
            mapping[k] = [5, v]

    out = {}
    rows = []
    for r in recs:
        mid = r['id']
        if mid not in mapping:
            continue
        fname = mapping[mid][1]
        p = os.path.join(SRC, fname)
        if not os.path.exists(p):
            continue
        s = open(p, encoding='utf-8', errors='ignore').read()
        lines = s.split('\n')
        defs = parse_fns(lines)
        if not defs:
            continue
        y = load_yldb(mid)
        if not y:
            continue

        fn_ranges = {}
        for j, (st, name) in enumerate(defs):
            en = defs[j + 1][0] if j + 1 < len(defs) else len(lines)
            fn_ranges[name] = (st, en)

        # 目标键 → 函数
        by_fn = {}
        for m in re.finditer(r'"(' + re.escape(mid) + r'_OBJ[A-Z0-9_]*)"', s):
            line = s.count('\n', 0, m.start())
            fn = fn_at(defs, line)
            by_fn.setdefault(fn, []).append((m.group(1), line))

        steps = []
        for fn, ks in by_fn.items():
            texts, keys, lines_ = [], [], []
            for k, ln in ks:
                t = clean(y.get(k))
                if not t:
                    continue
                if k not in keys:
                    keys.append(k)
                if t not in texts:
                    texts.append(t)
                lines_.append(ln)
            if not texts:
                continue
            calls = [i for i, l in enumerate(lines)
                     if re.search(r'\b' + fn + r'\(', l)
                     and not re.match(r'^(?:void|int|float|bool|vector3|var|struct<[^>]*>)\s+' + fn, l)]
            caller = fn_at(defs, min(calls)) if calls else ''
            host = caller if caller in fn_ranges else fn
            st, en = fn_ranges[host]
            body = "\n".join(lines[st:en])
            callees = set(re.findall(r'\b(func_\d+)\(', body)) - {host}
            tasks = Counter()
            spawn_total = [0]

            def collect(name, depth, seen):
                if name in seen or depth < 0 or name not in fn_ranges:
                    return
                seen.add(name)
                b = "\n".join(lines[fn_ranges[name][0]:fn_ranges[name][1]])
                tasks.update(re.findall(r'TASK::(TASK_[A-Z_0-9]+)\(', b))
                spawn_total[0] += len(re.findall(r'(PED|VEHICLE|OBJECT)::CREATE_', b))
                for c in set(re.findall(r'\b(func_\d+)\(', b)) - {name}:
                    collect(c, depth - 1, seen)

            collect(host, 2, set())
            if not tasks:
                collect(host, 3, set())

            fails = []
            for m in re.finditer(r'"(' + re.escape(mid) + r'_[A-Z0-9_]*(?:FAIL|LOST|DEAD)[A-Z0-9_]*)"', body):
                t = clean(y.get(m.group(1)))
                if t and t not in fails:
                    fails.append(t)
            steps.append({
                'fn': fn,
                'call_line': (min(calls) + 1) if calls else None,
                'caller': caller,
                'line': min(lines_) + 1,
                'keys': keys[:4],
                'objectives': texts[:4],
                'tasks': sum(tasks.values()),
                'task_top': [[k, v] for k, v in tasks.most_common(4)],
                'spawns': spawn_total[0],
                'fails': fails[:6],
            })

        # 合并重复目标（同一目标键的多个函数只留一个），按调用行排序
        merged = {}
        for st in steps:
            k = st['keys'][0] if st['keys'] else st['fn']
            if k not in merged or (st['call_line'] or 10**9) < (merged[k]['call_line'] or 10**9):
                merged[k] = st
        steps = sorted(merged.values(), key=lambda x: (x['call_line'] if x['call_line'] is not None else 10**9, x['line']))

        if not steps:
            continue
        for i, st in enumerate(steps, 1):
            st['step'] = i
        out[mid] = {'script': fname, 'steps': steps}
        rows.append({'mission_id': mid, 'kind': r['kind'], 'chapter': r['chapter'],
                     'script': fname, 'steps': len(steps),
                     'step_titles': ' → '.join((s['objectives'][0] if s['objectives'] else s['fn']) for s in steps[:8])})

    json.dump(out, open(W('export/levels/world/mission_steps.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    with open(W('export/levels/world/mission_steps.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    print('逐步骤 %d 条任务，合计 %d 步' % (len(out), sum(len(v['steps']) for v in out.values())))


if __name__ == '__main__':
    main()
