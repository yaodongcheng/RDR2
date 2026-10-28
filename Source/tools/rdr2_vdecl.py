"""RDR2 顶点声明（VertexDeclarationG9）解析 —— 解开"顶点里没有 UV"的假象。

## 为什么之前一直找不到 UV

RDR2 的顶点缓冲是 **SOA（平面分属性数组）**，而 GTA V 是 **AOS（交织）**。
CodeWalker `VertexDeclarationG9.HasSOA` 的注释原文：
    "seems to always be false for GTAV gen9 (but true for RDR2)"

属性语义**不在顶点缓冲里，而在 `VertexBuffer + 0x38` 指向的 `VertexDeclarationG9`**：
    Offsets[52] u32 (208B)  —— 每个语义元素在顶点数据块内的**起始字节偏移**
    Sizes[52]   u8  (52B)   —— 每个语义元素的**每顶点步长**（不是元素大小，是 stride）
    Types[52]   u8  (52B)   —— 元素格式（VertexDeclarationG9ElementFormat = DXGI 码）
    Data        u64         —— bit0=HasSOA / bit2..9=VertexSize / bit10..=VertexCount

元素下标 → 语义（CodeWalker `GetLegacyComponentIndex`）：
    0 POSITION · 4 NORMAL · 8 TANGENT(0) · 9 TANGENT1 · 16 BLENDWEIGHTS · 20 BLENDINDICES
    24 COLOR0 · 25 COLOR1 · 26 COLOR2 · 28 TEXCOORD0 · 29 TEXCOORD1 · 30 TEXCOORD2 ...

**SOA 读法**：元素 i 的第 v 个顶点数据在 `数据块起点 + Offsets[i] + Sizes[i] * v`。

## 实测结论（2026-10-16）

| 资产 | stride | 布局 |
|---|---|---|
| 建筑 `.ydr`（val_03_saloon_ext / val_01_trainstn_ext） | 40 | POSITION(12) NORMAL(4) TANGENT(4) **COLOR0(4)** **TEXCOORD0(8)** **TEXCOORD1(8)** |
| 地形 `.ydr`（l_09__hd_0_0_0） | 56 | POSITION(12) NORMAL(4) TANGENT(4) TANGENT1(4) **COLOR1(4) COLOR2(4)** **TEXCOORD0/1/2(8×3)** |

⇒ **建筑确实有 UV**（两套），前几轮"顶点里没有 UV"是因为没读声明、按交织/错误偏移解读。
⇒ 建筑的 `COLOR0` 是**每顶点调色板/染色选择子**（配合 `TintPaletteTex` / `*_pal` LUT）。
⇒ 地形的 `COLOR1/COLOR2` 是**逐顶点图层混合权重**，3 套 UV 分别是宏观色图 / 平铺图层 / 细节。

用法：
    python rdr2_vdecl.py <file.ydr>                 # 打印每个几何体的语义布局
    python rdr2_vdecl.py <file.ydr> --json out.json  # 连 UV/颜色一起导出（前 N 个顶点）
    python rdr2_vdecl.py <file.ydr> --check          # UV 合理性自检（边长线性度）
"""
import struct
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rdr2_ydr as Y

# ---- 元素下标 → 语义名（CodeWalker GetLegacyComponentIndex + RageSemanticNames）----
SEM = {
    0: 'POSITION', 4: 'NORMAL', 8: 'TANGENT', 9: 'TANGENT1', 10: 'TANGENT2', 11: 'TANGENT3',
    12: 'BINORMAL', 16: 'BLENDWEIGHTS', 20: 'BLENDINDICES',
    24: 'COLOR0', 25: 'COLOR1', 26: 'COLOR2', 27: 'COLOR3',
    28: 'TEXCOORD0', 29: 'TEXCOORD1', 30: 'TEXCOORD2', 31: 'TEXCOORD3',
    32: 'TEXCOORD4', 33: 'TEXCOORD5',
}

# ---- VertexDeclarationG9ElementFormat（= DXGI 码低字节，见 CodeWalker Drawable.cs）----
# 值 → (名字, 分量数, 每顶点字节数)
FMT = {
    0: ('NONE', 0, 0),
    2: ('R32G32B32A32_FLOAT', 4, 16),
    6: ('R32G32B32_FLOAT', 3, 12),
    10: ('R16G16B16A16_FLOAT', 4, 8),
    16: ('R32G32_FLOAT', 2, 8),
    24: ('R10G10B10A2_UNORM', 4, 4),
    28: ('R8G8B8A8_UNORM', 4, 4),
    30: ('R8G8B8A8_UINT', 4, 4),
    34: ('R16G16_FLOAT', 2, 4),
}



# 元素下标 → 语义字母（CodeWalker XML 用；P/N/X/W/I/C/T）
SEM_LETTER = {0: 'P', 4: 'N', 8: 'X', 9: 'X', 10: 'X', 11: 'X', 12: 'X', 13: 'X',
              16: 'W', 17: 'W', 18: 'W', 19: 'W', 20: 'I', 21: 'I', 22: 'I', 23: 'I',
              24: 'C', 25: 'C', 26: 'C', 27: 'C',
              28: 'T', 29: 'T', 30: 'T', 31: 'T', 32: 'T', 33: 'T'}

def parse_vdecl(res, ptr):
    """读取 VertexDeclarationG9；返回 None 表示该几何体没有声明。"""
    o = res.off(ptr)
    if o is None or o + 320 > len(res.body):
        return None
    offs = [res.u32(o + 4 * i) for i in range(52)]
    sizes = list(res.body[o + 208:o + 208 + 52])
    types = list(res.body[o + 260:o + 260 + 52])
    data = res.u64(o + 312)
    return dict(
        ptr=ptr, offsets=offs, sizes=sizes, types=types,
        hassoa=(data & 1) > 0,
        vertex_size=(data >> 2) & 0xFF,
        vertex_count=(data >> 10) & 0x3FFFFF,
    )


def elements(vd):
    """[(下标, 语义名, 格式名, 分量数, 偏移, 步长), ...]（只列非空元素）"""
    out = []
    if not vd:
        return out
    for i, t in enumerate(vd['types']):
        if t == 0:
            continue
        name, comps, _sz = FMT.get(t, ('?0x%02x' % t, 0, 0))
        out.append((i, SEM.get(i, 'elem%d' % i), name, comps, vd['offsets'][i], vd['sizes'][i]))
    return out


def read_element(res, data_ptr, vd, idx, limit=None):
    """按 SOA 读元素 idx → [[float,...], ...]（分量数由格式决定）。"""
    o = res.off(data_ptr)
    if o is None:
        return []
    name, comps, _ = FMT.get(vd['types'][idx], ('?', 0, 0))
    n = vd['vertex_count'] if limit is None else min(vd['vertex_count'], limit)
    off, step = vd['offsets'][idx], vd['sizes'][idx]
    out = []
    for v in range(n):
        p = o + off + step * v
        if p + step > len(res.body):
            break
        t = vd['types'][idx]
        if t == 6:
            out.append(list(struct.unpack_from('<3f', res.body, p)))
        elif t in (16, 34):
            out.append(list(struct.unpack_from('<2f', res.body, p)))
        elif t == 2:
            out.append(list(struct.unpack_from('<4f', res.body, p)))
        elif t in (28, 30):                      # 4×u8（颜色/权重）
            out.append(list(struct.unpack_from('<4B', res.body, p)))
        elif t == 24:                            # R10G10B10A2
            u = struct.unpack_from('<I', res.body, p)[0]
            out.append([(u >> 0) & 0x3FF, (u >> 10) & 0x3FF, (u >> 20) & 0x3FF, (u >> 30) & 0x3])
        elif t == 10:
            out.append(list(struct.unpack_from('<4e', res.body, p)))
        else:
            out.append(list(res.body[p:p + step]))
    return out


def geoms_of(res, base=0, lod='high'):
    """[(几何体序号, vb, ib, vdecl), ...]"""
    out = []
    models = Y.pointer_list(res, res.u64(base + {'high': 0x50, 'med': 0x58, 'low': 0x60, 'vlow': 0x68}[lod]))
    for m in models:
        for gi, g in enumerate(Y.parse_model_geoms(res, m)):
            go = res.off(g)
            if go is None:
                continue
            vb = Y.parse_vertex_buffer(res, res.u64(go + 0x08))
            ib = Y.parse_index_buffer(res, res.u64(go + 0x10))
            if not vb:
                continue
            vd = parse_vdecl(res, res.u64(vb['off'] + 0x38))     # ★ VB+0x38 = VertexDeclarationG9
            out.append((gi, vb, ib, vd))
    return out


def layout_report(path):
    res = Y.Res(open(path, 'rb').read())
    print(f'{os.path.basename(path)}  sys={res.sys_size} gfx={res.gfx_size}')
    for gi, vb, ib, vd in geoms_of(res, 0):
        print(f'  geom{gi}: vc={vb["count"]} stride={vb["stride"]} vdecl='
              f'{"yes" if vd else "NONE"} hasSOA={vd["hassoa"] if vd else "-"} '
              f'decl.vsize={vd["vertex_size"] if vd else "-"} decl.vcount={vd["vertex_count"] if vd else "-"}')
        for i, name, fmt, comps, off, step in elements(vd):
            print(f'      elem[{i:2}] {name:<14} {fmt:<20} comps={comps} off={off:<6} step={step}')
    return res


def check(path):
    """UV 合理性：UV 在网格边上应与位置线性相关（|duv|/|dpos| 的 MAD 小 = 真 UV）"""
    import statistics
    res = Y.Res(open(path, 'rb').read())
    print(f'--- {os.path.basename(path)} ---')
    for gi, vb, ib, vd in geoms_of(res, 0):
        if not vd:
            continue
        pos = read_element(res, vb['data'], vd, 0)
        idx = Y.read_indices(res, ib) if ib else []
        for i, name, fmt, comps, off, step in elements(vd):
            # 只体检"可能的 UV / 权重"（TEXCOORD* / COLOR*），位置/法线必过不算数
            if comps < 2 or not (name.startswith('TEXCOORD') or name.startswith('COLOR')):
                continue
            arr = read_element(res, vb['data'], vd, i)
            flat = [c for v in arr for c in v if isinstance(c, (int, float))]
            ratios = []
            for e in range(0, min(len(idx), 9000) - 2, 3):
                a, b = idx[e], idx[e + 1]
                duv = sum((arr[a][k] - arr[b][k]) ** 2 for k in range(comps)) ** 0.5
                dpo = sum((pos[a][k] - pos[b][k]) ** 2 for k in range(3)) ** 0.5
                if dpo > 1e-6:
                    ratios.append(duv / dpo)
            if not ratios:
                continue
            med = statistics.median(ratios)
            mad = statistics.median([abs(r - med) for r in ratios])
            # 真 UV 判据：UV 随位置**线性**变化（MAD/med 小），且不是位置本身（med≠1 时剔除退化）
            is_uv = mad < med * 0.5 and med != 1.0
            tag = '★真 UV（随位置线性）' if is_uv else ('（常量/非 UV）' if mad > med * 0.9 else '')
            print(f'  geom{gi} elem[{i:2}] {name:<12} {fmt:<18} range=[{min(flat):.3f},{max(flat):.3f}] '
                  f'med={med:.4f} MAD={mad:.4f} {tag}')


def dump(path, out, maxv=256):
    res = Y.Res(open(path, 'rb').read())
    data = {'name': os.path.basename(path), 'geoms': []}
    for gi, vb, ib, vd in geoms_of(res, 0):
        g = dict(geom=gi, vertex_count=vb['count'], stride=vb['stride'],
                 layout=[dict(elem=i, name=n, fmt=f, comps=c, off=o, step=s)
                         for i, n, f, c, o, s in elements(vd)], data={})
        for i, name, fmt, comps, off, step in elements(vd):
            g['data'][name] = read_element(res, vb['data'], vd, i, limit=maxv)
        data['geoms'].append(g)
    json.dump(data, open(out, 'w'), separators=(',', ':'))
    print('wrote', out)


if __name__ == '__main__':
    p = sys.argv[1]
    if '--check' in sys.argv:
        check(p)
    elif '--json' in sys.argv:
        dump(p, sys.argv[sys.argv.index('--json') + 1])
    else:
        layout_report(p)
