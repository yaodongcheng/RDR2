#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""RDR2 剧情任务（主线 / 支线）结构化导出。

数据源：
  work/meta/common/data/missions.meta                             任务定义（270）
  work/meta/common/data/stats_and_challenges/challenges_sp_missions.meta  任务挑战
  work/meta/common/data/stats_and_challenges/goals_sp_missions.meta       挑战文案 label
  work/story/lang/chinesesimp/global.yldb                          中文标题 / 简介
  work/story/lang/american/global.yldb                             英文标题 / 简介
  export/levels/world/mission_cast.csv                             过场 cast
  export/levels/world/npc_roster.csv                               cast → 中文名
  export/levels/world/mission_dialogue_index.csv                   任务对白库

输出：
  export/levels/world/missions_story.csv
  export/levels/world/missions_story.json
  export/levels/world/mission_challenges.csv
"""
import csv
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from yldb_keys import Yldb  # noqa: E402

W = lambda *p: os.path.join(ROOT, *p)

CHAPTERS = [
    ('CHAPTER_1', 1, '第一章 · 科尔特（雪山）'),
    ('CHAPTER_2', 2, '第二章 · 马掌望台'),
    ('CHAPTER_3', 3, '第三章 · 谢迪贝莱'),
    ('CHAPTER_4', 4, '第四章 · 圣丹尼斯'),
    ('CHAPTER_5', 5, '第五章 · 瓜玛'),
    ('CHAPTER_6', 6, '第六章 · 河狸岩洞'),
    ('CHAPTER_7', 7, '尾声上 · 叉角羚牧场'),
    ('CHAPTER_8', 8, '尾声下 · 比彻之愿'),
]
CH_META = {c: (n, name) for c, n, name in CHAPTERS}

# 主线剧情顺序（按任务简介与过场包推断；任务 ID 本身不按剧情编号）
MAIN_ORDER = {
    'CHAPTER_1': ['WNT1', 'WNT2', 'DST1', 'RPRSN', 'WNT4', 'MUD1'],
    'CHAPTER_2': ['MUD2', 'MUD3', 'REV1', 'SEN1', 'BOU1', 'SAL1', 'UTP1', 'HNT1',
                  'RABI1', 'RHMR0', 'MRY1', 'UTP2', 'RMUD32', 'MUD6', 'MUD4',
                  'RDST2', 'RDOWN3', 'RDTC1'],
    'CHAPTER_3': ['MUD5', 'FUD1', 'RSAD1', 'GRY1', 'RBNP11', 'RBNP12', 'BRT1', 'BRT2',
                  'GRY2', 'TRE1', 'RCHRB', 'CRN1', 'RXCF1', 'GRY3', 'BRT3', 'RDTC2', 'DST3'],
    'CHAPTER_4': ['MOB1', 'IND1', 'MOB2', 'MOB3', 'IND3', 'MOB4', 'MOB5', 'NBD1',
                  'CABR01', 'SUS1', 'ODR4', 'RCLDN1', 'RCLDN2', 'RNATV2', 'MRY3'],
    'CHAPTER_5': ['GUA2', 'GUA3', 'FUS1', 'FUS2', 'SMG2', 'GNG1', 'RDCH3', 'RDOPN', 'RGNG02'],
    'CHAPTER_6': ['DST5', 'TRN1', 'TRN2', 'TRN3', 'TRN4', 'NTV1', 'NTV2', 'NTV3',
                  'NTS1', 'NTS2', 'NTS3', 'GNG2', 'GNG3', 'FIN1', 'RMNR1',
                  'REDW21', 'REDW22', 'RDST62', 'RBNP21'],
    'CHAPTER_7': ['MAR1', 'MAR5', 'MAR2', 'MR52', 'MR53', 'MAR4', 'LAR1', 'AB21',
                  'SAD2', 'RBCH12'],
    'CHAPTER_8': ['BE22', 'RBCH21', 'MAR7', 'MAR6', 'MAR8', 'RJCK2', 'RABI3',
                  'SAD3', 'SAD4', 'SAD5', 'FIN2'],
}

CAT_ZH = {
    'RANDOM_CHARACTER': '陌生人 / 随机事件',
    'RANDOM_STORY_CHARACTER': '随机剧情角色',
    'BOUNTY_HUNTING': '赏金任务',
    'ITEM_REQUEST': '物品请求',
    'RECIPE': '配方（非剧情）',
    'ENDLESS_SUMMER': '线上 / 无尽夏日',
}

# 支线故事线：ID 前缀 → (故事线名, 触发地点/角色)
SIDE_LINES = [
    ('RBWCG', '捆绑的纽带', '黑先生与白先生（罗兹）'),
    ('RCAL', '枪手传', '西奥多·莱文 / 小鬼卡洛威（瓦伦丁·基恩酒馆）'),
    ('RGUN', '枪手传 · 四枪手', '莱文的传记对象：埃米特·格兰杰 / 弗拉科 / 比利·米德奈特 / 黑衣美人'),
    ('RCEXO', '公爵夫人和其他动物', '阿尔杰农·沃斯普（圣丹尼斯）'),
    ('RCDIN', '信仰考验', '黛博拉·麦克基尼斯（恐龙骨）'),
    ('RCRKF', '地质学入门', '弗朗西斯·辛克莱（岩刻）'),
    ('RCFSH', '天生钓手', '杰里米·吉尔（传说鱼）'),
    ('RCKPT', '一个聪明好动的男孩', '马尔科·德拉吉奇（遥控船）'),
    ('RKTTY', '他当然是英国佬', '玛格丽特与莎莉（马戏团走失动物）'),
    ('RMASN', '爱好者的乐土', '阿尔伯特·梅森（野生动物摄影）'),
    ('RMARY', '真爱易逝', '玛丽·灵顿'),
    ('RMAYR', '实用与理想主义入门', '勒米厄市长（圣丹尼斯）'),
    ('ROBT', '噢，兄弟', '阿克瑞斯与普洛托斯'),
    ('RODDF', '“粉末”登台', '伯特伦与马乔里（马戏团）'),
    ('RHNTN', '长者的智慧', '布彻河村诅咒'),
    ('RRTL', '知识的仁慈', '奥尔登教授（私酒驱动机器）'),
    ('RFMA', '艺术家的方式', '查尔斯·夏特奈（画家）'),
    ('RCLD2', '善恶参半', '卡尔德隆修女（施舍）'),
    ('RBNP', '真爱之路', '佩内洛普·布雷斯韦特与鲍·格雷'),
    ('RBRT0', '广告，美国的新派艺术', '布雷斯韦特私酒线（何西阿）'),
    ('RCTAX', '新世界新朋友', '霍布斯夫人（兽皮标本）'),
    ('RCCIG', '吸烟和其他爱好', '菲尼亚斯·T·拉姆斯博顿（香烟卡）'),
    ('RCRLE', '好心没好报', '雷诺医生（医疗车）'),
    ('RCRAW', '如此良宵', '蓝水沼泽的卡津人'),
    ('REFND', '募捐人', '圣丹尼斯公园募捐点'),
    ('RETH', '金光闪闪', '巴尔德斯皮诺（藏宝图）'),
    ('RHMRB', '拜访麦奎尔先生', '西恩（朗尼棚屋）'),
    ('REHEC', '（未命名支线）', '—'),
    ('RGNG0', '亲爱的塔西佗叔叔', '瓜玛归来（达奇分头行动）'),
]


def parse_challenges():
    """mission -> [goal_name]"""
    p = W('work/meta/common/data/stats_and_challenges/challenges_sp_missions.meta')
    root = ET.parse(p).getroot()
    out = {}
    for item in root.iter('Item'):
        nm = item.findtext('name')
        if not nm:
            continue
        goals = [g.text for g in item.findall('goalHashes/Item') if g.text]
        out[nm] = goals
    return out


def parse_goal_labels():
    """goal_name -> localization key"""
    p = W('work/meta/common/data/stats_and_challenges/goals_sp_missions.meta')
    root = ET.parse(p).getroot()
    out = {}
    for item in root.iter('Item'):
        if item.get('type') != 'StatsGoal':
            continue
        nm = item.findtext('name')
        ui = item.find('uiInfo')
        if not nm or ui is None:
            continue
        key = ui.findtext('logDescriptionLabel') or ui.findtext('pauseMenuDescriptionLabel')
        fmt = ui.findtext('logDescriptionFormatLabel')
        if key:
            out[nm] = (key, fmt or '')
    return out


def strip_marks(s):
    if not s:
        return ''
    s = re.sub(r'~\w+[^~]*~', '', s)
    return s.replace('\u00a0', ' ').strip()


def main():
    cn = Yldb(W('work/story/lang/chinesesimp/global.yldb'))
    en = Yldb(W('work/story/lang/american/global.yldb'))

    root = ET.parse(W('work/meta/common/data/missions.meta')).getroot()
    missions = []
    for m in root.find('Missions'):
        missions.append({
            'id': m.findtext('MissionId'),
            'category': m.findtext('Category'),
            'description_key': m.findtext('Description'),
            'texture': m.findtext('TextureName'),
            'mission_type': m.findtext('MissionType'),
        })

    # cast
    cast = {}
    for r in csv.DictReader(open(W('export/levels/world/mission_cast.csv'), encoding='utf-8-sig')):
        cast[r['mission_id']] = [x for x in (r['cast'] or '').split(';') if x]

    # 角色中文名
    name_zh = {}
    for r in csv.DictReader(open(W('export/levels/world/npc_roster.csv'), encoding='utf-8-sig')):
        name_zh[r['id']] = r['name_zh'] or r['name_en'] or r['id']

    # 对白
    dlg = {}
    for r in csv.DictReader(open(W('export/levels/world/mission_dialogue_index.csv'), encoding='utf-8-sig')):
        dlg[r['mission_id']] = (r['audio_bank'], int(r['lines'] or 0))

    chals = parse_challenges()
    goal_labels = parse_goal_labels()

    def cast_names(ids):
        out = []
        for c in ids:
            if c in name_zh:
                out.append(name_zh[c])
            elif c.startswith('player_'):
                out.append('亚瑟·摩根' if c == 'player_zero' else '约翰·马斯顿')
            else:
                out.append(c)
        return out

    challenge_rows = []
    recs = []
    for m in missions:
        mid = m['id']
        cat = m['category']
        title_cn = strip_marks(cn.get(mid) or '')
        title_en = strip_marks(en.get(mid) or '')
        desc_cn = strip_marks(cn.get(m['description_key']) or '')
        if not title_cn and desc_cn:
            # 物品请求一类没有独立标题，用简介首句代标题
            title_cn = desc_cn if len(desc_cn) <= 24 else desc_cn[:24] + '…'
        desc_en = strip_marks(en.get(m['description_key']) or '')
        names = cast_names(cast.get(mid, []))
        bank, lines = dlg.get(mid, ('', 0))

        goals = []
        for g in chals.get(mid, []):
            key, fmt = goal_labels.get(g, ('', ''))
            label = strip_marks(cn.get(key) or '') if key else ''
            if not label:
                label = g
            elif fmt == 'ACJGOAL_COUNT' and '{' not in label:
                pass
            goals.append(label)
            challenge_rows.append({'mission_id': mid, 'goal': g, 'label_key': key, 'label_zh': label})

        if cat in CH_META:
            ch_num, ch_name = CH_META[cat]
            order = MAIN_ORDER[cat].index(mid) + 1 if mid in MAIN_ORDER[cat] else 99
            kind = 'main'
        else:
            ch_num, ch_name = 0, CAT_ZH.get(cat, cat)
            order = 0
            kind = 'side'

        recs.append({
            'id': mid, 'kind': kind, 'category': cat, 'chapter': ch_num, 'chapter_name': ch_name,
            'order': order,
            'title_zh': title_cn, 'title_en': title_en,
            'desc_zh': desc_cn, 'desc_en': desc_en,
            'cast_count': len(names), 'cast': names,
            'cutscene_pkg': '', 'dialogue_bank': bank, 'dialogue_lines': lines,
            'challenges': goals,
        })

    # 过场包 + 场景统计
    cs = json.load(open(W('work/story/cutscene_clip_stats.json'), encoding='utf-8'))
    pkg = {}
    for r in csv.DictReader(open(W('export/levels/world/mission_cast.csv'), encoding='utf-8-sig')):
        if r['cutscene_pkgs']:
            pkg[r['mission_id']] = r['cutscene_pkgs']
    for r in recs:
        r['cutscene_pkg'] = pkg.get(r['id'], '')
        info = cs.get(r['cutscene_pkg'], {})
        r['cutscene_clips'] = info.get('clips', 0)
        r['cutscene_scenes'] = info.get('scenes', [])

    # 排序：主线按章+剧情序；支线按分类+编号
    recs.sort(key=lambda r: (0 if r['kind'] == 'main' else 1, r['chapter'], r['order'], r['id']))

    fields = ['id', 'kind', 'category', 'chapter', 'chapter_name', 'order', 'title_zh', 'title_en',
              'desc_zh', 'desc_en', 'cast_count', 'cast', 'cutscene_pkg', 'cutscene_clips',
              'dialogue_bank', 'dialogue_lines', 'challenges']
    with open(W('export/levels/world/missions_story.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in recs:
            row = dict(r)
            row['cast'] = ';'.join(r['cast'])
            row['challenges'] = ';'.join(r['challenges'])
            row.pop('cutscene_scenes', None)
            w.writerow(row)

    json.dump(recs, open(W('export/levels/world/missions_story.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    with open(W('export/levels/world/mission_challenges.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['mission_id', 'goal', 'label_key', 'label_zh'])
        w.writeheader()
        w.writerows(challenge_rows)

    # 统计
    with_title = sum(1 for r in recs if r['title_zh'])
    with_desc = sum(1 for r in recs if r['desc_zh'])
    main = [r for r in recs if r['kind'] == 'main']
    print('任务 %d（主线 %d / 支线 %d）' % (len(recs), len(main), len(recs) - len(main)))
    print('中文标题 %d，中文简介 %d，挑战 %d 条' % (with_title, with_desc, len(challenge_rows)))
    missing = [r['id'] for r in recs if not r['title_zh']]
    print('缺标题:', missing)


if __name__ == '__main__':
    main()
