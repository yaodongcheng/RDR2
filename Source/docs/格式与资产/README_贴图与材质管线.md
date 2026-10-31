# RDR2 贴图与材质管线 —— 从 `.rpf` 到"能看的贴图"

> 工作目录：`D:\BrainMaker\大镖客2解包分析` ｜ 2026-10-16 定稿
> 本文只讲**贴图/材质**这条线（几何见 `RDR2_ydr几何格式.md`，骨架见 `RDR2骨架_yft格式.md`，动画见 `RDR2_ycd动画解码.md`）。
> **结论先给**：RDR2 的贴图**能 100% 正确解出**，之前的"全是错的/马赛克"是**四处解析错误**造成的，全部已定位并修好。

---

## 1. 一句话

**RDR2 的贴图 = `.ytd`（RSC8 容器里的一张纹理表）+ 贴在几何体上的"按 slot 语义命名"的材质引用；
UV 在顶点缓冲里（`TEXCOORD0/1`）。** 三件事各自都有坑，踩过的都在 §7。

---

## 2. 资产在哪（层级）

| 层级 | 位置 | 说明 |
|---|---|---|
| RPF8 | `H:\...\levels_1.rpf` 等 | 需要 TFIT2 密钥（`secrets.bin`，**不在游戏里**）|
| 区域包 | `levels/rdr3/area/jklm_07_10/val_01_.rpf` … `val_07_.rpf` | 每个"街块"一个包，内含 `<楼>_ext.ydr` + `<楼>_ext+hidr.ytd` |
| **共享纹理字典** | `levels/rdr3/gtxd/gtxd_valentine.rpf`（在 `levels_2.rpf` 内）| **Valentine 的公共贴图**（`valentine.ytd` / `val_02030405.ytd` / `val_0203g.ytd` / `val07g.ytd` + `+hi`）|
| 地形贴图 | `levels/rdr3/terrain/jklm_07_10/<tile>_.rpf` | `<tile>_.ytd`（含宏观色图 `l_09_t`）/ `_+hi.ytd` / `__bkt_{1,2,3}.ytd` |
| 大地图 | `levels/rdr3/gtxd/gtxd.rpf` | ⚠️ **只有 `gtxd.ymt` 清单，没有贴图**（已排除）|

> 找不到某张贴图时，按上表**逐层找字典**；本项目已抽 1086 个 `.ytd`，索引 **3657** 个贴图名。

---

## 3. `.ytd` 结构（= R3R3 `grcTexture`，权威已对上）

`.ytd` = RSC8（16B 头 + system 段 + graphics 段），**纹理表条目步长 `0xB0`，表基址每文件不同**（实测 `0x40 / 0x180 / 0x200 / 0x2e0 / 0x360`）→ 必须用 `find_base()` 自动定位。

条目字段（**我们读到的地址 = 结构体起点 + 8**，因为 RDR3 含 8B `datBase` 前缀）：

| 我们的偏移 | RDR3 权威字段（`citizenfx/fivem → rage-formats-x/include/rmcDrawable.h`）| 说明 |
|---|---|---|
| `+0x08` u32 | `m_blockSize` | ≈ mip 链字节数 / 16 |
| `+0x0C` u32 | `m_blockCount` | |
| `+0x10` u32 | **`m_flags`** | 默认 `0x18008002`（一直以为是"魔法常量"）|
| `+0x18` u16 | `m_width` | |
| `+0x1A` u16 | `m_height` | |
| `+0x1C` u32 | `m_depth(u16)+m_dimension(u8)+**m_pixelFormat(u8)**` | ⇒ **格式码 = `fmt >> 24`** 的由来 |
| `+0x1F` u8 | `m_pixelFormat` | DXGI 码 |
| `+0x28` u64 | `m_name` | ASCII 名 |
| `+0x38` u64 | `m_pixelData` | gfx 段偏移 |

**新认出的可用字段**：`m_levels`（mip 数）、`m_dimension`（1=2D）、`m_tileMode`（0x0D）、`m_srv`。

---

## 4. 纹理格式（DXGI 码，已扩全）

`fmt >> 24` 就是 **DXGI_FORMAT**（= RDR3 的 `sgaBufferFormat`）。**解码器必须认识这些，否则会被静默丢弃**（这就是"调色板/BC7 取不到"的原因）：

| 码 | 格式 | 解码方式 |
|---|---|---|
| `0x46/0x47/0x48` | BC1 / TYPELESS / sRGB | DDS 四字节码 `DXT1` |
| `0x49/0x4A/0x4B` | BC2 | `DXT3` |
| `0x4C/0x4D/0x4E` | BC3 | `DXT5` |
| `0x4F/0x50/0x51` | BC4 | `DDS_HEADER_DXT10`, dxgi=80/81/82 |
| `0x52/0x53/0x54` | BC5（法线）| dxgi=83/84/85 |
| `0x5E/0x5F/0x60` | BC6H | dxgi=95/96/97 |
| `0x61/0x62/0x63` | **BC7** | dxgi=98/99（**PIL 12 可解**）|
| `0x57/0x5A/0x5B` | **B8G8R8A8**（调色板 `_pal`）| 直接 `frombytes('BGRA')` + 通道交换 |
| `0x1B/0x1C/0x1D` | R8G8B8A8 | `frombytes('RGBA')` |

> ⚠️ **DDS 头必须正好 128 字节**（多写 4 字节 ⇒ 像素整体偏移 ⇒ 全噪声，会被误判成 tile/swizzle）。

---

## 5. 名字解析（三个坑）

1. **大小写不敏感**：RDR2 名字是哈希，**实测 `nbx_wood_beamBare01_ma`（shader 引用） ↔ `nbx_wood_beambare01_ma`（字典里）** —— 用大小写敏感匹配会丢一大批（本项目从 26 缺降到 9 缺就靠这条）。
2. **名字池有串接**：部分条目的名字会读成两个名字粘在一起（如 `rr_template_hea_weed_hbb_abrr_template_hea_weed_hbb_al`）⇒ 查找要允许**前缀命中**。
3. **同名多份**：同一名字可能在多个字典里（`X.ytd` 与 `X+hi.ytd`）⇒ **取面积最大的一份**（HD）。

---

## 6. ★ 材质 = shader 的 **slot 语义**（不是文件名后缀）

`ShaderFX` 里有一张**按 slot 索引的纹理指针数组**（`u64[NumTextures]` @ `ShaderFX+0x10`，`NumTextures` 在 `+0x20 → sgaShaderParamData.numTextures`）。
**slot 的含义由 shader 参数表决定**，来自社区权威（`Sollumz-RDR/cwxml/ModRDRShaders.xml` + `RedDead2Blend/data/shaders/*.json`，两来源**顺序逐条一致**，已固化为 `tools/rdr2_shader_params.py`，195 个 shader）。

| shader | slot 表（要点）|
|---|---|
| **`terrain_uber_4lyr_*`**（地形）| `0 lookuptexture` · `1..3` = **layer0 的 diffuse/bump/materialA** · `4..6` layer1 · `7..9` layer2 · `10..12` layer3 · **`13 tinttexture`** · `15 tintbumptexture` |
| **`standard`**（建筑）| `0 tintpalettetex` · `2 diffusetex` · `4 bumptex` · `5/6 speculartex/2` |
| **`standard_dirt`**（最常见的建筑）| `0 tintpalettetex` · `2 diffusetex` · **`4 diffusetex2`** · `5 bumptex` · `6 speculartex` |
| **`standard_2lyr`** | `0 tintpalettetex` · `1..4` = lyr0 的 diffuse/normal/materialA/materialB · `5..8` lyr1 · `9 dirtdiffusetex` · `10 controltexturetex` |
| **`terrain_lod_2lyr_grass_wetness`**（查看器用的 LOD 地形）| `0 diffusetex` · `2 diffusetex2` · `3/4 bumptexture/2` · `5/6 speculartexture/2` |
| `cpv_only` | 只有逐顶点色（没有 albedo）|

**实测验证**：`terrain_uber_4lyr_pxm_hbb` 资产里 `NumTextures=16` = 表里 16 条；`standard=7`；`standard_dirt=9`。slot 名字与数据语义**完全吻合**（slot13 `tinttexture` 就是 2048² 的 `l_09_t`）。

> 也解释了为什么"只看文件名后缀猜 albedo"必错：
> `standard_dirt` 的 **第 2 张 albedo 在 slot 4（`diffusetex2`）**，按后缀排根本选不出来。

---

## 7. UV 从哪来（**顶点里有 UV**）

RDR2 顶点是 **SOA（平面分属性数组）**，语义在 `VertexBuffer + 0x38` 的 **`VertexDeclarationG9`**（= RDR3 `sgaInputLayout{offsets[52]; sizes[52]; types[52]; hasSOA; …}`）。

| 资产 | stride | 布局（实测）|
|---|---|---|
| 建筑 | 40 | `POSITION(12) NORMAL(4) TANGENT(4) COLOR0(4) **TEXCOORD0(8) TEXCOORD1(8)**` |
| 地形 | 56 | `POSITION NORMAL TANGENT TANGENT1 COLOR1 COLOR2 **TEXCOORD0/1/2**` |

**读法**：元素 i 的第 v 个顶点 = `数据块起点 + offsets[i] + sizes[i] * v`。
**实测 UV 是真的**：木墙 `|Δuv|/|Δpos|` 中位 0.99 / MAD 0.11（≈1 UV 单位 = 1 米）；地形 UV0 全局拟合 `1/a ≈ 512 m`。

---

## 8. 贴图三级解析 + 兜底（顺序很重要）

```
① .ytd 索引（名字→条目，大小写不敏感，取 HD）        ← 权威，永远优先
② .ydr 内嵌（只对 *_pal 开放；且要求 blockSize↔面积自洽）
③ 同族回退：去后缀基名 → 词干（paintwood→woodpaintedoverlap）→ 前缀
④ 兜底：本模型"出现最多的 albedo"（避免整块占位色）
```
⚠️ **①必须在②之前**：`.ydr` 里 shader 的 `grcTextureRef` 结构 `+0x18` 是 **pad（不是 W/H）**，
偶尔"看起来合法"⇒ 会从 `.ydr` 读到无关字节 ⇒ **彩虹噪声**（这就是"马赛克"的真凶）。

---

## 9. 命令清单

```bash
UV="C:/Users/yaodongcheng/AppData/Roaming/com.brainmaker.client/cowork-updates/uv-binary/uv.exe"
RP=tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe

# 0) 抽共享纹理字典（Valentine）
$RP extract "H:/EPICGAMES/RedDeadRedemption2/levels_2.rpf" work/gtxd "levels/rdr3/gtxd/gtxd_valentine.rpf"
$RP extract work/gtxd/.../gtxd_valentine.rpf work/gtxd_out ".ytd"

# 1) 单张 .ytd 列表 / 解 PNG（自动定位表基址、支持 BC7/BC5/BGRA）
$UV run python tools/rdr2_ytd.py <file.ytd>
$UV run python tools/ytd_to_png.py <file.ytd> <outdir> --sheet sheet.png

# 2) shader → slot → 参数名
$UV run python tools/rdr2_shader_params.py

# 3) 顶点语义 / UV 自检
$UV run python tools/rdr2_vdecl.py <file.ydr> [--check]

# 4) 按"真 UV + slot 语义材质"导出 4 栋建筑 demo → 单文件查看器
$UV run python tools/export_building_materials.py
$UV run python tools/build_material_viewer.py     # export/levels/town/materials_demo.html

# 5) 整镇（69 个高清建筑 + 实体摆放）→ 单文件查看器
$UV run python tools/export_town_textured.py
$UV run python tools/build_town_textured_viewer.py # export/levels/town/town_textured.html
```

---

## 10. 踩过的坑（逐条对应到修复）

| # | 现象 | 根因 | 修复 |
|---|---|---|---|
| 1 | 解出来全是噪声 | DDS 头写了 **132** 字节（应 128）⇒ 像素偏移 | 写严格 128 字节头 |
| 2 | 格式判错成 BC7 | 格式码在 `fmt>>24`（DXGI），不是 `fmt` 本身 | 取 `fmt>>24` 并配全 DXGI 表 |
| 3 | 表基址找错 ⇒ 条目错位 | 每文件基址不同，且旧 `find_base` 会选到假基址 | 自动定位 + **复用 `rdr2_ytd.Ytd`**（单一真相源）|
| 4 | 调色板 / BC7 法线"不存在" | `entries()` 里 `if f not in FMT: continue` **静默丢弃** | 扩格式表（BC7/BC5/BC4/BGRA/RGBA）|
| 5 | 一大批贴图找不到 | **名字大小写不一致** | 索引键全部小写 |
| 6 | **马赛克/彩虹噪声** | 解析顺序：先 `.ydr` 内嵌（其 `+0x18` 是 pad）| **顺序反转为 `.ytd` 优先**；内嵌只对 `*_pal` |
| 7 | 贴图挂错面 / 整片占位色 | 用 `extract_at` 的**下标**对齐几何体（它会跳过无 VB 的几何体）⇒ 材质错位 | 改为按几何体**自己的 `ShaderID`** 取材质 |
| 8 | 取到低清版 | 同名多份只取 glob 顺序第一个 | 取**面积最大**（HD）|
| 9 | 少数仍缺 | 字典没抽到 | 词干回退 + dominant 兜底；HUD 用 `≈原名` 明示 |

---

## 11. 现状与产物

| 项 | 状态 |
|---|---|
| `.ytd` 解码 | ✅ BC1/BC3/BC4/BC5/BC6H/BC7 + BGRA8/RGBA8；`l_09_+hi.ytd` **64/64 全解** |
| 材质语义 | ✅ 195 个 shader 的 slot 表（Sollumz XML + RedDead2Blend JSON 双源交叉验证）|
| UV | ✅ 建筑 2 套 / 地形 3 套，实测随位置线性 |
| 覆盖 | 整镇 69 个高清建筑 / 798k 顶点 / 419 个几何体；贴图 **171 张（缺 13、回退 15）** |
| 建筑 PBR | ✅ albedo + `_nm` 法线（翻 G）+ `_ma`→ORM（metal/rough/AO），见 §11.3 |

| 产物（双击即开） | 内容 |
|---|---|
| ⭐ `export/levels/town/town_textured.html` | **整个瓦伦丁小镇 + 地形 + 树木**：真 UV + 原生贴图；69 个高清建筑（按实体摆放）+ **14 块地形 LOD**（世界空间平面 UV + 草地贴图）+ **728 棵树**（`?v=0 全镇 / 1 主街 / 2 街口`）|
| ⭐ `export/levels/town/materials_demo.html` | 4 栋重点建筑（酒馆/银行/火车站/监狱）近景 + 逐几何体材质清单 |
| `export/levels/town/town_textured_{v0,v1,v2}.png` · `materials_demo_{1,train,all}.png` | 截图 |
| `export/models/textures/terrain_l09/` | 地形实证素材（`l_09_t` 宏观色图 2048²、BC7 法线、桶遮罩、图层）|

### 11.1 加了地形之后踩的两个坑（2026-10-16 续）

| 现象 | 根因 | 修复 |
|---|---|---|
| **建筑被"糊了一层绿"**（用户截图） | 地形 LOD 面与建筑**底座同高**（实测镇中心地形 `z=116.7` vs 建筑中位 `116.5`），粗 LOD 的三角形整片盖住房子。旧版同款 LOD 是**灰色无贴图**，所以看不出来；一上草地贴图就暴露 | **把小镇范围内（半径 150 m）的地形三角形裁掉**，镇内由基准地面承接（同材质草地 + 世界空间 UV）；镇外保留山体 |
| 建筑墙面出现**竖直拉伸的草地条纹** | three.js 的**程序缓存键不含 `onBeforeCompile`** ⇒ 打过补丁的"世界空间 UV"材质和普通 Lambert(带 map) **共用 program**，建筑也被用了世界 UV | 给补丁材质设 `customProgramCacheKey`（本例还会被地形裁洞掩盖，两者都要修） |

> 经验：**给一类材质注入自定义 shader 时，必须同时给 `customProgramCacheKey`**，否则会"污染"同类材质的程序缓存。

### 11.2 再加地形/道路之后踩的三个坑（2026-10-16 收尾）

| 现象 | 根因 | 修复 |
|---|---|---|
| 地面出现**白色带子**（用户截图）| 那是**道路 decal**（`val_03_road_d_*`，shader `standard_decal_blend_ground`）；而**导出时把贴图 alpha 丢了**（`decode_one` 末尾 `convert('RGB')`）⇒ 本该半透明混合到地面的路沿被当**不透明**画 | ① `decode_one` **保留 alpha**；② decal 材质 `transparent + alphaTest + polygonOffset` |
| **建筑地基悬空 / 埋进土**（用户截图）| 地形用**常量**基准校准（`off=+126.55`，全镇 2263 实体中位）⇒ 局部仍有 ±几米偏差 | 改**局部校准场**：`dz=z_实体−z_高度图` → 镇区 bbox 128² 网格 + 3 次 3×3 平滑 → 双线性插值加到每个地形顶点 ⇒ **地面必然穿过建筑底座** |
| `cpv_only` 网格是一块**灰方块** | 该 shader「colour per vertex only」**本身没有贴图**，颜色来自逐顶点 `COLOR0`；而本轮导出**没带 COLOR0** | 待修：导出带 `col` + 材质开 `vertexColors` |

> 地形本身用的是 **`heightmap.dat` 高度场**（512²，与旧版"贴合建筑"的那套一致），
> 不是游戏 LOD 瓦片（LOD 面与建筑底座同高，粗 LOD 会整片盖住房子）。

### 11.3 建筑材质接 PBR：法线 + ORM（2026-10-25）

> 结论：**以前建筑的 glTF 只写了 baseColor**，`roughness` 是常量 0.85、`metallic` 是 0、
> 没有法线也没有 AO ⇒ 圣丹尼斯"塑料廉价"。素材一直都在，是导出器只挑了 albedo。

`_ma`（`speculartex` / `materialA`）通道语义，**别再用后缀猜**：

| 通道 | 语义 | 出处 |
|---|---|---|
| R | Metallic | `tools/ref/Sollumz-RDR-main/ydr/shader_materials_RDR.py`（R→Metallic、G→Roughness、B×BaseColor 当 AO） |
| G | Roughness | 同上 |
| B | AO | 同上 |

glTF 要 **G=roughness / B=metallic**，AO 在 **R** ⇒ 打包成 **ORM** 图：
`ORM.R = _ma.B`、`ORM.G = _ma.G`、`ORM.B = _ma.R`，同一张图同时挂
`pbrMetallicRoughness.metallicRoughnessTexture` 与 `occlusionTexture`。

法线：`_nm` 是 **DirectX 约定（+Y 朝下）**，glTF/OpenGL 要 +Y 朝上 ⇒ **G 通道翻转**。

实测（553 张 `_ma` 分组均值）反过来验证了这三条：
metal R 104~230 / brass 205~255 / iron 113~222；木·砖·大理石 R≈0~2；
glass G=57（光滑）、marble G=98、brick G=197（粗糙）。

工程细节：
- `_nm` / `_orm` 存 **JPEG 4:4:4**（`subsampling=0`，否则法线 R/G 被色度下采样糊掉），ORM 上限 256²；
- PIL 对「ytd 切片 + split/merge」出来的图直接 `save()` 偶发 `broken data stream`，
  用 `Image.frombytes('RGB', size, tobytes())` 重建后再存；
- 查看器侧必须**跨分块去重贴图**：38 个 tile 各建一份 Texture ⇒ 显存 ×N，会随机 `Couldn't load texture`。

实现在 `tools/export_sdn_gltf.py`（`pick_tex` / `TexLib.get_normal` / `TexLib.get_orm` / `material_for`）。

### 11.4 模型库槽位三贴图（2026-10-30）—— Blender 侧也补上了

> §11.3 只解决了**圣丹尼斯网页 glTF**。Blender 大陆场景走的是另一条链
> （`assets/lib_native` 的 `.mdl` + `index.json`），那条链以前**每个子网格只存一个 texId**，
> 法线/高光在写库时就被丢掉了。本轮补全。

**为什么不改 `.mdl`**：`SUB` 记录是 7×u32（`texId, vCount, iCount, posOff, nrmOff, uvOff, idxOff`），
改格式要重写 10.3 GB 二进制 + 改所有读取器（`rdr2_mdl` / `relink_from_mdl` / `fix_ydd_textures` /
`blender_city_lod` …）。改成 **index 侧车**：

```jsonc
"models": {
  "0x10005d2e": {
    "f": "10/0x10005d2e.mdl",
    "b": [ /* bbox */ ],
    "s": [[1464, 21, 48]],        // 老字段：texId, vCount, iCount（**一个都没动**）
    "st": [[-1, -1]]              // 新字段：每槽 [normal_tid, ma_tid]，与 s 等长同序
  }
}
```

`tex` 表**只在末尾追加**（旧 id 保持有效）：新条目带 `role:"nm"|"ma"`、`gflip`、`w`、`h`。

**取图规则（`tools/tex_slots.py`）**：按 **albedo 所在图层**配对，不做跨层模糊匹配 ——

| albedo role | 法线 | 高光/材质 |
|---|---|---|
| `albedo_layerN`（地形） | `normal_layerN` → `normal` | `material_layerN` → `material` |
| `albedo`（standard） | `normal`/`bumptex` | `material`/`speculartex` |
| `albedo2`（第二层） | `normal2` → `normal` | `material2` → `materialA/B` |

> 注意：`export_sdn_gltf.ROLE_MATERIAL` **不含** `material_layerN` —— 地形（占网格大头）的 `_ma`
> 就是被这个列表漏掉的，别照抄那份常量。

**绑定校验**（`tools/extract_slot_textures.py --stage bind`，三条同时成立才写，否则留 `-1`）：
① 槽数一致；② 该槽 `vCount/iCount` 与 `s` 完全相等；③ 源 albedo 名字与库里该 texId 的名字一致。

**实测（2026-10-30）**：

| 项 | 数 |
|---|---|
| 有源文件、解析成功的模型 | 55,608 / 58,837 |
| 几何 + 名字双双对上的槽位 | 221,492 / 225,412（98.3%） |
| 已绑三贴图的槽位 | 212,207 |
| 新解出的贴图 | 14,843 张（`nm` 8,578 / `ma` 6,265），池 12,214 → 27,057 |
| 槽位覆盖 | 漫反射 97.73% / 法线 93.38% / 高光 91.28% |
| 实例加权覆盖 | 94.65% / 91.11% / 86.83% |
| 补不上的名字 | 法线 2,883 + 高光 4,718（**磁盘上任何 ytd 都没有**，不是解析问题） |

**Blender 节点图**（`tools/mat_rdr2.py`，构建与 relink 共用）：

```
TEX_IMAGE(albedo, sRGB) ──────────────────► BSDF.Base Color
TEX_IMAGE(_nm, Non-Color) ─► NORMAL_MAP ──► BSDF.Normal      （_nm 入池时已翻 G）
TEX_IMAGE(_ma, Non-Color) ─► SEPARATE_COLOR ─ Red ──► BSDF.Metallic
                                            └ Green ─► BSDF.Roughness
```

材质名 `alb_<albedo>__nm_<法线>__ma_<材质>`（超 60 字符退化成 `alb_<albedo>__<md5前10>`，
完整名字留在材质自定义属性 `albedo/normal/orm` 上）。Workbench 只有 `diffuse_color`，
所以**用 Workbench 看不到法线**，要看凹凸必须 Eevee/Cycles（`tools/render_material_ab.py`）。

---

**仍剩**：13 张找不到的贴图（`givemechecker`、`menu_ab`、`val_iw_wallpaper02`、`p_*` 等小道具/室内贴图，
所在字典尚未定位；现走 dominant 兜底）；`terrain_uber_4lyr` 的 **2 层混合遮罩通道**是经验取值（未从 `.sps` 反编译确认）。
