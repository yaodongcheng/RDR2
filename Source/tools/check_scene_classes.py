# -*- coding: utf-8 -*-
"""单场景分类体检：跑完场景后用它核对，不用开 Blender。

    python -X utf8 tools/_check_scene_classes.py hso [hso2 ...]

三件事：
  1. 分类直方图（与上次构建的日志对账，对象数/室内数应一致）；
  2. 未分类清单（按占地排序，判断该不该补词）；
  3. 🔴 风险项：可见类（建筑/部件/道具/废墟等）里混进了「远景壳」——
     判据 = 名字像 LOD，或 albedo 贴图名带 `_lod` / `_slod`（黑水镇 2026-11-06 实测踩过 3 个）。
"""
import json
import os
import re
import sys

SCENES = r'D:/BrainMaker/大镖客2解包分析/deliverable/blender/scenes'
INDEX = r'D:/BrainMaker/大镖客2解包分析/assets/lib_native/index.json'
VISIBLE = ('bldg', 'part', 'prop', 'ruin', 'struct', 'rock', 'stone', 'junk', 'veh')
LOD_NAME = re.compile(r'_lod|slod|fragslod', re.I)
LOD_TEX = re.compile(r'_lod_|_slod|fragslod|_lod$', re.I)


def main(ids):
    idx = json.load(open(INDEX, encoding='utf-8'))
    models, tex = idx['models'], idx['tex']
    for sid in ids:
        p = os.path.join(SCENES, 'manifest_%s.jsonl' % sid)
        if not os.path.exists(p):
            print('[%s] 缺 manifest' % sid)
            continue
        rows = [json.loads(l) for l in open(p, encoding='utf-8')]
        hist = {}
        for r in rows:
            hist[r.get('c')] = hist.get(r.get('c'), 0) + 1
        print('=== %s：%d 个对象 ===' % (sid, len(rows)))
        print('   ' + ' · '.join('%s:%d' % (k, v) for k, v in
                                 sorted(hist.items(), key=lambda kv: -kv[1])))
        unk = [(r['n'], r['bb']) for r in rows if r.get('c') == 'unknown']
        print('   未分类 %d 个，最大的几个：' % len(unk))
        for n, bb in sorted(unk, key=lambda x: -(x[1][3] - x[1][0]))[:8]:
            print('      %-34s %6.1f x %5.1f x %5.1f' %
                  (n, bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]))
        risk = []
        for r in rows:
            if r.get('c') not in VISIBLE:
                continue
            n = r.get('n') or ''
            if LOD_NAME.search(n):
                risk.append((n, r.get('c'), '名字像 LOD'))
                continue
            h = ('0x%08x' % int(n[2:10], 16)) if n.startswith('e_') else None
            m = models.get(h) if h else None
            if not m:
                continue
            for s in (m.get('s') or []):
                t = s[0] if s else -1
                if isinstance(t, int) and 0 <= t < len(tex) and LOD_TEX.search(tex[t].get('n') or ''):
                    risk.append((n, r.get('c'), tex[t]['n']))
                    break
        print('   风险项（可见类里混进远景壳）：%d 个' % len(risk))
        for n, c, why in risk[:10]:
            print('      %-34s %-8s %s' % (n, c, why))


if __name__ == '__main__':
    main(sys.argv[1:] or ['hso'])
