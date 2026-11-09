# -*- coding: utf-8 -*-
"""生成 63 版《世界场景划分》页（据点 44 + 野地 17 + 瓜玛 2）。

数据：scene_specs.json（build_scene_division.py 产出）
底图：settlement_map_base.jpg（同目录）
输出：docs/世界与地编/regions_viewer.html
"""
import json, os, hashlib, time, math

RDR2 = r"D:\BrainMaker\大镖客2解包分析"
BASE = os.path.join(RDR2, "_scratch", "settlement_plan")
OUTDIR = r"h:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source\docs\世界与地编"

specs = json.load(open(os.path.join(BASE, "scene_specs.json"), encoding="utf-8"))
check = json.load(open(os.path.join(BASE, "scene_division_check.json"), encoding="utf-8"))
# 地图画面区 bbox（远景框不得超出）—— 由 tools/gen_scene_extent.py 生成
try:
    EXTENT = json.load(open(os.path.join(OUTDIR, "scene_extent.json"), encoding="utf-8"))
except Exception:
    EXTENT = {}
S = specs["settlements"]
WL = specs["wilds"]
PROJ = specs["frame"]


# ---------------------------------------------------------------- 室内房间（2026-11-04）
# 数据 = export/world/interior_placement_audit.json（tools/audit_interior_placement.py 产出）
# 只在「点了一个据点」时画，所以先把房间归到据点：
#   ① 落在某个据点的 P 矩形里 → 就是它；② 落不进 → 取 800 m 内最近的据点；③ 都够不着 → 不画。
# 只收 inside=True 的包（= 室内确实被一栋建筑包住，和场景里实际摆的那批同一口径）。
def _load_rooms(settlements):
    p = os.path.join(RDR2, "export", "world", "interior_placement_audit.json")
    if not os.path.exists(p):
        return []
    out = []
    for x in json.load(open(p, encoding="utf-8")):
        if not x.get("inside"):
            continue
        bb = x.get("interior") or []
        if len(bb) < 4:
            continue
        rx, ry = (bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0
        code, near = None, None
        for s in settlements:
            r = (s.get("P") or [[]])[0]
            if not r:
                continue
            xs = [q[0] for q in r]
            ys = [q[1] for q in r]
            if min(xs) <= rx <= max(xs) and min(ys) <= ry <= max(ys):
                code = s["code"]
                break
            d = math.hypot(s["x"] - rx, s["y"] - ry)
            if d <= 800 and (near is None or d < near[1]):
                near = (s["code"], d)
        if code is None and near:
            code = near[0]
        if code is None:
            continue
        out.append({"code": code, "pkg": x["pkg"], "host": x.get("host") or "",
                    "x": round(rx, 1), "y": round(ry, 1)})
    return out


ROOMS = _load_rooms(S)

NSET, NWILD, NGUA = len(S), len(WL), 1
TOTAL = NSET + NWILD + NGUA
MAP_W, MAP_H = 2500, 1859

HTML = r"""<title>世界场景划分 63</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;600;700&family=Noto+Serif+SC:wght@600;700&display=swap">
<style>
:root {
  --bg:#efe9dc; --panel:#fbf7ee; --panel-2:#f6f0e4; --ink:#241c14; --muted:#756654;
  --line:#d9ccb7; --line-strong:#b9a98f; --accent:#b4552d; --accent-ink:#fff8ef;
  --city:#b8861f; --castle:#3d6d99; --village:#4f8456; --hideout:#8a5a9e;
  --walk:#d9772a; --wild:#2f7f72; --danger:#b23b2e;
  --act:#1c1610; --far:#1f6feb;
  --map-ink:#241c14; --map-halo:#fffaf0;
  --shadow:0 10px 28px rgba(45,30,15,.14);
  --sans:"Noto Sans SC","Microsoft YaHei",system-ui,-apple-system,sans-serif;
  --serif:"Noto Serif SC","Songti SC","SimSun",serif;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg:#14110d; --panel:#1e1913; --panel-2:#251f17; --ink:#f0e6d6; --muted:#a89880;
    --line:#3a2f24; --line-strong:#57483a; --accent:#e08a4c; --accent-ink:#1a120a;
    --city:#d9a83a; --castle:#6fa3d1; --village:#79b87f; --hideout:#b98cc9;
    --walk:#ef9a52; --wild:#5fb3a3; --danger:#e06a56;
    --act:#ffdcaa; --far:#6aa8ff;
    --shadow:0 10px 28px rgba(0,0,0,.38); color-scheme:dark;
  }
}
:root[data-theme="dark"] {
  --bg:#14110d; --panel:#1e1913; --panel-2:#251f17; --ink:#f0e6d6; --muted:#a89880;
  --line:#3a2f24; --line-strong:#57483a; --accent:#e08a4c; --accent-ink:#1a120a;
  --city:#d9a83a; --castle:#6fa3d1; --village:#79b87f; --hideout:#b98cc9;
  --walk:#ef9a52; --wild:#5fb3a3; --danger:#e06a56;
  --act:#ffdcaa; --far:#6aa8ff;
  --shadow:0 10px 28px rgba(0,0,0,.38); color-scheme:dark;
}
* { box-sizing: border-box; }
html, body { height: 100%; }
body { margin:0; background:var(--bg); color:var(--ink); font-family:var(--sans); font-size:13.5px; line-height:1.5; -webkit-font-smoothing:antialiased; }
button { font: inherit; }
.app { display:grid; grid-template-columns:420px minmax(0,1fr); height:100%; min-height:0; }
.sidebar { display:flex; flex-direction:column; min-height:0; background:var(--panel); border-right:1px solid var(--line); }
.head { padding:18px 20px 10px; border-bottom:1px solid var(--line); }
.eyebrow { font-size:10.5px; letter-spacing:.13em; text-transform:uppercase; color:var(--muted); font-weight:700; }
h1 { font-family:var(--serif); font-size:23px; line-height:1.2; margin:4px 0 2px; letter-spacing:.02em; }
.sub { margin:0; color:var(--muted); font-size:12.5px; }
.summary { display:grid; grid-template-columns:repeat(4,1fr); gap:6px; padding:11px 18px 7px; }
.card { background:var(--panel-2); border:1px solid var(--line); border-radius:10px; padding:7px 8px; min-width:0; }
.card span { display:block; font-size:9.5px; color:var(--muted); white-space:nowrap; }
.card b { display:block; font-size:20px; line-height:1.15; font-variant-numeric:tabular-nums; }
.card.total { background:color-mix(in srgb,var(--accent) 12%,var(--panel)); border-color:color-mix(in srgb,var(--accent) 40%,var(--line)); }
.tabs { display:flex; gap:6px; flex-wrap:wrap; padding:3px 18px 9px; }
.tab { appearance:none; border:1px solid var(--line); background:var(--panel); color:var(--ink); border-radius:999px; padding:5px 10px; font-size:11.5px; cursor:pointer; }
.tab.active { background:var(--ink); color:var(--panel); border-color:var(--ink); }
.note { margin:0 18px 9px; font-size:11px; color:var(--muted); line-height:1.45; }
.note b { color:var(--ink); }
.legend { margin:0 18px 9px; border:1px solid var(--line); border-radius:10px; background:var(--panel); }
.legend summary { cursor:pointer; padding:7px 10px; font-size:10.5px; letter-spacing:.06em; color:var(--muted); font-weight:700; }
.legend-grid { display:grid; gap:5px; padding:1px 10px 10px; font-size:10.8px; line-height:1.4; }
.legend-grid div { display:flex; gap:7px; align-items:flex-start; }
.legend-grid i { flex:0 0 auto; width:12px; height:12px; margin-top:2px; display:inline-block; }
.legend-grid b { color:var(--ink); }
.sw-p { background:rgba(217,119,42,.4); border:1px solid var(--walk); }
.sw-wild { background:rgba(47,127,114,.4); border:1px solid var(--wild); }
.sw-t { border:2px solid var(--act); background:rgba(28,22,16,.05); }
.sw-o { border:2px dashed var(--far); background:rgba(31,111,235,.05); }
.sw-city { background:var(--city); border-radius:50%; }
.sw-castle { background:var(--castle); transform:rotate(45deg); width:10px !important; height:10px !important; }
.sw-village { background:var(--village); border-radius:50%; }
.sw-hideout { width:0 !important; height:0 !important; border-left:6px solid transparent; border-right:6px solid transparent; border-bottom:10px solid var(--hideout); background:none !important; }
.sw-anchor { background:var(--wild); border-radius:50%; }
.sw-edge { border-top:2px dotted #6b5d4d; height:7px; }
.detail { margin:0 18px 9px; padding:10px 11px; background:var(--panel-2); border:1px solid var(--line); border-radius:10px; }
.detail h2 { font-family:var(--serif); font-size:17px; margin:2px 0 4px; }
.detail .row { display:flex; justify-content:space-between; gap:10px; font-size:11.5px; }
.detail .roomrow { display:flex; justify-content:space-between; gap:10px; font-size:11px; color:var(--muted); cursor:pointer; padding:1px 2px; border-radius:3px; }
.detail .roomrow:hover { background:var(--panel-2); color:var(--ink); }
.detail .roomrow b { font-weight:600; color:var(--ink); }
.detail .row span { color:var(--muted); }
.detail .row b { text-align:right; font-variant-numeric:tabular-nums; }
.detail .hint { margin:7px 0 0; font-size:11px; color:var(--muted); line-height:1.45; }
.detail .hint.warn { color:var(--accent); font-weight:600; }
.list { flex:1; overflow:auto; padding:0 10px 16px; min-height:0; }
.group-head { display:flex; justify-content:space-between; padding:9px 8px 4px; font-size:10.5px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); font-weight:700; }
.group-head span { font-variant-numeric:tabular-nums; }
.rowbtn { display:flex; align-items:center; gap:8px; width:100%; border:0; background:transparent; color:var(--ink); text-align:left; padding:6px 8px; border-radius:8px; cursor:pointer; font-size:12.5px; }
.rowbtn:hover { background:var(--panel-2); }
.rowbtn.active { background:color-mix(in srgb,var(--accent) 13%,var(--panel)); outline:1px solid color-mix(in srgb,var(--accent) 40%,var(--line)); }
.dot { width:8px; height:8px; border-radius:50%; flex:0 0 auto; }
.rowbtn .name { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.rowbtn .meta { margin-left:auto; flex:0 0 auto; color:var(--muted); font-size:10px; font-variant-numeric:tabular-nums; max-width:165px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.main { position:relative; min-width:0; overflow:hidden; background:#cbc2b1; }
#map { width:100%; height:100%; display:block; cursor:default; }
.map-controls { position:absolute; top:12px; left:12px; display:flex; gap:6px; flex-wrap:wrap; max-width:calc(100% - 24px); }
.ctrl { white-space:nowrap; appearance:none; border:1px solid var(--line); background:color-mix(in srgb,var(--panel) 92%,transparent); color:var(--ink); border-radius:8px; padding:6px 10px; font-size:11.5px; cursor:pointer; box-shadow:var(--shadow); }
.ctrl:hover { border-color:var(--line-strong); }
.scalebar { position:absolute; left:14px; bottom:12px; display:flex; align-items:center; gap:8px; background:color-mix(in srgb,var(--panel) 88%,transparent); border:1px solid var(--line); border-radius:8px; padding:5px 9px; font-size:10.5px; color:var(--muted); box-shadow:var(--shadow); }
.scalebar i { display:block; height:7px; border-left:2px solid var(--ink); border-right:2px solid var(--ink); border-bottom:2px solid var(--ink); width:232px; }
.outside-fill { fill:url(#hatch); stroke:rgba(90,80,70,.55); stroke-width:1; stroke-dasharray:4 4; vector-effect:non-scaling-stroke; }
.outside-lbl { font-family:var(--sans); font-size:calc(34px * var(--k,1)); font-weight:700; fill:#6b5d4d; paint-order:stroke; stroke:var(--map-halo); stroke-width:calc(5px * var(--k,1)); }
.h { fill:#fff; stroke:var(--accent); stroke-width:1.4; vector-effect:non-scaling-stroke; cursor:crosshair; }
.hov { fill:var(--accent); stroke:#fff; stroke-width:1.5; vector-effect:non-scaling-stroke; cursor:move; }
.vh { fill:var(--accent); stroke:#fff; stroke-width:1.2; vector-effect:non-scaling-stroke; cursor:crosshair; }
.editnum { width:92px; padding:2px 6px; border:1px solid var(--line); border-radius:6px; background:var(--panel); color:var(--ink); font:inherit; text-align:right; }
.draft { fill:rgba(180,85,45,.15); stroke:var(--accent); stroke-width:1.6; stroke-dasharray:6 4; vector-effect:non-scaling-stroke; pointer-events:none; }
.gap { fill:rgba(210,30,30,.40); stroke:#d21f1f; stroke-width:3; vector-effect:non-scaling-stroke; pointer-events:none; }
.ovl { fill:rgba(235,140,20,.35); stroke:#d9820f; stroke-width:3; vector-effect:non-scaling-stroke; pointer-events:none; }
.guide { stroke:var(--accent); stroke-width:1; stroke-dasharray:6 4; vector-effect:non-scaling-stroke; opacity:.7; pointer-events:none; }
.frame-line { fill:none; stroke:var(--ink); stroke-width:1.2; stroke-dasharray:6 6; vector-effect:non-scaling-stroke; opacity:.55; }
.p-fill { vector-effect:non-scaling-stroke; }
.p-fill.city { fill:rgba(184,134,31,.30); stroke:var(--city); }
.p-fill.castle { fill:rgba(61,109,153,.28); stroke:var(--castle); }
.p-fill.village { fill:rgba(79,132,86,.28); stroke:var(--village); }
.p-fill.hideout { fill:rgba(138,90,158,.30); stroke:var(--hideout); }
.p-fill.sel { stroke-width:2.6; }
.p-fill.faint { opacity:.30; }
.wild-fill { fill:rgba(47,127,114,.22); stroke:var(--wild); stroke-width:1.5; vector-effect:non-scaling-stroke; }
.wild-fill.sel { fill:rgba(47,127,114,.20); stroke:none; }
.wild-fill.faint { fill:rgba(47,127,114,.08); stroke-width:.8; stroke-opacity:.35; }
/* 点选后只留两种框（2026-11-07）：黑实线 = 玩家活动区，蓝虚线 = 远景范围。
   其他野地 / 据点一律淡化让路，缺口/重叠默认关闭 —— 否则满屏矩形分不清谁是谁。 */
.t-box { fill:rgba(28,22,16,.05); stroke:var(--act); stroke-width:2.4; vector-effect:non-scaling-stroke; }
.t-box.ghost { fill:none; stroke-width:1.2; stroke-opacity:.45; }
.o-box { fill:rgba(31,111,235,.05); stroke:var(--far); stroke-width:2; stroke-dasharray:10 6; vector-effect:non-scaling-stroke; opacity:.9; }
.box-lbl { font-weight:700; paint-order:stroke; stroke:var(--map-halo); stroke-linejoin:round; pointer-events:none; }
.box-lbl.t { fill:var(--act); }
.box-lbl.o { fill:var(--far); }
.extent-line { fill:none; stroke:#6b5d4d; stroke-width:1.3; stroke-dasharray:2 7; vector-effect:non-scaling-stroke; opacity:.5; }
.extent-lbl { fill:#6b5d4d; opacity:.85; pointer-events:none; }
.anchor { fill:var(--wild); stroke:var(--map-halo); stroke-width:1.1; vector-effect:non-scaling-stroke; }
.city-m { fill:var(--city); stroke:var(--map-halo); stroke-width:1.4; vector-effect:non-scaling-stroke; }
.castle-m { fill:var(--castle); stroke:var(--map-halo); stroke-width:1.4; vector-effect:non-scaling-stroke; }
.hideout-m { fill:var(--hideout); stroke:var(--map-halo); stroke-width:1.4; vector-effect:non-scaling-stroke; }
.village-m { fill:var(--village); stroke:var(--map-halo); stroke-width:1.1; vector-effect:non-scaling-stroke; }
.lbl { font-family:var(--sans); paint-order:stroke; stroke:var(--map-halo); stroke-linejoin:round; pointer-events:none; }
.lbl.big { font-size:calc(44px * var(--k,1)); font-weight:700; fill:var(--map-ink); stroke-width:calc(7px * var(--k,1)); }
.lbl.small { font-size:calc(30px * var(--k,1)); font-weight:600; fill:var(--map-ink); stroke-width:calc(5px * var(--k,1)); }
.lbl.wild { font-size:calc(34px * var(--k,1)); font-weight:700; fill:var(--wild); stroke-width:calc(5.5px * var(--k,1)); }
.lbl.click { pointer-events:auto; cursor:pointer; }
/* 含室内场景的房间（2026-11-04）：只在点选据点后出现 */
.room-mark { fill:#7c3aed; fill-opacity:.85; stroke:#fff8ef; stroke-width:calc(3px * var(--k,1)); }
.lbl.room { font-size:calc(20px * var(--k,1)); font-weight:600; fill:#6d28d9; stroke-width:calc(4px * var(--k,1)); }
.lbl.room-head { font-size:calc(24px * var(--k,1)); font-weight:700; fill:#6d28d9; stroke-width:calc(5px * var(--k,1)); paint-order:stroke; stroke:var(--map-halo); pointer-events:none; }
@media (max-width:860px) {
  .app { grid-template-columns:1fr; height:auto; }
  .main { order:1; height:58vh; height:58svh; min-height:360px; }
  .sidebar { order:2; border-right:0; border-top:1px solid var(--line); }
  .list { overflow:visible; }
  .summary { grid-template-columns:repeat(2,1fr); }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>

<div class="app">
  <aside class="sidebar">
    <div class="head">
      <div class="eyebrow">荒野大镖客 2 → 骑砍 2</div>
      <h1>世界场景划分 · 63</h1>
      <p class="sub">44 张据点地图 + 17 张野地地图 + 2 张瓜玛</p>
    </div>
    <div class="summary">
      <div class="card"><span>据点地图</span><b id="nSet">__NSET__</b></div>
      <div class="card"><span>野地地图</span><b id="nWild">__NWILD__</b></div>
      <div class="card"><span>瓜玛</span><b>2</b></div>
      <div class="card total"><span>地图总数</span><b id="nTotal">__TOTAL__</b></div>
    </div>
    <div class="tabs">
      <button class="tab active" data-tab="overview">总览</button>
      <button class="tab" data-tab="settle">据点 __NSET__</button>
      <button class="tab" data-tab="wild">野地 __NWILD__</button>
      <button class="tab" data-tab="cover">拼起来看覆盖</button>
    </div>
    <p class="note"><b>据点各自一张地图，野地按 17 个中心把剩下的陆地分完。</b>
      野地 P（绿色块）<b>包含据点范围</b>：野地场景里那几块地方用<b>远景碎片</b>表现，玩家走进去时弹「是否进入据点」→ 再切到据点自己的场景。
      <b>斜线区是地图外</b>——官方地图上就是空白，不算地图，只做远景。</p>
    <details class="legend" open>
      <summary>图例 / 怎么读（大白话）</summary>
      <div class="legend-grid">
        <div><i class="sw-p"></i><span><b>彩色矩形 = 据点里能走的地方（P）</b>：建成区外扩后的<b>外切矩形</b>，44 个各一块，互相不压。走进这块范围会提示「进入据点」。</span></div>
        <div><i style="background:rgba(200,40,40,.35);border:1px dashed #b23b2e"></i><span><b>红色块 = 没被任何野地覆盖的地方</b>（缺口）：地图区里有、但没有野地管，拖相邻野地的边补上。</span></div>
        <div><i style="background:rgba(230,140,20,.3);border:1px dashed #c87a10"></i><span><b>橙色块 = 两个野地互相重叠的地方</b>：拖边让它们刚好贴住（吸附会帮你对齐）。</span></div>
        <div><i class="sw-wild"></i><span><b>绿色块 = 野地的核心区（P）</b>：17 个中心把真实陆地分完，也是「站在这块坐标就载入这张野地图」的归属区；<b>包含据点范围</b>。方框内、绿块外的部分是<b>缓冲带</b>（能看见、能走，但没内容）。</span></div>
        <div><i class="sw-t"></i><span><b>黑实线方框 = 玩家活动区</b>：这张地图玩家走得到的地方，走到边上就被挡住，框上直接写着尺寸。<b>默认只画你选中的那一个</b>；想一次看全部，点左上角「显示全部活动区」（那时变成淡线）。</span></div>
        <div><i class="sw-o"></i><span><b>蓝虚线方框 = 远景范围</b>：活动区每边再往外铺一圈（只做背景，不能走）；可以互相重叠。<b>顶到地图边界会被裁短</b> —— 裁完就不再以活动区为中心，这是正常的。<b>图上画的框 = blend 里真正有的地面</b>（4 m 高度图只覆盖到地图画面区，外面那截既不建地形也没贴图）。</span></div>
        <div><i style="background:repeating-linear-gradient(45deg,rgba(90,80,70,.05) 0 3px,rgba(90,80,70,.45) 3px 5px);border:1px dashed rgba(90,80,70,.55)"></i><span><b>斜线区 = 地图外</b>：官方地图上就是空白羊皮纸（河流以南、西北角、东侧海面外侧），<b>不算有效地图</b>；只做远景，谁也不能走。</span></div>
        <div><i class="sw-anchor"></i><span><b>绿点 = 野地地图的中心</b>：玩家在这一片扎营，就载入以它为中心的野地场景。</span></div>
        <div><i class="sw-edge"></i><span><b>深色点线 = 大镖客地图边缘</b>（远景框不得超出它）；线外面是扩充区，不能走。</span></div>
        <div><i style="background:#7c3aed;border:1px solid #fff8ef;border-radius:2px"></i><span><b>紫方块 = 含室内场景的房间</b>：这栋建筑内部有独立室内模型（已摆进场景 blend）。<b>点一个据点就显示</b>，滚轮放大到房间铺得开时会自动出名字（<b>再点它一次 / 按 Esc 取消</b>）；悬停看包名 / 宿主建筑 / 世界坐标；左侧清单点一行可单间放大。</span></div>
        <div><span style="display:flex;gap:5px;align-items:center;flex-wrap:wrap"><i class="sw-city"></i>黄星=城市 · <i class="sw-castle"></i>蓝菱=城堡 · <i class="sw-village"></i>绿点=村庄/营地/点位 · <i class="sw-hideout"></i>紫三角=藏身处</span></div>
      </div>
    </details>
    <div id="detail" class="detail"></div>
    <div id="list" class="list"></div>
  </aside>
  <main class="main">
    <svg id="map" viewBox="0 0 2500 1859" role="img" aria-label="世界场景划分 63">
      <defs>
        <pattern id="hatch" width="16" height="16" patternUnits="userSpaceOnUse" patternTransform="rotate(35)">
          <rect width="16" height="16" fill="rgba(90,80,70,.06)"></rect>
          <line x1="0" y1="0" x2="0" y2="16" stroke="rgba(90,80,70,.32)" stroke-width="2"></line>
        </pattern>
      </defs>
      <image href="settlement_map_base.jpg" x="0" y="0" width="2500" height="1859" preserveAspectRatio="none"></image>
      <rect x="0" y="0" width="2500" height="1859" class="frame-line"></rect>
      <g id="l-outside"></g>
      <g id="l-extent"></g>
      <g id="l-frames"></g>
      <g id="l-wild"></g>
      <g id="l-settle"></g>
      <g id="l-issues"></g>
      <g id="l-rooms"></g>
      <g id="l-selected"></g>
      <g id="l-marks"></g>
    </svg>
    <div class="map-controls">
      <button class="ctrl" id="reset">复位</button>
      <button class="ctrl" id="tall">显示全部活动区</button>
      <button class="ctrl" id="iss">缺口/重叠：关</button>
      <button class="ctrl" id="edit">编辑模式：关</button>
      <button class="ctrl" id="newWild" style="display:none">＋新建野地</button>
      <span class="ctrl" id="dirtyBadge" style="cursor:default">无改动</span>
      <span id="editTools" style="display:none;gap:6px">
        <button class="ctrl" id="snapBtn">吸附：开</button>
        <button class="ctrl" id="fitBtn">贴合邻居</button>
        <button class="ctrl" id="allRect">野地全转矩形</button>
        <button class="ctrl" id="polyRect">多边形转矩形</button>
        <button class="ctrl" id="zoomin">放大</button>
        <button class="ctrl" id="zoomout">缩小</button>
        <button class="ctrl" id="exp">导出改动</button>
        <button class="ctrl" id="imp">导入</button>
        <button class="ctrl" id="resetAll">全部重置</button>
        <input type="file" id="file" accept=".json" style="display:none">
      </span>
    </div>
    <div class="scalebar"><i></i><span>1 km</span></div>
  </main>
</div>

<script>
const SETTLE = __SETTLE__;
const WILDS = __WILDS__;
const OUTSIDE = __OUTSIDE__;
const EXTENT = __EXTENT__;
const GAPS = __GAPS__;
const OVLS = __OVERLAPS__;
const PROJ = __PROJ__;
const CHECK = __CHECK__;
const ROOMS = __ROOMS__;
const MAP_W = 2500, MAP_H = 1859;
const MX = (PROJ.x1 - PROJ.x0) / MAP_W;
const MY = (PROJ.y1 - PROJ.y0) / MAP_H;
const NS = "http://www.w3.org/2000/svg";
const SVG = document.getElementById("map");
const state = { tab: "overview", sel: null, showAllT: false, showIssues: false, edit: false, mode: "select", drag: null, draft: [], dirtyS: new Set(), dirtyW: new Set(), addedW: new Set(), deletedW: new Set(), exported: true, snap: true, snapX: null, snapY: null, drawStart: null, view: { x: 0, y: 0, w: MAP_W, h: MAP_H } };
for (const w of WILDS) {
  const r = w.P[0];
  let axis = r.length >= 4;
  for (let i = 0; axis && i < r.length - 1; i++) {
    const a = r[i], b = r[i + 1];
    if (Math.abs(a[0] - b[0]) > 0.5 && Math.abs(a[1] - b[1]) > 0.5) axis = false;
  }
  if (axis) w.isRect = true;
}
const ORIG = { S: JSON.parse(JSON.stringify(SETTLE)), W: JSON.parse(JSON.stringify(WILDS)) };
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
const byCode = new Map(SETTLE.map(p => [p.code, p]));
const byWild = new Map(WILDS.map(w => [w.id, w]));

function px(x) { return (x - PROJ.x0) / (PROJ.x1 - PROJ.x0) * MAP_W; }
function py(y) { return (PROJ.y1 - y) / (PROJ.y1 - PROJ.y0) * MAP_H; }
function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
function fmt(n) { return Number(n).toLocaleString("en-US"); }
function el(tag, attrs = {}, parent) { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }
function clear(g) { while (g.firstChild) g.removeChild(g.firstChild); }
function text(parent, x, y, s, cls, anchor = "start") { const t = el("text", { x, y, class: cls, "text-anchor": anchor }, parent); t.textContent = s; return t; }
function polyPath(polys) {
  let d = "";
  for (const poly of polys || []) {
    if (!poly || poly.length < 3) continue;
    for (let i = 0; i < poly.length; i++) {
      const p = poly[i];
      d += (i ? "L" : "M") + px(p[0]).toFixed(1) + " " + py(p[1]).toFixed(1);
    }
    d += "Z";
  }
  return d;
}
function applyView() {
  $("#map").setAttribute("viewBox", `${state.view.x} ${state.view.y} ${state.view.w} ${state.view.h}`);
  $("#map").style.setProperty("--k", Math.max(0.12, Math.min(1, state.view.w / MAP_W)).toFixed(3));
}
function focusOnBBox(b) {
  if (!b || !b.every(Number.isFinite)) return;
  const x0 = px(b[0]), x1 = px(b[2]), y0 = py(b[3]), y1 = py(b[1]);
  const w = Math.max(300, Math.abs(x1 - x0) * 1.18);
  const h = Math.max(220, Math.abs(y1 - y0) * 1.18);
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  state.view = { x: clamp(cx - w / 2, 0, Math.max(0, MAP_W - w)), y: clamp(cy - h / 2, 0, Math.max(0, MAP_H - h)), w, h };
  applyView();
}
function zoomView(k) {
  const cx = state.view.x + state.view.w / 2, cy = state.view.y + state.view.h / 2;
  state.view.w = Math.max(60, Math.min(MAP_W * 2, state.view.w * k));
  state.view.h = state.view.w * (MAP_H / MAP_W);
  state.view.x = cx - state.view.w / 2; state.view.y = cy - state.view.h / 2;
  applyView();
}
function resetView() { state.view = { x: 0, y: 0, w: MAP_W, h: MAP_H }; applyView(); }

// ---- 室内房间的「放大模式」（2026-11-04：用户反馈点完据点房间还是太小）----------
// 一个据点可能有离得很远的房间（黑水镇有两个码头棚屋在 600 m 外），
// 所以先取**中位中心**、只用 260 m 内的房间算放大框，免得被离群点拉远。
function roomsOf(code) { return ROOMS.filter(r => r.code === code); }
function focusRoom(x, y) {
  const w = 60, h = w * (MAP_H / MAP_W);
  state.view = { x: clamp(px(x) - w / 2, 0, Math.max(0, MAP_W - w)),
                 y: clamp(py(y) - h / 2, 0, Math.max(0, MAP_H - h)), w, h };
  applyView(); render();
}

function marker(g, p, x, y) {
  if (p.tier === "city") {
    let d = "";
    for (let k = 0; k < 10; k++) {
      const a = -Math.PI / 2 + k * Math.PI / 5, rr = k % 2 ? 4 : 9;
      d += (k ? "L" : "M") + (x + rr * Math.cos(a)).toFixed(1) + " " + (y + rr * Math.sin(a)).toFixed(1);
    }
    el("path", { d: d + "Z", class: "city-m" }, g);
  } else if (p.tier === "castle") {
    el("polygon", { points: `${x},${y-8} ${x+8},${y} ${x},${y+8} ${x-8},${y}`, class: "castle-m" }, g);
  } else if (p.kind === "hideout") {
    el("polygon", { points: `${x},${y-8} ${x+8},${y+5} ${x-8},${y+5}`, class: "hideout-m" }, g);
  } else {
    el("circle", { cx: x, cy: y, r: 4.2, class: "village-m" }, g);
  }
}

function ringCentroid(ring) {
  let a = 0, cx = 0, cy = 0;
  for (let i = 0; i < ring.length - 1; i++) {
    const x0 = ring[i][0], y0 = ring[i][1], x1 = ring[i + 1][0], y1 = ring[i + 1][1];
    const f = x0 * y1 - x1 * y0;
    a += f; cx += (x0 + x1) * f; cy += (y0 + y1) * f;
  }
  a *= 0.5;
  if (!a) return ring[0];
  return [cx / (6 * a), cy / (6 * a)];
}

function drawOutside(g) {
  const d = polyPath(OUTSIDE);
  if (!d) return;
  el("path", { d, class: "outside-fill", "fill-rule": "evenodd" }, g);
  let big = null, best = 0;
  for (const r of OUTSIDE) {
    let a = 0;
    for (let i = 0; i < r.length - 1; i++) a += r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1];
    if (Math.abs(a) > best) { best = Math.abs(a); big = r; }
  }
  if (big) {
    const c = ringCentroid(big);
    const t1 = text(g, px(c[0]), py(c[1]) - 10, "地图外", "outside-lbl", "middle");
    const t2 = text(g, px(c[0]), py(c[1]) + 28, "官方地图上没有画面 · 不可走 · 只做远景", "outside-lbl", "middle");
    t2.setAttribute("font-size", "calc(22px * var(--k,1))");
  }
}

function drawSettle(g, faint) {
  for (const p of SETTLE) {
    const d = polyPath(p.P);
    if (!d) continue;
    const sel = state.sel && state.sel.kind === "settle" && state.sel.id === p.code;
    const path = el("path", { d, class: `p-fill ${p.kind}` + (sel ? " sel" : "") + (faint && !sel ? " faint" : ""), "fill-rule": "evenodd" }, g);
    path.addEventListener("pointerdown", ev => { ev.stopPropagation(); select({ kind: "settle", id: p.code }); });
  }
}

function drawWild(g, faint) {
  for (const w of WILDS) {
    const d = polyPath(w.P);
    if (!d) continue;
    const sel = state.sel && state.sel.kind === "wild" && state.sel.id === w.id;
    const path = el("path", { d, class: "wild-fill" + (sel ? " sel" : (faint ? " faint" : "")), "fill-rule": "evenodd" }, g);
    path.addEventListener("pointerdown", ev => { ev.stopPropagation(); select({ kind: "wild", id: w.id }); });
  }
}

// 活动区 = 能走矩形（= scene_list.csv 的「能走_x0..y1」：据点取 P_rect，野地取 P 的外接矩形）；
// 远景 = FW/FH（构建侧配置的原值 —— 据点的 FW 是「档位 T + 外扩」，**不是** AW + 外扩）。
// 2026-11-07 修：以前据点用 AW+2W 算远景框，比真实配置小最多 370 m。
// 🔴 同一轮第二修：高度图 / blend 里的地形**只覆盖地图画面区**（`scene_terrain.build` 会把框再夹回去），
//    所以这里两个矩形都先夹进地图框 —— 保证「图上画的 = 高度图范围 = blend 里的地面」是同一个数。
function sceneExtent(o) {
  const poly = (o.P && o.P[0]) || [];
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const q of poly) {
    x0 = Math.min(x0, q[0]); y0 = Math.min(y0, q[1]);
    x1 = Math.max(x1, q[0]); y1 = Math.max(y1, q[1]);
  }
  if (!isFinite(x0)) { x0 = x1 = o.x; y0 = y1 = o.y; }
  const raw = { x0: x0, y0: y0, x1: x1, y1: y1 };   // 规格能走矩形（未夹地图框）
  const b = EXTENT && EXTENT.map;
  if (b && b.length >= 4) {
    x0 = Math.max(x0, b[0]); y0 = Math.max(y0, b[1]);
    x1 = Math.min(x1, b[2]); y1 = Math.min(y1, b[3]);
  }
  const w = o.W || 0;
  const aw = x1 - x0, ah = y1 - y0;
  const isWild = !!(o.id && String(o.id).indexOf("wild_") === 0);
  // 远景尺寸要和 build_scene_division 一致：野地 = 活动区(box 取整到 128) + 2W；
  // 据点 = 档位 T + 2W（T 是老的档位方块，和能走范围 P 无关）。
  const aw0 = raw.x1 - raw.x0, ah0 = raw.y1 - raw.y0;
  const fw = isWild ? Math.ceil(aw0 / 128) * 128 + 2 * w : (o.T || Math.ceil(aw0 / 128) * 128) + 2 * w;
  const fh = isWild ? Math.ceil(ah0 / 128) * 128 + 2 * w : (o.T || Math.ceil(ah0 / 128) * 128) + 2 * w;
  // 远景框是**以场景中心 (x,y) 为原点**铺的，不是以能走范围的中心 —— 据点这两个中心常差几十米
  return { x0: x0, y0: y0, x1: x1, y1: y1, aw: aw, ah: ah, w: w, fw: fw, fh: fh,
           cx: o.x, cy: o.y, raw: raw };
}

// 屏幕恒定字号：SVG 里写多少 px = 屏幕上多少 px（--k 在深放大时兜不住，会越放越大）
function unitFor(p) { const r = SVG.getBoundingClientRect(); const ppu = (r.width || 1100) / state.view.w; return p / ppu; }

// 两个框：黑实线 = 玩家活动区（能走），蓝虚线 = 远景范围（只做背景）
function sceneBox(g, e, withO) {
  const bx0 = px(e.x0), by0 = py(e.y1);
  const tw = px(e.x1) - bx0, th = py(e.y0) - by0;
  if (!withO) {   // 「显示全部活动区」：只画淡框，不写字
    el("rect", { x: bx0, y: by0, width: tw, height: th, class: "t-box ghost" }, g);
    return;
  }
  const pad = unitFor(9), fs = unitFor(14), sw = unitFor(3.5);
  // 画面顶部被工具栏占着（复位/显示全部活动区/…），标签别钻到它下面
  const topSafe = state.view.y + unitFor(52), botSafe = state.view.y + state.view.h - unitFor(8);
  const clampY = y => Math.min(Math.max(y, topSafe), botSafe);
  el("rect", { x: bx0, y: by0, width: tw, height: th, class: "t-box" }, g);
  const lt = text(g, bx0 + pad, clampY(by0 + pad + fs), "活动区 " + fmt(e.aw) + " × " + fmt(e.ah) + " m", "box-lbl t", "start");
  lt.style.fontSize = fs.toFixed(2) + "px"; lt.style.strokeWidth = sw.toFixed(2) + "px";
  // 小据点的框装不下这行字（会压到镇名上）→ 挪到框外上方
  const lw = lt.getComputedTextLength ? lt.getComputedTextLength() : 0;
  const outTop = by0 - pad > state.view.y + fs;
  if (outTop && lw + 2 * pad > tw) {
    lt.setAttribute("x", (bx0 + unitFor(2)).toFixed(2));
    lt.setAttribute("y", clampY(by0 - pad).toFixed(2));
  }

  const c = clampFar(e.cx, e.cy, e.fw, e.fh, e);
  const fbx = px(c.x) - c.fw / MX / 2, fby = py(c.y) - c.fh / MY / 2;
  const fw = c.fw / MX, fh = c.fh / MY;
  el("rect", { x: fbx, y: fby, width: fw, height: fh, class: "o-box" }, g);
  const cn = cutNames(c.cut);
  // 规格尺寸与"超出地图多少"放在右侧面板讲，图上只留实际尺寸（否则又变成"一堆看不懂的数"）
  // 远景标签挂在「远景框上边、活动区正上方」——远景框一定包住活动区，而活动区一定在画面里，
  // 所以这个位置永远看得见（挂在框的右下角时，框被地图边界推出去，字就跑到屏幕外了）。
  // 但框本身顶出地图画面区时上边会跑到屏幕外 —— 所以纵向也要夹进视口。
  const crowded = (by0 - fby) < fs * 3.2;      // 上边离活动区太近 → 字挪到框外上方
  const yA = clampY(by0 + pad + fs);           // 活动区那行字的实际落点
  let ly = clampY(crowded ? fby - pad : fby + pad + fs);
  if (Math.abs(ly - yA) < fs * 1.5) {          // 两行会压在一起（框顶顶出画面时就是这情况）→ 错开一行
    ly = yA + fs * 1.6;
    if (ly > botSafe) ly = yA - fs * 1.6;
  }
  const cxA = (bx0 + px(e.x1)) / 2;            // 活动区中心（水平）
  const lo = text(g, cxA, ly,
    "远景 " + fmt(c.fw) + " × " + fmt(c.fh) + " m" + (cn ? "（按地图边界裁剪）" : ""),
    "box-lbl o", "middle");
  lo.style.fontSize = fs.toFixed(2) + "px"; lo.style.strokeWidth = sw.toFixed(2) + "px";
  // 长标签别越出远景框（也夹进视口，免得被屏幕边缘切掉）
  const lwO = lo.getComputedTextLength ? lo.getComputedTextLength() : 0;
  const minX = Math.max(fbx + pad + lwO / 2, state.view.x + pad + lwO / 2);
  const maxX = Math.min(fbx + fw - pad - lwO / 2, state.view.x + state.view.w - pad - lwO / 2);
  lo.setAttribute("x", (minX <= maxX ? Math.min(Math.max(cxA, minX), maxX) : (minX + maxX) / 2).toFixed(2));
}

// 远景框被地图边界裁剪后，面板里那句解释（用户 2026-11-07 问："是你画错了还是框范围错了"）
function cutHint(c, e) {
  const cn = cutNames(c.cut);
  if (!cn) return "";
  const sp = c.spill > 0.5
    ? ` 规格远景框是 <b>${fmt(e.fw)} × ${fmt(e.fh)} m</b>，其中 <b>${fmt(Math.round(c.spill))} m</b> 伸出地图画面区 —— `
      + `那一条既没有地形也没有贴图（4 m 高度图只到画面区，建场景时远景框还会被夹回来），`
      + `所以图上画的、blend 里的地面，都只到 <b>${fmt(c.fw)} × ${fmt(c.fh)} m</b>。`
    : "";
  return `<p class="hint warn">⚠ 远景框${cn}顶到地图边界，被裁短了 —— 所以图上它不再以活动区为中心，四边余量不一样是正常的。${sp}</p>`;
}

// 能走范围被地图画面区切掉时也要说清楚（切掉的那块没有地面）。<2 m 属取整噪声，不报。
function actHint(e) {
  const dx = Math.round((e.raw.x1 - e.raw.x0) - e.aw);
  const dy = Math.round((e.raw.y1 - e.raw.y0) - e.ah);
  if (dx < 2 && dy < 2) return "";
  const parts = [];
  if (dx >= 2) parts.push("宽 " + fmt(dx) + " m");
  if (dy >= 2) parts.push("高 " + fmt(dy) + " m");
  return `<p class="hint warn">⚠ 能走范围有 ${parts.join(" / ")} 落在地图画面区外面 —— `
    + `那块没有高度图、场景里也没有地面（build 时会夹掉），实际能走 = <b>${fmt(e.aw)} × ${fmt(e.ah)} m</b>。</p>`;
}

function cutNames(cut) {
  if (!cut) return "";
  const n = [];
  if (cut.left) n.push("左");
  if (cut.right) n.push("右");
  if (cut.top) n.push("上");
  if (cut.bottom) n.push("下");
  if (!n.length) return "";
  return n.length === 4 ? "四边" : n.join("、") + "边";
}

// 远景框按地图边界裁剪（与构建侧 tools/scene_bounds.py **同一规则**：夹进地图框 → 向内取 128 →
// 只有活动区 P 会被切到时才外扩）。`p` = 能走矩形 {x0,y0,x1,y1}，必须用**真实矩形**，
// 不能用"以中心为原点 + 宽高"近似 —— 据点 P 的中心和 x/y 常常差几十米，会多切/少切一格。
// 🔴 最后再硬夹一道地图框：高度图只覆盖到画面区，`scene_terrain.build()` 也会把框夹回去 ——
//    所以「图上画的框」=「blend 里的地面」=「高度图范围」，三个数必须一模一样（用户 2026-11-07 要求）。
function clampFar(x, y, fw, fh, p) {
  const b = EXTENT && EXTENT.map;
  const none = { left: false, right: false, bottom: false, top: false };
  if (!b || b.length < 4) return { x: x, y: y, fw: fw, fh: fh, cut: none, spill: 0 };
  const L0 = x - fw / 2, R0 = x + fw / 2, B0 = y - fh / 2, T0 = y + fh / 2;
  if (!(L0 < b[0] || B0 < b[1] || R0 > b[2] || T0 > b[3])) return { x: x, y: y, fw: fw, fh: fh, cut: none, spill: 0 };
  const Q = 128;
  let L = Math.ceil(Math.max(L0, b[0]) / Q) * Q, B = Math.ceil(Math.max(B0, b[1]) / Q) * Q;
  let R = Math.floor(Math.min(R0, b[2]) / Q) * Q, T = Math.floor(Math.min(T0, b[3]) / Q) * Q;
  L = Math.min(L, Math.floor(p.x0 / Q) * Q); B = Math.min(B, Math.floor(p.y0 / Q) * Q);
  R = Math.max(R, Math.ceil(p.x1 / Q) * Q);  T = Math.max(T, Math.ceil(p.y1 / Q) * Q);
  // 记下哪几条边真的被裁短了（图上要写明白，否则"两个框不同心"看着像 bug）
  const cut = { left: L > L0 + 1e-6, right: R < R0 - 1e-6, bottom: B > B0 + 1e-6, top: T < T0 - 1e-6 };
  // 规格框伸出地图画面区的量（要报给用户：这一段既没地形也没贴图）
  const spill = Math.max(0, b[0] - L, R - b[2], b[1] - B, T - b[3]);
  L = Math.max(L, b[0]); B = Math.max(B, b[1]);
  R = Math.min(R, b[2]); T = Math.min(T, b[3]);
  return { x: (L + R) / 2, y: (B + T) / 2, fw: R - L, fh: T - B, cut: cut, spill: spill };
}

// 地图画面区边界（官方地图有画的那一片）—— 远景框不得超出
function drawExtent(g) {
  const b = EXTENT && EXTENT.map;
  if (!b || b.length < 4) return;
  const x0 = px(b[0]), x1 = px(b[2]), y0 = py(b[3]), y1 = py(b[1]);
  el("rect", { x: x0, y: y0, width: x1 - x0, height: y1 - y0, class: "extent-line" }, g);
  if (state.sel) return;   // 选中场景时那两行字已经写了"被地图边界裁剪"，这条灰字就多余且会压字
  // 标签挂到离画面中心最近的那条边上：放大看某个场景时边界常常只露出一条线，
  // 固定在左上角会跑到屏幕外，用户就只剩一条莫名其妙的线了（2026-11-07）。
  const cx = state.view.x + state.view.w / 2, cy = state.view.y + state.view.h / 2;
  const mid = [[x0, (y0 + y1) / 2], [x1, (y0 + y1) / 2], [(x0 + x1) / 2, y0], [(x0 + x1) / 2, y1]];
  let best = mid[0], bd = Infinity;
  for (const m of mid) {
    const d = (m[0] - cx) * (m[0] - cx) + (m[1] - cy) * (m[1] - cy);
    if (d < bd) { bd = d; best = m; }
  }
  const t = text(g, best[0], best[1] - unitFor(7), "地图边界（远景框不得超出）", "extent-lbl", "middle");
  t.style.fontSize = unitFor(13).toFixed(2) + "px";
  // 夹进视口：放大看某个场景时边界常常只露出一条线，标签跟着线跑出屏幕就白写了
  const m = unitFor(8), w = t.getComputedTextLength ? t.getComputedTextLength() : 0;
  const vx0 = state.view.x + m + w / 2, vx1 = state.view.x + state.view.w - m - w / 2;
  t.setAttribute("x", (vx0 <= vx1 ? Math.min(Math.max(best[0], vx0), vx1) : (vx0 + vx1) / 2).toFixed(2));
  const vy0 = state.view.y + unitFor(52), vy1 = state.view.y + state.view.h - m;   // 52 = 让开左上角工具栏
  t.setAttribute("y", (vy0 <= vy1 ? Math.min(Math.max(best[1] - unitFor(7), vy0), vy1) : (vy0 + vy1) / 2).toFixed(2));
}

function drawTFrames(g) {
  if (!state.showAllT) return;
  if (state.tab === "settle") {
    for (const p of SETTLE) {
      if (state.sel && state.sel.kind === "settle" && state.sel.id === p.code) continue;
      const e = sceneExtent(p);
      sceneBox(g, e, false);
    }
  }
  if (state.tab === "wild") {
    for (const w of WILDS) {
      if (state.sel && state.sel.kind === "wild" && state.sel.id === w.id) continue;
      const e = sceneExtent(w);
      sceneBox(g, e, false);
    }
  }
}

function drawMarks(g) {
  // 放大到房间级（view.w 很小）时，据点名会按 --k 被撑到几十像素、盖住房间标签 → 深放大时不画地名
  const deep = state.view.w < 220;
  for (const p of SETTLE) {
    const x = px(p.x), y = py(p.y);
    if (!deep) marker(g, p, x, y);   // 深放大时连据点图标也不画（星星会被放大成一大块，挡住房间）
    if (!deep && (state.tab === "settle" || state.tab === "overview" || state.tab === "cover")) {
      const cls = (p.tier === "city" || p.tier === "castle") ? "lbl big click" : "lbl small click";
      const t = text(g, x + 10, y - 8, p.name, cls);
      t.addEventListener("click", ev => { ev.stopPropagation(); select({ kind: "settle", id: p.code }); });
    }
  }
  if (state.tab === "wild" || state.tab === "overview" || state.tab === "cover") {
    for (const w of WILDS) {
      const x = px(w.x), y = py(w.y);
      el("circle", { cx: x, cy: y, r: 4.5, class: "anchor" }, g);
      const t = text(g, x + 8, y - 8, w.id.replace("wild_", "W"), "lbl wild click");
      t.addEventListener("click", ev => { ev.stopPropagation(); select({ kind: "wild", id: w.id }); });
    }
  }
}

function drawSelected(g) {
  if (state.edit) drawEditHandles(g);
  if (!state.sel) return;
  if (state.sel.kind === "settle") {
    const p = byCode.get(state.sel.id);
    if (!p) return;
    const e = sceneExtent(p);
    sceneBox(g, e, true);
  } else {
    const w = byWild.get(state.sel.id);
    if (!w) return;
    const e = sceneExtent(w);
    sceneBox(g, e, true);
  }
}

// 含室内场景的房间：点了据点就画（没有额外开关，取消选中就消失）
function drawRooms(g, code) {
  const list = ROOMS.filter(r => r.code === code);
  const k = Math.max(0.12, Math.min(1, state.view.w / MAP_W));
  // 方块跟着 --k 走 → 屏幕上恒定约 6 px（镇里 10 间房挨得近，画大了会糊成一坨）
  const s = 14 * k;
  // 标签密度判据：按"相邻两个房间在屏幕上的间距"决定显不显示，
  // 而不是死盯缩放比例 —— 圣丹尼斯房间铺得开（21 间 / 800 m），黑水镇挤成一团，
  // 同一个缩放值对两者意义完全不同。
  const rect = SVG.getBoundingClientRect();
  const pxPerUnit = (rect.width || 1100) / state.view.w;
  const xs = list.map(r => px(r.x)), ys = list.map(r => py(r.y));
  const span = Math.max(1, Math.max.apply(null, xs) - Math.min.apply(null, xs),
                        Math.max.apply(null, ys) - Math.min.apply(null, ys));
  const spacingPx = (span / Math.max(1, list.length - 1)) * pxPerUnit;
  const showLbl = spacingPx >= 16;
  // 屏幕恒定字号：CSS 的 --k 在深放大时被 clamp 到 0.12 就不再缩小，字会越放越大，
  // 所以这里直接按「屏幕像素 / 每单位像素」写死字号（13 px 高、光晕 4 px）。
  const fs = (13 / pxPerUnit).toFixed(3);
  const sw = (4 / pxPerUnit).toFixed(3);
  const labeled = new Set();
  list.forEach((r, i) => {
    const x = px(r.x), y = py(r.y);
    const box = el("rect", { x: (x - s / 2).toFixed(1), y: (y - s / 2).toFixed(1),
                             width: s.toFixed(1), height: s.toFixed(1), rx: (s * 0.2).toFixed(1),
                             class: "room-mark" }, g);
    const t = el("title", {}, box);
    t.textContent = `${r.pkg}${r.host ? "\n宿主建筑：" + r.host : ""}\n世界坐标 (${r.x}, ${r.y})`;
    if (!showLbl) return;
    const nm = r.host || r.pkg;
    if (labeled.has(nm)) return;   // 同一栋楼里的两个室内（理发 + 照相）只标一次
    labeled.add(nm);
    // 标签去掉据点前缀（bla_new_bank_ext → new_bank_ext）：镇里房间挤，短名才不互相压
    const short = nm.indexOf(code + "_") === 0 ? nm.slice(code.length + 1) : nm;
    const right = (i % 2 === 0);
    const dy = ((i % 4) - 1.5) * 20 * k;
    // 标签与方块的间距按**屏幕像素**算（方块半个宽 + 5 px），否则深放大时会压在方块上
    const off = s * 0.5 + 5 / pxPerUnit;
    const lb = text(g, x + (right ? off : -off), y + 4.5 / pxPerUnit + dy,
                    short, "lbl room", right ? "start" : "end");
    lb.style.fontSize = fs + "px";
    lb.style.strokeWidth = sw + "px";
  });
  const p = byCode.get(code);
  if (list.length && p) {
    // 挂在远景框上边**外面**：框内顶上那行是「远景 xx × yy m」，两行都在框内会压在一起
    const e = sceneExtent(p);
    const c = clampFar(e.cx, e.cy, e.fw, e.fh, e);
    const fby = py(c.y) - c.fh / MY / 2;
    const hd = text(g, px(p.x) + 10, Math.max(state.view.y + (58 / pxPerUnit), fby - 8),
                    `含室内场景的房间 ×${list.length}（放大看名字 / 悬停看坐标）`, "lbl room-head");
    hd.style.fontSize = (15 / pxPerUnit).toFixed(3) + "px";
    hd.style.strokeWidth = (5 / pxPerUnit).toFixed(3) + "px";
  }
}

function drawIssues(g) {
  if (!state.showIssues) return;
  const dg = polyPath(GAPS);
  if (dg) el("path", { d: dg, class: "gap", "fill-rule": "evenodd" }, g);
  const dv = polyPath(OVLS);
  if (dv) el("path", { d: dv, class: "ovl", "fill-rule": "evenodd" }, g);
}

function render() {
  const go = $("#l-outside"), gf = $("#l-frames"), gs = $("#l-settle"), gw = $("#l-wild"), gi = $("#l-issues"), gr = $("#l-rooms"), gx = $("#l-selected"), gm = $("#l-marks");
  const ge = $("#l-extent");
  clear(go); clear(gf); clear(gs); clear(gw); clear(gi); clear(gr); clear(gx); clear(gm); if (ge) clear(ge);
  drawIssues(gi);
  drawOutside(go); if (ge) drawExtent(ge); drawTFrames(gf);
  // 选中任何东西以后，其他区域一律淡化让路（2026-11-07：不然满屏矩形，分不清选的是谁）
  const dim = !!state.sel;
  if (state.tab === "overview") { drawSettle(gs, true); drawWild(gw, true); }
  if (state.tab === "settle") { drawSettle(gs, dim); }
  if (state.tab === "wild") { drawWild(gw, dim); drawSettle(gs, true); }
  if (state.tab === "cover") { drawSettle(gs, dim); drawWild(gw, dim); }
  drawMarks(gm);
  // 含室内场景的房间：只在点选了据点时出现
  if (state.sel && state.sel.kind === "settle") drawRooms(gr, state.sel.id);
  drawSelected(gx); drawSnapGuides(gx);
  if (state.mode === "rect" && state.drawStart && state.draft.length) {
    const a = state.drawStart, b = state.draft[0];
    el("rect", { x: px(Math.min(a[0], b[0])), y: py(Math.max(a[1], b[1])),
      width: Math.abs(px(b[0]) - px(a[0])), height: Math.abs(py(b[1]) - py(a[1])), class: "draft" }, gx);
  }
}

function detailDefault() {
  return `<h2>63 张地图</h2>
    <div class="row"><span>据点自己的地图</span><b>${SETTLE.length}</b></div>
    <div class="row"><span>野地地图</span><b>${WILDS.length}</b></div>
    <div class="row"><span>瓜玛岛</span><b>2</b></div>
    <div class="row"><span>合计</span><b>${SETTLE.length + WILDS.length + 2}</b></div>
    <div class="row"><span>有效地图（陆地 + 码头）</span><b>${CHECK.valid_km2.toFixed(2)} km²</b></div>
    <div class="row"><span>野地 ∩ 据点（设计内）</span><b>${(CHECK.wild_settle_overlap_km2 || 0).toFixed(2)} km²</b></div>
    <div class="row"><span>野地矩形合计（含地图外空白）</span><b>${(CHECK.wild_km2 || 0).toFixed(2)} km²</b></div>
    <div class="row"><span>没盖到的</span><b>${CHECK.missing_km2.toFixed(3)} km²</b></div>
    <p class="hint">野地是 ${WILDS.length} 个横平竖直的矩形；矩形边角会盖到「地图外」的空白，那部分只是背景。红色 = 地图区里没被任何野地覆盖的缝（拖相邻边补上），橙色 = 野地互相重叠的地方。</p>`;
}

function renderDetail() {
  const d = $("#detail");
  if (!state.sel) { d.innerHTML = detailDefault(); return; }
  if (state.sel.kind === "settle") {
    const p = byCode.get(state.sel.id);
    const tierName = { city: "城市", castle: "城堡", village: "村庄/营地/点位", hideout: "藏身处" }[p.kind] || p.tier;
    const tCell = state.edit
      ? `<input class="editnum" id="inT" type="number" step="128" value="${p.AW || p.T}">`
      : `<b>${fmt(p.AW || p.T)} × ${fmt(p.AH || p.T)} m</b>`;
    const wCell = state.edit
      ? `<input class="editnum" id="inW" type="number" step="128" value="${p.W}">`
      : `<b>${fmt(p.W)} m</b>`;
    d.innerHTML = `<h2>${p.name} <span style="font-size:12px;color:var(--muted)">${tierName}</span></h2>
      <div class="row"><span>玩家活动区</span>${tCell}</div>
      <div class="row"><span>能走面积 P</span><b id="pArea">${rectArea(p).toFixed(3)} km²</b></div>
      <div class="row"><span>P 最宽</span><b>${fmt(p.P_max_m)} m</b></div>
      <div class="row"><span>每边外扩</span>${wCell}</div>
      ${(() => {
        const e = sceneExtent(p);
        const c = clampFar(e.cx, e.cy, e.fw, e.fh, e);
        const ak = e.aw * e.ah / 1e6, fk = c.fw * c.fh / 1e6;
        const pc = 100 * ak / fk;
        const cn = cutNames(c.cut);
        return `<div class="row"><span>远景范围（实际 = 图上 = blend 地面）</span><b id="oVal">${fmt(c.fw)} × ${fmt(c.fh)} m</b></div>
          ${(Math.abs(c.fw - e.fw) > 0.5 || Math.abs(c.fh - e.fh) > 0.5)
             ? `<div class="row"><span>远景框（配置值）</span><b>${fmt(e.fw)} × ${fmt(e.fh)} m</b></div>` : ""}
          <div class="row"><span>活动区面积</span><b>${ak.toFixed(2)} km²</b></div>
          <div class="row"><span>远景框面积</span><b>${fk.toFixed(2)} km²</b></div>
          <div class="row"><span>活动区占比</span><b>${pc.toFixed(1)}%</b></div>
          <div class="row"><span>外圈（只做远景）</span><b>${(fk - ak).toFixed(2)} km² · ${(100 - pc).toFixed(1)}%</b></div>`
          + cutHint(c, e) + actHint(e);
      })()}
      <div class="row"><span>场景中心</span><b>${p.x.toFixed(0)}, ${p.y.toFixed(0)}</b></div>
      ${(() => {
        const rs = ROOMS.filter(r => r.code === p.code);
        if (!rs.length) return "";
        return `<div class="group-head" style="margin-top:10px">含室内场景的房间<span>${rs.length}</span></div>`
          + rs.map(r => `<div class="roomrow" data-x="${r.x}" data-y="${r.y}" title="点一下放大到这间（${r.pkg}）"><b>${r.host || r.pkg}</b><span>${r.x.toFixed(0)}, ${r.y.toFixed(0)}</span></div>`).join("");
      })()}
      ${state.edit ? '<p class="hint">拖方框 8 个把手改可行走范围；中间圆点整体挪。数字直接改活动区 / 外扩（步长 128）。</p>'
                   : '<p class="hint">玩家活动区 = 玩家走得到的地方，走到边上被挡住；每边外扩 = 活动区外面再铺多宽的远景（只做背景）。</p>'}
      ${state.edit ? '<div class="tools" style="padding:8px 0 0"><button class="ctrl" id="redraw">重画矩形</button><button class="ctrl" id="resetOne">重置这个</button></div>' : ''}`;
    d.querySelectorAll(".roomrow").forEach(el2 =>
      el2.addEventListener("click", () => focusRoom(+el2.dataset.x, +el2.dataset.y)));
    if (state.edit) {
      $("#redraw").addEventListener("click", () => { state.mode = "rect"; state.drawStart = null; state.draft = []; });
      $("#inT").addEventListener("input", e => {
        p.AW = p.AH = p.T = +e.target.value || 0; markDirty(p);
        $("#oVal").textContent = `${fmt(p.AW + 2 * p.W)} × ${fmt(p.AH + 2 * p.W)} m`; render(); persist();
      });
      $("#inW").addEventListener("input", e => {
        p.W = +e.target.value || 0; markDirty(p);
        $("#oVal").textContent = `${fmt((p.AW || p.T) + 2 * p.W)} × ${fmt((p.AH || p.T) + 2 * p.W)} m`; render(); persist();
      });
      $("#resetOne").addEventListener("click", () => resetOne());
    }
    return;
  }
  const w = byWild.get(state.sel.id);
  const act = sceneExtent(w);
  const wCell = state.edit
    ? `<input class="editnum" id="inW" type="number" step="128" value="${w.W}">`
    : `<b>${fmt(w.W)} m</b>`;
  d.innerHTML = `<h2>${w.id.replace("wild_", "W")} <span style="font-size:12px;color:var(--muted)">野地</span></h2>
    <div class="row"><span>玩家活动区</span><b>${fmt(act.aw)} × ${fmt(act.ah)} m</b></div>
    <div class="row"><span>形状</span><b>${w.isRect ? "矩形" : "多边形"}</b></div>
    <div class="row"><span>能走面积 P</span><b id="pArea">${polyArea(w.P[0]).toFixed(3)} km²</b></div>
    <div class="row"><span>每边外扩</span>${wCell}</div>
    ${(() => {
      const c = clampFar(act.cx, act.cy, act.fw, act.fh, act);
      const ak = act.aw * act.ah / 1e6, fk = c.fw * c.fh / 1e6;
      const pc = 100 * ak / fk;
      const cn = cutNames(c.cut);
      return `<div class="row"><span>远景范围（实际 = 图上 = blend 地面）</span><b id="oVal">${fmt(c.fw)} × ${fmt(c.fh)} m</b></div>
          ${(Math.abs(c.fw - act.fw) > 0.5 || Math.abs(c.fh - act.fh) > 0.5)
             ? `<div class="row"><span>远景框（配置值）</span><b>${fmt(act.fw)} × ${fmt(act.fh)} m</b></div>` : ""}
        <div class="row"><span>活动区面积</span><b>${ak.toFixed(2)} km²</b></div>
        <div class="row"><span>远景框面积</span><b>${fk.toFixed(2)} km²</b></div>
        <div class="row"><span>活动区占比</span><b>${pc.toFixed(1)}%</b></div>
        <div class="row"><span>外圈（只做远景）</span><b>${(fk - ak).toFixed(2)} km² · ${(100 - pc).toFixed(1)}%</b></div>`
        + cutHint(c, act) + actHint(act);
    })()}
    <div class="row"><span>中心</span><b>${w.x.toFixed(0)}, ${w.y.toFixed(0)}</b></div>
    ${state.edit ? '<p class="hint">矩形：拖 8 个把手改大小、中间圆点整体挪；多边形：拖顶点。活动区由矩形自动算（取整到 128），改形状就会跟着变。新建野地看左上角「＋新建野地」。</p>'
                 : '<p class="hint">野地的活动区就是这张矩形（走到边回大地图），外面那一圈是远景。矩形里遇到据点会提示是否进入据点。</p>'}
    ${state.edit ? '<div class="tools" style="padding:8px 0 0"><button class="ctrl" id="redraw">重画矩形</button><button class="ctrl" id="toRect">按外接矩形</button><button class="ctrl danger" id="delWild">删除这个野地</button><button class="ctrl" id="resetOne">重置这个</button></div>' : ''}`;
  if (state.edit) {
    $("#redraw").addEventListener("click", () => { state.mode = "rect"; state.drawStart = null; state.draft = []; });
    $("#toRect").addEventListener("click", () => {
      const poly = w.P[0];
      const xs = poly.map(q => q[0]), ys = poly.map(q => q[1]);
      setRectW(w, [Math.min.apply(null, xs), Math.min.apply(null, ys), Math.max.apply(null, xs), Math.max.apply(null, ys)]);
      markDirty(w); persist(); render(); renderDetail(); renderList();
    });
    $("#inW").addEventListener("input", e => {
      w.W = +e.target.value || 0; markDirty(w);
      const a = sceneExtent(w);
      $("#oVal").textContent = `${fmt(a.fw)} × ${fmt(a.fh)} m`; render(); persist();
    });
    $("#delWild").addEventListener("click", () => {
      if (!confirm("删除野地 " + w.id + "？导出后总数会少一张。")) return;
      const i = WILDS.findIndex(x => x.id === w.id);
      if (i >= 0) WILDS.splice(i, 1);
      byWild.delete(w.id);
      if (state.addedW.has(w.id)) state.addedW.delete(w.id); else state.deletedW.add(w.id);
      state.dirtyW.delete(w.id);
      state.sel = null;
      persist(); render(); renderDetail(); renderList(); updateBadge(); updateCounts(); updateCounts();
    });
    $("#resetOne").addEventListener("click", () => resetOne());
  }
}

function resetOne() {
  if (!state.sel) return;
  if (state.sel.kind === "settle") {
    const p = byCode.get(state.sel.id), o = ORIG.S.find(x => x.code === state.sel.id);
    Object.assign(p, JSON.parse(JSON.stringify(o)));
    state.dirtyS.delete(p.code);
  } else {
    const w = byWild.get(state.sel.id), o = ORIG.W.find(x => x.id === state.sel.id);
    Object.assign(w, JSON.parse(JSON.stringify(o)));
    state.dirtyW.delete(w.id);
  }
  persist(); render(); renderDetail(); renderList();
}

function select(sel) {
  // 再点一次同一个 = 取消选中（2026-11-04：原来"点地图任意处就取消"太容易误触，
  // 滚轮放大时手一抖选中就没了 —— 现在只有「再点它一下 / 按 Esc」才取消）
  if (sel && state.sel && sel.kind === state.sel.kind && sel.id === state.sel.id) {
    state.sel = null;
    render(); renderDetail(); renderList();
    return;
  }
  state.sel = sel;
  render(); renderDetail(); renderList();
  if (sel.kind === "settle") {
    const p = byCode.get(sel.id);
    if (p) {
      const e = sceneExtent(p);
      const c = clampFar(e.cx, e.cy, e.fw, e.fh, e);
      focusOnBBox([c.x - c.fw / 2, c.y - c.fh / 2, c.x + c.fw / 2, c.y + c.fh / 2]);
    }
  } else {
    const w = byWild.get(sel.id);
    if (w) {
      const e = sceneExtent(w);
      // 按**裁剪后**的远景框取景（2026-11-07）：按未裁的算，框会被地图边界推出去，底边跑到屏幕外
      const c = clampFar(e.cx, e.cy, e.fw, e.fh, e);
      focusOnBBox([c.x - c.fw / 2, c.y - c.fh / 2, c.x + c.fw / 2, c.y + c.fh / 2]);
    }
  }
}

function renderList() {
  const list = $("#list");
  list.innerHTML = "";
  function group(title, n) {
    const h = document.createElement("div");
    h.className = "group-head";
    h.innerHTML = `${title}<span>${n}</span>`;
    list.appendChild(h);
  }
  if (state.tab === "wild") {
    group("野地地图", WILDS.length);
    for (const w of WILDS) {
      const b = document.createElement("button");
      b.className = "rowbtn" + (state.sel && state.sel.kind === "wild" && state.sel.id === w.id ? " active" : "");
      b.innerHTML = `<i class="dot" style="background:var(--wild)"></i><span class="name">${w.id.replace("wild_", "W")}</span><span class="meta">${Number(w.P_area_km2).toFixed(2)} km² / 活动区 ${fmt(sceneExtent(w).aw)}</span>`;
      b.addEventListener("click", () => select({ kind: "wild", id: w.id }));
      list.appendChild(b);
    }
    return;
  }
  const order = [["city", "城市"], ["castle", "城堡"], ["village", "村庄 / 营地 / 点位"], ["hideout", "藏身处"]];
  for (const [kind, title] of order) {
    const items = SETTLE.filter(p => p.kind === kind);
    if (!items.length) continue;
    group(title, items.length);
    for (const p of items) {
      const b = document.createElement("button");
      b.className = "rowbtn" + (state.sel && state.sel.kind === "settle" && state.sel.id === p.code ? " active" : "");
      const color = kind === "city" ? "var(--city)" : kind === "castle" ? "var(--castle)" : kind === "hideout" ? "var(--hideout)" : "var(--village)";
      b.innerHTML = `<i class="dot" style="background:${color}"></i><span class="name">${p.name}</span><span class="meta">${Number(p.P_area_km2).toFixed(2)} km² / 活动区 ${fmt(p.AW || p.T)}</span>`;
      b.addEventListener("click", () => select({ kind: "settle", id: p.code }));
      list.appendChild(b);
    }
  }
}

// ---------------------------------------------------------------- 编辑模式
function wx(sx) { return PROJ.x0 + sx / MAP_W * (PROJ.x1 - PROJ.x0); }
function wy(sy) { return PROJ.y1 - sy / MAP_H * (PROJ.y1 - PROJ.y0); }
function toSvg(evt) {
  const p = SVG.createSVGPoint(); p.x = evt.clientX; p.y = evt.clientY;
  return p.matrixTransform(SVG.getScreenCTM().inverse());
}
function rectOf(p) {
  const r = p.P[0];
  const xs = r.map(q => q[0]), ys = r.map(q => q[1]);
  return [Math.min.apply(null, xs), Math.min.apply(null, ys), Math.max.apply(null, xs), Math.max.apply(null, ys)];
}
function setRect(p, r) {
  p.P = [[[r[0], r[1]], [r[2], r[1]], [r[2], r[3]], [r[0], r[3]], [r[0], r[1]]]];
  p.P_area_km2 = Math.max(0, r[2] - r[0]) * Math.max(0, r[3] - r[1]) / 1e6;
  p.P_max_m = Math.max(r[2] - r[0], r[3] - r[1]);
}
function setRectW(w, r) {
  w.isRect = true;
  w.x = Math.round((r[0] + r[2]) / 2 * 10) / 10;     // 场景中心跟矩形中心走（标签画在中心）
  w.y = Math.round((r[1] + r[3]) / 2 * 10) / 10;
  w.P = [[[r[0], r[1]], [r[2], r[1]], [r[2], r[3]], [r[0], r[3]], [r[0], r[1]]]];
  w.P_area_km2 = Math.max(0, r[2] - r[0]) * Math.max(0, r[3] - r[1]) / 1e6;
  w.P_max_m = Math.max(r[2] - r[0], r[3] - r[1]);
}
function rectOfW(w) {
  const r = w.P[0];
  const xs = r.map(q => q[0]), ys = r.map(q => q[1]);
  return [Math.min.apply(null, xs), Math.min.apply(null, ys), Math.max.apply(null, xs), Math.max.apply(null, ys)];
}
function polyArea(poly) {
  let a = 0;
  for (let i = 0; i < poly.length; i++) {
    const p0 = poly[i], p1 = poly[(i + 1) % poly.length];
    a += p0[0] * p1[1] - p1[0] * p0[1];
  }
  return Math.abs(a) / 2 / 1e6;
}
function centroid(poly) {
  let x = 0, y = 0;
  poly.forEach(p => { x += p[0]; y += p[1]; });
  return [x / poly.length, y / poly.length];
}
function markDirty(item) {
  if (state.sel.kind === "settle") state.dirtyS.add(item.code); else state.dirtyW.add(item.id);
}
function snapXVal(v, selfCode) {
  if (!state.snap) { state.snapX = null; return v; }
  const tol = 30;
  let best = v, bd = tol;
  const cands = [];
  for (const q of SETTLE) { const r = rectOf(q); cands.push(r[0], r[2]); }
  for (const q of WILDS) { if (q.isRect && q.id !== selfCode) { const r = rectOfW(q); cands.push(r[0], r[2]); } }
  const self = byCode.get(selfCode);
  if (self) cands.push(self.x - self.T / 2, self.x + self.T / 2);
  for (const c of cands) { const d = Math.abs(v - c); if (d < bd) { bd = d; best = c; } }
  state.snapX = (best === v) ? null : best;
  return best;
}
function snapYVal(v, selfCode) {
  if (!state.snap) { state.snapY = null; return v; }
  const tol = 30;
  let best = v, bd = tol;
  const cands = [];
  for (const q of SETTLE) { const r = rectOf(q); cands.push(r[1], r[3]); }
  for (const q of WILDS) { if (q.isRect && q.id !== selfCode) { const r = rectOfW(q); cands.push(r[1], r[3]); } }
  const self = byCode.get(selfCode);
  if (self) cands.push(self.y - self.T / 2, self.y + self.T / 2);
  for (const c of cands) { const d = Math.abs(v - c); if (d < bd) { bd = d; best = c; } }
  state.snapY = (best === v) ? null : best;
  return best;
}
function snapPoint(x, y, selfId) {
  if (!state.snap) { state.snapX = state.snapY = null; return [x, y]; }
  const tol2 = 30 * 30;
  let best = null, bd = tol2;
  const test = (cx, cy) => { const d = (cx - x) ** 2 + (cy - y) ** 2; if (d < bd) { bd = d; best = [cx, cy]; } };
  for (const w of WILDS) {
    if (w.id === selfId) continue;
    for (const q of w.P[0]) test(q[0], q[1]);
  }
  for (const q of SETTLE) {
    const r = rectOf(q);
    test(r[0], r[1]); test(r[2], r[1]); test(r[2], r[3]); test(r[0], r[3]);
    test((r[0] + r[2]) / 2, r[1]); test((r[0] + r[2]) / 2, r[3]);
    test(r[0], (r[1] + r[3]) / 2); test(r[2], (r[1] + r[3]) / 2);
  }
  state.snapX = best ? best[0] : null;
  state.snapY = best ? best[1] : null;
  return best || [x, y];
}
function drawSnapGuides(g) {
  if (state.snapX == null && state.snapY == null) return;
  const vb = state.view;
  if (state.snapX != null) el("line", { x1: px(state.snapX), y1: vb.y, x2: px(state.snapX), y2: vb.y + vb.h, class: "guide" }, g);
  if (state.snapY != null) el("line", { x1: vb.x, y1: py(state.snapY), x2: vb.x + vb.w, y2: py(state.snapY), class: "guide" }, g);
}

function drawEditHandles(g) {
  if (!state.sel) return;
  if (state.sel.kind === "settle") {
    const p = byCode.get(state.sel.id); if (!p) return;
    const r = rectOf(p);
    const xs = [r[0], (r[0] + r[2]) / 2, r[2]], ys = [r[1], (r[1] + r[3]) / 2, r[3]];
    for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) {
      if (i === 1 && j === 1) continue;
      const c = el("circle", { cx: px(xs[i]), cy: py(ys[j]), r: 5, class: "h" }, g);
      c.addEventListener("pointerdown", ev => {
        ev.stopPropagation();
        state.drag = { kind: "rect", i, j, start: toSvg(ev), orig: r.slice() };
        SVG.setPointerCapture(ev.pointerId);
      });
    }
    const m = el("circle", { cx: px((r[0] + r[2]) / 2), cy: py((r[1] + r[3]) / 2), r: 6, class: "hov" }, g);
    m.addEventListener("pointerdown", ev => {
      ev.stopPropagation();
      state.drag = { kind: "move", start: toSvg(ev), orig: r.slice() };
      SVG.setPointerCapture(ev.pointerId);
    });
  } else {
    const w = byWild.get(state.sel.id); if (!w) return;
    if (w.isRect) {
      const r = rectOfW(w);
      const xs = [r[0], (r[0] + r[2]) / 2, r[2]], ys = [r[1], (r[1] + r[3]) / 2, r[3]];
      for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) {
        if (i === 1 && j === 1) continue;
        const c = el("circle", { cx: px(xs[i]), cy: py(ys[j]), r: 5, class: "h" }, g);
        c.addEventListener("pointerdown", ev => {
          ev.stopPropagation();
          state.drag = { kind: "rectw", i, j, start: toSvg(ev), orig: r.slice() };
          SVG.setPointerCapture(ev.pointerId);
        });
      }
      const mm = el("circle", { cx: px((r[0] + r[2]) / 2), cy: py((r[1] + r[3]) / 2), r: 6, class: "hov" }, g);
      mm.addEventListener("pointerdown", ev => {
        ev.stopPropagation();
        state.drag = { kind: "movew", start: toSvg(ev), orig: r.slice() };
        SVG.setPointerCapture(ev.pointerId);
      });
      return;
    }
    const poly = w.P[0];
    poly.forEach((pt, i) => {
      const c = el("circle", { cx: px(pt[0]), cy: py(pt[1]), r: 5, class: "vh" }, g);
      c.addEventListener("pointerdown", ev => {
        ev.stopPropagation();
        state.drag = { kind: "vertex", i, start: toSvg(ev), orig: poly.map(q => q.slice()) };
        SVG.setPointerCapture(ev.pointerId);
      });
    });
    const c0 = centroid(poly);
    const m = el("circle", { cx: px(c0[0]), cy: py(c0[1]), r: 6, class: "hov" }, g);
    m.addEventListener("pointerdown", ev => {
      ev.stopPropagation();
      state.drag = { kind: "movepoly", start: toSvg(ev), orig: poly.map(q => q.slice()) };
      SVG.setPointerCapture(ev.pointerId);
    });
  }
}
function updateAreaReadout() {
  const el2 = document.getElementById("pArea");
  if (!el2 || !state.sel) return;
  if (state.sel.kind === "settle") el2.textContent = rectArea(byCode.get(state.sel.id)).toFixed(3) + " km²";
  else el2.textContent = polyArea(byWild.get(state.sel.id).P[0]).toFixed(3) + " km²";
}
function rectArea(p) { const r = rectOf(p); return Math.max(0, r[2] - r[0]) * Math.max(0, r[3] - r[1]) / 1e6; }

SVG.addEventListener("pointerdown", ev => {
  if (!state.edit || state.drag) return;
  const sv0 = toSvg(ev);
  if (state.mode === "rect") {
    state.drawStart = [wx(sv0.x), wy(sv0.y)];
    state.draft = [state.drawStart.slice()];
    SVG.setPointerCapture(ev.pointerId);
    return;
  }
  const sv = toSvg(ev);
  state.drag = { kind: "pan", start: sv, orig: { x: state.view.x, y: state.view.y } };
  SVG.setPointerCapture(ev.pointerId);
});
SVG.addEventListener("pointermove", ev => {
  if (state.mode === "rect" && state.drawStart) {
    const sv0 = toSvg(ev);
    state.draft = [[wx(sv0.x), wy(sv0.y)]];
    render(); return;
  }
  const d = state.drag; if (!d) return;
  const sv = toSvg(ev);
  if (d.kind === "pan") {
    state.view.x = d.orig.x - (sv.x - d.start.x);
    state.view.y = d.orig.y - (sv.y - d.start.y);
    applyView(); return;
  }
  const dx = wx(sv.x) - wx(d.start.x), dy = wy(sv.y) - wy(d.start.y);
  if (d.kind === "rect") {
    const p = byCode.get(state.sel.id), r = d.orig.slice();
    if (d.i === 0) r[0] = snapXVal(d.orig[0] + dx, p.code); else if (d.i === 2) r[2] = snapXVal(d.orig[2] + dx, p.code);
    if (d.j === 0) r[1] = snapYVal(d.orig[1] + dy, p.code); else if (d.j === 2) r[3] = snapYVal(d.orig[3] + dy, p.code);
    if (r[2] - r[0] < 30 || r[3] - r[1] < 30) return;
    setRect(p, r); markDirty(p);
  } else if (d.kind === "move") {
    const p = byCode.get(state.sel.id);
    setRect(p, [d.orig[0] + dx, d.orig[1] + dy, d.orig[2] + dx, d.orig[3] + dy]); markDirty(p);
  } else if (d.kind === "rectw") {
    const w = byWild.get(state.sel.id), r = d.orig.slice();
    if (d.i === 0) r[0] = snapXVal(d.orig[0] + dx, w.id); else if (d.i === 2) r[2] = snapXVal(d.orig[2] + dx, w.id);
    if (d.j === 0) r[1] = snapYVal(d.orig[1] + dy, w.id); else if (d.j === 2) r[3] = snapYVal(d.orig[3] + dy, w.id);
    if (r[2] - r[0] < 30 || r[3] - r[1] < 30) return;
    setRectW(w, r); markDirty(w);
  } else if (d.kind === "movew") {
    const w = byWild.get(state.sel.id);
    setRectW(w, [d.orig[0] + dx, d.orig[1] + dy, d.orig[2] + dx, d.orig[3] + dy]); markDirty(w);
  } else if (d.kind === "vertex") {
    const w = byWild.get(state.sel.id);
    const sp = snapPoint(d.orig[d.i][0] + dx, d.orig[d.i][1] + dy, w.id);
    w.P[0][d.i] = [sp[0], sp[1]];
    w.P_area_km2 = polyArea(w.P[0]); markDirty(w);
  } else if (d.kind === "movepoly") {
    const w = byWild.get(state.sel.id);
    w.P[0] = d.orig.map(q => [q[0] + dx, q[1] + dy]);
    w.P_area_km2 = polyArea(w.P[0]); markDirty(w);
  }
  render(); updateAreaReadout();
});
SVG.addEventListener("pointerup", () => {
  if (state.mode === "rect" && state.drawStart) {
    const a = state.drawStart, b = state.draft[0];
    if (a && b && state.sel) {
      const r = [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[0], b[0]), Math.max(a[1], b[1])];
      if (r[2] - r[0] > 50 && r[3] - r[1] > 50) {
        if (state.sel.kind === "settle") { const p = byCode.get(state.sel.id); setRect(p, r); state.dirtyS.add(p.code); }
        else { const w = byWild.get(state.sel.id); setRectW(w, r); state.dirtyW.add(w.id); }
        persist();
      }
    }
    state.mode = "select"; state.drawStart = null; state.draft = [];
    render(); renderDetail(); renderList(); return;
  }
  const d = state.drag; state.drag = null; state.snapX = state.snapY = null;
  if (d && d.kind !== "pan") { persist(); render(); }
});
SVG.addEventListener("wheel", ev => {
  // 2026-11-04：原来这里写了 `if (!state.edit) return` —— 非编辑模式滚轮完全没反应，
  // 用户只能靠按钮/缩放键。滚轮缩放本来就该随时可用（编辑模式也一样）。
  ev.preventDefault();
  const p = toSvg(ev);
  const k = ev.deltaY > 0 ? 1.15 : 1 / 1.15;
  const nw = Math.max(60, Math.min(MAP_W * 2, state.view.w * k));
  const nh = nw * (MAP_H / MAP_W);
  state.view.x = p.x - (p.x - state.view.x) * (nw / state.view.w);
  state.view.y = p.y - (p.y - state.view.y) * (nh / state.view.h);
  state.view.w = nw; state.view.h = nh; applyView();
  // 只有点着据点时才需要重画（房间标签的显隐/字号跟屏幕像素走）；否则保持轻量
  if ((state.sel && state.sel.kind === "settle") || state.view.w < 240) render();
}, { passive: false });

function allWildsToRect() {
  // 按行分块：17 个中心从北到南分 4 行（5/4/4/4），每行再按经度切开。
  // 行高 ∝ 该行块数 ⇒ 每块面积相等，且 17 块严丝合缝铺满整个地图框（重叠 0、空缝 0）。
  const order = WILDS.slice().sort((a, b) => (b.y - a.y) || (a.x - b.x));
  const n = order.length;
  const rows = Math.max(1, Math.round(Math.sqrt(n)));
  const base = Math.floor(n / rows), extra = n % rows;
  const counts = [];
  for (let i = 0; i < rows; i++) counts.push(base + (i < extra ? 1 : 0));
  const x0 = PROJ.x0, x1 = PROJ.x1, y0 = PROJ.y0, y1 = PROJ.y1;
  const H = y1 - y0;
  let yTop = y1, idx = 0, changedN = 0;
  for (let r = 0; r < rows; r++) {
    const c = counts[r];
    const h = H * c / n;
    const yBot = yTop - h;
    const w = (x1 - x0) / c;
    for (let k = 0; k < c; k++) {
      const ww = byWild.get(order[idx++].id);
      const before = snapW(ww);
      setRectW(ww, [x0 + k * w, yBot, x0 + (k + 1) * w, yTop]);
      if (snapW(ww) !== before) { state.dirtyW.add(ww.id); changedN++; }
    }
    yTop = yBot;
  }
  persist(); render(); renderDetail(); renderList();
  alert("已切成 " + n + " 个等面积矩形（" + rows + " 行 " + counts.join("/") + "），铺满地图框、互不重叠。之后拖边继续调，会自动吸住邻居。");
}

function fitNeighbors() {
  const tol = 60;
  const arr = SETTLE.map(s => ({ s, r: rectOf(s), before: snapS(s) }));
  let moved = 0;
  for (let pass = 0; pass < 3; pass++) {
    for (let a = 0; a < arr.length; a++) {
      for (let b = 0; b < arr.length; b++) {
        if (a === b) continue;
        const A = arr[a].r, B = arr[b].r;
        const yOv = Math.min(A[3], B[3]) - Math.max(A[1], B[1]);
        const xOv = Math.min(A[2], B[2]) - Math.max(A[0], B[0]);
        if (yOv > 50) {
          const g1 = B[0] - A[2], g2 = A[0] - B[2];
          if (g1 >= -tol && g1 <= tol) { const m = (A[2] + B[0]) / 2; A[2] = m; B[0] = m; moved++; }
          else if (g2 >= -tol && g2 <= tol) { const m = (B[2] + A[0]) / 2; B[2] = m; A[0] = m; moved++; }
        }
        if (xOv > 50) {
          const g1 = B[1] - A[3], g2 = A[1] - B[3];
          if (g1 >= -tol && g1 <= tol) { const m = (A[3] + B[1]) / 2; A[3] = m; B[1] = m; moved++; }
          else if (g2 >= -tol && g2 <= tol) { const m = (B[3] + A[1]) / 2; B[3] = m; A[1] = m; moved++; }
        }
      }
    }
  }
  let n = 0;
  arr.forEach(({ s: st, r, before }) => {
    if (r[2] - r[0] > 30 && r[3] - r[1] > 30) {
      setRect(st, r);
      if (snapS(st) !== before) { state.dirtyS.add(st.code); n++; }
    }
  });
  persist(); render(); renderDetail(); renderList();
  alert("贴合完成：调整了 " + n + " 个据点的边（" + moved + " 处相邻边对齐）。没问题就点「导出改动」。");
}

const BUILD_ID = "__BUILD_ID__";
const LS_KEY = "lwn_rdr2_scene_overrides_v1";
let RESTORED = 0;
function dirtyCount() { return state.dirtyS.size + state.dirtyW.size + state.deletedW.size; }
function updateCounts() {
  const nS = SETTLE.length, nW = WILDS.length, tot = nS + nW + 2;
  const setTxt = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
  setTxt("nSet", nS); setTxt("nWild", nW); setTxt("nTotal", tot);
  const t1 = document.querySelector('.tab[data-tab="settle"]'); if (t1) t1.textContent = "据点 " + nS;
  const t2 = document.querySelector('.tab[data-tab="wild"]'); if (t2) t2.textContent = "野地 " + nW;
}
function updateBadge() {
  const b = document.getElementById("dirtyBadge"); if (!b) return;
  const n = dirtyCount();
  if (!n) { b.textContent = "无改动"; b.style.color = "var(--muted)"; return; }
  b.textContent = (state.exported ? "已导出 " : "改动 ") + n + " 项" + (state.exported ? "" : "（未导出）");
  b.style.color = state.exported ? "var(--muted)" : "var(--accent)";
}
function persist() {
  try { localStorage.setItem(LS_KEY, JSON.stringify({ id: BUILD_ID, data: buildExport() })); } catch (e) {}
  state.exported = false;
  updateBadge();
}
function snapS(p) {
  const r = rectOf(p);
  return JSON.stringify([r.map(v => Math.round(v * 10) / 10), p.T, p.W]);
}
function snapW(w) {
  return JSON.stringify([w.isRect ? "r" : "p", w.P[0].map(q => [Math.round(q[0] * 10) / 10, Math.round(q[1] * 10) / 10]), w.T, w.W, Math.round(w.x), Math.round(w.y)]);
}
function applyOverrides(d) {
  let n = 0;
  (d.deleted_wilds || []).forEach(id => {
    const w = byWild.get(id); if (!w) return;
    const i = WILDS.findIndex(x => x.id === id);
    if (i >= 0) WILDS.splice(i, 1);
    byWild.delete(id); state.addedW.delete(id); state.dirtyW.delete(id); state.deletedW.add(id); n++;
  });
  for (const code in (d.settlements || {})) {
    const p = byCode.get(code); if (!p) continue;
    const before = snapS(p);
    const o = d.settlements[code];
    if (o.rect) setRect(p, o.rect);
    if (o.T) { p.T = o.T; p.AW = o.T; p.AH = o.T; }
    if (o.W != null) p.W = o.W;
    if (snapS(p) !== before) { state.dirtyS.add(code); n++; }
  }
  for (const id in (d.wilds || {})) {
    let w = byWild.get(id);
    if (!w) {
      const o0 = d.wilds[id];
      const rr = o0.rect || null;
      const cx = (o0.x != null) ? o0.x : (rr ? (rr[0] + rr[2]) / 2 : 0);
      const cy = (o0.y != null) ? o0.y : (rr ? (rr[1] + rr[3]) / 2 : 0);
      w = { id, x: cx, y: cy, T: o0.T || 3072, W: (o0.W == null ? 1000 : o0.W), isRect: false,
            P: [[[cx - 800, cy - 600], [cx + 800, cy - 600], [cx + 800, cy + 600], [cx - 800, cy + 600], [cx - 800, cy - 600]]],
            P_area_km2: 1.92 };
      WILDS.push(w); byWild.set(id, w); state.addedW.add(id);
    }
    const before = snapW(w);
    const o = d.wilds[id];
    if (o.rect) setRectW(w, o.rect);
    else if (o.poly) { w.isRect = false; w.P = [o.poly.map(q => q.slice())]; w.P_area_km2 = polyArea(w.P[0]); }
    if (o.T) w.T = o.T;
    if (o.W != null) w.W = o.W;
    if (snapW(w) !== before) { state.dirtyW.add(id); n++; }
  }
  return n;
}
function restoreCache() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return 0;
    const obj = JSON.parse(raw);
    // 页面重新生成过（编号/基准可能变了）→ 旧缓存一律忽略，避免把过时图形套回来
    if (!obj || obj.id !== BUILD_ID) return 0;
    return applyOverrides(obj.data || {});
  } catch (e) { return 0; }
}

function buildExport() {
  const out = { version: 1, note: "regions_viewer 导出；放到 _scratch/settlement_plan/scene_overrides.json 后重跑 build_scene_division.py", settlements: {}, wilds: {} };
  state.dirtyS.forEach(code => {
    const p = byCode.get(code), r = rectOf(p);
    out.settlements[code] = { rect: r.map(v => Math.round(v * 10) / 10), T: p.T, W: p.W };
  });
  state.dirtyW.forEach(id => {
    const w = byWild.get(id);
    if (!w) return;
    const o = w.isRect
      ? { rect: rectOfW(w).map(v => Math.round(v * 10) / 10) }
      : { poly: w.P[0].map(q => [Math.round(q[0] * 10) / 10, Math.round(q[1] * 10) / 10]) };
    o.T = w.T; o.W = w.W;
    o.x = Math.round(w.x); o.y = Math.round(w.y);
    out.wilds[id] = o;
  });
  out.deleted_wilds = Array.from(state.deletedW);
  return out;
}

function bind() {
  $$(".tab").forEach(b => b.addEventListener("click", () => {
    state.tab = b.dataset.tab;
    state.sel = null;
    $$(".tab").forEach(x => x.classList.toggle("active", x === b));
    render(); renderDetail(); renderList(); resetView();
  }));
  // 点地图空白**不再取消选中**（2026-11-04 用户反馈：滚轮放大时手一抖，选中和房间层就没了）
  window.addEventListener("keydown", e => {
    if (e.key === "Escape" && state.sel) { state.sel = null; render(); renderDetail(); renderList(); }
  });
  $("#reset").addEventListener("click", resetView);
  $("#edit").addEventListener("click", () => {
    state.edit = !state.edit;
    $("#edit").textContent = "编辑模式：" + (state.edit ? "开" : "关");
    $("#editTools").style.display = state.edit ? "inline-flex" : "none";
    $("#newWild").style.display = state.edit ? "inline-block" : "none";
    if (!state.edit) { state.drag = null; resetView(); }
    render(); renderDetail();
  });
  $("#snapBtn").addEventListener("click", () => {
    state.snap = !state.snap;
    $("#snapBtn").textContent = "吸附：" + (state.snap ? "开" : "关");
  });
  $("#fitBtn").addEventListener("click", () => fitNeighbors());
  $("#polyRect").addEventListener("click", () => {
    let n = 0;
    for (const w of WILDS) {
      if (w.isRect) continue;
      const poly = w.P[0];
      const xs = poly.map(q => q[0]), ys = poly.map(q => q[1]);
      setRectW(w, [Math.min.apply(null, xs), Math.min.apply(null, ys), Math.max.apply(null, xs), Math.max.apply(null, ys)]);
      state.dirtyW.add(w.id); n++;
    }
    persist(); render(); renderDetail(); renderList(); updateBadge(); updateCounts();
    alert("已把 " + n + " 个多边形野地转成外接矩形（其它矩形没动）。");
  });
  $("#allRect").addEventListener("click", () => {
    if (!confirm("把 17 个野地全部改成各自的外接矩形？（之后可以逐个拖边调整）")) return;
    allWildsToRect();
  });
  $("#newWild").addEventListener("click", () => {
    let n = 18;
    while (byWild.has("wild_" + String(n).padStart(2, "0"))) n++;
    const id = "wild_" + String(n).padStart(2, "0");
    let cx = Math.round(wx(state.view.x + state.view.w / 2));
    let cy = Math.round(wy(state.view.y + state.view.h / 2));
    const halfW = 1000, halfH = 750;
    if (!Number.isFinite(cx)) { cx = 0; cy = 0; }
    // 只避免和已有的完全重合（重叠没关系，用户会自己拖）；每次错开 300 m
    for (let tries = 0; tries < 20; tries++) {
      const same = WILDS.some(x => {
        if (!x.isRect) return false;
        const r = rectOfW(x);
        return Math.abs(r[0] - (cx - halfW)) < 50 && Math.abs(r[1] - (cy - halfH)) < 50
            && Math.abs(r[2] - (cx + halfW)) < 50 && Math.abs(r[3] - (cy + halfH)) < 50;
      });
      if (!same) break;
      cx += 300; cy += 300;
    }
    const w = { id, x: cx, y: cy, T: 3072, W: 1000, O: 3072 + 2000, half_need_m: 1179, T_basis: "min", isRect: true,
                P: [[[cx - halfW, cy - halfH], [cx + halfW, cy - halfH], [cx + halfW, cy + halfH], [cx - halfW, cy + halfH], [cx - halfW, cy - halfH]]],
                P_area_km2: (2 * halfW) * (2 * halfH) / 1e6 };
    WILDS.push(w); byWild.set(id, w);
    state.addedW.add(id); state.dirtyW.add(id);
    state.tab = "wild";
    document.querySelectorAll(".tab").forEach(x => x.classList.toggle("active", x.dataset.tab === "wild"));
    select({ kind: "wild", id });
    persist(); render(); renderList(); renderDetail(); updateBadge(); updateCounts();
  });
  $("#zoomin").addEventListener("click", () => zoomView(1 / 1.3));
  $("#zoomout").addEventListener("click", () => zoomView(1.3));
  $("#exp").addEventListener("click", () => {
    const out = buildExport();
    if (!Object.keys(out.settlements).length && !Object.keys(out.wilds).length) { alert("没有改动可导出。"); return; }
    const blob = new Blob([JSON.stringify(out, null, 1)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "scene_overrides.json"; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 3000);
    state.exported = true; updateBadge();
    alert("已导出 " + (Object.keys(out.settlements).length + Object.keys(out.wilds).length) + " 项。把 scene_overrides.json 放到 _scratch/settlement_plan/ 后重跑 build_scene_division.py 才生效。");
  });
  $("#imp").addEventListener("click", () => $("#file").click());
  $("#file").addEventListener("change", e => {
    const f = e.target.files[0]; if (!f) return;
    const r = new FileReader();
    r.onload = () => {
      try {
        const n = applyOverrides(JSON.parse(r.result));
        state.exported = true;
        persist(); render(); renderDetail(); renderList();
        alert("已导入 " + n + " 项改动");
      } catch (err) { alert("JSON 读不了：" + err); }
    };
    r.readAsText(f);
  });
  $("#resetAll").addEventListener("click", () => {
    if (!confirm("把所有改动恢复成初始数据？")) return;
    SETTLE.length = 0; ORIG.S.forEach(x => SETTLE.push(JSON.parse(JSON.stringify(x))));
    WILDS.length = 0; ORIG.W.forEach(x => WILDS.push(JSON.parse(JSON.stringify(x))));
    byCode.clear(); SETTLE.forEach(x => byCode.set(x.code, x));
    byWild.clear(); WILDS.forEach(x => byWild.set(x.id, x));
    state.dirtyS.clear(); state.dirtyW.clear(); state.addedW.clear(); state.deletedW.clear();
    state.exported = true; state.sel = null;
    try { localStorage.removeItem(LS_KEY); } catch (e) {}
    updateBadge(); render(); renderDetail(); renderList(); updateCounts();
  });
  $("#iss").addEventListener("click", () => {
    state.showIssues = !state.showIssues;
    $("#iss").textContent = "缺口/重叠：" + (state.showIssues ? "开" : "关");
    render();
  });
  $("#tall").addEventListener("click", () => {
    state.showAllT = !state.showAllT;
    $("#tall").textContent = state.showAllT ? "只显示选中的活动区" : "显示全部活动区";
    render();
  });
}

applyView();
bind();
RESTORED = restoreCache();
if (RESTORED) state.exported = false;
render(); renderDetail(); renderList(); updateBadge();
window.addEventListener("beforeunload", e => {
  if (dirtyCount() > 0 && !state.exported) { e.preventDefault(); e.returnValue = ""; }
});
</script>
"""

BUILD_ID = hashlib.md5(("%.6f" % time.time()).encode()).hexdigest()[:8]
html = (HTML
        .replace("__BUILD_ID__", BUILD_ID)
        .replace("__SETTLE__", json.dumps(S, ensure_ascii=False))
        .replace("__WILDS__", json.dumps(WL, ensure_ascii=False))
        .replace("__OUTSIDE__", json.dumps(specs.get("outside", []), ensure_ascii=False))
        .replace("__EXTENT__", json.dumps(EXTENT, ensure_ascii=False))
        .replace("__GAPS__", json.dumps(specs.get("gaps", []), ensure_ascii=False))
        .replace("__OVERLAPS__", json.dumps(specs.get("overlaps", []), ensure_ascii=False))
        .replace("__PROJ__", json.dumps(PROJ, ensure_ascii=False))
        .replace("__ROOMS__", json.dumps(ROOMS, ensure_ascii=False))
        .replace("__CHECK__", json.dumps({k: check[k] for k in
                                          ("valid_km2", "cover_km2", "missing_km2",
                                           "settle_km2", "wild_km2",
                                           "wild_settle_overlap_km2",
                                           "settle_pair_max_overlap_m2",
                                           "wild_pair_max_overlap_m2")}, ensure_ascii=False))
        .replace("__NSET__", str(NSET))
        .replace("__NWILD__", str(NWILD))
        .replace("__TOTAL__", str(TOTAL)))

out = os.path.join(OUTDIR, "regions_viewer.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print("html", out, round(os.path.getsize(out) / 1024, 1), "KB",
      "settle", NSET, "wild", NWILD, "total", TOTAL)
