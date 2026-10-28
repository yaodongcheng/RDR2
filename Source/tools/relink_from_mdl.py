# -*- coding: utf-8 -*-
"""按 **.mdl 里的子网格**给 blend 重挂材质（修"槽数 ≠ 子网格数 → relink 跳过"）。

## 为什么

`relink_materials.py` 用 `index.json` 的 `s` 当目标槽列表，要求 `len(材质槽) == len(s)`。
但构建时用的是 `.mdl` 里**过滤后**的子网格（`ic==0 / vc==0 / 索引越界` 的段会被丢掉），
所以有些网格的槽数比 `s` 少 → relink 只能跳过（v10 实测跳过 **2,179** 个，全是 `.ydd` 新模型）。

本工具不猜：直接读该网格对应的 `.mdl`，用**和构建完全相同**的过滤规则算出有效子段，
再按"一个子网格一个槽"挂 `alb_<贴图名>` 材质。这样槽数天然对得上。

    blender -b <blend> --python tools/_unbuffer.py -P tools/relink_from_mdl.py [-- --dry]
"""
import bpy
import os
import sys
import json
import struct
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')
MAGIC = b'RMDL1' + bytes(3)
SUB = struct.Struct('<7I')


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def load_index():
    d = json.load(open(INDEX, encoding='utf-8'))
    return d['models'], {t['id']: t for t in d['tex']}


def _slug(name, limit=58):
    import re as _re
    s = _re.sub(r'[^0-9A-Za-z_.-]+', '_', (name or '')).strip('_')
    return s[:limit] or 'noname'


def _set_image(m, fp, texname):
    nt = m.node_tree
    nodes = [n for n in nt.nodes if n.type == 'TEX_IMAGE']
    cur = nodes[0] if nodes else None
    if cur is not None and cur.image and \
            os.path.abspath(bpy.path.abspath(cur.image.filepath)) == os.path.abspath(fp):
        return
    img = bpy.data.images.load(fp, check_existing=True)
    img.colorspace_settings.name = 'sRGB'
    if cur is None:
        cur = nt.nodes.new('ShaderNodeTexImage')
        cur.location = (-380, 200)
        bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bsdf is None:
            return
        nt.links.new(cur.outputs['Color'], bsdf.inputs['Base Color'])
    cur.image = img
    cur.label = texname


def make_material(tinfo):
    texname = (tinfo or {}).get('n') or ''
    rel = (tinfo or {}).get('f') or ''
    name = ('alb_' + _slug(texname)) if texname else 'nonalbedo_warmgray'
    fp = os.path.join(LIB, rel.replace('/', os.sep)) if rel else ''
    m = bpy.data.materials.get(name)
    if m:
        if texname and fp and os.path.exists(fp):
            m['albedo'] = texname
            _set_image(m, fp, texname)
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        return m
    if texname and fp and os.path.exists(fp):
        m['albedo'] = texname
        _set_image(m, fp, texname)
        bsdf.inputs['Roughness'].default_value = 0.72
    else:
        bsdf.inputs['Base Color'].default_value = (0.30, 0.27, 0.23, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.85
        m.diffuse_color = (0.30, 0.27, 0.23, 1.0)
    m.roughness = 0.85
    return m


def valid_subs(mdl_path):
    """与 blender_continent.load_model_mesh 同样的过滤：只要 ic>0 且 vc>0 的段。"""
    try:
        buf = open(mdl_path, 'rb').read()
    except Exception:
        return None
    if buf[:8] != MAGIC:
        return None
    nsub = struct.unpack_from('<I', buf, 8)[0]
    o = 12 + 24
    out = []
    for _ in range(nsub):
        tid, vc, ic, po, no, uo, io_ = SUB.unpack_from(buf, o)
        o += SUB.size
        if ic == 0 or vc == 0:
            continue
        out.append(tid)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args(argv())

    models, tex = load_index()
    print('[rm] 库内模型 %d，贴图 %d' % (len(models), len(tex)))

    done = changed = skipped = nohash = 0
    for ob in bpy.data.objects:
        if ob.type != 'MESH':
            continue
        hx = ob.get('hash')
        if not hx:
            nohash += 1
            continue
        e = models.get(hx)
        if not e:
            continue
        tids = valid_subs(os.path.join(LIB, e['f']))
        if not tids:
            continue
        me = ob.data
        if len(me.materials) != len(tids):
            skipped += 1
            continue
        if a.dry:
            done += 1
            continue
        for i, tid in enumerate(tids):
            tinfo = tex.get(tid) if tid not in (0xFFFFFFFF, 0xFFFF) else None
            m = make_material(tinfo) if tinfo else None
            if m is None:
                continue
            if me.materials[i] is not m:
                me.materials[i] = m
                changed += 1
        done += 1

    print('[rm] 处理网格 %d，换材质槽 %d；槽数仍不匹配 %d；无 hash %d'
          % (done, changed, skipped, nohash))
    if a.dry:
        print('[rm] dry-run')
        return
    out = bpy.data.filepath
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print('[rm] saved %s (%.2f GB)' % (out, os.path.getsize(out) / 1e9))


if __name__ == '__main__':
    main()
