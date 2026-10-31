"""把全大陆唯一模型**无损**导出成一个 Blender 可直接读的资产包。

和之前那个给浏览器用的量化包不同：
  · 位置 / 法线 / UV 全部 float32，不做量化
  · 贴图按名字去重，512 上限（源多数就是 512 / 1024）
  · 一个模型只存一份，实体只存 (hash, 变换)

产物：
  export/world/lib_native/
      <hh>/<hash>.mdl        每个模型的几何
      tex/<id>.png           去重后的贴图
      index.json             hash → 文件 / 包围盒 / 子网格 / 贴图 id

用法：
  uv run python tools/dump_model_lib.py --limit 200
  uv run python tools/dump_model_lib.py
"""
import os
import sys
import json
import time
import glob
import struct
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import numpy as np                       # noqa: E402
from PIL import Image                    # noqa: E402
import export_sdn_gltf as EX             # noqa: E402
from export_sdn_props2 import load_frag_model  # noqa: E402

MODELS = os.path.join(ROOT, 'export/world/continent/models.json')
NEED = os.path.join(ROOT, 'work/world_analysis/model_need.json')
OUT = os.path.join(ROOT, 'export/world/lib_native')

MAGIC = b'RMDL1\x00\x00\x00'
SUB = struct.Struct('<I I I I I I I')    # texId, vCount, iCount, posOff, nrmOff, uvOff, idxOff


def load_any(path):
    if path.lower().endswith('.yft'):
        try:
            return load_frag_model(path)
        except Exception:
            return None
    return EX.load_model(path)


class Tex:
    def __init__(self, lib, maxs=512):
        self.tl = EX.TexLib([os.path.join(ROOT, 'work/lib_gtxd/txd'),
                             os.path.join(ROOT, 'work/sdn/gtxd/txd'),
                             os.path.join(ROOT, 'export/models')], maxs)
        self.dir = os.path.join(lib, 'tex')
        os.makedirs(self.dir, exist_ok=True)
        self.by_name = {}
        self.meta = []
        self.maxs = maxs

    def get(self, name, hint):
        if not name:
            return -1
        k = name.lower()
        if k in self.by_name:
            return self.by_name[k]
        im, _ = self.tl.get(name, hint)
        if im is None:
            self.by_name[k] = -1
            return -1
        if max(im.size) > self.maxs:
            im = im.resize((self.maxs, self.maxs), Image.LANCZOS)
        if im.mode not in ('RGB', 'RGBA'):
            im = im.convert('RGB')
        tid = len(self.meta)
        fn = '%04d.png' % tid
        im.save(os.path.join(self.dir, fn), 'PNG', optimize=True)
        self.meta.append(dict(id=tid, n=name, f='tex/' + fn))
        self.by_name[k] = tid
        return tid


def write_model(M, h, outdir, tex):
    geoms = [g for g in M['geoms'] if len(g['pos']) and len(g['idx'])]
    if not geoms:
        return None
    bmin = np.array([1e30] * 3, np.float64)
    bmax = np.array([-1e30] * 3, np.float64)
    for g in geoms:
        p = np.asarray(g['pos'], np.float64)
        bmin = np.minimum(bmin, p.min(0))
        bmax = np.maximum(bmax, p.max(0))
    # 2026-10-30 修正：以前要求**三个轴都严格 bmin<bmax**，于是所有"完全扁平"的网格
    # （地面/地台/贴花/地板：dz 恰好为 0）被静默判为退化、整只丢掉 ——
    # 全量抽取里这类文件有上千个（`agu_back_floor003` 之类）。
    # 现在只拒"真正退化"（对角线长度为 0 的一个点网格）。
    if float(np.max(bmax - bmin)) <= 1e-6:
        return None

    subs = []
    blobs = []
    for g in geoms:
        pos = np.asarray(g['pos'], np.float32)
        nrm = np.asarray(g['nrm'], np.float32)
        uv = np.asarray(g['uv'], np.float32)
        if uv.shape[0] < pos.shape[0]:
            uv = np.vstack([uv, np.zeros((pos.shape[0] - uv.shape[0], 2), np.float32)])
        idx = np.asarray(g['idx'], np.uint32)
        tid = tex.get(g.get('tex'), M.get('ytd'))
        subs.append((tid, len(pos), len(idx)))
        blobs.append((pos.tobytes(), nrm.tobytes(), uv.tobytes(), idx.tobytes()))

    nsub = len(subs)
    head = len(MAGIC) + 4 + 24 + nsub * SUB.size
    payload = bytearray()
    cur = head
    offs = []
    for (pb, nb, ub, ib) in blobs:
        o1 = cur; payload += pb; cur += len(pb)
        o2 = cur; payload += nb; cur += len(nb)
        o3 = cur; payload += ub; cur += len(ub)
        o4 = cur; payload += ib; cur += len(ib)
        offs.append((o1, o2, o3, o4))

    out = bytearray(MAGIC)
    out += struct.pack('<I', nsub)
    out += struct.pack('<6f', *[float(x) for x in bmin], *[float(x) for x in bmax])
    for i, (tid, v, n) in enumerate(subs):
        o1, o2, o3, o4 = offs[i]
        out += SUB.pack(tid & 0xffffffff, v, n, o1, o2, o3, o4)
    out += payload

    # key / 文件名一律 `0x` + 8 位补零 hex：hex() 不补零会让 0x04ac59bc 变成 0x4ac59bc，
    # 构建时按 '0x%08x' 查表就查不到（最高原则 §6.4 那个坑，2026-10-29 修复）。
    hx = '0x%08x' % h
    d = os.path.join(outdir, hx[2:4])
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, hx + '.mdl'), 'wb') as f:
        f.write(bytes(out))
    return dict(f='%s/%s.mdl' % (hx[2:4], hx),
                b=[round(float(x), 3) for x in list(bmin) + list(bmax)],
                s=[[t, v, n] for (t, v, n) in subs],
                sz=len(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--maxs', type=int, default=512)
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    models = json.load(open(MODELS, encoding='utf-8'))
    try:
        need = json.load(open(NEED, encoding='utf-8'))
        refs = {k: v['n'] for k, v in need.items()}
    except Exception as e:
        print('model_need.json 不可用（%s），按原始顺序处理' % e)
        refs = {}
    items = sorted(models.items(), key=lambda kv: -refs.get(kv[0], 0))
    if a.limit:
        items = items[:a.limit]
    print('模型 %d 个' % len(items))

    tex = Tex(OUT, a.maxs)
    print('贴图库 %d 名' % len(tex.tl.idx))

    index = {}
    t0 = time.time()
    done = skipped = 0
    nv = ni = nb = 0
    for hx, rel in items:
        M = load_any(os.path.join(ROOT, rel))
        if not M:
            skipped += 1
            continue
        e = write_model(M, int(hx, 16), OUT, tex)
        if not e:
            skipped += 1
            continue
        index[hx] = {k: e[k] for k in ('f', 'b', 's')}
        nv += sum(x[1] for x in e['s'])
        ni += sum(x[2] for x in e['s'])
        nb += e['sz']
        done += 1
        if done % 300 == 0:
            el = time.time() - t0
            print('  %5d/%d  %.6f GB  %.0f/分  剩 ~%.0f 分' %
                  (done, len(items), nb / 1e9, done / el * 60,
                   (len(items) - done) / max(1e-9, done / el) / 60))

    json.dump(dict(models=index, tex=tex.meta),
              open(os.path.join(OUT, 'index.json'), 'w'), separators=(',', ':'))
    tsz = sum(os.path.getsize(os.path.join(tex.dir, f)) for f in os.listdir(tex.dir))
    print('\n完成 %d（跳过 %d）几何 %.2f GB / 顶点 %.1f M / 三角 %.1f M / 贴图 %d 张 %.0f MB'
          % (done, skipped, nb / 1e9, nv / 1e6, ni / 3e6, len(tex.meta), tsz / 1e6))
    print('用时 %.1f 分' % ((time.time() - t0) / 60))


if __name__ == '__main__':
    main()
