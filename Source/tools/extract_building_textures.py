"""T5-v2: 按 **material 名** 为 Valentine 建筑解出全部游戏原生 albedo 贴图。

三级策略（优先保真）：
  1) **`.ytd` 名字索引**（最可靠）：扫 buildings_jklm/** 全部 .ytd 建 name→entry，按名解码；
  2) `.ydr` **内嵌**：部分纹理直接存在建筑 .ydr 自己的 gfx 段（描述符 +0x38 有数据指针）；
  3) **同族最近邻回退**：仍缺的按「最长公共前缀 + 同后缀类别」沿用同类贴图，并在 json 里标 `fallback`。

输出：export/levels/town/valentine_textures.json = { "tex": {name: {w,h,fcc,b64[,fallback]}} }
"""
import os, sys, json, glob, io, base64, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import rdr2_ydr as Y
import rdr2_ytd as T
from ytd_to_png import dds, FMT, FMT_NAME

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TOWN = os.path.join(ROOT, 'export/levels/town')
BUILD = os.path.join(ROOT, 'export/models/buildings_jklm')
OUT = os.path.join(TOWN, 'valentine_textures.json')
MAXS = 256


def enc(im, w, h, fccname):
    im = im.resize((MAXS, MAXS))
    bio = io.BytesIO()
    im.convert('RGB').save(bio, 'PNG', optimize=True)
    return dict(w=w, h=h, fcc=fccname, b64=base64.b64encode(bio.getvalue()).decode())


def dec_blob(blob, w, h, fcc):
    blk = 8 if fcc == b'DXT1' else 16
    n = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * blk
    if len(blob) < n:
        return None
    return dds(blob, w, h, fcc)


# 地形/地面用的贴图（查看器里做世界空间 box/planar 映射）
TERRAIN_TEX = [
    'hea_grass_lush_01_abte',
    'nbx_dirt_discolor_02_abal',
    'nbx_dirt_stone_grime_02_ab',
    'nbx_ground_road02_abal',
    'bla_ground_sand05_abal',
]

meshes = json.load(open(os.path.join(TOWN, 'valentine_meshes.json'), encoding='utf-8'))
need = set(TERRAIN_TEX)
for v in meshes.values():
    for t in (v.get('texs') or []):
        if t: need.add(t)
    for t, s, n in v.get('grp', []):
        if t: need.add(t)
print(f'需要 {len(need)} 张贴图')

# ---- 1) .ytd 名字索引 ----
index = {}
for f in glob.glob(BUILD + '/**/*.ytd', recursive=True):
    try:
        y = T.Ytd(open(f, 'rb').read())
        for t in y.textures():
            if t['name'] and t['name'] not in index:
                index[t['name']] = (y, t)
    except Exception:
        continue
print(f'.ytd 索引 {len(index)} 个名字')

out = {}
for nm in sorted(need & set(index)):
    y, t = index[nm]
    code = (t['fmt'] >> 24) & 0xFF
    fcc = FMT.get(code)
    if not fcc:
        continue
    blk = 8 if fcc == b'DXT1' else 16
    n = max(1, (t['w'] + 3) // 4) * max(1, (t['h'] + 3) // 4) * blk
    try:
        im = dec_blob(y.gfx[t['gfx_off']: t['gfx_off'] + n], t['w'], t['h'], fcc)
        if im:
            out[nm] = enc(im, t['w'], t['h'], FMT_NAME[code])
    except Exception:
        pass
print(f'  从 .ytd 解出 {len(out)}')

# ---- 2) .ydr 内嵌 ----
rest = need - set(out)
byname = {}
for f in glob.glob(BUILD + '/**/*.ydr', recursive=True):
    byname.setdefault(os.path.splitext(os.path.basename(f))[0], f)
for v in meshes.values():
    if not rest:
        break
    f = byname.get(v['name'])
    if not f:
        continue
    try:
        res = Y.Res(open(f, 'rb').read())
        for sh in Y.parse_shader_group(res, res.u64(0x10)):
            for t in sh:
                k = t['name']
                if k not in rest or not t['dptr'] or not t['w'] or not t['h']:
                    continue
                code = (t['fmt'] >> 24) & 0xFF
                fcc = FMT.get(code)
                if not fcc:
                    continue
                blk = 8 if fcc == b'DXT1' else 16
                n = max(1, (t['w'] + 3) // 4) * max(1, (t['h'] + 3) // 4) * blk
                go = res.sys_size + (t['dptr'] - 0x60000000)
                im = dec_blob(res.body[go:go + n], t['w'], t['h'], fcc)
                if im:
                    out[k] = enc(im, t['w'], t['h'], FMT_NAME[code])
                    rest.discard(k)
    except Exception:
        continue
print(f'  + .ydr 内嵌 -> 共 {len(out)}')

# ---- 3) 同族最近邻回退 ----
def cls(n):
    for s in ('_ab', '_abal', '_al', '_ct', '_abc'):
        if n.lower().endswith(s):
            return s
    return ''
fb = {}
for nm in sorted(need - set(out)):
    best = None
    for cand in out:
        k = 0
        while k < len(nm) and k < len(cand) and nm[k] == cand[k]:
            k += 1
        score = k + (6 if cls(cand) == cls(nm) else 0)
        if best is None or score > best[0]:
            best = (score, cand)
    if best and best[0] >= 8:
        fb[nm] = best[1]
        out[nm] = dict(out[best[1]], fallback=best[1])
print(f'  + 同族回退 {len(fb)} -> 最终 {len(out)}')

json.dump(dict(tex=out), open(OUT, 'w'), separators=(',', ':'))
print('wrote', OUT, round(os.path.getsize(OUT) / 1024 / 1024, 2), 'MB')
