# 圣丹尼斯（Saint Denis）地编破解 —— 整城 + 室内 → Blender

> 2026-10-18。承接 `README_进度总结.md` §5/§8：**three.js 装不下整城（485 MB / 2200 万三角）**，
> 本轮改为**面向 Blender 的高保真导出**，并把此前缺的两块补上：
> **① 共享贴图（315 张缺失的根因）② 30 个室内 MLO 包**。
>
> 交付：`export/levels/world/blender/sdn.blend`（1.4 GB）+ `sdn_report.html`（图文报告）。

---

## 0. 一句话结论

**圣丹尼斯可以完整搬进 Blender**：城市 **2 275** 个实例 + 街道道具 **660** 个实例、2 324 个独立 ydr、
2 410 万顶点 / 1 963 万三角、2 192+ 张贴图，外加 **30 个室内包（27 个已按 MLO 实体原位落进建筑）**。
在 `sdn.blend` 里能自由飞行、逐栋查看，街面能读出 **Saint Denis Banking** 招牌。

---

## 1. 之前为什么"显示不了 / 显示不全"

| 现象 | 根因 | 本轮修法 |
|---|---|---|
| three.js 只能看 8~13 块 | 整城 485 MB，WebGL 内存上限 | **换载体**：glTF → Blender（单场景 1.4 GB 无压力） |
| 屋顶偏暗、墙面发紫 | 贴图模糊匹配把 `_nm`（法线图）当 albedo | **只允许 albedo 后缀**（`_ab/_abal/_al/...`）；法线图均值≈(128,128,255) 就是那层紫 |
| 315 张贴图"缺失" | 城市贴图有**全局词典**，不在 area 包里 | 抽 `levels/rdr3/gtxd/gtxd_saintdenis.rpf`（1.1 GB）与 `gtxd_saintdenis_int.rpf`；缺失 315 → **124** |
| 建筑丢 233 个 | 旧管线"没贴图就整模型丢弃" | 无图也导出（灰模），**实例 1 788 → 2 275** |
| 装饰细节糊 | 旧管线按 0.25 m 焊接顶点 | **不焊接**；0.02~0.06 m 级装饰全部保留 |
| 整片街区被白色板糊住 | `_slod` LOD、`default` shader 占位网格混进来了 | 剔除 `_slod`/VFX/阴影代理；`default`+`givemechecker` 判为占位，**跳过 340 个** |
| 电线像大白板 | `cable` shader 用 `givemechecker` 占位贴图 | cable 走深色材质 |

---

## 2. 数据来源

```
城市模型   levels_2.rpf → levels/rdr3/area/nopq_15_18/new_*.rpf（61 包）
           → 2 733 ydr / 887 ytd / 3.4 GB    （work/sdn/models）
城市贴图   levels_2.rpf → levels/rdr3/gtxd/gtxd_saintdenis.rpf（189 项 / 1.1 GB）
室内模型   levels_3.rpf → levels/rdr3/interiors/new_*_int.rpf（30 包）
室内贴图   levels_2.rpf → levels/rdr3/gtxd/gtxd_saintdenis_int.rpf
摆放       export/levels/map_metadata/**/*.ymap（4 163 张）
```

> ⚠️ 注意 rpf 归属：`interiors/*` 与 `props/areas/p_new_01.rpf` 在 **levels_3.rpf**，
> 而 `area/nopq_15_18/*` 在 **levels_2.rpf**。按包名在 `work/terrain/list_levels_*.txt` 里查归属，别硬编码。

---

## 3. 关键格式点（ydr → glTF）

| 项 | 结论 |
|---|---|
| 几何 | 只取 `+0x50` 的 **high LOD**；每个 geom 一个 primitive（各自材质） |
| 位置 | `VertexDeclarationG9` 元素 0，`R32G32B32_FLOAT`（SOA 平面数组） |
| **法线** | 元素 4，格式 **`R10G10B10A2_UNORM`**：`n = v/1023*2-1`（缺了它就是死平面） |
| UV | 元素 28 `TEXCOORD0`；RDR2 是 OpenGL 底左原点 ⇒ **glTF 里写 `1-v`**，Blender 导入后与游戏一致 |
| 坐标 | RDR2 = **Z-up**；glTF = Y-up ⇒ **根节点挂 −90° X 旋转**，子节点保留原始 T/R/S（实例四元数直接可用） |
| 实例 | `[name,x,y,z,qx,qy,qz,qw,sxy,sxy,sz]`（RDR2 的 scaleXY/scaleZ 语义） |
| 占位 | `shader == default` 且贴图 `givemechecker` ⇒ 游戏内不渲染的代理网格，跳过 |
| 变体 | 同位置 `_em_hd/_dec/_dc/_d` 只留基名，避免一栋楼画两三遍 |

---

## 4. 室内（MLO）怎么落位

1. 室内包里的 `.ydr` **全部建模在 MLO 局部坐标**（银行：X −15.7~8.1 / Y −4.7~21.3 / Z −2.8~4.6）。
2. 摆放来自 ymap 里 **archetype == 包名** 的实体（如 `new_com_bank_int` @ `2643.7, −1293.3, 51.2`）。
3. ⇒ 「把包内所有网格挂在同一个 MLO 变换下」就自动落进对应建筑。

结果：

| 状态 | 数量 | 说明 |
|---|---|---|
| 城内、已原位落位 | **27** | 银行/枪店/杂货/药房/剧场/酒店三层/警局/理发/裁缝/电车库… |
| 城外或 ymap 无位置 | 3 | `new_gang01_int`（帮派窝点在城外）、`new_saloon01_int`、`new_tailor01_int` |

> ⚠️ 这是「整包平铺」，**没有**做 MLO 的门/传送门与房间可见性裁剪。
> 站在建筑外面时室内被外壳挡住（符合预期）；要单独看就隐藏 `Scene Collection`。

---

## 5. 覆盖度

zone 多边形内（不是包围盒）按 ytyp 包围盒筛「建筑类」实体（z≥3 m、占地≥30 m²、体积>100 m³）：

| 指标 | 值 |
|---|---|
| zone 内实体 | 24 090 |
| 建筑类 | 3 016 |
| 命中已解包模型 | 1 677（55.6%） |
| 未命中的 1 339 | **全部是 names.txt 里查不到的匿名 hash**，包围盒 200~1900 m（水体/LOD/地形体积），**不是建筑** |

⇒ **城市建筑本体基本全在**。

街道小物件（`p_*` 路灯/围栏/报刊亭/垃圾）已从 `levels/rdr3/props/areas/p_new_01.rpf`
抽出 **179 个 ydr / 660 个实例**（`sdn_props/`，16 块 / 13.6 MB），并入 Blender 的 `Props` 集合。

---

## 5.5 地面层重建（2026-10-18 第二轮）

**用户反馈**：地面支离破碎、看不到水/山/桥、边界一刀切。

**根因**：
1. 旧地形是 **8 m 网格纯色板**（只用了 H4 高程），城市地面模型（240 个 `*_rds` + 79 个 `*_ground*`）
   合计只有 **55.6 万 m²**，而城区约 120 万 m² ⇒ 中间大片露出底色 = "碎了"
2. 游戏里城市地形是**挖空**的（地形颜色图里城市区域全黑），地面由建筑地面模型接管；
   我们既没有地形颜色，也没有水，所以只剩一块灰绿板
3. 水体只有 `mapzones.meta` 的粗多边形，之前完全没生成

**做法**：
| 层 | 数据 | 说明 |
|---|---|---|
| 地形颜色 | `levels/rdr3/terrain/<area>/<tile>_.rpf` 里 `<tile>_t`（2048²，sRGB） | 抽 20 个瓦片（n..r × 13..16）→ 拼 **4096² 区域贴图**（0.5 m/px）；草地/沼泽/农田/沙滩/河床都是游戏原色 |
| 地形高度 | `H4.npy`（4 m 真高程） | 4 m 网格 51.3 万三角；城市多边形内压低 0.35 m（防 z-fighting） |
| 水体 | `mapzones.meta` 的 RIVER/LAKE/CREEK/POND/SWAMP/OCEAN | Chaikin 平滑 → 与「地形 < 水位」求交 → 2 m 水面网格（56.8 万顶点 / 55.3 万面，水位 40.4 m，等高线收边），水下地形再压低 0.45 m |
| 城市 | `StDenis` 官方多边形 | 颜色图上城市黑区补"路面石"色；**不再按城市多边形整体去水**（港区地形 37 m 本就在水位下，去水会把船搁浅） |
| 边界 | 区域 `x 1536~3584 / y −2560~0`（2.0 × 2.6 km） | 城四周留 500 m+，不再看到切边 |

**产物**：
```
export/levels/world/blender/terrain/
├─ sdn_ground.png    4096² 区域地面颜色（20 个瓦片拼合 + 亮度归一化）
└─ sdn_ground.json   区域范围 / 瓦片摆放（朝向由 patch UV 拟合确定：u→+x, v→−y）
tools/build_sdn_terrain_tex.py   拼地面颜色
tools/blender_rebuild_ground.py  重建地形 + 水面（在已有 sdn.blend 上原地替换）
```

**2026-10-18 第三轮修正（细长沙洲楔形）**：
现象：港区口等位置有细长、直边的沙洲尖刺，而且不止一处。
根因：水面是**用 `mapzones` 多边形裁出来的**——多边形只有 4~6 个点，直边压过低洼地形时，
边内是水、边外是露出的河床 ⇒ 沿直边形成长条楔形。
修法：**不再用多边形裁水**，改为「地形低于水位即水面」——`LEVEL = 40.4 m`，
同一区域内低于 40.4 m 的地形全部灌水，岸线完全由**等高线**决定；水下地形再压低 0.45 m。
代价：水域按 2 m 网格占 **43.3%**，西侧 Bayou 连成大片水面（游戏里那里本就是湿地）；
好处是岸线不再是直边，细长楔形彻底消失。

**2026-10-18 第二轮修正（船只搁浅）**：
第一版为了"保护码头"把 StDenis 多边形内的水整块删了，结果港区（地形 37 m）变成干地，船全部搁在沙洲上。
现已去掉这条硬剔除，只保留「地形高于水位」的裁剪 ⇒ 港区/运河恢复水面。
实测 121 个船/舰实例全部落在水位以下（`terrain > 41` 的船 = **0**）。

**已知限制**：
- `mapzones` 的水体多边形只有 4~6 个点（河岸一条边 200~600 m），所以水面是"贴着低地裁过的粗轮廓"，
  不是逐米河岸线；要做准需要解 **`waterheight.dat`（magic `RTAW`，192² 头 + 复杂数据）**，本轮没啃下来。
- 地形贴图是 **每瓦片一张 2048² 颜色图**拼的，瓦片之间有轻微亮度接缝（已做中位数归一化）。
- 建筑立面上的**贴花 billboard**（海报/招牌）在没有 alpha 裁切时会浮在墙外。

---

## 5.6 水面高度可调（2026-10-18 第四轮）

用户反馈"有些游戏里有水的地方被我做成了浅滩"，而且"游戏里不同区域水平面通常是定值"。
因此把水位做成**参数**：

```bash
# 直接改水位（单位 m），并出 2 张预览图
blender -b export/levels/world/blender/sdn.blend -P tools/blender_rebuild_ground.py --     --water-level 41.8 --gate 20 --views overview,top --res 1600x900
```

或者双击 `调水面.bat`，按提示输入水位（回车用默认）。

| 参数 | 含义 | 参考值 |
|---|---|---|
| `--water-level` | **水面绝对高程**（m）。地形低于它即水面，岸线由等高线决定 | 40.0 低 / **41.8 默认** / 42.5 高 |
| `--gate` | 水域范围门外扩格数（2 m/格），决定水最多能离开官方水体多边形多远 | 默认 20（40 m） |

### 5.6.1 Blender 里实时调（推荐）

水面现在**不再是一块"按水位烘好的网格"**，而是**一整块平面**（`Water`，2.6×3.2 km）放在 `z = 水位`。
地形天然把这块平面"切"出岸线 ⇒ 改 z 就是改水位，**立刻生效，不用重建**。

平面上挂了自定义属性 + 驱动器：

1. 选中 `Water`
2. 右侧 **物体属性 → 自定义属性（Custom Properties）→ `water_level`**
3. 拖动数值（35~50，软范围 38~46），水面实时升降

> 如果拖动没反应（某些机器禁用了驱动器），右键该属性 → **删除驱动器（Delete Driver）**，
> 然后直接改 **物体属性 → 变换 → 位置 Z** 即可，效果一样。

### 5.6.2 命令行/批处理重建（可选）

**实测水位—水域占比**（2 m 网格，区域 2.0×2.6 km）：

| 水位 | 水域占比 | 观感 |
|---|---|---|
| 40.4 | 43% | 港区/河口会露出成片浅滩（用户指的那块） |
| **41.8** | **58%** | 港区、东岸、湾汊都有水；城区（≥44.4 m）保持干燥 |
| 42.5 | 60~66% | 更"满"，但西北农田低洼处也会进水 |

> 关键约束：**城区核心地形 p5 = 44.4 m**，所以水位只要 ≤ 43 就不会淹到城里；
> 而港区河床 35~40 m、东岸浅滩 40~42.5 m —— 要盖住东岸浅滩就得把水位抬到 ~42。

---

## 5.7 天空与自然光（2026-10-18 第五轮）

用户反馈"天空灰暗"。原因：世界只有一个纯色 Background（0.42,0.55,0.75 / 0.8），
且视口在用材质的 studio HDRI，所以永远是灰底。

改成：

| 项 | 做法 | 当前值 |
|---|---|---|
| 天空 | `ShaderNodeTexSky`（Blender 5.x 的 **MULTIPLE_SCATTERING**，即 Nishita 后继） | 太阳高度 30° / 方位 200°，气溶胶 1.0 |
| 环境强度 | Background Strength | 0.22 |
| 太阳 | Sun 灯，方向与天空太阳一致（`rotation=(90-elev, 0, rot-90)`） | 强度 4.6，色温偏暖 (1.0,0.95,0.88) |
| 色彩管理 | AgX + Punchy + 曝光 −0.1（以前是 Standard，容易死白） | — |
| 视口 | 所有工作区 `shading.use_scene_world = True` | 材质预览也能看到天空 |

> ⚠️ 踩坑：给世界加 Volume（空气透视）会让 EEVEE 整幅压黑，已移除；需要空气透视请用 Mist 通道后期加。

工具：`tools/blender_setup_sky.py`（可调 `--elevation/--rotation/--strength/--sun-energy`）。

---

## 5.8 地面贴花层级修复（方案 B，2026-10-18 第六轮）

**症状**：街面上一块块深色/灰色补丁叠在石板上，像"贴错层"；转视角时还会闪。

**根因**（查文件得到）：
1. 147 个贴花面片用 **BLEND / HASHED**，BLEND 不写深度 ⇒ 相互重叠时排序错乱；
2. 642 个贴花材质里有 **72 个没有贴图**（导出时的回退材质），还有一批**贴图没接 Alpha** ⇒ alpha=1，整片实心盖住地面；
3. 贴花离路面只有几毫米 ⇒ 与路面 z-fighting。

**做法（方案 B）**：`tools/fix_decal_materials.py`
| 步骤 | 数量 |
|---|---|
| 补上 `Image.Alpha → Principled.Alpha` 连线 | 561 个材质 |
| 全部改成 **HASHED（抖动透明，写深度，无排序问题）** | 642 个材质 |
| 删除完全没有贴图的"灰面板"贴花 | 12 个对象 |
| 贴花整体抬高 2 cm，消除与路面 z-fighting | 283 个对象 |

> 试过把 alpha 二值化（Greater Than 0.5）做硬裁剪，但会在屋檐/边缘出现白色锯齿，已回退为 alpha hashed。

**验证**：同一机位 before/after 像素差 mean 1.34（6.9% 像素变化），地面无闪面；剩余的褐色斑块经"隐藏全部贴花"对比确认**不是贴花**，而是地形颜色图里游戏自带的泥土着色（若要抹掉需方案 C：把贴花/泥地烘进地形贴图）。

## 5.9 材质 PBR 化：法线 + 高光/粗糙（2026-10-25 第七轮）

**触发**：用户反馈"圣丹尼斯看起来很塑料廉价"。

### 5.9.1 审计结论：**法线图与高光图从来没导出过**

| 检查项 | 实际值 |
|---|---|
| `export/previews/sdn/tiles/*.gltf`（38 块） | 4719 个材质 |
| `baseColorTexture` | 4310 |
| `normalTexture` | **0** |
| `metallicRoughnessTexture` | **0** |
| `occlusionTexture` | **0** |
| `roughnessFactor` | **4705 个全是 0.85 常量** |
| `metallicFactor` | **4719 个全是 0.00 常量** |
| 导出贴图 1825 张 | 全是 albedo（`_ab` 1210 / `_al` 280 / `_abal` 225…），且只有 **192²** |

**素材并不缺**：`new_com_04_600.ydr` 实测 22 个 shader，每个都带
slot 4 `bumptex → xxx_nm`、slot 5 `speculartex → xxx_ma`。
根因是 `export_sdn_gltf.py` 只按 role 挑了 albedo，其余**全部丢弃**，
roughness/metallic 退化成全局常量 ⇒ 平板几何 + 常量粗糙度 = 塑料。

### 5.9.2 `_ma` 的通道语义（已定死，别再猜）

| 通道 | 含义 | 依据 |
|---|---|---|
| **R** | **Metallic** | `tools/ref/Sollumz-RDR-main/ydr/shader_materials_RDR.py`（R→Metallic, G→Roughness, B×BaseColor 当 AO） |
| **G** | **Roughness** | 同上 |
| **B** | **AO** | 同上 |

实测统计与之一致（553 张 `_ma` 分组均值）：
metal R均值 104~230、brass 205~255、iron 113~222；木/砖/大理石/花岗岩 R≈0~2；
glass G=57（光滑）、marble G=98、brick G=197（粗糙）。

### 5.9.3 改了什么

1. `tools/export_sdn_gltf.py`
   - 按 shader role 取 `_nm` / `_ma`（`ROLE_NORMAL` / `ROLE_MATERIAL`，跳过 `blank_*` 占位）；
   - `_nm` → `normalTexture`，**G 通道翻转**（RDR2 是 DirectX 约定，glTF/OpenGL 要 +Y 朝上）；
   - `_ma` → 打包 **ORM**（R=AO、G=roughness、B=metallic）同时挂 `metallicRoughnessTexture` + `occlusionTexture`；
   - `_nm`/`_orm` 存 **JPEG 4:4:4**（subsampling=0，法线 R/G 不能被色度下采样），ORM 上限 **256²**；
   - 没有 `_ma` 的材质按名称兜底（glass 0.16 / metal 0.75+0.42），不再全城 0.85。
2. `export/previews/index.html`
   - **加 PMREM 环境光**（程序生成等距柱状天空，不联网）：原本只有半球光+平行光，
     MeshStandardMaterial 没有可反射环境 ⇒ 镜面反射≈0，材质再准也像塑料；
   - **跨分块材质/贴图去重**：38 个 tile 各自 load 同一张 png → 各自建 Texture ⇒ 显存按块数翻倍，
     加贴图后直接出现随机 `Couldn't load texture`。改为按 `image` 对象在首次渲染前去重 + 材质按名复用；
   - 光照再平衡：`hemi 1.15 → 0.25`、`envMapIntensity 0.45`、`exposure 1.0`
     （IBL 叠上去后砖墙从砖红变粉白，A/C 两个机位比出来的值）。

### 5.9.4 结果

| 指标 | 之前 | 现在 |
|---|---|---|
| 材质带法线 | 0 | **3811** |
| 材质带 ORM | 0 | **3447** |
| albedo 分辨率 | 192² | **512²** |
| 贴图文件 | 1825（全 albedo） | 1826 albedo + **1281 法线** + **1071 ORM** |
| 预览体积 | 1.14 GB | 1.75 GB |
| 贴图报错 | — | 0 |

对比图：`deliverable/materials/sdn_material_before_after.jpg`（远景 A 机位 + 近景 C 机位，同机位前后）。

### 5.9.5 踩坑

| 现象 | 根因 | 修法 |
|---|---|---|
| `OSError: broken data stream when writing image file` | PIL 对 ytd 切片 + split/merge 出来的图直接 save 偶发失败 | `Image.frombytes('RGB', size, tobytes())` 重建后再存，并 try/except 不中断 10 分钟导出 |
| 随机 `Couldn't load texture` | 38 个 tile 各建一份 Texture，显存 ×N | 首次渲染前按 image 去重 + dispose 重复 Texture |
| 加 IBL 后砖墙变粉白 | 半球光 + 平行光 + 环境三重叠加，ACES 把高光压成灰白 | hemi 0.25 / env 0.45，并给出 `?env=&hemi=&exp=` 调参口 |

### 5.9.6 还没做

- `deliverable/blender/sdn.blend`（2.23 GB）里的材质仍是旧的（只有 baseColor），
  要生效必须用新 glTF 重跑 `tools/blender_assemble_sdn.py`；
- 其余 42 个据点用的还是 192² + 无法线（同一套 `export_sdn_gltf.py`，重跑即可）。

---

## 6. 交付物

```
export/levels/world/gltf/sdn/
├─ tiles/c<k0>_<k1>.gltf + .bin   30 块 / 843 MB / 不焊接 / 带法线
├─ textures/*.png                 2 192 张（城市 + 室内）
└─ missing_textures.json          124 个缺图（门/绳/落叶等小件）

export/levels/world/gltf/sdn_props/
├─ tiles/                     16 块 / 13.6 MB（179 个 ydr / 660 实例：路灯/围栏/报刊亭/垃圾）
└─ textures/                  55 张

export/levels/world/gltf/sdn_interiors/
├─ <interior>.gltf + .bin         27 个城内室内（已按 MLO 位置摆放）
├─ unplaced/                      3 个无位置/城外
└─ manifest.json                  室内名 → 位置/网格数/顶点数

export/levels/world/blender/
├─ sdn.blend                      1.4 GB：Scene Collection(城市) + Interiors + Terrain
├─ shots/                         overview / top / north / street / landmark / canal
├─ interiors/*.png                27 张室内单图
├─ interiors_sheet.png            室内目录（4×7）
└─ sdn_report.html                ⭐ 图文报告（双击即开）
```

工具：

| 脚本 | 作用 |
|---|---|
| `tools/export_sdn_gltf.py` | ydr → 高保真 glTF（不焊接 / 法线 / 全分辨率贴图 / 分块） |
| `tools/export_sdn_interiors.py` | 30 个室内包 → glTF，并按 MLO 实体落位 |
| `tools/blender_assemble_sdn.py` | 拼场景（城市 + 室内 + 地形）、存 .blend、出图 |
| `tools/blender_render_blend.py` | 打开 .blend 反复调机位出图 |
| `tools/blender_render_interiors.py` | 逐个室内出图（目录用） |
| `tools/audit_sdn_coverage.py` / `resolve_missing.py` | 覆盖度审计：实体 vs 模型、未命中 hash 反查名字 |

---

## 7. 复现

```bash
cd D:/BrainMaker/大镖客2解包分析

# 城市模型（幂等，已有可跳过）
bash work/sdn_extract.sh
# 共享贴图
RP=tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe
$RP extract H:/EPICGAMES/RedDeadRedemption2/levels_2.rpf work/sdn/gtxd levels/rdr3/gtxd/gtxd_saintdenis.rpf
$RP extract work/sdn/gtxd/levels/rdr3/gtxd/gtxd_saintdenis.rpf work/sdn/gtxd/txd ""
$RP extract H:/EPICGAMES/RedDeadRedemption2/levels_2.rpf work/sdn/gtxd levels/rdr3/gtxd/gtxd_saintdenis_int.rpf
$RP extract work/sdn/gtxd/levels/rdr3/gtxd/gtxd_saintdenis_int.rpf work/sdn/gtxd/txd_int ""

# glTF
uv run python tools/export_sdn_gltf.py --cx 2555 --cy -1151 --r 620 --chunk 160 --maxs 512 \
    --out export/levels/world/gltf/sdn

# 室内（先把 30 个包解到 work/sdn/int/<name>/）
uv run python tools/export_sdn_interiors.py

# Blender
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b -P tools/blender_assemble_sdn.py -- --views overview,top
```

---

## 8. 下一步（未做）

- [ ] 室内 MLO 的门/房间可见性（真正的"进门"体验），需要解 `ytyp` 的 `CMloArchetypeDef.rooms/portals`
- [ ] 道路贴花与 `standard_dirt` 的 albedo2 混合（现在只取 albedo，地面偏单一）
- [ ] 把 glTF 分块换成一个 `.blend` 的 collection 实例化（Link Duplicate）以压缩体积
- [x] ~~建筑只取 albedo、没有法线/高光~~ → 2026-10-25 已修（§5.9），但 **sdn.blend 未重新装配**
- [ ] 其余 42 个据点按同一套（法线 + ORM + 512²）重导
