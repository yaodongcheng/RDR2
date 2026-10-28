# -*- coding: utf-8 -*-
"""渲染骑砍2落地文档用的 Markdown 片段。"""
import json, csv, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

d = json.load(open(os.path.join(ROOT, "export/levels/world/settlements_bannerlord.json"), encoding="utf-8"))
FAC = d["factions"]; S = d["settlements"]
by = {r["code"]: r for r in S}
npc = list(csv.DictReader(open(os.path.join(ROOT, "export/levels/world/npc_roster.csv"), encoding="utf-8-sig")))

TYP = {"town": "城市", "castle": "城堡", "village": "村庄", "camp": "营地", "poi": "野外点位", "hideout": "藏身处"}
out = []

# ── 村庄依附表（按主人分组）
n_v = sum(1 for r in S if r["btype"] == "village")
out.append(f"### 村庄依附表（{n_v} 个村，全部有主）" + chr(10))
owners = [r for r in S if r["btype"] in ("town", "castle")]
groups = {}
for v in S:
    if v["btype"] == "village":
        groups.setdefault(v["bound_to"], []).append(v)
out.append("| 依附的城/堡 | 类型 | 势力 | 村庄 | 距离 (m) | 大地图距离 (u) |")
out.append("|---|---|---|---|---|---|")
empty = []
for o in owners:
    vs = groups.get(o["code"], [])
    if not vs:
        empty.append(o["name_zh"])
        continue
    for v in vs:
        out.append(f'| **{o["name_zh"]}** | {TYP[o["btype"]]} | {o["faction_zh"]} | {v["name_zh"]} | '
                   f'{v["bound_dist_m"]} | {round(v["bound_dist_m"]/14.5,1)} |')
out.append("")
out.append("> 无附属村的城/堡（%d 个）：%s —— 城堡靠自身田庄/驻军，不强行配村。" % (len(empty), "、".join(empty)))
out.append("")

# ── 全量归属表
out.append("### 43 个据点的归属\n")
out.append("| 类型 | 名称 | 势力 | 家族 | 领主/所有者 | 依附 | 距离 (m) |")
out.append("|---|---|---|---|---|---|---|")
for r in S:
    out.append(f'| {TYP[r["btype"]]} | **{r["name_zh"]}** | {r["faction_zh"]} | {r["clan"]} | {r["owner"]} | '
               f'{r["bound_name"] or "—"} | {r["bound_dist_m"] or "—"} |')
out.append("")

# ── NPC 按势力
FAC_ORDER = [("VDL", "范德林德帮"), ("US", "联邦 / 平克顿"), ("LEM", "莱莫恩庄园联盟"),
             ("COR", "康沃尔工业"), ("WAP", "瓦匹提部落"), ("GUA", "瓜马"),
             ("OUT", "边陲匪帮"), ("CIV", "平民 / 支线")]
for code, title in FAC_ORDER:
    rows = [n for n in npc if n["faction"] == code]
    if not rows:
        continue
    rows.sort(key=lambda n: (int(n["rank"]) if n["rank"] else 999, n["name_zh"]))
    out.append(f"### {title}（{len(rows)}）\n")
    out.append("| 中文名 | 英文名 | 身份 | 常驻地 | 置信度 |")
    out.append("|---|---|---|---|---|")
    for n in rows:
        out.append(f'| **{n["name_zh"]}** | {n["name_en"]} | {n["role"]} | {n["home"]} | {n["confidence"]} |')
    out.append("")

txt = "\n".join(out)
open(os.path.join(ROOT, "work/bannerlord_tables.md"), "w", encoding="utf-8").write(txt)
print(txt[:3000])
print("... total chars", len(txt))
