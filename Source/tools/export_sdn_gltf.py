"""圣丹尼斯 · 高保真 glTF 导出（给 Blender 用）。

与 `export_town_l2.py`（给 three.js 的量化包）的区别：
  * **不焊接顶点**（0.25 m 焊接会吃掉 0.02~0.06 m 级装饰细节）
  * **带法线**（R10G10B10A2_UNORM → float3），Blender 里不再是死平面
  * **贴图按原分辨率**（默认 512，可 --maxs 1024/2048），不再压到 96/128
  * **没贴图的模型也导出**（灰模），不再整模型丢弃（旧管线因此丢了 233 个模型 / 236 个实例）
  * 输出 **glTF + .bin + PNG 贴图**，按 160 m 空间分块，Blender 可逐块 Append

坐标系：RDR2 是 Z-up。glTF 是 Y-up ⇒ 顶点保持 RDR2 原值，在 **场景根节点** 上挂
绕 X 轴 −90° 的旋转（子节点仍是 RDR2 的 T/R/S）；Blender 的 glTF 导入器会再转回 Z-up，
所以最终在 Blender 里看到的就是 RDR2 世界坐标（X 东 / Y 北 / Z 上）。

用法：
  uv run python tools/export_sdn_gltf.py --cx 2555 --cy -1151 --r 620 \
      --ydr work/sdn/models --chunk 160 --maxs 512 \
      --out export/levels/world/gltf/sdn
  # 只导几个模型做验证
  uv run python tools/export_sdn_gltf.py --only new_com_04_main1 --out work/sdn/gltf_test
"""
import os
import re
import io
import sys
import glob
import json
import math
import base64
import struct
import argparse
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import rdr2_ydr as Y
import rdr2_vdecl as V
import rdr2_ytd as T
from ytd_to_png import decode_one

ROOT = r'D:/BrainMaker/大镖客2解包分析'

# 只要建筑/道具本体：LOD、阴影、贴花代理、音频、VFX 代理不进 Blender
EXCLUDE = ('_em_slod', '_slod', 'audioproxy', 'vfx_', 'helper', 'lights_holder',
           '_decal', 'decal', '_props_', 'props_debris', 'footboards', '_dcl',
           '_shad', '_em00', 'audioemitter')
VARIANT = re.compile(r'(_em_hd|_det_dec|_detail|_dec|_dc|_dslod|_slod|_glue|_d)$')
ROLE_ALBEDO = ('albedo', 'albedo_layer0', 'albedo_layer1', 'albedo_layer2', 'albedo_layer3',
               'lyr0diffusetex', 'albedo_dirt')
ROLE_NORMAL = ('normal', 'normal_layer0', 'normal2', 'tint_normal')
ROLE_MATERIAL = ('material', 'materialA', 'material2', 'materialA2', 'materialB2')
# RDR2 的 `_nm` 是 DirectX 约定（+Y 朝下），glTF/OpenGL 要求 +Y 朝上 ⇒ 默认翻 G
FLIP_G = True
STRICT_TEX = os.environ.get('RDR2_STRICT_TEX', '1') == '1'   # 默认禁止模糊猜贴图
# 统计（本轮导出里分别挂上多少张法线/ORM）
STAT = Counter()
# ORM 是低频信息（粗糙度/金属度成片变化），256 足够，省一半以上显存
ORM_MAX = 256


def _resize_prop(im, lim):
    """按比例缩到最长边 lim（不拉伸；法线/ORM 用方图拉伸会糊掉细节）"""
    if not lim:
        return im
    w, h = im.size
    if max(w, h) <= lim:
        return im
    k = lim / float(max(w, h))
    return im.resize((max(1, int(round(w * k))), max(1, int(round(h * k)))), Image.LANCZOS)


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
    """去掉 `_ab1_name` 这类"共享前缀"重复段，回到真正的贴图名。"""
    if not n or len(n) < 12:
        return n
    for m in re.finditer(r'_(ab|abal|abte|al|nm|ma|mb|ct|d|s)$', n):
        A = n[:m.end()]
        B = n[m.end():]
        if len(B) < 8:
            continue
        i = A.rfind('_')
        if i <= 0:
            continue
        base = A[:i]
        if len(base) >= 6 and B.lower().startswith(base.lower()):
            return A
    return n


# ------------------------------------------------------------------ 贴图库
# ★ 只允许把「颜色」贴图当 albedo。早期版本模糊匹配会命中 `_nm`（法线图），
#   法线图的平均值 ≈ (128,128,255) ⇒ 整面墙渲染成**紫色**、屋檐变成青蓝色。
ALBEDO_SUF = ('_ab', '_abal', '_abte', '_al', '_abnbx', '+hidr')
NON_ALBEDO = ('_nm', '_ma', '_mb', '_pal', '_mtl', '_s', '_d', '_ct', '_dr',
              '_em', '_msk', '_wt', '_lay', '_mask')


def is_albedo(n):
    n = n.lower()
    if any(n.endswith(s) for s in NON_ALBEDO):
        return False
    # 组合名（`xxx_abnbx_xxx_al`）也算 albedo
    return any(s in n for s in ALBEDO_SUF) or n.endswith('_ab')


class TexLib:
    def __init__(self, dirs, maxs=512):
        self.maxs = maxs
        self.idx = {}
        self.files = []
        for d in dirs:
            self.files += glob.glob(os.path.join(d, '**', '*.ytd'), recursive=True)
        for f in self.files:
            try:
                y = T.Ytd(open(f, 'rb').read())
            except Exception:
                continue
            for t in y.textures():
                if not t['name']:
                    continue
                k = t['name'].lower()
                cur = self.idx.get(k)
                if cur is None or (t['w'] * t['h']) > (cur[1]['w'] * cur[1]['h']):
                    self.idx[k] = (y, t)
        self.cache = {}
        self.written = {}
        self._alb = [k for k in self.idx if is_albedo(k)]

    def _decode(self, y, t):
        blob = y.gfx[t['gfx_off']:t['gfx_off'] + max(4096, t['w'] * t['h'] * 4)]
        return decode_one(blob, t['w'], t['h'], t['fmt'])

    def get(self, name, hint_ytd=None):
        """→ (PIL.Image | None, 说明)"""
        key = (name, hint_ytd)
        if key in self.cache:
            return self.cache[key]
        im = None
        diag = 'miss'
        # 0) 模型自带的 `+hidr.ytd` 优先（同模型的贴图一定在这份字典里）
        if hint_ytd and os.path.exists(hint_ytd):
            try:
                y = T.Ytd(open(hint_ytd, 'rb').read())
                for t in y.textures():
                    if t['name'] and t['name'].lower() == name.lower():
                        im, fmt = self._decode(y, t)
                        diag = 'own:' + str(fmt)
                        break
            except Exception:
                pass
        ent = self.idx.get(clean_name(name).lower()) if im is None else None
        if ent:
            im, fmt = self._decode(*ent)
            diag = 'hit:' + str(fmt)
        if im is None and STRICT_TEX:
            # 2026-10-28：禁用模糊猜测。猜错会把草地配成"烧焦地面"（bra_dr_burn_01），
            # 全城发黑。找不到就留空 → 走中性兜底色，并计入缺图统计。
            pass
        elif im is None:
            stem = name.lower()
            base = re.sub(r'_(ab|abal|abte|al|nm|ma|mb|d|s|ct|dr)$', '', stem)
            # 只从 albedo 候选里挑；优先公共前缀最长的
            cands = [k for k in self._alb if k != stem and k.startswith(base)]
            if not cands:
                toks = [w for w in re.split(r'[^a-z0-9]+', base) if len(w) >= 4]
                best = None
                for k in self._alb:
                    hit = sum(1 for w in toks if w in k)
                    if hit >= max(2, len(toks) - 1):
                        L = 0
                        while L < min(len(k), len(base)) and k[L] == base[L]:
                            L += 1
                        sc = (hit, L, self.idx[k][1]['w'] * self.idx[k][1]['h'])
                        if best is None or sc > best[0]:
                            best = (sc, k)
                if best:
                    cands = [best[1]]
            if cands:
                cands.sort(key=lambda k: (-len(os.path.commonprefix([k, base])),
                                          -self.idx[k][1]['w'] * self.idx[k][1]['h']))
                y, t = self.idx[cands[0]]
                im2, fmt = self._decode(y, t)
                if im2 is not None:
                    im = im2
                    diag = 'fuzzy(' + cands[0] + '):' + str(fmt)
        if im is not None and self.maxs and max(im.size) > self.maxs:
            im = im.resize((self.maxs, self.maxs), Image.LANCZOS)
        self.cache[key] = (im, diag)
        return self.cache[key]

    # ---------------------------------------------------------------- 法线 / ORM
    def _raw(self, name, hint_ytd=None):
        """取原始贴图（不走 albedo 模糊匹配，只做「模型自带 ytd → 全局索引」两级）"""
        ent = None
        if hint_ytd and os.path.exists(hint_ytd):
            try:
                y = T.Ytd(open(hint_ytd, 'rb').read())
                for t in y.textures():
                    if t['name'] and t['name'].lower() == name.lower():
                        return self._decode(y, t)[0]
            except Exception:
                pass
        ent = self.idx.get(clean_name(name).lower()) or self.idx.get(name.lower())
        if ent:
            im, _ = self._decode(*ent)
            return im
        return None

    def get_normal(self, name, hint=None, flip_g=True):
        """`_nm` → glTF 法线图。RDR2 是 DirectX 约定，G 需要翻转成 OpenGL。
        返回 RGB（**不要**把蓝通道当颜色压缩，保持 8bit 即可）"""
        ck = ('n', name, hint, flip_g)
        if ck in self.cache:
            return self.cache[ck]
        im = self._raw(name, hint)
        diag = 'miss'
        out = None
        if im is not None:
            try:
                rgb = im.convert('RGB')
                if flip_g:
                    r, g, b = rgb.split()
                    from PIL import ImageChops
                    rgb = Image.merge('RGB', (r, ImageChops.invert(g), b))
                rgb = _resize_prop(rgb, self.maxs)
                out = rgb
                diag = 'ok'
            except Exception:
                out = None
        self.cache[ck] = (out, diag)
        return self.cache[ck]

    def get_orm(self, name, hint=None):
        """`_ma` → ORM：R=AO(源B) · G=roughness(源G) · B=metallic(源R)。
        语义依据 Sollumz-RDR 的 RDR2 节点图（R→Metallic、G→Roughness、B→AO×BaseColor）"""
        ck = ('orm', name, hint)
        if ck in self.cache:
            return self.cache[ck]
        im = self._raw(name, hint)
        out, diag = None, 'miss'
        if im is not None:
            try:
                rgb = im.convert('RGB')
                rgb = _resize_prop(rgb, min(self.maxs or ORM_MAX, ORM_MAX))
                r, g, b = rgb.split()          # 源：R=metal G=rough B=ao
                out = Image.merge('RGB', (b, g, r))
                diag = 'ok'
            except Exception:
                out = None
        self.cache[ck] = (out, diag)
        return self.cache[ck]


def safe_fn(name):
    return re.sub(r'[^0-9A-Za-z_.+-]', '_', name)[:120]


# ------------------------------------------------------------------ ydr 解析
def read_geom(res, gp, sid):
    go = res.off(gp)
    if go is None:
        return None
    vb = Y.parse_vertex_buffer(res, res.u64(go + 0x08))
    ib = Y.parse_index_buffer(res, res.u64(go + 0x10))
    if not vb:
        return None
    vd = V.parse_vdecl(res, res.u64(vb['off'] + 0x38)) if vb else None
    if not vd:
        return None
    pos = V.read_element(res, vb['data'], vd, 0)
    if not pos:
        return None
    if vd['types'][4]:
        nrm = V.read_element(res, vb['data'], vd, 4)
        nrm = [(((v[0] / 1023.0) * 2 - 1), ((v[1] / 1023.0) * 2 - 1), ((v[2] / 1023.0) * 2 - 1))
               if len(v) >= 3 else (0, 0, 1) for v in nrm]
    else:
        nrm = [(0, 0, 1)] * len(pos)
    uv = V.read_element(res, vb['data'], vd, 28) if vd['types'][28] else []
    if len(uv) < len(pos):
        uv = uv + [[0.0, 0.0]] * (len(pos) - len(uv))
    idx = Y.read_indices(res, ib) if ib else []
    if not idx:
        return None
    return dict(pos=pos, nrm=nrm, uv=uv, idx=idx, vb=vb, vd=vd, sid=sid)


def pick_tex(texs, roles):
    """按 role 优先级取第一张非占位贴图（`blank_nm` / `blank_ma` 是引擎占位，等于"没有"）"""
    for r in roles:
        for t in texs:
            if (t.get('role') or '') != r:
                continue
            n = t.get('name')
            if not n or n.lower().startswith('blank'):
                continue
            return n
    return None


def load_model(path):
    """→ dict(geoms=[...], bbox) 或 None"""
    try:
        res = Y.Res(open(path, 'rb').read())
    except Exception:
        return None
    base = os.path.dirname(path)
    nm = os.path.splitext(os.path.basename(path))[0]
    hint = None
    for cand in (nm + '+hidr.ytd', nm + '.ytd'):
        if os.path.exists(os.path.join(base, cand)):
            hint = os.path.join(base, cand)
            break
    sg = res.u64(0x10)
    shaders = Y.parse_shader_group(res, sg)
    shd = Y.parse_shader_hashes(res, sg)
    geoms = []
    for mo in Y.pointer_list(res, res.u64(0x50)):
        gs = Y.parse_model_geoms(res, mo)
        shmap = Y.parse_model_shaders(res, mo, len(gs))
        for gi, gp in enumerate(gs):
            sid = shmap[gi] if gi < len(shmap) else 0
            g = read_geom(res, gp, sid)
            if not g:
                continue
            texs = shaders[sid] if 0 <= sid < len(shaders) else []
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
            if alb is None:
                # 退到「最大面积的非法线/材质贴图」
                drop = ('normal', 'material', 'materialA', 'materialB', 'palette',
                        'lookup', 'control', 'detail', '')
                cand = [t for t in texs if t.get('name')
                        and not t['name'].lower().startswith('blank')
                        and t.get('role') not in drop]
                if cand:
                    alb = max(cand, key=lambda t: t['w'] * t['h'])
            g['tex'] = alb['name'] if alb else None
            g['shader'] = shd[sid]['name'] if 0 <= sid < len(shd) else None
            # 法线 / 材质图：与 albedo 同一层（albedo2 就取 normal2/material2）
            a2 = (alb or {}).get('role') in ('albedo2', 'albedo_layer1', 'lyr1diffusetex')
            g['ntex'] = pick_tex(texs, ('normal2',) if a2 else ROLE_NORMAL)
            g['mtex'] = pick_tex(texs, ('materialB2', 'materialA2', 'material2') if a2 else ROLE_MATERIAL)
            geoms.append(g)
    if not geoms:
        return None
    # `default` shader + givemechecker = 占位/代理网格（游戏里不渲染），进 Blender 就是一坨白盒子
    if all((g.get('shader') or '').lower() == 'default' for g in geoms):
        return None
    return dict(geoms=geoms, ytd=hint)


# ------------------------------------------------------------------ glTF 写出
def acc_minmax(vals, comps):
    mn = [1e30] * comps
    mx = [-1e30] * comps
    for v in vals:
        for i in range(comps):
            x = v[i]
            if x < mn[i]:
                mn[i] = x
            if x > mx[i]:
                mx[i] = x
    return mn, mx


class BinWriter:
    def __init__(self):
        self.buf = bytearray()

    def add(self, data, align=4):
        while len(self.buf) % align:
            self.buf.append(0)
        off = len(self.buf)
        self.buf += data
        return off


def write_tile(path, models, insts, texlib, tex_uri, q):
    """写一个分块 glTF（models: {name: model}, insts: [[name,x,y,z,qx,qy,qz,qw,sxy,sxy,sz],...]）"""
    bw = BinWriter()
    gl = dict(asset=dict(version='2.0', generator='rdr2_sdn_gltf'),
              scene=0, scenes=[dict(nodes=[])],
              nodes=[], meshes=[], materials=[], accessors=[], bufferViews=[],
              buffers=[dict(byteLength=0, uri=os.path.basename(path).replace('.gltf', '.bin'))])
    # 根节点：Z-up → Y-up
    a = math.radians(-90.0) / 2
    root = dict(name='RDR2_Zup', rotation=[math.sin(a), 0.0, 0.0, math.cos(a)], children=[])
    gl['scenes'][0]['nodes'] = [0]
    gl['nodes'].append(root)

    mat_id = {}

    def reg_image(im, fn):
        """写图并登记 image/texture，返回 texture index。

        `.jpg` 后缀 → JPEG **4:4:4**（subsampling=0，法线的 R/G 通道不能被色度下采样糊掉）。
        法线/ORM 没有 alpha，用 JPEG 比 PNG 小 6~8 倍：圣丹尼斯这类大城贴图能少几百 MB。
        """
        if 'images' not in gl:
            gl['images'] = []
            gl['textures'] = []
            gl['samplers'] = [dict(magFilter=9729, minFilter=9987, wrapS=10497, wrapT=10497)]
        fp = os.path.join(tex_uri, fn)
        if not os.path.exists(fp):
            os.makedirs(tex_uri, exist_ok=True)
            try:
                if fn.lower().endswith('.jpg'):
                    rgb = im.convert('RGB')
                    # 重新落地一份完整像素：源图是 ytd 切片 + split/merge 出来的，
                    # 直接 save 偶发 "broken data stream"，重建后 100% 可靠
                    rgb = Image.frombytes('RGB', rgb.size, rgb.tobytes())
                    rgb.save(fp, 'JPEG', quality=90, subsampling=0, optimize=True)
                else:
                    im.save(fp, 'PNG', optimize=True)
            except Exception as e:
                print('  ! 贴图写出失败 %s: %s' % (fn, e))
                return None
        rel = os.path.relpath(tex_uri, os.path.dirname(path)).replace(os.sep, '/')
        gl['images'].append(dict(uri=(rel + '/' + fn) if rel not in ('.', '') else fn))
        gl['textures'].append(dict(source=len(gl['images']) - 1, sampler=0))
        return len(gl['textures']) - 1

    def material_for(g, hint=None):
        """材质 = baseColor(_ab) + normal(_nm) + metallicRoughness/occlusion(_ma → ORM)。

        ★ 2026-10-25：以前只写 baseColor，`roughness=0.85 / metallic=0` 是**全局常量**，
          也没有法线 ⇒ 圣丹尼斯"塑料廉价"的根因。这里按 RDR2 标准 shader 的真实语义接上：
            `_ma`  R = Metallic   G = Roughness   B = AO   （与 Sollumz-RDR 的 RDR2 节点图一致）
          glTF 的 metallicRoughness 要 **G=roughness / B=metallic**，AO 用 **R** ⇒ 打包成 ORM 图。
        """
        texname = g.get('tex')
        ntex = g.get('ntex')
        mtex = g.get('mtex')
        shader = g.get('shader') or ''
        alpha = ''
        s = shader.lower()
        if 'alpha' in s or 'cutout' in s:
            alpha = 'mask'
        elif 'decal' in s:
            alpha = 'blend'
        key = f'{texname or "__none__"}|{ntex}|{mtex}|{alpha}'
        if key in mat_id:
            return mat_id[key]
        # 没有 _ma 时的兜底：玻璃要亮、其余保持哑光（别再全城一个 0.85）
        rough0, metal0 = 0.85, 0.0
        tl_ = (texname or '').lower() + '|' + s
        if 'glass' in tl_ or 'window' in tl_:
            rough0 = 0.16
        if 'metal' in tl_ or 'iron' in tl_ or 'brass' in tl_:
            metal0 = 0.75
            rough0 = 0.42
        m = dict(name=(texname or 'gray'), doubleSided=True,
                 pbrMetallicRoughness=dict(metallicFactor=metal0, roughnessFactor=rough0))
        if texname and texname.lower() == 'givemechecker':
            m['name'] = 'cable_dark'
            m['pbrMetallicRoughness']['baseColorFactor'] = [0.09, 0.09, 0.1, 1.0]
            m['pbrMetallicRoughness']['roughnessFactor'] = 0.55
            gl['materials'].append(m)
            mat_id[key] = len(gl['materials']) - 1
            return mat_id[key]
        if texname:
            im, _ = texlib.get(texname, hint)
            if im is not None and tex_uri:
                has_a = im.mode in ('RGBA', 'LA') and im.getextrema()[-1][0] < 250
                fn = safe_fn(texname) + '.png'
                fp = os.path.join(tex_uri, fn)
                if not os.path.exists(fp):
                    os.makedirs(tex_uri, exist_ok=True)
                    (im if has_a else im.convert('RGB')).save(fp, 'PNG', optimize=True)
                if 'images' not in gl:
                    gl['images'] = []
                    gl['textures'] = []
                    gl['samplers'] = [dict(magFilter=9729, minFilter=9987, wrapS=10497, wrapT=10497)]
                rel = os.path.relpath(tex_uri, os.path.dirname(path)).replace(os.sep, '/')
                gl['images'].append(dict(uri=(rel + '/' + fn) if rel not in ('.', '') else fn))
                gl['textures'].append(dict(source=len(gl['images']) - 1, sampler=0))
                m['pbrMetallicRoughness']['baseColorTexture'] = dict(index=len(gl['textures']) - 1)
                if alpha and has_a:
                    m['alphaMode'] = 'MASK' if alpha == 'mask' else 'BLEND'
                    if alpha == 'mask':
                        m['alphaCutoff'] = 0.5
            else:
                m['pbrMetallicRoughness']['baseColorFactor'] = [0.62, 0.58, 0.52, 1.0]
        else:
            m['pbrMetallicRoughness']['baseColorFactor'] = [0.62, 0.58, 0.52, 1.0]
        # ---- 法线贴图：没有它，砖缝/石纹/木纹全靠凹凸算出来，表面永远是"平板塑料"
        if ntex and tex_uri:
            nim, _ = texlib.get_normal(ntex, hint, FLIP_G)
            if nim is not None:
                ti_n = reg_image(nim, safe_fn(ntex) + '.jpg')
                if ti_n is not None:
                    m['normalTexture'] = dict(index=ti_n, scale=1.0)
                    STAT['normal'] += 1
        # ---- ORM（AO/roughness/metallic）：让石/木/铁/玻璃各自有真实高光与粗糙度
        if mtex and tex_uri:
            orm, _ = texlib.get_orm(mtex, hint)
            if orm is not None:
                ti = reg_image(orm, safe_fn(mtex) + '_orm.jpg')
                if ti is not None:
                    m['pbrMetallicRoughness']['metallicRoughnessTexture'] = dict(index=ti)
                    m['pbrMetallicRoughness']['metallicFactor'] = 1.0
                    m['pbrMetallicRoughness']['roughnessFactor'] = 1.0
                    m['occlusionTexture'] = dict(index=ti, strength=1.0)
                    STAT['orm'] += 1
        gl['materials'].append(m)
        mat_id[key] = len(gl['materials']) - 1
        return mat_id[key]

    def add_acc(vals, comps, typ, with_minmax=True):
        off = bw.add(struct.pack('<%df' % (len(vals) * comps), *[c for v in vals for c in v]))
        gl['bufferViews'].append(dict(buffer=0, byteOffset=off,
                                      byteLength=len(vals) * comps * 4, target=34962))
        acc = dict(bufferView=len(gl['bufferViews']) - 1, componentType=5126,
                   count=len(vals), type=typ)
        if with_minmax:
            mn, mx = acc_minmax(vals, comps)
            acc['min'] = mn
            acc['max'] = mx
        gl['accessors'].append(acc)
        return len(gl['accessors']) - 1

    for name in sorted({i[0] for i in insts}):
        M = models.get(name)
        if not M:
            continue
        prims = []
        for g in M['geoms']:
            pos = g['pos']
            nrm = g['nrm']
            uv = [(u[0], 1.0 - u[1]) for u in g['uv']]      # OpenGL bottom-left → glTF top-left
            a_pos = add_acc(pos, 3, 'VEC3')
            a_nrm = add_acc(nrm, 3, 'VEC3')
            a_uv = add_acc(uv, 2, 'VEC2', with_minmax=False)
            wide = len(pos) > 65535
            fmt = '<%dI' if wide else '<%dH'
            data = struct.pack(fmt % len(g['idx']), *g['idx'])
            off = bw.add(data, 4)
            gl['bufferViews'].append(dict(buffer=0, byteOffset=off, byteLength=len(data), target=34963))
            gl['accessors'].append(dict(bufferView=len(gl['bufferViews']) - 1,
                                        componentType=5125 if wide else 5123,
                                        count=len(g['idx']), type='SCALAR'))
            pr = dict(attributes=dict(POSITION=a_pos, NORMAL=a_nrm, TEXCOORD_0=a_uv),
                      indices=len(gl['accessors']) - 1,
                      material=material_for(g, g.get('ytd') or M.get('ytd')))
            prims.append(pr)
        gl['meshes'].append(dict(name=name, primitives=prims))
        mesh_id = len(gl['meshes']) - 1
        # 所有实例
        for it in insts:
            if it[0] != name:
                continue
            sxy = it[8] if abs(it[8]) > 1e-6 else 1.0
            sz = it[9] if abs(it[9]) > 1e-6 else 1.0
            node = dict(name=name, mesh=mesh_id, translation=[it[1], it[2], it[3]],
                        rotation=[it[4], it[5], it[6], it[7]],
                        scale=[sxy, sxy, sz])
            gl['nodes'].append(node)
            root['children'].append(len(gl['nodes']) - 1)

    gw = BinWriter()
    gw.buf = bw.buf
    gl['buffers'][0]['byteLength'] = len(gw.buf)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path.replace('.gltf', '.bin'), 'wb') as f:
        f.write(bytes(gw.buf))
    json.dump(gl, open(path, 'w', encoding='utf-8'), separators=(',', ':'))
    return len(gl['nodes']) - 1, len(gl['meshes'])


# ------------------------------------------------------------------ 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cx', type=float, default=2555.0)
    ap.add_argument('--cy', type=float, default=-1151.0)
    ap.add_argument('--r', type=float, default=620.0)
    ap.add_argument('--ydr', default=os.path.join(ROOT, 'work/sdn/models'))
    ap.add_argument('--ytd', default='')
    ap.add_argument('--chunk', type=float, default=160.0)
    ap.add_argument('--maxs', type=int, default=512)
    ap.add_argument('--only', default='', help='逗号分隔的模型名（调试）')
    ap.add_argument('--single', action='store_true', help='不按实例分块，全部塞一个 gltf')
    ap.add_argument('--normal-flip-g', type=int, default=1,
                    help='1=RDR2(DirectX) 法线翻 G 以适配 glTF/OpenGL（默认）；0=原样')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    global FLIP_G
    FLIP_G = bool(a.normal_flip_g)

    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    tex_uri = os.path.join(out, 'textures')
    os.makedirs(tex_uri, exist_ok=True)

    ydr_dirs = [x for x in a.ydr.split(',') if x]
    byname = {}
    nskip = 0
    for d in ydr_dirs:
        for f in glob.glob(os.path.join(d, '**', '*.ydr'), recursive=True):
            n = os.path.splitext(os.path.basename(f))[0]
            low = n.lower()
            # LOD / 代理 / 特效 / 阴影：游戏里是"低模占位"，进 Blender 会糊住整片街区
            if any(x in low for x in ('_slod', 'audioproxy', 'vfx_', 'lights_holder',
                                      '_shad', 'audioemitter', 'helper', '_em00')):
                nskip += 1
                continue
            byname[n] = f
    print(f'剔除 LOD/代理 {nskip} 个')
    print(f'ydr {len(byname)} 个')

    used = set()
    insts = []
    if a.only:
        used = {n.strip() for n in a.only.split(',') if n.strip()}
        for n in used:
            insts.append([n, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1])
    else:
        hash2file = {joaat(n): (n, f) for n, f in byname.items()}
        import ymap_entities
        R2 = a.r * a.r
        seen = set()
        raw = []
        for f in sorted(glob.glob(os.path.join(ROOT, 'export/levels/map_metadata/**/*.ymap'),
                                  recursive=True)):
            try:
                _sig, _sz, es = ymap_entities.extract(f)
            except Exception:
                continue
            for e in es:
                if (e[1] - a.cx) ** 2 + (e[2] - a.cy) ** 2 > R2:
                    continue
                if e[0] not in hash2file:
                    continue
                key = (e[0], round(e[1], 1), round(e[2], 1), round(e[3], 1))
                if key in seen:
                    continue
                seen.add(key)
                raw.append([hash2file[e[0]][0], e[1], e[2], e[3],
                            e[4], e[5], e[6], e[7], e[8], e[8], e[9]])
        # 同位置变体去重
        def base_of(n):
            b = n
            while VARIANT.search(b):
                b = VARIANT.sub('', b)
            return b
        groups = {}
        for it in raw:
            groups.setdefault((round(it[1], 1), round(it[2], 1), round(it[3], 1),
                               base_of(it[0])), []).append(it)
        for g in groups.values():
            g.sort(key=lambda t: (1 if VARIANT.search(t[0]) else 0, len(t[0])))
            insts.append(g[0])
        used = {i[0] for i in insts}
        print(f'实例 {len(insts)} 个（去重前 {len(raw)}），模型 {len(used)} 个')

    # 贴图库
    tex_dirs = [os.path.join(ROOT, 'export/models')]
    for d in (os.path.join(ROOT, 'work/sdn/gtxd/txd'),):
        if os.path.isdir(d):
            tex_dirs.append(d)
    tex_dirs += [x for x in a.ytd.split(',') if x] + ydr_dirs
    tl = TexLib(tex_dirs, a.maxs)
    print(f'贴图库 {len(tl.idx)} 名（{len(tl.files)} 个 ytd）')

    models = {}
    tmiss = Counter()
    for i, n in enumerate(sorted(used)):
        f = byname.get(n)
        if not f:
            continue
        M = load_model(f)
        if not M:
            continue
        models[n] = M
        for g in M['geoms']:
            if g.get('tex'):
                im, diag = tl.get(g['tex'], M.get('ytd'))
                if im is None:
                    tmiss[g['tex']] += 1
        if (i + 1) % 200 == 0:
            print(f'  ... {i+1}/{len(used)}')
    print(f'模型解析成功 {len(models)} / {len(used)}；'
          f'顶点 {sum(len(g["pos"]) for m in models.values() for g in m["geoms"])}，'
          f'三角 {sum(len(g["idx"])//3 for m in models.values() for g in m["geoms"])}')
    print(f'贴图缺失 {len(tmiss)} 个（引用 {sum(tmiss.values())} 次）')
    if tmiss:
        json.dump(tmiss.most_common(), open(os.path.join(out, 'missing_textures.json'), 'w'),
                  ensure_ascii=False, indent=1)

    insts = [i for i in insts if i[0] in models]

    if a.single or a.chunk <= 0:
        p = os.path.join(out, 'sdn_all.gltf')
        n, nm = write_tile(p, models, insts, tl, tex_uri, None)
        print(f'-> {p}  {os.path.getsize(p)/1048576:.1f} MB')
        return

    cs = a.chunk
    buckets = defaultdict(list)
    for it in insts:
        buckets[(int((it[1] - a.cx) // cs), int((it[2] - a.cy) // cs))].append(it)
    tot = 0
    for (k0, k1), its in sorted(buckets.items()):
        p = os.path.join(out, 'tiles', f'c{k0}_{k1}.gltf')
        n, nm = write_tile(p, models, its, tl, tex_uri, None)
        sz = os.path.getsize(p.replace('.gltf', '.bin')) + os.path.getsize(p)
        tot += sz
        print(f'  c{k0}_{k1}: {len(its)} inst / {nm} mesh  {sz/1048576:.1f} MB')
    ntex = len([x for x in os.listdir(tex_uri) if x.endswith('.png')])
    print(f'-> {out}/tiles/  {len(buckets)} 块，合计 {tot/1048576:.1f} MB；贴图 {ntex} 张')
    print(f'材质贴图挂载：法线 {STAT["normal"]} 个材质 · ORM(metallic/roughness/AO) {STAT["orm"]} 个材质')


if __name__ == '__main__':
    main()
