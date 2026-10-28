#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""渲染《RDR2 任务调度解析》：生成点 / 演员行为 / 阶段 / 演出。"""
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)

CH = {1: '第一章 · 科尔特', 2: '第二章 · 马掌望台', 3: '第三章 · 谢迪贝莱', 4: '第四章 · 圣丹尼斯',
      5: '第五章 · 瓜玛', 6: '第六章 · 河狸岩洞', 7: '尾声上 · 叉角羚牧场', 8: '尾声下 · 比彻之愿'}

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
    'TASK_LOOK_AT_ENTITY': '看向实体',
    'TASK_SWAP_WEAPON': '切换武器',
    'TASK_HORSE_ACTION': '马匹动作',
}


def main():
    recs = json.load(open(W('export/levels/world/missions_story.json'), encoding='utf-8'))
    sch = json.load(open(W('export/levels/world/mission_schedule.json'), encoding='utf-8'))
    main_recs = [r for r in recs if r['kind'] == 'main']
    side_recs = [r for r in recs if r['kind'] == 'side']

    n_spawn = sum(len(v['spawns']) for v in sch.values())
    n_task = sum(sum(v['task_counts'].values()) for v in sch.values())
    n_anim = sum(v['anim_calls'] for v in sch.values())
    n_stage = sum(len(v['stages']) for v in sch.values())

    L = []
    A = L.append
    A('# 荒野大镖客 2 · 任务调度解析')
    A('')
    A('> 上一份文档回答“玩家要做什么”；这一份回答“**脚本怎么调度演员**”。')
    A('>')
    A('> 数据来自 194 个任务脚本（build 1355 反编译），解析出 **%s 个生成调用点、%s 次行为调用、%s 次演出调用**。'
      % (f'{n_spawn:,}', f'{n_task:,}', f'{n_anim:,}'))
    A('')
    A('| 指标 | 数值 |')
    A('|---|---|')
    A('| 有调度数据的任务 | %d / 270 |' % len(sch))
    A('| 生成调用点 | %s（ped / vehicle / object / pickup / group） |' % f'{n_spawn:,}')
    A('| 演员行为调用（TASK_*） | %s |' % f'{n_task:,}')
    A('| 演出调用（ANIMSCENE_*） | %s |' % f'{n_anim:,}')
    A('| 可归属到目标函数的“阶段” | %d 个（覆盖 %d 个任务） |' % (n_stage, sum(1 for v in sch.values() if v['stages'])))
    A('')
    A('## 0. 先说明：这是什么，不是什么')
    A('')
    A('| 能回答 | 不能回答 |')
    A('|---|---|')
    A('| 这一关用了哪些生成调用（ped/车/物） | 运行时**实际**刷出几个（数量在参数/表里） |')
    A('| 这一关用了哪些演员行为（走位/掩体/瞄准移动/上马） | 每个演员在**第几秒**做（静态代码没有时间轴） |')
    A('| 目标更新发生在哪个函数、附近有哪些行为 | 触发条件（哪个 volume、哪个 flag） |')
    A('| 演出场景名与调用密度 | 运行时的 actor 绑定关系 |')
    A('')
    A('> 一句话：这是**静态调度画像**，不是运行时回放。要做到“第 12 秒刷 4 个敌人、第 20 秒 A 走到 B”，还需要运行时 trace 或把脚本状态机完整还原。')
    A('')

    A('## 1. 全局：行为类型分布')
    A('')
    all_tasks = Counter()
    for v in sch.values():
        all_tasks.update(v['task_counts'])
    A('| 行为 | 中文 | 调用次数 |')
    A('|---|---|---|')
    for k, c in all_tasks.most_common(20):
        A('| `%s` | %s | %s |' % (k, TASK_ZH.get(k, '—'), f'{c:,}'))
    A('')

    A('### 1.1 调度密度 Top 15（行为+生成+目标 每千行）')
    A('')
    A('| 任务 | 脚本 | 生成点 | 行为调用 | 密度 |')
    A('|---|---|---|---|---|')
    dens = sorted(sch.values(), key=lambda v: -v['density'])[:15]
    for v in dens:
        r = next((x for x in recs if x['id'] == v['id']), None)
        A('| %s `%s` | `%s` | %d | %d | %.1f |' % (
            (r or {}).get('title_zh', v['id']), v['id'], v['script'],
            len(v['spawns']), sum(v['task_counts'].values()), v['density']))
    A('')

    A('## 2. 主线逐任务')
    A('')
    for ch in range(1, 9):
        rs = sorted([r for r in main_recs if r['chapter'] == ch], key=lambda r: r['order'])
        A('### 2.%d %s' % (ch, CH[ch]))
        A('')
        for i, r in enumerate(rs, 1):
            v = sch.get(r['id'])
            A('#### %d. %s `%s`' % (i, r['title_zh'] or r['id'], r['id']))
            A('')
            if not v:
                A('- 未匹配到脚本，无调度数据。')
                A('')
                continue
            sc = v['spawn_counts']
            A('- **生成**：ped %d · vehicle %d · object %d · pickup %d（调用点）' % (
                sc['ped'], sc['vehicle'], sc['object'], sc['pickup']))
            A('- **行为**：%s 次调用 / %d 种；演出 %s 次' % (
                f"{sum(v['task_counts'].values()):,}", len(v['task_counts']), f"{v['anim_calls']:,}"))
            top = list(v['task_counts'].items())[:8]
            if top:
                A('- **主要行为**：' + '、'.join('%s ×%d' % (TASK_ZH.get(k, k), c) for k, c in top))
            if v['stages']:
                A('')
                A('| 阶段函数 | 目标 | 生成 | 行为 |')
                A('|---|---|---|---|')
                order = {t: i for i, t in enumerate(r.get('script_objectives') or [])}
                shown = [x for x in v['stages'] if x['spawns'] + x['tasks'] > 0] or v['stages']
                shown = sorted(shown, key=lambda x: min([order.get(o, 999) for o in x['objectives']] or [999]))[:8]
                for st in shown:
                    A('| `%s` | %s | %d | %d |' % (
                        st['fn'], '；'.join(st['objectives'][:2]) or '；'.join(st['keys'][:2]),
                        st['spawns'], st['tasks']))
            A('')

    A('## 3. 支线（有调度数据的）')
    A('')
    side_sch = [r for r in side_recs if r['id'] in sch]
    A('共 %d 条。' % len(side_sch))
    A('')
    A('| 任务 | 脚本 | 生成点 | 行为调用 | 演出 |')
    A('|---|---|---|---|---|')
    for r in sorted(side_sch, key=lambda x: (x['chapter'] or 99, x['id'])):
        v = sch[r['id']]
        A('| %s `%s` | `%s` | %d | %d | %d |' % (
            r['title_zh'] or r['id'], r['id'], v['script'], len(v['spawns']),
            sum(v['task_counts'].values()), v['anim_calls']))
    A('')

    A('## 4. 局限与下一步')
    A('')
    A('| 局限 | 原因 | 下一步 |')
    A('|---|---|---|')
    A('| 生成数量是调用点 | 数量在参数/静态表里，跨函数传递 | 解析 spawn 表 / 循环上界；或运行时 hook CREATE_PED |')
    A('| 行为没有时间轴 | 静态代码没有执行顺序 | 运行时 trace；或还原状态机后按状态排序 |')
    A('| 阶段只覆盖 44 个任务 | 目标键必须和函数在同一段代码里 | 用调用图把目标函数与行为函数连起来 |')
    A('| 演出只统计调用 | ANIMSCENE 绑定谁、播哪段在参数里 | 解析 ANIMSCENE 名与 actor 绑定 |')
    A('')
    A('> 如果要做“第几秒刷几个敌人”，最直接的是**运行时 hook**：在 CREATE_PED / TASK_* 上打点，跑一遍任务就能得到真实时间轴。')
    A('')
    A('## 5. 产物与复现')
    A('')
    A('| 文件 | 内容 |')
    A('|---|---|')
    A('| `export/levels/world/mission_schedule.json` | 每个任务：生成点、行为计数、阶段、演出、时间线候选 |')
    A('| `export/levels/world/mission_schedule.csv` | 汇总表 |')
    A('| `tools/build_mission_schedule.py` | 解析脚本生成调度画像 |')
    A('')
    A('```bash')
    A('uv run python tools/build_mission_schedule.py')
    A('uv run python tools/render_mission_schedule_md.py')
    A('```')

    out = W('RDR2_任务调度解析.md')
    open(out, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('written', out, len(L), 'lines')


if __name__ == '__main__':
    main()
