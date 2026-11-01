# -*- coding: utf-8 -*-
"""模型池解析：把已废弃的 `export/models/<类别>/<子目录>` 约定，映射到 `raw/all_packs`。

## 背景

`export/models` 原本是指向 `raw/models` 的目录联接，`raw/models` 在 2026-11-01 的源合并里被误删，
联接悬空。核对后发现旧池的**二级目录名就是 RPF 包名**：

    export/models/buildings_jklm/cor_01_/**/*.ydr   ≡   raw/all_packs/cor_01_/**/*.ydr
    export/models/props/p_armory/…                  ≡   raw/all_packs/p_armory/…
    export/models/veg/rdr_bushes/…                  ≡   raw/all_packs/rdr_bushes/…

所以不再重建那份 4 GB 的副本，脚本直接用本模块按类别取包。

## 用法

    import pool_models as PM
    PM.iter_models('buildings_jklm', exts=('.ydr',))      # 逐文件
    PM.iter_ytd('props')                                   # 该类别包里的 .ytd
    PM.find('p_armory_shelf01x', cat='props')              # 按模型名找文件
    PM.area_lod_ydds()                                     # 所有 LOD 合并字典 .ydd

类别清单来自旧池的实际二级目录（`archive/inventory.csv` + `models.json` + `tex_name_index2.json` 三处汇总）。
"""
import os
import glob

ROOT = r'D:/BrainMaker/大镖客2解包分析'
PACKS = os.path.join(ROOT, 'raw/all_packs')

CATS = {
    'props': ['int_general_store', 'p_armory', 'p_bathroom', 'p_bedroom', 'p_camp', 'p_camp02',
              'p_clothing', 'p_debris', 'p_drug', 'p_farm', 'p_fence', 'p_furniture',
              'p_graveyard', 'p_household', 'p_hunting', 'p_instrument', 'p_kitchen',
              'p_light_ground01', 'p_light_wall01', 'p_mine', 'p_office', 'p_outhouse',
              'p_pottery', 'p_roadside', 'p_seating', 'p_storage', 'p_storage02', 'p_table',
              'p_tool', 'p_val_frags', 'p_valentines_frags', 'p_vehicle_static',
              'p_watertower', 'p_window', 's_caravan', 's_cs_objects', 's_lev_des', 's_pickups'],
    'veg': ['rdr_birch', 'rdr_bushes', 'rdr_cacti', 'rdr_cedar', 'rdr_dead', 'rdr_debris',
            'rdr_flowers', 'rdr_grass', 'rdr_grass_oldmap', 'rdr_inst_crops',
            'rdr_inst_crops_es', 'rdr_maple', 'rdr_oak', 'rdr_palm', 'rdr_rock_alpine',
            'rdr_rock_bigvalley', 'rdr_rock_cforest', 'rdr_rock_dakota', 'rdr_rock_gplains',
            'rdr_rock_grizzlies', 'rdr_rock_guama', 'rdr_rock_hlands', 'rdr_rock_oldmap',
            'rdr_rock_roanoke', 'rdr_rock_smeadow', 'rdr_rock_talltrees', 'rdr_talltrees',
            'rdr_trees', 'rdr_weeds', 'su_rdr_inst_crops', 'swamp'],
    'buildings_jklm': ['bea_for', 'che_01_', 'cor_01_', 'cor_derricks', 'cor_workers01',
                       'din_01_', 'dow_01_', 'hea_bridge', 'hea_rd_sgn_', 'jklm_7_10_rails_b',
                       'jklm_7_10_rails_c', 'luc_01_', 'mil_01_', 'mp_moo_02', 'old_01_',
                       'reg_hrt_00', 'shack_dr', 'shack_fe', 'six_01_', 'val_02_', 'val_03_',
                       'val_04_', 'val_05_', 'val_06_', 'val_07_', 'wag_01_', 'wal_train_',
                       'wild_01'],
    'buildings': ['val_01_', 'val_02_', 'val_03_', 'val_04_', 'val_05_', 'val_06_', 'val_07_'],
}

# `buildings` / `buildings_jklm` 合起来才是"建筑"全量（旧脚本用 buildings* 同时匹配两者）
CATS['buildings_all'] = sorted(set(CATS['buildings']) | set(CATS['buildings_jklm']))

DEFAULT_MODEL_EXTS = ('.ydr', '.ydd', '.yft')


def pack_dir(name):
    """包名 → 目录；旧池里有 `val_02__rpf` 这类抽取残留名，做一次归一。"""
    for cand in (name, name.replace('__rpf', '_'), name.replace('_rpf', '')):
        p = os.path.join(PACKS, cand)
        if os.path.isdir(p):
            return p
    p = os.path.join(PACKS, name)
    return p if os.path.isdir(p) else None


def category_dirs(cat):
    if cat not in CATS:
        raise KeyError('未知类别 %r（可用：%s）' % (cat, ', '.join(sorted(CATS))))
    out = []
    for n in CATS[cat]:
        d = pack_dir(n)
        if d:
            out.append(d)
    return out


def iter_files(dirs, exts):
    exts = tuple(e.lower() for e in exts)
    for d in dirs:
        for dp, _, fs in os.walk(d):
            for f in fs:
                if f.lower().endswith(exts):
                    yield os.path.join(dp, f)


def iter_models(cat, exts=DEFAULT_MODEL_EXTS):
    return iter_files(category_dirs(cat), exts)


def iter_ytd(cat):
    return iter_files(category_dirs(cat), ('.ytd',))


def area_lod_ydds():
    """旧池 `area_lod_ydd*/*.ydd` —— 来自所有 `*_area_lod_combine` 包。"""
    out = []
    for d in sorted(glob.glob(os.path.join(PACKS, '*_area_lod_combine'))):
        out += glob.glob(os.path.join(d, '**', '*.ydd'), recursive=True)
    return out


def find(name, cat=None, exts=DEFAULT_MODEL_EXTS):
    """按模型名（不含扩展名）找文件；`cat` 为空时在**全部包**里找。"""
    want = name.lower()
    dirs = category_dirs(cat) if cat else [PACKS]
    for p in iter_files(dirs, exts):
        if os.path.splitext(os.path.basename(p))[0].lower() == want:
            return p
    return None
