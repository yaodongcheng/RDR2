# -*- coding: utf-8 -*-
"""在 .yas 的 PSIN 里暴力找「时间轴」：等距、单调递增、落在 0~60 秒的浮点序列

思路
----
镜头表最可能的形态是一串「起始时间」或「时长」。它们在二进制里表现为：
    · 同 stride、同 phase 的一列 f32
    · 数值单调不减，且落在 0~60 秒（或 0~1800 帧）

本脚本对所有 (stride ≤ 256, phase < stride) 组合扫一遍，找出满足条件的列，
并按「长度是否等于该场景的镜头数」排序输出。

用法
    uv run python tools/probe_yas_timeline.py <yas> [--shots N]
"""
import argparse
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_pso as P


def scan(psin, max_stride=256, lo=0.2, hi=64.0, minlen=3):
    """返回 [(长度, stride, phase, 首值, 末值, 首个偏移, 值域跨度)]"""
    best = []
    n = len(psin)
    for stride in range(4, max_stride + 1, 4):
        for phase in range(0, min(stride, n), 4):
            run = []
            o = phase
            while o + 4 <= n:
                v = struct.unpack_from('<f', psin, o)[0]
                ok = (lo <= v <= hi) and (v == v)
                if ok and (not run or v >= run[-1][1] - 0.001):
                    run.append((o, v))
                else:
                    if ok:
                        if len(run) >= minlen:
                            best.append((len(run), stride, phase, round(run[0][1], 2),
                                         round(run[-1][1], 2), run[0][0]))
                        run = [(o, v)]
                    else:
                        if len(run) >= minlen:
                            best.append((len(run), stride, phase, round(run[0][1], 2),
                                         round(run[-1][1], 2), run[0][0]))
                        run = []
                o += stride
            if len(run) >= minlen:
                best.append((len(run), stride, phase, round(run[0][1], 2),
                             round(run[-1][1], 2), run[0][0]))
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('yas')
    ap.add_argument('--shots', type=int, default=0)
    args = ap.parse_args()
    info, sec = P.parse(args.yas)
    psin = sec.get('PSIN') or b''
    print('%s  PSIN=%d  镜头数(参考)=%s' % (os.path.basename(args.yas), len(psin),
                                        args.shots or '?'))
    best = scan(psin)
    # 优先：长度大、值跨度接近整段过场
    best.sort(key=lambda x: (-x[0], -(x[4] - x[3])))
    seen = set()
    shown = 0
    for cnt, stride, phase, v0, v1, off in best:
        key = (cnt, round(v0, 1), round(v1, 1))
        if key in seen:
            continue
        seen.add(key)
        flag = '  <== 长度==镜头数' if args.shots and cnt == args.shots else ''
        print('  长度%3d stride=%3d phase=%3d 值 %.2f→%.2f 起始偏移 %#x%s' % (
            cnt, stride, phase, v0, v1, off, flag))
        shown += 1
        if shown >= 25:
            break


if __name__ == '__main__':
    main()
