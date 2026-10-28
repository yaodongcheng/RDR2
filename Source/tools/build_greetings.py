#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导出 18 个角色语音包里的「环境/寒暄台词」，按角色归类。

为什么有用：RDR2 的环境语音是**按角色分包**的（`john_player.yldb` / `arthur.yldb` …），
包名就是说话人。把这些台词抽出来，就能得到「某个角色会说哪些话」——
做骑砍2 的随机互动（打招呼、挑衅、感慨）时，这是现成的语料。

输出
  export/story/greetings.json      { 角色: [台词...] }
  export/story/greeting_stats.json { 角色: 条数 }
"""
import glob
import json
import os
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG = os.path.join(ROOT, 'raw', 'story', 'lang', 'chinesesimp')
STORY = os.path.join(ROOT, 'export', 'story')
BASE = 0x50000000

BANKS = {
    'arthur': '亚瑟', 'john_player': '约翰', 'dutch': '达奇', 'abigail': '阿比盖尔',
    'charles_smith': '查尔斯', 'bill': '比尔', 'javier': '哈维尔', 'hosea': '何西阿',
    'uncle': '大叔', 'jack': '杰克', 'karen': '凯伦', 'tilly': '蒂莉',
    'strauss': '施特劳斯', 'pearson': '皮尔逊', 'molly': '莫莉', 'sean': '西恩',
    'lenny': '蓝尼', 'swanson': '斯旺森',
}


def enumerate_entries(path):
    d = open(path, 'rb').read()
    n = len(d)
    out = []
    i = 0
    while i < n - 20:
        if d[i + 4:i + 8] == b'\0\0\0\0':
            node = struct.unpack_from('<I', d, i + 8)[0]
            if BASE <= node < BASE + n:
                o = node - BASE
                if o + 0x30 <= n:
                    sp = struct.unpack_from('<I', d, o + 0x20)[0]
                    ln = struct.unpack_from('<I', d, o + 0x28)[0]
                    if BASE <= sp < BASE + n and 0 < ln < 400:
                        s = sp - BASE + 0x10
                        if s + ln <= n:
                            raw = d[s:s + ln].lstrip(b'\0').rstrip(b'\0')
                            try:
                                t = raw.decode('utf-8')
                            except UnicodeDecodeError:
                                t = None
                            if t and t.strip():
                                out.append(t.strip())
                            i += 20
                            continue
        i += 4
    return out


def clean(t):
    import re
    t = re.sub(r'~[^~]{0,80}~', '', t).strip()
    t = t.replace('\\n', ' ').strip()
    return t


def main():
    out = {}
    stats = {}
    for bank, cn in BANKS.items():
        p = os.path.join(LANG, bank + '.yldb')
        if not os.path.exists(p):
            continue
        lines = []
        seen = set()
        for raw in enumerate_entries(p):
            t = clean(raw)
            if len(t) < 2 or len(t) > 60:
                continue
            if t in seen:
                continue
            seen.add(t)
            lines.append(t)
        out[cn] = lines
        stats[cn] = len(lines)
    os.makedirs(STORY, exist_ok=True)
    json.dump(out, open(os.path.join(STORY, 'greetings.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)
    json.dump(stats, open(os.path.join(STORY, 'greeting_stats.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('characters', len(out), 'total lines', sum(stats.values()))
    for k, v in sorted(stats.items(), key=lambda x: -x[1])[:8]:
        print(f'  {k}: {v}')


if __name__ == '__main__':
    main()
