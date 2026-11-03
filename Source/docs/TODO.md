# TODO —— 交接版（2026-11-03）

> 交接阅读顺序：1) 本文（最上面就是下一步）2) `docs/格式与资产/分类体系与判定规则.md`（21 类 / 判定顺序 / 纠错清单）3) `docs/AGENTS.md`（§1.7 bat 纪律 · §1.8 分类入口 · §1.9 目录纪律）4) `docs/交接与状态/README_交接.md`（历史）。
> **红线**：分类规则只改 `tools/class_rules.py`；改完必须跑 `python tools/_check_rules.py`。构建前先关 RDR2（RPF 锁）。

---

## ★ 2026-11-03 · 大地图场景划分原则（交接 · 未实施）

**一句话原则（用户原话，按这个做，别再反）**：
> 据点本身的能走范围（P）的并集 ≠ 原版大地图全部有效区域。**剩下的有效区域才是野地**；野地单独开图，但只在这块“剩下的”范围内分配，不覆盖据点。**据点 P + 野地 P = 整张有效地图，互不重叠；场景地面 T / 灰色远景可以重叠。**

### 最终数字（41 / 46 两版作废）

| 层 | 数量 | 说明 |
|---|---:|---|
| 据点自己的地图 | 44 | 22 大（9 城 + 11 堡 + 2 藏身处）+ 22 小（11 村 + 5 营地 + 6 点位）；**每个据点一张**，村不再跳去野地 |
| 野地地图 | 17 | **只铺在据点 P 并集之外的剩余有效区域**；野地 P 之间不重叠，也不碰据点 P |
| 瓜玛岛 | 2 | 独立 |
| **总计** | **63** | 44 + 17 + 2 |

### 硬规则（交接时必须保持）

1. **据点 P 各自不重叠**；据点有自己的地图，玩家从大地图点据点进入的是**据点自己的场景**。
2. **野地 P = 有效地图 − 44 个据点 P 的并集**；野地只在这块剩余里分配（17 个野地中心的 Voronoi ∩ 剩余，再裁真实地图边界）；**野地 P 不许覆盖任何据点 P**。
3. **据点 P ∪ 野地 P = 整张有效地图**（有效 = 陆地，水面不算）；必须跑通“并集覆盖 + 两两不重叠”的自检。
4. **场景地面 T 和灰色远景可以重叠**（不同 Mission，玩家一次只进一张）；只有 P 不能重叠。
5. **坐标 → 场景**：点/开战坐标落在据点 P 内 → 进该据点自己的地图；落在野地 P → 进该野地地图。两类都按坐标换算场景局部位置。
6. **41 / 46 两版作废**；不许再出现“小据点并进野外营地、村庄跳去野地”的写法。

### 当前资产与下一步

| 东西 | 状态 |
|---|---|
| `deliverable/handoff/settlements_world_v2.csv` | 44 个上地图据点（46 − 瓜玛 2） |
| `_scratch/settlement_plan/settlements_p.json` | 44 个据点 P + 44 块领地（已裁真实地图边界） |
| `_scratch/settlement_plan/rects.json` | 22 个大据点的能走矩形 1 + 地图地面 T / 远景 O |
| `_scratch/settlement_plan/bubbles.json` | 17 个野地中心；**当前 P 是全图 3,072 方框裁边界，还没扣据点 P**（下一步要重算） |
| `_scratch/settlement_plan/regions.json` | 22 个“大据点 + 并入小据点”的归属区；**只作归属查看，不是野地分配依据** |
| `Modules/RDR2/Source/docs/世界与地编/regions_viewer.html` | 当前还是 41 版（小据点跳营地），**要按 63 版重做** |
| `Modules/RDR2/Source/docs/世界与地编/RDR2_据点分级与场景边界方案.md` | 当前是 41 版，**要改 63 版** |

**下一步（按顺序）**：

1. **重算野地 P**：17 个野地中心的 Voronoi ∩（有效陆地 − 44 个据点 P 并集）∩ 真实地图边界；输出每个野地的 P 多边形 + 面积；自检“44 P + 17 P = 有效陆地，且两两不重叠”。
2. **22 个小据点各开 512 m 地图**（自己进入用）；22 个大据点地图沿用现有 T / W / O。
3. **页面改成 63 版**：据点页 44 个据点 P；野地页 17 个野地 P；地盘页把 44 + 17 拼在一起看覆盖；顶部 63。
4. **文档改 63 版**：把“22 小据点并进野外营地 / 41”全部替换为“44 据点地图 + 17 野地地图 + 2 瓜玛 = 63”。
5. **P0 验证**：3,072 m 野地场景 / 512 m 据点场景 / 是否需要 2,304 m / 远景外框 / navmesh；按结果调大小，但 **P 互补原则不变**。

### 页面/数据里的口径

- **有效地图** = `deliverable/heightmap/water_mask.png` 的陆地（水面不可走）；地图框 = `meta.json` 的 `x0..x1 / y0..y1`。
- **据点 P** = `settlements_p.json` 的 P（建成区 + 边距 ∩ 领地线 ∩ T ∩ 地图边界）。
- **野地 P** = 17 个野地中心 Voronoi ∩ 剩余陆地；野地**场景地面** 3,072 m，远景外框 `O = T + 2W`。
- **据点地图**：22 大（城 768–1,536 / 堡 640–1,024 / 藏身处 384）；22 小 **512 m**。

---

## ★ 2026-11-02 · 地形**两级**管线 —— 已重跑出图，⏳ **等用户逐条验收**

**一句话**：管线现在只做「原始 → 高原/平原」两级，每级一套完整的高度图 + 彩图，可单看可单独用。
🔴 **2026-11-02 按用户裁定砍掉两级**：
· **「水域加深」** —— 按单级水位挖/填，把圣路易斯河河床从 −28 m 抬到 +7 m（错的）；
· **「统一水位陆地修正」** —— 按「骑砍2 只有一个水面」垫高干地，前提不成立（已确认是**两块不同高度的水位**）。
⇒ **地形高度本身是对的，管线不再按水位动地形。**

**产物**：`deliverable\terrain\stages\`（**明细与验证方法见 `deliverable\terrain\README.md`**）

| 级 | 做了什么 | 改动面积 | z 区间 |
|---|---|---|---|
| `00_raw` | 外延包补过的原始地形，未塑形 | — | −56.9 ~ 690.3 m |
| `01_plateau_plain` | 西北高原（720 m + fBm + 150 m 高斯隆起，只抬外延区）/ 东南平原（42 m 合成） | 20.6 km² | −56.9 ~ 690.3 m |

**脚本**：`tools/make_terrain_stages.py`（两级）+ `tools/make_terrain_stage_compare.py`（对比图）；
参数与噪声种子 `import` 自 `tools/build_final_map_heightmap.py`，不另抄。

**本轮已修 / 已清**

- 🔴 **彩图不再重上色**（用户裁定）：各级 `color_1m.png` = **原始地形材质**（`world_ground_final_out.png` 原色）。
  旧做法「改动区按同高程带均值重刷」= 平坦色块 + 硬边界；之后又试了三种（高程重映射 / 局部色差场 /
  按同高程找最近真实数据整块拼贴），全部失败：
  · 高程重映射：79.5% 找不到同高程目标，退回色块；
  · 局部色差场：整片染成紫红；
  · 同高程最近真实地块拼贴：**数据量根本不够**——东南要铺 6.57 km²，该区 32~52 m 的真实地块只有 **0.04 km²**；
    西北目标 720 m，全图 ≥690 m 的真实数据是 **0**。结果就是同一块纹理被反复复制，出现网格状重复。
- 已删除的阶段目录：`02_water_deepen` / `03_unified_water` / `02_unified_water`；
  对比图只保留 `stages_height.png` / `stages_color.png` / `diff_00_01.png`。

**新发现：彩图有 512 m 瓦片接缝（2026-11-02，待用户定方案）**

- 彩图由 480 块 512 m 瓦片拼成，全图 **23 条横缝 + 23 条竖缝**；最明显的一条在世界 **y≈0 / 左侧**（缝上下 150 m 均值差 **11.3**）。
- 三种后处理都试过：
  | 方法 | 缝差 | 副作用 |
  |---|---:|---|
  | 渐变色调对齐（±220 m，4 遍） | 11.3 → 2.0 | 缝附近出现**亮带** |
  | 硬台阶对齐（下半整块平移） | ≈0 | 23 条累计**漂移发白**，整图报废（已删） |
  | **柔化（±40 m 垂直模糊）** | 硬线消失 | 缝附近 80 m 软过渡、轻微糊 |
- 柔化产物（**未覆盖源文件、未进管线**）：`export\world\world_ground_final_out_seamsoft.png`
- 对比图：`_scratch\color_repaint\cmp_soft_A.png` / `cmp_soft_SE.png`
- **待用户选**：① 用柔化版（要重跑 final/stages/weights）② 保持原样 ③ 柔化+轻色调对齐组合。
- 实话：真正无缝需要源瓦片一致（重新导出/统一校色），纯后处理只能在「硬线」和「糊」之间取舍。

**已知问题（既有问题，待用户裁定处理）**

| # | 问题 | 实测 |
|---|---|---|
| 1 | ~~与出厂文件不一致 / 改动幅度太小~~ | 随「水域加深」「统一水位」两级一起删除，不再适用 |
| 2 | **高度图矩形接缝台阶**（外延包 ↔ 主瓦片） | 竖直 **x≈−732**、水平 **y≈−2048**，两侧高差 >20 m；**出厂文件同样存在**（上游导出，本管线改不了） |
| 3 | **彩图 512 m 瓦片接缝** | 见上表；柔化版已出，等用户选（采用后要重跑 final/stages/weights） |

**下一步**：用户逐条指出「哪里不符合预期」→ 按条改；候选处理见 `deliverable\terrain\README.md` §三「已知问题」。

---

## ★ 2026-11-02 · 水面改成**两级**（瀑布两侧水位差 62 m）—— ✅ 数据与脚本已完成，⏳ **blend 尚未重建**

**用户实机确认**：圣路易斯河（瀑布以西）水面比主水系（平铁湖 / 海岸）低，实机里就是那道瀑布
（截图：峡谷大瀑布，骑马视角）。**地形不用改**——标高数据是对的，错的是「水面只有一个平面」。

| 项 | 值 |
|---|---|
| 主水系（平铁湖 + 海岸 + 东侧河流） | **40.5 m**（`water.xml` 真值，沿用原单平面的高度） |
| 西盆地（圣路易斯河 / 新奥斯汀，瀑布以西） | **−22 m**（西盆地岸线中位 −16.8，按主水系「岸线 45.5→水面 40.5」同样扣 5 m） |
| 两级交界 | ≈ **(−2000, −3177)**，x −2400~−1600 / y −3450~−2900 |
| 高山小湖（40 个零碎水体） | 各自岸线中位（58~243 m），**不参与两级**，否则会被压到 40.5 埋掉 |

**产物**

- `export\world\water_level_map_2lv.npy` —— 两级水位图（2048²，行 0=南，NaN=陆地）
- `tools\water_two_levels.py` —— 建 **三个**对象（默认 **32 m** 网格，约 1 万四边形；
  ⚠️ 2026-10-28 否掉的是 8 m / 28.5 万四边形 + 半透明版本，视口会卡，别退回去）：
  · **`Water_Main`** —— 主水系，默认 40.5 m
  · **`Water_West`** —— 西盆地，默认 −22 m
  · **`Water_Alpine`** —— 高山小湖（58~243 m），各湖保留自己的水位

🔴 **水位可调**（同旧版 `make_water_dynamic()`）：选中 `Water_Main` / `Water_West` →
物体属性 → 自定义属性 **`water_level`**，改数值水面立刻升降（网格顶点 z=0，对象按 `water_level` 移动）。
上面 40.5 / −22 只是**初值**，准不准以实机为准 —— 直接调旋钮，不用改脚本重跑。

**已同步改过的脚本**（都按 `Water` / `Water_*` 前缀找水面，不再写死单对象）

| 脚本 | 改了什么 |
|---|---|
| `blender_continent.py` `water()` | 单平面 → 调用 `water_two_levels.build()`；两级图缺失时退回旧图，再失败才退回单平面 |
| `blender_crop_continent_to_map.py` | 裁框后重建水面 → 两级、只留框内四边形 |
| `blender_sync_blend_to_heightmap.py` | 同上 |
| `blender_tour.py` | `decimate` / `undecimate` / 性能提示 覆盖所有水面对象 |
| `blender_probe_maparea.py` | 水面面数按所有水面对象求和 |
| `blender_rebuild_ground.py` | `clear_old()` 清掉所有水面对象 |
| `clamp_water.py` / `lower_water_local.py` / `carve_water_channel.py` | 逐个水面对象处理（原来是单对象） |
| `replace_water_plane.py` | 改成委托 `water_two_levels.build()`（原「一张平面 40.5」的做法作废） |
| `rebuild_water_from_map.py` | 同上，委托两级构建 |
| `rebuild_water_levels.py` | 头部标注：**只负责算单级水位图**，建水面走 `water_two_levels.py` |

**状态**：按用户 2026-11-02 指示，**没有重建 blend**（`continent_v23.blend` 是红线内的主产物，不许动）。
下次建大陆 / 裁框 / 同步时新脚本自动生效。冒烟测试已在小 blend（`16_wild2000_01_02`）跑通：
`Water_Main 8124 四边形` / `Water_West 1770 四边形`。

**遗留**：两张水位图并存 —— `water_level_map.npy`（单级，旧）与 `water_level_map_2lv.npy`（两级，新）。
旧图仍被 `build_final_map_heightmap.py` / `make_terrain_stages.py`（节点 2 的水深）引用；
是否切到两级图、以及 `02_water_deepen` 要不要按西盆地重算，等用户裁定。

---

## ★ 待办 · 瓜玛岛地形对齐（2026-11-02 用户裁定：**暂不处理**）

**目标**（等用户说做的时候再动手）：出一版 `guarma_height.png` / `guarma_color.png`，
和 `地图下载\瓜玛岛.jpg` 精确贴合，跟大陆那套（`deliverable\terrain/on_map\`）同口径。

**卡在哪**：官方瓜玛地图**没有配准数据**（`地图下载\配准结果.json` 里只有大陆的 5 个控制点），
而且那张图是**手绘风美术地图**（纸边 + 示意海岸线），轮廓对不上真实地形，自动匹配不可靠。

**需要用户提供**：2 个以上「像素坐标 ↔ 世界坐标」对应点。已知世界坐标：

| 地点 | 世界坐标 |
|---|---|
| 阿瓜多切斯 Aguasdulces | `1364.0, -6992.5` |
| 瓜玛营 Guarma Camp | `1426.3, -7328.9` |

**取点工具**：`python tools\make_map_aligned_terrain.py`（不带参数）会生成
`deliverable\terrain/on_map\guarma_grid.png`（200 px 红网格 + 坐标标注）。
拿到点后：

```powershell
python "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source\tools\make_map_aligned_terrain.py" --guarma-pts "<px>,<py>,1364.0,-6992.5;<px>,<py>,1426.3,-7328.9"
```

---

## ★ 2026-11-01 · 两层材质 B —— ✅ 已实施（规则见 `docs/格式与资产/RDR2_贴图分层与两层材质.md`）

### 0. 一句话（修正自原判断）

码头/墙体"整块发黑"有**两个原因**，原 TODO 只抓到了一个半：

1. 🔴 **主因：贴图池的 PNG 被缩图缩黑了。** PIL 12 对 RGBA 做 `resize` 是**按 alpha 预乘**的重采样，
   alpha 稀疏的贴图 RGB 会被乘暗。实测 `nbx_wall_woodplank_11long_rotted_ab`：
   **源 0.30 → 池子里 0.034**（原 TODO 记的"RGB 0.034、是遮罩"其实是这个 bug 的产物）。
   同时旧代码 `resize((512,512))` 还把 1024×512 的墙板纵向拉长一倍。
   修法 = `ytd_to_png.resize_max()`：**RGB 与 alpha 分开缩** + 等比。
2. **次因：两层材质只导了第 0 层。** `standard_2lyr*` 是 `lyr0 + lyr1 + control`，
   `standard_dirt` 是 `diffusetex + diffusetex2`。现已全部接上。

### 1. 做完了什么

| # | 内容 | 落在哪 |
|---|---|---|
| 1 | 贴图池刷新（修缩图缩黑 + 长宽比） | `tools/refresh_tex_pool.py`（新）；全量 32,878 张，**3,348 张被改写** |
| 2 | 两层取图规则 + 遮罩通道自动判定 | `tools/tex_slots.py` 的 `pick_layers()` / `mask_channel()` / `alpha_std()` |
| 3 | 抽 `l1/ct/dt/nm2/ma2/pl` 并写索引 | `tools/extract_slot_textures.py`（四段式扩展，写 `models[h].lyr` 与 `tex[i].ch`） |
| 4 | 材质节点 `mix(lyr0, lyr1, w)` | `tools/mat_rdr2.py`（颜色/法线/ORM 同一 Fac） |
| 5 | 构建与重挂开关 | `blender_continent --lyr on|off`、`relink_materials --lyr on|off` |
| 6 | 文档 | `docs/格式与资产/RDR2_贴图分层与两层材质.md`（新）· `tools/README.md` |

**全库实测（2026-11-01，68,744 个源模型）**：
* 绑上两层的模型 **7,984 个 / 21,870 个槽位**（第 1 层 21,662、control 9,035、dirt 9,740）；
* 其中 **6,965 个模型真有混合权重**（`python tools/audit_two_layers.py`）：
  `ctrl.R` 4,300 · `ctrl.G` 3,150 · `ctrl.B` 968 · `ctrl.A` 358 · `l1.alpha` 8,602 · 无权重（退回单层）4,073 槽；
* 调色板内嵌在 `.ydr` 体内，已解出 **9,147 张**进池，**但材质暂不使用**（语义未验证，见下）。

**验收（2026-11-01 已做）**：
* 🔴 **区域 #20 已用两层材质重建到官方路径** `deliverable\blender\regions\20_wild2000_05_02.blend`（959 MB，旧版 955 MB 已挪到
  `_scratch\two_layer\region20_prev.blend` 作回退）→ `VERIFY ENTITIES ... PASS` · `_check_region.py` **PASS**（18 类逐项一致）；
  清单已归位 `regions_support\20_wild2000_05_02\`；
* 场景内 **4,378 个材质里 1,356 个带两层混合（31%）**；
* 圣丹尼斯码头（世界坐标 ≈ `2543, -1570, 46`）同机位 A/B 出图：
  旧 blend 的木桩/栈桥是一片褐色糊，新 blend 能看到一根根木桩与板缝
  （图在 `D:\BrainMaker\大镖客2解包分析\_scratch\two_layer\region\region_sdn_dock_{old,new}.png`）。
  🔴 探针产物一律放**项目自己的** `大镖客2解包分析\_scratch\<主题>\`，不许放 `D:\BrainMaker\` 根（2026-11-01 用户裁定，见 AGENTS §1.9）。

### 2. 关键判定（留档，别再重查）

* **混合方向**：`w 大 → 第 1 层`。依据 = 控制图资产名直接叫第 1 层的素材
  （`nbx_ground_grass_bay_lsuh_mb` ↔ lyr1 `nbx_ground_grass_bay_lsuh_ab`），
  以及社区实现 Sollumz-RDR `RDR_create_2lyr_shader`（`diff_lyr_mix` 的 Color2 = `lyr1diffusetex`）。
* **取哪个通道**：不写死 R —— 专用 `_ct` 是灰度、复用 `_mb` 时往往只有一个通道在变，
  所以按**方差最大**挑，结果存在 `tex[i].ch`。
* **`standard_dirt` 没有控制图** → 第 1 层 `_abal` 的 **alpha** 就是权重（实测 alpha 0~0.89 起伏）。
* **调色板先不用**：码头那张 256×4 是「绿 / 青 / 白」渐变条，直接乘会把木头染绿；
  它要配合逐顶点 `COLOR0` 选择子（`tintpaletteselector` CBuffer）才有意义 —— 未验证。
* **逐顶点 `COLOR1`** 与 control 贴图**互不相关**（实测 |r| < 0.4），是两条独立通道；
  要用它得给 `.mdl` 加逐顶点属性并重导几何 —— 本轮没做。

### 3. 下一步（真要做的话）

1. 区域重建后**肉眼抽查码头/城墙/室内墙面**（区域 #20 已重建，见下）；
2. 若某个模型的两层看起来"反了"，先看材质的 `layer_mix` 自定义属性（记录权重来源），
   再用 `--lyr off` 对照 —— 不要靠改公式猜；
3. 想更进一步就是 §2 最后两条（调色板 / 逐顶点权重），都要先解 CBuffer 或改 `.mdl`。

### 4. 已知风险（保留）

- 材质每槽最多多 2~4 张图节点（第 1 层 albedo/法线/ORM + 控制图），大陆重建时间会变长；
- `control` 有 25 个 SDN 模型取不到（`nbx_wall_woodplank_14long_ct` 不在已解包的任何 `.ytd` 里）
  → 这些槽退回单层，不报错。

---

### 5. 本轮（2026-11-01）其他已完成事项

- 22 个区域裁剪全部 PASS；`unknown` 在 #19/#20 已清零（#20：254 个缩略图目视 → 250 条纠错 #91~340）。
- 分类规则：`struct` 只留桥/栈桥；码头→建筑；信号灯→部件；tower/build/kitchen/coop/tabacco/boathouse/props/水面/道岔等词缀。
- 修掉构建 bug：材质名截断（贴图纠错漏匹配）、隐藏集合 `matrix_world` 未求值（包围盒/埋深错误）。
- 资产目录重构复核通过；探针"专用目录 + 用完即删"规矩已落到
  `docs/格式与资产/分类体系与判定规则.md` §6.1。

---

## ★ 下一步（新 session 从这一节开始）：批量生成 22 个「有网格」的区域裁剪

> ✅ **2026-11-01 已完成**：22/22 块 `status=done`，`_check_region` 全部 PASS；
> 本节保留作流程/命令参考。**上一件事（两层材质 B）也已在同日落地**，见上面那一节；
> 现在要重做区域/大陆时会自动带两层材质（`--lyr off` 可回退）。

### 0. 一句话

大陆 v23 目前还是 **17 类旧规则**；分类规则已升级到 **21 类**（新增 `road`、`ruin`、`rail_decal`），区域 #19 已验证 PASS。接下来把**可见对象 > 0** 的 22 个区域各裁一个 blend，逐个对账；全部 PASS 后再对大陆跑一次，出 v24。

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
- 日志：`D:\BrainMaker\大镖客2解包分析\_logs\region_<编号>.log`。
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
cmd /c 'tools\run.cmd D:\BrainMaker\大镖客2解包分析\_logs\region_20.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --python tools\_unbuffer.py -P tools\blender_continent.py -- --out "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions\20_wild2000_05_02.blend" --lib "D:\BrainMaker\大镖客2解包分析\assets\lib_native" --only-tile wild2000_05_02 --step 8 --rails --full --no-water --corrections "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions_support\region_corrections.csv"'
```

**B. 已建好的区域只重跑分类/纠错**（约 3~5 分钟，不重建几何）

```powershell
Set-Location "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source"
cmd /c 'tools\run.cmd D:\BrainMaker\大镖客2解包分析\_logs\region_20_fix.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions\20_wild2000_05_02.blend" -P tools\_unbuffer.py -P tools\_apply_corrections.py -- --corrections "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions_support\region_corrections.csv" --out "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions\20_wild2000_05_02.blend"'
```

**C. 对账（每块必跑）**

```powershell
python "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source\tools\_check_region.py" --tile wild2000_05_02 --audit "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions_support\20_wild2000_05_02\manifest_20_wild2000_05_02.jsonl"
```

> 说明：A 构建会把 manifest 写在 blend 旁边。**必须**把它移到 `regions_support\<编号>_<tile>\`（`_apply_corrections.py` 会自动挪；纯 A 构建要手动 `Move-Item`）。判据永远是 `_check_region.py` **PASS**（21 类计数逐项一致）。

### 4. 批量驱动（已实现：`tools/build_regions.py`，2026-10-31）

要求：

| 项 | 规定 |
|---|---|
| 输入 | `regions_support/region_list.csv`（列：`number,tile,blend,visible,status`） |
| 执行 | **一次一个 Blender**（内存/磁盘），顺序按编号；每块调 A 命令 |
| 断点 | `status=done` 跳过；`--resume` 默认开启；`--force` 重跑；`--only 19,20` 指定 |
| 归位 | 构建完把 `manifest_<编号>_<tile>.json/.jsonl` 移到 `regions_support\<编号>_<tile>\` |
| 对账 | 立刻跑 `_check_region.py`；**FAIL 就停**，不继续下一块 |
| 日志 | `D:\BrainMaker\大镖客2解包分析\_logs\region_<编号>.log`；驱动自身日志 `_logs\build_regions.log` |
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
cmd /c 'tools\run.cmd D:\BrainMaker\大镖客2解包分析\_logs\continent_v24.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b "D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_v23.blend" -P tools\_unbuffer.py -P tools\_apply_corrections.py -- --corrections "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions_support\region_corrections.csv" --out "D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_v24.blend"'
```

2. 验收：manifest `verdict=PASS`（`unknown` 允许为 0，看 `classes_missing` 为空）、`_check_region.py` PASS；`_check_class_visibility.py` 确认 `road` 隐藏、`ruin` 显示。
3. 之后所有区域重建都自动继承 21 类 + 纠错清单。

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

### 分类体系（现已 21 类，规则唯一真身 = `tools/class_rules.py`）

- 新增类：`road`（道路，**默认隐藏**）· `ruin`（废墟，**默认显示**）；
- 硬规则：**名字含 `junc` 一律 road**（无例外）；名字含 `ruin` 一律 ruin（`lod/underground` 除外）；
- 纠错清单：`regions_support\region_corrections.csv`（40 条，id 1~4 / 6~41；16~41 = 区域 #19 的 unknown 清理）；
- 回归：`tools/rules_cases.csv`（16 条用例），`_check_rules.py` 全过；内置关键词最近补了 `infirmary`（bldg）、`_bri(?!ck)`（struct）
- 改分类流程与坑：见 `docs/格式与资产/分类体系与判定规则.md`。

### 相关脚本

| 脚本 | 用途 |
|---|---|
| `tools/class_rules.py` | **规则唯一真身**（21 类 / RULES / 硬规则 / 纠错解析） |
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
| `D:\BrainMaker\大镖客2解包分析\_logs\test2.bat` / `test_launcher.bat` / `bat_dump.txt` | 调试 bat 的临时文件 |

---

## 禁止事项（交接红线）

1. **不要改 `continent_v23.blend`**（7.3 GB 主产物）；要升级就出 `continent_v24.blend`；
2. **不要在 `D:\BrainMaker` 根放任何文件**；新目录先问（见 `AGENTS.md` §1.9）；
3. **不要手动改 `regions_support\region_corrections.csv` 之外再抄一份规则**；规则值只进 `class_rules.py`；
4. **不要跳过 `_check_rules.py` / `_check_region.py`**；
5. **不要同时跑两个 Blender**（内存/磁盘竞争）；
6. **不要生成 `.blend1`**（构建脚本设 `save_version=0`）。
