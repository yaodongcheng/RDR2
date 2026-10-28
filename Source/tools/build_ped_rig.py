"""用【运行期 dump 的 ped 骨架】造一套干净骨架，并把 `.ycd` 动作按 `pose = R_ped_rest ⊗ q` 直接套上去。

为什么换 ped 骨架：
  * 动画本来就是给 ped（124 骨）做的；我们模型绑的 metaped（756 骨）里 Spine0-6、Pelt* 都是装饰，
    两者只有 24 个同名核心骨，逐骨常量对齐在拓扑不一致时必然崩。
  * ped 的 rest 直接来自游戏内存（`work/npc/live/idle_*.tsv`），是**真正的动画参考帧**，
    所以不需要任何 90°/de-bias 补丁。

做法：
  1. 取 ped 的局部 rest 四元数（内存 dump）+ 与 metaped 的**同名骨**（24 根核心骨，拓扑一致）
  2. 骨长/位置沿用 metaped 的 bind（几何正确）
  3. 动作：R_local = R_ped_rest ⊗ q        ← 与游戏内部一致
  4. 输出 glTF（骨架 + 动画），供 blender_bind_player_walk.py 绑网格

用法: python tools/build_ped_rig.py <anim.json> <out.gltf> [--name X]
"""
import glob
import json
import math
import os
import struct
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKEL = os.path.join(PROJ, 'export/skeleton_runtime/yft_skel.json')
BIND = os.path.join(PROJ, 'export/skeleton_runtime/yft_bind.json')


def qmul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return (aw*bx+ax*bw+ay*bz-az*by, aw*by-ax*bz+ay*bw+az*bx,
            aw*bz+ax*by-ay*bx+az*bw, aw*bw-ax*bx-ay*by-az*bz)


def qnorm(q):
    n = math.sqrt(sum(c*c for c in q)) or 1.0
    return tuple(c/n for c in q)


Q_FIX = (math.sin(math.radians(-45)), 0.0, 0.0, math.cos(math.radians(-45)))
Q_FIX_INV = (-Q_FIX[0], -Q_FIX[1], -Q_FIX[2], Q_FIX[3])


def conv_q(q):
    return qnorm(qmul(qmul(Q_FIX, qnorm(q)), Q_FIX_INV))


def conv_t(t):
    return (t[0], t[2], -t[1])


def mat_to_quat(R):
    m = R
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        return qnorm(((m[2][1]-m[1][2])/s, (m[0][2]-m[2][0])/s, (m[1][0]-m[0][1])/s, 0.25*s))
    if m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0+m[0][0]-m[1][1]-m[2][2])*2
        return qnorm((0.25*s, (m[0][1]+m[1][0])/s, (m[0][2]+m[2][0])/s, (m[2][1]-m[1][2])/s))
    if m[1][1] > m[2][2]:
        s = math.sqrt(1.0+m[1][1]-m[0][0]-m[2][2])*2
        return qnorm(((m[0][1]+m[1][0])/s, 0.25*s, (m[1][2]+m[2][1])/s, (m[0][2]-m[2][0])/s))
    s = math.sqrt(1.0+m[2][2]-m[0][0]-m[1][1])*2
    return qnorm(((m[0][2]+m[2][0])/s, (m[1][2]+m[2][1])/s, 0.25*s, (m[1][0]-m[0][1])/s))


def main():
    anim_json, out_gltf = sys.argv[1], sys.argv[2]
    name = 'rdr2_walk'
    if '--name' in sys.argv:
        name = sys.argv[sys.argv.index('--name') + 1]

    # ---- ped rest（内存 dump）
    live_tsv = sorted(glob.glob(os.path.join(PROJ, 'work/npc/live/idle_*.tsv')))[-1]
    ped_q = {}
    for l in open(live_tsv, encoding='utf-8').read().splitlines()[1:]:
        c = l.split('\t')
        ped_q[c[1]] = tuple(float(x) for x in c[2:6])
    print('[ped] rest 来自 %s（%d 骨）' % (os.path.basename(live_tsv), len(ped_q)))

    # ---- metaped 骨架（取名/父/位置）
    sk = json.load(open(SKEL, encoding='utf-8'))
    bind = json.load(open(BIND, encoding='utf-8'))
    bones = {b['i']: b for b in sk['bones']}
    byname = {}
    for i, b in bones.items():
        byname.setdefault(b['name'], i)

    # 只保留「ped 有 rest」且「metaped 有位置」的骨
    keep = [n for n in ped_q if n in byname and str(bones[byname[n]]['tag']) in bind]
    keep.sort(key=lambda n: byname[n])
    keepset = set(keep)
    print('[ped] 交集核心骨 %d 根' % len(keep))

    # 父 = metaped 里最近的、仍在集合内的祖先
    parent = {}
    for n in keep:
        p = bones[byname[n]]['parent']
        while p in bones and bones[p]['name'] not in keepset:
            p = bones[p]['parent']
        parent[n] = bones[p]['name'] if (p in bones and bones[p]['name'] in keepset) else None

    # 世界位置（metaped bind 的 pos 是骨末端）
    G = {}
    for n in keep:
        d = bind[str(bones[byname[n]]['tag'])]
        G[n] = d['pos']
    HEAD = {}
    for n in keep:
        pn = parent[n]
        HEAD[n] = G[pn] if pn else G[n]

    # 局部平移（用 metaped 的世界旋转把差值转回父空间）
    # 世界旋转：用 metaped 局部 rest 累积（父可能被跳过，取最近保留祖先的旋转做近似）
    def local_rot_to_world():
        W = {}
        order = sorted(keep, key=lambda n: byname[n])
        for n in order:
            pn = parent[n]
            Rp = W.get(pn, [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]])
            # metaped 局部旋转
            i = byname[n]
            p = bones[i]['parent']
            if p in bones and str(bones[p]['tag']) in bind and bones[p]['name'] in keepset:
                # 用 metaped 局部
                pass
            R7 = [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]
            W[n] = Rp
        return W

    # ★ 局部平移必须转到**父骨的局部坐标系**：t_local = R_parent_worldᵀ · (HEAD_i − HEAD_parent)
    #   （直接拿世界差值会在链上越走越歪 —— 实测骨架高度只剩 0.5 m）
    def q2m3_(q):
        x, y, z, w = qnorm(q)
        return [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]

    import numpy as _np
    WR = {}
    def _wr(n):
        if n in WR:
            return WR[n]
        pn = parent[n]
        Rp = _wr(pn) if pn else _np.eye(3)
        WR[n] = Rp @ _np.array(q2m3_(ped_q[n]), float)
        return WR[n]
    for n in keep:
        _wr(n)

    LOC_T = {}
    for n in keep:
        pn = parent[n]
        h = _np.array(HEAD[n], float)
        hp = _np.array(HEAD[pn], float) if pn else _np.zeros(3)
        Rp = _wr(pn) if pn else _np.eye(3)
        LOC_T[n] = (Rp.T @ (h - hp)).tolist()

    # ---- 动画
    A = json.load(open(anim_json, encoding='utf-8'))
    anim = A['animations'][0]
    tag2name = {}
    for i, b in bones.items():
        tag2name.setdefault(b['tag'], b['name'])
    tracks = {}
    for b in anim['bones']:
        nm = tag2name.get(b['boneId'])
        if nm in keepset:
            tracks[nm] = b['quats']
    nframes = anim['frames']
    print('[ped] 动画轨 %d 条 / %d 帧' % (len(tracks), nframes))

    # ---- 写 glTF
    nodes, pos_of = [], {}
    for k, n in enumerate(keep):
        pos_of[n] = k
        q_rest = ped_q[n]
        nodes.append(dict(name=n,
                          translation=[round(x, 6) for x in conv_t(LOC_T[n])],
                          rotation=[round(x, 8) for x in conv_q(q_rest)],
                          children=[]))
    for n in keep:
        pn = parent[n]
        if pn:
            nodes[pos_of[pn]]['children'].append(pos_of[n])
    for nd in nodes:
        if not nd['children']:
            del nd['children']
    roots = [pos_of[n] for n in keep if not parent[n]]

    buf = bytearray(); views = []; accessors = []

    def add_f32(vals, typ='VEC4'):
        off = len(buf)
        buf.extend(struct.pack('<%df' % len(vals), *vals))
        while len(buf) % 4:
            buf.append(0)
        views.append(dict(buffer=0, byteOffset=off, byteLength=len(vals) * 4))
        n = {'SCALAR': 1, 'VEC3': 3, 'VEC4': 4}[typ]
        accessors.append(dict(bufferView=len(views) - 1, componentType=5126,
                              count=len(vals) // n, type=typ))
        return len(accessors) - 1

    times = [f / 30.0 for f in range(nframes)]
    tacc = add_f32(times, 'SCALAR')
    accessors[tacc]['min'] = [times[0]]
    accessors[tacc]['max'] = [times[-1]]

    samplers, channels = [], []
    for n, quats in tracks.items():
        arr = []
        q_rest = ped_q[n]
        for f in range(nframes):
            q = qnorm(tuple(quats[min(f, len(quats) - 1)]))
            arr.extend(conv_q(qmul(q_rest, q)))      # ★ pose = R_rest ⊗ q
        vacc = add_f32(arr)
        samplers.append(dict(input=tacc, output=vacc, interpolation='LINEAR'))
        channels.append(dict(sampler=len(samplers) - 1,
                             target=dict(node=pos_of[n], path='rotation')))

    # ---- 让 Blender 认出骨架：需要一个 skin（+ 一个占位网格）
    def q2m3(q):
        x, y, z, w = qnorm(q)
        return [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]

    import numpy as np
    GW = {}
    order_top = []

    def _topo(n):
        pn = parent[n]
        if pn and pn not in GW:
            _topo(pn)
        R = np.array(q2m3(ped_q[n]), float)
        t = np.array(LOC_T[n], float)
        if pn:
            Rp = GW[pn][:3, :3]
            tp = GW[pn][:3, 3]
            M = np.eye(4)
            M[:3, :3] = R
            M[:3, 3] = Rp @ t + tp
        else:
            M = np.eye(4)
            M[:3, :3] = R
            M[:3, 3] = t
        GW[n] = M
    for n in keep:
        _topo(n)

    ibm = []
    for n in keep:
        inv = np.linalg.inv(GW[n])
        ibm.extend(np.ascontiguousarray(inv.T).ravel().tolist())   # column-major
    ibm_off = len(buf)
    buf.extend(struct.pack('<%df' % len(ibm), *ibm))
    views.append(dict(buffer=0, byteOffset=ibm_off, byteLength=len(ibm) * 4))
    accessors.append(dict(bufferView=len(views) - 1, componentType=5126,
                          count=len(ibm) // 16, type='MAT4'))
    ibm_acc = len(accessors) - 1

    # 占位三角（Blender 导入用；绑定后会删掉）
    pos = [0.0, 0.0, 0.0, 0.01, 0.0, 0.0, 0.0, 0.01, 0.0]
    poff = len(buf); buf.extend(struct.pack('<9f', *pos))
    views.append(dict(buffer=0, byteOffset=poff, byteLength=36))
    accessors.append(dict(bufferView=len(views) - 1, componentType=5126, count=3, type='VEC3'))
    pacc = len(accessors) - 1
    joints = [0, 0, 0, 0] * 3
    joff = len(buf); buf.extend(struct.pack('<12H', *joints))
    views.append(dict(buffer=0, byteOffset=joff, byteLength=24))
    accessors.append(dict(bufferView=len(views) - 1, componentType=5123, count=3, type='VEC4'))
    jacc = len(accessors) - 1
    wts = [1.0, 0.0, 0.0, 0.0] * 3
    woff = len(buf); buf.extend(struct.pack('<12f', *wts))
    views.append(dict(buffer=0, byteOffset=woff, byteLength=48))
    accessors.append(dict(bufferView=len(views) - 1, componentType=5126, count=3, type='VEC4'))
    wacc = len(accessors) - 1

    meshes = [dict(primitives=[dict(attributes=dict(POSITION=pacc, JOINTS_0=jacc, WEIGHTS_0=wacc),
                                   mode=4)])]
    skins = [dict(joints=[pos_of[n] for n in keep], inverseBindMatrices=ibm_acc, skeleton=roots[0])]
    stub = len(nodes)
    nodes.append(dict(name='ped_rig_stub', mesh=0, skin=0))

    import base64
    gltf = dict(
        asset=dict(version='2.0', generator='rdr2-ped-rig'),
        scene=0, scenes=[dict(nodes=roots + [stub])],
        nodes=nodes,
        meshes=meshes, skins=skins,
        animations=[dict(name=name, channels=channels, samplers=samplers)],
        accessors=accessors, bufferViews=views,
        buffers=[dict(byteLength=len(buf),
                      uri='data:application/octet-stream;base64,' + base64.b64encode(bytes(buf)).decode())],
    )
    json.dump(gltf, open(out_gltf, 'w'), separators=(',', ':'))
    print('[ped] 写出 %s（%d 骨 / %d 动画轨 / %d 帧）' % (out_gltf, len(keep), len(tracks), nframes))


if __name__ == '__main__':
    main()
