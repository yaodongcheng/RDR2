"""通用版「据点真模型（L2）」导出：把任意据点的建筑 ydr + 原生贴图导成
与 `town_textured.json` 同构的 JSON，再用 `build_world_map.pack_l2` 量化成 l2/<code>.js。

★ 与旧脚本（只服务 Valentine）的关键区别：**实体按世界坐标空间聚类取**，不按 ymap 文件名前缀。
  安尼斯堡就是反例：它的建筑被几十个**哈希命名的 ymap** 分散引用，按 `ann_*.ymap` 前缀分组只能捞到 632 个
  实体、命中 4 个建筑；改成"中心 230 m 内的全部实体"后能捞到 3545 个实体、命中 **219 个 ann 建筑**。

用法：
  uv run python tools/export_town_l2.py --code ann --cx 2884 --cy 1348 --r 230 \
      --ydr work/ann/models --out work/ann/town.json
"""
import os
import re
import io
import sys
import glob
import json
import base64
import argparse
import builtins
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import rdr2_ydr as Y
import rdr2_vdecl as V
import rdr2_ytd as T
from ytd_to_png import decode_one

ROOT = r'D:/BrainMaker/大镖客2解包分析'
MAXS = 128      # 贴图边长上限（瓦伦丁那套也是 128²，够用且省 4 倍）
KNOWN_FMT = {0x46, 0x47, 0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x4F, 0x50, 0x51,
             0x52, 0x53, 0x54, 0x57, 0x5A, 0x5B, 0x1B, 0x1C, 0x1D, 0x5E, 0x5F, 0x60, 0x61, 0x62, 0x63}
ROLE_ALBEDO = ('albedo', 'albedo_layer0', 'albedo_layer1', 'albedo_layer2', 'albedo_layer3',
               'lyr0diffusetex', 'albedo_dirt')
EXCLUDE = ('_em_slod', '_slod', 'audioproxy', 'vfx_', 'helper', 'lights_holder',
           '_decal', 'decal', '_props_', 'props_debris', 'footboards', '_dcl', '_veg',
           '_shad', '_em00', '_int_', '_lod', 'pr_combo', 'audioemitter', '_glue')
_SUFFIX_POS = re.compile(r'_(ab|abal|abte|al|nm|ma|mb|ct|d|s)')
# ★ 同一栋楼的「表现层变体」：游戏按距离/状态切换用，**同位置只能留一个**
#   不加这个过滤会把一栋楼画 2~3 遍（互相重叠 + z-fighting）⇒ 看起来又乱又"缺"
VARIANT = re.compile(r'(_em_hd|_det_dec|_detail|_dec|_dc|_dslod|_slod|_glue|_d)$')


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xffffffff
        h = (h + (h << 10)) & 0xffffffff
        h ^= (h >> 6)
    h = (h + (h << 3)) & 0xffffffff
    h ^= (h >> 11)
    h = (h + (h << 15)) & 0xffffffff
    return h


def clean_name(n):
    if not n or len(n) < 12:
        return n
    for m in _SUFFIX_POS.finditer(n):
        cut = m.end()
        A, B = n[:cut], n[cut:]
        if len(B) < 8:
            continue
        i = A.rfind('_')
        if i <= 0:
            continue
        base = A[:i]
        if len(base) < 6:
            continue
        if B.lower().startswith(base.lower()):
            return A
    return n


# ---------------------------------------------------------------- 贴图索引
def build_index(dirs):
    idx = {}
    files = []
    for d in dirs:
        files += glob.glob(os.path.join(d, '**', '*.ytd'), recursive=True)
    for f in files:
        try:
            y = T.Ytd(open(f, 'rb').read())
        except Exception:
            continue
        for t in y.textures():
            if not t['name']:
                continue
            k = t['name'].lower()
            cur = idx.get(k)
            if cur is None or (t['w'] * t['h']) > (cur[1]['w'] * cur[1]['h']):
                idx[k] = (y, t)
    return idx, len(files)


# ---------------------------------------------------------------- 主流程
def main():
    global MAXS
    ap = argparse.ArgumentParser()
    ap.add_argument('--code', required=True)
    ap.add_argument('--cx', type=float, required=True)
    ap.add_argument('--cy', type=float, required=True)
    ap.add_argument('--r', type=float, default=230.0)
    ap.add_argument('--ydr', required=True, help='该据点模型的 ydr 目录')
    ap.add_argument('--ytd', default='', help='额外的 ytd 目录（逗号分隔）')
    ap.add_argument('--maxs', type=int, default=128)
    ap.add_argument('--weld', type=float, default=0.0,
                    help='顶点焊接阈值（m）。城市高模有大量 <0.25m 的装饰三角，'
                         '按 (位置,UV) 焊接可在几乎不损外形的前提下去掉它们')
    ap.add_argument('--budget', type=int, default=0,
                    help='顶点预算（0=不限）。超预算时**按模型顶点数从大到小**保留实例，'
                         '小杂物自动落回灰盒（不会丢失内容）')
    ap.add_argument('--chunk', type=float, default=0.0,
                    help='>0 时按该边长(m)把实例切成空间分块，输出到 <out 所在目录>/chunks/，'
                         '配套 tex.json（共享贴图）。供查看器按视距按需加载')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    MAXS = a.maxs
    tex_dirs = [os.path.join(ROOT, 'export/models')] + [x for x in a.ytd.split(',') if x]
    hp_path = a.out.replace('town.json', 'hpatch.json')
    index, nfiles = build_index(tex_dirs)
    print(f'贴图索引 {len(index)} 名（{nfiles} 个 .ytd）')

    # ---- 模型名表（joaat → 文件）----
    byname = {}
    for f in glob.glob(os.path.join(a.ydr, '**', '*.ydr'), recursive=True):
        n = os.path.splitext(os.path.basename(f))[0]
        if any(s in n for s in EXCLUDE):
            continue
        byname[n] = f
    hash2file = {joaat(n): (n, f) for n, f in byname.items()}
    print(f'{a.code} 模型名 {len(hash2file)} 个（{a.ydr}，已剔 LOD/decal/影）')

    # ---- 空间聚类取实体 ----
    import builtins as _b
    _p = _b.print
    _b.print = lambda *x, **k: None
    import ymap_entities
    _b.print = _p
    R2 = a.r * a.r
    insts, used = [], set()
    seen = set()
    for f in sorted(glob.glob(os.path.join(ROOT, 'export/levels/map_metadata/**/*.ymap'), recursive=True)):
        try:
            sig, size, ents = ymap_entities.extract(f)
        except Exception:
            continue
        for e in ents:
            if (e[1] - a.cx) ** 2 + (e[2] - a.cy) ** 2 > R2:
                continue
            h = e[0]
            if h not in hash2file:
                continue
            key = (h, round(e[1], 1), round(e[2], 1), round(e[3], 1))
            if key in seen:                      # 去重：同一实例可能出现在多张 ymap
                continue
            seen.add(key)
            name, _f = hash2file[h]
            insts.append([name, round(e[1], 2), round(e[2], 2), round(e[3], 2),
                          round(e[4], 4), round(e[5], 4), round(e[6], 4), round(e[7], 4),
                          round(e[8], 3), round(e[8], 3), round(e[9], 3)])   # ★ (sxy,sxy,sz)：RDR2 的 XY 是水平面
            used.add(name)
    # ---- ★ 去重：同一位置的多层变体只留一个（优先"基名"）----
    def base_of(n):
        b = n
        while VARIANT.search(b):
            b = VARIANT.sub('', b)
        return b
    groups = {}
    for it in insts:
        # 只按"位置 + 基名"分组（变体的旋转常有微小差异，不能把旋转算进键）
        key = (round(it[1], 1), round(it[2], 1), round(it[3], 1), base_of(it[0]))
        groups.setdefault(key, []).append(it)
    kept, dropped = [], 0
    for key, g in groups.items():
        if len(g) == 1:
            kept.append(g[0]); continue
        g.sort(key=lambda t: (1 if VARIANT.search(t[0]) else 0, len(t[0])))
        kept.append(g[0]); dropped += len(g) - 1
    if dropped:
        print(f'  ★ 同位置变体去重：{len(insts)} → {len(kept)}（丢掉 {dropped} 个 _em_hd/_d/_dc 等表现层）')
    insts = kept
    used = {i[0] for i in insts}
    print(f'半径 {a.r:.0f} m 内命中模型实例 {len(insts)} 个，涉及 {len(used)} 个模型')

    # ---- ★ 顶点预算：按模型顶点数从大到小保留（保证最显眼的建筑优先）----
    if a.budget:
        import numpy as _np
        size = {}
        for nm in used:
            size[nm] = os.path.getsize(byname[nm])      # 用文件体积近似顶点数，省一次解析
        insts.sort(key=lambda it: -size.get(it[0], 0))
        keep, acc = [], 0
        for it in insts:
            if acc >= a.budget and keep:
                break
            keep.append(it); acc += size.get(it[0], 0)
        print(f'  ★ 顶点预算：{len(insts)} → {len(keep)} 实例（文件总量 {acc/1048576:.0f} MB 上限 {a.budget/1048576:.0f} MB）')
        insts = keep
        used = {i[0] for i in insts}

    # ---- 逐模型抽几何 ----
    tex_cache, tex_names, tex_id = {}, [], {}
    models = {}

    def enc(im):
        if im.mode != 'RGBA':
            im = im.convert('RGBA')
        im = im.resize((MAXS, MAXS))
        b = io.BytesIO()
        im.save(b, 'PNG', optimize=True)
        return base64.b64encode(b.getvalue()).decode()

    def dec_entry(y, t):
        blob = y.gfx[t['gfx_off']:t['gfx_off'] + max(4096, t['w'] * t['h'] * 4)]
        return decode_one(blob, t['w'], t['h'], t['fmt'])

    def get_tex(name):
        if name in tex_cache:
            return tex_cache[name]
        im = None
        ent = index.get(clean_name(name).lower())
        if ent:
            im, _ = dec_entry(*ent)
        if im is None:
            stem = name.lower()
            base = re.sub(r'_(ab|abal|al|abte|nm|ma|mb|d|s|ct|dr)$', '', stem)
            cands = [k for k in index if k.startswith(base) and k != stem]
            if not cands:
                toks = [w for w in re.split(r'[^a-z]+', base) if len(w) >= 5]
                best = None
                for k in index:
                    sc = sum(1 for w in toks if w in k)
                    if sc > 0 and (best is None or sc > best[0]):
                        best = (sc, k)
                if best and best[0] >= 1:
                    cands = [best[1]]
            if cands:
                y, t = index[sorted(cands)[0]]
                im, _ = dec_entry(y, t)
        if im is None:
            tex_cache[name] = None
            return None
        d = dict(b64=enc(im))
        tex_cache[name] = d
        return d

    for name in sorted(used):
        f = byname[name]
        try:
            res = Y.Res(open(f, 'rb').read())
            shaders = Y.parse_shader_group(res, res.u64(0x10))
            shd_all = Y.parse_shader_hashes(res, res.u64(0x10))
        except Exception:
            continue
        glist = []
        for mo in Y.pointer_list(res, res.u64(0x50)):
            gs = Y.parse_model_geoms(res, mo)
            shmap = Y.parse_model_shaders(res, mo, len(gs))
            for gi, gp in enumerate(gs):
                glist.append((gp, shmap[gi] if gi < len(shmap) else 0))
        P, UV, IDX, G, base = [], [], [], [], 0
        for gp, sid in glist:
            go = res.off(gp)
            vb = Y.parse_vertex_buffer(res, res.u64(go + 0x08))
            ib = Y.parse_index_buffer(res, res.u64(go + 0x10))
            vd = V.parse_vdecl(res, res.u64(vb['off'] + 0x38)) if vb else None
            if not vd:
                continue
            texs = shaders[sid] if 0 <= sid < len(shaders) else []
            pos = V.read_element(res, vb['data'], vd, 0)
            if not pos:
                continue
            uv0 = V.read_element(res, vb['data'], vd, 28)
            if len(uv0) < len(pos):
                uv0 = uv0 + [[0, 0]] * (len(pos) - len(uv0))
            idx = Y.read_indices(res, ib) if ib else []
            if not idx:
                continue
            alb = None
            for t in texs:
                if (t.get('role') or '') in ROLE_ALBEDO and t.get('name') \
                        and not t['name'].lower().startswith('blank'):
                    alb = t
                    break
            if alb is None:
                for t in texs:
                    if t.get('role') == 'albedo2' and t.get('name'):
                        alb = t
                        break
            key = alb['name'] if alb else ''
            if key and key not in tex_id:
                tex_id[key] = len(tex_names)
                tex_names.append(key)
            # ---- ★ 逐几何体焊接（位置 + UV 联合键）：保住各自的材质组 ----
            start = len(IDX)
            if a.weld > 0 and idx:
                import numpy as _np
                Pn = _np.asarray(pos, dtype='float32')
                Un = _np.asarray([(u[0], u[1]) if u and len(u) > 1 else (0.0, 0.0) for u in uv0],
                                 dtype='float32')
                kk = _np.hstack([_np.round(Pn / a.weld).astype('int64'),
                                 _np.round(Un * 511).astype('int64')])
                _, first, inv = _np.unique(kk, axis=0, return_index=True, return_inverse=True)
                inv = inv.reshape(-1)
                ji = inv[_np.asarray(idx, dtype='int64').reshape(-1, 3)]
                kp = ~((ji[:, 0] == ji[:, 1]) | (ji[:, 1] == ji[:, 2]) | (ji[:, 0] == ji[:, 2]))
                ji = ji[kp]
                if len(ji):
                    _, u2 = _np.unique(_np.sort(ji, axis=1), axis=0, return_index=True)
                    ji = ji[_np.sort(u2)]
                op = Pn[first]; ou = Un[first]
            else:
                op = pos; ou = [(u[0], u[1]) if u and len(u) > 1 else (0.0, 0.0) for u in uv0]
                ji = None
            for v in op:
                P.extend([round(float(v[0]), 1), round(float(v[1]), 1), round(float(v[2]), 1)])
            for u in ou:
                UV.extend([round(float(u[0]), 3), round(float(u[1]), 3)])
            n_new = len(op)
            IDX.extend([i + base for i in (ji.ravel().tolist() if ji is not None else idx)])
            base += n_new
            G.append([start, len(IDX) - start, tex_id.get(key, -1),
                      (shd_all[sid]['name'] if 0 <= sid < len(shd_all) and shd_all[sid]['name'] else '')])
        if not IDX:
            continue
        cnt = Counter(g[2] for g in G if g[2] >= 0)
        dom = cnt.most_common(1)[0][0] if cnt else -1
        for g in G:
            if g[2] < 0:
                g[2] = dom
        models[name] = dict(p=P, uv=UV, i=IDX, vc=base, tc=len(IDX) // 3, g=G)

    print(f'模型 {len(models)} 个，顶点 {sum(m["vc"] for m in models.values())}，'
          f'三角 {sum(m["tc"] for m in models.values())}')
    # 收集用到的贴图（只取模型实际引用的）
    need = set()
    for m in models.values():
        for g in m['g']:
            if 0 <= g[2] < len(tex_names):
                need.add(tex_names[g[2]])
    for nm in sorted(need):
        get_tex(nm)
    tex = {k: v for k, v in tex_cache.items() if v is not None}
    print(f'贴图 {len(tex)} 张（缺 {len(need) - len(tex)}）')

    # 重映射 tex_names → 只保留有图的
    remap, names2 = {}, []
    for i, nm in enumerate(tex_names):
        if nm in tex:
            remap[i] = len(names2)
            names2.append(nm)
    for m in models.values():
        for g in m['g']:
            g[2] = remap.get(g[2], -1)
    models = {k: v for k, v in models.items() if any(g[2] >= 0 for g in v['g'])}
    insts = [i for i in insts if i[0] in models]
    print(f'最终：模型 {len(models)} / 实例 {len(insts)} / 贴图 {len(names2)}')

    if a.chunk > 0:
        # ---- ★ 分块输出：共享贴图 + 每块一个文件（查看器按视距按需加载）----
        outdir = os.path.join(os.path.dirname(a.out), 'chunks')
        os.makedirs(outdir, exist_ok=True)
        json.dump(dict(tex=tex, tex_names=names2, hp=json.load(open(hp_path, encoding='utf-8'))
                       if hp_path and os.path.exists(hp_path) else None,
                       chunk=a.chunk, center=[a.cx, a.cy]),
                  open(os.path.join(outdir, 'tex.json'), 'w', encoding='utf-8'),
                  separators=(',', ':'))
        cs = a.chunk
        buckets = {}
        for it in insts:
            k = (int((it[1] - a.cx) // cs), int((it[2] - a.cy) // cs))
            buckets.setdefault(k, []).append(it)
        total = 0
        for k, its in sorted(buckets.items()):
            names = {i[0] for i in its}
            sub = {n: models[n] for n in names if n in models}
            if not sub:
                continue
            fp = os.path.join(outdir, f'c{k[0]}_{k[1]}.json')
            json.dump(dict(models=sub, insts=its, key=[k[0], k[1]], chunk=cs,
                           center=[a.cx, a.cy]),
                      open(fp, 'w', encoding='utf-8'), separators=(',', ':'))
            total += os.path.getsize(fp)
        print(f'-> {outdir}/  {len(buckets)} 块，合计 {total/1048576:.1f} MB；'
              f'tex.json {os.path.getsize(os.path.join(outdir,"tex.json"))/1048576:.1f} MB')
    else:
        json.dump(dict(tex=tex, tex_names=names2, models=models, insts=insts,
                       center=[a.cx, a.cy]), open(a.out, 'w', encoding='utf-8'),
                  separators=(',', ':'))
        print(f'-> {a.out}  {os.path.getsize(a.out)/1048576:.1f} MB')


if __name__ == '__main__':
    main()
