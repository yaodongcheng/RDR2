# RDR2 `.ydr` 几何/顶点格式（已攻克）

> 工作目录：`D:\BrainMaker\大镖客2解包分析`
> 攻克日期：2026-10-14 ｜ 样例：`export/models/buildings/val_0*_/*.ydr`
> 工具：`tools/rdr2_ydr.py`（解析器）· `tools/export_building_meshes.py`（批量导出）· `tools/build_valentine_real.py`（查看器）

---

## 0. 一句话结论

RDR2 的 `.ydr`（Drawable）几何**已经解出来了**：
**顶点位置是 `f32×3` 的「平面(planar)数组」**，紧跟在缓冲区数据指针后面（`count × 12` 字节），
**不是 GTA V 那种「交织(interleaved)」布局**——这就是上一轮移植 CodeWalker 读法读出 stride/顶点数=0 的根本原因。

验证：用 index buffer 还原三角形，**中位边长 0.29 m**（bbox 对角线 54.5 m），
且输出到查看器后能明确辨认出**中央塔楼 + 两侧坡顶 + 月台 + 台阶 + 栏杆**的火车站外形。

---

## 1. 容器与指针

- 文件 = `RSC8` 16 字节头 + 资源体（body）。
- 资源体内指针形如 `0x50000000 | offset`（system 段）、`0x60000000 | offset`（graphics 段）；
  `offset` 相对 **body 起点**。
- ⚠️ 所有偏移都是**每文件不同**的，必须跟着指针走，不能硬编码。

```
RSC8 头： magic(0x38435352) | version | u32 | u32
```

---

## 2. Drawable 头（body 相对偏移，实测）

| 偏移 | 类型 | 含义 |
|---|---|---|
| `+0x10` | u64 | `ShaderGroup*` |
| `+0x18` | u64 | `Skeleton*`（静态建筑为 0） |
| `+0x2c` | f32 | 包围球半径 |
| `+0x30` | f32×3 | 包围盒 min |
| `+0x40` | f32×3 | 包围盒 max |
| `+0x50` | u64 | `DrawableModels*`（high LOD）|
| `+0x58` | u64 | med |
| `+0x60` | u64 | low |
| `+0x68` | u64 | vlow |

**PointerListHeader（16 B）**
```
u64 ArrayPtr | u16 Capacity | u16 Count | u16 Count2 | u16 pad
```
> 注意：**Count 在 +0x0A**（不是 +0x0A 之后那种 GTA V 版本），得按这个读。

---

## 3. DrawableModel → Geometry

**DrawableModel（0x40 B）**
```
+0x00 f32  Radius
+0x04 u32  1
+0x08 u64  Geometries[] 数组指针      ← 也可能落在 +0x10（两种排布都遇到过）
+0x10 u16  GeometryCount（配合 +0x08 排布）
+0x18 u64  （其余字段，本流程未用）
```
> 解析器里对 `(+0x08,cnt@+0x10)` 与 `(+0x10,cnt@+0x18)` 两种排布做了探测，取能解出合法 VB/IB 的那个。

**DrawableGeometry（0x40 B）**
```
+0x08 u64  VertexBuffer*
+0x10 u64  IndexBuffer*
```

---

## 4. VertexBuffer / IndexBuffer（关键）

**VertexBuffer（0x40 B）**
```
+0x00 f32  Tag/半径（≈4.53）
+0x04 u32  1
+0x08 u32  VertexCount
+0x0c u32  TotalStride        （= 所有属性每顶点字节数之和；实测 40）
+0x10 u64  Flags（0x209000）
+0x18 u64  Data*              ← 属性数据起点
+0x30 u64  ...                +0x38 u64 ...
```

**IndexBuffer（0x40 B）**
```
+0x00 f32  Tag
+0x04 u32  1
+0x08 u32  IndexCount
+0x0c u32  IndexSize（2 = u16）
+0x10 u64  Flags（0x20a000）
+0x18 u64  Data*
```

---

## 5. ★★ 顶点是「平面分属性数组」，不是交织 ★★

`TotalStride = 40` **不是**「一个顶点 40 字节交织存放」，而是**每类属性各自连续成一块**：

| 段 | 起始（相对 Data） | 每顶点字节 | 说明 |
|---|---|---|---|
| **position** | `0` | **12**（f32×3） | ★ 本工具使用，直接可读 |
| attribute1 | `12*count` | 16 | 未解（法线/切线/色等） |
| attribute2 | `28*count` | 12 | 未解（疑似 UV 或切线） |

即数据区总长 = `count × 40`，位置数组只占开头 `count × 12` 字节。

**判别依据**（可复现）：拿配对的 IndexBuffer 还原三角形，比较「中位边长 / bbox 对角线」——
- 平面 stride=12：`median edge 0.29`，`max edge 3.5~5.0`（**合理**）
- 交织 stride=40（+0 / +12）：`max edge ≈ 1e38`（**炸开**）

```
# 复现（火车头 val_01_trainstn_ext.ydr）
VB data=0xce6c0 count=3171 ; IB data=0x11eba0 n=6081
→ planar(12)  median=0.293  max=5.02     ✅
→ inter(40)   median=4.18   max=1e38     ❌
```

---

## 6. 配对校验（怎么确认 VB↔IB 是同一网格）

IndexBuffer 的**索引最大值 + 1 == VertexBuffer 的 VertexCount**，且**唯一索引数 == 顶点数**：

| 样例 | VB count | IB 索引数 | IB max | IB unique |
|---|---|---|---|---|
| `val_01_srtsign_a` geom0 | 104 | 384 | 103 | **104** ✅ |
| `val_01_srtsign_a` geom1 | 64 | 120 | 63 | **64** ✅ |
| `val_01_trainstn_ext` VB@0x134cc0 | 3171 | 6081 | 3170 | — |

另外**顶点缓冲区在文件里是连续平铺的**（`buf_end + 8` 即为下一段），可用来交叉验证 count/stride：
`0xd0 + 104×40 = 0x1110`（下一段起点）✅

---

## 7. archetype ↔ 模型名（精确映射，实测）

**实体里的 archetype 哈希 == `joaat(<ydr 文件名>)`。**

验证：32 个 `val_01_*` 模型名全部以 `joaat(name)` 命中 `.ytyp` 里 archetype 结构的 **`+88` 与 `+112`** 两个字段，
`.ymap` 实体的 archetype 字段引用的正是这个哈希。

⇒ 于是可以：**用实体位置/旋转/缩放 + 该模型真实网格**，把真房子摆回世界坐标（见 `build_valentine_real.py`）。

---

## 8. 已知 / 待办

- ✅ 位置、索引、LOD 分组（high/med/low/vlow）已通
- ⬜ **attribute1 / attribute2 语义未定**（法线、UV、切线、色彩）——贴图/PBR 需要它
- ⬜ `_em_slod` / `road_d_*` / `*_decal*` 这类资源是 LOD/路面/贴花，做「建筑本体」展示时应过滤
- ⬜ 纹理 `.ytd`（RSC8 纹理 → DDS/PNG）未做（P1）

> 命名备注：RDR2 里 `*_ext` = 建筑外观、`*_em_hd` = 高模/自发光外观、`_em_slod` = LOD、`_decal` = 贴花、`road_d_*` = 路面段。

---

## 9. 变换校验（2026-10-14 追加，已通过）

用「网格局部包围盒」对「archetype 包围盒」做数值比对，验证 **几何解码 + 单位/朝向**：

```
model                     mesh ext(x,y,z)            arch ext(x,y,z)          ratio
val_bank                  [17.73, 26.64,  7.86]      [17.73, 26.64,  7.86]    1.000
val_03_genstore_ext       [24.71, 22.18, 10.83]      [24.71, 22.18, 10.83]    1.000
val_03_jail_ext           [13.89, 16.75,  8.36]      [13.88, 16.75,  8.36]    1.000
val_shrffhs               [19.09, 20.09,  8.72]      [19.09, 20.08,  8.73]    1.000
val_03_doctor_ext         [12.13, 19.97,  9.39]      [12.13, 19.96,  9.40]    1.001
...
ratio ∈ [0.5,2] : 38/38 全部通过
实体四元数模长 / 缩放异常 : 0 / 2263
```

**结论**：网格局部空间 == archetype 定义空间（单位一致、无镜像），
因此 `world = T(entity.pos) * R(entity.quat) * S(entity.scale) * localMesh` 可直接使用。

⚠️ 例外：`val_03_stables_fence`、`val_06_pigpen` 的 x/y 轴互换（ratio 仍≈1，属 ytyp 轴向记录差异），
`val_gallows` / `val_hotel_ext_prch` / `val_07_resf_vines` 为组合件（含多个子件），extent 略大属正常。

---

## 10. 地形高度（heightmap）—— ⚠️ 基准不一致（未解决）

实测：`heightmap.dat` 按头里的 `zmin=-57 / zmax=729` 归一化后，**Valentine 处地形只有 -10 ~ +2 m**，
而城镇实体的 z（= .ymap 世界 z，且被 `jklm_7_10_area_lod` 的实体 z 93.8~245.8 交叉验证过）是 **104 ~ 141 m**。

| 检验 | 结果 |
|---|---|
| 182 个建筑实体 z vs 地形 raw 的相关 | **corr = +0.06**（无相关） |
| 常量偏移假设 | dz 92.7 ~ 147.5，std 8.8（非常量） |
| 行列互换 / 翻转 / 反相 | 最高 \|corr\|≈0.2，rms 仍 4.6 |
| 21 个 area-LOD 实体拟合 | rms 42（差） |

⇒ **heightmap.dat 的「世界范围」或「垂直基准」与 .ymap 世界坐标对不上**（可能：文件只覆盖某一级 mip / 范围标注有误 / 垂直基准另有一套）。

**当前处理**：查看器 `valentine_real.html` 里按本镇实体反推一个**常量 z 偏移（+129.47 m）**做局部校准，
使地形与城镇自洽；HUD 会显示该偏移。**这是局部校准，不是正解**——待 P6 找到正确映射后替换。

---

## 11. `.ytd` 纹理（P1）—— 🟡 结构已全解，BC3 可解、BC1 待解

样例 `val_01_trainstn_ext+hidr.ytd`：`RSC8`，sys 段 6240 B、gfx 段 10813442 B。

### 11.1 纹理表（已解通）

**条目步长 `0xB0`，起点 `body+0x180`**，共 27 张。条目字段（实测）：

| 偏移 | 类型 | 含义 |
|---|---|---|
| `+0x08` | u32 | 尺寸（≈ (mip链字节数 + ~2731)/16）|
| `+0x0C` | u32 | 8 或 16 |
| `+0x10` | u32 | 常量 `0x18008002` |
| `+0x18` | u16 | **Width** |
| `+0x1A` | u16 | **Height** |
| `+0x1F` | u8 | **格式字节（DXGI 码低字节）** ← 关键 |
| `+0x20` | u32 | 65536 |
| `+0x28` | u64 | **名称字符串 ptr**（`0x50000000|off`，ASCII）|
| `+0x38` | u64 | **数据 ptr**（`0x60000000|gfxoff`）|

槽位间距实测：1024²→`0xAB000`(700416)，512²→`0x56000`(352256)，BC3 的 1024²→`0x156000`(1400832)，
与对应 BC 的 mip 链大小吻合 ⇒ **数据按「每张纹理 mip 链」顺序平铺**。

### 11.2 格式字节 → BC 格式（实测）

| 字节 | DXGI | 含义 | 解码状态 |
|---|---|---|---|
| `0x47` | 71 | BC1_UNORM | ⬜ 仍噪声 |
| `0x48` | 72 | BC1_UNORM_SRGB | ⬜ 仍噪声 |
| `0x4D` | 77 | BC3_UNORM | ✅ **完美** |
| `0x4E` | 78 | BC3_UNORM_SRGB | ✅ **完美** |

**铁证**：`val_sn_ext_22_abal`（1024²，BC3_sRGB，gfx+0）解出**完全清晰**的
**"VALENTINE STATION"** 招牌（大号奶白字 + 深青底 + 下方 3 行说明文字），
且**名称与内容语义吻合**（`val_sn_ext` = Valentine Station exterior）⇒ 名称↔数据配对正确、BC3 解码路径无误。

### 11.3 未解 / 待办

- ⬜ **BC1（0x47/0x48）纹理仍呈噪声**：对同一条目做过偏移搜索（0~4096 步进）与 DXT1/DXT5 双格式尝试，
  平滑度几乎不变 ⇒ 数据并非「BC1 线性排布」。可能：RDR2 对 BC1 用了不同的块序（swizzle/tiling），
  或该字节并非纯 DXGI 码（高 24 位还有信息）。
- ⬜ **UV 仍未定位**（本轮又推进一步，结论如下）：

  **顶点布局（再确认）**：位置是**平面 f32×3**（`body[data : data+12*count]`），
  其后每个顶点还有 **28 字节**其它属性（`data+12*count : data+40*count`）。

  **已识别的通道**：把 `rest` 段按 **4 字节/顶点**切（共 7 条 lane），
  第 0 条 lane 当 **4×int8 SNORM** 解释时，与**用三角面算出来的几何法线**最吻合：
  `|n| 均值 1.013`、`|dot| 均值 0.639`、`30% 的面 dot>0.9`
  ⇒ **lane0（4 B）疑似打包法线**。其余 lane（i16/u16/f16 各解释）都还没对上 UV。

  **走过的弯路（别再试）**：
  * 逐三角面做「UV = 位置 的仿射函数」拟合 → **欠定**（3 个点 4 个未知），残差恒为 0，无判别力；
  * 「整段扫 f16/f32 对在 [-4,4]」→ 无命中；
  * 直接用 stride 40 当交织顶点读 → 全 lane 都是满量程噪声（因为布局是平面的）。

  **★ 关键结论（本轮实测，多模型一致）：顶点里没有常规 UV。**
  用「UV 在网格边上应与位置变化线性相关」做判据（`|Δuv|/|Δpos|` 的中位数绝对偏差 MAD）：

  | 模型 | 位置对照(必然最像) | 最好的 lane 候选 |
  |---|---|---|
  | `val_01_srtsign_a` (104v) | **0.014** | lane3u16 = 0.185 |
  | `val_01_trainstn_ext` (3171v) | **0.003** | lane5u16 = 0.654 |
  | `val_03_saloon_ext` (2150v) | 0.116 | lane5u16 = 3.575 |
  | `val_genstore_ext` (4175v) | **0.001** | lane2u16 = 0.895 |

  候选与对照**差一个数量级** ⇒ **这些建筑资产的顶点里根本没有 UV 通道**。
  > ❌ **本条已被 §20 推翻**（2026-10-16）：UV 就在顶点里（`TEXCOORD0/1`），只是当时没读
  > `VertexBuffer+0x38` 的 `VertexDeclarationG9`，把 SOA 属性当"未知字节块"在猜。

  **推论**：RDR2 对场景资产用 **triplanar（三向投影）程序化 UV**（由世界/物体坐标在 shader 里算），
  所以**不需要导出 UV 也能上材质** —— 正确做法是在查看器里实现 triplanar 采样，
  而不是继续在顶点里找 UV。

  **走过的弯路（别再试）**：
  * 逐三角面做「UV = 位置 的仿射函数」拟合 → **欠定**（3 点 4 未知），残差恒为 0，无判别力；
  * 整段扫 f16/f32 对落在 [-4,4] → 无命中；
  * 按 stride 40 交织顶点读 → 每条 lane 满量程噪声（布局是平面的）；
  * headless 里用 shader 注入 triplanar 采样 → **语法/编译不稳定**，已回退（这条要在真实浏览器里做）。

  **可行的下一步**：把 triplanar 材质做进查看器（在真实浏览器验收，不要在 headless 里调试 shader）。

### 11.4 工具

| 工具 | 作用 |
|---|---|
| `tools/rdr2_ytd.py` | `.ytd` 纹理表解析（列名/尺寸/格式/数据偏移，可 `--dump`/`--json`）|
| `tools/ytd_to_png.py` | 按真实 BC 格式解码为 PNG（`--sheet` 出拼图）|
| `tools/uv_probe.py` | **UV 候选探针**：导出位置+各候选 UV → 生成渲染比对页 |
| `tools/build_ytd_preview.py` | WebGL2 预览页（备用路径：PIL 不支持 BC7，可用 `EXT_texture_compression_bptc` 上传）|
| 成果 | `export/models/textures/val_01_trainstn/*.png` + `sheet_trainstn.png` |

---

## 12. `.ydd`（DrawableDictionary）—— LOD 模型的来源（2026-10-14 追加）

Valentine 的 2263 个实体里，只有 182 个 archetype 能在 `.ydr` 里找到；剩下 926 个里
**431 个**存在于 `levels/rdr3/area/lod/<grid>_area_lod_combine.rpf` 的 **`*_slod_children.ydd`** 中。

`.ydd` 结构（实测，body 相对）：

```
+0x18 u32                            1
+0x20 u64 哈希数组 ptr(sys 段)  +0x2A u16 Count    ← 升序 u32 哈希表
+0x30 u64 drawable 指针数组 ptr +0x3A u16 Count    ← 与哈希表【并行】
```

两个数组等长且一一对应 ⇒ `哈希[i] ↔ 指针[i]`。指针指向资源体里的一个 **Drawable**
（结构与 `.ydr` 内的 Drawable 完全一致），因此把 `parse_drawable` 参数化为
`extract_at(res, base)` 即可复用来解析字典里的每个子 drawable。

工具：`tools/rdr2_ydr.py` 的 `parse_drawable_dictionary()` / `extract_ydd()`；
批量导出：`tools/export_lod_meshes.py` → `valentine_lod_meshes.json`。

**成果**：431 个 LOD 网格（29.4 万顶点 / 19.2 万三角面），把 Valentine 的模型覆盖
从 **182 → 613 个 archetype / 42 → 473 个实体**（21%）。教堂双塔、主街木屋群因此可见。

**仍未覆盖的 1790 个实体**：其中 1661 个连 `archetypes.json` 里都没有 bbox 记录
（说明我们扫到的 `.ytyp` 不全），需要先补 `jklm_7_10_*_metadata` 的 `.ytyp` 才能继续。

---

## 13. `.yft`（fragment）与 props 包 —— 道具从哪来（2026-10-14 追加）

Valentine 2263 个实体里，建筑只占一部分；**大头是道具**（栅栏、水塔、桁架桥、长椅、木箱、马车、路灯、墓碑、水槽…）。
它们 **不在 town 自己的 area rpf 里**，而在：

```
levels_3.rpf
  levels/rdr3/props/generic/*.rpf        （p_fence / p_storage / p_seating / p_food / p_watertower / p_sign …）
  levels/rdr3/props/vegetation/*.rpf     （rdr_oak / rdr_cedar / rdr_bushes / rdr_rock_* …）
  levels/rdr3/props/structure/*.rpf
  levels/rdr3/props/areas/*.rpf
  levels/rdr3/props/lev_des/*.rpf        （s_* 关卡设计件）
```

共 **149 个 props 包**，且绝大多数是 **`.yft`（fragment）**，所以只扫 `.ydr` 时全漏。

### 13.1 `.yft` 的 drawable 在哪

`.yft`（fragment）头里有若干指针，主 drawable 通常挂在 **`+0x20`**：

```
+0x08 u64 (sys ptr)   +0x10 float4（旋转）   +0x20 u64 ← 主 drawable
+0x40 u64   +0x70 u64   +0x90 u64（其余子结构）
```

解析方式：把这些指针逐个当 drawable base 丢给 `extract_at(res, base)`，
取三角形最多的那个 —— 即 `rdr2_ydr.extract_frag()`。

实测抽样（bbox 都合理，证明解对）：

| 资源 | 三角形 | bbox |
|---|---|---|
| `p_mattress04x.yft` | 488 | 1.0 × 0.11 m |
| `p_foldedblanket01x.yft` | 202 | 0.6 × 0.14 m |
| `p_crateweapons04x.yft` | 2108 | 2.6 × 1.09 m |
| `p_horseprops03x.yft` | 2249 | 2.1 × 1.63 m |

### 13.2 匹配方法（可复现）

1. 从 `valentine.json` 取未覆盖的 archetype 哈希；
2. 用 `tools/rdr2rpf` 的 `list` **列出 149 个 props 包的目录**（名字反查 `src/names.txt`，未知名按 `0xXXXXXXXX.ext` 拿到原始哈希）；
3. 命中 478 个 → `extract` 出对应 `.ydr`/`.yft` → `export_prop_meshes.py` 导出。

> 也用过一条更快的路：`rdr2rpf extract <顶层rpf> <out> <名字> --recurse` 能直接下钻嵌套包找到文件。

### 13.3 仍然缺的

- **树木/植被**：RDR2 的树走 **instance placement**（独立实例系统），不是 ymap 实体 ⇒ 需另解植被实例数据。
- 剩余 157 个实体：`val_vfx_*`（粒子辅助体）、`*_dcl`（贴花）、`*_int`（室内件）、`*_shad`（阴影代理）——**都不是可见几何**。

---

## 14. 地形 LOD 的摆放表（2026-10-14 追加）

地形不是"一张 heightmap"，而是**按 512 对齐的 LOD 瓦片 + 全区域物件实例**：

| 来源 | 内容 |
|---|---|
| `jklm_7_10_lod.ymap` | **24 块地形瓦片**，位置严格按 512 对齐（256/768/1280/1792…），z 70~340 |
| `jklm_7_10_area_lod_combine_metadata`（325 个 ymap） | 9874 个实例（区域 LOD 物件）|
| `jklm_7_10_lod_combine_metadata`（39 个 ymap） | 2659 个实例（地形/林区 LOD）|

网格本体在 `*_slod{1,2,3,4}_children.ydd` / `*_area_slod*_children.ydd`
（在 `levels_3/5.rpf` 的 `levels/rdr3/areas/lod/*_area_lod_combine.rpf` 与 `terrain/*_lod_combine.rpf` 里）。

把 ymap 实例的哈希和 `.ydd` 字典的哈希对起来 → **命中 2494 个 drawable**。

⚠️ **关键坑**：同一瓦片 archetype 在**多个格位复用**（有的用 154 次），
所以必须保留**全量实例**（`terrain_instances.json`，12310 条），按 hash 去重会大面积丢地面。

裁剪策略（兼顾体积）：`大瓦片(mesh 尺寸≥250) 全留` + `小物件只留小镇 450m 内` ⇒ 1308 个模型 / 地面连续。

**道路**：`val_03_road_d_*` 这批 `.ydr` 就是路面网格（已解析、已摆放，但**无贴图**所以只见轮廓线，等 P1b 打通 UV）。

---

## 15. 植被实例系统（2026-10-14 追加）

**树/草不走 ymap 实体**，走独立系统：

```
levels_4.rpf → levels/rdr3/terrain/instance_placement/<grid>_instance_placement.rpf
                    ├─ *_trees_*.ymap   ← 每格 N 份
                    └─ *_grass_*.ymap
```

### 记录结构（关键，与普通实体不同）

普通 ymap 实体是 **144 字节**；**植被实例是 368 字节**：

| 偏移 | 内容 |
|---|---|
| `+0x08` | u32 archetype 哈希（== `joaat(模型名)`；实测 **452/452** 命中 names.txt）|
| `+0x90` | **float3 世界坐标**（实测 **1913/2328** 落在合理世界范围）|
| `+0x20` | float4（四元数，常为 0,0,0,1）|

坑：用普通实体解析器读它会得到**位置全 0**（因为位置字段不在 32/48）。

模型本体：`hd/levels/rdr3/props/vegetation/*.rpf`（HD：`p_tree_*`）+ `levels/rdr3/props/vegetation/*.rpf`。
两者合起来可把该区域的植被 archetype **100% 匹配**到模型。

**成果**：3402 个植被实例、270 种树/灌木/岩石模型（小镇 420m 内 728 棵）进查看器。

工具：`tools/parse_veg_instances.py`（解析实例）· `tools/export_veg_meshes.py`（导出模型+实例）

> 另注：`.yft`（fragment）的 drawable 在 `+0x20` 指针处，用 `rdr2_ydr.extract_frag()`。

---

## 16. 不可见实体（逻辑体）—— 别再给它们画盒子（2026-10-14）

`valentine.json` 里"找不到模型"的那批实体，**绝大多数在游戏里根本不渲染**，它们是逻辑/辅助体积：

| 名字模式 | 实际用途 |
|---|---|
| `*_int_*` / `*_milo*` | **室内 / 门厅体积**（进出室内、遮挡关系）|
| `*_dcl*` / `*_decal*` | 贴花 |
| `val_audioemitter*` | 音频发射器 / 代理 |
| `*_em*`（em001/em_slod…）| 发光/特效辅助体 |
| `*_slod*` / `*_lod*` | LOD 占位 |
| `lights_holder_*` | 灯光挂点 |
| `*_veg` / `*_dec` / `*_shad` / `*_rope` / `*_banner` | 植被/装饰/阴影/绳索/旗帜辅助 |

早期把"没模型的实体"一律画成灰盒 → 视觉上是「**每栋房子外面套一个方块**」（因为每栋楼都有个 `_int` 室内体积）。
正确做法：按名字模式过滤掉这些，**不要给逻辑体画盒子**。

> 剩下真正"有几何但还没解到"的极少（如 `val_genstore` / `des_val_sheriff` 两个 archetype），
> 可能是室内实例或复合体，可单独再查。

---

## 17. 建筑材质：box mapping 已打通（2026-10-14）

### 17.1 做法（绕开"顶点里没有 UV"）

既然顶点里没有 UV（§11.3 已实测），改用 **box mapping**：在 CPU 端按**顶点法线主轴**选投影平面，现算 UV：

```
|nx| 最大 → uv = (z, y)
|ny| 最大 → uv = (x, z)     （屋顶/地面）
否则      → uv = (x, y)     （墙面）
uv *= S（每 S 米一个贴图周期）
```

纯 JS 实现（`makeBoxUV()`，见 `build_valentine_real.py`），**不注入 shader**，零编译风险。

### 17.2 ✅ 管线验证通过 + 现用**程序化木墙材质**

游戏自带 albedo 目前只有 `val_sn_ext_22_*` 一族能解对（是**招牌**），拿它糊墙显然不合理。
所以演示材质改为**程序化生成**：

* `export/models/textures/proc/wood_wall.png` —— 横向木板 + 木纹 + 板缝（暖棕）
* `export/models/textures/proc/plaster.png` —— 灰泥
* 生成脚本内联在会话里（PIL 画板 + 噪声），可按需重做

另外给**每栋楼按 archetype 哈希加了轻微色相/明度扰动**，避免"一色复制粘贴"的克隆感。

视觉核验：**7.5/10**，"从广告牌糊脸到正经木板材质，量级改进"。

### 17.2b ✅ 管线验证（原始）

用 BC3 招牌贴图（`val_sn_ext_22_abal`，能正确解码的那张）贴到建筑上，
视觉核验确认：**墙面上出现了清晰的 "VAL" 字母，无拉伸、无噪点、方向正确**
⇒ BC3 解码 + CPU UV + 采样链路全通。截图 `valentine_real_material.png`。

查看器按钮：**`材质(box map)`**（默认开，与"真房子"互斥切换）。

### 17.3 ⚠️ 但贴图解码只可靠 2/7

对同一批 BC3 贴图做对比（`sheet_bc3.png`）：

| 可靠 | `val_sn_ext_22_mb`、`val_sn_ext_22_abal`（招牌类，青底白字，清晰）|
|---|---|
| **仍是噪声** | `val_dr_floor_01_abal`、`nbx_wall_woodpaintedoverlap_02_mb`、`rho_dr_stationwood_abal`、`val_cs_trim_02_mb`（高饱和 RGB 颗粒）|
| 勉强 | `rho_dr_wood01`（灰白、对比度极低）|

⇒ **纹理数据本身的定位/排布还有问题**（可能：mip0 不在槽位开头 / 有 swizzle / 部分条目 format 字节不是纯 DXGI 码）。
这个不影响 box mapping 的正确性，但**要拿到"木板/墙面"这类真材质，必须先把纹理解码修对**（P1a 收尾）。

> 备忘：能用的是 `val_sn_ext_22_*` 这一族，说明"槽位起点"对某些条目是对的、对另一些不对 ⇒
> 应该逐条目核对 `+0x08`(size) / `+0x38`(data ptr) 与槽位步长的关系，而不是用统一偏移。

### 17.4 纹理解码排除清单（本轮系统排查，2026-10-14）

| 假设 | 做法 | 结论 |
|---|---|---|
| 数据偏移错 | 全部 27 张，偏移 0~0x2000 步进 64 | ❌ 平滑度几乎不变 |
| mip 顺序反（mip0 在槽尾） | 按各 mip 边界（头序/尾序）全试 | ❌ 不改善 |
| 块排布转置/旋转/翻转 | 行/列主序、rot180、flipX/Y | ❌ 不改善 |
| **格式判定错** | 交叉验证 `+0x0c` 字段 | ✅ **格式判定是对的**：`+0x0c = 2 × bits-per-pixel`（BC1=8、BC3=16），与 fmt 字节 0x47/0x48(BC1)、0x4D/0x4E(BC3) 一致 |
| 数据仍被压缩 | 用游戏 `oo2core_5_win64.dll` 试解（脚本异常未完成） | ⬜ **待做** |

**关键对照数据**（同文件、同代码路径）：

| # | 名字 | 格式 | gfx 偏移 | 平滑度 | 观感 |
|---|---|---|---|---|---|
| 13 | `val_sn_ext_22_abal` | BC3 1024² | `0x0` | **28.7** | ✅ 能读出 "VALENTINE STATION" |
| 12 | `val_sn_ext_22_mb` | BC3 512² | `0x705000` | **40.1** | ✅ 另一张招牌 |
| 18 | `nbx_wall_woodpaintedoverlap_02_mb` | BC3 512² | `0x603000` | 40.5 | ❌ 噪声 |
| 3 | `nbx_wall_woodplank_16_ab` | **BC1** 1024² | `0x201000` | 65.2 | ❌ 噪声 |
| — | 所有 `+0x0c=8`（BC1）的条目 | BC1 | — | 45~69 | ❌ **全噪声** |

⇒ 规律：**BC1 类全废**；BC3 里只有 `val_sn_ext_22_*` 成；
说明不是"代码路径不同"，而是**这些槽位里的数据本身不是解码器期待的 BCN 线性块流**。

**下一步入口（按性价比）**：
1. **试 Oodle**：对噪声槽位直接调 `oo2core` 解压（本轮脚本异常，重做一遍即可）——如果 RDR2 把纹理再压了一层，这一下就能通；
2. 若 Oodle 也不行，再考虑 **tile/swizzle**（需要参考实现，CodeWalker 的 `Texture.cs` 可作对照）。

### 17.4b 原始记录

对**全部 27 张**贴图做了「偏移扫描 / mip 顺序假设（mip0 在头 vs 在尾）/ 各 mip 边界」的系统尝试：

* 偏移微调：平滑度几乎不变 ⇒ **不是偏移问题**；
* mip0 在尾 / 在头 / 各 mip 边界：都不改善；
* 唯一差异是内容：`val_sn_ext_22_abal`（平滑度 28.7，能读出字）vs 其余（36~70，噪声）。

⇒ 结论：**不是偏移、不是 mip 顺序**，剩下的可能是
1. **块压缩数据的 tile/swizzle 排布**（RDR2 PC 常见），或
2. format 字节虽像 DXGI 码，但实际另有含义。

**下一步入口**：拿 `val_sn_ext_22_abal`（已知正确）与 `nbx_wall_woodpaintedoverlap_02_mb`（已知错误）
**逐字段对比 ytd 条目**（`+0x08` size / `+0x0c` / `+0x10` / `+0x1c` fmt / `+0x24` / `+0x38` data ptr），
再对同一槽位的原始字节做统计（比如看 8 字节 block 的端点色是否连续），定位是排布还是格式。

---

## 18. 纹理解码：排查终局 + 新发现（2026-10-14 收尾）

### 18.1 已系统排除的假设

| # | 假设 | 做法 | 结论 |
|---|---|---|---|
| 1 | 数据偏移错 | 27 张 × 偏移 0~0x2000 步进 64 | ❌ 平滑度不变 |
| 2 | mip 顺序反 | 全部 mip 边界，头序/尾序 | ❌ 不改善 |
| 3 | 块排布转置/旋转/翻转 | 行列主序 / rot180 / flipX,Y | ❌ 不改善 |
| 4 | 格式判错 | `+0x0c` 字段交叉验证 | ✅ 判定**是对的**（`+0x0c = 2×bpp`：BC1=8、BC3=16）|
| 5 | 数据还压了一层（Oodle） | 调游戏 `oo2core_5_win64.dll`（fuzzSafe=1） | ❌ **返回 -1**，不是 Oodle |
| 6 | 格式其实是 BC4/BC5 | 同样字节按 DXT1/DXT5/BC4U/ATI2 四解对比 | ❌ 没有一列还原出木纹 |

**自相关分析**（关键证据）：正确的那张在 **shift=4096** 处差异最低（23.8）⇒ 数据有 **4096 字节的块周期**；
噪声的那些只有 8/16 字节（=一个 BC 块）的粒度、没有大周期。

### 18.2 ★ 新发现：纹理表基址**不是固定 0x180**

`tools/rdr2_ytd.py` 里把条目表硬编码在 `body+0x180`。实测：

| 文件 | 表基址 |
|---|---|
| `val_01_trainstn_ext+hidr.ytd` | `0x180` ✅（名字解出来是对的）|
| `val_01_.ytd` / `val_01_+hi.ytd` | 也是 `0x180`，但**开头几个槽位是空的**（W/H=0）|
| `0x449106A9.ytd` | **`0x200`** |
| `0xD44DBD8.ytd` | **`0x40`** |
| `val_01_aucbarns_barn2+hidr.ytd` | **扫不出合格条目**（结构可能又不同）|

⇒ **必须自动定位表基址**（按「W/H 为 2 的幂 + `+0x0c∈{8,16}` + `+0x38` 是指向 gfx 的指针 + `+0x28` 指向 ASCII 名」扫描），
不能硬编码。探测器脚本见本轮会话 `/tmp/findtab.py` 的思路，应固化进 `rdr2_ytd.py`。

### 18.3 交接建议（需要"进游戏"的理由）

纯文件路已经走到头。要**确证**纹理的真实排布，只有两条路：

1. **参考实现对照**：拿 `CodeWalker`（GTA V，codeload 可下）的 `Texture.cs` 比对 RDR2 的差异；
2. **运行期证据**（← 推荐）：**进游戏 + GPU 抓帧**，直接看到纹理资源绑定的格式与尺寸，一次定性。
   同时这一步还能顺带解决 **P2 骨架**（运行期骨架是活对象，能直接读骨名↔索引、bind pose）。

⇒ **建议用户开一次游戏**，做一次「站在 Valentine + 触发一个角色动作」的抓取，
一次性把 **纹理格式** 和 **骨架结构** 两个卡点都解决。

---

## 19. 【2026-10-15】纹理 / UV 运行期验证（游戏内取证）

游戏内跑起来后，对 **Valentine 建筑纹理**与 **`.ydr` 顶点 UV** 做了运行期核对：

### 19.1 ✅ 纹理字段（W/H/format）**运行期已证实正确**

在内存里定位到 **纹理条目对象**（对 `nbx_wall_woodplank_16_ab`）：

```
对象 @ 0x192b8865798 : { name ptr @+0x00, next @+0x08, ... }
对象 @ 0x192b8865778 : u32 0x00015600 (= 87552, 与文件 size 一致)
对象 @ 0x192b8865788 : u16 0x0400(W=1024)  u16 0x0400(H=1024)  u32 0x48010001(fmt)
```

⇒ **和 `.ytd` 文件里解析出的 `W=1024 / H=1024 / fmt=0x48010001` 完全一致**。
**结论**：`.ytd` 的**表结构、字段偏移（W@+0x18/H@+0x1A/fmt@+0x1C/size@+0x08）全部正确**，
问题**只在数据的块排布（tile/swizzle）或 format→BC 映射**，不在字段解析。

### 19.2 ⚠️ `.ydr` 顶点布局修正 + UV 仍未解

- **修正**：顶点缓冲是**平面分属性数组**，但**位置数组是 `12 B/顶点` 连续排布**（不是 40B 间隔）。
  之前按 `stride=40` 逐顶点读会把位置数组"串读"成假顶点 —— 已纠正。
- 位置之后的**属性区是打包数据**（**不是 float**）：
  - 模式为 **4 字节一组、每 4 个连续顶点取值相同**（典型「每面/每四边形常量」，如打包法线）；
  - attr1 名义 `16 B/顶点`（4×u32），每列有 ~1000~1200 个不同值（3171 顶点）。
- **排除了 half-float UV**：把 attr1 的低/高 16 位按 IEEE half 解，得到 `inf/nan` ⇒ 不是 `2×half` 的 UV。
- **当前结论**：**顶点里确实带打包属性，但既不是 `float2` 也不是 `2×half` 的 UV** —— 具体编码（packed normal / UNorm / 自定义）待定，
  所以查看器目前仍用 **box mapping** 现算 UV。

**下一步建议**：拿同一顶点在**运行期**的内存顶点缓冲 vs 文件缓冲做逐字节比对（两者应完全一致），
再用「已知是平面的面（如墙面）其法线应为常量」这一约束反推打包格式。

### 19.3 ✅ UV 结论（系统性验证）：**建筑顶点本来就无 UV，游戏走 shader 侧世界空间映射**

> ❌ **本节结论已被 §20 推翻（2026-10-16）**：建筑/地形顶点**有** `TEXCOORD0/1(/2)`，
> 之前的"相关性全 ≈ 0 / 一团乱麻"来自**没读顶点声明**（按猜测偏移切字节）。
> 保留本节仅作"当时怎么排除的"追溯；**以 §20 为准**。

用两条硬判据**系统地**验证了「顶点是否带 UV」：

| 判据 | 做法 | 结果 |
|---|---|---|
| **法线相关性** | 逐顶点取所属面的**几何法线**，对属性区每个字节槽（A1 的 4×u32 按 float/lo_s16/hi_s16/u8 四种解码 + A2 的 3×float）算相关系数 | **全部 ≈ 0**（最高 0.095）⇒ 属性**不是法线** |
| **UV 展开合理性** | 把属性当 UV 在 UV 空间画 6081 条三角线框 | **一团乱麻**（中心密结 + 放射线）⇒ **不是 UV** |

⇒ **顶点属性区（A1 16B + A2 12B）既不是法线也不是 UV**（应是切线/AO/混合权重一类的渲染辅助量）。

**结论**：`.ydr` 建筑的顶点里**确实没有 UV** —— 与早前「实测排除 UV」一致。
⇒ **RDR2 建筑着色器在 shader 内部做世界空间 / triplanar 映射**，
   所以查看器里的 **box mapping 不是"退而求其次"，而是与游戏同源的正确做法** ✅

**因此「贴图 UV」这条线真正剩下的只有一件事**：把 `.ytd` 的**块排布（tile/swizzle）**解对
（字段 W/H/format 已被运行期证实正确，见 §19.1），让 box mapping 能贴上**游戏原生纹理**。

---

## 20. ★★ 推翻了 §11.3 / §19.2 / §19.3 的结论：**顶点里本来就有 UV**（2026-10-16）

> ⚠️ **本文 §11.3、§19.2、§19.3 的"顶点里没有 UV"是错的**。根因是**没读顶点声明**、
> 把 SOA 数据按交织/猜测偏移解读。下面是实测纠正与新结论。

### 20.1 决定性事实：`VertexDeclarationG9`（顶点语义在 `VertexBuffer + 0x38`）

RDR2 的顶点缓冲是 **SOA（平面分属性数组）**，GTA V 是 AOS（交织）。
CodeWalker `VertexDeclarationG9.HasSOA` 的源码注释原文：

> `//seems to always be false for GTAV gen9  (but true for RDR2)`

属性语义**不在顶点缓冲里**，而在 `VertexBuffer + 0x38` 指向的 `VertexDeclarationG9`：

```
Offsets[52] u32 (208B)  ← 各语义元素在顶点数据块内的起始偏移
Sizes[52]   u8  ( 52B)  ← 各元素**每顶点步长**（stride，不是元素大小）
Types[52]   u8  ( 52B)  ← 元素格式（= VertexDeclarationG9ElementFormat，即 DXGI 码）
Data        u64         ← bit0=HasSOA / bit2..9=VertexSize / bit10..=VertexCount
```

元素下标 → 语义（CodeWalker `GetLegacyComponentIndex`）：
`0 POSITION · 4 NORMAL · 8 TANGENT · 9 TANGENT1 · 16 BLENDWEIGHTS · 20 BLENDINDICES ·
24 COLOR0 · 25 COLOR1 · 26 COLOR2 · 28 TEXCOORD0 · 29 TEXCOORD1 · 30 TEXCOORD2 …`

**SOA 读法**：元素 i 的第 v 个顶点 = `数据块起点 + Offsets[i] + Sizes[i] * v`。
（`Offsets[0]=0, Sizes[0]=12` ⇒ 位置恰好是"开头 count×12 连续数组"，这正是 §5 观察到的现象。）
⇒ **"位置之后两块 16B/12B 未知属性"（§5 表）其实是被当作一坨读的结果**；按声明拆开就全是明确的语义。

**工具**：`tools/rdr2_vdecl.py`（新增）
```
python tools/rdr2_vdecl.py <file.ydr>            # 打印每个几何体的语义布局
python tools/rdr2_vdecl.py <file.ydr> --check    # UV 合理性自检（随位置线性）
python tools/rdr2_vdecl.py <file.ydr> --json o.json
```

### 20.2 实测布局（两个家族）

| 资产 | stride | 布局（实测） |
|---|---|---|
| 建筑 `.ydr`（`val_03_saloon_ext`、`val_01_trainstn_ext`…） | **40** | `POSITION(12)` `NORMAL(4)` `TANGENT(4)` **`COLOR0(4)`** **`TEXCOORD0(8)`** **`TEXCOORD1(8)`** |
| 地形 `.ydr`（`l_09__hd_0_*`，Valentine 那块） | **56** | `POSITION(12)` `NORMAL(4)` `TANGENT(4)` `TANGENT1(4)` **`COLOR1(4)` `COLOR2(4)`** **`TEXCOORD0/1/2(8×3)`** |

* NORMAL/TANGENT 是 `R10G10B10A2_UNORM`（4B 打包），之前按 float 读自然全是噪声。
* 建筑的 `COLOR0` = **逐顶点调色板/染色选择子**（配合 shader 的 `TintPaletteTex`、资产的 `*_pal` LUT，
  见 §20.4）。
* 地形的 `COLOR1/COLOR2` = **逐顶点图层混合权重**。

### 20.3 ★ UV 是真的（量化验证）

`tools/rdr2_vdecl.py --check` 用「UV 在网格边上应与位置线性相关（\|Δuv\|/\|Δpos\| 的 MAD 小）」判据：

| 资产 | 元素 | 范围 | \|Δuv\|/\|Δpos\| 中位 | MAD | 判定 |
|---|---|---|---|---|---|
| `val_03_saloon_ext` geom1（木墙） | TEXCOORD0/1 | [-13.3, 25.9] | **0.9929** | **0.114** | ✅ 真 UV（≈1 单位/米） |
| 同上 geom2（屋顶） | TEXCOORD0 | [-3.5, 7.7] | 0.2723 | **0.0039** | ✅ 真 UV（另一套平铺比例） |
| 同上 geom2 | TEXCOORD1 | [-5.0, 6.0] | 0.1046 | **0.0092** | ✅ 第二层用**不同比例**的 UV |
| `l_09__hd_0_0_0`（地形） | TEXCOORD0 | [0.375, 0.62] | 0.0019 | **0.0000** | ✅ 全局平面 UV（宏观色图用） |
| 同上 | TEXCOORD1 | [-266, 11] | 0.1830 | 0.0238 | ✅ 平铺图层 UV |

**地形 UV0 的全局拟合**（跨 64 个 `l_09__hd_0_*` 子网格，UV0 ≈ a·世界坐标 + b）：

```
u = 0.00192·x + b      （各子网格 a 一致到 3%，b 按 1/8 步进 = 子网格分块偏移）
v = -0.00196·y + b
⇒ 1/a ≈ 520 ≈ 512 = 地形瓦片尺寸 ⇒ UV0 是【以 512 m 瓦片为单位、跨整个瓦片连续的全局平面 UV】
⇒ 宏观色图 2048² 覆盖 512×512 m ≙ 4 px/m
```

⇒ 结论：**地形用一个连续 UV 即可正确投影宏观色图**，不再需要 box mapping 估。

### 20.4 为什么"现在的贴图都是错的"——两处材质语义被丢掉

用 `VertexDeclarationG9` 同法把 shader 名解出来（`ShaderFX.Name` 是 `joaat` 哈希，用
`names.txt` 里的 `common/shaders/db/*.sps` 反查，实测**全部命中**）：

| 资产 | 实测 shader | 含义 |
|---|---|---|
| 地形 `l_09__hd_0_*` | **`terrain_uber_4lyr_pxm_hbb` / `..._mud_dm_hbb` / `..._spx_dm_hbb`** | **多层地形材质** |
| 建筑 `val_03_saloon_ext` | `standard` / **`standard_2lyr`** / **`standard_dirt`** / `standard_decal*` / `cpv_only` | **2 层材质** / 纯逐顶点色 |

**(1) 建筑 = 2 层 + 逐顶点调色板**（不是单张 albedo）
`standard` / `standard_2lyr` / `standard_dirt` 的纹理引用模式实测为：

```
[0] <楼名>_pal            ← 调色板 LUT（256×4，格式 0x5B = B8G8R8A8_UNORM_SRGB）
[1] <A>_ab                ← 底层 albedo
[2] <B>_abal              ← 叠层 albedo     （例：val_be_wood01b_ab + nbx_dirt_grungedr_03c_abal）
[3] <A>_ma                ← 叠层**混合遮罩**
```

⇒ 游戏是 `lerp(A_ab, B_abal, mask)` 再经调色板染色。现在的管线用 `albedo_of()` **只取一张**、
并把 `_ma`/`_pal` 当噪声丢掉 ⇒ 观感"就是错的"。

**(2) 地形 = 4 层材质 + 宏观色图**（不是一张草）
每块地形瓦片（512 m）真正的素材在 `levels/rdr3/terrain/<grid>/<tile>.rpf`（例 `jklm_07_10/l_09_.rpf`）：

| 文件 | 内容 |
|---|---|
| `<tile>_.ytd`（64 张） | **`l_09_t` = 2048² 宏观色图**（BC1_sRGB，**就是该瓦片的俯视地表色/镇子/道路/河**）、`l_09_n` = 2048² 法线（**BC7**）、以及各类平铺图层 |
| `<tile>_+hi.ytd`（64 张） | HD 版图层（1024² 的 `*_abte` / `*_nm` / `*_ma`） |
| `<tile>__bkt_{1,2,3}.ytd` | 每个"材质桶"的图层集 + **混合遮罩**（`tile_blend`、`griscree01_mask`…，RGBA=4 层权重） |
| `<tile>__hd_0_i_j.ydr`（64 块） | **真正的地表网格**（stride 56，带 3 套 UV + 图层权重） |

而现在查看器用的是 **LOD combine 瓦片 + 单张 `hea_grass_lush_01_abte`** ⇒ 必然是一整片绿。

### 20.5 ★ 纹理解码器补了两类被**静默丢弃**的格式

`ytd_to_png.py` 旧版 `entries()` 里有 `if f not in FMT: continue`，而 `FMT` 只有 BC1/BC3
⇒ **调色板（0x5B B8G8R8A8）与 BC7/BC5 法线被当不存在**（这就是"地形法线/调色板取不到"的原因）。
本轮已扩：

| 格式码 | 类型 | 处理 |
|---|---|---|
| `0x47/0x48/0x4D/0x4E` | BC1 / BC3 | 原 DDS 路径 |
| `0x62/0x63` | **BC7** | `DDS_HEADER_DXT10` + `dxgiFormat=98/99`（**PIL 12 可解**，实测 2048² 法线出图） |
| `0x52/0x53/0x54` | **BC5**（法线） | `dxgiFormat=83/84/85` |
| `0x4F/0x50/0x51` | BC4 | `dxgiFormat=80/81/82` |
| `0x57/0x5A/0x5B` | **B8G8R8A8（调色板）** | 直接 `frombytes('BGRA')` + 通道交换 |
| `0x1C/0x1D` | R8G8B8A8 | 直接 `frombytes('RGBA')` |

另修一处真 bug：`ytd_to_png.py` 自带的 `find_base()`（扫到 `0x4000`）会选到**假基址**
（同一文件它数出 108 张、`rdr2_ytd.py` 数出 64 张）⇒ 已改为**复用 `rdr2_ytd.Ytd`** 单一真相源。

### 20.6 结论（回答"还有没有办法继续解包获取"）

**有，而且素材一直都在包里**，缺的只是"读顶点声明 + 认全纹理格式 + 认材质分层"三件事：

1. ✅ **UV 有**：建筑 2 套（`TEXCOORD0/1`）、地形 3 套（`TEXCOORD0/1/2`）；
2. ✅ **地形贴图层有**：`<tile>_.rpf` 里的 `t/_n` + `_bkt_*.ytd` 图层集 + 混合遮罩 + `_hd_0_i_j.ydr` 地表网格；
3. ✅ **建筑 2 层 + 调色板有**：`_ab` + `_abal` + `_ma` 遮罩 + `_pal`（0x5B 可解）；
4. ✅ **缺的 40 张共享 `.ytd`** 也有了明确来源：地形走 `terrain/<grid>/`、建筑共享贴图走 **`levels/rdr3/gtxd/`（`<area>_gtxd` / `*_gtxd+hi`）**与各 area 包。

**注意**：`terrain_uber_4lyr` 在资产里**只声明 7 条纹理引用**（1 遮罩 + 2 层 × (nm, abte, ma)），
"4lyr" 的第 3/4 层到底来自"遮罩 RGBA 选层"还是"其他桶字典"，要拿 `.sps` 参数表才能钉死
（`.sps` 在 `shaders_x64.rpf → shaders/fxdb/sga_win32_60_final.fxdb`，本轮已取出，未逐条解参数表）。

> ⚠️ **本节末尾的这条"注意"已被 §21 推翻**：那不是 7 条引用，而是**我们按 16 字节步长读数组读错**
> （正确是 8 字节）；`terrain_uber_4lyr` 实际有 **16 个纹理 slot**，4 层都在。

---

## 21. ★★ 用社区权威结构体头文件校正（2026-10-16）——并修掉一个**材质全错位**的 bug

### 21.1 权威来源（社区 RDR2 mod 工具链的格式定义，已落地本机）

| 路径（`tools/ref/`） | 内容 |
|---|---|
| `fivem-*/rmcDrawable.h`（源：`citizenfx/fivem → code/components/rage-formats-x/include/`）| **RDR3 权威结构体**（`RAGE_FORMATS_GAME_RDR3` 分支）：`grcTexture` / `grcTexturePC` / `grcTextureRef` / `grmShader` / `grmShaderFx` / `grmShaderGroup` / `sgaShaderParamData` / `sgaInputLayout` / `grcVertexBuffer` |
| `fivem-*/ConvertFormats.RDR3.cpp`（95 KB）| RSC7 ↔ RSC8 的 **RDR3 转换器**（社区靠它让 CodeWalker 能读 RDR2 资源） |
| `Sollumz-RDR-main/cwxml/ModRDRShaders.xml` | **197 个 RDR2 shader 的纹理参数表**（`slot → 参数名`） |

> 背景（回答"社区怎么 mod RDR2"）：`RPF8 解包 → RSC8→RSC7 转换 → CodeWalker XML → Blender(Sollumz) →
> 按原路径放进 LML(lml/) 替换`。贴图走 `RDR2 Texture Toolkit`（GTA5 ytd → RedM ytd 转换器）。
> ⇒ **能替换 ⇒ 一定能提取**；而他们连格式定义都开源了。**我们比社区少一环**：直接读 RSC8。

### 21.2 交叉验证：我们的 `.ytd` 字段 = RDR3 `grcTexture`

```
RDR3 grcTexture（rmcDrawable.h，datBase 之后）：
  +0x00 u32 m_blockSize     +0x04 u32 m_blockCount
  +0x08 u32 m_flags (0x18008002)   +0x0C u32 m_unk0
  --- sga::ImageParams ---
  +0x10 u16 m_width   +0x12 u16 m_height   +0x14 u16 m_depth   +0x16 u8 m_dimension
  +0x17 u8  m_pixelFormat (sgaBufferFormat = DXGI 码)
  +0x18 u8 m_tileMode(0x0D)  +0x19 u8 m_antiAliasType  +0x1A u8 m_levels  …
  +0x1E u16 m_usageCount      +0x20 pgPtr<char> m_name
  +0x28 pgPtr<sga::ShaderResourceView> m_srv   +0x30 pgPtr<void> m_pixelData
```

我们的读法（`.ytd` 条目基址 `base`）与它的关系：**结构体起点 = `base + 8`**（RDR3 含 8B datBase 前缀），于是

| 我们读的 | 实际字段 | 校验 |
|---|---|---|
| `+0x08` "size" | `m_blockSize` | — |
| `+0x0C` 8/16 | `m_blockCount` | — |
| `+0x10` 常量 `0x18008002` | **`m_flags`（默认值就是 0x18008002）** | ✅ |
| `+0x18/0x1A` W/H | `m_width/m_height` | ✅ |
| `+0x1C` u32（`fmt>>24` 是格式码） | `m_depth(u16)+m_dimension(u8)+**m_pixelFormat(u8)**` | ✅ **解释了"格式码在 `fmt>>24`"** |
| `+0x1F` 格式字节 | `m_pixelFormat` | ✅ |
| `+0x28` 名称 ptr | `m_name` | ✅ |
| `+0x38` 数据 ptr | `m_pixelData` | ✅ |

**新认出的可用字段**：`m_levels`（**mip 数**）、`m_dimension`（1=2D）、`m_tileMode`（0x0D）、`m_srv`。
⇒ 以后不必再猜 mip 链长度，直接读 `m_levels`。

### 21.3 ⚠️ 修掉一个"材质整体错位"的真 bug（重要）

```
RDR3 grmShader：
  +0x00 u32 m_shaderHash        +0x04 u32 pad
  +0x08 pgPtr m_parameters
  +0x10 pgPtr<grcTextureRef> m_textureRefs     ← ★ 纹理数组
  +0x20 pgPtr<sgaShaderParamData> m_parameterData   ← numTextures 在这里
RDR3 sgaShaderParamData：{ u8 numCBuffers; u8 numTextures; u8 numUnk1; u8 numSamplers; u32 numParams; params[] }
RDR3 grmShader Resolve： for (i < m_parameterData->numTextures) (*m_textureRefs)[i].Resolve();
```

* **数组元素是 `pgPtr` ⇒ 8 字节**，长度 = `numTextures`。
* 旧实现 `parse_shader_group` 按 **16 字节**步长读 ⇒ **只读到偶数 slot** ⇒ 材质/图层整体错位。
  **这就是"建筑网格贴图都是错的、地形把 `_nm` 当 albedo"的直接原因。**

**修复后实测（与 `ModRDRShaders.xml` 逐条吻合）**：

| shader | `numTextures` | XML 条数 | 结果 |
|---|---|---|---|
| `terrain_uber_4lyr_pxm_hbb` | **16** | 16 | ✅ 4 层 × (diffuse,bump,materialA) + `lookuptexture` + `tinttexture` + `tintbumptexture` |
| `standard` | **7** | 7 | ✅ `tintpalettetex / diffusetex / bumptex / speculartex …` |
| `standard_dirt` | **9** | 9 | ✅ `diffusetex + diffusetex2`（两层）+ `bumptex` + `tintpalettetex` |
| `standard_2lyr` | **13** | 13 | ✅ `lyr0/lyr1` 各 4 张 + `dirtdiffusetex` + `controltexturetex` |

**修好后读到的真实材质（节选）**：

```
地形 l_09__hd_0_0_0.ydr / terrain_uber_4lyr_pxm_hbb：
  slot[ 0] lookuptexture               = l_09_c                      ← 图层查找/混合图
  slot[ 1..3]  layer0                  = hea_dirt_cracked_rock_02_{abte,nm,ma}
  slot[ 4..6]  layer1                  = hea_grass_val_01_{abte,nm,ma}
  slot[ 7..9]  layer2                  = hea_grass_lush_je_02_{abte,nm,ma}
  slot[10..12] layer3                  = hea_val_dirt_grassy_02_{abte,nm,ma}
  slot[13]     tinttexture             = l_09_t   ★ 2048² 宏观色图
  slot[15]     tintbumptexture         = l_09_n   ★ 2048² BC7 法线
建筑 val_03_saloon_ext.ydr：
  standard_dirt：tintpalettetex=…_pal, diffusetex=val_be_wood01b_ab,
                 diffusetex2=nbx_dirt_grungedr_03c_abal, bumptex=val_be_wood01b_nm
  standard_2lyr：lyr0=val_ew_woodplank56_{ab,nm,ma}, lyr1=val_ew_woodplank55_{ab,nm,ma},
                 controltexturetex=val_ew_woodplank_cont_1
```

### 21.4 顺带确认（同源）

* `grcVertexBuffer`（RDR3）：`m_vertexCount / m_vertexSize / m_vertexData / m_vertexFormat` ⇒
  我们的 `+0x08/+0x0C/+0x18/+0x38` **逐字段对上**（同样 `-8` 前缀）；`m_vertexFormat` = `sgaInputLayout`。
* `sgaInputLayout` = `{ u32 offsets[52]; u8 sizes[52]; sgaBufferFormat types[52]; hasSOA:1; flag:1; vertexSize:8; vertexCount:22; }`
  ⇒ 与 §20 的 `VertexDeclarationG9` 完全一致，**RDR2 顶点是 SOA 板上钉钉**。
* `grmShaderFx`（RDR3）**没有**名字字符串指针，只有 `m_shaderHash` ⇒ 反查 shader 名必须靠
  `ModRDRShaders.xml` / `names.txt` 的 `*/db/*.sps`（我们两条都用了）。

### 21.5 本轮落地

| 产物 | 说明 |
|---|---|
| `tools/rdr2_shader_params.py`（新） | 载入 `ModRDRShaders.xml` → `{shader_hash: {slot: 参数名}}` + `role()`；带兜底表 |
| `tools/rdr2_ydr.py`（改） | **`parse_shader_group` 改 8 字节步长 + 从 `m_parameterData` 读 `numTextures`**；新增 `parse_shader_hashes()`；`albedo_of()` 改为**按 shader 参数角色**挑 albedo；mesh 增加 `shader` / `shader_hash` / `texs_detail` |
| `tools/ref/`（新增） | `Sollumz-RDR-main/`、`rdr2-unpack-main/`、`Sollumz-main/`、`RAGE-RDR2-Binary-Packer-main/`、`AizenX-RDR2-XML-Forge-main/`、`fivefury-main/`，以及 `rmcDrawable.h` / `grcTexture.h` / `ShaderInfo.h` / `ConvertFormats.RDR3.cpp` |
