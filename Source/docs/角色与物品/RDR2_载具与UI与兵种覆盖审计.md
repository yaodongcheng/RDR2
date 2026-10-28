# RDR2 · 载具 / UI / 兵种 覆盖审计（2026-10-24）

> 起因：用户指出「马车上有机枪我没看到、轮船没看到、游戏里各种 UI 没看到、平克镇侦探兵种没看到」，
> 并追问「武器和兵种全都拿到模型和参数了吗」。
>
> 本文是这四类资产的逐项对账：**拿到什么、怎么拿的、缺什么、为什么缺**。
> 结论先放前面，证据在后面。

---

## 0. 一句话结论

| 类别 | 之前 | 现在 | 缺口 |
|---|---|---|---|
| **武器模型** | 289 文件 / 120 base | 同左，已核对 | 只有 5 个 base 没转 glTF（都是子弹/枪带等子件）；查看器只列了 45 把"装配好的"枪 |
| **武器参数** | 表里只有哈希 | MP 24 条有完整数值 | **SP 数值表没打通**：base `weapons.ymt` 142 条记录几乎全是默认值 |
| **载具（马车/船/火车）** | ❌ 完全没导 | ✅ **108 个模型 + 载具页** | 车体涂装色（carcols）未套用 |
| **UI** | ❌ 完全没导 | ✅ **1 922 张纹理 + 862 界面/控件 + 378 影片 + 20 布局** | `.gfx` 影片要 Scaleform 运行时才能播 |
| **兵种（gameplay ped）** | 只有过场角色 | ✅ 清单全 + 246 个过场 GLB + 平克顿可看 | **部件配方（PedComponentSetName）未解 → 兵种模型 0 个** |

---

## 1. 载具：`vehicles.rpf` 全量解出

### 1.1 源

```
packs_0.rpf
  └─ packs/base/levels/rdr3/vehicles.rpf   550 415 409 B / 663 项
       → raw/vehicles/out/                 662 个文件（1.8 GB）
           .yft  216（108 载具 × base/_hi 两档 LOD）
           .ytd  445
```

之前只有 `trolley01x` 和幽灵列车 4 节车厢被抽出来放进 Blender，**其余从没导过**，
所以查看器里看不到任何马车/船。

### 1.2 分类（108 个 base 载具，全部能解析出 drawable）

| 类别 | 数量 | 代表 |
|---|---|---|
| 马车 / 货运车 | **50** | `stagecoach001x…006x`、`coach2…6`、`cart01…08`、`wagon02x…06x`、`supplywagon`、`wagonprison01x` |
| 火车车厢 | **33** | `northsteamer01x`、`privatesteamer01x`、`wintersteamer`、`caboose01x`、各种 boxcar/flatcar/passenger/coalcar |
| 船 / 舰 | **18** | `ship_guama02`（最大）、`tugboat2`、`turbineboat`、`boatsteam02x`、`keelboat`、`horseboat`、`rowboat`、`canoe`、`pirogue`、`skiff`、`smuggler02` |
| **武器载具** | **5** | ★`policewagongatling01x`（车厢+加特林一体）、★`gatchuck`/`gatchuck_2`（炊事车+机枪）、`gatling_gun`、`gatlingmaxim02`、`breach_cannon`、`hotchkiss_cannon` |
| 有轨电车 | 1 | `trolley01x` |
| 飞行器 | 1 | `hotairballoon01` |

> **用户说的"马车上有机枪"= `policewagongatling01x`**（2.3 × 7.1 × 2.1 m，19 160 面，
> 车厢 + 转盘 + 加特林）。另有 `gatchuck`（炊事车底盘 + 机枪）。
> **"轮船"= `ship_guama02`**（17.6 × 78.6 × 29.2 m，270 386 面，桅杆/甲板/舱室齐全）。

### 1.3 产物

| 路径 | 内容 |
|---|---|
| `raw/vehicles/out/` | 662 个原始文件（yft + ytd） |
| `export/viewer/models/vehicles/` | **108 个 glTF + 353 张 PNG**（207 MB） |
| `export/vehicles/index.html` + `data.json` | 载具页（分类筛选 / 搜索 / 旋转 / 线框 / 面数尺寸） |
| `export/levels/world/vehicle_inventory.csv` | 216 行清单（含 _hi），面数/顶点/几何数/尺寸/字节 |
| `tools/build_vehicle_inventory.py` | 清单生成 |
| `tools/export_vehicle_gltf.py` | `.yft` → glTF（含涂装烘焙） |

### 1.4 两个必须知道的坑

1. **`.yft` 不是 `.ydr`**：fragment 头里 drawable 指针在 +0x20/+0x08/+0x40… 之一，
   要先探测（`export_vehicle_gltf.find_drawable_base`），不能直接套 `load_model()`。
2. **车体 albedo 是 `*_control` 不是 albedo**：载具车体走 `standard_vehicle_2lyr`，
   `lyr0diffusetex` 取到 `policeWagon01x_Body_control`，实测均色 RGB(127,121,22)，
   直接当颜色渲染就是一片**荧光黄绿**。真正车漆色来自 `tintpalettetex`
   （`Generic_skinned_pal`）+ `carcols.ymt` / `carvariations.ymt`。
   现在用「控制图亮度 × 中性深灰漆」烘焙（`PaintTexLib`），**看起来像素色车，但不等于真实配色**。

---

## 2. UI：`textures/ui_textures.rpf` + Scaleform 全解

### 2.1 源

| 包 | 内容 |
|---|---|
| `textures_0.rpf → textures/ui_textures.rpf` | 16 个 UI 纹理字典（7.3 MB） |
| `common_0.rpf → data/ui/**` | HUD 布局 XML、配色、字体映射（20 个文件） |
| `data_0.rpf → data/cdimages/scaleform_*.rpf` | HUD/小地图/暂停菜单的 Scaleform 影片 + 自带图集 |
| `data_0.rpf → data/ui/screens.rpf` / `widgets.rpf` | 界面与控件的定义（461 / 401 个 .ymt） |

### 2.2 纹理（1 922 张解出，1 959 行清单）

| 字典 | 张数 | 内容 |
|---|---|---|
| `inventory_items` | **803** | 背包/商器物图标 |
| `satchel_textures` | **326** | 背包界面 |
| `blips` | **321** | ★地图/雷达图标（商店、任务、动物、武器、帮派…） |
| `swatches_gunsmith` | 107 | 枪匠木料/金属配色票 |
| `multiwheel_weapons` | **64** | ★武器轮盘图标 |
| `menu_textures` | 63 | 菜单九宫格/滚动条/按钮底 |
| `shaving_menu` | 50 | 理发界面 |
| `generic_textures` | 40 | 通用底图/网格 |
| `itemtype_textures` | 28 | 物品类型徽标 |
| `minigames_hud` | 20 | 小游戏 HUD |
| `scoretimer_textures` / `honor_display` / `scoreboard_textures` / `document_textures` / `feeds` / `credits` | 4~11 | 计时 / 荣誉条 / 记分板 / 通缉令等文档 / 消息条 / 片尾 |
| Scaleform 自带图集（7 个） | 76 | HUD 准星、小地图 v2、按键提示、全屏警告、枪管、暂停菜单 |

### 2.3 关键突破：**第二种 .ytd 布局**

`blips / menu_textures / inventory_items / satchel_textures / honor_display /
shaving_menu / swatches_gunsmith` 这 7 个字典**此前一律解出 0 张**。

根因不是压缩、不是权限，而是这些 `.ytd` 的 struct 是**指针数组**：
`body + 某个偏移` 处是一串 u64 指针（`0x50000000|off`），指向各自的纹理结构体；
而原解析器只认「内联条目、步长 0xB0」。结构体字段本身完全一样
（+0x18 W/H、+0x1C fmt、+0x28 名称 ptr、+0x38 gfx ptr）。

修法：`rdr2_ytd.Ytd.textures_ptr_array()` + `textures_any()`（先内联、再指针数组）。
这一条把 0 → 1 922。

### 2.4 界面 / 控件 / 影片 / 布局清单

| 项 | 数量 | 说明 |
|---|---|---|
| 界面 `screens.rpf` | **461** | `pause_*`、`sidemenus/shops/*`、`sidemenus/player_menu/*`、`mp/character_creator_*` … |
| 控件 `widgets.rpf` | **401** | `hud/attribute_status_meters`、`hud/quick_select/wheels/weapon_wheels/*`、`scoreboard/*` … |
| Scaleform 影片 `.gfx` | **378** | `hudmanager`、`pausemenu_assets`、`minimap_v2`、`hud_reticle`、`font_lib_*` … |
| HUD 布局 / 配置 | **20** | `screens/hud/hud_persistent.xml`（节点树：PanelNode/GridNode…）、`colors.xml`、`fontmap.xml`、`gps.xml` … |

> `.gfx` 是 Scaleform（Flash 字节码），**要在本地播放需要 Scaleform 运行时**。
> 所以这里给的是完整清单 + 与它们配套的图集纹理，不冒充"还原了界面"。
> `screens.rpf` / `widgets.rpf` 里的 .ymt 带签名保护（`[skip] signature protected`），
> 只能列出名字，内容没解。

### 2.5 产物

| 路径 | 内容 |
|---|---|
| `export/ui/textures/<字典>/*.png` | 1 922 张 PNG |
| `export/ui/index.html` + `data.json` | UI 页（纹理画廊 + 界面/控件/影片/布局四张清单 + 搜索） |
| `export/levels/world/ui_textures.csv` | 1 959 行（字典 / 名称 / W×H / 格式 / PNG 路径 / 状态） |
| `tools/extract_ui_textures.py` | 解码落盘 |
| `tools/build_ui_page.py` | 页面数据 |

---

## 3. 兵种：清单全了，模型 0 个（配方未解）

### 3.1 兵种到底是怎么来的

```
metapeds.rpf（1086 个 <archetype>.ymt）      ← 一个兵种一个文件：骨骼偏移/表情/变体
metapeds.ymt（PSIN，CPedModelInfo 1271 条）  ← 每个兵种一条：Name / Pedtype / **PedComponentSetName**
部件池（3653 个 .ydd：uppr_* / lowr_* / vest_* / boot_* / head_* / hair_* …）
```

**"这个兵种长什么样"= `PedComponentSetName` 指向的部件集**。
这一层还没解通（部件集定义的位置/索引链没打通），所以：

- 能解：1086 个兵种的**名字、类别、55 骨偏移、表情集、变体表**
- 不能解：**穿哪几件** → 导不出该兵种的整只模型

### 3.2 各路径都试过（避免重复踩）

| 尝试 | 结果 |
|---|---|
| `metapeds.ymt` 里找部件资产哈希 | ❌ 0 命中（用 names.txt 29.4 万条反查） |
| `assets_drawable.ymt`（2.5 MB / 12 034 个资产）找部件名 | ❌ 只有 30 个噪声命中 |
| 每兵种 `<archetype>.ymt` 当配方解 | ❌ 用 CodeWalker `PsoFile` 解出 schema：字段是 `name/scale/Float×N/eAnimBoneTag/expressions/variations`，**是骨骼偏移，不是衣服** |
| 部件池按槽位随机拼 | ✅ 能拼出**结构完整**的人物，但衣服是随机的 → 只能当管线样本，不能当兵种还原 |

### 3.3 平克顿侦探（用户点名）

| 项 | 状态 |
|---|---|
| archetype | `s_m_m_pinlaw_01`（全库只有这 1 个平克顿兵种） |
| 骨骼/表情/变体 | ✅ `raw/ped_meta/s_m_m_pinlaw_01.ymt`（17.8 KB，55 骨） |
| 穿着配方 | ❌ 未解 |
| 过场版 | `cs_pinkertongoon`（模型只有上半身：头 + 马甲 + 手 + 头发）→ 已导出 GLB |
| 拼出的完整人物 | `export/npc/units/cs_pinkertongoon_full/`：**平克顿真实马甲/头发/头 + 通用手臂/裤/靴**，明确标注哪几件是补齐的 |

> 不画像、不随便拼一套就叫它"平克顿"——那样只会误导下游。

### 3.4 产物

| 路径 | 内容 |
|---|---|
| `export/units/index.html` + `data.json` | 兵种页（1086 行清单 + 平克顿专区 + 渲染图） |
| `export/levels/world/ped_coverage.csv` | 1086 行：archetype / 类别 / 骨骼 ymt 大小 / 有无过场 GLB / 有无兵种模型 |
| `raw/npc/list_metapeds.txt` | metapeds.rpf 全清单 |
| `tools/build_units_page.py` | 生成清单与页面数据 |
| `export/npc/units/*` | 拼装样本 GLB（含 `cs_pinkertongoon_full`） |

---

## 4. 武器：模型全，参数没打通

### 4.1 模型

| 项 | 值 |
|---|---|
| `export/weapons/models/` | 289 个模型文件（287 ydr + 1 ydd + 1 yft）+ 224 张 ytd |
| 唯一 base（剥掉 `_grip/_mag/_barrel/_sight/_wrap/_clip/_stock`） | **120 个 `w_*`** |
| 已转 glTF | 286 个（含部件件） |
| **没有 glTF 的 base** | **5 个**：`w_repeater_cloth_strap01`、`w_repeater_winchester01_bullet`、`w_rifle`、`w_rifle_rollingblock02`、`w_shotgun_doublebarrel02` |
| 查看器里"装配好"可看的 | 45 把（把 `_grip` 等部件剔重后的列表） |

> 所以"武器模型全不全"→ **基本全**（120 个 base，只有 5 个子件级 base 没转）。
> 但**查看器只列了 45 把**，剩下的是"有模型、没进列表"。

### 4.2 参数

| 表 | 状态 |
|---|---|
| `CWeaponInfo.csv`（142 行） | ⚠️ 只有 `Name` 一列有值，且是**哈希**；数值列全空 |
| 哈希能否反查 | ❌ `names.txt` 不含武器名；joaat 试遍 `weapon_*` / `WEAPON_*` 都不匹配 → 这一列**不是武器名哈希**，是错抽 |
| `weapons_mp.csv` | ✅ **24 条**真实数值（爆头距离、伤害衰减曲线、精度衰减、锁定距离） |
| SP `weapons.ymt` | 用新写的 PSO 导出器（`tools/pso_xml`）解出：`CWeaponInfo` 142 条 × 2768 B，schema 118 字段齐全，但**两条记录之间只差 4 个字段**（Name / 一个 hash / 一个 hash / 2 个 float）→ base 包里是**模板/默认值**，真实数值在嵌套 `CWeaponInfoBlob`（需指针解析）或 update 覆盖包 |
| `update_4.rpf → x64/packs/base/data/ai/weapons.ymt` | 与 base 同一个文件（638 912 B，逐字段一致） |

**下一步（没做）**：给 `tools/pso_xml` 加数组/指针解析（`PsoDataType.Array` 的
`(offset,count)` + `ReferenceKey` → 子结构），把 `CWeaponInfo → CWeaponInfoBlob` 展开，
才能拿到每把枪的伤害/射速/散布。

---

## 5. 新增工具（都在 `tools/`）

| 脚本 | 作用 |
|---|---|
| `build_vehicle_inventory.py` | 载具清单（面数/尺寸/分类） |
| `export_vehicle_gltf.py` | `.yft` → glTF + 涂装烘焙（`PaintTexLib`） |
| `build_vehicles_page.py` | 载具页数据（中文名表在文件里，可继续补） |
| `extract_ui_textures.py` | UI 纹理 → PNG + 清单 |
| `build_ui_page.py` | UI 页数据（纹理 + 界面/控件/影片/布局） |
| `build_units_page.py` | 兵种覆盖清单 + 页面数据 |
| `build_weapon_audit.py` | 武器/弹药/载具武器 参数表对账 |
| `pso_xml/` | **通用 PSIN(.ymt) 结构 + 数据导出器**（CodeWalker `PsoFile`），解武器/兵种 ymt 就靠它 |

---

## 6. 复现

```bash
cd "D:/BrainMaker/大镖客2解包分析"
RP=tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe
G=H:/EPICGAMES/RedDeadRedemption2

# 载具
$RP extract "$G/packs_0.rpf" raw/vehicles "packs/base/levels/rdr3/vehicles.rpf"
$RP extract raw/vehicles/packs/base/levels/rdr3/vehicles.rpf raw/vehicles/out ""
uv run python tools/build_vehicle_inventory.py
uv run python tools/export_vehicle_gltf.py --all
uv run python tools/build_vehicles_page.py

# UI
$RP extract "$G/textures_0.rpf" raw/ui "textures/ui_textures.rpf"
$RP extract raw/ui/textures/ui_textures.rpf raw/ui/out ""
$RP extract "$G/common_0.rpf" raw/ui/layout "data/ui"
uv run python tools/extract_ui_textures.py
uv run python tools/build_ui_page.py

# 兵种
$RP list raw/npc/meta/packs/base/data/metapeds/metapeds.rpf > raw/npc/list_metapeds.txt
uv run python tools/build_units_page.py

# 武器参数审计
uv run python tools/build_weapon_audit.py
# 通用 ymt 导出器
dotnet build tools/pso_xml/pso_xml.csproj -c Release
tools/pso_xml/bin/Release/net9.0/pso_xml.exe <in.ymt> <out.txt>
```
