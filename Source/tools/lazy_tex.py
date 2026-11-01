# -*- coding: utf-8 -*-
"""索引驱动的贴图加载器 —— 替代 `export_sdn_gltf.TexLib` 的「整目录读进内存」做法。

## 为什么

`TexLib(dirs)` 会 `glob` 每个目录下的 `.ytd` 并**把整个文件字节留在内存里**。
源树合并到 `raw/all_packs` 之后（29,236 张 / 58 GB），这条路已经走不通。

`work/tex_name_index.json`（由 `tools/tex_index_ytd.py` 生成）只记录
`名字 → (文件, gfx 偏移, w, h, fmt)`，按需读单张。本模块把它包成和 `TexLib` 同形：

    lib = LazyTexLib(maxs=512)
    img, diag = lib.get('nbx_ground_grass_bay_lsuh_ab', hint_ytd='.../+hidr.ytd')

索引覆盖：`raw/all_packs` + `raw/lib_gtxd/txd` + `txd_game` + `txd_all` + `raw/sdn/gtxd/txd*`
（2026-11-01 重建：145,962 个名字、失效路径 0）。

**池变了必须重建索引**（见 `docs/格式与资产/资产目录方案.md` §8）。
"""
import os
import json

ROOT = r'D:/BrainMaker/大镖客2解包分析'
INDEX = os.path.join(ROOT, 'work/tex_name_index.json')

_CACHE = {}


def _decode_one(blob, w, h, fmt):
    from export_sdn_gltf import decode_one
    return decode_one(blob, w, h, fmt)


def _is_albedo(n):
    from export_sdn_gltf import is_albedo
    return is_albedo(n)


def _clean_name(n):
    from export_sdn_gltf import clean_name
    return clean_name(n)


class LazyTexLib:
    """和 `TexLib` 同接口的懒加载版：`get(name, hint_ytd) -> (PIL.Image|None, 说明)`。"""

    def __init__(self, maxs=512, index_path=INDEX, extra_dirs=()):
        if not os.path.exists(index_path):
            raise SystemExit(
                '[lazy_tex] 缺索引 %s\n'
                '  先生成：python tools/tex_index_ytd.py' % index_path)
        self.maxs = maxs
        self.index_path = index_path
        self.idx = json.load(open(index_path, encoding='utf-8'))
        self.cache = {}
        self.hits = 0
        self.misses = 0
        # 调用方临时给的目录（例：刚抽到 tmp 的某城 gtxd）：**只有索引查不到时才扫**，
        # 避免又把几十 GB 读进内存。
        self.extra_dirs = [d for d in extra_dirs if d and os.path.isdir(d)]
        self._extra = None

    def _ensure_extra(self):
        if self._extra is not None or not self.extra_dirs:
            return
        import glob
        import rdr2_ytd as T
        extra = {}
        for d in self.extra_dirs:
            for f in glob.glob(os.path.join(d, '**', '*.ytd'), recursive=True):
                try:
                    y = T.Ytd(open(f, 'rb').read())
                except Exception:
                    continue
                for t in y.textures():
                    n = t.get('name')
                    if not n:
                        continue
                    k = n.lower()
                    cur = extra.get(k)
                    if cur is None or (t['w'] * t['h']) > (cur[1]['w'] * cur[1]['h']):
                        extra[k] = (y, t)
        self._extra = extra

    def __len__(self):
        return len(self.idx)

    # ---- 内部：按索引条目解一张
    def _from_entry(self, ent):
        f = os.path.join(ROOT, ent['f'].replace('\\', '/'))
        key = (f, ent.get('gfx'))
        if key in _CACHE:
            y = _CACHE[key]
        else:
            import rdr2_ytd as T
            with open(f, 'rb') as fh:
                y = T.Ytd(fh.read())
            _CACHE[key] = y
        off = ent.get('gfx', 0)
        w, h, fmt = ent.get('w', 0), ent.get('h', 0), ent.get('fmt', 0)
        blob = y.gfx[off:off + max(4096, w * h * 4)]
        im, _fmt = _decode_one(blob, w, h, fmt)   # decode_one 返回 (image, fmt)
        return im

    def _entry(self, name):
        if not name:
            return None
        return self.idx.get(name.lower())

    def get(self, name, hint_ytd=None):
        key = (name, hint_ytd)
        if key in self.cache:
            return self.cache[key]
        im, diag = None, 'miss'

        # 0) 模型自带的 `+hidr.ytd` 优先（同模型的贴图一定在这份字典里）
        if hint_ytd and os.path.exists(hint_ytd):
            try:
                import rdr2_ytd as T
                y = T.Ytd(open(hint_ytd, 'rb').read())
                for t in y.textures():
                    if t['name'] and t['name'].lower() == name.lower():
                        blob = y.gfx[t['gfx_off']:t['gfx_off'] + max(4096, t['w'] * t['h'] * 4)]
                        im, _f = _decode_one(blob, t['w'], t['h'], t['fmt'])
                        diag = 'own:' + str(t['fmt'])
                        break
            except Exception:
                pass

        # 1) 精确名 → 2) clean_name 归一
        if im is None:
            ent = self._entry(name) or self._entry(_clean_name(name))
            if ent:
                try:
                    im = self._from_entry(ent)
                    diag = 'hit:' + str(ent.get('fmt'))
                except Exception as e:
                    diag = 'err:' + str(e)[:40]

        # 2b) 索引没有 → 才去扫调用方临时给的目录
        if im is None and self.extra_dirs:
            self._ensure_extra()
            for k in (name.lower(), _clean_name(name).lower()):
                e2 = self._extra.get(k)
                if e2:
                    y, t = e2
                    blob = y.gfx[t['gfx_off']:t['gfx_off'] + max(4096, t['w'] * t['h'] * 4)]
                    im, _f = _decode_one(blob, t['w'], t['h'], t['fmt'])
                    diag = 'extra:' + str(t['fmt'])
                    break

        # 3) 不做模糊猜测（2026-10-28 立的规矩：猜错会把草地配成烧焦地面）
        if im is None:
            self.misses += 1
        else:
            self.hits += 1
        self.cache[key] = (im, diag)
        return im, diag

    def stats(self):
        return 'lazy_tex 命中 %d / 未命中 %d / 名字总数 %d' % (self.hits, self.misses, len(self.idx))
