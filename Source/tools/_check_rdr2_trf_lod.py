#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TRF 交付物校验（只读，纯 Python，秒级）—— 逐文件检查结构 + LOD 档位。

判据：
  ① 首行 `rfver 4`、末行 `end`
  ② `mesh` 记录数与解析结果一致
  ③ **LOD0 面数 == 清单 `faces`**（`.mdl` 的三角数）
  ④ 有 LOD 的模型：每档面数**不增**，且档位从 0 连续到 N
  ⑤ 网格名遵守 `<名>.<子网格序>` / `<名>.lod<N>.<子网格序>`

用法：
```powershell
python tools/_check_rdr2_trf_lod.py --set import --sample 200
python tools/_check_rdr2_trf_lod.py --set import            # 全量（约 1~2 分钟）
```
"""
import argparse
import collections
import csv
import io
import os
import re
import sys

ROOT = r"D:\BrainMaker\大镖客2解包分析"
MANIFESTS = os.path.join(ROOT, "deliverable", "manifests")
SETS = {
    "import": (os.path.join(MANIFESTS, "models_export.csv"),
               os.path.join(ROOT, "deliverable", "models")),
    "extra": (os.path.join(MANIFESTS, "models_export_extra.csv"),
              os.path.join(ROOT, "deliverable", "models_extra")),
}
NAME_RE = re.compile(r"^(?P<base>.+?)(?:\.lod(?P<lod>\d+))?\.(?P<sub>\d+)$")


def parse_trf(path):
    """→ [(name, materials, face_count)]；结构不对抛异常。"""
    with io.open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    if not lines or lines[0].strip() != "rfver 4":
        raise ValueError("bad header: %r" % (lines[0] if lines else ""))
    n = int(lines[1].split()[1])
    i = 2
    out = []
    for _ in range(n):
        head = lines[i].split()
        i += 1
        vc = int(lines[i])
        i += 1 + vc
        i += 1                                  # flag
        fvf = int(lines[i])
        i += 1 + fvf * 3
        mk = int(lines[i])
        i += 1
        for _m in range(mk):
            i += 1
            c = int(lines[i])
            i += 1 + c
        fc = int(lines[i])
        i += 1 + fc
        out.append((head[0], head[2:], fc))
    if lines[i].strip() != "end":
        raise ValueError("missing end (line %d)" % i)
    return out


def main():
    argv = sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=list(SETS), default="import")
    ap.add_argument("--sample", type=int, default=0, help="只查前 N 个（0 = 全部）")
    ap.add_argument("--every", type=int, default=0, help="等间隔抽样")
    a = ap.parse_args(argv)

    manifest, dirp = SETS[a.set]
    with io.open(manifest, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if a.every > 0:
        rows = rows[::a.every]
    if a.sample > 0:
        rows = rows[:a.sample]

    bad = 0
    no_lod = 0
    lod_ok = 0
    for r in rows:
        name = r["name"]
        p = os.path.join(dirp, name + ".trf")
        try:
            if not os.path.exists(p):
                raise ValueError("missing file")
            meshes = parse_trf(p)
            by_lv = collections.defaultdict(int)
            for mname, mats, fc in meshes:
                m = NAME_RE.match(mname)
                if not m or m.group("base") != name:
                    raise ValueError("bad mesh name %r" % mname)
                lv = int(m.group("lod")) if m.group("lod") else 0
                by_lv[lv] += fc
            lv0 = by_lv.get(0, 0)
            exp = int(float(r.get("faces") or 0))
            if lv0 != exp:
                raise ValueError("LOD0 faces %d != manifest %d" % (lv0, exp))
            levels = sorted(by_lv)
            if levels != list(range(len(levels))):
                raise ValueError("LOD levels not contiguous: %s" % levels)
            faces = [by_lv[k] for k in levels]
            if any(faces[i + 1] > faces[i] for i in range(len(faces) - 1)):
                raise ValueError("LOD faces not non-increasing: %s" % faces)
            if len(levels) > 1:
                lod_ok += 1
            else:
                no_lod += 1
        except Exception as e:
            bad += 1
            if bad <= 20:
                print("FAIL|%s|%s" % (name, e))

    print("TOTAL %d | 多档 %d | 单档 %d | BAD %d  (dir=%s)"
          % (len(rows), lod_ok, no_lod, bad, dirp))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
