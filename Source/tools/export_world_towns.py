"""把 RDR2 全世界的城镇/据点实体抽出来，做成**可按需懒加载**的数据。

产物（都在 `export/levels/world/`）：
  * `towns.json`            —— 索引：每个据点 {code, name, zh, n, bbox, cx, cy, cy?}
  * `town_data/<code>.js`   —— 单个据点的实体数组（惰性 <script src> 加载）
  * `arch_bbox.js`          —— 只用到的 archetype 包围盒（hash -> [minx,miny,minz,maxx,maxy,maxz]）

为什么要拆：整个地图 4000+ 个 ymap / 世界级实体量很大，一次性内联进一个 HTML 会
几百 MB 且浏览器卡死。拆成「一个索引 + 每镇一个 .js」后，查看器**同一时刻只加载
用户点开的那一个据点**，切镇时把上一个 dispose 掉即可。

用法：uv run python tools/export_world_towns.py
"""
import os
import re
import sys
import glob
import json
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ymap_entities import extract

ROOT = r'D:/BrainMaker/大镖客2解包分析'
META = os.path.join(ROOT, 'export/levels/map_metadata')
WORLD = os.path.join(ROOT, 'export/levels/world')
ARCH = os.path.join(ROOT, 'export/levels/town/archetypes.json')

# 内部区域码 → 官方地名（英文 / 中文）。仅覆盖"有名有姓"的据点；
# 其余（纯区域网格 a-z、临时营地等）归到"其他据点"，也可点开看灰盒。
NAMES = {
    'val': ('Valentine', '瓦伦丁'),
    'rho': ('Rhodes', '罗兹'),
    'sdn': ('Saint Denis', '圣丹尼斯'),
    'bla': ('Blackwater', '黑水镇'),
    'arm': ('Armadillo', '犰狳镇'),
    'tum': ('Tumbleweed', '风滚草镇'),
    'ann': ('Annesburg', '安尼斯堡'),
    'str': ('Strawberry', '草莓镇'),
    'van': ('Van Horn Trading Post', '范霍恩贸易站'),
    'eme': ('Emerald Ranch', '翡翠牧场'),
    'lag': ('Lagras', '拉格拉斯'),
    'col': ('Colter', '科尔特'),
    'cal': ('Caliga Hall', '卡利加庄园'),
    'agu': ('Aguasdulces', '阿瓜斯杜尔塞斯'),
    'bra': ('Braithwaite Manor', '布雷斯韦特庄园'),
    'wap': ('Wapiti', '瓦匹提'),
    'bea': ('Beaver Hollow', '海狸洞'),
    'but': ('Butcher Creek', '屠夫溪'),
    'dew': ('Dewberry Creek', '杜伯里溪'),
    'gap': ('Gaptooth Breach', '裂齿矿洞'),
    'rat': ('Rathskeller Fork', '鼠窖岔口'),
    'man': ('Manzanita Post', '曼萨尼塔哨站'),
    'pro': ('Pronghorn Ranch', '叉角羚牧场'),
    'sis': ('Sisika Penitentiary', '西西卡监狱'),
    'cor': ('Cornwall Kerosene & Tar', '康沃尔煤油厂'),
    'bee': ('Beechers Hope', '比彻之愿'),
    'wal': ('Fort Wallace', '华莱士堡'),
    'mfr': ("MacFarlane's Ranch", '麦克法兰牧场'),
    'rid': ('Ridgewood Farm?', '里奇伍德农场'),
    'han': ("Hanging Dog Ranch", '吊狗牧场'),
    'cro': ('Crawford?', '克劳福德'),
    'com': ('Compson?', '康普森'),
    'che': ("Chez Porter", '波特小屋'),
    'dow': ("Downe's Ranch", '唐恩牧场'),
    'old': ('Old Bacchus Place?', '老巴克斯'),
    'fom': ('Fort Mercer', '默瑟堡'),
    'cle': ('Clemens Point', '克莱门斯据点'),
    'adl': ('Adler Ranch', '阿德勒牧场'),
    'twi': ('Twin Rocks', '双岩'),
    'ora': ("O'Creagh's Run", '奥克雷格'),
    'lon': ("Lonnie's Shack", '朗尼小屋'),
    'sod': ('Sod House', '草皮屋'),
    'dewclm': ('Dewberry Creek', '杜伯里溪'),
    'wil': ('Willard\'s Rest', '威拉德安息地'),
    'sis2': ('Sisika', '西西卡'),
}
# 不属于据点、只是区域网格或系统件的码（也能点，但默认隐藏）
GRID = set('abcdefghijklmnopqrstuvwxyz') | {
    'new', 'jklm', 'nopq', 'rstu', 'vwxy', 'fghi', 'abcd', 'cd', 'mp', 'reg',
    'shack', 'mission', 'des', 'wild', 'bone', 'sca', 'swa', 'two', 'six',
    'three', 'big', 'bea', 'cvb', 'dai', 'sol', 'cle', 'nat', 'cra', 'dea',
    'min', 'com', 'cro', 'grays1', 'bac', 'hat', 'rho2'}


def main():
    os.makedirs(os.path.join(WORLD, 'town_data'), exist_ok=True)
    arch = json.load(open(ARCH, encoding='utf-8'))

    # 1) 按区域码聚合实体（hash 命名的 ymap 合并到 _misc，不单独成点）
    groups = collections.defaultdict(list)
    files = 0
    for f in sorted(glob.glob(os.path.join(META, '**', '*.ymap'), recursive=True)):
        b = os.path.basename(f)
        code = '_misc' if b.lower().startswith('0x') else b.split('_')[0]
        sig, size, ents = extract(f)
        if not ents:
            continue
        files += 1
        groups[code].extend(ents)
    print(f'scanned {files} ymap, {sum(len(v) for v in groups.values())} entities, '
          f'{len(groups)} area codes')

    # 2) 组索引 + 每镇 .js（archetype 包围盒在导出时**就地解析**，避免全局大表）
    index = []
    for code, ents in groups.items():
        xs = [e[1] for e in ents]
        ys = [e[2] for e in ents]
        zs = [e[3] for e in ents]
        bbox = [round(min(xs), 1), round(min(ys), 1), round(min(zs), 1),
                round(max(xs), 1), round(max(ys), 1), round(max(zs), 1)]
        nm = NAMES.get(code)
        if nm:
            name, zh = nm
        elif code in GRID or code == '_misc':
            name, zh = f'Region {code.upper()}', f'区域 {code.upper()}'
        else:
            name, zh = code.upper(), f'据点 {code.upper()}'
        index.append({
            'code': code, 'name': name, 'zh': zh, 'n': len(ents),
            'bbox': bbox, 'cx': round((bbox[0] + bbox[3]) / 2, 1),
            'cy': round((bbox[1] + bbox[4]) / 2, 1), 'cz': round((bbox[2] + bbox[5]) / 2, 1),
            'grid': (code in GRID or code == '_misc'),
            'major': (code in NAMES and code not in GRID),
        })
        # 实体 = [x,y,z, qx,qy,qz,qw, sx,sy,sz, |  bminx,bminy,bminz, bmaxx,bmaxy,bmaxz]
        out = []
        for e in ents:
            b = arch.get(str(e[0]))
            if b:
                out.append(e + [round(v, 2) for v in b])
            else:
                # 没有 archetype 记录：退化成一个 1m 小盒
                out.append(e + [-0.5, -0.5, -0.5, 0.5, 0.5, 0.5])
        js = ('window.RDR2_TOWNS=window.RDR2_TOWNS||{};window.RDR2_TOWNS['
              + json.dumps(code) + ']=' + json.dumps(out, separators=(',', ':')) + ';')
        open(os.path.join(WORLD, 'town_data', code + '.js'), 'w', encoding='utf-8').write(js)

    index.sort(key=lambda t: -t['n'])
    json.dump({'towns': index}, open(os.path.join(WORLD, 'towns.json'), 'w',
                                     encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f'index {len(index)} settlements, {len(groups)} files written')
    named = [t for t in index if not t['grid']]
    print('named settlements:', ', '.join(f"{t['name']}({t['n']})" for t in named[:45]))


if __name__ == '__main__':
    main()
