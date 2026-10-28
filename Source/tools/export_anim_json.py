import struct, sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ycd_decode import load, find_animations, load_animation


def _qdot(a, b):
    return abs(sum(x*y for x, y in zip(a, b)))


def _slerp(a, b, t=0.5):
    d = sum(x*y for x, y in zip(a, b))
    if d < 0:
        b = tuple(-x for x in b); d = -d
    if d > 0.9995:
        r = tuple(a[i] + t*(b[i]-a[i]) for i in range(4))
    else:
        th = math.acos(max(-1.0, min(1.0, d)))
        s = math.sin(th)
        r = tuple((math.sin((1-t)*th)*a[i] + math.sin(t*th)*b[i])/s for i in range(4))
    n = math.sqrt(sum(c*c for c in r)) or 1.0
    return tuple(c/n for c in r)


def repair_isolated_jumps(quats, deg=20.0):
    """★ 修"孤立单帧跳变"：`frame_offset + frame_length*f` 的逐帧定长布局**并非对所有帧成立**
    （RAGE 帧区分块），实测会出现单帧的 bit 解码错，表现为前后都平滑、只该帧突跳
    （如 walk_slow 的 SKEL_R_Foot @f202、stow_lt 的 SKEL_ROOT @f120）。
    判据保守：`θ(prev,f) > deg` 且 `θ(f,next) > deg` 且 `θ(prev,next) < deg/2` ⇒ 用 slerp 中点替换。
    ⚠️ 只动"孤立"帧，真实快速动作（连续多帧大角速度）不会被误伤。"""
    cos_lim = math.cos(math.radians(deg)/2)
    cos_mid = math.cos(math.radians(deg/2)/2)
    fixed = []
    for f in range(1, len(quats)-1):
        p, c, n = quats[f-1], quats[f], quats[f+1]
        if _qdot(p, c) < cos_lim and _qdot(c, n) < cos_lim and _qdot(p, n) > cos_mid:
            quats[f] = [round(x, 5) for x in _slerp(tuple(p), tuple(n), 0.5)]
            fixed.append(f)
    return fixed


def export(path, out_json):
    d, body = load(path)
    anims = find_animations(body)
    # clip / animation name strings
    import re
    strs = sorted(set(m.group().decode() for m in re.finditer(rb'[\x20-\x7e]{4,}', body)))
    clips = [s.split('/')[-1] for s in strs if s.startswith('pack:/') and s.endswith('.clip')]
    animnames = [s.split('/')[-1] for s in strs if s.startswith('pack:/') and s.endswith('.anim')]
    out = {"file": os.path.basename(path), "clips": sorted(set(clips)),
           "animationNames": sorted(set(animnames)), "animations": []}
    n_fixed = 0
    for base, fr, sl, du, sp in anims:
        a = load_animation(body, base)
        s = a['seqs'][0]
        bones = []
        for bi, s2 in enumerate(s['animseq']):
            # ★ Track 过滤（2026-10-16）：`Bones` 元素 = {u16 boneId, u8 Unk0, u8 Track}，
            #   **Track==1 才是旋转轨**（0x3b/0x8a/0x06 等是位置轨）。原先用"通道数≥3 + 单位四元数"
            #   启发式 ⇒ 漏掉 `SKEL_L_Thigh`(Q2 形式) 等。实测本文件 Track==1 恰好 24 条旋转轨。
            track = a['boneids'][bi][2] if bi < len(a['boneids']) else 0
            if track != 1:
                continue
            if len(s2.channels) < 3:
                continue
            try:
                q0 = s2.evaluate_quat(0)
            except Exception:
                continue
            m = math.sqrt(sum(c*c for c in q0))
            if not (abs(m-1) < 0.05):
                # position-style: skip
                continue
            quats = []
            prev = None; mstep = 0.0
            for f in range(s['nframes']):
                q = s2.evaluate_quat(f)
                quats.append([round(c, 5) for c in q])
                if prev is not None:
                    dot = abs(sum(x*y for x, y in zip(q, prev)))
                    mstep = max(mstep, math.degrees(2*math.acos(min(1.0, dot))))
                prev = q
            fixed = repair_isolated_jumps(quats)
            if fixed:
                n_fixed += len(fixed)
                mstep = 0.0
                for f in range(1, len(quats)):
                    mstep = max(mstep, math.degrees(2*math.acos(min(1.0, _qdot(quats[f], quats[f-1])))))
            track = a['boneids'][bi] if bi < len(a['boneids']) else (0, 0, 0)
            bones.append({"i": bi, "boneId": track[0], "track": track[2],                          "nch": len(s2.channels), "maxstep": round(mstep, 1),
                          "fixed_frames": fixed, "quats": quats})
        bones.sort(key=lambda b: -b["maxstep"])
        out["animations"].append({"base": hex(base), "frames": fr, "duration": round(du, 3),
                                  "bones": bones})
    json.dump(out, open(out_json, 'w'), separators=(',', ':'))
    print("wrote", out_json, "clips:", out['clips'])
    print("  孤立单帧修复 %d 处" % n_fixed)
    for an in out["animations"]:
        print(f"  {an['base']} frames={an['frames']} animatedBones={len(an['bones'])} top={[b['maxstep'] for b in an['bones'][:6]]}")

if __name__ == '__main__':
    export(sys.argv[1], sys.argv[2])
