# -*- coding: utf-8 -*-
"""导出「安尼斯堡铁路」一小片的 glTF-free 预览数据 + 一个 three.js 页面（不经过 Blender）。

为什么要它：blend 7.8 GB，开一次太慢；而 `export/previews/ann/` 是 10-19 的旧导出，
里面只有站内 `ann_02_rails_*`，没有主线 `jklm_1518b_r_*` 和枕木片。

做法：
  export/world/continent/tiles/*.json 里取走廊内的实例（名字匹配 rail/_r_x_/dec/track）
  → 读 assets/lib_native/<xx>/0x….mdl 的顶点
  → 按实例的 (pos, quat, scale) 烘到世界坐标
  → 按 (贴图, UV 模式) 分组写成一份 rail.json
     · 普通件：用模型自带 UV
     · 贴花件（名字含 dec/decal/track）：**UV 改成世界米坐标**，页面里用 texture.repeat 实时调平铺密度
  → 顺手把用到的 albedo PNG 拷到 tex/，并生成 index.html（three.js + OrbitControls）

    python tools/export_rail_preview.py
    python tools/export_rail_preview.py --x0 2780 --x1 3120 --y0 1080 --y1 1580
"""
import argparse
import io
import json
import os
import re
import shutil
import struct
import glob

import numpy as np

ROOT = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(ROOT, 'assets/lib_native')
TILES = os.path.join(ROOT, 'export/world/continent/tiles')
NAMES = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
MAGIC = b'RMDL1' + bytes(3)
SUB = struct.Struct('<7I')

RAIL_RE = re.compile(r'rail|_r_[abc]_|_dec(?![a-z])|decal|track|tressle|trestle|b_r_', re.I)
DECAL_UV_RE = re.compile(r'_dec|_decal|rail_decal|track_decal|maintrack|northtrack|southtrack|minetrack|b_r_dec', re.I)


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xffffffff
        h = (h + (h << 10)) & 0xffffffff
        h ^= h >> 6
    h = (h + (h << 3)) & 0xffffffff
    h ^= h >> 11
    h = (h + (h << 15)) & 0xffffffff
    return h


def load_names():
    m = {}
    for line in io.open(NAMES, encoding='utf-8', errors='ignore'):
        s = line.strip()
        if s:
            m.setdefault(joaat(s), s)
    return m


def quat_rot(q, v):
    """q=(x,y,z,w) 单位四元数，v=(n,3) → 旋转后的向量"""
    x, y, z, w = q
    if abs(x) + abs(y) + abs(z) < 1e-9:
        return v
    R = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ], dtype=np.float64)
    return v @ R.T


def read_mdl(path):
    b = open(path, 'rb').read()
    if b[:8] != MAGIC:
        return None
    nsub = struct.unpack_from('<I', b, 8)[0]
    subs = []
    for i in range(nsub):
        tid, vc, ic, po, no, uo, io_ = SUB.unpack_from(b, 12 + 24 + i * SUB.size)
        if vc == 0 or ic == 0:
            continue
        pos = np.frombuffer(b, dtype=np.float32, count=vc * 3, offset=po).reshape(-1, 3).astype(np.float64)
        nrm = np.frombuffer(b, dtype=np.float32, count=vc * 3, offset=no).reshape(-1, 3).astype(np.float64)
        uv = np.frombuffer(b, dtype=np.float32, count=vc * 2, offset=uo).reshape(-1, 2).astype(np.float64)
        idx = np.frombuffer(b, dtype=np.uint32, count=ic, offset=io_).astype(np.int64)
        if idx.max() >= vc:
            continue
        subs.append((tid, pos, nrm, uv, idx))
    return subs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--x0', type=float, default=2780)
    ap.add_argument('--x1', type=float, default=3130)
    ap.add_argument('--y0', type=float, default=1080)
    ap.add_argument('--y1', type=float, default=1580)
    ap.add_argument('--out', default=os.path.join(ROOT, 'export/previews/rail_ann'))
    a = ap.parse_args()

    os.makedirs(os.path.join(a.out, 'tex'), exist_ok=True)
    names = load_names()
    idx = json.load(io.open(os.path.join(LIB, 'index.json'), encoding='utf-8'))
    models = idx['models']
    tex = idx['tex']

    insts = []
    for f in sorted(glob.glob(os.path.join(TILES, '*.json'))):
        for e in json.load(io.open(f, encoding='utf-8')):
            h, x, y, z = e[0], e[1], e[2], e[3]
            if not (a.x0 <= x <= a.x1 and a.y0 <= y <= a.y1):
                continue
            nm = names.get(h)
            if not nm or not RAIL_RE.search(nm):
                continue
            insts.append((nm, '0x%08x' % h, e))
    print('[rail] 走廊内选中实例 %d' % len(insts))

    cache = {}
    groups = {}      # (texname, uv_mode) -> dict(pos=[], nrm=[], uv=[], idx=[])
    used_tex = set()
    skipped = 0
    for nm, hx, e in insts:
        ent = models.get(hx)
        if not ent:
            skipped += 1
            continue
        path = os.path.join(LIB, ent['f'])
        if hx not in cache:
            cache[hx] = read_mdl(path) if os.path.exists(path) else None
        subs = cache[hx]
        if not subs:
            skipped += 1
            continue
        x, y, z, qx, qy, qz, qw, sxy, sz = e[1], e[2], e[3], e[4], e[5], e[6], e[7], e[8], e[9]
        decal_uv = bool(DECAL_UV_RE.search(nm))
        for tid, pos, nrm, uv, ix in subs:
            tname = tex[tid]['n'] if 0 <= tid < len(tex) else None
            key = (tname, 'world' if decal_uv else 'model')
            g = groups.get(key)
            if g is None:
                g = {'pos': [], 'nrm': [], 'idx': [], 'base': 0}
                groups[key] = g
            p = pos * np.array([sxy, sxy, sz])
            p = quat_rot((qx, qy, qz, qw), p) + np.array([x, y, z])
            n = quat_rot((qx, qy, qz, qw), nrm)
            if decal_uv:
                # 世界米坐标（X/Y）；页面里用 texture.repeat 调每几米一次平铺
                u = np.stack([p[:, 0], p[:, 1]], axis=1)
            else:
                u = uv
            g['pos'].append(p.astype(np.float32))
            g['nrm'].append(n.astype(np.float32))
            g.setdefault('uvs', []).append(u.astype(np.float32))
            g['idx'].append((ix + g['base']).astype(np.uint32))
            g['base'] += len(p)
            if tname:
                used_tex.add(tname)

    # 二进制打包（JSON 会到 90+ MB，浏览器解析太慢）
    blob = bytearray()
    out_groups = []

    def put(arr, dtype):
        nonlocal blob
        while len(blob) % 4:
            blob.append(0)
        off = len(blob)
        buf = arr.tobytes()
        blob += buf
        return off

    for (tname, mode), g in groups.items():
        pos = np.concatenate(g['pos']).astype(np.float32)
        nrm = np.concatenate(g['nrm']).astype(np.float32)
        uv = np.concatenate(g['uvs']).astype(np.float32)
        ix = np.concatenate(g['idx']).astype(np.uint32)
        fname = None
        if tname:
            t = None
            for tt in tex:
                if tt['n'] == tname:
                    t = tt
                    break
            if t:
                src = os.path.join(LIB, t['f'])
                if os.path.exists(src):
                    fname = os.path.basename(t['f'])
                    shutil.copyfile(src, os.path.join(a.out, 'tex', fname))
        out_groups.append({
            'tex': fname, 'name': tname or '(none)', 'uv': mode,
            'pos': put(pos, np.float32), 'nvp': len(pos),
            'nrm': put(nrm, np.float32),
            'uvs': put(uv, np.float32),
            'idx': put(ix, np.uint32), 'nvi': len(ix),
        })

    with open(os.path.join(a.out, 'rail.bin'), 'wb') as f:
        f.write(bytes(blob))
    data = {'box': [a.x0, a.y0, a.x1, a.y1], 'groups': out_groups}
    with io.open(os.path.join(a.out, 'rail.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, separators=(',', ':'))
    mb = os.path.getsize(os.path.join(a.out, 'rail.bin')) / 2**20
    print('[rail] 组 %d / 贴图 %d / rail.bin %.1f MB / 跳过 %d'
          % (len(out_groups), len(used_tex), mb, skipped))


if __name__ == '__main__':
    main()
