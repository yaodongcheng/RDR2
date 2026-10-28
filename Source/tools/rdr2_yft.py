"""
RDR2 .yft (fragment / RSC8 v58) skeleton extractor.
Empirically located offsets (validated on meta_base_abe.yft):
  Skeleton struct @ 0x024a80  (BonesCount @ +0x5E)
  ParentIndices   @ 0x015000  (335 x int16, root = -1)     <- validated: 0 bad
  Bones[i]        @ 0x00110 + i*0x50                       <- rest quat @+0x20, pos @+0x30
  Name pool       @ 0x026e40..                              (shared-suffix strings)
"""
import struct, sys, re, json, math


def load(path):
    d = open(path, 'rb').read()
    assert struct.unpack_from('<I', d, 0)[0] == 0x38435352, "not RSC8"
    return d, d


def find_skeleton(d):
    """Locate the Skeleton struct: tail = u16 1, u16 BonesCount, u16 ChildIdxCount, u16 0, u32 0, u64 0."""
    n = len(d)
    for o in range(0, n - 18, 2):
        a, b, c, e = struct.unpack_from('<HHHH', d, o)
        if a == 1 and 40 <= b <= 1200 and c <= b + 64 and e == 0:
            if struct.unpack_from('<I', d, o + 8)[0] == 0 and struct.unpack_from('<Q', d, o + 12)[0] == 0:
                return o - 0x5C, b          # struct start, bones count
    return None, None


def read_skeleton(d):
    """Read skeleton. NOTE: offsets below are validated for meta_base_abe.yft;
    other .yft files have different block offsets (use find_skeleton + manual offsets)."""
    par_off = 0x15000
    bones_off = 0x110
    stride = 0x50
    bones_count = struct.unpack_from('<H', d, 0x24a80 + 0x5E)[0]
    parents = [struct.unpack_from('<h', d, par_off + i * 2)[0] for i in range(bones_count)]
    bones = []
    for i in range(bones_count):
        o = bones_off + i * stride
        bones.append(dict(quat=struct.unpack_from('<4f', d, o + 0x20),
                          pos=struct.unpack_from('<3f', d, o + 0x30),
                          nameptr=struct.unpack_from('<I', d, o)[0]))
    return bones_count, parents, bones


def read_skeleton_dyn(d):
    sk, bones_count = find_skeleton(d)
    if sk is None:
        raise RuntimeError("Skeleton struct not found")
    bones_ptr = struct.unpack_from('<Q', d, sk + 0x28)[0]
    par_ptr = struct.unpack_from('<Q', d, sk + 0x40)[0]
    if not (0x50000000 <= bones_ptr < 0x50200000 and 0x50000000 <= par_ptr < 0x50200000):
        raise RuntimeError("skeleton child pointers out of range")
    bones_ptr -= 0x50000000
    par_ptr -= 0x50000000
    bones_off = bones_ptr + 0x40
    stride = 0x50
    par_off = None; parents = None
    for cand in range(par_ptr, par_ptr + 0x80, 2):
        if cand + bones_count * 2 > len(d): break
        v = [struct.unpack_from('<h', d, cand + i * 2)[0] for i in range(bones_count)]
        bad = sum(1 for i, x in enumerate(v) if not (x == -1 or (0 <= x < i)))
        if bad <= 2:
            par_off = cand; parents = v; break
    if par_off is None:
        raise RuntimeError("parent array not found")
    bones = []
    for i in range(bones_count):
        o = bones_off + i * stride
        bones.append(dict(quat=struct.unpack_from('<4f', d, o + 0x20),
                          pos=struct.unpack_from('<3f', d, o + 0x30),
                          nameptr=struct.unpack_from('<I', d, o)[0]))
    return bones_count, parents, bones


def _read_skeleton_hardcoded(d):
    par_off = 0x15000
    bone_off = 0x110
    bone_stride = 0x50
    bones_count = struct.unpack_from('<H', d, 0x24a80 + 0x5E)[0]
    parents = [struct.unpack_from('<h', d, par_off + i * 2)[0] for i in range(bones_count)]
    bones = []
    for i in range(bones_count):
        o = bone_off + i * bone_stride
        bones.append(dict(quat=struct.unpack_from('<4f', d, o + 0x20),
                          pos=struct.unpack_from('<3f', d, o + 0x30),
                          nameptr=struct.unpack_from('<I', d, o)[0]))
    return bones_count, parents, bones


def name_pool(body, lo=0x26e00, hi=0x27c00):
    seg = body[lo:hi]
    return [(lo + m.start(), m.group().decode('latin1'))
            for m in re.finditer(rb'[\x20-\x7e]{3,}', seg)]


def fk(parents, bones, order='xyzw', conj=False, rotmode='parent'):
    def qmul(a, b):
        ax, ay, az, aw = a; bx, by, bz, bw = b
        return (aw*bx+ax*bw+ay*bz-az*by, aw*by-ax*bz+ay*bw+az*bx,
                aw*bz+ax*by-ay*bx+az*bw, aw*bw-ax*bx-ay*by-az*bz)
    def qrot(q, v):
        x, y, z, w = q; vx, vy, vz = v
        tx = 2*(y*vz-z*vy); ty = 2*(z*vx-x*vz); tz = 2*(x*vy-y*vx)
        return (vx+w*tx+(y*tz-z*ty), vy+w*ty+(z*tx-x*tz), vz+w*tz+(x*ty-y*tx))
    def norm(q):
        n = math.sqrt(sum(c*c for c in q)) or 1
        return tuple(c/n for c in q)
    Wp = [None]*len(bones); Wq = [None]*len(bones)
    for i, b in enumerate(bones):
        q0 = b['quat']; p = b['pos']
        q = norm(q0 if order == 'xyzw' else (q0[3], q0[0], q0[1], q0[2]))
        if conj: q = (-q[0], -q[1], -q[2], q[3])
        pi = parents[i]
        if pi < 0 or Wp[pi] is None:
            Wp[i] = (0.0, 0.0, 0.0); Wq[i] = q
        else:
            r = qrot(q if rotmode == 'own' else Wq[pi], p)
            Wp[i] = (Wp[pi][0]+r[0], Wp[pi][1]+r[1], Wp[pi][2]+r[2])
            Wq[i] = qmul(Wq[pi], q)
    return Wp


if __name__ == '__main__':
    path = sys.argv[1]
    d, body = load(path)
    n, parents, bones = read_skeleton(d)
    print(f"bones={n} roots={sum(1 for p in parents if p<0)} maxdepth=", end='')
    depth = [0]*n
    for i, p in enumerate(parents):
        depth[i] = 0 if p < 0 else depth[p]+1
    print(max(depth))
    print("first 8:", [(i, parents[i], tuple(round(v, 3) for v in bones[i]['pos'])) for i in range(8)])
    pool = name_pool(d)
    print("name-pool entries:", len(pool))
    for o, s in pool[:12]:
        print(f"  {o:#08x} {s}")
    for v in ('xyzw', 'wxyz'):
        W = fk(parents, bones, order=v)
        xs = [p[0] for p in W]; ys = [p[1] for p in W]; zs = [p[2] for p in W]
        print(f"FK {v}: span=({max(xs)-min(xs):.2f},{max(ys)-min(ys):.2f},{max(zs)-min(zs):.2f})")
