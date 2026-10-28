# RDR2 ymap 实体变换解析（2026-10-26 修正）

> 起因：Blender 重装的大陆里，夏洛蒂家的主屋**烟囱左右反了**，且"有些物件差 180°、有些差 45°"。
> 最终定位：**四元数旋向反了**（RDR2 ymap 与 Blender 的旋转方向相反）。
> 这份文档记录证据链和修法，避免以后再踩。

---

## 1. 实体字段布局（已逐字节核对）

`CMapEntity` 结构 144 字节（`jklm_15_18_area_lod_combine_metadata/0xC7EDFFEF.ymap`，struct `0xce501483`）：

| 偏移 | 类型 | 内容 | 主屋实测值 |
|---|---|---|---|
| +8 | uint32 | archetype hash | 611244496（`roc_01_ext_home01`） |
| +32 | float3 | position | 2989.4629 / 2189.3975 / 168.5727 |
| +44 | float | —（与 pos.x 相同，未使用） | 2989.4629 |
| +48 | float4 | rotation (x,y,z,w) | 0 / 0 / 0.7660 / −0.6428 |
| +64 | float2 | scale（sxy, sz） | 1.0 / 1.0 |
| +72 | uint32 | flags | 3 |
| +76 | float | lodDist | 70.0 |
| +132 | uint16 | parentIndex | 0xFFFF = **−1（无父）** |

**结论：字段偏移全部正确，`tools/ymap_entities.py` 读的 pos/quat/scale 没有错位。**
（早前怀疑的"17 字段"是我数错了，`town_data` 实际是 16 字段：arch+pos+quat+sxy,sz+bbox6。）

## 2. 镜像排查：没有镜像

用 **mesh bbox 的 min/max 绝对值** 对 **ytyp archetype bbox**（比只看 extent 严格，镜像会让 min/max 互换）：

| 模型 | arch bbox min..max | mesh bbox min..max | 判定 |
|---|---|---|---|
| roc_01_ext_home01 | [−9.90, −7.53, −4.05]..[8.55, 9.75, 4.05] | 完全相同 | x/y/z 一致 |
| roc_shed_01 | [−3.93, −3.97, −3.36]..[3.92, 3.95, 3.48] | 完全相同 | 一致 |
| roc_leanto | [−3.26, −2.99, −1.75]..[3.30, 3.13, 1.61] | 完全相同 | 一致 |
| roc_01_ext_well | [−1.13, −1.18, −1.37]..[1.18, 1.18, 1.37] | 完全相同 | 一致 |

**⇒ 模型几何没有镜像，scale 无负值，问题不在几何。**

## 3. 根因：四元数需要取共轭

### 3.1 决定性证据 —— 栅栏连续性

`p_fence04bx` 有 21 段，围成一个畜栏。如果旋转正确，**相邻段的端点必须首尾相接**。
把 21 段按空间最近邻排成链，用每段的 yaw 算两个端点，统计相邻段最小端点距离：

| 方案 | 相邻段端点平均距离 | 最大 |
|---|---|---|
| 原样 yaw | **1.65 m** | 3.24 m |
| **yaw 取反（共轭）** | **0.56 m** | 2.08 m |

段本身长 2.81 m。原样方案下相邻段错开一整段，栅栏是"断"的；取反后基本接上。

### 3.2 视觉复核

主屋烟囱位置（游戏照片：**左端**）：

| 方案 | 烟囱位置 | 与游戏 |
|---|---|---|
| 原样 | 右端 | ✗ |
| **共轭** | **左端** | ✅ |

## 4. 修法

`tools/blender_continent.py` 装配实体时：

```python
# 以前（错）
ob.rotation_quaternion = (e[7], e[4], e[5], e[6])          # (w, x, y, z)

# 现在（默认）
ob.rotation_quaternion = (e[7], -e[4], -e[5], -e[6])       # 共轭
```

命令行开关：

- **默认已开启共轭**
- `--no-conj-quat` 可关闭（回退到旧行为，用于对照）

> 为什么是共轭：RDR2 ymap 的四元数旋向与 Blender 的 `rotation_quaternion` 相反
> （等价于"模型→世界"与"世界→模型"的定义差异，或左右手系差异）。
> **不是**镜像——镜像会让 bbox 的 min/max 互换，实测没有。

## 5. 附带修掉的两个问题

| # | 问题 | 修法 |
|---|---|---|
| 1 | `settlements_bannerlord.csv` 里 `hso`/`abe`/`roc` 三个点的 `u,v` 是 `0,0`，PAD 把它们算到地图西北角，地形没被压平 | 已按 `settlements_world_v2.csv` 的正确 u/v 修正 |
| 2 | PAD 按"区域实例 z 的中位数"压平，roc 的建筑高度分散（坟 158.5 / 主屋 168.6），中位算错 → 房子悬空 3.45 m（或反过来被埋 9 m） | 分区装配加 `--no-pad`，用原始 H4 地形。**roc 处 H4=165.23、建筑底 164.55，本来就吻合（差 0.69 m）** |

## 6. 复现 / 重建

```bash
# 分区（威拉德之息），原始地形 + 共轭旋转
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b -P tools/blender_continent.py -- \
  --out ".../deliverable/blender/willard/willard.blend" \
  --lib ".../assets/lib_native" \
  --only-tile wild2000_05_00 --no-pad
```

> `--no-pad` 只建议用于**分区/POI**。整图重建仍要 PAD（城镇需要），
> 但要注意 POI 会被 PAD 误压平——见 §5 第 2 条，后续应让 `poi`/`camp` 跳过 PAD。

---

## 7. 植被实例（368 字节结构，2026-10-26 追加）

### 7.1 数据在哪

植被**不在** `map_metadata/*_lod_combine*`，而在：

```
levels/rdr3/terrain/instance_placement/<area>_instance_placement.rpf
  ├── j_15__trees_0.ymap … j_18__trees_3.ymap   （树/灌木/石头，368 字节结构）
  └── *_grass_*.ymap                             （草丛，同为 368 字节）
```

### 7.2 结构（与建筑的 144 字节完全不同）

| 偏移 | 类型 | 内容 |
|---|---|---|
| +8 | uint32 | archetype hash |
| +48 | float4 | rotation（实测多为 0，植被不需要精确朝向） |
| **+144** | **float3** | **position（世界坐标）** ← 不是 +32 |
| +32 | Vec3 | 恒为 0（未使用） |

> 用建筑的 `+32 position` 去读植被，会得到全 0 —— 这就是之前"植被坐标读不出来"的原因。

### 7.3 验证（jklm_15_18 区域）

| 指标 | 结果 |
|---|---|
| 解析出的实例 | 1,382 |
| 坐标合理率 | **100%**（如 2959.6, 1534.7, 59.8） |
| 能命名 | **100%**（`p_tree_log_08_upb` / `rdr_bush_scrub_aa_sim` / `roa_rock_scree_04`） |
| 模型在库 | **99.2%**（1,371 / 1,382，只缺 8 个 lodgepole 变体） |

### 7.4 重要限制：ymap 里的植被只是"稀疏实体层"

把 1,382 个实例合并进 tiles 后渲染，**密度远低于游戏内的森林**：

- 该区域 ~2000×2000 m 只有 1,168 个带植被的 tile 实例（约 0.3 个/1000 m²）
- 游戏里 RDR2 的茂密森林是 **GPU instanced / point-cloud 层**，不在这套 ymap 实体里

**结论**：补 ymap 植被能让野外"有树"，但**不可能靠它还原游戏的植被密度**。

### 7.5 工具

`tools/parse_veg.py`：

```bash
uv run python tools/parse_veg.py --scan-only          # 统计
uv run python tools/parse_veg.py --tile wild2000_05_01  # 合并进指定 tile
```

---

## 8. 室内 MLO 布局（2026-10-26 追加）

### 8.1 布局在哪

室内模型和**摆放**是分开的：

| 内容 | 位置 |
|---|---|
| 室内模型（ydr/ytd） | `levels/rdr3/interiors/<name>_int.rpf` |
| **摆放（MLO）** | 同包的 **`<name>.ytyp`**（不是 ymap！） |

例：夏洛蒂家 → `levels/rdr3/interiors/roc_house_int.rpf` 里有 `roc_house_int.ytyp`（30 KB）。

### 8.2 ytyp 里的 144 字节 entity

ytyp 的 `0xce501483` block（455 条 × 144 字节）就是每个摆放项：

| 偏移 | 类型 | 内容 |
|---|---|---|
| +8 | uint32 | archetype hash |
| +32 | float3 | **position（室内局部坐标，±10 m）** |
| +48 | float4 | rotation (x,y,z,w) → Blender 要**取共轭** |
| +132 | uint16 | parentIndex（65535 = 无父） |

**实测（roc_house_int.ytyp）**：

| 指标 | 值 |
|---|---|
| 摆放项 | **455** |
| 唯一模型 | **241**（100% 能命名） |
| 模型在库 | 207（86%） |
| 缺失 | 34（灯光盒 `roc_house_lightbox*`、`roc_light_parent`、部分 `p_*_dressing`） |

样例：餐椅 `p_chairdining03x`(0.94,1.86,-1.10)、角柜 `p_cornercabinet02x`(-0.80,-3.91,-1.10)、水槽 `p_sink04x`(2.65,-0.58,-1.12)、铜锅 `p_copperpan03x`(4.79,0.60,0.47)。

### 8.3 装配结果

`tools/parse_interior_mlo.py`（解析布局） + `tools/make_interior.py`（装配渲染）：

- 455 项中 **415 项成功摆放**，40 项模型缺失跳过
- 产物：`deliverable/blender/willard/roc_interior.blend` + `roc_interior.png`
- **家具按真实变换就位**：餐桌+椅、橱柜、壁炉、书桌、吊灯、酒瓶、木箱

> 校验方法：隐藏墙壳/天花（>6 m 的大件），从上方俯视；如果布局错，家具会堆在原点或穿墙。

---

## 9. 小道具（prop）贴图缺失的追查记录（2026-10-26）

### 9.1 现象

室内 415 个对象里 **46.5% 有贴图**，其余用中性色。缺图的是小道具：
`p_coin01x`(硬币)、`p_can04x/05x/06x`(罐头)、`p_book05x/08x`(书)、`p_candlelamp01x`(烛灯)、
`p_glass01x`、`p_cupfancy01x`、`p_mugcoffee01x`、`p_copperpot01x`、`p_kettlecopper01x`…

### 9.2 已确认的事实

| 检查 | 结果 |
|---|---|
| 模型有 albedo 名吗 | **有**。`p_coin01x.ydr` 的 shader：`albedo=p_coin01x_ab`、`palette=p_coin01x_pal`、`normal=_nm`、`material=_ma` |
| 为什么 tex_id=-1 | 入库时 `TexLib` 里找不到这张 PNG，退回 -1 |
| props 包里有没有 | 提取 25 个 props 包（`p_valuable` / `p_food` / `p_drink` / `p_household` / `p_furniture` …），**3,000+ 个 ytd 全部没有** |
| 通用 gtxd 包里有没有 | 提取 `gtxd.rpf`（只有 `gtxd.ymt` 索引）+ `gtxd_ann.rpf`（16 个区域 ytd / 452 张贴图），**仍没有** |
| 全库扫描 | 扫了 **3,696 个 ytd**，`p_coin01x_ab` / `p_glass01x_ab` / `p_book05x_ab` 等**一个都没有** |

### 9.3 结论

**这些 prop 的 albedo 贴图确实不在当前已解出的资源集里**（既不在 props 包，也不在区域 gtxd）。

剩余可能位置（未验证，成本高）：
1. `gtxds.meta` 列的另外 31 个 `gtxd_*.rpf`（按区域分，单包几百 MB）
2. `_strm` 纹理流
3. 解包时的资源过滤把它们排除了

### 9.4 当前处理

- 已把这批无图模型按**名字类别**上近似色（硬币黄铜 `(0.72,0.58,0.24)`、罐头铁灰、书棕、玻璃浅蓝），
  见 `tools/make_interior.py` 里的 `PALETTE` 表。
- 已写 `tools/relink_textures.py`：一旦贴图补进来，可批量回填（不重解几何）。

**要根治，需要先把 31 个 `gtxd_*.rpf` 全部解出来再做一次全库匹配。**

---

## 10. 植被全图补全进展（2026-10-26）

| 区域段 | 状态 | 实例数 |
|---|---|---|
| jklm_2_6 / 7_10 / 11_14 / 15_18 | ✅ 已提 | — |
| nopq_2_6 / 7_10 / 11_14 / 15_18 | ✅ 已提 | — |
| fghi_2_6 / 7_10 / 11_14 / 15_18 | ✅ 已提 | — |
| **合计** | **13 个区域包** | **18,149 实例** |
| 覆盖 | **23 / 43 个 tile** | 模型在库 96.8% |

### 关键结果

- `wild2000_05_00`（威拉德之息所在）植被从 **0 → +776**，willard.blend 对象数 334 → **1,060**
- 组合脚本：`tools/parse_veg.py --extract-dir ...` 可重复执行

### 已知问题：植被贴图缺失 → 白色

部分树（`p_tree_whitepine_02/03`、`p_tree_douglasfir_02`）模型在库但 **albedo 贴图不在已解资源里**（同 §9 的 prop 问题），
显示为白色大块（30 m 高的树冠）。

已在 `blender_continent.py` 的 `build_entities` 里加**按名字分类上色**（`_ntex_cat` / `_ntex_mat`）：

| 类别 | 颜色 |
|---|---|
| tree / pine / fir / oak / cedar / maple / birch | 深绿 (0.115, 0.20, 0.095) |
| bush / shrub / scrub | 绿 (0.150, 0.235, 0.110) |
| grass / weed / fern | 黄绿 (0.265, 0.285, 0.135) |
| rock / stone / cliff | 灰 (0.340, 0.330, 0.310) |
| log / stump / wood | 棕 (0.300, 0.225, 0.150) |

生效条件：**整模型所有 submesh 都无贴图**。部分有贴图的模型不走分类（残留白块的部分来源）。

**根治仍需 §9 的 gtxd 贴图补齐。**
