"""探针：读人物 .ydd 子 drawable 的顶点声明（找 UV / 蒙皮权重）。

用法: uv run python tools/probe_ped_vdecl.py <file.ydd> [...]
"""
import sys, os, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rdr2_ydr as Y
import rdr2_vdecl as V


def dump_geom(res, g, label):
    go = res.off(g)
    if go is None:
        return None
    vb = Y.parse_vertex_buffer(res, res.u64(go + 0x08))
    ib = Y.parse_index_buffer(res, res.u64(go + 0x10))
    if not vb:
        return None
    vd = V.parse_vdecl(res, res.u64(vb['off'] + 0x38))
    print(f"    {label}: vc={vb['count']} stride={vb['stride']} "
          f"vdecl={'yes' if vd else 'NONE'} SOA={vd['hassoa'] if vd else '-'} "
          f"declVS={vd['vertex_size'] if vd else '-'} declVC={vd['vertex_count'] if vd else '-'}")
    if vd:
        for i, name, fmt, comps, off, step in V.elements(vd):
            tag = ''
            if name.startswith('TEXCOORD'):
                arr = V.read_element(res, vb['data'], vd, i, limit=8)
                tag = ' sample=' + str([[round(float(c), 4) for c in v] for v in arr[:3]])
            elif name.startswith('BLEND'):
                arr = V.read_element(res, vb['data'], vd, i, limit=8)
                tag = ' sample=' + str(arr[:3])
            print(f"      elem[{i:2}] {name:<14} {fmt:<20} comps={comps} off={off:<5} step={step}{tag}")
    return vb


def probe(path, max_geoms=99):
    print("=" * 78)
    print(os.path.basename(path))
    res = Y.Res(open(path, 'rb').read())
    entries = Y.parse_drawable_dictionary(res)
    for h, off in entries[:max_geoms]:
        try:
            models = Y.pointer_list(res, res.u64(off + 0x50))
        except Exception as e:
            print(f"  hash={h:#010x} ERR {e}")
            continue
        skel = res.u64(off + 0x18)
        print(f"  hash={h:#010x} off={off:#x} models={len(models)} skeleton={skel:#x} "
              f"shadergrp={res.u64(off + 0x10):#x}")
        for mi, m in enumerate(models):
            for gi, g in enumerate(Y.parse_model_geoms(res, m)):
                dump_geom(res, g, f"m{mi}.g{gi}")


if __name__ == '__main__':
    for p in sys.argv[1:]:
        probe(p, 4)
