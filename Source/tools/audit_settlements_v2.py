# -*- coding: utf-8 -*-
"""骑砍2 落地据点审计 v2 —— 用解包实体反查模型前缀，验证"这个据点到底能不能看见"。

对每个据点：
  · 在据点中心半径内取实例（`export/world/continent/tiles/*.json`）
  · 用 `export/levels/town/archetypes.json` 的包围盒判"建筑"（最大边 ≥8 m）
  · 用 `assets/lib_native/index.json` 判"有没有网格"（能不能真的摆出来）
  · 用 `names.txt` 的 joaat 表把 hash 还原成模型名（用于核对前缀）

修正项（相对 v1 的 `settlements_world.csv`）：
  wap 瓦匹提        (627.4, 2049.7) → (456, 2226)
  gap 裂齿矿洞      (-5568.4,-2926.7) → (-5986, -3211)
  lnn 朗尼小屋      (1897.6,-464.6) → lon (-852, -747)
新增：
  roc 威拉德歇脚处 / hso 马蹄铁眺望 / abe 阿伯丁猪场

产物：
  deliverable/handoff/settlement_audit.csv
  work/bannerlord_settlement_table.md   （文档用的 markdown 表）
"""
import os
import csv
import json
import glob
import math

ROOT = r'D:/BrainMaker/大镖客2解包分析'
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
ARCH = os.path.join(ROOT, 'export/levels/town/archetypes.json')
LIB = os.path.join(ROOT, 'assets/lib_native/index.json')
CSV_IN = os.path.join(ROOT, 'deliverable/handoff/settlements_world_v2.csv')
CSV_OUT = os.path.join(ROOT, 'deliverable/handoff/settlement_audit.csv')
MD_OUT = os.path.join(ROOT, 'deliverable/handoff/settlement_audit.md')

FIX = {}   # v2 清单里坐标已修正
ADD = [
    ('roc', '威拉德之息', "Willard's Rest", 'poi', 2989.0, 2189.0,
     '夏洛蒂·贝尔福的家（A New Future 三部曲）'),
    ('hso', '马掌望台', 'Horseshoe Overlook', 'camp', -126.0, -34.0,
     '第 2 章范德林德营地'),
    ('abe', '阿伯丁猪场', 'Aberdeen Pig Farm', 'poi', 1803.0, -77.0,
     '阿伯丁兄妹黑店（支线）'),
]
TYPE_ZH = {'town': '城市', 'castle': '城堡', 'village': '村庄',
           'camp': '营地', 'poi': '野外点位', 'hideout': '藏身处'}


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xffffffff
        h = (h + ((h << 10) & 0xffffffff)) & 0xffffffff
        h ^= h >> 6
    h = (h + ((h << 3) & 0xffffffff)) & 0xffffffff
    h ^= h >> 11
    h = (h + ((h << 15) & 0xffffffff)) & 0xffffffff
    return h


def main():
    names = {}
    for n in open(NAMES, encoding='latin1', errors='ignore'):
        n = n.strip()
        if n and not n.startswith('#'):
            names[joaat(n)] = n
    lib = set(json.load(open(LIB, encoding='utf-8'))['models'].keys())
    arch = json.load(open(ARCH, encoding='utf-8'))
    inst = []
    for fn in glob.glob(os.path.join(TILES, '*.json')):
        inst += json.load(open(fn))

    def stat(x, y, r):
        es = [e for e in inst if abs(e[1] - x) <= r and abs(e[2] - y) <= r]
        bld = libb = 0
        pref = {}
        for e in es:
            bb = arch.get(str(e[0]))
            if not bb:
                continue
            if max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]) >= 8:
                bld += 1
                if ('0x%08x' % e[0]) in lib:
                    libb += 1
                nm = names.get(e[0]) or ''
                if '_' in nm:
                    k = nm.split('_')[0]
                    pref[k] = pref.get(k, 0) + 1
        top = sorted(pref.items(), key=lambda kv: -kv[1])[:3]
        return dict(n_all=len(es), n_bld=bld, n_bld_lib=libb,
                    prefix=','.join('%s×%d' % kv for kv in top))

    rows = []
    for r in csv.DictReader(open(CSV_IN, encoding='utf-8-sig')):
        code = r['code']
        x, y = float(r['world_x']), float(r['world_y'])
        if code in FIX:
            x, y = FIX[code]
        st = stat(x, y, max(120.0, float(r['size_w_m']) / 2 + 20))
        rows.append(dict(code=('lon' if code == 'lnn' else code),
                         name_zh=r['name_zh'], name_en=r['name_en'],
                         btype=r['btype'], world_x=x, world_y=y,
                         size_w_m=r['size_w_m'], size_d_m=r['size_d_m'],
                         fixed='是' if code in FIX else '', note='', **st))
    have = {r['code'] for r in rows}
    for code, zh, en, t, x, y, note in ADD:
        if code in have:
            continue
        st = stat(x, y, 110)
        rows.append(dict(code=code, name_zh=zh, name_en=en, btype=t,
                         world_x=x, world_y=y, size_w_m=60, size_d_m=60,
                         fixed='新增', note=note, **st))

    with open(CSV_OUT, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # markdown 表：按 类型顺序
    order = ['town', 'castle', 'village', 'camp', 'poi', 'hideout']
    lines = ['| 类型 | 据点 | 编码 | 世界坐标 (x, y) | 实体 | ≥8m 建筑 | 有网格 | 模型前缀（前3） | 备注 |',
             '|---|---|---|---|---|---|---|---|---|']
    for t in order:
        for r in [x for x in rows if x['btype'] == t]:
            note = r.get('note', '')
            if r['fixed'] == '是':
                note = '**坐标/编码已修正**'
            elif r['fixed'] == '新增':
                note = '**本轮新增** · ' + note
            lines.append('| %s | **%s** | `%s` | %.0f, %.0f | %d | %d | **%d** | %s | %s |' % (
                TYPE_ZH[t], r['name_zh'], r['code'], r['world_x'], r['world_y'],
                r['n_all'], r['n_bld'], r['n_bld_lib'], r['prefix'], note))
    open(MD_OUT, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('rows', len(rows), '->', CSV_OUT)
    print('table ->', MD_OUT)


if __name__ == '__main__':
    main()
