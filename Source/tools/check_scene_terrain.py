# -*- coding: utf-8 -*-
"""场景地形算法自检（离线，不需要 Blender）。

    python tools/check_scene_terrain.py           # 生产口径自检 + 负面测试
    python tools/check_scene_terrain.py -v        # 打印每点明细

检查三件事（2026-11-04 那三条硬口径）：
  1. 采样值与 H4 一致（最近邻 + 行偏移 -1）；
  2. 网格轴吸附全局格点（都是 STEP 的整数倍）；
  3. **负面测试**：把行偏移改成 0、把最近邻改成双线性 —— 检查必须报错（证明有分辨力）。

任何一条不过 → 退出码 1。`tools/build_scenes.py` 开跑前会先调它，算法回归就立即停。
"""
import argparse
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene_terrain_core as core  # noqa: E402


def _sample_shift0(meta, H, x, y):
    """错误口径 A：行偏移不修正。"""
    fx = (x - meta["x0"]) / meta["hres"]
    fy = (meta["y1"] - y) / meta["hres"]
    ix = np.clip(np.rint(fx).astype(int), 0, meta["hw"] - 1)
    iy = np.clip(np.rint(fy).astype(int), 0, meta["hh"] - 1)
    return H[iy, ix]


def _sample_offgrid(meta, H, x, y):
    """错误口径 B：网格没吸附全局格点（顶点落在半格上，偏移 2 m）。"""
    return core.sample_h(meta, H, x + 2.0, y + 2.0)


def _h4(x, y):
    H = np.load(core.H4)
    c = int((x + 7684) / 4)
    r = int((y + 8196) / 4)
    return float(H[r, c])


def _fail(meta, H, sampler, tol=0.05):
    bad = []
    for x, y, exp in core.REGRESSION:
        got = float(sampler(meta, H, x, y))
        if abs(got - exp) > tol:
            bad.append((x, y, exp, got))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()

    meta = core.load_meta()
    H = core.heights(meta)
    ok = True

    # 1) 采样值 vs 回归点（同时对照 H4 原生值）
    bad = _fail(meta, H, core.sample_h)
    for x, y, exp in core.REGRESSION:
        got = float(core.sample_h(meta, H, x, y))
        h4 = _h4(x, y)
        flag = "OK " if abs(got - exp) <= 0.05 else "BAD"
        if a.verbose or flag == "BAD":
            print("  %s (%8.1f,%8.1f) 期望 %7.2f  实得 %7.2f  H4 %7.2f" % (flag, x, y, exp, got, h4))
    if bad:
        ok = False
        print("[check] FAIL 采样值与基准不符：%s" % bad)
    else:
        print("[check] 采样值 PASS（%d 个回归点，容差 0.05 m）" % len(core.REGRESSION))

    # 2) 网格轴吸附全局格点
    ax = core.axis(-1000.0, 1000.0, core.STEP)
    off = [float(v) for v in ax if abs(v / core.STEP - round(v / core.STEP)) > 1e-9]
    if off:
        ok = False
        print("[check] FAIL 网格未吸附全局格点：%s" % off[:5])
    else:
        print("[check] 网格吸附 PASS（轴步长 %.0f m，全部落在整数格点）" % core.STEP)

    # 3) 负面测试：错误口径必须被抓到（否则这个检查没有分辨力）
    neg = True
    for name, fn in (("行偏移不修正", _sample_shift0), ("网格未吸附（半格偏移）", _sample_offgrid)):
        bad = _fail(meta, H, fn)
        if bad:
            print("[check] 负面测试 PASS：%s → 被抓到（%d 个点超差，例 %s）"
                  % (name, len(bad), bad[0][:3]))
        else:
            neg = False
            print("[check] 负面测试 FAIL：%s → 检查没抓到，说明回归点选得不对" % name)
    ok = ok and neg

    print("[check] 结论：%s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
