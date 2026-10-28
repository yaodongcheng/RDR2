# -*- coding: utf-8 -*-
"""把武器导出成「带烘焙 albedo + 法线」的 glTF —— 真正解决"武器没贴图"。

和 `export_weapon_assembled.py` 的关系：
  那个负责"装配部件"（主体 + 木托/护木…）；这个负责"上色"（把 standard_weapon_2lyr
  的调色板/双层参数烘成 UV 空间的 albedo + normal，写进 glTF 的材质）。

原理见 `weapon_tint.py` 顶部注释（附 slot→参数对照表）。

用法：
    python tools/export_weapon_tint.py                 # 全部武器
    python tools/export_weapon_tint.py --only w_repeater_carbine01,w_rifle_springfield01
"""
import os
import sys
import json
import struct
import hashlib
import argparse
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rdr2_ydr as Y
import rdr2_vdecl as V
import weapon_tint as WT
import export_weapon_assembled as ASM

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "export/viewer/models/weapons")
TEXOUT = os.path.join(OUT, "textures")


# ---------------------------------------------------------------- 读取几何
def load_geoms(path):
    """→ [dict(pos,nrm,uv,idx,params,texname)]"""
    res = Y.Res(open(path, "rb").read())
    sg = res.u64(0x10)
    shaders = Y.parse_shader_group(res, sg)
    out = []
    for m in Y.pointer_list(res, res.u64(0x50)):
        gs = Y.parse_model_geoms(res, m)
        shmap = Y.parse_model_shaders(res, m, len(gs))
        for gi, gp in enumerate(gs):
            go = res.off(gp)
            if go is None:
                continue
            vb = Y.parse_vertex_buffer(res, res.u64(go + 0x08))
            ib = Y.parse_index_buffer(res, res.u64(go + 0x10))
            if not vb:
                continue
            vd = V.parse_vdecl(res, res.u64(vb["off"] + 0x38))
            if not vd:
                continue
            pos = V.read_element(res, vb["data"], vd, 0)
            if not pos:
                continue
            nrm = V.read_element(res, vb["data"], vd, 4) if vd["types"][4] else []
            nrm = [((v[0] / 1023.0) * 2 - 1, (v[1] / 1023.0) * 2 - 1, (v[2] / 1023.0) * 2 - 1)
                   if len(v) >= 3 else (0, 0, 1) for v in nrm]
            if len(nrm) < len(pos):
                nrm += [(0, 0, 1)] * (len(pos) - len(nrm))
            uv = V.read_element(res, vb["data"], vd, 28) if vd["types"][28] else []
            if len(uv) < len(pos):
                uv += [[0.0, 0.0]] * (len(pos) - len(uv))
            idx = Y.read_indices(res, ib) if ib else []
            if not idx:
                continue
            sid = shmap[gi] if gi < len(shmap) else 0
            params = WT.params_of(shaders[sid]) if 0 <= sid < len(shaders) else {}
            out.append(dict(pos=pos, nrm=nrm, uv=uv, idx=idx, params=params))
    return out


# ---------------------------------------------------------------- 纹理落盘
def save_tex(arr, name):
    os.makedirs(TEXOUT, exist_ok=True)
    p = os.path.join(TEXOUT, name)
    # 无条件覆盖：烘焙公式改过之后，同名文件如果还留着旧内容（以前是纯白）就会看着"没贴图"
    Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).save(p)
    return "textures/" + name


def normal_of(params, size=512):
    """把 lyr0normal 按 UV 空间重采样成一张法线图（没有就返回 None）"""
    nm = WT._tex(params.get("lyr0normaltex"))
    if nm is None:
        nm = WT._tex(params.get("bumptex"))
    if nm is None:
        return None
    u = (np.arange(size) + 0.5) / size
    U, V = np.meshgrid(u, u)
    return WT._sample(nm, U, V)[..., :3]


# ---------------------------------------------------------------- 写 glTF
class Bin:
    def __init__(self):
        self.buf = bytearray()

    def add(self, data, align=4):
        while len(self.buf) % align:
            self.buf.append(0)
        off = len(self.buf)
        self.buf += data
        return off


def write_gltf(base, geoms, path):
    bw = Bin()
    gl = dict(asset=dict(version="2.0", generator="rdr2_weapon_tint"),
              scene=0, scenes=[dict(nodes=[])],
              nodes=[], meshes=[], materials=[], accessors=[], bufferViews=[],
              buffers=[dict(byteLength=0, uri=os.path.basename(path).replace(".gltf", ".bin"))])
    a = -0.7853981633974483
    gl["nodes"].append(dict(name="RDR2_Zup", rotation=[np.sin(a), 0.0, 0.0, np.cos(a)], children=[]))
    gl["scenes"][0]["nodes"] = [0]
    gl.setdefault("images", [])
    gl.setdefault("textures", [])
    gl.setdefault("samplers", [dict(magFilter=9729, minFilter=9987, wrapS=10497, wrapT=10497)])

    def add_acc(vals, comps, typ, with_minmax=True):
        flat = [c for v in vals for c in v]
        off = bw.add(struct.pack("<%df" % len(flat), *flat))
        gl["bufferViews"].append(dict(buffer=0, byteOffset=off,
                                      byteLength=len(flat) * 4, target=34962))
        acc = dict(bufferView=len(gl["bufferViews"]) - 1, componentType=5126,
                   count=len(vals), type=typ)
        if with_minmax:
            mn = [min(v[i] for v in vals) for i in range(comps)]
            mx = [max(v[i] for v in vals) for i in range(comps)]
            acc["min"] = mn
            acc["max"] = mx
        gl["accessors"].append(acc)
        return len(gl["accessors"]) - 1

    def tex_index(uri, srgb=False):
        gl["images"].append(dict(uri=uri))
        gl["textures"].append(dict(source=len(gl["images"]) - 1, sampler=0))
        return len(gl["textures"]) - 1

    prims = []
    for g in geoms:
        params = g["params"]
        alb = WT.bake_albedo(params)
        h = hashlib.md5(WT.key_of(params).encode("utf-8")).hexdigest()[:10]
        is_wood = WT._tex(params.get("albedopalettetex")) is not None
        uri_ab = save_tex(alb, "wt_%s_ab.png" % h)
        mat = dict(name=("wood_" if is_wood else "metal_") + h, doubleSided=True,
                   pbrMetallicRoughness=dict(
                       # 金属必须"有金属度 + 低粗糙度"才像金属；以前 0.15/0.45 是
                       # 纯漫反射灰，看起来就是水泥。木料保持非金属、高粗糙。
                       metallicFactor=0.0 if is_wood else 0.62,
                       roughnessFactor=0.78 if is_wood else 0.30,
                       baseColorTexture=dict(index=tex_index(uri_ab))))
        nmarr = normal_of(params)
        if nmarr is not None:
            uri_nm = save_tex(nmarr, "wt_%s_nm.png" % h)
            mat["normalTexture"] = dict(index=tex_index(uri_nm))
        gl["materials"].append(mat)
        m_id = len(gl["materials"]) - 1

        pos = g["pos"]
        nrm = g["nrm"]
        uv = [(u[0], 1.0 - u[1]) for u in g["uv"]]
        a_pos = add_acc(pos, 3, "VEC3")
        a_nrm = add_acc(nrm, 3, "VEC3")
        a_uv = add_acc(uv, 2, "VEC2", with_minmax=False)
        wide = len(pos) > 65535
        data = struct.pack(("<%dI" if wide else "<%dH") % len(g["idx"]), *g["idx"])
        off = bw.add(data, 4)
        gl["bufferViews"].append(dict(buffer=0, byteOffset=off, byteLength=len(data), target=34963))
        gl["accessors"].append(dict(bufferView=len(gl["bufferViews"]) - 1,
                                    componentType=5125 if wide else 5123,
                                    count=len(g["idx"]), type="SCALAR"))
        prims.append(dict(attributes=dict(POSITION=a_pos, NORMAL=a_nrm, TEXCOORD_0=a_uv),
                          indices=len(gl["accessors"]) - 1, material=m_id))

    gl["meshes"].append(dict(name=base, primitives=prims))
    gl["nodes"].append(dict(name=base, mesh=0, translation=[0, 0, 0],
                            rotation=[0, 0, 0, 1], scale=[1, 1, 1]))
    gl["nodes"][0]["children"].append(len(gl["nodes"]) - 1)
    gl["buffers"][0]["byteLength"] = len(bw.buf)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path.replace(".gltf", ".bin"), "wb") as f:
        f.write(bytes(bw.buf))
    json.dump(gl, open(path, "w", encoding="utf-8"), separators=(",", ":"))
    return len(prims)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    idx = ASM.build_index()
    ok = 0
    for base, parts in sorted(idx.items()):
        mainp = parts.get("main")
        if not mainp:
            continue
        if only and base not in only:
            continue
        paths = [mainp]
        for cname in ASM.pick_parts(base, parts):
            p = os.path.join(ASM.SRC, base + "_" + cname + ".ydr")
            if not os.path.exists(p):
                continue
            if cname == "barrel1":
                # 只有"主体真缺管"时才装（同 export_weapon_assembled 的判据）
                mx = max(v[0] for g in load_geoms(paths[0]) for v in g["pos"])
                bm = max(v[0] for g in load_geoms(p) for v in g["pos"])
                if bm - mx <= 0.12:
                    continue
            paths.append(p)
        geoms = []
        for p in paths:
            geoms += load_geoms(p)
        if not geoms:
            continue
        n = write_gltf(base, geoms, os.path.join(a.out, base + ".gltf"))
        ok += 1
        print("OK  %-40s prims=%d" % (base, n), flush=True)
    print("done", ok)


if __name__ == "__main__":
    main()
