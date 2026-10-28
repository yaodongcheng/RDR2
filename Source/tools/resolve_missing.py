"""把 coverage.json 里未命中的 archetype hash 用 names.txt 反查成名字，
并按前缀/体积分组，判断哪些是「真建筑」而不是植被/道具。

用法：uv run python tools/resolve_missing.py
"""
import os
import re
import json
import sys
from collections import Counter, defaultdict

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
    names = open(os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt'),
                 encoding='latin1').read().splitlines()
    h2n = {}
    for n in names:
        n = n.strip()
        if not n:
            continue
        h2n[joaat(n)] = n
    print(f'names.txt {len(names)} 行，唯一 hash {len(h2n)}')

    cov = json.load(open(os.path.join(ROOT, 'work/sdn/coverage.json'), encoding='utf-8'))
    miss = cov['miss']
    print(f"未命中 archetype {len(miss)} 个 / 实例 {sum(m['n'] for m in miss)}")

    resolved, unresolved = [], []
    for m in miss:
        n = h2n.get(int(m['hash']))
        if n:
            resolved.append((n, m['n'], m.get('bbox')))
        else:
            unresolved.append(m)

    print(f'  名字可解析 {len(resolved)}（实例 {sum(r[1] for r in resolved)}）；'
          f'仍未知 {len(unresolved)}（实例 {sum(u["n"] for u in unresolved)}）')

    # 前缀分类
    def prefix(n):
        p = n.split('_')[0]
        return p

    cnt = Counter()
    for n, c, bb in resolved:
        cnt[prefix(n)] += c
    print('\n按名前缀 × 实例数 Top 30：')
    for p, c in cnt.most_common(30):
        print(f'  {p:24s} {c}')

    # 建筑候选：名字像建筑/体积大
    BUILD = re.compile(r'(com|gar|wrh|mrk|pie|frn|slm|rur|bank|hotel|church|store|saloon|'
                       r'house|bldg|build|shop|office|station|depot|warehouse|factory|'
                       r'civic|theat|theater|hosp|school|hall|market|dock|pier|shed|'
                       r'barn|stable|roof|wall|fence|gala|bron)', re.I)
    cand = [(n, c, bb) for n, c, bb in resolved if BUILD.search(n)]
    print(f'\n像建筑的未命中名 {len(cand)} 个，实例 {sum(c for _, c, _ in cand)}')

    # 按前缀聚合，输出可读清单
    grp = defaultdict(list)
    for n, c, bb in cand:
        grp[prefix(n)].append((n, c, bb))
    for p, lst in sorted(grp.items(), key=lambda t: -sum(x[1] for x in t[1])):
        print(f'\n[{p}] {len(lst)} 名 / {sum(x[1] for x in lst)} 实例')
        for n, c, bb in sorted(lst, key=lambda t: -t[1])[:12]:
            dim = (f'{bb[3]-bb[0]:.0f}x{bb[4]-bb[1]:.0f}x{bb[5]-bb[2]:.0f}' if bb else '-')
            print(f'   {c:4d}  {dim:>14s}  {n}')

    json.dump(dict(resolved=[dict(name=n, n=c, bbox=bb) for n, c, bb in resolved],
                   unresolved=len(unresolved)),
              open(os.path.join(ROOT, 'work/sdn/miss_names.json'), 'w', encoding='utf-8'),
              ensure_ascii=False)


if __name__ == '__main__':
    main()
