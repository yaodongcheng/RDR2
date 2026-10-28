# RDR2 · 武器/道具模型 & 剧本对白

> 回答两个问题：
> 1）武器和道具的模型都有了吗？
> 2）具体的剧本对白能拿到吗？

---

## 0. 直接回答

| 问题 | 结论 | 数量 |
|---|---|---|
| **武器模型** | ✅ **有了，已全部导出** | **289 个模型**（287 `.ydr` + 1 `.ydd` + 1 `.yft`）+ **224 张贴图**，174 个唯一 base |
| **道具模型** | 🟡 **主要道具包已导出，但不是"全部 props"** | **2,071 个模型 + 884 张贴图**（10 个 prop 包，2,955 个文件） |
| **剧本对白** | ✅ **全部中文对白都在**，并能按任务/音频库拆开 | **339,635 条**（中文 153,830 条）；其中 **302 个任务音频库 99,532 条** |

---

## 1. 武器模型：289 个模型 + 224 张贴图

### 1.1 从哪来

```
packs_1.rpf → packs/base/models/weapons.rpf  （86 MB）
  → 已导出到 export/weapons/models/（205 MB）
```

### 1.2 数量

| 类型 | 数量 |
|---|---|
| `.ydr` 模型 | **287** |
| `.ydd` 模型 | 1 |
| `.yft` 模型 | 1 |
| `.ytd` 贴图 | **224** |
| 合计文件 | **513** |
| 唯一 base | **174** |

### 1.3 分类（按 base 名）

| 类别 | 唯一 base |
|---|---|
| 霰弹枪 | 35 |
| 步枪 | 29 |
| 连发步枪 | 25 |
| 左轮手枪 | 18 |
| 手枪 | 17 |
| 近战 | 16 |
| 特殊 | 6 |
| 其他（大号弓/投掷/望远镜/相机等） | 28 |

> 清单：`export/levels/world/weapon_models.csv`（文件 / base / 类别 / model-or-texture）。
> 模型文件：`export/weapons/models/`。

### 1.4-b（2026-10-21 补充）贴图其实能拿到：`standard_weapon_2lyr` 的参数烘焙

之前写"武器没有单张 albedo，颜色来自 palette/tint"是**只看到了表象**。真正的机制是
（见 `tools/weapon_tint.py` 顶部注释的 slot 对照表）：

| slot | 参数 | 枪身（金属） | 枪托/护木（木料） |
|---|---|---|---|
| 0 | `tintpalettetex` | `w_repeater_carbine01_pal`（256×16，**整张均匀洋红 = 占位**） | — |
| 1 | `lyr0diffusetex` | `w_blank_ab`（4×4 纯白） | `w_stock1_tintControl`（遮罩图） |
| 4 | `lyr1diffusetex` | `w_rust01_ab`（**真色**，锈蚀层） | `w_woodDamge01_ab`（**真色**，木纹/磨损） |
| 7 | `controltexturetex` | `w_repeater_carbine01_ct`（层混合权重） | `w_stock_blank_ct` |
| 9 | `engravingtexturetex` | `w_repeater_carbine01_eg`（蚀刻遮罩） | `w_repeater_carbine01_stock_eg` |
| 10 | `albedopalettetex` | `givemechecker` | **`weapon_tint_wood`（木纹渐变 LUT）** |

两张关键结论：

1. **木料**：颜色 = `weapon_tint_wood` 按 mesh UV0 采样（直接是木纹），再乘 `lyr1`（木料磨损）做细节；
2. **金属**：这批资产里 `tintpalette` 是纯白占位，实际颜色 = `lyr0`(白) × `lerp(lyr0, lyr1(锈), control)`。

> 另一个"找不到贴图"的直接原因：`ytd_to_png.decode_one()` 用 `Image.frombytes('BGRA', …)`，
> PIL 没有这个模式，**调色板纹理一读就崩**，被上层 try 吞掉后就成了"没有调色板"。已修。

烘焙做法：在 **UV 空间**画一张 512² 图逐像素合成 → 写进 glTF 的 `baseColorTexture`，
法线继续用原来的 `_NM`。实现在 `tools/weapon_tint.py` + `tools/export_weapon_tint.py`，
105 个武器 glTF 全部重导（`export/viewer/models/weapons/`）。

### 1.4 ⚠️ 长枪是"拼装"的：为什么查看器里"没有枪托"

**现象**：查看器里步枪/连发枪/霰弹枪只有枪管 + 机匣，枪托那一截是空的（左轮、手枪正常）。

**根因**（2026-10-21 查清，不是解包漏了）：

RDR2 的武器在游戏里由**主体 + 部件**拼出来，主体 ydr 里**本来就没有木质件**：

| 文件 | 内容 | 实测量 |
|---|---|---|
| `w_repeater_carbine01.ydr` | 金属件：枪管 + 机匣 + 扳机/杠杆 | 2 个 geometry，x∈[−0.311, 0.560]，**x∈[−0.24,−0.08] 完全没有顶点**（就是枪托那一截） |
| `w_repeater_carbine01_grip1.ydr` | **木质枪托 + 护木**（grip1/2/3 只是三套木纹） | 3,369 顶点，x∈[−0.301, 0.368] |
| `_sight1` / `_clip1` / `_wrap1` / `_barrel1` | 准星、弹仓、布缠、枪管替换件 | 小件 / 外观件 |

旁证：`w_repeater_carbine01.ytd` 里有一张 `w_repeater_carbine01_stock_eg` + `weapon_tint_wood`
——贴图都留着"木头"那一套，说明模型确实有木质件，只是不在主体文件里。

左轮手枪是例外：握把就在主体里（`_grip1..5` 是象牙/珍珠等替换样式），所以看起来是完整的。

**修法**：`tools/export_weapon_assembled.py` —— 按游戏内部的部件系统，把
`主体 + grip1（木托/护木）`（必要时再加 `barrel1`）合并成一个 glTF 再导出。

装配判定规则（写在脚本注释里，可复查）：

| 部件 | 装不装 | 依据 |
|---|---|---|
| `grip1` | ✅ 长枪必装 | 不装就没有枪托/护木 |
| `barrel1` | ⚠️ 仅在"主体缺管"时装 | 判据：`barrel1.max_x − 主体.max_x > 0.12 m`；只有双管霰弹枪命中（主体到 0.277，管到 0.571），其余霰弹枪/手枪的 barrelN 是"更长/更短"的替换件，装了会穿模 |
| `stock1/2/3` | ❌ | 削短霰弹枪的可选枪托，默认是改装件 |
| `sight1/2`、`clip1..3`、`mag1..3` | ❌ | 改装件，主体已有默认那套，装了重复 |
| `wrap1..6` | ❌ | 布/皮革缠绕，纯外观 |

**结果**：45 把可预览武器里 **14 把完成装配**（13 把长枪 + 1 把手枪），清单见
`export/levels/world/weapon_assembly.csv`；`site.json` 的每条武器多了 `parts` / `parts_zh`，
查看器 HUD 会显示"部件：木托/护木（+ 枪管）"。

**重跑**：

```bash
python tools/export_weapon_assembled.py         # 覆盖 export/viewer/models/weapons/<base>.gltf
python tools/patch_viewer_weapon_parts.py       # 把部件信息写回 site.json
```


### 1.4-c（2026-10-21 晚）三处补正

1. **工具类（望远镜/相机/套索）以前是纯白**：它们走的是 `standard` / `standard_alpha` / `standard_looking_glass_tube`，
   不是 `standard_weapon_2lyr`。这些 shader 有现成的 `diffusetex`，烘焙时补上这条分支后就能直接采样；
   法线也改从 `bumptex` 取。
2. **左轮/手枪"缺枪管"**：主体只到枪管座，`barrel01`/`barrel1` 是真枪管。装配规则改成
   "左轮/手枪一律补最短枪管（barrel1 / barrel01），长枪仍只在主体真缺管时补"。
   现在 `w_revolver_cattleman01` 部件 = 木托/护木 + barrel01。
3. **列表里混进部件**：`w_shotgun_doublebarrel01_mag1` 这类被当成一把枪重复列了 3 次同名"双管霰弹枪"。
   `tools/patch_viewer_weapon_parts.py` 现在会剔掉 `_grip/_mag/_barrel/_sight/...` 结尾的条目，并把同名不同枪加后缀区分
   （45 → **43 把**）。

> 还有一个小坑：贴图文件名是"参数组合的哈希"，公式改了但文件名不变，
> `save_tex` 原来 "存在就跳过" → 旧白图被沿用。已改成**无条件覆盖**。

---

## 2. 道具模型：10 个 prop 包，2,071 个模型

### 2.1 从哪来

```
levels_3.rpf → levels/rdr3/props/...
  → 已导出到 export/items/models/<包名>/
```

### 2.2 已导出的包

| 包 | 类别 | 文件 | 模型 | 贴图 |
|---|---|---|---|---|
| `s_pickups` | 地面拾取物 | 652 | 432 | 220 |
| `s_cards` | 香烟卡 | 503 | 495 | 8 |
| `p_food` | 食物 | 486 | 334 | 152 |
| `int_lootable` | 可搜刮物 | 325 | 187 | 138 |
| `p_hunting` | 狩猎/皮毛 | 309 | 176 | 133 |
| `p_store` | 商店道具 | 277 | 188 | 89 |
| `p_drink` | 酒水 | 173 | 114 | 59 |
| `p_plant` | 植物/草药 | 108 | 57 | 51 |
| `int_doctor_office` | 医疗用品 | 73 | 50 | 23 |
| `p_valuable` | 贵重物品 | 49 | 38 | 11 |
| **合计** | | **2,955** | **2,071** | **884** |

> 清单：`export/levels/world/item_models.csv`（包 / 类别 / 文件 / base / model-or-texture）。
> 模型文件：`export/items/models/`。

### 2.3 "都有了吗"——诚实回答

**没有"全部"**。目前导出的是**道具相关的主 prop 包**（贵重、食物、拾取、搜刮、草药、狩猎、酒水、医疗、商店、卡片）。
以下**还没导**：

- `p_household` / `p_kitchen` / `p_storage` / `p_camp` / `p_furniture` —— 家具、容器、营地物件；
- `p_sign` / `p_door` / `p_fence` —— 场景 props，不是"道具"；
- `p_horse` / 马具、车辆 props。

另外，**`catalog_sp.ymt` 的 item → model 映射还没走通**（见上一轮报告），
所以现在是"按 prop 包全量导出"，**不能保证每个 catalog 道具都精确对上它的模型**。

---

## 3. 剧本对白：339,635 条，全部可读

### 3.1 全量

| 指标 | 数量 |
|---|---|
| `.yldb` 文件 | **1,929** |
| 对白条数 | **339,635** |
| 含中文条数 | **153,830** |

> 源文件：`export/story/dialogue_chinesesimp.txt`（16 MB）。

### 3.2 按文件类型分

| 类型 | 文件 | 条数 | 说明 |
|---|---|---|---|
| **任务音频库**（`*aud.yldb`） | **302** | **49,290**（清洗后） | 原始 99,532 行含二进制噪声，已过滤为纯中文台词 |
| 环境路人（`*_a_*`） | 321 | 25,873 | 街头/营地闲聊 |
| 通用 ped（`*_s_*`） | 119 | 10,034 | 通用语音 |
| 专属服务 NPC（`*_u_*`） | 53 | 7,414 | 店主/医生/警长 |
| 其他（`g_*`、角色名等） | 1,134 | 196,782 | 帮派、角色专属、系统提示 |

### 3.3 按任务拆开

已生成：`export/story/mission_dialogue/`

| 项 | 数量 |
|---|---|
| 匹配到 `missions.meta` 的任务 | **129 个音频库** |
| 其中主线任务 | **94 / 105** |
| 其中支线/赏金 | **33 / 121** |
| 未匹配的音频库 | **173 个**（导出到 `_unmatched/`，仍可读） |
| 导出行数 | **49,290**（纯中文台词） |

文件格式：

```
export/story/mission_dialogue/BRT1.txt
# BRT1 | CHAPTER_3 | bank: brt1aud.yldb
~z~肖恩，你回来了！
...
```

索引：`export/levels/world/mission_dialogue_index.csv`（任务 / 章节 / 音频库 / 条数 / 中文条数）。

### 3.4 能拿到什么、拿不到什么

**能拿到：**

- 每条对白的**中文原文**；
- 它属于**哪个音频库**（任务 `brt1aud`、角色 `cs_dutch`、服务 NPC `valdoctor` 等）；
- 按任务/角色/服务 NPC **分组导出**。

**拿不到：**

- **逐行说话人标签**：`*aud.yldb` 是任务音频库，一个文件里有多人台词，但没有"这行是谁说的"字段；
  要精确到每行，需要音频时间轴/字幕轨道（目前没解）。
- **任务步骤/分支对齐**：哪句对白属于哪个 objective、哪个分支，在 `.ysc` 里；`.ysc` 仍是 0。
- **演出指令**：镜头、动作、表情在过场 ycd 里，不在对白文本里。

> 一句话：**对白原文 100% 有；"谁在哪个任务步骤说这句"还差 `.ysc` + 音频时间轴。**

---

## 4. 产物

| 文件 | 内容 |
|---|---|
| `export/weapons/models/` | **513 个武器资产**（289 模型 + 224 贴图，205 MB） |
| `export/items/models/` | **2,955 个道具资产**（2,071 模型 + 884 贴图，936 MB），10 个包 |
| `export/levels/world/weapon_models.csv` | 武器模型清单 |
| `export/levels/world/item_models.csv` | 道具模型清单 |
| `export/story/mission_dialogue/` | 129 个任务 + 173 个未匹配音频库的对白文本（2.8 MB） |
| `export/levels/world/mission_dialogue_index.csv` | 任务对白索引 |
| `export/story/dialogue_chinesesimp.txt` | 全量对白 339,635 条 |

### 复现

```bash
cd "D:/BrainMaker/大镖客2解包分析"
RP=tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe
G=H:/EPICGAMES/RedDeadRedemption2

# 武器模型
$RP extract "$G/packs_1.rpf" work/weapons "packs/base/models/weapons.rpf"
$RP extract work/weapons/packs/base/models/weapons.rpf export/weapons/models ""

# 道具模型（以 p_valuable / s_pickups 为例）
$RP extract "$G/levels_3.rpf" work/items/props "levels/rdr3/props/generic/p_valuable.rpf"
$RP extract work/items/props/levels/rdr3/props/generic/p_valuable.rpf export/items/models/p_valuable ""

# 清单 + 对白
python tools/build_model_inventory.py
python tools/build_dialogue_export.py
```

---

## 5. 一句话总结

> **武器模型：全了**（289 模型 + 224 贴图）。
> **道具模型：主要 10 个包全导了**（2,071 模型），但家具/容器/场景 props 未导，且 catalog 的道具→模型映射还没走通。
> **剧本对白：全部中文对白都在**（339,635 条），任务音频库 99,532 条已按任务拆开；
> 但"逐行说话人 + 任务步骤对齐"还差 `.ysc` 和音频时间轴。
