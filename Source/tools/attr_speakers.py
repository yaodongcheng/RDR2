#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""给每句对白做「说话人」归属，按证据强度分级（不假装是官方字段）。

证据来源（由强到弱）
  bank   该句原文能在**唯一一个**角色语音文本包里找到（`john_player.yldb` / `arthur.yldb` …）
         —— 包名就是说话人，来自 `tools/build_ambient_speaker_index.py` 建的索引
  high   玩家对话选项（"问他是否见过约翰。" 这类祈使句）→ 玩家角色
  infer  句子里有称呼（"…，迈卡？"）→ 反推说话人是对面那位
  low    无锚点时按对话轮次交替（可能错）

输出 export/story/speakers.json
"""
import csv
import glob
import json
import os
import re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY = os.path.join(ROOT, 'export', 'story')

PUNCT = '，。！？、,.!?…“”"\' \u3000'
CHOICE_RE = re.compile(
    r'^(问他|问她|问他们|接受|拒绝|同意|反驳|威胁|给他|给她|收下|离开|离开这里|帮忙|付钱|不付|'
    r'打招呼|无视|道歉|挑衅|安慰|嘲笑|质疑|劝说|答应)')
PLAYER = ('亚瑟', '约翰')
CN_NAME = {
    'arthur': '亚瑟', 'john': '约翰', 'dutch': '达奇', 'micah': '迈卡', 'abigail': '阿比盖尔',
    'sadie': '莎迪', 'charles': '查尔斯', 'bill': '比尔', 'javier': '哈维尔', 'hosea': '何西阿',
    'uncle': '大叔', 'jack': '杰克', 'karen': '凯伦', 'tilly': '蒂莉', 'mary': '玛丽',
    'strauss': '施特劳斯', 'pearson': '皮尔逊', 'grimshaw': '格里姆肖', 'molly': '莫莉',
    'sean': '西恩', 'lenny': '蓝尼', 'swanson': '斯旺森', 'treawny': '特雷劳尼',
    'josiah': '乔赛亚', 'john_player': '约翰', 'charles_smith': '查尔斯',
}


def norm(s):
    return ''.join(ch for ch in (s or '') if ch not in PUNCT)


def is_choice(t):
    t = (t or '').strip()
    return bool(CHOICE_RE.match(t)) and len(t) <= 26


def cn_of(name):
    n = (name or '').lower()
    n = re.sub(r'^(cs_|player_)', '', n)
    n = re.sub(r'_(ms|fs)\d+$', '', n)
    return CN_NAME.get(n, name)


def vocative(zh, name):
    """name 是否以「称呼」形式出现（前后紧跟标点或句首/句尾）"""
    if not name or name not in zh:
        return False
    for m in re.finditer(re.escape(name), zh):
        i, j = m.start(), m.end()
        before = zh[i - 1] if i > 0 else ''
        after = zh[j] if j < len(zh) else ''
        if before in '，。！？、,.' or after in '，。！？、,.':
            return True
    return False


def load_ambient():
    p = os.path.join(STORY, 'ambient_index.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


def main():
    meta = {r['id']: r for r in json.load(
        open(os.path.join(ROOT, 'export/levels/world/missions_story.json'), encoding='utf-8'))}
    amb = load_ambient()
    out = {}
    stat = Counter()
    for f in glob.glob(os.path.join(STORY, 'beats', '*.json')):
        b = json.load(open(f, encoding='utf-8'))
        mid = b['id']
        m = meta.get(mid, {})
        cast_cn = [c for c in (m.get('cast') or []) if c]
        name_pool = cast_cn + list(CN_NAME.values())
        convs = {}
        for g, lines in b['conversations'].items():
            text_all = ' '.join(x['zh'] for x in lines)
            cnt = Counter()
            for nm in name_pool:
                if len(nm) >= 2 and nm in text_all and not any(p in nm for p in PLAYER):
                    cnt[nm] = text_all.count(nm)
            npc = None
            first = lines[0]['zh'] if lines else ''
            for nm in name_pool:
                if len(nm) >= 2 and vocative(first, nm) and not any(p in nm for p in PLAYER):
                    npc = nm
                    break
            if not npc and cnt:
                npc = cnt.most_common(1)[0][0]

            seq = []
            last = None
            for i, ln in enumerate(lines):
                zh = ln['zh']
                who, kind, conf = None, 'say', 'none'
                banks = amb.get(norm(zh))
                if banks and len(banks) == 1:
                    who, conf = cn_of(banks[0]), 'bank'
                elif is_choice(zh):
                    who, kind, conf = PLAYER[0], 'choice', 'high'
                    last = who
                elif npc and vocative(zh, npc) and not vocative(zh, PLAYER[0]):
                    who, conf = PLAYER[0], 'infer'
                    last = who
                elif npc and vocative(zh, PLAYER[0]) and not vocative(zh, npc):
                    who, conf = npc, 'infer'
                    last = who
                # 没有锚点时不猜（实测会错：WNT1_INT_CABIN_31 真值是达奇，轮次推断给了亚瑟）
                seq.append({'n': ln['n'], 'zh': zh, 'who': who, 'kind': kind, 'conf': conf})
                stat[conf] += 1
            convs[g] = {'participants': [npc, PLAYER[0]] if npc else [], 'lines': seq}
        out[mid] = convs

    json.dump(out, open(os.path.join(STORY, 'speakers.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    total = sum(stat.values())
    print('speakers.json', len(out), 'missions', dict(stat), 'covered',
          sum(v for k, v in stat.items() if k != 'none'), '/', total)


if __name__ == '__main__':
    main()
