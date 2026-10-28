# -*- coding: utf-8 -*-
"""武器 / 载具武器 / 弹药 参数表审计：把哈希列解成真名，并和已导出模型对账。

## 为什么需要
`CWeaponInfo.csv`（142 行）、`CAmmoInfo.csv`、`CVehicleWeaponInfo.csv` 是从 `.ymt`
里粗抽的：**Name 列只有 joaat 哈希（0x52BED408），其余数值列基本是空的**。
所以"武器参数都有了吗"之前无法回答——表里连一把枪叫什么都不知道。

本脚本用 `names.txt`（294 471 条资源名）建 joaat 反查表，把每个 `0x…` 单元格解回名字，
再与 `export/weapons/models`（实际导出的 .ydr/.ydd/.yft）+ `export/viewer/models/weapons`
（可预览 glTF）对账，输出：

  export/levels/world/weapon_audit.csv      每把武器：名字 / 有无模型 / 有无 glTF / 来源表
  export/levels/world/vehicle_weapon_audit.csv
  export/levels/world/ammo_audit.csv

用法：
  uv run python tools/build_weapon_audit.py
"""
import os
import re
import csv
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from rage_meta import joaat, load_names      # noqa: E402

NAMES = os.path.join(ROOT, "tools/rdr2rpf/bin/Release/net9.0/names.txt")
WORLD = os.path.join(ROOT, "export/levels/world")
WEAPON_MODELS = os.path.join(ROOT, "export/weapons/models")
WEAPON_GLTF = os.path.join(ROOT, "export/viewer/models/weapons")

HASH_RE = re.compile(r"^0x([0-9A-Fa-f]{6,8})$")


def load_name_map():
    return load_names(NAMES)


def resolve(val, nm):
    """单元格 → (hash_str, resolved_name)"""
    if not val:
        return "", ""
    m = HASH_RE.match(val.strip())
    if not m:
        return "", val
    h = int(m.group(1), 16)
    return val.strip(), nm.get(h, "")


def read_csv(p):
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def model_index():
    """已导出的武器模型 base 名（去掉 +hi / .ydr 等）"""
    idx = set()
    if os.path.isdir(WEAPON_MODELS):
        for f in os.listdir(WEAPON_MODELS):
            b = f.split(".")[0]
            b = b.replace("+hi", "").replace("_hi", "")
            idx.add(b.lower())
    gidx = set()
    if os.path.isdir(WEAPON_GLTF):
        for f in os.listdir(WEAPON_GLTF):
            if f.endswith(".gltf"):
                gidx.add(f[:-5].lower())
    return idx, gidx


def has_model(name, midx):
    """把 VEHICLE_WEAPON_GATLING / WEAPON_REVOLVER_CATTLEMAN 映射到 w_xxx_01 资产名"""
    if not name:
        return False
    n = name.lower()
    for pre in ("weapon_", "vehicle_weapon_", "ammo_"):
        if n.startswith(pre):
            n = n[len(pre):]
    cands = [n, "w_" + n, "w_" + n + "01x", "w_" + n + "01"]
    for c in cands:
        for suf in ("", "_hi"):
            if c + suf in midx:
                return True
    # 退化：前缀匹配（例如 repeater_carbine -> w_repeater_carbine01）
    stem = n.rstrip("0123456789_")
    return any(s.startswith("w_" + stem) for s in midx)


def main():
    nm = load_name_map()
    midx, gidx = model_index()

    # ---- 主武器表
    rows = read_csv(os.path.join(WORLD, "CWeaponInfo.csv"))
    out = []
    seen = set()
    for r in rows:
        h, name = resolve(r.get("Name", ""), nm)
        if not name:
            continue
        if name in seen:
            continue
        seen.add(name)
        out.append(dict(weapon=name, hash=h,
                        slot=r.get("Slot", ""), fire_type=r.get("FireType", ""),
                        weapon_type=r.get("WeaponType", ""), group=r.get("Group", ""),
                        has_model="Y" if has_model(name, midx) else "N",
                        has_gltf="Y" if has_model(name, gidx) else "N",
                        source="CWeaponInfo.csv"))
    # 已导出模型但表里没有的，也补上（说明模型比表全）
    for m in sorted(midx):
        n = m.replace("w_", "").rstrip("x")
        if not any(o["weapon"].lower().endswith(n) or n in o["weapon"].lower() for o in out):
            out.append(dict(weapon="(只在模型库)", hash="", slot="", fire_type="",
                            weapon_type="", group="", has_model="Y",
                            has_gltf="Y" if m in gidx else "N",
                            source="export/weapons/models"))

    def dump(fname, rows_):
        if not rows_:
            print("skip", fname)
            return
        with open(os.path.join(WORLD, fname), "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows_[0].keys()))
            w.writeheader()
            w.writerows(rows_)
        print(fname, len(rows_))

    dump("weapon_audit.csv", out)

    # ---- 载具武器
    vw = []
    for r in read_csv(os.path.join(WORLD, "CVehicleWeaponInfo.csv")):
        h, name = resolve(r.get("Name", ""), nm)
        vw.append(dict(vehicle_weapon=name or "(未解)", hash=h,
                       kickback_amplitude=r.get("KickbackAmplitude", ""),
                       kickback_impulse=r.get("KickbackImpulse", ""),
                       note="" if name else "该行只有哈希，表中无其它字段"))
    dump("vehicle_weapon_audit.csv", vw)

    # ---- 弹药
    am = []
    for r in read_csv(os.path.join(WORLD, "CAmmoInfo.csv")):
        h, name = resolve(r.get("Name", ""), nm)
        am.append(dict(ammo=name or "(未解)", hash=h))
    dump("ammo_audit.csv", am)

    named = sum(1 for o in out if o["weapon"] != "(只在模型库)")
    withm = sum(1 for o in out if o["has_model"] == "Y")
    print(f"武器: 解析出名字 {named} 条 / 有模型 {withm} 条 / 共 {len(out)} 行")


if __name__ == "__main__":
    main()
