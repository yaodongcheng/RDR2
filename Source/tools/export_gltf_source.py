"""把 RDR2 运行期骨架（133 骨：名/层级/tag）+ **.yft 权威 bind** + 一条 .ycd 动画，导成 GLTF。

数据来源
  * 骨架拓扑/骨名/tag ： `export/skeleton_runtime/skel_full.tsv`（运行期只读取证）
  * ★ 权威 rest（bind）： `export/skeleton_runtime/yft_bind.json`（`tools/yft_bind.py` 从人类 .yft 抽）
        —— bind 全局 rot = 存储 3x3 原样，pos = -R·t（见 tools/yft_bind.py 文件头）
        —— 局部绑变换 = inv(G[运行期父]) @ G[自己]  ⇒ 骨长/朝向都是 RDR2 真值
  * 动画： `tools/export_anim_json.py` 导出的 .ycd JSON；boneId == 骨结构的 Tag
  * ★ 动画语义（2026-10-15 定案）：.ycd 的四元数是【相对 bind 的增量】，
    姿态 = `R_bind_local ⊗ q_anim`（判决实验见 RDR2_ycd动画解码.md §6.5）。
    ⚠️ 旧版把 q_anim 当绝对局部旋转 ⇒ 会把 bind 旋转整个抹掉 ⇒ 骨架坍缩。

坐标系
  源是 RDR2 **Z-up**（+Y 面 / +X 右）；glTF 是 Y-up。
  做法：**逐骨把局部旋转做 F·R·Fᵀ 共轭、局部平移做 F·t**（F = 绕 X −90°），
  这样 glTF 的 world = F·(RDR2 world)，Blender 导入时再补 +90° ⇒ Blender 里就是 RDR2 原始 Z-up。
  ⚠️ 平移与旋转必须**同时**变换，只共轭旋转会让局部位移落在错误坐标系（旧版这里漏了平移）。

用法：
  python tools/export_gltf_source.py <anim.json> <out.gltf> [--name clip] [--anim N]
"""
import json, sys, os, struct, base64, math
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKEL = os.path.join(ROOT, 'export/skeleton_runtime/skel_full.tsv')
BINDF = os.path.join(ROOT, 'export/skeleton_runtime/yft_bind.json')
YFTSKEL = os.path.join(ROOT, 'export/skeleton_runtime/yft_skel.json')


def qmul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return (aw*bx+ax*bw+ay*bz-az*by, aw*by-ax*bz+ay*bw+az*bx,
            aw*bz+ax*by-ay*bx+az*bw, aw*bw-ax*bx-ay*by-az*bz)


def qnorm(q):
    n = math.sqrt(sum(c*c for c in q)) or 1.0
    return tuple(c/n for c in q)


# RDR2(Z-up) -> GLTF(Y-up)：绕 X 轴 -90°；位置按 (x, z, -y) 变换
Q_FIX = (math.sin(math.radians(-45)), 0.0, 0.0, math.cos(math.radians(-45)))   # (x,y,z,w)
Q_FIX_INV = (-Q_FIX[0], -Q_FIX[1], -Q_FIX[2], Q_FIX[3])


def qinv(q):
    x, y, z, w = q
    n = x*x + y*y + z*z + w*w
    if n == 0:
        return (0.0, 0.0, 0.0, 1.0)
    return (-x/n, -y/n, -z/n, w/n)


def conv_q(q):
    """RDR2 空间四元数 -> GLTF 空间（q' = F · q · F⁻¹）"""
    return qnorm(qmul(qmul(Q_FIX, qnorm(q)), Q_FIX_INV))


def conv_t(t):
    """RDR2 空间平移 -> GLTF 空间（绕 X −90°）"""
    return (t[0], t[2], -t[1])


def mat_to_quat(R):
    """3x3 旋转矩阵(标准列向量约定) -> (x,y,z,w)"""
    m = R
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        w = 0.25 * s
        x = (m[2][1] - m[1][2]) / s
        y = (m[0][2] - m[2][0]) / s
        z = (m[1][0] - m[0][1]) / s
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2
        w = (m[2][1] - m[1][2]) / s
        x = 0.25 * s
        y = (m[0][1] + m[1][0]) / s
        z = (m[0][2] + m[2][0]) / s
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2
        w = (m[0][2] - m[2][0]) / s
        x = (m[0][1] + m[1][0]) / s
        y = 0.25 * s
        z = (m[1][2] + m[2][1]) / s
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2
        w = (m[1][0] - m[0][1]) / s
        x = (m[0][2] + m[2][0]) / s
        y = (m[1][2] + m[2][1]) / s
        z = 0.25 * s
    return qnorm((x, y, z, w))


def _aff(R, t):
    return [[R[r][c] for c in range(3)] + [t[r]] for r in range(3)] + [[0.0, 0.0, 0.0, 1.0]]


def _inv_aff(M):
    R = [[M[r][c] for c in range(3)] for r in range(3)]
    t = [M[r][3] for r in range(3)]
    Rt = [[R[c][r] for c in range(3)] for r in range(3)]
    tt = [-sum(Rt[r][k]*t[k] for k in range(3)) for r in range(3)]
    return _aff(Rt, tt)


def load_skeleton():
    """运行期 dump 的骨架（133 骨；f1a 即 tag）"""
    bones = {}
    for line in open(SKEL, encoding='utf-8').read().splitlines()[1:]:
        r = line.split('\t')
        if len(r) < 14:
            continue
        idx = int(r[0])
        par = int(r[2])
        bones[idx] = dict(idx=idx, name=r[1], parent=(-1 if par == 65535 else par),
                          tag=int(r[5]), quat=tuple(float(x) for x in r[7:11]),
                          vec=tuple(float(x) for x in r[11:14]))
    return bones


def load_yft_skel(name_by_tag):
    """从 .yft 建骨架（player.yft 756 骨）。
    ★ 为什么：动画的骨 ID 空间只 25/114 落在运行期 133 骨里，但 65/114 落在 player.yft 里
      ⇒ 用 .yft 当源骨架能把动画覆盖率从 25 提到 65（见 RDR2_ycd动画解码.md §6.6）。
    节点名优先级：
      ① 运行期骨名（tag 能在运行期骨架里查到）—— 保证与 map.json 一致（那 34 根 = 要重定向的）
      ② ★ .yft 骨名池解出的真名（tools/yft_bind.py §read_yft_names，756/756 全解出）
      ③ 兜底 `T<tag>`
    """
    skel = json.load(open(YFTSKEL, encoding='utf-8'))
    out = {}
    for b in skel['bones']:
        i = b['i']
        nm = name_by_tag.get(b['tag']) or b.get('name') or ('T%d' % b['tag'])
        out[i] = dict(idx=i, name=nm, parent=b['parent'], tag=b['tag'], dup=bool(b.get('dup')))
    return out


def reparent_known(bones, rt):
    """★ 把"有运行期骨名"的节点重挂到它的【运行期父】下。
    为什么：`.yft` 的拓扑与运行期/骑砍不同（例：.yft 里 `SKEL_L_Hand_01_02` 直挂
    `SKEL_L_Forearm`，而运行期是 `Forearm → Hand_01_01 → Hand_01_02`，骑砍是
    `foretwist → foretwist1 → hand`）。重定向的 align 靠"源链 ↔ 目标链"一一配对，
    拓扑不一致会让 align 配不上（实测 `l_hand` 的肢段方向差 101.8°）。
    只动有名字的 34 根，其余 700 多根 .yft 骨保持 .yft 父链。
    注意：LOC 是 `inv(Gx[父]) @ G[自己]`算的 ⇒ 重挂父**不改变任何骨的 bind 世界位置**。"""
    name2i = {}
    for i, b in bones.items():
        name2i.setdefault(b['name'], i)
    r_by_name = {}
    for b in rt.values():
        r_by_name.setdefault(b['name'], b)
    changed = []
    for i in sorted(bones):
        b = bones[i]
        if b['name'].startswith('T'):
            continue
        r = r_by_name.get(b['name'])
        if not r or r['parent'] < 0:
            continue
        pname = rt[r['parent']]['name']
        pi = name2i.get(pname)
        if pi is None or pi == b['parent'] or pi == i:
            continue
        # 防环：沿新父往上，不能回到 i
        j, guard = pi, 0
        while j is not None and guard < 4096:
            guard += 1
            if j == i:
                j = None
                break
            j = bones[j]['parent'] if j in bones else None
        if j is not None:
            continue
        b['parent'] = pi
        changed.append(b['name'])
    return changed


def opsx_fix_arm_chain():
    """★ 把 RDR2 的臂链"串成线"，对齐骑砍的链序。
    骑砍（目标）：clavicle → upperarm_twist → upperarm_twist1 → foretwist → foretwist1 → hand
    RDR2（源）  ：Clavicle → UpperArm → {UpperArm_02_01, Forearm}         ← roll 骨是【兄弟】
                                     Forearm → {Forearm_01_01, Hand_01_01} ← 同上
    align 靠 `mapped_kids` 找"最近的映射子骨"配对，兄弟结构会让配对落空
    （实测 `l_foretwist` / `l_hand` 的肢段方向差 ~100°，因为它们量的是不同的父骨出向）。
    这里显式把源链改成线链；LOC 是 `inv(Gx[父]) @ G[自己]` 算的 ⇒ 有 bind 的骨
    世界位置**不变**（已逐骨验证 err ≤ 2e-6），只有无 bind 的 graft 骨走几何回退。"""
    return [('SKEL_L_Forearm', 'SKEL_L_UpperArm_02_01'),
            ('SKEL_R_Forearm', 'SKEL_R_UpperArm_02_01'),
            ('SKEL_L_Hand_01_01', 'SKEL_L_Forearm_01_01'),
            ('SKEL_R_Hand_01_01', 'SKEL_R_Forearm_01_01')]


def apply_chain_fix(bones):
    name2i = {}
    for i, b in bones.items():
        name2i.setdefault(b['name'], i)
    done = []
    for child, par in opsx_fix_arm_chain():
        ci, pi = name2i.get(child), name2i.get(par)
        if ci is None or pi is None or ci == pi:
            continue
        # 防环
        j, guard = pi, 0
        ok = True
        while j is not None and guard < 4096:
            guard += 1
            if j == ci:
                ok = False
                break
            j = bones[j]['parent'] if j in bones else None
        if ok:
            bones[ci]['parent'] = pi
            done.append('%s→%s' % (child, par))
    return done


def augment_with_runtime(bones, rt, wanted):
    """★ 混合骨架：.yft 基底 + 接回"map.json 需要但 .yft 缺"的骨。
    典型就是手臂 roll 链 `SKEL_L/R_UpperArm_02_01` / `Forearm_01_01` / `Hand_01_01`
    （player.yft 里没有），它们在运行期骨架里有、父骨在 .yft 里也有。
    接法：挂到"运行期父链里最近的、.yft 中存在的祖先"下，局部变换走几何回退
    （这些 tag 在任何 .yft 里都没有 bind，运行期路径下本来也是几何回退）。"""
    have = set(b['name'] for b in bones.values())
    by_name = {}
    for b in rt.values():
        by_name.setdefault(b['name'], b)
    nxt = max(bones) + 1
    added = []
    for nm in wanted:
        if nm in have or nm not in by_name:
            continue
        r = by_name[nm]
        # 沿运行期父链找第一个在 .yft 里存在的祖先
        p = r['parent']
        anchor = None
        while p >= 0:
            pn = rt[p]['name']
            hit = next((i for i, b in bones.items() if b['name'] == pn), None)
            if hit is not None:
                anchor = hit
                break
            p = rt[p]['parent']
        if anchor is None:
            continue
        bones[nxt] = dict(idx=nxt, name=nm, parent=anchor, tag=r['tag'], dup=False)
        have.add(nm)
        added.append(nm)
        nxt += 1
    return added


def load_bind():
    if not os.path.exists(BINDF):
        return {}
    out = {}
    for k, v in json.load(open(BINDF, encoding='utf-8')).items():
        out[int(k)] = _aff(v['rot'], v['pos'])
    return out


def topo_order(bones):
    """父在子之前的顺序。★ 必需：重挂父之后"父索引 < 子索引"不再成立，
    按 `sorted(bones)` 遍历会拿到还没算的父（曾导致 KeyError / 拿 identity 当父矩阵）。"""
    seen = set()
    out = []
    for start in sorted(bones):
        if start in seen:
            continue
        stack = [start]
        while stack:
            i = stack[-1]
            if i in seen:
                stack.pop()
                continue
            p = bones[i]['parent']
            if p in bones and p not in seen:
                stack.append(p)
                continue
            seen.add(i)
            stack.pop()
            out.append(i)
    return out


def build_rest(bones, BIND):
    """按【运行期父链】把 bind 全局转成局部绑变换；缺 bind 的骨用几何回退。
    返回 (local_mats, globals, stats)"""
    ident = _aff([[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0, 0, 0])
    Gx, LOC = {}, {}
    n_bind = n_fb = n_break = 0
    for i in topo_order(bones):
        b = bones[i]
        p = b['parent']
        Gp = Gx.get(p, ident)
        par_local = LOC.get(p)
        if b['tag'] in BIND and not b.get('dup'):
            Gi = BIND[b['tag']]
            LOC[i] = _mm(_inv_aff(Gp), Gi)
            Gx[i] = Gi
            n_bind += 1
        else:
            # 缺 bind：沿父骨轴中点摆放、姿态与父一致（twist/roll 骨就该这样）
            plen = 0.0
            if par_local is not None:
                plen = math.sqrt(sum(par_local[r][3]**2 for r in range(3)))
            t = (0.5 * plen, 0.0, 0.0)
            L = _aff([[1, 0, 0], [0, 1, 0], [0, 0, 1]], t)
            LOC[i] = L
            Gx[i] = _mm(Gp, L)
            n_fb += 1
            if plen == 0.0:
                n_break += 1
    return LOC, Gx, dict(bind=n_bind, fallback=n_fb, degenerate=n_break)


def _mm(A, B):
    return [[sum(A[r][k]*B[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def main():
    anim_json, out_path = sys.argv[1], sys.argv[2]
    name = 'clip'
    if '--name' in sys.argv:
        name = sys.argv[sys.argv.index('--name') + 1]

    skel_kind = 'runtime'
    if '--skel' in sys.argv:
        skel_kind = sys.argv[sys.argv.index('--skel') + 1]
    if skel_kind == 'yft':
        rt = load_skeleton()
        n2t = {}
        for b in rt.values():
            n2t.setdefault(b['tag'], b['name'])
        bones = load_yft_skel(n2t)
        named = sum(1 for b in bones.values() if b['tag'] in n2t)
        # map.json 需要的源骨名 → 把 .yft 里缺的补回来
        wanted = []
        p_map = r'D:/BrainMaker/骑砍2动画重定向/pipeline/rigs/rdr2/map.json'
        if os.path.exists(p_map):
            wanted = list(json.load(open(p_map, encoding='utf-8'))['bone_map'].keys())
        added = augment_with_runtime(bones, rt, wanted)
        chg = reparent_known(bones, rt)
        chain = apply_chain_fix(bones)
        print('[skel] 源骨架 = .yft（%s，%d 骨；%d 骨有运行期骨名，其余全部用 .yft 骨名池真名）'
              % (os.path.basename(YFTSKEL), len(bones), named))
        if added:
            print('[skel] 从运行期骨架接回 %d 根 map.json 需要的骨: %s'
                  % (len(added), ', '.join(added)))
        if chg:
            print('[skel] 有名骨重挂到运行期父（对齐骑砍链拓扑）%d 根: %s'
                  % (len(chg), ', '.join(chg)))
        for _nm in (('SKEL_Pelvis', 'SKEL_L_Clavicle', 'SKEL_L_Hand_01_02', 'SKEL_L_Forearm')
                    if '-v' in sys.argv else ()):
            _i = next((k for k, b in bones.items() if b['name'] == _nm), None)
            if _i is not None:
                _p = bones[_i]['parent']
                print('[dbg] %-22s idx=%-4d parent=%-4d(%s)' %
                      (_nm, _i, _p, bones[_p]['name'] if _p in bones else '-'))
        if chain:
            print('[skel] 臂链串成线链（对齐骑砍链序）: %s' % ', '.join(chain))
    else:
        bones = load_skeleton()
        print('[skel] 源骨架 = 运行期 dump（%d 骨）' % len(bones))
    BIND = load_bind()
    tag2idx = {}
    for i, b in bones.items():
        tag2idx.setdefault(b['tag'], i)

    LOC, Gx, st = build_rest(bones, BIND)
    print('[rest] .yft 权威 bind 覆盖 %d 骨；几何回退 %d 骨（其中退化 %d）'
          % (st['bind'], st['fallback'], st['degenerate']))

    A = json.load(open(anim_json, encoding='utf-8'))
    ranked = sorted(A['animations'], key=lambda a: -sum(b['maxstep'] for b in a['bones']))
    ai = 0
    if '--anim' in sys.argv:
        ai = int(sys.argv[sys.argv.index('--anim') + 1])
    anim = ranked[min(ai, len(ranked) - 1)]
    nframes = anim['frames']
    print(f'[选段] 共 {len(ranked)} 段，取第 {ai} 段 (base={anim["base"]} '
          f'运动量={round(sum(b["maxstep"] for b in anim["bones"]),1)} 骨数={len(anim["bones"])})')
    for k, a2 in enumerate(ranked[:4]):
        print(f'   候选[{k}] base={a2["base"]} 骨数={len(a2["bones"])} '
              f'运动量={round(sum(b["maxstep"] for b in a2["bones"]),1)}')

    tracks = {}
    dropped = {}
    for t in anim['bones']:
        i = tag2idx.get(t['boneId'])
        if i is None:
            dropped.setdefault(t['boneId'], []).append(round(t['maxstep'], 1))
            continue
        tracks.setdefault(i, t)
    if dropped:
        # ⚠️ 动画的骨 ID 空间 ≠ 运行期 dump 的 f1a 空间：
        #    walk_slow 的 114 个 id 里只有 25 个落在运行期骨架、65 个落在 player.yft。
        #    这里把丢掉的轨道显式列出来（含运动量），不要静默吞掉。
        tot = sum(max(v) for v in dropped.values())
        kept = sum(t['maxstep'] for t in tracks.values())
        print(f'[覆盖] 映射成功 {len(tracks)} 条 / 丢弃 {len(dropped)} 条（丢弃的运动量合计 {tot:.1f}°，'
              f'保留 {kept:.1f}°）')
        for b in sorted(dropped, key=lambda k: -max(dropped[k])):
            print(f'   丢弃 boneId={b:<8d} maxstep={max(dropped[b]):.1f}°  '
                  f'（该 id 不在运行期 133 骨 tag 内）')
    else:
        print(f'[覆盖] 映射成功 {len(tracks)} 条，无丢弃')

    idxs = sorted(bones)
    pos_of = {i: k for k, i in enumerate(idxs)}

    # ★ 2026-10-17：关节必须放在**骨头的 head**，不是 bind 里记的 tail。
    #   `.yft` 的 bind pos 是「骨末端」，直接当节点位置 ⇒ "大腿关节"落在膝盖、
    #   "小腿关节"落在脚踝，旋转轴心整体下一段：走路/弯腿时整条腿在错误的高度折
    #   （实测 Blender 里 SKEL_L_Thigh head z=-0.481、SKEL_L_Calf head z=-0.902）。
    #   head(i) = tail(parent(i)) = Gx[parent] 的平移。
    def _wpos(M):
        return [M[r][3] for r in range(3)]

    def _wrot(M):
        return [[M[r][c] for c in range(3)] for r in range(3)]

    HEADW = {}
    for i in idxs:
        p = bones[i]['parent']
        if p in Gx:
            HEADW[i] = _wpos(Gx[p])
        elif i in Gx:
            HEADW[i] = _wpos(Gx[i])
        else:
            HEADW[i] = [0.0, 0.0, 0.0]

    nodes = []
    for i in idxs:
        b = bones[i]
        L = LOC[i]
        R = [[L[r][c] for c in range(3)] for r in range(3)]
        p = b['parent']
        if p in HEADW:
            Rp = _wrot(Gx[p])
            d = [HEADW[i][k] - HEADW[p][k] for k in range(3)]
            t = [sum(Rp[k][c]*d[k] for k in range(3)) for c in range(3)]   # Rᵀ·d
        else:
            t = HEADW[i]
        nodes.append(dict(name=b['name'],
                          translation=[round(x, 6) for x in conv_t(t)],
                          rotation=[round(x, 8) for x in conv_q(mat_to_quat(R))],
                          children=[]))
    for i in idxs:
        p = bones[i]['parent']
        if p in pos_of:
            nodes[pos_of[p]]['children'].append(pos_of[i])
    for nd in nodes:
        if not nd['children']:
            del nd['children']
    roots = [pos_of[i] for i in idxs if bones[i]['parent'] not in pos_of]
    if '-v' in sys.argv:
        _par = {}
        for _i2, _n in enumerate(nodes):
            for _c in _n.get('children', []):
                _par[_c] = _i2
        for _nm in ('SKEL_Pelvis', 'SKEL_L_Clavicle', 'SKEL_L_Hand_01_02'):
            _k = next((k for k, n in enumerate(nodes) if n.get('name') == _nm), None)
            if _k is None:
                continue
            print('[dbg2] %-22s node=%-4d parentNode=%-4s (%s)' %
                  (_nm, _k, _par.get(_k, '-'),
                   nodes[_par[_k]].get('name') if _k in _par else '-'))

    # ---- rest 世界旋转（给 --arms-down 这类"世界空间附加旋转"用）
    #   ⚠️ 必须按**拓扑序**累积：重挂父之后"父索引 < 子索引"不再成立，
    #   按索引遍历会拿到未初始化的父（表现为世界旋转全错）。
    RESTW = {}
    _W = {}
    _order, _seen = [], set()

    def _topo(i):
        if i in _seen or i not in bones:
            return
        _p = bones[i]['parent']
        if _p in bones:
            _topo(_p)
        _seen.add(i)
        _order.append(i)
    for _i in bones:
        _topo(_i)
    for _i in _order:
        _Rl = [[LOC[_i][r][c] for c in range(3)] for r in range(3)]
        _p = bones[_i]['parent']
        _Rp = _W.get(_p, [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]])
        _W[_i] = [[sum(_Rp[r][k]*_Rl[k][c] for k in range(3)) for c in range(3)] for r in range(3)]
        RESTW[_i] = _W[_i]

    ARM_UP = {'SKEL_L_UpperArm': +1, 'SKEL_R_UpperArm': -1}
    _arms_deg = 0.0
    if '--arms-down' in sys.argv:
        _arms_deg = float(sys.argv[sys.argv.index('--arms-down') + 1])

    def _arms_extra(world_deg, side):
        """世界空间绕 Y（前后轴）把大臂压下来的局部增量四元数"""
        half = math.radians(world_deg * side) / 2.0
        qw = (0.0, math.sin(half), 0.0, math.cos(half))
        return qw

    sampler_data = {}
    for i, t in tracks.items():
        qs = t['quats']
        # ★ 关键：.ycd 的四元数是【相对 bind 的增量】，不是绝对局部旋转。
        #   实测三种语义（walk_slow 404 帧，RDR2 原始空间 FK）：
        #     abs   (R = q)                → 骨架坍缩（head.z 0.65→0.15）
        #     Xbind (R = q ⊗ R_bind)       → 整体倒立（head.z −0.50）
        #     bindX (R = R_bind ⊗ q) ✅    → 站立人形（head.z 0.58 / 脚 z −0.95 / 双脚前后行程 0.11 m）
        #   佐证：多个骨的 q≈单位阵而 bind 旋转是 ~180°（如 SKEL_ROOT q=(1,0,0,0)、
        #   SKEL_L_Clavicle q=单位阵）—— 若按 abs 会把 bind 旋转整个抹掉。
        Rb = LOC[i]
        rbq = mat_to_quat([[Rb[r][c] for c in range(3)] for r in range(3)])
        _rv = 0
        if '--rotvar' in sys.argv:
            _rv = int(sys.argv[sys.argv.index('--rotvar') + 1])
        _rbi = qinv(rbq)
        arr = []
        for f in range(nframes):
            q = qnorm(tuple(qs[min(f, len(qs) - 1)]))
            if _rv == 0:
                # ★ 根骨（无父）例外：它的 q 是**世界空间**的姿态（mover 朝向）。
                #   bind 的根旋转是个 180° 翻转（绕 (1,0,−1)/√2），按 bindX 左乘会把
                #   "偏航"变成"前后俯仰" ⇒ 上身前后晃（实测头部 Y 摆幅 0.29 m → 0.09 m）。
                if bones[i]['parent'] not in bones and '--no-rootworld' not in sys.argv:
                    r = qmul(q, rbq)      # 根骨：q ⊗ R_bind（世界左乘）
                else:
                    r = qmul(rbq, q)      # 其余：R_bind ⊗ q
            elif _rv == 1:
                r = qmul(q, rbq)          # q ⊗ R_bind
            elif _rv == 2:
                r = qmul(_rbi, q)         # inv(R_bind) ⊗ q
            elif _rv == 3:
                r = qmul(q, _rbi)         # q ⊗ inv(R_bind)
            elif _rv == 4:
                r = q                    # 绝对
            else:
                r = qmul(rbq, q)
            if _arms_deg and i in tracks and bones[i]['name'] in ARM_UP:
                # 世界空间绕 Y（前后轴）把大臂压下来：q_local = (Rw⁻¹ q_world Rw) ⊗ r
                Rw = RESTW[i]
                Rq = mat_to_quat(Rw)
                qw = _arms_extra(_arms_deg, ARM_UP[bones[i]['name']])
                r = qmul(qmul(qinv(Rq), qw), qmul(Rq, r))

            arr.extend(conv_q(r))
        sampler_data[i] = arr

    buf = bytearray()
    views = []
    accessors = []

    def add_f32(vals):
        off = len(buf)
        buf.extend(struct.pack('<%df' % len(vals), *vals))
        while len(buf) % 4:
            buf.append(0)
        views.append(dict(buffer=0, byteOffset=off, byteLength=len(vals)*4))
        n = len(vals) // 4
        accessors.append(dict(bufferView=len(views)-1, componentType=5126, count=n, type='VEC4'))
        return len(accessors) - 1

    times = [f / 30.0 for f in range(nframes)]
    toff = len(buf); buf.extend(struct.pack('<%df' % len(times), *times))
    views.append(dict(buffer=0, byteOffset=toff, byteLength=len(times)*4))
    accessors.append(dict(bufferView=len(views)-1, componentType=5126, count=len(times),
                          type='SCALAR', min=[times[0]], max=[times[-1]]))
    tacc = len(accessors) - 1

    samplers, channels = [], []
    for i, arr in sampler_data.items():
        vacc = add_f32(arr)
        samplers.append(dict(input=tacc, output=vacc, interpolation='LINEAR'))
        channels.append(dict(sampler=len(samplers)-1,
                             target=dict(node=pos_of[i], path='rotation')))

    NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}

    def add_raw(vals, fmt, ctype, typ, extra=None):
        off = len(buf)
        buf.extend(struct.pack('<' + fmt * len(vals), *vals))
        while len(buf) % 4:
            buf.append(0)
        views.append(dict(buffer=0, byteOffset=off, byteLength=len(buf) - off))
        a = dict(bufferView=len(views) - 1, componentType=ctype,
                 count=len(vals) // NCOMP[typ], type=typ)
        if extra:
            a.update(extra)
        accessors.append(a)
        return len(accessors) - 1

    P = [[0.0, 0.0, 0.0], [0.02, 0.0, 0.0], [0.0, 0.02, 0.0]]
    pacc = add_raw([c for v in P for c in v], 'f', 5126, 'VEC3', {'min': [0, 0, 0], 'max': [0.02, 0.02, 0.0]})
    jacc = add_raw([0, 0, 0, 0] * 3, 'H', 5123, 'VEC4')
    wacc = add_raw([1.0, 0.0, 0.0, 0.0] * 3, 'f', 5126, 'VEC4')
    iacc = add_raw([0, 1, 2], 'H', 5123, 'SCALAR')

    def _m4(t):
        return np.array([[1, 0, 0, t[0]], [0, 1, 0, t[1]], [0, 0, 1, t[2]], [0, 0, 0, 1]], float)

    def _mq(q):
        x, y, z, w = q
        return np.array([
            [1-2*(y*y+z*z), 2*(x*y-z*w),   2*(x*z+y*w),   0],
            [2*(x*y+z*w),   1-2*(x*x+z*z), 2*(y*z-x*w),   0],
            [2*(x*z-y*w),   2*(y*z+x*w),   1-2*(x*x+y*y), 0],
            [0, 0, 0, 1]], float)

    W4 = {}
    for i in topo_order(bones):
        local = _m4(nodes[pos_of[i]]['translation']) @ _mq(nodes[pos_of[i]]['rotation'])
        p = bones[i]['parent']
        W4[i] = local if p not in pos_of else W4[p] @ local
    ibm = []
    for i in idxs:
        inv = np.linalg.inv(W4[i])
        ibm.extend(inv.T.reshape(-1).tolist())
    bacc = add_raw(ibm, 'f', 5126, 'MAT4')
    meshes = [dict(primitives=[dict(attributes=dict(POSITION=pacc, JOINTS_0=jacc, WEIGHTS_0=wacc),
                                    indices=iacc, mode=4)])]
    skins = [dict(joints=[pos_of[i] for i in idxs], inverseBindMatrices=bacc, skeleton=roots[0])]
    meshnode = len(nodes)
    nodes.append(dict(name='rdr2_bind_stub', mesh=0, skin=0))
    scenes_nodes = roots + [meshnode]

    b64 = base64.b64encode(bytes(buf)).decode()
    gltf = dict(asset=dict(version='2.0', generator='rdr2-export-source/yftbind'),
                scene=0, scenes=[dict(nodes=scenes_nodes)], nodes=nodes,
                meshes=meshes, skins=skins,
                animations=[dict(name=name, samplers=samplers, channels=channels)],
                buffers=[dict(byteLength=len(buf), uri='data:application/octet-stream;base64,' + b64)],
                bufferViews=views, accessors=accessors)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    json.dump(gltf, open(out_path, 'w'), separators=(',', ':'))
    print(f'wrote {out_path}')
    print(f'  bones={len(nodes)} animated={len(tracks)} frames={nframes} roots={len(roots)} '
          f'size={os.path.getsize(out_path)/1e6:.2f}MB')
    print(f'  根部骨: {[nodes[r]["name"] for r in roots][:6]}')
    print(f'  已映射动画的骨(前12): {[bones[i]["name"] for i in list(tracks)[:12]]}')


if __name__ == '__main__':
    main()
