"""Decode RDR2 .ytd textures to PNG (per-texture real BC format).  —— v2 (2026-10-15 已通)

`.ytd` 结构（实测，详见 tools/rdr2_ytd.py 文档）：纹理表条目步长 0xB0，起点 body+0x180；
  +0x18 W / +0x1A H / **+0x1F 格式字节（DXGI 码）** / +0x28 名称 ptr / +0x38 数据 gfx ptr。

格式字节（= `fmt >> 24`，即 DXGI_FORMAT 码）实测映射（CodeWalker `TextureFormatG9`）：
  0x47 → BC1_UNORM (DXT1)        0x48 → BC1_UNORM_SRGB
  0x4D → BC3_UNORM (DXT5)        0x4E → BC3_UNORM_SRGB

★ 2026-10-15 修复（27/27 全部完美解码）：根因不是格式映射，而是 **DDS 头长度写错**——
  旧实现拼出 **132 字节**头（应为 128），像素数据整体后移 4 字节 ⇒ 解出来全是噪声。
  正确 DDS 头：4(magic)+124(=0x7C) = 128 字节；pixelformat 在偏移 76，caps 在 108。

用法：
  python ytd_to_png.py <file.ytd> <outdir> [--sheet sheet.png] [--only 13,20]
"""
import os, sys, io, struct
from PIL import Image

# 压缩格式（走 DDS 四字节码 / DX10 头）
FMT = {0x47: b'DXT1', 0x48: b'DXT1', 0x4D: b'DXT5', 0x4E: b'DXT5'}
FMT_NAME = {0x47: 'BC1', 0x48: 'BC1_sRGB', 0x4D: 'BC3', 0x4E: 'BC3_sRGB'}

# ★ 2026-10-16 扩充：CodeWalker TextureFormatG9 里已定名的其余格式
#   0x52/53/54 BC5（法线）、0x4F/50/51 BC4、0x62/63 BC7、0x46/49/4A/4B/4C BC1/2/3 TYPELESS
#   —— 之前 entries() 直接 `if f not in FMT: continue` **静默丢弃**，所以调色板 / BC7 法线一直"不存在"
BC_EXTRA = {0x46: (71, 'BC1_TYPELESS'), 0x49: (74, 'BC2_TYPELESS'), 0x4A: (74, 'BC2'),
            0x4B: (75, 'BC2_sRGB'), 0x4C: (77, 'BC3_TYPELESS'),
            0x4F: (80, 'BC4_TYPELESS'), 0x50: (81, 'BC4'), 0x51: (82, 'BC4_SNORM'),
            0x52: (83, 'BC5_TYPELESS'), 0x53: (84, 'BC5'), 0x54: (85, 'BC5_SNORM'),
            0x5E: (95, 'BC6H_TYPELESS'), 0x5F: (96, 'BC6H_UF16'), 0x60: (97, 'BC6H_SF16'),
            0x61: (98, 'BC7_TYPELESS'), 0x62: (98, 'BC7'), 0x63: (99, 'BC7_sRGB')}
# 未压缩格式（直接 frombytes）
RAW_FMT = {0x1B: ('RGBA', 'RGBA8_TYPELESS'), 0x1C: ('RGBA', 'RGBA8'), 0x1D: ('RGBA', 'RGBA8_sRGB'),
           0x57: ('BGRA', 'BGRA8'), 0x5A: ('BGRA', 'BGRA8_TYPELESS'), 0x5B: ('BGRA', 'BGRA8_sRGB')}


def dds(data, w, h, fcc):
    """构造**严格 128 字节**的 DDS 头 + 数据（旧版多写 4 字节导致数据错位）。"""
    hdr = bytearray(128)
    hdr[0:4] = b'DDS '
    struct.pack_into('<I', hdr, 4, 124)                              # dwSize
    struct.pack_into('<I', hdr, 8, 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000)  # caps|H|W|PF|linearsize
    struct.pack_into('<I', hdr, 12, h)
    struct.pack_into('<I', hdr, 16, w)
    struct.pack_into('<I', hdr, 20, len(data))                       # linear size
    struct.pack_into('<I', hdr, 76, 32)                              # DDPF dwSize
    struct.pack_into('<I', hdr, 80, 0x4)                             # DDPF_FOURCC
    hdr[84:88] = fcc
    struct.pack_into('<I', hdr, 108, 0x1000)                         # DDSCAPS_TEXTURE
    bio = io.BytesIO(bytes(hdr) + data)
    im = Image.open(bio)
    im.load()
    return im           # ★ 保留 alpha（BC3/BC5）；调用方按需 convert


def dds_dx10(data, w, h, dxgi):
    """BC7 / BC5 / BC4 等需要 DDS_HEADER_DXT10（+20 字节，含 dxgiFormat）。"""
    hdr = bytearray(128)
    hdr[0:4] = b'DDS '
    struct.pack_into('<I', hdr, 4, 124)
    struct.pack_into('<I', hdr, 8, 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000)
    struct.pack_into('<I', hdr, 12, h)
    struct.pack_into('<I', hdr, 16, w)
    struct.pack_into('<I', hdr, 20, len(data))
    struct.pack_into('<I', hdr, 76, 32)
    struct.pack_into('<I', hdr, 80, 0x4)
    hdr[84:88] = b'DX10'
    struct.pack_into('<I', hdr, 108, 0x1000)
    dx10 = struct.pack('<IIIII', dxgi, 3, 0, 1, 0)   # dxgiFormat, ResourceDimension=TEXTURE2D, miscFlag, arraySize, miscFlags2
    bio = io.BytesIO(bytes(hdr) + dx10 + data)
    im = Image.open(bio)
    im.load()
    return im           # ★ 保留 alpha


def decode_one(blob, w, h, fmt_byte):
    """按格式字节解码一张纹理 → (PIL.Image, 格式名) 或 (None, 名字)。"""
    code = fmt_byte & 0xFF if fmt_byte > 0xFF else fmt_byte
    # 本文件里 fmt 可能是整条 u32（fmt>>24 后调用），也支持直接给低字节
    if fmt_byte > 0xFF:
        code = (fmt_byte >> 24) & 0xFF
    if code in FMT:
        blk = 8 if FMT[code] == b'DXT1' else 16
        n = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * blk
        if len(blob) < n:
            return None, FMT_NAME[code]
        return dds(blob[:n], w, h, FMT[code]), FMT_NAME[code]
    if code in BC_EXTRA:
        dxgi, nm = BC_EXTRA[code]
        blk = 8 if dxgi in (80, 81, 82) else 16
        n = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * blk
        if len(blob) < n:
            return None, nm
        try:
            return dds_dx10(blob[:n], w, h, dxgi), nm
        except Exception:
            return None, nm
    if code in RAW_FMT:
        mode, nm = RAW_FMT[code]
        n = w * h * 4
        if len(blob) < n:
            return None, nm
        # PIL 没有 'BGRA' 模式（旧写法直接崩溃 → 调色板 _pal 一直是"解不出来"）
        im = Image.frombytes('RGBA' if mode == 'BGRA' else mode, (w, h), blob[:n])
        if mode == 'BGRA':
            b, g, r, a = im.split()
            im = Image.merge('RGBA', (r, g, b, a))
        return im, nm
    return None, '0x%02x' % code


def load(path):
    d = open(path, 'rb').read()
    ss = struct.unpack_from('<I', d, 8)[0]
    gfx = struct.unpack_from('<I', d, 12)[0]
    return d[16:], d[16 + ss:16 + ss + gfx]


_POW2 = set(1 << k for k in range(1, 14))


def find_base(body):
    """★ 自动定位纹理表基址（2026-10-16 补，即 README 的 T2 待办）。
    原来硬编码 `body+0x180`，只对项目自己抽的那批成立；**每个文件的基址不同**
    （实测 mod 贴图是 `body+0x40`，早前抽的是 `0x180`/`0x200`）。
    判据：连续 N 条满足「W/H 是 2 的幂 + `+0x1F` 是已知 BC 格式码 + `+0x38` 指向 gfx 段」。"""
    best = (0, 0x180)
    for base in range(0x20, 0x4000, 0x10):
        n = 0
        for i in range(200):
            o = base + i * 0xB0
            if o + 0x48 > len(body):
                break
            w, h = struct.unpack_from('<HH', body, o + 0x18)
            gp = struct.unpack_from('<I', body, o + 0x38)[0]
            if w in _POW2 and h in _POW2 and body[o + 0x1F] in FMT and 0x60000000 <= gp < 0x70000000:
                n += 1
            else:
                break
        if n > best[0]:
            best = (n, base)
    return best[1]


def entries(body, raw=None):
    """★ 复用 rdr2_ytd.Ytd（单一真相源：表基址该文件自己定位得最准）。
    旧版这里自带一份 find_base（扫到 0x4000）会选到**假基址**，导致条目错位。"""
    if raw is not None:
        import rdr2_ytd as _Y
        y = _Y.Ytd(raw)
        return [dict(idx=t['idx'], w=t['w'], h=t['h'], f=(t['fmt'] >> 24) & 0xFF,
                     go=t['gfx_off'], name=t['name']) for t in y.textures()]
    # 退化：兼容旧的 body-only 调用
    base = find_base(body)
    out = []
    for i in range(0, 256):
        o = base + i * 0xB0
        if o + 0x40 > len(body):
            break
        w, h = struct.unpack_from('<HH', body, o + 0x18)
        if not (1 <= w <= 8192 and 1 <= h <= 8192):
            break
        gp = struct.unpack_from('<I', body, o + 0x38)[0]
        if not (0x60000000 <= gp < 0x70000000):
            continue
        out.append(dict(idx=i, w=w, h=h, f=body[o + 0x1F], go=gp - 0x60000000, name=''))
    return out


def main():
    p, outdir = sys.argv[1], sys.argv[2]
    raw = open(p, 'rb').read()
    body, gpx = load(p)
    ents = entries(body, raw=raw)
    only = None
    if '--only' in sys.argv:
        only = set(int(x) for x in sys.argv[sys.argv.index('--only') + 1].split(','))
    os.makedirs(outdir, exist_ok=True)
    tiles = []
    print(f"{os.path.basename(p)}: {len(ents)} textures")
    for t in ents:
        if only and t['idx'] not in only:
            continue
        blob = gpx[t['go']:t['go'] + max(4096, t['w'] * t['h'] * 4)]
        im, fname = decode_one(blob, t['w'], t['h'], t['f'])
        if im is None:
            print(f"  #{t['idx']:>2} {t['w']}x{t['h']} {fname:10s} {t['name']}  [跳过/未支持]")
            continue
        fn = os.path.join(outdir, f"{t['idx']:02d}_{t['name']}_{fname}.png")
        im.save(fn)
        tiles.append((t, im))
        print(f"  #{t['idx']:>2} {t['w']}x{t['h']} {fname:8s} {t['name']} -> {os.path.basename(fn)}")
    if '--sheet' in sys.argv and tiles:
        out = sys.argv[sys.argv.index('--sheet') + 1]
        CELL, COLS = 320, 4
        rows = (len(tiles) + COLS - 1) // COLS
        sheet = Image.new('RGB', (COLS * CELL, rows * CELL), (12, 14, 18))
        for k, (t, im) in enumerate(tiles):
            sheet.paste(im.resize((CELL, CELL)), ((k % COLS) * CELL, (k // COLS) * CELL))
        sheet.save(out)
        print("sheet ->", out)


if __name__ == '__main__':
    main()
