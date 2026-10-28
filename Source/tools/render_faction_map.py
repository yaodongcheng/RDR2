# -*- coding: utf-8 -*-
"""势力归属图：据点按势力着色，村庄连线到它的依附城/堡。"""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.colors import LightSource, LinearSegmentedColormap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = np.load(os.path.join(ROOT, "work/terrain/H4.npy"))
VM = np.load(os.path.join(ROOT, "work/terrain/valid4.npy"))
X0, Y0, RES = -7684.0, -8196.0, 4.0
X1, Y1 = 4612.0, 4100.0

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

d = json.load(open(os.path.join(ROOT, "export/levels/world/settlements_bannerlord.json"), encoding="utf-8"))
FAC = d["factions"]
rows = d["settlements"]

step = max(1, H.shape[0] // 1024)
h = H[::step, ::step].astype(float)
v = VM[::step, ::step] > 0
h = np.where(v, h, np.nan)

terr = LinearSegmentedColormap.from_list("rdr", [
    (0.00, "#1b3a42"), (0.10, "#24504a"), (0.22, "#3d6144"), (0.36, "#63784a"),
    (0.52, "#948f5e"), (0.72, "#b6a887"), (0.88, "#d8d2c4"), (1.00, "#f2f0ea")])
ls = LightSource(azdeg=315, altdeg=40)
rgb = ls.shade(np.nan_to_num(h, nan=0.0), cmap=terr, vert_exag=1.2, blend_mode="soft",
               vmin=-80, vmax=730)
rgb = rgb[..., :3]
rgb[~v] = np.array([0.105, 0.165, 0.180])
rgb = np.dstack([rgb, np.ones(v.shape)])

fig, ax = plt.subplots(figsize=(11, 11), dpi=160)
fig.patch.set_facecolor("#0d1117"); ax.set_facecolor("#0d1117")
ax.imshow(rgb, extent=[X0, X1, Y0, Y1], origin="lower")

k = 0
while X0 + k * 848 <= X1:
    ax.axvline(X0 + k * 848, color="#ffffff", lw=0.3, alpha=0.22); k += 1
k = 0
while Y0 + k * 848 <= Y1:
    ax.axhline(Y0 + k * 848, color="#ffffff", lw=0.3, alpha=0.22); k += 1

# 村庄 → 依附城/堡
by = {r["code"]: r for r in rows}
for r in rows:
    if r["btype"] == "village" and r["bound_to"]:
        o = by[r["bound_to"]]
        ax.plot([r["cx"], o["cx"]], [r["cy"], o["cy"]], color=FAC[r["faction"]]["color"],
                lw=0.9, alpha=0.45, ls=(0, (2, 2)), zorder=4)

STYLE = {
    "town": dict(marker="s", s=210, lw=1.0),
    "castle": dict(marker="^", s=230, lw=1.0),
    "village": dict(marker="o", s=62, lw=0.6),
    "camp": dict(marker="D", s=95, lw=0.7),
    "poi": dict(marker="P", s=80, lw=0.8),
    "hideout": dict(marker="X", s=95, lw=1.0),
}
for r in rows:
    st = STYLE[r["btype"]]
    ax.scatter(r["cx"], r["cy"], marker=st["marker"], s=st["s"],
               c=FAC[r["faction"]]["color"], edgecolors="white", linewidths=st["lw"],
               zorder=8 if r["btype"] in ("town", "castle") else 6)

OFF = {
    "圣丹尼斯": (310, 170), "罗兹": (-300, -200), "黑水镇": (-330, 110),
    "瓦伦丁": (150, 190), "草莓镇": (-350, 90), "犰狳镇": (-300, 130),
    "风滚草镇": (-380, 80), "安尼斯堡": (-340, 150), "范霍恩贸易站": (-360, 190),
    "阿瓜斯杜尔塞斯": (-340, 120), "布雷斯韦特庄园": (-420, -200),
    "卡利加庄园": (170, 170), "华莱士堡": (-300, 130), "默瑟堡": (120, 160),
    "西西卡监狱": (150, -190), "吊狗牧场": (-380, 110), "康沃尔煤油厂": (150, -170),
    "瓦匹提": (130, 190),
}
for r in rows:
    if r["btype"] in ("town", "castle"):
        dx, dy = OFF.get(r["name_zh"], (150, 120))
        ax.annotate(r["name_zh"], (r["cx"], r["cy"]), xytext=(r["cx"] + dx, r["cy"] + dy),
                    fontsize=8.5, color="white", zorder=12, ha="center",
                    bbox=dict(boxstyle="round,pad=0.22", fc="#000000", ec="none", alpha=0.65))

fac_handles = [Line2D([0], [0], marker="o", color="w", markersize=9,
                      markerfacecolor=FAC[k]["color"], label=f'{FAC[k]["zh"]}（{sum(1 for r in rows if r["faction"]==k)}）')
               for k in ["US", "LEM", "COR", "OUT", "VDL", "GUA", "WAP", "FREE"]]
type_handles = [
    Line2D([0], [0], marker="s", color="w", markerfacecolor="#bbb", markersize=11, label="城市 Town（10）"),
    Line2D([0], [0], marker="^", color="w", markerfacecolor="#bbb", markersize=11, label="城堡 Castle（11）"),
    Line2D([0], [0], marker="o", color="w", markerfacecolor="#bbb", markersize=7, label="村庄 Village（12）"),
    Line2D([0], [0], marker="D", color="w", markerfacecolor="#bbb", markersize=8, label="玩家营地（4）"),
    Line2D([0], [0], marker="P", color="w", markerfacecolor="#bbb", markersize=8, label="野外点位（4）"),
    Line2D([0], [0], marker="X", color="#bbb", markersize=9, label="藏身处（2）"),
]
l1 = ax.legend(handles=fac_handles, loc="lower left", framealpha=0.85, fontsize=8,
               title="势力", title_fontsize=9, bbox_to_anchor=(0.0, 0.03))
ax.add_artist(l1)
ax.legend(handles=type_handles, loc="lower left", framealpha=0.85, fontsize=8,
          title="据点类型", title_fontsize=9, bbox_to_anchor=(0.0, 0.22))

ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1); ax.set_aspect("equal")
ax.set_xlabel("RDR2 世界 X (m)", color="#444")
ax.set_ylabel("RDR2 世界 Y (m)", color="#444")
ax.set_title("荒野大镖客 2 · 势力归属与村庄依附（虚线 = 村庄 → 城/堡）", fontsize=13, pad=12)
ax.tick_params(labelsize=7, colors="#666")
for sp in ax.spines.values():
    sp.set_color("#888")

out = os.path.join(ROOT, "export/levels/world/faction_map.png")
fig.tight_layout()
fig.savefig(out, bbox_inches="tight", facecolor="#0d1117")
print("saved", out)
