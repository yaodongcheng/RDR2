# -*- coding: utf-8 -*-
"""RDR2 材质 = 漫反射(`_ab`) + 法线(`_nm`) + 材质/高光(`_ma` → ORM) [+ 第二层 + 控制图]。

## 为什么单独一个模块

`blender_continent._mat_for()`（构建用）和 `relink_materials.make_material()`（给已存盘
blend 重挂用）必须是**同一套**节点图，否则重建和重挂会得到两种材质。
2026-10-30 之前两份都只挂了 albedo → 整个大陆是"平板 + 常量粗糙度 0.85"。

## 通道语义（已定死，别再猜）

| 图 | 通道 | 含义 | 依据 |
|---|---|---|---|
| `_ma` | **R** | Metallic | `docs/世界与地编/RDR2_圣丹尼斯地编破解.md` §5.9.2 |
| `_ma` | **G** | Roughness | 同上 |
| `_ma` | **B** | AO | 同上（Blender 的 Principled 没有 AO 输入，这里不接，避免把颜色乘暗） |

`_nm` 在入池时已经把 **G 通道翻转过**（DirectX→OpenGL，见
`tools/extract_slot_textures.py` 的 `FLIP_G`），所以这里 Normal Map 节点直接用，
**不要再翻一次**（翻了会凹凸反向）。

## 两层材质（`standard_2lyr*` / `standard_dirt`，2026-11-01）

    BaseColor = mix(lyr0, lyr1, w)      w 来自「控制图的一个通道」或「lyr1 的 alpha」

* **方向**：w 越大越靠 **第 1 层**。依据 = `nbx_ground_grass_bay_lsuh_mb` 这种
  "遮罩图直接命名成第 1 层素材"的资产，以及社区实现 Sollumz-RDR
  `shader_materials_RDR.RDR_create_2lyr_shader`（`diff_lyr_mix` 的 Fac 走控制分支、
  Color2 是 `lyr1diffusetex`）。
* **哪个通道**：不写死 R。`extract_slot_textures` 解码时用 `tex_slots.mask_channel()`
  挑方差最大的通道，结果存在 `tex[i]["ch"]`（`-1` = 四通道全平、不能当遮罩）。
  实测依据：专用 `_ct` 是灰度；复用 `_mb` 当控制图时往往只有一个通道在变。
* **`_abal`**：`standard_dirt` 没有控制图，第 1 层的 `_abal` 贴图 **alpha 就是混合权重**
  （实测 `nbx_dirt_moss_02dark_abal` alpha 0~0.89 起伏）。
* 取不到权重（没有控制图、也没有可用的 alpha）→ **保持单层**，老行为不变。

## 用法（只能在 Blender 里 import）

    import mat_rdr2
    mat = mat_rdr2.get_or_make(ab_tid, nm_tid, ma_tid, texmeta, libdir, cache)
    mat = mat_rdr2.get_or_make(ab, nm, ma, texmeta, libdir, cache, lyr=(l1, ctrl, dirt, nm2, ma2))
"""
import os


def _slug(name, limit=58):
    import re
    s = re.sub(r'[^0-9A-Za-z_.-]+', '_', name or '').strip('_')
    return s[:limit] or 'noname'


def tex_name(texmeta, tid):
    if tid is not None and 0 <= tid < len(texmeta):
        return (texmeta[tid].get('n') or '').strip()
    return ''


def _tex_rel(texmeta, tid):
    if tid is not None and 0 <= tid < len(texmeta):
        return texmeta[tid].get('f') or ''
    return ''


def _tex_entry(texmeta, tid):
    if tid is not None and 0 <= tid < len(texmeta):
        return texmeta[tid]
    return {}


# 贴图 → 平均色（给 Solid/Workbench 视图用的「视口显示色」）。按路径缓存，一次构建只解一遍。
_AVG_CACHE = {}


def avg_color(path):
    """贴图平均色 → (r,g,b,1.0)。

    🔴 为什么需要：**Solid / Workbench 视图不看节点树**，只认 `mat.diffuse_color`。
    不设它，所有贴图材质一律显示成 Blender 默认的 0.8 灰白 —— 2026-11-01 用户在
    Solid 视图里看到码头是白的，以为材质没生效（实际切 Material Preview 才是深色木纹）。
    这里把 albedo 缩到 8×8 取均值，Solid 里至少是「木头是木色、石头是灰色」。
    """
    if path in _AVG_CACHE:
        return _AVG_CACHE[path]
    c = (0.30, 0.27, 0.23, 1.0)
    try:
        from PIL import Image
        im = Image.open(path).convert('RGB')
        im.thumbnail((8, 8))
        px = list(im.getdata())
        n = max(1, len(px))
        c = (sum(p[0] for p in px) / n / 255.0,
             sum(p[1] for p in px) / n / 255.0,
             sum(p[2] for p in px) / n / 255.0, 1.0)
    except Exception:
        pass
    _AVG_CACHE[path] = c
    return c


# 贴图的 alpha 用法。按路径缓存（一张图只解一次）。
_ALPHA_CACHE = {}


def alpha_mode(path):
    """→ ''（不用 alpha）/ 'clip'（镂空）/ 'blend'（半透明）。

    🔴 为什么要有这个（2026-11-05 定位）：`make()` 一直只把 albedo 接到 Base Color，
    **alpha 从来没接进 BSDF** —— 于是所有带透明通道的贴图（招牌刷漆、贴花、植被卡片、
    栅栏网）都被当实心画上去。实测 `val_sn_ext_05a_ab`：alpha==0 占 68.2%、<128 占 80.6%，
    透明区 RGB 是深红棕 (106,72,73) ⇒ 游戏里"字直接刷在粉墙上"，我们渲染成一块深红实心板。

    判据（保守，宁可少开不可乱开）：
      · 才算"有 alpha"：alpha < 0.5 的像素占比 ≥ 2%，且最小 alpha < 0.5；
      · 中间值（0.15~0.85）占比 < 5% ⇒ 二值 = 'clip'（植被/栅栏/铁艺，便宜、无排序问题）；
      · 否则 'blend'（半透明刷漆/玻璃/贴花，必须真混合）。
    """
    if path in _ALPHA_CACHE:
        return _ALPHA_CACHE[path]
    mode = ''
    try:
        from PIL import Image
        import numpy as np
        im = Image.open(path)
        if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
            a = np.asarray(im.convert('RGBA'))[..., 3].astype(np.float32) / 255.0
            if a.size and a.min() < 0.5 and float((a < 0.5).mean()) >= 0.02:
                mid = float(((a > 0.15) & (a < 0.85)).mean())
                mode = 'clip' if mid < 0.05 else 'blend'
    except Exception:
        mode = ''
    _ALPHA_CACHE[path] = mode
    return mode


def mat_name(ab, nm, ma, l1=None, ctrl=None):
    """材质名：`alb_<albedo>`，有法线/高光时再挂后缀；超长用短哈希保证唯一。"""
    parts = ['alb_' + _slug(ab)]
    if nm:
        parts.append('nm_' + _slug(nm, 18))
    if ma:
        parts.append('ma_' + _slug(ma, 18))
    if l1:
        parts.append('l1_' + _slug(l1, 18))
    if ctrl:
        parts.append('ct_' + _slug(ctrl, 16))
    s = '__'.join(parts)
    if len(s) <= 60:
        return s
    import hashlib
    h = hashlib.md5(('%s|%s|%s|%s|%s' % (ab, nm, ma, l1, ctrl)).encode('utf-8')).hexdigest()[:10]
    return 'alb_%s__%s' % (_slug(ab, 26), h)


def _bsdf(mat):
    for n in mat.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            return n
    return mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')


def _img_node(mat, path, label, noncolor, loc):
    """建/取图像节点。同名同路径的图片用 `check_existing` 复用（不重复解码）。"""
    import bpy
    nt = mat.node_tree
    node = nt.nodes.new('ShaderNodeTexImage')
    node.location = loc
    img = bpy.data.images.load(path, check_existing=True)
    try:
        img.colorspace_settings.name = 'Non-Color' if noncolor else 'sRGB'
    except Exception:
        pass
    node.image = img
    node.label = label
    return node


def _separate(mat, loc):
    nt = mat.node_tree
    try:
        return nt.nodes.new('ShaderNodeSeparateColor'), 'Red', 'Green', 'Blue'
    except Exception:
        return nt.nodes.new('ShaderNodeSeparateRGB'), 'R', 'G', 'B'


# 新版 `ShaderNodeMix`（3.4+）的多态 socket 下标：0=Fac(float) 6=A(color) 7=B(color) → 输出 2
# 老版 `ShaderNodeMixRGB`：Fac / Color1 / Color2 → 输出 Color。
# 两个都试一遍 —— Blender 5.x 上 `ShaderNodeMixRGB` 是遗留节点，随时可能消失。
def _mix_node(nt, data_type, blend, loc):
    """→ dict(node, fac, a, b, out)；`data_type` = 'RGBA' | 'FLOAT' | 'VECTOR'。"""
    try:
        n = nt.nodes.new('ShaderNodeMix')
        n.data_type = data_type
        n.blend_type = blend
        n.location = loc
        if data_type == 'RGBA':
            return dict(node=n, fac=n.inputs[0], a=n.inputs[6], b=n.inputs[7], out=n.outputs[2])
        if data_type == 'VECTOR':
            return dict(node=n, fac=n.inputs[0], a=n.inputs[4], b=n.inputs[5], out=n.outputs[1])
        return dict(node=n, fac=n.inputs[0], a=n.inputs[2], b=n.inputs[3], out=n.outputs[0])
    except Exception:
        n = nt.nodes.new('ShaderNodeMixRGB')
        n.blend_type = blend
        n.location = loc
        return dict(node=n, fac=n.inputs['Fac'], a=n.inputs['Color1'],
                    b=n.inputs['Color2'], out=n.outputs['Color'])


def _layer_weight(m, texmeta, libdir, l1_tid, ctrl_tid, loc):
    """两层混合权重 → (socket|None, 说明)。

    优先「控制图里方差最大的通道」；没有控制图就退到「第 1 层自己的 alpha」
    （`_abal` = albedo+alpha，alpha 就是混合权重）。都没有就返回 None（保持单层）。
    """
    nt = m.node_tree
    # 1) 控制图
    if ctrl_tid is not None and ctrl_tid >= 0:
        e = _tex_entry(texmeta, ctrl_tid)
        ch = e.get('ch', -1)
        rel = e.get('f') or ''
        path = os.path.join(libdir, rel) if rel else ''
        if path and os.path.exists(path) and ch is not None and ch >= 0:
            n = _img_node(m, path, (e.get('n') or '') + ' [ctrl]', True, loc)
            if ch >= 3:
                return n.outputs['Alpha'], 'ctrl.alpha:' + (e.get('n') or '')
            sep, kr, kg, kb = _separate(m, (loc[0] + 180, loc[1]))
            nt.links.new(n.outputs['Color'], sep.inputs['Color'])
            return sep.outputs[[kr, kg, kb][ch]], 'ctrl.%s:%s' % ('RGB'[ch], e.get('n') or '')
    # 2) 第 1 层自己的 alpha（`_abal`）
    if l1_tid is not None and l1_tid >= 0:
        e = _tex_entry(texmeta, l1_tid)
        rel = e.get('f') or ''
        path = os.path.join(libdir, rel) if rel else ''
        if e.get('ch', -1) == 3 and path and os.path.exists(path):
            n = _img_node(m, path, (e.get('n') or '') + ' [l1.mask]', False, loc)
            return n.outputs['Alpha'], 'l1.alpha:' + (e.get('n') or '')
    return None, ''


def make(ab_tid, nm_tid, ma_tid, texmeta, libdir, fallback=(0.30, 0.27, 0.23, 1.0),
         lyr=None, two_layer=True, alpha=True):
    """照三张图（+ 可选的第二层）建一个材质（调用方负责缓存）。

    `lyr` = (l1_tid, ctrl_tid, dirt_tid, nm2_tid, ma2_tid)；None/全 -1 = 单层，行为与旧版一致。
    """
    import bpy
    ab = tex_name(texmeta, ab_tid)
    nm = tex_name(texmeta, nm_tid)
    ma = tex_name(texmeta, ma_tid)
    l1_tid, ctrl_tid, _dirt_tid, nm2_tid, ma2_tid = (list(lyr) + [-1] * 5)[:5] if lyr else (-1,) * 5
    l1 = tex_name(texmeta, l1_tid)
    ctrl = tex_name(texmeta, ctrl_tid)
    nm2 = tex_name(texmeta, nm2_tid)
    ma2 = tex_name(texmeta, ma2_tid)

    name = mat_name(ab, nm, ma, l1 if two_layer else None, ctrl if two_layer else None) if ab else (
        'nonalbedo_' + '_'.join(x for x in (
            ('nm_' + _slug(nm, 18)) if nm else '',
            ('ma_' + _slug(ma, 18)) if ma else '') if x) or 'nonalbedo_warmgray')
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = _bsdf(m)
    nt = m.node_tree

    ab_path = os.path.join(libdir, _tex_rel(texmeta, ab_tid)) if ab else ''
    nm_path = os.path.join(libdir, _tex_rel(texmeta, nm_tid)) if nm else ''
    ma_path = os.path.join(libdir, _tex_rel(texmeta, ma_tid)) if ma else ''

    ok_ab = bool(ab_path) and os.path.exists(ab_path)
    has_rough = False
    # ---- 两层混合权重（先算，下面颜色/法线/ORM 共用同一条 Fac）
    weight, how = (None, '')
    if two_layer and ok_ab and l1:
        p1 = os.path.join(libdir, _tex_rel(texmeta, l1_tid))
        if os.path.exists(p1):
            weight, how = _layer_weight(m, texmeta, libdir, l1_tid, ctrl_tid, (-980, 380))

    if ok_ab:
        n0 = _img_node(m, ab_path, ab, False, (-620, 320))
        col = n0.outputs['Color']
        if weight is not None:
            n1 = _img_node(m, os.path.join(libdir, _tex_rel(texmeta, l1_tid)),
                           l1, False, (-620, 100))
            mx = _mix_node(nt, 'RGBA', 'MIX', (-360, 320))
            nt.links.new(weight, mx['fac'])
            nt.links.new(col, mx['a'])
            nt.links.new(n1.outputs['Color'], mx['b'])
            col = mx['out']
            m['layer1'] = l1
            m['layer_mix'] = how
        nt.links.new(col, bsdf.inputs['Base Color'])
        m['albedo'] = ab
        # ---- alpha（2026-11-05）：把 albedo 的 alpha 接进 BSDF，否则透明区被当实心画。
        if alpha:
            am = alpha_mode(ab_path)
            if am:
                nt.links.new(n0.outputs['Alpha'], bsdf.inputs['Alpha'])
                blended = (am == 'blend')
                # Blender 4.2+ 用 surface_render_method；老版本用 blend_method。两个都试。
                try:
                    m.surface_render_method = 'BLENDED' if blended else 'DITHERED'
                except Exception:
                    try:
                        m.blend_method = 'BLEND' if blended else 'CLIP'
                    except Exception:
                        pass
                try:
                    m.alpha_threshold = 0.5
                except Exception:
                    pass
                if blended:
                    try:
                        m.show_transparent_back = False
                    except Exception:
                        pass
                m['alpha_mode'] = am
        # Solid / Workbench 视图色（不设的话全是默认灰白，容易被误判成"材质没生效"）
        if weight is not None and l1:
            p1 = os.path.join(libdir, _tex_rel(texmeta, l1_tid))
            if os.path.exists(p1):
                c0, c1 = avg_color(ab_path), avg_color(p1)
                m.diffuse_color = tuple(0.5 * (c0[i] + c1[i]) for i in range(3)) + (1.0,)
            else:
                m.diffuse_color = avg_color(ab_path)
        else:
            m.diffuse_color = avg_color(ab_path)
    # ---- 法线（两层的法线按同一 Fac 混）
    if nm and os.path.exists(nm_path):
        n = _img_node(m, nm_path, nm, True, (-620, 20))
        nmp = nt.nodes.new('ShaderNodeNormalMap')
        nmp.location = (-320, 40)
        nmp.inputs['Strength'].default_value = 1.0
        nt.links.new(n.outputs['Color'], nmp.inputs['Color'])
        nrm_out = nmp.outputs['Normal']
        nm2_path = os.path.join(libdir, _tex_rel(texmeta, nm2_tid)) if nm2 else ''
        if weight is not None and nm2_path and os.path.exists(nm2_path):
            n2 = _img_node(m, nm2_path, nm2, True, (-620, -120))
            nmp2 = nt.nodes.new('ShaderNodeNormalMap')
            nmp2.location = (-320, -120)
            nmp2.inputs['Strength'].default_value = 1.0
            nt.links.new(n2.outputs['Color'], nmp2.inputs['Color'])
            mv = _mix_node(nt, 'VECTOR', 'MIX', (-150, 40))
            nt.links.new(weight, mv['fac'])
            nt.links.new(nrm_out, mv['a'])
            nt.links.new(nmp2.outputs['Normal'], mv['b'])
            nrm_out = mv['out']
            m['normal2'] = nm2
        if 'Normal' in bsdf.inputs:
            nt.links.new(nrm_out, bsdf.inputs['Normal'])
        m['normal'] = nm
    # ---- ORM（`_ma` 的 R=Metallic G=Roughness；两层同样按 Fac 混）
    if ma and os.path.exists(ma_path):
        n = _img_node(m, ma_path, ma, True, (-620, -280))
        orm_out = n.outputs['Color']
        ma2_path = os.path.join(libdir, _tex_rel(texmeta, ma2_tid)) if ma2 else ''
        if weight is not None and ma2_path and os.path.exists(ma2_path):
            n2 = _img_node(m, ma2_path, ma2, True, (-620, -420))
            mo = _mix_node(nt, 'RGBA', 'MIX', (-440, -300))
            nt.links.new(weight, mo['fac'])
            nt.links.new(orm_out, mo['a'])
            nt.links.new(n2.outputs['Color'], mo['b'])
            orm_out = mo['out']
            m['orm2'] = ma2
        sep, kr, kg, kb = _separate(m, (-340, -280))
        nt.links.new(orm_out, sep.inputs['Color'])
        # ★ 这里判的是 **BSDF 的 socket 名**（Metallic/Roughness），
        #   不是分离节点的通道名（Red/Green）—— 2026-10-30 写错过一次，
        #   `'Red' in bsdf.inputs` 恒为 False，结果 ORM 只连了 Color 输入、没接到 BSDF。
        if 'Metallic' in bsdf.inputs:
            nt.links.new(sep.outputs[kr], bsdf.inputs['Metallic'])
        if 'Roughness' in bsdf.inputs:
            nt.links.new(sep.outputs[kg], bsdf.inputs['Roughness'])
            has_rough = True
        m['orm'] = ma

    if not ok_ab:
        # 没有 albedo：给中性暖灰 + 视口色（否则 Workbench 里是默认 0.8 灰白 → 满屏白块）
        bsdf.inputs['Base Color'].default_value = fallback
        m.diffuse_color = fallback
    if not has_rough:
        bsdf.inputs['Roughness'].default_value = 0.85
    m.roughness = 0.85
    return m


def get_or_make(ab_tid, nm_tid, ma_tid, texmeta, libdir, cache, lyr=None, two_layer=True,
                alpha=True):
    """带缓存的版本。缓存键 = (albedo, normal, orm) [+ 第二层五个 id] [+ alpha 开关]。"""
    def _i(x):
        return x if x is not None and x >= 0 else -1
    key = (_i(ab_tid), _i(nm_tid), _i(ma_tid))
    if two_layer and lyr:
        key = key + tuple(_i(x) for x in (list(lyr) + [-1] * 5)[:5])
    key = key + (bool(alpha),)
    hit = cache.get(key)
    if hit is not None:
        return hit
    # 无 albedo 且无 nm/ma → 共用同一只暖灰材质
    if key[:3] == (-1, -1, -1):
        import bpy
        m = bpy.data.materials.get('nonalbedo_warmgray')
        if m is None:
            m = bpy.data.materials.new('nonalbedo_warmgray')
            m.use_nodes = True
            b = _bsdf(m)
            b.inputs['Base Color'].default_value = (0.30, 0.27, 0.23, 1.0)
            b.inputs['Roughness'].default_value = 0.85
            m.diffuse_color = (0.30, 0.27, 0.23, 1.0)
            m.roughness = 0.85
        cache[key] = m
        return m
    m = make(key[0], key[1], key[2], texmeta, libdir, lyr=(lyr or None), two_layer=two_layer,
             alpha=alpha)
    cache[key] = m
    return m
