# -*- coding: utf-8 -*-
"""把武器"主体 + 部件"装配成一个完整 glTF。

## 为什么需要这一步

RDR2 的长枪（步枪/连发枪/霰弹枪）在游戏里是**拼装**的：
  - `w_repeater_carbine01.ydr`      ← 只有金属件（机匣 + 枪管 + 扳机/杠杆）
  - `w_repeater_carbine01_grip1.ydr`← 木质件（枪托 + 护木），三套木纹样式 grip1/2/3
  - `w_repeater_carbine01_sight1`   ← 准星/照门
  - `w_repeater_carbine01_clip1`    ← 弹仓
  - `w_repeater_carbine01_wrap1`    ← 布/皮革缠绕（纯外观，默认不装）

旧流程只导了主体，所以查看器里所有长枪"缺枪托"——不是解包漏了，是**没装部件**。
左轮手枪是例外：握把本来就在主体里（grip1..5 是象牙/珍珠等替换样式），不需要装配。

## 用法

    python tools/export_weapon_assembled.py                 # 全部主体 → export/viewer/models/weapons
    python tools/export_weapon_assembled.py --only w_repeater_carbine01
    python tools/export_weapon_assembled.py --out-root <临时目录>   # 试跑，不动现网

输出：
    export/viewer/models/weapons/<base>.gltf/.bin   覆盖为装配版
    export/levels/world/weapon_assembly.csv          每个武器装了哪些部件
"""
import os, sys, glob, csv, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import export_sdn_gltf as G
import rdr2_ytd as T

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "export/weapons/models")
OUT = os.path.join(ROOT, "export/viewer/models/weapons")

# 部件后缀 → 装配优先级。同组只取第一个（grip1 优于 grip2/3：三套只是木纹样式）
# 装配规则（2026-10-21 实测结论）
#   grip1/2/3 = 木质枪托 + 护木（长枪唯一的木质件，三套只是木纹样式）→ **必须装**，否则枪"没有枪托"#   stock1/2/3 = 削短霰弹枪的可选枪托（默认不带，属于改装件）→ 默认不装
#   sight1/2 = 准星/照门改装件（主体自带你默认的那套）→ 默认不装，避免与主体重复
#   clip1..3 = 弹仓/弹匣扩容件；mag1..3 = 双管霰弹枪弹仓 → 默认不装
#   wrap1..6 = 布/皮革缠绕（纯外观）；barrel1/2 = 枪管长度替换件 → 不装
#   bullet / strap / inner / slod / hi = 子弹、背带、内筒、低模 → 不装
COMP_GROUPS = [
    ("grip", ("grip1", "grip2", "grip3", "grip4", "grip5")),
]
# 想连准星/弹仓一起装：把对应后缀加进 COMP_GROUPS 即可
SKIP_SUFFIX = ("wrap", "barrel", "bullet", "strap", "inner", "slod", "hi")

# 这些主体系列握把在主体里，不需要 grip 部件（装上会与握把重复）
# 左轮/手枪的 _grip1..5 是"木质/象牙握把片"，和主体握把区完全重合（实测
# cattleman 主体 x[-0.101,0.166]、grip1 x[-0.102,-0.023]），装上才是游戏里的样子 → 要装。
# 只有近战/投掷/工具这类"握把就是本体"的才跳过。
NO_GRIP_PREFIX = ("w_melee_", "w_sp_", "w_throw_", "w_stick_",
                  "w_binocular", "w_camera", "w_electric", "w_leftshoulder", "w_sight_",
                  "w_rifle_scope", "w_rifle_binoculars", "w_engravings")


class TexLib(G.TexLib):
    """复用 export_sdn_gltf 的 TexLib（建索引 + 解码 mip0）"""


def base_name(fn):
    return os.path.splitext(os.path.basename(fn))[0]


COMP_SUFFIX_RE = None


def split_parts(stem):
    """w_repeater_carbine01_grip1 → ('w_repeater_carbine01', 'grip1')；不是部件返回 (None, None)"""
    global COMP_SUFFIX_RE
    import re
    if COMP_SUFFIX_RE is None:
        COMP_SUFFIX_RE = re.compile(
            r"^(.*)_(grip\d|stock\d|sight\d|clip\d?|mag\d|barrel\d+|wrap\d|bullet|strap\d*|inner\d*)$")
    m = COMP_SUFFIX_RE.match(stem)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def build_index():
    """→ {base: {'main': path, 'grip1': path, ...}}

    注意：`w_shotgun_sawed01_stock1` 这类"看着像部件、其实是独立模型"的文件，
    只有当去掉后缀后确实存在同名主体时才归为部件（否则它自己就是主体）。
    """
    files = {}
    for f in sorted(glob.glob(os.path.join(SRC, "*.ydr"))):
        stem = base_name(f)
        low = stem.lower()
        if "_slod" in low or low.endswith("_hi"):
            continue
        files[stem] = f
    idx = {}
    for stem, f in files.items():
        b, part = split_parts(stem)
        if b and b in files:
            idx.setdefault(b, {})[part] = f
        else:
            idx.setdefault(stem, {})["main"] = f
    return idx


def pick_parts(base, parts):
    """按 COMP_GROUPS 顺序挑要装的部件；枪管作为候选带上，是否真装见 assemble()"""
    out = []
    skip_grip = base.lower().startswith(NO_GRIP_PREFIX)
    for g, names in COMP_GROUPS:
        if g == "grip" and skip_grip:
            continue
        for n in names:
            if n in parts:
                out.append(n)
                break
    for n in ("barrel1", "barrel01"):
        if n in parts:
            out.append(n)
            break
    return out


def geom_max_x(geoms):
    return max((v[0] for g in geoms for v in g["pos"]), default=-9e9)


def assemble(base, main_path, comp_paths, out_dir, texlib, tex_uri):
    m = G.load_model(main_path)
    if not m:
        return None
    geoms = list(m["geoms"])
    for g in geoms:
        g["ytd"] = g.get("ytd") or m.get("ytd")
    ytd_main = m.get("ytd")
    base_maxx = geom_max_x(geoms)
    used = []
    for cname in comp_paths:
        cm = G.load_model(os.path.join(SRC, base + "_" + cname + ".ydr"))
        if not cm:
            continue
        # 枪管类部件：只有"主体真的缺枪管"时才装（双管霰弹枪就是这种：
        # 主体只到 x=0.277，barrel1 一直到 0.571，不装就是根没有管子的枪）。
        # 其余霰弹枪/手枪的 barrelN 是"枪管更长/更短"的替换件，主体已经有管，装上会穿模、z-fighting。
        if cname.startswith("barrel"):
            short_gun = base.lower().startswith(("w_revolver_", "w_pistol_"))
            if not short_gun and geom_max_x(cm["geoms"]) - base_maxx <= 0.12:
                continue
        for g in cm["geoms"]:
            g["ytd"] = cm.get("ytd")
            geoms.append(g)
        used.append(cname)
    merged = dict(geoms=geoms, ytd=ytd_main)
    out = os.path.join(out_dir, base + ".gltf")
    try:
        G.write_tile(out, {base: merged}, [[base, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1]], texlib, tex_uri, None)
        return used
    except Exception as e:
        print("FAIL", base, e)
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--out-root", default="")
    ap.add_argument("--tex", action="store_true", default=True)
    a = ap.parse_args()
    out_root = os.path.abspath(a.out_root) if a.out_root else OUT
    tex_uri = os.path.join(out_root, "textures")
    os.makedirs(tex_uri, exist_ok=True)

    idx = build_index()
    texlib = TexLib([SRC], maxs=256) if a.tex else None
    only = {x.strip() for x in a.only.split(",") if x.strip()}

    rows = []
    ok = 0
    for base, parts in sorted(idx.items()):
        mainp = parts.get("main")
        if not mainp:
            continue
        if only and base not in only:
            continue
        comp = pick_parts(base, parts)
        used = assemble(base, mainp, comp, out_root, texlib, tex_uri)
        if used is None:
            continue
        ok += 1
        rows.append({"base": base, "category": "", "parts": ";".join(used),
                     "part_count": 1 + len(used)})
        print(("OK  %-42s %s" % (base, " + ".join(used) or "(单件)")), flush=True)
    print("done", ok)

    if not only:
        csvp = os.path.join(ROOT, "export/levels/world/weapon_assembly.csv")
        with open(csvp, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["base", "parts", "part_count"])
            w.writeheader()
            for r in rows:
                w.writerow({"base": r["base"], "parts": r["parts"], "part_count": r["part_count"]})
        print("csv", csvp)


if __name__ == "__main__":
    main()
