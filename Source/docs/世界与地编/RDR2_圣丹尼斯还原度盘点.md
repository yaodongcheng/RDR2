# RDR2 · 圣丹尼斯还原度盘点（缺什么 / 怎么实现 / 工作量）

> 2026-10-18。目的：把"圣丹尼斯还差什么"一次说清，并给出每块的**游戏内实现原理 + 数据位置 + 我们该怎么做**。
> 结论先行：**静态城市已基本还原（建筑 96%、地形/水/天空已接游戏数据）**；
> **动态世界（火车、电车、行人、车马）一个都还没做**——但它们的数据**全是可读的文本/XML**，完全能还原。

---

## 0. 总量对账

| 指标 | 数值 |
|---|---|
| 圣丹尼斯 zone 内 ymap 实体（去重） | **25 136** |
| 已导出到 Blender 的实体 | **3 371**（13.4%） |
| 其中建筑类（`new_*`） | 2 698 → 已导 **2 638**（97.8%） |
| 其中街道道具/植被（`p_*` 等） | 18 631 → 只导 **660**（3.5%） |
| 无法解析名字的哈希实体 | 3 207（多为地形/水体/LOD 体积，非建筑） |

**一句话**：楼基本齐了，**街道是空的**。

---

## 1. 已完成（不用再动）

| 模块 | 现状 | 数据来源 |
|---|---|---|
| 城市建筑 | 2 260 模型 / 2 275 实例，不焊接、带法线、512² 贴图 | `levels_2.rpf → area/nopq_15_18/new_*.rpf` |
| 室内 MLO | 30 包全解，27 个按 MLO 实体落位 | `levels/rdr3/interiors/new_*_int.rpf` |
| 地形 | 20 瓦片颜色图 → 4096² 贴图 + 4 m 高程 | `<tile>_t` + `H4.npy` |
| 水 | 一整块平面 + `water_level` 驱动，水位可实时调 | 地形等高线 |
| 天空/光照 | 物理天空（多次散射）+ Sun 联动 + AgX | — |
| 街道道具（部分） | 179 ydr / 660 实例（仅 `p_new_01.rpf`） | `props/areas/p_new_01.rpf` |
| NPC 模型/动画 | 412 个 GLB（2.1 GB）、357 段动画 JSON、446 个 `.ycd` | metapeds / `.ycd` |

---

## 2. 缺口清单（按视觉影响排序）

### 2.1 街道道具与植被 ★★★（影响最大）

**缺**：18 558 个实例 / 2 120 种模型。

| 类别 | 实例数 | 典型模型 |
|---|---|---|
| 垃圾/杂物 | 4 956 | `p_crate01x` `p_barrel05b` `p_pallet02x` `p_sandbags02x` |
| 路灯/照明 | 2 338 | `p_lamptelegraphpole01x` `p_walllampnbx01x` `p_lightpolenbx04x` `p_lantern09x` |
| 植被/盆栽 | 1 911 | `p_pot_plant_05b` `p_dirtpot01x` `p_planternbx04a` |
| 桌椅/市集 | 1 615 | `p_chairwhite01x` `p_chair24x` `p_benchnbx03x` |
| 围栏/栏杆 | 955 | `p_fence04ax/bx/cx` `p_emrfence02cx` |
| 船（静态） | 165 | `p_ship*` `p_boats*` |
| 火车/电车部件 | 45 | `p_trolley*` `p_rail*` |
| 招牌/标识 | 33 | `p_signs*` |

**游戏里怎么做**：全部是 **ymap 实体 → archetype → `.ydr`**，和建筑同一套管线，只是分散在
`levels/rdr3/props/**` 的 **149 个分类包**里（`p_light*` / `p_fence` / `p_debris` / `p_plant` /
`p_seating` / `p_table` / `p_storage` / `p_waterfront` / `p_roadside` …）。

**★ 实测发现（重要）**：这些道具**很多不是 `.ydr`，而是 `.yft`（fragment 碎片模型）**。
我们原来的管线只吃了 `.ydr`，所以街上才空——`p_crate01x` 就在 `p_storage.rpf` 里以 `p_crate01x.yft` 存在。

**实测覆盖率**：抽了 19 个道具包（`p_light*` `p_fence` `p_debris` `p_plant` `p_seating` `p_table`
`p_waterfront` `p_storage` `p_roadside` `p_barrier` `p_light_hanging01/ground01` `p_furniture` `p_store` `p_sign` …），
**18 558 个缺失实例中覆盖 8 847 个 = 47.7%**；剩余 9 711 个还要继续抽包（`p_household` `p_lumber` `p_office`
`p_rooftop` `p_window` `p_door` `p_vehicle_static` `p_kitchen` …）。

**`.yft` 能不能解？能。** 实测 `p_crate01x.yft` → `extract_frag()` 解出 4 个 mesh / 1 053 三角，
贴图 `p_barrela_1_ab` 正常。所以管线只需**加一条 `.yft` 分支**即可。

> 植被补充：世界植被有独立系统 `levels/rdr3/props/vegetation/rdr_*.rpf`（31 包：birch/bushes/oak/palm/grass/flowers/crops…），
> 但**圣丹尼斯城内**只有 167 个 `p_*` 植被实体 + 2 个 `new_*`，城市绿化主要是 `p_plant` 的盆栽/行道树 + 地形颜色图里的草。

---

### 2.2 火车 ★★★（动态感的门面）

**数据（全部是纯文本，已实测）**：

```
data/levels/rdr3/trains1.dat      规则：473 454 close，然后每行
                                   c  x1 y1 z1  x2 y2 z2  x3 y3 z3  宽 标志
trains2.dat / trains3.dat
trains_nb1/2/3.dat                （New Bordeaux = 圣丹尼斯）
trains_rob3.dat
trains_intersection1_3 / 1_ann / 2_3 / 2_ann / 3_cor
trains_old_west01..03 / _intersection01/02
```

**游戏里怎么做**：火车由 AI 沿这些样条推进（含信号、停站、道岔），车厢是独立 actor。
**我们怎么做**：
1. 解析 `c` 行 → 折线/样条；
2. Blender 里 `Curve` + `Follow Path`，车头挂 3~5 节车厢（车厢用固定偏移跟随前车）；
3. 道岔（intersection）用多条曲线 + 分支切换。
**工作量**：解析半天 + 场景搭建 1 天。**风险低**（文本格式、模型已解包）。

---

### 2.3 有轨电车（圣丹尼斯特色）★★★

```
data/levels/rdr3/trolley1..4.dat                    电车线路（245 节点 / 77 段起）
trolley_intersection1_2 ... 7.dat                   道岔
sd_trolley_cable01..11.dat                          架空接触网（11 段）
trolleycabletracks.xml                              电缆轨道配置
data/levels/rdr3/ai/vehiclepoints/trolley01x.meta   候车/发车点
```

格式与火车一致（`x y z 速度 标志 [配置名]`），实测第一条线路就在圣丹尼斯主街
（`2774.8 -1350.44 ...`）。车站模型已导出（`new_trolleydepot` 室内）。
**做法**：同火车，路径动画 + 沿线电缆（`sd_trolley_cable` 直接生成曲线/管状体）。
**工作量**：1 天。

---

### 2.4 行人 / 动物 ★★（有基础，缺"活起来"）

**已有**：412 个 NPC GLB、357 段动画、446 个 `.ycd`。

**游戏里怎么做**（三层）：
| 层 | 文件 | 作用 | 可读性 |
|---|---|---|---|
| 模型集 | `data/ai/ambientpedmodelsets.meta`（XML，1 MB） | **971 个 ModelSet**（`Models/Variations/TimeOfDay/Probability`） | ✅ 完全可读 |
| 场景行为 | `data/ai/scenarios/*.meta`（amb_work / amb_rest / amb_misc / mech_ransack …） | 站桩、干活、翻找等"情景动作" | ✅ 可读 |
| 车流密度 | `data/levels/rdr3/popcycle.dat`（**纯文本**） | 按区域 + 2 h 时段 + 工作日/周末给**车辆**密度；`TRAFFIC_ST_DENIS_MAIN_SCHEDULE` 就是圣丹尼斯主街（MaxCars 100、HORSE_SDN 12 / COACH_SDN_* 25~30） | ✅ 可读 |
| 行人密度 | **未找到** GTA 那种 `pedpopcycle` 文本；应在 `packs/base/data/metapeds/metapeds*.rpf`（PSIN 二进制）或引擎内 | 半黑盒 | ⚠️ 需逆向 |
| 走路 | `levels/rdr3/navmeshes0..5.rpf` | 导航网格（**尚未抽取**） | ⚠️ 需解析 |

**我们怎么做**：
- 抽取 navmesh → Blender 里做"可行走面"；
- 用 `popcycle` 的密度在街区内随机撒人，沿 navmesh 做循环路径；
- 动画用已有的 357 段（走/站/坐/聊天）；
- 车厢/电车上下客还能用 `transportanimations/default_trolley/*`。
**工作量**：navmesh 解析 1~2 天 + 简单循环 AI 2 天。**这是最"活"的一块，但也是最重的**。

---

### 2.5 车马（马车/骑马）★★

- 模型：`packs/base/levels/rdr3/vehicles.rpf`（**550 MB**，马车/货车/马）
- 密度/配比：同 `popcycle.dat`，圣丹尼斯主街 `HORSE_SDN 12 / COACH_SDN_SMALL_POSH 30 / COACH_SDN_LARGE 25 …`
- 路线：车辆走 navmesh 车道（`data/levels/rdr3/ai/vehiclepoints/*.meta` 定义了停车/发车点）

**做法**：抽 3~5 种马车 + 3 种马 → 沿主干道样条跑（比行人简单，不需要复杂寻路）。
**工作量**：1~2 天。

---

### 2.6 粒子 / VFX ★（氛围）

- `levels/rdr3/area/nopq_15_18/new_*_vfx.rpf`（蒸汽、烟、雨、枪火代理）
- `packs/base/data/effects/vfxvehicleinfo.ymt`
- **现状**：我们只导了静态几何，`vfx` 代理网格被剔除。

**做法**：这批是 `.ydr` 代理 + 游戏侧粒子系统参数，**真正还原需要解粒子定义**（难）；
低成本替代：蒸汽船/火车烟囱用 Blender 粒子或体积烟手工补。
**工作量**：手工 1 天（近似），精确还原 3 天+（不建议）。

---

### 2.7 天气 / 昼夜 ★★

- `data/levels/rdr3/weather.xml`
- `data/timecycle/timecycle_mods_1.xml`、`w_*.xml`（各种天气预设）
- **现状**：固定一套黄昏光照。

**做法**：解析 timecycle 的**太阳角度/色温/雾密度/云量**曲线 → Blender 里做一天的时间轴动画（或几套预设切换）。
（`timecycle_mods_1.xml` 31 KB，是文本，可读。）
**工作量**：1 天（做 4 套：清晨/正午/黄昏/夜）。

---

### 2.8 室内 MLO 门 / 房间可见性 ★

- 现状：30 个室内包是"整包平铺"，没有门、没有房间裁剪。
- 需要：解 `ytyp` 的 `CMloArchetypeDef.rooms / portals / entities`，按房间做 portal culling。
- **工作量**：2~3 天（RDR2 的 MLO 结构与 GTA V 不同，需要试错）。

---

### 2.9 碰撞 / 物理 ★

- `.ybn`（碰撞网格）在区域包里（我们抽 p15 时看到 5 个），`nopq_new_area_lod_combine_collision.rpf`。
- 用途：让 Walk 模式贴地、做遮挡剔除、物理模拟。
- **工作量**：1 天（导入为 Blender 碰撞体）。

---

### 2.10 音频 ★（可选）

- `.awc` 音频包 + `audio` 元数据；环境音/马蹄/电车铃。
- **工作量**：解析 2 天，或直接用免版权音效替代（半天）。

---

### 2.11 水面真实高度（技术债）

- `waterheight.dat`（magic `RTAW`）：192² 头 + 复杂格网，**目前未解开**，所以水位是"区域统一值 + 手动调"。
- 解开后能做到"哪片洼地是干农田、哪条渠有水"。
- **工作量**：逆向 2~3 天（有风险）。

---

## 3. 建议推进顺序

| 优先级 | 任务 | 理由 | 预计 |
|---|---|---|---|
| **P0** | 街道道具 + 植被（2.1） | 管线已通，1.8 万实例，观感提升最大 | 1~2 天 |
| **P1** | 火车 + 电车沿路径（2.2/2.3） | 数据是文本、模型已解包，动态感强 | 1~2 天 |
| **P2** | 车马沿主干道（2.5） | 同上，比行人简单 | 1~2 天 |
| **P3** | 行人（2.4） | 需要 navmesh + 简单 AI，最重但最"活" | 3~4 天 |
| **P4** | 天气/昼夜（2.7）、VFX 近似（2.6） | 氛围提升 | 1~2 天 |
| **P5** | MLO 门/房间（2.8）、碰撞（2.9）、音频（2.10） | 交互/物理向 | 各 1~3 天 |
| **P6** | `waterheight.dat`（2.11） | 技术债，风险高 | 2~3 天 |

---

## 4. 关键文件索引（可直接取用）

```
城市/道具
  levels_2.rpf → levels/rdr3/area/nopq_15_18/new_*.rpf          城市
  levels_3.rpf → levels/rdr3/props/areas/p_new_01.rpf           已抽（179 ydr）
  levels_?.rpf → levels/rdr3/props/generic/p_light*.rpf         路灯
                 levels/rdr3/props/generic/p_fence.rpf
                 levels/rdr3/props/generic/p_debris.rpf
                 levels/rdr3/props/generic/p_plant.rpf
                 levels/rdr3/props/generic/p_seating.rpf / p_table.rpf
                 levels/rdr3/props/generic/p_waterfront.rpf
  levels/rdr3/props/vegetation/rdr_*.rpf（31 包，世界植被）

动态
  common_0.rpf → data/levels/rdr3/trains*.dat / trolley*.dat    线路（文本）
                 data/levels/rdr3/popcycle.dat                  人流/车流密度（文本）
                 data/ai/ambientpedmodelsets.meta               NPC 模型集（XML）
                 data/levels/rdr3/weather.xml / data/timecycle/*.xml
  levels_0/1.rpf → levels/rdr3/navmeshes0..5.rpf                导航网格
  packs_0.rpf → packs/base/levels/rdr3/vehicles.rpf             车马（550 MB）

其它
  各 area 包 → *_vfx.rpf                                         粒子代理
  各 area 包 → *.ybn                                             碰撞
  common_0.rpf → data/levels/rdr3/waterheight.dat                真实水位（未解）
```

---

## 6. 本轮实测验证（把估算换成数字）

| 项 | 验证方式 | 结果 |
|---|---|---|
| 道具缺口 | 19 个道具包实抽 + 名字比对 | 18 558 → 覆盖 **8 847（47.7%）** |
| 道具载体 | 检查扩展名 | **大量是 `.yft`**（`props2` 里已抽出 1 175 个 `.yft`） |
| `.yft` 可解性 | `extract_frag('p_crate01x.yft')` | ✅ 4 mesh / 1 053 tri / 贴图正常 |
| 火车线路 | 解析 `trains1/2/3`、`trains_nb1-3`、交叉线 | `trains1` 473 节点 / **15 055 m** / 近城 111 节点；`trains_nb1-3` 全部在城内（451/118/104 m） |
| 电车线路 | 解析 `trolley1-4` | `trolley1` **245 节点 / 776 m，245 个节点全部落在圣丹尼斯**；trolley2/3/4 = 162/363/212 m |
| 接触网 | 解析 `sd_trolley_cable01/03` | 398/146 节点，778/361 m，z 51.7~59.5（架空） |
| 导航网格 | 抽 `navmeshes0.rpf`（149 MB） | **620 个 `.ynv`**，按 `navmesh[row][col]` 网格命名；RSC8 解压 ✅（body 2.8 MB），`.ynv` 结构待解析 |
| 行人模型集 | 读 `ambientpedmodelsets.meta` | **971 个 ModelSet**（XML） |
| 车流密度 | 读 `popcycle.dat` | `TRAFFIC_ST_DENIS_MAIN_SCHEDULE`：MaxCars 100、`HORSE_SDN 12 / COACH_SDN_SMALL_POSH 30 / COACH_SDN_LARGE 25` |

> 结论：**道具和火车/电车的数据都已被实际读完并验证可用**；剩下的不确定项只有
> 行人密度（半黑盒）和 `.ynv` 结构（可解但要写解析器）。

**线路落地验证图**：把解析出的线路按世界坐标画到地形颜色图上（`export/levels/world/blender/shots/routes_overlay.png`）——
红色 = `trolley1`（776 m 环线）、黄色 = `trolley3`、白色 = `sd_trolley_cable01`（架空线）、
蓝色 = `trains_nb1-3`（滨水铁路），全部落在城市灰色范围内，**坐标映射正确**。

---

## 5. 一句话总结

> **楼已经很完整了，缺的是"城市里的人间烟火"**：18 558 个路灯/围栏/箱子/盆栽，
> 以及火车、电车、马车、行人这四类"会动的东西"。
> 前四类（道具、火车、电车、车马）**数据全是文本 + 模型已解包**，按现有管线 3~5 天能把圣丹尼斯做成"活的"。
> 行人最重（要 navmesh + 简单 AI），但模型和动画我们已经有了。


---

## 7. 开工进度（2026-10-18 晚）

### ✅ P0 街道道具（已完成）

| 项 | 结果 |
|---|---|
| 新增管线 | `tools/export_sdn_props2.py` —— **支持 `.yft` fragment**（`load_frag_model`：找最重 drawable，合并大件，读 vdecl 取 POSITION/NORMAL/UV） |
| 抽包 | 39 个道具包（`p_light*` `p_fence` `p_debris` `p_plant` `p_seating` `p_table` `p_waterfront` `p_storage` `p_household` `p_kitchen` `p_door` `p_window` `p_furniture` `p_store` `p_sign` …） |
| 导出 | **3 820 个模型 / 20 742 个实例**，36 块 glTF，**1.2 GB** |
| 覆盖率 | 缺失 18 558 → 名字覆盖 **17 032（91.8%）** |
| 落地 | 替换旧 `Props` 集合 → `sdn.blend`（2.4 GB） |

**观感**：街面出现了**路灯、电报杆、悬挂花篮、货箱、长椅、摊位、港口小船**，`shots/props_street.png` 可直接对比。

### ✅ P1 有轨电车（已完成）

| 项 | 结果 |
|---|---|
| 线路 | `trolley1.dat` 245 节点 → Blender **Cyclic Curve**（776 m 环线） |
| 车体 | 从 `packs_0.rpf → packs/base/levels/rdr3/vehicles.rpf` 抽出 **`trolley01x.yft`**（18 geom / 51 799 顶点）+ 贴图，转 glTF |
| 动画 | `TrolleyRig`（Empty）+ **Follow Path** 约束，`offset_factor` 1→1800 帧线性，24 fps ≈ 75 s 一圈（≈10 m/s） |
| 验证 | 帧 200 渲染 `shots/trolley_close_f200.png`：电车正确落在街道上、朝向沿轨道；帧 1/200/400/800/1200 位置连续变化 |

**怎么播**：打开 `sdn.blend` → 把 `TrolleyRig` 保持选中 → 时间轴按 **空格** 播放（帧 1~1800）。

### ✅ P1 火车（已完成）；行人已移除

| 项 | 做法 | 结果 |
|---|---|---|
| 火车 | `vehicles.rpf` 抽 `ghosttrainsteamer/passenger/caboose/coalcar`（合计 4.3 万顶点）→ 4 节车厢各自 `Follow Path`，按 31 帧递延拉开间距，跑 `trains_nb1` 环线（868 m / 1200 帧） | 帧 300 时车头在 `(2765, −1414)`，车尾在 `(2808, −1363)` |
| 行人 | ⚠️ **已按用户要求移除**（走路蒙皮有瑕疵、形象单一，观感诡异）。模型/动画仍在 `export/npc` 与 `export/animations_ped` | 场景里不再有行人 |
| 性能 | 只加 **14 个 actor**；唯一顶点 62.4M → 62.8M（+0.6%）；文件 2.39 → 2.40 GB | 对打开速度基本无影响 |

**踩坑记录**：
1. `player_zero_walk.glb` 的蒙皮是坏的（走路时炸成尖刺）→ 改用 `player_zero_ue_walk.glb`；
2. 导入后网格**既 parent 到骨架又挂了 Armature 修改器**（双重变换），一播动画就炸 → 解除 parent、只保留修改器；
3. `ghosttrain*` 是“幽灵火车”（贴图带 alpha，几乎全透明）→ 材质改不透明 + 深灰金属色。

**怎么播**：`sdn.blend` 里直接 **空格**；集合 `Actors_Train` / `Actors_Peds` 可单独隐藏。

### ⏭ 下一步
- 火车（`trains1.dat` 15 km + `trains_nb1-3` 城内），车厢多节跟随；
- 马车/骑马（`vehicles.rpf` 里 `p_cart*` / `coach*`）；
- 行人（先解 `.ynv`，再用 971 个 ModelSet + 已有 412 模型/357 动画）。


---

## 8. 性能：按摄像机分块显隐（Blender 版"流式"）

**问题**：道具补齐后场景 2.4 GB / 约 5 600 万顶点，视口移动很卡。

**Blender 没有真正的运行时卸载**，但可以做**按距离剔除**（数据在内存，不参与绘制）：

已写进 `sdn.blend` 的文本块 `zone_stream.py`（也在 `tools/zone_stream.py`）：

1. 打开 `sdn.blend` → 顶部 **Scripting** 工作区
2. 左侧文本块选 `zone_stream.py` → 点 **▶ Run Script**（或 `Alt+P`）
3. 视口按 **N** → 「分块加载」面板 → 调 **半径**（默认 350 m）

脚本做的事：
- 已经把 94 个 glTF 分块各收进一个 `TILE_*` Collection
- 每 0.35 s 读一次视口摄像机位置，**超出半径的块自动 hide_viewport/hide_render**
- 关掉时一键恢复全部

**额外提速建议**：
- 视口用 **Solid（Z → Solid）**，别用 Material Preview / Rendered；
- 顶部 **Simplify**（渲染属性 → Simplify）勾上，Viewport 细分/纹理降级；
- 只看某一片时用 **Local View**（选中物体 → `Numpad /`）；
- 需要更狠：把 `Tools` 里 `ZONE_OT_slim` 思路的**道具减面**跑一次（需要我做可以再说）。

**注意**：分块显隐只降低"绘制负担"，**不释放内存**（Blender 没有运行时卸载）。
如果内存也吃紧（实测渲染时 ~30 GB），真正的解法只有两条：
1. **按区拆文件**（4 个象限各一个 `.blend`，每次只开一个）——我可以生成；
2. **减面/降贴图**（道具 Decimate 0.4~0.5、贴图 256→128）——画质略降。

**实测结构**：94 个 `TILE_*` 集合、23 131 个对象；`Terrain`/`Water` 保留在场景根、始终可见。
