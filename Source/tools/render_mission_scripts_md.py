#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""渲染《RDR2 脚本级任务解析》。"""
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)

CH = {1: '第一章 · 科尔特', 2: '第二章 · 马掌望台', 3: '第三章 · 谢迪贝莱', 4: '第四章 · 圣丹尼斯',
      5: '第五章 · 瓜玛', 6: '第六章 · 河狸岩洞', 7: '尾声上 · 叉角羚牧场', 8: '尾声下 · 比彻之愿'}


def main():
    recs = json.load(open(W('export/levels/world/missions_story.json'), encoding='utf-8'))
    sc = json.load(open(W('export/levels/world/mission_scripts.json'), encoding='utf-8'))
    main_recs = [r for r in recs if r['kind'] == 'main']
    side_recs = [r for r in recs if r['kind'] == 'side']

    n_obj = sum(len(v['objectives']) for v in sc.values())
    n_fail = sum(len(v['fails']) for v in sc.values())
    strong = sum(1 for v in sc.values() if v['confidence'] == 'strong')
    main_n = sum(1 for r in main_recs if r['id'] in sc)

    L = []
    A = L.append
    A('# 荒野大镖客 2 · 脚本级任务解析')
    A('')
    A('> 回答："完成脚本级的任务信息解析。"')
    A('>')
    A('> 本机 `script_rel.rpf` 仍因 AES key #198 无法解密；但它的 RPF 条目数是 **1639**，'
      '与社区反编译脚本库 build 1355 的 `script_rel/` 文件数 **1639** 完全一致。'
      '因此本轮以该反编译代码为脚本层数据源，逐任务还原：**脚本文件、目标键→中文、失败条件、生成调用、过场、高频 native**。')
    A('')
    A('| 指标 | 数值 |')
    A('|---|---|')
    A('| 脚本文件总数 | 1,639（= 本机 RPF 条目数） |')
    A('| 解析到脚本的任务 | %d / 270 |' % len(sc))
    A('| 其中主线 | %d / 105 |' % main_n)
    A('| 强匹配（脚本内 `<ID>_` 文本键 ≥10） | %d |' % strong)
    A('| 脚本目标（键 + 中文） | %d 条（%d 个任务有目标文本） |' % (n_obj, sum(1 for v in sc.values() if v['objectives'])))
    A('| 脚本失败条件 | %d 条 |' % n_fail)
    A('')

    A('## 0. 数据来源与校验')
    A('')
    A('| 项 | 值 |')
    A('|---|---|')
    A('| 本机脚本包 | `work/script_probe/.../script_rel.rpf`（113,038,110 B） |')
    A('| RPF 条目数 | **1639**（`rdr2rpf list` 读到的 EntryCount） |')
    A('| RPF tag | `0xC6(198)`，AES key 缺失，无法本地解密 |')
    A('| 脚本库 | `RDR3-Decompiled-Scripts`，build **1355**，`script_rel/` 下 **1639** 个 `.c` |')
    A('| 本地副本 | `work/script_probe/script_src/`（用到的 **164** 个脚本，299 MB，便于复现） |')
    A('| 对应关系 | 文件名 → 任务 ID：按脚本内 `<ID>_...` 文本键出现次数匹配 |')
    A('')
    A('> 说明：这是**反编译后的 C 代码**，不是原始字节码；变量名多为 `uLocal_*` / `func_*`，'
      '但 native 调用、文本键、控制流是真实的。')
    A('')

    A('## 1. 解析方法')
    A('')
    A('1. **任务 → 脚本**：统计每个 `.c` 里 `"<ID>_..."` 形式的文本键数量，取最高的文件；≥10 记为强匹配。')
    A('2. **目标**：脚本里的文本键前缀不一定等于任务 ID（如 MUD6 → `MUD3B_*`、DST3 → `ODR3_*`）。'
      '先按"该前缀的键能在任务 yldb 里解析出中文"打分，自动选出真实前缀；再按"祈使句 / 含 OBJ"归类，'
      '按脚本内**首次出现顺序**排列。')
    A('3. **失败条件**：文案含"失败/已无法/被惊动/逃走/太远/死了/犯法/被抛弃"等，或 key 含 `FAIL`。')
    A('4. **生成调用**：统计 `PED::CREATE_PED` / `VEHICLE::CREATE_VEHICLE` / `OBJECT::CREATE_OBJECT` 的**调用点**（不是运行时数量）。')
    A('5. **过场**：脚本里的 `script@story@...` 动画场景名。')
    A('6. **高频 native**：按 `命名空间::函数` 统计，反映这一关主要在用哪些系统。')
    A('')

    zero_main = [r for r in main_recs if r['id'] in sc and not sc[r['id']]['objectives']]
    if zero_main:
        A('### 1.1 目标文本未能静态提取的主线（%d 条）' % len(zero_main))
        A('')
        A('这些任务的脚本已匹配，但目标文案由变量拼装或不在任务 yldb 中；'
          '仍可从脚本得到生成调用、过场与 native 画像。')
        A('')
        A('| 任务 | 脚本 |')
        A('|---|---|')
        for r in zero_main:
            A('| %s `%s` | `%s` |' % (r['title_zh'] or r['id'], r['id'], sc[r['id']]['script']))
        A('')

    A('## 2. 主线逐任务')
    A('')
    for ch in range(1, 9):
        rs = sorted([r for r in main_recs if r['chapter'] == ch], key=lambda r: r['order'])
        A('### 2.%d %s' % (ch, CH[ch]))
        A('')
        for i, r in enumerate(rs, 1):
            v = sc.get(r['id'])
            A('#### %d. %s `%s`' % (i, r['title_zh'] or r['id'], r['id']))
            A('')
            if not v:
                A('- 未匹配到脚本文件（该任务可能走通用脚本或未在 build 1355 中单独成文件）。')
                A('')
                continue
            A('- 脚本：`%s`（%s，%s 行 / %s 个函数）' % (
                v['script'], '强匹配' if v['confidence'] == 'strong' else '弱匹配',
                f"{v['lines']:,}", f"{v['funcs']:,}"))
            if v['objectives']:
                A('- **目标（脚本顺序）**')
                for k, o in enumerate(v['objectives'][:12], 1):
                    A('  %d. %s' % (k, o['text']))
                if len(v['objectives']) > 12:
                    A('  - …（另有 %d 条）' % (len(v['objectives']) - 12))
            if v['fails']:
                A('- **失败条件**：%s' % '；'.join(o['text'] for o in v['fails'][:6]))
            sp = v['spawn']
            A('- **生成调用点**：ped %d / vehicle %d / object %d / pickup %d' % (
                sp['ped'], sp['vehicle'], sp['object'], sp['pickup']))
            if v['cutscenes']:
                A('- **过场**：%s' % '；'.join('`%s`' % c for c in v['cutscenes'][:3]))
            if v['top_natives']:
                A('- **高频 native**：%s' % '、'.join('%s ×%d' % (n, c) for n, c in v['top_natives'][:5]))
            A('')

    A('## 3. 支线（有脚本的）')
    A('')
    side_with = [r for r in side_recs if r['id'] in sc]
    A('共 %d 条支线匹配到脚本。' % len(side_with))
    A('')
    A('| 任务 | 脚本 | 目标数 | 失败数 |')
    A('|---|---|---|---|')
    for r in sorted(side_with, key=lambda x: x['id']):
        v = sc[r['id']]
        A('| %s `%s` | `%s` | %d | %d |' % (r['title_zh'] or r['id'], r['id'], v['script'],
                                             len(v['objectives']), len(v['fails'])))
    A('')

    A('## 4. 局限')
    A('')
    A('| 项 | 说明 |')
    A('|---|---|')
    A('| 反编译源码 | 变量名已丢失，无法直接看出"哪个 volume 触发哪个目标"；但 native 调用与文本键是真实的 |')
    A('| 目标不全 | 部分任务的目标由变量拼装（`func_xxx` 返回文本键），静态匹配抓不到全部 |')
    A('| 生成计数 | 是调用点数量，不是运行时实际生成数量 |')
    A('| 版本 | 脚本库为 build 1355；与本机 RPF 条目数一致，但若游戏版本不同可能有差异 |')
    A('| 78 条未匹配 | 主要是物品请求、配方、线上任务，它们走通用脚本 |')
    A('| 目标文本不全 | 部分任务的文案由变量拼装（`func_xxx` 返回键），或文本键不在任务 yldb，静态抓不到 |')
    A('')

    A('## 5. 产物与复现')
    A('')
    A('| 文件 | 内容 |')
    A('|---|---|')
    A('| `export/levels/world/mission_scripts.csv` | 192 条任务：脚本文件、行数、函数数、目标数、失败数、生成调用点 |')
    A('| `export/levels/world/mission_scripts.json` | 同上 + 完整目标/失败/过场/native 列表 |')
    A('| `work/script_probe/script_map_raw.json` | 任务 → 脚本匹配（含匹配置信度） |')
    A('| `tools/build_mission_scripts.py` | 解析脚本并生成上述数据 |')
    A('')
    A('```bash')
    A('uv run python tools/build_mission_scripts.py')
    A('uv run python tools/render_mission_scripts_md.py')
    A('```')

    out = W('RDR2_脚本级任务解析.md')
    open(out, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('written', out, len(L), 'lines')


if __name__ == '__main__':
    main()
