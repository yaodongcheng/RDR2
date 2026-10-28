# -*- coding: utf-8 -*-
"""补导「没有任何贴图」的服饰件（贴图确实缺失时给部位底色，避免白模）。

和 `export_clothing3d.py --only-missing` 等价，但独立实现，避免主脚本的增量跳过逻辑干扰。
"""
import os
import sys
import json
import time
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rdr2_npc_export as E

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'export/clothing3d')
IDX = os.path.join(OUT, 'index.json')
SRC = {'generic': 'raw/npc/models/generic',
       'player': 'raw/npc/models/player',
       'cutscene': 'raw/npc/models/cutscene'}


def has_basecolor(path):
    with open(path, 'rb') as f:
        f.read(12)
        clen, _ = struct.unpack('<II', f.read(8))
        g = json.loads(f.read(clen).decode('utf-8'))
    return any('baseColorTexture' in m.get('pbrMetallicRoughness', {})
               for m in g.get('materials', []))


def main():
    idx = json.load(open(IDX, encoding='utf-8'))
    tex_index = E.load_tex_index(os.path.join(ROOT, 'raw/npc/index/tex_index.json'))
    cache = {}
    todo = []
    for k, v in idx.items():
        p = os.path.join(OUT, v['glb'])
        if not os.path.exists(p):
            continue
        try:
            if not has_basecolor(p):
                todo.append((k, v))
        except Exception:
            pass
    print('待补', len(todo))
    n = 0
    t0 = time.time()
    for k, v in todo:
        src = None
        for d in SRC.values():
            p = os.path.join(ROOT, d, k + '.ydd')
            if os.path.exists(p):
                src = p
                break
        if not src:
            continue
        try:
            ped = E.parse_ped(src)
            res = E.write_glb(os.path.join(OUT, v['glb']), ped, tex_index,
                              png_dir=None, want_tex=True, tex_cache=cache,
                              keep_vcol=False, neutralize=True)
            v.update(tris=res.get('tris', v['tris']), textures=res.get('textures', 0),
                     bytes=res.get('bytes', v['bytes']))
            n += 1
            if n % 100 == 0:
                json.dump(idx, open(IDX, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
                print('  %d/%d %.0fs' % (n, len(todo), time.time() - t0), flush=True)
        except Exception as e:
            print('  [fail]', k, e)
    json.dump(idx, open(IDX, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('done', n, '%.0fs' % (time.time() - t0))


if __name__ == '__main__':
    main()
