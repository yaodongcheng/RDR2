#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""主线 AVG 化：把 105 个主线任务拆成「玩家观看段（过场）」与「实际游玩段」。

为什么能拆
----------
RDR2 每个任务脚本里都有一张**过场段链**（本文件 `parse_chain` 解析），形如：

    func_784(uParam0, iLocal_81, iLocal_82, 116734, 116743, 116913, 117093, 117139,
             "WNT1_INT_WAGON", 2, -1);
    func_784(uParam0, iLocal_84, iLocal_85, 119870, 119879, 120161, 120378, 120772,
             "", 0, -1);                       ← 空名字 = **纯游玩段**

签名 `(参数块, 状态from, 状态to, mark1..mark5, 过场名, flag, clip数)`。
- 过场名非空 → 该状态下播一段过场（= 观看阶段）
- 过场名为空 → 该状态是纯游玩（= 实际游玩阶段）

mark1..mark5 与 `story/cutscene/mission_timeline.json` 里的 `marks` 逐值相同，
因此可以反查该段的**时长 / 镜头数 / 累计起始时间**。

台词从哪来
----------
过场字幕在任务音频库（`<mid>aud.yldb`）里以 `<过场名>_<序号>` 为键；
每行的说话人来自 `story/conversation_actors.json`（handle）
+ `story/speaker_overrides.json`（中文名）。

游玩段的「去哪里 / 找谁 / 打谁」
--------------------------------
不是猜的：目标文案本身是 yldb 原文，按动词归类 + 与任务 cast 名做最长匹配：

    与达奇交谈 → talk  找「达奇」说话
    跟随迈卡   → follow  跟着「迈卡」
    击退攻击者 → fight  打「攻击者」
    前往火车头 → goto   去「火车头」

坐标来自 `levels/world/mission_coords.json`（脚本里解析出的真实坐标点聚类），
据点来自 `settlements.json`。有 `mission_events.json` 的任务还能拿到逐步骤字面坐标。

输出
----
  export/levels/world/avg_main.json     全部任务的结构化 AVG 剧本 + 游玩步骤
  export/avg/data/missions/<MID>.json   单任务拆件（页面按需加载）
"""
import json
import os
import re
import sys
import math
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'D:/BrainMaker/大镖客2解包分析'
SRC = os.path.join(ROOT, 'raw/script_full/1491.50')
LANG = os.path.join(ROOT, 'raw/story/lang/chinesesimp')
EXP = os.path.join(ROOT, 'export')
W = os.path.join(EXP, 'levels/world')
ST = os.path.join(EXP, 'story')

sys.path.insert(0, os.path.join(ROOT, 'tools'))
from yldb_keys import Yldb  # noqa: E402


# ---------------------------------------------------------------- 基础工具
RICH = re.compile(r'~[A-Za-z_]+[^~]*~')
def clean(t):
    if not t:
        return ''
    t = RICH.sub('', t)
    return re.sub(r'\s+', ' ', t).strip()


def jload(p, default=None):
    if not os.path.exists(p):
        return default
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def jdump(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- 过场段链
CALL_RE = re.compile(r'^[ \t]*func_\d+\s*\((?P<args>[^;]*?)\)\s*;', re.M)


def _split_args(s):
    """按顶层逗号切参数（本场景无嵌套括号，直接切即可）。"""
    return [x.strip() for x in s.split(',')]


def parse_chain(text):
    """从脚本里取最长的那一段连续「过场段注册」调用。

    签名: (参数块, from, to, m1..m5, "过场名或 0", flag, clips)
    只认：至少 11 个参数、2~6 号是 5~8 位整数、7 号是字符串字面量或 0。
    """
    cand = []
    for m in CALL_RE.finditer(text):
        a = _split_args(m.group('args'))
        if len(a) < 11:
            continue
        if not all(re.fullmatch(r'\d{5,8}', a[i]) for i in range(3, 8)):
            continue
        nm = a[8]
        if not (nm == '0' or re.fullmatch(r'"[^"]*"', nm)):
            continue
        if not re.fullmatch(r'-?\d+', a[10]):
            continue
        cand.append({
            'line': text.count('\n', 0, m.start()) + 1,
            'from': a[1], 'to': a[2],
            'marks': [int(a[i]) for i in range(3, 8)],
            'name': '' if nm == '0' else nm.strip('"'),
            'flag': a[9], 'clips': int(a[10]),
        })
    if not cand:
        return []
    # 按行号邻近切 run（相邻调用行号差 ≤ 2），取最长
    runs, cur = [], [cand[0]]
    for a, b in zip(cand, cand[1:]):
        if b['line'] - a['line'] <= 2:
            cur.append(b)
        else:
            runs.append(cur)
            cur = [b]
    runs.append(cur)
    best = max(runs, key=len)
    return best


# ---------------------------------------------------------------- 角色表
# handle（conversation_actors 里的短名）→ cs 模型 / 玩家模型
HANDLE_MODEL = {
    'arthur': 'player_zero',
    'player': 'player_zero',
    'john': 'cs_johnmarston_ms1',
    'john_player': 'cs_johnmarston_ms1',
    'john_marston': 'cs_johnmarston_ms1',
    'dutch': 'cs_dutch_ms1',
    'hosea': 'cs_hoseamatthews_ms1',
    'micah_bell': 'cs_micahbell_ms1',
    'micah': 'cs_micahbell_ms1',
    'sadie_adler': 'cs_mrsadler_fs1',
    'sadie': 'cs_mrsadler_fs1',
    'abigail': 'cs_abigailroberts_fs1',
    'abigail_roberts': 'cs_abigailroberts_fs1',
    'marybeth': 'cs_marybeth_fs1',
    'mary_beth': 'cs_marybeth_fs1',
    'trelawny': 'cs_josiahtrelawny_ms1',
    'treawny': 'cs_josiahtrelawny_ms1',
    'uncle': 'cs_uncle_ms1',
    'charles_smith': 'cs_charlessmith_ms1',
    'charles': 'cs_charlessmith_ms1',
    'bill': 'cs_billwilliamson_ms1',
    'bill_williamson': 'cs_billwilliamson_ms1',
    'beau_gray': 'cs_beaugray_ms1',
    'susan': 'cs_susangrimshaw_fs1',
    'grimshaw': 'cs_susangrimshaw_fs1',
    'clay': 'cs_clay_ms1',
    'karen': 'cs_karen_fs1',
    'karen_jones': 'cs_karen_fs1',
    'tilly': 'cs_tilly_fs1',
    'tilly_jackson': 'cs_tilly_fs1',
    'pearson': 'cs_mrpearson_ms1',
    'simon_pearson': 'cs_mrpearson_ms1',
    'strauss': 'cs_leostrauss_ms1',
    'leopold_strauss': 'cs_leostrauss_ms1',
    'sean': 'cs_sean_ms1',
    'sean_macguire': 'cs_sean_ms1',
    'swanson': 'cs_revswanson_ms1',
    'orville_swanson': 'cs_revswanson_ms1',
    'javier': 'cs_javierescuella_ms1',
    'javier_escuella': 'cs_javierescuella_ms1',
    'cornwall': 'cs_leviticuscornwall_ms1',
    'lenny': 'cs_lenny_ms1',
    'lenny_summers': 'cs_lenny_ms1',
    'teen_jack': 'cs_jackmarston_teen_ms1',
    'jack': 'cs_jackmarston_ms1',
    'rrch1_abe': 'cs_abe_ms1',
    'thomas_downes': 'cs_thomasdown_ms1',
    'molly': 'cs_mollyoshea_fs1',
    'molly_oshea': 'cs_mollyoshea_fs1',
    'cleet': 'cs_cleet_ms1',
    'kieran': 'cs_kieran_ms1',
    'mary': 'cs_marylinton_fs1',
    'mary_linton': 'cs_marylinton_fs1',
    'rains_fall': 'cs_rainsfall_ms1',
    'rainsfall': 'cs_rainsfall_ms1',
    'eagle_flies': 'cs_eagleflies_ms1',
    'captain_monroe': 'cs_captainmonroe_ms1',
    'monroe': 'cs_captainmonroe_ms1',
    'brontë': 'cs_bronte_ms1',
    'bronte': 'cs_bronte_ms1',
    'evelyn_miller': 'cs_evelynmiller_ms1',
    'leviticus_cornwall': 'cs_leviticuscornwall_ms1',
}

# speaker_overrides 里没用到的原生 handle 中文兜底
CN_FALLBACK = {
    'arthur': '亚瑟', 'john': '约翰', 'dutch': '达奇', 'abigail': '阿比盖尔',
    'hosea': '何西阿', 'susan': '苏珊', 'swanson': '斯旺森', 'charles_smith': '查尔斯',
    'bill': '比尔', 'javier': '哈维尔', 'micah': '迈卡', 'micah_bell': '迈卡',
    'sadie': '莎迪', 'sadie_adler': '莎迪', 'uncle': '大叔', 'jack': '杰克',
    'teen_jack': '少年杰克', 'karen': '凯伦', 'tilly': '蒂莉', 'strauss': '施特劳斯',
    'pearson': '皮尔逊', 'molly': '莫莉', 'sean': '西恩', 'lenny': '蓝尼',
    'mary': '玛丽', 'trelawny': '特里劳尼', 'treawny': '特里劳尼',
    'grimshaw': '格里姆肖', 'marybeth': '玛丽-贝丝', 'cornwall': '康沃尔',
    'beau_gray': '博·格雷', 'clay': '克莱', 'cleet': '克利特', 'kieran': '基兰',
    'thomas_downes': '托马斯·唐斯', 'rrch1_abe': '亚伯', 'emr_son1': '埃米特之子',
}

GENERIC_F = ('_fs1', '_f_', 'sister', 'lady', 'woman', 'girl', 'wife', 'mother',
             'widow', 'madam', 'mrs', 'dowd', 'nun')


def model_for(handle, gender_hint_female=False):
    m = HANDLE_MODEL.get(handle)
    if m:
        return m
    h = handle.lower()
    if any(k in h for k in GENERIC_F):
        return 'generic_female_01'
    if re.match(r'^\d{4}_', h):
        # 0012_s_m_m_ispworker_02_black_02 这类原生 ped id：_f_ 是女，其余男
        return 'generic_female_01' if '_f_' in h else 'generic_male_01'
    return 'generic_male_01'


# ---------------------------------------------------------------- 目标文案语义
TALK = ('交谈', '谈话', '对话', '谈论', '聊', '打听', '询问', '问话', '搭话')
FIGHT = ('击退', '杀死', '消灭', '干掉', '射杀', '爆头', '解决掉', '击败',
         '杀掉', '刺杀', '打')
PROTECT = ('保护', '掩护', '护送', '营救', '守护', '救下')
FOLLOW = ('跟随', '跟上', '追上', '追赶', '追', '跟踪', '尾随')
GOTO = ('前往', '到达', '去往', '前往', '进入', '离开', '逃离', '来到', '抵达')
LOOT = ('搜刮', '洗劫', '搜寻', '搜查', '拾取', '拿走', '偷走', '翻找', '寻找')
CARRY = ('扛起', '抬起', '捆绑', '套索', '拖', '抱', '扶')
INTERACT = ('靠近', '使用', '轻拍', '安抚', '抚摸', '操作', '查看', '检查', '调查', '观察')


def classify_obj(text):
    """把一句目标文案归类成 act + target。全部基于原文规则，不改写文案。"""
    t = text.strip().rstrip('。;; ,')
    act = 'other'
    if any(k in t for k in TALK):
        act = 'talk'
    elif any(k in t for k in PROTECT):
        act = 'protect'
    elif any(k in t for k in FIGHT):
        act = 'fight'
    elif any(k in t for k in FOLLOW):
        act = 'follow'
    elif any(k in t for k in CARRY):
        act = 'carry'
    elif any(k in t for k in INTERACT):
        act = 'interact'
    elif any(k in t for k in LOOT):
        act = 'loot'
    elif any(k in t for k in GOTO):
        act = 'goto'
    return act


def extract_target(text, names):
    """从目标文案里挑出最长的已知 cast 名（找谁 / 打谁）。"""
    best = ''
    for n in names:
        if len(n) >= 2 and n in text and len(n) > len(best):
            best = n
    return best


# ---------------------------------------------------------------- 主流程
def main():
    missions = jload(os.path.join(W, 'missions_story.json'), [])
    main_ms = [m for m in missions if m.get('kind') == 'main']
    smap = jload(os.path.join(EXP, 'story/script_map.json'), {})
    timeline = jload(os.path.join(ST, 'cutscene/mission_timeline.json'), {})
    conv_actors = jload(os.path.join(ST, 'conversation_actors.json'), {})
    spk_ov = jload(os.path.join(ST, 'speaker_overrides.json'), {})
    objectives = jload(os.path.join(W, 'mission_objectives.json'), {})
    coords = jload(os.path.join(W, 'mission_coords.json'), {})
    settlements = jload(os.path.join(W, 'settlements.json'), {}).get('settlements', [])
    events = jload(os.path.join(W, 'mission_events.json'), {})
    steps_db = jload(os.path.join(W, 'mission_steps.json'), {})
    per_mission_dir = os.path.join(ST, 'cutscene/per_mission')

    # ---- 据点最近邻
    def nearest_settlement(x, y):
        best, bd = None, 1e18
        for s in settlements:
            d = (s['cx'] - x) ** 2 + (s['cy'] - y) ** 2
            if d < bd:
                bd, best = d, s
        if not best:
            return None, None
        return best, math.sqrt(bd)

    # ---- 句柄→中文名（用 speaker_overrides 投票）
    votes = defaultdict(Counter)
    for mid, groups in spk_ov.items():
        for g, m in groups.items():
            ca = conv_actors.get(g.upper())
            if not ca:
                continue
            for ln in ca.get('lines', []):
                who = m.get(str(ln.get('n')))
                if who and ln.get('actor'):
                    votes[ln['actor']][who] += 1

    def zh_of(handle):
        if votes.get(handle):
            return votes[handle].most_common(1)[0][0]
        return CN_FALLBACK.get(handle, handle)

    # ---- 银行缓存
    banks = {}

    def _probe(y, name):
        out = []
        n = 1
        while n <= 400:
            v = y.get('%s_%d' % (name.upper(), n))
            if v is None:
                if n > 1:
                    break
                n += 1
                continue
            out.append((n, clean(v)))
            n += 1
        return out

    def bank_lines(mid, csname):
        m = next((x for x in main_ms if x['id'] == mid), None)
        if not m:
            return []
        bank = m.get('dialogue_bank') or ''
        if not bank:
            return []
        p = os.path.join(LANG, bank)
        if not os.path.exists(p):
            return []
        if p not in banks:
            banks[p] = Yldb(p)
        y = banks[p]
        # 过场在脚本里用的是**资产名**（如 ODR1_INT），字幕却常挂在**任务名**上
        # （如 DST1_INT）——两种都试一遍。
        got = _probe(y, csname)
        if not got and '_' in csname:
            alt = mid + '_' + csname.split('_', 1)[1]
            got = _probe(y, alt)
        return got

    # ---- 背景键：优先最近据点，否则任务专属点
    used_settlements = Counter()
    mission_bg = {}

    out_missions = []
    stats = Counter()
    char_registry = {}

    for m in sorted(main_ms, key=lambda z: (z.get('chapter') or 0, z.get('order') or 0)):
        mid = m['id']
        sm = smap.get(mid) or []
        script = sm[0] if sm else ''
        sp = os.path.join(SRC, script) if script else ''
        text = open(sp, encoding='utf-8', errors='ignore').read() if os.path.exists(sp) else ''
        chain = parse_chain(text)

        # 坐标 / 地点
        ck = script
        cdat = coords.get(ck) or {}
        prim = cdat.get('primary') or {}
        loc = {}
        if prim:
            x, y, z = prim.get('x'), prim.get('y'), prim.get('z')
            s, dist = nearest_settlement(x, y)
            loc = {
                'x': round(x, 1), 'y': round(y, 1), 'z': round(z, 1),
                'radius': round(prim.get('radius') or 0, 1),
                'n_points': cdat.get('n_points'),
                'settlement': (s or {}).get('code'),
                'settlement_zh': (s or {}).get('name_zh'),
                'settlement_dist_m': round(dist, 0) if dist is not None else None,
            }
            for c in (cdat.get('clusters') or [])[1:5]:
                pass
            loc['clusters'] = [{'x': round(c['x'], 1), 'y': round(c['y'], 1),
                                'z': round(c['z'], 1), 'n': c.get('n'),
                                'r': round(c.get('radius') or 0, 1)}
                               for c in (cdat.get('clusters') or [])[:4]]
        if not loc:
            # 没有坐标点（多为 rcm_* 同伴任务）：用章节营地兜底，保证 AVG 有背景
            cn = m.get('chapter_name') or ''
            hit = next((s for s in settlements if s.get('name_zh') and s['name_zh'] in cn), None)
            if hit:
                loc = {'x': round(hit['cx'], 1), 'y': round(hit['cy'], 1),
                       'z': round(hit.get('cz') or 0, 1), 'radius': round(hit.get('size_w') or 0, 1),
                       'settlement': hit['code'], 'settlement_zh': hit['name_zh'],
                       'source': 'chapter-camp'}
        if not loc:
            for s in settlements:
                if s['code'] == 'val':
                    loc = {'x': round(s['cx'], 1), 'y': round(s['cy'], 1),
                           'z': round(s.get('cz') or 0, 1), 'radius': round(s.get('size_w') or 0, 1),
                           'settlement': 'val', 'settlement_zh': s['name_zh'],
                           'source': 'default'}
                    break
        bgkey = (loc.get('settlement') or ('m_' + mid.lower()))
        mission_bg[mid] = bgkey
        used_settlements[bgkey] += 1

        # 台词 / 过场元数据
        tl = timeline.get(os.path.splitext(script)[0]) if script else None
        tl_by_mark = {}
        if tl:
            for cs in tl.get('cutscenes', []):
                mk = cs.get('marks') or []
                if mk:
                    tl_by_mark[mk[0]] = cs
        pm = jload(os.path.join(per_mission_dir, mid + '.json'), {}) or {}
        pm_by_name = {}
        for cs in pm.get('cutscenes', []):
            pm_by_name[cs['cutscene'].lower()] = cs
            pm_by_name[cs['cutscene'].upper()] = cs

        cast = m.get('cast') or []
        segs = []

        def build_cutscene(segno, name, state_from=None, state_to=None, marks=None):
            key = name.upper()
            info = tl_by_mark.get((marks or [0])[0]) if marks else None
            if info is None and tl:
                for cs in tl.get('cutscenes', []):
                    if cs['name'].upper() == key:
                        info = cs
                        break
            pminfo = pm_by_name.get(name.lower()) or pm_by_name.get(key) or {}
            raw = bank_lines(mid, name)
            altkey = (mid + '_' + name.split('_', 1)[1]).upper() if '_' in name else key
            ov = (spk_ov.get(mid, {}) or {}).get(key) or (spk_ov.get(mid, {}) or {}).get(altkey) or {}
            ca = conv_actors.get(key) or conv_actors.get(altkey) or {}
            ca_by_n = {str(l.get('n')): l.get('actor') for l in ca.get('lines', [])}
            lines = []
            for n, zh in raw:
                handle = ca_by_n.get(str(n))
                who = ov.get(str(n)) or (zh_of(handle) if handle else '')
                lines.append({'n': n, 'who': who, 'handle': handle, 'zh': zh})
                if handle:
                    char_registry.setdefault(handle, {
                        'zh': zh_of(handle),
                        'model': model_for(handle),
                    })
            actors_cs = []
            for shot in pminfo.get('shot_list', []):
                for a in shot.get('actors', []):
                    if a not in actors_cs:
                        actors_cs.append(a)
            return {
                'no': segno, 'kind': 'cutscene', 'name': name,
                'state': [state_from, state_to],
                'duration_s': info.get('duration') if info else None,
                'shots': info.get('shots') if info else None,
                'start_s': info.get('start') if info else None,
                'marks': marks,
                'cutscene_models': actors_cs,
                'speakers': sorted({l['who'] for l in lines if l['who']}),
                'lines': lines,
                'bg': bgkey,
            }

        if chain:
            segno = 0
            for seg in chain:
                segno += 1
                if seg['name']:
                    segs.append(build_cutscene(segno, seg['name'], seg['from'], seg['to'], seg['marks']))
                else:
                    segs.append({'no': segno, 'kind': 'gameplay',
                                 'name': None, 'state': [seg['from'], seg['to']],
                                 'baseline': 'chain-empty-name', 'bg': bgkey})
            basis_seg = 'script-chain'
        else:
            # 兜底：用 missions_story 的过场清单，全部当开场/中段/收尾，中间 1 个游玩块
            segno = 0
            for csname in (m.get('cutscene_scenes') or []):
                segno += 1
                segs.append(build_cutscene(segno, csname))
            segno += 1
            segs.append({'no': segno, 'kind': 'gameplay', 'name': None,
                         'baseline': 'fallback-single-block', 'bg': bgkey})
            basis_seg = 'fallback'

        # ---- 目标 / 失败 / 挑战
        od = objectives.get(mid) or {}
        objs = od.get('objective') or []
        fails = od.get('fail') or []
        steps = (steps_db.get(mid) or {}).get('steps') or []
        ev = (events.get(mid) or {}).get('steps') or {}

        # 有序目标：优先 mission_steps 的步骤顺序，否则原文顺序
        ordered = []   # [(text, step_no, None)]
        seen = set()
        if steps:
            for st in steps:
                for o in st.get('objectives', []):
                    if o in seen:
                        continue          # 同一条目标在多个步骤里重复出现，只保留首次
                    seen.add(o)
                    ordered.append((o, st.get('step'), None))
            for o in objs:
                if o not in seen:
                    seen.add(o)
                    ordered.append((o, None, None))
        else:
            for o in objs:
                if o in seen:
                    continue
                seen.add(o)
                ordered.append((o, None, None))

        # 逐步骤字面坐标（mission_events）
        coord_by_obj = {}
        if ev:
            for sno, evs in ev.items():
                cs = []
                for e in evs:
                    # 坐标一定是**带小数点**的三元组，且落在世界框内
                    # （x∈[-6844,3924] y∈[-4800,3224] z∈[-60,800]）。
                    # 任务脚本里有两种写法：func(0, (x,y,z), ...) 与 func(0, x, y, z, ...)，
                    # 两种都要认；用世界框把 (speed, timeout, radius) 这类参数筛掉。
                    for mm in re.finditer(r'(-?\d+\.\d+)f?\s*,\s*(-?\d+\.\d+)f?\s*,\s*(-?\d+\.\d+)f?',
                                          e.get('args', '')):
                        x, y, z = float(mm.group(1)), float(mm.group(2)), float(mm.group(3))
                        if (-6844 <= x <= 3924 and -4800 <= y <= 3224 and -60 <= z <= 800
                                and max(abs(x), abs(y)) > 300):
                            cs.append([round(x, 1), round(y, 1), round(z, 1)])
                            break
                if cs:
                    coord_by_obj[str(sno)] = cs[0]

        # 目标文案用的是简称（迈卡），cast 里是全名（迈卡·贝尔）→ 两种都要能匹配
        vs = set()
        for c in cast:
            if len(c) < 2:
                continue
            vs.add(c)
            short = re.split(r'[·・（(]', c)[0].strip()
            if len(short) >= 2:
                vs.add(short)
        names = sorted(vs, key=len, reverse=True)
        cards = []
        for i, (o, sno, _) in enumerate(ordered):
            act = classify_obj(o)
            tgt = extract_target(o, names)
            c = coord_by_obj.get(str(sno)) if sno else None
            cards.append({
                'i': i + 1,
                'objective': o,
                'act': act,
                'target': tgt or None,
                'coord': c,
                'step': sno,
            })

        # ---- 把目标卡分到各游玩段
        gp = [s for s in segs if s['kind'] == 'gameplay']
        if gp and cards:
            n = len(gp)
            for k, s in enumerate(gp):
                lo = round(k * len(cards) / n)
                hi = round((k + 1) * len(cards) / n)
                s['steps'] = cards[lo:hi]
                s['fail'] = fails
            basis_obj = 'steps-order-proportional' if steps else 'yldb-order-proportional'
        else:
            basis_obj = 'none'

        # 概览
        cut = [s for s in segs if s['kind'] == 'cutscene']
        out_missions.append({
            'id': mid,
            'order': m.get('order'),
            'chapter': m.get('chapter'),
            'chapter_name': m.get('chapter_name'),
            'title_zh': m.get('title_zh'),
            'title_en': m.get('title_en'),
            'desc_zh': m.get('desc_zh'),
            'script': script,
            'cast': cast,
            'challenges': m.get('challenges') or [],
            'dialogue_lines': m.get('dialogue_lines'),
            'location': loc,
            'segments': segs,
            'objectives_all': objs,
            'fails_all': fails,
            'basis': {'segments': basis_seg, 'objective_assign': basis_obj},
            'stats': {
                'segments': len(segs),
                'cutscene_segs': len(cut),
                'gameplay_segs': len(gp),
                'cutscene_s': round(sum((s.get('duration_s') or 0) for s in cut), 1),
                'lines': sum(len(s.get('lines') or []) for s in cut),
                'objectives': len(objs),
                'steps_cards': len(cards),
            },
        })
        stats['missions'] += 1
        stats['with_chain'] += 1 if chain else 0
        stats['segments'] += len(segs)
        stats['cutscene_segs'] += len(cut)
        stats['gameplay_segs'] += len(gp)
        stats['lines'] += sum(len(s.get('lines') or []) for s in cut)
        stats['named_lines'] += sum(1 for s in cut for l in (s.get('lines') or []) if l.get('who'))
        stats['objectives'] += len(objs)
        stats['missions_with_lines'] += 1 if any((s.get('lines') for s in cut)) else 0

    # ---- 输出
    payload = {
        'generated': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M'),
        'note': '主线任务的「观看段(过场) / 游玩段」拆分。观看段来自脚本过场段链；'
                '游玩段=链上过场名为空的状态；目标是 yldb 原文，按动词归类。',
        'settlements_used': dict(used_settlements),
        'chars': char_registry,
        'missions': out_missions,
        'stats': dict(stats),
    }
    jdump(os.path.join(W, 'avg_main.json'), payload)

    # 单任务拆件目录（页面按需加载，避免一个 10 MB 的 JSON）
    mdir = os.path.join(EXP, 'avg/data/missions')
    os.makedirs(mdir, exist_ok=True)
    for mm in out_missions:
        jdump(os.path.join(mdir, mm['id'] + '.json'), mm)
    jdump(os.path.join(EXP, 'avg/data/index.json'), {
        'generated': payload['generated'],
        'chars': char_registry,
        'missions': [{k: mm[k] for k in ('id', 'order', 'chapter', 'chapter_name',
                                         'title_zh', 'title_en', 'desc_zh',
                                         'location', 'stats', 'basis')} for mm in out_missions],
    })

    print('== AVG 主线拆分 ==')
    for k, v in payload['stats'].items():
        print('  %-26s %s' % (k, v))
    print('  有台词的任务 / 总任务       %s / %s' % (payload['stats']['missions_with_lines'], payload['stats']['missions']))
    print('  不同说话人(handle)          %s' % len(char_registry))
    print('  不同背景地点                %s' % len(used_settlements))
    print('  输出                        %s' % os.path.join(W, 'avg_main.json'))
    print('  输出                        %s' % os.path.join(EXP, 'avg/data/index.json'))


if __name__ == '__main__':
    main()
