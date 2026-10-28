#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""过场解析总览页：数字 + 覆盖 + 已验证数据 + 链接

产物：export/story/cutscene/index.html
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CS = os.path.join(ROOT, 'export', 'story', 'cutscene')
OUT = os.path.join(CS, 'index.html')


def load():
    rows = []
    for f in glob.glob(os.path.join(CS, 'structure', 'cuts_*.json')):
        d = json.load(open(f, encoding='utf-8'))
        for s in d.get('scenes', []):
            rows.append(s)
    verified = []
    p = os.path.join(CS, 'shot_durations_verified.json')
    if os.path.exists(p):
        verified = json.load(open(p, encoding='utf-8'))
    cam = 0
    cam_seg = 0
    for f in glob.glob(os.path.join(CS, 'camera_stitched', '*', '*.json')):
        d = json.load(open(f, encoding='utf-8'))
        cam += 1
        cam_seg += len(d.get('segments') or [])
    sd = {}
    p2 = os.path.join(CS, 'shot_durations.json')
    if os.path.exists(p2):
        sd = json.load(open(p2, encoding='utf-8'))
    mt = {}
    p3 = os.path.join(CS, 'mission_timeline.json')
    if os.path.exists(p3):
        mt = json.load(open(p3, encoding='utf-8'))
    rh = {}
    p4 = os.path.join(CS, 'rhythm.json')
    if os.path.exists(p4):
        rh = json.load(open(p4, encoding='utf-8'))
    return rows, verified, cam, cam_seg, sd, mt, rh


def main():
    rows, verified, cam, cam_seg, sd, mt, rh = load()
    missions = {}
    for s in rows:
        m = missions.setdefault(s['mission'], dict(n=0, shots=0, dur=0.0))
        m['n'] += 1
        m['shots'] += s['n_shots']
        m['dur'] += s.get('duration_s') or 0
    tot_shots = sum(s['n_shots'] for s in rows)
    tot_dur = sum((s.get('duration_s') or 0) for s in rows)
    n_ok = sum(1 for v in sd.values() if v.get('ok'))

    ver_rows = ''.join(
        f"<tr><td>{v['cutscene']}</td><td class='num'>{v['shots']}</td>"
        f"<td>{' / '.join(str(x) for x in v['durs'])}</td>"
        f"<td class='num'>{v['sum']}</td><td class='num'>{v['scene']}</td></tr>"
        for v in verified)

    try:
        _t = json.load(open(os.path.join(CS, 'shot_durations_tiers.json'), encoding='utf-8'))
    except Exception:
        _t = {}
    tier_rows = ''.join(
        f"<tr><td>{lab}</td><td>{crit}</td><td class='num'>{len(_t.get(k, []))}</td>"
        f"<td class='num'>{sum(x['shots'] for x in _t.get(k, []))}</td></tr>"
        for k, lab, crit in (('A', 'A 级', '子集和 ≈ 总长（±0.35s）+ 条数=镜头数 + 未截断'),
                             ('B', 'B 级', '子集和 ≈ 总长（±1.0s）+ 条数=镜头数 + 未截断'),
                             ('C', 'C 级', '仅「去重时长个数 == 镜头数」（时长集合可信，具体值待验）')))

    _pm = (rh.get('per_mission') or {})
    rhythm_rows = ''.join(
        f"<tr><td>{m}</td><td class='num'>{v['n']}</td><td class='num'>{v['median']} s</td>"
        f"<td class='num'>{v['mean']} s</td></tr>"
        for m, v in sorted(_pm.items(), key=lambda x: -x[1]['n'])[:12])
    rh_med = (rh.get('overall') or {}).get('median', '—')

    timeline_rows = ''.join(
        f"<tr><td>{k}</td><td>{' → '.join(x['name'] for x in v['cutscenes'][:8])}"
        f"{' …' if len(v['cutscenes'])>8 else ''}</td>"
        f"<td class='num'>{v['total']:.1f} s</td></tr>"
        for k, v in sorted(mt.items(), key=lambda x: -x[1]['total'])[:20])

    mis_rows = ''.join(
        f"<tr><td>{m}</td><td class='num'>{v['n']}</td><td class='num'>{v['shots']}</td>"
        f"<td class='num'>{v['dur']/60:.1f} 分</td></tr>"
        for m, v in sorted(missions.items(), key=lambda x: -x[1]['dur'])[:30])

    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>过场（实时演算动画）解析总览</title>
<style>
:root{{--bg:#0d1015;--panel:#151a22;--line:#28313d;--fg:#e2e9f2;--mut:#8d9aab;--hl:#e0b356;--ok:#5fbf7f}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.65 "Microsoft YaHei",system-ui,sans-serif}}
header{{padding:22px 26px 12px;border-bottom:1px solid var(--line)}}
h1{{margin:0 0 6px;font-size:20px}}
.sub{{color:var(--mut);font-size:12.5px}}
.wrap{{padding:16px 26px 50px;max-width:1200px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin:16px 0 22px}}
.kpi{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}}
.kpi .v{{font-size:24px;font-weight:600;color:var(--hl)}}
.kpi .k{{color:var(--mut);font-size:12.5px;margin-top:2px}}
h2{{font-size:15px;margin:26px 0 8px;color:#c7d2df;border-left:3px solid var(--hl);padding-left:9px}}
table{{width:100%;border-collapse:collapse;font-size:13px;background:var(--panel);border:1px solid var(--line);border-radius:8px;overflow:hidden}}
th,td{{padding:6px 10px;border-bottom:1px solid #1c232d;text-align:left}}
th{{color:var(--mut);font-weight:500;background:#1a222c}}
td.num{{text-align:right;font-variant-numeric:tabular-nums}}
a{{color:#7fb4ff}}
.note{{color:var(--mut);font-size:12.5px;line-height:1.8}}
.links a{{display:inline-block;margin:4px 14px 4px 0}}
.tag{{display:inline-block;padding:0 7px;border-radius:4px;border:1px solid var(--line);font-size:11.5px;color:var(--mut);margin-left:6px}}
.tag.ok{{color:var(--ok);border-color:#2f5f43}}
</style></head><body>
<header>
  <h1>过场（实时演算动画）解析总览</h1>
  <div class="sub">数据源：<code>anim/cutscene/cuts_*.rpf</code> → 181 包 / 708 .ycd / 4 529 .yad；录屏仅用于校验</div>
</header>
<div class="wrap">
  <div class="kpis">
    <div class="kpi"><div class="v">{len(rows)}</div><div class="k">过场</div></div>
    <div class="kpi"><div class="v">{tot_shots}</div><div class="k">镜头（槽）</div></div>
    <div class="kpi"><div class="v">{tot_dur/60:.0f} 分</div><div class="k">过场总时长</div></div>
    <div class="kpi"><div class="v">{len(missions)}</div><div class="k">涉及任务</div></div>
    <div class="kpi"><div class="v">{cam}</div><div class="k">解出相机轨迹</div></div>
    <div class="kpi"><div class="v">{cam_seg}</div><div class="k">相机段</div></div>
    <div class="kpi"><div class="v">{n_ok}</div><div class="k">时长个数=镜头数</div></div>
    <div class="kpi"><div class="v">{len(verified)}</div><div class="k">逐镜时长已验证</div></div>
  </div>

  <h2>从哪看</h2>
  <div class="note links">
    <a href="structure.html">① 过场结构浏览器（{len(rows)} 个逐个展开：分镜槽 / 演员 / 相机段）</a><br>
    <a href="camera.html">② 相机俯视图（{cam} 个过场：机位位置、朝向、停留时长）</a><br>
    <a href="shot_table.csv">③ 分镜总表 CSV</a> ·
    <a href="shot_durations.json">④ 各页时长 / 候选集合</a> ·
    <a href="shot_durations_verified.json">⑤ 已验证逐镜时长</a><br>
    <a href="scene_cards.html">⑦ 场次卡（分镜 + 出场 + 台词，303 张）</a><br>
    <a href="per_mission/WNT1.json">⑥ 按任务导出（{len(missions)} 个任务 JSON）</a>
  </div>

  <h2>已验证的逐镜时长 <span class="tag ok">求和与过场总长吻合（≤0.6s）</span></h2>
  <div class="note">判定：去重后的页面时长个数 == 镜头数，且时长求和 ≈ 过场时长，且未被 16 秒分页上限截断。</div>
  <table><tr><th>过场</th><th>镜头数</th><th>逐镜时长（秒）</th><th>求和</th><th>过场总长</th></tr>{ver_rows}</table>

  <h2>逐镜时长的可信度分档</h2>
  <table><tr><th>档</th><th>判据</th><th>过场数</th><th>镜头数</th></tr>{tier_rows}</table>

  <h2>剪辑节奏（任务中位镜长）<span class="tag">素材口径，非成片</span></h2>
  <div class="note">样本来自「时长个数=镜头数」的过场页时长；<b>中位 {rh_med}s</b>，而录屏实测成片节奏中位 <b>3.75 s</b>
  —— 差异说明素材会被裁短，详见 <code>README.md</code> §6。</div>
  <table><tr><th>任务</th><th>样本镜数</th><th>中位</th><th>均值</th></tr>{rhythm_rows}</table>

  <h2>任务级过场时间轴 <span class="tag">顺序来自任务脚本</span></h2>
  <div class="note">从 72 个任务脚本里提取的过场播放顺序（`func_NNN(..., "WNT1_MCS2", ...)`），叠加资产里解出的时长。</div>
  <table><tr><th>任务脚本</th><th>过场顺序</th><th>合计</th></tr>{timeline_rows}</table>

  <h2>任务分布（按时长，前 30）</h2>
  <table><tr><th>任务</th><th>过场数</th><th>镜头数</th><th>过场时长</th></tr>{mis_rows}</table>

  <h2>方法与已知边界</h2>
  <div class="note">
    <b>已确认</b>：过场有上下黑边；clip 名编码 演员/过场/段/条/镜；`.yad` 每页内动画时长一致；clip 结构体里的时长 == 所在页时长；
    镜头数（clip 组合）与相机 clip 数 98% 一致；剪辑密度与录屏实测相差 13%。<br>
    <b>未解出</b>：分页是并列的 take / 多版本素材，不是时间轴 → 「第 N 镜多少秒」「成片剪辑顺序」仍缺；
    需要 `.yas` 场景时间轴或游戏运行时数据。详见 <a href="../../../docs/格式与资产/YCD_clip字典_探查.md">YCD 探查</a> /
    <a href="../../../docs/格式与资产/YAS_animation_scene_探查.md">YAS 探查</a>。
  </div>
</div></body></html>"""
    open(OUT, 'w', encoding='utf-8').write(html)
    print('写入', OUT, '%.1f KB' % (os.path.getsize(OUT) / 1024))


if __name__ == '__main__':
    main()
