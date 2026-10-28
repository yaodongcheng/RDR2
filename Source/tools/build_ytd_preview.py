"""Build a self-contained WebGL2 page that decodes RDR2 .ytd textures (BC7/BPTC) for visual check.

Why: RDR2 的 .ytd 纹理是 1 字节/像素的块压缩（BC7/BPTC 一族），
PIL/Pillow 不支持 BC7（DX10 头），本机也无 texconv/Compressonator。
但 headless Chrome 的 WebGL2 有 `EXT_texture_compression_bptc`，
可用 `compressedTexImage2D` 把原始数据直接上传解码 —— 本工具即走这条路。

用法:
  python build_ytd_preview.py <t1.ytd> [t2.ytd ...] --out preview.html [--cols 3]
"""
import os, sys, json, base64, subprocess, struct

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rdr2_ytd import Ytd, mip0_bytes

TEMPLATE = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>RDR2 .ytd 纹理预览 (BC7)</title>
<style>body{margin:0;background:#101216;color:#cfd8e3;font-family:"Microsoft YaHei",monospace}
#st{padding:6px 10px;font-size:13px;background:#181d24}
.grid{display:flex;flex-wrap:wrap;gap:6px;padding:6px}
.cell{background:#000;border:1px solid #2a323d}
.cap{font-size:11px;padding:3px 5px;color:#9fb3c8;max-width:296px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
canvas{display:block;width:296px;height:296px;image-rendering:pixelated}
</style></head><body>
<div id="st">loading…</div>
<div class="grid" id="g"></div>
<script>
const TEX = __TEX__;
const st = document.getElementById('st'), g = document.getElementById('g');
const probe = document.createElement('canvas').getContext('webgl2');
const ext = probe && probe.getExtension('EXT_texture_compression_bptc');
st.textContent = 'WebGL2: ' + (probe?'OK':'NO') + ' | BPTC: ' + (ext?'YES':'NO') + ' | textures: ' + TEX.length
  + ' | fmt=' + (TEX[0]?TEX[0].fmt:'-');
function b64(s){const b=atob(s);const u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return u;}
const VS = `#version 300 es
in vec2 p; out vec2 uv;
void main(){ uv=vec2(p.x*0.5+0.5, 0.5-p.y*0.5); gl_Position=vec4(p,0.,1.); }`;
const FS = `#version 300 es
precision highp float; in vec2 uv; uniform sampler2D t; out vec4 o;
void main(){ vec4 c=texture(t,uv); o=vec4(pow(max(c.rgb,0.0),vec3(0.4545)),1.0); }`;
TEX.forEach(t=>{
  const cell=document.createElement('div'); cell.className='cell';
  const cv=document.createElement('canvas'); cv.width=296; cv.height=296;
  const cap=document.createElement('div'); cap.className='cap';
  cap.textContent = t.name+'  '+t.w+'x'+t.h+'  '+t.fmt;
  cell.appendChild(cv); cell.appendChild(cap); g.appendChild(cell);
  const gl=cv.getContext('webgl2',{preserveDrawingBuffer:true});
  const e2=gl&&gl.getExtension('EXT_texture_compression_bptc');
  if(!gl||!ext){ cap.textContent+=' [no BPTC]'; return; }
  const mk=(ty,src)=>{const s=gl.createShader(ty);gl.shaderSource(s,src);gl.compileShader(s);return s;};
  const pr=gl.createProgram(); gl.attachShader(pr,mk(gl.VERTEX_SHADER,VS)); gl.attachShader(pr,mk(gl.FRAGMENT_SHADER,FS));
  gl.linkProgram(pr); gl.useProgram(pr);
  const b=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,b);
  gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);
  const loc=gl.getAttribLocation(pr,'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc,2,gl.FLOAT,false,0,0);
  const tex=gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D,tex);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
  gl.pixelStorei(gl.UNPACK_ALIGNMENT,1);
  try{
    gl.compressedTexImage2D(gl.TEXTURE_2D,0,(e2&&e2.COMPRESSED_RGBA_BPTC_UNORM_EXT)||0x8E8C,t.w,t.h,0,b64(t.b64));
    gl.viewport(0,0,296,296); gl.clearColor(0,0,0,1); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLE_STRIP,0,4);
  }catch(e){ cap.textContent += ' ERR:'+e; }
});
window.__ready=true;
</script></body></html>"""


def build(ytd_paths, out, max_per=9):
    pack = []
    for p in ytd_paths:
        y = Ytd(open(p, 'rb').read())
        for t in y.textures():
            if len(pack) >= max_per:
                break
            n = mip0_bytes(t['w'], t['h'])
            blob = y.gfx[t['gfx_off']:t['gfx_off'] + n]
            if len(blob) < n:
                continue
            pack.append(dict(name=t['name'] or f"tex{t['idx']}", w=t['w'], h=t['h'],
                             fmt=f"{t['fmt']:#010x}", b64=base64.b64encode(blob).decode()))
    open(out, 'w', encoding='utf-8').write(TEMPLATE.replace('__TEX__', json.dumps(pack, separators=(',', ':'))))
    print("wrote", out, len(pack), "textures", round(os.path.getsize(out) / 1024 / 1024, 2), "MB")


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = args[-1] if args[-1].endswith('.html') else 'ytd_preview.html'
    ytds = [a for a in args if a.endswith('.ytd')]
    build(ytds, out, max_per=int(os.environ.get('MAXTEX', '9')))
