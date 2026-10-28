# -*- coding: utf-8 -*-
"""载具（.yft fragment）→ glTF 导出，供 HTML 查看器使用。

## 为什么单独写一个
`export_prop_gltf.py` 走的是 `export_sdn_gltf.load_model()`，那个函数假设
**`.ydr` 布局**（shader_group 直接在 0x10）。载具是 **`.yft`**：
fragment 头里若干指针才指向真正的 Drawable（`rdr2_ydr.extract_frag` 已在用同样的探测法）。
所以这里把 `load_model` 的逻辑复制一份，但 **base 由探测得到**。

## 输入 / 输出
  raw/vehicles/out/*.yft          ← `rdr2rpf extract` 出来的载具包（662 个文件）
  export/viewer/models/vehicles/  ← <name>.gltf + .bin + textures/*.png

用法：
  uv run python tools/export_vehicle_gltf.py --names gatling_gun,boatsteam02x
  uv run python tools/export_vehicle_gltf.py --all
"""
import os
import sys
import json
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import rdr2_ydr as Y            # noqa: E402
import export_sdn_gltf as G     # noqa: E402

SRC = os.path.join(ROOT, "raw/vehicles/out")
OUT = os.path.join(ROOT, "export/viewer/models/vehicles")

ROLE_ALBEDO = {"albedo", "albedo2", "diffuse", "diffusetex"}


class PaintTexLib:
    """包一层 TexLib：把载具的 `*_control`（涂装控制图）烘成可看的"素色车漆"。

    ## 为什么
    RDR2 载具车体走 `standard_vehicle_2lyr`：`lyr0diffusetex` 取到的是
    `policeWagon01x_Body_control`——它**不是 albedo**，而是
    (R=车漆覆盖/G=层混合/B=×) 的控制图（实测均色 RGB 127,121,22，直接当颜色就是一片黄绿）。
    真正的车漆色来自 `tintpalettetex`（`Generic_skinned_pal`）+ `carcols.ymt` / `carvariations.ymt`。

    这一步只做**最小可信近似**：用控制图亮度当明暗，乘一个中性深灰车漆色，
    让车体看起来像"未上漆/中性漆面的车"，而不是荧光黄绿。
    真实涂装色仍未还原——已在页面与文档里标注，不冒充。
    """

    PAINT = (0.30, 0.33, 0.31)   # 中性深灰绿（不指向任何具体车型配色）

    def __init__(self, texlib):
        self.t = texlib
        self.baked = 0

    def get(self, name, hint=None):
        if name and ('control' in name.lower() or name.lower().endswith('_ct')):
            im, _ = self.t.get(name, hint)
            if im is None:
                return None, None
            from PIL import Image
            g = im.convert('L')
            px = g.load()
            out = Image.new('RGB', g.size)
            op = out.load()
            pr, pg, pb = self.PAINT
            w, h = g.size
            for y in range(h):
                for x in range(w):
                    l = px[x, y] / 255.0
                    k = 0.55 + 0.85 * l
                    op[x, y] = (min(255, int(pr * 255 * k)),
                                min(255, int(pg * 255 * k)),
                                min(255, int(pb * 255 * k)))
            self.baked += 1
            return out, 'paint'
        return self.t.get(name, hint) if self.t is not None else (None, None)



def find_drawable_base(res):
    """在 .yft 里探测 Drawable 的偏移（与 rdr2_ydr.extract_frag 同一套指针）。"""
    best = None
    for off in (0x20, 0x08, 0x40, 0x70, 0x90, 0x28, 0x48):
        try:
            v = res.u64(off)
        except Exception:
            continue
        o = res.off(v)
        if o is None:
            continue
        try:
            tris = 0
            for mo in Y.pointer_list(res, res.u64(o + 0x50)):
                for gp in Y.parse_model_geoms(res, mo):
                    g = Y.parse_geometry(res, gp)
                    if g and g.get('ib'):
                        tris += len(Y.read_indices(res, g['ib'])) // 3
        except Exception:
            continue
        if tris and (best is None or tris > best[0]):
            best = (tris, o)
    return best[1] if best else None


def load_frag_model(path):
    """→ dict(geoms=[{pos,nrm,uv,idx,tex,shader}], ytd=..., base=...) 或 None"""
    try:
        res = Y.Res(open(path, 'rb').read())
    except Exception:
        return None
    base = find_drawable_base(res)
    if base is None:
        return None
    base_dir = os.path.dirname(path)
    nm = os.path.splitext(os.path.basename(path))[0]
    hint = None
    for cand in (nm + '+hi.ytd', nm + '.ytd', nm.replace('_hi', '') + '+hi.ytd',
                 nm.replace('_hi', '') + '.ytd'):
        if os.path.exists(os.path.join(base_dir, cand)):
            hint = os.path.join(base_dir, cand)
            break
    sg = res.u64(base + 0x10)
    shaders = Y.parse_shader_group(res, sg)
    shd = Y.parse_shader_hashes(res, sg)
    geoms = []
    for mo in Y.pointer_list(res, res.u64(base + 0x50)):
        gs = Y.parse_model_geoms(res, mo)
        shmap = Y.parse_model_shaders(res, mo, len(gs))
        for gi, gp in enumerate(gs):
            sid = shmap[gi] if gi < len(shmap) else 0
            g = G.read_geom(res, gp, sid)
            if not g:
                continue
            texs = shaders[sid] if 0 <= sid < len(shaders) else []
            alb = None
            for t in texs:
                if (t.get('role') or '') in ROLE_ALBEDO and t.get('name') \
                        and not t['name'].lower().startswith('blank'):
                    alb = t
                    break
            if alb is None:
                cand = [t for t in texs if t.get('name')
                        and not t['name'].lower().startswith('blank')
                        and t.get('role') not in ('normal', 'material', 'materialA',
                                                  'materialB', 'palette', 'lookup',
                                                  'control', 'detail', '')]
                if cand:
                    alb = max(cand, key=lambda t: t['w'] * t['h'])
            g['tex'] = alb['name'] if alb else None
            g['shader'] = shd[sid]['name'] if 0 <= sid < len(shd) else None
            geoms.append(g)
    if not geoms:
        return None
    return dict(geoms=geoms, ytd=hint, base=base)


def convert(name, texlib=None, tex_uri=None, out_dir=OUT):
    src = os.path.join(SRC, name + ".yft")
    if not os.path.exists(src):
        # 允许带 _hi 的调用
        src = os.path.join(SRC, name + ".yft")
        if not os.path.exists(src):
            return None
    m = load_frag_model(src)
    if not m:
        return None
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, name + ".gltf")
    try:
        G.write_tile(out, {name: m}, [[name, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1]],
                     texlib or G.TexLib([]), tex_uri, None)
        return out
    except Exception as e:
        print("  FAIL", name, repr(e)[:160])
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", default="", help="逗号分隔的载具名（不含 .yft）")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-tex", action="store_true")
    a = ap.parse_args()

    if a.all:
        names = sorted(os.path.splitext(f)[0] for f in os.listdir(SRC)
                       if f.endswith(".yft") and not f.endswith("_hi.yft"))
    else:
        names = [n.strip() for n in a.names.split(",") if n.strip()]
    if not names:
        print("no names")
        return

    texlib = None
    tex_uri = None
    if not a.no_tex:
        print("building TexLib over", SRC, flush=True)
        texlib = PaintTexLib(G.TexLib([SRC], maxs=512))
        tex_uri = os.path.abspath(os.path.join(OUT, "textures"))
        os.makedirs(tex_uri, exist_ok=True)
        print("texlib", len(texlib.t.idx), flush=True)

    ok = []
    for i, n in enumerate(names):
        p = convert(n, texlib, tex_uri)
        if p:
            ok.append(n)
        if (i + 1) % 20 == 0:
            print(f"{i+1}/{len(names)} ok={len(ok)}", flush=True)
    print("done", len(ok), "/", len(names))
    print("missing:", [n for n in names if n not in ok][:20])


if __name__ == "__main__":
    main()
