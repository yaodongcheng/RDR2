# -*- coding: utf-8 -*-
"""更新方案文档里的 44 据点表：加“可走 P (km²)”列，T 改叫地形 T。"""
import csv, json, io, os

RDR2 = r"D:\BrainMaker\大镖客2解包分析"
BASE = os.path.join(RDR2, "_scratch", "settlement_plan")
DOC = r"h:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source\docs\世界与地编\RDR2_据点分级与场景边界方案.md"

rows = list(csv.DictReader(open(os.path.join(BASE, "settlements_plan.csv"), encoding="utf-8-sig")))
pdata = json.load(open(os.path.join(BASE, "settlements_p.json"), encoding="utf-8"))
bubbles = json.load(open(os.path.join(BASE, "bubbles.json"), encoding="utf-8"))
small_host = {code: b["id"] for b in bubbles for code in b["small_codes"]}

def f(x):
    try:
        return float(x)
    except Exception:
        return 0.0

order = {"city": 0, "castle": 1, "village": 2}
rows.sort(key=lambda r: (order[r["tier"]], -f(r["scene_T_m"]), r["code"]))

lines = []
lines.append("> **T 不是可走面积**：T 是场景地形方框；**可走 P** 是「建成区 + 边距 ∩ 领地线 ∩ T」。带 `*` 的是并进野外的小据点：P 是本村领地，实际可走 = 宿主野外场景 **5.31 km²**（2,304 m 方框）。")
lines.append("")
lines.append("| 据点 | 编码 | 层级 | RDR2 类型 | 地形 T (m) | 可走 P (km²) | 远景环宽 W (m) | 外框 O (m) | 归属场景 | 实例/建筑/建筑面数 |")
lines.append("|---|---|---|---|---:|---:|---:|---:|---|---|")
for r in rows:
    code = r["code"]
    p = pdata.get(code, {})
    area = p.get("P_area_km2", 0)
    host = small_host.get(code, "")
    T = int(f(r["scene_T_m"]))
    W = 1200 if r["tier"] == "city" else 800 if r["tier"] == "castle" else 500 if r["rdr2_type"] == "hideout" else 600
    O = T + 2 * W
    Tstr = str(T) + ("*" if host else "")
    Wstr = "—" if host else str(W)
    Ostr = "—" if host else str(O)
    owner = host if host else "自成场景"
    pa = f"{area:.2f}" + ("*" if host else "")
    lines.append(f'| {r["name_zh"]} | `{code}` | {r["tier"]} | {r["rdr2_type"]} | {Tstr} | {pa} | {Wstr} | {Ostr} | {owner} | {int(f(r["n_inst"]))}/{int(f(r["n_bld"]))}/{int(f(r["bld_tris"]))} |')

table = "\n".join(lines)

doc = io.open(DOC, encoding="utf-8").read()
start = doc.index("| 据点 | 编码 | 层级 | RDR2 类型 | 地形 T (m) | 可走 P (km²) | 远景环宽 W (m) | 外框 O (m) | 归属场景 | 实例/建筑/建筑面数 |")
# include the note line before the table if present
before = doc.rfind("\n", 0, start)
# find end of table: next "\n---\n"
end = doc.index("\n---\n", start)
new = doc[:start] + table + doc[end:]
io.open(DOC, "w", encoding="utf-8").write(new)
print("replaced table", len(table), "chars")
