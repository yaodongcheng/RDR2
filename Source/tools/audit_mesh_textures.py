# -*- coding: utf-8 -*-
"""全局网格库清单 + 三类贴图清单（交接 TODO-3）。

输入：
  deliverable/handoff/mesh_usage.csv       export_scene_placements.py 产出（用到哪些模型 hash）
  assets/lib_native/index.json             模型 → 子网格/贴图 id 的索引

产物：
  deliverable/handoff/mesh_texture_audit.csv
      hash / mdl / 子网格数 / albedo / normal / ma 名称 / 三类是否齐 / 被几张场景用到
  deliverable/handoff/texture_list.csv
      tex_id / 名称 / 文件 / 类型（alb|nm|ma）/ 被多少模型用 / 文件是否存在
  deliverable/handoff/mesh_texture_audit.json
      汇总：缺 alb / 缺 nm / 缺 ma 的数量与清单（缺 nm/ma **不阻塞**，只列出）

用法：
    python tools/audit_mesh_textures.py
"""
import argparse
import csv
import json
import os

RDR2 = r'D:/BrainMaker/大镖客2解包分析'
HANDOFF = os.path.join(RDR2, 'deliverable/handoff')
USAGE = os.path.join(HANDOFF, 'mesh_usage.csv')
INDEX = os.path.join(RDR2, 'assets/lib_native/index.json')
OUT_CSV = os.path.join(HANDOFF, 'mesh_texture_audit.csv')
OUT_TEX = os.path.join(HANDOFF, 'texture_list.csv')
OUT_JSON = os.path.join(HANDOFF, 'mesh_texture_audit.json')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--usage', default=USAGE)
    ap.add_argument('--index', default=INDEX)
    ap.add_argument('--out', default=OUT_CSV)
    ap.add_argument('--tex-out', default=OUT_TEX)
    ap.add_argument('--json', default=OUT_JSON)
    a = ap.parse_args()

    idx = json.load(open(a.index, encoding='utf-8'))
    models = idx['models']
    tex = idx['tex']
    libdir = os.path.dirname(a.index)

    def tex_name(tid):
        try:
            tid = int(tid)
        except Exception:
            return None
        if 0 <= tid < len(tex):
            return tex[tid].get('n') or None
        return None

    def tex_file(tid):
        try:
            tid = int(tid)
        except Exception:
            return None
        if 0 <= tid < len(tex):
            return tex[tid].get('f') or None
        return None

    used = {}
    with open(a.usage, encoding='utf-8-sig', newline='') as fp:
        for r in csv.DictReader(fp):
            used[(r.get('model_hash') or '').strip().lower()] = {
                'scenes': int(float(r.get('scenes') or 0)),
                'instances': int(float(r.get('instances') or 0)),
            }

    rows = []
    tex_use = {}
    miss_alb, miss_nm, miss_ma, miss_model = [], [], [], []
    for h, u in sorted(used.items(), key=lambda kv: -kv[1]['instances']):
        m = models.get(h) or models.get(h.replace('0x', '0x0'))
        if m is None:
            # 尝试补零的 hash（历史上有不补零的键）
            hh = h[2:] if h.startswith('0x') else h
            try:
                cand = '0x%08x' % int(hh, 16)
            except Exception:
                cand = None
            m = models.get(cand) if cand else None
            if m is not None:
                h = cand
        if m is None:
            miss_model.append(h)
            rows.append([h, '', 0, '', '', '', 0, 0, 0, u['scenes'], u['instances'], 1])
            continue

        subs = m.get('s') or []
        stp = m.get('st') or []
        alb, nm, ma = [], [], []
        for i, sub in enumerate(subs):
            tid = sub[0] if sub else -1
            n = tex_name(tid)
            if n:
                alb.append(n)
                tex_use.setdefault(tid, {'type': 'alb', 'models': set(), 'inst': 0})
                tex_use[tid]['models'].add(h)
                tex_use[tid]['inst'] += u['instances']
            pair = stp[i] if i < len(stp) else None
            if pair:
                nt, mt = pair[0], pair[1]
                nn = tex_name(nt)
                if nn:
                    nm.append(nn)
                    tex_use.setdefault(nt, {'type': 'nm', 'models': set(), 'inst': 0})
                    tex_use[nt]['models'].add(h)
                    tex_use[nt]['inst'] += u['instances']
                mn = tex_name(mt)
                if mn:
                    ma.append(mn)
                    tex_use.setdefault(mt, {'type': 'ma', 'models': set(), 'inst': 0})
                    tex_use[mt]['models'].add(h)
                    tex_use[mt]['inst'] += u['instances']

        has_alb = 1 if alb else 0
        has_nm = 1 if nm else 0
        has_ma = 1 if ma else 0
        if not has_alb:
            miss_alb.append(h)
        if not has_nm:
            miss_nm.append(h)
        if not has_ma:
            miss_ma.append(h)
        rows.append([h, m.get('f') or '', len(subs),
                     '|'.join(sorted(set(alb))), '|'.join(sorted(set(nm))), '|'.join(sorted(set(ma))),
                     has_alb, has_nm, has_ma, u['scenes'], u['instances'], 0])

    with open(a.out, 'w', encoding='utf-8-sig', newline='') as fp:
        wr = csv.writer(fp)
        wr.writerow(['model_hash', 'mdl', 'submeshes', 'albedo', 'normal', 'ma',
                     'has_alb', 'has_nm', 'has_ma', 'scenes', 'instances', 'missing_in_index'])
        wr.writerows(rows)

    with open(a.tex_out, 'w', encoding='utf-8-sig', newline='') as fp:
        wr = csv.writer(fp)
        wr.writerow(['tex_id', 'name', 'file', 'type', 'models', 'instances', 'file_exists'])
        for tid, u in sorted(tex_use.items(), key=lambda kv: -len(kv[1]['models'])):
            f = tex_file(tid) or ''
            exists = 1 if f and os.path.exists(os.path.join(libdir, f)) else 0
            wr.writerow([tid, tex_name(tid) or '', f, u['type'], len(u['models']),
                         u['inst'], exists])

    summary = {
        'source_usage': os.path.relpath(a.usage, RDR2).replace('\\', '/'),
        'used_models': len(used),
        'missing_in_index': len(miss_model),
        'missing_albedo': {'count': len(miss_alb), 'hashes': miss_alb[:50]},
        'missing_normal': {'count': len(miss_nm), 'hashes': miss_nm[:50]},
        'missing_ma': {'count': len(miss_ma), 'hashes': miss_ma[:50]},
        'textures_used': len(tex_use),
        'note': '缺 nm/ma 不阻塞（交接规范）；缺 alb 的模型列为待补',
    }
    json.dump(summary, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('[tex] 用到模型 %d 个' % len(used))
    print('[tex] 索引里找不到：%d' % len(miss_model))
    print('[tex] 缺 albedo：%d · 缺 normal：%d · 缺 ma：%d'
          % (len(miss_alb), len(miss_nm), len(miss_ma)))
    print('[tex] 用到贴图：%d 张' % len(tex_use))
    print('[tex] 清单 -> %s' % a.out)
    print('[tex] 贴图表 -> %s' % a.tex_out)
    print('[tex] 汇总 -> %s' % a.json)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
