# -*- coding: utf-8 -*-
"""把 43 个据点画到 848 大地图上（晕渲地形 + 848 m 网格 + 档位配色）。"""
import json, os, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.colors import LightSource

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = np.load(os.path.join(ROOT, "work/terrain/H4.npy"))
VM = np.load(os.path.join(ROOT, "work/terrain/valid4.npy"))
X0, Y0, RES = -7684.0, -8196.0, 4.0
X1, Y1 = 4612.0, 4100.0

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

rows = json.load(open(os.path.join(ROOT, "export/levels/world/settlements.json"), encoding="utf-8"))["settlements"]

# 下采样到 ~1024
step = max(1, H.shape[0] // 1024)
h = H[::step, ::step].astype(float)
v = VM[::step, ::step] > 0
h = np.where(v, h, np.nan)
ext = [X0, X1, Y0, Y1]

# 高程配色：低地墨绿 → 草原黄绿 → 荒漠土黄 → 高山灰白
from matplotlib.colors import LinearSegmentedColormap
terr = LinearSegmentedColormap.from_list("rdr", [
    (0.00, "#1b3a42"), (0.10, "#24504a"), (0.22, "#3d6144"), (0.36, "#63784a"),
    (0.52, "#948f5e"), (0.72, "#b6a887"), (0.88, "#d8d2c4"), (1.00, "#f2f0ea")])
ls = LightSource(azdeg=315, altdeg=40)
rgb = ls.shade(np.nan_to_num(h, nan=0.0), cmap=terr, vert_exag=1.2, blend_mode="soft",
               vmin=-80, vmax=730)
# 无效区（水体/无地形 patch）统一填成深青灰，避免画面出现"黑洞"
base = np.array([0.105, 0.165, 0.180])
rgb = rgb[..., :3]
rgb[~v] = base
rgb = np.dstack([rgb, np.ones(v.shape, dtype=float)])

fig, ax = plt.subplots(figsize=(10.5, 10.5), dpi=160)
fig.patch.set_facecolor("#0d1117"); ax.set_facecolor("#0d1117")
ax.imshow(rgb, extent=ext, origin="lower")

# 848 m 网格
k = 0
while X0 + k * 848 <= X1:
    ax.axvline(X0 + k * 848, color="#ffffff", lw=0.35, alpha=0.28)
    k += 1
k = 0
while Y0 + k * 848 <= Y1:
    ax.axhline(Y0 + k * 848, color="#ffffff", lw=0.35, alpha=0.28)
    k += 1

STYLE = {
    "大城市": dict(marker="*", s=520, c="#d81b60", ec="white", lw=1.2, z=9),
    "城堡": dict(marker="s", s=170, c="#f57c00", ec="white", lw=0.9, z=8),
    "村庄": dict(marker="o", s=95, c="#2e7d32", ec="white", lw=0.7, z=7),
    "藏身处": dict(marker="^", s=110, c="#6a1b9a", ec="white", lw=0.7, z=7),
    "小剧情": dict(marker="o", s=38, c="#607d8b", ec="white", lw=0.4, z=6),
    "野外点位": dict(marker="x", s=80, c="#1565c0", lw=1.6, z=7),
}
for r in rows:
    st = STYLE[r["tier"]]
    ax.scatter(r["cx"], r["cy"], marker=st["marker"], s=st["s"], c=st["c"],
               edgecolors=st.get("ec", "none"), linewidths=st["lw"], zorder=st["z"], alpha=0.95)

# 标注 9 座城镇（逐个给偏移，避免东海岸挤在一起）
OFF = {
    "圣丹尼斯": (300, 150), "罗兹": (-300, 190), "黑水镇": (-320, 100),
    "瓦伦丁": (130, 170), "草莓镇": (-340, 80), "犰狳镇": (-280, 120),
    "风滚草镇": (-360, 70), "安尼斯堡": (-320, 130), "范霍恩贸易站": (-330, 170),
}
for r in rows:
    if r["category"] in ("大城市", "城镇"):
        dx, dy = OFF.get(r["name_zh"], (150, 120))
        ax.annotate(r["name_zh"], (r["cx"], r["cy"]), xytext=(r["cx"] + dx, r["cy"] + dy),
                    fontsize=8, color="white", zorder=10, ha="center",
                    bbox=dict(boxstyle="round,pad=0.22", fc="#000000", ec="none", alpha=0.62))

legend = [
    Line2D([0], [0], marker="*", color="w", markerfacecolor="#d81b60", markersize=13, label="大城市 (1)"),
    Line2D([0], [0], marker="s", color="w", markerfacecolor="#f57c00", markersize=9, label="城堡档 (5)"),
    Line2D([0], [0], marker="o", color="w", markerfacecolor="#2e7d32", markersize=8, label="村庄档 (24)"),
    Line2D([0], [0], marker="^", color="w", markerfacecolor="#6a1b9a", markersize=9, label="藏身处 (6)"),
    Line2D([0], [0], marker="o", color="w", markerfacecolor="#607d8b", markersize=6, label="小剧情 (6)"),
    Line2D([0], [0], marker="x", color="#1565c0", markersize=8, label="野外点位 (1)"),
]
ax.legend(handles=legend, loc="lower left", framealpha=0.82, fontsize=8, title="档位", title_fontsize=8)

ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1)
ax.set_aspect("equal")
ax.set_xlabel("RDR2 世界 X (m)", color="#333")
ax.set_ylabel("RDR2 世界 Y (m)", color="#333")
ax.set_title("荒野大镖客 2 · 43 个据点分布（白线 = 848 m 场景网格）", fontsize=13, pad=12)
ax.tick_params(labelsize=7, colors="#555")
for sp in ax.spines.values():
    sp.set_color("#888")

out = os.path.join(ROOT, "export/levels/world/settlements_map.png")
fig.tight_layout()
fig.savefig(out, bbox_inches="tight", facecolor="#0d1117")
print("saved", out)
