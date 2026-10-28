# RDR2 地形与城镇（关卡/地编）—— 解包与复原笔记

> ⚠️⚠️ **2026-10-16 二次更正（推翻性）**：`heightmap.dat` **根本不是世界地形**——用官方水体多边形做判据，
> 水/陆在 8 种朝向下**零相关**（水体百分位 26~58%，随机=50%），缩放+平移全搜也救不回来。
> 所有基于它的"地形"渲染都是假的。详见 **`RDR2_世界地图与据点浏览.md` §2.1**。
> 真地形在 `levels_*.rpf → levels/rdr3/terrain/<area>/<tile>_.rpf` 的 `_hd_0_i_j.ydr` 里（GB 级，独立一轮）。

> ⚠️ **2026-10-16 一次更正**：本文 §2 里"`heightmap.dat` 是 1536×1536 的高度图、可直接读"是**错的**。
> 实测该文件是 **768×768 的世界高度图平铺 2×2** 存满 1536²（行/列自相关在 lag=768 处≈0）。
> 用 1536² 直接读会得到高程错位的"伪地形"（Valentine 读到 −10.8 m，实际 ≈ +123 m）。
> 正确读法 + 全世界地图/据点浏览见 ⭐ **`RDR2_世界地图与据点浏览.md`**。

> 承接 `README.md`（资产提取）与两份逆向笔记。本文记录**地形**与**城镇（关卡地编）**的现状、可用数据与复原路线。

---

## 1. 已提取的关卡/地编数据

| 类别 | 数量 | 位置 |
|---|---|---|
| 地图元数据 `.ymap`（实体摆放） | **4228** | `export/levels/map_metadata/**` |
| 原型定义 `.ytyp`（archetype） | **1026** | `export/levels/map_metadata/**` |
| 地形高度图 `heightmap.dat` | 1536×1536 | `export/levels/terrain/` |
| 水面高度 `waterheight.dat` | — | 同上 |
| 碰撞 `.ybn` | 12301 | `export/levels/collision/**` |
| 城镇街区 `.ymap`（举例） | Valentine `val_01_` · Blackwater `bla_blk01..06`+`bla_civic` · Annesburg `ann_01..05` · Armadillo `arm_01..05`（含 saloon/bank/genstore/sheriff 室内） | 同上 |

---

## 2. 地形（✅ 已复原到可视化）

**`heightmap.dat` 是可直接读的**：

```
magic = "HMAP" (0x484D4150)
+0x04 ver = 0x101
+0x08 unknown = 1
+0x0C dimX(u16)=1536 , dimY(u16)=1536
+0x10 minX(f32)=-7680 , minY(f32)=-8192 , minZ(f32)=-57
+0x1C maxX(f32)= 4608 , maxY(f32)= 4096 , maxZ(f32)= 729
data = 文件末尾 dimX*dimY*2 字节（u16 高度），归一化到 [minZ,maxZ]
```

- 世界范围 **x[-7680,4608] × y[-8192,4096]**（约 12.3 km × 12.3 km），高程 **-57 ~ 729 m**。
- 已导出：`height_768.bin`(768² u16) + `height_meta.json` + **`terrain.html`**（three.js 3D 地形，绿平原/棕丘陵/雪峰分色）。
- 实测效果：**能看出 RDR2 的地貌**（远处雪线山脉 + 大片平原）。
- 🔸 待修：正视图有**竖向条纹**（列均值方差偏大）⇒ 说明 1536² 的行/列排布可能还有一层 **block/swizzle**（或末尾那段不是纯高度数据），需再定布局。

---

## 3. 城镇（`.ymap` / `.ytyp`）—— ✅ 已打通并复原出 Valentine

### 3.1 `.ymap` 格式破解（关键突破）
`.ymap` = **RSC8 容器 + RAGE `Meta` 格式**（magic `0x50524430`，即 "0DRP"，+平台字节 0x79=PC）。
Meta 头（RDR2 实测偏移，在 body 内）：

```
+0x10 magic 0x50524430
+0x14 u16 平台(0x79)  +0x16 u8 +0x17 u8  +0x18 u32 +0x1C u32
+0x20 u64 rootIndex
+0x28 u64 StructureInfos 指针   +0x48 u16 StructureInfos 数
+0x30 u64 EnumInfos 指针        +0x4A u16 EnumInfos 数
+0x38 u64 DataBlocks 指针       +0x4C u16 DataBlocks 数
+0x40 u64 Name 指针
StructureInfo(32B): nameHash(u32) key(u32) u32 u32 | entriesPtr(u64) size(i32) u16 entriesCount(i16)
StructureEntry(16B): nameHash(i32) dataOffset(i32) dataType(u8) unk(u8) refTypeIdx(i16) refKey(i32)
DataBlock(16B): nameHash(u32) dataLength(i32) dataPtr(u64)
```
**实体结构（实测）**：`size=144`，字段 `archetype Hash @+8`、`flags @+12`、`guid @+16`、
**position float3 @+32**、**rotation float4(四元数) @+48**、`scaleXY @+64`、`scaleZ @+68`
（与 GTA V 的 `CEntityDef` 同构）。

工具：`tools/rage_meta.py`（Meta 解析）+ `tools/ymap_entities.py`（按结构特征自动识别实体表 → 导出实体）。

### 3.2 Valentine 复原结果
- 扫 `val_*.ymap` **43 个文件** → **2263 个实体**（archetype + 位置 + 旋转 + 缩放）。
- 城镇包围盒：**x[-443.9,-158.6] y[586.2,969.1] z[104.7,140.8]**（RDR2 世界坐标，Z 为高程）。
- 产物：
  - `export/levels/town/valentine.json`（实体清单）
  - **`export/levels/town/valentine.html`**（three.js 交互灰盒，支持 `?view=top|iso|side`）
  - `valentine_top.png` / `valentine_iso.png`（俯视平面图 / 斜视）
- 实测效果：**能看出瓦伦丁的街道走向与建筑轮廓**（矩形房基、沿街排列、外围零散道具）。

### 3.3 `.ytyp` 解析（archetype → 真实尺寸）
`.ytyp` 同样是 **RAGE Meta**。实测 archetype 结构（`size=160`）：
`float3 @+32`(bbox min) · `float3 @+48`(bbox max) · `Hash @+88` · `Hash @+112`（archetype 名哈希）。

工具 `tools/ytyp_archetypes.py` 扫全部 **1026 个 `.ytyp`** → **96,141 个 archetype** 的包围盒表
（`export/levels/town/archetypes.json`）。

把这张表套到 Valentine：
- **427 / 2263** 个实体拿到了真实包围盒（其余用默认小盒）；
- 过滤掉"又大又扁"的地面/甲板片后，**盒子尺寸按建筑真实比例渲染** —— 画面里能看出
  **成排的房屋体块 + 街巷 + 围栏状小物件**，已经是像样的城镇灰盒。
- 颜色按尺寸分级：大结构(蓝) / 建筑(米黄) / 中物件(绿) / 小物件(红)。

### 3.4 后续可做
1. `.ytyp` 里还带 archetype 名的哈希 —— 若有 RDR2 名称表即可把哈希解成 `val_bank01` 之类的**真名**。
2. 把实体**叠到 §2 的真实地形**上（当前是平面）。
3. 需要**真模型**时再解析 `.ydr`（RDR2 drawable，与骨架同源，难度较高）。

---

## 4. 合并交付：地形 + 城镇（✅ 单文件双击可看）

> ⚠️ **重要**：浏览器在 `file://` 下**禁止** ES module import 与 `fetch()`，所以早期用
> `importmap + fetch(json)` 的页面**双击打开会黑屏**（必须走本地 http 服务）。现已改为
> **自包含单文件**（three.js 源码 + 实体 + 地形全部内联，用 Blob URL 动态 import），**双击即可**。

| 文件 | 说明 |
|---|---|
| **`export/levels/town/valentine_terrain.html`** | ⭐ **地形 + Valentine 城镇**（2.1 MB，双击可看；右上角可开关「地形/城镇」）|
| `export/levels/town/valentine_standalone.html` | 只有城镇（1.5 MB，双击可看）|
| `export/levels/town/valentine.html` | 城镇（需本地 http 服务）|
| `valentine_iso.png` / `valentine_top.png` / `valentine_terrain.png` | 截图 |

生成器：`tools/build_town_standalone.py`、`tools/build_town_terrain_viewer.py`。

### 地形带状条纹的结论
实测 `heightmap.dat` 的**行/列均值连续、逐格中位差仅 0.4%**；试过 row-major / col-major /
一维 tile / 二维 block（16~256）等 **13 种排布，row-major 最平滑** ⇒ **数据本身没问题**，
远处山峰上的竖向条纹是**渲染/法线层面的表现**，不是解包错误。

---

## 5. 复现

```bash
# 地形
tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe extract "H:/EPICGAMES/RedDeadRedemption2/common_0.rpf" \
    export/levels/terrain "heightmap"
# 城镇实体（自动识别实体表）
uv run python tools/ymap_entities.py export/levels/map_metadata "val_*.ymap" export/levels/town/valentine.json
# archetype 包围盒（全量 ytyp）
uv run python tools/ytyp_archetypes.py export/levels/map_metadata export/levels/town/archetypes.json
# 生成单文件查看器（双击可看）
uv run python tools/build_town_terrain_viewer.py
```
