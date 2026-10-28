#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分镜构图示意（blockout）：用相机位姿 + 出场角色，画每个镜头的俯视构图。

说明：角色位置是**启发式摆放**（相机前方 2~3.5 m 呈扇形），不是真实站位——
真实站位在过场本体的 .yas 里，当前拿不到。这张图用来判断"这一镜是什么景别、
几个人、谁在镜头方向"，不是精确复现。

用法
    uv run python tools/build_storyboard.py --cutscene wnt1_mcs2
输出
    export/story/cutscene/storyboard.html
"""
import argparse
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CS = os.path.join(ROOT, 'export', 'story', 'cutscene')


def quat_yaw(q):
    if not q:
        return 0.0
    x, y, z, w = q
    siny = 2 * (w * y + z * x)
    cosy = 1 - 2 * (y * y + x * x)
    return math.atan2(siny, cosy)


def load_cutscene(cid):
    cam = None
    for f in (os.path.join(CS, 'camera_stitched', 'cuts_wnt1', cid + '.json'),):
        if os.path.exists(f):
            cam = json.load(open(f, encoding='utf-8'))
    cards = json.load(open(os.path.join(CS, 'scene_cards.json'), encoding='utf-8'))
    card = next((c for c in cards if c['cutscene'].lower() == cid.lower()), None)
    return cam, card


def panel(i, seg, shot):
    W, H = 420, 300
    cx, cy = W / 2, H * 0.55
    yaw = quat_yaw(seg.get('quat0'))
    fov = 45.0
    scale = 40.0
    def pt(dx, dy):
        """局部坐标（右, 前）→ 屏幕"""
        r = dx * math.cos(yaw) - dy * math.sin(yaw)
        f = dx * math.sin(yaw) + dy * math.cos(yaw)
        return cx + r * scale, cy - f * scale
    # 视锥
    l = pt(-math.tan(math.radians(fov / 2)) * 6, 6)
    r = pt(math.tan(math.radians(fov / 2)) * 6, 6)
    actors = (shot or {}).get('actors') or []
    props = (shot or {}).get('props') or []
    n = max(1, len(actors))
    body = []
    for k, a in enumerate(actors):
        ang = (k - (n - 1) / 2) * (26.0 / max(1, n - 1) if n > 1 else 0)
        dist = 3.2 if k % 2 == 0 else 2.4
        x, y = pt(dist * math.sin(math.radians(ang)), dist * math.cos(math.radians(ang)))
        x = min(max(x, 26), W - 26); y = min(max(y, 54), H - 22)
        body.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="11" fill="#2f6d68" stroke="#7fd3c8"/>'
                    f'<text x="{x:.0f}" y="{y+4:.0f}" font-size="10" fill="#dff" text-anchor="middle">{a[:4]}</text>')
    px = []
    for k, p in enumerate(props[:4]):
        x, y = pt(-2.6 + k * 1.1, 1.6)
        x = min(max(x, 10), W - 10); y = min(max(y, 50), H - 14)
        px.append(f'<rect x="{x-4:.0f}" y="{y-4:.0f}" width="8" height="8" fill="#8a6f3a"/>')
    return f'''<div class="p">
  <svg viewBox="0 0 {W} {H}">
    <rect width="{W}" height="{H}" fill="#0b0e13"/>
    <polygon points="{cx},{cy} {l[0]:.0f},{l[1]:.0f} {r[0]:.0f},{r[1]:.0f}" fill="#1d3b3a" opacity=".55"/>
    <circle cx="{cx}" cy="{cy}" r="7" fill="#e0b356"/>
    <line x1="{cx}" y1="{cy}" x2="{cx + math.sin(yaw)*46:.0f}" y2="{cy - math.cos(yaw)*46:.0f}"
          stroke="#e0b356" stroke-width="2"/>
    {''.join(body)}{''.join(px)}
    <text x="10" y="20" font-size="12" fill="#c7d2df">镜 {i+1} · {seg['dur']:.1f}s · t={seg['t0']:.1f}s</text>
    <text x="10" y="38" font-size="10.5" fill="#8d9aab">机位 ({seg['pos0'][0]:.1f}, {seg['pos0'][1]:.1f}) · 朝向 {math.degrees(yaw):.0f}°</text>
  </svg></div>'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cutscene', default='wnt1_mcs2')
    a = ap.parse_args()
    cam, card = load_cutscene(a.cutscene)
    if not cam:
        print('没有相机数据:', a.cutscene)
        return
    shots = {s['shot']: s for s in (card or {}).get('shots', [])}
    panels = []
    for i, seg in enumerate(cam['segments']):
        sh = shots.get(i + 1) or (list(shots.values())[i] if i < len(shots) else {})
        panels.append(panel(i, seg, sh))
    lines = (card or {}).get('lines') or []
    line_html = ''.join(f'<div class="l"><b>{l["speaker"]}</b> {l["zh"]}</div>' for l in lines[:40])
    html = f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>分镜构图示意 · {a.cutscene}</title>
<style>
body{{margin:0;background:#0d1015;color:#e2e9f2;font:14px/1.6 "Microsoft YaHei",system-ui,sans-serif}}
header{{padding:16px 22px;border-bottom:1px solid #28313d}}
h1{{margin:0 0 4px;font-size:18px}} .sub{{color:#8d9aab;font-size:12.5px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:12px;padding:16px 22px}}
.p{{background:#151a22;border:1px solid #28313d;border-radius:10px;overflow:hidden}}
svg{{display:block;width:100%}}
.lines{{padding:8px 22px 40px;max-width:900px}}
.l{{padding:3px 0;border-bottom:1px solid #1c232d;font-size:13px}}
.l b{{color:#e0b356;margin-right:6px}}
.note{{color:#8d9aab;font-size:12.5px;margin-top:6px}}
</style></head><body>
<header><h1>分镜构图示意 · {a.cutscene}</h1>
<div class="sub">{(card or {}).get('script','')} · {cam['duration']:.1f}s · {len(cam['segments'])} 段相机 ·
 角色位置为<b>启发式摆放</b>（真实站位需过场本体 .yas）</div></header>
<div class="grid">{''.join(panels)}</div>
<div class="lines"><h3>台词（{(card or {}).get("cutscene","")}）</h3>{line_html or '<div class="note">无</div>'}</div>
</body></html>'''
    out = os.path.join(CS, 'storyboard.html')
    open(out, 'w', encoding='utf-8').write(html)
    print('写入', out, '%.1f KB' % (os.path.getsize(out) / 1024))


if __name__ == '__main__':
    main()
