# -*- coding: utf-8 -*-
"""对已存盘的审计块重跑分类 + 清单（不重建几何）。

    blender -b <blend> -P tools/_unbuffer.py -P tools/_apply_corrections.py -- \
        --corrections "D:/BrainMaker/大镖客2解包分析/deliverable/blender/regions_support/region_corrections.csv" --out <同一 blend>

用于审计阶段：改分类规则/纠错清单后，子块只需这一步（约 3~5 分钟），
不用从零重建；全部纠正完再对大陆跑一次 reclassify。
"""
import glob
import os
import shutil
import sys

argv = sys.argv
ARGS = argv[argv.index('--') + 1:] if '--' in argv else []
CORR = ARGS[ARGS.index('--corrections') + 1] if '--corrections' in ARGS else ''
OUT = ARGS[ARGS.index('--out') + 1] if '--out' in ARGS else ''

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import classify_entities  # noqa: E402
import write_manifest     # noqa: E402

sys.argv = ['classify_entities', '--', '--apply', '--out', OUT] + \
           (['--corrections', CORR] if CORR else [])
classify_entities.main()

sys.argv = ['write_manifest', '--', '--out', OUT]
write_manifest.main()

# 清单不留在 blend 目录：约定是「regions/ 只放 blend，验证内容放 regions_support/」
d = os.path.dirname(os.path.abspath(OUT))
stem = os.path.splitext(os.path.basename(OUT))[0]
sup = os.path.join(os.path.dirname(d), 'regions_support')
# 只有 regions/ 下的区域裁剪才把清单挪走；大陆/其他 blend 的清单留在同目录
if os.path.basename(d) == 'regions' and os.path.isdir(sup):
    for p in glob.glob(os.path.join(d, 'manifest_%s.*' % stem)) + [os.path.join(d, 'manifest.json')]:
        if os.path.exists(p):
            shutil.move(p, os.path.join(sup, os.path.basename(p)))
            print('[apply] moved %s -> %s' % (os.path.basename(p), sup))
