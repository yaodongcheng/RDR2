"""把**整个瓦伦丁小镇**按"真 UV + shader slot 语义贴图"导出（供单文件查看器用）。

与旧 `valentine_real.html` 的区别：**用游戏原生 UV（TEXCOORD0）与正确的逐几何体 albedo**，
不再是 box mapping + 单张猜的贴图。

流程：
  1. `valentine.json`（实体：[archetype, x,y,z, quat, scale]）→ 与 `joaat(<ydr名>)` 对上模型；
  2. **只取小镇核心**（半径 R 内）的实例，避免全区域爆体积；
  3. 每个模型只导一次（几何 + 逐几何体 albedo 索引），实例只存变换；
  4. 贴图三级解析：`.ytd` 索引（**大小写不敏感 + 取 HD**）→ `.ydr` 内嵌（仅 `*_pal`）→ 同族/词干回退。

输出：`export/levels/town/town_textured.json`
"""
import os
import sys
import glob
import json
import base64
import io
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import rdr2_ydr as Y
import rdr2_vdecl as V
import rdr2_ytd as T
from ytd_to_png import decode_one

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TOWN = os.path.join(ROOT, 'export/levels/town')
GTXD = r'C:/Users/yaodongcheng/AppData/Local/Temp/codemaker/gtxd/out'
OUT = os.path.join(TOWN, 'town_textured.json')
MAXS = 128
RADIUS = 300.0          # 小镇核心半径（米）
KNOWN_FMT = {0x46, 0x47, 0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x4F, 0x50, 0x51,
             0x52, 0x53, 0x54, 0x57, 0x5A, 0x5B, 0x1B, 0x1C, 0x1D, 0x5E, 0x5F, 0x60, 0x61, 0x62, 0x63}
# ★ 名字池会把**相邻两个同名纹理**粘在一起（`X_ab` + `X_al`）。条目名以真名开头，
#   所以切成 `A|B` 且 **B 以 A 的前缀开头** 时，取 A = 该条目的真名（数据也随之对上）。
_SUFFIX_POS = re.compile(r'_(ab|abal|abte|al|nm|ma|mb|ct|d|s)')


def clean_name(n):
    """把 "A_abA_al" 这类粘接名截回 "A_ab"；普通名原样返回。"""
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

ROLE_ALBEDO = ('albedo', 'albedo_layer0', 'albedo_layer1', 'albedo_layer2', 'albedo_layer3',
               'lyr0diffusetex', 'albedo_dirt')


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


def build_index():
    idx = {}
    files = glob.glob(os.path.join(ROOT, 'export/models/**/*.ytd'), recursive=True)
    if os.path.isdir(GTXD):
        files += glob.glob(os.path.join(GTXD, '*.ytd'))
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


def main():
    index, nfiles = build_index()
    print(f'贴图索引 {len(index)} 名（{nfiles} 个 .ytd）')

    tex_cache = {}

    def enc(im):
        # ★ 保留 alpha：道路/贴花是 `standard_decal*`（靠 alpha 混合到地面），
        #   一旦丢弃 alpha，半透明边缘会变成**不透明的白带**（"白色的带子"的真凶）
        if im.mode != 'RGBA':
            im = im.convert('RGBA')
        im = im.resize((MAXS, MAXS))
        b = io.BytesIO()
        im.save(b, 'PNG', optimize=True)
        return base64.b64encode(b.getvalue()).decode()

    def dec_entry(y, t):
        blob = y.gfx[t['gfx_off']:t['gfx_off'] + max(4096, t['w'] * t['h'] * 4)]
        return decode_one(blob, t['w'], t['h'], t['fmt'])

    def get_tex(name, res=None, desc=None):
        if name in tex_cache:
            return tex_cache[name]
        im = None
        fb = None
        ent = index.get(clean_name(name).lower())
        if ent:
            im, _ = dec_entry(*ent)
        if im is None and desc and desc.get('dptr') and res is not None and name.lower().endswith('_pal'):
            w, h = desc.get('w') or 0, desc.get('h') or 0
            code = ((desc.get('fmt') or 0) >> 24) & 0xFF
            if (4 <= w <= 8192 and 4 <= h <= 8192 and (w & (w - 1)) == 0 and (h & (h - 1)) == 0
                    and code in KNOWN_FMT):
                try:
                    blob = res.blob(desc['dptr'], max(4096, w * h * 4))
                    im, _ = decode_one(blob, w, h, desc['fmt'])
                except Exception:
                    im = None
        if im is None:
            stem = name.lower()
            base = re.sub(r'_(ab|abal|al|abte|nm|ma|mb|d|s|ct|dr)$', '', stem)
            suf_m = re.search(r'_(ab|abal|al|abte|nm|ma|mb|d|s|ct|dr)$', stem)
            suf = suf_m.group(0) if suf_m else ''
            cands = [k for k in index if k.startswith(base) and k != stem]
            if not cands:
                toks = [w for w in re.split(r'[^a-z]+', base) if len(w) >= 4]
                toks += [w[:6] for w in toks if len(w) >= 6]
                best = None
                for k in index:
                    sc = sum(1 for w in toks if w in k) - (0 if (suf and k.endswith(suf)) else 0.4)
                    if sc > 0 and (best is None or sc > best[0]):
                        best = (sc, k)
                if best:
                    cands = [best[1]]
            if cands:
                y, t = index[sorted(cands)[0]]
                im, _ = dec_entry(y, t)
                fb = t['name']
        if im is None:
            tex_cache[name] = None
            return None
        d = dict(b64=enc(im))
        if fb:
            d['fb'] = fb
        tex_cache[name] = d
        return d

    # ---- 实体 → 模型 ----
    ents = json.load(open(os.path.join(TOWN, 'valentine.json'), encoding='utf-8'))
    xs = [e[1] for e in ents]; ys = [e[2] for e in ents]
    cx = (min(xs) + max(xs)) / 2; cy = (min(ys) + max(ys)) / 2
    print(f'小镇中心 ≈ ({cx:.1f}, {cy:.1f})；半径 {RADIUS} m 内取实例')

    byname = {}
    for f in glob.glob(os.path.join(ROOT, 'export/models/buildings_jklm/**/*.ydr'), recursive=True):
        byname[os.path.splitext(os.path.basename(f))[0]] = f
    EXCLUDE = ('_em_slod', '_slod', 'audioproxy', 'vfx_', 'helper', 'lights_holder',
               '_decal', 'decal', '_props_', 'props_debris', 'footboards', '_dcl', '_veg',
               '_shad', '_em00', '_int_', '_lod', 'pr_combo', 'audioemitter')
    hash2file = {}
    for name, f in byname.items():
        if any(s in name for s in EXCLUDE):
            continue
        hash2file[joaat(name)] = (name, f)

    insts = []
    used_models = set()
    for e in ents:
        h = e[0]
        if h not in hash2file:
            continue
        x, y, z = e[1], e[2], e[3]
        if (x - cx) ** 2 + (y - cy) ** 2 > RADIUS * RADIUS:
            continue
        q = e[4:8] if len(e) >= 8 else [0, 0, 0, 1]
        sc = e[8:11] if len(e) >= 11 else [1, 1, 1]
        name, f = hash2file[h]
        insts.append([name, round(x, 2), round(y, 2), round(z, 2),
                      round(q[0], 4), round(q[1], 4), round(q[2], 4), round(q[3], 4),
                      round(sc[0], 3), round(sc[1], 3), round(sc[2], 3)])
        used_models.add(name)
    print(f'实例 {len(insts)} 个，涉及模型 {len(used_models)} 个')

    models = {}
    tex_names = []
    tex_id = {}
    for name in sorted(used_models):
        f = byname[name]
        try:
            res = Y.Res(open(f, 'rb').read())
            info, ms = Y.extract_at(res, 0, 'high')
            geoms = V.geoms_of(res, 0)
        except Exception:
            continue
        P, UV, IDX, G = [], [], [], []
        base = 0
        # ★ 按 **几何体自己的 shaderID** 取材质（不要用 extract_at 的下标对齐：
        #   它会跳过没有 VB 的几何体，下标会错位 ⇒ 贴图挂错面 ⇒ 整片占位色）
        shaders = Y.parse_shader_group(res, res.u64(0x10))
        glist = []
        for mo in Y.pointer_list(res, res.u64(0x50)):
            gs = Y.parse_model_geoms(res, mo)
            shmap = Y.parse_model_shaders(res, mo, len(gs))
            for gi, gp in enumerate(gs):
                glist.append((gp, shmap[gi] if gi < len(shmap) else 0))
        shd_all = Y.parse_shader_hashes(res, res.u64(0x10))
        for n, (gp, sid) in enumerate(glist):
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
            # 逐几何体 albedo（按 shader slot 语义）
            alb = None
            for t in texs:
                if (t.get('role') or '') in ROLE_ALBEDO and t.get('name') and not t['name'].lower().startswith('blank'):
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
            start = len(IDX)
            IDX.extend([i + base for i in idx])
            base += len(pos)
            for i in range(len(pos)):
                P.extend([round(pos[i][0], 1), round(pos[i][1], 1), round(pos[i][2], 1)])
                u = uv0[i] if i < len(uv0) else None
                UV.extend([round(u[0], 2) if u else 0.0, round(u[1], 2) if u and len(u) > 1 else 0.0])
            G.append([start, len(idx), tex_id.get(key, -1),
                      (shd_all[sid]['name'] if 0 <= sid < len(shd_all) and shd_all[sid]['name'] else '')])
        if not IDX:
            continue
        # ★ 兜底：没有 albedo（或解析不到图）的几何体，改用"本模型出现最多的 albedo"，
        #    避免出现绿色/占位色大块（各几何体都是同一栋楼的材质族，视觉上自洽）
        from collections import Counter
        cnt = Counter(g[2] for g in G if g[2] >= 0)
        dom = cnt.most_common(1)[0][0] if cnt else -1
        for g in G:
            if g[2] < 0:
                g[2] = dom
        models[name] = dict(p=P, uv=UV, i=IDX, vc=base, tc=len(IDX) // 3, g=G)

    print(f'模型 {len(models)} 个，顶点合计 {sum(m["vc"] for m in models.values())}')
    # 贴图
    for nm in tex_names:
        desc = None
        res = None
        get_tex(nm, None, None)
    tex = {k: v for k, v in tex_cache.items() if v is not None}
    miss = sum(1 for v in tex_cache.values() if v is None)
    fb = sum(1 for v in tex.values() if v.get('fb'))
    print(f'贴图 {len(tex)} 张（缺 {miss}，回退 {fb}）')

    # ---- 地形 LOD + 树（复用既有导出，避免重跑整条链）----
    def pack_simple(d, keep=None):
        out = {}
        for k, v in d.items():
            if keep is not None and k not in keep:
                continue
            p = v.get('p') or []
            i = v.get('i') or []
            if not i:
                continue
            out[k] = dict(p=[round(x, 1) for x in p], i=i)
        return out

    terrain_models, terrain_insts = {}, []
    tp = os.path.join(TOWN, 'valentine_terrain_meshes.json')
    ip = os.path.join(TOWN, 'terrain_instances.json')
    if os.path.exists(tp) and os.path.exists(ip):
        TERRM = json.load(open(tp, encoding='utf-8'))
        ARAL = json.load(open(ip, encoding='utf-8'))
        used_t = {str(e[0]) for e in ARAL}
        terrain_models = pack_simple(TERRM, used_t)
        for e in ARAL:
            k = str(e[0])
            if k not in terrain_models:
                continue
            terrain_insts.append([k] + [round(float(x), 2) for x in e[1:4]]
                                 + [round(float(x), 4) for x in (e[4:8] if len(e) >= 8 else [0, 0, 0, 1])]
                                 + [round(float(x), 3) for x in (e[8:11] if len(e) >= 11 else [1, 1, 1])])
        print(f'地形：模型 {len(terrain_models)} / 实例 {len(terrain_insts)}')

    veg_models, veg_insts = {}, []
    vp = os.path.join(TOWN, 'valentine_veg_meshes.json')
    vi = os.path.join(TOWN, 'valentine_veg_instances.json')
    if os.path.exists(vp) and os.path.exists(vi):
        VEGM = json.load(open(vp, encoding='utf-8'))
        VEGI = json.load(open(vi, encoding='utf-8'))
        used_v = {str(e[0]) for e in VEGI}
        veg_models = pack_simple(VEGM, used_v)
        for e in VEGI:
            k = str(e[0])
            if k not in veg_models:
                continue
            veg_insts.append([k] + [round(float(x), 2) for x in e[1:4]] + [0, 0, 0, 1, 1, 1, 1])
        print(f'树木：模型 {len(veg_models)} / 实例 {len(veg_insts)}')

    # 地面用贴图（走同一套解析）
    for g in ('hea_grass_lush_01_abte', 'nbx_ground_road02_abal', 'nbx_dirt_discolor_02_abal'):
        get_tex(g, None, None)
    tex = {k: v for k, v in tex_cache.items() if v is not None}

    # ---- 高度场地形：**按建筑基座做局部校准场**（消掉"地基悬空/埋进土里"）----
    #   思路：dz(x,y) = z_实体 − z_高度图(该点)，用镇内 2263 个实体在 128² 网格上分箱求均值
    #         + 平滑，再按双线性插值加到每个地形顶点上 ⇒ 地面必然穿过建筑底座。
    import struct as _st
    HM = os.path.join(ROOT, 'export/levels/terrain/data/levels/rdr3/heightmap.dat')
    terr = None
    if os.path.exists(HM):
        d = open(HM, 'rb').read()
        sx, sy = _st.unpack_from('<HH', d, 0x0C)
        mnx, mny, mnz, mxx, mxy, mxz = _st.unpack_from('<6f', d, 0x10)
        doff = len(d) - sx * sy * 2
        h = _st.unpack_from('<%dH' % (sx * sy), d, doff)

        def raw_h(x, y):
            c = int((x - mnx) / (mxx - mnx) * (sx - 1))
            r = int((y - mny) / (mxy - mny) * (sy - 1))
            if 0 <= c < sx and 0 <= r < sy:
                return h[r * sx + c] / 65535.0 * (mxz - mnz) + mnz
            return None

        # 1) 各实体的 dz
        samples = []
        for e in ents:
            z0 = raw_h(e[1], e[2])
            if z0 is not None:
                samples.append((e[1], e[2], e[3] - z0))
        all_dz = sorted(s[2] for s in samples)
        gmed = all_dz[len(all_dz) // 2] if all_dz else 0.0
        print(f'  校准样本 {len(samples)} 个；全图中位 dz={gmed:.2f} m')

        # 2) 128² 网格 + 平滑（只覆盖小镇周边，外面退回全图中位）
        NB, PAD = 128, 120.0
        bx0, by0 = min(xs) - PAD, min(ys) - PAD
        bx1, by1 = max(xs) + PAD, max(ys) + PAD
        acc = [[0.0] * NB for _ in range(NB)]
        cnt = [[0] * NB for _ in range(NB)]
        for x, y, dz in samples:
            if not (bx0 <= x <= bx1 and by0 <= y <= by1):
                continue
            bi = min(NB - 1, int((x - bx0) / (bx1 - bx0) * NB))
            bj = min(NB - 1, int((y - by0) / (by1 - by0) * NB))
            acc[bj][bi] += dz
            cnt[bj][bi] += 1
        grid = [[(acc[j][i] / cnt[j][i]) if cnt[j][i] else None for i in range(NB)] for j in range(NB)]
        for _ in range(3):                       # 3 次 3×3 平滑 + 空格用邻域/中位填充
            ng = [[None] * NB for _ in range(NB)]
            for j in range(NB):
                for i in range(NB):
                    v, n = 0.0, 0
                    for dj in (-1, 0, 1):
                        for di in (-1, 0, 1):
                            jj, ii = j + dj, i + di
                            if 0 <= jj < NB and 0 <= ii < NB and grid[jj][ii] is not None:
                                v += grid[jj][ii]
                                n += 1
                    ng[j][i] = (v / n) if n else (grid[j][i] if grid[j][i] is not None else gmed)
            grid = ng

        def corr(x, y):
            if not (bx0 <= x <= bx1 and by0 <= y <= by1):
                return gmed
            fx = (x - bx0) / (bx1 - bx0) * (NB - 1)
            fy = (y - by0) / (by1 - by0) * (NB - 1)
            i0, j0 = int(fx), int(fy)
            i1, j1 = min(NB - 1, i0 + 1), min(NB - 1, j0 + 1)
            tx, ty = fx - i0, fy - j0
            a = grid[j0][i0] * (1 - tx) + grid[j0][i1] * tx
            b = grid[j1][i0] * (1 - tx) + grid[j1][i1] * tx
            return a * (1 - ty) + b * ty

        # 3) 512² 输出（**已校正**的高度，u16 归一）
        N = 512
        vals = []
        step = sx // N
        for r in range(N):
            yy = mny + (r / (N - 1)) * (mxy - mny)
            for c in range(N):
                xx = mnx + (c / (N - 1)) * (mxx - mnx)
                z0 = raw_h(xx, yy)
                vals.append((z0 if z0 is not None else mnz) + corr(xx, yy))
        vmin, vmax = min(vals), max(vals)
        rng = (vmax - vmin) or 1.0
        ds = bytearray()
        for v in vals:
            ds += _st.pack('<H', max(0, min(65535, int((v - vmin) / rng * 65535))))
        terr = dict(b64=base64.b64encode(bytes(ds)).decode(), N=N,
                    x0=round(mnx, 1), y0=round(mny, 1), x1=round(mxx, 1), y1=round(mxy, 1),
                    zmin=round(vmin, 2), zmax=round(vmax, 2), off=0.0)
        print(f'高度场（局部校准场）512² 导出；高度范围 {vmin:.1f}~{vmax:.1f}')

    json.dump(dict(terr=terr, tex=tex, tex_names=tex_names, models=models, insts=insts,
                   terrain_models=terrain_models, terrain_insts=terrain_insts,
                   veg_models=veg_models, veg_insts=veg_insts,
                   center=[round(cx, 2), round(cy, 2)]), open(OUT, 'w'), separators=(',', ':'))
    print('wrote', OUT, round(os.path.getsize(OUT) / 1024 / 1024, 2), 'MB')


if __name__ == '__main__':
    main()
