# -*- coding: utf-8 -*-
"""用人工标定的控制点，反解「官方地图 ↔ 我们的世界」的相似变换，并重画比对图。

## 你要做的只有一件事：填 3 个以上的点

1. 打开 `docs/世界与地编/img/ref_map_grid.png`（官方地图，1400 宽，每 100 px 一条网格线，标了像素坐标）
2. 打开 `docs/世界与地编/img/ours_grid.png`（我们的世界俯视图，1400×1400，同样带网格）
3. 在两张图里找**同一个特征点**（河口、湖角、城墙拐角…），把两边的像素坐标填进
   `地图下载/配准控制点.csv`：

    name,map_x,map_y,ours_x,ours_y
    圣丹尼斯河口,1188,660,1010,905
    瓦伦丁桥,805,405,650,905
    ...

   * `map_x/map_y` = 官方图上的像素（1400 宽那张）
   * `ours_x/ours_y` = 我方俯视图上的像素（1400×1400 那张）

4. 跑：

    python tools/fit_map_anchors.py

   会输出每个点的残差、总 RMS，并把标定结果写到 `地图下载/配准结果.json`。
   加 `--rerender` 会顺手重画 `docs/世界与地编/img/overlay_towns.png` / `overlay_water.png`。

## 为什么 3 个点就够

相似变换只有 4 个未知数（缩放 s、旋转 θ、平移 tx/ty）：
* 1 个点给 2 个方程 → 2 个点就能解（4 方程 4 未知）；
* **第 3 个点是"验算"**：三个点的残差都小，说明标定可信；
* 多于 3 个点时用最小二乘，抗单点误差。建议标 4~6 个点（分布在四个角最好）。

## 坐标口径

* 官方图：1400 px 宽，覆盖 `地图下载/大陆地图_缩略.jpg` 的可见范围（整幅地图，含纸边）。
* 我方图：1400×1400，正好覆盖世界方块 `x∈[-7684, 4612]、y∈[-8196, 4100]`（12296 m）。
  换算：`x = -7684 + (px+0.5)/1400*12296`，`y = 4100 - (py+0.5)/1400*12296`。
"""
import os
import sys
import csv
import json
import argparse

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "地图下载/配准控制点.csv")
OUT = os.path.join(ROOT, "地图下载/配准结果.json")

X0, YM1, WORLD, SCALE = -7684.0, 4100.0, 12296.0, 14.5
OURS_PX = 1400.0     # ours_grid.png 的边长
MAP_PX = 1400.0      # ref_map_grid.png 的宽度


def ours_px_to_world(px, py):
    return (X0 + (px + 0.5) / OURS_PX * WORLD,
            YM1 - (py + 0.5) / OURS_PX * WORLD)


def world_to_uv(x, y):
    return ((x - X0) / SCALE, (YM1 - y) / SCALE)


def fit_similarity(uv, px):
    """uv:(N,2) 我方 campaign 单位；px:(N,2) 官方图像素 → a, c, tx, ty（px = a*u - c*v + tx, c*u + a*v + ty）"""
    A, b = [], []
    for (u, v), (x, y) in zip(uv, px):
        A.append([u, -v, 1, 0]); b.append(x)
        A.append([v,  u, 0, 1]); b.append(y)
    sol, *_ = np.linalg.lstsq(np.array(A, float), np.array(b, float), rcond=None)
    a, c, tx, ty = sol
    return a, c, tx, ty


def apply_t(uv, a, c, tx, ty):
    u, v = uv[:, 0], uv[:, 1]
    return np.stack([a * u - c * v + tx, c * u + a * v + ty], axis=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=CSV)
    ap.add_argument("--rerender", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(a.csv):
        tpl = os.path.join(ROOT, "地图下载/配准控制点_模板.csv")
        with open(tpl, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["name", "map_x", "map_y", "ours_x", "ours_y"])
            w.writerow(["示例_圣丹尼斯河口", 1188, 660, 1010, 905])
            w.writerow(["示例_瓦伦丁桥", 805, 405, 650, 905])
        print("没找到 %s，已生成模板：%s" % (a.csv, tpl))
        return

    pts = []
    for r in csv.DictReader(open(a.csv, encoding="utf-8-sig")):
        try:
            mx, my = float(r["map_x"]), float(r["map_y"])
            ox, oy = float(r["ours_x"]), float(r["ours_y"])
        except (KeyError, TypeError, ValueError):
            continue
        wx, wy = ours_px_to_world(ox, oy)
        u, v = world_to_uv(wx, wy)
        pts.append((r.get("name", "?"), (u, v), (mx, my)))

    if len(pts) < 2:
        print("有效点不足 2 个（当前 %d），没法解相似变换" % len(pts))
        return

    uv = np.array([p[1] for p in pts])
    px = np.array([p[2] for p in pts])
    a_s, c_s, tx, ty = fit_similarity(uv, px)
    pred = apply_t(uv, a_s, c_s, tx, ty)
    res = np.linalg.norm(pred - px, axis=1)

    scale = float(np.hypot(a_s, c_s))
    rot = float(np.degrees(np.arctan2(c_s, a_s)))
    print("控制点 %d 个" % len(pts))
    print("  scale a = %.4f   rotation = %.2f°   tx = %.2f   ty = %.2f" % (scale, rot, tx, ty))
    print("  残差(px): 中位 %.1f  RMS %.1f  最大 %.1f" % (np.median(res), float(np.sqrt((res ** 2).mean())), res.max()))
    for (n, _, (x, y)), p, r in zip(pts, pred, res):
        print("   %-16s 观测(%6.1f,%6.1f) 预测(%6.1f,%6.1f) 误差 %5.1f px" % (n, x, y, p[0], p[1], r))

    out = dict(a=scale, c=float(c_s), tx=float(tx), ty=float(ty), rot_deg=rot,
               n=len(pts), rms_px=float(np.sqrt((res ** 2).mean())), points=[
                   dict(name=n, u=float(u), v=float(v), map_x=x, map_y=y, err_px=float(r))
                   for (n, (u, v), (x, y)), r in zip(pts, res)])
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("→", OUT)

    if a.rerender:
        try:
            import rerender_overlays
            rerender_overlays.run(scale, c_s, tx, ty)
            print("→ 已重画 overlay_towns.png / overlay_water.png")
        except Exception as e:
            print("重画失败（可忽略，脚本仍在 tools/ 下单独跑）：", e)


if __name__ == "__main__":
    main()
