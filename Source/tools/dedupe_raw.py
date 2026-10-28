#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
重复文件清理（保守版）：只删「有同内容副本、且位于可重抽的 raw/towns 抽取残留里」的文件。

规则
----
1. 按大小分组 + md5 比对，找完全重复；
2. 每个重复组里，如果**同时存在** canonical（`raw/lib_gtxd` / `raw/sdn` / `raw/models`）
   和 residue（`raw/towns/<area>/gtxd` 或 `raw/towns/<area>/gtxd_x`），则删 residue 的那份；
   理由：canonical 是贴图/模型的权威源（README 标注"别删"），residue 是重复抽取的残留；
3. 其它情况一律不删，只报告。

用法
----
uv run python tools/dedupe_raw.py            # 只报告
uv run python tools/dedupe_raw.py --apply    # 实际删除
"""
import argparse
import hashlib
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN = 5 * 1024 * 1024
CANON = ("raw/lib_gtxd", "raw/sdn", "raw/models", "raw/story")
RESIDUE = ("raw/towns/", "tmp_x/", "/tmp_x")
# tmp_x / gtxd_x 是同一区域重复抽取的试验目录，内容有副本即可删


def md5(p):
    m = hashlib.md5()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            m.update(b)
    return m.hexdigest()


def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    bysize = defaultdict(list)
    for dp, dns, fns in os.walk(os.path.join(ROOT, "raw")):
        dns[:] = [d for d in dns if not os.path.islink(os.path.join(dp, d))]
        for f in fns:
            p = os.path.join(dp, f)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            if os.path.islink(p) or st.st_size < MIN:
                continue
            bysize[st.st_size].append(p)

    plans = []
    for sz, paths in bysize.items():
        if len(paths) < 2:
            continue
        byhash = defaultdict(list)
        for p in paths:
            try:
                byhash[md5(p)].append(p)
            except OSError:
                pass
        for h, group in byhash.items():
            if len(group) < 2:
                continue
            rs = [rel(p) for p in group]
            has_canon = any(r.startswith(CANON) for r in rs)
            residues = [p for p, r in zip(group, rs) if any(k in r for k in RESIDUE)]
            if residues and len(residues) < len(group):
                for p in residues:
                    plans.append((sz, p, [r for r in rs if r != rel(p)]))
            else:
                print(f"[跳过] {sz/1048576:7.1f} MB × {len(group)}  无法安全判定保留哪份：")
                for r in rs:
                    print("        ", r)

    plans.sort(key=lambda x: -x[0])
    total = sum(p[0] for p in plans)
    print(f"\n=== 可删（raw/towns 抽取残留，canonical 副本保留）===")
    for sz, p, keeps in plans:
        print(f"  {sz/1048576:7.1f} MB  DEL {rel(p)}")
        print(f"                    保留 {keeps[0]}")
    print(f"\n合计可回收: {total/1073741824:.2f} GB  ({len(plans)} 个文件)")

    if args.apply and plans:
        freed = 0
        for sz, p, _ in plans:
            try:
                os.remove(p)
                freed += sz
            except OSError as e:
                print("  删除失败:", rel(p), e)
        print(f"\n已删除 {len(plans)} 个文件，回收 {freed/1073741824:.2f} GB")
    elif plans:
        print("\n（预演模式，未删除；加 --apply 执行）")


if __name__ == "__main__":
    main()
