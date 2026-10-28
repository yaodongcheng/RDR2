# -*- coding: utf-8 -*-
"""把 6106 件服饰全部导出成 **3D 模型（.glb）**，供 `viewer/clothing3d.html` 试穿。

为什么能做得动：单件只有 1~2 个 drawable，实测 **0.37 s / 278 KB**，
6106 件 ≈ 40 分钟 / 1.7 GB（贴图内嵌，文件自包含，不依赖外部 png）。

产物：
  export/clothing3d/<槽位>/<文件名>.glb
  export/clothing3d/index.json      {file, slot, glb, tris, parts, textures, bytes}

用法：
  uv run python tools/export_clothing3d.py            # 全部
  uv run python tools/export_clothing3d.py --limit 50 # 试跑
  uv run python tools/export_clothing3d.py --slot coat,uppr   # 只导某些槽位
"""
import os
import sys
import json
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rdr2_npc_export as E

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = [('generic', 'raw/npc/models/generic'),
       ('player', 'raw/npc/models/player'),
       ('cutscene', 'raw/npc/models/cutscene')]
OUT = os.path.join(ROOT, 'export/clothing3d')
TEXIDX = os.path.join(ROOT, 'raw/npc/index/tex_index.json')



def _has_basecolor(path):
    """读 glb 的 JSON chunk，看有没有任何材质带 baseColorTexture。"""
    import struct as _s
    with open(path, 'rb') as f:
        f.read(12)
        clen, _ctype = _s.unpack('<II', f.read(8))
        g = json.loads(f.read(clen).decode('utf-8'))
    for m in g.get('materials', []):
        if 'baseColorTexture' in m.get('pbrMetallicRoughness', {}):
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--slot', default='')
    ap.add_argument('--force', action='store_true', help='已有文件也重导（贴图修复后用）')
    ap.add_argument('--only-missing', action='store_true', help='只重导当前 glb 完全没有贴图的件')
    ap.add_argument('--out', default=OUT)
    a = ap.parse_args()
    only = {s.strip() for s in a.slot.split(',') if s.strip()}

    tex_index = E.load_tex_index(TEXIDX)
    tex_cache = {}            # 跨文件共享解码结果
    os.makedirs(a.out, exist_ok=True)
    idx_path = os.path.join(a.out, 'index.json')
    index = {}
    if os.path.exists(idx_path):
        try:
            index = json.load(open(idx_path, encoding='utf-8'))
        except Exception:
            index = {}

    n = 0
    t0 = time.time()
    for _src, rel in SRC:
        d = os.path.join(ROOT, rel)
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.ydd'):
                continue
            base = fn[:-4]
            slot = base.split('_')[0] or 'other'
            if only and slot not in only:
                continue
            if a.limit and n >= a.limit:
                break
            rel_glb = '%s/%s.glb' % (slot, base)
            out_glb = os.path.join(a.out, rel_glb)
            if a.only_missing and os.path.exists(out_glb):
                try:
                    if _has_basecolor(out_glb):
                        n += 1
                        continue
                except Exception:
                    pass
            if not a.force and os.path.exists(out_glb) and base in index:
                n += 1
                continue
            try:
                ped = E.parse_ped(os.path.join(d, fn))
            except Exception as e:
                print('  [skip] %s: %s' % (fn, e))
                continue
            if not ped['parts']:
                continue
            os.makedirs(os.path.dirname(out_glb), exist_ok=True)
            try:
                res = E.write_glb(out_glb, ped, tex_index, png_dir=None,
                                  want_tex=True, tex_cache=tex_cache,
                                  keep_vcol=False, neutralize=True)
            except Exception as e:
                print('  [fail] %s: %s' % (fn, e))
                continue
            index[base] = dict(file=fn, slot=slot, glb=rel_glb,
                               tris=res.get('tris', 0), parts=res.get('parts', 0),
                               textures=res.get('textures', 0),
                               bytes=res.get('bytes', 0))
            n += 1
            if n % 200 == 0:
                json.dump(index, open(idx_path, 'w', encoding='utf-8'),
                          ensure_ascii=False, separators=(',', ':'))
                print('  %d … %.0fs' % (n, time.time() - t0), flush=True)

    json.dump(index, open(idx_path, 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    total = sum(v['bytes'] for v in index.values())
    print('done %d models, %.2f GB, %.0fs → %s' %
          (len(index), total / 1e9, time.time() - t0, a.out))


if __name__ == '__main__':
    main()
