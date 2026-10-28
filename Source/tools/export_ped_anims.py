"""批量把 `.ycd` 解成「ped 骨架」上的动画数据（可直接交付/重定向）。

输出（export/animations_ped/<相对路径>.json）：
  {
    "file": "...ycd",
    "animations": [
      {"index": 0, "base": "0xf5a0", "frames": 398, "duration": 13.2,
       "bones": {"SKEL_L_Thigh": [[x,y,z,w], ...], ...}}
    ]
  }
说明：
  * 轨道按 **全局 tag → ped 骨名**（ped_bone_map.json）映射；映射不到的轨道（手指/装饰骨）丢弃并统计。
  * 四元数语义 = 「相对 ped rest 的增量」⇒ 消费方用 pose = R_rest ⊗ q（ped_skeleton.json 里有 rest）。
  * Track 过滤：只取 track==1（旋转）；`--repair-ramps` 可选修"整段爬升占满量程"的坏通道。

用法:
  python tools/export_ped_anims.py                 # 全量（412 个 ycd）
  python tools/export_ped_anims.py <某个.ycd>      # 单个
"""
import json
import os
import sys
import math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ycd_decode import load, find_animations, load_animation
from rdr2_ycd import ChCachedQuat

PROJ = os.path.dirname(HERE)
OUT = os.path.join(PROJ, 'export/animations_ped')
MAPF = os.path.join(PROJ, 'export/skeleton_runtime/ped_bone_map.json')
SKF = os.path.join(PROJ, 'export/skeleton_runtime/ped_skeleton.json')


def qnorm(q):
    n = math.sqrt(sum(c * c for c in q)) or 1.0
    return tuple(c / n for c in q)


def eval_quat(seq, f):
    """(x,y,z) 三个显式 + 缓存通道 = w（RDR2 语义，见 RDR2_ycd动画解码.md §7）"""
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
        return qnorm((v[0], v[1], v[2], cache.eval_float(f)))
    return qnorm(seq.evaluate_quat(f))


def repair_ramps(seq):
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
        diffs = [v[i + 1] - v[i] for i in range(0, n - 1, max(1, n // 8))]
        if not (all(d >= 0 for d in diffs) or all(d <= 0 for d in diffs)):
            continue
        if abs(v[-1] - v[0]) < 0.8 * span:
            continue
        med = sorted(v[:8])[len(v[:8]) // 2]
        c.values = [med] * n
        fixed += 1
    return fixed


def export_one(path, mapping, ped_names, do_repair):
    d, body = load(path)
    anims = find_animations(body)
    if not anims:
        return None, dict(blocks=0, tracks=0, dropped=0)
    out = dict(file=os.path.relpath(path, os.path.join(PROJ, 'export/animations')).replace('\\', '/'),
               animations=[])
    tot_tracks = tot_drop = 0
    for idx, (base, fr, sl, du, sp) in enumerate(anims):
        a = load_animation(body, base)
        s = a['seqs'][0]
        nf = s['nframes']
        bones = {}
        dropped = set()
        for bi, s2 in enumerate(s['animseq']):
            if bi >= len(a['boneids']):
                break
            bid, unk, trk = a['boneids'][bi]
            if trk != 1 or not s2.channels:
                continue
            nm = mapping.get(str(bid))
            if not nm or nm not in ped_names:
                dropped.add(bid)
                continue
            if do_repair:
                repair_ramps(s2)
            try:
                qs = [eval_quat(s2, f) for f in range(nf)]
            except Exception:
                continue
            bones[nm] = [[round(c, 5) for c in q] for q in qs]
        tot_tracks += len(bones)
        tot_drop += len(dropped)
        if bones:
            out['animations'].append(dict(index=idx, base=hex(base), frames=nf,
                                          duration=round(du, 3), bones=bones))
    return out, dict(blocks=len(anims), tracks=tot_tracks, dropped=tot_drop)


def main():
    mapping = json.load(open(MAPF, encoding='utf-8'))
    sk = json.load(open(SKF, encoding='utf-8'))
    ped_names = {b['name'] for b in sk['bones']}
    print('[map] %d 条 tag→骨名；ped 骨 %d' % (len(mapping), len(ped_names)))

    if len(sys.argv) > 1:
        files = [sys.argv[1]]
    else:
        files = []
        root = os.path.join(PROJ, 'export/animations')
        for dp, _, fns in os.walk(root):
            for fn in fns:
                if fn.lower().endswith('.ycd'):
                    files.append(os.path.join(dp, fn))
        files.sort()
    print('[in] %d 个 .ycd' % len(files))

    n_ok = n_clip = 0
    for i, f in enumerate(files):
        try:
            out, st = export_one(f, mapping, ped_names, do_repair=True)
        except Exception as e:
            print('  [x] %s: %s' % (os.path.basename(f), e))
            continue
        if not out or not out['animations']:
            continue
        rel = out['file'].replace('.ycd', '.json')
        dst = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        json.dump(out, open(dst, 'w'), separators=(',', ':'))
        n_ok += 1
        n_clip += len(out['animations'])
        if (i + 1) % 25 == 0:
            print('  %d/%d …' % (i + 1, len(files)))
    print('[done] %d 个文件 / %d 段动画 → %s' % (n_ok, n_clip, OUT))


if __name__ == '__main__':
    main()
