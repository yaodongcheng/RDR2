# -*- coding: utf-8 -*-
"""探针：把一块 .yad 里每条动画的通道/位移范围打出来，找出「相机」那条的特征"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ycd_decode as Y
from rdr2_ycd import (C_STATIC_QUAT, C_STATIC_VEC3, C_STATIC_FLOAT, C_RAW_FLOAT,
                      C_QUANT_FLOAT, C_IND_QUANT_FLOAT, C_LINEAR_FLOAT, C_CACHED_Q1, C_CACHED_Q2)

TNAME = {0: 'SQuat', 1: 'SVec3', 2: 'SFloat', 3: 'RawF', 4: 'QuantF', 5: 'IndQ', 6: 'LinF',
         7: 'CQ1', 8: 'CQ2'}


def anim_stats(a):
    out = []
    for si, s in enumerate(a['seqs']):
        for k, s2 in enumerate(s['animseq']):
            chans = [c for c in s2.channels if c is not None]
            types = [TNAME.get(c.typ, '?') for c in chans]
            floats = []
            for c in chans:
                if c.typ in (C_STATIC_FLOAT, C_QUANT_FLOAT, C_IND_QUANT_FLOAT, C_RAW_FLOAT, C_LINEAR_FLOAT):
                    vals = [c.eval_float(f) for f in range(min(a['frames'], 4000))]
                    vals = [v for v in vals if abs(v) < 1e6]
                    if vals:
                        floats.append((round(min(vals), 2), round(max(vals), 2)))
            out.append(dict(seq=si, idx=k, n=len(chans), types=types,
                            float_ranges=floats[:6]))
    return out


def main(path):
    _, body = Y.load(path)
    anims = Y.find_animations(body)
    print('==', os.path.basename(path), 'anims', len(anims))
    for base, fr, sl, dur, _ in anims:
        a = Y.load_animation(body, base)
        st = anim_stats(a)
        span = 0.0
        for s in st:
            for lo, hi in s['float_ranges']:
                span = max(span, abs(hi - lo))
        print(f'  @{base:#x} frames={fr:4d} dur={dur:6.3f}s seqs={len(a["seqs"])} '
              f'bones={len(a["boneids"])} 位移跨度≈{span:.2f}  animseqs={len(st)}')
        for s in st[:6]:
            print(f'      [{s["seq"]}.{s["idx"]}] ch={s["n"]} {",".join(s["types"][:8])} '
                  f'range={s["float_ranges"][:3]}')


if __name__ == '__main__':
    main(sys.argv[1])
