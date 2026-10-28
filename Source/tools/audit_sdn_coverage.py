"""圣丹尼斯（StDenis）地编覆盖度审计。

目的：量化「建筑是否破解完全」——
  1) 官方 zone 范围内 ymap 实体总数 / 唯一 archetype 数
  2) 其中能对到已解包 .ydr 的比例
  3) 对不到的 archetype：在 ytyp 里有没有包围盒（=是不是真建筑）
  4) 已导出 L2 里实际落了多少实例

用法：
  uv run python tools/audit_sdn_coverage.py
"""
import os
import sys
import glob
import json
import argparse
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ymap_entities

ROOT = r'D:/BrainMaker/大镖客2解包分析'


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xffffffff
        h = (h + (h << 10)) & 0xffffffff
        h ^= (h >> 6)
    h = (h + (h << 3)) & 0xffffffff
    h ^= (h >> 11)
    h = (h + (h << 15)) & 0xffffffff
    return h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bbox', nargs=4, type=float, default=[2124.0, -1629.0, 2986.0, -674.0],
                    help='xmin ymin xmax ymax（默认 StDenis 官方 zone）')
    ap.add_argument('--margin', type=float, default=30.0)
    ap.add_argument('--ydr', default=os.path.join(ROOT, 'work/sdn/models'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'work/sdn/coverage.json'))
    a = ap.parse_args()

    xmin, ymin, xmax, ymax = a.bbox
    xmin -= a.margin; ymin -= a.margin; xmax += a.margin; ymax += a.margin

    # ---- 模型名 → hash ----
    byname = {}
    for f in glob.glob(os.path.join(a.ydr, '**', '*.ydr'), recursive=True):
        n = os.path.splitext(os.path.basename(f))[0]
        byname[n] = f
    hash2name = defaultdict(list)
    for n in byname:
        hash2name[joaat(n)].append(n)
    print(f'解包 ydr: {len(byname)} 个，joaat 唯一 hash {len(hash2name)}')

    # ---- 扫 ymap ----
    ents = []
    files = 0
    dup = set()
    for f in sorted(glob.glob(os.path.join(ROOT, 'export/levels/map_metadata/**/*.ymap'),
                              recursive=True)):
        try:
            sig, size, es = ymap_entities.extract(f)
        except Exception:
            continue
        if not es:
            continue
        files += 1
        for e in es:
            px, py = e[1], e[2]
            if not (xmin <= px <= xmax and ymin <= py <= ymax):
                continue
            key = (e[0], round(px, 1), round(py, 1), round(e[3], 1))
            if key in dup:
                continue
            dup.add(key)
            ents.append(e)
    print(f'扫描 ymap {files} 个，zone 内实体 {len(ents)} 个')

    # ---- 匹配 ----
    arch_cnt = Counter(e[0] for e in ents)
    matched_i = sum(c for h, c in arch_cnt.items() if h in hash2name)
    print(f'唯一 archetype {len(arch_cnt)}，命中模型 {sum(1 for h in arch_cnt if h in hash2name)}；'
          f'实例命中 {matched_i} / {len(ents)} = {matched_i/max(1,len(ents))*100:.1f}%')

    archs = json.load(open(os.path.join(ROOT, 'export/levels/town/archetypes.json'), encoding='utf-8'))
    archs = {int(k): v for k, v in archs.items()}

    miss = [(h, c) for h, c in arch_cnt.items() if h not in hash2name]
    miss.sort(key=lambda t: -t[1])
    print(f'\n未命中 archetype {len(miss)} 个（实例 {sum(c for _, c in miss)}）')

    def vol(bb):
        if not bb:
            return 0.0
        return max(0.01, (bb[3]-bb[0])) * max(0.01, (bb[4]-bb[1])) * max(0.01, (bb[5]-bb[2]))

    has_bb = sum(1 for h, _ in miss if h in archs)
    big = [(h, c) for h, c in miss if h in archs and vol(archs[h]) > 30]
    print(f'  其中 ytyp 里有包围盒 {has_bb}，体积>30m³ 的 {len(big)}（大概是真建筑/大物件）')

    print('\n  Top 25 未命中（按实例数）：')
    for h, c in miss[:25]:
        bb = archs.get(h)
        vs = f'{vol(bb):8.0f}' if bb else '     ?'
        dim = (f'{bb[3]-bb[0]:.1f}x{bb[4]-bb[1]:.1f}x{bb[5]-bb[2]:.1f}' if bb else '-')
        print(f'    {h:>10} (0x{h:08X}) x{c:3d}  vol={vs}  dim={dim}')

    # ---- 已导出 L2 实例 ----
    exp = None
    p = os.path.join(ROOT, 'work/sdn/insts_merged.json')
    if os.path.exists(p):
        try:
            exp = json.load(open(p, encoding='utf-8'))
        except Exception:
            exp = None
    out = dict(bbox=[xmin, ymin, xmax, ymax], entities=len(ents), unique=len(arch_cnt),
               matched_inst=matched_i, uniq_hit=sum(1 for h in arch_cnt if h in hash2name),
               miss=[dict(hash=h, n=c, bbox=archs.get(h)) for h, c in miss])
    json.dump(out, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'\n-> {a.out}')


if __name__ == '__main__':
    main()
