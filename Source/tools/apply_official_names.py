# -*- coding: utf-8 -*-
"""把项目里"我自己翻的"地名/人名统一换成**游戏官方本地化**用词。

官方来源：`raw/lang/{en,zh}/global.yldb`（`data/lang/*_rel.rpf` 抽出）
对照工具：`tools/official_name_map.py`
本脚本只做**替换**，不动数值/坐标；跑完会打印每个文件改了多少处。

用法：
  uv run python tools/apply_official_names.py --check     # 只看会改什么
  uv run python tools/apply_official_names.py             # 直接改
"""
import os
import re
import glob
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 旧（我翻的）→ 官方（游戏文本）
PLACES = {
    '阿瓜斯杜尔塞斯': '阿瓜多切斯',      # Aguasdulces
    '康沃尔煤油厂': '康沃尔煤焦油厂',    # Cornwall Kerosene & Tar
    '卡利加庄园': '卡利加种植园',        # Caliga Hall
    '吊狗牧场': '垂犬牧场',              # Hanging Dog Ranch
    '默瑟堡': '布商堡',                  # Fort Mercer（游戏原文"堡垒布商"，攻略通用"布商堡"）
    '瓦匹提': '瓦匹缇',                  # Wapiti
    '屠夫溪': '布彻河村',                # Butcher Creek
    '杜伯里溪': '露莓溪',                # Dewberry Creek
    '波特小屋': '切兹波特',              # Chez Porter
    '里奇伍德农场': '脊木农场',          # Ridgewood Farm
    '克莱门斯据点': '克莱蒙斯岬',        # Clemens Point
    '科尔特': '犁刀村',                  # Colter
    '鼠窖岔口': '岔路酒馆',              # Rathskeller Fork
    '朗尼小屋': '朗尼棚屋',              # Lonnie's Shack
    '双岩': '双子岩',                    # Twin Rocks
    '裂齿矿洞': '豁牙裂口',              # Gaptooth Breach
    '曼萨尼塔哨站': '石兰贸易站',        # Manzanita Trading Post
    '唐恩牧场': '唐斯牧场',              # Downes' Ranch
    '瓜马营地': '瓜玛营',                # Guarma Camp
    '马蹄铁眺望': '马掌望台',            # Horseshoe Overlook ★ 用户纠正
    '威拉德歇脚处': '威拉德之息',        # Willard's Rest（对白原文）
    '奥兰治庄园': '奥兰治种植园',        # Orange Plantation（无官方文本，按内部关卡名）
    '雪山藏身处': '迈卡藏身处',          # Micah's Hideout（无官方文本）
    '瓜马': '瓜玛',                      # Guarma
    '罗阿诺克岭': '罗诺克山脊',          # Roanoke Ridge
    '红宝石草甸': '斯嘉丽草甸',          # Scarlett Meadows
    '六点小屋': '六点木屋',              # Six Point Cabin
    '奥克雷格': '奥克里夫潭',            # O'Creagh's Run
    '海狸洞': '河狸岩洞',                # Beaver Hollow
}

# 人名：官方文本里能对上的才改（歧义的不动，见 SKIP）
PEOPLE = {
    '阿比盖尔·罗伯茨': '艾比盖尔·罗伯茨',
    '比尔·威廉森': '比尔·威廉姆森',
    '兰尼·萨默斯': '蓝尼·萨莫斯',
    '肖恩·麦圭尔': '西恩·麦奎尔',
    '乔赛亚·特雷劳尼': '约西亚·特里劳尼',
    '凯瑟琳·布莱斯韦特': '凯瑟琳·布雷斯韦特',
    '佩内洛普·布莱斯韦特': '佩内洛普·布雷斯韦特',
    '博·格雷': '鲍·格雷',
    '佩塔': '佩塔赫',
    '莱昂': '利昂',
    '科尔姆·奥德里斯科尔': '科尔姆·奥德里斯科',
    '克利特': '克里特',
    '多金斯修士': '道金斯修士',
    '奥贝迪亚·欣顿': '俄巴底亚·辛顿',
    '卢卡·纳波利': '卢卡·拿波里',
    '蒂莫西·多纳休': '提莫西·多纳休',
    '玛丽·林顿': '玛丽·灵顿',
    '黑贝尔': '黑衣美人',
    '马科·德拉吉奇': '马尔科·德拉吉奇',
    '伊芙琳·米勒': '艾夫林·米勒',
    '夏尔·沙特奈': '查尔斯·夏特奈',
    '阿尔杰农·瓦斯普': '阿尔杰农·沃斯普',
    '黛博拉·麦吉尼斯': '黛博拉·麦克吉尼斯',
    '玛格丽特': '马尼菲科',
    '小埃德蒙·劳里': '小艾德蒙·劳里',
    '米奇': '米基',
    '马乔里小姐': '玛乔丽小姐',
    '巴蒂斯特': '巴普蒂斯特',
}

# 刻意不改：官方串指向的不是这个人 / 语境不同
SKIP = {'克里奥尔医生', '希金斯医生'}

REPL = {}
for k, v in PLACES.items():
    if k not in SKIP:
        REPL[k] = v
for k, v in PEOPLE.items():
    if k not in SKIP:
        REPL[k] = v

TARGETS = [
    'README.md', 'README_骑砍2交接.md',
    'docs/**/*.md',
    'deliverable/**/*.csv', 'deliverable/**/*.md',
    'export/levels/world/*.csv', 'export/levels/world/*.json',
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    files = set()
    for pat in TARGETS:
        files |= set(glob.glob(os.path.join(ROOT, pat), recursive=True))
    total = 0
    for f in sorted(files):
        try:
            s = open(f, encoding='utf-8').read()
        except (UnicodeDecodeError, PermissionError):
            continue
        orig = s
        n = 0
        for k, v in REPL.items():
            c = s.count(k)
            if c:
                s = s.replace(k, v)
                n += c
        if s != orig:
            total += n
            print('%-70s %d' % (os.path.relpath(f, ROOT), n))
            if not a.check:
                open(f, 'w', encoding='utf-8').write(s)
    print(('会修改 %d 处' if a.check else '已修改 %d 处') % total)


if __name__ == '__main__':
    main()
