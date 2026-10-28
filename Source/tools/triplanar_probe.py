import sys,os,json,base64,io
sys.path.insert(0,"D:/BrainMaker/大镖客2解包分析/tools")
import numpy as np
from PIL import Image
from rdr2_ydr import Res, extract_at
R="D:/BrainMaker/大镖客2解包分析"
f=R+"/export/models/buildings/val_01_/val_01_trainstn_ext.ydr"
res=Res(open(f,'rb').read())
info,ms=extract_at(res,0,'high')
pos=[];idx=[];b=0
for m in ms:
    pos+=m['positions']; idx+=[i+b for i in m['indices']]; b+=m['vertex_count']
P=np.array(pos,dtype=np.float32).reshape(-1,3); I=np.array(idx,dtype=np.int64)
tex=Image.open(R+"/export/models/textures/val_01_trainstn/03_nbx_wall_woodplank_16_ab_BC1_sRGB.png").resize((512,512)).convert('RGB')
bio=io.BytesIO(); tex.save(bio,'PNG')
three=open(R+"/export/levels/town/three.module.js",encoding="utf-8").read().replace("</script","<\/script")
html='''<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{margin:0;background:#111}#s{padding:4px 8px;color:#9c9;font:12px monospace}</style></head><body>
<div id="s">triplanar test</div>
<script id="t3" type="text/plain">__THREE__</script>
<script>window.__D=__PAY__;</script>
<script type="module">
const u=URL.createObjectURL(new Blob([document.getElementById('t3').textContent],{type:'text/javascript'}));
const THREE=await import(u);
const D=window.__D;
const img=new Image();
img.onload=()=>{
 const W=760;
 const r=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
 r.setSize(W*2,W); document.body.appendChild(r.domElement);
 const tx=new THREE.CanvasTexture(img); tx.wrapS=tx.wrapT=THREE.RepeatWrapping;
 const cam=new THREE.PerspectiveCamera(45,1,0.5,5000);
 [0,1].forEach(mode=>{
  const sc=new THREE.Scene(); sc.background=new THREE.Color(0x223040);
  sc.add(new THREE.HemisphereLight(0xffffff,0x556677,2.2));
  const dl=new THREE.DirectionalLight(0xffffff,1.2); dl.position.set(1,2,0.8); sc.add(dl);
  const g=new THREE.BufferGeometry();
  const pos=new Float32Array(D.POS.length);
  for(let i=0;i<D.POS.length;i+=3){pos[i]=D.POS[i];pos[i+1]=D.POS[i+2];pos[i+2]=-D.POS[i+1];}
  g.setAttribute('position',new THREE.BufferAttribute(pos,3));
  g.setIndex(new THREE.BufferAttribute(new Uint32Array(D.IDX),1));
  g.computeVertexNormals(); g.computeBoundingSphere();
  let mat;
  if(mode===0){ mat=new THREE.MeshLambertMaterial({map:tx,side:THREE.DoubleSide}); }
  else{
    mat=new THREE.MeshLambertMaterial({color:0xffffff,side:THREE.DoubleSide});
    mat.onBeforeCompile=(sh)=>{
      sh.uniforms.triTex={value:tx};
      sh.vertexShader='varying vec3 vWPos; varying vec3 vWNrm;\n'+sh.vertexShader.replace('#include <begin_vertex>',
        '#include <begin_vertex>\n vWPos=position; vWNrm=normal;');
      sh.fragmentShader='uniform sampler2D triTex; varying vec3 vWPos; varying vec3 vWNrm;\n'+sh.fragmentShader.replace(
        '#include <map_fragment>',
        'vec3 n=normalize(vWNrm); vec3 an=abs(n); vec3 sc=vec3(0.55);\n'+
        'vec3 cx=texture2D(triTex, vWPos.zy*sc.z).rgb;\n'+
        'vec3 cy=texture2D(triTex, vWPos.xz*sc.z).rgb;\n'+
        'vec3 cz=texture2D(triTex, vWPos.xy*sc.z).rgb;\n'+
        'vec3 col=(cx*an.x+cy*an.y+cz*an.z)/(an.x+an.y+an.z);\n'+
        'diffuseColor.rgb*=col;');
    };
  }
  sc.add(new THREE.Mesh(g,mat));
  const bs=g.boundingSphere,D2=bs.radius*2.2;
  cam.position.set(bs.center.x+D2*0.7,bs.center.y+D2*0.45,bs.center.z+D2*0.7); cam.lookAt(bs.center);
  r.setViewport(mode*W,0,W,W); r.render(sc,cam);
 });
 window.__ready=true;
};
img.src="data:image/png;base64,"+D.TEX;
</script></body></html>'''
pl=dict(POS=P.ravel().tolist(), IDX=I.ravel().tolist(), TEX=base64.b64encode(bio.getvalue()).decode())
open("D:/tmp/triplanar.html","w",encoding="utf-8").write(html.replace("__THREE__",three).replace("__PAY__",json.dumps(pl,separators=(',',':'))))
print("wrote D:/tmp/triplanar.html", round(os.path.getsize("D:/tmp/triplanar.html")/1e6,2),"MB")
