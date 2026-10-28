# -*- coding: utf-8 -*-
"""把武器/道具 YDR 批量转成 glTF（只导几何，不导贴图），供 HTML 查看器加载。

输出：export/viewer/models/<kind>/<base>.gltf + .bin
"""
import os, sys, glob, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import export_sdn_gltf as G
import rdr2_ytd as T

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DummyTex:
    def get(self, name, hint=None):
        return (None, None)


def add_normal_map(gltf_path, model, texlib, tex_uri):
    ytd = model.get("ytd")
    if not ytd or not os.path.exists(ytd):
        return
    try:
        y = T.Ytd(open(ytd, "rb").read())
    except Exception:
        return
    names = [t["name"] for t in y.textures() if t["name"]]
    cand = [n for n in names if n.endswith("_eg") or n.endswith("_n") or n.endswith("_nm")]
    if not cand:
        return
    nm = cand[0]
    im, diag = texlib.get(nm, ytd)
    if im is None:
        return
    fn = G.safe_fn(nm) + ".png"
    im.save(os.path.join(tex_uri, fn))
    try:
        d = json.load(open(gltf_path, encoding="utf-8"))
    except Exception:
        return
    idx = len(d.get("images", []))
    d.setdefault("images", []).append({"uri": "textures/" + fn})
    d.setdefault("samplers", []).append({"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497})
    d.setdefault("textures", []).append({"sampler": len(d["samplers"]) - 1, "source": idx})
    ti = len(d["textures"]) - 1
    for m in d.get("materials", []):
        m["normalTexture"] = {"index": ti}
    json.dump(d, open(gltf_path, "w", encoding="utf-8"), ensure_ascii=False)


def convert(src, out_dir, name, texlib=None, tex_uri=None):
    if not os.path.exists(src):
        return None
    out = os.path.join(out_dir, name + ".gltf")
    m = G.load_model(src)
    if not m:
        return None
    os.makedirs(out_dir, exist_ok=True)
    try:
        G.write_tile(out, {name: m}, [[name, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1]],
                     texlib or DummyTex(), tex_uri, None)
        if texlib is not None and tex_uri:
            add_normal_map(out, m, texlib, tex_uri)
        return out
    except Exception as e:
        print("FAIL", name, e)
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["weapons", "items"], required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tex", action="store_true")
    a = ap.parse_args()
    if a.kind == "weapons":
        files = sorted(glob.glob(os.path.join(ROOT, "export/weapons/models/*.ydr")))
        outroot = os.path.join(ROOT, "export/viewer/models/weapons")
    else:
        files = sorted(glob.glob(os.path.join(ROOT, "export/items/models/*/**/*.ydr"), recursive=True))
        outroot = os.path.join(ROOT, "export/viewer/models/items")
    if a.limit:
        files = files[:a.limit]
    texlib = None
    tex_uri = None
    if a.tex:
        dirs = [os.path.join(ROOT, "export/items/models")] if a.kind == "items" else [os.path.join(ROOT, "export/weapons/models")]
        print("building TexLib...", flush=True)
        texlib = G.TexLib(dirs, maxs=256)
        tex_uri = os.path.abspath(os.path.join(outroot, "textures"))
        os.makedirs(tex_uri, exist_ok=True)
        print("texlib", len(texlib.idx), "albedo", len(texlib._alb), flush=True)
    ok = 0
    for i, f in enumerate(files):
        name = os.path.splitext(os.path.basename(f))[0]
        if convert(f, outroot, name, texlib, tex_uri):
            ok += 1
        if (i + 1) % 50 == 0:
            print(f"{i+1}/{len(files)} ok={ok}", flush=True)
    print("done", ok, "/", len(files))


if __name__ == "__main__":
    main()
