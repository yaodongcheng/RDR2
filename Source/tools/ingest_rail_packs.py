# -*- coding: utf-8 -*-
"""把「铁路网 RPF 包」里的 .ydr 入库（assets/lib_native），补上整条铁路。

## 为什么需要它（2026-10-30 定位）

安尼斯堡一带在 blend 里**看不到那条从南到北的铁路**。排查结论：
铁路网在游戏里是**按区块的独立 RPF 包**（`levels/rdr3/area/rails/*.rpf`），
其中 `jklm_15_18_rails_a/b`、`fghi_15_18_rails_a` 三个包**从来没有被抽出来**：

    raw/rails_extract/jklm_15_18_rails_a_rpf/    ← 空目录（有目录没文件）
    raw/rails_extract/jklm_15_18_rails_b_rpf/    ← 空目录
    raw/rails_extract/fghi_15_18_rails_a_rpf/    ← 空目录

于是 `town_data`（= 全量 ymap 实体，184,593 条）里没有这 500 条铁路实例，
`assets/lib_native` 里也没有它们引用的 500 个模型 —— **不是解析失败，是这一步没跑**。

## 做了什么

    python tools/ingest_rail_packs.py --dry     # 只看会入多少个
    python tools/ingest_rail_packs.py           # 写 .mdl + tex + index.json（先备份）

· 模型：`raw/rails_extract/{jklma,jklmb,fghia}/**/*.ydr`，hash = joaat(文件名)
· 贴图：包里的 `.ytd` 直接进 `TexLib` 搜索路径，解出来的 PNG 追加到 `lib/tex/`
· 已入库的 hash 自动跳过（可反复执行）

配套：`tools/merge_rail_entities.py` 把实例并进 tiles，然后重建/打补丁。
"""
import os
import sys
import json
import time
import glob
import shutil
import argparse
from datetime import datetime

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))

LIB = os.path.join(ROOT, 'assets/lib_native')
PACKS = [os.path.join(ROOT, 'raw/rails_extract', d) for d in ('jklma', 'jklmb', 'fghia')]
BASEDIRS = [os.path.join(ROOT, 'work/lib_gtxd/txd'),
            os.path.join(ROOT, 'work/sdn/gtxd/txd'),
            os.path.join(ROOT, 'export/models')]

MAGIC = None


def joaat(s):
    h = 0
    for c in s.lower().encode('latin1', 'ignore'):
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF


class TexShim:
    """复用 index.json 里已有的贴图 id，新的才解包追加（与 dump_model_lib.Tex 同规则）。"""

    def __init__(self, lib, meta, extra_dirs, maxs=512):
        import export_sdn_gltf as G
        self.dir = os.path.join(lib, 'tex')
        os.makedirs(self.dir, exist_ok=True)
        self.meta = meta
        self.by_name = {}
        for t in meta:
            if t.get('n'):
                self.by_name.setdefault(t['n'].lower(), t['id'])
        self.tl = G.TexLib(list(extra_dirs) + BASEDIRS, maxs)
        self.maxs = maxs
        self.added = 0

    def get(self, name, hint=None):
        if not name:
            return -1
        k = name.lower()
        if k in self.by_name:
            return self.by_name[k]
        im, _ = self.tl.get(name, hint)
        if im is None:
            self.by_name[k] = -1
            return -1
        if max(im.size) > self.maxs:
            im = im.resize((self.maxs, self.maxs))
        if im.mode not in ('RGB', 'RGBA'):
            im = im.convert('RGB')
        tid = len(self.meta)
        fn = '%05d.png' % tid
        im.save(os.path.join(self.dir, fn), 'PNG', optimize=True)
        self.meta.append(dict(id=tid, n=name, f='tex/' + fn))
        self.by_name[k] = tid
        self.added += 1
        return tid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--packs', nargs='*', default=None)
    a = ap.parse_args()

    import export_sdn_gltf as EX
    import export_sdn_props2 as P2
    import dump_model_lib as DL

    packs = a.packs or PACKS
    idxp = os.path.join(LIB, 'index.json')
    idx = json.load(open(idxp, encoding='utf-8'))
    models, tex = idx['models'], idx['tex']
    print('[rail] 现有 模型 %d / 贴图 %d' % (len(models), len(tex)))

    ytd_dirs = []
    for p in packs:
        for f in glob.glob(os.path.join(p, '**', '*.ytd'), recursive=True):
            d = os.path.dirname(f)
            if d not in ytd_dirs:
                ytd_dirs.append(d)
    print('[rail] 包内 ytd 目录 %d 个' % len(ytd_dirs))

    files = []
    for p in packs:
        files += glob.glob(os.path.join(p, '**', '*.ydr'), recursive=True)
        files += glob.glob(os.path.join(p, '**', '*.yft'), recursive=True)   # 2026-10-30: 以前只扫 .ydr，7389 个 fragment 从未入库
    files.sort()
    print('[rail] 候选 .ydr %d 个' % len(files))

    shim = TexShim(LIB, tex, ytd_dirs)
    added = skipped = failed = 0
    t0 = time.time()
    todo = []
    for f in files:
        hx = '0x%08x' % joaat(os.path.splitext(os.path.basename(f))[0])
        if hx in models:
            skipped += 1
            continue
        todo.append((f, hx))
    print('[rail] 已在库 %d / 待入 %d' % (skipped, len(todo)))
    if a.limit:
        todo = todo[:a.limit]
    if a.dry:
        for f, hx in todo[:8]:
            print('   会入 %s  %s' % (hx, os.path.basename(f)))
        return

    if not a.dry:
        bak = os.path.join(LIB, 'index_before_rail_%s.json' % datetime.now().strftime('%Y%m%d_%H%M'))
        shutil.copy2(idxp, bak)
        print('[rail] 备份 %s' % os.path.basename(bak))

    for i, (f, hx) in enumerate(todo, 1):
        try:
            if f.lower().endswith('.yft'):
                M = P2.load_frag_model(f)
            else:
                M = EX.load_model(f)
        except Exception as e:
            M = None
            if failed < 5:
                print('   [load fail] %s %s' % (os.path.basename(f), e))
        if not M or not M.get('geoms'):
            failed += 1
            continue
        rec = DL.write_model(M, int(hx, 16), LIB, shim)
        if not rec:
            failed += 1
            continue
        # 顺带把法线 / _ma 槽位记上（与 extract_slot_textures 的 st 同格式）
        geoms = [g for g in M['geoms'] if len(g['pos']) and len(g['idx'])]
        st = []
        for g in geoms:
            nt = shim.get(g.get('ntex')) if g.get('ntex') else -1
            mt = shim.get(g.get('mtex')) if g.get('mtex') else -1
            st.append([nt, mt])
        if any(x[0] >= 0 or x[1] >= 0 for x in st):
            rec['st'] = st
        models[hx] = rec
        added += 1
        if i % 50 == 0:
            print('   [%3d/%3d] 入库 %d 失败 %d  贴图 +%d  (%.1f 分)'
                  % (i, len(todo), added, failed, shim.added, (time.time() - t0) / 60))

    idx['tex'] = tex
    idx['models'] = models
    json.dump(idx, open(idxp, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('[rail] 完成：入库 %d / 跳过 %d / 失败 %d / 新贴图 %d；模型总数 %d'
          % (added, skipped, failed, shim.added, len(models)))


if __name__ == '__main__':
    main()
