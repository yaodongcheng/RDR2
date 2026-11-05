# -*- coding: utf-8 -*-
"""无贴图模型的**通用材质族**：按模型名判定类别，每类给一个真实贴图 + 合理粗糙度/金属度。

和旧版（只给一个 RGB）的区别：
  · 每类有一张**库内真实贴图**（木纹 / 金属 / 布 / 石…），用 Box 投影贴在模型上；
  · 金属类 metallic=0.85、roughness≈0.45；布/木 roughness≈0.9；
  · 取不到贴图才退回纯色 + 噪声。

用法：
    from ntex_palette import category_for
    from ntex_materials import get_material      # 需要 bpy
    cat = category_for(model_name)
    mat = get_material(cat, libdir, texmeta)      # texmeta = index.json['tex']
"""
import re

# key, 名字关键词, 候选贴图正则（在库 tex 名里找）, 基础色, metallic, roughness, 贴图世界尺度(m)
CATS = [
    ('veg', r'kudz|tree|pine|fir|oak|cedar|maple|birch|lodgepole|bush|shrub|scrub|bramble|fern|'
            r'grass|weed|moss|leaf|leaves|vine|palm|cactus|plant|flower|reed|foliage|canopy',
     r'(?i)(leaves|leaf|bark|tree|bush|grass|fern|moss).*_ab', (0.12, 0.20, 0.09, 1), 0.0, 0.9, 1.0),
    ('food', r'grain|corn|wheat|hay|straw|food|bread|meat|fruit|vegetable|produce|feed|sugarcane|flour',
     r'(?i)(grain|hay|straw|wheat|sack).*_ab', (0.52, 0.42, 0.22, 1), 0.0, 0.95, 0.8),
    ('paper', r'paper|news|poster|sign|letter|book|map|ledger|notice|circular',
     r'(?i)(paper|news|poster).*_ab', (0.76, 0.72, 0.64, 1), 0.0, 0.9, 0.6),
    ('cloth', r'cloth|canvas|tarp|rug|curtain|sack|bag|bed|blanket|towel|garment|pillow|mat',
     r'(?i)(fabric|cloth|canvas|rug|curtain|carpet).*_ab', (0.52, 0.46, 0.36, 1), 0.0, 0.95, 0.8),
    ('leather', r'leather|saddle|harness|boot|strap|reins|bridle',
     r'(?i)(leather|saddle).*_ab', (0.30, 0.18, 0.10, 1), 0.0, 0.8, 0.6),
    ('rope', r'rope|string|twine|cord|lariat',
     r'(?i)(rope|twine|cord).*_ab', (0.48, 0.40, 0.26, 1), 0.0, 0.95, 0.4),
    ('ceramic', r'pot|ceramic|plate|bowl|jug|cup|pitcher|vase|dish',
     r'(?i)(ceramic|pottery|plate|china).*_ab', (0.60, 0.54, 0.44, 1), 0.0, 0.6, 0.4),
    ('glass', r'glass|window|bottle|jar|lens',
     r'', (0.18, 0.24, 0.28, 1), 0.0, 0.15, 0.4),
    ('metal', r'metal|iron|steel|pipe|anvil|wheel|rail|can_|tin|lantern|lamp|chain|hook|stove|'
              r'safe_|gun|rifle|revolver|bucket_metal|nails|bolt|gear|machin',
     r'(?i)(metal|iron|steel|rust|brass|copper).*_ab', (0.28, 0.28, 0.30, 1), 0.85, 0.45, 0.7),
    ('wood', r'barrel|crate|box|plank|lumber|beam|board|log|stump|wagon|cart|coffin|pallet|'
             r'cooper|bucket|bench|table|chair|cabinet|shelf|door|wood|timber|fence|post_|pole|'
             r'handle|shaft',
     r'(?i)(wood_plank|plank|wood_0|nbx_wood|lumber|woodpole|woodbeam).*_ab', (0.36, 0.24, 0.14, 1), 0.0, 0.85, 0.9),
    ('stone', r'rock|stone|cliff|boulder|scree|brick|concrete|cement|cobble|slab|rubble',
     r'(?i)(stone|rock|brick|cobble).*_ab', (0.38, 0.37, 0.35, 1), 0.0, 0.9, 1.0),
    ('dirt', r'dirt|mud|soil|dust|sand|gravel|clay|mound',
     r'(?i)(dirt|mud|soil|sand|gravel).*_ab', (0.30, 0.23, 0.15, 1), 0.0, 0.95, 0.8),
    ('water', r'water|puddle|lake|river|pond|stream|well_',
     r'', (0.10, 0.16, 0.18, 1), 0.0, 0.1, 0.5),
]

DEFAULT = ('default', (0.30, 0.27, 0.23, 1), 0.0, 0.85, 0.8)


def category_for(*names):
    """返回 (key, color, metallic, roughness, scale)；命中不了给 default。"""
    for n in names:
        if not n:
            continue
        s = str(n)
        for key, pat, _tex, col, metal, rough, scale in CATS:
            if re.search(pat, s, re.I):
                return key, col, metal, rough, scale
    return DEFAULT


def category_info(*names):
    """(key, color, metallic, roughness, scale, tex_pattern) —— 给材质构建器用。"""
    key, col, metal, rough, scale = category_for(*names)
    pat = ''
    for k, _p, tex, *_rest in CATS:
        if k == key:
            pat = tex
            break
    return key, col, metal, rough, scale, pat


def color_for(*names):
    """兼容旧调用：只要颜色。"""
    return category_for(*names)[1]


def material_name(key):
    return 'ntex_' + key
