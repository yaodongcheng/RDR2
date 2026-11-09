# -*- coding: utf-8 -*-
"""圣丹尼斯场景特写：1,536m 场景方框 + 官方 TOWN 多边形 + 周边小据点。"""
import json, os
from PIL import Image, ImageDraw, ImageFont

RDR2 = r"D:\BrainMaker\大镖客2解包分析"
OUT = os.path.join(RDR2, "_scratch", "settlement_plan")
meta = json.load(open(os.path.join(RDR2, "deliverable/terrain/on_map/meta.json"), encoding="utf-8"))["mainland"]
zones = json.load(open(os.path.join(RDR2, "export/levels/world/zones.json"), encoding="utf-8"))["zones"]

BOX_L, BOX_T = 146, 388
BOX_W, BOX_H = 4804 - 146, 3851 - 388
MX0, MX1 = meta["world"]["x0"], meta["world"]["x1"]
MY0, MY1 = meta["world"]["y0"], meta["world"]["y1"]

def w2p(x, y):
    return (BOX_L + (x - MX0) / (MX1 - MX0) * BOX_W,
            BOX_T + (MY1 - y) / (MY1 - MY0) * BOX_H)

overlay = Image.open(os.path.join(RDR2, "deliverable/terrain/on_map/mainland_overlay.png")).convert("RGBA")

# 裁剪：世界 x 1450..3650, y -2300..-50
x0, x1, y0, y1 = 1450, 3650, -2300, -50
p0 = w2p(x0, y1)   # 左上
p1 = w2p(x1, y0)   # 右下
crop = overlay.crop((int(p0[0]), int(p0[1]), int(p1[0]), int(p1[1])))
# 放大到 1800 宽
scale = 1800 / crop.width
crop = crop.resize((1800, int(crop.height * scale)), Image.LANCZOS)

layer = Image.new("RGBA", crop.size, (0, 0, 0, 0))
d = ImageDraw.Draw(layer, "RGBA")

def P(x, y):
    px, py = w2p(x, y)
    return ((px - p0[0]) * scale, (py - p0[1]) * scale)

FONT = r"C:\Windows\Fonts\msyh.ttc"
def font(sz):
    return ImageFont.truetype(FONT, sz)

def halo(xy, s, sz, fill=(20, 16, 12), halo_c=(255, 255, 255), w=3):
    f = font(sz)
    for dx in (-w, 0, w):
        for dy in (-w, 0, w):
            d.text((xy[0] + dx, xy[1] + dy), s, font=f, fill=halo_c)
    d.text(xy, s, font=f, fill=fill)

# 1,536 场景方框
cx, cy = 2554.5, -1150.5
T = 1536
a = P(cx - T / 2, cy + T / 2)
b = P(cx + T / 2, cy - T / 2)
d.rectangle([a[0], a[1], b[0], b[1]], outline=(255, 205, 60, 255), width=5)
halo((a[0] + 8, a[1] + 6), "圣丹尼斯场景 1536 × 1536 m", 30, (120, 80, 0))

# 官方 TOWN 多边形
for z in zones:
    if z["type"] != "TOWN":
        continue
    for poly in z["polygons"]:
        pts = [P(px, py) for px, py in poly]
        if len(pts) >= 3:
            d.polygon(pts, outline=(255, 90, 60, 220), width=3)
    if z["name"] == "StDenis":
        bx, by = P(z["cx"], z["cy"])
        halo((bx + 10, by + 10), "官方建成区 862 × 955 m", 28, (180, 30, 20))

# 周边小据点
near = [("拉格拉斯", 2065.8, -699.5), ("奥兰治种植园", 2028.1, -835.8),
        ("谢迪贝莱", 1896.2, -1818.9), ("拉凯", 2274.6, -760.4),
        ("卡利加种植园", 1807.7, -1354.9), ("布雷斯韦特庄园", 1095.8, -1730.5),
        ("罗兹", 1217.5, -1256.3)]
for name, x, y in near:
    px, py = P(x, y)
    if 0 <= px < crop.width and 0 <= py < crop.height:
        d.ellipse([px - 7, py - 7, px + 7, py + 7], fill=(110, 220, 120), outline=(20, 16, 12), width=2)
        halo((px + 10, py - 12), name, 26, (20, 60, 20))

out = Image.alpha_composite(crop, layer).convert("RGB")
out.save(os.path.join(OUT, "04_圣丹尼斯特写.png"))
print("saved", out.size)
