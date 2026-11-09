# -*- coding: utf-8 -*-
"""【已废弃】41 版页面生成器 —— 2026-11-03 起由 build_settlement_map.py（63 版）取代。

两个脚本都会写 docs/世界与地编/regions_viewer.html，留着会互相覆盖，所以这里直接退出。
"""
import sys

sys.exit("build_regions_viewer.py 已废弃：页面统一由 build_settlement_map.py 生成（63 版）。")

"""生成《区域划分 · 最终 scene》可视化汇报页。

数据：
  regions.json / bubbles.json / settlements_p.json / settlements_plan.csv
输出：
  h:/.../Modules/RDR2/Source/docs/世界与地编/regions_viewer.html
底图：
  settlement_map_base.jpg（同目录，已存在）
"""
import csv, json, os

RDR2 = r"D:\BrainMaker\大镖客2解包分析"
BASE = os.path.join(RDR2, "_scratch", "settlement_plan")
OUTDIR = r"h:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source\docs\世界与地编"

def read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def f(x):
    try:
        return float(x)
    except Exception:
        return 0.0

rows = read_csv(os.path.join(BASE, "settlements_plan.csv"))
pdata = json.load(open(os.path.join(BASE, "settlements_p.json"), encoding="utf-8"))
regions = json.load(open(os.path.join(BASE, "regions.json"), encoding="utf-8"))
bubbles = json.load(open(os.path.join(BASE, "bubbles.json"), encoding="utf-8"))

points = []
compact = {}
for r in rows:
    code = r["code"]
    tier = r["tier"]
    typ = r["rdr2_type"]
    p = pdata.get(code, {})
    points.append({
        "code": code, "name": r["name_zh"], "tier": tier, "type": typ,
        "x": round(f(r["world_x"]), 1), "y": round(f(r["world_y"]), 1),
        "area": p.get("P_area_km2", 0), "max": p.get("P_max_m", 0),
        "host": r["embed_into"] or "",
        "big": tier in ("city", "castle") or typ == "hideout",
    })
    if tier in ("city", "castle") or typ == "hideout":
        compact[code] = {"P": p.get("P", []), "area": p.get("P_area_km2", 0),
                         "T": int(f(r["scene_T_m"])),
                         "W": 1200 if tier == "city" else 800 if tier == "castle" else 500}

meta = json.load(open(os.path.join(RDR2, "deliverable/terrain/on_map/meta.json"), encoding="utf-8"))["mainland"]["world"]
proj = {"x0": meta["x0"], "x1": meta["x1"], "y0": meta["y0"], "y1": meta["y1"]}
MAP_W, MAP_H = 2500, 1859
NB = len(bubbles)
TOTAL = 22 + NB + 2

HTML = r"""<title>区域划分 · 最终 scene</title>
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
  --wild: #2f7f72;
  --danger: #b23b2e;
  --map-ink: #241c14;
  --map-halo: #fffaf0;
  --shadow: 0 10px 28px rgba(45,30,15,.14);
  --sans: "Noto Sans SC", "Microsoft YaHei", system-ui, -apple-system, sans-serif;
  --serif: "Noto Serif SC", "Songti SC", "SimSun", serif;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #14110d; --panel: #1e1913; --panel-2: #251f17;
    --ink: #f0e6d6; --muted: #a89880; --line: #3a2f24; --line-strong: #57483a;
    --accent: #e08a4c; --accent-ink: #1a120a;
    --city: #d9a83a; --castle: #6fa3d1; --village: #79b87f;
    --walk: #ef9a52; --wild: #5fb3a3; --danger: #e06a56;
    --shadow: 0 10px 28px rgba(0,0,0,.38);
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #14110d; --panel: #1e1913; --panel-2: #251f17;
  --ink: #f0e6d6; --muted: #a89880; --line: #3a2f24; --line-strong: #57483a;
  --accent: #e08a4c; --accent-ink: #1a120a;
  --city: #d9a83a; --castle: #6fa3d1; --village: #79b87f;
  --walk: #ef9a52; --wild: #5fb3a3; --danger: #e06a56;
  --shadow: 0 10px 28px rgba(0,0,0,.38);
  color-scheme: dark;
}
* { box-sizing: border-box; }
html, body { height: 100%; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: var(--sans); font-size: 13.5px; line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
button { font: inherit; }
.app { display: grid; grid-template-columns: 430px minmax(0, 1fr); height: 100%; min-height: 0; }
.sidebar { display: flex; flex-direction: column; min-height: 0; background: var(--panel); border-right: 1px solid var(--line); }
.head { padding: 18px 20px 12px; border-bottom: 1px solid var(--line); }
.eyebrow { font-size: 10.5px; letter-spacing: .13em; text-transform: uppercase; color: var(--muted); font-weight: 700; }
h1 { font-family: var(--serif); font-size: 23px; line-height: 1.2; margin: 4px 0 2px; letter-spacing: .02em; }
.sub { margin: 0; color: var(--muted); font-size: 12.5px; }
.summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; padding: 12px 18px 8px; }
.card { background: var(--panel-2); border: 1px solid var(--line); border-radius: 10px; padding: 7px 8px; min-width: 0; }
.card span { display: block; font-size: 9.5px; color: var(--muted); white-space: nowrap; }
.card b { display: block; font-size: 20px; line-height: 1.15; font-variant-numeric: tabular-nums; }
.card.total { background: color-mix(in srgb, var(--accent) 12%, var(--panel)); border-color: color-mix(in srgb, var(--accent) 40%, var(--line)); }
.tabs { display: flex; gap: 6px; flex-wrap: wrap; padding: 4px 18px 10px; }
.tab { appearance: none; border: 1px solid var(--line); background: var(--panel); color: var(--ink); border-radius: 999px; padding: 5px 10px; font-size: 11.5px; cursor: pointer; }
.tab.active { background: var(--ink); color: var(--panel); border-color: var(--ink); }
.note { margin: 0 18px 10px; font-size: 11px; color: var(--muted); line-height: 1.45; }
.note b { color: var(--ink); }
.legend { margin: 0 18px 10px; border: 1px solid var(--line); border-radius: 10px; background: var(--panel); }
.legend summary { cursor: pointer; padding: 8px 11px; font-size: 10.5px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); font-weight: 700; }
.legend-grid { display: grid; gap: 6px; padding: 2px 11px 11px; font-size: 11px; line-height: 1.4; }
.legend-grid div { display: flex; gap: 7px; align-items: flex-start; }
.legend-grid i { flex: 0 0 auto; width: 12px; height: 12px; margin-top: 2px; display: inline-block; }
.legend-grid b { color: var(--ink); }
.sw-region { background: conic-gradient(from 0deg, #d62728, #ff7f0e, #2ca02c, #1f77b4, #9467bd, #d62728); border-radius: 2px; }
.sw-p { background: rgba(217,119,42,.55); border: 1px solid var(--walk); }
.sw-t { border: 1px dashed var(--muted); }
.sw-o { border: 1px dashed var(--castle); }
.sw-bubble { border: 1px dashed var(--wild); }
.sw-bubblep { background: rgba(47,127,114,.45); border: 1px solid var(--wild); }
.sw-anchor { background: var(--wild); border-radius: 50%; }
.sw-boundary { border-top: 2px dashed var(--ink); height: 7px; }
.sw-city { background: var(--city); border-radius: 50%; }
.sw-castle { background: var(--castle); transform: rotate(45deg); width: 10px !important; height: 10px !important; }
.sw-hideout { width: 0 !important; height: 0 !important; border-left: 6px solid transparent; border-right: 6px solid transparent; border-bottom: 10px solid var(--village); background: none !important; }
.detail { margin: 0 18px 10px; padding: 10px 11px; background: var(--panel-2); border: 1px solid var(--line); border-radius: 10px; }
.detail h2 { font-family: var(--serif); font-size: 17px; margin: 2px 0 4px; }
.detail .row { display: flex; justify-content: space-between; gap: 8px; font-size: 11.5px; }
.detail .row span { color: var(--muted); }
.detail .row b { text-align: right; font-variant-numeric: tabular-nums; }
.table-wrap { flex: 1; overflow: auto; padding: 0 10px 16px; min-height: 0; }
table { width: 100%; border-collapse: collapse; font-size: 11px; }
th { position: sticky; top: 0; background: var(--panel); color: var(--muted); font-weight: 700; text-align: left; padding: 6px 6px; border-bottom: 1px solid var(--line); z-index: 1; }
td { padding: 5px 6px; border-bottom: 1px solid color-mix(in srgb, var(--line) 60%, transparent); vertical-align: top; }
tr.region-row { cursor: pointer; }
tr.region-row:hover td { background: var(--panel-2); }
tr.region-row.active td { background: color-mix(in srgb, var(--accent) 12%, var(--panel)); }
td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
td.bad { color: var(--danger); font-weight: 700; }
.smalls { color: var(--muted); line-height: 1.35; }
.bubble-group { margin-top: 8px; border-top: 1px solid var(--line); padding-top: 6px; }
.bubble-group summary { cursor: pointer; font-size: 10.5px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); font-weight: 700; padding: 4px 6px; }
.main { position: relative; min-width: 0; overflow: hidden; background: #cbc2b1; }
.map-wrap { position: absolute; inset: 0; }
#map { width: 100%; height: 100%; display: block; }
.map-controls { position: absolute; top: 12px; left: 12px; display: flex; gap: 6px; }
.ctrl { appearance: none; border: 1px solid var(--line); background: color-mix(in srgb, var(--panel) 92%, transparent); color: var(--ink); border-radius: 8px; padding: 6px 10px; font-size: 11.5px; cursor: pointer; box-shadow: var(--shadow); }
.ctrl:hover { border-color: var(--line-strong); }
.scalebar { position: absolute; left: 14px; bottom: 12px; display: flex; align-items: center; gap: 8px; background: color-mix(in srgb, var(--panel) 88%, transparent); border: 1px solid var(--line); border-radius: 8px; padding: 5px 9px; font-size: 10.5px; color: var(--muted); box-shadow: var(--shadow); }
.scalebar i { display: block; height: 7px; border-left: 2px solid var(--ink); border-right: 2px solid var(--ink); border-bottom: 2px solid var(--ink); width: 232px; }
/* SVG */
.region-fill { vector-effect: non-scaling-stroke; }
.region-fill.selected { stroke: var(--ink); stroke-width: 3; }
.p-fill { fill: rgba(217,119,42,.26); stroke: var(--walk); stroke-width: 1.8; vector-effect: non-scaling-stroke; }
.p-fill.selected { fill: rgba(217,119,42,.42); stroke-width: 3; }
.t-ghost { fill: none; stroke: var(--muted); stroke-width: 1; stroke-dasharray: 4 4; vector-effect: non-scaling-stroke; opacity: .6; }
.o-frame { fill: none; stroke: var(--castle); stroke-width: 1.1; stroke-dasharray: 5 5; vector-effect: non-scaling-stroke; opacity: .45; }
.bubble-scene { fill: none; stroke: var(--wild); stroke-width: 1; stroke-dasharray: 3 6; vector-effect: non-scaling-stroke; opacity: .35; }
.bubble-p { fill: rgba(47,127,114,.17); stroke: var(--wild); stroke-width: 1.8; vector-effect: non-scaling-stroke; }
.bubble-p.selected { fill: rgba(47,127,114,.34); stroke-width: 3; }
.expansion { fill: url(#hatch); }
.frame-line { fill: none; stroke: var(--ink); stroke-width: 1.4; stroke-dasharray: 7 5; vector-effect: non-scaling-stroke; }
.expansion-label { font-family: var(--sans); font-size: 23px; font-weight: 700; fill: var(--muted); letter-spacing: .10em; }
.anchor { fill: var(--wild); stroke: var(--map-halo); stroke-width: 1.2; vector-effect: non-scaling-stroke; }
.assign-line { stroke: var(--wild); stroke-width: .8; stroke-dasharray: 2 4; vector-effect: non-scaling-stroke; opacity: .35; }
.big-city { fill: var(--city); stroke: var(--map-halo); stroke-width: 1.5; vector-effect: non-scaling-stroke; }
.big-castle { fill: var(--castle); stroke: var(--map-halo); stroke-width: 1.5; vector-effect: non-scaling-stroke; }
.big-hideout { fill: var(--village); stroke: var(--map-halo); stroke-width: 1.5; vector-effect: non-scaling-stroke; }
.small-dot { fill: var(--ink); stroke: var(--map-halo); stroke-width: 1; vector-effect: non-scaling-stroke; }
.lbl { font-family: var(--sans); paint-order: stroke; stroke: var(--map-halo); stroke-linejoin: round; pointer-events: none; }
.lbl.big { font-size: 27px; font-weight: 700; fill: var(--map-ink); stroke-width: 4.5px; }
.lbl.small { font-size: 17px; font-weight: 500; fill: var(--map-ink); stroke-width: 3.5px; }
.lbl.bubble { font-size: 19px; font-weight: 700; fill: var(--wild); stroke-width: 4px; }
@media (max-width: 860px) {
  .app { grid-template-columns: 1fr; height: auto; }
  .main { order: 1; height: 58vh; height: 58svh; min-height: 360px; }
  .sidebar { order: 2; border-right: 0; border-top: 1px solid var(--line); }
  .table-wrap { overflow: visible; }
  .summary { grid-template-columns: repeat(2, 1fr); }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>

<div class="app">
  <aside class="sidebar">
    <div class="head">
      <div class="eyebrow">荒野大镖客 2 → 骑砍 2</div>
      <h1>地盘划分 · 要做的地图</h1>
      <p class="sub">22 块彩色地盘 ≠ 22 张地图；真正要做的是城镇地图 + 野外营地地图</p>
    </div>
    <div class="summary">
      <div class="card"><span>城镇地图</span><b>22</b></div>
      <div class="card"><span>野外营地</span><b>__NB__</b></div>
      <div class="card"><span>瓜玛</span><b>2</b></div>
      <div class="card total"><span>地图总数</span><b>__TOTAL__</b></div>
    </div>
    <div class="tabs">
      <button class="tab" data-tab="overview">总览</button>
      <button class="tab" data-tab="ownership">地盘划分 22</button>
      <button class="tab" data-tab="compact">城镇能走范围 22</button>
      <button class="tab" data-tab="wild">野外营地 __NB__</button>
    </div>
    <p class="note"><b>22 块彩色地盘不是 22 张地图。</b>如果把一整块地盘做成一张地图，地面要 4–10.8 km 宽，引擎做不了。地盘线只干一件事：让两个城镇的<b>能走范围不压在一起</b>。所有能走的地方都已经切在<b>大镖客地图边缘以内</b>；地图外面我们多铺的地形只做远景，不能走。</p>
    <details class="legend" open>
      <summary>图例 / 怎么读（大白话）</summary>
      <div class="legend-grid">
        <div><i class="sw-region"></i><span><b>彩色大块 = 地盘划分</b>：地图上“这块地归谁”的分区。不是能走的地方，也不是一张地图；只用来让两个城镇的能走范围不压在一起。</span></div>
        <div><i class="sw-p"></i><span><b>橙色实心块 = 城镇里能走的范围</b>：城/堡/藏身处本身；已经切在大镖客地图边缘以内。圣丹尼斯 1.02 km²。</span></div>
        <div><i class="sw-t"></i><span><b>灰色虚线方框 = 场景地面要做多大</b>：不是全部能走；方框里超出橙色块的部分是缓冲带，走不过去。</span></div>
        <div><i class="sw-o"></i><span><b>蓝色虚线方框 = 远景范围</b>：只做背景，不能走；可以互相重叠。</span></div>
        <div><i class="sw-bubble"></i><span><b>绿色虚线方框 = 野外营地的一张地图（3,072 m）</b>：玩家在框内任意位置扎营 → 载入它；营地地图可以互相重叠。</span></div>
        <div><i class="sw-bubblep"></i><span><b>绿色实心块 = 野外营地里能走的范围</b>：3,072 m 地面里切掉大镖客地图以外之后剩下的部分。</span></div>
        <div><i class="sw-anchor"></i><span><b>绿点 = 营地范围的中心</b>：不是据点，也不是藏身处。</span></div>
        <div><i class="sw-boundary"></i><span><b>深色虚线 = 大镖客地图的边缘</b>；外面斜线带 = 我们为了远景多铺的地形，不能走。</span></div>
        <div><span style="display:flex;gap:5px;align-items:center;flex-wrap:wrap"><i class="sw-city"></i>黄星 = 城市 · <i class="sw-castle"></i>蓝菱 = 城堡 · <i class="sw-hideout"></i>绿三角 = 藏身处 · 黑点 = 小据点</span></div>
      </div>
    </details>
    <div id="detail" class="detail"></div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>地盘（归谁）</th><th>带上的小据点</th><th>能走面积 km²</th><th>整块地盘当一张图要多大</th></tr></thead>
        <tbody id="region-rows"></tbody>
      </table>
      <details class="bubble-group">
        <summary>野外气泡 __NB__ 个（点行高亮）</summary>
        <table>
          <thead><tr><th>营地</th><th>中心</th><th>能走面积 km²</th><th>带上的小据点</th></tr></thead>
          <tbody id="bubble-rows"></tbody>
        </table>
      </details>
    </div>
  </aside>
  <main class="main">
    <div class="map-wrap">
      <svg id="map" viewBox="0 0 2500 1859" role="img" aria-label="区域划分与最终 scene">
        <defs>
          <pattern id="hatch" width="16" height="16" patternUnits="userSpaceOnUse" patternTransform="rotate(35)">
            <rect width="16" height="16" fill="rgba(110,95,75,.05)"></rect>
            <line x1="0" y1="0" x2="0" y2="16" stroke="rgba(110,95,75,.30)" stroke-width="2"></line>
          </pattern>
        </defs>
        <path d="M-60 -48 H2560 V1907 H-60 Z M0 0 V1859 H2500 V0 Z" fill-rule="evenodd" class="expansion"></path>
        <image href="settlement_map_base.jpg" x="0" y="0" width="2500" height="1859" preserveAspectRatio="none"></image>
        <rect x="0" y="0" width="2500" height="1859" class="frame-line"></rect>
        <text x="8" y="-18" class="expansion-label">扩充区 · 不可走</text>
        <g id="l-regions"></g>
        <g id="l-compact"></g>
        <g id="l-wild"></g>
        <g id="l-marks"></g>
      </svg>
    </div>
    <div class="map-controls">
      <button class="ctrl" id="reset">复位</button>
    </div>
    <div class="scalebar"><i></i><span>1 km</span></div>
  </main>
</div>

<script>
const REGIONS = __REGIONS__;
const BUBBLES = __BUBBLES__;
const NB = BUBBLES.length;
const TOTAL = 22 + NB + 2;
const POINTS = __POINTS__;
const COMPACT = __COMPACT__;
const PROJ = __PROJ__;
const MAP_W = 2500, MAP_H = 1859;
const MX = (PROJ.x1 - PROJ.x0) / MAP_W;
const MY = (PROJ.y1 - PROJ.y0) / MAP_H;
const NS = "http://www.w3.org/2000/svg";
const PALETTE = [
  [214,39,40],[255,127,14],[44,160,44],[31,119,180],[148,103,189],
  [140,86,75],[227,119,194],[188,189,34],[23,190,207],[174,199,232],
  [255,187,120],[152,223,138],[197,176,213],[196,156,148],[247,182,210],
  [199,199,199],[219,219,141],[158,218,229],[255,152,150],[255,204,130],
  [176,220,170],[190,174,212]
];
const state = { tab: "overview", selectedRegion: null, selectedBubble: null, view: { x: -60, y: -48, w: MAP_W + 120, h: MAP_H + 96 } };
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
const byCode = new Map(POINTS.map(p => [p.code, p]));
const regionBySeed = new Map(REGIONS.map(r => [r.seed, r]));
const bubbleById = new Map(BUBBLES.map(b => [b.id, b]));

function px(x) { return (x - PROJ.x0) / (PROJ.x1 - PROJ.x0) * MAP_W; }
function py(y) { return (PROJ.y1 - y) / (PROJ.y1 - PROJ.y0) * MAP_H; }
function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
function fmt(n) { return Number(n).toLocaleString("en-US"); }
function color(i, a) { const c = PALETTE[i % PALETTE.length]; return `rgba(${c[0]},${c[1]},${c[2]},${a})`; }
function el(tag, attrs = {}, parent) { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }
function clear(g) { while (g.firstChild) g.removeChild(g.firstChild); }
function text(parent, x, y, s, cls, anchor = "start") { const t = el("text", { x, y, class: cls, "text-anchor": anchor }, parent); t.textContent = s; return t; }
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
function applyView() { $("#map").setAttribute("viewBox", `${state.view.x} ${state.view.y} ${state.view.w} ${state.view.h}`); }
function focusOnBBox(b) {
  const x0 = px(b[0]), x1 = px(b[2]), y0 = py(b[3]), y1 = py(b[1]);
  const w = Math.max(260, Math.abs(x1 - x0) * 1.18);
  const h = Math.max(200, Math.abs(y1 - y0) * 1.18);
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  state.view = { x: clamp(cx - w / 2, 0, MAP_W - w), y: clamp(cy - h / 2, 0, MAP_H - h), w, h };
  applyView();
}
function resetView() { state.view = { x: -60, y: -48, w: MAP_W + 120, h: MAP_H + 96 }; applyView(); }

function drawMarks(g) {
  for (const p of POINTS) {
    if (p.big) {
      const x = px(p.x), y = py(p.y);
      if (p.tier === "city") {
        let d = "";
        for (let k = 0; k < 10; k++) {
          const a = -Math.PI / 2 + k * Math.PI / 5, rr = k % 2 ? 4 : 9;
          d += (k ? "L" : "M") + (x + rr * Math.cos(a)).toFixed(1) + " " + (y + rr * Math.sin(a)).toFixed(1);
        }
        el("path", { d: d + "Z", class: "big-city" }, g);
      } else if (p.tier === "castle") {
        el("polygon", { points: `${x},${y-8} ${x+8},${y} ${x},${y+8} ${x-8},${y}`, class: "big-castle" }, g);
      } else {
        el("polygon", { points: `${x},${y-7} ${x+7},${y+5} ${x-7},${y+5}`, class: "big-hideout" }, g);
      }
      text(g, x + 11, y - 9, p.name, "lbl big");
    } else {
      const x = px(p.x), y = py(p.y);
      el("circle", { cx: x, cy: y, r: 3.2, class: "small-dot" }, g);
      text(g, x + 6, y - 5, p.name, "lbl small");
    }
  }
}

function drawRegions(g, faint) {
  REGIONS.forEach((r, i) => {
    const d = polyPath(r.P);
    if (!d) return;
    const sel = state.selectedRegion === r.seed;
    el("path", {
      d, class: "region-fill" + (sel ? " selected" : ""),
      fill: color(i, faint ? 0.05 : sel ? 0.28 : 0.13),
      stroke: color(i, faint ? 0.45 : 0.95), "stroke-width": sel ? 3 : 1.2
    }, g);
  });
}

function drawCompact(g) {
  for (const [code, c] of Object.entries(COMPACT)) {
    const p = byCode.get(code);
    if (!p) continue;
    const d = polyPath(c.P);
    const sel = state.selectedRegion === code;
    if (d) el("path", { d, class: "p-fill" + (sel ? " selected" : "") }, g);
    const x = px(p.x), y = py(p.y);
    const t = c.T / MX, h = c.T / MY;
    el("rect", { x: x - t / 2, y: y - h / 2, width: t, height: h, class: "t-ghost" }, g);
    const O = c.T + 2 * c.W;
    const ow = O / MX, oh = O / MY;
    el("rect", { x: x - ow / 2, y: y - oh / 2, width: ow, height: oh, class: "o-frame" }, g);
    text(g, x - t / 2 + 5, y - h / 2 + 14, `T ${c.T}`, "lbl small");
  }
}

function drawWild(g) {
  for (const b of BUBBLES) {
    const x = px(b.x), y = py(b.y);
    const t = b.T / MX, h = b.T / MY;
    const sel = state.selectedBubble === b.id;
    // 场景地形方框（3,072）——可以伸进扩充区
    el("rect", { x: x - t / 2, y: y - h / 2, width: t, height: h, class: "bubble-scene" }, g);
    // 可走 P——已裁到真实地图边界
    const d = polyPath(b.P);
    if (d) el("path", { d, class: "bubble-p" + (sel ? " selected" : "") }, g);
    el("circle", { cx: x, cy: y, r: 5, class: "anchor" }, g);
    text(g, x + 9, y - 9, b.id.replace("wild_", "W"), "lbl bubble");
    for (const code of b.small_codes) {
      const p = byCode.get(code);
      if (!p) continue;
      const sx = px(p.x), sy = py(p.y);
      el("line", { x1: sx, y1: sy, x2: x, y2: y, class: "assign-line" }, g);
    }
  }
}

function render() {
  const gr = $("#l-regions"), gc = $("#l-compact"), gw = $("#l-wild"), gm = $("#l-marks");
  clear(gr); clear(gc); clear(gw); clear(gm);
  if (state.tab === "ownership") drawRegions(gr, false);
  if (state.tab === "overview") drawRegions(gr, true);
  if (state.tab === "compact" || state.tab === "overview") drawCompact(gc);
  if (state.tab === "wild" || state.tab === "overview") drawWild(gw);
  drawMarks(gm);
}

function renderDetail() {
  const d = $("#detail");
  if (state.selectedBubble) {
    const b = bubbleById.get(state.selectedBubble);
    const names = b.small_names.join("、") || "纯野外";
    d.innerHTML = `<div class="row"><span>野外营地</span><b>${b.id.replace("wild_", "W")}</b></div>
      <div class="row"><span>锚点</span><b>${b.x}, ${b.y}</b></div>
      <div class="row"><span>营地地图地面</span><b>3,072 m 见方</b></div>
      <div class="row"><span>能走面积</span><b>${Number(b.P_area_km2 || 0).toFixed(2)} km²</b></div>
      <div class="row"><span>地图外</span><b>${b.clipped ? "靠边的部分已切掉，不能走" : "全在大镖客地图内"}</b></div>
      <div class="row"><span>并入的小据点</span><b>${names}</b></div>`;
    return;
  }
  if (state.selectedRegion) {
    const r = regionBySeed.get(state.selectedRegion);
    if (!r) return;
    const bad = r.T_whole > 4096;
    d.innerHTML = `<h2>${r.name} <span style="font-size:12px;color:var(--muted)">${r.seed}</span></h2>
      <div class="row"><span>并入的小据点</span><b>${r.small_names.join("、") || "—"}</b></div>
      <div class="row"><span>这块地盘的能走面积</span><b>${r.area_km2.toFixed(2)} km²</b></div>
      <div class="row"><span>整块地盘当一张图</span><b style="color:${bad ? "var(--danger)" : "inherit"}">要 ${fmt(r.T_whole)} m 宽 ${bad ? "✗ 做不了" : ""}</b></div>
      <div class="row"><span>实际做法</span><b>城镇能走范围 + 野外营地地图</b></div>
      <div class="row"><span>城镇里能走面积</span><b>${(COMPACT[r.seed] ? COMPACT[r.seed].area : 0).toFixed(2)} km²</b></div>
      <div class="row"><span>地图外</span><b>已切掉，不能走</b></div>`;
    return;
  }
  d.innerHTML = `<h2>最终要做的地图</h2>
    <div class="row"><span>城镇自己的地图</span><b>22</b></div>
    <div class="row"><span>野外营地地图</span><b>${NB}</b></div>
    <div class="row"><span>瓜玛岛</span><b>2</b></div>
    <div class="row"><span>一共</span><b>${TOTAL}</b></div>
    <div class="row"><span>最坏情况（小据点不能共用地图）</span><b>${TOTAL + 22}</b></div>
    <p class="note" style="margin:6px 0 0">点表格里的行或地图上的营地，看具体归谁。</p>`;
}

function renderTable() {
  const tbody = $("#region-rows");
  tbody.innerHTML = "";
  REGIONS.forEach((r, i) => {
    const tr = document.createElement("tr");
    tr.className = "region-row" + (state.selectedRegion === r.seed ? " active" : "");
    const bad = r.T_whole > 4096;
    tr.innerHTML = `<td><i style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${color(i, .9)};margin-right:5px"></i><b>${r.name}</b><br><span style="color:var(--muted);font-size:10px">${r.seed}</span></td>
      <td class="smalls">${r.small_names.join("、") || "—"}</td>
      <td class="num">${r.area_km2.toFixed(2)}</td>
      <td class="num ${bad ? "bad" : ""}">${fmt(r.T_whole)}</td>`;
    tr.addEventListener("click", () => {
      state.selectedRegion = r.seed; state.selectedBubble = null;
      render(); renderDetail(); renderTable();
      focusOnBBox(r.bbox);
    });
    tbody.appendChild(tr);
  });
  const btbody = $("#bubble-rows");
  btbody.innerHTML = "";
  BUBBLES.forEach(b => {
    const tr = document.createElement("tr");
    tr.className = "region-row" + (state.selectedBubble === b.id ? " active" : "");
    tr.innerHTML = `<td><b>${b.id.replace("wild_", "W")}</b></td><td class="num">${b.x.toFixed(0)}, ${b.y.toFixed(0)}</td><td class="num">${Number(b.P_area_km2 || 0).toFixed(2)}</td><td class="smalls">${b.small_names.join("、") || "—"}</td>`;
    tr.addEventListener("click", () => {
      state.selectedBubble = b.id; state.selectedRegion = null;
      render(); renderDetail(); renderTable();
      focusOnBBox([b.x - b.T / 2, b.y - b.T / 2, b.x + b.T / 2, b.y + b.T / 2]);
    });
    btbody.appendChild(tr);
  });
}

function bind() {
  $$(".tab").forEach(b => b.addEventListener("click", () => {
    state.tab = b.dataset.tab;
    $$(".tab").forEach(x => x.classList.toggle("active", x === b));
    render();
  }));
  $("#reset").addEventListener("click", () => { resetView(); });
}
bind();
$$(".tab")[0].classList.add("active");
render(); renderDetail(); renderTable();
</script>
"""

html = (HTML
        .replace("__REGIONS__", json.dumps(regions, ensure_ascii=False))
        .replace("__BUBBLES__", json.dumps(bubbles, ensure_ascii=False))
        .replace("__POINTS__", json.dumps(points, ensure_ascii=False))
        .replace("__COMPACT__", json.dumps(compact, ensure_ascii=False))
        .replace("__PROJ__", json.dumps(proj, ensure_ascii=False))
        .replace("__NB__", str(NB))
        .replace("__TOTAL__", str(TOTAL)))

out = os.path.join(OUTDIR, "regions_viewer.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print("html", out, round(os.path.getsize(out) / 1024, 1), "KB", "bubbles", NB, "total", TOTAL)
