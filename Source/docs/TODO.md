# TODO —— 交接版（2026-10-31 核对）

> 交接顺序：1) `docs/交接与状态/README_交接.md`（上一轮到哪了，最新一节 = 本轮）2) 本文件 3) `docs/AGENTS.md`（长任务 / 禁开大文件 / 已知坑）4) `docs/最高原则_单一管线与分块即裁剪.md`（五条禁令）
> 历史 TODO 在 `docs/交接与状态/TODO.md`。

---

## 0. 一句话状态（2026-10-31 按产物实测）

**唯一主产物：`deliverable/blender/continent/continent_v23.blend`**（7.78 GB，建 2026-10-30 23:27，`manifest_continent_v23.json` → **PASS**）

| 项 | 数 |
|---|---:|
| 对象 / ENTITIES | 184,035 / **184,032** |
| 分类 | **17 类 17/17**（明细见 §4.1） |
| 默认隐藏合计 | **49,918**（地形块 30,839 · 地下停放 8,335 · 植被 7,472 · 远景 LOD 2,290 · 石块 648 · 水面块 321 · 占位 13） |
| 未分类 `unknown` | 7,143（3.9%） |
| 贴图用 / 无 albedo | 8,209 张 / **26,440 个对象**（拆解见 §2.2） |
| 带法线 / 带 ORM 对象 | 162,566（5,991 张）/ 153,413（4,722 张） |
| 模型库 / 贴图表 | **71,790** / **32,878** |

**这一版已经做到**：游戏 `levels_*.rpf` 2,158 个嵌套包全抽（0 空包 / 176,097 文件 / 58.58 GB）；抽出的 72,407 个 `.ydr/.yft` 入库 71,790（99.15%）；tiles 233,104 条实例里 184,032 条建成对象；位置/四元数/缩放完整率 **100.000%**；分类从"垃圾桶制"改成 17 类划分制（v18~v23 逐轮收口，细节见交接 §16）。

---

## 1. 还剩什么（按优先级）

> 判据：**能观感验收的排前面；等用户拍板/等新数据源的排后面**。每行都带可复核的数字。

| P | 事项 | 现在卡在哪（实测） | 下一步 |
|---|---|---|---|
| **P1** | **泥路面发白（粘连贴图名）** | `ann_04_d_maintrack_*` 渲出来是白带。ytd SYS 里名字本身是 `std_annesburg_muddyroad_03_ab` + `..._al` 两段粘连，我们取到的是近白那张（RGB 均值 218）。量级：贴图表里这种粘连名 **1,285 个 / 8,720 个子网格**；发白集中在 `std_annesburg_muddyroad_03`（253 处）、`_01`（114）、`road_muddyroad_03`（69）、`road_muddyroadtnt_02`（83） | 解粘连名时**选 `_ab` 子资源**（不要 `_al`）→ 重跑贴图表 + 重绑 + 重建。涉及 `rdr2_ytd.py` 与贴图表生成 |
| **P1** | **2,813 个 albedo 名没有图**（占引用 2.0%） | 已排除四个来源（见 §2.3）：hd_0 命中 0 · textures_0/1 内容全是 UI/deferred probe（命中 0）· update_1~3 没有 ytd/ydr · appdata0_update 只有 1 个 `.dat` + 1 个 `.xml`。这 2,813 个名的模型槽位是 `-1`，所以清单里表现为"无 albedo 槽" | 换找法：**按 ydr 里记录的纹理引用 hash 反查**（不再按名字搜 RPF）。工具缺口 = 现在没有"纹理 hash → 包内条目"的索引 |
| **P1** | **铁路 14% 埋在地形面以下** | H4 地形 4 m/px 表达不了路堑；安尼斯堡以北仍是"轨面陷进土里" | **等用户拍板**：要不要切地形开路堑（最高原则 §6.2 禁擅自改地形） |
| **P2** | **室内 319 个 hash** | 146 包已解包、2,301 模型入库、79 包已摆；缺 MLO `rooms/portals` 变换 | 用 3 栋已知房子做三角验证（老阻塞） |
| **P2** | **`rpf_available` 1,770 个 hash 只有物理代理** | 包里只有 `_ph/_occ`，没有可渲染几何 | 只能等新数据源，或按缺件记录 |
| **P2** | **`no_definition` 306 个 hash** | ytyp 里查不到定义，来源不明 | 下一轮用 `archetype_swaps.ymt` 之类查 |
| **P2** | **地形 4 层混合没还原** | 每个槽只挂第 0 层的法线/材质图；引擎是 4 层按权重混合，近景会有"一层法线盖全图"的观感 | 在 `mat_rdr2.py` 里写多层混合节点（下一轮） |
| **P2** | **渲染图左下/右下有异常灰块** | `_test/ann/v16ann_full.png` 可见，疑似地形块缺失/未贴图 | 没查；先用 `report_manifest` 对照那块坐标的对象与类 |
| **P3** | **`plantpot` 30 个还标成建筑部件** | 代码已改（veg 排除 + prop 兜底 + `bldg/part` 前置跳过），**等下一次 reclassify 自动归位** | 下次 reclassify 后核对这 30 个 |
| **P3** | **`unknown` 7,143 个** | 每轮靠用户点名收口（v21~v23 就是这么把 und/watertile/placeholder/rail 收掉的） | 继续按"用户点名 → 补规则 → reclassify（约 18 分钟，不要重建）"循环 |
| **搁置** | **504 个 fragment 道具 / 1,158 条实例**（衣物/纸张/木料/旗帜/弹药/箱顶） | 文件已抽出（`raw/all_packs/**/*.yft`），是另一种 fragment 布局，能定位到的 drawable 只有 1~3 个三角形的占位 | **用户 2026-10-30 决定暂不补**；补 = 解析新布局（1,244 真实例 = 0.53%） |

### 1.1 本轮核对发现的两个「文档与产物不符」（已回填，留档）

| 项 | 文档原写法 | 实测 |
|---|---|---|
| `underground` 数量 | 交接 §16.6 的 v23 行写 **1,158**（那是旧的 `x=y=0` 规则） | **8,335** —— v23 建库前 2 分钟规则改成了"9 点取最低地形，比对象最高点高 10 m 即判地下"。其中 **5,891 个 z>50**（高山），抽样含冷杉/岩石；**建议抽查是否在陡坡误伤**（4 m/px 地形在崖边取样误差可能 >10 m） |
| `hd_0.rpf` | README 待办写"**未抽**（1 GB / 23 包，26,440 个无 albedo 多半靠它补）" | 状态文件记 `done（0 new / 320 dup）`，但**磁盘上 0 个文件**；320 条 = 292 个基础名，其中**只有 1 个被场景模型引用**，与 2,813 缺名的交集 **0** ⇒ **补 hd_0 对场景没有可见收益**，假设推翻 |

---

## 2. 已关闭 / 已排除（别再查）

### 2.1 已关闭的旧 TODO

| 项 | 结论 |
|---|---|
| `update_1..4.rpf` 未核对 | **已核对**：`update_1/2/3` 里 0 个 ytd/ydr；`update_4` = 5,704 个 ytd + 17 个 ydd，已抽取（4,969 个新 ytd 入库） |
| `appdata0_update.rpf` 未查 | **已查**：2 个条目（1 `.dat` + 1 `.xml`），不含贴图 |
| 植被"应删未删 416" | **口径已改**（交接 §16.3）：新判据 = "默认隐藏类里还露着的对象"，v19 起为 **0** |
| `real_ytyp` 3,061 无几何 | **已解决**：压在 `.ydd` 字典里（子 drawable 用自己的 hash），已入库 3,229 个模型 |
| 贴图表 id↔名字↔文件错位 | **已重做**：按名字重建 11,504 条，55,608 模型全量重绑，审计绑错 0 |
| 城区"白块" / 水面灰板 / willard 陷地 | 已修/已数值化验证（交接 §11~§13） |
| `lod_combine` 无名块 46,532 | **不是缺口**：引擎运行时合并的远景替身，磁盘上没有独立资源；`lod` 类整类默认隐藏 |

### 2.2 "26,440 个无 albedo" 的真实构成（2026-10-31 从 v23 jsonl 拆）

| 类别 | 数 | 含义 |
|---|---:|---|
| 完全没有 albedo 槽（全部材质走 `ntex_` 兜底） | **15,094** | 模型 `.mdl` 里 albedo id = `-1`；小道具占大头（jug / ashtray / book / can / pot …） |
| 部分子网格走兜底材质 | **11,346** | 其中 **11,239 个**的贴图名其实**有图**（在 `have` 里）⇒ 是材质回退，不是缺图；剩下 62 个名字未知、45 个混合 |

> 所以"无 albedo"不等于"贴图没抽到"。真正缺图的名字是 §2.3 那 2,813 个。

### 2.3 2,813 个缺名的四个来源已逐个排除

| 来源 | 检查 | 结果 |
|---|---|---|
| `hd_0.rpf` | 索引 320 条 → 292 个基础名 | 与缺名交集 **0**；被场景引用的基础名只有 1 个 |
| `textures_0.rpf` | `hashindex` 8,380 个 ytd（45 顶层 + 14 嵌套包） | 内容 = deferred probes / AMV 网格 / underwater height / item UI；与缺名交集 **0** |
| `textures_1.rpf` | `hashindex` 3,376 个 ytd | 内容 = UI（journal/pausemenu/discovery/newspaper…）；与缺名交集 **0** |
| `update_1~3` / `appdata0_update` | 条目清点 | 没有 ytd/ydr / 只有 dat+xml |

> 顺带发现：`textures/item_textures.rpf` 里 338 个 ytd 用现有 `rdr2_ytd.py` 解析出 **0 个名字**（另一种字典布局）。这批是 UI 物品图，不影响世界场景，但如果以后要做物品图标，解析器要补这个布局。

---

## 3. 五分钟上手（不用开 7.8 GB）

```powershell
# 启动器（自动挑最新的 continent_v*.blend，并执行默认隐藏）
双击 打开大陆_流畅.bat

# 不开 Blender 核对
uv run python tools\report_manifest.py
uv run python tools\report_manifest.py --find new_gar06_park_terrain
uv run python tools\report_manifest.py --class rail --limit 20

# 缺模型到底缺什么
python tools\audit_missing_models.py

# 保存态的类可见性（三层验收之一）
blender -b <blend> -P tools\_check_class_visibility.py
```

**整类默认隐藏的七类**（N 面板勾上就显示）：地形块 · 地下停放 · 植被 · 远景 LOD · 石块 · 水面块 · 占位代理。2026-10-29 起不再有 `HIDDEN_*` 垃圾桶集合 —— 藏 = 整类关掉，对象仍留在类里。

---

## 4. 文件清单

### 4.1 v23 分类明细（17 类）

| 类 | 数 | 类 | 数 |
|---|---:|---|---:|
| prop 道具 | 72,786 | rail 铁路 | 2,978 |
| terrain_cell 地形块 | 30,839 | veh 载具 | 2,802 |
| part 建筑部件 | 19,139 | lod 远景碎片 | 2,290 |
| junk 杂物 | 17,139 | struct 结构 | 1,461 |
| underground 地下停放 | 8,335 | stone 石块 | 648 |
| veg 植被 | 7,472 | watertile 水面块 | 321 |
| unknown 未分类 | 7,143 | placeholder 占位代理 | 13 |
| rock 岩石 | 3,800 | light / terrain / water | 1 / 1 / 1 |
| decal 地面贴花 | 3,618 | **合计** | **184,035** |

### 4.2 有效产物

| 文件 | 大小 | 说明 |
|---|---|---|
| `deliverable/blender/continent/continent_v23.blend` | 7.78 GB | **当前主产物**（2026-10-30 23:27，PASS） |
| `…/manifest_continent_v23.json` / `.jsonl` | 1.3 KB / 59 MB | 汇总 + 对象级清单 |
| `…/manifest.json` | 1.3 KB | 恒定指向最新一次的汇总 |
| `export/world/missing_classified.json` | 9.9 MB | 缺模型分类明细（逐 hash：桶/名字/来源 ytyp/bbox） |
| `export/levels/town/archetype_assetnames.json` | 13.2 MB | 96,141 条 archetype：hash → assetName/bbox/来源 |
| `work/rpf_index/all.tsv` | 7.1 MB | RPF 全量 drawable 索引（包 + hash + 大小 + 名字） |
| `work/unparsed_models.json` | 720 KB | 4,076 个未能入库的文件逐条 |
| `assets/lib_native/` | — | 模型 **71,790** / 贴图表 **32,878** |
| `deliverable/blender/sdn_full2/` · `willard/` · `guarma/` | — | 历史管线产物，只作证据，**不作验收对象** |

> **磁盘上最多保留 3 个版本**（AGENTS §2.8）。当前 v22 / v23 两个，够回退；再出新品先删更早的（删除命令交给用户）。

### 4.3 建议删除（等用户点头）

| 目录/文件 | 占用 | 原因 |
|---|---|---|
| `work/lib_gtxd/txd_game/` | 28.5 GiB | 19,058 个 ytd，几乎全是 `ui_*`/`metaped_*`，场景不用 |
| `archive/废弃_sdn_full管线/` | 4.3 GiB | 废弃 glTF 管线产物 |
| `assets/lib_native/index_before_*` | 约 100 MB | 多轮改库备份，确认后删 |
| ~~`work/_probe_itemtex/` + `work/_probe_textures*.tsv`~~ | 约 344 MB | 2026-10-31 核对 `textures_0/1` 的临时探针，**已删** |

---

## 5. 关键脚本

| 脚本 | 用途 |
|---|---|
| `tools/blender_continent.py` | **唯一构建入口**：`--rails --full [--veg hide\|delete\|keep] [--pad] [--bbox x0,y0,x1,y1] [--only-tile <id>]` |
| `tools/reclassify.py` | **只改分类不重建**：打开最新 blend → `classify_entities --apply` → 重写 manifest → 另存（约 18 分钟） |
| `tools/class_registry.py` | 17 类 + `DEFAULT_HIDDEN` **唯一一份**；分类/巡视/面板/清单全部 import 它 |
| `tools/classify_entities.py` | 分类规则（名字正则 + 属性兜底 + 地下判定） |
| `tools/report_manifest.py` | 不开 Blender 核对 + `--find/--class/--tile` 查询 |
| `tools/manifest_from_jsonl.py` | 0.5 秒从 jsonl 反算汇总（替代 20~35 分钟的两遍扫描） |
| `tools/audit_missing_models.py` | 缺模型分桶（LOD 块 / 真件 / 包里有无 / 来源 ytyp） |
| `tools/audit_full_extraction.py` | 全抽取四列验收（包级 / 模型级 / 实例级 / 变换） |
| `tools/audit_three_maps.py` | 漫反射/法线/ORM 覆盖率（槽位级 + 实例加权） |
| `tools/extract_all_packs.py` | 2,158 个嵌套包全抽（约 45 分钟） |
| `tools/ingest_rail_packs.py` / `merge_rail_entities.py` | 模型入库（含 `.yft`）/ 实例并进 tiles（幂等） |
| `tools/extract_slot_textures.py` + `tools/tex_slots.py` + `tools/mat_rdr2.py` | 法线/ORM 槽位提取、绑定、材质节点（构建与 relink 共用） |
| `tools/relink_materials.py` | 给已存盘 blend 按当前 index 重挂材质（槽位按子网格序） |
| `tools/export_rail_preview.py` | **不经过 Blender** 的铁路 glTF-free 预览（three.js 页面，2026-10-31 新增） |
| `tools/blender_tour.py` / `blender_autoload.py` / `rdr2_cat_ui.py` | 巡视相机 / 启动器 / N 面板 |
| `tools/_check_tour_vis_unit.py` / `_check_tour_behavior.py` | **可见性回归检查**（合成场景秒级 / 真 blend 行为）；7 个验收渲染脚本见 `tools/README.md`「验收渲染 / 可见性检查」 |
| `tools/run.cmd` / `read_text.py` / `_unbuffer.py` / `watch_build.ps1` | 起子进程 / 读 GBK / 行缓冲 / 长任务看门狗 |

---

## 6. 常用命令

```powershell
# 全量重建（实测 60~90 分钟；先过 AGENTS §2.7 三条门禁）
cmd /c 'tools\run.cmd D:\BrainMaker\build_vN.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --python tools\_unbuffer.py -P tools\blender_continent.py -- --out D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_vN.blend --lib D:\BrainMaker\大镖客2解包分析\assets\lib_native --rails --full'

# 只重分类（不重建，约 18 分钟）
cmd /c 'tools\run.cmd D:\BrainMaker\_reclass.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --python tools\_unbuffer.py -P tools\reclassify.py -- --blend <最新 blend>'

# 小范围试验（3~6 分钟）
cmd /c 'tools\run.cmd D:\BrainMaker\_t.log "<blender>" -b --python tools\_unbuffer.py -P tools\blender_continent.py -- --out D:\BrainMaker\_test\t.blend --lib D:\BrainMaker\大镖客2解包分析\assets\lib_native --rails --full --only-tile wild2000_05_00 --bbox 2900,2100,3100,2300'

# 核对 / 缺口 / 库
python tools\report_manifest.py
python tools\audit_missing_models.py
python tools\audit_full_extraction.py
python tools\rpf_index.py
python tools\extract_by_hash.py --dry
python tools\normalize_lib_index.py --dry
```

> ⚠️ 需要 `numpy/PIL` 的脚本用系统 `python`；`uv run python` 是空环境，只适合不依赖第三方库的小脚本。
> ⚠️ 解包前先关游戏（rpf 被独占锁）；`set TEMP=D:\BrainMaker\_tmp`（别用 C 盘，见 AGENTS §4）。

---

## 7. 已知坑

全部在 `docs/AGENTS.md` §4（30 条）。最常踩的 5 条：

1. **别把"重建 blend"当进度条**（一次 60~90 分钟）→ 先跑 `audit_full_extraction.py` 四列收口。
2. **`-b` 测不出启动器画面** → 启动器行为只认 GUI 双击 bat。
3. **`Collection.hide_viewport` ≠ `LayerCollection.hide_viewport`** → 两套一起设。
4. **贴图只存 tid 不存名字会串号** → 一律按名字绑定。
5. **`hex()` 不补零**（第 N 次）→ 文件名/JSON key/对象名一律 `'0x%08x'`。

---

## 8. 下游（骑砍2 落地，不在本仓库）

本仓库只负责"解包 → Blender 全集"。送进骑砍2 的管线仍在旧数据上：

- `Modules/RDR2/SceneObj/rdr2_sanit_denis/scene.xscene` 是 **2026-10-26** 的导出（1.78 MB，圣丹尼斯 6,568 个实例），**未接 v23**。
- 交接文档：`LivingWorldNpcs/plans/大镖客2还原/00-总纲.md` 顶部「⏭ 下一步 TODO」三条（①圣丹尼斯实体完整性核查 ②LOD0~6 + TRF ③`custom.rdr2 openscene` 进场景），仍全部未完成。
