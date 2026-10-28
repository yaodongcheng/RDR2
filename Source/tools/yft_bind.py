"""
RDR2 `.yft` / `.ydd` 骨架 **bind 全局矩阵** 提取器。
==============================================================================
破解记录（2026-10-15，本文件即结论）：

  * Skeleton 结构定位：扫尾部 `u16 1, u16 BonesCount, u16 <=N+64, u16 0, u32 0, u64 0`，
    再要求 `+0x28 / +0x30 / +0x38 / +0x40` 四个指针都落在 RAGE 段（0x5000_0000..）。
       +0x28 -> Bones 记录数组（真实基址 = 指针 + 0x40，步长 0x50；Tag(u16) @ +0x1a）
       +0x30 -> TransformationsInverted（真实基址 = 指针 + 0x50，步长 64B）
       +0x38 -> Transformations（局部；本工具不用）
       +0x40 -> ParentIndices

  * ★ 每个 64B 块是 **行向量仿射矩阵**，存的是 **bind 全局的逆**：
        rows[0..2] = (R 的 3 列 | 0)        # R 是 3x3 旋转
        rows[3]    = (tx, ty, tz | 0)
    其逆（= bind 全局，标准列向量约定）为：
        rot = R           （三个 3x3 元素原样使用，列向量约定）
        pos = -R @ t
    验证：`meta_base_player.yft` 755 骨与既有产物 `player_bind_pos.json` 最大误差 8e-6；
          `meta_base_abe.yft` 得 Z 跨度 1.953 m 的干净 A-pose 人形（头 0.649 / 脚 -0.963 / 臂 ±0.41）。

  * ⚠️ Tag 只能在同一物种内当作骨骼名 ID。跨物种会碰撞
    （鸟 `roseatespoonbill` 与人的重叠 tag 位置中位误差 0.49 m），
    所以 **只用人类 .yft**（abe / player / male 三者对同一 tag 完全一致）。

用途：给 `tools/export_gltf_source.py` 提供**权威 rest（bind）**，取代此前
"运行期 vec 方向 + 骑砍骨长 + idle 第 0 帧"的启发式拼装。
"""
import struct
import os
import json


def _in_rage(v):
    return 0x50000000 <= v < 0x50400000


def find_skeleton(d):
    """返回 (skeleton_struct_offset, bones_count)。"""
    n = len(d)
    for o in range(0, n - 18, 2):
        a, b, c, e = struct.unpack_from('<HHHH', d, o)
        if not (a == 1 and 40 <= b <= 2000 and c <= b + 64 and e == 0):
            continue
        if struct.unpack_from('<I', d, o + 8)[0] != 0:
            continue
        if struct.unpack_from('<Q', d, o + 12)[0] != 0:
            continue
        sk = o - 0x5C
        if sk < 0:
            continue
        try:
            p = [struct.unpack_from('<Q', d, sk + k)[0] for k in (0x28, 0x30, 0x38, 0x40)]
        except struct.error:
            continue
        if all(_in_rage(x) for x in p):
            return sk, b
    return None, None


def read_yft_skeleton(path):
    """读取 .yft/.ydd。返回 dict(bones=[{tag,parent}], bind={tag: (pos, rot3x3)}, n=)"""
    d = open(path, 'rb').read()
    if struct.unpack_from('<I', d, 0)[0] != 0x38435352:
        raise ValueError('not RSC8: %s' % path)
    sk, n = find_skeleton(d)
    if sk is None:
        raise ValueError('skeleton struct not found: %s' % path)

    bones_ptr = struct.unpack_from('<Q', d, sk + 0x28)[0] - 0x50000000
    par_ptr = struct.unpack_from('<Q', d, sk + 0x40)[0] - 0x50000000
    inv_ptr = struct.unpack_from('<Q', d, sk + 0x30)[0] - 0x50000000
    bones_off = bones_ptr + 0x40
    inv_off = inv_ptr + 0x50
    if bones_off + n * 0x50 > len(d) or inv_off + n * 64 > len(d):
        raise ValueError('array out of file: %s' % path)

    bones = []
    for i in range(n):
        o = bones_off + i * 0x50
        bones.append(dict(
            tag=struct.unpack_from('<H', d, o + 0x1a)[0],
            parent=struct.unpack_from('<H', d, o + 0x16)[0],
            q=struct.unpack_from('<4f', d, o + 0x20),
            t=struct.unpack_from('<3f', d, o + 0x30)))

    # 父索引数组（更权威）
    parents = None
    for cand in range(par_ptr, par_ptr + 0x200, 2):
        if cand + n * 2 > len(d):
            break
        v = [struct.unpack_from('<h', d, cand + i * 2)[0] for i in range(n)]
        if sum(1 for i, x in enumerate(v) if not (x == -1 or (0 <= x < i))) == 0:
            parents = v
            break
    if parents:
        for i, p in enumerate(parents):
            bones[i]['parent'] = p

    bind = {}
    for i in range(n):
        rows = [list(struct.unpack_from('<4f', d, inv_off + i * 64 + r * 16)) for r in range(4)]
        R = [[rows[r][c] for c in range(3)] for r in range(3)]
        t = [rows[3][c] for c in range(3)]
        pos = [-sum(R[r][k] * t[k] for k in range(3)) for r in range(3)]
        bind.setdefault(bones[i]['tag'], (pos, R))
    return dict(bones=bones, bind=bind, n=n, file=os.path.basename(path))


# --- 浮点舍入，避免 JSON 过大 ---
def _r(x):
    return round(x, 7)


def build_bind_table(paths):
    """把多个 .yft 的 bind 合并成 {tag: {pos, rot}}（先到先得）。"""
    table = {}
    stats = []
    for p in paths:
        try:
            S = read_yft_skeleton(p)
        except Exception as e:
            stats.append((os.path.basename(p), 0, str(e)))
            continue
        added = 0
        for tag, (pos, R) in S['bind'].items():
            if tag in table:
                continue
            table[tag] = dict(pos=[_r(x) for x in pos],
                              rot=[[_r(R[r][c]) for c in range(3)] for r in range(3)])
            added += 1
        stats.append((os.path.basename(p), added, 'n=%d' % S['n']))
    return table, stats


def read_yft_names(path):
    """★ 骨名池（2026-10-16 解出）：名字是**连续 NUL 分隔字符串表**，
    每根骨的 `NamePointer`(+0x00) 指向 **名字起点 − 0x10**（即落在上一个名字内部）。
    ⇒ `name = NUL_string(ptr − 0x50000000 + 0x10)`。

    验证（`meta_base_player.yft`）：对运行期已知的 34 根骨，31 根**逐字命中**；
    未命中 3 个 = 1 个纯大小写差异（池 `PH_Hat_loc` / 运行期 `PH_Hat_Loc`）
    + 2 个**tag 空间碰撞**（同 tag 在池里是 `SCALE_L_Forearm` / `SC_SatchelPosition`，
    运行期却是 `SKEL_L_Hand_01_02` / `SKEL_R_Pelt_D03`）—— 即 tag 并非全局唯一。
    返回与 read_yft_skeleton()['bones'] 同序的名字列表。"""
    d = open(path, 'rb').read()
    sk, n = find_skeleton(d)
    if sk is None:
        raise ValueError('skeleton struct not found: %s' % path)
    bp = struct.unpack_from('<Q', d, sk + 0x28)[0] - 0x50000000
    off = bp + 0x40
    out = []
    for i in range(n):
        ptr = struct.unpack_from('<Q', d, off + i * 0x50)[0]
        o = ptr - 0x50000000 + 0x10
        if not (0 <= o < len(d)):
            out.append('')
            continue
        seg = d[o:o + 96]
        z = seg.find(b'\x00')
        out.append(seg[:z].decode('latin1') if z >= 0 else '')
    return out


DEFAULT_HUMAN_YFT = [
    'export/models/fragments/meta_base_player.yft',
    'export/models/fragments/meta_base_abe.yft',
    'export/models/fragments/meta_base_male.yft',
]


if __name__ == '__main__':
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, 'export/skeleton_runtime/yft_bind.json')
    out_skel = os.path.join(root, 'export/skeleton_runtime/yft_skel.json')
    args = sys.argv[1:]
    only_skel = '--skel-only' in args
    fl = [a for a in args if not a.startswith('--')] or \
         [os.path.join(root, p) for p in DEFAULT_HUMAN_YFT]
    table, stats = build_bind_table(fl)
    for name, added, note in stats:
        print('  %-34s +%-4d %s' % (name, added, note))
    if not only_skel:
        json.dump(table, open(out, 'w'), separators=(',', ':'))
        print('wrote %s : %d 个 tag' % (out, len(table)))

    # ★ 骨架层级（用于"从 .yft 建源骨架"，覆盖度 25 → 65）：
    #   第一个文件作为骨表基底（默认 player.yft，756 骨），bind 用上面合并后的表
    S = read_yft_skeleton(fl[0])
    NM = read_yft_names(fl[0])          # ★ 骨名池（本轮解出）
    n_named = sum(1 for x in NM if x)
    seen = {}
    bones = []
    for i, b in enumerate(S['bones']):
        tag = b['tag']
        dup = tag in seen
        seen.setdefault(tag, i)
        bones.append(dict(i=i, tag=tag, parent=b['parent'], dup=dup,
                          name=(NM[i] if i < len(NM) else '')))
    json.dump(dict(file=os.path.basename(fl[0]), n=S['n'], bones=bones),
              open(out_skel, 'w'), separators=(',', ':'))
    n_dup = sum(1 for b in bones if b['dup'])
    print('wrote %s : %d 骨（root %d 个，重复 tag %d 个；★ 解出骨名 %d 个）' %
          (out_skel, len(bones), sum(1 for b in bones if b['parent'] < 0), n_dup, n_named))
