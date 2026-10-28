"""RDR2 .ytd (TextureDictionary, RSC8) parser  —— 结构已摸通（2026-10-14）

实测结构（样例 `val_01_trainstn_ext+hidr.ytd`）：

  RSC8 头 16B：magic | version | u32 SysSize @+0x08 | u32 GfxSize @+0x0C
  body = d[16:]；sys 段 = body[0:SysSize]，gfx 段 = body[SysSize:SysSize+GfxSize]

  纹理表：条目 **步长 0xB0**，起点 body+0x180。条目字段（实测）：
    +0x08 u32  尺寸（≈ (mip链字节数 + ~2731) / 16）
    +0x0C u32  8 或 16（疑似 mip/块相关）
    +0x10 u32  常量 0x18008002
    +0x18 u16  Width
    +0x1A u16  Height
    +0x1C u32  0x47xxxxxx / 0x48xxxxxx / 0x4Dxxxxxx / 0x4Exxxxxx（疑似 format/usage）
    +0x20 u32  65536
    +0x24 u32  589837 / 524301 / 458765（疑似 数据校验/偏移基）
    +0x28 u64  名称字符串 ptr（0x50000000|off，ASCII，如 nbx_wall_woodplank_16_nm）
    +0x38 u64  数据 ptr（0x60000000|gfxoff）

  纹理数据在 gfx 段；1024×1024 槽位间距实测 0xAB000(700416)，512×512 槽位 0x56000(352256)。
  尺寸 ∝ 面积，且 ≈ 1 字节/像素 × mip 链 ⇒ **块压缩 1B/px（BC7/BPTC 一族）**。

实测解码状态：
  * 用 WebGL2 `EXT_texture_compression_bptc` + `COMPRESSED_RGBA_BPTC_UNORM_EXT` 上传可渲染；
  * 部分纹理能解出**完全可读**的内容（例：`val_sn_ext_22_*` 解出红底白字招牌 RIVER/TURNER/VETERAN；
    gfx+0 区域用 DXT1 曾解出 DRINK/STITCH 酒馆招牌）；
  * 但同一批里多数仍呈噪声 ⇒ **每张纹理的精确 format / 槽位步长 / 名称↔数据配对仍有未定项**（见 §待办）。

用法：
  python rdr2_ytd.py <file.ytd>                 # 列表
  python rdr2_ytd.py <file.ytd> --dump <dir>    # 导出每张纹理的 mip0 原始数据(.bin)
  python rdr2_ytd.py <file.ytd> --json <out>    # 导出给 WebGL 预览用（含 base64）
"""
import struct, sys, os, json, base64

SYS = 0x50000000
GFX = 0x60000000
ENTRY_BASE = 0x180
ENTRY_STRIDE = 0xB0


class Ytd:
    def __init__(self, data):
        self.raw = data
        self.sys_size = struct.unpack_from('<I', data, 8)[0]
        self.gfx_size = struct.unpack_from('<I', data, 12)[0]
        self.body = data[16:]
        self.gfx = self.body[self.sys_size:self.sys_size + self.gfx_size]

    def u32(self, o): return struct.unpack_from('<I', self.body, o)[0]
    def u16(self, o): return struct.unpack_from('<H', self.body, o)[0]

    def cstr(self, ptr):
        if not (SYS <= ptr < GFX):
            return ''
        o = ptr - SYS
        end = self.body.find(b'\x00', o)
        if end < 0:
            end = o + 256
        return self.body[o:end].decode('latin1', 'replace')

    def find_base(self):
        """自动定位纹理表基址（实测不是恒定 0x180：另有 0x200 / 0x40 等）。
        判据：条目步长 0xB0；W/H 是 2 的幂；+0x38 是 gfx 段指针。"""
        def ispow2(x):
            return x > 0 and (x & (x - 1)) == 0

        best = (0, ENTRY_BASE)
        for base in range(0x20, 0x800, 0x10):
            n = 0
            for i in range(0, 64):
                o = base + i * ENTRY_STRIDE
                if o + 0x40 > len(self.body):
                    break
                w, h = self.u16(o + 0x18), self.u16(o + 0x1A)
                if not (ispow2(w) and ispow2(h) and 4 <= w <= 8192 and 4 <= h <= 8192):
                    break
                dptr = struct.unpack_from('<Q', self.body, o + 0x38)[0]
                if not (GFX <= dptr < 0x70000000):
                    break
                n += 1
            if n > best[0]:
                best = (n, base)
        return best[1]

    def textures(self):
        out = []
        base = self.find_base()
        for i in range(0, 64):
            o = base + i * ENTRY_STRIDE
            if o + 0x40 > len(self.body):
                break
            w, h = self.u16(o + 0x18), self.u16(o + 0x1A)
            if not (1 <= w <= 8192 and 1 <= h <= 8192):
                break
            dptr = struct.unpack_from('<Q', self.body, o + 0x38)[0]
            nptr = struct.unpack_from('<Q', self.body, o + 0x28)[0]
            if not (GFX <= dptr < 0x70000000):
                continue
            out.append(dict(
                idx=len(out), entry=o, w=w, h=h,
                size=self.u32(o + 0x08), fl0c=self.u32(o + 0x0c),
                fmt=self.u32(o + 0x1C), f20=self.u32(o + 0x20), f24=self.u32(o + 0x24),
                gfx_off=dptr - GFX, name=self.cstr(nptr),
            ))
        return out

    # ------------------------------------------------------------ 指针数组布局
    def textures_ptr_array(self):
        """★ 2026-10-24 补：另一种 .ytd 布局——struct 是**指针数组**，纹理结构体不内联。

        实测 `textures/ui_textures.rpf` 里的 `blips/menu_textures/inventory_items/
        satchel_textures/honor_display/shaving_menu/swatches_gunsmith` 都是这种：
          body + 某个偏移处是一串 u64 指针（0x50000000|off），指向各自的纹理结构体；
          结构体字段与内联条目**完全一致**（+0x08 尺寸 / +0x18 W,H u16 / +0x1C fmt /
          +0x28 名称 ptr / +0x38 gfx ptr）。
        内联布局的 `find_base()` 在这种文件里定位不到（步长 0xB0 处不是结构体），
        这就是这 7 个字典早先一律"0 张纹理"的原因。
        """
        out = []
        best = (0, 0)
        for st in range(0x20, min(0x800, len(self.body) - 8), 8):
            n = 0
            while True:
                o = st + n * 8
                if o + 8 > len(self.body):
                    break
                v = struct.unpack_from('<Q', self.body, o)[0]
                if not (SYS <= v < 0x70000000):
                    break
                n += 1
            if n > best[0]:
                best = (n, st)
        n, st = best
        if n < 4:
            return out
        for i in range(n):
            p = struct.unpack_from('<Q', self.body, st + i * 8)[0] - SYS
            if not (0 <= p + 0x40 <= len(self.body)):
                continue
            w, h = self.u16(p + 0x18), self.u16(p + 0x1A)
            dptr = struct.unpack_from('<Q', self.body, p + 0x38)[0]
            nptr = struct.unpack_from('<Q', self.body, p + 0x28)[0]
            if not (1 <= w <= 8192 and 1 <= h <= 8192):
                continue
            if not (GFX <= dptr < 0x90000000):
                continue
            out.append(dict(
                idx=len(out), entry=p, w=w, h=h,
                size=self.u32(p + 0x08), fl0c=self.u32(p + 0x0c),
                fmt=self.u32(p + 0x1C), f20=self.u32(p + 0x20), f24=self.u32(p + 0x24),
                gfx_off=dptr - GFX, name=self.cstr(nptr),
            ))
        return out

    def textures_any(self):
        """内联布局优先；解不出时退到指针数组布局。"""
        t = self.textures()
        if t:
            return t
        return self.textures_ptr_array()


def mip0_bytes(w, h, bpp=1.0):
    """mip0 原始字节数（块压缩 1B/px 家族）"""
    return int(max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 16 * bpp)


def main():
    p = sys.argv[1]
    y = Ytd(open(p, 'rb').read())
    texs = y.textures()
    print(f"{os.path.basename(p)}: sys={y.sys_size} gfx={y.gfx_size} body={len(y.body)} textures={len(texs)}")
    print(f"{'#':>3} {'W':>5} {'H':>5} {'gfxoff':>9} {'size':>7} {'fmt':>10}  name")
    for t in texs:
        print(f"{t['idx']:>3} {t['w']:>5} {t['h']:>5} {t['gfx_off']:#9x} {t['size']:>7} {t['fmt']:#10x}  {t['name']}")
    if '--dump' in sys.argv:
        d = sys.argv[sys.argv.index('--dump') + 1]
        os.makedirs(d, exist_ok=True)
        for t in texs:
            n = mip0_bytes(t['w'], t['h'])
            blob = y.gfx[t['gfx_off']:t['gfx_off'] + n]
            open(os.path.join(d, f"{t['idx']:02d}_{t['name']}.bin"), 'wb').write(blob)
            print("dumped", t['name'], len(blob))
    if '--json' in sys.argv:
        out = sys.argv[sys.argv.index('--json') + 1]
        pack = []
        for t in texs:
            n = mip0_bytes(t['w'], t['h'])
            blob = y.gfx[t['gfx_off']:t['gfx_off'] + n]
            if len(blob) < n:
                continue
            pack.append(dict(name=t['name'], w=t['w'], h=t['h'],
                             fmt=f"{t['fmt']:#010x}",
                             b64=base64.b64encode(blob).decode()))
        json.dump(pack, open(out, 'w'))
        print("wrote", out, len(pack), "textures")


if __name__ == '__main__':
    main()
