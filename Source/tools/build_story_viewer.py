#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 export/story/beats/*.json + encounters.json 打包成一个可浏览的静态页。

产物：export/story/index.html（自包含，双击即可看；也可从首页进入）
"""
import glob
import json
import os
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY = os.path.join(ROOT, 'export', 'story')

ORDER = ['CHAPTER_1', 'CHAPTER_2', 'CHAPTER_3', 'CHAPTER_4', 'CHAPTER_5',
         'CHAPTER_6', 'CHAPTER_7', 'CHAPTER_8', 'RANDOM_STORY_CHARACTER',
         'RANDOM_CHARACTER', 'BOUNTY_HUNTING', 'ITEM_REQUEST', 'ENDLESS_SUMMER', 'RECIPE']


def pack(d):
    """精简：去掉行号、重复嵌套信息"""
    seqs = []
    for s in d['sequences']:
        cases = []
        for c in s['cases']:
            ev = []
            for e in c['events']:
                if e['t'] == 'objective':
                    if e.get('zh'):
                        ev.append(['o', e['zh']])
                elif e['t'] == 'conv':
                    ev.append(['c', e['group']])
                elif e['t'] == 'animscene':
                    if ev and ev[-1][0] == 'A':
                        ev[-1][1].append(e['name'])
                    else:
                        ev.append(['A', [e['name']]])
                elif e['t'] == 'spawn' and e.get('model'):
                    ev.append(['s', e['model']])
            if ev:
                cases.append([c['case'], c['next'], ev])
        if cases:
            seqs.append([s['func'], cases])
    return {
        'id': d['id'], 'zh': d.get('title_zh'), 'en': d.get('title_en'),
        'cat': d.get('category'), 'ch': d.get('chapter'), 'chn': d.get('chapter_name'),
        'desc': (d.get('desc_zh') or '')[:220],
        'st': d['stats'],
        'obj': (d.get('objectives_all') or {}).get('objectives', []),
        'fail': (d.get('objectives_all') or {}).get('fails', []),
        'cast': d.get('cast', []),
        'seqs': seqs,
        'fb': any(s[0] == '(file_scan)' for s in seqs),
        'conv': {k: [x['zh'] for x in v] for k, v in d['conversations'].items()},
    }


def main():
    meta = {r['id']: r for r in json.load(
        open(os.path.join(ROOT, 'export/levels/world/missions_story.json'), encoding='utf-8'))}
    missions = []
    for f in glob.glob(os.path.join(STORY, 'beats', '*.json')):
        d = json.load(open(f, encoding='utf-8'))
        m = meta.get(d['id'], {})
        d['desc_zh'] = m.get('desc_zh', '')
        missions.append(pack(d))
    qg = {}
    for f in glob.glob(os.path.join(STORY, 'questgraph', '*.json')):
        g = json.load(open(f, encoding='utf-8'))
        idx = {n['id']: i for i, n in enumerate(g['nodes'])}
        nodes = []
        for n in g['nodes']:
            t = n['type']
            if t == 'objective':
                nodes.append(['o', n['text']])
            elif t == 'dialogue':
                nodes.append(['d', n['group']])
            elif t == 'cutscene':
                nodes.append(['k', len(n.get('scenes', []))])
            else:
                nodes.append(['p', n.get('model', '')])
        edges = [[idx[e['from']], idx[e['to']], e['kind'], e.get('next')]
                 for e in g['edges'] if e['from'] in idx and e['to'] in idx]
        qg[g['id']] = {'n': nodes, 'e': edges, 'c': g['confidence']}
    missions.sort(key=lambda x: (ORDER.index(x['cat']) if x['cat'] in ORDER else 99,
                                 x['ch'] or 0, x['zh'] or ''))
    # 逐句音频（若已用 apply_speaker_log.py 切出来）
    aud = {}
    ad = os.path.join(STORY, 'audio')
    if os.path.isdir(ad):
        for fn in os.listdir(ad):
            if fn.lower().endswith(('.wav', '.mp3', '.ogg')):
                aud[fn.rsplit('.', 1)[0]] = 'audio/' + fn
        for sub in os.listdir(ad):
            p2 = os.path.join(ad, sub)
            if not os.path.isdir(p2):
                continue
            for fn in os.listdir(p2):
                if fn.lower().endswith(('.wav', '.mp3', '.ogg')):
                    aud[f'{sub}/' + fn.rsplit('.', 1)[0]] = f'audio/{sub}/' + fn
    recaps = {r['id']: r for r in json.load(
        open(os.path.join(STORY, 'recaps.json'), encoding='utf-8'))}
    spk = json.load(open(os.path.join(STORY, 'speakers.json'), encoding='utf-8'))
    _ovp = os.path.join(STORY, 'speaker_overrides.json')
    overrides = json.load(open(_ovp, encoding='utf-8')) if os.path.exists(_ovp) else {}
    for m in missions:
        m['g'] = qg.get(m['id'])
        m['rc'] = recaps.get(m['id'])
        m['sp'] = spk.get(m['id'], {})
        ov = overrides.get(m['id'], {})
        arr = {}
        for g, info in (m['sp'] or {}).items():
            who = [None] * len(m['conv'].get(g, []))
            for i, ln in enumerate((info.get('lines') or [])):
                if i < len(who) and ln.get('who'):
                    who[i] = ln['who'] + ('?' if ln.get('conf') == 'low' else '')
            for n, w in (ov.get(g) or {}).items():
                idx = int(n) - 1
                if 0 <= idx < len(who):
                    who[idx] = w
            if any(who):
                arr[g] = who
        m['spk'] = arr
    recap_list = [recaps[m['id']] for m in missions if m['id'] in recaps]
    _cf = os.path.join(STORY, 'conversation_flows.json')
    flows = json.load(open(_cf, encoding='utf-8')) if os.path.exists(_cf) else {}
    _gr = os.path.join(STORY, 'greetings.json')
    greet = json.load(open(_gr, encoding='utf-8')) if os.path.exists(_gr) else {}
    _cp = os.path.join(STORY, 'captured.json')
    captured = json.load(open(_cp, encoding='utf-8')) if os.path.exists(_cp) else []
    enc = json.load(open(os.path.join(STORY, 'encounters.json'), encoding='utf-8'))
    stats = {
        'missions': len(missions),
        'beats': sum(m['st']['beats'] for m in missions),
        'conv': sum(m['st']['conversations'] for m in missions),
        'lines': sum(m['st']['dialogue_lines'] for m in missions),
        'obj': sum(m['st']['objectives'] for m in missions),
        'enc': len(enc),
        'gnodes': sum(len(g['n']) for g in qg.values()),
        'gedges': sum(len(g['e']) for g in qg.values()),
    }
    payload = json.dumps({'missions': missions, 'enc': enc, 'stats': stats, 'captured': captured, 'aud': aud,
                          'recaps': recap_list, 'greet': greet, 'flows': flows},
                         ensure_ascii=False, separators=(',', ':'))
    html = TEMPLATE.replace('__DATA__', payload)
    out = os.path.join(STORY, 'index.html')
    open(out, 'w', encoding='utf-8').write(html)
    print('->', out, round(os.path.getsize(out) / 1e6, 2), 'MB')
    print(stats)


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>RDR2 剧情与随机遭遇 · 剧本浏览器</title>
<style>
:root{--bg:#141416;--panel:#1c1c20;--line:#2c2c33;--fg:#e8e4dc;--dim:#8d8a84;--acc:#d8a15a;--acc2:#6fa8dc}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.7 "Microsoft YaHei",system-ui,sans-serif;display:flex;height:100vh;overflow:hidden}
#side{width:320px;flex:0 0 320px;background:var(--panel);border-right:1px solid var(--line);overflow:auto;padding:12px}
#main{flex:1;overflow:auto;padding:28px 40px}
h1{font-size:17px;margin:4px 0 10px;letter-spacing:.5px}
.stat{color:var(--dim);font-size:12px;line-height:1.9}
.stat b{color:var(--acc);font-weight:600}
input{width:100%;margin:10px 0;padding:8px 10px;background:#0f0f11;border:1px solid var(--line);color:var(--fg);border-radius:6px;outline:none}
.grp{color:var(--acc2);font-size:12px;margin:14px 0 4px;letter-spacing:1px}
.item{padding:7px 10px;border-radius:6px;cursor:pointer;display:flex;justify-content:space-between;gap:8px;color:#cfcac2}
.item:hover{background:#26262c}
.item.on{background:#2f2a22;color:#fff;box-shadow:inset 2px 0 0 var(--acc)}
.item small{color:var(--dim);flex:0 0 auto}
h2{font-size:22px;margin:0 0 4px}
.sub{color:var(--dim);font-size:12.5px;margin-bottom:14px}
.chips span{display:inline-block;background:#26262c;border:1px solid var(--line);border-radius:20px;padding:1px 9px;margin:0 6px 6px 0;font-size:12px;color:#bdb8b0}
.sec{margin:26px 0 8px;font-size:13px;color:var(--acc2);letter-spacing:1px;border-bottom:1px solid var(--line);padding-bottom:6px}
.obj{color:#e9d9b8}
.beat{border-left:2px solid var(--line);margin-left:6px;padding:2px 0 14px 16px;position:relative}
.beat:before{content:"";position:absolute;left:-5px;top:9px;width:8px;height:8px;border-radius:50%;background:var(--acc)}
.beat .h{color:var(--dim);font-size:11.5px;letter-spacing:.5px}
.dlg{background:#1c1c20;border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin:8px 0}
.dlg .g{color:var(--acc2);font-size:11.5px;margin-bottom:4px}
.dlg p{margin:2px 0;color:#ded9d0}
.anim{color:#7f8a99;font-size:12px;margin-top:4px}
.seq{margin:18px 0 4px;color:#a89a86;font-size:12px;letter-spacing:.5px}
table{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:8px;table-layout:fixed}
td:nth-child(1),th:nth-child(1){width:24%}
td:nth-child(2),th:nth-child(2){width:9%}
td:nth-child(3),th:nth-child(3){width:14%}
td:nth-child(4),th:nth-child(4){width:6%}
td:nth-child(5),th:nth-child(5){width:6%}
td:nth-child(6),th:nth-child(6){width:17%}
td:nth-child(7),th:nth-child(7){width:14%}
th,td{border-bottom:1px solid var(--line);padding:7px 8px;text-align:left;vertical-align:top}
th{color:var(--acc2);font-weight:500}
td.mono{font-family:Consolas,monospace;color:#b9b4ab}
.tabs{display:flex;gap:8px;margin-bottom:10px}
.tabs button{background:#26262c;border:1px solid var(--line);color:#bdb8b0;padding:6px 14px;border-radius:6px;cursor:pointer}
.tabs button.on{background:var(--acc);color:#1a1a1a;border-color:var(--acc)}
.hide{display:none}
.player{background:#1b1a17;border:1px solid #3a352c;border-radius:12px;padding:18px 20px;margin-top:14px}
.player .bar{height:4px;background:#2a2823;border-radius:2px;overflow:hidden;margin-bottom:14px}
.player .bar i{display:block;height:100%;background:var(--acc);transition:.2s}
.player .stp{color:#8d8a84;font-size:12px;letter-spacing:1px}
.player .big{font-size:17px;line-height:1.9;margin:10px 0;color:#f0e9dc}
.player .big.o{color:#f0d9a8}
.player .ln{color:#ded9d0;margin:3px 0 3px 8px}
.player .btns{display:flex;gap:8px;margin-top:16px;flex-wrap:wrap}
.player button{background:#26262c;border:1px solid var(--line);color:#cfcac2;padding:7px 16px;border-radius:6px;cursor:pointer}
.player button:hover{border-color:var(--acc)}
.player button.pri{background:var(--acc);color:#1a1a1a;border-color:var(--acc)}
.player button.jmp{background:#332a1e;color:#e5c58b;border-color:#5a4a30}
</style></head><body>
<div id="side">
  <h1>RDR2 剧情 · 剧本浏览器</h1>
  <div class="stat" id="stat"></div>
  <input id="q" placeholder="搜索任务 / 对白 / 角色…">
  <div id="list"></div>
</div>
<div id="main"><div id="view"></div></div>
<script>
const D=__DATA__;
const S=D.stats;
document.getElementById('stat').innerHTML =
  `任务 <b>${S.missions}</b> · beat <b>${S.beats.toLocaleString()}</b><br>`+
  `对白组 <b>${S.conv.toLocaleString()}</b> · 台词 <b>${S.lines.toLocaleString()}</b> 行<br>`+
  `目标 <b>${S.obj}</b> · 随机遭遇模板 <b>${S.enc}</b><br>`+
  `任务图节点 <b>${S.gnodes.toLocaleString()}</b> · 边 <b>${S.gedges.toLocaleString()}</b>`;
const CATN={CHAPTER_1:'第一章 犁刀村',CHAPTER_2:'第二章 马蹄铁高台',CHAPTER_3:'第三章 克莱蒙斯据点',
CHAPTER_4:'第四章 圣丹尼斯',CHAPTER_5:'第五章 瓜玛',CHAPTER_6:'第六章 河狸洞',
CHAPTER_7:'尾声 上',CHAPTER_8:'尾声 下',RANDOM_CHARACTER:'陌生人任务',
RANDOM_STORY_CHARACTER:'随机剧情角色',BOUNTY_HUNTING:'赏金任务',ITEM_REQUEST:'物品请求',
ENDLESS_SUMMER:'线上',RECIPE:'配方'};
let SHOWG=(localStorage.getItem('showguess')!=='0');
let cur=null, tab=(location.search.includes('tab=enc')?'enc':(location.search.includes('tab=graph')?'graph':(location.search.includes('tab=recap')?'recap':(location.search.includes('tab=cap')?'cap':(location.search.includes('tab=gr')?'gr':(location.search.includes('tab=fl')?'fl':'story'))))));
function renderList(f){
  const el=document.getElementById('list'); el.innerHTML='';
  let last=null;
  D.missions.filter(m=>!f||JSON.stringify(m).toLowerCase().includes(f)).forEach(m=>{
    if(m.cat!==last){last=m.cat;const g=document.createElement('div');g.className='grp';g.textContent=CATN[m.cat]||m.cat;el.appendChild(g);}
    const it=document.createElement('div'); it.className='item'+(cur===m.id?' on':'');
    it.innerHTML=`<span>${m.zh||m.id}</span><small>${m.st.dialogue_lines}</small>`;
    it.onclick=()=>{cur=m.id;tab='story';renderList(document.getElementById('q').value.toLowerCase());render();};
    el.appendChild(it);
  });
}
function render(){
  const v=document.getElementById('view');
  if(tab==='enc'){return renderEnc(v);}
  if(tab==='recap'){return renderRecap(v);}
  if(tab==='cap'){return renderCaptured(v);}
  if(tab==='gr'){return renderGreet(v);}
  if(tab==='fl'){return renderFlows(v);}
  if(tab==='graph'){return renderGraph(v);}
  const m=D.missions.find(x=>x.id===cur)||D.missions.find(x=>x.g&&x.g.c==='ordered')||D.missions[0];
  if(!m){v.innerHTML='<p>没有数据</p>';return;}
  let h=`<div class="tabs"><button class="${tab==='story'?'on':''}" onclick="tab='story';render()">剧情剧本</button>
  <button class="${tab==='graph'?'on':''}" onclick="tab='graph';render()">任务图</button>
  <button class="${tab==='recap'?'on':''}" onclick="tab='recap';render()">剧情回顾</button>
  <button class="${tab==='cap'?'on':''}" onclick="tab='cap';render()">现场采集 (${D.captured.length})</button>
  <button class="${tab==='gr'?'on':''}" onclick="tab='gr';render()">角色语料</button>
  <button class="${tab==='fl'?'on':''}" onclick="tab='fl';render()">对话流 (${Object.keys(D.flows||{}).length})</button>
  <button class="${tab==='enc'?'on':''}" onclick="tab='enc';render()">随机遭遇模板</button></div>`;
  h+=`<h2>${m.zh||m.id} <span style="color:#8d8a84;font-size:14px">${m.en||''}</span></h2>`;
  h+=`<div class="sub">${m.chn||''} · <code>${m.id}</code> · beat ${m.st.beats} · 对白组 ${m.st.conversations} · 台词 ${m.st.dialogue_lines} 行 · 目标 ${m.st.objectives}</div>`;
  if(m.desc) h+=`<p style="color:#c9c3b8">${m.desc}</p>`;
  if(m.cast&&m.cast.length) h+=`<div class="chips">${m.cast.slice(0,24).map(c=>`<span>${c}</span>`).join('')}</div>`;
  if(m.obj&&m.obj.length){h+=`<div class="sec">任务目标（原文顺序）</div><ol class="obj">${m.obj.map(o=>`<li>${o}</li>`).join('')}</ol>`;}
  if(m.fail&&m.fail.length){h+=`<div class="sec">失败条件</div><div style="color:#a58e8e;font-size:12.5px">${m.fail.join('　·　')}</div>`;}
  h+=`<div class="sec">${m.fb?'内容清单（该脚本未识别出状态机，按源文件顺序）':'剧本片段（按状态机 case 顺序）'}
    <span style="color:#5c5c66;font-weight:400">　
      <label style="cursor:pointer"><input type="checkbox" ${SHOWG?'checked':''} onchange="SHOWG=this.checked;localStorage.setItem('showguess',SHOWG?'1':'0');render()"> 显示推测说话人</label>
      　（文本库无说话人字段；确定项=玩家选项，推测项按对话轮次推断，可在 <a href="annotate.html" style="color:#d8a15a">标注页</a> 修正）</span></div>`;
  m.seqs.forEach((s,si)=>{
    h+=`<div class="seq">序列 ${si+1} · <code>${s[0]}</code></div>`;
    s[1].forEach(([n,nx,ev])=>{
      h+=`<div class="beat"><div class="h">case ${n}${nx!=null&&nx>=0?' → '+nx:''}</div>`;
      ev.forEach(([t,x])=>{
        if(t==='o') h+=`<div class="obj">🎯 ${x}</div>`;
        else if(t==='A') h+=`<div class="anim">🎬 演出场景 ${x.length} 个：${x.slice(0,4).join(' / ')}${x.length>4?' …':''}</div>`;
        else if(t==='s') h+=`<div class="anim">👤 生成 ${x}</div>`;
        else if(t==='c'){
          const ls=m.conv[x]||[];
          const pp=(m.sp&&m.sp[x])?m.sp[x].participants:[];
          const sp=(m.spk&&m.spk[x])||[];
          h+=`<div class="dlg"><div class="g">💬 ${x}　${ls.length} 句`+
             (pp.length<=3&&pp.length>0?`　<span style="color:#7f8a99">参与：${pp.join('、')}</span>`:'')+
             `</div>${ls.map((l,i)=>`<p>${(sp[i]&&(SHOWG||!sp[i].endsWith('?')))?`<b style="color:${sp[i].endsWith('?')?'#8d8a84':'#d8a15a'};font-weight:500">${sp[i].replace('?','')}${sp[i].endsWith('?')?'（轮次推测）':''}：</b>`:''}${l}${(D.aud&&D.aud[x+'_'+(i+1)])?` <audio controls preload="none" src="${D.aud[x+'_'+(i+1)]}" style="height:22px;vertical-align:middle;width:150px"></audio>`:''}</p>`).join('')}</div>`;
        }
      });
      h+='</div>';
    });
  });
  v.innerHTML=h;
}
function renderGraph(v){
  const m=D.missions.find(x=>x.id===cur)||D.missions.find(x=>x.g&&x.g.c==='ordered')||D.missions[0];
  if(!cur&&m) cur=m.id;
  let h=`<div class="tabs"><button onclick="tab='story';render()">剧情剧本</button>
  <button class="on" onclick="tab='graph';render()">任务图</button>
  <button onclick="tab='recap';render()">剧情回顾</button>
  <button onclick="tab='cap';render()">现场采集 (${D.captured.length})</button>
  <button onclick="tab='enc';render()">随机遭遇模板</button></div>`;
  if(!m||!m.g){v.innerHTML=h+'<p>没有任务图</p>';return;}
  h+=`<h2>${m.zh||m.id} · 任务图 <span style="color:#8d8a84;font-size:14px">${m.en||''}</span></h2>`;
  h+=`<div class="sub">节点 ${m.g.n.length} · 边 ${m.g.e.length} · 顺序置信度：<b style="color:${m.g.c==='ordered'?'#8fbf7f':'#d0a060'}">${m.g.c==='ordered'?'有序（脚本状态机）':'仅内容清单（顺序待人工排）'}</b></div>`;
  h+=`<div class="sub" style="color:#8d8a84">这张图就是从 beat 表生成的 QuestGraph：🎯 目标 / 💬 对白 / 🎬 演出 / 👤 生成；⤵ 表示 case 的分支或回环。</div>`;
  h+=`<div style="margin:12px 0"><button class="pri" style="background:var(--acc);color:#1a1a1a;border:0;padding:8px 18px;border-radius:6px;cursor:pointer" onclick="startPlay('${m.id}')">▶ 按任务图试玩一遍</button></div>`;
  h+=`<div id="player"></div>`;
  const jumps={};
  m.g.e.forEach(([a,b,k,nx])=>{if(k==='jump'){(jumps[a]=jumps[a]||[]).push(b);}});
  h+='<div style="margin-top:14px">';
  m.g.n.forEach((n,i)=>{
    const [t,x]=n;
    let body='';
    if(t==='o') body=`<span class="obj">🎯 ${x}</span>`;
    else if(t==='d'){const ls=(m.conv[x]||[]);body=`<span style="color:#9fc4e0">💬 ${x}</span> <span style="color:#8d8a84">${ls.length} 句</span>
      <div style="color:#cfcac2;font-size:12.5px;margin-left:6px">${ls.slice(0,2).map((l,k)=>{const sp=(m.spk&&m.spk[x])||[];const w=sp[k];return (w?`<b style="color:#9ecb9e;font-weight:500">${w.replace('?','')}：</b>`:'')+l;}).join('　/　')}${ls.length>2?' …':''}</div>`;}
    else if(t==='k') body=`<span class="anim">🎬 演出场景 ${x} 个</span>`;
    else body=`<span class="anim">👤 生成 ${x}</span>`;
    h+=`<div style="display:flex;gap:10px;align-items:flex-start;padding:5px 0">
      <span style="color:#5c5c66;font-size:11.5px;min-width:34px;text-align:right">#${i}</span>
      <span style="color:#3a3a44">│</span><span>${body}</span></div>`;
    if(jumps[i]) h+=`<div style="margin-left:52px;color:#d0a060;font-size:12px">⤵ 分支 → #${jumps[i].join(', #')}</div>`;
  });
  h+='</div>'; v.innerHTML=h;
}
let P={id:null,i:0};
function startPlay(id){P={id,i:0};cur=id;render();setTimeout(()=>playStep(),0);}
function playNode(){
  const m=D.missions.find(x=>x.id===P.id); if(!m||!m.g) return null;
  return m.g.n[P.i]||null;
}
function playStep(){
  const el=document.getElementById('player'); if(!el) return;
  const m=D.missions.find(x=>x.id===P.id); if(!m||!m.g){el.innerHTML='';return;}
  const n=m.g.n[P.i]||['','']; const [t,x]=n;
  const total=m.g.n.length;
  const jumps=m.g.e.filter(e=>e[2]==='jump'&&e[0]===P.i).map(e=>e[1]);
  let body='';
  if(t==='o') body=`<div class="big o">🎯 ${x}</div>`;
  else if(t==='d'){const ls=m.conv[x]||[];body=`<div class="stp">💬 ${x}　${ls.length} 句</div>`+ls.map(l=>`<div class="ln">${l}</div>`).join('');}
  else if(t==='k') body=`<div class="big anim">🎬 演出场景 ${x} 个</div>`;
  else body=`<div class="big anim">👤 生成 ${x}</div>`;
  el.innerHTML=`<div class="player">
    <div class="bar"><i style="width:${((P.i+1)/total*100).toFixed(1)}%"></i></div>
    <div class="stp">${m.zh} · 节点 ${P.i+1} / ${total} · ${t==='o'?'目标':t==='d'?'对白':t==='k'?'演出':'生成'}</div>
    ${body}
    <div class="btns">
      <button ${P.i<=0?'disabled':''} onclick="P.i=Math.max(0,P.i-1);playStep()">← 上一步</button>
      <button class="pri" ${P.i>=total-1?'disabled':''} onclick="P.i=Math.min(${total-1},P.i+1);playStep()">下一步 →</button>
      ${jumps.map(j=>`<button class="jmp" onclick="P.i=${j};playStep()">⤵ 分支 → 节点 ${j+1}</button>`).join('')}
      <button onclick="P.i=0;playStep()">↺ 从头</button>
    </div></div>`;
}
function renderRecap(v){
  let h=`<div class="tabs"><button onclick="tab='story';render()">剧情剧本</button>
  <button onclick="tab='graph';render()">任务图</button>
  <button class="on" onclick="tab='recap';render()">剧情回顾</button>
  <button onclick="tab='enc';render()">随机遭遇模板</button></div>`;
  h+=`<h2>剧情回顾 · 全部任务 <span style="color:#8d8a84;font-size:14px">${D.recaps.length} 条</span></h2>`;
  h+=`<div class="sub">这是「演不出来时给玩家看的文字版」：官方任务简介 + 目标/对白要点 + 收尾台词。按章节排列，可直接当任务日志或过场旁白稿。</div>`;
  let last='';
  D.recaps.forEach(r=>{
    if(r.chapter&&r.chapter!==last){last=r.chapter;h+=`<div class="sec">${r.chapter}</div>`;}
    h+=`<div style="background:#1b1b1f;border:1px solid #2c2c33;border-radius:10px;padding:14px 16px;margin:10px 0">
      <div style="font-size:15px;color:#f0e9dc"><b>${r.title}</b>
        <span style="color:#7f8a99;font-size:12px">　${r.id}　${r.confidence==='ordered'?'有序':'内容清单'}</span></div>`;
    if(r.summary) h+=`<div style="color:#a9a49b;font-size:12.5px;margin:6px 0">${r.summary}</div>`;
    if(r.stanzas&&r.stanzas.length){
      h+=`<div style="margin-top:6px">`;
      r.stanzas.forEach(st=>{
        if(st.obj) h+=`<div class="obj" style="font-size:13px">🎯 ${st.obj}</div>`;
        if(st.lines&&st.lines.length) h+=`<div style="color:#cfcac2;font-size:12.5px;margin-left:14px">“${st.lines.join('” / “')}”</div>`;
        if(st.scene) h+=`<div class="anim" style="margin-left:14px">🎬 ${st.scene}</div>`;
      });
      h+=`</div>`;
    } else {
      h+=`<div style="color:#7f8a99;font-size:12px">（该任务没有可用的对白数据）</div>`;
    }
    if(r.cast&&r.cast.length) h+=`<div style="color:#6f6a63;font-size:11.5px;margin-top:8px">出场：${r.cast.slice(0,6).join('、')}</div>`;
    h+=`</div>`;
  });
  v.innerHTML=h;
}
function renderFlows(v){
  let h=`<div class="tabs"><button onclick="tab='story';render()">剧情剧本</button>
  <button onclick="tab='graph';render()">任务图</button>
  <button onclick="tab='recap';render()">剧情回顾</button>
  <button onclick="tab='cap';render()">现场采集 (${D.captured.length})</button>
  <button onclick="tab='gr';render()">角色语料</button>
  <button class="on" onclick="tab='fl';render()">对话流 (${Object.keys(D.flows||{}).length})</button>
  <button onclick="tab='enc';render()">随机遭遇模板</button></div>`;
  const fl=D.flows||{}; const keys=Object.keys(fl);
  h+=`<h2>对话流 · 环境互动结构 <span style="color:#8d8a84;font-size:14px">${keys.length} 条</span></h2>`;
  h+=`<div class="sub">来自 <code>common/data/ai/conversations.meta</code>：每条流按顺序列出 <b>SpeechContext</b>，
  第 1 句=发起者，后续=回应者。这就是"和陌生人打招呼"的对话骨架，可直接用于砍2 的随机互动。</div>`;
  h+='<table><tr><th>对话流</th><th>句数</th><th>说话顺序（SpeechContext）</th></tr>';
  keys.forEach(k=>{
    h+=`<tr><td class="mono">${k}</td><td>${fl[k].length}</td><td class="mono" style="font-size:11.5px">${fl[k].join(' → ')}</td></tr>`;
  });
  h+='</table>'; v.innerHTML=h;
}
let GCUR=null, GQ='';
function renderGreet(v){
  const names=Object.keys(D.greet||{});
  let h=`<div class="tabs"><button onclick="tab='story';render()">剧情剧本</button>
  <button onclick="tab='graph';render()">任务图</button>
  <button onclick="tab='recap';render()">剧情回顾</button>
  <button onclick="tab='cap';render()">现场采集 (${D.captured.length})</button>
  <button class="on" onclick="tab='gr';render()">角色语料</button>
  <button onclick="tab='enc';render()">随机遭遇模板</button></div>`;
  const total=names.reduce((a,n)=>a+(D.greet[n]||[]).length,0);
  h+=`<h2>角色语料（环境/寒暄台词） <span style="color:#8d8a84;font-size:14px">${names.length} 个角色 · ${total.toLocaleString()} 条</span></h2>`;
  h+=`<div class="sub">来自各角色的语音文本包（<code>john_player.yldb</code> 等）——<b>包名即说话人</b>。可用于砍2 的随机互动语料。</div>`;
  h+=`<div style="margin:10px 0"><input id="gq" placeholder="搜索台词…" value="${GQ}" style="max-width:320px" oninput="GQ=this.value;renderGreet(document.getElementById('view'))"></div>`;
  h+=`<div class="chips">${names.map(n=>`<span style="cursor:pointer;${GCUR===n?'background:#3a3226;color:#fff':''}" onclick="GCUR='${n}';renderGreet(document.getElementById('view'))">${n} ${(D.greet[n]||[]).length}</span>`).join('')}</div>`;
  const list=GCUR? (D.greet[GCUR]||[]) : [];
  if(!GCUR){h+=`<p style="color:#7f8a99">选一个角色查看他会说的环境台词。</p>`;}
  else{
    const fl=list.filter(x=>!GQ||x.includes(GQ));
    h+=`<div class="sec">${GCUR} · ${fl.length} 条</div>`;
    h+=`<div style="columns:2;column-gap:28px;font-size:13px;color:#cfcac2">${fl.slice(0,400).map(x=>`<div style="break-inside:avoid;padding:2px 0">· ${x}</div>`).join('')}</div>`;
    if(fl.length>400) h+=`<p style="color:#7f8a99">（只显示前 400 条，用搜索缩小范围）</p>`;
  }
  v.innerHTML=h;
}
function renderCaptured(v){
  let h=`<div class="tabs"><button onclick="tab='story';render()">剧情剧本</button>
  <button onclick="tab='graph';render()">任务图</button>
  <button onclick="tab='recap';render()">剧情回顾</button>
  <button class="on" onclick="tab='cap';render()">现场采集 (${D.captured.length})</button>
  <button onclick="tab='enc';render()">随机遭遇模板</button></div>`;
  h+=`<h2>现场采集 <span style="color:#8d8a84;font-size:14px">${D.captured.length} 条</span></h2>`;
  h+=`<div class="sub">从录屏字幕里读出来的台词（含说话人）。剧本库里没有的对话（陌生人任务等）会落在这里，可听、可查。</div>`;
  if(!D.captured.length){v.innerHTML=h+'<p style="color:#7f8a99">还没有采集记录。</p>';return;}
  h+='<table><tr><th>说话人</th><th>台词</th><th>时间</th><th>来源</th></tr>';
  D.captured.forEach(c=>{
    const ms=Math.round(parseFloat(c.start)*100);
    const src=`audio/_captured/cap_${String(ms).padStart(5,'0')}.wav`;
    h+=`<tr><td style="color:#d8a15a">${c.speaker}</td>
      <td>${c.text} ${D.aud&&D.aud['_captured/cap_'+String(ms).padStart(5,'0')]?`<audio controls preload="none" src="${src}" style="height:22px;vertical-align:middle"></audio>`:''}</td>
      <td class="mono">${c.start}s–${c.end}s</td><td class="mono" style="font-size:11px">${c.source||''}</td></tr>`;
  });
  h+='</table>'; v.innerHTML=h;
}
function renderEnc(v){
  let h=`<div class="tabs"><button class="${tab==='story'?'on':''}" onclick="tab='story';render()">剧情剧本</button>
  <button class="${tab==='enc'?'on':''}" onclick="tab='enc';render()">随机遭遇模板</button></div>`;
  h+=`<h2>随机遭遇 / 世界事件模板 <span style="color:#8d8a84;font-size:14px">${D.enc.length} 个脚本</span></h2>`;
  h+=`<div class="sub">RDR2 的随机遭遇没有专属对白库：靠「区域人物池 + 行为脚本 + 通用呼喝」生成。这里导出的是可直接参数化成遭遇模板的要素。</div>`;
  h+=`<table><tr><th>脚本</th><th>类型</th><th>势力</th><th>生成</th><th>人物池</th><th>武器</th><th>主要行为</th><th>事件上下文</th></tr>`;
  D.enc.forEach(r=>{
    h+=`<tr><td class="mono">${r.script}</td><td>${r.archetype}</td><td>${r.faction}</td>
    <td>${r.spawn_calls}</td><td>${r.ped_pool_size}</td>
    <td class="mono">${(r.weapons||[]).filter(w=>w!=='WEAPON_UNARMED').slice(0,3).join(', ')}</td>
    <td class="mono">${(r.top_tasks||[]).slice(0,3).join(', ')}</td>
    <td class="mono">${(r.event_ctx||[]).slice(0,2).join(', ')}</td></tr>`;
  });
  h+='</table>'; v.innerHTML=h;
}
document.getElementById('q').oninput=e=>renderList(e.target.value.toLowerCase());
const _id=location.search.match(/[?&]id=([A-Z0-9]+)/i);
if(_id&&D.missions.some(x=>x.id===_id[1].toUpperCase())) cur=_id[1].toUpperCase();
const _pm=location.search.match(/play=([A-Z0-9]+)/i);
if(_pm){tab='graph';cur=_pm[1].toUpperCase();P={id:cur,i:+(location.search.match(/step=(\d+)/)||[0,0])[1]};}
renderList(''); render();
if(_pm) setTimeout(()=>playStep(),30);
</script></body></html>
"""

if __name__ == '__main__':
    main()
