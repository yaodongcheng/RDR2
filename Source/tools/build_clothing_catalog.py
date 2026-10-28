# -*- coding: utf-8 -*-
"""RDR2 全服饰清单：把解包出来的每件服装/部件做成可查询的目录。

数据源（都是已解包到本地的 .ydd = DrawableDictionary，一件服饰一个文件）：
  raw/npc/models/generic    3653 件  通用 ped 部件（男女、多种款式，玩家换装用的就是这套）
  raw/npc/models/player     1458 件  亚瑟 / 约翰的专属部件
  raw/npc/models/cutscene   1442 件  剧情角色（cs_*）的专属服饰

输出：
  export/levels/world/clothing_catalog.csv     每件一行
  export/levels/world/clothing_catalog.json    含槽位统计 / 分类
  export/viewer/clothing.html                  浏览页（按槽位分组 + 搜索 + 贴图清单）

用法： uv run python tools/build_clothing_catalog.py
"""
import os
import re
import sys
import json
import csv
import glob
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rdr2_npc_export as E

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = [('generic', '通用部件'), ('player', '主角'), ('cutscene', '剧情角色')]
OUT_CSV = os.path.join(ROOT, 'export/levels/world/clothing_catalog.csv')
OUT_JSON = os.path.join(ROOT, 'export/levels/world/clothing_catalog.json')
OUT_HTML = os.path.join(ROOT, 'export/viewer/clothing.html')

# 槽位（文件名前缀）→ 中文名 / 大类
SLOT = {
    'head': ('头', '头部'), 'hair': ('头发', '头部'), 'beard': ('胡须', '头部'),
    'modular_beard': ('胡须(模块)', '头部'), 'teeth': ('牙齿', '头部'), 'eyes': ('眼睛', '头部'),
    'uppr': ('上衣', '上装'), 'shirt': ('衬衫', '上装'), 'modshirt': ('衬衫(模块)', '上装'),
    'tatteredshirt': ('破衬衫', '上装'), 'chemise': ('女式衬衣', '上装'),
    'vest': ('马甲', '上装'), 'coat': ('外套', '上装'), 'cloak': ('斗篷', '上装'),
    'combocoat': ('连体外套', '上装'), 'combovest': ('连体马甲', '上装'),
    'comboshirt': ('连体衬衫', '上装'), 'combooveralls': ('连体工装', '上装'),
    'uppertorso': ('上躯干', '躯干'), 'lowertorso': ('下躯干', '躯干'), 'torso': ('躯干', '躯干'),
    'lowr': ('下装', '下装'), 'pant': ('裤子', '下装'), 'pantcombo': ('连体裤', '下装'),
    'boot': ('靴子', '鞋履'), 'feet': ('脚部', '鞋履'), 'shoe': ('鞋', '鞋履'),
    'hand': ('手', '手部'), 'glov': ('手套', '手部'),
    'hat': ('帽子', '配饰'), 'accs': ('配饰', '配饰'), 'neckerchief': ('领巾', '配饰'),
    'tie': ('领带', '配饰'), 'scarf': ('围巾', '配饰'), 'belt': ('腰带', '配饰'),
    'ring': ('戒指', '配饰'), 'necklace': ('项链', '配饰'), 'mask': ('面罩', '配饰'),
    'arrow': ('箭袋', '配饰'), 'spurs': ('马刺', '配饰'), 'holster': ('枪套', '配饰'),
    'satchel': ('背包', '配饰'), 'badge': ('徽章', '配饰'), 'beltchain': ('链饰', '配饰'),
    'suspenders': ('背带', '配饰'), 'boutonniere': ('胸花', '配饰'), 'bibshirt': ('围兜衬衫', '上装'),
    'chain': ('怀表链', '配饰'), 'bandolier': ('弹药带', '配饰'), 'fishbag': ('鱼袋', '配饰'),
    'nude_upper': ('裸上身', '身体'), 'nude': ('裸体/身体', '身体'), 'body': ('身体', '身体'),
    'gore': ('血腥/伤口', '其它'), 'merge': ('整套合并件', '套装'), 'ammo': ('弹药带', '配饰'),
    'p_c_horse': ('马匹(非服饰)', '排除'), 'player': ('主角(未分类)', '其它'),
    'pants': ('裤子', '下装'), 'gloves': ('手套', '手部'), 'necktie': ('领带', '配饰'),
    'shawl': ('披肩', '上装'), 'chaps': ('皮套裤', '下装'), 'spats': ('鞋罩', '鞋履'),
    'unionsuit': ('连体内衣', '上装'), 'modoverall': ('连体工装', '上装'),
    'outfit': ('整套', '套装'), 'satchel_strap': ('背包带', '配饰'),
    'holster_front_cup': ('枪套', '配饰'), 'armour': ('护甲', '配饰'),
    'beard_shv_stache': ('胡须(髭)', '头部'), 'beard_shv_chops': ('胡须(络腮)', '头部'),
    'beard_shv_chin': ('胡须(下巴)', '头部'), 'lowertorsogore': ('下躯干伤口', '其它'),
    'uppertorsogore': ('上躯干伤口', '其它'), 'uppertorsoamputaed': ('上躯干(截肢)', '躯干'),
    'goreal': ('血腥', '其它'), 'gorear': ('血腥', '其它'), 'gorell': ('血腥', '其它'),
    'gorelr': ('血腥', '其它'), 'goreh': ('血腥', '其它'), 'horn': ('角(非服饰)', '排除'),
    'saddlecombo': ('马鞍(非服饰)', '排除'), 'stirrup': ('马镫(非服饰)', '排除'),
    'ammo_rifle': ('步枪弹药带', '配饰'), 'ammo_shotgun': ('霰弹弹药带', '配饰'),
    'ammo_pistol': ('手枪弹药带', '配饰'),
}
CAT_ORDER = ['头部', '上装', '躯干', '下装', '鞋履', '手部', '配饰', '套装', '身体', '其它', '排除']


OWNER_PREFIX = ('player_zero_ms1_', 'player_zero_', 'player_three_ms1_', 'player_three_')


def split_name(base):
    """文件名 → (prefix, gender, rank, idx, variant)"""
    for op in OWNER_PREFIX:
        if base.startswith(op):
            tail = base[len(op):]
            pre = re.split(r'[\d]', tail)[0].rstrip('_')
            mi = re.search(r'_(\d{2,3})', '_' + tail)
            idx = int(mi.group(1)) if mi else None
            variant = ''
            if idx is not None:
                variant = tail.split('%03d' % idx, 1)[-1].strip('_')
            return pre, None, None, idx, variant
    m = re.match(r'^(?P<pre>.+?)_(?P<g>[mf])(?P<r>[rst])1(?:_.*)?$', base)
    pre = g = r = None
    rest = ''
    if m:
        pre, g, r = m.group('pre'), m.group('g'), m.group('r')
        rest = base[m.end():]
    else:
        m2 = re.match(r'^(?P<pre>[a-z_]+?)_(?P<rest>\d.*)$', base)
        if m2:
            pre, rest = m2.group('pre'), m2.group('rest')
        else:
            pre = re.split(r'[_\d]', base)[0]
            rest = base[len(pre):]
    idx = None
    mi = re.search(r'(\d{2,3})', rest or base)
    if mi:
        idx = int(mi.group(1))
    variant = ''
    tail = (rest or '')
    if idx is not None:
        variant = tail.replace(str(idx), '', 1).lstrip('_')
    variant = re.sub(r'^_+', '', variant)
    return pre, g, r, idx, variant


def main():
    rows = []
    for folder, label in SRC:
        d = os.path.join(ROOT, 'raw/npc/models', folder)
        for f in sorted(os.listdir(d)):
            if not f.endswith('.ydd'):
                continue
            base = f[:-4]
            if base.startswith('cs_'):
                # cs_<名字>_<m/f>s1_<件名>_<编号>
                m = re.match(r'^(cs_[a-z0-9_]+?)_(m|f)s1_(.+)$', base)
                if m:
                    owner, g, tail = m.group(1), m.group(2), m.group(3)
                    pre = re.split(r'[_\d]', tail)[0]
                    mi = re.search(r'_(\d{2,3})', '_' + tail)
                    idx = int(mi.group(1)) if mi else None
                    variant = re.sub(r'.*?_?\d{2,3}', '', tail)
                else:
                    owner, g, pre, idx, variant = base, None, 'merge', None, ''
                pre = pre.rstrip('_')
                if pre.endswith('_s') and pre[:-2] in SLOT:
                    pre = pre[:-2]
                if pre == 'acc2':
                    pre = 'accs'
                slot_name, cat = SLOT.get(pre, (pre, '其它'))
                row = dict(source='cutscene', source_zh=label, file=f, owner=owner,
                           slot=pre, slot_zh=slot_name, category=cat,
                           gender='男' if g == 'm' else ('女' if g == 'f' else ''),
                           idx=idx, variant=variant or '')
            else:
                pre, g, r, idx, variant = split_name(base)
                pre = pre.rstrip('_')
                if pre.endswith('_s') and pre[:-2] in SLOT:
                    pre = pre[:-2]
                if pre == 'acc2':
                    pre = 'accs'
                slot_name, cat = SLOT.get(pre, (pre, '其它'))
                owner = ''
                for op in OWNER_PREFIX:
                    if base.startswith(op):
                        owner = op[:-1]
                row = dict(source=folder, source_zh=label, file=f, owner=owner,
                           slot=pre, slot_zh=slot_name, category=cat,
                           gender='男' if g == 'm' else ('女' if g == 'f' else ''),
                           idx=idx, variant=variant or '')
            try:
                ped = E.parse_ped(os.path.join(d, f))
                parts = ped['parts']
                texs = sorted({p['name'] for p in parts if p.get('name')})
                row.update(parts=len(parts), verts=sum(p['verts'] for p in parts),
                           tris=sum(p['tris'] for p in parts),
                           textures=len(texs), tex_names=';'.join(texs[:12]))
            except Exception as e:
                row.update(parts=0, verts=0, tris=0, textures=0, tex_names='')
            row['bytes'] = os.path.getsize(os.path.join(d, f))
            rows.append(row)

    cols = ['source', 'source_zh', 'file', 'owner', 'slot', 'slot_zh', 'category',
            'gender', 'idx', 'variant', 'parts', 'verts', 'tris', 'textures',
            'tex_names', 'bytes']
    with open(OUT_CSV, 'w', newline='', encoding='utf-8-sig') as fp:
        w = csv.DictWriter(fp, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    # 统计
    by_slot = collections.Counter()
    by_cat = collections.Counter()
    by_src = collections.Counter()
    for r in rows:
        by_slot[r['slot']] += 1
        by_cat[r['category']] += 1
        by_src[r['source']] += 1
    cat_slots = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        cat_slots[r['category']][r['slot']] += 1

    meta = dict(
        total=len(rows),
        by_source=dict(by_src),
        by_category=dict(by_cat),
        by_slot={k: v for k, v in by_slot.most_common()},
        cat_slots={k: dict(v.most_common()) for k, v in cat_slots.items()},
        slot_zh={k: v[0] for k, v in SLOT.items()},
        order=CAT_ORDER,
    )
    json.dump(meta, open(OUT_JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    write_html(rows, meta)
    print('rows', len(rows), '→', OUT_CSV)
    print('slots', len(by_slot), 'cats', dict(by_cat))


HTML = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>RDR2 全服饰清单</title>
<style>
:root{--bg:#12161c;--panel:#1a2029;--line:#2b3440;--fg:#e6edf3;--mut:#8b98a6;--acc:#d9a441}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:13px/1.55 "Microsoft YaHei",system-ui,sans-serif}
header{padding:18px 22px;border-bottom:1px solid var(--line);display:flex;gap:18px;align-items:baseline;flex-wrap:wrap}
h1{font-size:18px;margin:0;letter-spacing:.5px}
.kpi{color:var(--mut)}.kpi b{color:var(--acc);font-size:15px}
.wrap{display:grid;grid-template-columns:230px 1fr;height:calc(100vh - 66px)}
aside{border-right:1px solid var(--line);overflow:auto;padding:10px 0}
aside button{display:flex;justify-content:space-between;width:100%;background:none;border:0;color:var(--fg);
 padding:7px 16px;cursor:pointer;font:inherit;text-align:left}
aside button:hover{background:#1f2833}aside button.on{background:#243041;color:var(--acc)}
aside .cat{padding:12px 16px 4px;color:var(--mut);font-size:11px;letter-spacing:1px}
aside small{color:var(--mut)}
main{display:flex;flex-direction:column;overflow:hidden}
.bar{padding:10px 14px;border-bottom:1px solid var(--line);display:flex;gap:10px;align-items:center;flex-wrap:wrap}
input{background:#0e1218;border:1px solid var(--line);color:var(--fg);padding:7px 10px;border-radius:6px;width:260px}
.tabs{display:flex;gap:6px}.tabs button{background:#1c242f;border:1px solid var(--line);color:var(--fg);
 padding:5px 10px;border-radius:6px;cursor:pointer}.tabs button.on{background:var(--acc);color:#1a1206;border-color:var(--acc)}
.scroll{overflow:auto;flex:1}
table{border-collapse:collapse;width:100%}th,td{padding:6px 10px;border-bottom:1px solid #212a34;white-space:nowrap}
th{position:sticky;top:0;background:#161c24;color:var(--mut);font-weight:500;text-align:left;z-index:2}
tr:hover td{background:#18202a}
td.mono{font-family:ui-monospace,Consolas,monospace;color:#a9b6c4}
.view3d{display:inline-block;padding:1px 8px;border-radius:99px;background:#243041;color:#9fb4c9;text-decoration:none;font-size:11px}
.view3d:hover{background:var(--acc);color:#1a1206}
.thumb{width:36px;height:54px;object-fit:contain;display:block;background:#12161c;border-radius:3px}
td.thumbcol{width:44px;padding:2px 6px}
.badge{display:inline-block;padding:1px 7px;border-radius:99px;background:#243041;color:#9fb4c9;font-size:11px}
.g-m{background:#1d3346;color:#8fc4ea}.g-f{background:#3a2033;color:#e69ac2}
</style></head><body>
<header><h1>荒野大镖客 2 · 全服饰清单</h1>
<span class="kpi">服饰总数 <b id="k1"></b></span>
<span class="kpi">槽位 <b id="k2"></b></span>
<span class="kpi">通用可换装 <b id="k3"></b></span>
<span class="kpi">剧情专属 <b id="k4"></b></span>
</header>
<div class="wrap"><aside id="side"></aside>
<main><div class="bar">
<input id="q" placeholder="搜索 文件名 / 槽位 / 角色 / 贴图名…">
<div class="tabs"><button data-src="all" class="on">全部</button><button data-src="generic">通用</button>
<button data-src="player">主角</button><button data-src="cutscene">剧情</button></div>
<span id="cnt" class="kpi"></span></div>
<div class="scroll"><table><thead><tr>
<th class="thumbcol"></th><th>文件</th><th>槽位</th><th>性别</th><th>编号</th><th>变体</th><th>部件</th><th>三角面</th><th>贴图</th><th>归属</th><th>来源</th><th>3D</th>
</tr></thead><tbody id="tb"></tbody></table></div></main></div>
<script>
(function(){
  if (location.protocol==='file:') {
    var d=document.createElement('div');
    d.style.cssText='position:fixed;inset:0;z-index:99;background:#1a0f10;color:#ffb4b4;'+
      'font:14px/1.8 "Microsoft YaHei",sans-serif;padding:60px;white-space:pre-wrap';
    d.textContent=['这个页面不能双击打开。','','请回到项目根目录，双击「打开查看器.bat」，','然后在首页点「服饰清单」。'].join(String.fromCharCode(10));
    document.body.appendChild(d);
  }
})();
</script>
<script>
const DATA = __DATA__;
const META = __META__;
let curSlot = '', curSrc = 'all', q = '';
document.getElementById('k1').textContent = META.total;
document.getElementById('k2').textContent = Object.keys(META.by_slot).length;
document.getElementById('k3').textContent = META.by_source.generic || 0;
document.getElementById('k4').textContent = META.by_source.cutscene || 0;
const side = document.getElementById('side');
for (const cat of META.order) {
  const slots = META.cat_slots[cat]; if (!slots) continue;
  const h = document.createElement('div'); h.className = 'cat'; h.textContent = cat; side.appendChild(h);
  for (const [slot, n] of Object.entries(slots)) {
    const b = document.createElement('button');
    b.innerHTML = `<span>${slot} <small>${META.slot_zh[slot]||''}</small></span><small>${n}</small>`;
    b.onclick = () => { curSlot = (curSlot === slot ? '' : slot); renderSide(); draw(); };
    b.dataset.slot = slot; side.appendChild(b);
  }
}
function renderSide(){ for (const b of side.querySelectorAll('button')) b.classList.toggle('on', b.dataset.slot === curSlot); }
document.querySelectorAll('.tabs button').forEach(b => b.onclick = () => {
  curSrc = b.dataset.src; document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('on',x===b)); draw();
});
document.getElementById('q').oninput = e => { q = e.target.value.toLowerCase(); draw(); };
function draw(){
  const rows = DATA.filter(r => (!curSlot || r.slot === curSlot)
    && (curSrc === 'all' || r.source === curSrc)
    && (!q || (r.file + ' ' + r.slot + ' ' + (r.owner||'') + ' ' + (r.tex_names||'') + ' ' + (r.variant||'')).toLowerCase().includes(q)));
  document.getElementById('cnt').textContent = rows.length + ' 件';
  const tb = document.getElementById('tb');
  tb.innerHTML = rows.slice(0, 2000).map(r => `<tr>
    <td class="thumbcol">${r.thumb ? `<img class="thumb" loading="lazy" src="${r.thumb}?v=3" alt="">` : ''}</td>
    <td class="mono">${r.file}</td><td><span class="badge">${r.slot}</span> ${r.slot_zh}</td>
    <td><span class="badge ${r.gender==='男'?'g-m':r.gender==='女'?'g-f':''}">${r.gender||'-'}</span></td>
    <td>${r.idx ?? '-'}</td><td>${r.variant||''}</td><td>${r.parts}</td><td>${r.tris.toLocaleString()}</td>
    <td>${r.textures}</td><td class="mono">${r.owner||''}</td><td>${r.source_zh}</td>
    <td><a class="view3d" target="_blank" href="clothing3d.html?item=${encodeURIComponent(r.file.replace(/\.ydd$/,''))}">3D</a></td></tr>`).join('');
  if (rows.length > 2000) tb.insertAdjacentHTML('beforeend',
    `<tr><td colspan="11" style="color:#8b98a6">仅显示前 2000 条，请用搜索/筛选缩小范围（共 ${rows.length} 条）</td></tr>`);
}
draw();
</script></body></html>'''


def write_html(rows, meta):
    import json as _json
    tpath = os.path.join(ROOT, 'export/viewer/clothing_thumbs/index.json')
    thumbs = _json.load(open(tpath, encoding='utf-8')) if os.path.exists(tpath) else {}
    slim = [dict(thumb=thumbs.get(r['file'], ''), file=r['file'], slot=r['slot'], slot_zh=r['slot_zh'], category=r['category'],
                 gender=r['gender'], idx=r['idx'], variant=r['variant'], parts=r['parts'],
                 tris=r['tris'], textures=r['textures'], owner=r['owner'],
                 source=r['source'], source_zh=r['source_zh'], tex_names=r['tex_names'][:120])
            for r in rows]
    html = HTML.replace('__DATA__', json.dumps(slim, ensure_ascii=False, separators=(',', ':')))
    html = html.replace('__META__', json.dumps(meta, ensure_ascii=False, separators=(',', ':')))
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    open(OUT_HTML, 'w', encoding='utf-8').write(html)


if __name__ == '__main__':
    main()
