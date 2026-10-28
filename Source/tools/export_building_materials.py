"""按**修正后的材质管线**导出 Valentine 建筑：真 UV + shader slot 语义材质。

与旧 `export_building_meshes.py` 的区别（这就是"贴图是错的"的修复）：
  * **真 UV**：从 `VertexDeclarationG9` 读 `TEXCOORD0/1`（旧版用 box mapping 现算）；
  * **按 slot 语义取材质**：`rdr2_shader_params` 给出 `diffusetex / lyr0diffusetex / tintpalettetex …`
    （旧版按文件名后缀猜，且 shader 纹理数组步长写错 ⇒ 整体错位）；
  * **逐几何体带全套材质**：albedo / albedo2 / mask / normal / palette；
  * **大小写不敏感**解析贴图名（RDR2 名字是哈希，实测 `beamBare` vs `beambare` 大小写不一致）。

贴图三级解析：① `.ydr` 内嵌（`dptr != 0`，调色板就在这）② 全量 `.ytd` 索引（含
`gtxd_valentine`）③ 同族最近邻回退（标记 `fb`）。

输出：`export/levels/town/materials_demo.json`
"""
import os
import sys
import glob
import json
import base64
import io
import re
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import rdr2_ydr as Y
import rdr2_vdecl as V
import rdr2_ytd as T
from ytd_to_png import decode_one

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TOWN = os.path.join(ROOT, 'export/levels/town')
OUT = os.path.join(TOWN, 'materials_demo.json')
GTXD = r'C:/Users/yaodongcheng/AppData/Local/Temp/codemaker/gtxd/out'
MAXS = 128

WANT = ['val_03_saloon_ext', 'val_bank', 'val_01_trainstn_ext', 'val_03_jail_ext']
_KNOWN_FMT = {0x46,0x47,0x48,0x49,0x4A,0x4B,0x4C,0x4D,0x4E,0x4F,0x50,0x51,0x52,0x53,0x54,0x57,0x5A,0x5B,0x1B,0x1C,0x1D,0x5E,0x5F,0x60,0x61,0x62,0x63}
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


def vec_of(geom_name):
    """role -> 该几何体的贴图名"""
    m = {}
    for t in geom_name:
        r = t.get('role') or ''
        if not t['name'] or t['name'].lower().startswith('blank'):
            continue
        if r in ROLE_ALBEDO and 'a' not in m:
            m['a'] = t['name']
        elif r == 'albedo2' and 'b' not in m:
            m['b'] = t['name']
        elif r in ('materialA', 'control', 'material', 'materialB') and 'm' not in m:
            m['m'] = t['name']
        elif r in ('normal', 'normal_layer0') and 'n' not in m:
            m['n'] = t['name']
        elif r == 'palette' and 'p' not in m:
            m['p'] = t['name']
    return m


def main():
    # ---------- 1) 建贴图索引（小写键；含 gtxd）----------
    index = {}
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
            k = clean_name(t['name']).lower()
            cur = index.get(k)
            # 同名多份：取面积最大的（一般是 +hi / +hidr 的 HD 版）
            if cur is None or (t['w'] * t['h']) > (cur[1]['w'] * cur[1]['h']):
                index[k] = (y, t)
    print(f'贴图索引 {len(index)} 个名字（{len(files)} 个 .ytd）')

    def enc(im):
        im = im.convert('RGB').resize((MAXS, MAXS))
        b = io.BytesIO()
        im.save(b, 'PNG', optimize=True)
        return base64.b64encode(b.getvalue()).decode()

    tex_cache = {}

    def get_tex(name, res=None, desc=None):
        if name in tex_cache:
            return tex_cache[name]
        im = None
        fb = None
        # ① 全量 .ytd 索引（**优先**：名字→条目是权威配对；大小写不敏感）
        ent = index.get(clean_name(name).lower())
        if ent:
            y, t = ent
            blob = y.gfx[t['gfx_off']:t['gfx_off'] + max(4096, t['w'] * t['h'] * 4)]
            im, _ = decode_one(blob, t['w'], t['h'], t['fmt'])
        # ② .ydr 内嵌（调色板只在这里）：需要"描述符自洽"才信
        #    ⚠️ 这是之前"马赛克"的根因：shader 的 grcTextureRef 只有 name；
        #    若把 ref 结构里 +0x18 的 pad 当 W/H，偶尔会"看起来合法"⇒ 从 .ydr 里
        #    读到无关字节 ⇒ 彩虹噪声。故加 blockSize↔面积 的交叉校验。
        #    ★ 只对 `*_pal`（调色板，确实只存在于 .ydr 内嵌）走这条路；
        #    其他名字一律以 .ytd 索引为准 —— shader ref 的 W/H 是 pad，读它=抽奖。
        if im is None and desc and desc.get('dptr') and res is not None and name.lower().endswith('_pal'):
            w, h = desc.get('w') or 0, desc.get('h') or 0
            code = ((desc.get('fmt') or 0) >> 24) & 0xFF
            if (4 <= w <= 8192 and 4 <= h <= 8192 and (w & (w - 1)) == 0 and (h & (h - 1)) == 0
                    and code in _KNOWN_FMT):
                from ytd_to_png import FMT, BC_EXTRA, RAW_FMT
                blk = 8 if code in (0x46, 0x47, 0x48, 0x4F, 0x50, 0x51) else 16
                if code in RAW_FMT:
                    blk = 4
                mip0 = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * blk
                bs = desc.get('size') or 0
                # m_blockSize ≈ mip 链字节数/16（项目实测）；允许 0.25x~4x 偏差
                ok = (bs == 0) or (0.25 * mip0 / 16.0 <= bs <= 4.0 * mip0 / 16.0)
                if ok:
                    try:
                        blob = res.blob(desc['dptr'], max(4096, w * h * 4))
                        im, _ = decode_one(blob, w, h, desc['fmt'])
                    except Exception:
                        im = None
                if im is not None:
                    fb = None
        # ③ 同族回退：先按"去后缀的基名"找同族，再退化到前缀
        if im is None:
            stem = name.lower()
            base = re.sub(r'_(ab|abal|al|abte|nm|ma|mb|d|s|ct|dr)$', '', stem)
            cands = [k for k in index if k.startswith(base) and k != stem]
            if not cands:
                cands = [k for k in index if k.startswith(base[:max(10, len(base) - 2)])]
            if not cands:
                cands = [k for k in index if k.startswith(stem[:max(6, len(stem) - 3)])]
            if not cands:
                # ④ 关键词回退：同后缀 + 共享词元最多（例 rho_be_paintwood_ab -> *woodpaintedoverlap*_ab）
                suf_m = re.search(r'_(ab|abal|al|abte|nm|ma|mb|d|s|ct|dr)$', stem)
                suf = suf_m.group(0) if suf_m else ''
                toks = [w for w in re.split(r'[^a-z]+', base) if len(w) >= 4]
                # 词干匹配（paintwood -> paintedoverlap）：取每个词元前 5~6 字符
                stems = [w[:6] for w in toks if len(w) >= 6]
                toks = toks + stems
                best = None
                for k in index:
                    sc = sum(1 for w in toks if w in k)
                    if sc < 1:
                        continue
                    sc -= 0 if (suf and k.endswith(suf)) else 0.4   # 同后缀略加分
                    if best is None or sc > best[0]:
                        best = (sc, k)
                if best:
                    cands = [best[1]]
            if cands:
                pick = sorted(cands)[0]
                y, t = index[pick]
                blob = y.gfx[t['gfx_off']:t['gfx_off'] + max(4096, t['w'] * t['h'] * 4)]
                im, _ = decode_one(blob, t['w'], t['h'], t['fmt'])
                fb = t['name']
        if im is None:
            tex_cache[name] = None
            return None
        d = dict(b64=enc(im), src=('inline' if (name.lower().endswith('_pal') and name.lower() not in index) else ('fb' if fb else 'ytd')))
        if fb:
            d['fb'] = fb
        tex_cache[name] = d
        return d

    # ---------- 2) 导出建筑 ----------
    byname = {os.path.splitext(os.path.basename(f))[0]: f
              for f in glob.glob(os.path.join(ROOT, 'export/models/buildings_jklm/**/*.ydr'), recursive=True)}
    out = {}
    for w in WANT:
        f = byname.get(w)
        if not f:
            print('  跳过（无 ydr）', w)
            continue
        res = Y.Res(open(f, 'rb').read())
        info, ms = Y.extract_at(res, 0, 'high')
        # ★ 按几何体自己的 shaderID 取材质（extract_at 下标会错位）
        shaders = Y.parse_shader_group(res, info['shader_group'])
        shd_all = Y.parse_shader_hashes(res, info['shader_group'])
        glist = []
        for mo in Y.pointer_list(res, res.u64(0x50)):
            gs = Y.parse_model_geoms(res, mo)
            shmap = Y.parse_model_shaders(res, mo, len(gs))
            for gi, gp in enumerate(gs):
                glist.append((gp, shmap[gi] if gi < len(shmap) else 0))
        P, UV, COL, IDX, GRP = [], [], [], [], []
        base = 0
        for n, (gp, sid) in enumerate(glist):
            go = res.off(gp)
            vb = Y.parse_vertex_buffer(res, res.u64(go + 0x08))
            ib = Y.parse_index_buffer(res, res.u64(go + 0x10))
            vd = V.parse_vdecl(res, res.u64(vb['off'] + 0x38)) if vb else None
            if not vd:
                continue
            texs = shaders[sid] if 0 <= sid < len(shaders) else []
            m = dict(shader=(shd_all[sid]['name'] if 0 <= sid < len(shd_all) else None),
                     shader_id=sid, texs_detail=texs)
            pos = V.read_element(res, vb['data'], vd, 0)
            if not pos:
                continue
            uv0 = V.read_element(res, vb['data'], vd, 28)
            if len(uv0) < len(pos):
                uv0 = (uv0 + [[0, 0]] * (len(pos) - len(uv0)))
            uv1 = V.read_element(res, vb['data'], vd, 29)
            if len(uv1) < len(pos):
                uv1 = uv0
            ci = 24 if (len(vd['types']) > 24 and vd['types'][24]) else 25
            col = (V.read_element(res, vb['data'], vd, ci)
                   if ci < 52 and vd['types'][ci] else None)
            if not col or len(col) < len(pos):
                col = [[255, 255, 255, 255]] * len(pos)
            idx = Y.read_indices(res, ib) if ib else []
            mat = vec_of(m['texs_detail'])
            mats = {}
            for k, nm in mat.items():
                d = get_tex(nm, res, next((t for t in m['texs_detail'] if t['name'] == nm), None))
                mats[k] = (dict(name=nm, **d) if d else dict(name=nm, missing=True))
            start = len(IDX)
            IDX.extend([i + base for i in idx])
            base += len(pos)
            for i in range(len(pos)):
                P.extend([round(pos[i][0], 3), round(pos[i][1], 3), round(pos[i][2], 3)])

                def pv(a, k):
                    v = a[k] if k < len(a) else None
                    if not v:
                        return (0.0, 0.0)
                    return (float(v[0]) if len(v) > 0 else 0.0,
                            float(v[1]) if len(v) > 1 else 0.0)

                u0 = pv(uv0, i)
                u1 = pv(uv1, i)
                UV.extend([round(u0[0], 3), round(u0[1], 3), round(u1[0], 3), round(u1[1], 3)])
                c = col[i] if i < len(col) else (255, 255, 255, 255)
                COL.extend([int(c[0]), int(c[1]), int(c[2]), int(c[3] if len(c) > 3 else 255)])
            GRP.append(dict(start=start, count=len(idx), shader=m['shader'], sid=m['shader_id'],
                            mat=mats,
                            sem=''.join(V.SEM_LETTER.get(i, '?') for i, *_ in V.elements(vd))))
        out[w] = dict(name=w, bbox=[info['bbox_min'], info['bbox_max']],
                      p=P, uv=UV, col=COL, i=IDX, vc=base, tc=len(IDX) // 3, g=GRP)
        print(f'  {w:<24} geoms={len(GRP)} verts={base} tris={len(IDX)//3}')

    json.dump(dict(tex=tex_cache, buildings=out), open(OUT, 'w'), separators=(',', ':'))
    print('wrote', OUT, round(os.path.getsize(OUT) / 1024 / 1024, 2), 'MB')
    miss = sum(1 for v in tex_cache.values() if v is None)
    print(f'贴图：{len(tex_cache)} 张（缺失 {miss}），回退 {sum(1 for v in tex_cache.values() if v and v.get("fb"))} 张')


if __name__ == '__main__':
    main()
