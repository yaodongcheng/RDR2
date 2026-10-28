#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 conversation_index.json 做成可搜索的静态页 export/story/conversations.html"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY = os.path.join(ROOT, 'export', 'story')


def main():
    idx = json.load(open(os.path.join(STORY, 'conversation_index.json'), encoding='utf-8'))
    stats = json.load(open(os.path.join(STORY, 'conversation_index_stats.json'), encoding='utf-8'))
    ours = set()
    for fn in os.listdir(os.path.join(STORY, 'beats')):
        if fn.endswith('.json'):
            d = json.load(open(os.path.join(STORY, 'beats', fn), encoding='utf-8'))
            ours.update(d['conversations'].keys())

    ca = {}
    _cap = os.path.join(STORY, 'conversation_actors.json')
    if os.path.exists(_cap):
        ca = json.load(open(_cap, encoding='utf-8'))

    compact = []
    for name, v in idx.items():
        actors = ''
        if name in ca:
            seen = []
            for ln in ca[name]['lines']:
                a = ln.get('actor')
                if a and a not in seen:
                    seen.append(a)
            actors = ','.join(seen[:6])
        ctxs = [c for _, c in v['lines']]
        compact.append([name, len(v['lines']), '1' if name in ours else '0',
                        v.get('files', [''])[0], '|'.join(ctxs[:60]),
                        v.get('mission', ''), ','.join((v.get('cast') or [])[:6]), actors])
    compact.sort(key=lambda x: -x[1])
    payload = json.dumps({'rows': compact, 'stats': stats}, ensure_ascii=False,
                         separators=(',', ':'))
    html = TPL.replace('__DATA__', payload)
    out = os.path.join(STORY, 'conversations.html')
    open(out, 'w', encoding='utf-8').write(html)
    print('->', out, round(os.path.getsize(out) / 1e6, 2), 'MB', len(compact), 'conversations')


TPL = r"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>RDR2 全部对话索引</title>
<style>
:root{--bg:#141416;--panel:#1c1c20;--line:#2c2c33;--fg:#e8e4dc;--dim:#8d8a84;--acc:#d8a15a}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.6 "Microsoft YaHei",sans-serif;padding:24px 32px}
h1{font-size:20px;margin:0 0 6px}
.sub{color:var(--dim);font-size:12.5px;margin-bottom:14px}
input{width:420px;max-width:100%;padding:8px 12px;background:#0f0f11;border:1px solid var(--line);
      color:var(--fg);border-radius:6px;outline:none}
table{width:100%;border-collapse:collapse;margin-top:14px;font-size:12.5px}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{color:var(--acc);font-weight:500;position:sticky;top:0;background:var(--bg)}
td.mono{font-family:Consolas,monospace;color:#b9b4ab}
.tag{display:inline-block;padding:0 7px;border-radius:99px;font-size:11px;background:#243041;color:#9fb4c9}
.tag.own{background:#2b3a2b;color:#9ecb9e}
</style></head><body>
<h1>RDR2 全部对话索引</h1>
<div class="sub" id="sub"></div>
<input id="q" placeholder="搜索对话名 / 台词键（例：WNT1_INT_CABIN、GREET）">
<div id="list"></div>
<script>
const D=__DATA__, S=D.stats;
document.getElementById('sub').innerHTML =
  `对话 <b>${S.conversations.toLocaleString()}</b> · 台词 <b>${S.lines.toLocaleString()}</b> 句 · `+
  `来源 ${S.ymt_files.toLocaleString()} 个 .ymt · 已在剧本库 <b>${D.rows.filter(r=>r[2]==='1').length}</b> 个`;
const el=document.getElementById('list');
function render(f){
  const rows=D.rows.filter(r=>!f||r[0].toLowerCase().includes(f)||r[4].toLowerCase().includes(f)).slice(0,400);
  let h=`<table><tr><th>对话名</th><th>句数</th><th>状态</th><th>语音上下文（前 8 个）</th><th>说话人（解出）</th><th>ymt</th></tr>`;
  rows.forEach(r=>{
    const ctx=r[4]?r[4].split('|').slice(0,8).join(' → '):'';
    h+=`<tr><td class="mono">${r[0]}</td><td>${r[1]}</td>
      <td>${r[2]==='1'?'<span class="tag own">已入库</span>':'<span class="tag">未入库</span>'}</td>
      <td class="mono" style="font-size:11.5px">${ctx}</td>
      <td style="font-size:11px;color:#9ecb9e">${r[7]||''}</td>
      <td class="mono" style="font-size:11px">${r[3]}</td></tr>`;
  });
  h+='</table>';
  if(D.rows.length>400) h+='<p style="color:#7f8a99">（只显示前 400 条，用搜索缩小范围）</p>';
  el.innerHTML=h;
}
document.getElementById('q').oninput=e=>render(e.target.value.toLowerCase());
render('');
</script></body></html>
"""

if __name__ == '__main__':
    main()
