#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""校验并重建 AVG 背景清单（不重新渲染）。

为什么单独一个脚本：出图要 10+ 分钟（headless Chrome + 大城 6600 实例），
一旦中途被打断，产物目录里会留下空白图、清单也会缺项。这个脚本只做三件事：
  1. 逐张判空白（方差 < 8 视为没拍到东西）
  2. 删掉空白图，按真实存在的文件重建 data/bg.json
  3. 没图 / 面数不足的据点标 proxy，指向同章节主场景
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'D:/BrainMaker/大镖客2解包分析'
EXP = os.path.join(ROOT, 'export')
BG = os.path.join(EXP, 'avg/bg')
MIN_TRIS = 25000
PROXY = {'adl': 'col', 'wal': 'bla', 'sod': 'pro', 'wap': 'but', 'che': 'sdn',
         'man': 'van', 'hso': 'val', 'abe': 'mfr', 'lon': 'rho'}
# 上一轮渲染记下来的面数（用来判断"有没有烘出建筑"）
TRIS = {
    'sdn': 1400000, 'val': 420000, 'rho': 500000, 'bla': 600000, 'ann': 500000,
    'cle': 400000, 'agu': 400000, 'str': 250000, 'van': 250000, 'cal': 250000,
    'bra': 220000, 'dewclm': 220000, 'sis': 220000, 'but': 220000, 'bee': 150000,
    'sha': 180000, 'eme': 150000, 'mfr': 200000, 'old': 120000, 'lak': 100000,
    'cor': 200000, 'han': 90000, 'mic': 60000, 'col': 60000, 'pro': 70000,
    'man': 40000, 'che': 30000, 'wap': 30000, 'adl': 2000, 'wal': 9000,
    'sod': 9000, 'abe': 0, 'hso': 0, 'lon': 0,
}


def sd(path):
    try:
        from PIL import Image, ImageStat
        im = Image.open(path).convert('RGB').resize((160, 90))
        return sum(ImageStat.Stat(im).stddev) / 3.0
    except Exception:
        return 0.0


def main():
    data = json.load(open(os.path.join(EXP, 'levels/world/avg_main.json'), encoding='utf-8'))
    st = {s['code']: s for s in
          json.load(open(os.path.join(EXP, 'levels/world/settlements.json'), encoding='utf-8'))['settlements']}
    used = sorted({m['location']['settlement'] for m in data['missions']
                   if m.get('location') and m['location'].get('settlement')})

    locs = {}
    dropped = []
    for code in used:
        s = st.get(code) or {}
        rec = {'zh': s.get('name_zh'), 'en': s.get('name_en'),
               'radius': s.get('size_w'), 'proxy': None, 'shots': []}
        for n in (0, 1, 2, 3):
            fn = '%s_%d.jpg' % (code, n)
            p = os.path.join(BG, fn)
            if not os.path.exists(p):
                continue
            v = sd(p)
            if v < 8.0 or os.path.getsize(p) < 9000:
                dropped.append((fn, round(v, 1)))
                os.remove(p)
                continue
            rec['shots'].append({'file': 'bg/' + fn, 'shot': n})
        tris = TRIS.get(code, 100000)
        if not rec['shots']:
            rec['proxy'] = PROXY.get(code)
        elif tris < MIN_TRIS:
            rec['proxy'] = PROXY.get(code)
        locs[code] = rec

    # proxy 目标自己也得有图，否则清空 proxy（播放器会退回渐变底）
    for code, rec in locs.items():
        px = rec.get('proxy')
        if px and (px not in locs or not locs[px]['shots']):
            rec['proxy'] = None

    json.dump({'generated': data['generated'], 'size': [1600, 900], 'locations': locs},
              open(os.path.join(EXP, 'avg/data/bg.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    real = [c for c, v in locs.items() if v['shots'] and not v['proxy']]
    prox = [c for c, v in locs.items() if v['proxy']]
    noimg = [c for c, v in locs.items() if not v['shots'] and not v['proxy']]
    print('据点 %d：真实场景 %d · 走替身 %d · 无图 %d' % (len(locs), len(real), len(prox), len(noimg)))
    print('删掉的空白图：', dropped)
    print('替身映射：', {c: locs[c]['proxy'] for c in prox})
    if noimg:
        print('无图：', noimg)
    print('图片总数：', sum(len(v['shots']) for v in locs.values()))


if __name__ == '__main__':
    main()
