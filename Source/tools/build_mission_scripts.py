#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""脚本级任务信息解析。

数据源：社区反编译的 RDR2 脚本库（build 1355，`script_rel/` 下 1639 个 `.c`）。
校验：本机 `script_rel.rpf` 的 RPF 条目数也是 **1639**，与仓库文件数一致。

做的事：
  1. 任务 ID → 脚本文件（按脚本内 `<ID>_...` 文本键计数匹配）
  2. 抽目标键 `<ID>_OBJ*` → 用任务自己的 yldb 解析成中文
  3. 统计生成调用点（ped / vehicle / object）、失败判定、过场、高频 native
  4. 输出 CSV / JSON

注意：计数是**调用点**，不是运行时实际生成数量。
"""
import csv
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from yldb_keys import Yldb  # noqa: E402

W = lambda *p: os.path.join(ROOT, *p)
LOCAL_SRC = W('work/script_probe/script_src')
SCRIPTS = LOCAL_SRC if os.path.isdir(LOCAL_SRC) else os.path.join(os.environ.get('TEMP', ''), 'rdr3dec', '1355', 'script_rel')
LANG = W('work/story/lang/chinesesimp')

NATIVE_RX = re.compile(r'\b([A-Z][A-Z0-9_]+)::([A-Z][A-Z0-9_]+)')
FUNC_RX = re.compile(r'\n\s*(?:void|int|float|bool|var|vector3|struct<[^>]*>)\s+func_\d+\s*\(')
SPAWNS = {
    'ped': r'PED::CREATE_PED\b',
    'vehicle': r'VEHICLE::CREATE_VEHICLE\b',
    'object': r'OBJECT::CREATE_OBJECT\b|OBJECT::CREATE_OBJECT_NO_OFFSET\b',
    'pickup': r'OBJECT::CREATE_PICKUP\w*',
}
FAILS = ['IS_ENTITY_DEAD', 'IS_PED_DEAD_OR_DYING', 'IS_PLAYER_DEAD', 'IS_ENTITY_DEAD_OR_DYING',
         'IS_PED_INCAPACITATED']


def load_yldb(mid):
    base = mid.lower()
    for cand in (base, re.sub(r'\d$', '', base), re.sub(r'\d+$', '', base)):
        p = os.path.join(LANG, cand + '.yldb')
        if os.path.exists(p):
            return Yldb(p)
    return None


def clean_text(t):
    if not t:
        return ''
    t = re.sub(r'~[A-Za-z_]+(\|[^~]*)?~', '', t)
    return re.sub(r'\s+', ' ', t).strip()


MANUAL = {
    'RCLDN2': 'rcm_calderon2.c',
    'RBNP21': 'rcm_beau_and_penelope21.c',
}


def main():
    recs = json.load(open(W('export/levels/world/missions_story.json'), encoding='utf-8'))
    mapping = json.load(open(W('work/script_probe/script_map_raw.json'), encoding='utf-8'))
    for k, v in MANUAL.items():
        if os.path.exists(os.path.join(SCRIPTS, v)):
            mapping[k] = [5, v]
    out = {}
    rows = []

    for r in recs:
        mid = r['id']
        hit = mapping.get(mid)
        if not hit:
            continue
        cnt, fname = hit
        path = os.path.join(SCRIPTS, fname)
        if not os.path.exists(path):
            continue
        s = open(path, encoding='utf-8', errors='ignore').read()
        y = load_yldb(mid)

        # 自动识别该脚本的文本键前缀（任务 ID 不一定等于脚本内部前缀）
        BLOCK_PRE = {'CSTAG', 'COL', 'JOURNAL', 'WEAPON', 'INPUT', 'SHOP', 'REGION', 'AMMO', 'CS',
                     'PROVISION', 'MISSION', 'AF', 'MP', 'UI', 'PLAYER', 'HUD', 'TEXT', 'SOUND',
                     'ANIM', 'PED', 'VEH', 'OBJ', 'ITEM', 'PROP', 'AC', 'ACH', 'STAT', 'FM', 'NET'}
        by_pre = {}
        for m in re.finditer(r'"([A-Z][A-Z0-9]{1,8})_([A-Z0-9_]*)"', s):
            by_pre.setdefault(m.group(1), set()).add(m.group(0)[1:-1])
        cands = [p for p, ks in by_pre.items() if p not in BLOCK_PRE and len(ks) >= 3]
        cands.sort(key=lambda p: -len(by_pre[p]))

        def resolve_key(k):
            return clean_text(y.get(k)) if y else ''

        best_pre, best_score = mid, 0
        for p in cands[:10]:
            ks = list(by_pre[p])[:25]
            score = sum(1 for k in ks if resolve_key(k))
            if score > best_score:
                best_pre, best_score = p, score
        # 若任务 ID 本身可解析，优先用 ID
        id_keys_all = list(by_pre.get(mid, []))
        if id_keys_all and sum(1 for k in id_keys_all[:25] if resolve_key(k)) >= best_score:
            best_pre = mid

        use_pre = best_pre if best_score or best_pre == mid else mid
        keys = []
        for m in re.finditer(r'"(' + re.escape(use_pre) + r'_[A-Z0-9_]*)"', s):
            k = m.group(1)
            if k not in keys:
                keys.append(k)
        keys = keys[:500]

        objs, fails, texts = [], [], []
        for k in keys:
            txt = resolve_key(k)
            if not txt:
                continue
            ku = k.upper()
            item = {'key': k, 'text': txt}
            if 'HELP' in ku or '_H_' in ku or ku.endswith('_H'):
                if len(texts) < 15:
                    texts.append(item)
                continue
            is_fail = any(w in txt for w in ('失败', '已无法', '被惊动', '逃走', '太远', '死了', '未检查',
                                            '犯法', '被抛弃', '被吓坏', '被丢', '无法驾驶', '已失去'))
            is_obj = (('OBJ' in ku) or bool(re.match(
                r'^(前往|跟随|寻找|找到|搜查|搜刮|击退|杀死|抓住|掩护|护送|到达|救出|夺回|摧毁|放置|点燃|'
                r'拦截|审问|捆|扛|找回|追捕|解救|进入|离开|爬上|跳上|安装|引爆|清理|保护|守住|骑马|返回|'
                r'回去|和|与|帮|把|将|从|用|检查|追踪|赶|偷|抢|追|运到|送|带|救|打|守)', txt)))
            if is_fail and len(fails) < 20:
                fails.append(item)
            elif is_obj and len(txt) <= 60 and len(objs) < 40:
                objs.append(item)
            elif len(txt) <= 60 and len(texts) < 15:
                texts.append(item)

        spawn = {k: len(re.findall(v, s)) for k, v in SPAWNS.items()}
        fail_natives = {n: len(re.findall(r'\b' + n + r'\b', s)) for n in FAILS}
        fail_natives = {k: v for k, v in fail_natives.items() if v}

        cuts = []
        for m in re.finditer(r'"(script@[Ss]tory@[^"]+)"', s):
            v = m.group(1)
            if v not in cuts:
                cuts.append(v)

        nat = Counter()
        for a, b in NATIVE_RX.findall(s):
            nat[a + '::' + b] += 1

        rec = {
            'id': mid,
            'script': fname,
            'confidence': 'strong' if cnt >= 10 else 'weak',
            'id_keys': cnt,
            'lines': s.count('\n') + 1,
            'funcs': len(FUNC_RX.findall(s)),
            'prefix': use_pre,
            'prefix_score': best_score,
            'objectives': objs,
            'texts': texts,
            'spawn': spawn,
            'fails': fails,
            'fail_natives': fail_natives,
            'fail_natives': fail_natives,
            'cutscenes': cuts[:6],
            'top_natives': nat.most_common(10),
        }
        out[mid] = rec
        rows.append({
            'mission_id': mid, 'kind': r['kind'], 'chapter': r['chapter'],
            'script': fname, 'confidence': rec['confidence'], 'id_keys': cnt,
            'lines': rec['lines'], 'funcs': rec['funcs'],
            'objectives': len(objs), 'fails': len(fails),
            'objective_texts': ';'.join(o['text'] or o['key'] for o in objs[:8]),
            'spawn_ped': spawn['ped'], 'spawn_vehicle': spawn['vehicle'],
            'spawn_object': spawn['object'],
        })

    json.dump(out, open(W('export/levels/world/mission_scripts.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    with open(W('export/levels/world/mission_scripts.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    main_n = sum(1 for k, v in out.items() if any(r['id'] == k and r['kind'] == 'main' for r in recs))
    strong = sum(1 for v in out.values() if v['confidence'] == 'strong')
    print('脚本解析 %d 条任务（主线 %d），强匹配 %d；目标键合计 %d' % (
        len(out), main_n, strong, sum(len(v['objectives']) for v in out.values())))


if __name__ == '__main__':
    main()
