"""RDR2 人物/NPC 模型导出器 —— `.ydd`(DrawableDictionary) → glTF(.glb) + 贴图 + 清单

## 为什么需要它

`rdr2_ydr.py` 面向建筑的 `.ydr`（单个 Drawable）；**人物是 `.ydd` = DrawableDictionary**
（一个文件里 11 个子 drawable：头/躯干/腿/帽/大衣…），且顶点是 **60 字节 stride 的 SOA 布局**，
带 `BLENDWEIGHTS / BLENDINDICES / TEXCOORD0`（见 `rdr2_vdecl.py`）。

本工具把一个人物导出成**引擎可直接导入**的 glTF：每个子 drawable = 一个 primitive，
各自带自己的 `ped_standard` 材质（albedo + normal 贴进 glTF；`_ma/_mb` 一并落盘备查）。

## 坐标系

RDR2 模型空间 = **Z 轴向上**（人物 bbox z ≈ 0 ~ 1.68 m）；glTF 要 Y-up。
转换：`gltf = (x, z, -y)`。

用法:
  uv run python tools/rdr2_npc_export.py --ydd <file.ydd> --tex <贴图目录> --out <outdir>
        [--name NAME] [--lod high] [--no-tex]
"""
import os
import re
import sys
import json
import struct
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rdr2_ydr as Y          # noqa: E402
import rdr2_vdecl as V        # noqa: E402
import ytd_to_png as TP       # noqa: E402


# ---------------------------------------------------------------- 几何读取

def _norm_snorm10(v):
    """R10G10B10A2 的 0..1023 → [-1,1]"""
    return v / 1023.0 * 2.0 - 1.0


def read_geom_attrs(res, g, lod='high'):
    """读一个 DrawableGeometry 的全部我们关心的属性。"""
    go = res.off(g)
    if go is None:
        return None
    vb = Y.parse_vertex_buffer(res, res.u64(go + 0x08))
    ib = Y.parse_index_buffer(res, res.u64(go + 0x10))
    if not vb:
        return None
    vd = V.parse_vdecl(res, res.u64(vb['off'] + 0x38))
    if not vd:
        return None
    n = vb['count']
    elems = {name: idx for idx, name, _f, _c, _o, _s in V.elements(vd)}

    def rd(name):
        i = elems.get(name)
        if i is None:
            return None
        return V.read_element(res, vb['data'], vd, i, limit=n)

    pos_raw = rd('POSITION')
    if not pos_raw:
        return None
    # RDR2(Z-up) -> glTF(Y-up): (x, z, -y)
    pos = []
    for p in pos_raw:
        pos.extend((p[0], p[2], -p[1]))

    nrm_raw = rd('NORMAL')
    nrm = []
    if nrm_raw:
        for v in nrm_raw:
            nrm.extend((_norm_snorm10(v[0]), _norm_snorm10(v[1]), _norm_snorm10(v[2])))

    uv_raw = rd('TEXCOORD0')
    uv = []
    if uv_raw:
        for v in uv_raw:
            uv.extend((v[0], v[1]))

    tan_raw = rd('TANGENT')
    tan = []
    if tan_raw:
        for v in tan_raw:
            tan.extend((_norm_snorm10(v[0]), _norm_snorm10(v[1]), _norm_snorm10(v[2])))

    col_raw = rd('COLOR0')
    col = []
    if col_raw:
        for v in col_raw:
            col.extend((v[0] / 255.0, v[1] / 255.0, v[2] / 255.0, v[3] / 255.0))

    bw_raw = rd('BLENDWEIGHTS')
    bi_raw = rd('BLENDINDICES')
    joints, weights = [], []
    if bw_raw and bi_raw:
        for w, b in zip(bw_raw, bi_raw):
            joints.extend((b[0], b[1], b[2], b[3]))
            weights.extend((w[0] / 255.0, w[1] / 255.0, w[2] / 255.0, w[3] / 255.0))

    idx = Y.read_indices(res, ib) if ib else []
    return dict(pos=pos, nrm=nrm, uv=uv, tan=tan, col=col,
                joints=joints, weights=weights,
                vcount=n, stride=vb['stride'], indices=idx)


_HEAD_KEYS = ('head', 'eye', 'teeth', 'eyebrow', 'hair', 'beard')


def is_head_part(name):
    n = (name or '').lower()
    return any(k in n for k in _HEAD_KEYS)


def assemble_single(model_dir, prefix, verbose=True):
    """只取单个 `.ydd`（动物等"整只已合并"的资产用；避免把一只动物拆成两个来源拼出嵌合体）。"""
    import glob
    cands = sorted(glob.glob(os.path.join(model_dir, prefix + '*merge*.ydd')))
    if not cands:
        cands = sorted(glob.glob(os.path.join(model_dir, prefix + '*.ydd')))
    best = None
    for f in cands:
        try:
            ped = parse_ped(f)
        except Exception as e:
            if verbose:
                print('  [skip] %s: %s' % (os.path.basename(f), e))
            continue
        v = sum(p['verts'] for p in ped['parts'])
        if best is None or v > best[0]:
            best = (v, f, ped)
    if not best:
        return dict(parts=[], sources=[])
    _v, f, ped = best
    return dict(parts=ped['parts'], sources=[os.path.basename(f)],
                verts=sum(p['verts'] for p in ped['parts']),
                tris=sum(p['tris'] for p in ped['parts']))


def part_bbox(part):
    """部件在模型空间的包围盒 (minx,miny,minz,maxx,maxy,maxz)。
    pos 已转成 glTF 轴：x, y=高度, z。"""
    xs, ys, zs = [], [], []
    for g in part.get('geoms') or []:
        p = g['pos']
        xs += p[0::3]; ys += p[1::3]; zs += p[2::3]
    if not xs:
        return None
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def is_head_geometry(part, top=None):
    """是不是"真正的头部网格"——**不能靠贴图名**。
    实测 cs_dutch merge_18 里那个叫 `Head_000` 的 drawable 其实是**上半身皮肤**
    （宽 1.2 m、高 0.55 m），真正的头在 merge_22 里。按名字判会把身体当头，
    然后"已经有个头了"就不补真头 → 导出的人物没脑袋。

    ★ `top` 是这一组部件的最高点（米）。必须用**相对高度**判：
      之前写死 `zc > 1.40`，把儿童（杰克，总高只有 1.2 m）的头全判成"不是头"，
      结果是杰克/特里劳尼这类角色**整个脑袋都没有**。"""
    bb = part_bbox(part)
    if not bb:
        return False
    w = bb[3] - bb[0]; h = bb[4] - bb[1]; d = bb[5] - bb[2]
    zc = (bb[1] + bb[4]) * 0.5
    if max(w, d) >= 0.42 or h >= 0.42:
        return False
    if top is None:
        return zc > 1.40
    return zc > (top - 0.45)


def part_slots(name, part=None, top=None):
    """把部件名（albedo）归到服装槽位。用于判断一套 merge 是否"穿好了"。"""
    n = (name or '').lower()
    s = set()
    if 'nude' in n:
        s.add('nude')
    if (part is not None and is_head_geometry(part, top)) or ('head' in n and part is None):
        s.add('head')
    if 'hair' in n:
        s.add('hair')
    if 'beard' in n:
        s.add('beard')
    if any(k in n for k in ('shirt', 'vest', 'coat', 'tunic', 'chemise', 'bib',
                            'cloak', 'shawl', 'uppertorso', 'union', 'jacket',
                            'boutonniere', 'dress', 'gown', 'bodice')):
        s.add('upper')
    if any(k in n for k in ('pant', 'lowr', 'chaps', 'overall', 'skirt', 'dress',
                            'gown', 'petticoat', 'apron')):
        s.add('lower')
    if any(k in n for k in ('boot', 'feet', 'shoe', 'spat')):
        s.add('feet')
    if any(k in n for k in ('glove', 'hand')):
        s.add('hand')
    if any(k in n for k in ('hat', 'mask', 'scarf', 'neckerchief', 'tie', 'belt',
                            'holster', 'chain', 'suspender', 'spur', 'badge',
                            'bandolier', 'satchel', 'ring', 'necklace')):
        s.add('acc')
    return s


def outfit_score(slots, real_upper=True):
    """完整度打分：上装/下装/鞋是硬指标，裸体重罚。
    ★ 这是修 "剧情角色穿得奇怪" 的关键：以前按"顶点最多"选，会选到
      双外套叠穿或只穿衬衫的那一组；现在按"槽位覆盖"选完整的正装。"""
    v = (3 * ('upper' in slots) + 3 * ('lower' in slots)
         + 2 * ('feet' in slots) + 1 * ('head' in slots)
         + 0.5 * ('hair' in slots) + 0.5 * ('acc' in slots))
    if 'nude' in slots and not real_upper:
        v -= 10          # 纯裸体
    return v


def assemble_character(model_dir, prefix, verbose=True, outfit=None):
    """把一个角色的多个 `merge_N.ydd` 拼成完整人物。

    `merge_N` 不是"分组的部件集"，而是**一套套完整的 outfit**（实测 cs_dutch：
      merge_17 = 双外套+靴+手套+枪套（冬装）
      merge_18 = 马甲+领带+外套+靴+**头**（正装，默认）
      merge_26/27 = 裸上身（换装/洗澡）
    游戏运行期按任务选其中一套。旧代码按"顶点最多"挑 → 经常挑到冬装或裸体。

    现在：① 先排除含 nude 的组；② 按槽位覆盖打分选最完整的一套；
         ③ 缺头/下装/鞋时，从其它组里补"只补缺、不重复"的件。
    传 `outfit='merge_18'` 可强制指定某一套。
    """
    import glob
    cands = sorted(glob.glob(os.path.join(model_dir, prefix + '*.ydd')))
    # ★ 有些角色还有一套**不带性别后缀**的变体文件（如 cs_josiahtrelawny_m_merge.ydd），
    #   头/眼/牙只在这套里；只按 prefix 扫会漏掉 → 角色变成"没脑袋"。
    root = prefix
    for suf in ('_ms1', '_fs1', '_mt1', '_ft1'):
        if root.endswith(suf):
            root = root[:-len(suf)]
            break
    if root != prefix:
        cands += sorted(glob.glob(os.path.join(model_dir, root + '_m_merge*.ydd')))
        cands += sorted(glob.glob(os.path.join(model_dir, root + '_f_merge*.ydd')))
        cands = sorted(set(cands))
    cands = [c for c in cands if '_merge' in os.path.basename(c)] or cands
    groups = []
    for f in cands:
        try:
            ped = parse_ped(f)
        except Exception as e:
            if verbose:
                print('  [skip] %s: %s' % (os.path.basename(f), e))
            continue
        if not ped['parts']:
            continue
        slots = set()
        head_n = 0
        tcount = {}
        _bbs = [part_bbox(p) for p in ped['parts']]
        _top = max([b[4] for b in _bbs if b], default=None)
        for p in ped['parts']:
            slots |= part_slots(p['name'], p, _top)
            if is_head_geometry(p, _top) and 'head' in (p['name'] or '').lower():
                head_n += 1
            ln = (p['name'] or '').lower()
            for t in ('coat', 'vest', 'shirt', 'pants', 'boot', 'hat'):
                if t in ln:
                    tcount[t] = tcount.get(t, 0) + 1
        # 同一套里出现两件同类（双外套）要扣分：那是叠穿，不是"更完整"
        dup = sum(max(0, c - 1) for c in tcount.values())
        real_upper = any(
            any(k in (p['name'] or '').lower() for k in
                ('shirt', 'vest', 'coat', 'dress', 'gown', 'bodice', 'chemise', 'jacket'))
            for p in ped['parts'])
        groups.append(dict(file=f, ped=ped, slots=slots, head_n=head_n, dup=dup,
                           score=outfit_score(slots, real_upper) - 1.2 * dup,
                           verts=sum(p['verts'] for p in ped['parts'])))
    if not groups:
        return dict(parts=[], sources=[], verts=0, tris=0, outfit='')

    if outfit:
        pick = [g for g in groups if outfit in os.path.basename(g['file'])]
        if pick:
            groups = pick

    # ① 初始：最完整的一套（裸体已扣分，但再显式挡一次）
    base = max(groups, key=lambda g: (g['score'], g['verts']))
    chosen = [base]
    covered = set(base['slots'])

    # ② 补槽位：只补缺的，且不接受 nude / 不重复
    for need in ('head', 'upper', 'lower', 'feet'):
        if need in covered:
            continue
        best = None
        for g in groups:
            if g in chosen or 'nude' in g['slots'] or need not in g['slots']:
                continue
            if need == 'head' and g['head_n'] == 0:
                continue
            gain = len(g['slots'] - covered)
            if gain <= 0:
                continue
            if best is None or (gain, g['score']) > (best[0], best[1]['score']):
                best = (gain, g)
        if best:
            chosen.append(best[1])
            covered |= best[1]['slots']

    # ③ 头部永远从"真正的头部组"补（几何判定），不信任贴图名
    if not any(g['head_n'] for g in chosen):
        head_group = max(groups, key=lambda g: (g['head_n'], g['score']))
        if head_group['head_n'] and head_group not in chosen:
            chosen.append(head_group)
            covered |= head_group['slots']

    parts = []
    seen = set()
    src = []
    for g in chosen:
        src.append(os.path.basename(g['file']))
        for p in g['ped']['parts']:
            key = '%s|%s' % (p.get('albedo') or '', p.get('hash'))
            if key in seen:
                continue
            seen.add(key)
            parts.append(p)

    # ★ 兜底：下肢/靴子/头发常常是**独立部件**（不进任何 merge）
    have = ' '.join((p['name'] or '').lower() for p in parts)
    import re as _re
    for slot, rx, pats in (
            ('legs', r'(lowr|_leg|lower|pant|chaps|overall)',
             ('*_lowr*.ydd', '*lowr*.ydd', '*_pants*.ydd', '*pants*.ydd', '*_chaps*.ydd')),
            ('feet', r'(boot|_feet|_foot|footl|footr|shoe)',
             ('*_feet*.ydd', '*feet*.ydd', '*_boot*.ydd', '*boot*.ydd', '*_shoe*.ydd')),
            ('upper', r'(shirt|coat|vest|dress|gown|bodice|jacket|chemise)',
             ('*_shirt_*.ydd', '*_coat_*.ydd', '*_vest_*.ydd', '*_dress_*.ydd',
              '*_bodice_*.ydd', '*_gown_*.ydd')),
            ('hair', r'(hair|beard)',
             ('*_hair_000*.ydd', '*_hair*.ydd'))):
        if _re.search(rx, have):
            continue
        cands2 = []
        for pat in pats:
            cands2 += glob.glob(os.path.join(model_dir, prefix + pat))
        cands2 = sorted(set(cands2))
        best2 = None
        for f in cands2:
            try:
                ped2 = parse_ped(f)
            except Exception:
                continue
            v = sum(p['verts'] for p in ped2['parts'])
            if v and (best2 is None or v > best2[0]):
                best2 = (v, f, ped2)
        if best2:
            if verbose:
                print('  [兜底] %s 补 %s -> %s' % (prefix, slot, os.path.basename(best2[1])))
            src.append(os.path.basename(best2[1]))
            for p in best2[2]['parts']:
                key = '%s|%s' % (p.get('albedo') or '', p.get('hash'))
                if key in seen:
                    continue
                seen.add(key)
                parts.append(p)

    # ③-b 眼睛/牙齿经常单独放在另一个 merge 里（如 cs_jackmarston 的 merge_4），
    #     如果当前选的组合没有眼睛，就从该角色所有文件里把眼/牙补回来（只补这两类，不动衣服）
    have_l = ' '.join((p['name'] or '').lower() for p in parts)
    need = []
    if 'eyes' not in have_l:
        need.append('eyes')
    if 'teeth' not in have_l:
        need.append('teeth')
    if need:
        import glob as _glob
        for f in sorted(_glob.glob(os.path.join(model_dir, prefix + '*.ydd'))):
            if os.path.basename(f) in [os.path.basename(g['file']) for g in chosen]:
                continue
            try:
                ped2 = parse_ped(f)
            except Exception:
                continue
            for q in ped2['parts']:
                n = (q['name'] or '').lower()
                if any(k in n for k in need):
                    key = q['albedo'] or ('0x%08x' % q['hash'])
                    if key in seen:
                        continue
                    seen.add(key)
                    parts.append(q)
                    src.append(os.path.basename(f))

    # ③-b2 有头但没眼球：把通用眼球**按头部包围盒对齐**后放进去
    #       （直接按原生位置放会插进额头/颅内，看不到；实测按 62% 眼线 + 面部前缘 -3.5cm 准）
    have_e = ' '.join((p['name'] or '').lower() for p in parts)
    if 'eyes' not in have_e:
        _bbs2 = [(p, part_bbox(p)) for p in parts if part_bbox(p)]
        _top2 = max(b[4] for _p, b in _bbs2) if _bbs2 else None
        heads = [(p, b) for p, b in _bbs2
                 if is_head_geometry(p, _top2) and 'hat' not in (p['name'] or '').lower()]
        if heads:
            hp, hb = max(heads, key=lambda kv: kv[1][4] - kv[1][1])
            g2 = 'f' if '_fs1' in prefix else 'm'
            ef = os.path.join(model_dir.replace('cutscene', 'generic'), 'eyes_%sr1_0000.ydd' % g2)
            if os.path.exists(ef):
                try:
                    ep = parse_ped(ef)
                    eb = part_bbox(ep['parts'][0])
                    ty = hb[1] + 0.62 * (hb[4] - hb[1])
                    tz = hb[5] - 0.035
                    dy = ty - (eb[1] + eb[4]) / 2
                    dz = tz - (eb[2] + eb[5]) / 2
                    for q in ep['parts']:
                        for gg in q['geoms']:
                            pos = gg['pos']
                            for i in range(0, len(pos), 3):
                                pos[i + 1] += dy
                                pos[i + 2] += dz
                        key = '%s|%s' % (q.get('albedo') or '', q.get('hash'))
                        if key in seen:
                            continue
                        seen.add(key)
                        parts.append(q)
                    src.append('GENERIC_EYES_ALIGNED')
                except Exception:
                    pass

    # ③-c 少数角色（乐队、杂兵等）解包包里**根本没有头**——游戏里用的是通用头。
    #     这里补一套通用头/眼/牙（按性别），至少不是"无头人"，manifest 里会写 GENERIC_HEAD。
    have2 = ' '.join((p['name'] or '').lower() for p in parts)
    if prefix.startswith('cs_') and 'head' not in have2:
        import glob as _g2
        g = 'f' if '_fs1' in prefix else 'm'
        want = ['head_%sr1_%s' % (g, '0008' if g == 'f' else '0026'),
                'eyes_%sr1_0000' % g, 'teeth_%sr1_0000' % g]
        for stem in want:
            f = os.path.join(model_dir.replace('cutscene', 'generic'), stem + '.ydd')
            if not os.path.exists(f):
                continue
            try:
                ped3 = parse_ped(f)
            except Exception:
                continue
            for q in ped3['parts']:
                key = '%s|%s' % (q.get('albedo') or '', q.get('hash'))
                if key in seen:
                    continue
                seen.add(key)
                parts.append(q)
                src.append('GENERIC_HEAD:' + stem)

    # ③-d 小孩/矮个角色的眼球是按成人尺寸做的，直接用会"大眼珠外凸"。
    #     按身体高度等比缩小（以 1.9 m 成人身高为基准），围绕眼球自身中心缩放。
    _tops = [part_bbox(p)[4] for p in parts if part_bbox(p)]
    if _tops:
        body_h = max(_tops)
        sc = max(0.55, min(1.0, body_h / 1.90))
        if sc < 0.95:
            for p in parts:
                if 'eyes' not in (p['name'] or '').lower():
                    continue
                bb = part_bbox(p)
                if not bb:
                    continue
                cy = (bb[1] + bb[4]) / 2
                cz = (bb[2] + bb[5]) / 2
                for g in p['geoms']:
                    pos = g['pos']
                    for i in range(0, len(pos), 3):
                        pos[i] *= sc
                        pos[i + 1] = cy + (pos[i + 1] - cy) * sc
                        pos[i + 2] = cz + (pos[i + 2] - cz) * sc

    # ③-e （已回滚）不再跨文件替换头部网格：
    #      `*_head_*.ydd` 的顶点是**另一套局部空间**，直接换会让头下沉 7 cm（亚瑟的脸就是这么没的）。
    # ④ 帽子贴头：帽子顶点是相对头骨挂点存的，静态导出会浮在头顶上方
    #   （README 已记录的老问题）。这里按"头网格包围盒顶"把帽子往下压到刚好扣住。
    _all_bb = [part_bbox(p) for p in parts]
    _top_all = max([b[4] for b in _all_bb if b], default=None)
    head_tops = [part_bbox(p)[4] for p in parts
                 if is_head_geometry(p, _top_all) and 'hat' not in (p['name'] or '').lower()]
    if head_tops:
        htop = max(head_tops)
        for p in parts:
            if 'hat' not in (p['name'] or '').lower():
                continue
            bb = part_bbox(p)
            if not bb:
                continue
            if bb[1] > htop - 0.06:
                # 帽檐压到发顶下 3 cm，视觉上才是"戴在头上"而不是浮着
                dz = bb[1] - (htop - 0.03)
                for g in p['geoms']:
                    for i in range(1, len(g['pos']), 3):
                        g['pos'][i] -= dz

    return dict(parts=parts, sources=src,
                verts=sum(p['verts'] for p in parts),
                tris=sum(p['tris'] for p in parts),
                outfit=os.path.basename(base['file']),
                outfit_slots=sorted(covered),
                score=round(base['score'], 1))


def parse_ped(path, lod='high'):
    """`.ydd` → {parts:[{hash, name, material, geoms:[attrs]}], skeleton_ptr}"""
    data = open(path, 'rb').read()
    res = Y.Res(data)
    parts = []
    skeleton = 0
    for h, off in Y.parse_drawable_dictionary(res):
        sg = res.u64(off + 0x10)
        if not skeleton:
            skeleton = res.u64(off + 0x18)
        shader_names = Y.parse_shader_group(res, sg)
        shader_hashes = Y.parse_shader_hashes(res, sg)
        models = Y.pointer_list(res, res.u64(off + {'high': 0x50, 'med': 0x58,
                                                    'low': 0x60, 'vlow': 0x68}[lod]))
        geoms = []
        mats = []
        for m in models:
            shmap = Y.parse_model_shaders(res, m, len(Y.parse_model_geoms(res, m)))
            for gi, g in enumerate(Y.parse_model_geoms(res, m)):
                a = read_geom_attrs(res, g, lod)
                if not a or not a['indices']:
                    continue
                sid = shmap[gi] if gi < len(shmap) else 0
                tnames = shader_names[sid] if 0 <= sid < len(shader_names) else []
                shash = shader_hashes[sid] if 0 <= sid < len(shader_hashes) else {}
                geoms.append(a)
                mats.append(dict(shader=shash.get('name'), shader_hash=shash.get('hash'),
                                 texs=[dict(slot=t['slot'], param=t['param'], role=t['role'],
                                            name=t['name']) for t in tnames]))
        if not geoms:
            continue
        # 部件名：用 albedo 贴图名（可读）
        albedo = pick_albedo(mats)
        nm = albedo or ('part_%08x' % h)
        parts.append(dict(hash=h, name=nm, off=off, geoms=geoms, mats=mats,
                          albedo=albedo,
                          tris=sum(len(g['indices']) // 3 for g in geoms),
                          verts=sum(g['vcount'] for g in geoms)))

    # ★ up 偏移纠正（实测所有 RDR2 人物通用）：几何顶点相对"根骨（≈骨盆高度 1.0 m）"
    #   存放，而 Drawable 头里的 bbox 是**绝对高度**。两者恒差 +1.0000（本例 5 个角色全中：
    #   cs_dutch merge_17/18、player_three / player_zero、cs_billwilliamson）。
    #   不做这个平移，模型脚底会落在 y=−1，进引擎要手调；做了就"脚踩 y=0"。
    dzs = []
    for part in parts:
        hz0 = res.f32(part['off'] + 0x30 + 8)
        vmin = min(g['pos'][i] for g in part['geoms']
                   for i in range(1, len(g['pos']), 3))
        dzs.append(hz0 - vmin)
    up = sorted(dzs)[len(dzs) // 2] if dzs else 0.0
    for part in parts:
        for g in part['geoms']:
            p = g['pos']
            for i in range(1, len(p), 3):
                p[i] += up
    return dict(file=os.path.basename(path), parts=parts, skeleton=skeleton,
                up_offset=round(up, 4))


_PRIO = ('albedo', 'albedo_layer0', 'lyr0diffusetex', 'tint')


def pick_albedo(mats):
    best = None
    for m in mats:
        for t in m['texs']:
            if t['role'] in _PRIO and t['name'] and not t['name'].lower().startswith('giveme'):
                return t['name']
            if t['param'] in ('diffusetex',) and t['name'] and not t['name'].lower().startswith('giveme'):
                if best is None:
                    best = t['name']
    return best


def tex_of(mats, role):
    for m in mats:
        for t in m['texs']:
            if t['role'] == role and t['name'] and not t['name'].lower().startswith('giveme'):
                return t['name']
    return None


# ---------------------------------------------------------------- 贴图

def load_tex_index(path):
    """`rdr2_tex_index.py` 产出的全局索引：贴图条目名 -> (ytd 路径, 条目下标)。

    ★ 关键认识：RDR2 的 `.ytd` 是**多纹理字典**（`cs_dutch_ms1_merge.ytd` 内含 32 张），
      而 shader 里写的是**条目名**（`CS_Dutch_MS1_Holster_Belt_001_c0_000_ab`），
      所以必须靠这个反查表才能拿到正确像素；按文件名匹配是行不通的。
    """
    d = json.load(open(path))
    return {k.lower(): (v[0], v[1]) for k, v in d['index'].items()}


def decode_ytd_entry(path, idx):
    """从 `.ytd` 里解码**指定下标**的纹理 → (png_bytes, w, h, name)。"""
    import io
    raw = open(path, 'rb').read()
    body, gpx = TP.load(path)
    for t in TP.entries(body, raw=raw):
        if t['idx'] != idx:
            continue
        blob = gpx[t['go']:t['go'] + max(4096, t['w'] * t['h'] * 4)]
        im, _fname = TP.decode_one(blob, t['w'], t['h'], t['f'])
        if im is None:
            return None, 0, 0, t['name']
        if im.mode != 'RGBA':
            im = im.convert('RGBA')
        buf = io.BytesIO()
        im.save(buf, 'PNG')
        return buf.getvalue(), t['w'], t['h'], t['name']
    return None, 0, 0, ''


# ---------------------------------------------------------------- GLB 写出

class GlbWriter:
    def __init__(self):
        self.bin = bytearray()
        self.buffer_views = []
        self.accessors = []
        self.images = []
        self.textures = []
        self.materials = []
        self.meshes = []
        self.nodes = []

    def _bv(self, data, target=None):
        off = len(self.bin)
        self.bin += data
        pad = (4 - (len(self.bin) % 4)) % 4
        self.bin += b'\x00' * pad
        v = dict(buffer=0, byteOffset=off, byteLength=len(data))
        if target:
            v['target'] = target
        self.buffer_views.append(v)
        return len(self.buffer_views) - 1

    def add_accessor(self, data, comp_type, type_str, count, target=None, minmax=False):
        bv = self._bv(data, target)
        acc = dict(bufferView=bv, componentType=comp_type, count=count, type=type_str)
        if minmax:
            import struct as _s
            ncomp = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[type_str]
            fmt = {5120: 'b', 5121: 'B', 5122: 'h', 5123: 'H', 5125: 'I', 5126: 'f'}[comp_type]
            vals = _s.unpack_from('<%d%s' % (count * ncomp, fmt), data)
            mn = [min(vals[i::ncomp]) for i in range(ncomp)]
            mx = [max(vals[i::ncomp]) for i in range(ncomp)]
            acc['min'], acc['max'] = mn, mx
        self.accessors.append(acc)
        return len(self.accessors) - 1

    def add_png(self, png, name):
        bv = self._bv(png)
        self.images.append(dict(bufferView=bv, mimeType='image/png', name=name))
        self.textures.append(dict(source=len(self.images) - 1))
        return len(self.textures) - 1


def _neutralize_png(png):
    """把"tint 遮罩"贴图降饱和成中性色。

    RDR2 里两类贴图**本身不是最终颜色**，真色来自 tint 调色板（`assets_tints.ymt`，二进制
    PSIN，无法离线还原配方）：
      * 名字形如 `<...>_c<N>_999_ab`（`999` = 走调色板）
      * 头发 / 胡须的发片图（实测 `hair_gen_999` RGB≈(52,119,37)、`beard_mr1_000_c0_005` ≈(43,123,29)）
    直接当 albedo 用会渲染成**刺眼的纯绿**。这里保留明暗细节、去掉色相 → 中性灰衣物/毛发，
    比绿色可接受得多；拿到真调色板后再替换即可。
    """
    import io as _io
    from PIL import Image as _I
    im = _I.open(_io.BytesIO(png)).convert('RGBA')
    r, g, b, a = im.split()
    lum = _I.merge('RGB', (r, g, b)).convert('L')
    rr = lum.point(lambda v: min(255, int(v * 1.04)))
    gg = lum.point(lambda v: min(255, int(v * 0.97)))
    bb = lum.point(lambda v: min(255, int(v * 0.90)))
    out = _I.merge('RGBA', (rr, gg, bb, a))
    buf = _io.BytesIO()
    out.save(buf, 'PNG')
    return buf.getvalue()


_TINT_MASK_RX = __import__('re').compile(r'_c\d+_999_ab$', __import__('re').I)


def _looks_like_tint_mask(png):
    """靠"色相是否在同一张图上乱跳"识别 tint 遮罩。

    名字里带 `_c0_000_ab` 的未必就是真颜色（夏洛蒂的衬衫就是一张彩虹 mask，
    真色在 `assets_tints.ymt` 调色板里）。判据：
      · 平均饱和度 > 0.30
      · 色相的圆周标准差 > 0.22（单色衣服≈0，彩虹 mask 很大）
    """
    try:
        import io as _io
        import numpy as _np
        from PIL import Image as _I
        im = _I.open(_io.BytesIO(png)).convert('RGB').resize((64, 64))
        a = _np.asarray(im, dtype=_np.float32) / 255.0
        mx = a.max(2); mn = a.min(2)
        sat = (mx - mn) / _np.maximum(mx, 1e-6)
        if sat.mean() < 0.50:
            return False
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        ang = _np.arctan2(_np.sqrt(3) * (g - b), 2 * r - g - b)
        z = _np.exp(1j * ang).ravel()
        R = abs(z.mean())
        hue_std = _np.sqrt(max(0.0, -2 * _np.log(max(R, 1e-6)))) / (2 * _np.pi)
        return hue_std > 0.08
    except Exception:
        return False



def resolve_tex(idx_name, tex_index):
    """贴图名 → (ytd路径, 条目号)。带兜底：很多服饰的 albedo 名字在包里对不上。

    实测（6106 件服饰里 10745 个部件）：
      · 9676 直接命中
      · `_c3_998_ab` → `_c3_999_ab`（998 是"未调色"变体，正片在 999）
      · `_c1_999_ab` → `_c0_999_ab`（同款只做了 c0 的贴图）
      · `_c1_002_ab` → `_c0_999_ab`（同款只有 tint 遮罩）
    剩下确实没有的（约 900 个部件）只能留白，见 docs。
    """
    k = (idx_name or '').lower()
    if not k:
        return None, ''
    cands = [k]
    if k.endswith('_998_ab'):
        cands.append(k[:-7] + '_999_ab')            # 998 = 未调色变体
    m = re.sub(r'_(c\d+)_\d{3}_ab$', r'__999_ab', k)
    if m != k:
        cands.append(m)                             # 同 c，换 999 遮罩
    for ci in range(0, 7):
        c = re.sub(r'_c\d+_', '_c%d_' % ci, k)
        if c not in cands:
            cands.append(c)                         # 换 c，同后缀
    for ci in range(0, 7):
        c = re.sub(r'_c\d+_\d{3}_ab$', '_c%d_999_ab' % ci, k)
        if c not in cands:
            cands.append(c)                         # 换 c + 999
    for cnd in cands:
        ent = tex_index.get(cnd)
        if ent:
            return ent, cnd
    return None, ''


_EYE_RX = re.compile(r'(^|_)eyes?(_|$)|eyes_gen|eye_cap', re.I)


def synth_eye(png, skin=None):
    """把 RDR2 的眼球 tint 遮罩合成为**能看见眼白/虹膜/瞳孔**的贴图。

    实测 `eyes_gen_0000_c0_999_ab` 三个通道各管一件事：
      R = 虹膜盘（中间一个圆）
      G = 眼白（整个眼球）
      B = 瞳孔（圆心小点）
    直接把它当颜色用 → 整颗眼球是荧光绿；降饱和 → 一颗灰球，看起来像"没有眼球"。
    """
    import io as _io
    import numpy as _np
    from PIL import Image as _I
    im = _I.open(_io.BytesIO(png)).convert('RGB')
    a = _np.asarray(im, dtype=_np.float32) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    # 虹膜做一点膨胀（原遮罩偏小）；**虹膜以外一律用肤色**——这只头的眼睑是闭的，
    # 铺眼白会把整颗球露成"白球"；用肤色过渡，看起来就是正常睁着的眼睛。
    iris = _np.clip((r - b * 0.45) * 2.1, 0.0, 1.0)
    pupil = _np.clip((b - r * 0.25) * 1.9, 0.0, 1.0)
    sk = _np.asarray(skin if skin is not None else [0.62, 0.45, 0.36], _np.float32).reshape(1, 1, 3)
    iris_col = _np.array([0.33, 0.21, 0.13], _np.float32)
    out = sk * (1 - iris[..., None]) + iris_col * iris[..., None]
    out = out * (1 - pupil[..., None]) + 0.02 * pupil[..., None]
    buf = _io.BytesIO()
    _I.fromarray((_np.clip(out, 0, 1) * 255).astype(_np.uint8)).save(buf, 'PNG')
    return buf.getvalue()



def fallback_color(idx_name):
    """贴图确实找不到时给一个"像这个部位"的底色，至少不会渲染成纯白。"""
    n=(idx_name or '').lower()
    if any(k in n for k in ('head','eye','ear','hand','neck','skin')):
        return [0.62,0.45,0.36,1.0]          # 肤色
    if any(k in n for k in ('boot','holster','belt','saddle','leather','glove')):
        return [0.26,0.19,0.13,1.0]          # 皮革
    if any(k in n for k in ('metal','buckle','spur','chain','badge')):
        return [0.48,0.49,0.52,1.0]          # 金属
    if any(k in n for k in ('hair','beard','brow')):
        return [0.16,0.12,0.09,1.0]          # 毛发
    if any(k in n for k in ('teeth',)):
        return [0.86,0.84,0.78,1.0]
    if any(k in n for k in ('gore',)):
        return [0.30,0.06,0.06,1.0]
    return [0.34,0.30,0.26,1.0]              # 布料/默认



def _is_green_mask(png):
    """头发/胡须遮罩常见形态：一片绿（G 明显高于 R/B）。"""
    try:
        import io as _io
        import numpy as _np
        from PIL import Image as _I
        a = _np.asarray(_I.open(_io.BytesIO(png)).convert('RGB'), dtype=_np.float32) / 255.0
        m = a.reshape(-1, 3).mean(0)
        return m[1] > m[0] * 1.30 and m[1] > m[2] * 1.30
    except Exception:
        return False




_TEXIDX = None


def tex_index_cached():
    """assemble 阶段也要用贴图索引（挑干净的头部变体），这里做个懒加载。"""
    global _TEXIDX
    if _TEXIDX is None:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _TEXIDX = load_tex_index(os.path.join(root, 'raw/npc/index/tex_index.json'))
    return _TEXIDX


def _head_brightness(part, tex_index):
    """头部贴图的平均亮度——用来在多个头变体里挑"干净"的那张（脏脸/血污版本更暗）。"""
    import io as _io
    import numpy as _np
    from PIL import Image as _I
    ent, _hit = resolve_tex(part.get('albedo'), tex_index)
    if not ent:
        return 0.0
    try:
        png, w, h, tn = decode_ytd_entry(*ent)
    except Exception:
        return 0.0
    if not png:
        return 0.0
    a = _np.asarray(_I.open(_io.BytesIO(png)).convert('RGB'), dtype=_np.float32) / 255.0
    return float(a.mean())


def _head_color(ped, tex_index):
    """取头部 albedo 的平均色，用作眼球外圈（眼睑）的肤色。"""
    import io as _io
    import numpy as _np
    from PIL import Image as _I
    best = None
    for part in ped.get('parts', []):
        n = (part.get('name') or '').lower()
        if 'head' not in n:
            continue
        ent, _hit = resolve_tex(part.get('albedo'), tex_index)
        if not ent:
            continue
        try:
            png, w, h, tn = decode_ytd_entry(*ent)
        except Exception:
            continue
        if not png:
            continue
        a = _np.asarray(_I.open(_io.BytesIO(png)).convert('RGB'), dtype=_np.float32) / 255.0
        m = a.reshape(-1, 3).mean(0)
        if m[1] > m[0] * 1.3 and m[1] > m[2] * 1.3:   # 绿遮罩
            continue
        best = m
        break
    return best

def _eyebrow_color(ped, tex_index, tex_cache=None):
    """从**眉毛**的 albedo 取"本人发色"。

    头发贴图 `hair_gen_999_c0_999_ab` 是一张 tint 遮罩（绿），真色来自
    `assets_tints.ymt`（PSIN，没解）。但同角色的**眉毛**贴图往往是画好的真色
    （实测夏洛蒂 `..._Eyebrows_000_c0_000_ab` 均值 (0.015,0.007,0.006) = 近黑，
    正好就是游戏里她的黑发）。拿它当发色，比拍一个"通用棕/灰"准得多。
    若眉毛也是遮罩（绿成一片）或过亮，则退回深棕。
    """
    import io as _io
    import numpy as _np
    from PIL import Image as _I
    for part in ped.get('parts', []):
        n = (part.get('name') or '').lower()
        if not ('eyebrow' in n or 'brow' in n):
            continue
        ent, _hit = resolve_tex(part.get('albedo'), tex_index)
        if not ent:
            continue
        try:
            png, w, h, tn = decode_ytd_entry(*ent)
        except Exception:
            continue
        if not png:
            continue
        a = _np.asarray(_I.open(_io.BytesIO(png)).convert('RGB'), dtype=_np.float32) / 255.0
        m = a.reshape(-1, 3).mean(0)
        if m[1] > m[0] * 1.35 and m[1] > m[2] * 1.35:      # 绿色遮罩，不可信
            continue
        if float(m.mean()) > 0.72:                          # 太白，不像发色
            continue
        return _np.clip(m * 0.95, 0.015, 1.0)
    return _np.array([0.085, 0.062, 0.048], _np.float32)


def synth_hair(png, color):
    """把头发 tint 遮罩 → 保留发丝明暗、染成目标发色。"""
    import io as _io
    import numpy as _np
    from PIL import Image as _I
    im = _I.open(_io.BytesIO(png)).convert('RGBA')
    a = _np.asarray(im, dtype=_np.float32) / 255.0
    rgb, alpha = a[..., :3], a[..., 3:4]
    lum = (0.30 * rgb[..., 0] + 0.59 * rgb[..., 1] + 0.11 * rgb[..., 2])[..., None]
    lum = _np.clip((lum - 0.05) / 0.55, 0.0, 1.0)
    shade = 0.45 + 0.75 * lum                     # 发丝起伏
    out = _np.clip(_np.asarray(color, _np.float32).reshape(1, 1, 3) * shade, 0.01, 1.0)
    rgba = _np.concatenate([out, alpha], -1)
    buf = _io.BytesIO()
    _I.fromarray((rgba * 255).astype(_np.uint8), 'RGBA').save(buf, 'PNG')
    return buf.getvalue()


def write_glb(out_path, ped, tex_index, png_dir=None, want_tex=True, tex_cache=None,
              keep_vcol=False, neutralize=True):
    """把一个人物写成 .glb（+ 可选把用到的贴图 PNG 落盘备查）。

    ★ 关于 `COLOR0`（踩坑记录，务必别加回来）：
      RDR2 人物顶点里的 `COLOR0` **不是颜色**，而是 **palette/tint 选择子**——
      实测 `head_mr1_0026` / `hand_MR1_000` 的 COLOR0 均值恒为 **(0.107, 1.000, 0.000, 1.000)**，
      即"R=索引, G=1, B=0"的编码。glTF 规范里 `COLOR_0` 会**乘到 baseColor 上**，
      于是**整张脸和双手会被染成纯绿色**。所以默认**不导出 COLOR_0**。
      （只有极少数"逐顶点真彩色"shader 才需要，用 --keep-vertex-color 打开。）
    """
    w = GlbWriter()
    material_ids = {}
    used_tex = []
    _hair_col = _eyebrow_color(ped, tex_index, tex_cache)
    _skin_col = _head_color(ped, tex_index)

    def get_mat(idx_name, role, hair=False):
        key = (idx_name, role, hair)
        if key in material_ids:
            return material_ids[key]
        mat = dict(name='%s_%s' % (idx_name, role) if idx_name else (role or 'mat'),
                   pbrMetallicRoughness=dict(baseColorFactor=[1, 1, 1, 1],
                                             metallicFactor=0.0, roughnessFactor=0.85))
        if hair:
            # 头发/胡须/眉毛是**alpha 卡片**，必须 MASK + 双面，否则会渲染成一坨实心块
            mat['alphaMode'] = 'MASK'
            mat['alphaCutoff'] = 0.5
            mat['doubleSided'] = True
        # 眼球罩（eye_cap）在游戏里是一层很淡的湿润高光，纯色不透明会糊住眼球
        is_eye_cap = 'eye_cap' in (idx_name or '').lower()
        if is_eye_cap:
            mat['alphaMode'] = 'BLEND'
            mat['pbrMetallicRoughness']['baseColorFactor'] = [1, 1, 1, 0.06]
        if want_tex and idx_name and not is_eye_cap:
            ent, hit = resolve_tex(idx_name, tex_index)
            if not ent and role == 'albedo':
                # 贴图缺失：给部位底色，避免"白模"
                mat['pbrMetallicRoughness']['baseColorFactor'] = fallback_color(idx_name)
                mat['name'] += '_fallback'
            if ent:
                p, ti = ent
                cache_key = (p, ti)
                if tex_cache is not None and cache_key in tex_cache:
                    png, tw, th, tname = tex_cache[cache_key]
                else:
                    png, tw, th, tname = decode_ytd_entry(p, ti)
                    if tex_cache is not None:
                        tex_cache[cache_key] = (png, tw, th, tname)
                if png:
                    nm_l = (idx_name or '').lower()
                    is_eye = bool(re.search(r'eyes?_gen|eyes?_\d', nm_l))
                    if role == 'albedo' and is_eye and (
                            nm_l.endswith('_999_ab') or _looks_like_tint_mask(png)):
                        # 只有 **tint 遮罩**（_999_ab / 荧光绿）才需要合成；
                        # 专门的 cs_*_eyes_000_c0_000_ab 本来就是画好的眼球，直接用
                        png = synth_eye(png, _skin_col)
                    elif role == 'albedo' and hair and (
                            nm_l.endswith('_999_ab') or _looks_like_tint_mask(png)
                            or _is_green_mask(png)):
                        # 头发/胡须：遮罩只提供发丝明暗，颜色用**本人眉毛**的颜色
                        png = synth_hair(png, _hair_col)
                    elif neutralize and role == 'albedo' and (
                            _TINT_MASK_RX.search(idx_name or '')
                            or _looks_like_tint_mask(png)):
                        png = _neutralize_png(png)
                    tidx = w.add_png(png, '%s_%s' % (idx_name, role))
                    if role == 'albedo':
                        mat['pbrMetallicRoughness']['baseColorTexture'] = dict(index=tidx)
                    elif role == 'normal':
                        mat['normalTexture'] = dict(index=tidx)
                    else:
                        mat.setdefault('extras', {})[role + 'Texture'] = tidx
                    used_tex.append(dict(part=idx_name, role=role, texture=tname,
                                         w=tw, h=th, src=p, entry=ti))
                    if png_dir:
                        os.makedirs(png_dir, exist_ok=True)
                        fn = '%s_%s_%s.png' % (idx_name, role, tname or 'tex')
                        with open(os.path.join(png_dir, fn), 'wb') as fh:
                            fh.write(png)
        material_ids[key] = len(w.materials)
        w.materials.append(mat)
        return material_ids[key]

    prims = []
    part_meta = []
    for part in ped['parts']:
        if re.search(r'eyes?_?cap', (part.get('name') or ''), re.I):
            # eye_cap / eyes_cap 都是"湿润高光罩"，且与眼球共面 → 会 z-fighting 出白斑/红斑
            continue
        alb = part['albedo']
        nrm = tex_of(part['mats'], 'normal')
        hair = any(k in (part['name'] or '').lower()
                   for k in ('hair', 'beard', 'eyebrow', 'eyelash'))
        mat_a = get_mat(alb, 'albedo', hair)
        mat_n = get_mat(nrm, 'normal', hair)
        for gi, g in enumerate(part['geoms']):
            attrs = {}
            pos_f = struct.pack('<%df' % len(g['pos']), *g['pos'])
            attrs['POSITION'] = w.add_accessor(pos_f, 5126, 'VEC3', g['vcount'],
                                               target=34962, minmax=True)
            if g['nrm']:
                attrs['NORMAL'] = w.add_accessor(
                    struct.pack('<%df' % len(g['nrm']), *g['nrm']), 5126, 'VEC3',
                    g['vcount'], target=34962)
            if g['uv']:
                attrs['TEXCOORD_0'] = w.add_accessor(
                    struct.pack('<%df' % len(g['uv']), *g['uv']), 5126, 'VEC2',
                    g['vcount'], target=34962)
            if g['col'] and keep_vcol:
                attrs['COLOR_0'] = w.add_accessor(
                    struct.pack('<%df' % len(g['col']), *g['col']), 5126, 'VEC4',
                    g['vcount'], target=34962)
            if g['joints']:
                attrs['JOINTS_0'] = w.add_accessor(
                    bytes(g['joints']), 5121, 'VEC4', g['vcount'], target=34962)
                attrs['WEIGHTS_0'] = w.add_accessor(
                    struct.pack('<%df' % len(g['weights']), *g['weights']), 5126, 'VEC4',
                    g['vcount'], target=34962)
            ind = w.add_accessor(struct.pack('<%dI' % len(g['indices']), *g['indices']),
                                 5125, 'SCALAR', len(g['indices']), target=34963)
            prims.append(dict(attributes=attrs, indices=ind, material=mat_a,
                              extras=dict(part=part['name'], geom=gi,
                                          part_hash='0x%08x' % part['hash'])))
            part_meta.append(dict(part=part['name'], hash='0x%08x' % part['hash'],
                                  geom=gi, verts=g['vcount'], tris=len(g['indices']) // 3,
                                  stride=g['stride'], albedo=alb, normal=nrm,
                                  material=[dict(slot=t['slot'], param=t['param'],
                                                 role=t['role'], tex=t['name'])
                                            for m in part['mats'] for t in m['texs']]))

    w.meshes.append(dict(name=ped.get('file') or ped.get('name') or 'npc', primitives=prims))
    w.nodes.append(dict(mesh=0, name=ped.get('file') or ped.get('name') or 'npc'))
    gltf = dict(
        asset=dict(version='2.0', generator='rdr2_npc_export (BrainMaker)'),
        scene=0, scenes=[dict(nodes=[0])], nodes=w.nodes,
        meshes=w.meshes, materials=w.materials,
        bufferViews=w.buffer_views, accessors=w.accessors,
        buffers=[dict(byteLength=len(w.bin))],
    )
    if w.images:
        gltf['images'] = w.images
        gltf['textures'] = w.textures
        gltf['samplers'] = [dict(magFilter=9729, minFilter=9987, wrapS=10497, wrapT=10497)]
        # 用 albedo 的 sRGB；法线保持线性
        import copy
        for i, im in enumerate(gltf['images']):
            pass

    jchunk = json.dumps(gltf, separators=(',', ':')).encode('utf-8')
    jchunk += b' ' * ((4 - len(jchunk) % 4) % 4)
    bchunk = bytes(w.bin)
    total = 12 + 8 + len(jchunk) + 8 + len(bchunk)
    with open(out_path, 'wb') as fh:
        fh.write(struct.pack('<III', 0x46546C67, 2, total))
        fh.write(struct.pack('<II', len(jchunk), 0x4E4F534A))
        fh.write(jchunk)
        fh.write(struct.pack('<II', len(bchunk), 0x004E4942))
        fh.write(bchunk)

    return dict(glb=out_path, bytes=os.path.getsize(out_path),
                parts=len(ped['parts']), prims=len(prims),
                verts=sum(p['verts'] for p in ped['parts']),
                tris=sum(p['tris'] for p in ped['parts']),
                textures=len(w.images), part_meta=part_meta, used_tex=used_tex)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ydd', default=None, help='单个 .ydd')
    ap.add_argument('--character', action='append', default=[],
                    help='角色前缀（如 cs_dutch_ms1），配合 --model-dir 自动拼装')
    ap.add_argument("--character-file", default=None, help="每行一个角色前缀（批量）")
    ap.add_argument("--single", action="store_true", help="只取单个 .ydd（动物等整只已合并资产）")
    ap.add_argument('--compose-file', default=None,
                    help='JSON: [{"name":..., "ydds":[...]}, ...] 按部件清单拼装')
    ap.add_argument('--model-dir', default='work/npc/models/cutscene')
    ap.add_argument('--tex-index', default='work/npc/index/tex_index.json',
                    help='rdr2_tex_index.py 产出的全局贴图索引')
    ap.add_argument('--out', required=True, help='输出目录')
    ap.add_argument('--name', default=None)
    ap.add_argument('--lod', default='high')
    ap.add_argument('--no-tex', action='store_true')
    ap.add_argument('--exclude', default='', help='逗号分隔；部件名含任一子串则跳过')
    ap.add_argument('--keep-vertex-color', action='store_true',
                    help='导出 COLOR_0（默认关；RDR2 人物的 COLOR0 是调色板选择子，见 write_glb 文档）')
    ap.add_argument('--no-neutralize', action='store_true',
                    help='不把 tint 遮罩贴图（_c*_999_ab / 头发）降饱和（默认会降饱和）')
    ap.add_argument('--only', default='', help='逗号分隔；只保留部件名含任一子串的')
    a = ap.parse_args()

    def filt(ped_obj):
        ex = [x.strip().lower() for x in a.exclude.split(',') if x.strip()]
        on = [x.strip().lower() for x in a.only.split(',') if x.strip()]
        ps = ped_obj['parts']
        if ex:
            ps = [p for p in ps if not any(k in (p['name'] or '').lower() for k in ex)]
        if on:
            ps = [p for p in ps if any(k in (p['name'] or '').lower() for k in on)]
        ped_obj = dict(ped_obj)
        ped_obj['parts'] = ps
        return ped_obj

    tex_index = {} if a.no_tex else load_tex_index(a.tex_index)
    out = []

    def one(name, ydd, ped_obj, extra=None):
        outdir = os.path.join(a.out, name)
        os.makedirs(outdir, exist_ok=True)
        res = write_glb(os.path.join(outdir, name + '.glb'), ped_obj, tex_index,
                        png_dir=os.path.join(outdir, 'textures'),
                        want_tex=not a.no_tex, tex_cache={},
                        keep_vcol=a.keep_vertex_color,
                        neutralize=not a.no_neutralize)
        res['name'] = name
        res['src'] = ydd if ydd else (ped_obj.get('sources') or '')
        res['up_offset'] = ped_obj.get('up_offset')
        if extra:
            res.update(extra)
        with open(os.path.join(outdir, 'manifest.json'), 'w', encoding='utf-8') as fh:
            json.dump(res, fh, ensure_ascii=False, indent=1)
        out.append({k: v for k, v in res.items() if k not in ('part_meta', 'used_tex')})
        return res

    if a.character_file:
        with open(a.character_file, encoding='utf-8') as fh:
            a.character += [ln.strip() for ln in fh if ln.strip()
                            and not ln.strip().startswith('#')]
    if a.ydd:
        name = a.name or os.path.splitext(os.path.basename(a.ydd))[0]
        one(name, a.ydd, filt(parse_ped(a.ydd, a.lod)))
    for ch in a.character:
        ped = (assemble_single if a.single else assemble_character)(a.model_dir, ch)
        if not ped['parts']:
            print('!! 没找到部件:', ch)
            continue
        ped['name'] = ch
        one(ch, None, filt(ped), dict(sources=ped['sources']))
    if a.compose_file:
        spec = json.load(open(a.compose_file, encoding='utf-8'))
        for item in spec:
            parts = []
            src = []
            for y in item['ydds']:
                try:
                    p2 = parse_ped(y)
                except Exception as e:
                    print('  [skip] %s: %s' % (os.path.basename(y), e))
                    continue
                src.append(os.path.basename(y))
                parts.extend(p2['parts'])
            seen = set()
            uniq = []
            for p3 in parts:
                k = p3['albedo'] or ('0x%08x' % p3['hash'])
                if k in seen:
                    continue
                seen.add(k)
                uniq.append(p3)
            obj = dict(parts=uniq, sources=src, name=item['name'])
            one(item['name'], None, filt(obj), dict(sources=src))
    print(json.dumps(out, ensure_ascii=False))
    return out


if __name__ == '__main__':
    main()
