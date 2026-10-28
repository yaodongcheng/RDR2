#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 .ymt 解出来的 actor 合并进查看器用的 speaker_overrides.json。

优先级：手工/录屏标注 > .ymt actor（本次）
输出：export/story/speaker_overrides.json（{mission: {group: {line_no: 角色}}）
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY = os.path.join(ROOT, 'export', 'story')

CN = {
    'arthur': '亚瑟', 'john': '约翰', 'dutch': '达奇', 'abigail': '阿比盖尔',
    'hosea': '何西阿', 'susan': '苏珊', 'swanson': '斯旺森', 'charles_smith': '查尔斯',
    'bill': '比尔', 'javier': '哈维尔', 'micah': '迈卡', 'sadie': '莎迪',
    'uncle': '大叔', 'jack': '杰克', 'karen': '凯伦', 'tilly': '蒂莉',
    'strauss': '施特劳斯', 'pearson': '皮尔逊', 'molly': '莫莉', 'sean': '西恩',
    'lenny': '蓝尼', 'mary': '玛丽', 'treawny': '特雷劳尼', 'josiah': '乔赛亚',
    'grimshaw': '格里姆肖', 'john_player': '约翰', 'micah_bell': '迈卡',
    'trelawny': '特雷劳尼', 'sadie_adler': '莎迪', 'john_marston': '约翰',
    'abigail_roberts': '阿比盖尔', 'hosea_matthews': '何西阿', 'dutch_vanderlinde': '达奇',
    'bill_williamson': '比尔', 'javier_escuella': '哈维尔', 'uncle_': '大叔',
    'karen_jones': '凯伦', 'tilly_jackson': '蒂莉', 'mary_beth': '玛丽-贝丝',
    'simon_pearson': '皮尔逊', 'leopold_strauss': '施特劳斯', 'molly_oshea': '莫莉',
    'sean_macguire': '西恩', 'lenny_summers': '蓝尼', 'orville_swanson': '斯旺森',
}


NAMED = {
    'thomas_downes': '托马斯·唐斯', 'trelawny': '特雷劳尼', 'kieran': '基兰',
    'marybeth': '玛丽-贝丝', 'teen_jack': '少年杰克', 'cleet': '克利特',
    'clay': '克莱', 'joe': '乔', 'beau_gray': '博·格雷',
    'dorothea_wicklow': '多萝西娅·威克洛', 'rrch1_abe': '亚伯',
    'emr_son1': '埃米特之子', 're_treasure_hunter': '寻宝猎人',
    'rev1_witness': '目击者', 'twd_sheriff': '警长', 'js_towndealer': '镇上的商人',
    'player': '玩家', 'rbwcg_white': '白人工人', 'rbwcg_black': '黑人工人',
    'rbra_target': '赏金目标', 'rbco_target': '赏金目标', 'rbh_target18': '赏金目标',
    'rbh_target20': '赏金目标', 'rbh_target22': '赏金目标', '905783836': '陌生人',
}

# ped 模型名里的关键词 → 中文身份（按顺序匹配，先具体后通用）
PED_RULES = [
    ('valsheriff', '瓦伦丁警长'), ('rhdsheriff', '罗兹警长'), ('sdpolicechief', '圣丹尼斯警长'),
    ('blwpolicechief', '黑水镇警长'), ('sdpolice', '圣丹尼斯警察'), ('ambientlawrural', '乡村执法者'),
    ('pinlaw', '平克顿侦探'), ('unibraithwaites', '布雷斯韦特家丁'), ('unigrays', '格雷家丁'),
    ('unibanditos', '匪帮'), ('unicriminals', '匪徒'), ('uniinbred', '畸形家族'),
    ('uniranchers', '牧场主'), ('unimountainmen', '山地人'), ('uniduster', '乡民'),
    ('uniexconfeds', '前邦联军'), ('unitown', '镇民'), ('uniskinner', '剥皮帮'),
    ('wapwarriors', '原住民战士'), ('waptownfolk', '原住民'), ('fussarhenchman', '福萨尔的打手'),
    ('army', '士兵'), ('guard', '守卫'), ('streetkids', '街头小孩'), ('street', '街头游民'),
    ('townfolk', '镇民'), ('slums', '贫民窟居民'), ('travellers', '旅行者'),
    ('bartender', '酒保'), ('gunsmith', '枪匠'), ('doctor', '医生'), ('barber', '理发师'),
    ('tailor', '裁缝'), ('marketvendor', '摊贩'), ('newspaperboy', '报童'),
    ('genstoreowner', '店主'), ('storeowner', '店主'), ('hotelowner', '旅店老板'),
    ('photographer', '摄影师'), ('trainstationworker', '车站工人'),
    ('freightstationowner', '货运站主'), ('welcomecenter', '迎宾员'), ('civ', '平民'),
    ('police', '警察'), ('sheriff', '警长'), ('law', '执法者'),
]

PED_LABEL = [
    ('unicriminals', '匪徒'), ('unibanditos', '匪帮'), ('uniduster', '乡民'),
    ('uniranchers', '牧场主'), ('unimountainmen', '山地人'), ('uniinbred', '畸形家族'),
    ('uniexconfeds', '前邦联军'), ('unipinkerton', '平克顿'), ('unilaw', '执法者'),
    ('uniguard', '守卫'), ('uniwarvet', '退伍兵'), ('unicorpse', '尸体'),
    ('uniclay', '矿工'), ('unitown', '镇民'), ('unifarmer', '农夫'),
    ('unihunter', '猎人'), ('uniskinner', '剥皮帮'), ('unicivilwar', '内战士兵'),
    ('police', '警察'), ('sheriff', '警长'), ('doctor', '医生'), ('shopkeeper', '店主'),
    ('bartender', '酒保'), ('newspaper', '报童'), ('worker', '工人'),
]


def cn(n):
    if not n:
        return None
    k = n.lower()
    if k in NAMED:
        return NAMED[k]
    for kw, label in PED_RULES:
        if kw in k:
            return label
    for kw, label in PED_LABEL:
        if kw in k:
            return label
    for key, v in CN.items():
        if k == key or k.startswith(key + '_') or k.startswith('cs_' + key):
            return v
    return n


def main():
    ca = json.load(open(os.path.join(STORY, 'conversation_actors.json'), encoding='utf-8'))
    _pp = os.path.join(STORY, 'actor_name_patches.json')
    patches = json.load(open(_pp, encoding='utf-8')) if os.path.exists(_pp) else {}
    ov_path = os.path.join(STORY, 'speaker_overrides.json')
    # 手工/录屏标注放在独立文件里，避免把上一次的生成结果当人工数据
    _mp = os.path.join(STORY, 'speaker_overrides_manual.json')
    manual = json.load(open(_mp, encoding='utf-8')) if os.path.exists(_mp) else {}

    # 基线：speakers.json 里的推断结果（bank/high/infer），优先级低于 .ymt
    base = {}
    _sp = os.path.join(STORY, 'speakers.json')
    if os.path.exists(_sp):
        sp = json.load(open(_sp, encoding='utf-8'))
        for mid, groups in sp.items():
            for g, info in groups.items():
                who = [x.get('who') for x in (info.get('lines') or [])]
                if any(who):
                    base.setdefault(mid, {})[g] = {str(i + 1): w for i, w in enumerate(who) if w}

    out = {}
    for f in glob.glob(os.path.join(STORY, 'beats', '*.json')):
        b = json.load(open(f, encoding='utf-8'))
        mid = b['id']
        for g, lines in b['conversations'].items():
            rec = ca.get(g)
            if not rec:
                continue
            pm = patches.get(mid, {})
            wild = pm.get('*', {})
            local = pm.get(g, {})
            by_n = {}
            for l in rec['lines']:
                if l.get('actor_id') is None:
                    continue
                aid = str(l['actor_id'])
                if l.get('actor'):
                    by_n[l['n']] = cn(l['actor'])
                elif aid in local:
                    by_n[l['n']] = local[aid]
                elif aid in wild:
                    by_n[l['n']] = wild[aid]
                else:
                    by_n[l['n']] = '未知角色'
            if not by_n:
                continue
            bucket = out.setdefault(mid, {}).setdefault(g, {})
            bucket.update(base.get(mid, {}).get(g, {}))
            for i, ln in enumerate(lines):
                a = by_n.get(ln['n']) or by_n.get(i + 1)
                if a:
                    bucket[str(i + 1)] = a
    # 手工/录屏优先级最高
    for mid, groups in manual.items():
        for g, d in groups.items():
            tgt = out.setdefault(mid, {}).setdefault(g, {})
            for k, v in d.items():
                tgt[k] = cn(v) if (v and v[0].isascii()) else v   # 旧值里的英文 id 也翻译

    json.dump(out, open(ov_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    n = sum(len(g) for m in out.values() for g in m.values())
    print(f'overrides: {n} 句（{len(out)} 个任务），已写 {ov_path}')


if __name__ == '__main__':
    main()
