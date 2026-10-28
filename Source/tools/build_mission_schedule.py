#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""任务「调度画像」：从反编译脚本抽取生成 / 行为 / 目标 / 演出事件。

注意：这是**静态代码画像**，不是运行时回放。
  - spawn 是 CREATE_* 调用点，不是运行时实际刷出数量；
  - TASK_* 是行为调用点，反映这一关用了哪些走位/战斗/交互行为；
  - 时间线按源码行号排序，是近似顺序，不等于执行顺序。
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
LOCAL_SRC = W('work/script_probe/script_src')
LANG = W('work/story/lang/chinesesimp')

TASK_ZH = {
    'TASK_ACHIEVE_HEADING': '转向指定朝向',
    'TASK_CLEAR_LOOK_AT': '取消注视',
    'TASK_LEAVE_ANY_VEHICLE': '离开载具',
    'TASK_USE_SCENARIO_POINT': '使用场景点',
    'TASK_SMART_FLEE_PED': '逃离 ped',
    'TASK_START_SCENARIO_IN_PLACE_HASH': '原地开始场景交互',
    'TASK_VEHICLE_TEMP_ACTION': '载具临时动作',
    'TASK_SMART_FLEE_COORD': '逃离坐标',
    'TASK_ANIMAL_UNALERTED': '动物安静移动',
    'TASK_PED_SLIDE_TO_COORD': '滑步到坐标',
    'TASK_VEHICLE_PARK': '停车',
    'TASK_ENTER_COVER': '进入掩体',
    'TASK_EXIT_COVER': '离开掩体',
    'TASK_AIM_GUN_AT_ENTITY': '举枪瞄准实体',
    'TASK_SHOOT_AT_COORD': '朝坐标射击',
    'TASK_PLACE_CARRIED_ENTITY_ON_MOUNT': '把扛着的人放到马上',
    'TASK_THROW_PROJECTILE': '投掷投射物',
    'TASK_WARP_PED_INTO_VEHICLE': '把 ped 传送进载具',
    'TASK_FOLLOW_NAV_MESH_TO_COORD': '沿导航网格走位到坐标',
    'TASK_FOLLOW_NAV_MESH_TO_COORD_WHILE_AIMING': '边瞄准边沿导航走位',
    'TASK_GO_TO_COORD_ANY_MEANS': '用任意方式前往坐标',
    'TASK_GO_TO_COORD_WHILE_AIMING_AT_ENTITY': '边瞄准目标边移动',
    'TASK_GO_TO_ENTITY': '走向实体',
    'TASK_FOLLOW_TO_OFFSET_OF_ENTITY': '跟随实体并保持偏移',
    'TASK_FOLLOW_WAYPOINT_RECORDING': '沿路径点录制走位',
    'TASK_FOLLOW_POINT_ROUTE': '沿点路线走位',
    'TASK_WANDER_IN_AREA': '在区域内游荡',
    'TASK_WANDER_STANDARD': '标准游荡',
    'TASK_STAND_STILL': '原地站立',
    'TASK_PAUSE': '暂停/等待',
    'TASK_COWER': '畏缩/求饶',
    'TASK_PUT_PED_DIRECTLY_INTO_MELEE': '直接进入近战',
    'TASK_PERFORM_SEQUENCE': '执行行为序列',
    'TASK_PLAY_ANIM': '播放动画',
    'TASK_PLAY_ANIM_ADVANCED': '播放动画（高级）',
    'TASK_ENTER_VEHICLE': '上车',
    'TASK_LEAVE_VEHICLE': '下车',
    'TASK_VEHICLE_DRIVE_TO_COORD': '驾车前往坐标',
    'TASK_VEHICLE_FOLLOW_WAYPOINT_RECORDING': '驾车跟随路径点',
    'TASK_MOUNT_ANIMAL': '上马',
    'TASK_DISMOUNT_ANIMAL': '下马',
    'TASK_SHOOT_AT_ENTITY': '朝实体射击',
    'TASK_COMBAT_PED': '与 ped 战斗',
    'TASK_COMBAT_HATED_TARGETS_IN_AREA': '在区域内攻击敌对目标',
    'TASK_COMBAT_HATED_TARGETS_AROUND_PED': '攻击周围敌对目标',
    'TASK_PUT_PED_DIRECTLY_INTO_COVER': '直接进入掩体',
    'TASK_SEEK_COVER_FROM_POS': '寻找掩体',
    'TASK_TURN_PED_TO_FACE_ENTITY': '转身面向实体',
    'TASK_TURN_PED_TO_FACE_COORD': '转身面向坐标',
    'TASK_LOOK_AT_ENTITY': '看向实体',
    'TASK_LOOK_AT_COORD': '看向坐标',
    'TASK_SWAP_WEAPON': '切换武器',
    'TASK_HOLSTER_WEAPON': '收起武器',
    'TASK_HORSE_ACTION': '马匹动作',
    'TASK_CARRIABLE': '搬运/扛人',
    'TASK_LOOT_ENTITY': '搜刮实体',
    'TASK_PICKUP_CARRIABLE': '拾取可搬运物',
    'TASK_USE_SCENARIO': '使用场景交互',
    'TASK_START_SCENARIO_IN_PLACE': '原地开始场景交互',
    'TASK_SMART_FLEE_POINT': '逃离某点',
    'TASK_REACT_AND_FLEE_PED': '反应并逃离',
    'TASK_CUFF_PED': '给 ped 上手铐',
    'TASK_KNOCKED_OUT': '击倒',
    'TASK_KNOCK_DOWN': '打倒',
}

SPAWN_RX = re.compile(r'(PED|VEHICLE|OBJECT)::(CREATE_[A-Z_0-9]+)\s*\(')
TASK_RX = re.compile(r'TASK::(TASK_[A-Z_0-9]+)\s*\(')
UILOG_RX = re.compile(r'UILOG::(_UILOG_[A-Z_0-9]+)\s*\(')
ANIM_RX = re.compile(r'ANIMSCENE::([A-Z_0-9]+)\s*\(')
KEY_RX = re.compile(r'"([A-Z][A-Z0-9_]{3,40})"')


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


def fn_index(lines):
    idx = []
    for i, l in enumerate(lines):
        m = re.match(r'^(?:void|int|float|bool|vector3|var|struct<[^>]*>)\s+(func_\d+)\s*\(', l)
        if m:
            idx.append((i, m.group(1)))
    return idx


def fn_at(idx, line):
    cur = '?'
    for i, name in idx:
        if i <= line:
            cur = name
        else:
            break
    return cur


def loop_bound(lines, line, back=40):
    """向上找最近的 for 循环上界（< N / != N）。"""
    for i in range(line, max(-1, line - back), -1):
        m = re.search(r'for\s*\([^;]*;\s*[^;]*?(?:<|<=|!=)\s*(\d+)\s*;', lines[i])
        if m:
            return int(m.group(1))
    return None


def main():
    recs = json.load(open(W('export/levels/world/missions_story.json'), encoding='utf-8'))
    mapping = json.load(open(W('work/script_probe/script_map_raw.json'), encoding='utf-8'))
    manual = {'RCLDN2': 'rcm_calderon2.c', 'RBNP21': 'rcm_beau_and_penelope21.c'}
    for k, v in manual.items():
        if os.path.exists(os.path.join(LOCAL_SRC, v)):
            mapping[k] = [5, v]

    out = {}
    rows = []
    for r in recs:
        mid = r['id']
        hit = mapping.get(mid)
        if not hit:
            continue
        fname = hit[1]
        p = os.path.join(LOCAL_SRC, fname)
        if not os.path.exists(p):
            continue
        s = open(p, encoding='utf-8', errors='ignore').read()
        lines = s.split('\n')
        idx = fn_index(lines)
        y = load_yldb(mid)

        spawns = []
        for m in SPAWN_RX.finditer(s):
            line = s.count('\n', 0, m.start())
            kind = m.group(2).replace('CREATE_', '').lower()
            near = '\n'.join(lines[max(0, line - 12):line + 12])
            models = [x for x in KEY_RX.findall(near) if not x.startswith(('INPUT_', 'WEAPON_'))][:3]
            spawns.append({'line': line + 1, 'fn': fn_at(idx, line), 'kind': kind,
                           'loop': loop_bound(lines, line), 'models': models})

        tasks = {}
        task_samples = []
        for m in TASK_RX.finditer(s):
            typ = m.group(1)
            line = s.count('\n', 0, m.start())
            tasks[typ] = tasks.get(typ, 0) + 1
            if len(task_samples) < 400:
                task_samples.append({'line': line + 1, 'type': typ, 'fn': fn_at(idx, line),
                                     'snippet': lines[line].strip()[:150]})

        objs = []
        for m in UILOG_RX.finditer(s):
            line = s.count('\n', 0, m.start())
            win = '\n'.join(lines[line:line + 3])
            keys = KEY_RX.findall(win)
            key = keys[0] if keys else ''
            text = clean(y.get(key)) if (y and key) else ''
            if key and (key.startswith(mid) or 'OBJ' in key):
                objs.append({'line': line + 1, 'key': key, 'text': text})

        anim_count = len(ANIM_RX.findall(s))

        # 近似时间线：生成 / 目标 / 行为（每类取样，按行号）
        events = []
        for x in spawns:
            events.append({'line': x['line'], 'type': '生成', 'detail': f"{x['kind']} ×{x['loop'] or 1}" + (f" · {','.join(x['models'])}" if x['models'] else '')})
        for x in objs:
            events.append({'line': x['line'], 'type': '目标', 'detail': x['text'] or x['key']})
        seen_task = {}
        for x in task_samples:
            if seen_task.get(x['type'], 0) >= 2:
                continue
            seen_task[x['type']] = seen_task.get(x['type'], 0) + 1
            events.append({'line': x['line'], 'type': '行为', 'detail': TASK_ZH.get(x['type'], x['type'])})
        events.sort(key=lambda e: e['line'])

        # ---- 阶段聚合：设置目标的函数 + 其直接调用函数的活动
        fn_ranges = {}
        for j, (st, name) in enumerate(idx):
            en = idx[j + 1][0] if j + 1 < len(idx) else len(lines)
            fn_ranges[name] = (st, en)

        def fn_body(name):
            st, en = fn_ranges.get(name, (0, 0))
            return "\n".join(lines[st:en])

        fn_spawn = {}
        fn_task = {}
        for name, (st, en) in fn_ranges.items():
            body = "\n".join(lines[st:en])
            fn_spawn[name] = len(SPAWN_RX.findall(body))
            fn_task[name] = Counter(TASK_RX.findall(body))

        stages = []
        obj_by_fn = {}
        for m in re.finditer(r'"(' + re.escape(mid) + r'_(?:OBJ|H_OBJ)[A-Z0-9_]*)"', s):
            line = s.count("\n", 0, m.start())
            obj_by_fn.setdefault(fn_at(idx, line), []).append((m.group(1), line))
        for fn, ks in obj_by_fn.items():
            keys = []
            texts = []
            for k, ln in ks:
                if k in keys:
                    continue
                keys.append(k)
                t = clean(y.get(k)) if y else ''
                if t:
                    texts.append(t)
            if not keys:
                continue
            body = fn_body(fn)
            callees = set(re.findall(r'\b(func_\d+)\(', body)) - {fn}
            sp = fn_spawn.get(fn, 0) + sum(fn_spawn.get(c, 0) for c in callees)
            tk = Counter(fn_task.get(fn, {}))
            for c in callees:
                tk.update(fn_task.get(c, {}))
            stages.append({
                'fn': fn, 'line': min(ln for _, ln in ks) + 1,
                'keys': keys[:6], 'objectives': texts[:4],
                'spawns': sp, 'tasks': sum(tk.values()),
                'top_tasks': [[k, v] for k, v in tk.most_common(5)],
            })
        stages.sort(key=lambda x: x['line'])

        rec = {
            'id': mid, 'script': fname,
            'spawns': spawns,
            'spawn_counts': {
                'ped': sum(1 for x in spawns if x['kind'] == 'ped'),
                'vehicle': sum(1 for x in spawns if x['kind'] == 'vehicle'),
                'object': sum(1 for x in spawns if x['kind'] == 'object'),
                'pickup': sum(1 for x in spawns if x['kind'] == 'pickup'),
            },
            'task_counts': dict(sorted(tasks.items(), key=lambda kv: -kv[1])),
            'task_samples': task_samples[:60],
            'objectives': objs,
            'anim_calls': anim_count,
            'timeline': events[:60],
            'stages': stages,
            'density': round((len(spawns) + sum(tasks.values()) + len(objs)) / max(1, len(lines)) * 1000, 1),
        }
        out[mid] = rec
        rows.append({'mission_id': mid, 'kind': r['kind'], 'chapter': r['chapter'], 'script': fname,
                     'spawn_ped': rec['spawn_counts']['ped'], 'spawn_vehicle': rec['spawn_counts']['vehicle'],
                     'spawn_object': rec['spawn_counts']['object'], 'task_calls': sum(tasks.values()),
                     'task_types': len(tasks), 'objective_updates': len(objs), 'anim_calls': anim_count,
                     'density_per_1k': rec['density']})

    json.dump(out, open(W('export/levels/world/mission_schedule.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    with open(W('export/levels/world/mission_schedule.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    print('调度画像 %d 条任务；生成点 %d，行为调用 %d，目标更新 %d' % (
        len(out), sum(len(v['spawns']) for v in out.values()),
        sum(sum(v['task_counts'].values()) for v in out.values()),
        sum(len(v['objectives']) for v in out.values())))


if __name__ == '__main__':
    main()
