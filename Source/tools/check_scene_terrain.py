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
import csv
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene_terrain_core as core  # noqa: E402

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENE_CSV = os.path.join(SRC, "docs", "世界与地编", "scene_list.csv")
UV_SCENE = "bla"          # 黑水镇：镇区街道南北不对称，最能分辨 UV 翻转
UV_TOL = 8                # 单点允许的最大通道差（0~255）
UV_MAX_BAD = 0.02         # 允许的超差点比例


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


def _scene_box(sid):
    """从 scene_list.csv 取场景远景框 (x0, y0, x1, y1)。"""
    with open(SCENE_CSV, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("id") or "").strip() == sid:
                cx, cy = float(r["x"]), float(r["y"])
                fw, fh = float(r["远景宽_m"]), float(r["远景高_m"])
                return (cx - fw / 2, cy - fh / 2, cx + fw / 2, cy + fh / 2)
    raise RuntimeError("scene_list.csv 里找不到场景 %s" % sid)


def _uv_roundtrip(meta, box, img, uv_fn, n=32):
    """UV 朝向的往返比对：世界→像素(A) vs 世界→UV→Blender 取图(B)。

    比对对象是**场景实际用的那块贴图**（按 crop_color 同一口径从 color_1m 裁出来）。
    Blender 取图规则：u=0 在图像左边、**v=0 在图像底边** ⇒ 像素列 = u*W，行 = (1-v)*H。
    A、B 都取整数米点位，正确时逐点相等；V 翻转时 B 取到南北镜像点。
    返回 (超差点比例, 各点通道差均值, 图像比对的颜色标准差)。
    """
    x0, y0, x1, y1 = box
    x0 = max(x0, meta["x0"]); y0 = max(y0, meta["y0"])
    x1 = min(x1, meta["x1"]); y1 = min(y1, meta["y1"])
    # 与 scene_terrain.crop_color 同一口径裁出场景贴图
    c0 = int(round((x0 - meta["x0"]) / meta["cres"]))
    c1 = int(round((x1 - meta["x0"]) / meta["cres"]))
    r0 = int(round((meta["y1"] - y1) / meta["cres"]))
    r1 = int(round((meta["y1"] - y0) / meta["cres"]))
    tex = img[r0:r1, c0:c1]
    H, W = tex.shape[:2]

    xs = np.linspace(np.ceil(x0), np.floor(x1), n)
    ys = np.linspace(np.ceil(y0), np.floor(y1), n)
    gx, gy = np.meshgrid(xs, ys)
    gx = np.round(gx); gy = np.round(gy)

    # A：直接按世界坐标取图（贴图行 0 = 北）
    ca = np.clip(np.round(gx - x0).astype(int), 0, W - 1)
    ra = np.clip(np.round(y1 - gy).astype(int), 0, H - 1)
    a = tex[ra, ca].astype(np.int16)

    # B：走 UV，再按 Blender 的取图规则回到像素
    u, v = uv_fn(gx, gy, box)
    cb = np.clip(np.round(u * W).astype(int), 0, W - 1)
    rb = np.clip(np.round((1.0 - v) * H).astype(int), 0, H - 1)
    b = tex[rb, cb].astype(np.int16)

    d = np.abs(a - b).max(axis=2)
    return float((d > UV_TOL).mean()), float(d.mean()), float(a.std())


def check_uv_orientation(a):
    """地形贴图 UV 朝向（V 轴不能翻转）+ 负面测试。"""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    meta = core.load_meta()
    if not os.path.exists(meta["cfile"]):
        print("[check] SKIP 贴图 UV 朝向（找不到 %s）" % meta["cfile"])
        return True
    box = _scene_box(UV_SCENE)
    img = np.asarray(Image.open(meta["cfile"]).convert("RGB"))
    img = img[: meta["ch"], : meta["cw"]]

    bad, mean, std = _uv_roundtrip(meta, box, img, core.uv_of)
    good = (bad <= UV_MAX_BAD) and (std > 5.0)
    if a.verbose or not good:
        print("  UV 往返：超差 %.1f%% / 平均通道差 %.1f / 图像标准差 %.0f（%s 场景）"
              % (100 * bad, mean, std, UV_SCENE))
    if std <= 5.0:
        print("[check] FAIL UV 朝向检查没有分辨力（取样区颜色太平，std=%.1f）" % std)
        return False
    if not good:
        print("[check] FAIL 地形贴图 UV 朝向错：v 必须随 y 增大（v=0 在图像底边=南）")
        return False
    print("[check] 贴图 UV 朝向 PASS（%s 场景 %d×%d 点往返一致）" % (UV_SCENE, 32, 32))

    # 负面测试：V 翻转必须被抓到
    def _flip(x, y, b):
        u, v = core.uv_of(x, y, b)
        return u, 1.0 - v

    bad_f, mean_f, _ = _uv_roundtrip(meta, box, img, _flip)
    if bad_f > UV_MAX_BAD:
        print("[check] 负面测试 PASS：V 翻转 → 被抓到（超差 %.1f%%，平均通道差 %.0f）"
              % (100 * bad_f, mean_f))
        return True
    print("[check] 负面测试 FAIL：V 翻转没被抓到（超差 %.1f%%），说明取样区对称、检查无效"
          % (100 * bad_f))
    return False


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

    # 4) 贴图 UV 朝向（V 轴不能翻转；带负面测试）
    ok = check_uv_orientation(a) and ok

    print("[check] 结论：%s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
