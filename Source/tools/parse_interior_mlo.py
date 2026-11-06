"""解析 RDR2 室内 MLO 布局（ytyp 里的 144 字节 entity 块）。

背景：室内件的**摆放**不在 rpf 的同名 ymap 里，而在同包的 `<name>.ytyp`：

  levels/rdr3/interiors/<name>_int.rpf
      ├── <name>_int.ytyp        ← MLO 定义 + 455 个 entity（pos / rot / parentIndex）
      ├── roc_hse_int_shell_main.ydr
      └── ...

ytyp 内 144 字节 entity 的布局与 ymap 的 CMapEntity 一致：

    +8    uint32  archetype hash
    +32   float3  position（**室内局部坐标**，±100 m 内）
    +48   float4  rotation (x,y,z,w)      ← 注意要取共轭才能和 Blender 对齐
    +132  uint16  parentIndex（65535 = 无父）

用法：
  uv run python tools/parse_interior_mlo.py raw/_scratch/roc_ytyp/roc_house_int.ytyp
  uv run python tools/parse_interior_mlo.py <ytyp> --out interior_layout.json
"""
import os
import sys
import json
import glob
import struct
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 🔴 数据工程根（tiles / assets / raw 都在那边；本文件所在仓库只有 tools/）。
#   `Source/tools` 与数据工程的 `tools` 是同一份（junction），所以 names.txt 两边都能开，
#   但 `export/world/continent/tiles` **只在数据工程**里有。
DATA_ROOT = os.environ.get('RDR2_ROOT') or r'D:/BrainMaker/大镖客2解包分析'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from rage_meta import parse, SYS  # noqa: E402

ENTITY_STRUCT = 0xce501483   # 144 字节 entity
ENTITY_SIZE = 144


def joaat(s):
    h = 0
    for c in s.lower().encode():
        h = (h + c) & 0xffffffff
        h = (h + (h << 10)) & 0xffffffff
        h ^= h >> 6
    h = (h + (h << 3)) & 0xffffffff
    h ^= h >> 11
    h = (h + (h << 15)) & 0xffffffff
    return h


def load_names():
    d = {}
    p = os.path.join(DATA_ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
    if not os.path.exists(p):
        p = os.path.join(ROOT, 'tools/rdr2rpf/bin/Release/net9.0/names.txt')
    with open(p, encoding='latin1') as f:
        for n in f:
            n = n.strip()
            if n:
                d[joaat(n)] = n
    return d


# ── MLO 实例查找：**唯一口径**（构建 / 审计 / 体检三处共用）──────────────
# 🔴 2026-11-06 实机：`find_mlo` 曾有一份「先撞到谁算谁」的实现 —— `val_bank_int` 的精确实例
#    不在 tiles 里，先撞到 `val_bank_int_lod`（yaw −100°），而正确实例是 `val_bank_int_main`
#    （yaw 0°）⇒ 瓦伦丁银行室内转歪；体检脚本用的是正确优先级所以 PASS（假绿）。
#    全量 210 个 inside 包里 42 个会取错。
TILES_DIR = os.path.join(DATA_ROOT, 'export/world/continent/tiles')
_TILES_CACHE = None
_MLO_IDX = None


def tiles():
    """全部 tile 实体合并（只读一次）。"""
    global _TILES_CACHE
    if _TILES_CACHE is None:
        _TILES_CACHE = []
        for p in sorted(glob.glob(os.path.join(TILES_DIR, '*.json'))):
            if p.endswith('.bak'):
                continue
            try:
                _TILES_CACHE.extend(json.load(open(p, encoding='utf-8')))
            except Exception:
                continue
    return _TILES_CACHE


def build_mlo_index(names, tile_list):
    """（纯函数，闸门可单测）名字 basename → 实体；同名取首次出现。"""
    d = {}
    for e in tile_list:
        n = names.get(e[0])
        if not n:
            continue
        b = n.split('/')[-1].lower()
        if b not in d:
            d[b] = e
    return d


def mlo_index(names=None, tile_list=None):
    """名字 basename → 实体（同名取首次出现）。进程内缓存。"""
    global _MLO_IDX
    if _MLO_IDX is None:
        _MLO_IDX = build_mlo_index(
            names or load_names(),
            tile_list if tile_list is not None else tiles())
    return _MLO_IDX


def pick_instance(idx, pkg):
    """（纯函数，闸门可单测）按优先级从索引里取：精确 → `_main` → `_lod`。"""
    for key in (pkg, pkg + '_main', pkg + '_lod'):
        e = idx.get(key)
        if e is not None:
            return e
    return None


def find_mlo_instance(pkg, names=None, tile_list=None):
    """包名 → MLO 实例 `[hash, x, y, z, qx, qy, qz, qw]`。

    优先级 **精确 → `_main` → `_lod`**（LOD 只作最后兜底）。
    🔴 构建（scene_interiors）、审计（audit_interior_placement）、体检（_check_interior_align）
       必须调**这同一个函数**，禁止再各写一份。
    """
    return pick_instance(mlo_index(names=names, tile_list=tile_list), pkg)


def parse_ytyp(path):
    d = open(path, 'rb').read()[16:]
    structs, blocks = parse(d)
    out = []
    for bnh, dl, dp in blocks:
        if bnh != ENTITY_STRUCT or dl % ENTITY_SIZE:
            continue
        base = dp - SYS
        for i in range(dl // ENTITY_SIZE):
            o = base + i * ENTITY_SIZE
            h = struct.unpack_from('<I', d, o + 8)[0]
            px, py, pz = struct.unpack_from('<3f', d, o + 32)
            qx, qy, qz, qw = struct.unpack_from('<4f', d, o + 48)
            parent = struct.unpack_from('<H', d, o + 132)[0]
            if not (-100 < px < 100 and -100 < py < 100 and -100 < pz < 100):
                continue
            out.append({'h': h, 'p': [round(px, 3), round(py, 3), round(pz, 3)],
                        'q': [round(qx, 4), round(qy, 4), round(qz, 4), round(qw, 4)],
                        'parent': parent})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ytyp')
    ap.add_argument('--out', default='')
    a = ap.parse_args()

    ents = parse_ytyp(a.ytyp)
    names = load_names()
    lib = json.load(open(os.path.join(ROOT, 'assets/lib_native/index.json'), encoding='utf-8'))['models']

    uniq = {}
    for e in ents:
        uniq.setdefault(e['h'], 0)
        uniq[e['h']] += 1
    missing = [h for h in uniq if hex(h) not in lib]
    print('entity %d，唯一模型 %d，能命名 %d，模型在库 %d，缺 %d'
          % (len(ents), len(uniq), sum(1 for h in uniq if h in names),
             len(uniq) - len(missing), len(missing)))
    if missing:
        print('缺失模型（前 15）:')
        for h in missing[:15]:
            print('   0x%08x %-32s x%d' % (h, names.get(h, '<无名>'), uniq[h]))

    if a.out:
        json.dump({'ytyp': os.path.basename(a.ytyp), 'entities': ents}, open(a.out, 'w'), separators=(',', ':'))
        print('wrote', a.out)


if __name__ == '__main__':
    main()
