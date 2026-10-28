# -*- coding: utf-8 -*-
"""按**源文件**重绑全部模型贴图，并把库的贴图表改成"名字即真相"。

## 问题（为什么必须重做）

`.mdl` 的每个子网格只存 `tid`（整数），而 `tex` 表历史上被重建/重排/复用过多轮，
于是 `id ↔ 名字 ↔ 文件内容` 会互相错位：

- `new_gar06_park_terrain`（`0x3744d21b`）源 `.ydr` 要 `nbx_ground_grass_bay_lsuh_ab` + `nbx_ground_dirt04_ab`，
  库里却是 `s=[353,352,352,352]`；`tex/0352.png` 逐像素就是土（没错），但表里写着 `p_doornbd39x_ab`，
  而 353 那张真的是门 → 草坪上出现一扇门。
- 抽 300 条核对：可比 83 条里 82 一致、1 不一致 → 不是全错，但**不能再用 tid 当真相**。

## 新方案

1. **每个模型 hash 都有源**：实测 55,607/55,608 能在 RPF 索引里命中同 hash 的 `.ydr/.yft`；
2. 从源文件解析**真实贴图名 + 顶点数 + 索引数**（`dump_model_lib.load_any`）；
3. 贴图表按**名字排序**重建：`id = 排序下标`、`n = 名字`、`tex/<id>.png` 由 ytd 按名字解出
   （`work/tex_name_index.json`）→ 文件内容与名字**由构造保证一致**；
4. 回写两处：`.mdl` 里每个子网格的 `tid` 字段 + `index.json` 的 `s` 数组；
5. 名字找不到图的 → `tid = -1`（**宁可没贴图，也不贴错**，最高原则 §6.3），并记进缺口报告。

## 用法

    python tools/rebind_models_from_sources.py --plan        # 只统计（可解析/缺图/几何不一致）
    python tools/rebind_models_from_sources.py --apply       # 写库（自动备份 index + .mdl）
"""
import os
import sys
import json
import time
import shutil
import struct
import argparse
from collections import Counter

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')
TEXIDX = os.path.join(ROOT, 'work/tex_name_index.json')
MODELS = os.path.join(ROOT, 'export/world/continent/models.json')
FILEMAP = os.path.join(ROOT, 'work/model_file_map.json')
REPORT = os.path.join(ROOT, 'work/rebind_sources_report.json')
NEEDED = os.path.join(ROOT, 'work/needed_tex_names.json')
PLAN = os.path.join(ROOT, 'work/rebind_plan.json')
MAGIC = b'RMDL1' + bytes(3)
SUB = struct.Struct('<7I')     # tid, vc, ic, po, no, uo, io


def load_sources():
    m = {}
    for path, dst in ((MODELS, m),):
        if os.path.exists(path):
            for hx, p in json.load(open(path, encoding='utf-8')).items():
                if os.path.exists(p):
                    dst[int(hx, 16)] = p
    if os.path.exists(FILEMAP):
        try:
            for hx, p in json.load(open(FILEMAP, encoding='utf-8')).items():
                h = int(hx, 16)
                if h not in m and os.path.exists(p):
                    m[h] = p
        except Exception as e:
            print('[rb] model_file_map 读不了：%s' % e)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--patch-only', action='store_true',
                    help='只把 index.s 的 tid 写回 .mdl（s 已经改好、只有 .mdl 没跟上时用）')
    ap.add_argument('--refresh-names', action='store_true',
                    help='按当前 ytd 索引重算"需要的名字/有图/缺图"（不重扫源文件）')
    ap.add_argument('--names-only', action='store_true',
                    help='只产出"需要哪些贴图名"清单（给 tex_table_rebuild 用）')
    a = ap.parse_args()

    import dump_model_lib as D
    import export_sdn_gltf as EX

    d = json.load(open(INDEX, encoding='utf-8'))
    models, tex = d['models'], d['tex']
    src = load_sources()
    print('[rb] 模型 %d / 本地源 %d' % (len(models), len(src)))

    if a.refresh_names:
        pk = json.load(open(PLAN, encoding='utf-8'))
        nlist = pk['names']
        cnt = Counter()
        for _hx, subs in pk['models'].items():
            for i, _nv, _ni in subs:
                if i >= 0:
                    cnt[nlist[i]] += 1
        texidx = json.load(open(TEXIDX, encoding='utf-8')) if os.path.exists(TEXIDX) else {}
        have = [n for n in cnt if n in texidx]
        no_img = [n for n in cnt if n not in texidx]
        json.dump({'needed': dict(cnt), 'have': have, 'no_img': no_img,
                   'nsub_diff': 0, 'geo_bad': 0, 'parse_fail': 0},
                  open(NEEDED, 'w', encoding='utf-8'), ensure_ascii=False)
        print('[rb] 刷新名字清单：需要 %d / 有图 %d（%.1f%% 引用）/ 缺图 %d'
              % (len(cnt), len(have),
                 100.0 * sum(cnt[n] for n in have) / max(1, sum(cnt.values())), len(no_img)))
        return

    if a.patch_only:
        n_ok = n_bad = n_sub = 0
        for hx, e in models.items():
            s = e.get('s') or []
            p = os.path.join(LIB, e['f'])
            try:
                with open(p, 'r+b') as f:
                    head = f.read(12 + 24)
                    if head[:8] != MAGIC:
                        n_bad += 1
                        continue
                    nsub = struct.unpack_from('<I', head, 8)[0]
                    if nsub != len(s):
                        n_bad += 1
                        continue
                    for i, sub in enumerate(s):
                        f.seek(12 + 24 + i * SUB.size)
                        tid = sub[0]
                        f.write(struct.pack('<I', tid if tid is not None and tid >= 0 else 0xFFFFFFFF))
                    n_ok += 1
                    n_sub += nsub
            except Exception as ex:
                n_bad += 1
                if n_bad < 5:
                    print('[rb] 失败 %s: %s' % (e['f'], ex))
        print('[rb] patch-only：写回 .mdl %d 个（%d 个子网格），跳过 %d'
              % (n_ok, n_sub, n_bad))
        return

    # ---------- 1. 扫源文件，收集每个模型的新 s（名字版）+ 需要的贴图名 ----------
    plan = {}            # hash str -> [(name, nv, ni), ...]
    needed = Counter()
    fail = []
    geo_bad = 0
    nsub_diff = 0
    t0 = time.time()
    if a.apply and os.path.exists(PLAN):
        pk = json.load(open(PLAN, encoding='utf-8'))
        nlist = pk['names']
        for hx, subs in pk['models'].items():
            plan[hx] = [(nlist[i] if i >= 0 else '', nv, ni) for i, nv, ni in subs]
            for nm, _nv, _ni in plan[hx]:
                if nm:
                    needed[nm] += 1
        print('[rb] 复用计划 %s：模型 %d / 贴图名 %d（跳过源文件重扫）'
              % (os.path.basename(PLAN), len(plan), len(needed)))
    for hx in (models if not plan else ()):
        h = int(hx, 16)
        p = src.get(h)
        if not p:
            continue
        try:
            M = D.load_any(p)
        except Exception:
            M = None
        if not M or not M.get('geoms'):
            fail.append(hx)
            continue
        geoms = [g for g in M['geoms']
                 if g.get('pos') is not None and len(g['pos']) and len(g.get('idx') or [])]
        subs = []
        for g in geoms:
            nm = EX.clean_name(g.get('tex') or '').lower()
            nv = len(g['pos'])
            ni = len(g.get('idx') or [])
            if nv == 0 or ni == 0:
                continue
            subs.append((nm, nv, ni))
            if nm:
                needed[nm] += 1
        old = models[hx].get('s') or []
        if len(subs) != len(old):
            nsub_diff += 1
        elif any(nv != o[1] or ni != o[2] for (nm, nv, ni), o in zip(subs, old)):
            geo_bad += 1
        plan[hx] = subs
        if len(plan) % 5000 == 0:
            print('[rb] 扫 %d / %d（可解析 %d，失败 %d，%.0fs）'
                  % (len(plan) + len(fail), len(models), len(plan), len(fail), time.time() - t0))

    print('[rb] 解析成功 %d / 失败 %d / 子网格数不一致 %d / 顶点数不一致 %d'
          % (len(plan), len(fail), nsub_diff, geo_bad))
    print('[rb] 需要的贴图名 %d 个（引用 %d 次）' % (len(needed), sum(needed.values())))

    texidx = json.load(open(TEXIDX, encoding='utf-8')) if os.path.exists(TEXIDX) else {}
    have_img = [n for n in needed if n in texidx]
    no_img = [n for n in needed if n not in texidx]
    print('[rb] 有图 %d（%.1f%% 引用）/ 缺图 %d'
          % (len(have_img), 100.0 * sum(needed[n] for n in have_img) / max(1, sum(needed.values())),
             len(no_img)))

    json.dump({'needed': dict(needed), 'have': have_img, 'no_img': no_img,
               'nsub_diff': nsub_diff, 'geo_bad': geo_bad, 'parse_fail': len(fail)},
              open(NEEDED, 'w', encoding='utf-8'), ensure_ascii=False)

    # 把"每个模型的新 s（名字版）"打包存下来：--apply 不必再扫一遍源文件（省 ~15 分钟）
    # 空名字（有些子网格没有 albedo）用 -1 表示
    nlist = sorted(n for n in needed if n)
    nidx = {n: i for i, n in enumerate(nlist)}
    packed = {hx: [(nidx[nm] if nm else -1, nv, ni) for nm, nv, ni in subs]
              for hx, subs in plan.items()}
    json.dump({'names': nlist, 'models': packed}, open(PLAN, 'w', encoding='utf-8'),
              separators=(',', ':'))
    print('[rb] 计划 %s（%.1f MB）' % (PLAN, os.path.getsize(PLAN) / 2**20))

    if a.plan or a.names_only or not a.apply:
        print('[rb] 只出计划（%s）' % NEEDED)
        return

    # ---------- 2. 写回：贴图表由 tex_table_rebuild.py 建好后，这里只改 .mdl 与 index.s ----------
    idmap_p = os.path.join(ROOT, 'work/tex_name_ids.json')
    if not os.path.exists(idmap_p):
        raise SystemExit('先跑 tools/tex_table_rebuild.py 生成 %s' % idmap_p)
    ids = json.load(open(idmap_p, encoding='utf-8'))     # name -> id
    print('[rb] 贴图表 %d 个名字（epoch %s）' % (len(ids), ids.get('__epoch__') if isinstance(ids, dict) else '?'))
    if '__epoch__' in ids:
        ids = {k: v for k, v in ids.items() if not k.startswith('__')}

    bak = os.path.join(LIB, 'index_before_rebind_%s.json' % time.strftime('%Y%m%d_%H%M'))
    if not os.path.exists(bak):
        shutil.copy2(INDEX, bak)
        print('[rb] 备份 %s' % os.path.basename(bak))

    patched_mdl = 0
    patched_sub = 0
    changed = 0
    legacy = 0
    legacy_sub = 0

    def patch_mdl(e, new_s):
        p = os.path.join(LIB, e['f'])
        try:
            with open(p, 'r+b') as f:
                head = f.read(12 + 24)
                if head[:8] != MAGIC:
                    return 0
                nsub = struct.unpack_from('<I', head, 8)[0]
                if nsub != len(new_s):
                    return 0
                for i, (tid, _nv, _ni) in enumerate(new_s):
                    f.seek(12 + 24 + i * SUB.size)
                    f.write(struct.pack('<I', tid if tid is not None and tid >= 0 else 0xFFFFFFFF))
                return nsub
        except Exception as ex:
            print('[rb] 补 .mdl 失败 %s: %s' % (e['f'], ex))
            return 0

    for hx, subs in plan.items():
        e = models[hx]
        old = e.get('s') or []
        if len(subs) != len(old):
            continue                       # 结构不一致的先不动（报告里已计数）
        new_s = [[ids.get(nm, -1), nv, ni] for nm, nv, ni in subs]
        if new_s == old:
            continue
        changed += 1
        e['s'] = new_s
        n = patch_mdl(e, new_s)
        if n:
            patched_mdl += 1
            patched_sub += n

    # ---- 兜底：源文件解析失败的模型，用**旧表的名字**把旧 tid 翻成新 tid（不猜，只搬名字）----
    # 旧表要从 tex_table_rebuild 动表之前留的备份里读（当前 INDEX 已经是新表了）
    import glob
    cands = sorted(glob.glob(os.path.join(LIB, 'index_before_textable_*.json')))
    old_tex = {}
    if cands:
        try:
            old_d = json.load(open(cands[-1], encoding='utf-8'))
            old_tex = {t['id']: t for t in old_d.get('tex') or []}
            print('[rb] 旧贴图表取自 %s（%d 条）' % (os.path.basename(cands[-1]), len(old_tex)))
        except Exception as ex:
            print('[rb] 旧表读不了：%s' % ex)

    for hx, e in models.items():
        if hx in plan:
            continue
        old = e.get('s') or []
        new_s = []
        hit = False
        for tid, nv, ni in old:
            nm = (old_tex.get(tid) or {}).get('n') or ''
            nid = ids.get(nm, -1) if nm else -1
            if nid >= 0:
                hit = True
            new_s.append([nid, nv, ni])
            if nid >= 0:
                legacy_sub += 1
        if hit:
            legacy += 1
            e['s'] = new_s
            n = patch_mdl(e, new_s)
            if n:
                patched_mdl += 1
                patched_sub += n

    d['tex'] = tex                       # tex 表已由 tex_table_rebuild 写好
    json.dump(d, open(INDEX, 'w', encoding='utf-8'), separators=(',', ':'))
    print('[rb] 改绑模型 %d 个 / 兜底搬名字 %d 个（%d 个子网格）/ 补 .mdl %d 个（%d 个子网格）'
          % (changed, legacy, legacy_sub, patched_mdl, patched_sub))
    json.dump({'plan': len(plan), 'parse_fail': len(fail), 'nsub_diff': nsub_diff,
               'geo_bad': geo_bad, 'changed': changed, 'patched_mdl': patched_mdl,
               'patched_sub': patched_sub, 'names': len(needed), 'no_img': len(no_img),
               'legacy_models': legacy, 'legacy_subs': legacy_sub},
              open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('[rb] 报告 %s' % REPORT)


if __name__ == '__main__':
    main()
