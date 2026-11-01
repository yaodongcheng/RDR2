# -*- coding: utf-8 -*-
"""给模型库的**每个子网格槽位**补 法线(`_nm`) 与 高光/材质(`_ma`) 贴图。

## 背景

`assets/lib_native` 的 `.mdl` 里每个子网格只存了 **一个** texId（漫反射），
法线/高光从来没导出过（`docs/README_骑砍2交接.md` §5.4）。
但源 `.ydr` 里两张图一直都在：抽样 3,000 个模型 / 11,509 个子网格，
有法线的 96.9%、有 `_ma` 的 97.1%。

## 做法（三步，可分开跑、可中断续跑）

    python tools/extract_slot_textures.py --stage parse  --jobs 12   # 1) 解析 5.5 万源模型
    python tools/extract_slot_textures.py --stage decode --jobs 12   # 2) 解 PNG 进 tex 池
    python tools/extract_slot_textures.py --stage apply               # 3) 回写 index.json

产物（**不改 `.mdl`**，避免重写 10.3 GB 二进制、也不破坏老读取器）：
    index.json
      tex[]     末尾追加 `{"id","n","f","role":"nm"|"ma","gflip","w","h"}`
                —— 旧 id 一个不动（id = 原表长度 + 序号）
      models[h] 增 `"st": [[nid, mid], …]`，与 `s` **等长、同序**（-1 = 没有）

## 两层材质（2026-11-01 扩，`standard_2lyr*` / `standard_dirt`）

同一个四段式顺带把**第二层 + 控制图 + 土/调色板**一起收进池子，并写进
`models[h].lyr = [[l1, ctrl, dirt], …]`（与 `s`/`st` 等长同序，-1 = 没有）：

| 列 | 角色 | 来源 shader 参数 |
|---|---|---|
| `l1`   | `l1`  | `lyr1diffusetex`（2lyr）/ `diffusetex2`（dirt） |
| `ctrl` | `ct`  | `controltexturetex`（只有 2lyr 有） |
| `dirt` | `dt`  | `dirtdiffusetex` |
| —      | `nm2` / `ma2` | `lyr1normaltex` / `lyr1materialatex`（第 1 层的法线/高光） |
| —      | `pl`  | `tintpalettetex`（**内嵌在 .ydr 体内**，只能从源文件解） |

混合遮罩用哪个通道**不写死**：解码时用 `tex_slots.mask_channel()` 挑方差最大的那个，
写进 `tex[i]["ch"]`（`-1` = 四通道全平、不能当遮罩）。

## 绑定规矩（对得上才写，对不上就留 -1）

1. 槽数必须与 `s` 一致；
2. 逐槽 `vCount` / `iCount` 必须与 `s` 里的完全相等（几何对得上）；
3. 该槽的 albedo **名字必须与库里已存的 texId 名字一致**（shader 对得上）；
三条同时成立才写，否则该槽留 -1 —— 遵守最高原则 §6.3「禁靠猜测匹配贴图」。

工作文件：
    work/slot_parse.json   源侧解析结果（hash → 逐槽 vc/ic/albedo/normal/material）
    work/slot_bind.json    校验后的绑定（hash → 逐槽 [nid, mid]，名字形式）
    work/slot_report.json  统计
"""
import os
import sys
import json
import time
import shutil
import argparse
import multiprocessing as mp

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TOOLS = os.path.join(ROOT, 'tools')
LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')
FMAP = os.path.join(ROOT, 'raw/model_file_map.json')
TEXIDX = os.path.join(ROOT, 'raw/tex_name_index.json')
WORK = os.path.join(ROOT, 'work')
P_PARSE = os.path.join(WORK, 'slot_parse.json')
P_BIND = os.path.join(WORK, 'slot_bind.json')
P_REPORT = os.path.join(WORK, 'slot_report.json')
P_NEW = os.path.join(WORK, 'slot_tex_new.json')
P_PAL = os.path.join(WORK, 'paltex')          # 内嵌调色板解出来的 PNG（名字 → 文件）

sys.path.insert(0, TOOLS)

MAXS = 512          # 与 albedo 池统一（源多为 1024，缩到 512）
FLIP_G = True       # RDR2 `_nm` 是 DirectX(+Y 朝下)，Blender Normal Map 要 OpenGL(+Y 朝上)

# 槽位里除 st（法线/高光）之外还要收的层：位置下标 → 写进 index 的角色名
# 行的排布见 `_parse_one`：0 vc · 1 ic · 2 alb · 3 nrm · 4 mat · 5 l1 · 6 nrm2 · 7 mat2 · 8 ctrl · 9 dirt · 10 pal
COL_L1, COL_NRM2, COL_MAT2, COL_CTRL, COL_DIRT, COL_PAL = 5, 6, 7, 8, 9, 10


# ------------------------------------------------------------------ 1. 解析源文件
def _save_palette(res, texs, outdir):
    """把 shader 里**内嵌**的调色板（256×4 BGRA）解成 PNG，文件名 = 贴图名。

    内嵌贴图没有 `.ytd` 可查（实测 978 个 SDN 两层模型的 `*_pal` **全都**只在 .ydr 里），
    所以只能在解析源文件这一趟顺手抠出来。返回贴图名（失败 None）。
    """
    import tex_slots as S
    for t in texs:
        if (t.get('role') or '') != 'palette' or not t.get('name'):
            continue
        name = t['name']
        dst = os.path.join(outdir, name + '.png')
        if os.path.exists(dst):
            return name
        try:
            from PIL import Image
            im, _fmt = S.embedded_texture(res, t)
            if im is None:
                return None
            os.makedirs(outdir, exist_ok=True)
            im.convert('RGBA').save(dst, 'PNG', optimize=True)
            return name
        except Exception:
            return None
    return None


def _parse_one(item):
    h, rel = item
    fp = os.path.join(ROOT, rel.replace('/', os.sep))
    if not os.path.exists(fp):
        return h, None, 'no-file'
    ext = os.path.splitext(fp)[1].lower()
    try:
        if ext == '.yft':
            import export_sdn_props2 as P
            M = P.load_frag_model(fp)
            if not M:
                return h, None, 'no-geom'
            rows = [[len(g['pos']), len(g['idx']), g.get('tex'), g.get('ntex'), g.get('mtex'),
                     (g.get('lyrs') or {}).get('l1'), (g.get('lyrs') or {}).get('nrm2'),
                     (g.get('lyrs') or {}).get('mat2'), (g.get('lyrs') or {}).get('ctrl'),
                     (g.get('lyrs') or {}).get('dirt'), (g.get('lyrs') or {}).get('pal')]
                    for g in M['geoms']]
        else:
            import rdr2_ydr as Y
            import tex_slots as S
            with open(fp, 'rb') as f:
                res = Y.Res(f.read())
            rows = []
            for g, texs in S.geoms_of_ydr(res):
                p = S.pick_all(texs)
                L = S.pick_layers(texs)
                if L.get('pal'):
                    L['pal'] = _save_palette(res, texs, P_PAL)
                rows.append([len(g['pos']), len(g['idx']),
                             p['alb'], p['nrm'], p['mat'],
                             L.get('l1'), L.get('nrm2'), L.get('mat2'),
                             L.get('ctrl'), L.get('dirt'), L.get('pal')])
    except Exception as e:
        return h, None, 'exc:%s' % type(e).__name__
    return h, rows, None


def _slim(v):
    """名字能省就省：None → 0；否则原样（长度可控）。"""
    return v or 0


def stage_parse(a):
    idx = json.load(open(INDEX, encoding='utf-8'))
    models = idx['models']
    fmap = json.load(open(FMAP, encoding='utf-8'))

    def norm(s):
        s = str(s).lower()
        if s.startswith('0x'):
            s = s[2:]
        try:
            return '0x%08x' % int(s, 16)
        except Exception:
            return None

    fmap = {norm(k): v for k, v in fmap.items() if norm(k)}

    items = []
    for h in models:
        p = fmap.get(h)
        if p:
            items.append((h, p))
    print('[slot] 库内模型 %d，有源文件 %d' % (len(models), len(items)))
    if a.limit:
        items = items[:a.limit]

    out = {}
    fails = {}
    t0 = time.time()
    done = 0
    with mp.Pool(a.jobs) as pool:
        for h, rows, why in pool.imap_unordered(_parse_one, items, chunksize=max(1, len(items) // (a.jobs * 8))):
            done += 1
            if rows:
                out[h] = [[r[0], r[1]] + [_slim(x) for x in r[2:]] for r in rows]
            else:
                fails[h] = why
            if done % 2000 == 0:
                el = time.time() - t0
                print('[slot] %d/%d  成功 %d 失败 %d  %.0f/s  剩 ~%.0f 分'
                      % (done, len(items), len(out), len(fails), done / el,
                         (len(items) - done) / max(1e-9, done / el) / 60), flush=True)

    json.dump(out, open(P_PARSE, 'w', encoding='utf-8'), separators=(',', ':'))
    json.dump(fails, open(P_PARSE.replace('.json', '_fail.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('[slot] 解析完成：成功 %d / 失败 %d，%.1f 分钟 → %s'
          % (len(out), len(fails), (time.time() - t0) / 60, os.path.basename(P_PARSE)))


# ------------------------------------------------------------------ 2. 校验 + 绑定
def _clean(n):
    try:
        import export_sdn_gltf as EX
        return (EX.clean_name(n) or '').lower()
    except Exception:
        return (n or '').lower()


def stage_bind(a):
    idx = json.load(open(INDEX, encoding='utf-8'))
    models, tex = idx['models'], idx['tex']
    names = {t['id']: (t.get('n') or '') for t in tex}
    src = json.load(open(P_PARSE, encoding='utf-8'))

    bind = {}
    stat = dict(models=len(models), parsed=len(src), bound=0, slot=0,
                slot_vc_ok=0, slot_name_ok=0, slot_bound=0,
                has_nrm=0, has_mat=0, has_both=0,
                lyr_models=0, lyr_slots=0, with_ctrl=0, with_l1=0, with_dirt=0)
    reasons = {}
    for h, rows in src.items():
        m = models.get(h)
        if not m:
            continue
        s = m.get('s') or []
        if len(rows) != len(s):
            reasons['slot-count'] = reasons.get('slot-count', 0) + 1
            continue
        st = []
        ly = []
        anyb = False
        anyl = False
        for i, (tid, vc, ic) in enumerate(s):
            r = rows[i]
            stat['slot'] += 1
            if r[0] != vc or r[1] != ic:
                st.append(None)
                ly.append(None)
                continue
            stat['slot_vc_ok'] += 1
            if tid >= 0:
                stored = (names.get(tid) or '').lower()
                got = _clean(r[2]) if isinstance(r[2], str) else ''
                if stored and got and stored != got:
                    st.append(None)
                    ly.append(None)
                    continue
            stat['slot_name_ok'] += 1
            nm = r[3] if isinstance(r[3], str) else None
            mt = r[4] if isinstance(r[4], str) else None
            if nm or mt:
                st.append([nm, mt])
                anyb = True
                stat['slot_bound'] += 1
            else:
                st.append(None)
            # 第二层：**三个名字都保留**，取不到就是 None（apply 时落 -1）
            def _g(k):
                return r[k] if (k < len(r) and isinstance(r[k], str) and r[k]) else None
            l1, ct, dt = _g(COL_L1), _g(COL_CTRL), _g(COL_DIRT)
            extra = [_g(COL_NRM2), _g(COL_MAT2), _g(COL_PAL)]
            if l1 or ct or dt:
                ly.append([l1, ct, dt] + extra)
                anyl = True
                stat['lyr_slots'] += 1
                stat['with_l1'] += 1 if l1 else 0
                stat['with_ctrl'] += 1 if ct else 0
                stat['with_dirt'] += 1 if dt else 0
            else:
                ly.append(None)
        if anyb:
            bind[h] = st
            stat['bound'] += 1
        if anyl:
            bind.setdefault('__lyr__', {})[h] = ly
            stat['lyr_models'] += 1
    # 拆成两份，`slot_bind.json` 保持老结构（h → 逐槽 [nid, mid]），
    # 两层信息放 `slot_bind_lyr.json`，老的下游脚本照旧能读。
    lyr = bind.pop('__lyr__', {})
    # 统计
    for h, st in bind.items():
        n = any(x and x[0] for x in st)
        mm = any(x and x[1] for x in st)
        if n:
            stat['has_nrm'] += 1
        if mm:
            stat['has_mat'] += 1
        if n and mm:
            stat['has_both'] += 1
    stat['reasons'] = reasons
    json.dump(bind, open(P_BIND, 'w', encoding='utf-8'), separators=(',', ':'))
    json.dump(lyr, open(P_BIND.replace('.json', '_lyr.json'), 'w', encoding='utf-8'),
              separators=(',', ':'))
    print('[slot] 绑定：%d 个模型有至少一个槽位；槽位 %d 个（几何对上 %d / 名字对上 %d / 已绑 %d）'
          % (stat['bound'], stat['slot'], stat['slot_vc_ok'], stat['slot_name_ok'], stat['slot_bound']))
    print('[slot] 有法线的模型 %d / 有高光的 %d / 两者都有 %d；按原因丢弃 %s'
          % (stat['has_nrm'], stat['has_mat'], stat['has_both'], reasons))
    print('[slot] 两层：%d 个模型 / %d 个槽位（第1层 %d、control %d、dirt %d）'
          % (stat['lyr_models'], stat['lyr_slots'], stat['with_l1'], stat['with_ctrl'],
             stat['with_dirt']))
    json.dump(stat, open(P_REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


# ------------------------------------------------------------------ 3. 解贴图
# 角色 → 落盘格式（`l1/ct/dt/pl` 要留 alpha，混合遮罩可能就在 alpha 里）
_ROLE_KEEP_ALPHA = ('l1', 'ct', 'dt', 'pl')


def _decode_one(item):
    name, role, e = item
    try:
        from ytd_to_png import decode_one
        from PIL import Image
        import numpy as np
        # 内嵌调色板：解析那趟已经解好放在 work/paltex/ 了
        if e.get('pal_png'):
            im = Image.open(e['pal_png']).convert('RGBA')
        else:
            fp = os.path.join(ROOT, e['f'].replace('/', os.sep))
            with open(fp, 'rb') as f:
                data = f.read()
            blob = data[16 + e['sys'] + e['gfx']:]
            blob = blob[:max(4096, e['w'] * e['h'] * 4)]
            im, fmt = decode_one(blob, e['w'], e['h'], e['fmt'])
            if im is None:
                return name, role, None, 'decode-none'
            im = im.convert('RGBA')
        if max(im.size) > MAXS:
            # ★ 等比 + **颜色/alpha 分开缩**：PIL 12 的 RGBA resize 会按 alpha 预乘，
            #   把 alpha 稀疏的贴图 RGB 乘黑（2026-11-01 实锤，见 ytd_to_png.resize_max）。
            from ytd_to_png import resize_max
            im = resize_max(im, MAXS)
            if im.mode != 'RGBA':
                im = im.convert('RGBA')
        if role in _ROLE_KEEP_ALPHA:
            out = im.convert('RGBA')
        else:
            out = im.convert('RGB')
        if FLIP_G and role in ('nm', 'nm2'):
            a = np.asarray(out, dtype=np.uint8).copy()
            a[:, :, 1] = 255 - a[:, :, 1]
            out = Image.fromarray(a, 'RGB')
        # 遮罩通道：
        #   `ct`  → 方差最大的那个通道（灰度 `_ct` 三通道相同；复用 `_mb` 时往往只有一个在变）
        #   `l1`  → 只看 **alpha**（`_abal` = albedo+alpha，alpha 就是混合权重，
        #           和 RGB 方差无关，不能跟 RGB 抢"最大方差"）
        ch = -1
        try:
            import tex_slots as S
            if role == 'ct':
                ch0, _std = S.mask_channel(out)
                ch = -1 if ch0 is None else int(ch0)
            elif role == 'l1':
                ch = 3 if S.alpha_std(out) > 0.03 else -1
        except Exception:
            ch = -1
        buf = out.tobytes()
        return name, role, (out.size[0], out.size[1], buf, out.mode, ch), None
    except Exception as ex:
        return name, role, None, 'exc:%s' % type(ex).__name__


# `slot_bind_lyr.json` 的行排布：[l1, ctrl, dirt, nrm2, mat2, pal] → (下标, 角色名)
_LAYER_COLS = ((3, 'nm2'), (4, 'ma2'), (0, 'l1'), (1, 'ct'), (2, 'dt'))


def _need_sets(bind, lyr):
    """→ {role: set(names)}：st 提供 nm/ma，lyr 提供 l1/ct/dt/nm2/ma2/pl。"""
    need = {'nm': set(), 'ma': set(), 'l1': set(), 'ct': set(), 'dt': set(),
            'nm2': set(), 'ma2': set(), 'pl': set()}
    for st in bind.values():
        for x in st:
            if not x:
                continue
            if x[0]:
                need['nm'].add(x[0])
            if x[1]:
                need['ma'].add(x[1])
    for rows in lyr.values():
        for r in rows:
            if not r:
                continue
            for i, role in _LAYER_COLS:
                if r[i]:
                    need[role].add(r[i])
            if r[5]:
                need['pl'].add(r[5])
    return need


def stage_decode(a):
    bind = json.load(open(P_BIND, encoding='utf-8'))
    lyr = json.load(open(P_BIND.replace('.json', '_lyr.json'), encoding='utf-8'))
    texidx = json.load(open(TEXIDX, encoding='utf-8'))
    idx = json.load(open(INDEX, encoding='utf-8'))
    tex = idx['tex']
    have = {(t.get('n') or '').lower() for t in tex}

    need = _need_sets(bind, lyr)
    print('[slot] 需要法线 %d / 材质 %d / 第1层 %d / control %d / dirt %d / 层法线 %d / 层材质 %d / 调色板 %d（去重）'
          % (len(need['nm']), len(need['ma']), len(need['l1']), len(need['ct']),
             len(need['dt']), len(need['nm2']), len(need['ma2']), len(need['pl'])))

    jobs = []
    miss = []
    seen = set()
    for role in ('nm', 'ma', 'l1', 'ct', 'dt', 'nm2', 'ma2', 'pl'):
        for nm in sorted(need[role]):
            k = nm.lower()
            if k in have or k in seen:
                continue
            seen.add(k)
            if role == 'pl':
                p = os.path.join(P_PAL, nm + '.png')
                if not os.path.exists(p):
                    miss.append((nm, role, 'no-embedded-palette'))
                    continue
                jobs.append((nm, role, dict(pal_png=p)))
                continue
            e = texidx.get(k)
            if not e:
                miss.append((nm, role, 'no-ytd'))
                continue
            jobs.append((nm, role, e))
    print('[slot] 待解 %d 张（已存在 / ytd 里没有 的不算）' % len(jobs))

    texdir = os.path.join(LIB, 'tex')
    new = []
    fail = list(miss)
    t0 = time.time()
    done = 0
    tid = len(tex)
    with mp.Pool(a.jobs) as pool:
        for name, role, res, why in pool.imap_unordered(_decode_one, jobs, chunksize=16):
            done += 1
            if res is None:
                fail.append((name, role, why))
            else:
                w, h, buf, mode, ch = res
                new.append((name, role, w, h, buf, mode, ch, tid))
                tid += 1
            if done % 1000 == 0:
                el = time.time() - t0
                print('[slot] 解码 %d/%d 成功 %d 失败 %d  %.0f/s 剩 ~%.0f 分'
                      % (done, len(jobs), len(new), len(fail), done / el,
                         (len(jobs) - done) / max(1e-9, done / el) / 60), flush=True)

    # 写盘（串行，避免多进程抢同一目录句柄）
    from PIL import Image
    meta = []
    for name, role, w, h, buf, mode, ch, tid in new:
        fp = os.path.join(texdir, '%05d.png' % tid)
        Image.frombytes(mode, (w, h), buf).save(fp, 'PNG', optimize=False)
        e = dict(id=tid, n=name, f='tex/%05d.png' % tid, role=role,
                 gflip=(1 if (role in ('nm', 'nm2') and FLIP_G) else 0), w=w, h=h)
        if ch >= 0:
            e['ch'] = ch
        meta.append(e)
    json.dump(meta, open(P_NEW, 'w', encoding='utf-8'), ensure_ascii=False)
    print('[slot] 解出 %d 张，失败 %d；%.1f 分钟 → %s'
          % (len(meta), len(fail), (time.time() - t0) / 60, os.path.basename(P_NEW)))
    if fail:
        json.dump([{'n': n, 'role': r, 'why': w} for n, r, w in fail],
                  open(os.path.join(WORK, 'slot_tex_fail.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)


# ------------------------------------------------------------------ 4. 回写 index
def stage_apply(a):
    bind = json.load(open(P_BIND, encoding='utf-8'))
    lyr = json.load(open(P_BIND.replace('.json', '_lyr.json'), encoding='utf-8'))
    meta = json.load(open(P_NEW, encoding='utf-8'))
    idx = json.load(open(INDEX, encoding='utf-8'))
    models, tex = idx['models'], idx['tex']

    by_name_role = {}
    by_name = {}
    for t in tex:
        nm = (t.get('n') or '').lower()
        by_name_role[(nm, t.get('role') or 'ab')] = t['id']
        by_name.setdefault(nm, t['id'])

    def lookup(nm, role):
        if not nm:
            return -1
        k = nm.lower()
        if (k, role) in by_name_role:
            return by_name_role[(k, role)]
        return by_name.get(k, -1)      # 同名图已是别的 role（同一张图，复用即可）

    added = 0
    for e in meta:
        k = (e['n'].lower(), e['role'])
        if k in by_name_role:
            continue
        tex.append(e)
        by_name_role[k] = e['id']
        by_name.setdefault(k[0], e['id'])
        added += 1
    print('[slot] 贴图表 %d → %d（新增 %d）' % (len(tex) - added, len(tex), added))

    nslots = 0
    nbound = 0
    nmiss = 0
    for h, st in bind.items():
        m = models.get(h)
        if not m:
            continue
        s = m.get('s') or []
        if len(st) != len(s):
            continue
        out = []
        for i, x in enumerate(st):
            if not x:
                out.append([-1, -1])
                continue
            nid = lookup(x[0], 'nm') if x[0] else -1
            mid = lookup(x[1], 'ma') if x[1] else -1
            if nid < 0 and mid < 0:
                out.append([-1, -1])
                continue
            out.append([nid, mid])
            nbound += 1
            if nid < 0 or mid < 0:
                nmiss += 1
        m['st'] = out
        nslots += len(out)

    # ---- 两层：`lyr` 与 `s`/`st` 等长同序 → [l1, ctrl, dirt, nrm2, mat2]（-1 = 没有）
    #
    # 🔴 遮罩通道（`tex[i].ch`）必须**对"复用池里已有贴图"的情况也补算**：
    #    同一个文件经常既当 `_ma`（高光）又当 `controltexturetex`（实测码头
    #    `nbx_wall_woodplanks_rotted_docks_01_ma` 就是），而 decode 阶段按名字去重会跳过它
    #    → 老条目没有 `ch` → 材质那边判成"没有可控遮罩"，两层白接。
    by_id = {t['id']: t for t in tex}

    def ensure_ch(tid, kind):
        e = by_id.get(tid)
        if not e or not e.get('f'):
            return
        if e.get('ch') is not None:
            return
        p = os.path.join(LIB, e['f'])
        if not os.path.exists(p):
            return
        try:
            from PIL import Image
            import tex_slots as S
            im = Image.open(p)
            if kind == 'ct':
                ch0, _std = S.mask_channel(im)
                e['ch'] = -1 if ch0 is None else int(ch0)
            else:
                e['ch'] = 3 if S.alpha_std(im) > 0.03 else -1
        except Exception:
            return

    nl_models = 0
    nl_slots = 0
    nl_full = 0
    for h, rows in lyr.items():
        m = models.get(h)
        if not m:
            continue
        s = m.get('s') or []
        if len(rows) != len(s):
            continue
        out = []
        for r in rows:
            if not r:
                out.append(None)
                continue
            l1 = lookup(r[0], 'l1') if r[0] else -1
            ct = lookup(r[1], 'ct') if r[1] else -1
            dt = lookup(r[2], 'dt') if r[2] else -1
            n2 = lookup(r[3], 'nm2') if r[3] else -1
            m2 = lookup(r[4], 'ma2') if r[4] else -1
            if ct >= 0:
                ensure_ch(ct, 'ct')
            if l1 >= 0:
                ensure_ch(l1, 'l1')
            # 调色板只记 id（当前材质不使用，语义未验证；留着供后续）
            out.append([l1, ct, dt, n2, m2])
            if l1 >= 0:
                nl_slots += 1
                if ct >= 0 or l1 >= 0:
                    nl_full += 1
        m['lyr'] = out
        nl_models += 1

    bak = os.path.join(LIB, 'index_before_slots_%s.json' % time.strftime('%Y%m%d_%H%M'))
    if not os.path.exists(bak):
        shutil.copy2(INDEX, bak)
        print('[slot] 备份 %s' % os.path.basename(bak))

    idx['tex_epoch'] = time.strftime('%Y%m%d')
    idx['slot_epoch'] = time.strftime('%Y-%m-%dT%H:%M')
    json.dump(idx, open(INDEX, 'w', encoding='utf-8'), separators=(',', ':'))
    print('[slot] 写入 %s：%d 个模型带 st / %d 个槽位已绑（其中 %d 个只有一张图）'
          % (os.path.basename(INDEX), len(bind), nbound, nmiss))
    print('[slot] 写入 lyr：%d 个模型 / %d 个槽位有第1层（其中 %d 个可混合）'
          % (nl_models, nl_slots, nl_full))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', required=True, choices=['parse', 'bind', 'decode', 'apply'])
    ap.add_argument('--jobs', type=int, default=max(4, (os.cpu_count() or 8) - 4))
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    {'parse': stage_parse, 'bind': stage_bind,
     'decode': stage_decode, 'apply': stage_apply}[a.stage](a)


if __name__ == '__main__':
    mp.freeze_support()
    main()
