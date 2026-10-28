"""Build a self-contained single-file RDR2 level viewer: terrain + Valentine town (file:// friendly)."""
import json, os, struct, base64
import numpy as np

ROOT = r"D:/BrainMaker/大镖客2解包分析"
TOWN = os.path.join(ROOT, "export/levels/town")
HM = os.path.join(ROOT, "export/levels/terrain/data/levels/rdr3/heightmap.dat")

three = open(os.path.join(TOWN, "three.module.js"), encoding="utf-8").read().replace("</script", "<\\/script")
E = json.load(open(os.path.join(TOWN, "valentine.json"), encoding="utf-8"))
A = json.load(open(os.path.join(TOWN, "archetypes.json"), encoding="utf-8"))
arch = {str(k): v for k, v in A.items() if any(str(k) == str(e[0]) for e in E)}

# terrain
d = open(HM, "rb").read()
sx, sy = struct.unpack_from('<HH', d, 0x0C)
mnx, mny, mnz, mxx, mxy, mxz = struct.unpack_from('<6f', d, 0x10)
off = len(d) - sx * sy * 2
h = np.frombuffer(d[off:off + sx * sy * 2], dtype='<u2').reshape(sy, sx)
N = 512
step = sx // N
ds = h[::step, ::step][:N, :N].astype('<u2')
terr_b64 = base64.b64encode(ds.tobytes()).decode()
terr_meta = {"N": N, "x0": mnx, "y0": mny, "x1": mxx, "y1": mxy, "zmin": mnz, "zmax": mxz}

html = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>RDR2 · Valentine 瓦伦丁（地形 + 关卡复原）</title>
<style>
 body{margin:0;background:#0a0d12;color:#dfe6ee;font-family:"Microsoft YaHei",system-ui,sans-serif;overflow:hidden}
 #hud{position:fixed;left:12px;top:10px;font-size:13px;background:#0f1318dd;padding:9px 13px;border-radius:8px;line-height:1.8;pointer-events:none}
 #hud b{color:#6ec1ff}
 #lg{position:fixed;right:12px;bottom:12px;font-size:12px;background:#0f1318dd;padding:9px 13px;border-radius:8px;line-height:1.7;pointer-events:none}
 .k{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}
 #err{position:fixed;left:12px;bottom:12px;color:#ff8d8d;font-size:12px}
 #bar{position:fixed;right:12px;top:10px;font-size:12px;background:#0f1318dd;padding:8px 12px;border-radius:8px}
 button{background:#243040;color:#cfe3ff;border:1px solid #3a4757;border-radius:6px;padding:4px 9px;cursor:pointer;font-size:12px}
 button.on{background:#3d6ea5}
</style></head><body>
<div id="hud">RDR2 <b>Valentine 瓦伦丁</b> · 地形 + 关卡地编复原<br>
 地形 1536×1536（此处 512²）· 城镇 <span id="n"></span> 实体（<span id="nb"></span> 用真实包围盒）<br>
 左键=旋转 · 滚轮=缩放 · 右键=平移</div>
<div id="bar"><button id="bTer" class="on">地形</button> <button id="bTown" class="on">城镇</button></div>
<div id="lg"><div><span class="k" style="background:#8fb8ff"></span>大结构</div><div><span class="k" style="background:#e8c07a"></span>建筑</div><div><span class="k" style="background:#7fd6a8"></span>中物件</div><div><span class="k" style="background:#e88a9a"></span>小物件</div></div>
<div id="err"></div>
<script id="three-src" type="text/plain">__THREE__</script>
<script>
window.__ENTS=__ENTS__; window.__ARCH=__ARCH__; window.__TERR="__TERR__"; window.__TM=__TM__;
</script>
<script type="module">
try{
 const url=URL.createObjectURL(new Blob([document.getElementById('three-src').textContent],{type:'text/javascript'}));
 const THREE=await import(url);
 const E=window.__ENTS, A=window.__ARCH, TM=window.__TM;
 const bin=atob(window.__TERR); const buf=new Uint8Array(bin.length); for(let i=0;i<bin.length;i++) buf[i]=bin.charCodeAt(i);
 const H=new Float32Array(TM.N*TM.N); const dv=new DataView(buf.buffer);
 for(let i=0;i<TM.N*TM.N;i++){ H[i]=dv.getUint16(i*2,true)/65535*(TM.zmax-TM.zmin)+TM.zmin; }
 const renderer=new THREE.WebGLRenderer({antialias:true});
 renderer.setSize(innerWidth,innerHeight); document.body.appendChild(renderer.domElement);
 const scene=new THREE.Scene(); scene.background=new THREE.Color(0x0a0d12);
 const cam=new THREE.PerspectiveCamera(50, innerWidth/innerHeight, 1, 60000);
 scene.add(new THREE.HemisphereLight(0xffffff,0x223044,1.6));
 const sun=new THREE.DirectionalLight(0xffffff,1.4); sun.position.set(-0.5,1,0.4); scene.add(sun);
 // ---- terrain mesh (centered at town)
 let tcx=(TM.x0+TM.x1)/2, tcy=(TM.y0+TM.y1)/2;
 let cx=0, cy=0; for(const e of E){cx+=e[1]; cy+=e[2];} cx/=E.length; cy/=E.length;
 const S=TM.N, sizeX=TM.x1-TM.x0, sizeY=TM.y1-TM.y0;
 const tgeo=new THREE.BufferGeometry(); const vt=new Float32Array(S*S*3), ct=new Float32Array(S*S*3);
 const tzmin=TM.zmin, tzmax=TM.zmax;
 for(let r=0;r<S;r++)for(let c=0;c<S;c++){ const i=r*S+c, hv=H[r*S+c];
   vt[i*3]=(TM.x0+(c/(S-1))*sizeX)-cx; vt[i*3+1]=hv; vt[i*3+2]=(TM.y0+(r/(S-1))*sizeY)-cy;
   const t=Math.max(0,Math.min(1,(hv-tzmin)/(tzmax-tzmin)));
   const cc = t<0.30?[0.16+t*0.5,0.36+t*0.7,0.16] : t<0.62?[0.42,0.40-t*0.15,0.26] : [0.72,0.73,0.78];
   ct[i*3]=cc[0]; ct[i*3+1]=cc[1]; ct[i*3+2]=cc[2];
 }
 const it=[]; for(let r=0;r<S-1;r++)for(let c=0;c<S-1;c++){ const a=r*S+c,b=r*S+c+1,d2=(r+1)*S+c,e2=(r+1)*S+c+1; it.push(a,d2,b,b,d2,e2); }
 tgeo.setAttribute('position',new THREE.BufferAttribute(vt,3)); tgeo.setAttribute('color',new THREE.BufferAttribute(ct,3));
 tgeo.setIndex(it); tgeo.computeVertexNormals();
 const terrain=new THREE.Mesh(tgeo,new THREE.MeshLambertMaterial({vertexColors:true,side:THREE.DoubleSide}));
 scene.add(terrain);
 // ---- town
 let minZ=1e9; for(const e of E) if(e[3]<minZ)minZ=e[3];
 const geo=new THREE.BoxGeometry(1,1,1), mat=new THREE.MeshLambertMaterial();
 const inst=new THREE.InstancedMesh(geo,mat,E.length);
 const m4=new THREE.Matrix4(),q=new THREE.Quaternion(),p=new THREE.Vector3(),s=new THREE.Vector3(),c3=new THREE.Color();
 let nbox=0;
 function terrAt(x,y){ const c=Math.round((x-TM.x0)/sizeX*(S-1)), r=Math.round((y-TM.y0)/sizeY*(S-1)); if(c<0||r<0||c>=S||r>=S) return null; return H[r*S+c]; }
 E.forEach((e,i)=>{ const [arch,x,y,z,qx,qy,qz,qw,sxy,sz]=e;
   let dx=2.5,dy=2.5,dz=2.5,sized=false; const b=A[String(arch)];
   if(b){ const bx=Math.abs(b[3]-b[0]),by=Math.abs(b[4]-b[1]),bz=Math.abs(b[5]-b[2]);
     if(Math.max(bx,by,bz)<=30&&bz>=0.8){dx=Math.max(0.6,bx);dy=Math.max(0.6,by);dz=Math.max(0.8,bz);sized=true;nbox++;} }
   p.set(x-cx, z+dz/2, y-cy); q.set(qx,qy,qz,qw); s.set(dx,dz,dy);
   m4.compose(p,q,s); inst.setMatrixAt(i,m4);
   const m=Math.max(dx,dy,dz);
   if(!sized)c3.set(0.30,0.32,0.38); else if(m>25)c3.set(0.56,0.72,1.0); else if(m>8)c3.set(0.91,0.75,0.48); else if(m>3)c3.set(0.50,0.84,0.66); else c3.set(0.91,0.54,0.60);
   inst.setColorAt(i,c3);
 });
 inst.instanceMatrix.needsUpdate=true; if(inst.instanceColor) inst.instanceColor.needsUpdate=true;
 scene.add(inst);
 document.getElementById('n').textContent=E.length; document.getElementById('nb').textContent=nbox;
 document.getElementById('bTer').onclick=e=>{terrain.visible=!terrain.visible; e.target.classList.toggle('on',terrain.visible);};
 document.getElementById('bTown').onclick=e=>{inst.visible=!inst.visible; e.target.classList.toggle('on',inst.visible);};
 // camera: look at the town
 let yaw=0.85,pitch=0.28,dist=620,panX=0,panY=0;
 function upd(){ const ex=Math.cos(yaw)*Math.cos(pitch)*dist+panX, ey=Math.sin(pitch)*dist+(minZ+10)+panY, ez=Math.sin(yaw)*Math.cos(pitch)*dist;
   cam.position.set(ex, ey, ez); cam.lookAt(panX, minZ+10+panY, 0); }
 upd();
 let drag=0,lx=0,ly=0;
 renderer.domElement.addEventListener('mousedown',ev=>{drag=ev.button===2?2:1;lx=ev.clientX;ly=ev.clientY;});
 addEventListener('mouseup',()=>drag=0); addEventListener('contextmenu',e=>e.preventDefault());
 addEventListener('mousemove',ev=>{ if(!drag)return; const dx=ev.clientX-lx,dy=ev.clientY-ly; lx=ev.clientX; ly=ev.clientY;
   if(drag===1){ yaw-=dx*0.005; pitch=Math.max(-0.2,Math.min(1.4,pitch+dy*0.005)); } else { panX-=dx*dist*0.001; panY+=dy*dist*0.001; } upd(); });
 renderer.domElement.addEventListener('wheel',ev=>{ev.preventDefault(); dist*=(1+Math.sign(ev.deltaY)*0.1); dist=Math.max(20,Math.min(20000,dist)); upd();},{passive:false});
 addEventListener('resize',()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);});
 (function loop(){requestAnimationFrame(loop);renderer.render(scene,cam);})();
}catch(err){document.getElementById('err').textContent='ERR: '+err.message;}
</script></body></html>"""

html = html.replace("__THREE__", three).replace("__ENTS__", json.dumps(E, separators=(',', ':'))) \
           .replace("__ARCH__", json.dumps(arch, separators=(',', ':'))) \
           .replace("__TERR__", terr_b64).replace("__TM__", json.dumps(terr_meta))
out = os.path.join(TOWN, "valentine_terrain.html")
open(out, "w", encoding="utf-8").write(html)
print("wrote", out, round(os.path.getsize(out) / 1024 / 1024, 2), "MB")
