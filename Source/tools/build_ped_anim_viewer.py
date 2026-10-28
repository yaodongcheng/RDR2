"""把导出到 ped 骨架上的动画做成一个单文件 HTML 查看器（双击即开，不用服务器）。

输入：
  export/skeleton_runtime/ped_skeleton.json     124 骨 + rest 四元数
  export/animations_ped/**/*.json               每段动画（骨名 → 每帧四元数）
输出：
  export/skeleton_runtime/ped_anims.html

做法：数据全内联；用最简单的 CK 式 FK（pose = R_rest ⊗ q）画骨骼线段。
"""
import glob
import json
import math
import os

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = os.path.join(PROJ, 'export/skeleton_runtime/ped_skeleton.json')
SRC = os.path.join(PROJ, 'export/animations_ped')
OUT = os.path.join(PROJ, 'export/skeleton_runtime/ped_anims.html')

# 挑一组有代表性的片段（按关键字）
WANT = ['walk_interior', 'walk_slow', 'generic@action@unarmed@idle', 'pickup_body', 'drop_body',
        'throw_body', 'putdown_body', 'stow@lt', 'remove@lt', 'hogtie@human@pickup_body',
        'mech_drag', 'transitions', 'injured@idle', 'carried@human']


def main():
    sk = json.load(open(SK, encoding='utf-8'))
    bones = sk['bones']
    # ★ 只画"动画真正用到的骨 + 它们的祖先"：Pelt/Tail/Comb 这些装饰链会被等长骨头画成尖刺
    mp = json.load(open(os.path.join(PROJ, 'export/skeleton_runtime/ped_bone_map.json'), encoding='utf-8'))
    par_of = {b['name']: b['parent'] for b in bones}
    keep = set()
    for n in set(mp.values()):
        cur = n
        while cur and cur not in keep:
            keep.add(cur); cur = par_of.get(cur)
    bones = [b for b in bones if b['name'] in keep]
    print('绘制骨 %d / %d（去掉装饰链）' % (len(bones), len(sk['bones'])))
    names = [b['name'] for b in bones]
    idx = {n: i for i, n in enumerate(names)}

    files = glob.glob(os.path.join(SRC, '**', '*.json'), recursive=True)
    print('候选 %d 个文件' % len(files))

    picked = []
    used = set()
    # 按 WANT 顺序优先挑（保证 walk/idle 这些关键片段一定在）
    for w in WANT:
        for f in sorted(files):
            base = os.path.basename(f)
            if w not in base or f in used:
                continue
            d = json.load(open(f, encoding='utf-8'))
            best = None
            for a in d['animations']:
                if len(a['bones']) < 6:
                    continue
                if best is None or a['frames'] > best['frames']:
                    best = a
            if best:
                picked.append((d['file'], best))
                used.add(f)
                break

    # 每段降采样到 ≤120 帧
    clips = []
    for f, a in picked:
        step = max(1, a['frames'] // 120)
        tracks = {}
        for nm, qs in a['bones'].items():
            if nm not in idx:
                continue
            sub = qs[::step]
            tracks[nm] = [[round(x, 4) for x in q] for q in sub]
        if not tracks:
            continue
        clips.append(dict(name='%s#%d' % (os.path.splitext(f)[0].split('/')[-1], a['index']),
                          frames=len(next(iter(tracks.values()))),
                          fps=30 // step if step else 30,
                          tracks=tracks))
    print('内联 %d 段' % len(clips))

    data = dict(bones=[dict(n=b['name'], p=b['parent'], q=b['rest_quat'],
                            l=abs(b.get('offset', [0.15, 0, 0])[0]) or 0.15) for b in bones],
                clips=clips)
    html = TEMPLATE.replace('__DATA__', json.dumps(data, separators=(',', ':')))
    open(OUT, 'w', encoding='utf-8').write(html)
    print('->', OUT, '(%.1f MB)' % (os.path.getsize(OUT) / 1e6))


TEMPLATE = r"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>RDR2 ped 骨架 · 动画验收</title>
<style>
html,body{margin:0;height:100%;background:#0b0d10;color:#d7e0ea;overflow:hidden;
 font:13px/1.5 "Segoe UI",system-ui,"Microsoft YaHei",sans-serif}
#ui{position:fixed;left:10px;top:10px;background:#11161ce6;border:1px solid #263041;
 border-radius:8px;padding:10px 12px;z-index:9;min-width:320px}
#ui h1{font-size:13px;margin:0 0 8px;color:#8fd3ff}
select,button{background:#1b2330;color:#cfe0f0;border:1px solid #33415a;border-radius:6px;
 padding:4px 8px;font-size:12px;cursor:pointer}
#info{color:#7fe08a;font-size:12px;margin-top:6px}
input[type=range]{width:100%}
</style></head><body>
<div id="ui">
  <h1>RDR2 ped 骨架 · 动画验收（124 骨 / rest 来自游戏内存）</h1>
  <div><select id="clip"></select></div>
  <div style="margin-top:6px"><button id="play">暂停</button>
    <button id="spd">速度 1.0×</button>
    <button id="reset">复位视角</button></div>
  <div style="margin-top:6px"><input id="seek" type="range" min="0" max="1000" value="0"></div>
  <div id="info"></div>
</div>
<canvas id="cv"></canvas>
<script>
window.onerror = function(m, s, l){ document.getElementById('info').textContent = 'JS ERROR: '+m+' @'+l; };
const DATA = __DATA__;
const cv = document.getElementById('cv'), g = cv.getContext('2d');
let W=0,H=0,DPR=Math.min(2,devicePixelRatio||1);
function resize(){W=innerWidth;H=innerHeight;cv.width=W*DPR;cv.height=H*DPR;
  cv.style.width=W+'px';cv.style.height=H+'px';g.setTransform(DPR,0,0,DPR,0,0);}
addEventListener('resize',resize);resize();

const B = DATA.bones, IDX={}; B.forEach((b,i)=>IDX[b.n]=i);
const PAR = B.map(b=>b.p?IDX[b.p]:-1);
const REST = B.map(b=>b.q);

const clipSel=document.getElementById('clip'), playBtn=document.getElementById('play'),
      spdBtn=document.getElementById('spd'), seek=document.getElementById('seek'),
      info=document.getElementById('info');
DATA.clips.forEach((c,i)=>{const o=document.createElement('option');o.value=i;
  o.textContent=c.name+'  ('+(c.frames/c.fps).toFixed(1)+'s)';clipSel.appendChild(o);});

let cur=0, frame=0, playing=true, speed=1, last=0;
// 支持 ?clip=walk 预选（方便截图验收）
const qs=new URLSearchParams(location.search).get('clip');
if(qs){const k=DATA.clips.findIndex(c=>c.name.toLowerCase().includes(qs.toLowerCase())); if(k>=0){cur=k;clipSel.value=k;}}
function qmul(a,b){const [ax,ay,az,aw]=a,[bx,by,bz,bw]=b;
  return [aw*bx+ax*bw+ay*bz-az*by, aw*by-ax*bz+ay*bw+az*bx,
          aw*bz+ax*by-ay*bx+az*bw, aw*bw-ax*bx-ay*by-az*bz];}
function q2m(q){const [x,y,z,w]=q;
  return [1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),
          2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),
          2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)];}
function mul(A,Bm){const C=new Array(9);
  for(let r=0;r<3;r++)for(let c=0;c<3;c++){let s=0;for(let k=0;k<3;k++)s+=A[r*3+k]*Bm[k*3+c];C[r*3+c]=s;}
  return C;}
function fk(clip, f){
  const T=clip.tracks, R=[];
  for(let i=0;i<B.length;i++){
    const n=B[i].n, t=T[n];
    let q=REST[i];
    if(t){const k=Math.min(Math.floor(f), t.length-1); q=qmul(REST[i], t[k]);}
    const Rl=q2m(q);
    const p=PAR[i];
    R[i]= p>=0 ? mul(R[p], Rl) : Rl;
  }
  return R;
}
// 用"骨长=1"的示意骨架：每根骨从父节点向自己的 +X 方向延伸
function draw(){
  const clip=DATA.clips[cur];
  const R=fk(clip, frame);
  // 位置：父位置 + 父旋转 * (0.25,0,0)
  const P=new Array(B.length);
  for(let i=0;i<B.length;i++){
    const p=PAR[i];
    if(p<0){P[i]=[0,0,0];continue;}
    const Rp=R[p], L=(B[i].l||0.15);
    P[i]=[P[p][0]+Rp[0]*L, P[p][1]+Rp[3]*L, P[p][2]+Rp[6]*L];
  }
  // ★ ped 骨架自己的"上"不是 +Z：用 盆骨→头 方向当屏幕竖直轴，保证显示是站立的
  const iPel=IDX['SKEL_Pelvis'], iHead=IDX['SKEL_Head'];
  let up=[0,0,1];
  if(iPel!==undefined && iHead!==undefined){
    up=[P[iHead][0]-P[iPel][0], P[iHead][1]-P[iPel][1], P[iHead][2]-P[iPel][2]];
    const n=Math.hypot(...up)||1; up=up.map(x=>x/n);
  }
  let side=[0,1,0];
  if(Math.abs(up[1])>0.9) side=[1,0,0];
  const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
  // 取景（投影到 up/side 平面）
  let mn=[1e9,1e9],mx=[-1e9,-1e9];
  for(const p of P){
    const x=dot(p,side), y=dot(p,up);
    mn[0]=Math.min(mn[0],x);mx[0]=Math.max(mx[0],x);
    mn[1]=Math.min(mn[1],y);mx[1]=Math.max(mx[1],y);
  }
  const c=[(mn[0]+mx[0])/2,(mn[1]+mx[1])/2];
  const sz=Math.max(mx[0]-mn[0],mx[1]-mn[1],0.8);
  const sc=Math.min(W,H)*0.62/sz;
  const proj=(p)=>[W/2+(dot(p,side)-c[0])*sc, H/2-(dot(p,up)-c[1])*sc];
  g.fillStyle='#0b0d10';g.fillRect(0,0,W,H);
  g.strokeStyle='#3a4a63';g.lineWidth=1;
  for(let i=0;i<B.length;i++){
    const p=PAR[i]; if(p<0)continue;
    const a=P[p], b=P[i];
    const A=proj(a), Bp=proj(b);
    g.beginPath(); g.moveTo(A[0],A[1]); g.lineTo(Bp[0],Bp[1]); g.stroke();
  }
  g.fillStyle='#8fd3ff';
  for(const p of P){const q=proj(p);g.beginPath();g.arc(q[0],q[1],1.8,0,7);g.fill();}
  info.textContent=clip.name+' · 第 '+Math.floor(frame)+' / '+clip.frames+' 帧 · '+Object.keys(clip.tracks).length+' 条骨轨';
}
function tick(t){
  if(!last)last=t;
  const dt=(t-last)/1000;last=t;
  if(playing){
    frame += dt*clipFps()*speed;
    const clip=DATA.clips[cur];
    if(frame>=clip.frames) frame=0;
    seek.value=Math.round(1000*frame/clip.frames);
  }
  draw();requestAnimationFrame(tick);
}
function clipFps(){return DATA.clips[cur].fps||30;}
clipSel.onchange=()=>{cur=+clipSel.value;frame=0;};
playBtn.onclick=()=>{playing=!playing;playBtn.textContent=playing?'暂停':'播放';};
spdBtn.onclick=()=>{speed = speed>=2?0.5:speed*2;spdBtn.textContent='速度 '+speed.toFixed(1)+'×';};
seek.oninput=()=>{const clip=DATA.clips[cur];frame=clip.frames*seek.value/1000;};
document.getElementById('reset').onclick=()=>{frame=0;};
requestAnimationFrame(tick);
</script></body></html>
"""


if __name__ == '__main__':
    main()
