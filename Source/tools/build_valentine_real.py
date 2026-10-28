"""Build a self-contained single-file viewer: RDR2 Valentine terrain + REAL building meshes
(.ydr geometry decoded) + gray boxes for the remaining entities.

Axis mapping RDR2 (right-handed, Z-up) -> three.js (right-handed, Y-up):
    three = ( x,  z, -y )        M = [[1,0,0],[0,0,1],[0,-1,0]]
    R_three = M * R_rdr * M^T    (applied to each entity quaternion)

Usage: python build_valentine_real.py
Output: export/levels/town/valentine_real.html
"""
import json, os, struct, base64
import glob as _glob
import numpy as np

ROOT = r"D:/BrainMaker/大镖客2解包分析"
TOWN = os.path.join(ROOT, "export/levels/town")
HM = os.path.join(ROOT, "export/levels/terrain/data/levels/rdr3/heightmap.dat")

M = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=np.float64)

three = open(os.path.join(TOWN, "three.module.js"), encoding="utf-8").read().replace("</script", "<\\/script")
E = json.load(open(os.path.join(TOWN, "valentine.json"), encoding="utf-8"))
A = json.load(open(os.path.join(TOWN, "archetypes.json"), encoding="utf-8"))
MESH = json.load(open(os.path.join(TOWN, "valentine_meshes.json"), encoding="utf-8"))
_TEXF = []
_env = os.environ.get("BM_TEX", "")
if _env and os.path.exists(_env):
    _TEXF = [_env]
else:
    for _pat in ("**/*_BC3_sRGB.png", "**/*_BC3.png", "**/*wood*.png"):
        _TEXF += sorted(_glob.glob(os.path.join(ROOT, "export/models/textures", _pat), recursive=True))
        if _TEXF:
            break
WOOD_B64 = ""
if _TEXF:
    from PIL import Image as _I
    import io as _io
    _im = _I.open(_TEXF[0]).resize((512,512)).convert("RGB")
    _b = _io.BytesIO(); _im.save(_b, "PNG"); WOOD_B64 = base64.b64encode(_b.getvalue()).decode()
print("wood texture:", _TEXF[0] if _TEXF else "NONE")

# ---- T5: 每栋建筑的原生贴图（由 tools/extract_building_textures.py 产出）----
_BTEXP = os.path.join(TOWN, "valentine_textures.json")
BTEX = json.load(open(_BTEXP, encoding="utf-8")) if os.path.exists(_BTEXP) else {"meshes": {}, "tex": {}}
print(f"native textures: {len(BTEX.get('tex', {}))} 张, 覆盖 {len(BTEX.get('meshes', {}))} 栋建筑")

LODM = json.load(open(os.path.join(TOWN, "valentine_lod_meshes.json"), encoding="utf-8"))
PROPM = json.load(open(os.path.join(TOWN, "valentine_prop_meshes.json"), encoding="utf-8"))
TERRM = json.load(open(os.path.join(TOWN, "valentine_terrain_meshes.json"), encoding="utf-8"))
import os as _os
VEGM = json.load(open(os.path.join(TOWN, "valentine_veglod_meshes.json"), encoding="utf-8")) if _os.path.exists(os.path.join(TOWN, "valentine_veglod_meshes.json")) else {}
VEGT = json.load(open(os.path.join(TOWN, "valentine_veg_meshes.json"), encoding="utf-8")) if _os.path.exists(os.path.join(TOWN, "valentine_veg_meshes.json")) else {}
VEGI = json.load(open(os.path.join(TOWN, "valentine_veg_instances.json"), encoding="utf-8")) if _os.path.exists(os.path.join(TOWN, "valentine_veg_instances.json")) else []
ARAL = json.load(open(os.path.join(TOWN, "terrain_instances.json"), encoding="utf-8"))
ARAL = ARAL + [[e[0], e[1], e[2], e[3], 0.0, 0.0, 0.0, 1.0, 1.0, 1.0] for e in VEGI]



# ---- 逻辑体过滤：这些 archetype 在游戏里不渲染（室内 milo 体积 / 贴花 / 音频 / 遮挡 / 阴影代理）----
def _joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xffffffff
        h = (h + (h << 10)) & 0xffffffff
        h ^= (h >> 6)
    h = (h + (h << 3)) & 0xffffffff
    h ^= (h >> 11)
    h = (h + (h << 15)) & 0xffffffff
    return h

_LOGIC_PAT = ('_int', 'milo', 'audio', 'vfx', '_dcl', 'decal', '_shad', 'slod', '_lod',
              'lights_holder', 'props_debris', '_em0', '_em_', 'prox', 'helper', 'proxy',
              'occlu', 'nav', 'cover', 'path', 'anchor', 'spawn', 'volume',
              '_dec', '_veg', 'cloth', 'hay', 'banner', 'lockdown', 'debris', '_rope')
_covered = set(int(x) for x in MESH) | set(int(x) for x in LODM) | set(int(x) for x in PROPM) |            set(int(x) for x in VEGT) | set(int(x) for x in TERRM) | set(int(x) for x in VEGM)
_name_by_hash = {}
for _f in (os.path.join(ROOT, "tools/rdr2rpf/src/names.txt"),):
    if os.path.exists(_f):
        for _ln in open(_f, encoding="utf-8", errors="ignore"):
            _s = _ln.strip()
            if _s:
                _name_by_hash[_joaat(_s)] = _s
LOGIC = set()
for _e in E:
    if _e[0] in _covered:
        continue
    _nm = _name_by_hash.get(_e[0], '')
    if (not _nm) or any(t in _nm for t in _LOGIC_PAT):
        LOGIC.add(_e[0])
print(f"逻辑体(不画盒子): {len(LOGIC)} / 未覆盖 {len([e for e in E if e[0] not in _covered])}")

arch = {str(k): v for k, v in A.items() if any(str(k) == str(e[0]) for e in E)}

# ---- 地形 z 校准 ----------------------------------------------------------
# heightmap.dat 的绝对基准与 ymap 实体 z 不一致（实测 dz≈128，见 README §3.5 备注）。
# 这里用"本镇建筑实体的 z"反推一个常量偏移，使地形与城镇自洽（局部校准）。
import statistics
_hm = open(HM, "rb").read()
_sx, _sy = struct.unpack_from('<HH', _hm, 0x0C)
_mnx, _mny, _mnz, _mxx, _mxy, _mxz = struct.unpack_from('<6f', _hm, 0x10)
_off = len(_hm) - _sx * _sy * 2
_raw = np.frombuffer(_hm[_off:_off + _sx * _sy * 2], dtype='<u2').reshape(_sy, _sx)
_dz = []
for e in E:
    if str(e[0]) not in MESH:
        continue
    c = int((e[1] - _mnx) / (_mxx - _mnx) * (_sx - 1))
    r = int((e[2] - _mny) / (_mxy - _mny) * (_sy - 1))
    if 0 <= c < _sx and 0 <= r < _sy:
        zn = _raw[r, c] / 65535.0 * (_mxz - _mnz) + _mnz
        _dz.append(e[3] - zn)
TERR_OFF = round(statistics.median(_dz), 2) if _dz else 0.0
print("terrain z-offset (local calibration):", TERR_OFF, "n=", len(_dz))

# ---- terrain (512 subsample)
d = open(HM, "rb").read()
sx, sy = struct.unpack_from('<HH', d, 0x0C)
mnx, mny, mnz, mxx, mxy, mxz = struct.unpack_from('<6f', d, 0x10)
off = len(d) - sx * sy * 2
h = np.frombuffer(d[off:off + sx * sy * 2], dtype='<u2').reshape(sy, sx)
N = 512
step = sx // N
ds = h[::step, ::step][:N, :N].astype('<u2')
terr_b64 = base64.b64encode(ds.tobytes()).decode()
terr_meta = {"N": N, "x0": mnx, "y0": mny, "x1": mxx, "y1": mxy, "zmin": mnz, "zmax": mxz, "off": TERR_OFF}

# ---- pack real meshes: int16-quantized positions + uint16 indices (base64)
def pack_set(src, lod_flag):
    out = {}
    for hh, m in src.items():
        P = np.array(m["p"], dtype=np.float64).reshape(-1, 3)
        mn = P.min(axis=0); mx = P.max(axis=0)
        span = np.where(mx - mn < 1e-6, 1.0, mx - mn)
        q = np.clip(np.round((P - mn) / span * 65535.0).astype(np.int32) - 32768, -32768, 32767).astype('<i2')
        vc = int(P.shape[0]); idt = '<u2' if vc <= 65535 else '<u4'
        idx = np.array(m["i"], dtype=idt)
        e = {"n": m.get("name", ""), "vc": vc, "tc": int(len(idx) // 3),
             "u32": 1 if vc > 65535 else 0, "lod": lod_flag,
             "mn": [round(float(v), 4) for v in mn], "sp": [round(float(v), 6) for v in span],
             "p": base64.b64encode(q.tobytes()).decode(),
             "i": base64.b64encode(idx.tobytes()).decode()}
        # ★ 关键：保留**逐几何体材质分组**与贴图名（T5），否则前端拿不到材质信息
        if m.get("grp"):
            e["grp"] = m["grp"]
        if m.get("texs"):
            e["texs"] = m["texs"]
        out[hh] = e
    return out
packed = pack_set(MESH, 0)
packed.update(pack_set(LODM, 1))
packed.update(pack_set(TERRM, 2))
packed.update(pack_set(PROPM, 3))
packed.update(pack_set(VEGM, 2))
packed.update(pack_set(VEGT, 2))
print("packed HD", len(MESH), "+ LOD", len(LODM), "+ props", len(PROPM), "+ terrain", len(TERRM), "+ veglod", len(VEGM), "+ trees", len(VEGT))
print("packed", len(packed), "models")

html = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>RDR2 · Valentine 瓦伦丁（地形 + 真实建筑网格）</title>
<style>
 body{margin:0;background:#0a0d12;color:#dfe6ee;font-family:"Microsoft YaHei",system-ui,sans-serif;overflow:hidden}
 #hud{position:fixed;left:12px;top:10px;font-size:13px;background:#0f1318dd;padding:9px 13px;border-radius:8px;line-height:1.8;pointer-events:none}
 #hud b{color:#6ec1ff}
 #bar{position:fixed;right:12px;top:10px;font-size:12px;background:#0f1318dd;padding:8px 12px;border-radius:8px}
 button{background:#243040;color:#cfe3ff;border:1px solid #3a4757;border-radius:6px;padding:4px 9px;cursor:pointer;font-size:12px;margin:2px}
 button.on{background:#3d6ea5}
 #err{position:fixed;left:12px;bottom:12px;color:#ff8d8d;font-size:12px}
</style></head><body>
<div id="hud">RDR2 <b>Valentine 瓦伦丁</b> · 地形 + 真实建筑网格（.ydr 几何已解码）<br>
 高清建筑 <b id="nm"></b> · LOD 建筑 <b id="nl"></b> · 道具 <b id="npr"></b> · 树木 <b id="nvg"></b> 种<br>
 覆盖实体 <b id="ne"></b> / __NTOT__ (<b id="npct"></b>%) · 三角面 <b id="nt"></b> · 原生贴图 <b id="ntex">0/0</b> · 材质组 <b id="nmat">0</b><br>
 地面：游戏地块 LOD（heightmap 基准与 .ymap 不符，已改用它）<br>
 左键=旋转 · 滚轮=缩放 · 右键=平移</div>
<div id="bar">
 <button id="bTer">地形(heightmap)</button>
 <button id="bTL" class="on">地形(游戏LOD)</button>
 <button id="bTex">材质(box map)</button>
 <button id="bBase">基准地面</button>
 <button id="bReal" class="on">真房子</button>
 <button id="bBox" class="on">灰盒(其余)</button>
 <button id="bDbg">变换调试(轴/包围盒)</button>
 <button id="bFly">自动巡航</button>
</div>
<div id="err"></div>
<script id="three-src" type="text/plain">__THREE__</script>
<script>
window.__E=__ENTS__; window.__A=__ARCH__; window.__T="__TERR__"; window.__TM=__TM__; window.__M=__MESH__; window.__AL=__ARAL__; window.__LG=__LOGIC__; window.__WOOD="__WOOD__"; window.__BTEX=__BTEX__;
</script>
<script type="module">
try{
 const url=URL.createObjectURL(new Blob([document.getElementById('three-src').textContent],{type:'text/javascript'}));
 const THREE=await import(url);
 const E=window.__E, A=window.__A, TM=window.__TM, M=window.__M;
 function b64(s){const b=atob(s);const u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return u;}
 // ---- T5 贴图缓存（地形与建筑共用，必须最先建）----
 const texCache={}; let defTex=null;
 const texReady={n:0, tot:0}; window.__texReady=texReady;
 const _texLoads=[];
 (function(){
   const T=window.__BTEX||{tex:{}};
   texReady.tot=Object.keys(T.tex).length;
   for(const key in T.tex){
     const e=T.tex[key];
     const img=new Image();
     const tex=new THREE.Texture(img);
     tex.wrapS=tex.wrapT=THREE.RepeatWrapping;
     tex.colorSpace=THREE.SRGBColorSpace;
     tex.anisotropy=4;
     _texLoads.push(new Promise(res=>{
       img.onload=()=>{ tex.needsUpdate=true; texReady.n++; updTexHud(); res(true); };
       img.onerror=()=>{ res(false); };
     }));
     img.src="data:image/png;base64,"+e.b64;
     texCache[key]=tex;
     if(!defTex) defTex=tex;
   }
   // 全局兜底不要用地形草皮：优先灰泥/石面，最后才用第一个
   defTex = texCache['nbx_dirt_layers_plaster03'] || texCache['nbx_dirt_stone_grime_02_ab'] || defTex;
 })();
 function gtex(n){ return texCache[n]||defTex; }
 function updTexHud(){ const el=document.getElementById('ntex'); if(el) el.textContent=texReady.n+'/'+texReady.tot; }
 // terrain height field
 const bin=b64(window.__T); const H=new Float32Array(TM.N*TM.N); const dv=new DataView(bin.buffer);
 for(let i=0;i<TM.N*TM.N;i++) H[i]=dv.getUint16(i*2,true)/65535*(TM.zmax-TM.zmin)+TM.zmin + TM.off;
 // town center
 let cx=0,cy=0; for(const e of E){cx+=e[1];cy+=e[2];} cx/=E.length; cy/=E.length;
 let minZ=1e9; for(const e of E) if(e[3]<minZ)minZ=e[3];
 const sizeX=TM.x1-TM.x0, sizeY=TM.y1-TM.y0, S=TM.N;
 const renderer=new THREE.WebGLRenderer({antialias:true});
 renderer.setSize(innerWidth,innerHeight); document.body.appendChild(renderer.domElement);
 const scene=new THREE.Scene(); scene.background=new THREE.Color(0x3d5068);
 scene.fog=new THREE.Fog(0x3d5068, 500, 3400);
 const cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,0.5,60000);
 scene.add(new THREE.HemisphereLight(0xffffff,0x2a3340,1.5));
 const sun=new THREE.DirectionalLight(0xffffff,1.5); sun.position.set(-0.5,1,0.35); scene.add(sun);
 // ---- terrain
 const tgeo=new THREE.BufferGeometry(); const vt=new Float32Array(S*S*3), ct=new Float32Array(S*S*3);
 for(let r=0;r<S;r++)for(let c=0;c<S;c++){const i=r*S+c,hv=H[i];
   vt[i*3]=(TM.x0+(c/(S-1))*sizeX)-cx; vt[i*3+1]=hv; vt[i*3+2]=(TM.y0+(r/(S-1))*sizeY)-cy;
   const t=Math.max(0,Math.min(1,(hv-TM.zmin)/(TM.zmax-TM.zmin)));
   // 贴图打底，顶点色只做轻微明暗/色调变化（高处偏灰、低处偏绿）
   const b=0.80+0.40*t;
   const cc=[b*(1.05-0.16*t), b, b*(0.94+0.08*t)];
   ct[i*3]=cc[0];ct[i*3+1]=cc[1];ct[i*3+2]=cc[2];}
 const it=[]; const uvT=new Float32Array(S*S*2); const TS=6.0;   // 6 米/瓦
 for(let r=0;r<S;r++)for(let c=0;c<S;c++){const i=r*S+c;
   uvT[i*2]=(c/(S-1))*sizeX/TS; uvT[i*2+1]=(r/(S-1))*sizeY/TS;}
 for(let r=0;r<S-1;r++)for(let c=0;c<S-1;c++){const a=r*S+c,b=r*S+c+1,d2=(r+1)*S+c,e2=(r+1)*S+c+1;it.push(a,d2,b,b,d2,e2);}
 tgeo.setAttribute('position',new THREE.BufferAttribute(vt,3)); tgeo.setAttribute('color',new THREE.BufferAttribute(ct,3));
 tgeo.setAttribute('uv', new THREE.BufferAttribute(uvT,2));
 tgeo.setIndex(it); tgeo.computeVertexNormals();
 const terrain=new THREE.Mesh(tgeo,new THREE.MeshLambertMaterial({vertexColors:true, map:gtex('hea_grass_lush_01_abte'), side:THREE.DoubleSide}));
 terrain.visible=false; scene.add(terrain);

 // ---------- REAL building meshes ----------
 // axis mapping: three = (x, z, -y)
 const mgeo={};
 for(const hh in M){ const m=M[hh];
   const q=new Int16Array(b64(m.p).buffer);
   const ix=m.u32?new Uint32Array(b64(m.i).buffer):new Uint16Array(b64(m.i).buffer);
   const pos=new Float32Array(q.length), nor=new Float32Array(q.length);
   for(let i=0;i<q.length;i+=3){
     const x=m.mn[0]+(q[i]+32768)/65535*m.sp[0];
     const y=m.mn[1]+(q[i+1]+32768)/65535*m.sp[1];
     const z=m.mn[2]+(q[i+2]+32768)/65535*m.sp[2];
     pos[i]=x; pos[i+1]=z; pos[i+2]=-y;             // M * (x,y,z)
   }
   const gg=new THREE.BufferGeometry();
   gg.setAttribute('position',new THREE.BufferAttribute(pos,3));
   gg.setIndex(new THREE.BufferAttribute(new Uint32Array(ix),1));
   gg.computeVertexNormals();
   mgeo[hh]=gg;
 }
 // group entities by archetype，并按 lod 分两组（0=高清 .ydr，1=LOD .ydd）
 const byArch={}; const byArchL={}; const byArchP={};
 for(const e of E){ const k=String(e[0]);
   if(mgeo[k]){ const t=M[k].lod; const G = t===1?byArchL : t===3?byArchP : byArch;
     G[k]=G[k]||[]; G[k].push(e); } }
 const realGroup=new THREE.Group(); scene.add(realGroup);
 const realMat=new THREE.MeshLambertMaterial({color:0xc9b48c,side:THREE.DoubleSide});
 const lodMat=new THREE.MeshLambertMaterial({color:0x8d8378,side:THREE.DoubleSide});
 const propMat=new THREE.MeshLambertMaterial({color:0xa8926e,side:THREE.DoubleSide});
 // ---------- 材质：盒式 UV（box mapping，按法线主轴投影）----------
 // RDR2 场景资产顶点里没有 UV（实测），改用 box mapping 现算 UV。
 const boxRuns = [];
 function makeBoxUV(geo, S){
   geo.computeVertexNormals();
   const p = geo.attributes.position.array, n = geo.attributes.normal.array;
   const uv = new Float32Array((p.length/3)*2);
   for(let i=0, k=0; i<p.length; i+=3, k+=2){
     const ax=Math.abs(n[i]), ay=Math.abs(n[i+1]), az=Math.abs(n[i+2]);
     let u,v;
     if(ax>=ay && ax>=az){ u=p[i+2]; v=p[i+1]; }
     else if(ay>=az){ u=p[i]; v=p[i+2]; }
     else { u=p[i]; v=p[i+1]; }
     uv[k]=u*S; uv[k+1]=v*S;
   }
   geo.setAttribute('uv', new THREE.BufferAttribute(uv,2));
 }
 // ---- T5: 游戏原生贴图（每栋建筑用自己的 albedo，box mapping 投影）----
 const matGroup=new THREE.Group(); scene.add(matGroup);
 let matReady=false;
 function buildRealTex(){
   let _ng=0, _nmat=0, _ninst=0;
   for(const k in byArch){
     const g=mgeo[k];
     if(!g.attributes.uv) makeBoxUV(g, 0.42);   // 真实贴图：约 0.42 m / UV 单位
     const M0=M[k]||{};
     const grp=M0.grp;
     // 该楼自己的主贴图：grp 里出现最多的那个（用于空材质组兜底，避免串到别的楼/地形贴图）
     let bdef=defTex;
     if(grp && grp.length){
       const cnt={}; let bn=null, bc=0;
       for(const it of grp){ const t=it[0]; if(t){ cnt[t]=(cnt[t]||0)+1; if(cnt[t]>bc){bc=cnt[t];bn=t;} } }
       if(bn && texCache[bn]) bdef=texCache[bn];
     }
     let mats;
     if(grp && grp.length){
       // 逐几何体多材质（geometry groups + material array）
       mats=[];
       for(let i=0;i<grp.length;i++){
         const tname=grp[i][0];
         const tex=texCache[tname]||bdef;
         if(!tex) continue;
         const gi=mats.length;
         g.addGroup(grp[i][1], grp[i][2], gi);
         mats.push(new THREE.MeshLambertMaterial({map:tex, side:THREE.DoubleSide}));
       }
       if(!mats.length) continue;
     } else {
       if(!bdef) continue;
       mats=new THREE.MeshLambertMaterial({map:bdef, side:THREE.DoubleSide});
     }
     _ng++; _nmat += (mats.length||1); _ninst += byArch[k].length;
     for(const e of byArch[k]){
       const [arch,x,y,z,qx,qy,qz,qw,sxy,sz]=e;
       const mesh=new THREE.Mesh(g,mats);
       mesh.position.set(x-cx, z, -(y-cy));
       mesh.quaternion.copy(mapQuat(qx,qy,qz,qw));
       mesh.scale.set(sxy||1, sz||1, sxy||1);
       matGroup.add(mesh);
     }
   }
   matGroup.visible=true; realGroup.visible=false;
   matReady=true;
   document.getElementById('bTex').classList.add('on');
   if(typeof LODgroup!=='undefined') LODgroup.visible=false;
   const _el=document.getElementById('nmat');
   if(_el) _el.textContent = _ng + '栋/' + _nmat + '材质/实例' + _ninst;
   console.log('[T5] archetypes='+_ng+' materials='+_nmat+' instances='+_ninst);
 }
 // 等**全部原生贴图解码完成**再建材质（否则会渲染成白板/串图）；
 // 同时延迟到全部 const 声明之后（mapQuat 依赖后声明的 Q/M4）
 Promise.all(_texLoads).then(()=>{ try{ buildRealTex(); }catch(e){ console.error(e); } });
 document.getElementById('bTex').onclick=e=>{
   const on=!matGroup.visible;
   matGroup.visible=on; realGroup.visible=!on;
   document.getElementById('bReal').classList.toggle('on',!on);
   e.target.classList.toggle('on',on);
 };
 let nRealEnt=0,nTri=0;
 const M4=new THREE.Matrix4(),Q=new THREE.Quaternion(),QT=new THREE.Quaternion(),V=new THREE.Vector3(),SC=new THREE.Vector3();
 const MR=new THREE.Matrix4().set(1,0,0,0, 0,0,1,0, 0,-1,0,0, 0,0,0,1);   // maps rdr -> three
 const MRT=MR.clone().transpose();
 function mapQuat(qx,qy,qz,qw){ // R_three = MR * R_rdr * MR^T
   const R=new THREE.Matrix4().makeRotationFromQuaternion(Q.set(qx,qy,qz,qw));
   const R2=MR.clone().multiply(R).multiply(MRT);
   QT.setFromRotationMatrix(R2);
   return QT;
 }
 // ---------- 游戏自带地形 LOD（area_slod4）作为真实地面 ----------
 const TG=new THREE.Group(); scene.add(TG);
 {
   const byT={};
   for(const e of window.__AL){ const k=String(e[0]); if(mgeo[k]){ (byT[k]=byT[k]||[]).push(e); } }
   const tMat=new THREE.MeshLambertMaterial({map:gtex('hea_grass_lush_01_abte'),color:0xbfbfbf,side:THREE.DoubleSide});
   for(const k in byT){
     const list=byT[k];
     if(!mgeo[k].attributes.uv) makeBoxUV(mgeo[k], 8.0);   // 地形瓦片：8 米/瓦
     const im=new THREE.InstancedMesh(mgeo[k],tMat,list.length);
     list.forEach((e,j)=>{
       const [arch,x,y,z,qx,qy,qz,qw,sxy,sz]=e;
       V.set(x-cx, z, -(y-cy)); const qq=mapQuat(qx,qy,qz,qw);
       SC.set(sxy||1, sz||1, sxy||1);
       M4.compose(V,qq,SC); im.setMatrixAt(j,M4);
     });
     im.instanceMatrix.needsUpdate=true; TG.add(im);
   }
 }
 document.getElementById('bTL').onclick=e=>{TG.visible=!TG.visible;e.target.classList.toggle('on',TG.visible);};
 // ---------- 基准地面：填住 LOD 覆盖不到的空洞（高度取小镇实体地面的中位数）----------
 {
   const gz = (function(){ const a=E.map(e=>e[3]).sort((x,y)=>x-y); return a[Math.floor(a.length*0.35)]-0.5; })();
   const base=new THREE.Mesh(new THREE.PlaneGeometry(9000,9000,1,1),
      new THREE.MeshLambertMaterial({color:0x4b5a3c}));
   base.rotation.x=-Math.PI/2; base.position.set(0, gz-6, 0); base.name='BASE'; base.visible=false;
   scene.add(base);
   document.getElementById('bBase').onclick=e=>{base.visible=!base.visible;e.target.classList.toggle('on',base.visible);};
 }


 for(const [grp,mat] of [[byArch,realMat],[byArchL,lodMat],[byArchP,propMat]]){
  for(const k in grp){
   const list=grp[k];
   const im=new THREE.InstancedMesh(mgeo[k],mat,list.length);
   list.forEach((e,j)=>{
     const [arch,x,y,z,qx,qy,qz,qw,sxy,sz]=e;
     V.set(x-cx, z, -(y-cy));
     const qq=mapQuat(qx,qy,qz,qw);
     SC.set(sxy||1, sz||1, sxy||1);
     M4.compose(V,qq,SC); im.setMatrixAt(j,M4);
     nRealEnt++;
   });
   im.instanceMatrix.needsUpdate=true;
   realGroup.add(im);
   nTri += (mgeo[k].index.count/3)*list.length;
  }
 }
 document.getElementById('nm').textContent=__MESHN__;
 document.getElementById('nl').textContent=__LODN__;
 document.getElementById('npr').textContent=__PROPN__;
 document.getElementById('nvg').textContent=__VEGN__ + '(+' + __VEGINST__ + '棵)';
 document.getElementById('npct').textContent=(100*nRealEnt/E.length).toFixed(0);
 document.getElementById('ne').textContent=nRealEnt;
 document.getElementById('nt').textContent=nTri.toLocaleString();

 // ---------- 变换调试：世界坐标轴 + 每个真实建筑的世界包围盒 ----------
 const dbg=new THREE.Group(); dbg.visible=false; scene.add(dbg);
 const ax=new THREE.AxesHelper(40); ax.position.set(-cx, minZ+6, -(-cy)); dbg.add(ax);  // X红 Y绿 Z蓝
 const _v=new THREE.Vector3();
 for(const k in byArch){
   for(const e of byArch[k]){
     const [arch,x,y,z,qx,qy,qz,qw,sxy,sz]=e;
     const g=mgeo[k]; g.computeBoundingBox(); const lb=g.boundingBox;
     // 把局部盒 8 角变换到世界，重建 Box3（Box3Helper 会在每帧覆盖 position/scale）
     const qq=mapQuat(qx,qy,qz,qw); const V0=new THREE.Vector3(x-cx, z, -(y-cy));
     const wb=new THREE.Box3();
     for(let i=0;i<8;i++){
       _v.set(i&1?lb.max.x:lb.min.x, i&2?lb.max.y:lb.min.y, i&4?lb.max.z:lb.min.z);
       _v.multiply(new THREE.Vector3(sxy||1, sz||1, sxy||1)).applyQuaternion(qq).add(V0);
       wb.expandByPoint(_v);
     }
     dbg.add(new THREE.Box3Helper(wb,0x00ff88));
   }
 }
 document.getElementById('bDbg').onclick=e=>{dbg.visible=!dbg.visible;e.target.classList.toggle('on',dbg.visible);};

 // ---------- gray boxes for remaining entities ----------
 const boxGeo=new THREE.BoxGeometry(1,1,1);
 const LG=new Set(window.__LG||[]);
 const rest=E.filter(e=>!mgeo[String(e[0])] && !LG.has(e[0]));
 const inst=new THREE.InstancedMesh(boxGeo,new THREE.MeshLambertMaterial({transparent:true,opacity:0.35,depthWrite:false}),rest.length);
 const c3=new THREE.Color();
 rest.forEach((e,i)=>{ const [arch,x,y,z,qx,qy,qz,qw,sxy,sz]=e;
   let dx=2.5,dy=2.5,dz=2.5; const b=A[String(arch)];
   if(b){const bx=Math.abs(b[3]-b[0]),by=Math.abs(b[4]-b[1]),bz=Math.abs(b[5]-b[2]);
     if(Math.max(bx,by,bz)<=40&&bz>=0.8){dx=Math.max(0.6,bx);dy=Math.max(0.6,by);dz=Math.max(0.8,bz);}}
   V.set(x-cx, z+dz/2, -(y-cy)); const qq=mapQuat(qx,qy,qz,qw); SC.set(dx,dz,dy);
   M4.compose(V,qq,SC); inst.setMatrixAt(i,M4);
   const m=Math.max(dx,dy,dz);
   if(m>25)c3.set(0.56,0.72,1.0); else if(m>8)c3.set(0.91,0.75,0.48); else if(m>3)c3.set(0.50,0.84,0.66); else c3.set(0.91,0.54,0.60);
   inst.setColorAt(i,c3);
 });
 inst.instanceMatrix.needsUpdate=true; if(inst.instanceColor)inst.instanceColor.needsUpdate=true;
 scene.add(inst);

 document.getElementById('bTer').onclick=e=>{terrain.visible=!terrain.visible;e.target.classList.toggle('on',terrain.visible);};
 document.getElementById('bReal').onclick=e=>{realGroup.visible=!realGroup.visible;e.target.classList.toggle('on',realGroup.visible);};
 document.getElementById('bBox').onclick=e=>{inst.visible=!inst.visible;e.target.classList.toggle('on',inst.visible);};
 let yaw=0.95,pitch=0.52,dist=190,panX=0,panY=0,fly=false,ft=0;
 // URL 参数: ?yaw=&pitch=&dist=&px=&py=&real=0&box=0&ter=0&fly=1
 const QP=new URLSearchParams(location.search.replace(/^\?/,'')+ '&' + location.hash.replace(/^#/,''));
 if(QP.has('yaw'))yaw=+QP.get('yaw'); if(QP.has('pitch'))pitch=+QP.get('pitch');
 if(QP.has('dist'))dist=+QP.get('dist'); if(QP.has('px'))panX=+QP.get('px'); if(QP.has('py'))panY=+QP.get('py');
 if(QP.get('ter')==='0'){terrain.visible=false;document.getElementById('bTer').classList.remove('on');}
 if(QP.get('real')==='0'){realGroup.visible=false;document.getElementById('bReal').classList.remove('on');}
 if(QP.get('box')==='0'){inst.visible=false;document.getElementById('bBox').classList.remove('on');}
 if(QP.get('fly')==='1'){fly=true;document.getElementById('bFly').classList.add('on');}
 if(QP.get('dbg')==='1'){dbg.visible=true;document.getElementById('bDbg').classList.add('on');}
 function upd(){ const ex=Math.cos(yaw)*Math.cos(pitch)*dist+panX, ey=Math.sin(pitch)*dist+(minZ+8)+panY, ez=Math.sin(yaw)*Math.cos(pitch)*dist;
   cam.position.set(ex,ey,ez); cam.lookAt(panX,minZ+8+panY,0); }
 upd();
 document.getElementById('bFly').onclick=e=>{fly=!fly;e.target.classList.toggle('on',fly);};
 let drag=0,lx=0,ly=0;
 renderer.domElement.addEventListener('mousedown',ev=>{drag=ev.button===2?2:1;lx=ev.clientX;ly=ev.clientY;});
 addEventListener('mouseup',()=>drag=0); addEventListener('contextmenu',e=>e.preventDefault());
 addEventListener('mousemove',ev=>{ if(!drag)return; const dx=ev.clientX-lx,dy=ev.clientY-ly; lx=ev.clientX; ly=ev.clientY;
   if(drag===1){yaw-=dx*0.005; pitch=Math.max(-0.2,Math.min(1.45,pitch+dy*0.005));} else {panX-=dx*dist*0.001; panY+=dy*dist*0.001;} upd(); });
 renderer.domElement.addEventListener('wheel',ev=>{ev.preventDefault(); dist*=(1+Math.sign(ev.deltaY)*0.1); dist=Math.max(3,Math.min(4000,dist)); upd();},{passive:false});
 addEventListener('resize',()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);});
 (function loop(){ if(fly){ ft+=0.004; yaw+=0.0025; dist=110+40*Math.sin(ft*0.7); upd(); }
   requestAnimationFrame(loop); renderer.render(scene,cam); })();
 window.__ready=true;
}catch(err){document.getElementById('err').textContent='ERR: '+err.message; console.error(err);}
</script></body></html>"""

html = (html.replace("__MESHN__", str(len(MESH))).replace("__LODN__", str(len(LODM))).replace("__PROPN__", str(len(PROPM))).replace("__VEGN__", str(len(VEGT))).replace("__VEGINST__", str(len(VEGI)))
            .replace("__NTOT__", str(len(E)))
            .replace("__THREE__", three)
            .replace("__ENTS__", json.dumps(E, separators=(',', ':')))
            .replace("__ARCH__", json.dumps(arch, separators=(',', ':')))
            .replace("__TERR__", terr_b64)
            .replace("__TM__", json.dumps(terr_meta))
            .replace("__MESH__", json.dumps(packed, separators=(',', ':')))
            .replace("__ARAL__", json.dumps(ARAL, separators=(',', ':')))
            .replace("__LOGIC__", json.dumps(sorted(LOGIC), separators=(',', ':')))
            .replace("__WOOD__", WOOD_B64)
            .replace("__BTEX__", json.dumps(BTEX, separators=(',', ':'))))
out = os.path.join(TOWN, "valentine_real.html")
open(out, "w", encoding="utf-8").write(html)
print("wrote", out, round(os.path.getsize(out) / 1024 / 1024, 2), "MB")
