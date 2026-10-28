"""圣丹尼斯 · 室内（MLO）导出：30 个室内包 → glTF（带贴图，按 MLO 实体位置摆放）。

RDR2 的室内不是"建筑模型的一部分"，而是独立的 `levels/rdr3/interiors/new_*_int.rpf`：
  * 里面的 `.ydr` 是**房间/家具/细节**，全部建模在 **MLO 局部坐标**（原点 = 室内原点）
  * 摆放位置来自 ymap 里 archetype == `new_com_bank_int` 这类 **MLO 实体**（位置+旋转）
⇒ 把该包所有 ydr 作为同一个 MLO 变换下的实例导出，就自动"落"进对应建筑里。

用法：
  uv run python tools/export_sdn_interiors.py --out export/levels/world/gltf/sdn_interiors
"""
import os
import sys
import glob
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import export_sdn_gltf as G

ROOT = r'D:/BrainMaker/大镖客2解包分析'
INT_ROOT = os.path.join(ROOT, 'work/sdn/int')

# 室内包里这些不是"看得见的房间"：反射代理、阴影代理、碰撞替身、假窗遮挡
SKIP = ('proxy', 'shadow', 'dummy', 'collisionswap', 'refle', '_dcl', '+hidr', 'blocker')


def mlo_transforms():
    """→ {interior_name: (x,y,z,qx,qy,qz,qw)}"""
    import ymap_entities
    packs = [os.path.splitext(os.path.basename(p))[0]
             for p in glob.glob(os.path.join(INT_ROOT, '*')) if os.path.isdir(p)]
    h2n = {G.joaat(n): n for n in packs}
    out = {}
    files = sorted(glob.glob(os.path.join(ROOT, 'export/levels/map_metadata/**/*.ymap'),
                              recursive=True))
    for f in files:
        try:
            _s, _z, es = ymap_entities.extract(f)
        except Exception:
            continue
        for e in es:
            n = h2n.get(e[0])
            if n and n not in out:
                out[n] = (e[1], e[2], e[3], e[4], e[5], e[6], e[7])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(
        ROOT, 'export/levels/world/gltf/sdn_interiors'))
    ap.add_argument('--maxs', type=int, default=512)
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    tex_uri = os.path.join(os.path.dirname(out), 'sdn', 'textures')
    os.makedirs(tex_uri, exist_ok=True)

    tex_dirs = [os.path.join(ROOT, 'work/sdn/gtxd/txd'),
                os.path.join(ROOT, 'work/sdn/gtxd/txd_int'),
                os.path.join(ROOT, 'work/sdn/models')]
    tl = G.TexLib(tex_dirs, a.maxs)
    print('贴图库', len(tl.idx), '名')
    mlo = mlo_transforms()
    print('MLO 实体位置', len(mlo), '个')

    manifest = {}
    for d in sorted(glob.glob(os.path.join(INT_ROOT, '*'))):
        if not os.path.isdir(d):
            continue
        name = os.path.basename(d)
        files = [f for f in glob.glob(os.path.join(d, '*.ydr'))
                 if not any(s in os.path.basename(f).lower() for s in SKIP)]
        models = {}
        for f in files:
            n = os.path.splitext(os.path.basename(f))[0]
            M = G.load_model(f)
            if M:
                models[n] = M
        if not models:
            print(f'  {name}: 无可用网格')
            continue
        t = mlo.get(name)
        # 只把"在圣丹尼斯城里"的室内放进主场景；城外的（帮派窝点）/没位置的放 unplaced/
        city = False
        if t:
            dx, dy = t[0] - 2555.0, t[1] + 1151.0
            city = (dx * dx + dy * dy) < 760.0 * 760.0
        if city:
            insts = [[n, t[0], t[1], t[2], t[3], t[4], t[5], t[6], 1, 1, 1] for n in models]
            p = os.path.join(out, name + '.gltf')
        else:
            insts = [[n, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1] for n in models]
            os.makedirs(os.path.join(out, 'unplaced'), exist_ok=True)
            p = os.path.join(out, 'unplaced', name + '.gltf')
        G.write_tile(p, models, insts, tl, tex_uri, None)
        vt = sum(len(g['pos']) for m in models.values() for g in m['geoms'])
        manifest[name] = dict(pos=t, in_city=city, meshes=len(models), verts=vt,
                              file=os.path.relpath(p, out).replace(os.sep, '/'))
        print(f'  {name}: {len(models)} 网格 {vt} 顶点 '
              f'{"@ " + str([round(x,1) for x in t[:3]]) if t else "(无位置)"}{"" if city else "  -> unplaced"}')
    json.dump(manifest, open(os.path.join(out, 'manifest.json'), 'w'),
              ensure_ascii=False, indent=1)
    print('->', out)


if __name__ == '__main__':
    main()
