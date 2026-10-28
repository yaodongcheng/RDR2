#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""渲染《RDR2 任务执行逻辑还原》：目标层 + 失败条件层。"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)

CH = {1: '第一章 · 科尔特', 2: '第二章 · 马掌望台', 3: '第三章 · 谢迪贝莱', 4: '第四章 · 圣丹尼斯',
      5: '第五章 · 瓜玛', 6: '第六章 · 河狸岩洞', 7: '尾声上 · 叉角羚牧场', 8: '尾声下 · 比彻之愿'}


def main():
    recs = json.load(open(W('export/levels/world/missions_story.json'), encoding='utf-8'))
    obj = json.load(open(W('export/levels/world/mission_objectives.json'), encoding='utf-8'))
    main_recs = [r for r in recs if r['kind'] == 'main']
    side_recs = [r for r in recs if r['kind'] == 'side']

    L = []
    A = L.append
    A('# 荒野大镖客 2 · 任务执行逻辑还原（目标层 / 失败条件）')
    A('')
    A('> 回答："每个任务的具体执行逻辑也有了吗？"')
    A('>')
    A('> **脚本层没有，目标层有了。** `script_rel.rpf` 已从 `update_2.rpf` 抽出，'
      '但它用 RPF8 tag `0xC6(198)` 加密，密钥不在现有表里，`rdr2rpf list` 直接报 `Can\'t get encoder key!`。'
      '所以"触发器 / 生成 / 分支 / 奖励"仍然拿不到；本文件给的是**能从游戏资源里确证的另一半**：'
      '每条任务的玩家目标、失败条件、挑战与对白量。')
    A('')

    n_obj = sum(len(v['objective']) for v in obj.values())
    n_fail = sum(len(v['fail']) for v in obj.values())
    main_with = sum(1 for r in main_recs if r['id'] in obj)
    A('| 指标 | 数值 |')
    A('|---|---|')
    A('| 有目标文本的任务 | %d（主线 %d / 105） |' % (len(obj), main_with))
    A('| 目标条数 | %d |' % n_obj)
    A('| 失败条件条数 | %d |' % n_fail)
    A('| 任务挑战 | 308 条（105 条主线全覆盖） |')
    A('| 任务对白 | 41,005 行 |')
    A('')

    A('## 0. 为什么拿不到 `.ysc`（实测证据）')
    A('')
    A('| 项 | 实测结果 |')
    A('|---|---|')
    A('| 脚本包位置 | `update_2.rpf → x64/levels/rdr3/script/script_rel.rpf`，113,038,110 B |')
    A('| 已抽出 | ✅ `work/script_probe/x64/levels/rdr3/script/script_rel.rpf` |')
    A('| 包头 | `8FPR`(RPF8) / version 1639 / entries 27470 / **tag 0x00C6** / platform 121 |')
    A('| 解密 | ❌ `Can\'t get encoder key!`（`Cipher.GetCipher`，密钥表只有 0–162 + 192） |')
    A('| 其他副本 | 全盘 RPF 搜 `.ysc` 0 命中；`parseddata.rpf` 615 个 ymt 全部 signature-protected |')
    A('')
    A('> 换句话说：**不是没找到文件，是找到了但解不开**。需要 CodeX 的脚本反编译器，或补 tag 198 的 AES key。')
    A('')

    A('## 1. 现在我们能给出的四层')
    A('')
    A('| 层 | 来源 | 覆盖 | 能回答 | 不能回答 |')
    A('|---|---|---|---|---|')
    A('| 定义层 | `missions.meta` | 270/270 | 有哪些任务、属于哪章、过场包是谁 | 任务内部怎么跑 |')
    A('| **目标层** | 各任务 `<id>.yldb` | %d 个任务 / %d 条目标 | 玩家被要求做什么、做到哪一步 | 目标之间的触发条件与顺序 |' % (len(obj), n_obj))
    A('| **失败层** | 同上 | %d 条失败条件 | 什么情况会失败（跟丢、离场、NPC 死亡、被惊动） | 判定表达式与阈值 |' % n_fail)
    A('| 挑战层 | `challenges_sp_missions.meta` | 105 条主线 / 308 条 | 金牌条件（时间、爆头、精准度、不受伤） | — |')
    A('| 台词层 | 任务音频库 `.yldb` | 128 任务 / 41,005 行 | 任务里说了什么 | 谁在什么条件下说 |')
    A('')
    A('这四层足以还原"**一关的流程骨架**"：进场 → 目标 A/B/C → 失败条件 → 结算挑战；'
      '但还原不了"**脚本怎么实现**"：哪个 volume 触发哪个目标、生成几个 ped、什么条件下切分支。')
    A('')

    A('## 2. 主线逐任务：目标 + 失败条件')
    A('')
    A('> 目标按资源内顺序列出（同一任务的目标文本在 yldb 里按 key 排序，**不等于严格时间顺序**）；'
      '失败条件是原文，未做改写。')
    A('')
    for ch in range(1, 9):
        rs = sorted([r for r in main_recs if r['chapter'] == ch], key=lambda r: r['order'])
        A('### 2.%d %s' % (ch, CH[ch]))
        A('')
        for i, r in enumerate(rs, 1):
            o = obj.get(r['id'])
            A('#### %d. %s `%s`' % (i, r['title_zh'] or r['id'], r['id']))
            A('')
            if not o:
                A('- 无独立任务 yldb，目标文本未解出（可用简介/对白替代）。')
                if r['challenges']:
                    A('- 挑战：%s' % '；'.join(r['challenges']))
                A('')
                continue
            if o['objective']:
                A('**目标**')
                A('')
                for t in o['objective'][:12]:
                    A('- %s' % t)
                if len(o['objective']) > 12:
                    A('- …（另有 %d 条）' % (len(o['objective']) - 12))
                A('')
            if o['fail']:
                A('**失败条件**')
                A('')
                for t in o['fail'][:6]:
                    A('- %s' % t)
                if len(o['fail']) > 6:
                    A('- …（另有 %d 条）' % (len(o['fail']) - 6))
                A('')
            if r['challenges']:
                A('**金牌挑战**：%s' % '；'.join(r['challenges']))
                A('')
            A('> 台词 %d 行 · 过场 %d 段' % (r['dialogue_lines'], r.get('cutscene_clips', 0)))
            A('')

    A('## 3. 支线（有目标文本的）')
    A('')
    side_with = [r for r in side_recs if r['id'] in obj]
    A('共 %d 条支线有目标文本，下面按故事线列出目标摘要（完整条目见 CSV）。' % len(side_with))
    A('')
    for r in sorted(side_with, key=lambda x: (x['chapter'] or 99, x['id'])):
        o = obj[r['id']]['objective']
        A('- **%s** `%s`：%s' % (r['title_zh'] or r['id'], r['id'], '；'.join(o[:5]) + ('…' if len(o) > 5 else '')))
    A('')

    A('## 4. 仍然缺的部分与可行路线')
    A('')
    A('| 缺什么 | 影响 | 可行路线 |')
    A('|---|---|---|')
    A('| 触发器 / 区域判定 | 不知道目标在什么位置、什么条件下推进 | CodeX 反编译 `.ysc`；或补 AES key `0xC6` |')
    A('| 生成表（ped/载具/道具） | 不知道一关刷多少人、什么模型 | 同上；`metapeds.ymt` 另需 PSIN schema |')
    A('| 分支与失败表达式 | 不知道"如果…则…" | 同上 |')
    A('| 奖励与结算 | 不知道给多少钱/物品 | 同上；部分可从 `goals`/经济表反推 |')
    A('')
    A('> 结论：**"每个任务做什么"已经有了；"每个任务怎么被脚本驱动"还没有。**'
      '前者足够写攻略、做关卡复刻、排配音与过场；后者要动脚本层。')
    A('')

    A('## 5. 产物与复现')
    A('')
    A('| 文件 | 内容 |')
    A('|---|---|')
    A('| `export/levels/world/mission_objectives.csv` | 目标 / 失败条件（任务、类型、序号、原文） |')
    A('| `export/levels/world/mission_objectives.json` | 同上，按任务分组 |')
    A('| `tools/build_mission_objectives.py` | 从 `<id>.yldb` 抽取 + 过滤教学/按键文本 |')
    A('| `work/script_probe/x64/levels/rdr3/script/script_rel.rpf` | 已抽出的脚本包（待解密） |')
    A('')
    A('```bash')
    A('uv run python tools/build_mission_objectives.py')
    A('uv run python tools/render_mission_logic_md.py')
    A('```')

    out = W('RDR2_任务执行逻辑还原.md')
    open(out, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('written', out, len(L), 'lines')


if __name__ == '__main__':
    main()
