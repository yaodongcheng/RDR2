"""合成一段"教科书走路"，直接驱动 RDR2 骨架 —— 用来把【骨架+蒙皮】和【.ycd 数据】分开验证。

如果这条合成走路膝盖正常弯、腿前后摆，说明骨架/蒙皮没问题，问题在 `.ycd` 的幅度/解码；
如果它也怪，那骨架还有问题。

约定（由实测得出）：在这套 .yft 骨骼里，矢状面（前后）旋转对应骨骼的 **local Z**。
用法: uv run python tools/make_synth_walk.py <out.json>
"""
import json
import math
import sys

TAGS = {
    'thigh': (65478, 6884),
    'calf': (55120, 43312),
    'foot': (45454, 33646),
}


def q_axis_z(deg):
    h = math.radians(deg) / 2.0
    return (0.0, 0.0, math.sin(h), math.cos(h))


def main():
    out_path = sys.argv[1]
    N = 60            # 60 帧一个循环
    cycles = 2
    frames = N * cycles
    bones = []

    def add(tag, quats):
        bones.append({"i": 0, "boneId": tag, "track": 1, "nch": 4,
                      "maxstep": 1.0,
                      "quats": [[round(c, 5) for c in q] for q in quats]})

    for side, (tl, tc, tf) in enumerate(zip(TAGS['thigh'], TAGS['calf'], TAGS['foot'])):
        phase = 0.0 if side == 0 else math.pi
        th, ca, fo = [], [], []
        for f in range(frames):
            t = 2 * math.pi * (f / N) + phase
            # 大腿：前后摆 ±25°
            th.append(q_axis_z(25.0 * math.sin(t)))
            # 小腿：支撑相基本伸直，摆动相弯到 55°
            bend = 55.0 * max(0.0, math.sin(t + math.pi * 0.55)) ** 1.2
            ca.append(q_axis_z(-bend))
            # 脚：跟随，落地时略微背屈
            fo.append(q_axis_z(12.0 * math.sin(t + math.pi * 0.9)))
        add(tl, th)
        add(tc, ca)
        add(tf, fo)

    out = {"file": "synthetic_walk", "clips": [], "animationNames": [],
           "animations": [{"base": "0x0", "frames": frames,
                           "duration": round(frames / 30.0, 3), "bones": bones}]}
    json.dump(out, open(out_path, 'w'), separators=(',', ':'))
    print('wrote', out_path, 'frames', frames, 'tracks', len(bones))


if __name__ == '__main__':
    main()
