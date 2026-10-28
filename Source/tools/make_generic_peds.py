"""生成"通用路人"部件组合清单（compose spec）。

⚠️ 说明：RDR2 的**通用 ped（a_m_/a_f_ 城镇路人）不是单个模型**，而是由"部件池"
（`metapeds_<a-z>.rpf` 里的 `head_* / uppr_* / lowr_* / boot_* / hand_* …`）按
**metapede 定义**（`packs/base/data/metapeds/<ped>.ymt`，二进制 PSIN、无字符串、
无法离线还原配方）在运行期拼出来的。

所以本脚本的做法是：按**性别码**（mr1=男 / fr1=女）从部件池里**按槽位各取一件**
拼出一个**结构完整、比例正常**的路人——它**不是**游戏里某个具名 ped 的精确还原，
而是"同类路人"的可替代样本（用于场景摆人完全够用）。这一点必须写进交付说明。

用法: uv run python tools/make_generic_peds.py [--per-gender 4] [--out work/npc/generic_spec.json]
"""
import os
import re
import sys
import json
import glob
import argparse
from collections import defaultdict

SLOTS = [
    ('head', 1, r'^head_(%s)_\d+\.ydd$'),
    ('teeth', 1, r'^teeth_(%s)_?\d*\.ydd$'),
    ('eyes', 0, r'^eyes?_(%s)_?\d*\.ydd$'),
    ('hair', 1, r'^hair_(%s)_\d+.*\.ydd$'),
    ('beard', 0, r'^beard?_(%s)_\d+.*\.ydd$'),
    ('uppertorso', 1, r'^uppertorso_(%s)_\d+.*\.ydd$'),
    ('uppr', 1, r'^uppr_(%s)_\d+.*\.ydd$'),
    ('lowr', 1, r'^lowr_(%s)_\d+.*\.ydd$'),
    ('boot', 1, r'^boot_(%s)_\d+.*\.ydd$'),
    ('hand', 0, r'^hand?[lr]?_(%s)_?\d*\.ydd$'),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='work/npc/models/generic')
    ap.add_argument('--per-gender', type=int, default=4)
    ap.add_argument('--out', default='work/npc/generic_spec.json')
    a = ap.parse_args()

    files = [os.path.basename(p) for p in glob.glob(os.path.join(a.dir, '*.ydd'))]
    spec = []
    report = {}
    for gender, tag in (('mr1', 'male'), ('fr1', 'female')):
        pool = {}
        for slot, required, rx in SLOTS:
            hits = sorted([f for f in files if re.match(rx % gender, f)])
            pool[slot] = hits
            report['%s.%s' % (tag, slot)] = len(hits)
        for k in range(a.per_gender):
            ydd = []
            picks = {}
            for slot, required, _rx in SLOTS:
                hits = pool[slot]
                if not hits:
                    if required:
                        print('  !! %s 缺槽位 %s' % (tag, slot))
                    continue
                f = hits[k % len(hits)] if slot not in ('eyes', 'hand') else hits[0]
                picks[slot] = f
                ydd.append(os.path.join(a.dir, f))
            spec.append(dict(name='generic_%s_%02d' % (tag, k + 1), ydds=ydd, picks=picks))

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(spec, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('slots 可用数:', json.dumps(report, ensure_ascii=False))
    print('写出 %d 个路人组合 -> %s' % (len(spec), a.out))
    for s in spec:
        print('  %-18s %s' % (s['name'], ' + '.join(os.path.basename(x) for x in s['ydds'])))


if __name__ == '__main__':
    main()
