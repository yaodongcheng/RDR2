"""生成"正确材质"场景查看器（单文件 HTML，双击即开）。

读 `materials_demo.json`（由 `export_building_materials.py` 产出）：
  * 顶点用**游戏原生 UV**（TEXCOORD0 → 第 1 层；TEXCOORD1 → 第 2 层）
  * 材质按 **shader slot 语义**绑定（diffusetex / diffusetex2 / materialA / normal / tintpalettetex）
  * 三种模式对照：`原生 albedo（真 UV）` / `+第二层（遮罩混合）` / `旧：box map`
输出：`export/levels/town/materials_demo.html`
"""
import os
import json

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TOWN = os.path.join(ROOT, 'export/levels/town')
three = open(os.path.join(TOWN, 'three.module.js'), encoding='utf-8').read().replace('</script', '<\\/script')
data = json.load(open(os.path.join(TOWN, 'materials_demo.json'), encoding='utf-8'))

HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>RDR2 Valentine — 原生 UV + 分层材质（按 shader slot 语义）</title>
<style>
 body{margin:0;background:#0b0d10;color:#d7e0ea;font:13px/1.5 "Segoe UI",system-ui,sans-serif;overflow:hidden}
 #hud{position:fixed;left:10px;top:10px;background:#11161ce6;border:1px solid #263041;border-radius:8px;padding:10px 12px;max-width:430px;z-index:9}
 #hud h1{font-size:14px;margin:0 0 6px;color:#8fd3ff}
 #hud b{color:#ffd479}
 .row{margin:6px 0}
 button{background:#1b2330;color:#cfe0f0;border:1px solid #33415a;border-radius:6px;padding:3px 8px;margin:2px;cursor:pointer;font-size:12px}
 button.on{background:#2c6fb5;border-color:#4b9ade;color:#fff}
 #mat{position:fixed;right:10px;top:10px;background:#11161ce6;border:1px solid #263041;border-radius:8px;padding:8px 10px;width:390px;max-height:88vh;overflow:auto;z-index:9;font-size:11.5px}
 #mat .g{border-bottom:1px solid #223;padding:4px 0}
 #mat .sh{color:#8fd3ff}
 #mat .k{color:#8a9bb0;display:inline-block;width:64px}
 #mat .fb{color:#ffab6b}
 #err{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);color:#f88;font-size:16px;z-index:20}
</style></head><body>
<div id="hud">
  <h1>RDR2 Valentine · 场景模型贴图（原生 UV + shader slot 语义材质）</h1>
  <div>建筑：<span id="bld"></span></div>
  <div class="row">模式：<span id="mode"></span></div>
  <div class="row">UV 缩放 <input id="uvs" type="range" min="0.25" max="4" step="0.05" value="1" style="width:150px"> <span id="uvv">1.00</span></div>
  <div class="row">光照 <input id="litv" type="range" min="0.2" max="1" step="0.05" value="0.85" style="width:120px"> · 左键旋转 / 滚轮缩放 / 右键平移</div>
  <div style="color:#8a9bb0">数据来源：<code>materials_demo.json</code>（顶点 UV 由 VertexDeclarationG9 读出；材质名由 shader slot 语义解析）</div>
</div>
<div id="dbg" style="position:fixed;left:10px;bottom:8px;color:#7fe08a;z-index:9;font-size:12px"></div>
<div id="mat"></div><div id="err"></div>
<script id="data-src" type="application/json">__DATA__</script>
<script id="three-src" type="text/plain">__THREE__</script>
<script type="module">
const DATA=JSON.parse(document.getElementById('data-src').textContent);
const TEX={};               // name -> THREE.Texture
let THREE=null, renderer, scene, cam, groups=[], cur=0;
let mode=0, uvScale=1, litAmt=0.85;

const VERT=`
attribute vec4 aUv; attribute vec4 aCol; attribute vec3 aNormal;
uniform float uvScale;
varying vec2 vU0; varying vec2 vU1; varying vec4 vC; varying vec3 vN;
void main(){ vU0=aUv.xy*uvScale; vU1=aUv.zw*uvScale; vC=aCol; vN=normalize(normalMatrix*aNormal);
  gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }`;

const FRAG=`
uniform sampler2D t0,t1,tm,tp; uniform float useB,usePal,lit;
varying vec2 vU0; varying vec2 vU1; varying vec4 vC; varying vec3 vN;
float maskAt(){ 
  vec4 m=texture2D(tm,vU1);
  return clamp(m.r,0.0,1.0);
}
void main(){
  vec3 c=texture2D(t0,vU0).rgb;
  if(useB>0.5){ vec3 c1=texture2D(t1,vU1).rgb; c=mix(c,c1,maskAt()); }
  if(usePal>0.5){ vec3 tk=texture2D(tp, vec2(vC.r, vC.g)).rgb; c*= (0.35+1.3*tk); }
  float d=max(dot(normalize(vN), normalize(vec3(0.45,0.75,0.5))),0.0);
  float amb=0.55;
  vec3 lit_c=c*(amb+lit*d);
  gl_FragColor=vec4(pow(clamp(lit_c,0.0,1.0),vec3(0.4545)),1.0);
}`;

function tex(name){ if(TEX[name]!==undefined)return TEX[name];
  const d=DATA.tex[name];
  if(!d||!d.b64){TEX[name]=null;return null;}
  const img=new Image(); img.src='data:image/png;base64,'+d.b64;
  const t=new THREE.Texture(img); t.wrapS=t.wrapT=THREE.RepeatWrapping; t.colorSpace=THREE.SRGBColorSpace;
  img.onload=()=>{t.needsUpdate=true;};
  TEX[name]=t; return t;
}
function build(){
  const keys=Object.keys(DATA.buildings);
  keys.forEach((k,bi)=>{
    const B=DATA.buildings[k];
    const g=new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(B.p,3));
    // 真 UV：uv0 -> 标准 uv 槽（第 1 层）；uv1 存 aUv 供第二层用
    const uv=new Float32Array(B.uv.length/2);
    for(let i=0,n=B.uv.length/4;i<n;i++){ uv[2*i]=B.uv[4*i]; uv[2*i+1]=B.uv[4*i+1]; }
    g.setAttribute('uv', new THREE.BufferAttribute(uv,2));
    g.setAttribute('aUv', new THREE.Float32BufferAttribute(B.uv,4));
    g.setAttribute('aCol', new THREE.Float32BufferAttribute(B.col.map(v=>v/255),4));
    g.setIndex(B.i);
    g.computeVertexNormals();
    const mats=[];
    B.g.forEach(ge=>{
      const mat=ge.mat||{};
      const tA=tex((mat.a&&mat.a.name)||'');
      const tB=tex((mat.b&&mat.b.name)||'');
      const m=new THREE.MeshLambertMaterial({map:tA||null, color:0xffffff, side:THREE.DoubleSide});
      if(!tA){ m.color.setHex(0xc07a7a); }         // 缺贴图 -> 红棕提示
      m.userData={tB:tB, name:(mat.a&&mat.a.name)||''};
      mats.push(m);
      g.addGroup(ge.start, ge.count, mats.length-1);
    });
    const mesh=new THREE.Mesh(g, mats);
    const minx=B.bbox[0][0], maxx=B.bbox[1][0], cx=(minx+maxx)/2;
    // RDR2 drawable 局部空间是 Z-up -> 转到 three 的 Y-up
    mesh.rotation.x = -Math.PI/2;
    mesh.position.set(-cx + bi*Math.max(26,(B.bbox[1][0]-B.bbox[0][0])*1.5), -B.bbox[0][2], 0);
    mesh.frustumCulled=false;
    const grp=new THREE.Group(); grp.add(mesh); grp.userData={mesh:mesh,b:keys[bi]};
    scene.add(grp); groups.push(grp);
  });
}
function mat0n(mat,k){ return (mat[k]&&mat[k].name)||''; }
let _white=null;
function texWhite(){ if(!_white){_white=new THREE.DataTexture(new Uint8Array([255,255,255,255]),1,1); _white.needsUpdate=true;} return _white; }

function applyUniforms(){
  // UV 缩放：对所有已加载贴图统一设置 repeat（贴图共享，等价于全局 UV 缩放）
  Object.values(TEX).forEach(t=>{ if(t&&t.isTexture){ t.repeat.set(uvScale,uvScale); t.needsUpdate=true; } });
  groups.forEach(g=>{
    g.userData.mesh.material.forEach(mm=>{
      const want=(mode===1 && mm.userData && mm.userData.tB)? mm.userData.tB : tex((mm.userData&&mm.userData.name)||'');
      if(mm.map!==want){ mm.map=want; mm.needsUpdate=true; }
    });
  });
}
function drawHUD(){
  const tk=Object.keys(DATA.buildings);
  document.getElementById('bld').innerHTML=tk.map((k,i)=>`<button class="${i===cur?'on':''}" onclick="window.__sel(${i})">${DATA.buildings[k].name}</button>`).join('');
  document.getElementById('mode').innerHTML=['原生 albedo（真 UV）','+ 第二层（遮罩混合）','（保留）','+ 调色板（实验）']
    .map((n,i)=>`<button class="${i===mode?'on':''}" onclick="window.__mode(${i})">${n}</button>`).join('');
  document.getElementById('uvv').textContent=uvScale.toFixed(2);
  // 材质清单
  const B=DATA.buildings[tk[cur]]; let h='';
  ['a','b','m','n','p'].forEach(()=>{});
  B.g.forEach((ge,i)=>{
    const names=Object.entries(ge.mat||{}).map(([k,v])=>`<div><span class="k">${({a:'albedo',b:'albedo2',m:'mask',n:'normal',p:'palette'})[k]||k}</span>${v.name}${v.missing?' <span class="fb">（缺）</span>':''}${v.fb?` <span class="fb">≈${v.fb}</span>`:''}</div>`).join('');
    h+=`<div class="g"><b>#${i}</b> <span class="sh">${ge.shader||'?'}</span> <span style="color:#7c8b9c">sid=${ge.sid} 语义=${ge.sem}</span>${names}</div>`;
  });
  document.getElementById('mat').innerHTML=`<div style="color:#8fd3ff;margin-bottom:4px">${B.name} — ${B.g.length} 个几何体 / ${B.vc} 顶点 / ${B.tc} 三角面</div>`+h;
}
window.__sel=i=>{cur=i; focus(); drawHUD();};
window.__mode=i=>{mode=i; applyUniforms(); drawHUD();};

let yaw=0.9, pitch=0.18, dist=70, panX=0, panY=0;
let tgt=null;
function focus(){
  const G=groups[cur]; if(!G){return;}
  const box=new THREE.Box3().setFromObject(G.userData.mesh);
  const c=new THREE.Vector3(); box.getCenter(c); const s=new THREE.Vector3(); box.getSize(s);
  if(!tgt) tgt=new THREE.Vector3();
  tgt.copy(c);
  dist=Math.max(8, Math.max(s.x,s.y,s.z)*2.2);
  panX=0; panY=0; upd();
  const dbg=document.getElementById('dbg');
  if(dbg){
    const m=G.userData.mesh;
    const p0=new THREE.Vector3(m.geometry.attributes.position.getX(0),m.geometry.attributes.position.getY(0),m.geometry.attributes.position.getZ(0)).applyMatrix4(m.matrixWorld);
    const ndc=p0.clone().project(cam);
    dbg.textContent=`mesh=${G.userData.b} children=${scene.children.length} groups=${m.material.length} idx=${m.geometry.index.count} pos=${m.geometry.attributes.position.count} uv=${m.geometry.attributes.aUv.count} col=${m.geometry.attributes.aCol.count} bs=${m.geometry.boundingSphere?m.geometry.boundingSphere.radius.toFixed(1):'null'}`
      +` meshWorldPos=(${m.position.x.toFixed(1)},${m.position.y.toFixed(1)},${m.position.z.toFixed(1)})`
      +` camPos=(${cam.position.x.toFixed(1)},${cam.position.y.toFixed(1)},${cam.position.z.toFixed(1)})`
      +` v0=${p0.x.toFixed(1)},${p0.y.toFixed(1)},${p0.z.toFixed(1)} ndc=${ndc.x.toFixed(2)},${ndc.y.toFixed(2)},${ndc.z.toFixed(2)}`;
  }
}
function upd(){
  cam.position.set(tgt.x+Math.cos(yaw)*Math.cos(pitch)*dist, tgt.y+Math.sin(pitch)*dist, tgt.z+Math.sin(yaw)*Math.cos(pitch)*dist);
  cam.lookAt(tgt.x+panX, tgt.y+panY, tgt.z);
}
(async function(){
 try{
  const url=URL.createObjectURL(new Blob([document.getElementById('three-src').textContent],{type:'text/javascript'}));
  THREE=await import(url);
  renderer=new THREE.WebGLRenderer({antialias:true}); renderer.domElement.style.position='fixed';renderer.domElement.style.left='0';renderer.domElement.style.top='0';
  renderer.domElement.style.zIndex='0';
  const W=()=>Math.max(640,document.documentElement.clientWidth), H=()=>Math.max(480,document.documentElement.clientHeight);
  renderer.setSize(W(),H());
  renderer.outputColorSpace=THREE.SRGBColorSpace; document.body.appendChild(renderer.domElement);
  scene=new THREE.Scene(); scene.background=new THREE.Color(0x8fa9c4);
  cam=new THREE.PerspectiveCamera(45, W()/H(), 0.1, 5000);
  scene.add(new THREE.HemisphereLight(0xffffff,0x404860,1.0));
  document.getElementById('dbg').textContent='THREE 已加载，正在构建几何体…';
  build(); applyUniforms(); drawHUD(); focus();
  // URL 参数：?mode=1&b=2&all=1&uv=1.5
  const Q=new URLSearchParams(location.search.replace(/^\?/,''));
  if(Q.has('mode')){ mode=parseInt(Q.get('mode'))||0; }
  if(Q.has('b')){ cur=Math.max(0,Math.min(groups.length-1,parseInt(Q.get('b'))||0)); focus(); }
  if(Q.has('uv')){ uvScale=parseFloat(Q.get('uv'))||1; }
  if(Q.has('all')){
    const box=new THREE.Box3(); groups.forEach(g=>box.expandByObject(g.userData.mesh));
    const c=new THREE.Vector3(); box.getCenter(c); const sz=new THREE.Vector3(); box.getSize(sz);
    tgt=c; dist=Math.max(sz.x,sz.y,sz.z)*1.15; yaw=1.35; pitch=0.12;
  }
  applyUniforms(); drawHUD(); upd();
  cam.updateMatrixWorld(true); renderer.render(scene,cam);   // 先同步出一帧，别等 rAF
  document.getElementById('uvs').oninput=e=>{uvScale=parseFloat(e.target.value); applyUniforms(); document.getElementById('uvv').textContent=uvScale.toFixed(2);};
  document.getElementById('litv').oninput=e=>{litAmt=parseFloat(e.target.value); applyUniforms();};
  let drag=0,lx=0,ly=0;
  renderer.domElement.addEventListener('mousedown',e=>{drag=e.button===2?2:1;lx=e.clientX;ly=e.clientY;});
  addEventListener('mouseup',()=>drag=0);
  addEventListener('contextmenu',e=>e.preventDefault());
  addEventListener('mousemove',e=>{ if(!drag)return; const dx=e.clientX-lx,dy=e.clientY-ly; lx=e.clientX; ly=e.clientY;
    if(drag===1){yaw-=dx*0.006; pitch=Math.max(-1.3,Math.min(1.3,pitch+dy*0.006));} else {panX-=dx*dist*0.0012; panY+=dy*dist*0.0012;} upd(); });
  renderer.domElement.addEventListener('wheel',e=>{e.preventDefault(); dist*= (1+Math.sign(e.deltaY)*0.12); dist=Math.max(2,Math.min(3000,dist)); upd();},{passive:false});
  addEventListener('resize',()=>{cam.aspect=W()/H();cam.updateProjectionMatrix();renderer.setSize(W(),H());});
  (function loop(){requestAnimationFrame(loop);renderer.render(scene,cam);})();
  window.__ready=true;
 }catch(err){ document.getElementById('err').textContent='ERR: '+err.message; window.__err=err.message; console.error(err);}
})();
</script></body></html>"""

html = HTML.replace('__THREE__', three).replace('__DATA__', json.dumps(data, separators=(',', ':')))
out = os.path.join(TOWN, 'materials_demo.html')
open(out, 'w', encoding='utf-8').write(html)
print('wrote', out, round(os.path.getsize(out) / 1024 / 1024, 2), 'MB')
