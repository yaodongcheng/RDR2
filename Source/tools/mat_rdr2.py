# -*- coding: utf-8 -*-
"""RDR2 材质 = 漫反射(`_ab`) + 法线(`_nm`) + 材质/高光(`_ma` → ORM)。

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

## 用法（只能在 Blender 里 import）

    import mat_rdr2
    mat = mat_rdr2.get_or_make(ab_tid, nm_tid, ma_tid, texmeta, libdir, cache)
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


def mat_name(ab, nm, ma):
    """材质名：`alb_<albedo>`，有法线/高光时再挂后缀；超长用短哈希保证唯一。"""
    parts = ['alb_' + _slug(ab)]
    if nm:
        parts.append('nm_' + _slug(nm, 18))
    if ma:
        parts.append('ma_' + _slug(ma, 18))
    s = '__'.join(parts)
    if len(s) <= 60:
        return s
    import hashlib
    h = hashlib.md5(('%s|%s|%s' % (ab, nm, ma)).encode('utf-8')).hexdigest()[:10]
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


def make(ab_tid, nm_tid, ma_tid, texmeta, libdir, fallback=(0.30, 0.27, 0.23, 1.0)):
    """照三张图的 id 建一个材质（调用方负责缓存）。"""
    import bpy
    ab = tex_name(texmeta, ab_tid)
    nm = tex_name(texmeta, nm_tid)
    ma = tex_name(texmeta, ma_tid)

    name = mat_name(ab, nm, ma) if ab else (
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
    if ok_ab:
        n = _img_node(m, ab_path, ab, False, (-620, 320))
        nt.links.new(n.outputs['Color'], bsdf.inputs['Base Color'])
        m['albedo'] = ab
    if nm and os.path.exists(nm_path):
        n = _img_node(m, nm_path, nm, True, (-620, 20))
        nmp = nt.nodes.new('ShaderNodeNormalMap')
        nmp.location = (-320, 40)
        nmp.inputs['Strength'].default_value = 1.0
        nt.links.new(n.outputs['Color'], nmp.inputs['Color'])
        if 'Normal' in bsdf.inputs:
            nt.links.new(nmp.outputs['Normal'], bsdf.inputs['Normal'])
        m['normal'] = nm
    if ma and os.path.exists(ma_path):
        n = _img_node(m, ma_path, ma, True, (-620, -280))
        sep, kr, kg, kb = _separate(m, (-340, -280))
        nt.links.new(n.outputs['Color'], sep.inputs['Color'])
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


def get_or_make(ab_tid, nm_tid, ma_tid, texmeta, libdir, cache):
    """带缓存的版本。缓存键 = (albedo, normal, orm) 三个 id。"""
    key = (ab_tid if ab_tid is not None and ab_tid >= 0 else -1,
           nm_tid if nm_tid is not None and nm_tid >= 0 else -1,
           ma_tid if ma_tid is not None and ma_tid >= 0 else -1)
    hit = cache.get(key)
    if hit is not None:
        return hit
    # 无 albedo 且无 nm/ma → 共用同一只暖灰材质
    if key == (-1, -1, -1):
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
    m = make(key[0], key[1], key[2], texmeta, libdir)
    cache[key] = m
    return m
