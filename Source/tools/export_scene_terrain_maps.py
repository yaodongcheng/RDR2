# -*- coding: utf-8 -*-
"""每个子场景导出骑砍2 用的**地形交付物**（交接文档 TODO-2）。

产物（`deliverable/blender/scenes/terrain/`）：

| 文件 | 规格 |
|---|---|
| `<id>_height_16bit.png` | 16 bit 灰度，**4 m/px**，**行 0 = 北**，范围 = 该场景远景框（按全局 4 m 格点取整） |
| `<id>_mask.png` | 8 bit 灰度，**全 255**（RDR2 只有单层地形材质，不拆 8 层） |
| `<id>_terrain.json` | 原点 / 分辨率 / 尺寸 / z 范围 / 编码公式（引擎换算用） |

🔴 采样口径与场景网格**同一份实现**（`scene_terrain_core.sample_h`：最近邻 + 行偏移 −1），
   所以把导出的高度图按"行 0 = 北、4 m/px"朴素读取，值就和 blend 里的地形顶点一致（验收 ±0.05 m）。
   ⚠️ 范围按**全局 4 m 格点**取整：西/南边最多多出 <4 m，东/北边最多少 <4 m；
      实际范围以 `<id>_terrain.json` 为准，不要按 scene_list.csv 的远景框硬算。

用法：
    python tools/export_scene_terrain_maps.py                # scene_list.csv 里全部（有远景尺寸的）
    python tools/export_scene_terrain_maps.py --only sdn,bla
    python tools/export_scene_terrain_maps.py --only sdn -v  # 打印自检细节
"""
import argparse
import csv
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import scene_terrain_core as C   # noqa: E402

SRC = os.path.dirname(HERE)
CSV_DEF = os.path.join(SRC, "docs", "世界与地编", "scene_list.csv")
OUTDIR = os.path.join(C.RDR2, "deliverable", "blender", "scenes", "terrain")
STEP = C.STEP

_META = None
_H = None


def _data():
    """高度图整张读一次就够（批量时别每张场景都读 30 MB）。"""
    global _META, _H
    if _META is None:
        _META = C.load_meta()
        _H = C.heights(_META)
    return _META, _H


def read_scenes(path=CSV_DEF):
    out = []
    with open(path, encoding="utf-8-sig", newline="") as fp:
        for r in csv.DictReader(fp):
            sid = (r.get("id") or "").strip()
            if not sid:
                continue
            try:
                x, y = float(r["x"]), float(r["y"])
                fw, fh = float(r["远景宽_m"]), float(r["远景高_m"])
            except Exception:
                continue            # 瓜玛：尺寸待定
            out.append({"id": sid, "kind": r.get("kind"), "name": r.get("name"),
                        "x": x, "y": y, "fw": fw, "fh": fh})
    return out


def _grid_axis(a0, a1, step=STEP):
    """全局格点（与 scene_terrain_core.axis 同口径），但**不追加非格点的 a1**。

    高度图必须是等间距的（引擎按 4 m/px 读），所以只在格点上取；a1 落在格点之间时，
    东/北边最多少 <1 格，实际范围写进 meta。
    """
    a = np.arange(np.floor(a0 / step) * step, a1 + 1e-6, step, dtype=np.float64)
    return a


def export_scene(sid, meta=None, H=None, csv_path=CSV_DEF, outdir=OUTDIR, verbose=False):
    """导出一个场景；返回 meta dict。找不到该场景的远景尺寸时返回 None。"""
    sc = next((s for s in read_scenes(csv_path) if s["id"] == sid), None)
    if sc is None:
        return None
    if meta is None or H is None:
        meta, H = _data()

    fx0, fy0 = sc["x"] - sc["fw"] / 2, sc["y"] - sc["fh"] / 2
    fx1, fy1 = sc["x"] + sc["fw"] / 2, sc["y"] + sc["fh"] / 2
    xs = _grid_axis(fx0, fx1)
    ys = _grid_axis(fy0, fy1)
    if len(xs) < 2 or len(ys) < 2:
        return None

    gx, gy = np.meshgrid(xs, ys)
    z = C.sample_h(meta, H, gx, gy).astype(np.float64)
    zz = z[::-1, :]                      # 行 0 = 北（最大 y）

    denom = max(1e-9, meta["zmax"] - meta["zmin"])
    v = np.clip(np.rint((zz - meta["zmin"]) / denom * 65535.0), 0, 65535).astype(np.uint16)

    os.makedirs(outdir, exist_ok=True)
    hp = os.path.join(outdir, "%s_height_16bit.png" % sid)
    mp = os.path.join(outdir, "%s_mask.png" % sid)
    jp = os.path.join(outdir, "%s_terrain.json" % sid)
    # uint16 数组会自动落成 I;16（16 bit 灰度）；不要用已弃用的 fromarray(mode=...)
    Image.fromarray(v).save(hp)
    Image.fromarray(np.full(v.shape, 255, dtype=np.uint8)).save(mp)

    out = {
        "id": sid, "kind": sc.get("kind"), "name": sc.get("name"),
        "height_png": os.path.basename(hp), "mask_png": os.path.basename(mp),
        "encoding": "z = zmin + v/65535*(zmax-zmin)",
        "zmin": meta["zmin"], "zmax": meta["zmax"],
        "res_m": STEP, "row0": "north",
        "origin_x": float(xs[0]), "origin_y": float(ys[-1]),   # 左上角 = 最西、最北
        "width": int(len(xs)), "height": int(len(ys)),
        "x0": float(xs[0]), "x1": float(xs[-1]),
        "y0": float(ys[0]), "y1": float(ys[-1]),
        "nominal_far": [round(fx0, 1), round(fy0, 1), round(fx1, 1), round(fy1, 1)],
        "source": os.path.relpath(meta["hfile"], C.RDR2).replace("\\", "/"),
    }
    json.dump(out, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---------- 自检：导出的 PNG 朴素读取 vs 场景网格采样（±0.05 m） ----------
    back = np.asarray(Image.open(hp), dtype=np.float64)
    zback = meta["zmin"] + back / 65535.0 * (meta["zmax"] - meta["zmin"])
    pts = [p for p in C.REGRESSION
           if out["x0"] <= p[0] <= out["x1"] and out["y0"] <= p[1] <= out["y1"]]
    # 补一批随机格点（只在场景内）
    rng = np.random.default_rng(20261104)
    for _ in range(64):
        ix = int(rng.integers(0, len(xs)))
        iy = int(rng.integers(0, len(ys)))
        pts.append((float(xs[ix]), float(ys[iy]), None))
    worst = 0.0
    worst_pt = None
    for px, py, _ref in pts:
        ix = int(round((px - out["x0"]) / STEP))
        iy = int(round((out["y1"] - py) / STEP))
        if not (0 <= ix < out["width"] and 0 <= iy < out["height"]):
            continue
        ref = float(C.sample_h(meta, H, px, py))
        d = abs(float(zback[iy, ix]) - ref)
        if d > worst:
            worst, worst_pt = d, (px, py, ref, float(zback[iy, ix]))
    status = "PASS" if worst <= 0.05 else "FAIL"
    out["check"] = {"points": len(pts), "max_err_m": round(worst, 4), "status": status}
    json.dump(out, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    if verbose:
        print("[maps] %-8s %4d×%-4d px · %.0f×%.0f m · 最大误差 %.3f m · %s%s"
              % (sid, out["width"], out["height"], out["x1"] - out["x0"],
                 out["y1"] - out["y0"], worst, status,
                 "" if worst <= 0.05 else "  最差点 %s" % (worst_pt,)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="只导这些 id，逗号分隔")
    ap.add_argument("--csv", default=CSV_DEF)
    ap.add_argument("--out", default=OUTDIR)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()

    meta, H = _data()
    only = set(x.strip() for x in a.only.split(",") if x.strip())
    scenes = [s for s in read_scenes(a.csv) if not only or s["id"] in only]
    print("=== 导出 %d 张场景的地形图（4 m/px · 行 0 = 北）→ %s" % (len(scenes), a.out))
    bad = 0
    for s in scenes:
        r = export_scene(s["id"], meta=meta, H=H, csv_path=a.csv, outdir=a.out,
                         verbose=a.verbose or True)
        if r is None:
            print("[maps] %-8s 跳过（没有远景尺寸）" % s["id"])
            continue
        ck = r["check"]
        print("[maps] %-8s %4d×%-4d · %s · 最大误差 %.3f m"
              % (s["id"], r["width"], r["height"], ck["status"], ck["max_err_m"]))
        if ck["status"] != "PASS":
            bad += 1
    print("=== 完成：%d 张，FAIL %d 张" % (len(scenes), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
