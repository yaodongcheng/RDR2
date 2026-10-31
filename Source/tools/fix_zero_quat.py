# -*- coding: utf-8 -*-
"""修 tiles 里的退化变换：四元数为零的实例补成单位四元数。

2026-10-30 全量合并后发现 1,136 条实例的四元数全是 0（源 ymap 里就这么写的，
多半是"纯平移无旋转"的写法）。零四元数在 Blender 里会把物体压成一个点，
这里统一补成 (0,0,0,1)，并在 `work/quat_fix.json` 里记账。

    python tools/fix_zero_quat.py --dry
    python tools/fix_zero_quat.py
"""
import os
import json
import glob
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
REPORT = os.path.join(ROOT, 'work/quat_fix.json')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()

    fixed = 0
    per = {}
    for f in sorted(glob.glob(os.path.join(TILES, '*.json'))):
        rows = json.load(open(f, encoding='utf-8'))
        touched = 0
        for r in rows:
            q = r[4:8]
            if all(abs(v) < 1e-6 for v in q):
                r[4], r[5], r[6], r[7] = 0.0, 0.0, 0.0, 1.0
                touched += 1
        if touched:
            fixed += touched
            per[os.path.basename(f)] = touched
            if not a.dry:
                json.dump(rows, open(f, 'w', encoding='utf-8'), separators=(',', ':'))
    print('[quat] 补单位四元数 %d 条，涉及 %d 个 tile%s'
          % (fixed, len(per), '（dry，未写盘）' if a.dry else ''))
    for k, v in sorted(per.items(), key=lambda kv: -kv[1])[:8]:
        print('   %-22s %d' % (k, v))
    if not a.dry:
        json.dump(dict(total=fixed, per_tile=per), open(REPORT, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('→ %s' % os.path.relpath(REPORT, ROOT))


if __name__ == '__main__':
    main()
