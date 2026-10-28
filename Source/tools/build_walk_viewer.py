"""生成 RDR2 `walk` 动画骨架查看器（单文件 HTML）。

源：`骑砍2动画重定向/input/source/rdr2/rdr2_walk.gltf`
   （由 `tools/export_gltf_source.py --skel yft` 从 `.yft` 骨架 + `.ycd` 动画导出）
   763 节点 / 1 个 skin / 1 个动画 `rdr2_walk`（24 条旋转轨 × 404 帧 @30fps = 13.43 s）

做法：把 glTF 的节点层级 / rest 变换 / 旋转关键帧抓出来，重排成紧凑 JSON，
再用 three.js 按帧解算世界矩阵、画骨骼线段 + 关节球。
输出：`export/skeleton_runtime/rdr2_walk.html`
"""
import os
import json
import struct
import base64
import math

ROOT = r'D:/BrainMaker/大镖客2解包分析'
SK = os.path.join(ROOT, 'export/skeleton_runtime')
GLTF = r'D:/BrainMaker/骑砍2动画重定向/input/source/rdr2/rdr2_walk.gltf'
three = open(os.path.join(ROOT, 'export/levels/town/three.module.js'), encoding='utf-8').read().replace('</script', '<\\/script')

CT = {5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2), 5123: ('H', 2), 5125: ('I', 4), 5126: ('f', 4)}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def load_gltf(path):
    d = json.load(open(path, encoding='utf-8'))
    bufs = []
    for b in d.get('buffers', []):
        uri = b.get('uri')
        if uri and uri.startswith('data:'):
            bufs.append(base64.b64decode(uri.split(',', 1)[1]))
        elif uri:
            bufs.append(open(os.path.join(os.path.dirname(path), uri), 'rb').read())
        else:
            bufs.append(b'')
    return d, bufs


def accessor(d, bufs, idx):
    a = d['accessors'][idx]
    bv = d['bufferViews'][a['bufferView']]
    buf = bufs[bv.get('buffer', 0)]
    fmt, sz = CT[a['componentType']]
    n = NC[a['type']]
    stride = bv.get('byteStride') or (sz * n)
    off = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    out = []
    for i in range(a['count']):
        out.append(struct.unpack_from('<' + fmt * n, buf, off + i * stride))
    return out


def main():
    d, bufs = load_gltf(GLTF)
    nodes = d['nodes']
    parent = [-1] * len(nodes)
    for i, n in enumerate(nodes):
        for c in n.get('children', []):
            parent[c] = i
    keep = {}
    for i, n in enumerate(nodes):
        nm = n.get('name') or ''
        if nm.startswith('SKEL_') or nm in ('SKEL_ROOT',):
            keep[i] = len(keep)
    # 补上被跳过父节点（保证层级连通）：沿父链把中间节点也收进来
    for i in list(keep):
        p = parent[i]
        while p != -1 and p not in keep:
            keep[p] = 0
            p = parent[p]
    for k, i in enumerate(sorted(keep)):
        keep[i] = k
    order = sorted(keep)
    out_nodes = []
    for i in order:
        n = nodes[i]
        out_nodes.append(dict(
            name=n.get('name') or ('n%d' % i),
            parent=keep.get(parent[i], -1),
            t=list(n.get('translation', [0, 0, 0])),
            r=list(n.get('rotation', [0, 0, 0, 1])),
        ))
    anim = d['animations'][0]
    chans = {}
    fps = 30.0
    nframes = 0
    for ch in anim['channels']:
        if ch['target']['path'] != 'rotation':
            continue
        ni = ch['target']['node']
        if ni not in keep:
            continue
        s = anim['samplers'][ch['sampler']]
        t = [x[0] for x in accessor(d, bufs, s['input'])]
        q = accessor(d, bufs, s['output'])
        nframes = max(nframes, len(q))
        chans[keep[ni]] = dict(count=len(q), q=[round(v, 6) for qq in q for v in qq])
    if nframes:
        total = max([max(x[0] for x in accessor(d, bufs, anim['samplers'][c['sampler']]['input']))
                     for c in anim['channels'] if c['target']['path'] == 'rotation'] or [1])
        fps = nframes / total if total else 30.0
    print(f'节点（含补全）{len(out_nodes)} 根；动画轨 {len(chans)} 条；{nframes} 帧 @ {fps:.2f} fps')
    # ---- 用 rest 变换算世界位置，供查看器自动取景 ----
    def qmul(a, b):
        ax, ay, az, aw = a; bx, by, bz, bw = b
        return [aw*bx+ax*bw+ay*bz-az*by, aw*by-ax*bz+ay*bw+az*bx,
                aw*bz+ax*by-ay*bx+az*bw, aw*bw-ax*bx-ay*by-az*bz]

    def qrot(q, v):
        x, y, z, w = q; vx, vy, vz = v
        tx, ty, tz = 2*(y*vz-z*vy), 2*(z*vx-x*vz), 2*(x*vy-y*vx)
        return [vx+w*tx+(y*tz-z*ty), vy+w*ty+(z*tx-x*tz), vz+w*tz+(x*ty-y*tx)]

    memo = {}

    def resolve(i):
        if i in memo:
            return memo[i]
        n = out_nodes[i]
        t, r = n['t'], n['r']
        if n['parent'] < 0:
            memo[i] = [t, r]
        else:
            pt, pr = resolve(n['parent'])       # 递归（拓扑序不保证，改记忆化）
            rt = qrot(pr, t)
            memo[i] = [[pt[0]+rt[0], pt[1]+rt[1], pt[2]+rt[2]], qmul(pr, r)]
        return memo[i]

    world = [resolve(i) for i in range(len(out_nodes))]
    ws = [w[0] for w in world]
    bx = (min(w[0] for w in ws), max(w[0] for w in ws))
    by = (min(w[1] for w in ws), max(w[1] for w in ws))
    bz = (min(w[2] for w in ws), max(w[2] for w in ws))
    print(f'rest 世界包围盒 x{bx} y{by} z{bz}')
    tgt = [(bx[0]+bx[1])/2, (by[0]+by[1])/2, (bz[0]+bz[1])/2]
    span = max(bx[1]-bx[0], by[1]-by[0], bz[1]-bz[0])
    data = dict(nodes=out_nodes, anim=chans, frames=nframes, fps=round(fps, 4),
                tgt=[round(v, 3) for v in tgt], dist=round(span*1.9, 3))
    HTML = open(os.path.join(SK, '_walk_template.html'), encoding='utf-8').read() if os.path.exists(os.path.join(SK, '_walk_template.html')) else TEMPLATE
    html = (HTML.replace('__THREE__', three)
            .replace('__DATA__', json.dumps(data, separators=(',', ':')))
            .replace('__NB__', str(len(out_nodes))).replace('__NT__', str(len(chans)))
            .replace('__NF__', str(nframes)).replace('__FPS__', f'{fps:.2f}'))
    out = os.path.join(SK, 'rdr2_walk.html')
    open(out, 'w', encoding='utf-8').write(html)
    print('wrote', out, round(os.path.getsize(out) / 1024, 1), 'KB')


TEMPLATE = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>RDR2 walk 动画 — 骨架演示</title>
<style>body{margin:0;background:#0b0d10;color:#d7e0ea;font:13px/1.5 "Segoe UI",system-ui,sans-serif;overflow:hidden}
#hud{position:fixed;left:10px;top:10px;background:#11161ce6;border:1px solid #263041;border-radius:8px;padding:10px 12px;max-width:470px;z-index:9}
#hud h1{font-size:14px;margin:0 0 6px;color:#8fd3ff} b{color:#ffd479}
button{background:#1b2330;color:#cfe0f0;border:1px solid #33415a;border-radius:6px;padding:3px 10px;margin:2px;cursor:pointer}
button.on{background:#2c6fb5;border-color:#4b9ade;color:#fff}
input[type=range]{vertical-align:middle}
#err{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);color:#f88;z-index:20}</style></head><body>
<div id="hud">
 <h1>RDR2 <b>walk</b> — 骨架动画（`.ycd` → glTF → 本查看器）</h1>
 <div>骨 <b>__NB__</b> 根 · 旋转轨 <b>__NT__</b> 条 · <b>__NF__</b> 帧 @ <b>__FPS__</b> fps</div>
 <div class="row"><button id="play">⏸ 暂停</button> 速度 <span id="spd">1.00×</span>
   <button onclick="window.__s(0.25)">0.25×</button><button onclick="window.__s(0.5)">0.5×</button><button onclick="window.__s(1)">1×</button></div>
 <div>帧 <input id="fr" type="range" min="0" max="__NF__" value="0" style="width:230px"> <span id="frv">0</span></div>
 <div>左键旋转 / 滚轮缩放 / 右键平移 · 地面网格 = 1 m</div>
</div>
<div id="err"></div>
<script id="three-src" type="text/plain">__THREE__</script>
<script id="data-src" type="application/json">__DATA__</script>
<script type="module">
const D=JSON.parse(document.getElementById('data-src').textContent);
let THREE,renderer,scene,cam,objs=[],edges=[],playing=true,speed=1,frame=0,acc=0;
let yaw=1.15,pitch=0.06,dist=D.dist,px=0,py=0;
const qTmp=[];
(async()=>{try{
 const url=URL.createObjectURL(new Blob([document.getElementById('three-src').textContent],{type:'text/javascript'}));
 THREE=await import(url);
 renderer=new THREE.WebGLRenderer({antialias:true});
 renderer.domElement.style.position='fixed';renderer.domElement.style.left='0';renderer.domElement.style.top='0';renderer.domElement.style.zIndex='0';
 const W=()=>Math.max(640,document.documentElement.clientWidth),H=()=>Math.max(480,document.documentElement.clientHeight);
 renderer.setSize(W(),H()); renderer.outputColorSpace=THREE.SRGBColorSpace; document.body.appendChild(renderer.domElement);
 scene=new THREE.Scene(); scene.background=new THREE.Color(0x0e1116);
 cam=new THREE.PerspectiveCamera(40,W()/H(),0.01,200);
 // 层级
 objs=D.nodes.map(n=>{const o=new THREE.Object3D(); o.position.fromArray(n.t); o.quaternion.fromArray(n.r); return o;});
 D.nodes.forEach((n,i)=>{ if(n.parent>=0) objs[n.parent].add(objs[i]); else scene.add(objs[i]); });
 // 画骨骼：每个有父的骨画一条线
 const pairs=[];
 D.nodes.forEach((n,i)=>{ if(n.parent>=0) pairs.push([n.parent,i]); });
 const lgGeo=new THREE.BufferGeometry(); lgGeo.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(pairs.length*6),3));
 const lg=new THREE.LineSegments(lgGeo, new THREE.LineBasicMaterial({color:0x7fe0ff}));
 scene.add(lg);
 // 关节：用 Points（比 InstancedMesh 稳）
 const jgeo=new THREE.BufferGeometry(); jgeo.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(D.nodes.length*3),3));
 const jpts=new THREE.Points(jgeo, new THREE.PointsMaterial({color:0xffd479,size:0.018,sizeAttenuation:true}));
 scene.add(jpts);
 // 地面网格（1m）
 const grid=new THREE.GridHelper(4,4,0x2a3a4a,0x1b2530); grid.position.y=D.tgt[1]-D.dist*0.42; scene.add(grid);
 const axes=new THREE.AxesHelper(0.4); scene.add(axes);
 const tgt=new THREE.Vector3(D.tgt[0],D.tgt[1],D.tgt[2]);
 function upd(){ cam.position.set(tgt.x+Math.cos(yaw)*Math.cos(pitch)*dist, tgt.y+Math.sin(pitch)*dist, tgt.z+Math.sin(yaw)*Math.cos(pitch)*dist); cam.lookAt(tgt.x+px,tgt.y+py,tgt.z); }
 function setFrame(f){
   f=((f%D.frames)+D.frames)%D.frames;
   frame=f;
   const f0=Math.floor(f), f1=(f0+1)%D.frames, a=f-f0;
   Object.keys(D.anim).forEach(k=>{const A=D.anim[k]; const i=k|0;
     const q0=A.q.slice(f0*4,f0*4+4), q1=A.q.slice(f1*4,f1*4+4);
     const qa=new THREE.Quaternion(q0[0],q0[1],q0[2],q0[3]);
     const qb=new THREE.Quaternion(q1[0],q1[1],q1[2],q1[3]);
     objs[i].quaternion.slerpQuaternions(qa,qb,a);
   });
   objs.forEach(o=>o.updateMatrixWorld(true));
   if(!lg||!lg.geometry){ throw new Error('lg 未就绪'); }
   const pos=lg.geometry.attributes.position.array; let k=0;
   const tmp=new THREE.Vector3();
   pairs.forEach(([p,c])=>{ objs[p].getWorldPosition(tmp); pos[k++]=tmp.x;pos[k++]=tmp.y;pos[k++]=tmp.z;
                            objs[c].getWorldPosition(tmp); pos[k++]=tmp.x;pos[k++]=tmp.y;pos[k++]=tmp.z; });
   lg.geometry.attributes.position.needsUpdate=true;
   const jp=jgeo.attributes.position.array;
   D.nodes.forEach((n,i)=>{ objs[i].getWorldPosition(tmp); jp[i*3]=tmp.x; jp[i*3+1]=tmp.y; jp[i*3+2]=tmp.z; });
   jgeo.attributes.position.needsUpdate=true;
   document.getElementById('fr').value=frame|0; document.getElementById('frv').textContent=frame.toFixed(1);
 }
 const fr=document.getElementById('fr');
 fr.oninput=e=>{playing=false; document.getElementById('play').textContent='▶ 播放'; setFrame(parseFloat(e.target.value)); };
 document.getElementById('play').onclick=e=>{playing=!playing; e.target.textContent=playing?'⏸ 暂停':'▶ 播放';};
 window.__s=v=>{speed=v; document.getElementById('spd').textContent=v.toFixed(2)+'×';};
 setFrame(0); upd(); cam.updateMatrixWorld(true); renderer.render(scene,cam);
 let drag=0,lx=0,ly=0;
 renderer.domElement.addEventListener('mousedown',e=>{drag=e.button===2?2:1;lx=e.clientX;ly=e.clientY;});
 addEventListener('mouseup',()=>drag=0); addEventListener('contextmenu',e=>e.preventDefault());
 addEventListener('mousemove',e=>{ if(!drag)return; const dx=e.clientX-lx,dy=e.clientY-ly; lx=e.clientX; ly=e.clientY;
  if(drag===1){yaw-=dx*0.006; pitch=Math.max(-1.4,Math.min(1.4,pitch+dy*0.006));} else {px-=dx*dist*0.0012; py+=dy*dist*0.0012;} upd(); });
 renderer.domElement.addEventListener('wheel',e=>{e.preventDefault(); dist*=(1+Math.sign(e.deltaY)*0.12); dist=Math.max(0.3,Math.min(40,dist)); upd();},{passive:false});
 addEventListener('resize',()=>{cam.aspect=W()/H();cam.updateProjectionMatrix();renderer.setSize(W(),H());});
 let last=performance.now();
 (function loop(t){ const dt=(t-last)/1000; last=t; if(playing){ acc+=dt*D.fps*speed; if(acc>=1){ setFrame(frame+acc); acc=0; } }
   renderer.render(scene,cam); requestAnimationFrame(loop); })(performance.now());
 // 供截图：?f=NNN 定格
 const Q=new URLSearchParams(location.search.replace(/^\?/,''));
 if(Q.has('f')){ playing=false; document.getElementById('play').textContent='▶ 播放'; setFrame(parseFloat(Q.get('f'))||0); renderer.render(scene,cam); }
 window.__ready=true;
}catch(e){document.getElementById('err').textContent='ERR: '+e.message; console.error(e);}})();
</script></body></html>"""

if __name__ == '__main__':
    main()
