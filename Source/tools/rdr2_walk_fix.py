"""从 .ycd 解码「旋转轨」并导出成 export_gltf_source.py 能吃的 JSON（带两处关键修正）。

两个修正（都用数据验证过，见 RDR2_ycd动画解码.md §7）
----------------------------------------------------
1. **CachedQuaternion 的 w 位**：RDR2 的缓存四元数把「3 个显式分量 + 缓存通道」当作
   (x, y, z, w)，`quat_index` 不是"缺失分量位置"。按 CodeWalker 的 quat_index 摆放会把
   「三个显式分量全 0、缓存 = 1」的骨解成 (0,0,1,0) 这类 180° 翻转
   （实测：idle 的 SKEL_R_Clavicle、walk 的 SKEL_Spine6、SKEL_R_Forearm …）。
   改成恒按 (x,y,z,w) 后，idle/walk 的骨架立刻直立（head.z 0.35 → 0.64）。

2. **每骨常量基准去除（--debias）**：部分骨的整段旋转带一个常量（单帧只动 0.3~4°），
   是"动画参考骨架 rest ≠ 本骨架 rest"的残差。可选把它们减掉；默认关（先用 1 的结果看）。

用法：
  uv run python tools/rdr2_walk_fix.py <in.ycd> <out.json> [--anim N] [--debias]
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ycd_decode import load, find_animations, load_animation
from rdr2_ycd import ChCachedQuat


def qmul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return (aw*bx+ax*bw+ay*bz-az*by, aw*by-ax*bz+ay*bw+az*bx,
            aw*bz+ax*by-ay*bx+az*bw, aw*bw-ax*bx-ay*by-az*bz)


def qinv(q):
    x, y, z, w = q
    return (-x, -y, -z, w)


def qnorm(q):
    n = math.sqrt(sum(c*c for c in q)) or 1.0
    return tuple(c/n for c in q)


def qdot(a, b):
    return sum(x*y for x, y in zip(a, b))


def m2q_local(R):
    """3x3 → 四元数(x,y,z,w)"""
    m = R
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s_ = math.sqrt(tr + 1.0) * 2
        return qnorm(((m[2][1]-m[1][2])/s_, (m[0][2]-m[2][0])/s_, (m[1][0]-m[0][1])/s_, 0.25*s_))
    if m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s_ = math.sqrt(1.0+m[0][0]-m[1][1]-m[2][2])*2
        return qnorm((0.25*s_, (m[0][1]+m[1][0])/s_, (m[0][2]+m[2][0])/s_, (m[2][1]-m[1][2])/s_))
    if m[1][1] > m[2][2]:
        s_ = math.sqrt(1.0+m[1][1]-m[0][0]-m[2][2])*2
        return qnorm(((m[0][1]+m[1][0])/s_, 0.25*s_, (m[1][2]+m[2][1])/s_, (m[0][2]-m[2][0])/s_))
    s_ = math.sqrt(1.0+m[2][2]-m[0][0]-m[1][1])*2
    return qnorm(((m[0][2]+m[2][0])/s_, (m[1][2]+m[2][1])/s_, 0.25*s_, (m[1][0]-m[0][1])/s_))


def qmean(qs):
    acc = [0.0, 0.0, 0.0, 0.0]
    ref = qs[0]
    for q in qs:
        q = q if qdot(q, ref) >= 0 else tuple(-x for x in q)
        for i in range(4):
            acc[i] += q[i]
    n = math.sqrt(sum(c*c for c in acc)) or 1.0
    return tuple(c/n for c in acc)


def eval_quat_fixed(seq, f, nframes_hint=None):
    """按 (x,y,z,w) 语义取四元数：
    - 有 CachedQuat 通道：3 个显式 = x,y,z；缓存值 = w
    - 没有 CachedQuat（3 显式）：w = sqrt(1-x²-y²-z²)
    - 单 StaticQuat：直接取 q
    """
    cache = None
    for c in seq.channels:
        if isinstance(c, ChCachedQuat):
            cache = c
            break
    if cache is not None:
        v = [0.0, 0.0, 0.0]
        for k in range(3):
            ch = seq.channels[k] if k < len(seq.channels) else None
            v[k] = ch.eval_float(f) if ch is not None and not isinstance(ch, ChCachedQuat) else 0.0
        w = cache.eval_float(f)
        return qnorm((v[0], v[1], v[2], w))
    return tuple(qnorm(seq.evaluate_quat(f)))


THIGH_TAGS = {65478, 6884}      # SKEL_L_Thigh / SKEL_R_Thigh


def q_axis(axis, deg):
    h = math.radians(deg) / 2
    return (axis[0]*math.sin(h), axis[1]*math.sin(h), axis[2]*math.sin(h), math.cos(h))


# ★ 大腿骨的「动画参考帧」与 .yft bind 差一个绕 X 的 90°：
#   .yft 里大腿 local Z → 世界 X（矢状轴），而动画数据把摆动放在 local Y（= 世界的横轴/外展轴）
#   ⇒ 表现为"腿在水平面左右摆"。实测把大腿按 D⁻¹ q D 共轭一次（D = 绕 X −90°）后，
#   双脚轨迹从 X0.52/Y0.47 变成 X0.19/Y0.68（横向几乎不动、前后 0.68 m），才是真走路。
THIGH_FRAME_FIX = q_axis((1.0, 0.0, 0.0), -90.0)


def repair_ramp_channels(seq):
    """把"整段线性爬升/回落、且占满通道量程"的通道判定为解码损坏并压成常量。

    实测 SKEL_L_Thigh 的 z 通道（15 bit / quantum 1.3e-4 / offset −4.31）从 0 匀速爬到 −4.31，
    占满量程 ⇒ 四元数模长爆掉、大腿翻 180°。x/y 是好的（和右腿对称），只有 z 坏。
    """
    fixed = 0
    for c in seq.channels:
        if c is None or not getattr(c, 'values', None):
            continue
        v = c.values
        n = len(v)
        if n < 12:
            continue
        lo, hi = min(v), max(v)
        span = hi - lo
        if span <= 1e-9:
            continue
        full = getattr(c, 'quantum', 0.0) * ((1 << getattr(c, 'value_bits', 0)) - 1)
        if not full or span < 0.6 * full:
            continue
        diffs = [v[i+1] - v[i] for i in range(0, n-1, max(1, n//8))]
        if not (all(d >= 0 for d in diffs) or all(d <= 0 for d in diffs)):
            continue
        if abs(v[-1] - v[0]) < 0.8 * span:
            continue
        med = sorted(v[:8])[len(v[:8])//2]
        c.values = [med] * n
        fixed += 1
    return fixed


CALF_TAGS = {55120, 43312}      # L/R Calf（膝）


def scale_angle(q, k):
    """把四元数的旋转角按 k 缩放（轴不变）。用于补足片段里偏小的关节幅度。"""
    w = max(-1.0, min(1.0, q[3]))
    ang = 2*math.acos(abs(w))
    if ang < 1e-6:
        return q
    if w < 0:
        q = tuple(-x for x in q)
    v = (q[0], q[1], q[2])
    n = math.sqrt(sum(x*x for x in v)) or 1.0
    na = min(math.pi*0.98, ang*k)
    s2 = math.sin(na/2.0)
    return (v[0]/n*s2, v[1]/n*s2, v[2]/n*s2, math.cos(na/2.0))


ARM_TAGS = {
    30226, 54802,          # L/R Clavicle
    37873, 46065,          # L/R UpperArm
    53675, 54187,          # L/R Forearm
    34606, 22798,          # L/R Hand
    33869, 4126,           # CH_L/R_Hand
}


def clamp_deg(q, lim_deg):
    """把四元数 q 的旋转角限制在 lim_deg 以内（超出则按比例缩角）。"""
    w = max(-1.0, min(1.0, q[3]))
    ang = 2*math.degrees(math.acos(abs(w)))
    if ang <= lim_deg or ang < 1e-6:
        return q
    k = lim_deg / ang
    if w < 0:
        q = tuple(-x for x in q)
    s = math.sin(math.radians(ang*k/2))
    c = math.cos(math.radians(ang*k/2))
    v = (q[0], q[1], q[2])
    n = math.sqrt(sum(x*x for x in v)) or 1.0
    return (v[0]/n*s, v[1]/n*s, v[2]/n*s, c)


def main():
    path, out_json = sys.argv[1], sys.argv[2]
    debias = '--debias' in sys.argv
    armclamp = float(sys.argv[sys.argv.index('--clamp-arms')+1]) if '--clamp-arms' in sys.argv else 0.0
    fix_thigh = '--fix-thigh-axis' in sys.argv
    fix_arm = '--fix-arm-axis' in sys.argv
    keep_arm_bias = '--keep-arm-bias' in sys.argv
    drop_root = '--drop-root' in sys.argv
    align_live = sys.argv[sys.argv.index('--align-live')+1] if '--align-live' in sys.argv else None
    knee_gain = float(sys.argv[sys.argv.index('--knee-gain')+1]) if '--knee-gain' in sys.argv else 1.0
    fix_ramp = '--repair-ramps' in sys.argv

    # ★ 用运行期 dump 的 rest 做"精确对齐"：
    #   pose = R_src_local ⊗ q；我们写 R_ours_local ⊗ (D ⊗ q)，其中 D = R_ours⁻¹ ⊗ R_src
    #   ⇒ 等价于让每根骨都回到游戏真实的动画参考帧（而不是靠均值 de-bias 猜）。
    ALIGN = {}
    if align_live:
        import json as _js
        SK = _js.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                        'export/skeleton_runtime/yft_skel.json'), encoding='utf-8'))
        tag2name = {}
        for b in SK['bones']:
            tag2name.setdefault(b['tag'], b['name'])
        live = {}
        for l in open(align_live, encoding='utf-8').read().splitlines()[1:]:
            c = l.split('	')
            live[c[1]] = tuple(float(x) for x in c[2:6])
        # yft 局部 rest
        BI = _js.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                        'export/skeleton_runtime/yft_bind.json'), encoding='utf-8'))
        G = {}
        for b in SK['bones']:
            d0 = BI.get(str(b['tag']))
            if d0:
                G[b['i']] = (d0['rot'], d0['pos'])
        # 局部 rest（用父子链）
        bones = {b['i']: b for b in SK['bones']}
        Loc = {}
        order, seen = [], set()
        def _o(i):
            if i in seen or i not in bones:
                return
            _o(bones[i]['parent']); seen.add(i); order.append(i)
        for i in bones: _o(i)
        for i in order:
            p_ = bones[i]['parent']
            if i in G:
                R_, t_ = G[i]
                if p_ in G:
                    Rp_ = G[p_][0]
                    Rt = [[sum(Rp_[c][k]*R_[k][cc] for k in range(3)) for cc in range(3)] for c in range(3)]
                    Loc[i] = Rt
                else:
                    Loc[i] = R_
        for i, Rloc in Loc.items():
            nm = bones[i]['name']
            if nm in live:
                # D = R_ours⁻¹ ⊗ R_src
                ALIGN[bones[i]['tag']] = (nm, Rloc, live[nm])
        print('[align] 用 %d 根骨的 live rest 做精确对齐（%s）'
              % (len(ALIGN), os.path.basename(align_live)))

    d, body = load(path)
    anims = find_animations(body)
    if not anims:
        raise SystemExit('没扫到 Animation 块')

    if '--anim' in sys.argv:
        ai = int(sys.argv[sys.argv.index('--anim')+1])
    elif '--auto' in sys.argv:
        # 与旧管线一致：取"总运动量最大"的那一段
        # 打分 = (动起来的轨道数, 总运动量)。只按运动量排会被"单轨狂抖"的退化块骗到
        # （实测 pickup_body 的 block1/3 只有 1 条 root 轨在乱翻，总角度却最高）。
        best, ai = (-1, -1.0), 0
        for k, (b0, fr0, sl0, du0, sp0) in enumerate(anims):
            a0 = load_animation(body, b0)
            s0 = a0['seqs'][0]
            tot = 0.0
            nmov = 0
            for bi0, q0 in enumerate(s0['animseq']):
                if bi0 >= len(a0['boneids']):
                    break
                if a0['boneids'][bi0][2] != 1 or not q0.channels:
                    continue
                try:
                    # 用与导出同一套语义（eval_quat_fixed）打分，否则会和实际导出的数据不一致
                    qq = [eval_quat_fixed(q0, f) for f in range(0, s0['nframes'], 4)]
                except Exception:
                    continue
                mx = 0.0
                for j in range(1, len(qq)):
                    d0 = min(1.0, abs(sum(x*y for x, y in zip(qq[j], qq[j-1]))))
                    mx = max(mx, math.degrees(2*math.acos(d0)))
                tot += mx
                if mx > 2.0:
                    nmov += 1
            if (nmov, tot) > best:
                best, ai = (nmov, tot), k
    else:
        ai = 0
    base, fr, sl, du, sp = anims[min(ai, len(anims)-1)]
    a = load_animation(body, base)
    s = a['seqs'][0]
    nf = s['nframes']

    import re
    strs = sorted(set(m.group().decode() for m in re.finditer(rb'[\x20-\x7e]{4,}', body)))
    out = {"file": os.path.basename(path),
           "clips": sorted(set(x.split('/')[-1] for x in strs
                               if x.startswith('pack:/') and x.endswith('.clip'))),
           "animationNames": sorted(set(x.split('/')[-1] for x in strs
                                        if x.startswith('pack:/') and x.endswith('.anim'))),
           "animations": []}

    bones = []
    for bi, s2 in enumerate(s['animseq']):
        if bi >= len(a['boneids']):
            break
        bid, unk, trk = a['boneids'][bi]
        if trk != 1 or not s2.channels:
            continue
        # ★ 根骨(tag 0)的旋转是 **mover（实体朝向）**，不是骨骼姿态的一部分。
        #   硬套到骨架根骨上会让整个人左右/前后摇（实测 yaw 摆幅 163°、头部 Y 摆 0.29 m）；
        #   去掉后 yaw 0°、头部 Y 0.08 m、双脚前后 0.40 m 且横向 <0.06 m。
        if drop_root and bid == 0:
            continue
        if fix_ramp:
            nfix = repair_ramp_channels(s2)
            if nfix:
                print('   [ramp] bone %d 修掉 %d 条爬升通道' % (bid, nfix))
        try:
            qs = [eval_quat_fixed(s2, f) for f in range(nf)]
        except Exception:
            continue
        if fix_thigh and bid in THIGH_TAGS:
            D = THIGH_FRAME_FIX
            Di = qinv(D)
            qs = [qmul(qmul(Di, q), D) for q in qs]
        if fix_arm and bid in ARM_TAGS:
            D = THIGH_FRAME_FIX
            Di = qinv(D)
            qs = [qmul(qmul(Di, q), D) for q in qs]
        if bid in ALIGN:
            nm, Rloc, qlive = ALIGN[bid]
            q_ours = m2q_local(Rloc)
            D = qmul(qinv(q_ours), qlive)
            qs = [qmul(D, q) for q in qs]
        if debias and not (keep_arm_bias and bid in ARM_TAGS):
            C = qmean(qs)
            qs = [qmul(qinv(C), q) for q in qs]
        if knee_gain != 1.0 and bid in CALF_TAGS:
            qs = [scale_angle(q, knee_gain) for q in qs]
        if armclamp and bid in ARM_TAGS:
            qs = [clamp_deg(q, armclamp) for q in qs]
        mstep = 0.0
        for i in range(1, len(qs)):
            dd = min(1.0, abs(qdot(qs[i], qs[i-1])))
            mstep = max(mstep, math.degrees(2*math.acos(dd)))
        bones.append({"i": bi, "boneId": bid, "track": trk, "nch": len(s2.channels),
                      "maxstep": round(mstep, 1),
                      "quats": [[round(c, 5) for c in q] for q in qs]})
    # ★ 左腿整条轨（tag 65478）除 z 的爬升外还有一路跳变，右侧同名骨是干净的
    #   ⇒ 走路左右腿本就"同动作、差半周期"，直接用右腿轨道按半周期相位复制左腿。
    if '--mirror-left-leg' in sys.argv:
        by_tag = {b['boneId']: b for b in bones}
        R_ = by_tag.get(6884)
        L_ = by_tag.get(65478)
        if R_ and L_:
            qs_r = R_['quats']
            n = len(qs_r)
            # 用四元数相似度（不是单个分量）找周期：单分量在有噪声时会挑错 lag
            best = (1, -1.0)
            for lag in range(20, max(24, n//2)):
                sims = []
                for i in range(0, n - lag, max(1, (n-lag)//24)):
                    a = qs_r[i]; b2 = qs_r[i+lag]
                    sims.append(abs(sum(x*y for x, y in zip(a, b2))))
                if not sims:
                    continue
                c = sum(sims)/len(sims)
                if c > best[1]:
                    best = (lag, c)
            P = best[0] if best[1] > 0.8 else n // 2
            half = max(1, P//2)
            L_['quats'] = [list(qs_r[(f + half) % n]) for f in range(n)]
            L_['mirrored_from'] = {'tag': 6884, 'period': P, 'half': half, 'corr': round(best[1], 3)}
            print('   [mirror] 左大腿 ← 右大腿 相位 +%d 帧（周期 %d，相似度 %.3f）' % (half, P, best[1]))
    bones.sort(key=lambda b: -b['maxstep'])
    out['animations'].append({"base": hex(base), "frames": nf,
                              "duration": round(du, 3), "bones": bones})
    json.dump(out, open(out_json, 'w'), separators=(',', ':'))
    print('[walk_fix] anim%d frames=%d 旋转轨=%d debias=%s' % (ai, nf, len(bones), debias))
    print('           top: %s' % [(b['boneId'], b['maxstep']) for b in bones[:8]])
    print('           ->', out_json)


if __name__ == '__main__':
    main()
