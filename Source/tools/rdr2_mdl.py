"""读 assets/lib_native 的 .mdl（RMDL1）——微缩模型 v2 用真实建筑网格的入口。

格式（由 tools/dump_model_lib.py 写出，全部小端）：
    0   : 8 字节 magic 'RMDL1\\x00\\x00\\x00'
    8   : u32 nsub
    12  : 6f  bbox (minx,miny,minz,maxx,maxy,maxz)
    36  : nsub × SUB   SUB = <I I I I I I I> = texId, vCount, iCount, posOff, nrmOff, uvOff, idxOff
    ... : payload（偏移是相对文件头的绝对偏移）
"""
import os
import struct
import numpy as np

ROOT = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(ROOT, 'assets/lib_native')
MAGIC = b'RMDL1\x00\x00\x00'
SUB = struct.Struct('<I I I I I I I')


def mdl_path(h):
    hx = hex(h)
    return os.path.join(LIB, hx[2:4], hx + '.mdl')


def load_mdl(h, want_uv=True):
    """返回 (pos[N,3], nrm[N,3], uv[N,2], idx[M,3], tex_ids[list])；失败返回 None。"""
    p = mdl_path(h)
    if not os.path.exists(p):
        return None
    with open(p, 'rb') as f:
        d = f.read()
    if d[:8] != MAGIC:
        return None
    nsub, = struct.unpack_from('<I', d, 8)
    subs = []
    for i in range(nsub):
        subs.append(SUB.unpack_from(d, 36 + i * SUB.size))

    pos_l, nrm_l, uv_l, idx_l = [], [], [], []
    base = 0
    for (tid, vc, ic, po, no, uo, io) in subs:
        if vc == 0 or ic == 0:
            continue
        pos = np.frombuffer(d, dtype=np.float32, count=vc * 3, offset=po).reshape(-1, 3)
        nrm = np.frombuffer(d, dtype=np.float32, count=vc * 3, offset=no).reshape(-1, 3)
        uv = np.frombuffer(d, dtype=np.float32, count=vc * 2, offset=uo).reshape(-1, 2)
        idx = np.frombuffer(d, dtype=np.uint32, count=ic, offset=io).reshape(-1, 3)
        pos_l.append(pos)
        nrm_l.append(nrm)
        uv_l.append(uv if want_uv else np.zeros((vc, 2), np.float32))
        idx_l.append(idx.astype(np.int64) + base)
        base += vc

    if not pos_l:
        return None
    vtex = np.concatenate([np.full(vc, tid, np.int64) for (tid, vc, ic, *_r) in subs
                           if vc and ic])
    return (np.vstack(pos_l), np.vstack(nrm_l), np.vstack(uv_l),
            np.vstack(idx_l), [s[0] for s in subs], vtex)


# ---- 贴图（512 上限，按 texId 取）------------------------------------------
_TEX_CACHE = {}


def load_tex(tid, size=64):
    """读 texId → size² 的 RGB float（0..1）。只为"给顶点取色"，不需要原分辨率。"""
    if tid in _TEX_CACHE:
        return _TEX_CACHE[tid]
    p = os.path.join(LIB, 'tex', '%04d.png' % tid)
    if not os.path.exists(p):
        _TEX_CACHE[tid] = None
        return None
    from PIL import Image
    im = Image.open(p).convert('RGB')
    if im.size != (size, size):
        im = im.resize((size, size), Image.BILINEAR)
    a = np.asarray(im, dtype=np.float32) / 255.0
    # sRGB → 线性（顶点色最终会被引擎按 sRGB 解释，这里保持贴近原图）
    _TEX_CACHE[tid] = a
    return a


def sample_tex(tex, uv):
    """uv[N,2] → color[N,3]；uv 原点与 glTF 一致（左上）。"""
    size = tex.shape[0]
    u = np.clip(uv[:, 0], 0, 0.999999)
    v = np.clip(uv[:, 1], 0, 0.999999)
    x = (u * size).astype(np.int32)
    y = (v * size).astype(np.int32)
    return tex[y, x]
