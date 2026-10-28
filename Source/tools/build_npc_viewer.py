"""为 `export/npc/` 里的 NPC 产出浏览入口：index.csv + index.html（three.js）+ 启动脚本。

## 正确的启动方式

**双击根目录 `打开查看器.bat`** —— 它起一个本地静态服务（`http://127.0.0.1:8788`），首页点「角色模型 3D」。

### 为什么不建议直接双击 index.html

`file://` 下浏览器会拦两样东西：

| 被拦的 | 后果 | 本脚本的处理 |
|---|---|---|
| `import ... from './lib/three.js'`（ES module）| 整段脚本不执行 → 列表空 + 视口黑 | ✅ **把 three.js 源码内联**，运行时 `Blob` + `import()`，这一条已解决 |
| `fetch('xxx.glb')` | 模型永远加载不出来 | ❌ 无法在 `file://` 下绕过（除非整份 base64 复制一遍，体积 +33%，**已弃用**）|

所以 `file://` 直接打开时，页面**能正常显示列表和界面**，但会弹一条**红字提示**告诉你改用 bat。
（如果确实需要"随便双击到哪都能开"，可以用 `--b64` 生成 base64 伴生文件，代价是体积接近翻倍。）

用法: uv run python tools/build_npc_viewer.py [--root export/npc] [--b64]
"""
import os
import re
import csv
import json
import glob
import base64
import argparse
import time

VER = int(time.time())

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)

CATNAME = {'cs': '剧情角色 cs_*', 'player': '主角', 'generic': '通用路人', 'animals': '动物'}

# 主线重要度排名（人工维护）：name -> {rank, tier, cn, note}
RANK_PATH = os.path.join(PROJ, 'work/npc/story_rank.json')
TIER_ORDER = ['S', 'A', 'B', 'C', 'D']
TIER_LABEL = {
    'S': 'S · 双主角',
    'A': 'A · 范德林德帮核心',
    'B': 'B · 主线反派与章节关键',
    'C': 'C · 支线 / 陌生人任务',
    'D': 'D · 其他具名 NPC（未排名）',
    'generic': '通用路人（拼装示意）',
    'animals': '动物',
}

HTML_HEAD = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>RDR2 NPC 模型浏览（解包导出 · glTF）</title>
<style>
html,body{margin:0;height:100%;background:#0b0d10;color:#d7e0ea;
 font:13px/1.5 "Segoe UI",system-ui,"Microsoft YaHei",sans-serif;overflow:hidden}
#side{position:fixed;left:0;top:0;bottom:0;width:300px;background:#0e131a;
 border-right:1px solid #1d2634;display:flex;flex-direction:column}
#side h1{font-size:13px;margin:0;padding:10px 12px;color:#8fd3ff;border-bottom:1px solid #1d2634}
#side input{margin:8px 10px;padding:5px 8px;background:#141b25;border:1px solid #263041;
 border-radius:6px;color:#d7e0ea}
#list{flex:1;overflow:auto;padding-bottom:24px}
.grp{padding:7px 12px 3px;color:#ffd479;font-size:12px}
.it{padding:4px 12px 4px 20px;cursor:pointer;white-space:nowrap;overflow:hidden;
 text-overflow:ellipsis}
.it:hover{background:#16202c}
.it.on{background:#1d3956;color:#fff}
.it .rk{color:#ffd479;font-variant-numeric:tabular-nums}
.it .cn{color:#e6eef7}
#view{position:fixed;left:300px;right:0;top:0;bottom:0}
#hud{position:fixed;left:312px;top:10px;background:#11161ce6;border:1px solid #263041;
 border-radius:8px;padding:9px 12px;max-width:660px;z-index:9;font-size:12px}
#hud b{color:#ffd479}
#err{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);color:#f88;z-index:20;
 display:none;text-align:center}
#boot{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);color:#8fd3ff;z-index:21}
#lit{position:fixed;right:14px;bottom:14px;background:#11161ce6;border:1px solid #263041;
 border-radius:8px;padding:8px 10px;z-index:9}
#lit .row{display:flex;align-items:center;gap:7px;margin:2px 0}
#lit span{width:32px;color:#9fb2c6}
#lit input{width:104px}
#lit b{width:32px;text-align:right;color:#ffd479;font-weight:400}
#lit.btns button,#lit button{background:#1b2531;border:1px solid #2b3949;color:#c9d6e3;
 border-radius:5px;padding:3px 0;cursor:pointer;font:12px/1.2 inherit}
#lit .btns button{flex:1}
#lit button.on{background:#1d3956;border-color:#3a6f9e;color:#fff}
</style></head><body>
<div id="side">
 <h1>RDR2 NPC 模型（__TOTAL__ 个）</h1>
 <input id="q" placeholder="搜索名字，如 dutch / player / wolf">
 <div id="list"></div>
</div>
<div id="view"></div>
<div id="hud">左键旋转 / 滚轮缩放 / 右键平移</div>
<div id="lit">
 <div class="row btns"><button id="btnFull" class="on">全身</button><button id="btnHead">头部特写</button></div>
 <div class="row"><span>曝光</span><input id="exp" type="range" min="0.3" max="2.4" step="0.05" value="1.3"><b id="expv">1.30</b></div>
 <div class="row"><span>面光</span><input id="fac" type="range" min="0" max="2" step="0.05" value="1.2"><b id="facv">1.20</b></div>
 <div class="row"><span>环境</span><input id="amb" type="range" min="0" max="3" step="0.1" value="1.4"><b id="ambv">1.4</b></div>
</div>
<div id="err"></div>
<div id="boot">正在加载 three.js…</div>
<script id="srcdata" type="application/json">__SRCDATA__</script>
<script id="npclist" type="application/json">__NPCLIST__</script>
<script>
(async function(){
const S = JSON.parse(document.getElementById('srcdata').textContent);
const DATA = JSON.parse(document.getElementById('npclist').textContent);
const GRP = __GRPMAP__;
const boot = document.getElementById('boot');
const errBox = document.getElementById('err');
const hud = document.getElementById('hud');
const view = document.getElementById('view');
const listEl = document.getElementById('list');

function fail(msg){ boot.style.display='none'; errBox.style.display='block'; errBox.textContent=msg; }
function blobURL(src){ return URL.createObjectURL(new Blob([src],{type:'text/javascript'})); }
function rep(src, pairs){ for(const [a,b] of pairs) src = src.split(a).join(b); return src; }

let THREE, GLTFLoader, OrbitControls;
try{
  const threeURL = blobURL(S.three);
  const bguURL   = blobURL(rep(S.bgu,  [["from 'three'", "from '"+threeURL+"'"]]));
  const gltfURL  = blobURL(rep(S.gltf, [["from 'three'", "from '"+threeURL+"'"],
                                        ["from '../utils/BufferGeometryUtils.js'", "from '"+bguURL+"'"]]));
  const orbitURL = blobURL(rep(S.orbit, [["from 'three'", "from '"+threeURL+"'"]]));
  THREE         = await import(threeURL);
  GLTFLoader    = (await import(gltfURL)).GLTFLoader;
  OrbitControls = (await import(orbitURL)).OrbitControls;
}catch(e){ fail('three.js 加载失败：'+e); return; }
boot.style.display = 'none';

const renderer = new THREE.WebGLRenderer({antialias:true});
renderer.setPixelRatio(Math.min(2, devicePixelRatio||1));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;   // 高光不再死白，暗部也不糊成一片
renderer.toneMappingExposure = 1.3;
view.appendChild(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x141a21);
const camera = new THREE.PerspectiveCamera(45, 1, 0.05, 300);
// —— 环境光（IBL）：给 PBR 材质一个"影棚柔光"环境，暗面也能吃到光，不会半边脸纯黑
(function(){
  const c = document.createElement('canvas'); c.width = 128; c.height = 64;
  const g = c.getContext('2d');
  const gr = g.createLinearGradient(0, 0, 0, 64);
  gr.addColorStop(0.00, '#eef4fc');
  gr.addColorStop(0.45, '#a4b0bf');
  gr.addColorStop(0.56, '#6d7681');
  gr.addColorStop(1.00, '#33383e');
  g.fillStyle = gr; g.fillRect(0, 0, 128, 64);
  // 两侧各放一块"柔光箱"，让人脸左右都能吃到环境光
  g.fillStyle = 'rgba(255,255,255,0.95)'; g.fillRect(10, 14, 22, 26);
  g.fillStyle = 'rgba(255,255,255,0.70)'; g.fillRect(96, 14, 22, 26);
  const tex = new THREE.CanvasTexture(c);
  tex.mapping = THREE.EquirectangularReflectionMapping;
  tex.colorSpace = THREE.SRGBColorSpace;
  const pm = new THREE.PMREMGenerator(renderer);
  scene.environment = pm.fromEquirectangular(tex).texture;
  pm.dispose(); tex.dispose();
})();
// —— 影棚式布光：主光 + 两侧补光 + 轮廓光 + 一盏**跟着相机走**的面光
//    RDR2 皮肤 albedo 偏暗，纯方向光会把人切成"亮半边 + 死黑半边"。
const hemi  = new THREE.HemisphereLight(0xdfeaff, 0x5b6169, 0.8); scene.add(hemi);
const key   = new THREE.DirectionalLight(0xfff4e8, 1.8); key.position.set(2.2, 3.6, 3.4);  scene.add(key);
const fillL = new THREE.DirectionalLight(0xc8dcff, 1.1); fillL.position.set(-3.2, 1.8, 2.6); scene.add(fillL);
const rim   = new THREE.DirectionalLight(0xffffff, 1.0); rim.position.set(-0.6, 3.2, -4.4); scene.add(rim);
// 面光：方向 = 相机 → 模型中心，保证"当前看到的那一面"永远有光
const faceL = new THREE.DirectionalLight(0xffffff, 1.2); scene.add(faceL); scene.add(faceL.target);
const grid = new THREE.GridHelper(8,16,0x2a3646,0x1a2230); scene.add(grid);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

let cur = null, seq = 0;
const loader = new GLTFLoader();
const G = window.__NPCG = window.__NPCG || {};

function b64buf(b64){
  const bin = atob(b64), n = bin.length, ab = new Uint8Array(n);
  for(let i=0;i<n;i++) ab[i] = bin.charCodeAt(i);
  return ab.buffer;
}
let lastMode = 'full';
function fit(root){
  const box = new THREE.Box3().setFromObject(root);
  const size = box.getSize(new THREE.Vector3());
  const c = box.getCenter(new THREE.Vector3());
  const h = Math.max(size.x, size.y, size.z);
  curBox = box; curSize = size;
  camera.near = Math.max(0.02, h/300); camera.far = h*80;
  applyView(lastMode);
}
let curBox = null, curSize = null;
function applyView(mode){
  if(!curBox) return;
  lastMode = mode;
  // ★ 头部特写必须用长焦：45° 广角贴脸拍会把鼻子放大、脸拉宽（"变丑"的主因之一）
  camera.fov = (mode === 'head') ? 20 : 45;
  const size = curSize, box = curBox;
  const c = box.getCenter(new THREE.Vector3());
  const vFov = camera.fov * Math.PI / 180;
  const dir = new THREE.Vector3(0.42, 0.16, 1).normalize();
  if(mode === 'head'){
    // 头部特写：瞄准 bbox 顶部往下 10% 处，视口高度只要装下 ~0.45 m
    const t = new THREE.Vector3(c.x, box.max.y - Math.max(0.14, size.y*0.115), c.z);
    const d = (0.50*0.5) / Math.tan(vFov/2) / 0.85;
    controls.target.copy(t);
    camera.position.copy(t).addScaledVector(dir, d);
  }else{
    // 全身：让人物高度占视口 ~78%
    const d = (size.y*0.5) / Math.tan(vFov/2) / 0.78;
    controls.target.copy(c);
    camera.position.copy(c).addScaledVector(dir, d);
  }
  camera.updateProjectionMatrix();
  controls.update();
}
function resize(){
  const w = Math.max(320, view.clientWidth), h = Math.max(240, view.clientHeight);
  renderer.setSize(w,h); camera.aspect = w/h; camera.updateProjectionMatrix();
}
addEventListener('resize', resize);

function dispose(){
  if(!cur) return;
  scene.remove(cur);
  cur.traverse(o=>{ if(o.geometry) o.geometry.dispose(); });
  cur = null;
}
function shown(g, my){
  if(my !== seq) return;                 // 已被后续点击取代，丢弃
  dispose();
  cur = g.scene;
  scene.add(cur);
  fit(cur);
  errBox.style.display = 'none';
}

function load(item){
  const my = ++seq;
  document.querySelectorAll('.it').forEach(e=>e.classList.toggle('on', e.dataset.n===item.name));
  errBox.style.display='none';
  hud.innerHTML = (item.rank?('<b>#'+item.rank+' '+item.cn+'</b><br>'):'')+
    '<code>'+item.name+'</code> · '+item.cat+' · 部件 <b>'+item.parts+
    '</b> · 面 <b>'+item.tris+'</b> · 贴图 <b>'+item.textures+'</b>'+
    (item.note?('<br>'+item.note):'')+'<br>来源：<code>'+
    (item.sources||[]).join(' + ')+'</code>';

  const parse = buf => loader.parse(buf, '', g=>shown(g, my),
                                    e=>{ if(my===seq) fail('解析失败 '+item.name+'：'+e); });

  if(G[item.name]) { parse(b64buf(G[item.name])); return; }

  // 没有 base64 伴生文件 → 直接取 .glb（走 open_npc_viewer.bat 的本地服务时可用）
  fetch(item.glb, {cache:'no-cache'})
    .then(r=>{ if(!r.ok) throw new Error('HTTP '+r.status); return r.arrayBuffer(); })
    .then(parse)
    .catch(e=>{
      if(my !== seq) return;
      if(location.protocol === 'file:'){ hint(); }
      else { fail('无法加载 '+item.glb+'（'+e.message+'）'); }
    });
}

// file:// 直接打开的提示（不是错误，是"换个方式打开"）
let hinted = false;
function hint(){
  if(hinted) return; hinted = true;
  errBox.style.display='block';
  errBox.innerHTML =
    '你是在用 <b>file://</b> 直接打开这个页面（双击了 index.html）。<br>'+
    '浏览器不允许本地页面读取同目录的 .glb 文件，所以<b>模型加载不出来</b>。<br><br>'+
    '<b>请改为双击根目录的「打开查看器.bat」</b> —— 它起一个本地服务，首页进「角色模型 3D」。<br>'+
    '<span style="color:#8fd3ff">（左边的列表和界面不受影响，可以正常浏览/搜索）</span>';
}

function render(filter){
  listEl.innerHTML='';
  let grp=null, n=0;
  for(const it of DATA){
    if(filter){
      const hay = (it.name+' '+(it.cn||'')+' '+(it.note||'')).toLowerCase();
      if(hay.indexOf(filter)<0) continue;
    }
    n++;
    if(it.grp!==grp){ grp=it.grp; const d=document.createElement('div');
      d.className='grp'; d.textContent=(GRP[grp]||grp); listEl.appendChild(d); }
    const d=document.createElement('div');
    d.className='it'; d.dataset.n=it.name;
    if(it.rank) d.innerHTML='<span class="rk">'+String(it.rank).padStart(2,'0')+'</span> '+
        '<span class="cn">'+(it.cn||it.name)+'</span>';
    else d.textContent=it.name;
    d.title = it.note ? (it.cn||it.name)+'：'+it.note : it.name;
    d.onclick=()=>load(it);
    listEl.appendChild(d);
  }
  hud.innerHTML = filter ? ('匹配 <b>'+n+'</b> / '+DATA.length) :
                           ('共 <b>'+DATA.length+'</b> 个 NPC · 按主线重要度排序 —— 点左侧列表看模型');
}
document.getElementById('q').oninput = e=>render(e.target.value.trim().toLowerCase());
render('');
resize();
// 支持 index.html?npc=cs_dutch_ms1 直接定位到某个角色（&view=head 直接进头部特写）
const qs = new URLSearchParams(location.search);
const want = qs.get('npc');
if(qs.get('view') === 'head') lastMode = 'head';
const first = (want && DATA.find(d=>d.name===want)) || DATA[0];
if(first) load(first);
// 布光滑杆：曝光 / 面光强度 / 环境光强度
const expEl=document.getElementById('exp'), facEl=document.getElementById('fac'), ambEl=document.getElementById('amb');
function syncLit(){
  renderer.toneMappingExposure = +expEl.value;
  faceL.intensity = +facEl.value;
  hemi.intensity  = +ambEl.value;
  document.getElementById('expv').textContent = (+expEl.value).toFixed(2);
  document.getElementById('facv').textContent = (+facEl.value).toFixed(2);
  document.getElementById('ambv').textContent = (+ambEl.value).toFixed(1);
}
[expEl,facEl,ambEl].forEach(e=>e.addEventListener('input',syncLit));
syncLit();

// 构图：全身 / 头部特写
const btnFull=document.getElementById('btnFull'), btnHead=document.getElementById('btnHead');
function setMode(m){
  applyView(m);
  btnFull.classList.toggle('on', m==='full');
  btnHead.classList.toggle('on', m==='head');
}
btnFull.addEventListener('click', ()=>setMode('full'));
btnHead.addEventListener('click', ()=>setMode('head'));
btnFull.classList.toggle('on', lastMode==='full');
btnHead.classList.toggle('on', lastMode==='head');

(function loop(){
  requestAnimationFrame(loop);
  controls.update();
  // 面光始终从相机方向照向模型中心 → 当前可见的一面不会被"背光"
  faceL.position.copy(camera.position);
  faceL.target.position.copy(controls.target);
  faceL.target.updateMatrixWorld();
  renderer.render(scene,camera);
})();
})();
</script></body></html>
"""

BAT = """@echo off
chcp 65001 >nul
cd /d "%~dp0"
title RDR2 NPC viewer launcher

rem ============================================================
rem  RDR2 NPC 浏览页 启动器
rem  起一个本地静态服务再打开页面。
rem  为什么不能直接双击 index.html：浏览器禁止 file:// 页面读取
rem  同目录的 .glb 文件（跨域策略），模型会加载不出来。
rem ============================================================

set "UV=C:\\Users\\yaodongcheng\\AppData\\Roaming\\com.brainmaker.client\\cowork-updates\\uv-binary\\uv.exe"
set "SLEEP=%SystemRoot%\\System32\\timeout.exe"

if not exist "%UV%" goto use_python

start "RDR2 NPC viewer (关闭此窗口即停止服务)" "%UV%" run python -m http.server 8777 --directory "%~dp0."
goto wait

:use_python
where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 找不到 uv.exe，也找不到 python。
  echo        请在此目录手动执行:  python -m http.server 8777
  pause
  exit /b 1
)
start "RDR2 NPC viewer (关闭此窗口即停止服务)" python -m http.server 8777 --directory "%~dp0."

:wait
"%SLEEP%" /t 3 /nobreak >nul
start "" "http://127.0.0.1:8777/index.html"
echo.
echo 已启动：http://127.0.0.1:8777/index.html
echo 关闭标题为 "RDR2 NPC viewer" 的窗口即可停止服务。
"%SLEEP%" /t 3 /nobreak >nul
exit /b 0
"""


def json_for_html(obj):
    """JSON 进 HTML 内联安全：把 `</` 转成 `<\\/`（JSON 里合法，HTML 解析器不会提前闭合）。"""
    return json.dumps(obj, ensure_ascii=False).replace('</', '<\\/')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='export/npc')
    ap.add_argument('--b64', action='store_true',
                    help='额外生成 <name>.glb.js 伴生文件，使 file:// 直接双击也能加载'
                         '（体积 +33%%，非必需；正常用根目录「打开查看器.bat」不需要）')
    ap.add_argument('--purge-b64', action='store_true',
                    help='删掉已有的 <name>.glb.js 伴生文件')
    a = ap.parse_args()
    root = os.path.join(PROJ, a.root) if not os.path.isabs(a.root) else a.root

    if a.purge_b64:
        n = 0
        sz = 0
        for f in glob.glob(os.path.join(root, '*', '*', '*.glb.js')):
            sz += os.path.getsize(f)
            os.remove(f)
            n += 1
        print('已删除 %d 个 .glb.js，释放 %.2f GB' % (n, sz / 1e9))

    libsrc = os.path.join(PROJ, 'export/levels/town')

    # 主线重要度排名表（缺文件也能跑，只是全部归到 D）
    ranks = {}
    if os.path.exists(RANK_PATH):
        try:
            _r = json.load(open(RANK_PATH, encoding='utf-8'))
            ranks = {k: v for k, v in _r.items() if not k.startswith('_')}
            print('排名表 %d 条' % len(ranks))
        except Exception as e:
            print('!! 排名表读取失败，忽略：%s' % e)

    items = []
    for man in glob.glob(os.path.join(root, '*', '*', 'manifest.json')):
        d = os.path.dirname(man)
        name = os.path.basename(d)
        catraw = os.path.basename(os.path.dirname(d))
        if catraw == 'lib':
            continue
        try:
            m = json.load(open(man, encoding='utf-8'))
        except Exception:
            continue
        srcs = m.get('sources')
        if isinstance(srcs, str):
            srcs = [srcs]

        # 分组：主角/剧情角色按主线重要度 tier 分，路人与动物保留自己的组
        r = ranks.get(name) or {}
        if catraw in ('cs', 'player'):
            grp = r.get('tier') or ('D' if catraw == 'cs' else 'S')
        else:
            grp = catraw
        items.append(dict(name=name, cat=CATNAME.get(catraw, catraw),
                          grp=grp,
                          rank=r.get('rank'), cn=r.get('cn'), note=r.get('note'),
                          # 带版本号，避免浏览器缓存住旧的 .glb（改模型后不刷新就看到老样子）
                          glb='%s/%s/%s.glb?v=%d' % (catraw, name, name, VER),
                          parts=m.get('parts'), tris=m.get('tris'), verts=m.get('verts'),
                          textures=m.get('textures'), sources=srcs or []))

    def sort_key(x):
        g = TIER_ORDER.index(x['grp']) if x['grp'] in TIER_ORDER else 90
        # 组内：有名次的按名次（同名词次按名字稳定排序），无名次的排后面按名字
        return (g, x['rank'] if x['rank'] else 9999, x['name'])
    items.sort(key=sort_key)
    print('NPC %d 个（其中已排主线名次 %d 个）'
          % (len(items), sum(1 for i in items if i['rank'])))

    # ---- 1) base64 伴生文件（只有 --b64 才生成）
    made = 0
    total_b64 = 0
    if a.b64:
        for i, it in enumerate(items):
            side = os.path.join(root, *it['glb'].split('/')) + '.js'
            if os.path.exists(side) and os.path.getsize(side) > 1000:
                total_b64 += os.path.getsize(side)
                continue
            raw = open(os.path.join(root, *it['glb'].split('/')), 'rb').read()
            b64 = base64.b64encode(raw).decode('ascii')
            with open(side, 'w', encoding='utf-8') as fh:
                fh.write('window.__NPCG=window.__NPCG||{};'
                         'window.__NPCG[%s]="%s";\n' % (json.dumps(it['name']), b64))
            made += 1
            total_b64 += len(b64) + 80
            if made % 50 == 0:
                print('  base64 伴生 %d/%d' % (i + 1, len(items)))
        print('base64 伴生文件：新建 %d 个，合计 %.2f GB' % (made, total_b64 / 1e9))

    # ---- 2) 源码内联
    def rd(p):
        return open(os.path.join(libsrc, p), encoding='utf-8').read()

    srcdata = dict(three=rd('three.module.js'),
                   orbit=rd('addons/controls/OrbitControls.js'),
                   bgu=rd('addons/utils/BufferGeometryUtils.js'),
                   gltf=rd('addons/loaders/GLTFLoader.js'))

    html = (HTML_HEAD
            .replace('__SRCDATA__', json_for_html(srcdata))
            .replace('__GRPMAP__', json_for_html(TIER_LABEL))
            .replace('__NPCLIST__', json_for_html(items))
            .replace('__TOTAL__', str(len(items))))
    with open(os.path.join(root, 'index.html'), 'w', encoding='utf-8') as fh:
        fh.write(html)
    # 不再生成子目录 bat：统一由根目录「打开查看器.bat」起一个服务（/npc/index.html）

    # ---- 3) 清单
    with open(os.path.join(root, 'index.csv'), 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh)
        w.writerow(['rank', 'tier', 'cn_name', 'name', 'category', 'note',
                    'glb', 'parts', 'verts', 'tris', 'textures', 'sources'])
        for it in items:
            w.writerow([it['rank'] or '', it['grp'] if it['grp'] in TIER_ORDER else '',
                        it['cn'] or '', it['name'], it['cat'], it['note'] or '',
                        it['glb'], it['parts'], it['verts'], it['tris'],
                        it['textures'], ' + '.join(it['sources'])])

    print('-> %s/index.html （%.1f MB，three.js 已内联）' % (root, os.path.getsize(os.path.join(root, 'index.html')) / 1e6))
    print('-> %s/index.csv' % root)
    print('-> 入口：根目录「打开查看器.bat」→ %s/index.html' % root)


if __name__ == '__main__':
    main()
