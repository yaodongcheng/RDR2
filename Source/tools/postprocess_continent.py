# -*- coding: utf-8 -*-
"""对已构建好的 continent blend 补跑后处理：分类(12 类) → 删植被 → 地形 patch 归隐藏 → manifest。

用途：几何已建好（6.4 GB，重建要 20~25 分钟），但漏了后处理时，用这个补（只加载一次）。

    blender -b <blend> -P tools/postprocess_continent.py [-- --skip-veg]

2026-10-29：补上 hide_terrain_patches 与 manifest —— 之前 `--full` 链里没有这两步，
导致「构建产物」和交付的 v5 不一致（地形 patch 留在 ENTITIES 里、也没有清单可核对）。
"""
import bpy, os, sys, importlib

ROOT = r'D:/BrainMaker/大镖客2解包分析'
TOOLS = os.path.join(ROOT, 'tools')
if TOOLS not in sys.path:
  sys.path.insert(0, TOOLS)


def argv():
  a = sys.argv
  return a[a.index('--') + 1:] if '--' in a else []


def run(mod_name, args):
  old = sys.argv[:]
  sys.argv = [mod_name] + ['--'] + args
  try:
    if mod_name in sys.modules:
      del sys.modules[mod_name]
    importlib.import_module(mod_name).main()
  finally:
    sys.argv = old


def main():
  a = argv()
  out = bpy.data.filepath
  print('[pp] 文件', out)

  # 2026-10-29：贴图表补登记了 1,782 条孤儿贴图（id 5292..7073，见 register_orphan_textures.py）
  # 之后，已存盘 blend 的材质必须按新 index 重挂一次 —— 只换材质引用，不动几何/变换/隐藏。
  if '--relink' in a:
    print('\n=== [pp] 0/4 按当前 index 重挂材质（relink_materials） ===')
    run('relink_materials', [])

  if '--manifest-only' in a:
    print('\n=== [pp] 只重建清单 + 校验（不重跑分类/删植被/隐藏） ===')
    run('write_manifest', ['--out', out])
    if 'report_manifest' in sys.modules:
      del sys.modules['report_manifest']
    import report_manifest as RM
    RM.main(['--manifest', os.path.join(os.path.dirname(out), 'manifest.json')])
    return

  print('\n=== [pp] 1/4 分类（12 类集合树） ===')
  if '--skip-classify' in a:
    print('[pp] 跳过：分类已完成（加 --skip-classify）')
  else:
    run('classify_entities', ['--apply', '--out', out])

  veg = a[a.index('--veg') + 1] if '--veg' in a else 'hide'
  if '--skip-veg' in a or veg == 'keep':
    print('\n=== [pp] 2/4 植被：跳过（%s） ===' % ('--skip-veg' if '--skip-veg' in a else 'keep'))
  else:
    print('\n=== [pp] 2/4 植被：%s ===' % veg)
    run('strip_vegetation', ['--out', out, '--mode', veg])

  print('\n=== [pp] 3/4 地形 patch 归 HIDDEN_TERRAIN_CELL（隐藏不删） ===')
  run('hide_terrain_patches', [])

  print('\n=== [pp] 4/4 输出对象清单 ===')
  run('write_manifest', ['--out', out])

  print('\n=== [pp] 校验（读清单，数字口径与构建链一致） ===')
  if 'report_manifest' in sys.modules:
    del sys.modules['report_manifest']
  import report_manifest as RM
  RM.main(['--manifest', os.path.join(os.path.dirname(out), 'manifest.json')])


if __name__ == '__main__':
  main()
