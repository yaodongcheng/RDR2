"""把「街道道具」导出成 glTF 分块（支持 .ydr 与 .yft fragment）。

背景：RDR2 的街道道具大量是 `.yft`（fragment），我们此前只吃了 `.ydr`，所以街上空。
本脚本：
  1. 扫 `work/sdn/models`(城市) / `work/sdn/props`(p_new_01) / `work/sdn/props2/*`(30 个分类包)
  2. 按 ymap 实体名匹配（joaat）
  3. `.yft` 走 fragment 解析：找最“重”的 drawable（多个大件则合并），读 vdecl 取 POSITION/NORMAL/TEXCOORD0
  4. 复用 export_sdn_gltf 的 write_tile 输出 160 m 分块

用法：
  uv run python tools/export_sdn_props2.py --out export/levels/world/gltf/sdn_props2
"""
import os, sys, glob, json, argparse
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import export_sdn_gltf as G
import rdr2_ydr as Y

ROOT = r'D:/BrainMaker/大镖客2解包分析'


def pick_albedo(texs):
    for t in texs:
        if (t.get('role') or '') in G.ROLE_ALBEDO and t.get('name') and not t['name'].lower().startswith('blank'):
            return t['name']
    for t in texs:
        if t.get('role') == 'albedo2' and t.get('name'):
            return t['name']
    drop = ('normal', 'material', 'materialA', 'materialB', 'palette', 'lookup', 'control', 'detail', '')
    cand = [t for t in texs if t.get('name') and not t['name'].lower().startswith('blank')
            and t.get('role') not in drop]
    return max(cand, key=lambda t: t['w'] * t['h'])['name'] if cand else None


def load_drawable(res, base):
    """在给定 drawable base 上读几何（返回 geoms 列表）"""
    sg = res.u64(base + 0x10)
    shaders = Y.parse_shader_group(res, sg)
    shd = Y.parse_shader_hashes(res, sg)
    out = []
    for mo in Y.pointer_list(res, res.u64(base + 0x50)):
        gs = Y.parse_model_geoms(res, mo)
        shmap = Y.parse_model_shaders(res, mo, len(gs))
        for gi, gp in enumerate(gs):
            sid = shmap[gi] if gi < len(shmap) else 0
            g = G.read_geom(res, gp, sid)
            if not g:
                continue
            texs = shaders[sid] if 0 <= sid < len(shaders) else []
            g['tex'] = pick_albedo(texs)
            g['shader'] = shd[sid]['name'] if 0 <= sid < len(shd) else None
            out.append(g)
    return out


def load_frag_model(path):
    res = Y.Res(open(path, 'rb').read())
    cands = []
    for off in (0x20, 0x08, 0x40, 0x70, 0x90, 0x28, 0x48):
        try:
            v = res.u64(off)
        except Exception:
            continue
        o = res.off(v)
        if o is not None:
            cands.append(o)
    parts = []
    for base in cands:
        try:
            gs = load_drawable(res, base)
        except Exception:
            continue
        tris = sum(len(g['idx']) // 3 for g in gs)
        if tris:
            parts.append((tris, gs))
    if not parts:
        return None
    parts.sort(key=lambda t: -t[0])
    best = parts[0][0]
    geoms = []
    for tris, gs in parts:
        if tris >= max(30, best * 0.25):     # 合并大件（例如箱体 + 盖子），丢掉碎片/内部屑
            geoms += gs
    d = os.path.dirname(path); nm = os.path.splitext(os.path.basename(path))[0]
    hint = None
    for c in (nm + '+hidr.ytd', nm + '.ytd', nm + '+hi.ytd'):
        if os.path.exists(os.path.join(d, c)):
            hint = os.path.join(d, c); break
    return dict(geoms=geoms, ytd=hint)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'export/levels/world/gltf/sdn_props2'))
    ap.add_argument('--cx', type=float, default=2555.0)
    ap.add_argument('--cy', type=float, default=-1151.0)
    ap.add_argument('--bbox', default='2100,-1660,3010,-650')
    ap.add_argument('--chunk', type=float, default=160.0)
    ap.add_argument('--maxs', type=int, default=256)
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()

    dirs = [os.path.join(ROOT, 'work/sdn/props'), os.path.join(ROOT, 'work/sdn/models')] + \
           sorted(glob.glob(os.path.join(ROOT, 'work/sdn/props2', '*')))
    bypath = {}
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for f in glob.glob(os.path.join(d, '**', '*.ydr'), recursive=True) + \
                 glob.glob(os.path.join(d, '**', '*.yft'), recursive=True):
            n = os.path.splitext(os.path.basename(f))[0]
            if f.endswith('.ydr') or n not in bypath:
                bypath[n] = f
    print('模型文件', len(bypath), '（ydr %d / yft %d）' % (
        sum(1 for v in bypath.values() if v.endswith('.ydr')),
        sum(1 for v in bypath.values() if v.endswith('.yft'))))

    x0, y0, x1, y1 = [float(v) for v in a.bbox.split(',')]
    import ymap_entities
    hash2name = {G.joaat(n): n for n in bypath}
    seen = set(); insts = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'export/levels/map_metadata/**/*.ymap'), recursive=True)):
        try:
            _s, _z, es = ymap_entities.extract(f)
        except Exception:
            continue
        for e in es:
            if not (x0 <= e[1] <= x1 and y0 <= e[2] <= y1):
                continue
            nm = hash2name.get(e[0])
            if not nm:
                continue
            k = (e[0], round(e[1], 1), round(e[2], 1), round(e[3], 1))
            if k in seen:
                continue
            seen.add(k)
            insts.append([nm, e[1], e[2], e[3], e[4], e[5], e[6], e[7], e[8], e[8], e[9]])
    print('匹配实例', len(insts), '唯一模型', len({i[0] for i in insts}))

    # 同位置变体去重（保留基名）
    def base_of(n):
        b = n
        while G.VARIANT.search(b):
            b = G.VARIANT.sub('', b)
        return b
    groups = {}
    for it in insts:
        groups.setdefault((round(it[1], 1), round(it[2], 1), round(it[3], 1), base_of(it[0])), []).append(it)
    keep = []
    for g in groups.values():
        g.sort(key=lambda t: (1 if G.VARIANT.search(t[0]) else 0, len(t[0])))
        keep.append(g[0])
    insts = keep
    print('变体去重后', len(insts))

    tex_dirs = [os.path.join(ROOT, 'work/sdn/gtxd/txd'), os.path.join(ROOT, 'work/sdn/gtxd/txd_int')] + dirs
    tl = G.TexLib(tex_dirs, a.maxs)
    print('贴图库', len(tl.idx))

    used = sorted({i[0] for i in insts})
    if a.limit:
        used = used[:a.limit]
        insts = [i for i in insts if i[0] in set(used)]
    models = {}
    fail = 0
    for i, n in enumerate(used):
        f = bypath[n]
        M = G.load_model(f) if f.endswith('.ydr') else load_frag_model(f)
        if not M:
            fail += 1
            continue
        if all((g.get('shader') or '').lower() == 'default' for g in M['geoms']):
            fail += 1
            continue
        models[n] = M
        if (i + 1) % 300 == 0:
            print('  ... %d/%d' % (i + 1, len(used)))
    print('模型成功 %d / %d（失败/占位 %d），顶点 %d' % (
        len(models), len(used), fail,
        sum(len(g['pos']) for m in models.values() for g in m['geoms'])))

    insts = [i for i in insts if i[0] in models]
    cs = a.chunk
    buckets = defaultdict(list)
    for it in insts:
        buckets[(int((it[1] - a.cx) // cs), int((it[2] - a.cy) // cs))].append(it)
    out = os.path.abspath(a.out)
    tex_uri = os.path.join(out, 'textures')
    os.makedirs(tex_uri, exist_ok=True)
    tot = 0
    for (k0, k1), its in sorted(buckets.items()):
        p = os.path.join(out, 'tiles', 'c%d_%d.gltf' % (k0, k1))
        G.write_tile(p, models, its, tl, tex_uri, None)
        sz = os.path.getsize(p) + os.path.getsize(p.replace('.gltf', '.bin'))
        tot += sz
        print('  c%d_%d: %d inst  %.1f MB' % (k0, k1, len(its), sz / 1048576))
    print('-> %s  共 %d 块 %.1f MB' % (out, len(buckets), tot / 1048576))


if __name__ == '__main__':
    main()
