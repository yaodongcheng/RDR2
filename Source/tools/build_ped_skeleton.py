"""从运行期 dump 导出 **ped 骨架定义** + **tag→ped 骨名映射表**。

产物（都在 export/skeleton_runtime/ 下）：
  ped_skeleton.json   {bones:[{name, parent, rest_quat, source}]}   ← 124 骨，rest 来自游戏内存
  ped_bone_map.json   {"<tag>": "<ped 骨名>"}                        ← .ycd 轨道 → ped 骨

用法: python tools/build_ped_skeleton.py
"""
import glob
import json
import os
import re
import struct
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(PROJ, 'export/skeleton_runtime')


SCALE = 5.65    # 内存里的 pos 是归一化单位；×5.65 后全高 ≈1.56 m，与模型一致


def load_live():
    p = sorted(glob.glob(os.path.join(PROJ, 'work/npc/live/idle_*.tsv')))[-1]
    out = []
    for l in open(p, encoding='utf-8').read().splitlines()[1:]:
        c = l.split('\t')
        off = tuple(float(x) * SCALE for x in c[6:9]) if len(c) >= 9 else (0.0, 0.0, 0.0)
        out.append((c[1], tuple(float(x) for x in c[2:6]), off))
    return out, os.path.basename(p)


def main():
    live, src = load_live()
    names = [n for n, _, _ in live]
    quat = {n: q for n, q, _ in live}
    offs = {n: o for n, _, o in live}

    # 运行期骨架的父子表（133 骨，名字能对上的直接用）
    par = {}
    for l in open(os.path.join(PROJ, 'export/skeleton_runtime/skel_full.tsv'),
                  encoding='utf-8').read().splitlines()[1:]:
        c = l.strip('\r').split('\t')
        if len(c) >= 4:
            par[c[1]] = c[3]

    def infer_parent(n):
        if n in par and par[n] in names and par[n] != n:
            return par[n]
        # 1) 数字后缀：X00/X01… 挂到前一号
        m = re.match(r'^(.*?)(\d{2})$', n)
        if m:
            base, num = m.group(1), int(m.group(2))
            if num > 0:
                prev = '%s%02d' % (base, num - 1)
                if prev in names:
                    return prev
        # 2) 按前缀挂到最近的"主骨"
        for cand in ('SKEL_L_Clavicle', 'SKEL_R_Clavicle', 'SKEL_Neck0', 'SKEL_Spine1',
                     'SKEL_Pelvis', 'SKEL_ROOT'):
            if cand in names and cand != n:
                if n.startswith('SKEL_L_') and cand == 'SKEL_L_Clavicle' and 'Pelt' in n:
                    return cand
                if n.startswith('SKEL_R_') and cand == 'SKEL_R_Clavicle' and 'Pelt' in n:
                    return cand
        if n.startswith('PH_') or n.startswith('SKEL_Comb') or n.startswith('SKEL_Wattle'):
            return 'SKEL_Head' if n in ('SKEL_Comb', 'SKEL_Wattle', 'PH_Hat_Loc') else (
                'SKEL_L_Foot' if '_L_' in n else ('SKEL_R_Foot' if '_R_' in n else 'SKEL_Pelvis'))
        if n.startswith('SKEL_Tail') or n.startswith('SKEL_Top_Tail') or n.startswith('SKEL_Bot_Tail'):
            return 'SKEL_Pelvis'
        if n.startswith('SKEL_Neck'):
            return par.get(n) if par.get(n) in names else 'SKEL_Spine1'
        return 'SKEL_ROOT'

    bones = []
    n_inferred = 0
    for n in names:
        p = par.get(n) if par.get(n) in names else None
        src_flag = 'runtime_tsv'
        if p is None:
            p = infer_parent(n)
            src_flag = 'inferred'
            n_inferred += 1
        if n == 'SKEL_ROOT':
            p = None
        bones.append(dict(name=n, parent=p, rest_quat=[round(x, 6) for x in quat[n]],
                          offset=[round(x, 6) for x in offs[n]], source=src_flag))

    sk = dict(meta=dict(bone_count=len(bones), rest_from=src,
                        note='rest = 游戏内存里的局部四元数；父级优先取运行期 tsv，缺失的按命名规则推断'),
              bones=bones)
    out1 = os.path.join(OUT_DIR, 'ped_skeleton.json')
    json.dump(sk, open(out1, 'w'), ensure_ascii=False, indent=1)
    print('[1] %s（%d 骨，其中推断父级 %d 根）' % (out1, len(bones), n_inferred))

    # ---- tag → ped 骨名
    Y = json.load(open(os.path.join(OUT_DIR, 'yft_skel.json'), encoding='utf-8'))
    tag2name = {}
    for b in Y['bones']:
        tag2name.setdefault(b['tag'], b['name'])

    def norm(n):
        n = re.sub(r'_(0\d)_(0\d)$', '', n)
        n = re.sub(r'_Finger\d+.*$', '_Hand', n)
        n = re.sub(r'_Toe_?[TIMP]\d*$', '_Toe0', n)
        return n

    pedset = set(names)
    by_norm = {}
    for n in names:
        by_norm.setdefault(norm(n), n)

    mp = {}
    exact = fuzzy = 0
    for tag, yname in tag2name.items():
        if yname in pedset:
            mp[str(tag)] = yname
            exact += 1
        else:
            t = norm(yname)
            if t in pedset:
                mp[str(tag)] = t
                fuzzy += 1
            elif t in by_norm:
                mp[str(tag)] = by_norm[t]
                fuzzy += 1
    out2 = os.path.join(OUT_DIR, 'ped_bone_map.json')
    json.dump(mp, open(out2, 'w'), ensure_ascii=False, indent=0)
    print('[2] %s（%d 条：精确 %d / 归一化 %d）' % (out2, len(mp), exact, fuzzy))


if __name__ == '__main__':
    main()
