# -*- coding: utf-8 -*-
"""生成《据点场景范围》交互页 + 裁好的地图底图。

输入：
  D:/BrainMaker/大镖客2解包分析/_scratch/settlement_plan/settlements_plan.csv
  D:/BrainMaker/大镖客2解包分析/_scratch/settlement_plan/wild_anchors.csv
  D:/BrainMaker/大镖客2解包分析/deliverable/terrain/on_map/mainland_overlay.png
  D:/BrainMaker/大镖客2解包分析/deliverable/terrain/on_map/meta.json

输出：
  h:/.../Modules/RDR2/Source/docs/世界与地编/settlement_viewer.html
  h:/.../Modules/RDR2/Source/docs/世界与地编/settlement_map_base.jpg
"""
import csv, json, os
from PIL import Image

RDR2 = r"D:\BrainMaker\大镖客2解包分析"
OUTDIR = r"h:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source\docs\世界与地编"
os.makedirs(OUTDIR, exist_ok=True)

# ---------- 数据 ----------
def read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

rows = read_csv(os.path.join(RDR2, "_scratch/settlement_plan/settlements_plan.csv"))
wild = read_csv(os.path.join(RDR2, "_scratch/settlement_plan/wild_anchors.csv"))
P_DATA = json.load(open(os.path.join(RDR2, "_scratch/settlement_plan/settlements_p.json"), encoding="utf-8"))

def f(x):
    try:
        return float(x)
    except Exception:
        return 0.0

settlements = []
for r in rows:
    p = P_DATA.get(r["code"], {})
    _tier = r["tier"]
    _type = r["rdr2_type"]
    _T = int(f(r["scene_T_m"]))
    _W = 1200 if _tier == "city" else 800 if _tier == "castle" else 500 if _type == "hideout" else 600
    settlements.append({
        "code": r["code"],
        "name": r["name_zh"],
        "tier": _tier,
        "type": _type,
        "x": round(f(r["world_x"]), 1),
        "y": round(f(r["world_y"]), 1),
        "T": _T,
        "W": _W,
        "O": _T + 2 * _W,
        "R": int(f(r["backdrop_R_m"])),
        "host": r["embed_into"] or "",
        "w": int(f(r["size_w"])),
        "d": int(f(r["size_d"])),
        "inst": int(f(r["n_inst"])),
        "bld": int(f(r["n_bld"])),
        "tris": int(f(r["bld_tris"])),
        "P": p.get("P", []),
        "cell": p.get("cell", []),
        "P_area": p.get("P_area_km2", 0),
        "P_max": p.get("P_max_m", 0),
    })

# 小据点并进哪个野外单元
by_host = {}
for s in settlements:
    if s["host"]:
        by_host.setdefault(s["host"], []).append(s["code"])

wilds = []
for w in wild:
    wid = w["wid"]
    wilds.append({
        "id": wid,
        "x": round(f(w["x"]), 1),
        "y": round(f(w["y"]), 1),
        "land": round(f(w["land"]), 3),
        "T": 2304,
        "W": 1000,
        "O": 4304,
        "R": 4000,
        "sett": by_host.get(wid, []),
    })

meta = json.load(open(os.path.join(RDR2, "deliverable/terrain/on_map/meta.json"), encoding="utf-8"))["mainland"]["world"]
proj = {"x0": meta["x0"], "x1": meta["x1"], "y0": meta["y0"], "y1": meta["y1"]}

# ---------- 底图：裁到地图框，缩到 2500 宽 ----------
BOX_L, BOX_T, BOX_R, BOX_B = 146, 388, 4804, 3851
overlay = Image.open(os.path.join(RDR2, "deliverable/terrain/on_map/mainland_overlay.png")).convert("RGB")
crop = overlay.crop((BOX_L, BOX_T, BOX_R, BOX_B))  # 4658 x 3463
MAP_W = 2500
MAP_H = round(crop.height * MAP_W / crop.width)  # 1859
crop = crop.resize((MAP_W, MAP_H), Image.LANCZOS)
map_path = os.path.join(OUTDIR, "settlement_map_base.jpg")
crop.save(map_path, quality=90, optimize=True, progressive=True)
print("map", crop.size, round(os.path.getsize(map_path) / 1024 / 1024, 2), "MB")

# ---------- HTML ----------
HTML = r"""<title>据点场景范围</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;600;700&family=Noto+Serif+SC:wght@600;700&display=swap">
<style>
:root {
  --bg: #efe9dc;
  --panel: #fbf7ee;
  --panel-2: #f6f0e4;
  --ink: #241c14;
  --muted: #756654;
  --line: #d9ccb7;
  --line-strong: #b9a98f;
  --accent: #b4552d;
  --accent-ink: #fff8ef;
  --city: #b8861f;
  --castle: #3d6d99;
  --village: #4f8456;
  --walk: #d9772a;
  --backdrop: #3d6d99;
  --wild: #2f7f72;
  --walk-fill: rgba(217,119,42,.10);
  --backdrop-fill: rgba(61,109,153,.035);
  --walk-fill-all: rgba(217,119,42,.020);
  --backdrop-fill-all: rgba(61,109,153,.010);
  --map-ink: #241c14;
  --map-halo: #fffaf0;
  --shadow: 0 10px 28px rgba(45,30,15,.14);
  --radius: 14px;
  --sans: "Noto Sans SC", "Microsoft YaHei", system-ui, -apple-system, sans-serif;
  --serif: "Noto Serif SC", "Songti SC", "SimSun", serif;
  --mono: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #14110d;
    --panel: #1e1913;
    --panel-2: #251f17;
    --ink: #f0e6d6;
    --muted: #a89880;
    --line: #3a2f24;
    --line-strong: #57483a;
    --accent: #e08a4c;
    --accent-ink: #1a120a;
    --city: #d9a83a;
    --castle: #6fa3d1;
    --village: #79b87f;
    --walk: #ef9a52;
    --backdrop: #6fa3d1;
    --wild: #5fb3a3;
    --shadow: 0 10px 28px rgba(0,0,0,.38);
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #14110d;
  --panel: #1e1913;
  --panel-2: #251f17;
  --ink: #f0e6d6;
  --muted: #a89880;
  --line: #3a2f24;
  --line-strong: #57483a;
  --accent: #e08a4c;
  --accent-ink: #1a120a;
  --city: #d9a83a;
  --castle: #6fa3d1;
  --village: #79b87f;
  --walk: #ef9a52;
  --backdrop: #6fa3d1;
  --wild: #5fb3a3;
  --shadow: 0 10px 28px rgba(0,0,0,.38);
  color-scheme: dark;
}
* { box-sizing: border-box; }
html, body { height: 100%; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: var(--sans);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
button { font: inherit; }
.app {
  display: grid;
  grid-template-columns: 390px minmax(0, 1fr);
  height: 100%;
  min-height: 0;
}
.sidebar {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--panel);
  border-right: 1px solid var(--line);
}
.sidebar-head {
  padding: 20px 20px 12px;
  border-bottom: 1px solid var(--line);
}
.eyebrow {
  font-size: 11px;
  letter-spacing: .13em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 600;
}
h1 {
  font-family: var(--serif);
  font-size: 25px;
  line-height: 1.2;
  margin: 4px 0 2px;
  letter-spacing: .02em;
  text-wrap: balance;
}
.sub {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  padding: 11px 20px 13px;
  border-bottom: 1px solid var(--line);
  font-size: 12px;
  color: var(--muted);
}
.legend span { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
.sw { width: 11px; height: 11px; border-radius: 3px; display: inline-block; }
.sw.city { background: var(--city); }
.sw.castle { background: var(--castle); }
.sw.village { background: var(--village); border-radius: 50%; }
.sw.walk { background: var(--walk); border-radius: 2px; }
.sw.ring { background: transparent; border: 1.5px dashed var(--backdrop); border-radius: 2px; }
.sw.wild { background: transparent; border: 1.5px dashed var(--wild); border-radius: 2px; }
.sw.ghost { background: transparent; border: 1.5px dashed var(--walk); border-radius: 2px; }
.sw.cell { background: transparent; border: 1.5px dashed var(--muted); border-radius: 50%; }
.controls-row {
  display: flex;
  gap: 8px;
  padding: 12px 20px 8px;
  flex-wrap: wrap;
}
.chip {
  appearance: none;
  border: 1px solid var(--line);
  background: var(--panel);
  color: var(--ink);
  border-radius: 999px;
  padding: 5px 11px;
  font-size: 12px;
  cursor: pointer;
  transition: background .15s, border-color .15s, color .15s;
}
.chip:hover { border-color: var(--line-strong); }
.chip.active { background: var(--ink); color: var(--panel); border-color: var(--ink); }
.search-wrap { padding: 0 20px 12px; }
input[type="search"] {
  width: 100%;
  border: 1px solid var(--line);
  background: var(--panel-2);
  color: var(--ink);
  border-radius: 10px;
  padding: 9px 12px;
  font: inherit;
  outline: none;
}
input[type="search"]:focus { border-color: var(--accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 18%, transparent); }
.detail {
  padding: 16px 20px 15px;
  background: var(--panel-2);
  border-bottom: 1px solid var(--line);
}
.detail-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.detail h2 {
  font-family: var(--serif);
  font-size: 23px;
  line-height: 1.2;
  margin: 2px 0 0;
  letter-spacing: .02em;
}
.badge {
  flex: 0 0 auto;
  font-size: 11px;
  font-weight: 700;
  color: var(--accent-ink);
  background: var(--badge, var(--accent));
  border-radius: 999px;
  padding: 4px 9px;
  letter-spacing: .04em;
}
.stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}
.stat {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 8px 9px;
  min-width: 0;
}
.stat span {
  display: block;
  font-size: 10px;
  color: var(--muted);
  letter-spacing: .06em;
  white-space: nowrap;
}
.stat b {
  display: block;
  font-size: 21px;
  line-height: 1.15;
  font-variant-numeric: tabular-nums;
  letter-spacing: -.01em;
}
.stat small { font-size: 11px; font-weight: 500; color: var(--muted); }
.detail-body { display: grid; grid-template-columns: 132px minmax(0, 1fr); gap: 12px; align-items: center; margin-top: 12px; }
.mini-svg { width: 132px; height: 132px; display: block; }
.mini-o { fill: var(--backdrop-fill); stroke: var(--backdrop); stroke-width: 1.5; stroke-dasharray: 5 4; }
.mini-t { fill: none; stroke: var(--muted); stroke-width: 1.2; stroke-dasharray: 4 3; }
.mini-p { fill: rgba(217,119,42,.28); stroke: var(--walk); stroke-width: 1.4; }
.rows { display: grid; gap: 5px; min-width: 0; }
.rows div { display: flex; justify-content: space-between; gap: 10px; font-size: 12px; }
.rows span { color: var(--muted); }
.rows b { font-weight: 600; font-variant-numeric: tabular-nums; text-align: right; }
.note {
  margin: 10px 0 0;
  font-size: 11.5px;
  color: var(--muted);
  line-height: 1.45;
}
.note b { color: var(--ink); }
.chips { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 6px; }
.chiplet {
  font-size: 11px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 2px 8px;
  color: var(--ink);
}
.list {
  flex: 1;
  overflow: auto;
  padding: 8px 10px 18px;
  min-height: 0;
}
.group-head {
  display: flex;
  justify-content: space-between;
  padding: 10px 10px 5px;
  font-size: 11px;
  letter-spacing: .10em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 700;
}
.group-head span { font-variant-numeric: tabular-nums; }
.row {
  display: flex;
  align-items: center;
  gap: 9px;
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--ink);
  text-align: left;
  padding: 7px 10px;
  border-radius: 9px;
  cursor: pointer;
  font-size: 13px;
}
.row:hover { background: var(--panel-2); }
.row.active { background: color-mix(in srgb, var(--accent) 13%, var(--panel)); outline: 1px solid color-mix(in srgb, var(--accent) 40%, var(--line)); }
.dot { width: 8px; height: 8px; border-radius: 50%; flex: 0 0 auto; }
.row .name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row .meta {
  margin-left: auto;
  flex: 0 0 auto;
  color: var(--muted);
  font-size: 10.5px;
  font-variant-numeric: tabular-nums;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wild-group { margin-top: 10px; border-top: 1px solid var(--line); padding-top: 6px; }
.wild-group summary {
  cursor: pointer;
  padding: 8px 10px;
  font-size: 11px;
  letter-spacing: .10em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 700;
}
.wild-group summary span { float: right; font-variant-numeric: tabular-nums; }
.wild-list { padding-bottom: 8px; }
.main { position: relative; min-width: 0; overflow: hidden; background: #cbc2b1; }
.map-wrap { position: absolute; inset: 0; }
#map { width: 100%; height: 100%; display: block; touch-action: none; cursor: grab; }
#map.dragging { cursor: grabbing; }
.map-controls {
  position: absolute;
  top: 14px;
  left: 14px;
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
  max-width: calc(100% - 28px);
}
.ctrl {
  appearance: none;
  border: 1px solid var(--line);
  background: color-mix(in srgb, var(--panel) 92%, transparent);
  color: var(--ink);
  border-radius: 9px;
  padding: 7px 10px;
  font-size: 12px;
  cursor: pointer;
  box-shadow: var(--shadow);
  backdrop-filter: blur(6px);
}
.ctrl:hover { border-color: var(--line-strong); }
.ctrl.active { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }
.ctrl.icon { width: 34px; padding: 7px 0; text-align: center; font-weight: 700; }
.scalebar {
  position: absolute;
  left: 16px;
  bottom: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: color-mix(in srgb, var(--panel) 88%, transparent);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 5px 9px;
  font-size: 11px;
  color: var(--muted);
  box-shadow: var(--shadow);
  backdrop-filter: blur(6px);
}
.scalebar i {
  display: block;
  height: 7px;
  border-left: 2px solid var(--ink);
  border-right: 2px solid var(--ink);
  border-bottom: 2px solid var(--ink);
  width: var(--bar, 116px);
}
/* SVG */
.t-shape { fill: none; stroke: var(--walk); stroke-width: 1.4; vector-effect: non-scaling-stroke; }
.t-shape.ghost { stroke-opacity: .55; stroke-dasharray: 5 5; }
.p-shape { fill: rgba(217,119,42,.16); stroke: var(--walk); stroke-width: 2; vector-effect: non-scaling-stroke; }
.p-shape.all { fill: rgba(217,119,42,.05); stroke-opacity: .38; stroke-width: 1; }
.p-shape.host { fill: rgba(217,119,42,.05); stroke-opacity: .5; stroke-dasharray: 6 5; }
.cell-shape { fill: none; stroke: var(--muted); stroke-width: 1.1; stroke-dasharray: 3 6; opacity: .55; vector-effect: non-scaling-stroke; }
.t-shape.all { fill: var(--walk-fill-all); stroke-opacity: .38; stroke-width: 1; stroke-dasharray: 3 5; }
.r-shape { fill: var(--backdrop-fill); stroke: var(--backdrop); stroke-width: 1.6; stroke-dasharray: 6 6; vector-effect: non-scaling-stroke; }
.r-shape.all { fill: var(--backdrop-fill-all); stroke-opacity: .30; stroke-width: 1; stroke-dasharray: 3 7; }
.sel-ring { fill: none; stroke: var(--accent); stroke-width: 2.2; vector-effect: non-scaling-stroke; }
.sel-line { stroke: var(--accent); stroke-width: 1.4; stroke-dasharray: 4 4; vector-effect: non-scaling-stroke; opacity: .7; }
.camp-mark { fill: none; stroke: var(--accent); stroke-width: 2.4; vector-effect: non-scaling-stroke; }
.hex { fill: rgba(47,127,114,.035); stroke: var(--wild); stroke-width: 1.3; stroke-dasharray: 5 5; vector-effect: non-scaling-stroke; opacity: .85; }
.wild-dot { fill: var(--wild); stroke: var(--map-halo); stroke-width: 1.2; vector-effect: non-scaling-stroke; cursor: pointer; }
.wild-label { font-family: var(--sans); font-size: 20px; font-weight: 700; fill: var(--wild); paint-order: stroke; stroke: var(--map-halo); stroke-width: 4px; pointer-events: none; }
.marker { cursor: pointer; }
.marker .hit { fill: transparent; }
.marker-city { fill: var(--city); stroke: var(--map-halo); stroke-width: 1.6; vector-effect: non-scaling-stroke; }
.marker-castle { fill: var(--castle); stroke: var(--map-halo); stroke-width: 1.6; vector-effect: non-scaling-stroke; }
.marker-village { fill: var(--village); stroke: var(--map-halo); stroke-width: 1.4; vector-effect: non-scaling-stroke; }
.map-label {
  font-family: var(--sans);
  font-size: 28px;
  font-weight: 600;
  fill: var(--map-ink);
  paint-order: stroke;
  stroke: var(--map-halo);
  stroke-width: 4.5px;
  stroke-linejoin: round;
  pointer-events: none;
}
.map-label.village { font-size: 22px; font-weight: 500; display: none; }
svg[data-zoom="in"] .map-label.village { display: block; }
.shape-label {
  font-family: var(--sans);
  font-size: 24px;
  font-weight: 600;
  fill: var(--walk);
  paint-order: stroke;
  stroke: var(--map-halo);
  stroke-width: 4px;
  stroke-linejoin: round;
  pointer-events: none;
}
.shape-label.r { fill: var(--backdrop); }
.shape-label.p { fill: var(--walk); }
.shape-label.t { fill: var(--muted); font-size: 20px; font-weight: 500; }
@media (max-width: 860px) {
  .app { grid-template-columns: 1fr; height: auto; }
  .main { order: 1; height: 58vh; height: 58svh; min-height: 360px; }
  .sidebar { order: 2; border-right: 0; border-top: 1px solid var(--line); }
  .list { max-height: none; overflow: visible; }
  .detail-body { grid-template-columns: 110px minmax(0, 1fr); }
  .mini-svg { width: 110px; height: 110px; }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; }
}
</style>

<div class="app">
  <aside class="sidebar">
    <div class="sidebar-head">
      <div class="eyebrow">荒野大镖客 2 → 骑砍 2</div>
      <h1>据点场景范围</h1>
      <p class="sub">44 个上地图据点 · 可走场景与视觉外扩</p>
    </div>
    <div class="legend">
      <span><i class="sw city"></i>城市 9</span>
      <span><i class="sw castle"></i>城堡 11</span>
      <span><i class="sw village"></i>村庄 24</span>
      <span><i class="sw walk"></i>可走 P</span>
      <span><i class="sw ghost"></i>地形 T</span>
      <span><i class="sw ring"></i>远景外框</span>
      <span><i class="sw cell"></i>领地界</span>
    </div>
    <div class="controls-row">
      <button class="chip active" data-tier="all">全部 44</button>
      <button class="chip" data-tier="city">城市 9</button>
      <button class="chip" data-tier="castle">城堡 11</button>
      <button class="chip" data-tier="village">村庄 24</button>
    </div>
    <div class="search-wrap">
      <input id="q" type="search" placeholder="搜名字或编码，如 圣丹尼斯 / sdn" autocomplete="off">
    </div>
    <div id="detail" class="detail"></div>
    <div id="list" class="list"></div>
  </aside>
  <main class="main">
    <div class="map-wrap">
      <svg id="map" viewBox="0 0 2500 1859" role="img" aria-label="RDR2 据点场景范围地图">
        <image href="settlement_map_base.jpg" x="0" y="0" width="2500" height="1859" preserveAspectRatio="none"></image>
        <g id="layer-all"></g>
        <g id="layer-wild"></g>
        <g id="layer-sel"></g>
        <g id="layer-marks"></g>
      </svg>
    </div>
    <div class="map-controls">
      <button class="ctrl active" id="btn-all">全部范围</button>
      <button class="ctrl" id="btn-wild">野外网格</button>
      <button class="ctrl icon" id="btn-zin" title="放大">+</button>
      <button class="ctrl icon" id="btn-zout" title="缩小">−</button>
      <button class="ctrl" id="btn-reset">复位</button>
    </div>
    <div class="scalebar"><i id="scalebar"></i><span>1 km</span></div>
  </main>
</div>

<script>
const SETTLEMENTS = __SETTLEMENTS__;
const WILD = __WILD__;
const PROJ = __PROJ__;
const MAP_W = __MAP_W__, MAP_H = __MAP_H__;
const MX = (PROJ.x1 - PROJ.x0) / MAP_W;
const MY = (PROJ.y1 - PROJ.y0) / MAP_H;
const NS = "http://www.w3.org/2000/svg";

const state = {
  tier: "all",
  q: "",
  selected: "sdn",
  selectedWild: null,
  camp: null,
  showAll: true,
  showWild: false,
  view: { x: 0, y: 0, w: MAP_W, h: MAP_H }
};

const byCode = new Map(SETTLEMENTS.map(s => [s.code, s]));
const wildById = new Map(WILD.map(w => [w.id, w]));
const hostOf = s => s.host ? wildById.get(s.host) : null;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));

function px(x) { return (x - PROJ.x0) / (PROJ.x1 - PROJ.x0) * MAP_W; }
function py(y) { return (PROJ.y1 - y) / (PROJ.y1 - PROJ.y0) * MAP_H; }
function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
function fmt(n) { return Number(n).toLocaleString("en-US"); }
function esc(s) { return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
function tierName(t) { return t === "city" ? "城市" : t === "castle" ? "城堡" : "村庄"; }
function tierColor(t) { return t === "city" ? "var(--city)" : t === "castle" ? "var(--castle)" : "var(--village)"; }
function wildName(id) { return id ? id.replace("wild_", "W") : ""; }

function el(tag, attrs = {}, parent) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}
function svgText(parent, x, y, str, cls, anchor = "start") {
  const t = el("text", { x, y, class: cls, "text-anchor": anchor }, parent);
  t.textContent = str;
  return t;
}
function clear(g) { while (g.firstChild) g.removeChild(g.firstChild); }

/* ---------- 地图视图 ---------- */
function applyView() {
  const svg = $("#map");
  svg.setAttribute("viewBox", `${state.view.x} ${state.view.y} ${state.view.w} ${state.view.h}`);
  svg.dataset.zoom = state.view.w < 1350 ? "in" : "out";
}
function zoomAt(factor, mx, my) {
  const v = state.view;
  const nw = clamp(v.w * factor, 260, MAP_W);
  const nh = nw * MAP_H / MAP_W;
  const rx = mx / nw, ry = my / nh;
  state.view = {
    x: clamp(v.x + mx - rx * nw, 0, MAP_W - nw),
    y: clamp(v.y + my - ry * nh, 0, MAP_H - nh),
    w: nw, h: nh
  };
  applyView();
  renderMarkers();
}
function focusOn(x, y, spanM) {
  const w = clamp(spanM / MX, 420, MAP_W);
  const h = w * MAP_H / MAP_W;
  state.view = {
    x: clamp(px(x) - w / 2, 0, MAP_W - w),
    y: clamp(py(y) - h / 2, 0, MAP_H - h),
    w, h
  };
  applyView();
  renderMarkers();
}

/* ---------- 图形 ---------- */
const LABEL_OFFSETS = {
  sdn: { dx: 18, dy: -12, anchor: "start" },
  lag: { dx: -12, dy: -12, anchor: "end" },
  ora: { dx: -12, dy: 18, anchor: "end" },
  lak: { dx: 14, dy: -10, anchor: "start" },
  sha: { dx: 14, dy: 18, anchor: "start" },
  cal: { dx: -14, dy: 10, anchor: "end" },
  bra: { dx: -14, dy: -10, anchor: "end" },
  rho: { dx: 14, dy: -12, anchor: "start" },
  bla: { dx: 14, dy: -10, anchor: "start" },
  val: { dx: 14, dy: -10, anchor: "start" },
  ann: { dx: 14, dy: -10, anchor: "start" },
  van: { dx: 14, dy: 14, anchor: "start" },
  str: { dx: 14, dy: -10, anchor: "start" },
  tum: { dx: 14, dy: -10, anchor: "start" },
  arm: { dx: 14, dy: -10, anchor: "start" },
  bee: { dx: 14, dy: 16, anchor: "start" },
  hso: { dx: 14, dy: -10, anchor: "start" },
  lon: { dx: -12, dy: -10, anchor: "end" },
  mic: { dx: 14, dy: -10, anchor: "start" },
  sis: { dx: 14, dy: -10, anchor: "start" }
};

function starPath(cx, cy, r) {
  let d = "";
  for (let k = 0; k < 10; k++) {
    const a = -Math.PI / 2 + k * Math.PI / 5;
    const rr = k % 2 ? r * 0.45 : r;
    d += (k ? "L" : "M") + (cx + rr * Math.cos(a)).toFixed(2) + " " + (cy + rr * Math.sin(a)).toFixed(2);
  }
  return d + "Z";
}

function polyPath(polys) {
  let d = "";
  for (const poly of polys || []) {
    if (!poly || poly.length < 3) continue;
    for (let i = 0; i < poly.length; i++) {
      const pt = poly[i];
      d += (i ? "L" : "M") + px(pt[0]).toFixed(1) + " " + py(pt[1]).toFixed(1);
    }
    d += "Z";
  }
  return d;
}
function polyCenter(polys) {
  let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
  for (const poly of polys || []) for (const pt of poly) {
    if (pt[0] < minx) minx = pt[0];
    if (pt[0] > maxx) maxx = pt[0];
    if (pt[1] < miny) miny = pt[1];
    if (pt[1] > maxy) maxy = pt[1];
  }
  if (minx === Infinity) return null;
  return [(minx + maxx) / 2, (miny + maxy) / 2];
}
function drawP(g, s, opts = {}) {
  const d = polyPath(s.P);
  if (!d) return;
  el("path", { d, class: "p-shape" + (opts.all ? " all" : "") }, g);
}
function drawCell(g, s) {
  const d = polyPath(s.cell);
  if (!d) return;
  el("path", { d, class: "cell-shape" }, g);
}
function drawRange(g, s, opts = {}) {
  const host = hostOf(s);
  const T = host ? host.T : (s.T || 1);
  const W = host ? host.W : (s.W || 600);
  const O = host ? host.O : (s.O || (T + 2 * W));
  const cx = host ? px(host.x) : px(s.x);
  const cy = host ? py(host.y) : py(s.y);
  const w = T / MX, h = T / MY;
  const ow = O / MX, oh = O / MY;
  // 据点场景：地形方框 T（幽灵）；并进野外：宿主方框就是可走的野外场景 P
  const squareCls = host ? "p-shape host" : "t-shape ghost" + (opts.all ? " all" : "");
  el("rect", { x: cx - w / 2, y: cy - h / 2, width: w, height: h, rx: 2, class: squareCls }, g);
  el("rect", { x: cx - ow / 2, y: cy - oh / 2, width: ow, height: oh, rx: 2, class: "r-shape" + (opts.all ? " all" : "") }, g);
  if (opts.all) {
    drawP(g, s, { all: true });
    return;
  }
  drawCell(g, s);
  drawP(g, s);
  const pc = polyCenter(s.P) || [s.x, s.y];
  const pcx = px(pc[0]), pcy = py(pc[1]);
  const area = Number(s.P_area || 0).toFixed(2);
  if (host) {
    svgText(g, pcx, pcy - 8, `本村领地 ${area} km²`, "shape-label p", "middle");
    svgText(g, cx - w / 2 + 8, cy - h / 2 + 28, `野外场景 ${T} m`, "shape-label t");
    svgText(g, px(s.x) + 26, py(s.y) + 8, "并进 " + wildName(host.id), "shape-label");
  } else {
    svgText(g, pcx, pcy - 8, `可走 ${area} km²`, "shape-label p", "middle");
    svgText(g, cx - w / 2 + 8, cy - h / 2 + 28, `地形 T ${T} m`, "shape-label t");
  }
  const topY = cy - oh / 2 - 10, botY = cy + oh / 2 + 26;
  const rY = topY > 24 ? topY : (botY < MAP_H - 8 ? botY : cy);
  svgText(g, cx, rY, `远景环宽 W ${W} m · 外框 ${O} m`, "shape-label r", "middle");
}

function renderAll() {
  const g = $("#layer-all");
  clear(g);
  if (!state.showAll) return;
  for (const s of SETTLEMENTS) {
    if (s.host) continue;
    drawP(g, s, { all: true });
  }
}

function renderWild() {
  const g = $("#layer-wild");
  clear(g);
  if (!state.showWild && !state.selectedWild) return;
  for (const w of WILD) {
    const cx = px(w.x), cy = py(w.y);
    const rx = 1039 / MX, ry = 1039 / MY;
    const pts = [];
    for (let k = 0; k < 6; k++) {
      const a = Math.PI / 180 * (60 * k + 30);
      pts.push(`${(cx + rx * Math.cos(a)).toFixed(1)},${(cy + ry * Math.sin(a)).toFixed(1)}`);
    }
    el("polygon", { points: pts.join(" "), class: "hex" }, g);
    const dot = el("circle", { cx, cy, r: 6, class: "wild-dot" }, g);
    dot.addEventListener("click", ev => { ev.stopPropagation(); selectWild(w.id, false); });
    svgText(g, cx + 12, cy - 12, wildName(w.id), "wild-label");
  }
}

function renderSelected() {
  const g = $("#layer-sel");
  clear(g);
  if (state.selectedWild) {
    const w = wildById.get(state.selectedWild);
    if (!w) return;
    const cx = px(w.x), cy = py(w.y);
    const wpx = w.T / MX, hpx = w.T / MY;
    el("rect", { x: cx - wpx / 2, y: cy - hpx / 2, width: wpx, height: hpx, rx: 2, class: "p-shape" }, g);
    el("rect", { x: cx - w.O / MX / 2, y: cy - w.O / MY / 2, width: w.O / MX, height: w.O / MY, rx: 2, class: "r-shape" }, g);
    svgText(g, cx, cy - hpx / 2 + 30, `可走 ${(w.T * w.T / 1e6).toFixed(2)} km²`, "shape-label p", "middle");
    const wTop = cy - w.O / MY / 2 - 10, wBot = cy + w.O / MY / 2 + 26;
    const wY = wTop > 24 ? wTop : (wBot < MAP_H - 8 ? wBot : cy);
    svgText(g, cx, wY, `远景环宽 W ${w.W} m · 外框 ${w.O} m`, "shape-label r", "middle");
    if (state.camp && state.camp.wid === w.id) {
      const ccx = px(state.camp.x), ccy = py(state.camp.y);
      el("circle", { cx: ccx, cy: ccy, r: 9, class: "camp-mark" }, g);
      el("line", { x1: ccx - 14, y1: ccy, x2: ccx + 14, y2: ccy, class: "camp-mark" }, g);
      el("line", { x1: ccx, y1: ccy - 14, x2: ccx, y2: ccy + 14, class: "camp-mark" }, g);
      el("line", { x1: ccx, y1: ccy, x2: cx, y2: cy, class: "sel-line" }, g);
      svgText(g, ccx + 16, ccy - 10, "扎营点", "shape-label");
    }
    return;
  }
  const s = byCode.get(state.selected);
  if (!s) return;
  drawRange(g, s, { selected: true });
}

function renderMarkers() {
  const g = $("#layer-marks");
  clear(g);
  for (const s of SETTLEMENTS) {
    const cx = px(s.x), cy = py(s.y);
    const grp = el("g", { class: "marker", "data-code": s.code }, g);
    el("circle", { cx, cy, r: 17, class: "hit" }, grp);
    if (s.tier === "city") {
      el("path", { d: starPath(cx, cy, 11), class: "marker-city" }, grp);
    } else if (s.tier === "castle") {
      el("polygon", { points: `${cx},${cy - 9} ${cx + 8},${cy} ${cx},${cy + 9} ${cx - 8},${cy}`, class: "marker-castle" }, grp);
    } else {
      el("circle", { cx, cy, r: 5.5, class: "marker-village" }, grp);
    }
    if (s.tier !== "village" || s.code === state.selected) {
      const off = LABEL_OFFSETS[s.code] || { dx: 13, dy: 6, anchor: "start" };
      const cls = s.tier === "village" ? "map-label" : "map-label";
      svgText(g, cx + off.dx, cy + off.dy, s.name, cls, off.anchor);
    } else {
      const off = LABEL_OFFSETS[s.code] || { dx: 13, dy: 6, anchor: "start" };
      svgText(g, cx + off.dx, cy + off.dy, s.name, "map-label village", off.anchor);
    }
    grp.addEventListener("click", ev => { ev.stopPropagation(); selectSettlement(s.code, false); });
  }
}

/* ---------- 详情 ---------- */
function miniSVG(s, host) {
  const center = host ? host : s;
  const T = host ? host.T : (s.T || 1);
  const O = host ? host.O : (s.O || (s.T + 1200));
  const S = 132, P = 10, scale = (S - 2 * P) / O;
  const cx = S / 2, cy = S / 2, halfO = (O / 2) * scale, half = (T / 2) * scale;
  let d = "";
  for (const poly of s.P || []) {
    if (!poly || poly.length < 3) continue;
    for (let i = 0; i < poly.length; i++) {
      const pt = poly[i];
      const mx = cx + (pt[0] - center.x) * scale;
      const my = cy - (pt[1] - center.y) * scale;
      d += (i ? "L" : "M") + mx.toFixed(1) + " " + my.toFixed(1);
    }
    d += "Z";
  }
  return `<svg viewBox="0 0 ${S} ${S}" class="mini-svg" aria-hidden="true">
    <rect x="${cx - halfO}" y="${cy - halfO}" width="${halfO * 2}" height="${halfO * 2}" class="mini-o"></rect>
    <rect x="${cx - half}" y="${cy - half}" width="${half * 2}" height="${half * 2}" class="mini-t"></rect>
    <path d="${d}" class="mini-p"></path>
  </svg>`;
}

function renderDetail() {
  const d = $("#detail");
  if (state.selectedWild) {
    const w = wildById.get(state.selectedWild);
    if (!w) return;
    const names = w.sett.map(c => byCode.get(c).name);
    const sq = [[w.x - w.T / 2, w.y - w.T / 2], [w.x + w.T / 2, w.y - w.T / 2], [w.x + w.T / 2, w.y + w.T / 2], [w.x - w.T / 2, w.y + w.T / 2]];
    d.innerHTML = `
      <div class="detail-head">
        <div>
          <div class="eyebrow">野外单元 · ${w.id}</div>
          <h2>${wildName(w.id)}</h2>
        </div>
        <span class="badge" style="--badge: var(--wild)">野外</span>
      </div>
      <div class="stats">
        <div class="stat"><span>可走 P</span><b>${(w.T * w.T / 1e6).toFixed(2)}<small> km²</small></b></div>
        <div class="stat"><span>远景环宽 W</span><b>${w.W}<small> m</small></b></div>
        <div class="stat"><span>外框 O</span><b>${w.O}<small> m</small></b></div>
      </div>
      <div class="detail-body">
        ${miniSVG({ x: w.x, y: w.y, T: w.T, W: w.W, O: w.O, P: [sq] }, null)}
        <div class="rows">
          <div><span>锚点</span><b>${w.x}, ${w.y}</b></div>
          <div><span>锚点周边陆地</span><b>${Math.round(w.land * 100)}%</b></div>
          <div><span>并进的小据点</span><b>${names.length} 个</b></div>
        </div>
      </div>
      <p class="note">以锚点为中心的 ${w.T} m 场景；任意扎营点离锚点 ≤1 039 m，都在场景内。打开「野外网格」后点地图任意位置，会选最近的单元并标出扎营点。</p>
      ${state.camp ? `<p class="note">在这里扎营 → 载入 <b>${wildName(w.id)}</b>；出生点 = 场景局部 <b>(${Math.round(state.camp.x - w.x)}, ${Math.round(state.camp.y - w.y)})</b>。</p>` : ""}
      <div class="chips">${names.map(n => `<span class="chiplet">${esc(n)}</span>`).join("") || '<span class="chiplet">纯野外</span>'}</div>
    `;
    return;
  }
  const s = byCode.get(state.selected);
  if (!s) return;
  const host = hostOf(s);
  const T = host ? host.T : (s.T || 1);
  const W = host ? host.W : (s.W || 600);
  const O = host ? host.O : (s.O || (T + 2 * W));
  const area = Number(s.P_area || 0);
  const pmax = Math.round(Number(s.P_max || 0));
  d.innerHTML = `
    <div class="detail-head">
      <div>
        <div class="eyebrow">${tierName(s.tier)} · ${s.code}</div>
        <h2>${esc(s.name)}</h2>
      </div>
      <span class="badge" style="--badge: ${tierColor(s.tier)}">${tierName(s.tier)}</span>
    </div>
    <div class="stats">
      ${host ? `<div class="stat"><span>实际可走</span><b>5.31<small> km²</small></b></div>
      <div class="stat"><span>本村领地 P</span><b>${area.toFixed(2)}<small> km²</small></b></div>
      <div class="stat"><span>远景环宽 W</span><b>${fmt(W)}<small> m</small></b></div>` : `<div class="stat"><span>可走 P</span><b>${area.toFixed(2)}<small> km²</small></b></div>
      <div class="stat"><span>远景环宽 W</span><b>${fmt(W)}<small> m</small></b></div>
      <div class="stat"><span>外框 O</span><b>${fmt(O)}<small> m</small></b></div>`}
    </div>
    <div class="detail-body">
      ${miniSVG(s, host)}
      <div class="rows">
        <div><span>地形 T</span><b>${fmt(T)} m</b></div>
        <div><span>外框 O</span><b>${fmt(O)} m</b></div>
        <div><span>P 最宽</span><b>${fmt(pmax)} m</b></div>
        <div><span>归属场景</span><b>${host ? "并进 " + wildName(host.id) : "自成场景"}</b></div>
        <div><span>建成区</span><b>${s.w} × ${s.d} m</b></div>
        <div><span>实例 / 建筑</span><b>${fmt(s.inst)} / ${fmt(s.bld)}</b></div>
      </div>
    </div>
    ${host ? `<p class="note">并进 ${wildName(host.id)}：实际可走 = <b>5.31 km²</b>（2,304 m 野外场景，多村互通）；本村领地是其中一小块。</p>` : ""}
    <p class="note"><b>可走 P</b> = 建成区 + 边距，按据点领地线裁掉邻居；海岸/河岸还要再裁（页面是领地线近似）。<b>地形 T</b> 只是场景渲染范围，不代表全部能走。</p>
  `;
}

/* ---------- 列表 ---------- */
function renderList() {
  const q = state.q.trim().toLowerCase();
  const list = $("#list");
  const scroll = list.scrollTop;
  list.innerHTML = "";
  const groups = [["city", "城市"], ["castle", "城堡"], ["village", "村庄"]];
  for (const [tier, label] of groups) {
    if (state.tier !== "all" && state.tier !== tier) continue;
    const items = SETTLEMENTS.filter(s => s.tier === tier && (!q || s.name.toLowerCase().includes(q) || s.code.includes(q)));
    if (!items.length) continue;
    const head = document.createElement("div");
    head.className = "group-head";
    head.innerHTML = `${label}<span>${items.length}</span>`;
    list.appendChild(head);
    for (const s of items) {
      const host = hostOf(s);
      const b = document.createElement("button");
      b.className = "row" + (s.code === state.selected ? " active" : "");
      b.dataset.code = s.code;
      b.innerHTML = `<i class="dot" style="background:${tierColor(s.tier)}"></i>
        <span class="name">${esc(s.name)}</span>
        <span class="meta">${host ? "→ " + wildName(host.id) : "P " + Number(s.P_area).toFixed(2) + " / O " + s.O}</span>`;
      b.addEventListener("click", () => selectSettlement(s.code, true));
      list.appendChild(b);
    }
  }
  const det = document.createElement("details");
  det.className = "wild-group";
  det.innerHTML = `<summary>野外单元 <span>${WILD.length}</span></summary>`;
  const wrap = document.createElement("div");
  wrap.className = "wild-list";
  for (const w of WILD) {
    const names = w.sett.map(c => byCode.get(c).name).join("、");
    const b = document.createElement("button");
    b.className = "row" + (state.selectedWild === w.id ? " active" : "");
    b.dataset.wid = w.id;
    b.innerHTML = `<i class="dot" style="background:var(--wild)"></i>
      <span class="name">${wildName(w.id)}</span>
      <span class="meta">${names || "纯野外"}</span>`;
    b.addEventListener("click", () => selectWild(w.id, true));
    wrap.appendChild(b);
  }
  det.appendChild(wrap);
  list.appendChild(det);
  list.scrollTop = scroll;
}

/* ---------- 选择 ---------- */
function selectSettlement(code, focus) {
  const s = byCode.get(code);
  if (!s) return;
  state.selected = code;
  state.selectedWild = null;
  state.camp = null;
  renderAll(); renderWild(); renderSelected(); renderMarkers(); renderDetail(); renderList();
  if (focus) {
    const host = hostOf(s);
    const c = host ? host : s;
    const span = Math.max(2200, (host ? host.O : s.O) * 1.05);
    focusOn(c.x, c.y, span);
  }
}
function selectWild(id, focus, keepCamp) {
  const w = wildById.get(id);
  if (!w) return;
  state.selectedWild = id;
  state.selected = null;
  if (!keepCamp) state.camp = null;
  renderAll(); renderWild(); renderSelected(); renderMarkers(); renderDetail(); renderList();
  if (focus) focusOn(w.x, w.y, w.O * 1.05);
}

/* ---------- 交互 ---------- */
function bind() {
  const svg = $("#map");
  let drag = null;
  svg.addEventListener("wheel", e => {
    e.preventDefault();
    const rect = svg.getBoundingClientRect();
    const mx = state.view.x + (e.clientX - rect.left) / rect.width * state.view.w;
    const my = state.view.y + (e.clientY - rect.top) / rect.height * state.view.h;
    zoomAt(e.deltaY > 0 ? 1.15 : 0.87, mx, my);
  }, { passive: false });
  svg.addEventListener("pointerdown", e => {
    if (e.target.closest(".marker") || e.target.closest(".wild-dot")) return;
    drag = { x: e.clientX, y: e.clientY, vx: state.view.x, vy: state.view.y, moved: false };
    svg.classList.add("dragging");
    svg.setPointerCapture(e.pointerId);
  });
  svg.addEventListener("pointermove", e => {
    if (!drag) return;
    const rect = svg.getBoundingClientRect();
    const dx = (e.clientX - drag.x) / rect.width * state.view.w;
    const dy = (e.clientY - drag.y) / rect.height * state.view.h;
    if (Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y) > 3) drag.moved = true;
    state.view.x = clamp(drag.vx - dx, 0, MAP_W - state.view.w);
    state.view.y = clamp(drag.vy - dy, 0, MAP_H - state.view.h);
    applyView();
  });
  const endDrag = () => { drag = null; svg.classList.remove("dragging"); };
  svg.addEventListener("pointerup", e => {
    const wasDrag = drag ? drag.moved : false;
    endDrag();
    if (wasDrag || !state.showWild) return;
    if (e.target.closest(".marker") || e.target.closest(".wild-dot")) return;
    const rect = svg.getBoundingClientRect();
    const vx = state.view.x + (e.clientX - rect.left) / rect.width * state.view.w;
    const vy = state.view.y + (e.clientY - rect.top) / rect.height * state.view.h;
    const wx = PROJ.x0 + vx / MAP_W * (PROJ.x1 - PROJ.x0);
    const wy = PROJ.y1 - vy / MAP_H * (PROJ.y1 - PROJ.y0);
    let best = null, bd = Infinity;
    for (const w of WILD) {
      const d = (w.x - wx) * (w.x - wx) + (w.y - wy) * (w.y - wy);
      if (d < bd) { bd = d; best = w; }
    }
    if (best) {
      state.camp = { x: wx, y: wy, wid: best.id };
      selectWild(best.id, false, true);
    }
  });
  svg.addEventListener("pointercancel", endDrag);

  $("#btn-all").addEventListener("click", () => {
    state.showAll = !state.showAll;
    $("#btn-all").classList.toggle("active", state.showAll);
    renderAll();
  });
  $("#btn-wild").addEventListener("click", () => {
    state.showWild = !state.showWild;
    $("#btn-wild").classList.toggle("active", state.showWild);
    renderWild();
  });
  $("#btn-zin").addEventListener("click", () => zoomAt(0.8, state.view.w / 2, state.view.h / 2));
  $("#btn-zout").addEventListener("click", () => zoomAt(1.25, state.view.w / 2, state.view.h / 2));
  $("#btn-reset").addEventListener("click", () => {
    state.view = { x: 0, y: 0, w: MAP_W, h: MAP_H };
    applyView(); renderMarkers();
  });
  $$(".chip").forEach(b => b.addEventListener("click", () => {
    state.tier = b.dataset.tier;
    $$(".chip").forEach(x => x.classList.toggle("active", x === b));
    renderList();
  }));
  $("#q").addEventListener("input", e => {
    state.q = e.target.value;
    renderList();
  });
}

/* ---------- 启动 ---------- */
function start() {
  const bar = 1000 / MX;
  document.documentElement.style.setProperty("--bar", bar.toFixed(0) + "px");
  bind();
  applyView();
  const h = location.hash.slice(1);
  if (h && wildById.has(h)) selectWild(h, false);
  else if (h && byCode.has(h)) selectSettlement(h, false);
  else selectSettlement("sdn", false);
  renderAll(); renderWild(); renderSelected(); renderMarkers(); renderDetail(); renderList();
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
else start();
</script>
"""

html = (HTML
        .replace("__SETTLEMENTS__", json.dumps(settlements, ensure_ascii=False))
        .replace("__WILD__", json.dumps(wilds, ensure_ascii=False))
        .replace("__PROJ__", json.dumps(proj, ensure_ascii=False))
        .replace("__MAP_W__", str(MAP_W))
        .replace("__MAP_H__", str(MAP_H)))

out_html = os.path.join(OUTDIR, "settlement_viewer.html")
with open(out_html, "w", encoding="utf-8") as f:
    f.write(html)
print("html", out_html, round(os.path.getsize(out_html) / 1024, 1), "KB")
