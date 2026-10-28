"""Build a self-contained single-file town viewer (works from file://, no server)."""
import json, os, sys

TOWN = r"D:/BrainMaker/大镖客2解包分析/export/levels/town"
three = open(os.path.join(TOWN, "three.module.js"), encoding="utf-8").read()
E = json.load(open(os.path.join(TOWN, "valentine.json"), encoding="utf-8"))
A = json.load(open(os.path.join(TOWN, "archetypes.json"), encoding="utf-8"))

# keep only needed archetype entries
ents = [[e[0], e[1], e[2], e[3], e[4], e[5], e[6], e[7], e[8], e[9]] for e in E]
arch = {str(k): v for k, v in A.items() if any(str(k) == str(e[0]) for e in E)}

three_esc = three.replace("</script", "<\\/script")

html = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>RDR2 Valentine 瓦伦丁 · 关卡地编复原</title>
<style>
 body{margin:0;background:#0d1117;color:#dfe6ee;font-family:"Microsoft YaHei",system-ui,sans-serif;overflow:hidden}
 #hud{position:fixed;left:12px;top:10px;font-size:13px;background:#0f1318dd;padding:9px 13px;border-radius:8px;line-height:1.8;pointer-events:none}
 #hud b{color:#6ec1ff}
 #lg{position:fixed;right:12px;bottom:12px;font-size:12px;background:#0f1318dd;padding:9px 13px;border-radius:8px;line-height:1.7;pointer-events:none}
 .k{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}
 #err{position:fixed;left:12px;bottom:12px;color:#ff8d8d;font-size:12px}
</style></head><body>
<div id="hud">RDR2 <b>Valentine 瓦伦丁</b> · 关卡地编复原<br>
 <span id="n"></span> 个实体（解析自 .ymap）· <span id="nb"></span> 个用 archetype 真实包围盒<br>
 左键拖动=旋转 · 滚轮=缩放 · 右键拖动=平移</div>
<div id="lg">
 <div><span class="k" style="background:#8fb8ff"></span>大结构</div>
 <div><span class="k" style="background:#e8c07a"></span>建筑</div>
 <div><span class="k" style="background:#7fd6a8"></span>中物件</div>
 <div><span class="k" style="background:#e88a9a"></span>小物件</div>
</div>
<div id="err"></div>
<script id="three-src" type="text/plain">__THREE__</script>
<script>
window.__ENTS = __ENTS__;
window.__ARCH = __ARCH__;
</script>
<script type="module">
try{
  const src = document.getElementById('three-src').textContent;
  const url = URL.createObjectURL(new Blob([src], {type:'text/javascript'}));
  const THREE = await import(url);
  const E = window.__ENTS, A = window.__ARCH;
  const renderer = new THREE.WebGLRenderer({antialias:true});
  renderer.setSize(innerWidth, innerHeight); document.body.appendChild(renderer.domElement);
  const scene = new THREE.Scene(); scene.background = new THREE.Color(0x0d1117);
  const cam = new THREE.PerspectiveCamera(50, innerWidth/innerHeight, 1, 30000);
  scene.add(new THREE.HemisphereLight(0xffffff,0x2a3340,1.7));
  const sun = new THREE.DirectionalLight(0xffffff,1.5); sun.position.set(-0.4,1,0.5); scene.add(sun);
  let cx=0, cy=0; for(const e of E){cx+=e[1]; cy+=e[2];} cx/=E.length; cy/=E.length;
  let minZ=1e9, maxR=0;
  for(const e of E){ if(e[3]<minZ)minZ=e[3]; }
  for(const e of E){ const r=Math.hypot(e[1]-cx,e[2]-cy); if(r>maxR)maxR=r; }
  const geo=new THREE.BoxGeometry(1,1,1), mat=new THREE.MeshLambertMaterial();
  const inst=new THREE.InstancedMesh(geo, mat, E.length);
  const m4=new THREE.Matrix4(), q=new THREE.Quaternion(), p=new THREE.Vector3(), s=new THREE.Vector3(), c=new THREE.Color();
  let nbox=0;
  E.forEach((e,i)=>{
    const [arch,x,y,z,qx,qy,qz,qw,sxy,sz]=e;
    let dx=2.5, dy=2.5, dz=2.5, sized=false;
    const b=A[String(arch)];
    if(b){ const bx=Math.abs(b[3]-b[0]), by=Math.abs(b[4]-b[1]), bz=Math.abs(b[5]-b[2]);
      if(Math.max(bx,by,bz)<=30 && bz>=0.8){ dx=Math.max(0.6,bx); dy=Math.max(0.6,by); dz=Math.max(0.8,bz); sized=true; nbox++; } }
    p.set(x-cx, (z-minZ)+dz/2, y-cy);
    q.set(qx,qy,qz,qw);
    s.set(dx, dz, dy);            // RDR2 Z-up -> three.js Y-up
    m4.compose(p,q,s); inst.setMatrixAt(i,m4);
    const m=Math.max(dx,dy,dz);
    if(!sized) c.set(0.30,0.32,0.38);
    else if(m>25) c.set(0.56,0.72,1.0);
    else if(m>8)  c.set(0.91,0.75,0.48);
    else if(m>3)  c.set(0.50,0.84,0.66);
    else          c.set(0.91,0.54,0.60);
    inst.setColorAt(i,c);
  });
  inst.instanceMatrix.needsUpdate=true; if(inst.instanceColor) inst.instanceColor.needsUpdate=true;
  scene.add(inst);
  document.getElementById('n').textContent=E.length;
  document.getElementById('nb').textContent=nbox;
  // simple orbit
  let yaw=0.9, pitch=0.55, dist=maxR*2.2, panX=0, panY=0;
  function upd(){ cam.position.set(Math.cos(yaw)*Math.cos(pitch)*dist+panX, Math.sin(pitch)*dist+panY, Math.sin(yaw)*Math.cos(pitch)*dist); cam.lookAt(panX,panY,0); }
  upd();
  let drag=0, lx=0, ly=0;
  renderer.domElement.addEventListener('mousedown',ev=>{drag=ev.button===2?2:1;lx=ev.clientX;ly=ev.clientY;});
  addEventListener('mouseup',()=>drag=0);
  addEventListener('contextmenu',e=>e.preventDefault());
  addEventListener('mousemove',ev=>{ if(!drag)return; const dx=ev.clientX-lx, dy=ev.clientY-ly; lx=ev.clientX; ly=ev.clientY;
    if(drag===1){ yaw-=dx*0.005; pitch=Math.max(-1.4,Math.min(1.5,pitch+dy*0.005)); } else { panX-=dx*dist*0.001; panY+=dy*dist*0.001; } upd(); });
  renderer.domElement.addEventListener('wheel',ev=>{ ev.preventDefault(); dist*=(1+Math.sign(ev.deltaY)*0.1); dist=Math.max(5,Math.min(maxR*12,dist)); upd(); },{passive:false});
  addEventListener('resize',()=>{ cam.aspect=innerWidth/innerHeight; cam.updateProjectionMatrix(); renderer.setSize(innerWidth,innerHeight); });
  (function loop(){requestAnimationFrame(loop);renderer.render(scene,cam);})();
}catch(err){ document.getElementById('err').textContent='ERR: '+err.message; }
</script></body></html>"""

html = html.replace("__THREE__", three_esc)
html = html.replace("__ENTS__", json.dumps(ents, separators=(',', ':')))
html = html.replace("__ARCH__", json.dumps(arch, separators=(',', ':')))
out = os.path.join(TOWN, "valentine_standalone.html")
open(out, "w", encoding="utf-8").write(html)
print("wrote", out, round(os.path.getsize(out)/1024/1024, 2), "MB")
