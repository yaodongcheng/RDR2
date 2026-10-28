#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""主线自检页：逐任务统计「说话人覆盖 / 未知角色 / 无说话人 / 非中文」。

输出 export/story/selfcheck.html
"""
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY = os.path.join(ROOT, 'export', 'story')
CJK = re.compile(r'[\u4e00-\u9fff]')


def main():
    meta = {r['id']: r for r in json.load(
        open(os.path.join(ROOT, 'export/levels/world/missions_story.json'), encoding='utf-8'))}
    ov = json.load(open(os.path.join(STORY, 'speaker_overrides.json'), encoding='utf-8'))
    rows = []
    for f in glob.glob(os.path.join(STORY, 'beats', '*.json')):
        d = json.load(open(f, encoding='utf-8'))
        m = meta.get(d['id'], {})
        if not (m.get('category') or '').startswith('CHAPTER'):
            continue
        tot = named = unknown = none = nocjk = 0
        gaps = []
        for g, lines in d['conversations'].items():
            sp = ov.get(d['id'], {}).get(g, {})
            for i, ln in enumerate(lines):
                tot += 1
                w = sp.get(str(i + 1))
                if not w:
                    none += 1
                    gaps.append([g, i + 1, 'no-speaker', ln['zh'][:40]])
                elif w == '未知角色':
                    unknown += 1
                    gaps.append([g, i + 1, 'unknown-actor', ln['zh'][:40]])
                else:
                    named += 1
                if not CJK.search(ln['zh'] or ''):
                    nocjk += 1
        rows.append({'id': d['id'], 'title': m.get('title_zh') or d['id'],
                     'chapter': m.get('chapter') or 0, 'chapter_name': m.get('chapter_name') or '',
                     'total': tot, 'named': named, 'unknown': unknown, 'none': none,
                     'nocjk': nocjk,
                     'pct': round(named / max(tot, 1) * 100, 1), 'gaps': gaps[:40]})
    rows.sort(key=lambda r: (r['chapter'], -r['none'] - r['unknown']))
    stats = {
        'missions': len(rows),
        'lines': sum(r['total'] for r in rows),
        'named': sum(r['named'] for r in rows),
        'unknown': sum(r['unknown'] for r in rows),
        'none': sum(r['none'] for r in rows),
        'nocjk': sum(r['nocjk'] for r in rows),
    }
    payload = json.dumps({'rows': rows, 'stats': stats}, ensure_ascii=False,
                         separators=(',', ':'))
    html = TPL.replace('__DATA__', payload)
    out = os.path.join(STORY, 'selfcheck.html')
    open(out, 'w', encoding='utf-8').write(html)
    print('->', out, round(os.path.getsize(out) / 1e6, 2), 'MB', stats)


TPL = r"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>主线自检 · 说话人与中文覆盖</title>
<style>
:root{--bg:#141416;--panel:#1c1c20;--line:#2c2c33;--fg:#e8e4dc;--dim:#8d8a84;--acc:#d8a15a;--ok:#9ecb9e;--warn:#e0b070;--bad:#e08a8a}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.6 "Microsoft YaHei",sans-serif;padding:24px 32px}
h1{font-size:20px;margin:0 0 6px}
.sub{color:var(--dim);font-size:12.5px;margin-bottom:14px}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 16px;min-width:150px}
.card b{font-size:20px;display:block;color:var(--acc)}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left}
th{color:var(--acc);font-weight:500}
td.num{font-family:Consolas,monospace}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}
input{width:320px;max-width:100%;padding:7px 11px;background:#0f0f11;border:1px solid var(--line);color:var(--fg);border-radius:6px;margin-bottom:10px}
tr.gap td{background:#1a1614;font-size:11.5px;color:#bdb8b0}
</style></head><body>
<h1>主线自检 · 说话人与中文覆盖</h1>
<div class="sub" id="sub"></div>
<div class="cards" id="cards"></div>
<input id="q" placeholder="搜索任务名 / ID">
<div id="list"></div>
<script>
const D=__DATA__, S=D.stats;
document.getElementById('sub').textContent =
  `范围：${S.missions} 条主线 · ${S.lines.toLocaleString()} 句；数据来自 .ymt actor 解析 + 录屏标注`;
document.getElementById('cards').innerHTML = `
  <div class="card"><b class="ok">${(S.named/S.lines*100).toFixed(1)}%</b>有确切说话人 ${S.named.toLocaleString()}</div>
  <div class="card"><b class="warn">${(S.unknown/S.lines*100).toFixed(1)}%</b>未知角色 ${S.unknown.toLocaleString()}</div>
  <div class="card"><b class="bad">${(S.none/S.lines*100).toFixed(1)}%</b>无说话人 ${S.none.toLocaleString()}</div>
  <div class="card"><b class="ok">${S.nocjk} 处</b>非中文（纯数字提示）</div>`;
function render(f){
  const rows=D.rows.filter(r=>!f||(r.title+r.id).toLowerCase().includes(f));
  let h='<table><tr><th>章</th><th>任务</th><th>句数</th><th>有名字</th><th>未知</th><th>无</th><th>覆盖</th></tr>';
  rows.forEach((r,i)=>{
    const cls=r.pct>=99?'ok':(r.pct>=90?'warn':'bad');
    h+=`<tr onclick="document.getElementById('g${i}').classList.toggle('hide')" style="cursor:pointer">
      <td>${r.chapter}</td><td>${r.title} <span style="color:#5c5c66">${r.id}</span></td>
      <td class="num">${r.total}</td><td class="num ok">${r.named}</td>
      <td class="num warn">${r.unknown}</td><td class="num bad">${r.none}</td>
      <td class="num ${cls}">${r.pct}%</td></tr>`;
    if(r.gaps && r.gaps.length){
      h+=`<tr id="g${i}" class="gap hide"><td colspan="7">`+
         r.gaps.slice(0,12).map(g=>`${g[2]==='unknown-actor'?'未知':'无'} · ${g[0]} #${g[1]} · ${g[3]}`).join('<br>')+
         (r.gaps.length>12?`<br>…共 ${r.gaps.length} 条`:'')+`</td></tr>`;
    }
  });
  h+='</table>';
  document.getElementById('list').innerHTML=h;
}
document.getElementById('q').oninput=e=>render(e.target.value.toLowerCase());
render('');
</script></body></html>
"""

if __name__ == '__main__':
    main()
