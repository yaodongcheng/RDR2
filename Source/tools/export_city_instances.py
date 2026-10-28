"""导出某据点的实例清单（给 Blender 高模 LOD 用）。

产物 deliverable/miniatures/hi/<code>.json
  { code, bbox:[x0,y0,x1,y1], items:[{h, x,y,z, qx,qy,qz,qw, sx,sy,sz}], lib, tex }
"""
import os
import csv
import json
import glob
import re
import argparse
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
_s = importlib.util.spec_from_file_location('bmr', os.path.join(HERE, 'build_miniatures_real.py'))
BMR = importlib.util.module_from_spec(_s)
_s.loader.exec_module(BMR)

OUT = os.path.join(ROOT, 'deliverable/miniatures/hi')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--code', default='sdn')
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    ledger = BMR.load_ledger()
    insts = BMR.load_instances()
    s = [x for x in BMR.load_settlements() if x['code'] == args.code][0]
    hw, hd = s['w'] / 2, s['d'] / 2
    sel = [e for e in insts if abs(e[1] - s['x']) <= hw and abs(e[2] - s['y']) <= hd]

    items = []
    for e in sel:
        m = ledger.get(e[0])
        if not m:
            continue
        if not (BMR.is_building(m['name'], m['sz'], m['tris'], m['sx'], m['sy'])
                or BMR.is_keep_prop(m['name'], m['sz'])):
            continue
        items.append({
            'h': int(e[0]), 'x': e[1], 'y': e[2], 'z': e[3],
            'qx': e[4], 'qy': e[5], 'qz': e[6], 'qw': e[7],
            'sx': abs(e[8]), 'sy': abs(e[9]), 'sz': abs(e[10]),
        })

    data = {
        'code': s['code'], 'name': s['name_zh'],
        'cx': s['x'], 'cy': s['y'], 'w': s['w'], 'd': s['d'],
        'lib': os.path.join(ROOT, 'assets/lib_native').replace('\\', '/'),
        'items': items,
    }
    p = os.path.join(OUT, s['code'] + '.json')
    json.dump(data, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'{s["code"]}: {len(items)} 实例 → {p}')


if __name__ == '__main__':
    main()
