import struct, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rdr2_ycd import parse_sequence, SYS_BASE

def load(path):
    d = open(path, 'rb').read()
    return d, d[16:]

def ptr(body, off):
    return struct.unpack_from('<Q', body, off)[0]

def find_animations(body):
    out = []
    seen = set()
    for o in range(0, len(body)-0x60, 2):
        fr, sl = struct.unpack_from('<HH', body, o)
        if not (5 < fr < 3000): continue
        if not (fr <= sl <= fr + 16): continue
        dur = struct.unpack_from('<f', body, o+4)[0]
        if 0.05 < dur < 40 and abs(dur - fr/30.0) < 0.35:
            base = o - 0x14
            if base in seen: continue
            seen.add(base)
            out.append((base, fr, sl, round(dur, 3), ptr(body, base+0x40)))
    return out

def load_animation(body, base):
    frames, seql = struct.unpack_from('<HH', body, base+0x14)
    dur = struct.unpack_from('<f', body, base+0x18)[0]
    # Sequences: {ptr u64, count u16, cap u16, pad u32}
    sp = ptr(body, base+0x40)
    scount = struct.unpack_from('<H', body, base+0x48)[0]
    seq_ptrs = [ptr(body, sp - SYS_BASE + i*8) for i in range(scount)]
    # BoneIds
    bp = ptr(body, base+0x50)
    bcount = struct.unpack_from('<H', body, base+0x58)[0]
    boneids = []
    if bp:
        o = bp - SYS_BASE
        for i in range(bcount):
            bid, unk, trk = struct.unpack_from('<HBB', body, o + i*4)
            boneids.append((bid, unk, trk))
    seqs = []
    for sp2 in seq_ptrs:
        o = sp2 - SYS_BASE
        dl = struct.unpack_from('<I', body, o+4)[0]
        fo = struct.unpack_from('<I', body, o+0x0C)[0]
        nf, fl = struct.unpack_from('<HH', body, o+0x16)
        iq, qvb = struct.unpack_from('<HH', body, o+0x1A)
        cs, rmc = struct.unpack_from('<BB', body, o+0x1E)
        data = body[o+0x20:o+0x20+dl]
        s = parse_sequence(data, nf, cs, fo, fl)
        seqs.append(dict(data_len=dl, frame_off=fo, nframes=nf, framelen=fl,
                         chunk=cs, rootmotion=rmc, n_animseq=len(s), animseq=s))
    return dict(frames=frames, seqlim=seql, dur=dur, boneids=boneids, seqs=seqs)

if __name__ == '__main__':
    path = sys.argv[1]
    d, body = load(path)
    print(f"=== {os.path.basename(path)} body={len(body)} ===")
    anims = find_animations(body)
    print("animations:", [(hex(o), f, s, du) for o, f, s, du, _ in anims])
    if not anims:
        sys.exit(0)
    base = anims[0][0]
    a = load_animation(body, base)
    print(f" frames={a['frames']} seqlim={a['seqlim']} dur={a['dur']}")
    print(f" boneids={len(a['boneids'])}  sequences={len(a['seqs'])}")
    for si, s in enumerate(a['seqs']):
        print(f"  seq[{si}] nframes={s['nframes']} framelen={s['framelen']} chunk={s['chunk']} rmc={s['rootmotion']} animseqs={s['n_animseq']}")
        # channel type histogram
        from collections import Counter
        tnames = {0:'StaticQuat',1:'StaticVec3',2:'StaticFloat',3:'RawFloat',4:'QuantFloat',
                  5:'IndQuantFloat',6:'LinearFloat',7:'CachedQ1',8:'CachedQ2'}
        hist = Counter()
        widths = Counter()
        for s2 in s['animseq']:
            for ch in s2.channels:
                if ch is not None:
                    hist[tnames[ch.typ]] += 1
            widths[len(s2.channels)] += 1
        print("    channel-type hist:", dict(hist))
        print("    animseq channel widths:", dict(widths))
        # evaluate rotations for first few bones, check unit quaternions + motion
        for bi in range(min(6, len(s['animseq']))):
            s2 = s['animseq'][bi]
            if len(s2.channels) < 3: continue
            mags = []; prev = None; maxd = 0.0
            for f in range(0, s['nframes'], 8):
                try:
                    q = s2.evaluate_quat(f)
                except Exception as e:
                    q = (0,0,0,1)
                mags.append(round(math.sqrt(sum(c*c for c in q)), 4))
                if prev is not None:
                    dot = abs(sum(a1*b1 for a1,b1 in zip(q, prev)))
                    maxd = max(maxd, math.degrees(2*math.acos(min(1.0, dot))))
                prev = q
            print(f"    bone[{bi}] ch={len(s2.channels)} |q|range=[{min(mags):.3f},{max(mags):.3f}] maxstep={maxd:.1f}deg")
