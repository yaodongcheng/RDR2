#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从任务自己的 `<mission_id>.yldb` 里抽取"玩家可见的目标文本"。

说明：这不是 `.ysc` 脚本逻辑。`script_rel.rpf` 仍因 AES key #198 缺失无法解开，
所以拿不到触发器/生成/分支；这里抽取的是任务 UI 的目标与提示字符串（objective / hint），
能还原"玩家在这一关里被要求做什么"。

输出：
  export/levels/world/mission_objectives.csv
  export/levels/world/mission_objectives.json
"""
import csv
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = lambda *p: os.path.join(ROOT, *p)
LANG = W('work/story/lang/chinesesimp')

CJK = re.compile(r'[\u4e00-\u9fff]')
RX = re.compile(rb'(?:[\x20-\x7e]|[\xc2-\xdf][\x80-\xbf]|[\xe0-\xef][\x80-\xbf]{2}){3,}')

# 教学/系统提示（与具体任务无关）
BLOCK = [
    '核心生命值', '核心体力值', '死神之眼', '物品轮盘', '武器轮盘', '武器搭配', '默契',
    '拴马', '校准', '保存', '作弊', 'Social Club', 'Rockstar', '暂停菜单', '小地图',
    '雷达', '按键', '设置', '显示器', '屏幕', '帧数', '教程',
]
# 失败 / 状态反馈，不是目标
FAIL = re.compile(
    r'您跟丢|您离|您掉下|您犯法|您被|离.{0,8}太远|返回.{0,10}处|被惊动|失败了|被抛弃|'
    r'死了|逃走了|被吓坏|惊动了|太远了|犯法了|丢下|被发现了|被击倒')
# 目标动词
VERB = re.compile(
    r'^(前往|跟随|跟上|追上|搜寻|寻找|找到|搜查|搜刮|击退|杀死|抓住|掩护|护送|到达|救出|'
    r'夺回|摧毁|放置|点燃|拦截|审问|捆|扛|找回|追捕|解救|进入|离开|爬上|跳上|安装|引爆|'
    r'清理|保护|守住|骑马|返回|离开|叫|和|与|帮|救|把|从|在|用|检查|追踪|赶|偷|抢|追)'
)


def clean(t: str) -> str:
    t = re.sub(r'~[A-Za-z_]+(\|[^~]*)?~', '', t)   # 富文本 / 按键 token
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def extract(mid):
    """返回 {'objective': [...], 'fail': [...]}；无文件返回 None。"""
    p = os.path.join(LANG, mid.lower() + '.yldb')
    if not os.path.exists(p):
        return None
    d = open(p, 'rb').read()
    objs, fails = [], []
    for m in RX.finditer(d[16:]):
        raw = m.group(0).decode('utf-8', 'ignore')
        if not CJK.search(raw):
            continue
        had_input = '~INPUT' in raw
        t = clean(raw)
        if not t or len(t) > 64:
            continue
        if any(b in t for b in BLOCK):
            continue
        if had_input:          # 控制教学（按键说明）
            continue
        if FAIL.search(t):
            if not t.startswith('返回') and t not in fails:
                fails.append(t)
            continue
        if t.startswith('返回'):      # 导航/回位提示，不是任务目标
            continue
        if not VERB.search(t):
            continue
        if t not in objs:
            objs.append(t)
    return {'objective': objs, 'fail': fails}


def main():
    recs = json.load(open(W('export/levels/world/missions_story.json'), encoding='utf-8'))
    rows = []
    out = {}
    for r in recs:
        res = extract(r['id'])
        if not res:
            continue
        objs, fails = res['objective'], res['fail']
        if not objs and not fails:
            continue
        out[r['id']] = {'objective': objs, 'fail': fails}
        for i, t in enumerate(objs, 1):
            rows.append({'mission_id': r['id'], 'kind': r['kind'], 'chapter': r['chapter'],
                         'type': 'objective', 'seq': i, 'text': t})
        for i, t in enumerate(fails, 1):
            rows.append({'mission_id': r['id'], 'kind': r['kind'], 'chapter': r['chapter'],
                         'type': 'fail', 'seq': i, 'text': t})
    with open(W('export/levels/world/mission_objectives.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['mission_id', 'kind', 'chapter', 'type', 'seq', 'text'])
        w.writeheader()
        w.writerows(rows)
    json.dump(out, open(W('export/levels/world/mission_objectives.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    main_ids = {r['id'] for r in recs if r['kind'] == 'main'}
    main_n = sum(1 for k in out if k in main_ids)
    n_obj = sum(len(v['objective']) for v in out.values())
    n_fail = sum(len(v['fail']) for v in out.values())
    print('有文本的任务 %d（主线 %d）；目标 %d 条，失败条件 %d 条' % (len(out), main_n, n_obj, n_fail))


if __name__ == '__main__':
    main()
