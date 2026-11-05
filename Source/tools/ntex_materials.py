# -*- coding: utf-8 -*-
"""通用材质族（Blender 侧）：给无贴图模型按类别贴一张**真实库贴图**。

- 木/金属/布/石/皮革/绳/纸/陶/食物/植被：从 `index.json['tex']` 里按正则挑一张代表贴图，
  用 **Box 投影**（Object 坐标）铺开，避免依赖模型 UV 的缩放；
- 玻璃/水：纯色 + 低粗糙度；
- 取不到贴图时退回纯色。

材质按类别缓存，全场景只有 ~12 种，内存开销可忽略。
"""
import os
import re

import bpy

_CACHE = {}
_TEX_CACHE = {}


def _pick_texture(pattern, texmeta, libdir):
    """在库贴图里找第一张名字匹配 pattern 且文件存在的。"""
    if not pattern:
        return None
    key = (pattern, id(texmeta), libdir)
    if key in _TEX_CACHE:
        return _TEX_CACHE[key]
    rx = re.compile(pattern)
    for t in texmeta or []:
        n = t.get('n') or ''
        if not rx.search(n):
            continue
        p = os.path.join(libdir, t.get('f') or '')
        if os.path.exists(p):
            _TEX_CACHE[key] = p
            return p
    _TEX_CACHE[key] = None
    return None


def _bsdf(m):
    for n in m.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            return n
    return m.node_tree.nodes.new('ShaderNodeBsdfPrincipled')


def get_material(key, color, metallic, roughness, scale, tex_pattern, libdir, texmeta):
    """按类别建/取通用材质。"""
    name = 'ntex_' + key
    m = _CACHE.get(name) or bpy.data.materials.get(name)
    if m is not None:
        _CACHE[name] = m
        return m

    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = _bsdf(m)
    b.inputs['Base Color'].default_value = color
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Roughness'].default_value = roughness
    m.diffuse_color = color
    m.metallic = metallic
    m.roughness = roughness

    tex_path = _pick_texture(tex_pattern, texmeta, libdir)
    if tex_path:
        tc = nt.nodes.new('ShaderNodeTexCoord')
        mp = nt.nodes.new('ShaderNodeMapping')
        # Mapping.Scale 是「坐标乘数」：每 scale 米重复一次 → 乘 1/scale
        inv = 1.0 / max(0.05, float(scale))
        mp.inputs['Scale'].default_value = (inv, inv, inv)
        nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
        img = bpy.data.images.load(tex_path, check_existing=True)
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = img
        t.projection = 'BOX'
        t.projection_blend = 0.3
        try:
            t.extension = 'REPEAT'
        except Exception:
            pass
        nt.links.new(mp.outputs['Vector'], t.inputs['Vector'])
        nt.links.new(t.outputs['Color'], b.inputs['Base Color'])

    m['ntex_key'] = key
    _CACHE[name] = m
    return m
