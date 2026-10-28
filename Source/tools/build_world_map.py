"""组装 `export/levels/world/world_map.html`（见 world_map.template.html 顶部说明）。

底图 = **官方 mapzones.meta 栅格化**（陆地 = STATE 并集 / 水体 = 官方 35 个水体多边形），
不再使用 `heightmap.dat`（经判据证实它不是世界高程）。

用法：uv run python tools/build_world_map.py
"""
import os
import io
import glob
import json
import base64

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TER = os.path.join(ROOT, 'export/levels/terrain')
WORLD = os.path.join(ROOT, 'export/levels/world')
TOWN = os.path.join(ROOT, 'export/levels/town')
TPL = os.path.join(ROOT, 'tools/world_map.template.html')
OUT = os.path.join(WORLD, 'world_map.html')

N = 512        # 显示用网格（源为 768×768，见下）
SRC_N = 768    # ★ 真实世界高度图是 768×768（文件里存成 1536² 的 2×2 平铺）


def rasterize_official(size=2048, ext=None):
    """把**官方几何**栅格化成底图 PNG（不再用 heightmap.dat —— 已证实它不是世界高程）。

    图层顺序：背景 → 陆地(STATE 并集) → 水体(35 个官方水体多边形) → 地区细线 → 州界粗线
    返回 (png_bytes, extent[x0,y0,x1,y1])
    """
    from PIL import Image, ImageDraw
    z = json.load(open(os.path.join(WORLD, 'zones.json'), encoding='utf-8'))['zones']
    land = [a for a in z if a['type'] == 'STATE']
    wat = [a for a in z if a['type'] in ('LAKE', 'RIVER', 'CREEK', 'POND', 'OCEAN', 'SWAMP')]
    dis = [a for a in z if a['type'] == 'DISTRICT']
    reg = [a for a in z if a['type'] in ('REGION', 'TOWN')]
    xs, ys = [], []
    for a in z:
        xs += [a['bbox'][0], a['bbox'][2]]
        ys += [a['bbox'][1], a['bbox'][3]]
    if ext:
        x0, y0, x1, y1 = ext          # ★ 用真地形的 extent，保证底图与地形网格逐像素对齐
    else:
        pad = int((max(xs) - min(xs)) * 0.03)
        x0, x1 = min(xs) - pad, max(xs) + pad
        y0, y1 = min(ys) - pad, max(ys) + pad
    W = size
    H = int(round(W * (y1 - y0) / (x1 - x0)))
    im = Image.new('RGB', (W, H), (24, 33, 43))          # 界外（深色，不是水）
    dr = ImageDraw.Draw(im)

    def P(px, py):
        return ((px - x0) / (x1 - x0) * W, H - (py - y0) / (y1 - y0) * H)

    for a in land:                                        # 陆地
        for poly in a['polygons']:
            if len(poly) >= 3:
                dr.polygon([P(*q) for q in poly], fill=(208, 192, 155))
    for a in wat:                                         # 水体（官方）
        for poly in a['polygons']:
            if len(poly) >= 3:
                dr.polygon([P(*q) for q in poly], fill=(126, 152, 168))
    for a in dis:                                         # 地区细线
        for poly in a['polygons']:
            if len(poly) >= 3:
                dr.line([P(*q) for q in poly] + [P(*poly[0])], fill=(150, 142, 120), width=2)
    for a in reg:
        for poly in a['polygons']:
            if len(poly) >= 3:
                dr.line([P(*q) for q in poly] + [P(*poly[0])], fill=(160, 150, 126), width=1)
    for a in land:                                        # 海岸线（压在最后，最清晰）
        for poly in a['polygons']:
            if len(poly) >= 3:
                dr.line([P(*q) for q in poly] + [P(*poly[0])], fill=(150, 130, 85), width=5)
    buf = io.BytesIO()
    im.save(buf, 'PNG', optimize=True)
    return buf.getvalue(), [x0, y0, x1, y1]


def earclip(poly):
    n = len(poly)
    if n < 3:
        return []
    idx = list(range(n))

    def a2(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    sgn = 1 if sum(a2(poly[i], poly[(i + 1) % n], poly[(i + 2) % n]) for i in range(n)) >= 0 else -1
    tris, guard = [], 0
    while len(idx) > 3 and guard < 5000:
        guard += 1
        cut = False
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = poly[i0], poly[i1], poly[i2]
            if sgn * a2(a, b, c) <= 0:
                continue
            ok = True
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                p = poly[j]
                if sgn * a2(a, b, p) >= 0 and sgn * a2(b, c, p) >= 0 and sgn * a2(c, a, p) >= 0:
                    ok = False
                    break
            if ok:
                tris += [i0, i1, i2]
                idx.pop(k)
                cut = True
                break
        if not cut:
            return []
    if len(idx) == 3:
        tris += idx
    return tris


def pack_l2(src_json, out_js, code, hpatch=None):
    """把 town_textured.json 打成**量化二进制** L2 包（体积约为原 JSON 的 45%）。

    positions → 模型 bbox 内归一化的 u16；uv → u16；indices → u16/u32；全部 base64。
    这样浏览器端只需 base64→TypedArray 解码，**不用 JSON.parse 几百万个数字**
    （那才是加载慢的主因）。veg/terrain 子集不打包（世界地图里用不到）。
    """
    import numpy as np
    d = json.load(open(src_json, encoding='utf-8'))
    out = {'tex': d['tex'], 'tex_names': d['tex_names'], 'insts': d['insts'],
           'center': d.get('center'), 'models': {}}
    for name, M in d['models'].items():
        p = np.asarray(M['p'], dtype='float32').reshape(-1, 3)
        pmin = p.min(0); psc = np.maximum(p.max(0) - pmin, 1e-6)
        q = np.clip(np.round((p - pmin) / psc * 65535.0), 0, 65535).astype('<u2')
        uv = np.asarray(M['uv'], dtype='float32')
        uvq = np.clip(np.round(uv * 65535.0), 0, 65535).astype('<u2')
        idx = np.asarray(M['i'], dtype=np.uint32)
        i32 = 1 if M['vc'] > 65535 else 0
        idb = (idx.astype('<u4') if i32 else idx.astype('<u2')).tobytes()
        out['models'][name] = {
            'vc': M['vc'], 'tc': M['tc'],
            'pmin': [round(float(v), 3) for v in pmin],
            'psc': [round(float(v), 3) for v in psc],
            'pp': base64.b64encode(q.tobytes()).decode(),
            'uv': base64.b64encode(uvq.tobytes()).decode(),
            'i': base64.b64encode(idb).decode(), 'i32': i32, 'g': M['g']}
    if hpatch and os.path.exists(hpatch):
        out['hp'] = json.load(open(hpatch, encoding='utf-8'))
    txt = ('window.RDR2_L2=window.RDR2_L2||{};window.RDR2_L2['
           + json.dumps(code) + ']=' + json.dumps(out, separators=(',', ':')) + ';')
    open(out_js, 'w', encoding='utf-8').write(txt)
    nv = sum(m['vc'] for m in out['models'].values())
    print(f'L2 {code}: {len(out["models"])} 型 / {len(out["insts"])} 实例 / {nv} 顶点 '
          f'-> {os.path.getsize(out_js)/1048576:.1f} MB')


def pack_l2_chunks(chunk_dir, out_dir, code, qmodel=None):
    """把分块 L2（chunks/tex.json + chunks/c*.json）量化打包成 l2/<code>/。

    * `tex.js`   = 共享贴图 + 精地形 + 分块参数 + **每块字节数清单**（供查看器做内存预算）
    * `c<k>.js`  = 该块自己的模型 + 实例（贴图索引指向共享 tex_names）
    """
    import numpy as np
    os.makedirs(out_dir, exist_ok=True)
    T = json.load(open(os.path.join(chunk_dir, 'tex.json'), encoding='utf-8'))

    def qm(M):
        p = np.asarray(M['p'], dtype='float32').reshape(-1, 3)
        pmin = p.min(0); psc = np.maximum(p.max(0) - pmin, 1e-6)
        q = np.clip(np.round((p - pmin) / psc * 65535.0), 0, 65535).astype('<u2')
        uv = np.asarray(M['uv'], dtype='float32')
        uvq = np.clip(np.round(uv * 65535.0), 0, 65535).astype('<u2')
        idx = np.asarray(M['i'], dtype=np.uint32)
        i32 = 1 if M['vc'] > 65535 else 0
        idb = (idx.astype('<u4') if i32 else idx.astype('<u2')).tobytes()
        return {'vc': M['vc'], 'tc': M['tc'],
                'pmin': [round(float(v), 3) for v in pmin],
                'psc': [round(float(v), 3) for v in psc],
                'pp': base64.b64encode(q.tobytes()).decode(),
                'uv': base64.b64encode(uvq.tobytes()).decode(),
                'i': base64.b64encode(idb).decode(), 'i32': i32, 'g': M['g']}

    files = sorted(glob.glob(os.path.join(chunk_dir, 'c*.json')))
    sizes = {}
    tot = 0
    for fp in files:
        D = json.load(open(fp, encoding='utf-8'))
        k0, k1 = D['key']
        key = f'{k0}_{k1}'
        out = {'models': {n: qm(m) for n, m in D['models'].items()},
               'insts': D['insts'], 'key': D['key'], 'chunk': D['chunk'], 'center': D['center']}
        txt = ('window.RDR2_L2C=window.RDR2_L2C||{};window.RDR2_L2C['
               + json.dumps(code + ':' + key) + ']=' + json.dumps(out, separators=(',', ':')) + ';')
        dst = os.path.join(out_dir, 'c' + key + '.js')
        open(dst, 'w', encoding='utf-8').write(txt)
        sizes[key] = os.path.getsize(dst)
        tot += sizes[key]
    T['sizes'] = sizes
    txt = ('window.RDR2_L2TEX=window.RDR2_L2TEX||{};window.RDR2_L2TEX['
           + json.dumps(code) + ']=' + json.dumps(T, separators=(',', ':')) + ';')
    open(os.path.join(out_dir, 'tex.js'), 'w', encoding='utf-8').write(txt)
    print(f'L2 分块 {code}: {len(files)} 块 / {tot/1048576:.0f} MB + tex.js '
          f'{os.path.getsize(os.path.join(out_dir,"tex.js"))/1048576:.1f} MB')


def build_zones():
    """只保留**线 + 标签**需要的多边形（fill 已经烘进底图 PNG，不再前端重画）。"""
    z = json.load(open(os.path.join(WORLD, 'zones.json'), encoding='utf-8'))['zones']
    keep = {'STATE', 'DISTRICT', 'REGION', 'TOWN'}
    flat = []
    for zz in z:
        if zz['type'] not in keep:
            continue
        polys = [p for p in zz['polygons'] if len(p) >= 3]
        if polys:
            flat.append({'n': zz['name'], 'ty': zz['type'], 'b': zz['bbox'],
                         'cx': zz['cx'], 'cy': zz['cy'], 'p': polys})
    return flat


def main():
    th_path = os.path.join(WORLD, 'terrain_h.json')
    th_png = os.path.join(WORLD, 'terrain_h.png')
    if not (os.path.exists(th_path) and os.path.exists(th_png)):
        raise SystemExit('缺少 terrain_h.png / terrain_h.json —— 先跑 tools/build_terrain_heightmap.py')
    th = json.load(open(th_path, encoding='utf-8'))
    ext = [th['x0'], th['y0'], th['x1'], th['y1']]
    terh_b64 = base64.b64encode(open(th_png, 'rb').read()).decode()
    print(f"真地形 {th['W']}×{th['H']} 高程 {th['zmin']:.0f}~{th['zmax']:.0f} m "
          f"({os.path.getsize(th_png)/1048576:.2f} MB)")
    png, ext = rasterize_official(2048, ext)
    print(f'底图 PNG {len(png)/1024:.0f} KB  extent={ext}')
    b64 = base64.b64encode(png).decode()
    map_img = 'data:image/png;base64,' + b64
    x0, y0, x1, y1 = ext
    dx = {'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1}
    zones = build_zones()
    towns = json.load(open(os.path.join(WORLD, 'towns.json'), encoding='utf-8'))['towns']
    # ★ 取景修正：少数据点的 ymap 组只覆盖一个小角落（如 sdn 只有 29×102 m），
    #   用**官方 zone 的包围盒**覆盖，否则相机飞到错的地方、看不到整座城
    zmap = {}
    for z in json.load(open(os.path.join(WORLD, 'zones.json'), encoding='utf-8'))['zones']:
        zmap[z['name'].lower()] = z
    FIX = {'sdn': 'stdenis', 'rho': 'rhodes', 'arm': 'armadillo', 'tum': 'tumbleweed',
           'bla': 'blackwater', 'ann': 'annesburg', 'str': 'strawberry', 'val': 'valentine',
           'eme': 'emerald', 'lag': 'lagras', 'van': 'vanhorn', 'wap': 'wapiti'}
    nfix = 0
    for t in towns:
        z = zmap.get(FIX.get(t['code'], ''))
        if not z:
            continue
        b = z['bbox']                      # [x0,y0,x1,y1]
        w, h = b[2] - b[0], b[3] - b[1]
        if w > (t['bbox'][3] - t['bbox'][0]) and h > (t['bbox'][4] - t['bbox'][1]):
            t['bbox'] = [b[0], b[1], t['bbox'][2], b[2], b[3], t['bbox'][5]]
            t['cx'], t['cy'] = z['cx'], z['cy']
            nfix += 1
    if nfix:
        print(f'取景修正（用官方 zone 覆盖）: {nfix} 个据点')
    # ★ 把**具名据点**的实体整包内嵌（仅 3 MB / 3.3 万实体），让 HTML 真正单文件可用；
    #   区域网格（15 万实体，很少点）仍走外部 town_data/，加载失败时可让用户选文件夹兜底
    builtin = {}
    for t in towns:
        if t['grid']:
            continue
        fp = os.path.join(WORLD, 'town_data', t['code'] + '.js')
        if not os.path.exists(fp):
            continue
        txt = open(fp, encoding='utf-8').read()
        builtin[t['code']] = json.loads(txt.split(']=', 1)[1].rstrip().rstrip(';'))
    bjs = json.dumps(builtin, separators=(',', ':')).replace('</', '<' + chr(92) + '/')
    print(f'内嵌具名据点 {len(builtin)} 个 / {sum(len(v) for v in builtin.values())} 实体 '
          f'({len(bjs)/1048576:.2f} MB)')
    three = open(os.path.join(TOWN, 'three.module.js'), encoding='utf-8').read()
    three = three.replace('</script', '<' + chr(92) + '/script')

    tpl = open(TPL, encoding='utf-8').read()
    html = tpl.replace('__THREE__', three)
    html = html.replace('__BUILTIN__', bjs)
    html = html.replace('__MAPIMG__', map_img)
    html = html.replace('__TERHIMG__', 'data:image/png;base64,' + terh_b64)
    html = html.replace('__TERHMETA__', json.dumps(
        {k: round(th[k], 3) if isinstance(th[k], float) else th[k]
         for k in ('W', 'H', 'x0', 'y0', 'x1', 'y1', 'zmin', 'zmax')},
        separators=(',', ':')))
    html = html.replace('__TER__', json.dumps(dx, separators=(',', ':')))
    html = html.replace('__ZONES__', json.dumps(zones, separators=(',', ':'), ensure_ascii=False))
    html = html.replace('__TOWNS__', json.dumps({'towns': towns}, separators=(',', ':'),
                                                ensure_ascii=False))
    w_km = (x1 - x0) / 1000.0
    h_km = (y1 - y0) / 1000.0
    html = html.replace('__TERS__', f'{w_km:.1f}×{h_km:.1f} km · 真地形 30697 patch · 底图 2048px 官方几何')
    html = html.replace('__NZ__', str(len(zones)))
    html = html.replace('__NT__', str(len([t for t in towns if not t['grid']])))
    # ---- L2：真模型（懒加载，量化二进制打包）----
    l2dir = os.path.join(WORLD, 'l2')
    os.makedirs(l2dir, exist_ok=True)
    L2_SRC = {'val': (os.path.join(TOWN, 'town_textured.json'), os.path.join(ROOT, 'work/val/hpatch.json')),
              'ann': (os.path.join(ROOT, 'work/ann/town.json'), os.path.join(ROOT, 'work/ann/hpatch.json'))}
    for code, (src, hp) in L2_SRC.items():
        if os.path.exists(src):
            pack_l2(src, os.path.join(l2dir, code + '.js'), code, hp)
        else:
            print(f'L2 {code}: 缺 {src}（跳过）')
    # 分块流式的据点（圣丹尼斯）
    ch = os.path.join(ROOT, 'work/sdn/chunks')
    if os.path.isdir(ch):
        pack_l2_chunks(ch, os.path.join(l2dir, 'sdn'), 'sdn')

    os.makedirs(WORLD, exist_ok=True)
    open(OUT, 'w', encoding='utf-8').write(html)
    print(f'-> {OUT}  ({os.path.getsize(OUT)/1048576:.2f} MB)')
    print(f'   zones {len(zones)} · settlements '
          f'{len([t for t in towns if not t["grid"]])} (+{len([t for t in towns if t["grid"]])} grid)')


if __name__ == '__main__':
    main()
