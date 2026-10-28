#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""微观事件抽取：把阶段函数按调用树展开成事件流。

每个事件记录：调用序号、调用行、源码行、所在函数、类型、参数（坐标已解析）、最近条件。
这是“静态执行顺序”的近似：按代码调用顺序深度优先展开，不模拟运行时分支。
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)
SRC = W('work/script_probe/script_src')

DEF_RX = re.compile(r'^(?:void|int|float|bool|var|[Vv]ector3|struct<[^>]*>)\s+(func_\d+)\s*\(')
TASK_RX = re.compile(r'TASK::(TASK_[A-Z_0-9]+)\(')
CREATE_RX = re.compile(r'(PED|VEHICLE|OBJECT)::(CREATE_[A-Z_0-9]+)\(')
UILOG_RX = re.compile(r'UILOG::(_UILOG_[A-Z_0-9]+)\(')
TRANS_RX = re.compile(r'func_134\(cParam0,\s*(\d+)\)')
ANIM_RX = re.compile(r'ANIMSCENE::([A-Z_0-9]+)\(')
COORD_RX = re.compile(r'func_473\((\d+),\s*(\d+)\)')
CONV_RX = re.compile(r'"([A-Z][A-Z0-9_]{2,40})"')

SKIP_FUNCS = {'func_473', 'func_1013', 'func_494', 'func_1936', 'func_1331', 'func_1332'}


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
    return defs, rng


def parse_coords(lines, rng):
    if 'func_1013' not in rng:
        return {}
    st, en = rng['func_1013']
    out = {}
    i = None
    for k in range(st, en):
        m = re.match(r'\s*case (\d+):', lines[k])
        if m:
            i = int(m.group(1))
            continue
        m = re.search(r'return (-?\d+\.?\d*)f?,\s*(-?\d+\.?\d*)f?,\s*(-?\d+\.?\d*)f?;', lines[k])
        if m and i is not None:
            j = sum(len(v) for v in out.values()) if False else None
            # 内层 case 顺序即 j
            jj = len(out.get(i, {}))
            out.setdefault(i, {})[jj] = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
    return out


S_TASKS = {
    'TASK_FOLLOW_NAV_MESH_TO_COORD', 'TASK_GO_TO_COORD_ANY_MEANS',
    'TASK_GO_TO_COORD_WHILE_AIMING_AT_ENTITY', 'TASK_GO_TO_COORD_WHILE_AIMING_AT_COORD',
    'TASK_FOLLOW_TO_OFFSET_OF_ENTITY', 'TASK_FOLLOW_WAYPOINT_RECORDING',
    'TASK_ENTER_VEHICLE', 'TASK_VEHICLE_DRIVE_TO_COORD', 'TASK_MOUNT_ANIMAL',
    'TASK_DISMOUNT_ANIMAL', 'TASK_PUT_PED_DIRECTLY_INTO_COVER', 'TASK_SHOOT_AT_ENTITY',
    'TASK_COMBAT_PED', 'TASK_COMBAT_HATED_TARGETS_IN_AREA', 'TASK_PLAY_ANIM',
}
A_TASKS = {
    # 可见表演：动作序列 / 战斗 / 掩体 / 转身 / 注视 / 站姿 / 武器 / 马匹 / 逃跑
    'TASK_PERFORM_SEQUENCE', 'TASK_COMBAT_HATED_TARGETS_AROUND_PED', 'TASK_COMBAT_HATED_TARGETS_IN_AREA',
    'TASK_GO_TO_ENTITY', 'TASK_TURN_PED_TO_FACE_ENTITY', 'TASK_TURN_PED_TO_FACE_COORD',
    'TASK_LOOK_AT_ENTITY', 'TASK_LOOK_AT_COORD', 'TASK_ACHIEVE_HEADING', 'TASK_STAND_STILL',
    'TASK_PUT_PED_DIRECTLY_INTO_COVER', 'TASK_ENTER_COVER', 'TASK_EXIT_COVER',
    'TASK_SWAP_WEAPON', 'TASK_HOLSTER_WEAPON', 'TASK_HORSE_ACTION', 'TASK_USE_SCENARIO_POINT',
    'TASK_SMART_FLEE_PED', 'TASK_SMART_FLEE_COORD', 'TASK_LEAVE_ANY_VEHICLE',
    'TASK_PAUSE', 'TASK_STOP_LEADING_HORSE',
}
# 仅这些属于“玩家看不见”的管线
B_TASKS = {'TASK_CLEAR_LOOK_AT'}


def classify(typ, action, args):
    if typ in ('目标', '转场'):
        return 'S', '任务结构'
    if typ == '生成':
        if action == 'CREATE_GROUP':
            return 'B', 'AI 分组（不可见）'
        if 'joaat(' in args or re.search(r'\(-?\d+\.\d+,', args):
            return 'S', '带模型/坐标的生成'
        return 'A', '生成点（模型/坐标未解析）'
    if typ == '演出':
        if action in ('START_ANIM_SCENE', 'SET_ANIM_SCENE_PLAY_LIST'):
            return 'S', '过场/演出播放'
        if action.startswith('IS_'):
            return 'B', '状态查询（不可见）'
        return 'B', '资源加载'
    if typ == '行为':
        if action.startswith('TASK_SET_') or 'DEFENSIVE_AREA' in action:
            return 'B', 'AI 配置（不可见）'
        if action in S_TASKS:
            return 'S', '走位/生成位/过场位'
        if action in A_TASKS:
            return 'A', '可见表演（转身/注视/动作/战斗）'
        if action == 'TASK_CLEAR_LOOK_AT':
            return 'B', '清理注视（非表演）'
        if action == 'TASK_PAUSE':
            return 'A', '节奏等待（可见静止）'
        if action == 'TASK_STOP_LEADING_HORSE':
            return 'A', '停止牵马（可见）'
        if action in B_TASKS:
            return 'B', '不可见（清理）'
        return 'A', '可见行为'
    return 'B', '其他'


def nearest_condition(lines, idx):
    indent = len(lines[idx]) - len(lines[idx].lstrip('\t'))
    for j in range(idx - 1, max(-1, idx - 18), -1):
        l = lines[j]
        ind = len(l) - len(l.lstrip('\t'))
        if ind < indent and l.strip().startswith('if ('):
            return l.strip()[:120]
    return ''


def render_args(line, coords):
    line = line.strip()
    line = re.sub(r'\s+', ' ', line)
    def rep(m):
        c = coords.get(int(m.group(1)), {}).get(int(m.group(2)))
        if not c:
            return m.group(0)
        return '(%.1f, %.1f, %.1f)' % c
    line = COORD_RX.sub(rep, line)
    return line[:220]


def main():
    steps_all = json.load(open(W('export/levels/world/mission_steps.json'), encoding='utf-8'))
    mapping = json.load(open(W('work/script_probe/script_map_raw.json'), encoding='utf-8'))
    for k, v in {'RCLDN2': 'rcm_calderon2.c', 'RBNP21': 'rcm_beau_and_penelope21.c'}.items():
        if os.path.exists(os.path.join(SRC, v)):
            mapping[k] = [5, v]

    out = {}
    for mid, data in steps_all.items():
        if mid not in mapping:
            continue
        p = os.path.join(SRC, mapping[mid][1])
        if not os.path.exists(p):
            continue
        lines = open(p, encoding='utf-8', errors='ignore').read().split('\n')
        defs, rng = parse_funcs(lines)
        coords = parse_coords(lines, rng)
        steps = {}
        for st in data['steps']:
            host = st['caller'] if st.get('caller') in rng else st['fn']
            if host not in rng:
                continue
            events = []
            seq = [0]
            seen_events = set()

            def walk(fn, depth, stack, origin):
                if depth < 0 or fn not in rng or fn in stack or fn in SKIP_FUNCS:
                    return
                s0, e0 = rng[fn]
                if e0 - s0 > 700:
                    return
                for i in range(s0, e0):
                    l = lines[i]
                    m = TASK_RX.search(l)
                    typ = det = None
                    if m:
                        typ, det = '行为', m.group(1)
                    else:
                        m = CREATE_RX.search(l)
                        if m:
                            typ, det = '生成', m.group(2)
                        else:
                            m = UILOG_RX.search(l)
                            if m:
                                typ, det = '目标', m.group(1)
                            else:
                                m = TRANS_RX.search(l)
                                if m:
                                    typ, det = '转场', 'state -> ' + m.group(1)
                                else:
                                    m = ANIM_RX.search(l)
                                    if m:
                                        typ, det = '演出', m.group(1)
                    if typ:
                        args = render_args(l, coords)
                        # 过滤 UI 噪声
                        if typ == '目标' and not re.search(r'"[A-Z0-9_]{3,}"', args):
                            typ = None
                        if typ == '演出' and not any(x in det for x in ('PLAY', 'START')):
                            typ = None
                    if typ:
                        actor = ''
                        m2 = re.search(r'TASK::TASK_[A-Z_0-9]+\(([^,]+),', args)
                        if m2:
                            actor = m2.group(1).strip()
                        key = (typ, det, args)
                        if key in seen_events:
                            typ = None
                        else:
                            seen_events.add(key)
                    if typ:
                        seq[0] += 1
                        events.append({
                            'seq': seq[0], 'call_line': (i + 1 if origin is None else origin + 1), 'src_line': i + 1,
                            'fn': fn, 'type': typ, 'action': det, 'actor': actor,
                            'args': args, 'value': classify(typ, det, args)[0],
                            'why': classify(typ, det, args)[1],
                            'cond': nearest_condition(lines, i),
                        })
                    for c in re.findall(r'\b(func_\d+)\(', l):
                        if c not in SKIP_FUNCS:
                            walk(c, depth - 1, stack | {fn}, (i if origin is None else origin))
                return

            walk(host, 3, set(), None)
            steps[st['step']] = events[:400]
        if steps:
            out[mid] = {'script': mapping[mid][1], 'steps': steps}

    json.dump(out, open(W('export/levels/world/mission_events.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    import csv
    rows = []
    for mid, v in out.items():
        for step, evs in v['steps'].items():
            for e in evs:
                rows.append({'mission_id': mid, 'step': step, 'seq': e['seq'], 'type': e['type'],
                             'actor': e.get('actor', ''), 'action': e['action'],
                             'args': e['args'], 'value': e.get('value', ''), 'why': e.get('why', ''),
                             'cond': e['cond']})
    if rows:
        with open(W('export/levels/world/mission_events.csv'), 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
    print('事件 %d 任务，%d 事件' % (len(out), sum(len(v) for s in out.values() for v in s['steps'].values())))


if __name__ == '__main__':
    main()
