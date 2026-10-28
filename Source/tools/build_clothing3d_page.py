# -*- coding: utf-8 -*-
"""把 3D 索引内联进 `export/viewer/clothing3d.html`（页面可直接双击打开，不依赖 fetch）。

输入：export/clothing3d/index.json、export/viewer/clothing_thumbs/index.json
模板：tools/clothing3d_template.html
输出：export/viewer/clothing3d.html
"""
import os
import csv
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, 'export/clothing3d/index.json')
TH = os.path.join(ROOT, 'export/viewer/clothing_thumbs/index.json')
TPL = os.path.join(ROOT, 'tools/clothing3d_template.html')
OUT = os.path.join(ROOT, 'export/viewer/clothing3d.html')

idx = json.load(open(IDX, encoding='utf-8'))
# 槽位以 clothing_catalog 为准（index.json 里是按文件名首段粗分的，player/cs 会糊成一大坨）
CAT = os.path.join(ROOT, 'export/levels/world/clothing_catalog.csv')
slot_of, cat_of, sex_of = {}, {}, {}
if os.path.exists(CAT):
    for r in csv.DictReader(open(CAT, encoding='utf-8-sig')):
        k = r['file'][:-4]
        slot_of[k] = r['slot']
        cat_of[k] = r['category']
        g = (r.get('gender') or '').strip()
        if g in ('男', '女'):
            sex_of[k] = g
        elif r.get('source') == 'player':
            sex_of[k] = '男'          # 亚瑟 / 约翰
        else:
            sex_of[k] = '通用'
thumbs = json.load(open(TH, encoding='utf-8')) if os.path.exists(TH) else {}
# 只保留页面需要的字段，减小体积
slim = {k: dict(file=v['file'], slot=slot_of.get(k, v['slot']), cat=cat_of.get(k, '其它'),
                sex=sex_of.get(k, '通用'), glb=v['glb'], tris=v['tris'],
                textures=v['textures'], bytes=v['bytes']) for k, v in idx.items()}
html = open(TPL, encoding='utf-8').read()
html = html.replace('__INDEX__', json.dumps(slim, ensure_ascii=False, separators=(',', ':')))
html = html.replace('__THUMBS__', json.dumps(thumbs, ensure_ascii=False, separators=(',', ':')))
open(OUT, 'w', encoding='utf-8').write(html)
print('models', len(slim), '→', OUT, '%.1f MB' % (os.path.getsize(OUT) / 1e6))
