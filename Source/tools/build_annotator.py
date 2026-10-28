#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成「说话人标注页」：人工逐句点选说话人，导出 JSON 后由查看器合并。

为什么需要它：RDR2 的本地化文本库没有逐句说话人字段，说话人只存在于语音库
（按角色分包）与演出编排（.yas / PSIN，未解析）里。要 100% 准确，最现实的做法是
人工标注 —— 这个页面把 22 802 行台词按任务/对话组排好，点一下就能标。

产物 export/story/annotate.html
导出文件放 export/story/speaker_overrides.json，build_story_viewer.py 会自动合并。
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY = os.path.join(ROOT, 'export', 'story')


def shot_index():
    """raw/capture/shots/<组名>*.png|jpg -> {组名: [相对路径]}"""
    d = os.path.join(ROOT, 'raw', 'capture', 'shots')
    out = {}
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        if not fn.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            continue
        grp = fn.rsplit('.', 1)[0]
        for sep in ('_1', '_2', '_3', '-1', '-2'):
            pass
        out.setdefault(grp, []).append(fn)
    return out


def main():
    meta = {r['id']: r for r in json.load(
        open(os.path.join(ROOT, 'export/levels/world/missions_story.json'), encoding='utf-8'))}
    spk = json.load(open(os.path.join(STORY, 'speakers.json'), encoding='utf-8'))
    shots = shot_index()
    data = []
    for f in sorted(glob.glob(os.path.join(STORY, 'beats', '*.json'))):
        b = json.load(open(f, encoding='utf-8'))
        mid = b['id']
        m = meta.get(mid, {})
        groups = []
        for g, lines in b['conversations'].items():
            if not lines:
                continue
            part = (spk.get(mid, {}).get(g, {}) or {}).get('participants') or m.get('cast', [])
            imgs = []
            for k, v in shots.items():
                if k == g or k.startswith(g + '_') or k.startswith(g + '-'):
                    for fn in v[:3]:
                        src = os.path.join(ROOT, 'raw', 'capture', 'shots', fn)
                        dst = os.path.join(STORY, 'shots')
                        os.makedirs(dst, exist_ok=True)
                        try:
                            import shutil
                            shutil.copyfile(src, os.path.join(dst, fn))
                            imgs.append(fn)
                        except OSError:
                            pass
            groups.append({'g': g, 'p': part[:8], 'l': [[x['n'], x['zh']] for x in lines],
                           'img': imgs[:3]})
        if groups:
            data.append({'id': mid, 'title': m.get('title_zh') or mid,
                         'chapter': m.get('chapter_name') or '',
                         'groups': groups})
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    html = TPL.replace('__DATA__', payload)
    out = os.path.join(STORY, 'annotate.html')
    open(out, 'w', encoding='utf-8').write(html)
    print('->', out, round(os.path.getsize(out) / 1e6, 2), 'MB', len(data), 'missions')


TPL = r"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>RDR2 台词说话人标注</title>
<style>
:root{--bg:#141416;--panel:#1c1c20;--line:#2c2c33;--fg:#e8e4dc;--dim:#8d8a84;--acc:#d8a15a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.6 "Microsoft YaHei",sans-serif;display:flex;height:100vh;overflow:hidden}
#side{width:280px;flex:0 0 280px;background:var(--panel);border-right:1px solid var(--line);overflow:auto;padding:12px}
#main{flex:1;overflow:auto;padding:22px 30px}
h1{font-size:16px;margin:4px 0 10px}
.item{padding:6px 9px;border-radius:6px;cursor:pointer;color:#cfcac2;display:flex;justify-content:space-between}
.item:hover{background:#26262c}.item.on{background:#2f2a22;color:#fff}
.item small{color:var(--dim)}
.sec{color:#6fa8dc;font-size:12px;margin:14px 0 4px}
.grp{margin:18px 0 6px;color:#a89a86;font-size:12.5px}
.ln{display:flex;gap:10px;align-items:flex-start;padding:5px 6px;border-radius:6px}
.ln:hover{background:#1d1d21}
.who{flex:0 0 108px;font-size:12px;color:#d8a15a;cursor:pointer;text-align:right}
.who.none{color:#5c5c66}
.txt{flex:1;color:#ded9d0}
.bar{position:sticky;top:0;background:var(--bg);padding:8px 0 12px;border-bottom:1px solid var(--line);display:flex;gap:10px;align-items:center;flex-wrap:wrap}
button{background:#26262c;border:1px solid var(--line);color:#cfcac2;padding:6px 14px;border-radius:6px;cursor:pointer}
button.pri{background:var(--acc);color:#1a1a1a;border-color:var(--acc)}
input{background:#0f0f11;border:1px solid var(--line);color:var(--fg);padding:6px 10px;border-radius:6px;width:200px}
.note{color:#7f8a99;font-size:12px}
</style></head><body>
<div id="side"><h1>说话人标注</h1>
<div class="note" style="margin-bottom:8px">点左侧人物名切换/指定；灰色 = 未标注。</div>
<input id="q" placeholder="搜索任务…"><div id="list"></div></div>
<div id="main">
  <div class="bar">
    <span id="title"></span>
    <input id="custom" placeholder="自定义说话人（回车）">
    <button class="pri" onclick="exportJSON()">导出 speaker_overrides.json</button>
    <button onclick="clearM()">清空本任务</button>
    <span class="note" id="cnt"></span>
  </div>
  <div id="view"></div>
</div>
<script>
const D=__DATA__;
const OV={};   // {mission:{group:{lineN:who}}}
let cur=null;
function load(){try{return JSON.parse(localStorage.getItem('rdr2_spk')||'{}')}catch(e){return {}}}
Object.assign(OV, load());
function save(){localStorage.setItem('rdr2_spk', JSON.stringify(OV))}
function renderList(f){
  const el=document.getElementById('list'); el.innerHTML='';
  D.filter(m=>!f||(m.title+m.id).toLowerCase().includes(f)).forEach(m=>{
    const it=document.createElement('div'); it.className='item'+(cur===m.id?' on':'');
    it.innerHTML=`<span>${m.title}</span><small>${m.groups.length}</small>`;
    it.onclick=()=>{cur=m.id;renderList(document.getElementById('q').value.toLowerCase());render();};
    el.appendChild(it);
  });
}
function get(mid,g,n){ return ((OV[mid]||{})[g]||{})[n]; }
function set(mid,g,n,who){ (OV[mid]=OV[mid]||{})[g]=OV[mid][g]||{}; if(who) OV[mid][g][n]=who; else delete OV[mid][g][n]; save(); }
function render(){
  const m=D.find(x=>x.id===cur)||D[0]; if(!m) return; cur=m.id;
  document.getElementById('title').textContent=m.title+' · '+m.chapter;
  let total=0,done=0;
  let h='';
  m.groups.forEach(gr=>{
    if(gr.img&&gr.img.length) h+=`<div style="display:flex;gap:8px;margin:8px 0">${gr.img.map(i=>`<img src="shots/${i}" style="max-height:150px;border-radius:6px;border:1px solid #2c2c33">`).join('')}</div>`;
    h+=`<div class="grp">💬 ${gr.g}　<span style="color:#5c5c66">参与：${gr.p.join('、')||'未知'}</span>　`+
       gr.p.slice(0,6).map(pn=>`<button style="padding:1px 8px;font-size:11px;margin-left:4px" onclick="bulk('${m.id}','${gr.g}','${pn}')">全设 ${pn}</button>`).join('')+
       `<button style="padding:1px 8px;font-size:11px;margin-left:4px" onclick="bulk('${m.id}','${gr.g}','')">清空</button></div>`;
    gr.l.forEach(([n,zh])=>{
      total++; const who=get(m.id,gr.g,n); if(who) done++;
      h+=`<div class="ln"><span class="who ${who?'':'none'}" onclick="pick('${m.id}','${gr.g}',${n})">${who||'——'}</span><span class="txt">${zh}</span></div>`;
    });
  });
  document.getElementById('view').innerHTML=h;
  document.getElementById('cnt').textContent=`已标注 ${done}/${total}`;
}
function pick(mid,g,n){
  const m=D.find(x=>x.id===mid); const gr=m.groups.find(x=>x.g===g);
  const opts=[...new Set([...(gr.p||[]),'亚瑟','约翰'])];
  const cur=get(mid,g,n);
  const idx=cur?opts.indexOf(cur):-1;
  const next=opts[(idx+1)%opts.length];
  set(mid,g,n,next); render();
}
document.getElementById('custom').addEventListener('keydown',e=>{
  if(e.key==='Enter'&&e.target.value.trim()){
    window.__custom=e.target.value.trim(); e.target.value=''; alert('已设为默认自定义名，点击台词右侧名字后会使用它');
  }
});
function bulk(mid,g,who){
  const m=D.find(x=>x.id===mid); const gr=m.groups.find(x=>x.g===g);
  gr.l.forEach(([n])=>set(mid,g,n,who)); render();
}
function clearM(){ OV[cur]={}; save(); render(); }
function exportJSON(){
  const blob=new Blob([JSON.stringify(OV,null,1)],{type:'application/json'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='speaker_overrides.json'; a.click();
}
document.getElementById('q').oninput=e=>renderList(e.target.value.toLowerCase());
renderList('');render();
</script></body></html>
"""

if __name__ == '__main__':
    main()
