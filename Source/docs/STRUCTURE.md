# 目录结构与路径对照

> 2026-10-21 整理，2026-10-22 补 `deliverable/handoff/` 与交接文档。
> **旧路径全部仍然可用**（通过 NTFS 目录联接），现有脚本不需要改。

## 一、当前结构

```
大镖客2解包分析/
├── README.md                       总入口
├── README_骑砍2交接.md              **交给骑砍2 Agent 的数据契约**（取数路径/字段/LOD 建议）
├── STRUCTURE.md                    本文件
├── docs/                           36 篇文档
│   ├── 交接与状态/                  6 篇（含 `资源清理清单.md`）
│   ├── 世界与地编/                  11 篇
│   ├── 任务与剧情/                  8 篇
│   ├── 格式与资产/                  8 篇
│   └── 角色与物品/                  3 篇
├── deliverable/handoff/            机读交接清单（model_manifest.csv / settlements_world.csv / meta）
├── deliverable/heightmap/          权威高度图（16bit + r16 + 水掩码/水深 + meta）
├── deliverable/terrain_weights/    7 层材质权重 + 打包 RGB + 自检图
├── deliverable/blender/            Blender 成品
│   ├── continent/continent.blend   整块大陆（7.7 GB，已剔除瓜玛岛）
│   ├── guarma/guarma.blend         瓜玛岛（0.9 GB，2026-10-21 拆出）
│   ├── continent/shots/            验证截图
│   ├── sdn.blend                   圣丹尼斯基准（2.3 GB）
│   ├── interiors/ preview/ shots/ terrain/   圣丹尼斯配套
├── export/                         网站 + 数据（脚本按此路径读写）
│   ├── viewer/                     综合查看器（12 页）
│   ├── previews/                   43 城镇 3D 预览
│   ├── npc/                        408 角色 GLB
│   ├── world/                      地形数据 + lib_native 模型库（13 GB）
│   └── levels/                     世界数据（任务/据点/碰撞/gltf/城镇）
├── raw/                            原始解包素材（51 GB，可删）
├── tools/                          脚本
├── archive/                        历史文件
└── 打开查看器.bat
```

## 二、本次整理做了什么

| 动作 | 详情 |
|---|---|
| 建 `docs/` | 33 篇 `.md` 从根目录按主题分五类移入 |
| 建 `archive/` | `*.rar`、`inventory.csv`、`大镖客2地形图.png`、`Mods/`、`Mods.zip`、`textures/`、`骑砍2动画重定向/`、两个一次性 `.bat` |
| 建 `deliverable/` | `export/levels/world/blender` → `deliverable/blender` |
| 建 `assets/` | `export/world/lib_native`（13 GB 模型库）→ `assets/lib_native` |
| 去冗余 | `export/models`（4 GB 原始 ydr 池）→ `raw/models` |
| 去重名 | `sdn_city/sdn.blend` 移回上层，去掉硬链接；目录改名 `sdn_support` |
| 拆 `export/levels` | `collision`（8 GB）→ `raw/collision`；`gltf`（3.3 GB）→ `raw/gltf` |
| 建 `tools/README.md` | 145 个脚本按职责分 6 类索引 |
| `work` → `raw` | 原始素材改名，语义更清楚（"可删的原料"） |
| 保留 `export/` | 网页资源（viewer/previews/npc/world）互相引用，必须同层，不拆 |

## 三、旧路径对照（全部仍可用）

| 旧路径 | 新路径 | 兼容方式 |
|---|---|---|
| `export/levels/world/blender/*` | `deliverable/blender/*` | 联接 `export/levels/world/blender` → `deliverable/blender` |
| `export/world/lib_native/*` | `assets/lib_native/*` | 联接 `export/world/lib_native` → `assets/lib_native` |
| `export/levels/collision/*` | `raw/collision/*` | 联接 `export/levels/collision` → `raw/collision` |
| `export/levels/world/gltf/*` | `raw/gltf/*` | 联接 `export/levels/world/gltf` → `raw/gltf` |
| `work/*` | `raw/*` | 联接 `work` → `raw` |
| `export/models/*` | `raw/models/*` | 联接 `export/models` → `raw/models` |
| `根目录/*.md` | `docs/<主题>/*.md` | 无（文档无代码依赖） |

> **注意**：`export/` 与 `work/` 这两个名字仍在用，是因为 **100+ 个脚本和全部文档都按这两个路径读写**。
> 硬改会把整条流水线打断；所以采用「语义化实体目录 + 联接保留旧名」的方式：
> 真实文件在 `deliverable/`、`raw/`，旧名只是入口。

查看联接：

```bash
cmd //c dir export\levels\world | findstr blender
cmd //c dir | findstr work
```

## 四、为什么 `export/` 没有被拆开

网页三件套互相引用，路径是相对定位：

```
viewer/index.html   → ../previews/  ../world/  ../levels/town/
previews/index.html → ../world/
```

一旦把 `previews` 移出 `export/`，`../world/` 就断了。所以：

- **能搬的搬走**（Blender 文件，没人用相对路径引用）
- **有依赖的留在原地**，用 README 说明职责

## 五、建议的后续清理

见 `README.md` 的「目录职责」表，或直接：

| 档 | 内容 | 体积 |
|---|---|---|
| A | `deliverable/blender/continent/continent.blend1`（Blender 自动备份） | 7.7 G |
| B | `raw/sdn` `raw/towns` `raw/npc`（可重抽） | 43 G |
| C | `export/levels/world/gltf`、`raw/script_probe` 等 | 3.9 G |

`export/levels/collision`（8 G）建议保留 —— 骑砍2 modkit 物理碰撞要用。
