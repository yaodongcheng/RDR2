import json,base64,os
R="D:/BrainMaker/大镖客2解包分析"
pl=json.load(open("D:/tmp/uvtest_payload.json"))
three=open(R+"/export/levels/town/three.module.js",encoding="utf-8").read().replace("</script","<\/script")
html = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
body{margin:0;background:#111;color:#ccc;font:12px monospace}
.cell{position:relative;width:400px;height:400px;float:left}.cap{position:absolute;left:4px;top:2px;background:#000b;padding:1px 4px;color:#8f8}
#st{padding:4px 8px}</style></head><body>
<div id="st">loading</div>
<script id="t3" type="text/plain">__THREE__</script>
<script>window.__P=__PAY__;</script>
<script type="module">
const u=URL.createObjectURL(new Blob([document.getElementById('t3').textContent],{type:'text/javascript'}));
const THREE=await import(u);
const P=window.__P;
document.getElementById('st').textContent='candidates: '+P.CANDS.map(c=>c.name).join(' | ');
const img=new Image();
img.onload=()=>{
 const W=400, COLS=4, ROWS=Math.ceil(P.CANDS.length/COLS);
 const r2=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
 r2.setSize(W*COLS,W*ROWS); document.body.appendChild(r2.domElement);
 document.getElementById('st').textContent+=' | tex '+img.width+'x'+img.height;
 const tx=new THREE.CanvasTexture(img); tx.wrapS=tx.wrapT=THREE.RepeatWrapping; tx.needsUpdate=true;
 const cam=new THREE.PerspectiveCamera(45,1,0.5,5000);
 P.CANDS.forEach((c,ci)=>{
   const sc=new THREE.Scene(); sc.background=new THREE.Color(0x202830);
   sc.add(new THREE.HemisphereLight(0xffffff,0x556677,2.4));
   const dl=new THREE.DirectionalLight(0xffffff,1.2); dl.position.set(1,2,1); sc.add(dl);
   const g=new THREE.BufferGeometry();
   const pos=new Float32Array(P.POS.length);
   for(let i=0;i<P.POS.length;i+=3){pos[i]=P.POS[i];pos[i+1]=P.POS[i+2];pos[i+2]=-P.POS[i+1];}
   g.setAttribute('position',new THREE.BufferAttribute(pos,3));
   g.setAttribute('uv',new THREE.BufferAttribute(new Float32Array(c.uv),2));
   g.setIndex(new THREE.BufferAttribute(new Uint32Array(P.IDX),1));
   g.computeBoundingSphere();
   const bs=g.boundingSphere; const D=bs.radius*2.3;
   sc.add(new THREE.Mesh(g,new THREE.MeshLambertMaterial({map:tx,side:THREE.DoubleSide})));
   cam.position.set(bs.center.x+D*0.7, bs.center.y+D*0.45, bs.center.z+D*0.7); cam.lookAt(bs.center);
   r2.setViewport((ci%COLS)*W, (ROWS-1-Math.floor(ci/COLS))*W, W, W);
   r2.render(sc,cam);
 });
 window.__ready=true;
};
img.src="data:image/png;base64,"+P.TEX;

</script></body></html>"""
html=html.replace("__THREE__",three).replace("__PAY__", json.dumps(pl,separators=(',',':')))
out="D:/tmp/uvtest.html"
open(out,"w",encoding="utf-8").write(html)
print("wrote",out, round(os.path.getsize(out)/1e6,2),"MB")
