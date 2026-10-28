"""生成"角色动画预览器"（带蒙皮的 glb + 动画播放）。

产物：
  export/npc/anim.html                 单文件（three.js / GLTFLoader 已内联）
  export/npc/open_anim_viewer.bat      起本地服务(8778) 并打开 anim.html

为什么还要 bat：带蒙皮的 glb 必须靠 fetch 取，file:// 下会被浏览器拦
（同一原因见 README_NPC与剧情解包.md §4.1）。

用法: uv run python tools/build_anim_viewer.py
"""
import os
import json
import glob
import struct
import argparse

PROJ = r'D:/BrainMaker/大镖客2解包分析'
LIB = os.path.join(PROJ, 'export/levels/town')
ROOT = os.path.join(PROJ, 'export/npc')


def glb_anims(path):
    """读 glb 的 JSON chunk，取动画名与时长。"""
    try:
        d = open(path, 'rb').read()
        ln, ty = struct.unpack_from('<II', d, 12)
        js = json.loads(d[20:20 + ln].decode('utf-8'))
        out = []
        for a in js.get('animations') or []:
            dur = 0.0
            for s in a.get('samplers', []):
                acc = js['accessors'][s['input']]
                if acc.get('max'):
                    dur = max(dur, float(acc['max'][0]))
            out.append(dict(name=a.get('name') or 'clip', dur=round(dur, 2)))
        nb = 0
        if js.get('skins'):
            nb = len(js['skins'][0].get('joints') or [])
        return out, nb
    except Exception:
        return [], 0


HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>RDR2 角色动画预览</title>
<style>
html,body{margin:0;height:100%;background:#0b0d10;color:#d7e0ea;overflow:hidden;
 font:13px/1.5 "Segoe UI",system-ui,"Microsoft YaHei",sans-serif}
#ui{position:fixed;left:10px;top:10px;background:#11161ce6;border:1px solid #263041;
 border-radius:8px;padding:10px 12px;z-index:9;min-width:340px}
#ui h1{font-size:13px;margin:0 0 8px;color:#8fd3ff}
select,button{background:#1b2330;color:#cfe0f0;border:1px solid #33415a;border-radius:6px;
 padding:4px 8px;font-size:12px;cursor:pointer;margin-right:4px}
button.on{background:#2c6fb5;border-color:#4b9ade;color:#fff}
.row{margin:6px 0}
#info{color:#7fe08a;font-size:12px;margin-top:6px}
input[type=range]{width:100%}
#err{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);color:#f88;
 z-index:20;display:none;text-align:center;line-height:1.8}
</style></head><body>
<div id="ui">
  <h1>RDR2 角色动画预览 <small style="color:#7b8a9c">（蒙皮网格 + 原生动画）</small></h1>
  <div class="row"><select id="mdl"></select></div>
  <div class="row"><select id="clip"></select></div>
  <div class="row">
    <button id="play" class="on">暂停</button>
    <button id="spd">速度 1.0×</button>
    <button id="loop" class="on">循环</button>
    <button id="reset">复位视角</button>
  </div>
  <div class="row"><input id="seek" type="range" min="0" max="1000" value="0"></div>
  <div id="info"></div>
</div>
<div id="err"></div>
<div id="boot" style="position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);color:#8fd3ff">加载中…</div>
<script id="srcdata" type="application/json">__SRC__</script>
<script id="npclist" type="application/json">__DATA__</script>
<script>
(async function(){
const S = JSON.parse(document.getElementById('srcdata').textContent);
const DATA = JSON.parse(document.getElementById('npclist').textContent);
const boot = document.getElementById('boot'), errBox = document.getElementById('err');
function fail(m){ boot.style.display='none'; errBox.style.display='block'; errBox.innerHTML=m; }
function blobURL(s){ return URL.createObjectURL(new Blob([s],{type:'text/javascript'})); }
function rep(s,p){ for(const [a,b] of p) s=s.split(a).join(b); return s; }

let THREE, GLTFLoader, OrbitControls;
try{
  const threeURL = blobURL(S.three);
  const bguURL = blobURL(rep(S.bgu, [["from 'three'","from '"+threeURL+"'"]]));
  const gltfURL = blobURL(rep(S.gltf, [["from 'three'","from '"+threeURL+"'"],
      ["from '../utils/BufferGeometryUtils.js'","from '"+bguURL+"'"]]));
  const orbitURL = blobURL(rep(S.orbit, [["from 'three'","from '"+threeURL+"'"]]));
  THREE = await import(threeURL);
  GLTFLoader = (await import(gltfURL)).GLTFLoader;
  OrbitControls = (await import(orbitURL)).OrbitControls;
}catch(e){ fail('three.js 加载失败：'+e); return; }
boot.style.display='none';

const renderer = new THREE.WebGLRenderer({antialias:true});
renderer.setPixelRatio(Math.min(2, devicePixelRatio||1));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = true;
document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x11151b);
const cam = new THREE.PerspectiveCamera(45, 1, 0.05, 300);
scene.add(new THREE.HemisphereLight(0xcfe3ff, 0x2a2f38, 1.35));
const d1 = new THREE.DirectionalLight(0xffffff, 2.3);
d1.position.set(3,6,4); d1.castShadow = true; scene.add(d1);
const d2 = new THREE.DirectionalLight(0x9fc0ff, 1.0); d2.position.set(-4,3,-3); scene.add(d2);
const rim = new THREE.DirectionalLight(0xffe9c8, 1.4); rim.position.set(-2,1.2,-4); scene.add(rim);
const fill = new THREE.DirectionalLight(0xffffff, 0.8); fill.position.set(2,0.6,-1); scene.add(fill);
const ground = new THREE.Mesh(new THREE.PlaneGeometry(30,30),
  new THREE.MeshStandardMaterial({color:0x59616e, roughness:0.9}));
ground.rotation.x = -Math.PI/2; ground.position.y = -0.001; ground.receiveShadow = true;
scene.add(ground);
scene.add(new THREE.GridHelper(12, 24, 0x2a3646, 0x1a2230));
const controls = new OrbitControls(cam, renderer.domElement);
controls.enableDamping = true;

let mixer=null, actions=[], curObj=null, model=null, clipDur=1, playing=true, speed=1, loop=true;
const clock = new THREE.Clock();
const loader = new GLTFLoader();

function resize(){
  const w = innerWidth, h = innerHeight;
  renderer.setSize(w,h); cam.aspect = w/h; cam.updateProjectionMatrix();
}
addEventListener('resize', resize);

function fit(root){
  // 不用包围盒（蒙皮网格 + 骨架会把 Box3 撑成离谱的大小）。
  // 角色都是 1.7~1.9 m 的人形，直接按固定机位取景，稳定可预期。
  const H = 1.85;                       // 参考身高
  controls.target.set(0, H * 0.50, 0);
  cam.position.set(H * 0.62, H * 0.62, H * 1.55);
  cam.near = 0.02; cam.far = 200; cam.fov = 42;
  cam.updateProjectionMatrix();
  controls.update();
}

function loadModel(mi, ci){
  const m = DATA[mi];
  document.getElementById('mdl').value = mi;
  const clipSel = document.getElementById('clip');
  clipSel.innerHTML = '';
  m.anims.forEach((a,i)=>{
    const o=document.createElement('option'); o.value=i;
    o.textContent = a.name + '  (' + a.dur.toFixed(1) + 's)'; clipSel.appendChild(o);
  });
  clipSel.value = ci||0;
  if (curObj){ scene.remove(curObj); curObj=null; }
  boot.style.display='block'; boot.textContent='加载 '+m.path+' …';
  loader.load(m.path, g=>{
    boot.style.display='none';
    curObj = g.scene;
    curObj.traverse(o=>{ if(o.isMesh){ o.castShadow=true; o.frustumCulled=false; } });
    scene.add(curObj);
    // 落地：这份 glb 的网格在 y∈[-1.019, 1.000]（脚底 -1.019）。
    // 蒙皮网格的包围盒在 three.js 里算不准，这里直接用已知偏移抬起来，稳定可靠。
    const FOOT_Y = -1.019;
    curObj.position.y = -FOOT_Y;
    fit(curObj);
    mixer = new THREE.AnimationMixer(curObj);
    actions = g.animations.map(a=>mixer.clipAction(a));
    playClip(+clipSel.value);
  }, undefined, e=>fail('加载失败：'+m.path+'<br>'+e+'<br><br>'+
      '请用 open_anim_viewer.bat 打开（file:// 下浏览器不让读本地 glb）'));
}

function playClip(i){
  if (!actions.length) return;
  const a = actions[i] || actions[0];
  actions.forEach(x=>x.stop());
  a.reset(); a.setLoop(loop?THREE.LoopRepeat:THREE.LoopOnce, Infinity);
  a.clampWhenFinished = !loop; a.play();
  clipDur = a.getClip().duration || 1;
  document.getElementById('info').textContent =
    DATA[document.getElementById('mdl').value].name + ' · ' + a.getClip().name +
    ' · ' + clipDur.toFixed(2) + 's · ' + (DATA[document.getElementById('mdl').value].bones||'?') + ' 骨';
}

DATA.forEach((m,i)=>{ const o=document.createElement('option'); o.value=i; o.textContent=m.name;
  document.getElementById('mdl').appendChild(o); });
document.getElementById('mdl').onchange = e=>loadModel(+e.target.value, 0);
document.getElementById('clip').onchange = e=>playClip(+e.target.value);
const btnPlay = document.getElementById('play');
btnPlay.onclick = e=>{ playing=!playing; if(mixer) mixer.timeScale = playing?speed:0;
  e.target.classList.toggle('on', playing); e.target.textContent = playing?'暂停':'播放'; };
document.getElementById('spd').onclick = e=>{ speed = speed>=2?0.25:speed*2;
  if(mixer) mixer.timeScale = playing?speed:0; e.target.textContent='速度 '+speed+'×'; };
const btnLoop = document.getElementById('loop');
btnLoop.onclick = e=>{ loop=!loop; e.target.classList.toggle('on', loop); playClip(+document.getElementById('clip').value); };
document.getElementById('reset').onclick = ()=>{ if(curObj) fit(curObj); };
const seek = document.getElementById('seek');
seek.oninput = ()=>{ const a=actions[+document.getElementById('clip').value]; if(!a) return;
  a.time = (+seek.value/1000)*clipDur; mixer.update(0); };

resize();
if (DATA.length) loadModel(0,0);
else fail('没有找到带动画的 glb');

(function loopFn(){
  requestAnimationFrame(loopFn);
  const dt = clock.getDelta();
  if (mixer) mixer.update(dt);
  const a = actions[+document.getElementById('clip').value];
  if (a && clipDur>0) seek.value = Math.round(1000 * (a.time/clipDur));
  controls.update();
  renderer.render(scene, cam);
})();
})();
</script></body></html>
"""

BAT = """@echo off
chcp 65001 >nul
cd /d "%~dp0"
title RDR2 anim viewer launcher
set "UV=C:\\Users\\yaodongcheng\\AppData\\Roaming\\com.brainmaker.client\\cowork-updates\\uv-binary\\uv.exe"
set "SLEEP=%SystemRoot%\\System32\\timeout.exe"

if not exist "%UV%" goto ap
start "RDR2 anim viewer (关闭此窗口即停止服务)" "%UV%" run python -m http.server 8778 --directory "%~dp0."
goto open

:ap
start "RDR2 anim viewer (关闭此窗口即停止服务)" python -m http.server 8778 --directory "%~dp0."

:open
"%SLEEP%" /t 3 /nobreak >nul
start "" "http://127.0.0.1:8778/anim.html"
echo.
echo 已启动：http://127.0.0.1:8778/anim.html
echo 关闭标题为 "RDR2 anim viewer" 的窗口即停止服务。
"%SLEEP%" /t 3 /nobreak >nul
exit /b 0
"""


def main():
    ap = argparse.ArgumentParser()
    a = ap.parse_args()

    items = []
    for p in sorted(glob.glob(os.path.join(ROOT, '**', '*.glb'), recursive=True)):
        anims, nskin = glb_anims(p)
        if not anims:
            continue
        rel = os.path.relpath(p, ROOT).replace('\\', '/')
        items.append(dict(name=os.path.splitext(os.path.basename(p))[0],
                          path=rel, anims=anims, bones=nskin))
    print('找到 %d 个带动画的 glb:' % len(items))
    for it in items:
        print('   %-28s %s' % (it['name'], [x['name'] for x in it['anims']]))

    def rd(p):
        return open(os.path.join(LIB, p), encoding='utf-8').read()

    src = dict(three=rd('three.module.js'),
               orbit=rd('addons/controls/OrbitControls.js'),
               bgu=rd('addons/utils/BufferGeometryUtils.js'),
               gltf=rd('addons/loaders/GLTFLoader.js'))
    html = (HTML
            .replace('__SRC__', json.dumps(src, ensure_ascii=False).replace('</', '<\\/'))
            .replace('__DATA__', json.dumps(items, ensure_ascii=False).replace('</', '<\\/')))
    out = os.path.join(ROOT, 'anim.html')
    open(out, 'w', encoding='utf-8').write(html)
    open(os.path.join(ROOT, 'open_anim_viewer.bat'), 'w', encoding='utf-8').write(BAT)
    print('-> %s (%.1f MB)' % (out, os.path.getsize(out) / 1e6))
    print('-> %s' % os.path.join(ROOT, 'open_anim_viewer.bat'))


if __name__ == '__main__':
    main()
