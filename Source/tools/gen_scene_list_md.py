# -*- coding: utf-8 -*-
"""生成《场景对照表》：id ↔ 中文名 ↔ 类型 ↔ 规模 ↔ 有无室内。

    python -X utf8 tools/gen_scene_list_md.py

数据源（都是现有产物，不另造数据）：
  · `deliverable/blender/scenes/scene_build_status.csv` —— id / kind / name / objects / rooms
  · 生成物：`docs/世界与地编/场景对照表.md`（**禁止手改**，改数据就重跑本脚本）
"""
import csv
import io
import os

ROOT = r'D:/BrainMaker/大镖客2解包分析'
STATUS = os.path.join(ROOT, 'deliverable/blender/scenes/scene_build_status.csv')
SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(SRC, 'docs', '世界与地编', '场景对照表.md')


def main():
    rows = list(csv.DictReader(io.open(STATUS, encoding='utf-8')))
    for r in rows:
        r['_obj'] = int(r.get('objects') or 0)
    st = sorted([r for r in rows if r['kind'] == 'settlement'], key=lambda r: -r['_obj'])
    wd = sorted([r for r in rows if r['kind'] != 'settlement'], key=lambda r: r['id'])

    L = []
    L.append('# 场景对照表（id ↔ 中文名）\n')
    L.append('> **生成物，禁止手改** —— 由 `python -X utf8 tools/gen_scene_list_md.py` 生成；'
             '数据来自 `scene_build_status.csv`。\n')
    L.append('> 用途：聊天/文档里提到场景时，**id 后面一律跟中文名**（`sha`（谢迪贝莱）），'
             '避免看不懂指的是哪。\n')

    L.append('\n## 一、据点（%d 张，按对象数排序）\n' % len(st))
    L.append('| id | 中文名 | 对象数 | 室内（包/件） |')
    L.append('|---|---|---:|---|')
    for r in st:
        rooms = r.get('rooms') or '0/0'
        rooms = rooms if rooms != '0/0' else '—'
        L.append('| `%s` | %s | %s | %s |' % (r['id'], r['name'], r.get('objects') or '', rooms))

    L.append('\n## 二、野地（%d 张）\n' % len(wd))
    L.append('| id | 中文名 | 对象数 |')
    L.append('|---|---|---:|')
    for r in wd:
        L.append('| `%s` | %s | %s |' % (r['id'], r['name'], r.get('objects') or ''))

    L.append('\n## 三、代号出处（便于记）\n')
    L.append('| id | 由来 |')
    L.append('|---|---|')
    L.append('| `sdn` | SaN Denis 圣丹尼斯 |')
    L.append('| `val` | VALentine 瓦伦丁 |')
    L.append('| `bla` | BLAckwater 黑水镇 |')
    L.append('| `ann` | ANNesburg 安尼斯堡 |')
    L.append('| `van` | VAN horn 范霍恩 |')
    L.append('| `rho` | RHOdes 罗兹 |')
    L.append('| `str` | STRawberry 草莓镇 |')
    L.append('| `arm` | ARMa(dillo) 犰狳镇 |')
    L.append('| `cor` | CORnwall 康沃尔煤焦油厂 |')
    L.append('| `bra` | BRAithwaite 布雷斯韦特庄园 |')
    L.append('| `sha` | SHAdy Belle 谢迪贝莱 |')
    L.append('| `cal` | CALiga 卡利加种植园 |')
    L.append('| `dewclm` | DEWberry CReek 露莓溪 |')
    L.append('| `hso` | HorseSHOe 马掌望台 |')
    L.append('| `roc` | ROCk 威拉德之息 |')
    L.append('| `beechers`/`bee` | BEECHer\'s Hope 比彻之愿 |')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('已生成：%s（据点 %d / 野地 %d）' % (OUT, len(st), len(wd)))


if __name__ == '__main__':
    main()
