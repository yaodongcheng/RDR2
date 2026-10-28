# -*- coding: utf-8 -*-
"""重新解析模型的贴图绑定：从 ydr 读真实贴图名 → 从贴图池精确匹配 → 更新 index。

背景：旧 index 的贴图是 fuzzy 猜出来的（草地被配成"烧焦"），而 index 的 s 数组只存 tid，
不存名字，无法反推。好在 export/world/continent/models.json 里的 10,893 个 ydr 都还在，
可以从源文件重新解析。

    uv run --with numpy --with pillow python tools/rebind_textures.py [--dry]
"""
import os, sys, json
ROOT = r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import export_sdn_gltf as EX
import dump_model_lib as D
from PIL import Image

LIB = os.path.join(ROOT, 'assets/lib_native')
IDX = os.path.join(LIB, 'index.json')
MODELS = os.path.join(ROOT, 'export/world/continent/models.json')


def main():
    dry = '--dry' in sys.argv
    d = json.load(open(IDX, encoding='utf-8'))
    models, tex = d['models'], d['tex']
    print('[rebind] 库内模型 %d，贴图 %d' % (len(models), len(tex)))

    pool = EX.TexLib([os.path.join(ROOT, 'work/lib_gtxd/txd'),
                      os.path.join(ROOT, 'work/sdn/gtxd/txd'),
                      os.path.join(ROOT, 'work/sdn/gtxd/txd_int')], maxs=512)
    print('[rebind] 池内贴图名 %d' % len(pool.idx))
    name2tid = {t['n'].lower(): t['id'] for t in tex}

    def tid_of(nm):
        if not nm:
            return -1
        k = EX.clean_name(nm).lower()
        if k in name2tid:
            return name2tid[k]
        ent = pool.idx.get(k)
        if ent is None:
            return -1
        im, fmt = pool._decode(*ent)
        if im is None:
            return -1
        if max(im.size) > 512:
            im = im.resize((512, 512), Image.LANCZOS)
        if im.mode not in ('RGB', 'RGBA'):
            im = im.convert('RGB')
        tid = len(tex)
        fn = '%04d.png' % tid
        im.save(os.path.join(LIB, 'tex', fn), 'PNG', optimize=True)
        tex.append({'id': tid, 'n': nm, 'f': 'tex/' + fn})
        name2tid[k] = tid
        return tid

    src = json.load(open(MODELS, encoding='utf-8'))
    # 追加「按文件名哈希对上的」模型：库里 48,594 个模型没有 models.json 源路径，
    # 其中约 9,780 个能在 export/models / raw / work 里找到同名 .ydr/.yft/.ydd
    # （archetype hash == joaat(文件名)），这些同样能按名字重绑。
    extra = os.path.join(ROOT, 'work/model_file_map.json')
    if os.path.exists(extra):
        try:
            em = json.load(open(extra, encoding='utf-8'))
            added = 0
            for hx, path in em.items():
                if hx not in src and os.path.exists(path):
                    src[hx] = path
                    added += 1
            print('[rebind] 追加同名文件映射 %d 条（work/model_file_map.json）' % added)
        except Exception as e:
            print('[rebind] 额外映射读取失败：%s' % e)
    print('[rebind] 可重绑模型 %d' % len(src))
    done = fixed = added = miss = 0
    for hx, path in src.items():
        e = models.get(hx)
        if not e or not os.path.exists(path):
            continue
        try:
            M = D.load_any(path)
        except Exception:
            continue
        if not M:
            continue
        geoms = [g for g in M['geoms'] if len(g['pos'])]
        if not geoms:
            continue
        new_s = []
        changed = False
        for g in geoms:
            nv = len(g['pos']); ni = len(g.get('idx') or [])
            t = tid_of(g.get('tex'))
            if t < 0:
                miss += 1
            new_s.append([t, nv, ni])
        old_s = e.get('s') or []
        if old_s != new_s:
            changed = True
        if changed:
            fixed += 1
            if not dry:
                e['s'] = new_s
        done += 1
        if done % 1000 == 0:
            print('  %d/%d  改绑 %d' % (done, len(src), fixed))

    print('[rebind] 处理 %d，改绑 %d，无贴图子网格 %d' % (done, fixed, miss))
    if dry:
        print('[rebind] dry-run，未落盘')
        return
    json.dump(d, open(IDX, 'w', encoding='utf-8'), separators=(',', ':'))
    print('[rebind] saved（贴图 %d 张）' % len(tex))


main()
