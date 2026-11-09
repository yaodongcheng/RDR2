# -*- coding: utf-8 -*-
"""RDR2 -> Bannerlord 据点分级 / 场景边界 / 野外扎营单元 —— 方案数据与标注图生成。

输入（只读）：
  D:/BrainMaker/大镖客2解包分析/deliverable/handoff/settlements_world_v2.csv
  D:/BrainMaker/大镖客2解包分析/deliverable/handoff/settlement_scale.csv
  D:/BrainMaker/大镖客2解包分析/deliverable/terrain/on_map/mainland_overlay.png
  D:/BrainMaker/大镖客2解包分析/deliverable/terrain/on_map/meta.json
  D:/BrainMaker/大镖客2解包分析/export/levels/world/zones.json

输出：
  _scratch/settlement_plan/settlements_plan.csv
  _scratch/settlement_plan/wild_anchors.csv
  _scratch/settlement_plan/01_据点分级总图.png
  _scratch/settlement_plan/02_据点场景范围.png
  _scratch/settlement_plan/03_野外扎营分区.png
"""
import csv, json, math, os
from PIL import Image, ImageDraw, ImageFont

RDR2 = r"D:\BrainMaker\大镖客2解包分析"
OUT = os.path.join(RDR2, "_scratch", "settlement_plan")
os.makedirs(OUT, exist_ok=True)

# ---------- 基础数据 ----------
def read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

sett = read_csv(os.path.join(RDR2, "deliverable/handoff/settlements_world_v2.csv"))
scale = {r["code"]: r for r in read_csv(os.path.join(RDR2, "deliverable/handoff/settlement_scale.csv"))}
zones = json.load(open(os.path.join(RDR2, "export/levels/world/zones.json"), encoding="utf-8"))["zones"]
meta = json.load(open(os.path.join(RDR2, "deliverable/terrain/on_map/meta.json"), encoding="utf-8"))["mainland"]

def f(x):
    try:
        return float(x)
    except Exception:
        return 0.0

def sw(r):
    return f(r.get("size_w_m", r.get("size_w", 0)))

def sd(r):
    return f(r.get("size_d_m", r.get("size_d", 0)))

# 44 个上地图据点（瓜玛岛 2 个除外）
MAIN = [r for r in sett if r["code"] not in ("agu", "gua")]

# 三个大型庄园/工厂按城市级预算，但层级仍是 castle
CITY_BUDGET_CASTLES = {"cor", "cal", "bra"}

TIER = {}
for r in MAIN:
    t = r["btype"]
    if t == "town":
        TIER[r["code"]] = "city"
    elif t == "castle":
        TIER[r["code"]] = "castle"
    else:
        TIER[r["code"]] = "village"

def snap128(v):
    return int(math.ceil(v / 128.0) * 128)

def scene_T(r):
    code, t = r["code"], r["btype"]
    w, d = sw(r), sd(r)
    if code == "sdn":
        return 1536
    if t == "town":
        return max(768, min(1536, snap128(max(w, d) + 2 * 180)))
    if t == "castle":
        if code in CITY_BUDGET_CASTLES:
            return max(768, min(1024, snap128(max(w, d) + 2 * 180)))
        return 640
    if t == "village":
        return 512
    if t == "camp":
        return 512
    if t == "poi":
        return 512
    if t == "hideout":
        return 384
    return 384

def backdrop_R(r):
    code, t = r["code"], r["btype"]
    if code == "sdn":
        return 3500
    if t == "town" or code in CITY_BUDGET_CASTLES:
        return 3000 if t == "town" else 2000
    if t == "castle":
        return 1800
    if t == "village":
        return 1100
    if t == "camp":
        return 900
    if t == "poi":
        return 800
    if t == "hideout":
        return 900
    return 900

# ---------- 野外单元：1,800m 六边形网格 ----------
X0, X1, Y0, Y1 = -6844.0, 3924.0, -4800.0, 3224.0
SPACING = 1800.0
HEX_R = SPACING / math.sqrt(3.0)          # 1,039 m
WILD_T = 2304                            # 场景边长；半宽 1,152 > 1,039
WILD_R_OUT = 4000

# 用解包水面掩码判断单元是否以陆地为主
import numpy as np
from PIL import Image as PILImage
wm = np.array(PILImage.open(os.path.join(RDR2, "deliverable/terrain/water_mask.png")))
WM_H, WM_W = wm.shape
M_PER_PX = 4.0

def world_to_mask(x, y):
    c = int(round((x - X0) / M_PER_PX))
    r = int(round((Y1 - y) / M_PER_PX))
    return c, r

def land_frac(x, y, radius_m=200):
    c, r = world_to_mask(x, y)
    rad = int(radius_m / M_PER_PX)
    c0, c1 = max(0, c - rad), min(WM_W, c + rad)
    r0, r1 = max(0, r - rad), min(WM_H, r + rad)
    if c1 <= c0 or r1 <= r0:
        return 0.0
    return float((wm[r0:r1, c0:c1] < 128).mean())

def hex_centers():
    dx = SPACING
    dy = 1.5 * HEX_R
    ncol = int((X1 - X0) // dx) + 2
    nrow = int((Y1 - Y0) // dy) + 2
    pts = []
    for j in range(nrow):
        for i in range(ncol):
            x = X0 + (i + 0.5) * dx + (dx / 2 if j % 2 else 0)
            y = Y1 - (j + 0.5) * dy
            if X0 <= x <= X1 and Y0 <= y <= Y1:
                pts.append((i, j, x, y))
    return pts

def in_scene(x, y, cx, cy, T):
    return abs(x - cx) <= T / 2 and abs(y - cy) <= T / 2

wild = []
for i, j, x, y in hex_centers():
    if land_frac(x, y) < 0.02:
        continue
    # 跳过完全落在据点场景内的单元中心
    host = None
    for r in MAIN:
        # 只有城市/城堡/藏身处会从野外网格里挖掉一块；小村庄场景不参与网格划分
        if r["btype"] not in ("town", "castle", "hideout"):
            continue
        T = scene_T(r)
        if in_scene(x, y, f(r["world_x"]), f(r["world_y"]), T):
            host = r["code"]
            break
    if host:
        continue
    wild.append(dict(wid="wild_%02d" % (len(wild) + 1), i=i, j=j, x=round(x, 1), y=round(y, 1),
                     land=round(land_frac(x, y), 3)))

# ---------- 归属：小据点优先并进已有场景 ----------
# 先建大场景（city/castle）列表
big = [r for r in MAIN if r["btype"] in ("town", "castle")]
big_info = [(r["code"], f(r["world_x"]), f(r["world_y"]), scene_T(r)) for r in big]

rows = []
for r in MAIN:
    code = r["code"]
    cx, cy = f(r["world_x"]), f(r["world_y"])
    tier = TIER[code]
    T = scene_T(r)
    R = backdrop_R(r)
    embed = ""
    # 城市/城堡永远独立成场景；藏身处也必须独立（骑砍 Hideout 组件要专用场景）
    if tier == "village" and r["btype"] != "hideout":
        # ① 优先并进野外单元（保证“村外扎营能走进村”）
        for w in wild:
            if in_scene(cx, cy, w["x"], w["y"], WILD_T):
                embed = w["wid"]
                break
        # ② 野外单元没盖住的，再并进大据点的“实际可走圈”（建成区半径 + 100 m），
        #    不是并进整个场景方框——否则城市方框四角的独立村庄会被吞进城里
        if not embed:
            for bcode, bx, by, bT in big_info:
                if bcode == code:
                    continue
                br = max(sw(next(x for x in MAIN if x["code"] == bcode)),
                         sd(next(x for x in MAIN if x["code"] == bcode))) / 2 + 100
                if abs(cx - bx) <= br and abs(cy - by) <= br:
                    embed = bcode
                    break
    if embed:
        T_eff = 0
        R_eff = 0
    else:
        T_eff = T
        R_eff = R
    rows.append(dict(
        code=code, name_zh=r["name_zh"], name_en=r["name_en"], tier=tier, rdr2_type=r["btype"],
        world_x=cx, world_y=cy, size_w=sw(r), size_d=sd(r),
        scene_class=("city" if r["btype"] == "town" else "castle" if r["btype"] == "castle" else "village"),
        scene_T_m=T_eff if not embed else T,
        backdrop_R_m=R_eff,
        embed_into=embed,
        n_inst=f(scale.get(code, {}).get("n_inst", 0)),
        n_bld=f(scale.get(code, {}).get("n_bld", 0)),
        bld_tris=f(scale.get(code, {}).get("bld_tris", 0)),
    ))

# ---------- 输出 CSV ----------
cols = ["code", "name_zh", "name_en", "tier", "rdr2_type", "scene_class", "world_x", "world_y",
        "size_w", "size_d", "scene_T_m", "backdrop_R_m", "embed_into", "n_inst", "n_bld", "bld_tris"]
with open(os.path.join(OUT, "settlements_plan.csv"), "w", encoding="utf-8-sig", newline="") as fh:
    wr = csv.DictWriter(fh, fieldnames=cols)
    wr.writeheader()
    wr.writerows(rows)

with open(os.path.join(OUT, "wild_anchors.csv"), "w", encoding="utf-8-sig", newline="") as fh:
    wr = csv.DictWriter(fh, fieldnames=["wid", "i", "j", "x", "y", "land"])
    wr.writeheader()
    wr.writerows(wild)

# ---------- 统计 ----------
from collections import Counter
tc = Counter(r["tier"] for r in rows)
sc = Counter(r["rdr2_type"] for r in rows)
print("tiers", dict(tc), "types", dict(sc), "wild", len(wild))
print("sum playable scene area km2", round(sum((r["scene_T_m"] ** 2) / 1e6 for r in rows if not r["embed_into"]), 2))
print("embedded", sum(1 for r in rows if r["embed_into"]))

# ---------- 画图 ----------
overlay = Image.open(os.path.join(RDR2, "deliverable/terrain/on_map/mainland_overlay.png")).convert("RGBA")
OW, OH = overlay.size
BOX_L, BOX_T = 146, 388
BOX_W, BOX_H = 4804 - 146, 3851 - 388
MX0, MX1 = meta["world"]["x0"], meta["world"]["x1"]
MY0, MY1 = meta["world"]["y0"], meta["world"]["y1"]

def w2p(x, y):
    px = BOX_L + (x - MX0) / (MX1 - MX0) * BOX_W
    py = BOX_T + (MY1 - y) / (MY1 - MY0) * BOX_H
    return px, py

FONT = r"C:\Windows\Fonts\msyh.ttc"
def font(size, bold=False):
    try:
        return ImageFont.truetype(FONT, size)
    except Exception:
        return ImageFont.load_default()

F_TITLE = font(56, True)
F_LEG = font(28)
F_CITY = font(34, True)
F_CASTLE = font(28, True)
F_VILL = font(23)
F_SMALL = font(20)

CITY_C = (255, 205, 60)
CASTLE_C = (95, 175, 255)
VILL_C = (110, 220, 120)
HOST_C = (255, 120, 200)
INK = (30, 24, 18)
PAPER = (250, 246, 236)

def text_with_halo(d, xy, s, fnt, fill, halo=(255, 255, 255), w=3):
    x, y = xy
    for dx in (-w, 0, w):
        for dy in (-w, 0, w):
            d.text((x + dx, y + dy), s, font=fnt, fill=halo)
    d.text(xy, s, font=fnt, fill=fill)

def dashed_circle(d, cx, cy, r, color, width=3, dash=18, gap=12):
    n = max(1, int(2 * math.pi * r / (dash + gap)))
    for k in range(n):
        a0 = 360.0 * k / n
        a1 = a0 + 360.0 * dash / (dash + gap) / n * 1.0
        # PIL arc angles: degrees, clockwise from 3 o'clock
        d.arc([cx - r, cy - r, cx + r, cy + r], a0, a0 + 360.0 * dash / (dash + gap) / n,
              fill=color, width=width)

def marker(d, x, y, tier, r=10, embedded=False):
    color = CITY_C if tier == "city" else CASTLE_C if tier == "castle" else VILL_C
    if tier == "city":
        # 星形
        pts = []
        for k in range(10):
            ang = -math.pi / 2 + k * math.pi / 5
            rad = r * (1.0 if k % 2 == 0 else 0.45)
            pts.append((x + rad * math.cos(ang), y + rad * math.sin(ang)))
        d.polygon(pts, fill=color, outline=INK)
    elif tier == "castle":
        d.polygon([(x, y - r), (x + r, y), (x, y + r), (x - r, y)], fill=color, outline=INK)
    else:
        d.ellipse([x - r * 0.75, y - r * 0.75, x + r * 0.75, y + r * 0.75], fill=color, outline=INK)
    if embedded:
        d.ellipse([x - r - 5, y - r - 5, x + r + 5, y + r + 5], outline=HOST_C, width=3)

# 图 1：分级总图
img = overlay.copy()
layer = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
d = ImageDraw.Draw(layer, "RGBA")
# 标题带
d.rectangle([0, 0, OW, 96], fill=(28, 24, 18, 235))
text_with_halo(d, (28, 18), "荒野大镖客 2 → 骑砍 2 · 据点分级（44 个上地图据点）", F_TITLE, (250, 246, 236), halo=(28, 24, 18))
# 图例
lx, ly = 60, 130
d.rectangle([lx - 16, ly - 12, lx + 560, ly + 150], fill=(250, 246, 236, 225), outline=INK, width=2)
d.ellipse([lx, ly + 8, lx + 26, ly + 34], fill=CITY_C, outline=INK, width=2)
text_with_halo(d, (lx + 40, ly), "城市 City（9）", font(30, True), INK)
d.polygon([(lx + 13, ly + 50), (lx + 26, ly + 63), (lx + 13, ly + 76), (lx, ly + 63)], fill=CASTLE_C, outline=INK)
text_with_halo(d, (lx + 40, ly + 44), "城堡 Castle（11）", font(30, True), INK)
d.ellipse([lx + 3, ly + 90, lx + 23, ly + 110], fill=VILL_C, outline=INK, width=2)
text_with_halo(d, (lx + 40, ly + 86), "村庄 Village（24：含营地/点位/藏身处）", font(30, True), INK)
text_with_halo(d, (lx + 40, ly + 120), "粉圈 = 并进附近场景（不单独开场景）", F_LEG, HOST_C)

# 标注：避免重叠
placed = []
def put_label(x, y, s, fnt, color, prefer="right", tier="village"):
    bbox = d.textbbox((0, 0), s, font=fnt)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    cands = []
    if prefer == "right":
        cands = [(x + 22, y - th / 2), (x - 22 - tw, y - th / 2), (x - tw / 2, y - th - 18), (x - tw / 2, y + 18)]
    else:
        cands = [(x - 22 - tw, y - th / 2), (x + 22, y - th / 2), (x - tw / 2, y - th - 18), (x - tw / 2, y + 18)]
    for tx, ty in cands:
        rect = (tx - 3, ty - 2, tx + tw + 3, ty + th + 2)
        if rect[0] < BOX_L or rect[2] > BOX_L + BOX_W or rect[1] < 100 or rect[3] > BOX_T + BOX_H:
            continue
        if all(not (rect[0] < r[2] and rect[2] > r[0] and rect[1] < r[3] and rect[3] > r[1]) for r in placed):
            placed.append(rect)
            text_with_halo(d, (tx, ty), s, fnt, color)
            return
    # 都冲突就画在右侧
    text_with_halo(d, (x + 22, y - th / 2), s, fnt, color)

for r in sorted(rows, key=lambda z: (z["tier"] != "city", z["tier"] != "castle", z["code"])):
    x, y = w2p(r["world_x"], r["world_y"])
    embedded = bool(r["embed_into"])
    marker(d, x, y, r["tier"], r=12 if r["tier"] != "village" else 8, embedded=embedded)
    fnt = F_CITY if r["tier"] == "city" else F_CASTLE if r["tier"] == "castle" else F_VILL
    color = INK
    put_label(x, y, r["name_zh"], fnt, color, prefer="right", tier=r["tier"])

# 图 2：场景范围（P / T / 矩形远景外框）
P_DATA = json.load(open(os.path.join(OUT, "settlements_p.json"), encoding="utf-8")) if os.path.exists(os.path.join(OUT, "settlements_p.json")) else {}
img2 = overlay.copy()
layer2 = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
d2 = ImageDraw.Draw(layer2, "RGBA")
d2.rectangle([0, 0, OW, 96], fill=(28, 24, 18, 235))
text_with_halo(d2, (28, 18), "据点场景范围：橙 = 可走 P · 细虚线 = 地形 T · 蓝虚线方框 = 远景外框", F_TITLE, (250, 246, 236), halo=(28, 24, 18))
lx, ly = 60, 130
d2.rectangle([lx - 16, ly - 12, lx + 980, ly + 150], fill=(250, 246, 236, 225), outline=INK, width=2)
d2.rectangle([lx, ly + 8, lx + 34, ly + 34], fill=(217, 119, 42, 80), outline=(217, 119, 42, 255), width=3)
text_with_halo(d2, (lx + 46, ly + 2), "可走 P（建成区 + 边距 ∩ 领地线）", font(28, True), INK)
d2.rectangle([lx, ly + 48, lx + 34, ly + 74], outline=(120, 100, 80), width=2)
text_with_halo(d2, (lx + 46, ly + 42), "地形 T（只表示渲染范围，不是全部可走）", font(28, True), INK)
d2.rectangle([lx, ly + 88, lx + 34, ly + 114], outline=(61, 109, 153), width=3)
text_with_halo(d2, (lx + 46, ly + 82), "远景外框（矩形，环宽 W）", font(28, True), INK)
d2.rectangle([lx + 560, ly + 8, lx + 584, ly + 32], fill=CITY_C, outline=INK)
text_with_halo(d2, (lx + 594, ly + 2), "城市", font(28, True), INK)
d2.rectangle([lx + 560, ly + 48, lx + 584, ly + 72], fill=CASTLE_C, outline=INK)
text_with_halo(d2, (lx + 594, ly + 42), "城堡", font(28, True), INK)
d2.rectangle([lx + 560, ly + 88, lx + 584, ly + 112], fill=VILL_C, outline=INK)
text_with_halo(d2, (lx + 594, ly + 82), "村庄", font(28, True), INK)

def dashed_rect(d, box, color, width=2, dash=14, gap=10):
    x0, y0, x1, y1 = [int(v) for v in box]
    step = dash + gap
    for x in range(x0, x1, step):
        d.line([(x, y0), (min(x + dash, x1), y0)], fill=color, width=width)
        d.line([(x, y1), (min(x + dash, x1), y1)], fill=color, width=width)
    for y in range(y0, y1, step):
        d.line([(x0, y), (x0, min(y + dash, y1))], fill=color, width=width)
        d.line([(x1, y), (x1, min(y + dash, y1))], fill=color, width=width)

def put_label_on(dd, x, y, s, fnt, color):
    bbox = dd.textbbox((0, 0), s, font=fnt)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    text_with_halo(dd, (x + 8, y - th - 8), s, fnt, color)

def _W(r):
    t = r["tier"]
    typ = r["rdr2_type"]
    return 1200 if t == "city" else 800 if t == "castle" else 500 if typ == "hideout" else 600

# 先画外层矩形（避免压住 P/T）
for r in rows:
    if r["embed_into"]:
        continue
    x, y = w2p(r["world_x"], r["world_y"])
    T = float(r["scene_T_m"]); W = _W(r); O = T + 2 * W
    ow = O / (MX1 - MX0) * BOX_W; oh = O / (MY1 - MY0) * BOX_H
    dashed_rect(d2, [x - ow / 2, y - oh / 2, x + ow / 2, y + oh / 2], (61, 109, 153, 210), width=3, dash=18, gap=14)

# P + T
for r in rows:
    if r["embed_into"]:
        continue
    x, y = w2p(r["world_x"], r["world_y"])
    T = float(r["scene_T_m"]); tp = T / (MX1 - MX0) * BOX_W
    color = CITY_C if r["tier"] == "city" else CASTLE_C if r["tier"] == "castle" else VILL_C
    pdata = P_DATA.get(r["code"], {})
    for poly in pdata.get("P", []):
        pts = [w2p(px, py) for px, py in poly]
        if len(pts) >= 3:
            d2.polygon(pts, fill=(217, 119, 42, 80), outline=(217, 119, 42, 255))
    dashed_rect(d2, [x - tp / 2, y - tp / 2, x + tp / 2, y + tp / 2], (*color, 220), width=2, dash=10, gap=8)
    d2.ellipse([x - 4, y - 4, x + 4, y + 4], fill=INK)
    if r["tier"] in ("city", "castle"):
        put_label_on(d2, x, y, r["name_zh"], F_CASTLE, INK)

# 图 2 的标签避让已在上方 put_label_on 中实现

# 图 3：野外扎营分区
img3 = overlay.copy()
layer3 = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
d3 = ImageDraw.Draw(layer3, "RGBA")
d3.rectangle([0, 0, OW, 96], fill=(28, 24, 18, 235))
text_with_halo(d3, (28, 18), "野外扎营：1,800 m 六边形单元 · 25 个锚点 · 每单元 2,304 m 场景", F_TITLE, (250, 246, 236), halo=(28, 24, 18))
lx, ly = 60, 130
d3.rectangle([lx - 16, ly - 12, lx + 860, ly + 120], fill=(250, 246, 236, 225), outline=INK, width=2)
d3.polygon([(lx + 20, ly + 8), (lx + 40, ly + 20), (lx + 40, ly + 44), (lx + 20, ly + 56), (lx, ly + 44), (lx, ly + 20)], outline=(60, 140, 220), width=4)
text_with_halo(d3, (lx + 56, ly + 2), "野外扎营单元（六边形，1800 m）", font(28, True), INK)
d3.rectangle([lx + 420, ly + 8, lx + 454, ly + 42], outline=(240, 120, 80), width=4)
text_with_halo(d3, (lx + 466, ly + 2), "单元场景 2,304 m（覆盖整个六边形）", font(28, True), INK)
d3.ellipse([lx + 20, ly + 76, lx + 40, ly + 96], fill=(240, 120, 80), outline=INK)
text_with_halo(d3, (lx + 56, ly + 70), "锚点（场景中心）", font(28, True), INK)
text_with_halo(d3, (lx + 420, ly + 70), "据点场景不参与分块", font(28, True), INK)

# 据点场景（半透明填充）
for r in rows:
    if r["embed_into"]:
        continue
    x, y = w2p(r["world_x"], r["world_y"])
    tp = r["scene_T_m"] / (MX1 - MX0) * BOX_W
    color = CITY_C if r["tier"] == "city" else CASTLE_C if r["tier"] == "castle" else VILL_C
    d3.rectangle([x - tp / 2, y - tp / 2, x + tp / 2, y + tp / 2], fill=(*color, 45), outline=(*color, 220), width=4)

# 六边形
for w in wild:
    x, y = w2p(w["x"], w["y"])
    rp = HEX_R / (MX1 - MX0) * BOX_W
    pts = []
    for k in range(6):
        ang = math.radians(60 * k + 30)  # pointy-top
        pts.append((x + rp * math.cos(ang), y + rp * math.sin(ang)))
    d3.polygon(pts, outline=(60, 140, 220, 220), width=4, fill=(60, 140, 220, 10))
    d3.ellipse([x - 8, y - 8, x + 8, y + 8], fill=(240, 120, 80), outline=INK, width=2)
    text_with_halo(d3, (x + 12, y - 30), w["wid"].replace("wild_", "W"), font(22, True), (180, 40, 20))

# 图 1 保存
Image.alpha_composite(img, layer).convert("RGB").save(os.path.join(OUT, "01_据点分级总图.png"))
Image.alpha_composite(img2, layer2).convert("RGB").save(os.path.join(OUT, "02_据点场景范围.png"))
Image.alpha_composite(img3, layer3).convert("RGB").save(os.path.join(OUT, "03_野外扎营分区.png"))
print("saved images to", OUT)
