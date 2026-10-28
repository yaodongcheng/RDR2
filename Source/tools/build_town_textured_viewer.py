"""生成"整个瓦伦丁小镇（真 UV + 原生贴图）"单文件查看器。

读 `town_textured.json`（`export_town_textured.py` 产出）：
  * 69 个高清建筑模型（共享几何 + 实例变换，按 `valentine.json` 的实体摆放）
  * 逐几何体材质 = **shader slot 语义**的 albedo，UV = 游戏原生 `TEXCOORD0`
  * RDR2 世界是 Z-up ⇒ 场景根节点绕 X 轴 −90° 转成 three 的 Y-up

输出：`export/levels/town/town_textured.html`
"""
import os
import json

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TOWN = os.path.join(ROOT, 'export/levels/town')
three = open(os.path.join(TOWN, 'three.module.js'), encoding='utf-8').read().replace('</script', '<\\/script')
data = json.load(open(os.path.join(TOWN, 'town_textured.json'), encoding='utf-8'))

HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>RDR2 瓦伦丁小镇 — 原生 UV + 原生贴图</title>
<style>
body{margin:0;background:#0b0d10;color:#d7e0ea;font:13px/1.5 "Segoe UI",system-ui,sans-serif;overflow:hidden}
#hud{position:fixed;left:10px;top:10px;background:#11161ce6;border:1px solid #263041;border-radius:8px;padding:10px 12px;max-width:460px;z-index:9}
#hud h1{font-size:14px;margin:0 0 6px;color:#8fd3ff} b{color:#ffd479}
button{background:#1b2330;color:#cfe0f0;border:1px solid #33415a;border-radius:6px;padding:3px 9px;margin:2px;cursor:pointer;font-size:12px}
button.on{background:#2c6fb5;border-color:#4b9ade;color:#fff}
#dbg{position:fixed;left:10px;bottom:8px;color:#7fe08a;font-size:12px;z-index:9}
#err{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);color:#f88;z-index:20}
</style></head><body>
<div id="hud">
  <h1>RDR2 瓦伦丁小镇 · 真 UV + 原生贴图</h1>
  <div>模型 <b>__NM__</b> 个 / 实例 <b>__NI__</b> 个 / 顶点 <b>__NV__</b> / 贴图 <b>__NT__</b> 张</div>
  <div>UV = 游戏原生 <code>TEXCOORD0</code>；材质 = shader slot 语义 albedo（不再 box mapping）</div>
  <div class="row"><span id="views"></span> <button id="fog">雾 开/关</button> <button id="lodt">游戏LOD地形</button></div>
  <div>左键旋转 / 滚轮缩放 / 右键平移</div>
</div>
<div id="dbg"></div><div id="err"></div>
<script id="three-src" type="text/plain">__THREE__</script>
<script id="data-src" type="application/json">__DATA__</script>
<script type="module">
const D=JSON.parse(document.getElementById('data-src').textContent);
let THREE,renderer,scene,cam,root,mats={},useFog=true;
let yaw=0.6,pitch=0.55,dist=520,px=0,py=0;
const TEX={};
(function(){
  const d=document.createElement('div');
})();
(async()=>{try{
 const url=URL.createObjectURL(new Blob([document.getElementById('three-src').textContent],{type:'text/javascript'}));
 THREE=await import(url);
 renderer=new THREE.WebGLRenderer({antialias:true});
 renderer.domElement.style.position='fixed';renderer.domElement.style.left='0';renderer.domElement.style.top='0';renderer.domElement.style.zIndex='0';
 const W=()=>Math.max(640,document.documentElement.clientWidth),H=()=>Math.max(480,document.documentElement.clientHeight);
 renderer.setSize(W(),H()); renderer.outputColorSpace=THREE.SRGBColorSpace; renderer.toneMapping=THREE.NoToneMapping; document.body.appendChild(renderer.domElement);
 scene=new THREE.Scene(); scene.background=new THREE.Color(0x9fb6cf);
 scene.fog=new THREE.Fog(0x9fb6cf, 400, 3000);
 cam=new THREE.PerspectiveCamera(45,W()/H(),0.5,8000);
 scene.add(new THREE.HemisphereLight(0xffffff,0x6b7480,0.8));
 const sun=new THREE.DirectionalLight(0xfff2dd,0.72); sun.position.set(1,2,1); scene.add(sun);
 const fill=new THREE.DirectionalLight(0xdfe8ff,0.22); fill.position.set(-1,1,-1); scene.add(fill);
 // RDR2 世界 Z-up -> three Y-up
 root=new THREE.Group(); root.rotation.x=-Math.PI/2; scene.add(root);
 function tex(name){ if(name in TEX) return TEX[name];
   const v=D.tex[name];
   if(!v||!v.b64){TEX[name]=null;return null;}
   const img=new Image(); img.src='data:image/png;base64,'+v.b64;
   const t=new THREE.Texture(img); t.wrapS=t.wrapT=THREE.RepeatWrapping;
   t.colorSpace=THREE.SRGBColorSpace; img.onload=()=>{t.needsUpdate=true;};
   TEX[name]=t; return t;
 }
 // 材质：按 albedo 名缓存
 function matFor(nm, shader){
   const key=nm+'|'+(shader||'');
   if(key in mats) return mats[key];
   const t=tex(nm);
   // ★ 道路/贴花是 `standard_decal*`（alpha 混合到地面）→ 必须 transparent，
   //   否则半透明边缘会被当不透明画出来（表现为"白色带子"）
   const decal=/decal/i.test(shader||'');
   const m=new THREE.MeshLambertMaterial({side:THREE.DoubleSide});
   if(t) m.map=t; else m.color.setHex(0xc07a7a);
   if(decal){ m.transparent=true; m.alphaTest=0.0; m.depthWrite=false; m.polygonOffset=true; m.polygonOffsetFactor=-1; m.polygonOffsetUnits=-1; }
   mats[key]=m; return m;
 }
 let nv=0;
 const geos={};
 for(const [name,M] of Object.entries(D.models)){
   const g=new THREE.BufferGeometry();
   g.setAttribute('position', new THREE.Float32BufferAttribute(M.p,3));
   g.setAttribute('uv', new THREE.Float32BufferAttribute(M.uv,2));
   g.setIndex(M.i); g.computeVertexNormals();
   const marr=[];
   M.g.forEach(gg=>{ const nm=D.tex_names[gg[2]]; marr.push(matFor(nm||'', gg[3]||'')); g.addGroup(gg[0],gg[1],marr.length-1); });
   geos[name]={g, marr}; nv+=M.vc;
 }
 for(const I of D.insts){
   const E=geos[I[0]]; if(!E) continue;
   const mesh=new THREE.Mesh(E.g, E.marr);
   mesh.position.set(I[1],I[2],I[3]);
   mesh.quaternion.set(I[4],I[5],I[6],I[7]);
   mesh.scale.set(I[8],I[9],I[10]);
   root.add(mesh);
 }
 // ---- 地形 LOD：世界空间平面 UV（这些网格没有顶点 UV）----
 // ⚠️ three 的程序缓存键默认**不含 onBeforeCompile** ⇒ 打过补丁的材质会和
 //   "同样参数的普通 Lambert(带 map)" **共用 program** ⇒ 世界空间 UV 会被建筑一起用（建筑变绿）。
 //   必须给补丁材质一个唯一 customProgramCacheKey，把它和普通材质隔开。
 function worldUV(mat, scale, tag){
   mat.onBeforeCompile = (sh)=>{
     sh.vertexShader = sh.vertexShader
       .replace('#include <uv_vertex>', 'vMapUv = (modelMatrix * vec4(position,1.0)).xz * ' + scale + ';');
   };
   mat.customProgramCacheKey = function(){ return 'worlduv_' + tag; };
   mat.needsUpdate = true;
   return mat;
 }
 const gtex=(n)=>{const t=tex(n); return t;};
 const groundMat=worldUV(new THREE.MeshLambertMaterial({side:THREE.DoubleSide, map:gtex('hea_grass_lush_01_abte'), color:0xdfe8c8}), 0.09, 1);
 // ================= 地形：高度场（512²，局部基准校准）=================
 // 这就是旧版"贴合建筑"的那套地面：连续曲面、建筑坐在上面，没有接缝/空洞。
 let terrMesh=null;
 (function buildHeightTerrain(){
   const TM=D.terr; if(!TM) return;
   const bin=atob(TM.b64); const S=TM.N;
   const H=new Float32Array(S*S); const dv=new DataView(new ArrayBuffer(bin.length));
   for(let i=0;i<bin.length;i++) dv.setUint8(i, bin.charCodeAt(i));
   for(let i=0;i<S*S;i++) H[i]=dv.getUint16(i*2,true)/65535*(TM.zmax-TM.zmin)+TM.zmin+TM.off;
   const sizeX=TM.x1-TM.x0, sizeY=TM.y1-TM.y0;
   const vt=new Float32Array(S*S*3), ct=new Float32Array(S*S*3), uvT=new Float32Array(S*S*2);
   const TS=6.0;
   for(let r=0;r<S;r++)for(let c=0;c<S;c++){
     const i2=r*S+c;
     const x=TM.x0+(c/(S-1))*sizeX, y=TM.y0+(r/(S-1))*sizeY;
     vt[i2*3]=x; vt[i2*3+1]=y; vt[i2*3+2]=H[i2];      // RDR2 坐标（root 负责 Z-up→Y-up）
     const t=Math.max(0,Math.min(1,(H[i2]-TM.zmin-TM.off)/(TM.zmax-TM.zmin)));
     const b=0.80+0.40*t;
     ct[i2*3]=b*(1.05-0.16*t); ct[i2*3+1]=b; ct[i2*3+2]=b*(0.94+0.08*t);
     uvT[i2*2]=x/TS; uvT[i2*2+1]=y/TS;
   }
   const it=[];
   for(let r=0;r<S-1;r++)for(let c=0;c<S-1;c++){
     const a=r*S+c,b2=r*S+c+1,d2=(r+1)*S+c,e2=(r+1)*S+c+1;
     it.push(a,d2,b2, b2,d2,e2);
   }
   const g=new THREE.BufferGeometry();
   g.setAttribute('position',new THREE.BufferAttribute(vt,3));
   g.setAttribute('color',new THREE.BufferAttribute(ct,3));
   g.setAttribute('uv',new THREE.BufferAttribute(uvT,2));
   g.setIndex(it); g.computeVertexNormals();
   const mat=new THREE.MeshLambertMaterial({vertexColors:true, map:tex('hea_grass_lush_01_abte'), side:THREE.DoubleSide});
   terrMesh=new THREE.Mesh(g,mat); root.add(terrMesh);
 })();
 // 游戏 LOD 地形瓦片：默认**关闭**（与高度场重复且粗，会盖房子）；按钮可开
 const lodTerr=new THREE.Group(); root.add(lodTerr);
 (function buildLodTerr(){
   const groundMat=worldUV(new THREE.MeshLambertMaterial({side:THREE.DoubleSide, map:tex('hea_grass_lush_01_abte'), color:0xdfe8c8}), 0.09, 1);
   for(const I of (D.terrain_insts||[])){
     const M=(D.terrain_models||{})[I[0]]; if(!M) continue;
     const g=new THREE.BufferGeometry();
     g.setAttribute('position', new THREE.Float32BufferAttribute(M.p,3));
     g.setIndex(M.i); g.computeVertexNormals();
     const m=new THREE.Mesh(g, groundMat);
     m.position.set(I[1],I[2],I[3]); m.quaternion.set(I[4],I[5],I[6],I[7]); m.scale.set(I[8],I[9],I[10]);
     lodTerr.add(m);
   }
   lodTerr.visible=false;
 })();
 // ---- 树木 ----
 const vgeos={};
 for(const [name,M] of Object.entries(D.veg_models||{})){
   const g=new THREE.BufferGeometry();
   g.setAttribute('position', new THREE.Float32BufferAttribute(M.p,3));
   g.setIndex(M.i); g.computeVertexNormals();
   vgeos[name]=g;
 }
 const treeMat=new THREE.MeshLambertMaterial({color:0x6b7a48, side:THREE.DoubleSide});
 for(const I of (D.veg_insts||[])){
   const g=vgeos[I[0]]; if(!g) continue;
   const m=new THREE.Mesh(g, treeMat);
   m.position.set(I[1],I[2],I[3]); root.add(m);
 }

 const c=new THREE.Vector3(D.center[0],117,-D.center[1]);   // root 绕 X −90° ⇒ RDR2 y 映射到 scene −z
 function upd(){ cam.position.set(c.x+Math.cos(yaw)*Math.cos(pitch)*dist, c.y+Math.sin(pitch)*dist, c.z+Math.sin(yaw)*Math.cos(pitch)*dist);
   cam.lookAt(c.x+px,c.y+py,c.z); }
 const vw=document.getElementById('views');
 const PRESET=[['全镇',0.6,0.42,520],['主街',0.35,0.20,170],['街口',1.15,0.26,90]];
 vw.innerHTML=PRESET.map((p,i)=>`<button class="${i===0?'on':''}" onclick="window.__v(${i})">${p[0]}</button>`).join('');
 window.__v=i=>{yaw=PRESET[i][1];pitch=PRESET[i][2];dist=PRESET[i][3];px=0;py=0;upd();
   vw.querySelectorAll('button').forEach((b,j)=>b.className=(i===j?'on':''));};
 document.getElementById('fog').onclick=e=>{useFog=!useFog; scene.fog=useFog?new THREE.Fog(0x9fb6cf,400,3000):null; e.target.className=useFog?'on':'';};
 document.getElementById('lodt').onclick=e=>{lodTerr.visible=!lodTerr.visible; e.target.className=lodTerr.visible?'on':'';};
 upd(); cam.updateMatrixWorld(true); renderer.render(scene,cam);
 const bb=new THREE.Box3().setFromObject(root); const bc=new THREE.Vector3(); bb.getCenter(bc); const bs=new THREE.Vector3(); bb.getSize(bs);
 document.getElementById('dbg').textContent=`建筑 ${Object.keys(D.models).length}型/${D.insts.length}例 · 地形 ${Object.keys(D.terrain_models||{}).length}型/${(D.terrain_insts||[]).length}例 · 树 ${Object.keys(D.veg_models||{}).length}型/${(D.veg_insts||[]).length}例 · 贴图 ${Object.keys(D.tex).length}`
   +` | rootChildren=${root.children.length} bboxCenter=(${bc.x.toFixed(0)},${bc.y.toFixed(0)},${bc.z.toFixed(0)}) size=(${bs.x.toFixed(0)},${bs.y.toFixed(0)},${bs.z.toFixed(0)})`
   +` | cam=(${cam.position.x.toFixed(0)},${cam.position.y.toFixed(0)},${cam.position.z.toFixed(0)}) target=(${c.x.toFixed(0)},${c.y.toFixed(0)},${c.z.toFixed(0)}) canvas=${renderer.domElement.width}x${renderer.domElement.height}`;
 let drag=0,lx=0,ly=0;
 renderer.domElement.addEventListener('mousedown',e=>{drag=e.button===2?2:1;lx=e.clientX;ly=e.clientY;});
 addEventListener('mouseup',()=>drag=0); addEventListener('contextmenu',e=>e.preventDefault());
 addEventListener('mousemove',e=>{ if(!drag)return; const dx=e.clientX-lx,dy=e.clientY-ly; lx=e.clientX; ly=e.clientY;
  if(drag===1){yaw-=dx*0.006; pitch=Math.max(-0.2,Math.min(1.45,pitch+dy*0.006));} else {px-=dx*dist*0.0012; py+=dy*dist*0.0012;} upd(); });
 renderer.domElement.addEventListener('wheel',e=>{e.preventDefault(); dist*=(1+Math.sign(e.deltaY)*0.12); dist=Math.max(3,Math.min(4000,dist)); upd();},{passive:false});
 addEventListener('resize',()=>{cam.aspect=W()/H();cam.updateProjectionMatrix();renderer.setSize(W(),H());});
 const Q=new URLSearchParams(location.search.replace(/^\?/,''));
 if(Q.has('v')) window.__v(parseInt(Q.get('v'))||0);
 (function loop(){requestAnimationFrame(loop);renderer.render(scene,cam);})();
 window.__ready=true;
}catch(e){document.getElementById('err').textContent='ERR: '+e.message; console.error(e);}})();
</script></body></html>"""

html = (HTML.replace('__THREE__', three)
        .replace('__DATA__', json.dumps(data, separators=(',', ':')))
        .replace('__NM__', str(len(data['models']))).replace('__NI__', str(len(data['insts'])))
        .replace('__NV__', str(sum(m['vc'] for m in data['models'].values())))
        .replace('__NT__', str(len(data['tex']))))
out = os.path.join(TOWN, 'town_textured.html')
open(out, 'w', encoding='utf-8').write(html)
print('wrote', out, round(os.path.getsize(out) / 1024 / 1024, 2), 'MB')
