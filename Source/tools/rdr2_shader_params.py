"""RDR2 shader 参数表：`shader 名 → 纹理 slot → 参数名`。

## 为什么需要它

RDR2 的 `ShaderFX` 里有一张**按 slot 索引的纹理指针数组**（`u64[NumTextures]` @ `ShaderFX+0x10`），
slot 号 = shader 纹理参数的下标。**光有纹理文件名判断不出它是 albedo 还是遮罩**，
必须知道 slot 的语义（`diffusetex` / `lyr1diffusetex` / `tintpalettetex` / `materialmapatexture_layerN` …）。

参数名来自社区权威表 **Sollumz-RDR 的 `cwxml/ModRDRShaders.xml`**（197 个 RDR2 shader，
逐条列出 `<Item index="k" name="..." type="Texture"/>`）。
实测交叉验证（本目录 `l_09__hd_0_0_0.ydr` / `val_03_saloon_ext.ydr`）：

| shader | 资产里 `NumTextures` | XML 里 Texture 条数 |
|---|---|---|
| `terrain_uber_4lyr_pxm_hbb` | **16** | **16** ✅ |
| `standard` | **7** | **7** ✅ |
| `standard_dirt` | **9** | **9** ✅ |
| `standard_2lyr` | 13（saloon shader3） | **13** ✅ |

且 slot→名字与数据语义**完全吻合**（地形 slot1/2/3 = `..._abte/_nm/_ma` ↔
`diffusetexture_layer0/bumptexture_layer0/materialmapatexture_layer0`；slot13 `tinttexture` = `l_09_t`）。

用法：
    from rdr2_shader_params import load
    lib = load()                      # {shader_hash(u32): {slot: param_name}}
    lib[0x770b903e][1]                # -> 'diffusetexture_layer0'
"""
import os
import re

_XML_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 'ref/Sollumz-RDR-main/cwxml/ModRDRShaders.xml'),
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 'ref/Sollumz-RDR-main/cwxml/Shaders.xml'),
]
# 第二来源：RedDead2Blend 的每-shader JSON（`{hash, name, uniforms:[{hash,name,size}]}`，146 个）
# 两个来源实测 **uniform 顺序完全一致**，可互为校验；JSON 还提供 **参数名 hash**。
_JSON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'ref/RedDead2Blend-main/data/shaders')

# 兜底（按 slot 顺序，来源同上表；仅当 ref/ 里的 XML 缺失时用）
FALLBACK = {
    'standard': ['tintpalettetex', 'oIZmQFA_0xE9F32960', 'diffusetex', 'detailtexarrayn',
                 'bumptex', 'speculartex', 'speculartex2'],
    'standard_dirt': ['tintpalettetex', 'oIZmQFA_0xE9F32960', 'diffusetex', 'detailtexarrayn',
                      'diffusetex2', 'bumptex', 'speculartex', 'speculartex2', 'fjsTvVA_0x56D855C5'],
    'standard_2lyr': ['tintpalettetex', 'lyr0diffusetex', 'lyr0normaltex', 'lyr0materialatex',
                      'lyr0materialbtex', 'lyr1diffusetex', 'lyr1normaltex', 'lyr1materialatex',
                      'lyr1materialbtex', 'dirtdiffusetex', 'controltexturetex', 'aotexturetex',
                      'detailtexarrayn'],
    'terrain_uber_4lyr_pxm_hbb': ['lookuptexture',
                                  'diffusetexture_layer0', 'bumptexture_layer0', 'materialmapatexture_layer0',
                                  'diffusetexture_layer1', 'bumptexture_layer1', 'materialmapatexture_layer1',
                                  'diffusetexture_layer2', 'bumptexture_layer2', 'materialmapatexture_layer2',
                                  'diffusetexture_layer3', 'bumptexture_layer3', 'materialmapatexture_layer3',
                                  'tinttexture', 'fjsTvVA_0x56D855C5', 'tintbumptexture'],
    'terrain_lod_2lyr': ['fjsTvVA_0x56D855C5', 'diffusetex', 'diffusetex2',
                         'bumptexture', 'bumptexture2', 'speculartexture', 'speculartexture2'],
    'terrain_slod': ['diffusetex', 'bumptexture', 'speculartexture'],
}

# 参数名 → 该 slot 在"材质"里扮演的角色（albedo 选择用）
ROLE = {
    'diffusetex': 'albedo', 'diffusetex2': 'albedo2', 'detailtexarrayn': 'detail',
    'lyr0diffusetex': 'albedo', 'lyr1diffusetex': 'albedo2', 'dirtdiffusetex': 'albedo_dirt',
    'controltexturetex': 'control', 'tintpalettetex': 'palette',
    'bumptex': 'normal', 'lyr0normaltex': 'normal', 'lyr1normaltex': 'normal2',
    'speculartex': 'material', 'speculartex2': 'material2',
    'lyr0materialatex': 'materialA', 'lyr0materialbtex': 'materialB',
    'lyr1materialatex': 'materialA2', 'lyr1materialbtex': 'materialB2',
    'lookuptexture': 'lookup', 'tinttexture': 'tint', 'tintbumptexture': 'tint_normal',
}
for _i in range(4):
    ROLE[f'diffusetexture_layer{_i}'] = f'albedo_layer{_i}'
    ROLE[f'bumptexture_layer{_i}'] = f'normal_layer{_i}'
    ROLE[f'materialmapatexture_layer{_i}'] = f'material_layer{_i}'

_cache = None


def joaat(s):
    h = 0
    for c in s.encode('utf-8'):
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= (h >> 6)
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= (h >> 11)
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h


def _parse_xml(path):
    x = open(path, encoding='utf-8', errors='ignore').read()
    out = {}
    for m in re.finditer(r'<Item>\s*<Name>(.*?)</Name>(.*?)</Item>', x, re.S):
        name, body = m.group(1).strip(), m.group(2)
        slots = {}
        for t in re.finditer(r'<Item\s+([^>]*type="Texture"[^>]*)/>', body):
            a = t.group(1)
            idx = re.search(r'index="(\d+)"', a)
            nm = re.search(r'name="([^"]+)"', a)
            if idx and nm:
                slots[int(idx.group(1))] = nm.group(1)
        if slots:
            out[joaat(name)] = dict(name=name, slots=slots, param_hash_to_name={})
    return out


def _parse_json_db():
    """RedDead2Blend `data/shaders/*.json` → {shader_hash: {'name','slots','param_hash_to_name'}}"""
    import glob
    import json as _json
    out = {}
    for f in glob.glob(os.path.join(_JSON_DIR, '*.json')):
        try:
            d = _json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        sh = d.get('hash')
        if not isinstance(sh, int):
            continue
        slots = {}
        ph = {}
        for i, u in enumerate(d.get('uniforms') or []):
            nm = u.get('name') or ''
            # 只有"纯数字"的名字才是未命名的 hash 占位；其余是参数名
            if nm and not nm.isdigit():
                slots[i] = nm
            if isinstance(u.get('hash'), int) and nm and not nm.isdigit():
                ph[u['hash']] = nm
        out[sh] = dict(name=d.get('name') or '', slots=slots, param_hash_to_name=ph)
    return out


def load(reload=False):
    """→ {shader_hash: {'name': str, 'slots': {slot: param_name}, 'param_hash_to_name': {...}}}"""
    global _cache
    if _cache is not None and not reload:
        return _cache
    lib = {}
    for p in _XML_CANDIDATES:
        if os.path.isfile(p):
            try:
                lib.update(_parse_xml(p))
            except Exception:
                pass
    for h, e in _parse_json_db().items():
        cur = lib.setdefault(h, dict(name=e['name'], slots={}))
        cur.setdefault('param_hash_to_name', {}).update(e['param_hash_to_name'])
        for k, v in e['slots'].items():
            cur['slots'].setdefault(k, v)      # XML 优先
        if not cur.get('name'):
            cur['name'] = e['name']
    for nm, lst in FALLBACK.items():
        lib.setdefault(joaat(nm), dict(name=nm, slots={i: v for i, v in enumerate(lst)}))
    _cache = lib
    return lib


def slot_name(shader_hash, slot):
    """查 slot 的参数名；查不到返回 None。"""
    lib = load()
    e = lib.get(shader_hash)
    return (e['slots'].get(slot) if e else None)


def role(param_name):
    return ROLE.get(param_name or '', '')


if __name__ == '__main__':
    lib = load()
    print(f'loaded {len(lib)} shader definitions')
    for want in ('terrain_uber_4lyr_pxm_hbb', 'standard', 'standard_dirt', 'standard_2lyr'):
        e = lib.get(joaat(want))
        print(f'\n{want}: {"OK" if e else "MISSING"}')
        if e:
            for k in sorted(e['slots']):
                print(f'   slot[{k:2}] {e["slots"][k]:<28} role={role(e["slots"][k])}')
