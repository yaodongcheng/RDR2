# 给「骑砍2（Mount & Blade II: Bannerlord）」Agent 的交接说明

> 本文是**数据契约**：告诉你每个东西在哪、字段什么含义、哪些坑已经踩过。
> 首次生成 2026-10-22；**本次更新 2026-11-08**（交付包核对 + 目录全图 + 贴图/模型第一版）。
> 机读版索引：`deliverable\manifests\`（`asset_import_*` / `lod_fragments.csv` / `settlements_world_v2.csv` / `world_meta.json`）
> **交付包清单（git 版）**：[交付包清单_20261108.md](交接与状态/交付包清单_20261108.md)
> **交接 TODO（未完成清单）**：[交接_TODO_20261108.md](交接与状态/交接_TODO_20261108.md)
>
> 🔴 **2026-11-08 状态（先看这条）**：
> - **57/57 子场景已全部建成并重建到最新口径**（11-07/11-08；每张 0 超界、地形自检 PASS）；
> - **旧 sdn 实验作废**（`rdr2_sanit_denis` / 5,211 个 FBX / 旧 tpac），圣丹尼斯城要按新素材重做；
> - 🔴 **模型交付主线 = TRF（带 LOD0-6 七档）**：用户 2026-11-08 裁定「按多档 LOD 跑 mesh」，
>   而 **FBX 带不了多档 LOD**（见 §0.5.3 的实测表）⇒ 模型以 **TRF 多档**为准。
> - **FBX 保留作参照**（用户同日裁定："fbx 保留，作为参照，等导入真的完全成功了再删除"）。
> - **角色 = 纯 FBX**（414 个，**无骨架、不重定向**，用户裁定）；武器/道具同样 FBX。
> - **贴图**：`textures\alb|nm|ma` 28,430 张 PNG；**DDS 后补**。
> - **骑砍2 侧的落地计划 = `Modules/LivingWorldNpcs/plans/大镖客2还原/00-总纲.md`**（本文只做数据契约）；
> - 🔴 **交付包的目录结构与现状见下一节「★ 交付物总览」——那是包的入口说明，先读它。**

---

## ★ 交付物总览：`deliverable` 目录全图（2026-11-08 实测）

> **这一节回答三件事**：包里有什么、怎么组织的、哪份能用哪份别用。
> 全包 = **约 89 GB / 180,194 个文件**（2026-11-08 实测，**新旧格式并存中**：FBX 与旧的 TRF/GLB/glTF 都在）。
> **删掉旧格式后 ≈ 60 GB / 132,000 个文件**（旧格式共约 29 GB：TRF 27.7 GB + GLB 1.3 GB + glTF/bin 0.1 GB）。
> **10 个顶层目录**。
>
> 🔴 **自包含规则（2026-11-08）**：57 张场景 blend 的贴图路径已重指到包内 `textures\` / `textures_extra\`，不再引用 `assets\lib_native\tex`；场景用到的模型在 `models\` + `models_extra\` 各有一份导出。
>
> 🔴 **三件事先记住，不然一定拿错**：
> ① **模型的交付主线 = TRF（LOD0-6 七档）**，在 `models\`；FBX 保留作参照（导入验证通过前不删）。
> ② **角色/武器/道具 = FBX**（`characters\` / `weapons\` / `items\`）；**角色不带骨架**（源 GLB 本来就没有）。
> ③ **子场景的最新摆位表还没导出** —— 现有 `placement_<id>.jsonl` 是 11-04 旧版，与 11-07 场景不一致；最新清单 `manifest_<id>.jsonl` 只有名称/类/包围盒，**没有位置和旋转**。摆位要重跑 `tools\export_scene_placements.py`。

### ★1 目录树（数量 / 体积 / 是否交付）

```
deliverable\  ≈79 GB / 128,069 files（2026-11-08 实测）
├─ blender\                                        39 GB
│  ├─ scenes\          57 张子场景（主体）          12 GB / 456 files         ★
│  ├─ continent\       大地图（v23 + v25 + 贴图池）  28 GB / 46,970 files      ★
│  ├─ regions_support\ 纠错清单 + 区域清单           268 MB / 88 files        ⚙️ 必留·不交
│  ├─ guarma\          瓜玛整岛（无地形，非场景）    298 MB / 1 file          🟡 待定
│  └─ characters\      3 个角色示例 blend           11 MB / 4 files          🟡
├─ terrain\                                        2.9 GB / 521 files（2026-11-08 去重后）
│  ├─ stages\          三种模式：00_raw / 01 / 02     53 MB / 14 files        ★
│  ├─ scene_native\    子场景原生高度 + meta（原 final） 6.1 MB / 2 files         ★
│  ├─ color_1m.png     唯一地形材质图（1 m/px）        141 MB                     ★
│  ├─ water_mask.png   唯一水网图（8.10 km²）          36 KB                      ★
│  ├─ tiles\           0.25 m/px 原生彩图瓦片        2.55 GB / 482 files      🟡
│  ├─ on_map\          对齐官方地图的裁剪版          67.2 MB / 5 files        🟡
│  └─ weights\         7 层材质权重                  42.4 MB / 13 files       ⚙️ 必留·不交
├─ textures\                                        5.9 GB / 22,736 files
│  ├─ alb\             漫反射（10,400 张）           3.6 GB                      ★
│  ├─ nm\              法线（6,586 张）              1.5 GB                      ★
│  └─ ma\              高光/ORM（5,749 张）          785 MB                      ★
├─ textures_extra\     额外贴图（场景用到、非导入）   1.8 GB / 7,712 files      ★
├─ models\            TRF 多档 LOD（交付主线）+ FBX（参照） 31.5 GB + 3.97 GB / 49,433 files ★
├─ models_extra\      额外模型（场景用到、非导入）    单档 TRF 13 GB + FBX 5.4 GB / 40,025 files ★
├─ characters\        角色/动物 FBX（纯网格，无骨架） 0.44 GB + 0.59 GB 贴图     ★
├─ weapons\           286 个武器 FBX + `.fbm` 贴图    33 MB + 72 MB              ★
├─ items\             1,196 件道具 FBX + `.fbm` 贴图  55 MB + 110 MB             ★
├─ manifests\          机读清单                      67 MB / 106 files         ★
│  └─ prefabs\         56 组 / 2,481 碎片 prefab     1.6 MB / 56 files        ★
```

**图例**：★ 交付件 · 🟡 可选/参考 · ⚙️ 不交但**盘上必须保留**（生成器输入） · ⛔ 不交（旧版/中间物）。

> 🔴 **2026-11-07 用户已删**：`blender\regions\`（9.74 GB）、`blender\willard\`（2.07 GB）、`continent_lod_split_v24_raw.blend`（1.08 GB）。
> `regions_support\` 删过又**已从回收站还原**（`region_corrections.csv` 是 `build_scenes.py` / `build_lod_groups.py` 的必需输入）。

> ⚠️ 子目录里的 `blender\README.md` 是 2026-10-27 的旧布局说明（写的是 `continent.blend` / `sdn.blend` / `willard`），**以本文 ★1~★8 为准**；`terrain\README.md` 内容仍有效。

### ★2 十个顶层目录各管什么

| 目录 | 是什么 | 怎么用 |
|---|---|---|
| `blender\` | 所有 `.blend` 场景 + 贴图池 | 打开看地编；`scenes\` 是子场景主体，`continent\tex` 是贴图池 |
| `terrain\` | 大地图地形的源与派生物 | 引擎只读 `stages\`（三种模式）+ `scene_native\`（子场景原生）+ `color_1m.png`（唯一材质图）；其余是中间物 |
| `textures\` | **3 类贴图第一版**（PNG）：`alb\` / `nm\` / `ma\` | 按 `manifests\asset_import_textures.csv` 的 name 对应；DDS 转换待做 |
| `textures_extra\` | **额外贴图**（索引 1,936 张 + blend 兜底）：场景用到、但不在导入子集 | 只服务 `models_extra` / blend 额外材质；不进游戏；索引 `textures_export_extra.csv` |
| `models_extra\` | **额外模型**：场景用到、但不在导入子集（20,012 个单档 **FBX**） | 地形块/地下/水面/占位/地形 LOD；不进游戏，只为包自包含 |
| `models\` | **模型**：单档 **FBX**（LOD0，无 LOD0-6） | 直接给 ModKit 导入；7 档 LOD 后续补 |
| `characters\` | **角色/动物 FBX**（408 个入表，414 个文件） | 纯网格、**无骨架**；贴图在同级 `<名>.fbm\` |
| `weapons\` | **286 个武器 FBX** + `.fbm` 贴图 + `weapon_assembly.csv` | 长枪是主体+部件；第一版不建骑砍2物品定义 |
| `items\` | **1,196 件道具 FBX** + `.fbm` 贴图 | 店铺/兵种/任务用品；第一版不建物品定义 |
| `manifests\` | 机读清单（模型/贴图/碎片/据点/角色/武器/道具） | 所有导入脚本的输入 |

### ★2.1 `manifests\` 里每个文件是干什么的（行数含表头）

**资产（导入用）**

| 文件 | 行数 | 内容 | 用不用 |
|---|---:|---|---|
| `asset_import_models.csv` | 24,717 | 导入子集 24,716 个模型：hash/名/mdl/面数/三贴图/场景用量/类/是否要 LOD | ✅ 主清单 |
| `asset_import_textures.csv` | 28,431 | 导入子集 28,430 张贴图：tex_id/名/文件/类型(alb/nm/ma)/引用数 | ✅ 主清单 |
| `textures_export.csv` | 28,431 | **贴图导出索引**：tex_id/name/role/source/dest/bytes（对应 `textures\alb|nm|ma\`） | ✅ 第一版 |
| `textures_export_extra.csv` | 1,937 | **额外贴图索引**（1,936 张，对应 `textures_extra\`） | ✅ 额外 |
| `textures_export_fallback.csv` | 10,153 | 重指 blend 路径时从包内池补入的额外贴图（按 blend 记录，去重后约 6,886 张） | 记录 |
| `delivery_reconciliation.json` | — | **自包含核对**：场景并集 vs 交付模型/贴图、blend 外部引用 | ✅ 验收 |
| `models_export.csv` | 24,717 | **模型主表**：name/hash/mdl/trf/faces/bytes + slots/material_count/materials/material_status/no_tex_slots | ✅ 第一版 |
| `models_export_extra.csv` | 20,013 | **额外模型索引**（20,012 个，对应 `models_extra\`） | ✅ 额外 |
| `characters_export.csv` | 409 | **角色/动物 GLB 清单**：rank/tier/cn_name/name/category/glb/dest/bytes/parts/verts/tris/textures | ✅ 第一版 |
| `weapons_export.csv` | 46 | **武器清单**：id/name/category/gltf/dest/variants/assembly_parts | ✅ 第一版 |
| `items_export.csv` | 917 | **道具清单**：id/name/category/package/gltf/dest/bytes | ✅ 第一版 |
| `material_textures.csv` | 11,206 | **材质三件套**：material/albedo/normal/ma/models/slots/status | ✅ 材质接线 |
| `model_materials.csv` | 71,841 | **模型 → 材质逐槽表**：model/trf/trf_mesh/slot/material/albedo/normal/ma/faces/verts/status | ✅ 精确对应 |
| `model_name_fix.csv` | 45 | 44 个 bigmap-only 模型的 hash→真名修正记录 | 记录 |
| `asset_inventory_models.csv` | 44,729 | 全量 44,728 个模型（含不导的类） | 对账用 |
| `asset_inventory_textures.csv` | 30,357 | 全量 30,356 张贴图 | 对账用 |
| `asset_inventory_scenes.csv` | 57 | 每场景对象/唯一模型/面数/导入面数 | ✅ 预算用 |
| `asset_inventory_summary.json` | — | 上面几张的汇总 | 对账用 |
| `mesh_texture_audit.csv` | 39,947 | 每模型的三张贴图审计（缺哪张）；⚠️ 11-05 口径，未重跑 | 查缺图 |
| `mesh_usage.csv` | 44,725 | 每模型被哪些场景用、实例数（2026-11-08 重跑） | 排导入优先级 |
| `model_manifest.csv` | 10,894 | 大地图 10,893 个模型：hash/名/mdl/面数/尺寸/实例数 | 大地图查模型 |
| `texture_list.csv` | 20,889 | 11-04 版贴图清单（已被 `asset_inventory_textures.csv` 取代） | 🟡 旧 |
| `model_ledger.csv` | 52,540 | 模型库总账（52,539，旧口径） | 🟡 旧 |

**大地图远景碎片**

| 文件 | 行数 | 内容 |
|---|---:|---|
| `lod_fragments.csv` | 2,482 | 2,481 个碎片：hash/模型/面数/三贴图/**世界位姿 + 组内局部坐标** |
| `lod_groups.json` | — | 60 条分组记录（**56 组有碎片**）：锚点/数量/面数/包围盒/成员 |
| `lod_split_parts.json` | — | 11 个跨据点合并 LOD 的拆分件 |
| `prefabs\<group_id>.json` | 56 个文件 | 按据点/野地拼好的 prefab（2026-11-08 重跑，2,481 碎片；`dow` 已补） |
| `prefabs_index.json` | — | prefab 索引（56 组 / 2,481 碎片 / 4 空组） |

**据点 / 角色 / NPC**

| 文件 | 行数 | 内容 |
|---|---:|---|
| `settlements_world_v2.csv` | 47 | **46 个据点（用这个）**：code/中英名/类型/势力/世界坐标/尺寸/uv |
| `settlements_world.csv` | 44 | 43 个据点（v1，旧，别用） |
| `settlement_audit.csv` / `.md` | 47 | 每据点实体数、≥8 m 建筑数、有网格数 |
| `settlement_scale.csv` / `.json` | 47 | 每据点规模统计（占地/建筑/密度/地标） |
| `settlement_group_stats.csv` | 188 | 按地图分块（字母组）汇总：实体数/建筑数/缺网格数 |
| `official_names_settlements.csv` | 47 | 官方中英名对照 |
| `character_names.csv` | 99 | 98 个具名角色：key/中英名/引用脚本数 |
| `perschar_roster.csv` | 951 | 950 条脚本角色花名册（区域/身份/旗标） |
| `perschar_model_pairs.csv` | 93 | 92 条「角色 ↔ 模型」对（含匹配置信度） |
| `perschar_by_zone.csv` | 50 | 49 个区域的角色分布（注册/商店/执法） |
| `npc_names_extra.csv` | 103 | 102 个补充名字（含 GLB 匹配建议） |
| `ped_archetypes.csv` | 1,087 | 1,086 个路人原型：分类/中文/是否可改名 |
| `ped_model_catalog.csv` | 1,273 | 1,272 个 ped 模型：包/压缩/被多少 modelset 引用 |
| `ambient_modelsets.csv` | 2,469 | 2,468 条环境人群配置（模型/概率/时段/距离） |
| `ambient_modelsets_summary.csv` | 972 | 按 modelset 汇总 |
| `ambient_by_group.csv` | 33 | 按 ai_memory_group 汇总 |

**元信息 / 旧产物**

| 文件 | 行数 | 内容 |
|---|---:|---|
| `world_meta.json` | — | 世界框/4 m 网格/编码公式/单位（**坐标唯一权威**） |
| `scene_rebuild_reconcile_20261105.csv` | 57 | 11-05 重建对账（一次性） |
| `sdn_flat_table.csv` | 17,434 | 旧圣丹尼斯逐图元表（🗑️ 作废） |
| `sdn_landmark_church.json` | 395 | 旧圣丹尼斯地标（🗑️ 作废） |

### ★3 子场景：一张场景 = 一套文件，认文件名就行

`blender\scenes\` 下 **57 张**（44 据点 + 12 野地 + 瓜玛）。每张场景对应固定一组文件：

| 件 | 文件 | 数量 | 现状 |
|---|---|---|---|
| 场景 | `<id>.blend` | 57 | ✅ 11-07 最新，打开即可预览 |
| 高度图 | `terrain\<id>_height_16bit.png` + `<id>_terrain.json` | 57 套 | ✅ 4 m/px、行 0 = 北；json 给世界矩形与自检结果 |
| 彩色地形图 | `tex\<id>_color.png` | 57 | ✅ 1 m/px，与高度图同一矩形（6 张野地例外，见 ★7） |
| 对象清单 | `manifest_<id>.json` + `manifest_<id>.jsonl` | 57 套 | ✅ 11-07；**只有名称/类/包围盒，没有位置旋转** |
| 裁剪报告 | `scene_report_<id>.json` | 57 | ✅ 含活动区/远景矩形、各类计数、超界检查 |
| 摆位表（旧） | `placement_<id>.jsonl` | 56（瓜玛无旧表） | ⛔ 11-04 旧版，与当前 blend 不一致，**别用** |

**命名规则**：`<id>` = 据点短码（`sdn` / `val` / `roc`…）或野地 `wild_01`…`wild_12`；场景 id 统一 `rdr2_<id>`。
**总表**：`scene_build_status.csv`（每张的对象数/耗时/状态）、`manifest.json`（最近一次构建）、`shots\`（4 张预览）。

### ★4 大地图：两个 blend + 原生高度图

| 件 | 文件 | 数字 | 用途 |
|---|---|---|---|
| **远景碎片版（主）** | `blender\continent\continent_lod_split_v24.blend` | 343 MB / **2,481 件 / 56 组** | 进游戏拼 prefab、铺远景 |
| **完整版（主）** | `blender\continent\continent_v25.blend` | **7.83 GB / 186,473 对象** | 11-08 重建：高度 = 01 未刻版、LOD append 2,436 件、分类新口径；`continent_v23.blend` 转为历史存档 |
| 碎片清单 | `manifests\lod_fragments.csv` + `lod_groups.json` + `lod_split_parts.json` | 2,481 件；**56 组有碎片**（JSON 里共 60 条记录，含 4 个空组） | 带完整变换，拼 prefab 用这个 |
| 高度图（**大地图·刻河道版**） | `terrain\stages\02_river_carve\height_16bit_4m.png` + `meta.json` | 2692×2006 @4 m；zmin −56.9 / zmax 690.3 | 01 级 + **河床加深**：水网内全部刻到水位以下（东 40.5 / 西 −22）；**只降不抬，水网外陆地不动** |
| 高度图（**大地图·未刻版**） | `terrain\stages\01_plateau_plain\height_16bit_4m.png` + `meta.json` | 同尺寸；zmin −56.9 | 原生 + 自然界过渡、**未加深** |
| 高度图（**子场景专用**） | `terrain\scene_native\height_4m_16bit_native.png` | 同尺寸；zmin −34.9 | **100% 原生 H4**，57 张子场景一律用这张（不加深、不抬升） |
| 大地图彩图 | `terrain\color_1m.png` | 10768×8024 @1 m | 导大地图地表（唯一一份） |
| 水 | `terrain\water_mask.png` / `terrain\stages\02_river_carve\water_depth.png` | 8.10 km² | **唯一水网图** + 02 的水深；Blender 大地图用**两块矩形平面**（西 −22 / 东 40.5，分割线 x=−1000） |

🔴 **2026-11-07 口径（大地图交两版，子场景只用原生）**：

| 交付件 | blend | 高度图（同目录 `meta.json` 成对使用） |
|---|---|---|
| **大地图 · 未刻河道** | `continent_lod_split_v25.blend` | `terrain\stages\01_plateau_plain\height_16bit_4m.png`（原生 + 自然界过渡） |
| **大地图 · 已刻河道** | `continent_lod_split_v25_river.blend` | `terrain\stages\02_river_carve\height_16bit_4m.png`（01 + 河床加深，东 40.5 / 西 −22） |
| **子场景（57 张）** | `blender\scenes\<id>.blend` | `terrain\scene_native\height_4m_16bit_native.png`（**100% 原生 H4**）；瓜玛用 `terrain\outside\guarma\` 的独立地形源 |

- 两版大地图的水面都是**两块水平面**：东 `x≥−1000` @ **40.5 m**、西 `x<−1000` @ **−22 m**（水位在物体变换里，顶点局部 z=0）。
- 刻河道版的做法：水网内全部刻到 `水位 − 深度`（深度按河道宽度 4~35 m）；**只降不抬，水网外陆地不动**；水面绝不跟河床抬高。
- 旧的 `heightmap\` 目录已于 2026-11-08 删除；三种模式都在 `terrain\stages\`。

### ★5 摆位数据在哪（三层，别拿错）

| 对象 | 唯一可用来源 | 带旋转/缩放？ |
|---|---|---|
| 大地图远景碎片 | `manifests\lod_fragments.csv`（`wx,wy,wz` / `qx..qw` / `sxy,sz` / `gx,gy,gz`） | ✅ |
| 大地图完整场景 | `blender\continent\manifest_continent_v25.jsonl`（`p` = 位置）或直接读 blend | ❌ 只有位置 |
| 子场景 | **blend 里的对象变换**；`placement_*.jsonl` 必须用 `tools\export_scene_placements.py` 在 11-07 场景上重跑 | ✅（重跑后） |

### ★6 不进交付 / 待重建（附体积）

| 项 | 体积 | 状态 / 为什么不交 |
|---|---:|---|
| `blender\regions\`（22 张） | 9.74 GB | ✅ **用户已删（2026-11-07）**；只影响 `tools\backfill_lod_blend.py`（一次性步骤） |
| `blender\willard\`（3 张） | 2.07 GB | ✅ **用户已删**；`scenes\roc.blend` 已覆盖（含室内） |
| `continent_lod_split_v24_raw.blend` | 1.08 GB | ✅ **用户已删**（UV 翻转前中间物） |
| `continent_lod_split_v23.blend` | 1.05 GB | ⛔ **仍在，可删**：旧 LOD 库（2,324 件 / 55 组），现用 v24 |
| `terrain\stages\02_river_carve\` | 0.17 GB | ★ **必留**：**大地图**高度图来源（01 + 河床加深）；`01_plateau_plain\` 是它的输入（无加深），`00_raw\` 是原始底图，三个都保留 |
| `blender\guarma\guarma.blend` | 0.29 GB | 🟡 **待定**：实测 2,395 个实体、**没有 Terrain / Water**，不是可进入的子场景；要么按新口径重建，要么删 |
| `miniatures\` | 18.3 MB | ⛔ **2026-11-08 已删**：脚本生成的低模代理（1/29、单 mesh 单材质、46 个共 84,502 面），**不是远景碎片**。城市缩略改用 LOD 大陆按据点分组切 |
| `map_check\`（**已移出**） | 46 MB | ⛔ **2026-11-08 移出交付**：校验产物，不导入。结论见 `docs\世界与地编\地形高度图与材质权重图.md` §5.5；两张有效证据图已移到 `docs\世界与地编\img\map_check_*` |
| `terrain\weights\` | 42.4 MB | ⚙️ **不交但盘上必须留**：`Scripts\gen_rdr2_terrain.py` / `gen_rdr2_sdn_terrain.py` 的输入 |
| `placement_*.jsonl`（56 个） | 69 MB | ⛔ 11-04 旧摆位 —— **不是删，是重跑**（交付前用 11-07 场景重出） |
| `manifests\sdn_flat_table.csv` + `sdn_landmark_church.json` | 4.1 MB | ⛔ 旧圣丹尼斯实验产物 |
| `manifests\settlements_world.csv`（v1） | 0.01 MB | ⛔ 已被 `settlements_world_v2.csv` 取代 |

> 🔴 **`blender\regions_support\` 不许删**（0.26 GB）：`region_corrections.csv`（343 行）+ 22 个区域清单是 `build_scenes.py` / `build_lod_groups.py` 的必需输入；2026-11-07 删过一次，已从回收站还原。

**可选瘦身**：贴图池 46,901 张里有 **24,397 张（5.17 GB）** 没被导入清单引用；重跑引用审计后再删。

### ★7 已知不一致（交付前必须修，别当数据错误去查）

| # | 问题 | 实测 |
|---|---|---|
| 1 | ~~6 张野地的高度图与彩图矩形不一致~~ | ✅ **2026-11-08 已修**：高度图裁到彩图/地图框同一矩形；6 张全部 `mismatch 0` |
| 2 | ~~prefab 落后一版~~ | ✅ **2026-11-08 已重跑**：56 组 / 2,481 碎片；`dow` 已补 |
| 3 | ~~资产清单是 11-05 的~~ | ✅ **2026-11-08 已重跑**：摆位按当前 57 张场景重出，`asset_inventory_*` / `asset_import_*` 随之更新 |
| 4 | ~~blend 贴图路径指向包外~~ | ✅ **2026-11-08 已重指**：57 张全部指向包内 `textures` / `textures_extra`；`lib_native` 引用 = 0 |
| 5 | ~~完整版大地图的 LOD 是旧的~~ | ✅ 已解决：`continent_v25.blend`（11-08 重建，LOD append 2,436 件 / 高度 = 01 未刻版） |

### ★8 接手顺序（读什么 → 做什么）

1. 读 `manifests\asset_import_models.csv` / `asset_import_textures.csv` → 知道要导哪些模型和贴图；**第一版已按清单导出**：`models\*.trf` 24,716 个（单档）+ `textures\alb|nm|ma` 28,430 张 PNG，可直接导 ModKit。
2. 读 `manifests\lod_fragments.csv` + `lod_groups.json` → 拼大地图 prefab（唯一带完整变换的表）。
3. 读 `blender\scenes\<id>.blend` + `terrain\` + `tex\` → 建场景（先 `sdn` → `val` → 批量）。
4. 读 `scene_report_<id>.json` → 拿活动区/远景矩形；摆位用重跑后的 `placement_<id>.jsonl`。
5. **大地图**地形用 `terrain\stages\02_river_carve\height_16bit_4m.png` + `terrain\color_1m.png`；**子场景**地形用 `terrain\scene_native\height_4m_16bit_native.png`（原生 H4）。水用 `terrain\water_mask.png`。

---

## 0. 三条铁律（先看，能省你三天）

1. **坐标系**：RDR2 世界是 **X 东、Y 北、Z 上**，单位 **米**，地图框
   `x ∈ [−6844, 3924]`、`y ∈ [−4800, 3224]`（10 768 × 8 024 m = 86.4 km²）。
   所有位图 **行 0 = 北**。骑砍2 的 up 轴与 RDR2 不同，**必须先做 §2.3 的标定场景再批量导**。
2. **别把 20 万个实例按 LOD0 全摆进去**：那是 **300 M+ 三角面**（实测），任何引擎都跑不动。
   按 §7 的分级/剔除策略做，目标是单个城镇场景 ≤ 60 万面。
3. **网格只有 HD，没有 LOD 链**：10 893 个可加载 archetype 里 10 076 个有网格（**92.5%**，缺 817 个），
   且每个只有一份**最高精度**网格。缩略模型/LOD1~6 **需要你自己减面生成**（§7 给了预算表）。

---

## 0.5 素材总表：本项目给骑砍2 什么（2026-11-03 更新）

**一句话**：给的是「世界怎么摆 + 长什么样 + 有谁 + 干什么」四件事；**只有地编和建筑模型做成了可用资产**，其余是研究结论与提取管线，还没成包。

| 类别 | 现有产物 | 骑砍2 用途 | 状态 |
|---|---|---|---|
| ① **世界与地编** | `docs/世界与地编/scene_list.csv`（58 行）+ `scene_specs.json`（P 多边形）+ 高度图/彩图 + `deliverable/blender/scenes/`（**57 张 blend**） | 建 57 张场景、接入口、扎营落点 | ✅ **57/57 已建成**（11-07/11-08，0 超界、地形图全 PASS）；**等用户验收（TODO-6）** |
| ② **建筑/道具模型** | 全量清单 `deliverable/manifests/asset_import_models.csv`（**24,716 个模型**）+ `asset_import_textures.csv`（**28,430 张贴图**） | 场景里的房子/道具/铁路/植被… | ✅ **2026-11-08 已改 FBX**：`models\` + `models_extra\` = 44,728 个 `.fbx`（单档 LOD0）+ `textures\alb|nm|ma` PNG；正式 7 档 LOD / DDS 后补 |
| ③ **角色外观/服饰/人头** | `docs/角色与物品/RDR2_服饰全清单与换装修复.md`、`RDR2_角色眼睛与服饰贴图修复.md`、`docs/格式与资产/RDR2骨架_yft格式.md` | 让 NPC / 主角长得像大镖客 | ✅ **2026-11-08 已改 FBX**：`characters\` 414 个 `.fbx` + 同级 `.fbm\` 贴图；🔴 **不绑骨架、不重定向**（用户裁定） |
| ④ **武器/道具/载具** | `docs/角色与物品/RDR2_武器道具模型与剧本对白.md`、`RDR2_武器金属材质修正.md`、`RDR2_载具与UI与兵种覆盖审计.md`、`RDR2_模型图标与综合查看器.md` | 武器、道具、载具、图标 | ✅ **2026-11-08 已改 FBX**：`weapons\` 286 + `items\` 1,196 个 `.fbx`（带 `.fbm\` 贴图）；未建物品定义 |
| ⑤ **NPC 名单与组织** | `docs/世界与地编/RDR2_NPC名单与环境人群表.md`、`RDR2_NPC生成与行为机制.md`、`docs/格式与资产/RDR2_本地化文本与NPC池.md`、`docs/角色与物品/RDR2_骑砍2落地_势力与NPC.md` | 每个城镇有哪些 NPC / 身份职业 / 势力归属 / 生成规则 | 🟡 **研究完成**，未做成数据表 |
| ⑥ **剧情/任务/动画/音频** | `docs/任务与剧情/`（12 篇：主线 AVG 化、任务逐步骤拆解、随机任务搬运方案、音频与过场可行性）；`docs/格式与资产/RDR2_ycd动画解码.md`、`HANDOFF_动画与蒙皮.md` | 任务链、过场、对话、动画、BGM | 🟡 研究/方案阶段 |

### 0.5.1 场景划分的正式接口（建场景就读这两份）

**主入口 = `docs/世界与地编/scene_list.csv`（57 行，一行一张子场景）**

| 列 | 用途 |
|---|---|
| `kind` | `settlement` / `wild` / `guarma` |
| `id` / `code` | 场景键（据点用 code，野地 `wild_01..12`） |
| `x,y` | **场景中心（世界坐标）**；场景局部坐标 = 世界 − 中心；1 单位 = 1 m，Y+ 朝北 |
| `活动区宽_m` / `活动区高_m` | **玩家活动区**：玩家走得到的地面（地形精细区，引擎硬边界在这里） |
| `每边外扩_m` | 活动区外面再铺多宽的远景 |
| `远景宽_m` / `远景高_m` | **远景范围** = 活动区 + 2 × 每边外扩（只做背景，走不到） |
| `P_area_km2` | 能走范围面积（对账用） |
| `scene_name` | 建议场景 id：`rdr2_<code>` / `rdr2_wild_NN` |

> **两层口径（2026-11-03 定，2026-11-04 修）**：场景只有「玩家活动区」+「远景范围」，旧的 P / T / O 三个字母作废。活动区宽高与每边外扩都是 **128 的倍数**。**地形精度：全场 4 m**（活动区和远景同一精度，不再分 16 m 一档）。

**要几何时读 `scene_specs.json`**：`settlements[i].P` / `wilds[i].P` = 能走范围（环列表；野地是 4 角矩形）；`AW/AH/FW/FH` = 活动区/远景范围；`frame` = 地图框；`outside` = 地图外（只做远景）；`gaps`/`overlaps`/`issues` 只给页面看，**建场景不用**。

**尺寸分布**：据点活动区 512 / 640 / 768 / 896 / 1,024 / 1,152 / 1,536（圣丹尼斯），每边外扩 512 / 640 / 896 / 1,280；野地活动区 = 矩形本身（1,792–4,352），每边外扩 1,024；**瓜玛 1 张**：活动区 1,280×1,152、外扩 128、远景 1,536×1,280（2026-11-08 已建）。

**规则（用户裁定）**：据点能走范围 = 外切矩形（互不重叠）；野地 = 横平竖直矩形（**宁可重叠不留缺口**）；野地矩形含据点范围（野地场景里据点用 `C_lod_远景碎片`，走进据点弹「是否进入」）；地图区 = 官方地图有画面的部分（空白羊皮纸只做远景，水面算可走）。

**数据源头**：`docs/世界与地编/scene_overrides.json`（用户手画的分区，进 git，丢了不可重建）；`scene_specs.json` 是它 + 脚本跑出来的生成物。

### 0.5.2 大地图城镇缩略图：远景碎片分组（2026-11-03）

**一句话**：大地图上每个据点用一个 **远景碎片 prefab** 表示。碎片已经按空间分好组，
**一个据点一组**，直接用，不用自己从 `bldg` 重新裁或减面。

| 文件 | 内容 |
|---|---|
| `deliverable/manifests/lod_fragments.csv` | 一行一个碎片：`frag_id / group_type / group_id / scene_name / sub_group / name / hash / mdl / tris / verts / tex_albedo / tex_normal / tex_ma / wx,wy,wz / qx..qw / sxy,sz / gx,gy,gz / bbox / wild_scene / assign_via` |
| `deliverable/manifests/lod_groups.json` | 每组汇总（数量 / 面数 / 唯一模型 / 包围盒 / 子组 / 成员 id） |

**口径**（规则唯一实现 = `tools/build_lod_groups.py`，详见 `docs/世界与地编/RDR2_据点分级与场景边界方案.md` §8.1）：

- **1,309 个碎片 → 据点**（44 个据点里 **42 个有碎片**，`twi` / `abe` 为空）；**1,127 → 12 块野地**；45 → 瓜玛；合计 **2,481 件**。
- **合并 LOD 已按据点边界切开**（5 块 → 11 件）：`new_area_slod4` → 圣丹尼斯 + 西西卡监狱，
  `nopq_11_14_area_slod4` → 卡利加/罗兹/布雷斯特/圣丹尼斯，`rstu_96_99_area_slod4` → 风滚草/犰狳镇，
  `nopq_07_10_area_slod4` → 黑水镇（余量空），`bra01pr_combo10_slod` → 罗兹/布雷斯特；
  拆分件在 CSV 里带 `part_key` 列。
  🟢 `*_area_slod*` 是**建筑/道具的整区合并 LOD**，不是地形。
- **2 个小点位没有远景碎片**：`twi` 双岩 / `abe` 阿伯丁猪场 ——
  各只有 2~11 个高清建筑。**2026-11-08 口径**：从完整版 `continent_v25.blend` 按同一口径补采进 LOD 分组，
  **不再用微缩模型兜底**。`dow` 唐斯牧场在 11-05 分组里已有碎片。
- `sub_group` 五类：`bldg` 建筑/道具 · `interior` 室内 · `rail` 铁路与地形格 · `veg` 植被 · `block` 大区块。
- `gx,gy,gz` = 相对组锚点的局部坐标，**拼 prefab 直接用这三个数**（锚点 z 是地面高程）。
- 世界坐标 = RDR2 的 Z-up；进骑砍2 前仍要按 §2.3 做轴映射。
- **野地场景**取碎片按 `wild_scene` 列（含据点那 1,309 个），不要只取 `group_type=wild`。

### 0.5.3 全量资产清单与导入口径（2026-11-05）

**清单（大地图 ∪ 57 张子场景）**

| 文件 | 内容 |
|---|---|
| `deliverable/manifests/asset_inventory_models.csv` | 全量 **44,728 个模型**：hash / 名称 / 面数 / 贴图 / 场景用量 / 大地图用量 / 分类 / 是否需 LOD |
| `deliverable/manifests/asset_import_models.csv` | **导入子集 24,716 个模型**（按 21 类筛，见下；其中 10,370 个 ≥2,000 面要做 LOD） |
| `deliverable/manifests/asset_inventory_textures.csv` / `asset_import_textures.csv` | 全量 **30,356 张** / 导入 **28,430 张贴图**（类型、文件、大小、模型/实例用量） |
| `deliverable/manifests/asset_inventory_scenes.csv` | 每场景：对象 / 唯一模型 / 三角面 / **导入面数** |
| `deliverable/manifests/asset_inventory_summary.json` | 汇总（含大地图碎片 / 微缩模型） |

**导入范围（21 类，2026-11-05 用户裁定）**

- **导（16 类）**：`bldg / part / prop / junk / veg / rock / stone / struct / ruin / veh /
  rail / rail_decal / road / decal / unknown / lod_out`；
- **不导（6 类）**：`terrain_cell / terrain_lod / underground / watertile / placeholder / lod`。

**导入口径**

🔴 **2026-11-08 用户裁定（当天两次，后一次覆盖前一次）**：
① 先要"只认 FBX"；② 看过「FBX 带不了多档 LOD」的实测后改为
**"按多档 LOD 跑 mesh，但 FBX 保留作参照，等导入真的完全成功了再删除"**。
⇒ **模型的交付主线 = TRF（LOD0-6）；FBX = 参照件；角色 / 武器 / 道具 = FBX。**

模型（**TRF，多档**）：

- `deliverable/models/<name>.trf`（24,716），由 `tools/export_rdr2_trf_lod.py` 从 `.mdl` 直出；
- 命名（引擎约定，见 `plans/rules/wheels.d/assets.md` §28.4）：
  `<名>.<子网格序>` = **LOD0**；`<名>.lod<N>.<子网格序>` = 第 N 档；
- 比率 `RATIOS = [1.0, 0.50, 0.30, 0.19, 0.12, 0.12, 0.12]`（LOD5/6 复用 LOD4 的 12%）；
- **只给 ≥2,000 面的模型出多档**（小件只出 LOD0，原版也是小件不做 LOD）；
- 🔴 **只在室内用的模型（3,518 个）特殊处理**：LOD0-2 正常，**LOD3-6 压成包围盒**（每材质件 12 面）。
  清单 = `manifests\interior_only_models.txt`；判据 = `placement_*.jsonl` 的 `int_pkg` 非空。
  **内外都用的 1,642 个不做处理**（家具类，砍了室外就少东西）。
  依据 = 原版实测（`archhitecture_empire.tpac` 534 个 Metamesh：**0 个用空网格**，
  远档是 2~12 面的小片；室内在原版是**独立场景**）。我们场景室内外合并 ⇒ 用"27 米外缩成小盒子"近似，
  **不用"虚空"**（大厅里会开天窗）；
- 减面配方（2026-10-26 实测唯一能看的组合）：先 `remove_doubles(0.002)` + `normals_make_consistent`，
  再 `DECIMATE/COLLAPSE`；**逐材质拆子网格再减**，不丢零件；
- 材质名 = **albedo 贴图名原样**（TRF 是纯文本，**没有 63 字符上限**）；
- 坐标 = `.mdl` 局部坐标（米，Z 上），UV 的 V 翻成 `1-v`。
  🔴 **2026-11-09 实机 A/B 定案：引擎按左下原点采样，TRF 里必须写 `1-v`（原始 `.ydr` 是左上原点）。**
  **翻转必须全档一致**：统一在 `read_mdl()` 里翻一次，`make_part()` 不再翻。
  历史 bug（已修）：旧版只在 `make_part()` 里翻 ⇒ **LOD0 用原始 v、LOD1-6 用 `1-v`**
  （实测 972 个对位顶点里 971 个翻转），表现为「同一模型**近处**采到 V 镜像的另一块图、中远景正常」
  （圣丹尼斯花园十字消失就是它，不是 U/V 对调、也不是贴图旋转）。
  判据：拿贴图里一个**圆形**特征做 A/B —— 同一网格出 4 个单档 TRF（raw / vflip / uflip / uvswap），
  只有 `vflip` 出正圆；本例花园在贴图里是 52×24 px 横椭圆，正确落地 39.0×38.5 m（比值 1.01），
  换 U/V 或转 90° 会变成 2.3:1 的横椭圆。

模型（**FBX，参照件**）：`models/<name>.fbx`，单档 LOD0，Z 上/米，材质名 = albedo 贴图名
（>63 字符的走 `manifests/material_alias.csv` 别名）。**导入链路验证通过之前不删。**

角色 / 武器 / 道具（**FBX**）：

- `characters/**/<name>.fbx`（414）+ 同级 `<名>.fbm\` 贴图；**纯网格、无骨架、不重定向**；
- `weapons\` 286 + `items\` 1,196 个 `.fbx`，同样带 `.fbm\`。

贴图池：`deliverable/textures/alb|nm|ma/<name>.png` = 28,430 张 PNG（**DDS 转换待有 texconv 再做**）。

清单：`models_export*.csv` 有 `trf` / `trf_faces` / `lod_faces` / `lod_levels` / `fbx` 等列。

**校验（可复核）**：

```powershell
blender -b --factory-startup -P "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source\tools\_check_rdr2_fbx.py" -- --set import --sample 40
```

把 FBX 导回 Blender，与 `.mdl` 头比**材质名（含别名）/ 包围盒（严格）**、**面数（容差 0.2%）**。
面数容差是给「退化三角被 Blender 丢掉」留的（实测 80 个里 2 个差 1~2 个面）。
实测：模型 80/80 PASS、额外模型 40/40 PASS。

**FBX vs TRF 的材质能力（2026-11-08 实测，直接回答"槽位材质名"）**：

| | FBX | TRF（`rfver 4`） |
|---|---|---|
| 每个槽位能不能指定材质名 | ✅ 能：网格带材质槽数组，每个多边形有 `material_index`；实测 36 槽模型逐槽面数与 `.mdl` 完全一致 | ⚠️ 能写：mesh 头是 `名字 0 材质1 [材质2 …]`，**但面记录只有 `i j k`，没有材质索引** ⇒ 一个 mesh 内没法按面选材质，实际要**一个材质拆一个 mesh** |
| 名字长度 | ❌ **63 字符上限**（超了截断+哈希）⇒ 需要 `material_alias.csv` | ✅ **纯文本，无长度上限** |
| 多档 LOD | ❌ 带不了（见下） | ✅ 能（`<名>.lodN.<i>`） |
| 体积 | 小（同模型约为 TRF 的 1/4） | 大（纯文本） |

正式口径（**待做**）：
- **7 档 LOD**：主网格仍是 FBX，LOD0-6 怎么组织（一个资产挂多级 vs 多个 FBX）**还没定**，
  等 ModKit 里试导一个样板后定；
- 🔴 **已知硬约束（2026-10-26 实测，见 `plans/rules/wheels.d/assets.md` §28.4）**：
  **FBX 带不了多档 LOD** —— 把 `<名>_lod` 当独立文件导入时编辑器会按 `<名>` 注册、撞名直接跳过，
  永远不会合并成多档；**只有 `.trf` 能按 `<名>.lodN.<i>` 命名还原多档**。
  ⇒ "只交 FBX" 与 "7 档 LOD" 目前是**互斥**的，要么只交单档，要么 LOD 这条线破例用 TRF。
  **待用户裁定**（11-08 未决）。
- 贴图 = **DDS**（落地 DXT5，与 PNG 一致；源文件更小）；
- 🔴 **旧 FBX 路径（`rdr2_bld_fbx` / `rdr2_sanit_denis` / 旧 tpac）作废**，不要再按它导。

---

## 0.6 场景交付规范 + 后续 TODO（2026-11-04 用户裁定）

### A. 一共多少张（59）

| 类别 | 数量 | 说明 |
|---|---:|---|
| 大地图 | **1** | 战役地图（已有 `continent_lod_split_v23.blend` 预览，用户基本满意） |
| 据点子场景 | **44** | 一个据点一张 Mission |
| 野地子场景 | **12** | 一块矩形一张 Mission |
| 瓜玛 | **1** | 两处相距约 342 m，**合并成一张**；活动区 1,280×1,152（有网格区域外接矩形）、远景 1,536×1,280（2026-11-08 已建） |
| **合计** | **58** | **57 张子场景** + 1 张大地图 |

### B. 每张子场景交付 5 件

| # | 交付物 | 规格 | 现状 |
|---|---|---|---|
| 1 | **高度图** | 16 bit PNG（或 raw），**4 m/px**，行 0 = 北；范围 = 该场景远景范围（按全局 4 m 格点取整） | ✅ 已出：`deliverable/blender/scenes/terrain/<id>_height_16bit.png`（57 张） |
| 2 | **彩色地形图**（1 m/px） | RDR2 只有单层地表色 → 直接用烘好的彩图；**不再出 8 bit 全 255 的 mask**（2026-11-07 用户裁定："白图没有有效信息"） | ✅ 已出：`tex\<id>_color.png`；`<id>_terrain.json` 的 `color_png` 指过去 |
| 3 | **场景 blend** | 打开即可预览（地编信息全在里面） | ✅ **57/57 已建**（11-08；57 个 blend 合计约 11.7 GB） |
| 4 | **对象摆放清单** | 一行一个对象：模型 hash / 位置 / 旋转 / 缩放 / 分类 / 是否远景 | ⚠️ 现有 56 个 `placement_<id>.jsonl` 是 **11-04 旧版**，与 11-07 场景不一致 → **必须重跑** `tools\export_scene_placements.py`；当前最新的 `manifest_<id>.jsonl` 只有名称/类/包围盒，**没有摆位** |
| 5 | **网格库 + 三类贴图** | 全局一份：漫反射（alb）/ 法线（nm）/ 高光（ORM、`_ma`） | ✅ `mesh_texture_audit.csv` + `texture_list.csv`（`tools/audit_mesh_textures.py`） |

### C. 每个子场景里放什么（两层，规则固定）

- **远景碎片分两类**（2026-11-04 用户裁定，分类层面拆分）：

  | 类 key | 中文 | 内容 | 默认 |
  |---|---|---|---|
  | `lod` | 远景碎片 | **活动区内**的远景碎片 | **隐藏**（保留在 blend 里，不删） |
  | `lod_out` | 远景碎片·区外 | **活动区外**的远景碎片 | **显示**（不碰撞、不寻路、不投影） |

- **玩家活动区内**：**原始模型**（bldg / prop / part / struct / veh / rail / ruin …）。
- **活动区外（远景范围）**：只有 `lod_out`。
- `lod_out` 是**按几何改标**的：名字规则永远判不出它，由场景裁剪按"是否在活动区外"改 `cls_key`；
  大陆 / 旧分区里这个类永远为空，不受影响。
- **跨边界的碎片**：留在 `lod`（隐藏），不裁不删。
- 远景碎片**大量复用**：全局只存一份模型，各场景只存引用（摆位）。

### D. 大地图

- 需要**全部远景碎片**；
- **按据点组织成 prefab**：已经有现成的
  `deliverable/manifests/lod_fragments.csv` + `lod_groups.json`（**2,481 碎片 → 56 组**），
  拼 prefab 直接用其中的 `gx,gy,gz`（相对组锚点）。

### E. 预览硬门槛（每条都要能当场验）

1. 每张子场景 `.blend` 打开即可预览（打开方式：把 blend 拖到 `打开大陆_流畅.bat` 上）；
2. **活动区内看不到远景碎片**；活动区外远景碎片**默认显示**；
3. 分类面板可用（物体属性 →「分类（LWN）」），植被 / 地形块 / 贴花等按默认隐藏；
4. 贴图 0 缺失（不出现品红）。

---

## 0.7 TODO（按顺序做，做完一条勾一条）

| # | 事项 | 改哪里 | 验收（可复核） |
|---|---|---|---|
| **TODO-0** | **远景碎片两类落地**：分类器新增 `lod_out`（远景碎片·区外，默认显示）；场景裁剪把"完全在活动区外"的碎片改标为 `lod_out`，活动区内保持 `lod`（默认隐藏）；跨边界留在 `lod`；**不删对象** | `tools/class_rules.py` + `tools/scene_trim.py` | 打开 `bla.blend`：分类面板有 `远景碎片` / `远景碎片·区外` 两行；活动区内看不到 lod；活动区外可见；地形回归点 PASS |
| **TODO-1** | 用修好的口径**重建 58 张子场景 blend** | ✅ `tools/build_scenes.py` | ✅ **57/57 done**（含瓜玛）：全部 0 超界、地形自检 PASS、`rooms` 已入表；远景碎片来自打散分组远景库 |
| **TODO-2** | 每张场景出**高度图 + 彩色地形图** | ✅ `tools/export_scene_terrain_maps.py`（已接进 `build_scenes.py`） | ✅ 57 张全 PASS：高度图与 blend 同一套采样；**2026-11-08 高度图裁到彩图同矩形，6 张野地 mismatch 已归零** |
| **TODO-3** | 出**全局网格库清单 + 三类贴图清单** | ✅ `tools/audit_mesh_textures.py` | ✅ 清单在 `mesh_texture_audit.csv` / `texture_list.csv`；⚠️ 这两张仍是 11-05 口径，未随 11-08 重跑。🔴 **缺 albedo 是已知接受缺口**（扫 25 个 props 包 + `gtxd.rpf` + 3,696 个 ytd 全无，用近似色代替），**不要再重新解包** |
| **TODO-4** | 每场景出**对象摆放清单**（供骑砍2 生成 xscene） | ✅ `tools/export_scene_placements.py`（2026-11-08 已在当前 57 张场景重跑） | ✅ 57 个 `placement_<id>.jsonl` + `mesh_usage.csv` 已更新（字段含 loc/quat/scale/bbox/part_key/split_of/int_pkg/tile） |
| **TODO-5** | 大地图**按据点分组的 prefab** | ✅ `tools/build_lod_prefabs.py`（2026-11-08 重跑） | ✅ **56 组 / 2,481 碎片**，`dow` 已补；4 个空组（`abe` / `twi` / `none` / `span`） |
| **TODO-6** | 用户逐张预览确认 | — | 用户点开任意 3 张（大/中/小各一）说"可以" |

> 顺序硬约束：**TODO-0 不过，不要开 TODO-1 的批量**；TODO-1 不全过，不进入 TODO-2~5。

---

## 1. 取数总表（"我要什么 → 去哪拿"）

| 你要的 | 路径 | 规格 | 备注 |
|---|---|---|---|
| **大地图高度图（刻河道版）** | `deliverable/terrain/stages/02_river_carve/height_16bit_4m.png`（编码见同目录 `meta.json`） | 2692×2006，4 m/px，16 bit，行 0 = 北；zmin −56.9 | 01 自然过渡 + **河床加深**（水网内刻到水位以下；水网外低地 +1 m） |
| **大地图高度图（未刻版）** | `deliverable/terrain/stages/01_plateau_plain/height_16bit_4m.png` | 同尺寸；zmin −56.9 | 原生 + 自然界过渡，未加深 |
| **子场景高度图（16 bit）** | `deliverable/terrain/scene_native/height_4m_16bit_native.png` | 同尺寸；zmin −34.9 | **100% 原生 H4**，57 张子场景一律用这张 |
| 高度图 r16（引擎直读） | 两个 stage 目录下的 `height_r16.raw` | 同尺寸，uint16 **小端**，逐行 | 与同目录 PNG 逐值一致，行 0 = 北 |
| 高度图元数据 | 各 stage 目录的 `meta.json` | zmin/zmax/公式/原点 | 换算公式见 §3.1 |
| 水面 / 水深（参考） | `deliverable/terrain/water_mask.png`、`deliverable/terrain/stages/02_river_carve/water_depth.png` | 2692×2006 | 水面 8.10 km²；与 `terrain/weights/w_water.png` **同一张** |
| **地形材质权重（7 层）** | `deliverable/terrain/weights/w_{grass,conifer,rock,dirt,broadleaf,water,snow}.png` | 2692×2006，4 m/px，8 bit，行 0 = 北 | 逐像素归一化，**和高度图逐像素对齐** |
| 权重（打包成 RGB） | `deliverable/terrain/weights/weights_rgb_{1,2,3_snow}.png` | 同上 | R草G针叶B岩 / R泥G阔叶B水 / 雪 |
| 权重元数据 + 自检 | `deliverable/terrain/weights/weights_meta.json` | 阈值/统计 | 水面与地形水体 **IoU = 1.000** |
| **大地图彩图（包内）** | `deliverable/terrain/color_1m.png` | 10768×8024，**1 m/px**，RGB（已裁到地图框） | 直接从包里取；源 `export/world/world_ground_final_out.png`（12296²，含外延补边）在包外，仅备查 |
| 地面彩图（高清） | `export/world/world_ground_2p0.png` | 24592×24592，**0.5 m/px**，RGB | 细节最好，但**外延区 16.8% 是空的**（见 §4.3） |
| 合成色（低分辨率备用） | `export/world/world_color_4096.png` | 4096²，3 m/px | 顶点色/远景混合用 |
| **建筑/网格实例（位置+旋转+缩放）** | `export/world/continent/tiles/*.json`（43 块） | 每块一个数组 | **200 303 条**，字段见 §5.1。**注意：其中约 25%（50 007 条）没有对应模型**（未命名部件尚未抽回），别按"应该都有"来做容错 |
| 实例分块索引 | `export/world/continent/index.json` | 43 块 + 尺寸档统计 | 按 2000 m 方块切 |
| **模型清单（推荐入口）** | `deliverable/manifests/model_manifest.csv` | 10 893 行 | hash/名字/mdl/面数/尺寸/贴图/实例数，**一张表查全** |
| hash → 原始 ydr 路径 | `export/world/continent/models.json` | 10 893 条 | 需要回到原始资产时用 |
| **模型库索引** | `assets/lib_native/index.json` | **52 566** 模型 / 7 065 贴图 | `models{hash:{f,b,s}}` + `tex[{id,n,f}]` |
| **网格本体** | `assets/lib_native/<hh>/<hash>.mdl` | RMDL1 二进制，float32 | 格式见 §5.3（自带读取器） |
| **贴图** | `assets/lib_native/tex/<id>.png` | ≤512²，PNG，几乎都带 alpha | 只有 albedo，见 §5.4 |
| **据点坐标（43 个）** | `deliverable/manifests/settlements_world.csv` | 43 行 | 世界 x/y + 尺寸 + 势力 + 依附关系 |
| 区域/城镇多边形 | `export/levels/world/zones.json` | TOWN 多边形等 | 铺路面、划场景边界用 |
| 碰撞体 | `raw/collision/<area>_static_collision/*.ybn` | 30 个包 / **12 301** 个 | **还没有转换器**（§8） |
| NPC 模型 | `export/npc/**/*.glb`（**412 个**：354 角色 + 动物） | GLB 内嵌贴图，2.1 GB | 立即可用，清单 `export/npc/index.csv` |
| 任务/对白/步骤 | `export/levels/world/mission_*.csv|json` | 270 条任务、41 005 行对白 | **没有场景坐标**（§6.2） |
| 整块大陆（Blender） | `deliverable/blender/continent/continent.blend` | **8.95 GB** | 已在引擎外验证过装配正确。`ENTITIES` 112 653 + `RAILCELLS` **1 359**（铁路，2026-10-27 装回） |

---

## 2. 坐标与单位

### 2.1 世界 ↔ 像素（三个分辨率别混）

```
高度图 / 权重 / 水面   4 m/px：  col = (x − (−6844)) / 4        row = (3224 − y) / 4
地面彩图（完整）       1 m/px：  px  = x − (−7684)              py  = (−8196 + 12296) − y = 4100 − y
地面彩图（高清）       0.5 m/px：px  = (x + 7684) × 2            py  = (4100 − y) × 2
```

- 高度图/权重：原点 **(x0, y1) = (−6844, 3224)**，尺寸 2692×2006。
- 地面彩图：覆盖 **整块 12 296 m 世界**（原点 x=−7684, y 从 4100 往下），不止地图框，
  所以取地图框内的彩图要 crop：`(840, 876) → (11608, 8900)`（1 m/px）。
- 单位一律 **米**，Z=0 是海平面参考，**负值是海床/湖底**（最深 −34.9 m）。

### 2.2 实例数组字段（`tiles/*.json`）

```
[ hash, x, y, z, qx, qy, qz, qw, sxy, sz, cls ]
   0     1  2  3    4   5   6   7    8    9   10
```

| 字段 | 含义 |
|---|---|
| hash | archetype 哈希（`0x%08x`，对应 `models.json` / `index.json` 的键） |
| x, y, z | 世界坐标（米），z = 底部落点高度（已按模型 bbox 修正） |
| qx..qw | 四元数，**顺序是 (x, y, z, w)** —— 注意 Blender 要 (w, x, y, z)，别搞反 |
| sxy, sz | 水平缩放 / 垂直缩放（缺失时按 1.0） |
| cls | 尺寸档：3 = ≥8 m，2 = 4~8 m，1 = 1.5~4 m，0 = <1.5 m（决定要不要进 LOD/剔除） |

### 2.3 到骑砍2 的轴映射：**必须先标定，别猜**

RDR2 是 **Z-up**；骑砍2 的 `Vec3` 与世界朝向约定与它不同，直接套 (x, y, z) 会把整座城放倒。
推荐做法（一次性，约 10 分钟）：

1. 在骑砍2 场景里放一个 **1000 m × 1000 m 的参照地面**，原点立一根 **10 m 高的柱子**，
   在 +X / +Y / +Z 三个方向各放一个 1 m 立方并染成红/绿/蓝。
2. 用 `tiles` 里取一处已知地标（建议 **瓦伦丁**：世界 (x≈−400, y≈1100)），
   读 3~5 个实例的坐标，按你猜的映射摆进去，看是否落在正确位置。
3. 三选一试到对上为止（常见两种）：
   `(x, y, z)_rdr2 → (x, z, −y)_bl` 或 `(x, z, y)_bl`；朝向再单独确认（四元数要么换轴序、要么取逆）。
4. 固定下来写进你们自己的 `README`，之后所有脚本只用这一套。

> 我们的 `continent.blend` 里装配是按 Z-up 做的，可以在 Blender 里直接看"正确的样子"，用它当参照。

---

## 3. 高度图怎么用

### 3.1 数值换算

```
z(m) = zmin + v / 65535 × (zmax − zmin)
zmin = −34.9308 m      zmax = 690.3470 m
```

- **不要过 8 bit**：747 m 量程 / 255 ≈ 3 m 一档，地形会出现明显台阶。16 bit 直读或 r16 直读。
- PNG 与 `r16.raw` **逐值一致**（同尺寸、同行序、小端 uint16）。

### 3.2 分块建议（骑砍2）

- 单块 **2000 m × 2000 m**（和我们的实例分块一致，一望即知取哪块）；
  2000/4 = **501 个采样点**（用 4 m 网格，不要重采样到 2 m 假装更精细——源数据就是 4 m）。
- 现有实例已按 **世界网格**（原点 x=−7684、每 2000 m 一格）切好：**7×7 网格里 43 块非空**，
  最大一块 27 208 个实例、最小 34 个（`continent/index.json` 的 `tile_list` 有完整清单）。
- 每块只带该块高度 + 该块的权重 + 该块的实例，**按需加载**，不要一次性把 335 M 面塞进场景。

### 3.3 水面与「低地不是水」

- 水面掩码 `water_mask.png`（8.10 km²）与地形水体**逐像素一致**，可直接用它生成水面片。
- 注意：**新奥斯汀是低于海平面的干盆地**（犰狳镇 −14.7 m），高度图上看起来最暗但**不是水**。
  判水只看掩码，别用"z < 某阈值"。

---

## 4. 地形材质怎么用

### 4.1 七层权重（**不交付**，2026-11-07 用户裁定）

- **决定**：交接只给彩图（§4.2）；**材质怎么分层由骑砍2 侧自己定**，`deliverable/terrain/weights/` 不进交接包。
- **例外（盘上必须保留）**：这七张图是本项目**大地图地形生成器的输入** —— `Scripts/gen_rdr2_terrain.py` 读 `w_water.png` 等（第 128/185 行）、`Scripts/gen_rdr2_sdn_terrain.py` 也读（第 137/202 行）。删了就没法重跑地形。
- 规格（万一以后要用）：`grass / conifer / rock / dirt / broadleaf / water / snow`，4 m/px，8 bit，逐像素归一化；另有打包版 `weights_rgb_1/2/3_snow.png`。

### 4.2 颜色贴图

- **包内直接取 `deliverable/terrain/color_1m.png`（1 m/px，10768×8024）**；子场景各自取 `blender/scenes/tex/<id>_color.png`（同规格、按场景裁好）。
- 它是"烘好的地面彩图"，**平面 UV**（世界西南角 = (0,0)，东北 = (1,1)），陡坡会拉伸——
  这是 RDR2 自己的做法，也是我们复刻的方式。
- **进引擎的接法**：子场景走 colormap 整图（`vista_tileset="none"` + `vista_diffuse_name=<该场景彩图>` + `colormap_detail_level="-1"`，范本 = 织丰日本地图），详见 `Modules/LivingWorldNpcs/plans/大镖客2还原/00-总纲.md`「资产导入方案」§C。
- 城区地面在彩图里偏黑（游戏用路面模型接管），所以城区看起来会暗，这是正常的。

### 4.3 想要更清楚：0.5 m/px 那张

`export/world/world_ground_2p0.png`（24592²）是 0.5 m/px，但它是**补外延之前**的版本，
地图框外的补丁区是空的（实测 **16.8% 近黑**）。两种用法：

1. 地图框内用 2p0（0.5 m/px），框外回落到 final_out（1 m/px）——需要我们自己出一张混合版；
2. 就用 final_out（1 m/px），够用。

> 需要"0.5 m/px + 外延补全"的合版，可以让我们重烘一次（脚本链在，约 20 分钟）。

---

## 5. 建筑与网格（位置、坐标、贴图）

### 5.1 从"实例"到"摆进场景"

```
tiles/*.json  →  [hash, x,y,z, q...]  →  model_manifest.csv(查 hash)  →  .mdl + tex
```

- **去重是你省钱的关键**：182 158 个实例只对应 **10 076 个唯一网格**（约 18:1）。
  在骑砍2 里应该做成 **10 076 个 prefab（实体原型）**，场景只存引用 + 变换。
- 每块 tile 的实体数在 `continent/index.json` 的 `tile_list` 里（最大块 27 208 个实例、最小 34 个）。
- 想知道"这块地方有什么建筑"：读对应 tile，按 `cls` 过滤（≥8 m 才是房子，`<1.5 m` 是碎屑/小道具）。

### 5.2 模型清单（推荐先读这张）

`deliverable/manifests/model_manifest.csv`：

| 列 | 说明 |
|---|---|
| hash / name | 哈希与原模型名（来自 ydr 文件名） |
| in_lib | 1 = 有网格；**0 = 缺网格（共 817 个，见 §8）** |
| mdl | 相对 `assets/lib_native/` 的路径，如 `d4/0xd46e4919.mdl` |
| tris / verts | 三角面 / 顶点（决定 LOD 预算） |
| size_x / size_y / size_z | 模型包围盒尺寸（米），可直接判"这是房子还是碎屑" |
| tex_ids / tex_names | 该模型用到的贴图 id 与名字（`;` 分隔），对应 `assets/lib_native/tex/<id>.png` |
| instances | 该模型在大陆里被摆了多少次（**排前面的就是最值得做 LOD 的**） |

### 5.3 `.mdl` 二进制格式（RMDL1，自己写读取器只要 40 行）

```
偏移 0    : char[8]  "RMDL1\0\0\0"
偏移 8    : uint32   nsub                   子网格数
偏移 12   : float32[6] bbox                 minx,miny,minz,maxx,maxy,maxz（模型局部坐标）
偏移 36   : nsub × 28 B 子网格表，每项 7×uint32:
              texId, vCount, iCount, posOff, nrmOff, uvOff, idxOff
之后      : 按 posOff/nrmOff/uvOff/idxOff 取数据
              pos  float32[vCount*3]   （模型局部坐标，Z 向上）
              nrm  float32[vCount*3]
              uv   float32[vCount*2]
              idx  uint32[iCount]      （三角形列表，iCount 必为 3 的倍数）
```

- **texId = −1 表示无贴图**（用顶点色/纯色）。
- 现成读取器：`tools/blender_continent.py` 的 `load_model_mesh()`（含越界保护，可直接照抄逻辑）。
- 顶点/法线/UV **全部 float32，没有量化**；不是压缩格式。

### 5.4 贴图（漫反射 / 法线 / 高光 —— 2026-10-30 起**三张都进库了**）

- 命名后缀表明用途：`_ab / _abal / _abte / _al` = **漫反射（颜色）**；
  `_nm` = 法线、`_ma/_mb` = 材质图（R=Metallic / G=Roughness / B=AO）、`_s` = specular、`_d` = detail、`_pal` = 调色板。
- **贴图表 `index.json.tex` 现有 27,057 条**（2026-10-30 之前只有 12,214 条 albedo）：
  `role='ab'` 12,214 / `role='nm'` 8,578 / `role='ma'` 6,265，全部 ≤ **512×512**
  （源多为 1024，入池时统一缩到 512）。
- **每个子网格的三张贴图记在 `index.json.models[hash].st`**，与 `s` **等长同序**：
  `st[i] = [nm_tid, ma_tid]`，`-1` = 该槽没有这张图。`.mdl` 二进制**没有改**（仍是
  7×u32 的 `texId,vc,ic,pos,nrm,uv,idx`），三贴图信息只走 index 侧车 —— 老读取器不受影响。
- **法线图入池时已把 G 通道翻转**（RDR2 是 DirectX 约定 +Y 朝下，Blender/OpenGL 要 +Y 朝上），
  表里用 `gflip:1` 标记；**使用时不要再翻一次**，否则凹凸反向。
- **`_ma` 通道语义（已定死，别再猜）**：R=Metallic、G=Roughness、B=AO。
  Blender 里 `Separate Color` → R 接 Metallic、G 接 Roughness；B(AO) 暂不接
  （Principled 没有 AO 输入，硬乘 Base Color 会把颜色压暗）。
- 覆盖（`python tools/audit_three_maps.py` 实测）：

  | 口径 | 漫反射 | 法线 | 高光(`_ma`) |
  |---|---:|---:|---:|
  | 槽位（225,412 个子网格） | 97.73% | **93.38%** | **91.28%** |
  | 实例加权（场上 443,268 槽） | 94.65% | **91.11%** | **86.83%** |

  没补上的原因只有一个：**源 `.ydr` 引用的贴图名在磁盘上任何 ytd 里都没有**
  （法线 2,883 个名字 / 高光 4,718 个名字，13 个顶层包已全抽）。不是解析失败、也不是没绑定。
- 生成工具：`tools/extract_slot_textures.py --stage parse|bind|decode|apply`；
  绑定规矩是「几何 vc/ic 全等 + albedo 名字全等」才写，否则留 `-1`（最高原则 §6.3）。
- 材质：`tools/mat_rdr2.py` 统一建节点图（`alb_<名>` + `__nm_` + `__ma_`），
  `blender_continent._mat_for()` 与 `relink_materials.py` 共用；材质上有
  `albedo/normal/orm` 三个自定义属性，manifest 的 `tn`/`tm` 字段就是读它们。
- 圣丹尼斯的**网页预览**另有一套（glTF 管线，`export/previews/sdn/textures/`，
  `_ab.png` / `_nm.jpg` / `_ma_orm.jpg` 已按 glTF 重排成 ORM），与 Blender 侧互不影响。
- 绝大多数 PNG 带 alpha（植被/栅栏/贴花要靠 alpha 镂空，别当不透明贴）。

### 5.5 贴图预算（进引擎前先算）

地图用到的贴图 3 236 张。按 512² 估：

| 格式 | 显存 |
|---|---|
| RGBA8 未压缩 | ≈ 3.2 GB |
| **BC7（推荐近景）** | ≈ **0.85 GB** |
| BC1/DXT1（4 bpp，远景） | ≈ 0.42 GB |
| 256² 再降一档 | ≈ 0.21 GB |

> 建议：**近景 BC7 512 / 远景 BC1 256**，并按 prefab 分档，不要全用一个规格。

---

## 6. 据点与任务场景

### 6.1 46 个据点（`settlements_world_v2.csv`，v1 见 `settlements_world.csv`）

> ⚠️ **2026-10-22 修正**：v1 有 3 处坐标/编码错（瓦匹缇偏 246 m、豁牙裂口偏 505 m、
> 朗尼棚屋应走 `lon` 而非 `lnn`），并补了 3 个剧情必去点（**威拉德之息** = 夏洛蒂的家、
> 马掌望台 = 第 2 章营地、阿伯丁猪场）。**新项目请直接用 v2**；
> 每个点位的实体数 / ≥8m 建筑 / 有网格建筑数见 `settlement_audit.csv`，
> 说明见 `docs/世界与地编/RDR2_骑砍2落地_据点修正_v2.md`。

字段：`code, name_zh, name_en, btype, faction, owner, bound_to, world_x, world_y, size_w_m, size_d_m, u, v`

| 类型 | 数量 | 实测尺寸范围（`size_w × size_d`） |
|---|---|---|
| 城市 Town | 10 | 177~862 × 195~955 m（圣丹尼斯 862×955 最大，含港区） |
| 城堡 Castle | 11 | 94~541 × 86~537 m |
| 村庄 Village | 12 | 44~209 × 53~238 m |
| 营地 Camp | 4 | 106~196 × 82~505 m |
| 野外点位 POI | 4 | 15~80 × 14~74 m |
| 藏身处 Hideout | 2 | 150~165 × 55~150 m |

> 这些是"据点本体"的包围盒，不含外围林地/山谷。开场景时按 §6.2 再向外扩 600~1000 m。
>
> ⚠️ **43 个里有 2 个在地图框外**（瓜玛岛：阿瓜多切斯 y≈−6992、瓜玛营 y≈−7329），
> 它们属于 `guarma.blend` 那个独立场景，不在大陆高度图范围内——用之前先按坐标过滤。

用法：`world_x/world_y` 就是贴图/高度图同一套世界坐标，可直接拿来开场景、算距离、算所属势力。

### 6.2 任务场景：**有内容，没坐标**

`export/levels/world/mission_*` 里有：任务树、步骤、目标、事件、调度、剧本级脚本解析、演员表、对白（41 005 行）。
**但没有每个任务的世界坐标**（RDR2 的任务点是脚本里动态取的）。

所以任务场景的落位建议：

1. 按任务所属**据点**取 `settlements_world.csv` 的坐标（文档 `docs/角色与物品/RDR2_骑砍2落地_势力与NPC.md` 里已经给了任务↔势力/据点对应）；
2. 以该点为中心开一个 **1200~2000 m** 的方圆场景，从 `tiles` 里按坐标范围筛实例；
3. 需要"特定建筑"（银行/酒馆/警局/车站）时，用 `model_manifest.csv` 的 `name` 关键字筛（如 `sal_`=酒馆、`bank`、`jail`、`stat`）。

> 如果你们需要"每个任务的精确坐标"，我们可以在解包侧再挖一次任务脚本的坐标常量（工作量中等，先别假设已有）。

---

## 7. LOD0-6 与「大地图缩略模型」建议（回答"是不是交给我们自己做"）

### 7.1 现状（确认）

| 项 | 现状 |
|---|---|
| 几何精度 | **HD 原始精度，float32 无损**，没有减面、没有量化 |
| LOD 链 | **没有**。RDR2 自己的 `_slod/_l0` 资产我们基本没导（10 893 个里只有约 20 个名字带 lod/slod） |
| 纹理 | albedo ≤512（**源是 1024 的被我们压到 512**，这一项算有损） |
| 结论 | **几何是"无损源"，纹理是"够用版"，LOD 必须由你们生成** |

所以：**大世界缩略模型 + 任务场景高清模型 + LOD0~6 的分级，确实是骑砍2 Agent 的活**。
我们提供 LOD0 = HD 源（不再减面），你们负责 1~6 级与合批。

### 7.2 代价先算清楚（这是为什么要 LOD）

| 指标 | 数值 |
|---|---|
| 实例总数 | 182 158 |
| 唯一网格 | 10 076（**18:1** 复用率 → 必须走 prefab） |
| 唯一网格三角面 | **38.9 M** |
| **全量实例化（都按 LOD0）** | **335.6 M 三角** ← 跑不动 |
| 其中 ≥8 m 建筑 | 225.7 M |
| 其中 <1.5 m 碎屑/小道具 | 101.5 M（30%！**最先该被剔除或合并**） |

### 7.3 建议的 LOD 预算表（按观看距离）

| 级别 | 距离 | 单个建筑目标面数 | 做法 |
|---|---|---|---|
| LOD0 | 0~15 m | **≈2 000**（源中位 4 928，减 60%） | 保留轮廓/门窗，减面优先削内部与背面 |
| LOD1 | 15~40 m | ≈800 | 焊接顶点 + 减面 70% |
| LOD2 | 40~100 m | ≈300 | 去小件（栏杆/雨棚/招牌） |
| LOD3 | 100~250 m | ≈100 | 简化到体块 + 屋脊 |
| LOD4 | 250~600 m | 20~30 | 体块（box + 屋顶） |
| LOD5 | 600~1 500 m | 6~12 | 双面片 / 交叉公告板 |
| LOD6 | >1 500 m 或**大地图缩略** | 2 | 单公告板 或 纯色块（颜色取该模型 albedo 均值） |

单场景目标（一个 900 m 城镇）：**LOD0 可见 ≤400 个建筑 × 2 000 = 80 万**，配合 LOD1~2 挤出后 **≈60 万面**，可接受。
大地图缩略（43 据点全开）：每据点一个 LOD6 代表体（≈1 000 面内含地标）+ 地形，
总量 **≤5 万面**，可以一张地图全铺。

### 7.4 三条工程建议

1. **先做"剔除名单"再做 LOD**：`cls=0`（<1.5 m，101.5 M 面）和 `in_lib=0`（817 个）先排除，
   能砍掉约 30% 面数与所有缺模型问题。
2. **按 prefab 建 LOD，不按实例**：10 076 个 prefab 各生成一套 LOD0~6，实例只引用——
   否则你会做 182 158 次。
3. **两种"高清"分开**：任务特写用的建筑保留 HD（LOD0）单独进一个 `cinematic` 资源包，
   大地图用 LOD3~6，别让两套混在一个 prefab 里。

---

## 8. 已知缺口（照单核对，别当成 bug 再查一遍）

| # | 问题 | 规模/证据 | 影响 | 建议 |
|---|---|---|---|---|
| 1 | **817 个 archetype 没有网格** | `model_manifest.csv` 中 `in_lib=0` | 这些实例摆不出来（多为船/vfx/外延新道具） | 先跳过；要补需再从对应 rpf 抽 ydr |
| 2 | ~~**贴图只有 albedo，且 ≤512**~~ → ✅ **2026-10-30 已补** | `index.json.tex` 27,057 条：`ab` 12,214 / `nm` 8,578 / `ma` 6,265；`models[h].st` 记录每槽三张图 | 仍 ≤512（源 1024 被缩）；法线槽位覆盖 93.38% / 高光 91.28% | 仍未补上的 2,883个法线名 + 4,718 个 `_ma` 名在磁盘任何 ytd 里都没有（要先拿到游戏原包）；要 1024 就得重抽池子 |
| 3 | **没有 LOD 链** | 见 §7.1 | 必须自己减面 | §7.3 |
| 4 | **碰撞未转换** | `raw/collision` 30 包 / 12 331 个 `.ybn` / 7.9 GB | 骑砍2 物理/寻路需要 | 需要写 ybn→物理体转换（尚未实现，是独立任务） |
| 5 | **外延区精度低** | patch 顶点间距 ~13 m，彩图 4 m/px（主图 0.25 m） | 地图边缘发软 | 远景可接受 |
| 6 | **彩图分块接缝** | 外延包与主瓦片有色调台阶（权重实测台阶 0.28） | 权重图出现方块边界 | 可做跨块直方图匹配（未做） |
| 7 | **城区地面偏黑** | 游戏用路面模型接管 | 权重把城区判成"岩" | 要铺路面就单独加 urban 层 |
| 8 | **实体覆盖 70.6%** | 剩余多为引擎程序化植被 | 少了树/灌木 | 需要植被系统自己补 |
| 9 | **任务无坐标** | 见 §6.2 | 任务点要自己定 | 按据点开场景 |

---

## 9. 复现入口（需要重跑时）

| 目的 | 命令 |
|---|---|
| 地形三种模式 + 唯一彩图 | `uv run python tools/make_terrain_stages.py` → `uv run python tools/carve_rivers.py`（`build_final_map_heightmap.py` 已停用） |
| 子场景原生高度 | `uv run python tools/build_scene_heightmap_native.py` |
| 材质权重（v2） | `uv run python tools/build_terrain_weights.py` |
| 实例分块 | `uv run python tools/build_continent_index.py` |
| 模型库（无损几何） | `uv run python tools/dump_model_lib.py` |
| 交接清单 | `uv run python tools/build_handoff_manifest.py` |
| 水陆一致性核查 | `uv run python tools/build_map_check_overlay.py`（产物写到 `docs\世界与地编\img\map_check\`，**不再进交付目录**；已改为读 `terrain\stages\02_river_carve\`） |

更细的背景（怎么解包、格式怎么破、每轮踩了什么坑）见 `README.md` 与 `docs/`。

---

## 10. 资源清理（给接手人）

磁盘 126 GB 里有约 **27 GB 是可删的备份**、**40 GB 是可重建的原始解包**。
清单与删除命令见 `docs/交接与状态/资源清理清单.md`；**§0 的交付物一个都不要删**。
