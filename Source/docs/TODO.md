# TODO —— 交接版（2026-10-31 晚）

> 交接阅读顺序：1) 本文（最上面就是下一步）2) `docs/格式与资产/分类体系与判定规则.md`（19 类 / 判定顺序 / 纠错清单）3) `docs/AGENTS.md`（§1.7 bat 纪律 · §1.8 分类入口 · §1.9 目录纪律）4) `docs/交接与状态/README_交接.md`（历史）。
> **红线**：分类规则只改 `tools/class_rules.py`；改完必须跑 `python tools/_check_rules.py`。构建前先关 RDR2（RPF 锁）。

---

## ★ 2026-11-01 · 两层材质 B（当前最高优先级）

### 0. 一句话

RDR2 的 `standard_2lyr*` 材质有 **两层 albedo + control 混合图**，我们现在只导了第 0 层；
第 0 层经常是"腐烂/污渍遮罩"，所以码头、墙体在 Blender 里整块发黑。**B = 完整支持两层 + control + palette。**

### 1. 证据（不要重查，照这个做）

- 源文件：`raw/sdn/models/new_pie_03_dockmed3.ydr`，shader = `standard_2lyr_pxm`
- 槽位：
  - `lyr0diffusetex` → `nbx_wall_woodplank_11long_rotted_ab`（**遮罩**：alpha 均值 0.083、RGB 0.034）
  - `lyr1diffusetex` → `nbx_wall_woodplank_11long_ab`（**基底**：不透明、RGB 0.312）
  - `controltexturetex` → `nbx_wall_woodplank_14long_ct`（控制图，**未抽取**）
  - `tintpalettetex` → `new_pie_03_dockmed3_pal`（256×4 调色表，未抽取）
  - `dirtdiffusetex` → 泥土层（`standard_dirt` 用，未抽取）
- 当前导出器：`tools/export_sdn_props2.pick_albedo()` **只取第 0 层 albedo**（`ROLE_ALBEDO` 命中即返回），
  `rdr2_ydr.extract_at()` 的 `texs_detail` 里其实两层都在（role=`albedo` / `albedo2` / `control` / `albedo_dirt`）。
- 影响面：`raw/sdn/models` 3,309 个 ydr 里 **852 个用 2lyr**（`standard_2lyr` 735 / `standard_2lyr_pxm` 236）；
  `standard_dirt` 692 个的 dirt 层也被忽略。全包（all_packs）还没统计。

### 2. 验收（做成什么样算完）

1. `new_pie_03_dockmed3` 在 Material Preview 里能看到木板纹理（不再黑），并与基底图对比不偏色；
2. 区域 #20 重建后，抽查码头/城墙/室内墙面不黑；建筑类"低 alpha + 近黑"的贴图不再作为唯一 albedo；
3. control 混合生效：选一个 control 明显的模型，两层分别关闭/开启能看到混合差异；
4. 重建不崩、材质数量/内存可接受（每个两层材质多 1~2 张贴图 + 1 个控制图）。

### 3. 实施步骤

| # | 做什么 | 文件/数据 | 备注 |
|---|---|---|---|
| 1 | **扫描器**（已跑过一次，2026-11-01）：列出所有 2lyr / dirt 模型（hash、源文件、各层 role/name、control/palette）→ CSV | 一次性探针放 `D:\BrainMaker\_probe\two_layer\audit_two_layer.py`；重跑命令：`python "D:\BrainMaker\_probe\two_layer\audit_two_layer.py"` | **SDN 城市结果**：3,309 个 ydr → 1,073 个 2lyr/dirt 模型；全部有 lyr1；852 有 control；978 有 palette；95 无 palette |
| 2 | **抽 control/palette/dirt 贴图**：让贴图池包含这几类角色 | `tools/extract_slot_textures.py` / `tex_slots.py` / `work/tex_name_index.json` | 需要按 role 建索引，不能只认 albedo/normal/material |
| 3 | **导出器带上层信息** | `tools/export_sdn_props2.load_drawable`：把 `albedo2 / normal2 / materialA2/B2 / control / dirt` 一并带出；`dump_model_lib.write_model` 写入 | `.mdl` 格式扩展或 `index.json` 加 `lyrs` 字段；老模型按单层兼容 |
| 4 | **材质节点**：两层混合 + palette | `tools/mat_rdr2.py` | BaseColor = mix(lyr0, lyr1, control 通道)；法线/ORM 同步；palette 调色（需实测通道语义） |
| 5 | **重导**：先 SDN 城市 852 个 2lyr 模型 | `raw/sdn/models` + ingest 工具 | 逐模型验证：重导后 index/mdl 有 `lyrs` |
| 6 | **重建 + 验收** | 区域 #20 先重建，再全量 | `_check_region` PASS；肉眼抽查 |

### 4. 已知风险

- `controltexturetex` 的**通道语义**（R/G/B/A 各管哪层、是否多 dirt 层）没有公开文档 → 必须用 2~3 个模型做"关层对比"实测；
- `tintpalettetex` 是 256×4 调色表，可能依赖顶点色/调色索引 → 不还原会让颜色偏；
- 材质翻倍会显著增加显存/构建时间（尤其大陆 7.3 GB）→ 先只对 2lyr 模型启用，单层模型不动；
- `.mdl` 是自有二进制格式，扩展必须带版本号/兼容旧文件，否则整个库要重导。

### 5. 本轮（2026-11-01）其他已完成事项

- 22 个区域裁剪全部 PASS；`unknown` 在 #19/#20 已清零（#20：254 个缩略图目视 → 250 条纠错 #91~340）。
- 分类规则：`struct` 只留桥/栈桥；码头→建筑；信号灯→部件；tower/build/kitchen/coop/tabacco/boathouse/props/水面/道岔等词缀。
- 修掉构建 bug：材质名截断（贴图纠错漏匹配）、隐藏集合 `matrix_world` 未求值（包围盒/埋深错误）。
- 资产目录重构复核通过；探针"专用目录 + 用完即删"规矩已落到
  `docs/格式与资产/分类体系与判定规则.md` §6.1。

---

## ★ 下一步（新 session 从这一节开始）：批量生成 22 个「有网格」的区域裁剪

> ✅ **2026-11-01 已完成**：22/22 块 `status=done`，`_check_region` 全部 PASS；
> 本节保留作流程/命令参考，**下一件事是上面的「两层材质 B」**。

### 0. 一句话

大陆 v23 目前还是 **17 类旧规则**；分类规则已升级到 **19 类**（新增 `road`、`ruin`），区域 #19 已验证 PASS。接下来把**可见对象 > 0** 的 22 个区域各裁一个 blend，逐个对账；全部 PASS 后再对大陆跑一次，出 v24。

### 1. 目录约定（2026-10-31 用户裁定，照 `sdn_full2/`、`guarma/`、`willard/` 的先例）

```
D:\BrainMaker\大镖客2解包分析\deliverable\blender\
├── regions\                         ← 只放区域 blend
│   └── <编号>_<tile>.blend          （例：19_wild2000_04_02.blend）
└── regions_support\                 ← 验证内容
    ├── region_list.csv              ← 批量清单 + 状态（已建：22 行，19=done，其余 todo）
    ├── region_corrections.csv       ← 全局纠错清单（一份，共用）
    ├── overview\                    ← 全图俯视图/图例（可选）
    └── <编号>_<tile>\               ← 每区域一个验证子目录
        └── manifest_<编号>_<tile>.json / .jsonl
```

- **`regions\` 里只允许 `.blend`**；manifest / 预览图 / CSV 一律进 `regions_support\`。
- 日志：`D:\BrainMaker\_logs\region_<编号>.log`。
- 编号 = 俯视图图例的 `#1~#47`（`regions_support\tile_legend.csv`）。

### 2. 要跑的区域（22 块）

不做：24 个「可见对象 = 0」的块；4 个只有 4 个对象的边角桩（#1/#2/#8/#9）；**瓜玛 #40**（战役不含它）。

| 批 | 编号 | tile | 可见对象 |
|---|---|---|---:|
| 1 | #19 | `wild2000_04_02` | 26,018（**已完成**） |
| 1 | #20 | `wild2000_05_02` | 21,855 |
| 2 | #18 | `wild2000_03_02` | 15,199 |
| 2 | #12 | `wild2000_04_01` | 12,062 |
| 2 | #11 | `wild2000_03_01` | 11,556 |
| 2 | #13 | `wild2000_05_01` | 11,081 |
| 2 | #23 | `wild2000_01_03` | 8,158 |
| 2 | #17 | `wild2000_02_02` | 7,077 |
| 2 | #24 | `wild2000_02_03` | 4,077 |
| 3 | #10 | `wild2000_02_01` | 3,008 |
| 3 | #25 | `wild2000_03_03` | 2,027 |
| 3 | #26 | `wild2000_04_03` | 1,717 |
| 3 | #4 | `wild2000_03_00` | 1,347 |
| 3 | #22 | `wild2000_00_03` | 1,232 |
| 3 | #5 | `wild2000_04_00` | 1,066 |
| 3 | #6 | `wild2000_05_00` | 697 |
| 3 | #3 | `wild2000_02_00` | 78 |
| 3 | #27 | `wild2000_05_03` | 57 |
| 3 | #33 | `wild2000_04_04` | 29 |
| 3 | #16 | `wild2000_01_02` | 11 |
| 3 | #21 | `wild2000_06_02` | 7 |
| 3 | #30 | `wild2000_01_04` | 2 |

### 3. 单块命令（可直接复制的模板）

**A. 从零构建一块**（Blender 进程内跑完整链：几何 → 分类 → 植被/地形/LOD 隐藏 → 清单）

```powershell
Set-Location "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source"
cmd /c 'tools\run.cmd D:\BrainMaker\_logs\region_20.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --python tools\_unbuffer.py -P tools\blender_continent.py -- --out "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions\20_wild2000_05_02.blend" --lib "D:\BrainMaker\大镖客2解包分析\assets\lib_native" --only-tile wild2000_05_02 --step 8 --rails --full --no-water --corrections "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions_support\region_corrections.csv"'
```

**B. 已建好的区域只重跑分类/纠错**（约 3~5 分钟，不重建几何）

```powershell
Set-Location "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source"
cmd /c 'tools\run.cmd D:\BrainMaker\_logs\region_20_fix.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions\20_wild2000_05_02.blend" -P tools\_unbuffer.py -P tools\_apply_corrections.py -- --corrections "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions_support\region_corrections.csv" --out "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions\20_wild2000_05_02.blend"'
```

**C. 对账（每块必跑）**

```powershell
python "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source\tools\_check_region.py" --tile wild2000_05_02 --audit "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions_support\20_wild2000_05_02\manifest_20_wild2000_05_02.jsonl"
```

> 说明：A 构建会把 manifest 写在 blend 旁边。**必须**把它移到 `regions_support\<编号>_<tile>\`（`_apply_corrections.py` 会自动挪；纯 A 构建要手动 `Move-Item`）。判据永远是 `_check_region.py` **PASS**（19 类计数逐项一致）。

### 4. 批量驱动（已实现：`tools/build_regions.py`，2026-10-31）

要求：

| 项 | 规定 |
|---|---|
| 输入 | `regions_support/region_list.csv`（列：`number,tile,blend,visible,status`） |
| 执行 | **一次一个 Blender**（内存/磁盘），顺序按编号；每块调 A 命令 |
| 断点 | `status=done` 跳过；`--resume` 默认开启；`--force` 重跑；`--only 19,20` 指定 |
| 归位 | 构建完把 `manifest_<编号>_<tile>.json/.jsonl` 移到 `regions_support\<编号>_<tile>\` |
| 对账 | 立刻跑 `_check_region.py`；**FAIL 就停**，不继续下一块 |
| 日志 | `D:\BrainMaker\_logs\region_<编号>.log`；驱动自身日志 `_logs\build_regions.log` |
| 备份 | 构建前设 `save_version=0`，**不生成 `.blend1`**（`reclassify.py` 已有先例） |
| 状态 | 每块结束更新 `region_list.csv` 的 `status`（todo/done/failed） |

### 5. 验收 / 停止条件

- 单块：**以 `_check_region.py` PASS 为准**。
  🔴 `manifest` 的 `verdict` 在小区域常常是 `CHECK` —— **不是失败**：第 1 步的 18 类覆盖判据
     是给大陆用的，野外小块本来就没有 rail/watertile/bldg 这些类。看 `veg_should_delete==0` 即可。
  🔴 `unknown` 允许为 0 或非 0；区域检查期对账带 **`--allow-stale-underground`**：v23 有 2,312 个对象的
     包围盒是局部坐标（矩阵未求值），埋深判定失真；该开关只把「underground 差额恰好等于其他类差额」
     降级为警告，其它差异仍 FAIL。**大陆最终重跑（v24）之后必须去掉这个开关做严检。**
- 批量：22 块 `status=done`，无 `failed`。
- 任何一块 FAIL：**停止批量**，修规则/纠错 → 跑 `_check_rules.py` → 用 B 命令重跑该块。

### 6. 磁盘 / 时间

- 单块约 **0.4~0.9 GB**（`--step 8 --no-water`；#19 实测 860 MB），22 块合计约 **10~15 GB**；
- 单块 5~12 分钟，**22 块约 3~4 小时**；
- 做完不用的块可删（`region_list.csv` 留状态，`--only` 可重跑）。

---

## ★ 批量之后：大陆收口（v24）

> 🔴 2026-10-31 用户明确要求：**先把每个分块做对，最后才重跑一次大陆**。本轮只做到分块（22/22 done），
> 大陆重跑**未执行**（曾误启动一次，产物已删除）。开工前先征得用户同意。
> 重跑之后：`_check_region.py` 必须**去掉 `--allow-stale-underground`** 对所有区域做严检。

1. 用**同一份纠错清单**把 v23 重分类成 v24（**新建文件，不覆盖 v23**）：

```powershell
Set-Location "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source"
cmd /c 'tools\run.cmd D:\BrainMaker\_logs\continent_v24.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b "D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_v23.blend" -P tools\_unbuffer.py -P tools\_apply_corrections.py -- --corrections "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions_support\region_corrections.csv" --out "D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_v24.blend"'
```

2. 验收：manifest `verdict=PASS`（`unknown` 允许为 0，看 `classes_missing` 为空）、`_check_region.py` PASS；`_check_class_visibility.py` 确认 `road` 隐藏、`ruin` 显示。
3. 之后所有区域重建都自动继承 19 类 + 纠错清单。

---

## 当前状态（2026-10-31 晚）

### 区域批量：**22/22 全部完成**（`region_list.csv` 全 `done`）

- 产物：`deliverable\blender\regions\<编号>_<tile>.blend`（每块 0.1~0.9 GB）
- 清单：`regions_support\<编号>_<tile>\manifest_<编号>_<tile>.jsonl`
- 对账：全部 **PASS**；只有 #18 触发 1 条警告（v23 多出 underground 31 个，旧包围盒失真），其余 21 块逐类严格一致
- 驱动：`tools/build_regions.py`（断点续跑；FAIL 即停；一次一个 Blender）

### 本轮修掉的两个构建 bug（影响所有块的正确性）

1. **材质名截断**：`mat_rdr2.mat_name` 超 60 字符会截成 `alb_<前26字符>__<哈希>`，贴图纠错在构建侧漏匹配 → 贴图匹配时必须同时喂 `m['albedo']` 全名。
2. **隐藏集合不进 depsgraph**：后台模式下隐藏集合里的对象 `matrix_world` 不更新 → 包围盒/埋深/贴地判定全错（v23 清单里 2,312 个对象的 `bb` 是局部坐标）。已在 `classify_entities` / `write_manifest` 里强制「全开集合 + `view_layer.update()`」。
3. 连带：**修复前建的区域必须重建**（已全部重建完毕），否则几何判定不可信。

### 区域 #19（已完成，可作模板）

- `deliverable\blender\regions\19_wild2000_04_02.blend`（860 MB，`--no-water`）
- 29,843 对象 / **19 类 19/19** / 对账 **PASS**
- 隐藏 4,598（lod 512 / terrain_cell 999 / veg 2,502）
- **unknown 已清零**（`com_plane001` 目视确认完全埋在地下 → underground）——430 → 0，2026-10-31 纠错行 16~41

### 分类体系（现已 19 类，规则唯一真身 = `tools/class_rules.py`）

- 新增类：`road`（道路，**默认隐藏**）· `ruin`（废墟，**默认显示**）；
- 硬规则：**名字含 `junc` 一律 road**（无例外）；名字含 `ruin` 一律 ruin（`lod/underground` 除外）；
- 纠错清单：`regions_support\region_corrections.csv`（40 条，id 1~4 / 6~41；16~41 = 区域 #19 的 unknown 清理）；
- 回归：`tools/rules_cases.csv`（16 条用例），`_check_rules.py` 全过；内置关键词最近补了 `infirmary`（bldg）、`_bri(?!ck)`（struct）
- 改分类流程与坑：见 `docs/格式与资产/分类体系与判定规则.md`。

### 相关脚本

| 脚本 | 用途 |
|---|---|
| `tools/class_rules.py` | **规则唯一真身**（19 类 / RULES / 硬规则 / 纠错解析） |
| `tools/classify_entities.py` | Blender 驱动（建集合树、几何兜底） |
| `tools/_apply_corrections.py` | 已建区域重跑分类（含纠错、清单归位） |
| `tools/_check_region.py` | 区域对账（v23 + 纠错 vs 区域 manifest） |
| `tools/_check_rules.py` | 规则自检（合法性 / 冗余 / 用例） |
| `tools/_probe_tile_atlas.py` / `_probe_tile_labels.py` | 整图俯视渲染 / 地块编号 |
| `打开大陆_流畅.bat` | 双击选编号打开区域（`regions\<编号>_<tile>.blend`） |

---

## 遗留清理（等用户确认后执行）

| 文件 | 原因 |
|---|---|
| `deliverable\blender\regions\19_wild2000_04_02.blend1` | Blender 自动备份（860 MB）；新构建已要求 `save_version=0` |
| `deliverable\blender\regions_support\_probe_cards_wide.json` / `_probe_crosscards.json` | 一次性探针输出 |
| `D:\BrainMaker\_logs\test2.bat` / `test_launcher.bat` / `bat_dump.txt` | 调试 bat 的临时文件 |

---

## 禁止事项（交接红线）

1. **不要改 `continent_v23.blend`**（7.3 GB 主产物）；要升级就出 `continent_v24.blend`；
2. **不要在 `D:\BrainMaker` 根放任何文件**；新目录先问（见 `AGENTS.md` §1.9）；
3. **不要手动改 `regions_support\region_corrections.csv` 之外再抄一份规则**；规则值只进 `class_rules.py`；
4. **不要跳过 `_check_rules.py` / `_check_region.py`**；
5. **不要同时跑两个 Blender**（内存/磁盘竞争）；
6. **不要生成 `.blend1`**（构建脚本设 `save_version=0`）。
