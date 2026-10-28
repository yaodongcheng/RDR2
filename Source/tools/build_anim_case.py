"""把「骑砍2 规格 FBX → GLB」做成**双击即开**的单文件动画查看器（case）。
用法: python tools/build_anim_case.py <glb> <out.html> "<标题>" [<three_dir>]
"""
import os, sys, json, base64

glb, out, title = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else 'anim case')
TD = sys.argv[4] if len(sys.argv) > 4 else r'D:/BrainMaker/大镖客2解包分析/export/levels/town'

three = open(os.path.join(TD, 'three.module.js'), encoding='utf-8').read()
gl = open(os.path.join(TD, 'addons/loaders/GLTFLoader.js'), encoding='utf-8').read()
oc = open(os.path.join(TD, 'addons/controls/OrbitControls.js'), encoding='utf-8').read()
bgu = open(os.path.join(TD, 'addons/utils/BufferGeometryUtils.js'), encoding='utf-8').read()
b64 = base64.b64encode(open(glb, 'rb').read()).decode()

html = """<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>__T__</title>
<style>body{margin:0;background:#101418;color:#dfe6ee;font:13px "Microsoft YaHei",sans-serif;overflow:hidden}
#hud{position:fixed;left:12px;top:10px;background:#0f1318dd;padding:9px 13px;border-radius:8px;line-height:1.7}
#hud b{color:#6ec1ff}#bar{position:fixed;left:12px;bottom:12px;background:#0f1318dd;padding:9px 13px;border-radius:8px;display:flex;gap:10px;align-items:center}
input[type=range]{width:340px}#err{position:fixed;left:12px;bottom:70px;color:#ff8080}</style></head><body>
<div id="hud"><b>__T__</b><br>帧 <b id="fr">0</b> / <b id="tn">0</b> · 骨 <b id="bn">0</b> · <span id="st">加载中…</span><br><span style="color:#8fa">左键旋转 · 滚轮缩放 · 右键平移</span></div>
<div id="bar"><button id="pp">暂停</button><input type="range" id="sl" min="0" max="100" value="0"><span id="t2">0.00s</span></div>
<div id="err"></div>
<script type="text/plain" id="src-three">__THREE__</script>
<script type="text/plain" id="src-gltf">__GLTF__</script>
<script type="text/plain" id="src-orbit">__ORBIT__</script>
<script type="text/plain" id="src-bgu">__BGU__</script>
<script>
window.__GLB="__B64__";
(async()=>{
 try{
  const mk=s=>URL.createObjectURL(new Blob([s],{type:'text/javascript'}));
  const th=mk(document.getElementById('src-three').textContent);
  let bg=document.getElementById('src-bgu').textContent.replace(/from\s+['"]three['"]/g,"from '"+th+"'");
  const bu=mk(bg);
  let g=document.getElementById('src-gltf').textContent.replace(/from\s+['"]three['"]/g,"from '"+th+"'")
                       .replace(/from\s+['"][^'"]*BufferGeometryUtils\.js['"]/g,"from '"+bu+"'");
  let o=document.getElementById('src-orbit').textContent.replace(/from\s+['"]three['"]/g,"from '"+th+"'");
  const THREE=await import(th), GLTFLoader=(await import(mk(g))).GLTFLoader, OrbitControls=(await import(mk(o))).OrbitControls;
  const b=atob(window.__GLB); const u=new Uint8Array(b.length); for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);
  const r=new THREE.WebGLRenderer({antialias:true}); r.setSize(innerWidth,innerHeight); r.setPixelRatio(devicePixelRatio); document.body.appendChild(r.domElement);
  const sc=new THREE.Scene(); sc.background=new THREE.Color(0x101418);
  const cam=new THREE.PerspectiveCamera(45,innerWidth/innerHeight,0.05,500);
  sc.add(new THREE.HemisphereLight(0xffffff,0x404040,2.2));
  const d=new THREE.DirectionalLight(0xffffff,1.6); d.position.set(2,4,2); sc.add(d);
  sc.add(new THREE.GridHelper(6,24,0x334455,0x223344));
  const g2=new GLTFLoader(); g2.parse(u.buffer,'',(gltf)=>{
    sc.add(gltf.scene);
    // 蒙皮网格的 bbox 不可靠 ⇒ 用固定取景（目标 ≈ 1.8m 人形，原点在脚底/骨盆附近）
    const c=new THREE.Vector3(0,0.95,0);
    cam.position.set(0.2,1.45,3.6); cam.lookAt(c);
    const ctl=new OrbitControls(cam,r.domElement); ctl.target.copy(c); ctl.update();
    let mx=0,bn=0; gltf.scene.traverse(o2=>{ if(o2.isBone) bn++; if(o2.isSkinnedMesh) o2.frustumCulled=false; });
    document.getElementById('bn').textContent=bn;
    let mixer=null,act=null;
    if(gltf.animations && gltf.animations.length){
      mixer=new THREE.AnimationMixer(gltf.scene); act=mixer.clipAction(gltf.animations[0]); act.play();
      mx=gltf.animations[0].duration;
    }
    document.getElementById('tn').textContent=mx.toFixed(2)+'s';
    document.getElementById('st').textContent = gltf.animations.length? ('动画 '+gltf.animations.length+' 段') : '无动画';
    let t=0, playing=true, last=performance.now();
    document.getElementById('pp').onclick=e=>{playing=!playing;e.target.textContent=playing?'暂停':'播放';};
    document.getElementById('sl').oninput=e=>{t=parseFloat(e.target.value)/100*mx; if(mixer){mixer.setTime(0); mixer.update(t);} };
    (function loop(){ requestAnimationFrame(loop);
      const now=performance.now(); const dt=(now-last)/1000; last=now;
      if(playing && mixer){ t=(t+dt)%(mx||1); mixer.update(dt); }
      document.getElementById('fr').textContent=(mixer&&act)?(act.time/(mx||1)*100).toFixed(0)+'%':'0%';
      document.getElementById('t2').textContent=(mixer?act.time:0).toFixed(2)+'s';
      document.getElementById('sl').value=(mixer&&mx)?(act.time/mx*100):0;
      ctl.update(); r.render(sc,cam); })();
  }, (e)=>{document.getElementById('err').textContent='GLB 解析失败: '+e;});
 }catch(e){ document.getElementById('err').textContent='ERR: '+e.message; console.error(e); }
})();
</script></body></html>"""
html = (html.replace('__T__', title).replace('__THREE__', three)
            .replace('__GLTF__', gl).replace('__ORBIT__', oc).replace('__BGU__', bgu).replace('__B64__', b64))
open(out, 'w', encoding='utf-8').write(html)
print('wrote', out, round(os.path.getsize(out)/1e6, 2), 'MB')
