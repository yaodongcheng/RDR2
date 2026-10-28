#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""渲染《WNT1 西部亡命之徒 · 逐步骤拆解》以及全书步骤总表。"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)

NOTES = {
    1: '雪夜骑行开场。迈卡带路，玩家只需要跟住；脚本在这一段大量使用“路径点走位 + 导航走位”，并安排了下马动作。',
    2: '追上达奇，队伍从雪坡下到阿德勒牧场。行为以导航走位与转身面向为主，属于“到达目标点”的过渡段。',
    3: '抵达牧场后进入交火。这是本关行为最密集的一段：行为序列 11 次、导航走位 6 次、进入掩体 4 次，并生成 1 个对象（掩体/道具）。',
    4: '木屋段总控：进入木屋、继续搜查、出去与达奇会面、搜寻物资后会合，四个目标都挂在同一个阶段函数上。玩家在这里完成第一次搜刮。',
    5: '调查畜棚。脚本用 2 次“进入动画场景” + 1 次“切换武器”来表现推门/查看，属于轻交互段。',
    6: '把马牵到拴马桩，同时触发“调查木屋中的动静”。行为只有播放动画与停止牵马，重点是位置与朝向。',
    7: '前往牛棚并进入掩体，准备迎击奥德里斯科帮。这一段是防守位布置，行为以进入掩体为主。',
    8: '补充搜查木屋（第二次搜索），并生成 1 个对象；对应“漏搜”的补救目标。',
    9: '瞄准奥德里斯科帮成员，进入最后的射击教学/战斗提示。',
    10: '可选的马匹互动教学：瞄准马、安抚马。',
    11: '可选的马匹互动教学：靠近马、轻拍马。',
}


def main():
    recs = json.load(open(W('export/levels/world/missions_story.json'), encoding='utf-8'))
    steps_all = json.load(open(W('export/levels/world/mission_steps.json'), encoding='utf-8'))
    sched = json.load(open(W('export/levels/world/mission_schedule.json'), encoding='utf-8'))
    obj = json.load(open(W('export/levels/world/mission_objectives.json'), encoding='utf-8'))
    scripts = json.load(open(W('export/levels/world/mission_scripts.json'), encoding='utf-8'))
    dlg = json.load(open(W('export/levels/world/mission_dialogues.json'), encoding='utf-8'))
    events = json.load(open(W('export/levels/world/mission_events.json'), encoding='utf-8'))
    tree = json.load(open(W('export/levels/world/mission_tree.json'), encoding='utf-8'))
    by_id = {r['id']: r for r in recs}

    r = by_id['WNT1']
    v = steps_all['WNT1']
    v2 = sched['WNT1']

    L = []
    A = L.append
    A('# 西部亡命之徒 `WNT1` · 逐步骤拆解')
    A('')
    A('> 目标：把“这一关到底怎么跑”拆成可核对的步骤，而不是一句“跟随达奇”。')
    A('> 每一步都给出：**玩家目标 → 脚本函数 → 演员调度（行为/生成）→ 失败条件 → 说明**。')
    A('')
    A('| 项 | 值 |')
    A('|---|---|')
    A('| 章节 | 第 1 章 · 科尔特 |')
    sv = scripts['WNT1']
    A('| 脚本 | `%s`（%s 行 / %s 个函数） |' % (v['script'], f"{sv['lines']:,}", f"{sv['funcs']:,}"))
    A('| 步骤 | **%d 步** |' % len(v['steps']))
    A('| 生成调用点 | ped %d / vehicle %d / object %d |' % (
        v2['spawn_counts']['ped'], v2['spawn_counts']['vehicle'], v2['spawn_counts']['object']))
    A('| 行为调用 | %s 次 / %d 类 |' % (f"{sum(v2['task_counts'].values()):,}", len(v2['task_counts'])))
    A('| 过场 | %d 段 · 对白 %s 行 · 出场 %d 人 |' % (
        r.get('cutscene_clips', 0), f"{r['dialogue_lines']:,}", r['cast_count']))
    A('')
    A('## 0. 怎么读这张表')
    A('')
    A('- **目标**：任务 HUD 上显示的那句话，来自任务 yldb 的 `WNT1_OBJ_*` 文本键。')
    A('- **脚本函数**：设置这个目标的函数，以及它在主流程里被哪个阶段函数调用（行号）。')
    A('- **演员调度**：该阶段函数（含两层子调用）里的 `TASK_*` 行为计数；生成是 `CREATE_*` 调用点。')
    A('- **失败条件**：该阶段函数里能找到的 `WNT1_*FAIL/LOST/DEAD` 文本；找不到的放在文末统一列。')
    A('')
    A('**名词解释**：')
    A('')
    A('- **行为**：脚本里 `TASK_*` 的调用点数量，表示“让演员做动作”（走位 / 战斗 / 掩体 / 上下马 / 交互），**不是运行时执行次数**。')
    A('- **生成**：`PED::CREATE_PED` / `VEHICLE::CREATE_VEHICLE` / `OBJECT::CREATE_OBJECT` 的调用点，表示“刷出角色/车/物”，数量在参数里，未展开。')
    A('- **对白**：脚本里的对话组名（如 `WNT1_BANT3`），字幕在任务音频库里按 `_1..N` 编号。')
    A('- **微步骤事件**：把阶段函数按调用树展开后的逐条 `TASK_* / CREATE_* / ANIMSCENE / 转场` 事件；'
      '坐标已从 `func_1013` 的 211 个坐标点解析出来。**事件带条件分支，不是单条时间轴**。')
    A('')
    A('**重建价值分级**（决定哪些该看、哪些可以忽略）：')
    A('')
    A('| 级别 | 内容 | 处理 |')
    A('|---|---|---|')
    A('| **S · 结构与空间** | 目标更新、阶段转场、带坐标的走位、带模型/坐标的生成、过场播放 | 直接用于重建 |')
    A('| **A · 可见表演** | 转身（TURN）、注视（LOOK）、站姿、动作序列、战斗/掩体、武器/马匹动作、节奏等待（PAUSE）、停止牵马 | 必须还原，需补资源名 |')
    A('| **B · 不可见管线** | 资源加载、清理注视、状态查询、AI 分组（CREATE_GROUP）、AI 配置（TASK_SET_*） | 不影响画面，可跳过 |')
    A('')
    _ev = events.get('WNT1', {}).get('steps', {})
    _s = sum(1 for es in _ev.values() for e in es if e.get('value') == 'S')
    _a = sum(1 for es in _ev.values() for e in es if e.get('value') == 'A')
    _b = sum(1 for es in _ev.values() for e in es if e.get('value') == 'B')
    _tree_ev = [e for st in tree.get('WNT1', {}).get('steps', []) for c in st['cases'] for e in c['events']]
    _ts = sum(1 for e in _tree_ev if e.get('value') == 'S')
    _ta = sum(1 for e in _tree_ev if e.get('value') == 'A')
    _tb = sum(1 for e in _tree_ev if e.get('value') == 'B')
    A('不含对白的 TASK/CREATE 事件共 %d 条：**S %d / A %d / B %d**；加入对白后，树内共 %d 条：**S %d / A %d / B %d**。下面每步只列 S/A，B 类保留在 CSV 里。' % (
        _s + _a + _b, _s, _a, _b, _ts + _ta + _tb, _ts, _ta, _tb))
    A('')
    A('**关于 TURN / LOOK**：')
    A('')
    A('- 43 个任务里，**TURN（转身）111 条全部是 A**，**LOOK_AT（注视）78 条全部是 A**；')
    A('- B 里没有任何 TURN/LOOK_AT，只有 58 条 `CLEAR_LOOK_AT`（清除注视，不是表演）。')
    A('')
    _tw = [(st, e) for st, es in _ev.items() for e in es if 'TURN' in e['action'] or e['action'].startswith('TASK_LOOK_AT')]
    if _tw:
        A('WNT1 的可见朝向/注视事件：')
        A('')
        A('| 步骤 | # | 动作 | 对象 | 说明 |')
        A('|---|---|---|---|---|')
        for st, e in _tw[:12]:
            A('| %s | %d | `%s` | %s | 玩家可见的转身/注视 |' % (st, e['seq'], e['action'], e.get('actor') or '—'))
        A('')
    A('**怎么用它重建**：')
    A('')
    A('1. 按步骤顺序搭出阶段；每步的“微步骤事件”就是该阶段要执行的演员指令清单。')
    A('2. 每条事件都带“条件”列：`if (...)` 是进入该指令的前置判断，重建时照抄条件即可还原分支。')
    A('3. 坐标已从 `func_1013` 解析（211 个点），可以直接在引擎里摆点。')
    A('4. 实体列 `0/Global_35` 是玩家，`uLocal_1064[n]` 是任务演员槽位，`iLocal_*` 是任务本地实体；'
      '具体是谁需要看该槽位的赋值。')
    A('')
    A('> 注意：步骤顺序按“目标函数在主流程里第一次被调用的行号”排，不是引擎里的状态机顺序；'
      '少数分支（如木屋二次搜查、马匹教学）可能在实际游玩中是可选的。')
    A('')

    A('## 1. 步骤总表')
    A('')
    A('| # | 玩家目标 | 阶段函数 | 行为 | 生成 | 事件 |')
    A('|---|---|---|---|---|---|')
    for s in v['steps']:
        ec = len(events.get('WNT1', {}).get('steps', {}).get(str(s['step']), []))
        A('| %d | %s | `%s` | %d | %d | %d |' % (
            s['step'], s['objectives'][0].rstrip('。'), s['caller'] or s['fn'], s['tasks'], s['spawns'], ec))
    A('')

    A('## 2. 任务树（总任务 → 大步骤 → 小步骤 → 执行）')
    A('')
    A('```text')
    A('WNT1 西部亡命之徒')
    for st in tree.get('WNT1', {}).get('steps', []):
        A('├─ 步骤 %d %s（%d 事件）' % (st['step'], (st['objectives'][0] if st['objectives'] else ''), st['events']))
        for c in st['cases']:
            A('│  ├─ %s（%d 事件）' % (c['label'], len(c['events'])))
    A('```')
    A('')
    A('> 大步骤＝目标所在的阶段函数；小步骤＝该函数的 switch 状态（前置 / case N）；执行＝展开后的 TASK/CREATE/演出事件。')
    A('')
    A('## 3. 逐步拆解')
    A('')
    for s in v['steps']:
        A('### 步骤 %d · %s' % (s['step'], s['objectives'][0].rstrip('。')))
        A('')
        A('- **目标**：%s' % '；'.join(s['objectives']))
        A('- **脚本**：目标函数 `%s`；由阶段函数 `%s` 调用（行 %s）' % (
            s['fn'], s['caller'] or '—', s['call_line'] or '—'))
        if s['task_top']:
            A('- **演员调度**：%d 次行为，主要是 %s' % (
                s['tasks'], '、'.join('%s ×%d' % (k.replace('TASK_', ''), c) for k, c in s['task_top'])))
        else:
            A('- **演员调度**：该阶段以目标/UI 为主，未直接调用 TASK（行为在更深层的子函数里）')
        A('- **生成**：%d 个 CREATE_* 调用点' % s['spawns'])
        if s['fails']:
            A('- **失败条件**：%s' % '；'.join(s['fails']))
        convs = dlg.get('WNT1', {}).get('steps', {}).get(str(s['step']), [])
        if convs:
            A('- **对白**：%d 组对话，共 %d 行' % (len(convs), sum(len(c['lines']) for c in convs)))
            for c in convs[:3]:
                tag = '（条件触发）' if c['conditional'] else ''
                A('  - `%s`%s' % (c['name'], tag))
                for line in c['lines'][:4]:
                    A('    - %s' % line)
        note = NOTES.get(s['step'])
        if note:
            A('- **说明**：%s' % note)
        evs = events.get('WNT1', {}).get('steps', {}).get(str(s['step']), [])
        if evs:
            A('')
            keep = [e for e in evs if e.get('value') in ('S', 'A')]
            nb = len(evs) - len(keep)
            A('**微步骤事件（只列 S/A，共 %d 条；另有 B 类 %d 条已省略）**' % (len(keep), nb))
            A('')
            A('| # | 价值 | 类型 | 对象 | 动作 | 参数（坐标已解析） | 条件 |')
            A('|---|---|---|---|---|---|---|')
            for e in keep[:120]:
                args = e.get('args', '').replace('|', '／')[:120]
                cond = e.get('cond', '').replace('|', '／')[:60]
                A('| %d | %s | %s | %s | `%s` | `%s` | %s |' % (
                    e['seq'], e.get('value', ''), e['type'], e.get('actor', '').replace('|', '／') or '—',
                    e['action'], args, cond or '—'))
            if len(keep) > 120:
                A('| … | | | | | 另有 %d 条（见 mission_events.csv） | |' % (len(keep) - 120))
            A('')
        A('')

    A('## 4. 环境 / 条件对白')
    A('')
    un = dlg.get('WNT1', {}).get('unassigned', [])
    A('这些对话组不在某一步的目标函数里，通常是环境触发、战斗 bark 或条件分支（共 %d 组 / %d 行）。' % (
        len(un), sum(len(c['lines']) for c in un)))
    A('')
    for c in un[:20]:
        tag = '（条件触发）' if c['conditional'] else ''
        A('- `%s`%s' % (c['name'], tag))
        for line in c['lines'][:4]:
            A('  - %s' % line)
    A('')
    A('## 5. 全关失败条件')
    A('')
    fails = obj.get('WNT1', {}).get('fail', [])
    A('来自任务 yldb 的玩家提示（不是全部脚本判定，但覆盖了主要失败面）：')
    A('')
    for t in fails[:20]:
        A('- %s' % t)
    A('')

    A('## 6. 全关演员调度概览')
    A('')
    A('| 行为 | 次数 |')
    A('|---|---|')
    for k, c in list(v2['task_counts'].items())[:20]:
        A('| `%s` | %d |' % (k, c))
    A('')

    A('## 7. 这本书里其他任务的步骤')
    A('')
    A('同一套方法已经跑完 43 个任务（共 %d 步），完整数据在 `mission_steps.json`。' % sum(len(x['steps']) for x in steps_all.values()))
    A('')
    A('| 任务 | 脚本 | 步数 | 前几步 |')
    A('|---|---|---|---|')
    for mid, x in sorted(steps_all.items(), key=lambda kv: (by_id.get(kv[0], {}).get('chapter') or 99, kv[0])):
        rr = by_id.get(mid, {})
        titles = ' → '.join((s['objectives'][0].rstrip('。') if s['objectives'] else s['fn']) for s in x['steps'][:5])
        A('| %s `%s` | `%s` | %d | %s |' % (rr.get('title_zh', mid), mid, x['script'], len(x['steps']), titles))
    A('')

    A('## 8. 证据与局限')
    A('')
    A('| 项 | 说明 |')
    A('|---|---|')
    A('| 步骤切分 | 以“目标文本键所在函数 + 该函数最早调用行”为依据 |')
    A('| 行为计数 | 阶段函数 + 两层子调用的 `TASK_*` 调用点，不是运行时执行次数 |')
    A('| 生成计数 | `CREATE_*` 调用点，数量在参数/表里，未展开 |')
    A('| 顺序 | 静态调用行号，不等于状态机执行顺序；分支/可选段可能错位 |')
    A('| 失败条件 | 只能抓到同函数内的 `*FAIL/LOST/DEAD` 文本，判定表达式仍在代码里 |')
    A('')

    out = W('RDR2_任务逐步骤拆解_WNT1.md')
    open(out, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('written', out, len(L), 'lines')


if __name__ == '__main__':
    main()
