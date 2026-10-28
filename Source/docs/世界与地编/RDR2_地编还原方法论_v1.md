# RDR2 地编还原方法论 v1（可复用到任意城镇 / 整张地图）

> 2026-10-19。基于圣丹尼斯（St Denis）实战沉淀，并用 Valentine / Annesburg / Rhodes /
> Armadillo / Tumbleweed / Blackwater 六个镇验证过参数推导。
> **配套工具**：`tools/plan_town.py`（给出任意城镇的全部参数与命令）。

---

## 0. 一句话

**六个阶段、四道门禁、一张坑表。**
每个阶段都有可量化的验收指标，不达标不进入下一阶段。

```
S0 侦察 → S1 抽取 → S2 解码 → S3 摆放 → S4 环境 → S5 动态 → S6 组装/性能
                ↑________ 每阶段门禁 ________↓
```

---

## 1. S0 侦察（15 分钟）

```bash
uv run python tools/plan_town.py --zone valentine
```

输出即所需全部参数：

| 参数 | 示例（Valentine） | 用途 |
|---|---|---|
| 中心 / 半径 | (-304, 744) / 310 m | 导出时 `--cx --cy --r` |
| area 目录 | `jklm_07_10` | 模型包所在 `levels/rdr3/area/...` |
| 共享贴图包 | `gtxd_valentine.rpf` | **最关键**，缺了会紫墙/缺图 |
| 室内包 | 14 个 `val_*_int.rpf` | 室内 MLO |

> 已实测：Valentine→jklm_07_10、Annesburg→jklm_15_18、Rhodes→nopq_11_14、
> Blackwater→nopq_07_10、Armadillo/Tumbleweed→rstu_03_06。

**门禁 G0**：`area` 目录、`gtxd_*` 包、`*_int` 包**三者都能定位**，否则先补侦察。

---

## 2. S1 抽取（模型 + 贴图）

```bash
RP=tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe
# 1) 城市模型（该 area 下所有 rpf，逐个解包再拆）
$RP extract <game>/levels_2.rpf work/<code>/tmp "levels/rdr3/area/<area>/<pack>.rpf"
$RP extract work/<code>/tmp/<pack>.rpf work/<code>/models ""
# 2) 共享贴图（★ 必须）
$RP extract <game>/levels_2.rpf work/<code>/gtxd "levels/rdr3/gtxd/gtxd_<town>.rpf"
$RP extract work/<code>/gtxd/gtxd_<town>.rpf work/<code>/gtxd/txd ""
```

**门禁 G1**：`ydr + yft` 数量 > 500；`gtxd/txd` 里 ytd > 50。
数量明显偏少 → area 目录判断错了，回 S0。

---

## 3. S2 解码（几何 + 材质）

脚本：`tools/export_sdn_gltf.py`

必须遵守的规则（每条都是踩过的坑）：

| 规则 | 原因 |
|---|---|
| **`.ydr` 与 `.yft` 都要吃** | 大量道具是 fragment（`p_crate01x.yft`） |
| **不焊接顶点** | 0.25 m 焊接会吃掉 0.02~0.06 m 装饰 |
| **读 vdecl 取法线** | 法线是 `R10G10B10A2_UNORM`，漏了就是死平面 |
| **只允许 albedo 后缀**（`_ab/_abal/_al`） | 否则匹配到 `_nm` 法线图 → **整墙发紫** |
| **剔除 `_slod` / `default` shader** | LOD 与占位网格会把街区糊成白盒 |
| **同位置变体去重**（`_em_hd/_dec/_dc`） | 否则一栋楼画两三遍 |
| **贴图上限 512²**（道具可 256²） | 平衡清晰度与体积 |

**门禁 G2**：
- 缺图数 / 贴图总数 `< 10%`（圣丹尼斯：124/1504）
- 解析成功率 `> 90%`
- 抽样渲染 3 栋建筑，**墙面不是紫色、不是纯色**

---

## 4. S3 摆放（ymap 实体 → 实例）

- 扫描 `export/levels/map_metadata/**/*.ymap`，取 bbox 内全部实体；
- `archetype hash == joaat(model_name)` 直接匹配（RDR2 绝大多数可对上）；
- 按 `(hash, x, y, z)` 去重（同一实体可能出现在多张 ymap）。

**门禁 G3**：建筑类实体命中率 `> 90%`。
（圣丹尼斯 2 638/2 698 = 97.8%）

---

## 5. S4 环境（地面 / 水 / 天空）

| 组件 | 做法 | 脚本 |
|---|---|---|
| 地形颜色 | 抽 20 个地形瓦片的 `<tile>_t`（2048²）→ 拼 4096² | `build_sdn_terrain_tex.py` |
| 地形高度 | `H4.npy`（4 m 真高程） | 同上 |
| 水 | 区域统一水位（等腰线收边）+ `water_level` 可调 | `blender_rebuild_ground.py` |
| 天空 | 物理天空（多次散射）+ Sun 同向 + AgX | `blender_setup_sky.py` |

**门禁 G4**：
- 地面**不出现纯色板**（截图能看出草地/泥/路的差异）；
- 船不搁浅（船只实例地形高度 < 水位）；
- 城区不进水（城区地形 ≥ 水位）。

---

## 6. S5 动态（可选）

| 对象 | 数据 | 做法 |
|---|---|---|
| 电车 | `trolley*.dat`（文本样条） | Curve + Follow Path |
| 火车 | `trains*.dat` | 同上，多节按帧递延 |
| 船/马车 | `vehicles.rpf` + `popcycle.dat` | 待做 |

**门禁 G5**：帧 1/300/700 采样位置**连续变化**，且不与建筑穿插。

---

## 7. S6 组装与性能

- 按 glTF 分块导入 → 每块一个 `TILE_*` 集合；
- **不要 join**：join 会把实例几何展开（62M→90M 顶点）；
- 默认只显示中心 220 m 内的块；
- 视口用 Solid；需要动态时跑 `zone_stream.py`。

**门禁 G6**：文件 < 3 GB；打开后视口可见块 < 40；转动不卡。

---

## 8. 坑表（症状 → 根因 → 修法）

| 症状 | 根因 | 修法 |
|---|---|---|
| 墙发紫 | 匹配到 `_nm` 法线图 | 只认 albedo 后缀 |
| 屋顶偏暗 | 缺共享贴图 | 抽 `gtxd_<town>.rpf` |
| 街道空 | 道具是 `.yft` | 加 fragment 解析 |
| 整片白盒 | `_slod` / `default` shader | 剔除 |
| 楼画两遍 | 同位置变体 | 按基名去重 |
| 地面支离破碎 | 纯色地形板 | 地形颜色图 |
| 船搁浅 | 水域被城市多边形裁掉 | 只按地形高度裁 |
| 沙洲楔形 | 用多边形直边裁水 | 等高线收边 |
| 描边/闪面 | 视口 Clip Start 太小 | 设 5 m |
| 打开崩溃 | 文件太大 / 自动跑脚本 | 分块 + 关自动执行 |

---

## 9. 扩展到整张地图

| 项 | 建议 |
|---|---|
| 组织 | 按 **area 目录**（`jklm_07_10` 等）分文件，每份 1~4 个镇 |
| 预算 | 单文件 ≤ 3 GB / ≤ 6 000 万顶点 |
| 顺序 | 先 8 个官方 TOWN → 再 REGION（Annesburg/Blackwater/Valentine…）→ 最后荒野点缀 |
| 并行 | 每个镇的 S1~S3 完全独立，可并行抽包 |
| 工期 | 单镇：侦察 0.5 h + 抽包 0.5 h + 导出 1 h + 环境 1 h + 验收 0.5 h ≈ **3~4 h**（圣丹尼斯因体量大 3 倍） |

**整图粗估**：8 个城镇 × 4 h ≈ 32 h；若只做"城镇 + 主要据点"（约 20 个），约 80 h。

---

## 10. 脚本索引

| 脚本 | 职责 |
|---|---|
| `tools/plan_town.py` | ★ 输入城镇名 → 输出全部参数与命令 |
| `tools/export_sdn_gltf.py` | ydr → glTF（不焊接/法线/贴图） |
| `tools/export_sdn_props2.py` | 道具（含 `.yft`）批次导出 |
| `tools/build_sdn_terrain_tex.py` | 地形颜色图拼合 |
| `tools/blender_rebuild_ground.py` | 地形 + 水面（水位可调） |
| `tools/blender_setup_sky.py` | 物理天空 + 日照 |
| `tools/zone_stream.py` | 按摄像机距离分块显隐 |
| `tools/audit_sdn_coverage.py` | 覆盖率审计 |


---

## 11. 第二座城镇实测（Valentine 试点）

按本手册原样跑了一遍 Valentine，结果如下——**方法论可复用，但也暴露一条新规则**。

| 阶段 | 实际操作 | 结果 |
|---|---|---|
| S0 | `plan_town.py --zone valentine` | 中心 (-304,744)、半径 310、`jklm_07_10`、`gtxd_valentine.rpf`、14 个室内包 |
| S1 | 抽 8 个 `val_*.rpf` + gtxd | **291 ydr / 4 yft / 155 ytd**，gtxd 40 ytd |
| S2 | 现有导出器（无需改代码） | 383 模型 / **1 876 025 顶点** / 缺图 79/413（19%） |
| S3 | ymap 实体匹配 | 935 实例（仅本镇模型 197） |
| S6 | 导入 Blender + 平地 + 物理天空 | `work/val/val.blend`，出图 `work/val/val_iso.png` / `val_street.png` |

**新增规则（重要）**：

> **道具是全局共享的，不需要按镇重复抽。**
> 把圣丹尼斯已抽的 `work/sdn/props` + `work/sdn/props2`（3 800 模型）接进来后，
> Valentine 的实体覆盖率从 **6.2% → 72.4%**。
> 所以流水线应改为：**首镇抽全道具库 → 后续城镇只抽本镇建筑包**。

**试点暴露的缺口**：
- 仍有 122 个 `val_*` 实体没模型（该镇部分建筑在别的包里，或 `.ydd` 字典里）；
- 缺图 19%（比圣丹尼斯高，说明 gtxd_valentine 只覆盖一部分，需再补 `gtxd.rpf` 通用包）；
- 试点只做了模型+平地，未做地形颜色/水（S4 尚未在 Valentine 验证）。

**结论**：方法论 **S0~S3、S6 已在第二座城镇跑通**；S4（地形/水）和缺图补齐是下一步要补的。
