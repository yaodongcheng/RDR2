#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用「按角色分包的语音文本库」反查说话人。

原理（实测）：RDR2 的环境/寒暄台词是**按角色分包**存的——`john_player.yldb`（5 334 条）、
`arthur.yldb`（5 111 条）、`dutch.yldb`、`abigail.yldb` …… **包名就是说话人**。
所以只要某句台词原文能在**唯一一个**角色包里找到，说话人就是那个角色。

产物：
  export/story/ambient_index.json   { 归一化台词: [角色包名...] }
  export/story/ambient_stats.json   覆盖率统计
"""
import glob
import json
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG = os.path.join(ROOT, 'raw', 'story', 'lang', 'chinesesimp')
STORY = os.path.join(ROOT, 'export', 'story')

# 过场/系统用的非角色包，排除
SKIP = {'global', 'help', 'news', 'credit', 'hud', 'ui', 'text'}

CN = {
    'arthur': '亚瑟', 'john_player': '约翰', 'dutch': '达奇', 'abigail': '阿比盖尔',
    'sadie': '莎迪', 'charles_smith': '查尔斯', 'bill': '比尔', 'javier': '哈维尔',
    'hosea': '何西阿', 'uncle': '大叔', 'jack': '杰克', 'karen': '凯伦', 'tilly': '蒂莉',
    'mary': '玛丽', 'strauss': '施特劳斯', 'pearson': '皮尔逊', 'grimshaw': '格里姆肖',
    'molly': '莫莉', 'sean': '西恩', 'lenny': '蓝尼', 'swanson': '斯旺森',
    'treawny': '特雷劳尼', 'josiah': '乔赛亚', 'micah': '迈卡',
}


def cn(name):
    return CN.get(name, name)


# 只认「角色语音包」——任务语音包（rcexo / spsdvau / cashbau …）不算，否则会张冠李戴
CHARACTER_BANKS = {
    'arthur', 'john_player', 'dutch', 'abigail', 'charles_smith', 'bill', 'javier',
    'hosea', 'uncle', 'jack', 'karen', 'tilly', 'strauss', 'pearson', 'molly',
    'sean', 'lenny', 'swanson',
}


def is_character_bank(fn):
    n = fn[:-5] if fn.endswith('.yldb') else fn
    return n in CHARACTER_BANKS


def strings(path):
    d = open(path, 'rb').read()
    out = []
    for m in re.finditer(rb'(?:[\xe4-\xe9][\x80-\xbf]{2}|[\x20-\x7e]){3,160}', d):
        try:
            s = m.group().decode('utf-8')
        except UnicodeDecodeError:
            continue
        s = re.sub(r'~[^~]{0,60}~', '', s).strip()
        if 3 <= len(s) <= 60:
            out.append(s)
    return out


def norm(s):
    return ''.join(ch for ch in (s or '') if ch not in '，。！？、,.!?…“”"\' ')


def main():
    idx = defaultdict(set)
    banks = 0
    total = 0
    for p in glob.glob(os.path.join(LANG, '*.yldb')):
        fn = os.path.basename(p)
        if not is_character_bank(fn):
            continue
        banks += 1
        for s in strings(p):
            idx[norm(s)].add(fn[:-5])
            total += 1
    print(f'角色包 {banks} 个，台词 {total} 条，归一化去重 {len(idx)} 条')

    # 用任务台词的原文去查
    hit = 0
    tot = 0
    uniq = 0
    for f in glob.glob(os.path.join(STORY, 'beats', '*.json')):
        b = json.load(open(f, encoding='utf-8'))
        for g, lines in b['conversations'].items():
            for x in lines:
                tot += 1
                who = idx.get(norm(x['zh']))
                if who:
                    hit += 1
                    if len(who) == 1:
                        uniq += 1

    out = {k: sorted(v) for k, v in idx.items()}
    json.dump(out, open(os.path.join(STORY, 'ambient_index.json'), 'w', encoding='utf-8'),
              ensure_ascii=False)
    stats = {'character_banks': banks, 'bank_lines': total, 'unique_texts': len(idx),
             'mission_lines': tot, 'matched': hit, 'unique_match': uniq,
             'coverage': round(hit / max(tot, 1) * 100, 2)}
    json.dump(stats, open(os.path.join(STORY, 'ambient_stats.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(stats)


if __name__ == '__main__':
    main()
