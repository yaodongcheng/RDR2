"""生成 RDR2 人类骨架查看器（单文件 HTML）：用 `.yft` 的**权威 bind** 摆位。

数据：`export/skeleton_runtime/yft_skel.json`（756 骨：i/tag/parent/name）
     `export/skeleton_runtime/yft_bind.json`（1050 tag 的 bind 全局：pos + rot(3×3)）
只画 **72 根 `SKEL_*` 解剖骨**（MH_/PH_/ES_ 是服装/挂点骨，会糊成一团）。
输出：`export/skeleton_runtime/rdr2_skeleton.html`
"""
import os
import json
import math

ROOT = r'D:/BrainMaker/大镖客2解包分析'
SK = os.path.join(ROOT, 'export/skeleton_runtime')
three = open(os.path.join(ROOT, 'export/levels/town/three.module.js'), encoding='utf-8').read().replace('</script', '<\\/script')

skel = json.load(open(os.path.join(SK, 'yft_skel.json'), encoding='utf-8'))
bind = json.load(open(os.path.join(SK, 'yft_bind.json'), encoding='utf-8'))

bones = []
for b in skel['bones']:
    nm = b.get('name') or ''
    if not nm.startswith('SKEL_'):
        continue
    bd = bind.get(str(b['tag']))
    if not bd:
        continue
    bones.append(dict(i=b['i'], name=nm, tag=b['tag'], parent=b['parent'], pos=bd['pos']))
pos_by_i = {b['i']: b['pos'] for b in bones}
name_by_i = {b['i']: b['name'] for b in bones}

segs = []
for b in bones:
    p = b['parent']
    # 父链可能落在 MH_/PH_ 上；往上找到最近的 SKEL_ 祖先
    guard = 0
    while p is not None and p != -1 and p not in pos_by_i and guard < 40:
        p = skel['bones'][p]['parent'] if 0 <= p < len(skel['bones']) else -1
        guard += 1
    if p in pos_by_i:
        segs.append([pos_by_i[p], b['pos'], b['name']])

print(f'SKEL_ 骨 {len(bones)} 根，画 {len(segs)} 段')
xs = [b['pos'][0] for b in bones]; ys = [b['pos'][1] for b in bones]; zs = [b['pos'][2] for b in bones]
print(f'bind 包围盒 x[{min(xs):.3f},{max(xs):.3f}] y[{min(ys):.3f},{max(ys):.3f}] z[{min(zs):.3f},{max(zs):.3f}]')
print(f'身高(z 跨度) = {max(zs)-min(zs):.3f} m')

LABELS = ['SKEL_ROOT', 'SKEL_Pelvis', 'SKEL_Spine2', 'SKEL_Neck1', 'SKEL_Head',
          'SKEL_L_Hand', 'SKEL_R_Hand', 'SKEL_L_Foot', 'SKEL_R_Foot',
          'SKEL_L_UpperArm', 'SKEL_R_UpperArm', 'SKEL_L_Calf', 'SKEL_R_Calf']

HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>RDR2 人类骨架（.yft 权威 bind，72 根 SKEL_ 骨）</title>
<style>body{margin:0;background:#0b0d10;color:#d7e0ea;font:13px/1.55 "Segoe UI",system-ui,sans-serif;overflow:hidden}
#hud{position:fixed;left:10px;top:10px;background:#11161ce6;border:1px solid #263041;border-radius:8px;padding:10px 12px;max-width:420px;z-index:9}
#hud h1{font-size:14px;margin:0 0 6px;color:#8fd3ff} b{color:#ffd479}
button{background:#1b2330;color:#cfe0f0;border:1px solid #33415a;border-radius:6px;padding:3px 8px;margin:2px;cursor:pointer}
button.on{background:#2c6fb5;border-color:#4b9ade;color:#fff}
#err{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);color:#f88;z-index:20}</style></head><body>
<div id="hud">
 <h1>RDR2 人类骨架 — `.yft` 权威 bind（A-pose）</h1>
 <div>骨：<b>__NB__</b> 根 <code>SKEL_*</code>（从 756 骨中筛出解剖骨）· 段：<b>__NS__</b></div>
 <div>bind 包围盒 x[__BX__] y[__BY__] z[__BZ__] · <b>身高（Z 跨度）__H__ m</b></div>
 <div>视图：<span id="vw"></span></div>
 <div>左键旋转 / 滚轮缩放 / 右键平移</div>
</div>
<div id="err"></div>
<script id="three-src" type="text/plain">__THREE__</script>
<script id="data-src" type="application/json">__DATA__</script>
<script type="module">
const D=JSON.parse(document.getElementById('data-src').textContent);
let THREE,renderer,scene,cam,root=new Object();
let view='yup', yaw=1.25, pitch=0.06, dist=2.6, px=0, py=0;
function mklabel(txt){
  const c=document.createElement('canvas'); c.width=256; c.height=64;
  const g=c.getContext('2d'); g.fillStyle='#0b0d10'; g.fillRect(0,0,256,64);
  g.fillStyle='#8fd3ff'; g.font='bold 30px Segoe UI, sans-serif'; g.textBaseline='middle';
  g.fillText(txt.replace('SKEL_',''), 8, 34);
  const t=new THREE.CanvasTexture(c); t.colorSpace=THREE.SRGBColorSpace;
  const s=new THREE.Sprite(new THREE.SpriteMaterial({map:t, depthTest:false}));
  s.scale.set(0.20,0.05,1); return s;
}
(async()=>{try{
 const url=URL.createObjectURL(new Blob([document.getElementById('three-src').textContent],{type:'text/javascript'}));
 THREE=await import(url);
 renderer=new THREE.WebGLRenderer({antialias:true});
 renderer.domElement.style.position='fixed';renderer.domElement.style.left='0';renderer.domElement.style.top='0';renderer.domElement.style.zIndex='0';
 const W=()=>Math.max(640,document.documentElement.clientWidth),H=()=>Math.max(480,document.documentElement.clientHeight);
 renderer.setSize(W(),H()); renderer.outputColorSpace=THREE.SRGBColorSpace; document.body.appendChild(renderer.domElement);
 scene=new THREE.Scene(); scene.background=new THREE.Color(0x0e1116);
 cam=new THREE.PerspectiveCamera(40,W()/H(),0.01,200);
 root=new THREE.Group(); scene.add(root);
 // 世界坐标轴：X 红 / Y 绿 / Z 蓝（RDR2 为 Z-up）
 root.add(new THREE.AxesHelper(0.35));
 const grid=new THREE.GridHelper(3,24,0x2a3a4a,0x1b2530); grid.rotation.x=Math.PI/2; grid.visible=(false); root.add(grid);
 // 骨骼段
 const pts=[]; D.segs.forEach(s=>{pts.push(s[0][0],s[0][1],s[0][2], s[1][0],s[1][1],s[1][2]);});
 const lg=new THREE.BufferGeometry(); lg.setAttribute('position', new THREE.Float32BufferAttribute(pts,3));
 root.add(new THREE.LineSegments(lg, new THREE.LineBasicMaterial({color:0x7fe0ff, linewidth:2})));
 // 关节球
 const jg=new THREE.SphereGeometry(0.008,10,8); const jm=new THREE.MeshBasicMaterial({color:0xffd479});
 D.bones.forEach(b=>{const m=new THREE.Mesh(jg,jm); m.position.set(b.pos[0],b.pos[1],b.pos[2]); root.add(m);});
 // 标签
 D.labels.forEach(l=>{const b=D.bones.find(x=>x.name===l); if(!b)return;
   const s=mklabel(l); s.position.set(b.pos[0]+0.035,b.pos[1],b.pos[2]); root.add(s);});
 let tgt=new THREE.Vector3(0,0,0);
 function applyView(){
   root.rotation.set(0,0,0); if(view==='yup') root.rotation.x=-Math.PI/2;
   root.updateMatrixWorld(true);
   const box=new THREE.Box3().setFromObject(root); const c=new THREE.Vector3(); box.getCenter(c);
   const sz=new THREE.Vector3(); box.getSize(sz); tgt=c; dist=Math.max(sz.x,sz.y,sz.z)*1.35;
 }
 function upd(){ cam.position.set(tgt.x+Math.cos(yaw)*Math.cos(pitch)*dist, tgt.y+Math.sin(pitch)*dist, tgt.z+Math.sin(yaw)*Math.cos(pitch)*dist);
   cam.lookAt(tgt.x+px, tgt.y+py, tgt.z); }
 applyView(); upd(); cam.updateMatrixWorld(true); renderer.render(scene,cam);
 const vw=document.getElementById('vw');
 vw.innerHTML=['Z-up（RDR2 原始）','Y-up（转正）'].map((n,i)=>{const v=(i===0?'zup':'yup');
   return `<button class="${v===view?'on':''}" onclick="window.__v('${v}')">${n}</button>`;}).join('');
 window.__v=v=>{view=v; applyView(); upd(); cam.updateMatrixWorld(true); renderer.render(scene,cam);
   vw.querySelectorAll('button').forEach((b,i)=>b.className=((i===0?'zup':'yup')===v?'on':''));};
 let drag=0,lx=0,ly=0;
 renderer.domElement.addEventListener('mousedown',e=>{drag=e.button===2?2:1;lx=e.clientX;ly=e.clientY;});
 addEventListener('mouseup',()=>drag=0); addEventListener('contextmenu',e=>e.preventDefault());
 addEventListener('mousemove',e=>{ if(!drag)return; const dx=e.clientX-lx,dy=e.clientY-ly; lx=e.clientX; ly=e.clientY;
  if(drag===1){yaw-=dx*0.006; pitch=Math.max(-1.4,Math.min(1.4,pitch+dy*0.006));} else {px-=dx*dist*0.0012; py+=dy*dist*0.0012;} upd(); });
 renderer.domElement.addEventListener('wheel',e=>{e.preventDefault(); dist*=(1+Math.sign(e.deltaY)*0.12); dist=Math.max(0.4,Math.min(40,dist)); upd();},{passive:false});
 addEventListener('resize',()=>{cam.aspect=W()/H();cam.updateProjectionMatrix();renderer.setSize(W(),H());});
 (function loop(){requestAnimationFrame(loop);renderer.render(scene,cam);})();
 window.__ready=true;
}catch(e){document.getElementById('err').textContent='ERR: '+e.message; console.error(e);}})();
</script></body></html>"""

data = dict(bones=[dict(name=b['name'], pos=b['pos']) for b in bones],
            segs=[s for s in segs],
            labels=LABELS,
            center=[(min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2])
html = (HTML.replace('__THREE__', three)
        .replace('__DATA__', json.dumps(data, separators=(',', ':')))
        .replace('__NB__', str(len(bones))).replace('__NS__', str(len(segs)))
        .replace('__BX__', f'{min(xs):.3f},{max(xs):.3f}').replace('__BY__', f'{min(ys):.3f},{max(ys):.3f}')
        .replace('__BZ__', f'{min(zs):.3f},{max(zs):.3f}').replace('__H__', f'{max(zs)-min(zs):.3f}'))
out = os.path.join(SK, 'rdr2_skeleton.html')
open(out, 'w', encoding='utf-8').write(html)
print('wrote', out, round(os.path.getsize(out) / 1024 / 1024, 2), 'MB')
