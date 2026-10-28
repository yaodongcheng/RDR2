"""RDR2 **原生骨架** 多动作预览器（单文件 HTML）。

输入：`骑砍2动画重定向/input/source/rdr2/*.gltf`
      （由 `export_anim_json.py` + `export_gltf_source.py --skel yft` 产出：
        756 骨原生骨架 + `.ycd` 解出的旋转轨）
输出：`export/skeleton_runtime/rdr2_actions.html`

只画**骨骼**（线段 + 关节球），不挂网格 —— 网格蒙皮要先解 `.ydd` 的局部骨架布局（见 README）。

用法: uv run python tools/build_skel_actions_viewer.py
"""
import os
import json
import glob
import struct
import base64

PROJ = r'D:/BrainMaker/大镖客2解包分析'
SRC = r'D:/BrainMaker/骑砍2动画重定向/input/source/rdr2'
OUT = os.path.join(PROJ, 'export/skeleton_runtime/rdr2_actions.html')
THREE = os.path.join(PROJ, 'export/levels/town/three.module.js')

CT = {5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2), 5123: ('H', 2), 5125: ('I', 4), 5126: ('f', 4)}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def load_gltf(path):
    d = json.load(open(path, encoding='utf-8'))
    bufs = []
    for b in d.get('buffers', []):
        uri = b.get('uri')
        bufs.append(base64.b64decode(uri.split(',', 1)[1]) if uri and uri.startswith('data:') else b'')
    return d, bufs


def acc(d, bufs, idx):
    a = d['accessors'][idx]
    bv = d['bufferViews'][a['bufferView']]
    buf = bufs[bv.get('buffer', 0)]
    fmt, sz = CT[a['componentType']]
    n = NC[a['type']]
    stride = bv.get('byteStride') or (sz * n)
    off = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    return [struct.unpack_from('<' + fmt * n, buf, off + i * stride) for i in range(a['count'])]


def r4(v):
    return [round(x, 4) for x in v]


def parse(path):
    d, bufs = load_gltf(path)
    nodes = d['nodes']
    out_nodes = []
    for n in nodes:
        nm = n.get('name', '')
        rec = dict(nm=nm, p=-1, sk=nm.startswith('SKEL_'))
        if 'matrix' in n:                     # 极少见，转成 TRS 就跳过了 → 用单位
            rec.update(t=[0, 0, 0], r=[0, 0, 0, 1], s=[1, 1, 1])
        else:
            rec.update(t=r4(n.get('translation', [0, 0, 0])),
                       r=r4(n.get('rotation', [0, 0, 0, 1])),
                       s=r4(n.get('scale', [1, 1, 1])))
        out_nodes.append(rec)
    for i, n in enumerate(nodes):
        for c in n.get('children', []):
            out_nodes[c]['p'] = i

    clips = []
    for a in d.get('animations', []):
        tracks = {}
        for ch in a['channels']:
            s = a['samplers'][ch['sampler']]
            ni = ch['target']['node']
            path_ = ch['target']['path']
            if path_ not in ('rotation', 'translation'):
                continue
            keys = acc(d, bufs, s['input'])
            vals = acc(d, bufs, s['output'])
            t = tracks.setdefault(ni, {})
            t[path_[0]] = [[round(k[0], 4) for k in keys], [r4(v) for v in vals]]
        if not tracks:
            continue
        nm = a.get('name') or os.path.splitext(os.path.basename(path))[0]
        dur = max(max(tr['r'][0][-1] if 'r' in tr else 0, tr['t'][0][-1] if 't' in tr else 0)
                  for tr in tracks.values())
        nfr = max(len(tr['r'][0]) if 'r' in tr else 0 for tr in tracks.values())
        clips.append(dict(name=nm, dur=round(dur, 3), keys=nfr,
                          tracks={str(k): v for k, v in tracks.items()}))
    return out_nodes, clips


HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>RDR2 原生骨架 · 动作预览</title>
<style>
html,body{margin:0;height:100%;background:#0b0d10;color:#d7e0ea;overflow:hidden;
 font:13px/1.5 "Segoe UI",system-ui,"Microsoft YaHei",sans-serif}
#ui{position:fixed;left:10px;top:10px;background:#11161ce6;border:1px solid #263041;
 border-radius:8px;padding:10px 12px;z-index:9;min-width:330px}
#ui h1{font-size:13px;margin:0 0 8px;color:#8fd3ff}
#ui select,#ui button{background:#1b2330;color:#cfe0f0;border:1px solid #33415a;
 border-radius:6px;padding:4px 8px;font-size:12px;cursor:pointer}
#ui button.on{background:#2c6fb5;border-color:#4b9ade;color:#fff}
.row{margin:6px 0}
#info{color:#7fe08a;font-size:12px;margin-top:6px}
input[type=range]{width:100%}
</style></head><body>
<div id="ui">
  <h1>RDR2 原生骨架 · 动作预览<small style="color:#7b8a9c">（756 骨 / 只画骨骼）</small></h1>
  <div class="row"><select id="clip"></select></div>
  <div class="row"><button id="play" class="on">暂停</button>
    <button id="spd">速度 1.0×</button>
    <button id="loop" class="on">循环</button></div>
  <div class="row"><input id="seek" type="range" min="0" max="1000" value="0"></div>
  <div id="info"></div>
</div>
<div id="boot" style="position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);color:#8fd3ff">加载中…</div>
<script id="three-src" type="text/plain">__THREE__</script>
<script id="data" type="application/json">__DATA__</script>
<script>
(async function(){
const SRC = JSON.parse(document.getElementById('data').textContent);
const boot = document.getElementById('boot');
const url = URL.createObjectURL(new Blob([document.getElementById('three-src').textContent],
                                         {type:'text/javascript'}));
const THREE = await import(url);
boot.style.display = 'none';

const renderer = new THREE.WebGLRenderer({antialias:true});
renderer.setPixelRatio(Math.min(2, devicePixelRatio||1));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0d1117);
const cam = new THREE.PerspectiveCamera(40, innerWidth/innerHeight, 0.01, 200);
scene.add(new THREE.HemisphereLight(0xffffff, 0x334, 2.0));
const dl = new THREE.DirectionalLight(0xffffff, 1.6); dl.position.set(2,4,3); scene.add(dl);

let root=null, lineSeg=null, joints=null, skel=[], autoYaw=0;

function buildBoneTree(nodes){
  const objs = nodes.map(()=>new THREE.Object3D());
  nodes.forEach((n,i)=>{
    objs[i].position.fromArray(n.t);
    objs[i].quaternion.fromArray(n.r);
    objs[i].scale.fromArray(n.s);
    if(n.p>=0) objs[n.p].add(objs[i]);
  });
  const g = new THREE.Group();
  const roots = nodes.map((n,i)=>i).filter(i=>nodes[i].p<0);
  roots.forEach(i=>g.add(objs[i]));
  return {group:g, objs};
}

function buildSkelVisual(nodes){
  const N = nodes.length;
  const pos = new Float32Array(N*3*2);           // 每条骨一段
  const lg = new THREE.BufferGeometry();
  lg.setAttribute('position', new THREE.BufferAttribute(pos,3));
  const seg = new THREE.LineSegments(lg, new THREE.LineBasicMaterial({color:0x5ab0ff}));
  const jg = new THREE.BufferGeometry();
  jg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N*3),3));
  const pts = new THREE.Points(jg, new THREE.PointsMaterial({color:0xffd479, size:0.028, sizeAttenuation:true}));
  return {seg, pts, pos, posJ: jg.attributes.position.array};
}

function setClip(ci){
  const clip = SRC.clips[ci];
  if(root){ scene.remove(root.group); }
  const {group, objs} = buildBoneTree(clip.nodes);
  root = {group, objs, clip, cur:0, t:0};
  scene.add(group);
  // 只需重建一次骨架可视
  if(lineSeg) scene.remove(lineSeg.seg), scene.remove(lineSeg.pts);
  lineSeg = buildSkelVisual(clip.nodes);
  scene.add(lineSeg.seg); scene.add(lineSeg.pts);
  // 自动取向 + 取景：算一次包围盒
  group.updateMatrixWorld(true);
  const box = new THREE.Box3();
  clip.nodes.forEach((n,i)=>{ if(n.sk!==false) box.expandByPoint(objs[i].getWorldPosition(new THREE.Vector3())); });
  const sz = box.getSize(new THREE.Vector3()), c = box.getCenter(new THREE.Vector3());
  const upIsY = sz.y >= sz.z;
  group.rotation.x = upIsY ? 0 : -Math.PI/2;
  group.updateMatrixWorld(true);
  const box2 = new THREE.Box3();
  clip.nodes.forEach((n,i)=>{ if(n.sk!==false) box2.expandByPoint(objs[i].getWorldPosition(new THREE.Vector3())); });
  const s2 = box2.getSize(new THREE.Vector3()), c2 = box2.getCenter(new THREE.Vector3());
  const h = Math.max(s2.x,s2.y,s2.z);
  cam.position.set(c2.x + h*1.05, c2.y + h*0.28, c2.z + h*1.75);
  cam.lookAt(c2.x, c2.y, c2.z);
  cam.near = h/500; cam.far = h*40; cam.updateProjectionMatrix();
  document.getElementById('info').textContent =
    clip.name + ' · ' + clip.keys + ' 关键帧 · ' + clip.dur.toFixed(2) + ' s · ' +
    Object.keys(clip.tracks).length + ' 条轨 · ' + clip.nodes.filter(n=>n.sk!==false).length + ' 骨 · 朝向' + (upIsY?'Y-up':'已转Y-up');
}

// 采样：线性插值（旋转用 slerp）
function sampleTrack(tr, t, out){
  const [ts, vs] = tr;
  if(t <= ts[0]) return vs[0];
  if(t >= ts[ts.length-1]) return vs[vs.length-1];
  let lo=0, hi=ts.length-1;
  while(hi-lo>1){ const m=(lo+hi)>>1; if(ts[m]<=t) lo=m; else hi=m; }
  const a=vs[lo], b=vs[hi], u=(t-ts[lo])/Math.max(1e-6, ts[hi]-ts[lo]);
  if(a.length===4){
    const qa=new THREE.Quaternion().fromArray(a), qb=new THREE.Quaternion().fromArray(b);
    qa.slerp(qb,u); return qa.toArray();
  }
  return a.map((x,i)=>x+(b[i]-x)*u);
}

function applyFrame(){
  const {objs, clip} = root;
  for(const [ni, tr] of Object.entries(clip.tracks)){
    const o = objs[ni|0];
    if(tr.r) o.quaternion.fromArray(sampleTrack(tr.r, root.t, null));
    if(tr.t) o.position.fromArray(sampleTrack(tr.t, root.t, null));
  }
  root.group.updateMatrixWorld(true);
  // 更新线段
  const nodes = clip.nodes, pos = lineSeg.pos, posJ = lineSeg.posJ;
  const A = new THREE.Vector3(), B = new THREE.Vector3();
  for(let i=0;i<nodes.length;i++){
    const show = nodes[i].sk !== false;
    objs[i].getWorldPosition(A);
    posJ[i*3]=show?A.x:0; posJ[i*3+1]=show?A.y:0; posJ[i*3+2]=show?A.z:0;
    const p = nodes[i].p;
    let showSeg = show;
    if(p>=0 && nodes[p].sk===false) showSeg = false;
    if(showSeg && p>=0){ objs[p].getWorldPosition(B); } else { B.copy(A); showSeg=false; }
    pos[i*6]=B.x; pos[i*6+1]=B.y; pos[i*6+2]=B.z;
    pos[i*6+3]=showSeg?A.x:B.x; pos[i*6+4]=showSeg?A.y:B.y; pos[i*6+5]=showSeg?A.z:B.z;
  }
  lineSeg.seg.geometry.attributes.position.needsUpdate = true;
  lineSeg.pts.geometry.attributes.position.needsUpdate = true;
}

let playing = true, speed = 1, loop = true, last = performance.now();
const sel = document.getElementById('clip');
SRC.clips.forEach((c,i)=>{ const o=document.createElement('option'); o.value=i;
  o.textContent = c.name.replace(/^rdr2_/,'') + '  (' + c.dur.toFixed(1)+'s)'; sel.appendChild(o); });
sel.onchange = ()=>setClip(+sel.value);
document.getElementById('play').onclick = e=>{ playing=!playing;
  e.target.classList.toggle('on', playing); e.target.textContent = playing?'暂停':'播放'; };
document.getElementById('spd').onclick = e=>{ speed = speed>=2 ? 0.5 : speed*2;
  e.target.textContent = '速度 ' + speed.toFixed(1) + '×'; };
document.getElementById('loop').onclick = e=>{ loop=!loop; e.target.classList.toggle('on', loop); };
const seek = document.getElementById('seek');
seek.oninput = ()=>{ if(!root) return; root.t = (+seek.value/1000)*root.clip.dur; applyFrame(); };

setClip(0); applyFrame();

function loopFn(now){
  const dt = Math.min(0.1, (now-last)/1000); last = now;
  if(root){
    if(playing){
      root.t += dt*speed;
      if(root.t > root.clip.dur){ if(loop) root.t = root.t % root.clip.dur; else { root.t = root.clip.dur; playing=false; } }
    }
    applyFrame();
    seek.value = Math.round(1000*root.t/Math.max(1e-6,root.clip.dur));
  }
  renderer.render(scene, cam);
  requestAnimationFrame(loopFn);
}
requestAnimationFrame(loopFn);
addEventListener('resize', ()=>{ cam.aspect = innerWidth/innerHeight; cam.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight); });
})();
</script></body></html>
"""


def main():
    files = sorted(glob.glob(os.path.join(SRC, '*.gltf')))
    clips = []
    nodes_ref = None
    for p in files:
        try:
            nodes, cs = parse(p)
        except Exception as e:
            print('  skip', os.path.basename(p), e)
            continue
        for c in cs:
            c['nodes'] = nodes
            clips.append(c)
        if nodes_ref is None:
            nodes_ref = nodes
        print('  %-30s %d 轨  %d 关键帧  %.2fs' % (os.path.basename(p),
              len(cs[0]['tracks']) if cs else 0, cs[0]['keys'] if cs else 0,
              cs[0]['dur'] if cs else 0))
    clips.sort(key=lambda c: (0 if 'walk' in c['name'] else 1, c['name']))
    data = dict(clips=clips)
    payload = json.dumps(data, separators=(',', ':')).replace('</', '<\\/')
    three = open(THREE, encoding='utf-8').read().replace('</script', '<\\/script')
    html = HTML.replace('__THREE__', three).replace('__DATA__', payload)
    with open(OUT, 'w', encoding='utf-8') as fh:
        fh.write(html)
    print('\n%d 个动作 -> %s (%.1f MB)' % (len(clips), OUT, os.path.getsize(OUT)/1e6))


if __name__ == '__main__':
    main()
