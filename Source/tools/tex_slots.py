# -*- coding: utf-8 -*-
"""从 shader 的纹理列表里，**按同一个 albedo 图层**取出 漫反射 / 法线 / 材质(高光) 三个名字。

## 为什么单独一个模块

`export_sdn_gltf.load_model()` 只把 albedo 塞进 `g['tex']`，法线/材质是
`ntex`/`mtex` 且**只认 standard shader 的 role**（`ROLE_MATERIAL` 里没有
`material_layerN`）—— 地形（`terrain_uber_4lyr_*`，占网格大头）的 `_ma`
就是这么被漏掉的。

这里按 **albedo 所在图层**配对取另外两张：
    albedo_layer2  →  normal_layer2  →  material_layer2
    albedo(standard) → normal        → material
这样一张地形块不会把第 0 层的法线贴到第 2 层的漫反射上。

## 约定（与最高原则 §6.3「禁靠猜测匹配贴图」一致）

- 取不到就返回 `None`，**不模糊匹配、不跨层回退到"看起来像"的名字**；
- `blank_nm` / `blank_ma` 是引擎占位，等于没有；
- 选中的 albedo 必须与模型库里已存的 albedo **同名**，否则调用方应当丢弃整条绑定。
"""
import rdr2_ydr as Y

# 与 rdr2_ydr._ALBEDO_PRIORITY / export_sdn_gltf.ROLE_ALBEDO 保持一致
ALBEDO_PRIORITY = ('albedo', 'albedo_layer0', 'albedo_layer1', 'albedo_layer2',
                   'albedo_layer3', 'lyr0diffusetex', 'albedo2', 'albedo_dirt', 'tint')

# 与 export_sdn_gltf.ROLE_ALBEDO 一致（注意 `albedo2` 不在里面，它有单独一轮）
ROLE_ALBEDO = ('albedo', 'albedo_layer0', 'albedo_layer1', 'albedo_layer2', 'albedo_layer3',
               'lyr0diffusetex', 'albedo_dirt')

# albedo 三轮都挑不到时的兜底 drop 表：原样照抄 export_sdn_gltf.load_model()
_DROP_EX = ('normal', 'material', 'materialA', 'materialB', 'palette',
            'lookup', 'control', 'detail', '')


def _ok(t):
    n = t.get('name')
    return bool(n) and not n.lower().startswith('blank') and n.lower() != 'none'


def _biggest(cands):
    return max(cands, key=lambda t: t['w'] * t['h']).get('name')


def pick_albedo(texs):
    """→ (name|None, role|'')。

    **必须与 `export_sdn_gltf.load_model()` 的选择规则逐字一致** ——
    模型库里的 albedo 就是用那份代码写进去的，这里偏一点就会对不上名字，
    那样整条绑定就会被调用方丢弃（宁可没图，也不贴错）。
    """
    # 1) slot 顺序里第一张"角色属于 ROLE_ALBEDO"的图
    for t in texs:
        if (t.get('role') or '') in ROLE_ALBEDO and _ok(t):
            return t.get('name'), t.get('role') or ''
    # 2) 只认 albedo2
    for t in texs:
        if t.get('role') == 'albedo2' and _ok(t):
            return t.get('name'), 'albedo2'
    # 3) 退到"最大面积的非法线/材质图"（原样照抄 load_model 的 drop 表）
    cand = [t for t in texs if _ok(t) and (t.get('role') or '') not in _DROP_EX]
    if cand:
        best = max(cand, key=lambda t: t['w'] * t['h'])
        return best.get('name'), best.get('role') or ''
    return None, ''


def layer_of(role):
    """albedo_layer2 → 2；lyr0diffusetex → 0；standard 的 albedo → None"""
    if not role:
        return None
    if role.startswith('albedo_layer'):
        try:
            return int(role[-1])
        except ValueError:
            return None
    if role == 'lyr1diffusetex':
        return 1
    if role == 'lyr0diffusetex':
        return 0
    return None


def pick_normal(texs, layer=None, albedo_role=''):
    """同层 normal_layerN → 通用 normal → (albedo2 时) normal2；取不到 None。"""
    by_role = {}
    for t in texs:
        if _ok(t):
            by_role.setdefault(t.get('role') or '', []).append(t)
    order = []
    if layer is not None:
        order.append('normal_layer%d' % layer)
    order.append('normal')
    if albedo_role == 'albedo2':
        order.append('normal2')
    order.append('tint_normal')
    for r in order:
        if by_role.get(r):
            return _biggest(by_role[r])
    return None


def pick_material(texs, layer=None, albedo_role=''):
    """同层 material_layerN → 通用 material(speculartex) → materialA/B；取不到 None。

    `_ma` 的通道语义（已定死，见 docs/世界与地编/RDR2_圣丹尼斯地编破解.md §5.9.2）：
        R = Metallic   G = Roughness   B = AO
    """
    by_role = {}
    for t in texs:
        if _ok(t):
            by_role.setdefault(t.get('role') or '', []).append(t)
    order = []
    if layer is not None:
        order.append('material_layer%d' % layer)
    order.append('material')
    if albedo_role == 'albedo2':
        order.append('material2')
    order += ['materialA', 'materialB', 'materialA2', 'materialB2']
    for r in order:
        if by_role.get(r):
            return _biggest(by_role[r])
    return None


def pick_all(texs):
    """→ dict(alb=name|None, alb_role=role, nrm=name|None, mat=name|None)"""
    alb, role = pick_albedo(texs)
    layer = layer_of(role)
    return dict(alb=alb, alb_role=role, layer=layer,
                nrm=pick_normal(texs, layer, role),
                mat=pick_material(texs, layer, role))


# --------------------------------------------------------------------- 源文件读取
def geoms_of_ydr(res):
    """ydr → [(geom, texs), …]，顺序与 `export_sdn_gltf.load_model()` 完全一致。"""
    import export_sdn_gltf as EX
    sg = res.u64(0x10)
    shaders = Y.parse_shader_group(res, sg)
    out = []
    for mo in Y.pointer_list(res, res.u64(0x50)):
        gs = Y.parse_model_geoms(res, mo)
        shmap = Y.parse_model_shaders(res, mo, len(gs))
        for gi, gp in enumerate(gs):
            sid = shmap[gi] if gi < len(shmap) else 0
            g = EX.read_geom(res, gp, sid)
            if not g:
                continue
            texs = shaders[sid] if 0 <= sid < len(shaders) else []
            out.append((g, texs))
    return out
