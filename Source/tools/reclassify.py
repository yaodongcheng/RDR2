# -*- coding: utf-8 -*-
"""在**已建好的 blend** 上重跑分类（不重建几何），写出新版本 + 新清单。

用途：分类规则改了（例如 2026-10-30 新增「石块」类并默认隐藏）时，
不必花 80 分钟重建几何 —— 只是重新归集合 + 设可见性 + 存盘。

    blender -b continent_v16.blend --python tools/_unbuffer.py -P tools/reclassify.py -- \
        --out D:\...\continent_v17.blend

流程（单进程，避免二次加载 7.8 GB）：
    1. classify_entities --apply      重建 ENTITIES/<C_key>/<T_tid> 树 + 默认隐藏
    2. write_manifest --out <blend>    重写 manifest jsonl/json
    3. save_as_mainfile(--out)
"""
import os
import sys
import argparse

TOOLS = os.path.dirname(os.path.abspath(__file__))
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import bpy


def _run(mod_name, args):
    import importlib
    old = sys.argv[:]
    sys.argv = [mod_name] + ['--'] + args
    try:
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        mod = importlib.import_module(mod_name)
        mod.main()
    finally:
        sys.argv = old


def main():
    ap = argparse.ArgumentParser()
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap.add_argument('--out', required=True)
    ap.add_argument('--skip-manifest', action='store_true')
    a = ap.parse_args(argv)

    print('=== [reclass] 1/3 重新分类（不重建几何）===')
    _run('classify_entities', ['--apply'])

    if not a.skip_manifest:
        print('=== [reclass] 2/3 重写 manifest ===')
        try:
            _run('write_manifest', ['--out', a.out])
        except Exception as e:
            print('[reclass] manifest 失败（不影响 blend）:', e)

    print('=== [reclass] 3/3 另存 %s ===' % a.out)
    # 🔴 覆盖重建时不要生成 .blend1 备份：一个 7.2 GB 的备份纯属浪费（2026-10-30 用户明确反对）
    try:
        bpy.context.preferences.filepaths.save_version = 0
    except Exception as e:
        print('[reclass] 关备份失败（会多出一个 .blend1）:', e)
    bpy.ops.wm.save_as_mainfile(filepath=a.out)
    sz = os.path.getsize(a.out) / 1e9 if os.path.exists(a.out) else 0
    print('[reclass] saved %s (%.2f GB)' % (a.out, sz))


if __name__ == '__main__':
    main()
