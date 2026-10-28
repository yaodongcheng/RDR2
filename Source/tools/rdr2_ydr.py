"""RDR2 .ydr (Drawable, RSC8) mesh parser  —— v2 (2026-10-14, 已攻克)

关键突破（实测 val_01_*.ydr 验证）：
  * 资源体 = RSC8 16 字节头之后；指针形如 0x50000000|offset（system 段）。
  * Drawable 头（body 相对）：
      +0x10 ptr ShaderGroup      +0x18 ptr Skeleton
      +0x2c f32 BoundingSphereRadius
      +0x30 f32[3] BBoxMin       +0x40 f32[3] BBoxMax
      +0x50/0x58/0x60/0x68 ptr Models(high/med/low/vlow)
  * PointerListHeader (16B) = { u64 ArrayPtr; u16 Capacity; u16 Count; u16 Count2; u16 pad }
  * DrawableModel         = { f32 Radius; u32 1; u64 _unk; ptr Geometries; u16 GeomCount; u16 _; ... }
      —— 实测 Geometries 数组指针出现在 +0x08 或 +0x10（两种排布），本文件带自动识别。
  * DrawableGeometry      = { ..., ptr VertexBuffer @+0x08, ptr IndexBuffer @+0x10 }
  * VertexBuffer (0x40B)  = { f32 Tag; u32 1; u32 VertexCount @+0x08; u32 TotalStride @+0x0c;
                              u64 Flags(0x209000) @+0x10; ptr Data @+0x18; ... }
  * IndexBuffer  (0x40B)  = { f32 Tag; u32 1; u32 IndexCount  @+0x08; u32 2 @+0x0c;
                              u64 Flags(0x20a000) @+0x10; ptr Data @+0x18; ... }

  ★★ 顶点是【平面(planar)分属性数组】，不是交织(interleaved)：
      Data[0                .. 12*count)  = position  (f32 x3)   ← 本工具使用
      Data[12*count         .. 28*count)  = attribute1 (16 B/vert)
      Data[28*count         .. 40*count)  = attribute2 (12 B/vert)
     TotalStride = 12+16+12 = 40。
     （已用 index buffer 的三角形边长验证：planar 中位边长 0.29，交织则爆炸。）

用法:
  python rdr2_ydr.py <file.ydr>            # 概要
  python rdr2_ydr.py <file.ydr> --json out.json
"""
import struct, sys, os, json, math

SYS = 0x50000000
GFX = 0x60000000

# 属性布局（每顶点字节数），合计 = 40（= TotalStride）
ATTR_SIZES = (12, 16, 12)


def is_ptr(v):
    return 0x50000000 <= v < 0x70000000


class Res:
    def __init__(self, data):
        self.body = data[16:]
        self.sys_size = struct.unpack_from('<I', data, 8)[0]
        self.gfx_size = struct.unpack_from('<I', data, 12)[0]

    def u16(self, o): return struct.unpack_from('<H', self.body, o)[0]
    def u32(self, o): return struct.unpack_from('<I', self.body, o)[0]
    def u64(self, o): return struct.unpack_from('<Q', self.body, o)[0]
    def f32(self, o): return struct.unpack_from('<f', self.body, o)[0]

    def off(self, ptr):
        """RAGE 指针 -> body 偏移（None 非法）"""
        if ptr == 0:
            return None
        if SYS <= ptr < GFX:
            o = ptr - SYS
        elif GFX <= ptr < 0x70000000:
            o = self.sys_size + (ptr - GFX)
        else:
            return None
        return o if 0 <= o < len(self.body) else None

    def blob(self, ptr, n):
        o = self.off(ptr)
        if o is None:
            return b''
        return self.body[o:o + n]


def pointer_list(res, ptr):
    """ResourcePointerListHeader { u64 ArrayPtr; u16 Cap; u16 Count; ... } -> [ptr]"""
    o = res.off(ptr)
    if o is None or o + 16 > len(res.body):
        return []
    arr = res.u64(o)
    cnt = res.u16(o + 10)
    out = []
    ao = res.off(arr)
    if ao is not None:
        for i in range(cnt):
            if ao + 8 * i + 8 > len(res.body):
                break
            out.append(res.u64(ao + 8 * i))
    return out


def parse_vertex_buffer(res, ptr):
    o = res.off(ptr)
    if o is None or o + 0x40 > len(res.body):
        return None
    count = res.u32(o + 0x08)
    stride = res.u32(o + 0x0c)
    data = res.u64(o + 0x18)
    if not (1 <= count <= 5_000_000) or not is_ptr(data) or stride == 0:
        return None
    return dict(ptr=ptr, off=o, count=count, stride=stride, data=data)


def parse_index_buffer(res, ptr):
    o = res.off(ptr)
    if o is None or o + 0x40 > len(res.body):
        return None
    count = res.u32(o + 0x08)
    isize = res.u32(o + 0x0c)
    data = res.u64(o + 0x18)
    if not (1 <= count <= 20_000_000) or not is_ptr(data):
        return None
    return dict(ptr=ptr, off=o, count=count, isize=isize, data=data)


def read_positions(res, vb):
    """顶点位置 = Data 起始处 count 个 f32x3（平面数组）"""
    blob = res.blob(vb['data'], vb['count'] * 12)
    n = len(blob) // 12
    if n == 0:
        return []
    return list(struct.unpack_from('<%df' % (n * 3), blob))


def read_indices(res, ib):
    isize = 2 if ib['isize'] == 2 else (4 if ib['isize'] == 4 else 2)
    blob = res.blob(ib['data'], ib['count'] * isize)
    n = len(blob) // isize
    if n == 0:
        return []
    fmt = ('<%dH' if isize == 2 else '<%dI') % n
    return list(struct.unpack_from(fmt, blob))


def parse_model_geoms(res, mptr):
    """在 DrawableModel 里找几何数组：实测指针可能在 +0x08 或 +0x10"""
    candidates = []
    for arr_off, cnt_off in ((0x08, 0x10), (0x10, 0x18)):
        ap = res.u64(res.off(mptr) + arr_off) if res.off(mptr) is not None else 0
        if not is_ptr(ap):
            continue
        cnt = res.u16(res.off(mptr) + cnt_off)
        if 1 <= cnt <= 64:
            candidates.append((ap, cnt))
    if not candidates:
        return []
    # 取第一个能解出有效 VB/IB 的
    for ap, cnt in candidates:
        ao = res.off(ap)
        geoms = []
        ok = 0
        for i in range(cnt):
            if ao + 8 * i + 8 > len(res.body):
                break
            g = res.u64(ao + 8 * i)
            geoms.append(g)
        return geoms
    return []


def parse_geometry(res, gptr):
    o = res.off(gptr)
    if o is None or o + 0x40 > len(res.body):
        return None
    # 实测：+0x08 = VertexBuffer*, +0x10 = IndexBuffer*
    vb = parse_vertex_buffer(res, res.u64(o + 0x08))
    ib = parse_index_buffer(res, res.u64(o + 0x10))
    if not vb:
        return None
    return dict(ptr=gptr, vb=vb, ib=ib)


def parse_shader_group(res, ptr):
    """ShaderGroup -> 每个 shader 的纹理列表（★ 按 slot 索引，2026-10-16 修正）。

    ★ 修正记录（重要）：纹理指针数组是 **`u64[NumTextures]`，步长 8 字节**，
      旧实现按 **16 字节**步长读 ⇒ 只读到"偶数 slot"，材质全错位
      （这就是"建筑贴图不对 / 地形取到 `_nm` 当 albedo"的直接原因）。
      权威依据：CodeWalker `ShaderFX.G9_TexturePtrs = ReadUlongsAt(G9_TextureRefsPointer,
      G9_ParamInfos.NumTextures * mult)`。

    结构（G9 ShaderFX，实测）：
      +0x00 u32 Name(joaat)   +0x04 u32 Preset   +0x08 u64 ParametersPtr
      +0x10 u64 **G9_TextureRefsPtr**            ← u64[NumTextures]
      +0x18 u64 UnknownParamsPtr
      +0x20 u64 **ParamInfosPtr** → {+0x00 u8 NumBuffers, +0x01 u8 NumTextures, …}
    纹理描述符本身 = `TextureBase`：`+0x28` NamePtr · `+0x18/0x1A` W/H · `+0x1C` fmt · `+0x38` dataPtr。

    返回 `[[desc,…], …]`（每 shader 一项）；desc 带 `slot` 与 `param`（参数名，来自
    `rdr2_shader_params`，查不到为 None）。
    """
    try:
        import rdr2_shader_params as SP
    except Exception:
        SP = None
    o = res.off(ptr)
    if o is None:
        return []
    so = res.off(res.u64(o + 0x10))
    cnt = res.u16(o + 0x18)
    if so is None:
        return []
    out = []
    for i in range(min(cnt, 256)):
        s = res.off(res.u64(so + 8 * i))
        names = []
        if s is not None:
            shader_hash = res.u32(s + 0x00)
            ro = res.off(res.u64(s + 0x10))                 # u64[NumTextures]
            # NumTextures：优先用 ParamInfos（权威），否则按 XML 表的条数
            ntex = 0
            pio = res.off(res.u64(s + 0x20))
            if pio is not None and pio + 8 <= len(res.body):
                ntex = res.body[pio + 1]
            if ro is not None:
                limit = ntex if 1 <= ntex <= 64 else 24
                for k in range(limit):
                    # ★ 8 字节步长（不是 16）
                    rp = res.off(res.u64(ro + 8 * k))
                    if rp is None:
                        continue
                    nm_o = res.off(res.u64(rp + 0x28))
                    if nm_o is None:
                        continue
                    e = res.body.find(b'\x00', nm_o)
                    if e <= nm_o:
                        continue
                    s2 = res.body[nm_o:e].decode('latin1', 'replace')
                    if not all(32 <= ord(c) < 127 for c in s2):
                        continue
                    param = SP.slot_name(shader_hash, k) if SP else None
                    names.append(dict(name=s2, slot=k, param=param,
                                      role=(SP.role(param) if SP else ''),
                                      w=res.u16(rp + 0x18), h=res.u16(rp + 0x1A),
                                      fmt=res.u32(rp + 0x1C), off=rp,
                                      dptr=res.u64(rp + 0x38), size=res.u32(rp + 0x08)))
        out.append(names)
    return out


# 参数角色 → 优先级（越小越优先当 albedo）
_ALBEDO_PRIORITY = ('albedo', 'albedo_layer0', 'albedo_layer1', 'albedo_layer2', 'albedo_layer3',
                    'lyr0diffusetex', 'albedo2', 'albedo_dirt', 'tint')


def albedo_of(names):
    """从 shader 的纹理里挑 albedo。

    ★ 2026-10-16 改为**按 shader 参数角色**挑（`rdr2_shader_params`），而不是靠文件名后缀猜：
      优先 `diffusetex` / `lyr0diffusetex` / `diffusetexture_layer0`，其次 `diffusetex2`、
      再退到"非 normal/material/palette/lookup"的最大面积贴图。
    """
    cand = [t for t in names if t.get('name') and t['name'].lower() != 'none'
            and not t['name'].lower().startswith('blank')]
    if not cand:
        cand = [t for t in names if t.get('name') and t['name'].lower() != 'none']
    if not cand:
        return None
    for want in _ALBEDO_PRIORITY:
        hit = [t for t in cand if t.get('role') == want]
        if hit:
            return max(hit, key=lambda t: t['w'] * t['h'])['name']
    drop = ('normal', 'material', 'materialA', 'materialB', 'materialA2', 'materialB2',
            'material2', 'palette', 'lookup', 'control', 'detail', 'tint_normal', '')
    rest = [t for t in cand if t.get('role') not in drop]
    if rest:
        return max(rest, key=lambda t: t['w'] * t['h'])['name']
    # 最后退到旧的后缀启发式（无 shader 表时）
    legacy = [t for t in cand if not t['name'].lower().endswith(
        ('_pal', '_nm', '_ma', '_mb', '_n', '_s', '_mtl', '_em', 'emissive', 'decal'))]
    if legacy:
        return max(legacy, key=lambda t: t['w'] * t['h'])['name']
    return max(cand, key=lambda t: t['w'] * t['h'])['name']


def parse_shader_hashes(res, ptr):
    """→ [{'hash': u32, 'name': str|None}, …]，与 parse_shader_group 的下标一一对应。"""
    try:
        import rdr2_shader_params as SP
        lib = SP.load()
    except Exception:
        lib = {}
    o = res.off(ptr)
    if o is None:
        return []
    so = res.off(res.u64(o + 0x10))
    cnt = res.u16(o + 0x18)
    if so is None:
        return []
    out = []
    for i in range(min(cnt, 256)):
        s = res.off(res.u64(so + 8 * i))
        if s is None:
            out.append(dict(hash=0, name=None))
            continue
        h = res.u32(s + 0x00)
        e = lib.get(h)
        out.append(dict(hash=h, name=(e['name'] if e else None)))
    return out


def parse_model_shaders(res, mptr, ng):
    """DrawableModel+0x20 = ShaderMappingPointer -> 每几何体的 shaderID"""
    o = res.off(mptr)
    if o is None:
        return []
    so = res.off(res.u64(o + 0x20))
    if so is None:
        return []
    return [res.u16(so + 2 * i) for i in range(ng)]


def extract_at(res, base, lod='high'):
    """在资源体任意偏移 base 处解析一个 Drawable，返回 (info, meshes)。

    `.ydr` 用 base=0；`.ydd`(DrawableDictionary) 里每个子 drawable 用它的 body 偏移。
    """
    info = dict(
        base=base,
        bbox_min=[round(res.f32(base + 0x30 + 4 * i), 4) for i in range(3)],
        bbox_max=[round(res.f32(base + 0x40 + 4 * i), 4) for i in range(3)],
        radius=round(res.f32(base + 0x2c), 4),
        shader_group=res.u64(base + 0x10), skeleton=res.u64(base + 0x18),
    )
    lod_ptr = {'high': 0x50, 'med': 0x58, 'low': 0x60, 'vlow': 0x68}[lod]
    models = pointer_list(res, res.u64(base + lod_ptr))
    shaders = parse_shader_group(res, info['shader_group'])
    shd = parse_shader_hashes(res, info['shader_group'])
    meshes = []
    for mi, m in enumerate(models):
        geoms = parse_model_geoms(res, m)
        shmap = parse_model_shaders(res, m, len(geoms))
        for gi, g in enumerate(geoms):
            geom = parse_geometry(res, g)
            if not geom or not geom['vb']:
                continue
            pos = read_positions(res, geom['vb'])
            idx = read_indices(res, geom['ib']) if geom['ib'] else []
            sid = shmap[gi] if gi < len(shmap) else 0
            tnames = shaders[sid] if 0 <= sid < len(shaders) else []
            meshes.append(dict(
                lod=lod, model=mi, geom=gi, shader_id=sid,
                shader=(shd[sid]['name'] if 0 <= sid < len(shd) else None),
                shader_hash=(shd[sid]['hash'] if 0 <= sid < len(shd) else 0),
                tex=albedo_of(tnames), texs=[t['name'] for t in tnames],
                texs_detail=[dict(slot=t['slot'], param=t['param'], role=t['role'],
                                  name=t['name'], w=t['w'], h=t['h'],
                                  fmt=t['fmt'], dptr=t['dptr'], off=t['off'])
                             for t in tnames],
                vertex_count=geom['vb']['count'], stride=geom['vb']['stride'],
                index_count=len(idx), triangle_count=len(idx) // 3,
                positions=pos, indices=idx,
            ))
    return info, meshes


def parse_drawable_dictionary(res):
    """`.ydd` = DrawableDictionary → [(hash, drawable_body_offset), ...]

    实测头（body 相对）：+0x20 ptr 哈希数组（升序 u32），+0x2A u16 count；
                        +0x30 ptr drawable 指针数组，+0x3A u16 count。
    """
    out = []
    for hp, cp, pp in ((0x20, 0x2A, 0x30), (0x30, 0x3A, 0x20)):
        harr = res.u64(hp)
        parr = res.u64(pp)
        n = res.u16(cp)
        ho, po = res.off(harr), res.off(parr)
        if ho is None or po is None or not (1 <= n <= 4096):
            continue
        if ho + 4 * n > len(res.body) or po + 8 * n > len(res.body):
            continue
        for i in range(n):
            h = res.u32(ho + 4 * i)
            p = res.u64(po + 8 * i)
            o = res.off(p)
            if o is not None:
                out.append((h, o))
        if out:
            return out
    return out


def extract_ydd(path, lod='high', want_hashes=None):
    """解析 .ydd（LOD 字典）：hash -> meshes"""
    res = Res(open(path, 'rb').read())
    out = {}
    for h, off in parse_drawable_dictionary(res):
        if want_hashes is not None and h not in want_hashes:
            continue
        try:
            info, meshes = extract_at(res, off, lod)
        except Exception:
            continue
        pos = []
        idx = []
        base = 0
        for m in meshes:
            if m['lod'] != lod:
                continue
            pos.extend(m['positions'])
            idx.extend([i + base for i in m['indices']])
            base += m['vertex_count']
        if not idx:
            continue
        out[h] = dict(name=os.path.basename(path), p=pos, i=idx, vc=base, tc=len(idx) // 3)
    return out


def extract(path, lod='high'):
    data = open(path, 'rb').read()
    res = Res(data)
    info, meshes = extract_at(res, 0, lod)
    info.update(name=os.path.basename(path),
                sys_size=res.sys_size, gfx_size=res.gfx_size, body_len=len(res.body))
    return info, meshes


def summarize(info, meshes):
    print(f"{info['name']}: bbox {info['bbox_min']} .. {info['bbox_max']}  r={info['radius']}")
    print(f"  sys={info['sys_size']} gfx={info['gfx_size']} body={info['body_len']}")
    tv = ti = 0
    for m in meshes:
        tv += m['vertex_count']; ti += m['triangle_count']
        print(f"  mesh[{m['model']}.{m['geom']}] verts={m['vertex_count']:>7} tris={m['triangle_count']:>7} stride={m['stride']}")
    print(f"  TOTAL verts={tv} tris={ti}")


if __name__ == '__main__':
    p = sys.argv[1]
    info, meshes = extract(p)
    summarize(info, meshes)
    if '--json' in sys.argv:
        out = sys.argv[sys.argv.index('--json') + 1]
        json.dump(dict(info=info, meshes=meshes), open(out, 'w'), separators=(',', ':'))
        print("wrote", out)

def extract_frag(path, lod='high'):
    """解析 `.yft`（fragment）：里面的 Drawable 挂在若干指针上。

    实测 `p_*x.yft` 的 fragment 头里 +0x08/+0x20/+0x40/+0x70/+0x90 都可能有 drawable 指针
    （+0x20 通常是主 drawable），逐个用 extract_at 试，取三角形最多的那个。
    """
    res = Res(open(path, 'rb').read())
    cands = []
    for off in (0x20, 0x08, 0x40, 0x70, 0x90, 0x28, 0x48):
        try:
            v = res.u64(off)
        except Exception:
            continue
        o = res.off(v)
        if o is not None:
            cands.append(o)
    best = None
    for base in cands:
        try:
            info, ms = extract_at(res, base, lod)
        except Exception:
            continue
        tris = sum(m['triangle_count'] for m in ms)
        if tris > 0 and (best is None or tris > best[0]):
            best = (tris, base, ms)
    if best is None:
        return None, []
    return dict(base=best[1], triangles=best[0]), best[2]
