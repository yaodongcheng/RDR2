"""生成"高度图 ↔ 官方地图"的直观重叠对比（不用 PS 自己叠图层）。

产物（deliverable/map_check/）
    map_crop.png              官方地图，裁到地图框，统一尺寸
    height_gray.png           我方高度图（灰度），同尺寸
    overlay_50.png            两张 50/50 直接混合
    overlay_relief.png        官方地图 + 我方山影（叠加），看地形骨相
    slider.html               左右拖动滑块的对比页（双击即可看）
"""
import os
import json

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ROOT = r'D:/BrainMaker/大镖客2解包分析'
OUT = os.path.join(ROOT, 'deliverable/map_check')
HM = os.path.join(ROOT, 'deliverable/heightmap/continent_height_4m.png')
META = os.path.join(ROOT, 'deliverable/heightmap/continent_height_meta.json')
MAP = os.path.join(ROOT, '地图下载/大陆地图_缩略.jpg')
BOX = (146, 388, 4804, 3851)          # 5000 宽缩略图上的地图内容框
W = 2400                               # 输出宽


def main():
    os.makedirs(OUT, exist_ok=True)
    meta = json.load(open(META, encoding='utf-8'))
    zmin, zmax = meta['heightmap']['zmin'], meta['heightmap']['zmax']

    # 官方地图裁到内容框
    mp = Image.open(MAP).convert('RGB')
    k = mp.size[0] / 5000.0
    crop = mp.crop(tuple(int(round(v * k)) for v in BOX))
    H = int(round(crop.size[1] * W / crop.size[0]))
    map_img = crop.resize((W, H), Image.LANCZOS)

    # 高度图 → 同一尺寸（行 0 = 北）
    q = np.asarray(Image.open(HM).resize((W, H), Image.LANCZOS)).astype(np.float32)
    z = zmin + q / 65535.0 * (zmax - zmin)
    g = ((z - z.min()) / (z.max() - z.min()) * 255).astype(np.uint8)
    hm_img = Image.fromarray(np.dstack([g, g, g]))

    map_img.save(os.path.join(OUT, 'map_crop.png'))
    hm_img.save(os.path.join(OUT, 'height_gray.png'))

    # 上色版（水=蓝、低地=土黄），给人看更直观
    try:
        col = Image.open(os.path.join(ROOT, 'deliverable/heightmap/continent_height_preview.png')).convert('RGB')
        hm_color = col.resize((W, H), Image.LANCZOS)
        hm_color.save(os.path.join(OUT, 'height_color.png'))
    except Exception as e:
        print('上色版缺失', e)
        hm_color = hm_img

    # 50/50 混合
    blend = Image.blend(map_img, hm_img, 0.5)
    blend.save(os.path.join(OUT, 'overlay_50.png'))

    # 山影叠在地图上（正片叠底），地形骨相一眼可见
    gy, gx = np.gradient(z, 4.0)
    slope = np.arctan(np.hypot(gx, gy)); aspect = np.arctan2(-gx, gy)
    hs = np.clip(np.sin(np.radians(45)) * np.cos(slope) +
                 np.cos(np.radians(45)) * np.sin(slope) * np.cos(np.radians(315) - aspect), 0, 1)
    shade = (0.45 + 0.75 * hs)[..., None]
    base = np.asarray(map_img).astype(np.float32) / 255.0
    relief = (base * shade).clip(0, 1)
    Image.fromarray((relief * 255).astype(np.uint8)).save(os.path.join(OUT, 'overlay_relief.png'))

    # 拖拽对比页
    html = """<!doctype html><html><head><meta charset="utf-8"><title>高度图 vs 官方地图</title>
<style>
body{margin:0;background:#111;color:#ddd;font-family:system-ui,Segoe UI,Microsoft YaHei}
.bar{padding:10px 14px;font-size:14px;background:#1b1b1b;border-bottom:1px solid #333}
.wrap{position:relative;max-width:1500px;margin:14px auto;user-select:none;cursor:ew-resize}
.wrap img{display:block;width:100%}
.over{position:absolute;inset:0;clip-path:inset(0 0 0 50%)}
.over img{width:100%;height:100%;object-fit:cover}
.line{position:absolute;top:0;bottom:0;width:2px;background:#ff3b3b;left:50%}
.line:after{content:'◀ ▶';position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
 background:#ff3b3b;color:#fff;font-size:12px;padding:3px 7px;border-radius:10px;white-space:nowrap}
.tip{max-width:1500px;margin:8px auto 24px;color:#9aa;font-size:13px;line-height:1.7}
</style></head><body>
<div class="bar">拖动鼠标左右划：<b>左＝官方地图</b> ／ <b>右＝我方高度图（上色：蓝=水，土黄/绿=陆）</b></div>
<div class="wrap" id="w">
  <img src="map_crop.png">
  <div class="over" id="ov"><img src="height_color.png"></div>
  <div class="line" id="ln"></div>
</div>
<div class="tip">
同坐标系、同尺寸（2400 px 宽）。<br>
另外两张静态图：<b>overlay_50.png</b>（两图各 50% 混合）、<b>overlay_relief.png</b>（我方山影叠在地图上，最容易看出地形骨相对不对）。<br>高度图是线性灰度，<b>低于 0 米的干地（新奥斯汀盆地）在灰度图里会显得很暗</b>，那是陆地不是水；看上色版最准。
</div>
<script>
const w=document.getElementById('w'),ov=document.getElementById('ov'),ln=document.getElementById('ln');
function set(x){const r=w.getBoundingClientRect();
 x=Math.min(Math.max(x,0),r.width);
 ln.style.left=(x/r.width*100)+'%';
 ov.style.clipPath='inset(0 0 0 '+(x/r.width*100)+'%)';}
let drag=false;
w.addEventListener('mousedown',e=>{drag=true;set(e.clientX-w.getBoundingClientRect().left);});
w.addEventListener('mousemove',e=>{if(drag)set(e.clientX-w.getBoundingClientRect().left);});
window.addEventListener('mouseup',()=>drag=false);
w.addEventListener('touchstart',e=>{drag=true;set(e.touches[0].clientX-w.getBoundingClientRect().left);},{passive:true});
w.addEventListener('touchmove',e=>{if(drag)set(e.touches[0].clientX-w.getBoundingClientRect().left);},{passive:true});
window.addEventListener('touchend',()=>drag=false);
</script></body></html>"""
    open(os.path.join(OUT, 'slider.html'), 'w', encoding='utf-8').write(html)
    print('→', OUT)
    print('   map_crop.png  height_gray.png  overlay_50.png  overlay_relief.png  slider.html')


if __name__ == '__main__':
    main()
