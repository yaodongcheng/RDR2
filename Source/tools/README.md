# tools 脚本索引

> 按职责分类。所有脚本从项目根目录运行：`uv run python tools/<脚本>.py`
> 脚本之间用 `sys.path.insert(0, tools)` + `import 模块名` 互相引用，**不要移动文件**。

## 槽位三贴图：漫反射 + 法线 + 高光（2026-10-30 新增，5 个）

> 背景见 `docs/格式与资产/README_贴图与材质管线.md` §11.4。一句话：
> 模型库以前**每个子网格只存一个 texId**，法线/高光在写库时被丢掉；这五个文件把它补回来。

- `extract_slot_textures.py`  **主工具**，四段式（可中断续跑）：
  `--stage parse`（16 进程解析 5.5 万源 `.ydr/.yft`，实测 3.6 分钟）
  → `--stage bind`（对 `s` 做 vc/ic + albedo 名字三重校验）
  → `--stage decode`（14 进程解 `_nm`/`_ma` 进 `tex/`，池 12,214→27,057）
  → `--stage apply`（回写 `index.json` 的 `st`；`.mdl` 不动；先自动备份）
- `tex_slots.py`  源侧取图规则（**按 albedo 图层配对** `normal_layerN` / `material_layerN`）。
  注意 `export_sdn_gltf.ROLE_MATERIAL` **不含** `material_layerN`，别照抄那份常量
- `mat_rdr2.py`  Blender 节点图（albedo→BaseColor、`_nm`→NormalMap、`_ma`→SeparateColor→
  Metallic/Roughness）。`blender_continent._mat_for()` 与 `relink_materials.py` 共用这一份
- `audit_three_maps.py`  **不开 Blender** 的三贴图覆盖审计（槽位级 + 实例加权 + 池子分 role）
- `render_material_ab.py`  同机位 Eevee A/B 出图（`_on.png` 带三贴图 / `_off.png` 断掉法线与 ORM），
  用于肉眼验收 —— Workbench 只有 `diffuse_color`，**看不到法线**

> 配套改动（非新增文件）：`blender_continent.py`（`_mat_for` 收三个 id、`load_model_mesh` 读 `st`、
> `VERIFY` 多打一行 `TMAPS`）、`relink_materials.py`（重写成走 `mat_rdr2`）、
> `write_manifest.py`（`alb_` 名字可带 `__nm_`/`__ma_` 后缀、新增 `tn`/`tm` 字段）、
> `manifest_from_jsonl.py`（汇总加 `with_normal_objects` 等四项）、`export_sdn_props2.py`
> （`.yft` 的 geom 也带 `ntex`/`mtex`）。

## 整块大陆 / Blender 装配（19 个）

- `blender_add_props.py`
- `blender_add_train_peds.py`
- `blender_add_trolley.py`
- `blender_assemble_sdn.py`
- `blender_bind_player_walk.py`
- `blender_continent.py`  主装配。关键参数：`--only-tile <id>`（分区）、`--no-pad`（POI 用）、
  `--no-conj-quat`（回退旋向，仅对照）、**`--rails`（铁路豁免剔除规则；不加会丢 1,024/1,359 件铁路）**
- `blender_diag_bind.py`
- `blender_preview_gltf.py`
- `blender_rebuild_ground.py`
- `blender_render_blend.py`
- `blender_render_interiors.py`
- `blender_setup_sky.py`
- `build_continent_index.py`
- `build_water_level.py`
- `build_world_ground.py`
- `combine_ground.py`
- `dump_model_lib.py`
- `fill_model_lib.py`
- `make_ground_mask.py`

## 模型库缺口诊断 / RPF 全量索引（2026-10-29 新增，7 个）

> 结论先看 `docs/世界与地编/RDR2_整图覆盖率核查_20261026.md` §10：
> 「未命名 5 万」里 46,532 个是 **LOD 合并块**，不是缺口。这一组脚本就是产出那条结论的工具链。

- `ytyp_assetnames.py`    1,026 个 ytyp → 96,141 条 archetype（`hash / assetName / bbox / 来源文件`）。
  证明了 `+88 == +112 100%`（`assetName` 与 `name` 同值，没有第二个名字可挖）
- `rpf_index.py`          调 `rdr2rpf hashindex`：原地读嵌套 TOC（不解 57 GB）→ `work/rpf_index/all.tsv`
  （18 个顶层包 / 4,021 个 RPF / 74,449 个 drawable 条目）
- `extract_by_hash.py`    按 **RPF 条目 hash** 抽 drawable（调 `rdr2rpf extracthash`），可断点续跑
- `audit_missing_models.py`  **缺模型分桶**（`lod_block / real_ytyp / rpf_available / no_definition`）
  + 据点严格框拆分 → `export/world/missing_classified.json`（构建时 `VERIFY` 那行也读它）
- `normalize_lib_index.py`  以磁盘 `.mdl` 为准重建 `lib_native/index.json`（key 一律 `0x%08x`）。
  **本轮回收获 367 个「库里有、场景里没有」的模型**
- `audit_ground_contact.py`  任意 blend 的贴地/浮空/陷地数值审计（射线到 Terrain，出中位/MAE/三档占比）
- `register_orphan_textures.py`  把 `tex/` 里**磁盘有、tex 表没登记**的孤儿贴图按 id 补登记
  （本机 1,782 张；名字用 `tex<id>` + `x:1` 标记）→ 20,858 个模型恢复 albedo
- `patch_ground_town_white.py`  地面色图「无数据白」体检/补洞（默认 `--probe`，写盘前先备份原图）

> 配套 C# 侧（`tools/rdr2rpf/Program.cs`）新增两个命令：
> `hashindex <rpf> <out.tsv> [exts] [maxDepth]`、`extracthash <rpf> <hashlist> <outdir> [exts]`。

## 外延地形 / 空洞诊断（2026-10-22 新增，6 个）

> 修「地形右上角虚空」用的一条链路，顺序执行：
> `extract_outskirts` → `build_outskirts_ground` → `build_terrain_full_inputs`
> → `blender_rebuild_terrain_fixed`；诊断用 `blender_probe_terrain_holes` / `blender_diag_terrain_holes`。

- `extract_outskirts.py`              提取 `levels/rdr3/terrain/outskirts/out_*` 34 个包 + 算世界 bbox
- `parse_outskirts.py`                单包解析/出图（调试用）
- `build_outskirts_ground.py`         patch 顶点 → 4 m 高程 + `out_*.ytd` 色图 → `H4_full.npy` / `valid_full.npy`
- `build_terrain_full_inputs.py`      合并掩码 + 色图（含 40 m 羽化接缝、亮度对齐）
- `blender_rebuild_terrain_fixed.py`  用补完输入重建 blend 里的 Terrain（`RDR2_H4/RDR2_MASK/RDR2_GROUND` 可覆盖）
- `blender_probe_terrain_holes.py`    射线穿地法量空洞（输出 `work/verify/terrain_hole_probe.json`）
- `blender_diag_terrain_holes.py`     面中心栅格化看空洞形状（快速版）
- `blender_shots_fix.py` / `blender_shots_ne.py`   固定机位验证截图

## 大陆裁剪 / 高度图 / 材质权重（2026-10-22 新增，4 个）

- `export_map_area_heightmap.py`   官方地图框 → 世界矩形 → 16 bit 高度图（含 r16/meta/预览/核对图）
- `build_terrain_weights.py`       7 层材质权重图（**高程/坡度/水面都读最终高度图**，色图只提供颜色；阈值在文件顶部）
- `blender_crop_continent_to_map.py`  按地图框重建 Terrain + 删框外实体 + 重建框内水面
- `blender_probe_maparea.py`       裁剪后按地图框射线测覆盖率/空洞

## 世界 / 地形 / 城镇（19 个）

- `bake_campaign_map.py`
- `bake_scene_tile.py`
- `bake_ue_walk_to_rdr2.py`
- `audit_settlements_v2.py`     骑砍2 落地据点审计（坐标/编码修正 + 实体/建筑/有网格统计）
- `build_clothing_catalog.py`    全服饰清单（6106 件 → CSV/JSON/浏览页）
- `build_clothing_thumbs.py`     全服饰缩略图（点云投影 96×144，6106 件）
- `export_clothing3d.py`         全服饰 3D 导出（.glb，6106 件 / 4.17 GB）
- `build_clothing3d_page.py`     把 3D 索引内联进试衣间页面
- `official_name_map.py`         本地化 .yldb 中英配对查询
- `apply_official_names.py`      把项目里的旧译名批量换成官方用词
- `bake_ycd_walk_worlddelta.py`
- `build_entity_tiles.py`
- `build_settlement_list.py`
- `build_settlement_previews.py`
- `build_terrain_heightmap.py`
- `build_town_hpatch.py`
- `build_town_standalone.py`
- `build_town_terrain_viewer.py`
- `build_town_textured_viewer.py`
- `build_world_color.py`
- `build_world_grid.py`
- `build_world_map.py`
- `build_world_water.py`
- `export_sdn_gltf.py`
- `export_sdn_props2.py`
- `plan_town.py`

### 微缩模型 / 沙盒大地图（2026-10-26 新增，经验见 docs/世界与地编/RDR2_微缩模型_经验与失败路径.md）
- `build_model_ledger.py`         全量模型台账（52 539 个：名字/面数/包围盒），替代旧的 10 893 条清单
- `analyze_settlement_scale.py`   46 据点实测：建设占地/建筑件/密度/地标候选
- `build_miniatures.py`           v1 方块代理版（已废弃，留作对照）
- `build_miniatures_real.py`      v3 真实 `.mdl` + 贴图图集版（近看仍是碎薄壳）
- `build_miniatures_lego.py`      v4 体素/切片乐高实验（碎/发白）
- `build_miniatures_blocks.py`    **v5 街区积木（当前交付：46 城 18 404 面）**
- `build_miniatures_spec_doc.py`  生成 7.0.1 规格文档（46 行分档表）
- `build_sandbox_map.py`          大地图底图（高度/颜色/摆放表 → map/data）
- `audit_miniatures.py`           46 城验收（面数/单 draw/单材质/尺寸/非纯色）
- `rdr2_mdl.py`                   读 `assets/lib_native` 的 RMDL1（pos/nrm/uv/idx/texid）
- `blender_city_flatcolor.py`     从 `.blend` 抽特征建筑 → **平面消融保形减面**（2 650 万→270 万面）
- `blender_lego_city.py` / `blender_lego_boxes.py`  乐高化实验（薄壳会碎，仅留档）
- `blender_bake_city.py`          `.blend` → join → COLLAPSE 导出（材质 5 076 个，不可用）
- `export_city_instances.py`      导出单城实例清单（给 Blender 高模用）

## 任务 / 剧情 / 对白（16 个）

- `build_cutscene_cast.py`
- `build_dialogue_export.py`
- `build_mission_dialogues.py`
- `build_mission_events.py`
- `build_mission_inventory.py`
- `build_mission_objectives.py`
- `build_mission_schedule.py`
- `build_mission_scripts.py`
- `build_mission_steps.py`
- `build_mission_story.py`
- `build_mission_tree.py`
- `patch_viewer_missions.py`
- `render_mission_logic_md.py`
- `render_mission_schedule_md.py`
- `render_mission_scripts_md.py`
- `render_story_md.py`


## 载具 / UI / 兵种（2026-10-24 新增，7 个）

- `build_vehicle_inventory.py`   载具清单：`vehicles.rpf` 662 个文件 → 216 行（面数/顶点/几何/尺寸/分类）
- `export_vehicle_gltf.py`       `.yft`(fragment) → glTF；含 `PaintTexLib`（`*_control` 涂装控制图 → 中性漆面）
- `build_vehicles_page.py`       载具页数据（中文名表 `VEH_ZH` 在文件顶部，可继续补）
- `extract_ui_textures.py`       UI 纹理字典 → PNG + `ui_textures.csv`（两种 .ytd 布局都支持）
- `build_ui_page.py`             UI 页数据（纹理 + 界面 screen / 控件 widget / 影片 gfx / 布局 xml）
- `build_units_page.py`          兵种覆盖审计 → `ped_coverage.csv` + 兵种页数据
- `build_weapon_audit.py`        武器 / 弹药 / 载具武器 参数表对账（哈希解名 + 模型对账）

## 通用 PSIN(.ymt) 导出器

- `pso_xml/`（C#，CodeWalker `PsoFile`）：`pso_xml <in.ymt> <out.txt> [--raw]`
  输出 schema（每个结构的字段/类型/偏移/引用）+ data（每条记录的全部标量字段，
  哈希字段用 names.txt 反查）。武器/兵种/载具相关的 ymt 都靠它看字段结构。
  `--raw` 模式对比相邻两条记录的逐字节差异，用来判断"这文件里到底有没有真数据"。

## 角色 / 骨架 / 动画（13 个）

- `build_anim_case.py`
- `build_anim_viewer.py`
- `build_material_viewer.py`
- `build_model_inventory.py`
- `build_npc_viewer.py`
- `build_ped_anim_viewer.py`
- `build_ped_rig.py`
- `build_ped_skeleton.py`
- `build_service_npcs.py`
- `build_skel_actions_viewer.py`
- `build_skel_viewer.py`
- `build_walk_viewer.py`
- `build_weapon_item_data.py`

## 铁路 / 场景补全

- `add_rail_network.py` —— 把整条铁路网（道砟/枕木/钢轨/桥/隧道/道岔，**1,359 个对象**）装回 `continent.blend`。
  **幂等**（先删 `RAILCELLS` 再建；实测重跑仍是 1,359）。支持 `-- --out <blend>` / `--no-lift` / `--no-conj-quat`（仅对照用）。
  内含 joaat 哈希→名字 反查（`names.txt`），可复用于其它"无名实体"。
  > 2026-10-27 修正：旋向改为**共轭**（与 `blender_continent.py` 一致）；`tex_id<0` 给中性灰。
  > 更好的做法是重建时直接 `blender_continent.py --rails`，见 `README.md` §0.7.1。

### 铁路包补抽 / 入库 / 并实例（2026-10-30 新增，2 个）

**背景**：铁路网在游戏里是**按区块的独立 RPF 包**（`levels/rdr3/area/rails/*.rpf`）。
安尼斯堡区块的 `jklm_15_18_rails_a/b`、`fghi_15_18_rails_a` 三个包**只建了空目录、从没抽到文件**
（`raw/rails_extract/*_rails_*_rpf/` 都是 0 个文件），所以实例层里安尼斯堡只剩 4 段 `ann_02_rails_*`。
补抽 + 入库 + 并实例后重建，`rail` 类 2,033 → **2,193**，安尼斯堡 900 m 内铁路对象 65 → **217**。

- `ingest_rail_packs.py` —— 把 `raw/rails_extract/{jklma,jklmb,fghia}` 里的 `.ydr` 无损入库（`.mdl` + `tex/` + `index.json`）。
  hash = `joaat(文件名)`；**已入库的自动跳过**（可反复跑）；写盘前备份 `index_before_rail_<ts>.json`。
  顺带把法线/`_ma` 槽位写进 `st`（与 `extract_slot_textures.py` 同格式）。
  用法：`python tools/ingest_rail_packs.py --dry` / `python tools/ingest_rail_packs.py`
- `merge_rail_entities.py` —— 把这三个包的 `.ymap` 实体并进 `export/world/continent/tiles/wild2000_*.json`，
  行格式与 `build_continent_index.py` 完全一致（11 列）。默认**跳过 `_lod/_slod`**（构建时也会隐藏，避免双份）；
  按 `(hash,x,y)` 去重；先备份到 `tiles_before_rail_<ts>/`。
  用法：`python tools/merge_rail_entities.py --dry` / `python tools/merge_rail_entities.py`

> ⚠️ 抽包这一步不在脚本里（要游戏文件）：`rdr2rpf.exe extract levels_2.rpf <out> levels/rdr3/area/rails/<包>.rpf`，
> 再把抽出来的 `.rpf` 解一层。完整命令见 `docs/交接与状态/README_交接.md` §14。

## 验收渲染 / 可见性检查（2026-10-31 归口，7 个）

> **来源**：原先散落在 `D:\BrainMaker\` 根的 7 个一次性脚本（10-30 19:42 ~ 10-31 07:26 建），
> 按 `docs/AGENTS.md` §1.6 归口到 `tools/`。**产物仍在 `D:\BrainMaker\_railcheck\`**（交接 §16.6 引用了那批图）。
> 相关旧工具：`_check_class_visibility.py`（存盘态逐集合 dump）· `_probe_vis_state.py`（v11 时代的 saved vs `show_all` 对照，已被上面两个覆盖）。

| 脚本 | 类别 | 用途 | 产物 |
|---|---|---|---|
| `_check_tour_vis_unit.py` | 检查 | 合成场景单测：类名解析 + `show_all/apply_defaults/cat_show/only/full` 的可见性（秒级，不加载 blend） | 控制台 `=== UNIT OK ===` |
| `_check_tour_behavior.py` | 检查 | 真 blend 行为检查：逐函数调用并打印 data/eye 两套状态；与 `_check_class_visibility.py`（存盘态）互补 | 控制台 |
| `_check_bat.py` | 检查 | **bat 交付前必过**：静态规则（GBK/CRLF、echo 转义、引号、pause）+ 干跑（list/19/99） | 控制台 PASS/FAIL |
| `_probe_rail_wide.py` | 探针 | 安尼斯堡铁路远景：`top` / `oblique` / `wide` | `_railcheck/{top,oblique,wide}.png` |
| `_probe_rail_close.py` | 探针 | 断口近景：`close_top` / `close_along` / `close_yard` | `_railcheck/close_*.png` |
| `_probe_rail_ties.py` | 探针 | 枕木近景：A（有 dec 片）/ B（无 dec 片） | `_railcheck/tie_*.png` |
| `_probe_rail_r02.py` | 探针 | `jklm_1518b_r_02`（3075,1511）近景 | `_railcheck/r02_*.png` |
| `_probe_blend_ab.py` | 探针 | 任意两个 blend 同机位 A/B（默认 v22/v23）：normal + rail-only | `_railcheck/ab_<版本>_*.png` |

```powershell
# 可见性单测（秒级；不加载 7.8 GB）
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup -P tools\_check_tour_vis_unit.py

# 铁路渲图（Blender 要打开 7.8 GB blend，约 5~10 分钟）
cmd /c 'tools\run.cmd D:\BrainMaker\_railcheck\wide.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b "D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_v23.blend" -P tools\_unbuffer.py -P tools\_probe_rail_wide.py'
```

**保留判定**：`_check_*` 长期保留（回归检查）；`_probe_*` 是**证据脚本**，重跑即覆盖同名图，
交接文档还引用这些图 —— **别删**；要开新主题就新建 `_probe_*` 并在本表登记。

## 格式解析库（被其他脚本 import）（13 个）

- `rage_meta.py`
- `rdr2_cwxml.py`
- `rdr2_npc_export.py`
- `rdr2_shader_params.py`
- `rdr2_tex_index.py`
- `rdr2_vdecl.py`
- `rdr2_walk_fix.py`
- `rdr2_ycd.py`
- `rdr2_ydr.py`
- `rdr2_yft.py`
- `rdr2_ytd.py`
- `ymap_entities.py`
- `ytd_to_png.py`

## 查看器 / 站点（5 个）

- `build_sdn_terrain_tex.py`
- `build_viewer_data.py`
- `build_viewer_site.py`
- `export_weapon_assembled.py` —— 武器「主体 + 部件」装配成完整 glTF（长枪缺枪托就是缺 `_grip1`）
- `weapon_tint.py` —— 把 `standard_weapon_2lyr` 的 tintpalette/双层/control 参数在 UV 空间烘成 albedo
- `export_weapon_tint.py` —— 用上面的烘焙结果写带贴图的武器 glTF（覆盖 `export/viewer/models/weapons/`）
- `patch_viewer_weapon_parts.py` —— 把装配清单写回 `site.json`，查看器 HUD 显示「部件」

> 截图自检：`tools/shot.mjs <url> <out.png> [waitMs] [w] [h] [clickSelector] [afterMs]`，
> 走 CDP 无头 Chrome；每次自动用独立临时 profile + 空闲端口（否则会连到上次残留实例，截出全白页）。

## 其他 / 一次性探针（62 个）

- `audit_sdn_coverage.py`
- `audit_weights.py`
- `build_bannerlord_factions.py`
- `build_tile_buildings.py`
- `build_valentine_real.py`
- `build_ytd_preview.py`
- `capture_john_walk.py`
- `capture_raw.py`
- `diag_knee.py`
- `diffscan_pose.py`
- `dump_live_skeleton.py`
- `dump_rpf8_header.py`
- `export_anim_json.py`
- `export_area_terrain.py`
- `export_building_materials.py`
- `export_building_meshes.py`
- `export_gltf_source.py`
- `export_lod_meshes.py`
- `export_ped_anims.py`
- `export_prop_gltf.py`
- `export_prop_meshes.py`
- `export_sdn_interiors.py`
- `export_town_l2.py`
- `export_town_textured.py`
- `export_veg_meshes.py`
- `export_world_towns.py`
- `extract_building_textures.py`
- `extract_gtxd_pool.py`
- `find_pose_array.py`
- `fix_decal_materials.py`
- `make_generic_peds.py`
- `make_inventory.py`
- `make_synth_walk.py`
- `memscan.py`
- `open_bind_inspect.py`
- `open_walk_in_blender.py`
- `parse_mapzones.py`
- `parse_veg_instances.py`
- `probe_ped_vdecl.py`
- `rebuild_rdr2_clips.py`
- `render_bannerlord_md.py`
- `render_exported_glb.py`
- `render_faction_map.py`
- `render_glb_views.py`
- `render_settlement_map.py`
- `render_settlement_md.py`
- `render_willard.py`          威拉德歇脚处（夏洛蒂的屋子）单点渲染
- `render_wnt1_steps_md.py`
- `resolve_missing.py`
- `rsc8_standalone.py`
- `settlement_catalog.py`
- `triplanar_probe.py`
- `uv_probe.py`
- `uv_probe_page_gen.py`
- `validate_inventory.py`
- `xcheck_rdr2_on_bannerlord.py`
- `xcheck_ue_rdr2.py`
- `ycd_decode.py`
- `yft_bind.py`
- `yldb_dump.py`
- `yldb_keys.py`
- `ytyp_archetypes.py`
- `zone_stream.py`
