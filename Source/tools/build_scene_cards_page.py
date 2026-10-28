#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""场次卡浏览页：把 scene_cards.json 渲染成可翻阅的叙事卡。

产物：export/story/cutscene/scene_cards.html
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CS = os.path.join(ROOT, 'export', 'story', 'cutscene')
OUT = os.path.join(CS, 'scene_cards.html')


def main():
    cards = json.load(open(os.path.join(CS, 'scene_cards.json'), encoding='utf-8'))
    data = json.dumps(cards, ensure_ascii=False).replace('</', '<\\/')
    html = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>过场场次卡 · 叙事用</title>
<style>
:root{--bg:#0d1015;--panel:#151a22;--line:#28313d;--fg:#e2e9f2;--mut:#8d9aab;--hl:#e0b356}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.7 "Microsoft YaHei",system-ui,sans-serif}
header{padding:14px 20px;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:center;flex-wrap:wrap}
h1{font-size:17px;margin:0}
input,select{background:#0f141a;color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:5px 9px}
input{width:240px}
.wrap{padding:14px 20px 40px;max-width:1100px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:14px}
.card h2{margin:0 0 4px;font-size:15px;color:var(--hl)}
.meta{color:var(--mut);font-size:12.5px;margin-bottom:8px}
.shots{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
.shot{background:#1b222c;border:1px solid var(--line);border-radius:8px;padding:6px 9px;font-size:12.5px;min-width:150px}
.shot b{color:var(--cin)}
.line{display:grid;grid-template-columns:64px 1fr;gap:8px;padding:2px 0;font-size:13px}
.sp{color:var(--hl);font-weight:600}
.chip{display:inline-block;background:#243041;border-radius:4px;padding:0 6px;margin:1px 3px 1px 0;font-size:11.5px;color:#b9c8d9}
.note{color:var(--mut);font-size:12px}
</style></head><body>
<header><h1>过场场次卡 · 分镜 + 出场 + 台词</h1>
<input id="q" placeholder="搜任务 / 过场 / 角色 / 台词">
<span class="note" id="cnt"></span></header>
<div class="wrap" id="list"></div>
<script>
const CARDS = __DATA__;
const list = document.getElementById('list');
function render(){
  const q = document.getElementById('q').value.trim().toLowerCase();
  const out = CARDS.filter(c=>{
    if(!q) return true;
    const hay = [c.script,c.cutscene,...(c.cast||[]),...c.lines.map(l=>l.zh)].join(' ').toLowerCase();
    return hay.includes(q);
  }).sort((a,b)=> (a.script+a.order).localeCompare(b.script+b.order));
  document.getElementById('cnt').textContent = out.length + ' / ' + CARDS.length + ' 张';
  list.innerHTML = out.map(c=>`<div class="card">
    <h2>${c.cutscene}</h2>
    <div class="meta">${c.script} · 第 ${c.order+1} 个过场 · ${c.duration||'?'}s · ${c.shots_n} 镜 · ${c.lines.length} 句台词
      · <b style="color:#8fb6d9">${c.tone||''}</b></div>
    <div>${(c.cast||[]).map(a=>`<span class="chip">${a}</span>`).join('')}</div>
    <div class="shots">${(c.shots||[]).map(s=>`<div class="shot"><b>镜 ${s.shot}</b>${s.camera?' · 有相机':''}
      <div class="note">${(s.actors||[]).join('、')||'—'}</div>
      <div class="note">道具 ${(s.props||[]).slice(0,4).join('、')||'—'}</div></div>`).join('')}</div>
    ${c.lines.length? c.lines.map(l=>`<div class="line"><div class="note">${l.n}</div>
      <div><span class="sp">${l.speaker||'?'}</span> ${l.zh}</div></div>`).join('') : '<div class="note">（该过场没有可匹配的对话组）</div>'}
  </div>`).join('');
}
document.getElementById('q').addEventListener('input', render);
render();
</script></body></html>"""
    open(OUT, 'w', encoding='utf-8').write(html.replace('__DATA__', data))
    print('写入 %s  %.1f KB' % (OUT, os.path.getsize(OUT) / 1024))


if __name__ == '__main__':
    main()
