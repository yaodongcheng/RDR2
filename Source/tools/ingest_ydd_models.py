# -*- coding: utf-8 -*-
"""把躺在 `.ydd`（DrawableDictionary）里的 drawable 解析成模型、入库。

## 背景

`real_ytyp` 那 3,061 个 hash 有真实 ytyp 定义（bbox 中位 7.4 m），但按 hash 在 RPF 条目里
找不到 `.ydr/.yft`。本轮建了 `work/ydd_index.json`（16,766 个 .ydd → 62,499 个子 drawable hash），
实测这 3,061 个 **全部** 能在字典里定位到（另有 180 个 `no_definition`）。

本工具做的就是：按索引打开 .ydd → 在指定 body 偏移解析 drawable（`read_geom` 拿
pos/nrm/uv/idx，`parse_shader_group` 拿贴图名）→ 写 `.mdl` → 登记进 `index.json`。

    python tools/ingest_ydd_models.py --dry
    python tools/ingest_ydd_models.py --buckets real_ytyp no_definition
"""
import os
import sys
import json
import time
import argparse
from collections import Counter, OrderedDict

ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import rdr2_ydr as Y
import export_sdn_gltf as EX
import dump_model_lib as D

LIB = os.path.join(ROOT, 'assets/lib_native')
INDEX = os.path.join(LIB, 'index.json')
YDDIDX = os.path.join(ROOT, 'work/ydd_index.json')
MISS = os.path.join(ROOT, 'export/world/missing_classified.json')
IDS = os.path.join(ROOT, 'work/tex_name_ids.json')
REPORT = os.path.join(ROOT, 'work/ingest_ydd_report.json')
ROLE_ALBEDO = getattr(EX, 'ROLE_ALBEDO', ('albedo', 'albedo2'))


class TexId:
    """把贴图名字映射成**当前贴图表**的 id（名字即真相，2026-10-29 起）。"""

    def __init__(self, ids):
        self.ids = ids

    def get(self, name, hint=None):
        if not name:
            return 0xFFFFFFFF
        return self.ids.get(EX.clean_name(name).lower(), 0xFFFFFFFF)


class FileCache:
    def __init__(self, n=8):
        self.n = n
        self.d = OrderedDict()

    def get(self, path):
        if path in self.d:
            self.d.move_to_end(path)
            return self.d[path]
        b = open(path, 'rb').read()
        self.d[path] = b
        if len(self.d) > self.n:
            self.d.popitem(last=False)
        return b


def load_drawable_at(res, base):
    """在 body 偏移 base 处解析一个 drawable → geoms（与 EX.load_model 同一套解码）。"""
    sg = res.u64(base + 0x10)
    shaders = Y.parse_shader_group(res, sg)
    geoms = []
    for mo in Y.pointer_list(res, res.u64(base + 0x50)):
        gs = Y.parse_model_geoms(res, mo)
        shmap = Y.parse_model_shaders(res, mo, len(gs))
        for gi, gp in enumerate(gs):
            sid = shmap[gi] if gi < len(shmap) else 0
            g = EX.read_geom(res, gp, sid)
            if not g:
                continue
            texs = shaders[sid] if 0 <= sid < len(shaders) else []
            alb = None
            for t in texs:
                if (t.get('role') or '') in ROLE_ALBEDO and t.get('name') \
                        and not t['name'].lower().startswith('blank'):
                    alb = t
                    break
            if alb is None:
                cand = [t for t in texs if t.get('name')
                        and not t['name'].lower().startswith('blank')
                        and (t.get('role') or '') not in
                        ('normal', 'material', 'materialA', 'materialB', 'palette',
                         'lookup', 'control', 'detail', '')]
                if cand:
                    alb = max(cand, key=lambda t: t['w'] * t['h'])
            geoms.append(dict(pos=g['pos'], nrm=g['nrm'], uv=g['uv'], idx=g['idx'],
                              tex=(alb['name'] if alb else None),
                              role=(alb.get('role') if alb else None)))
    return geoms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--buckets', nargs='+', default=['real_ytyp', 'no_definition'])
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()

    idx = json.load(open(INDEX, encoding='utf-8'))
    models, tex = idx['models'], idx['tex']
    ids = json.load(open(IDS, encoding='utf-8'))
    ids = {k: v for k, v in ids.items() if not k.startswith('__')}
    tid = TexId(ids)
    ydd = json.load(open(YDDIDX, encoding='utf-8'))
    per = (json.load(open(MISS, encoding='utf-8')) or {}).get('per_hash') or {}

    targets = []
    for hx, v in per.items():
        b = v.get('bucket') or ''
        base = b.split(':')[0]
        if base in a.buckets and hx not in models and hx.lower() in ydd:
            targets.append(hx.lower())
    targets = sorted(set(targets))
    if a.limit:
        targets = targets[:a.limit]
    print('[gi] 目标 %d 个（桶 %s）；库里现无这些模型' % (len(targets), ','.join(a.buckets)))

    cache = FileCache()
    ok = 0
    nogeo = 0
    fail = 0
    faces = 0
    subs_total = 0
    added = {}
    t0 = time.time()
    for i, hx in enumerate(targets):
        rel, off = ydd[hx]
        path = os.path.join(ROOT, rel)
        try:
            data = cache.get(path)
            res = Y.Res(data)
            geoms = load_drawable_at(res, off)
        except Exception:
            fail += 1
            continue
        geoms = [g for g in geoms if len(g['pos']) and len(g['idx'])]
        if not geoms:
            nogeo += 1
            continue
        if a.dry:
            ok += 1
            faces += sum(len(g['idx']) // 3 for g in geoms)
            continue
        M = {'geoms': geoms, 'ytd': None}
        e = D.write_model(M, int(hx, 16), LIB, tid)
        if not e:
            nogeo += 1
            continue
        added[hx] = e
        ok += 1
        subs_total += len(e['s'])
        faces += sum(n // 3 for _t, _v, n in e['s'])
        if (i + 1) % 200 == 0:
            print('[gi] %d/%d  成功 %d / 无几何 %d / 失败 %d（%.0fs）'
                  % (i + 1, len(targets), ok, nogeo, fail, time.time() - t0))

    print('[gi] 解析成功 %d（子网格 %d、面 %d）/ 无几何 %d / 失败 %d（%.0fs）'
          % (ok, subs_total, faces, nogeo, fail, time.time() - t0))
    if a.dry:
        print('[gi] dry-run，未写库')
        return
    if added:
        import shutil
        bak = os.path.join(LIB, 'index_before_ydd_%s.json' % time.strftime('%Y%m%d_%H%M'))
        if not os.path.exists(bak):
            shutil.copy2(INDEX, bak)
            print('[gi] 备份 %s' % os.path.basename(bak))
        models.update(added)
        idx['models'] = models
        json.dump(idx, open(INDEX, 'w', encoding='utf-8'), separators=(',', ':'))
        print('[gi] 入库 %d 个模型 → %s（现有 %d）' % (len(added), INDEX, len(models)))
    json.dump({'targets': len(targets), 'added': len(added), 'nogeo': nogeo, 'fail': fail,
               'subs': subs_total, 'faces': faces,
               'buckets': a.buckets}, open(REPORT, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('[gi] 报告 %s' % REPORT)


if __name__ == '__main__':
    main()
