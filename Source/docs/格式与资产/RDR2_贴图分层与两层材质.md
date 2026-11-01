# RDR2 贴图分层与两层材质（`standard_2lyr` / `standard_dirt`）

> 2026-11-01 立。解决的是「码头、墙体、地面在 Blender 里整块发黑 / 只出一层」。
> 规则真身：`tools/tex_slots.py`（取图）、`tools/mat_rdr2.py`（节点图）、
> `tools/extract_slot_textures.py`（抽取与索引）。

---

## 一、结论（先看这段）

| # | 结论 |
|---|---|
| 1 | **整块发黑的主因不是"只导了第一层"，是贴图池里的 PNG 被缩图缩黑了** —— PIL 12 对 RGBA 图做 `resize` 是**按 alpha 预乘**的重采样，alpha 稀疏的贴图 RGB 会被乘暗（实测 0.30 → 0.069）。修法 = `ytd_to_png.resize_max()`：**RGB 与 alpha 分开缩**。 |
| 2 | 第二个主因才是分层：`standard_2lyr*` 有 **第 0 层 + 第 1 层 + 控制图**，旧管线只取第 0 层。 |
| 3 | 混合公式：`颜色 = mix(lyr0, lyr1, w)`，**w 越大越靠第 1 层**。 |
| 4 | w 从哪来：有 `controltexturetex` 就用它（**取方差最大的通道**，不写死 R）；没有控制图就用第 1 层自己的 **alpha**（`_abal` 的约定）。两样都没有 → 保持单层。 |
| 5 | `tintpalettetex` 目前**只抽取、不参与材质**：实测码头那张 256×4 调色板是「绿/青/白」渐变条，直接乘上去会把木头染绿；它的语义（要配合逐顶点 COLOR0 选择子）还没验证。 |
| 6 | `dirtdiffusetex` 只记录 id，不参与混合：没有可靠的逐顶点权重（那是 `COLOR0.A` 的事，见 §五）。 |

---

## 二、票位（slot）与角色对照

`tools/rdr2_shader_params.py` 的 `ROLE` 表就是这一节的代码版。

### `standard_2lyr` / `standard_2lyr_pxm` / `*_ground`

| slot | 参数名 | 角色 | 用途 |
|---|---|---|---|
| 0 | `tintpalettetex` | `palette` | 调色板（256×4，**内嵌在 .ydr 体内**） |
| 1–4 | `lyr0diffusetex` / `lyr0normaltex` / `lyr0materialatex` / `lyr0materialbtex` | `albedo` / `normal` / `materialA` / `materialB` | 第 0 层 |
| 5–8 | `lyr1diffusetex` / `lyr1normaltex` / `lyr1materialatex` / `lyr1materialbtex` | `albedo2` / `normal2` / `materialA2` / `materialB2` | 第 1 层 |
| 9 | `dirtdiffusetex` | `albedo_dirt` | 土/污渍层 |
| 10 | `controltexturetex` | `control` | **混合权重** |
| 11 | `aotexturetex` | — | 实测 80% 是 `blank_white` |

### `standard_dirt`（没有控制图）

`diffusetex`（第 0 层）+ `diffusetex2`（第 1 层，名字多为 `*_abal`）+ `bumptex` + `speculartex`。
`_abal` = **albedo + alpha**，alpha 就是第 1 层的混合权重。

---

## 三、混合权重怎么定（含实测依据）

`tools/tex_slots.py:mask_channel()` 在解码时算一次，结果写进 `index.json` 的 `tex[i]["ch"]`
（`-1` = 四通道全平，不能当遮罩）：

| 情况 | 实测例子 | 取哪个通道 |
|---|---|---|
| 专用 `_ct`（灰度） | `p_lumbera_ct`：R=G=B（相关系数 1.000） | 三通道等价，取方差最大的即可 |
| 复用 `_mb` 当控制图 | `nbx_ground_grass_bay_lsuh_mb`：R 恒 1.000、G 恒 0.525、**B 在 0.09~1.0 之间变** | **B**（方差最大） |
| 同一张图换成 alpha | `nbx_basketweave01_mb`：B 在变、A 也在变 | 谁方差大用谁 |
| 第 1 层是 `_abal` | `nbx_dirt_moss_02dark_abal`：alpha 0~0.89 | **alpha**（`ch=3`） |

**方向为什么是"w 大 → 第 1 层"**：
* 资产命名：控制图直接叫 `nbx_ground_grass_bay_lsuh_mb`（第 1 层是草地 `..._ab`），
  草/土这种二选一的场景里，这类图的语义只能是"第 1 层的遮罩"；
* 社区实现 Sollumz-RDR `ydr/shader_materials_RDR.py::RDR_create_2lyr_shader`：
  `diff_lyr_mix` 的 Fac 来自控制分支，Color2 = `lyr1diffusetex`。

**谁不是权重**：逐顶点 `COLOR1`（Sollumz 里叫 `Color 2`）和 control 贴图**互不相关**
（实测相关系数 < 0.4）—— 说明它们是两条独立通道，本轮只做贴图这一条。

---

## 四、数据落在哪

`assets/lib_native/index.json`（不碰 `.mdl`，几何二进制一个字节都不改）：

```jsonc
"models": {
  "0x3c588f25": {
    "s":   [[3858, 728, 2040], ...],          // 原有：每槽 [texId, vCount, iCount]
    "st":  [[15094, 23293], ...],             // 2026-10-30：每槽 [法线, ORM]
    "lyr": [[3909, -1, 10124, -1, -1], ...]   // 2026-11-01：每槽 [l1, ctrl, dirt, nrm2, ma2]
  }
}
"tex": [
  {"id": 40123, "n": "p_lumbera_ct", "f": "tex/40123.png", "role": "ct", "ch": 0, "w": 512, "h": 256}
]
```

规则：
* `lyr` 与 `s`/`st` **等长同序**，`-1` = 没有；老模型没有 `lyr` → 走单层，行为不变。
* 角色：`l1`（第 1 层 albedo）/ `ct`（控制图）/ `dt`（土）/ `nm2` / `ma2` / `pl`（调色板）。
* **`l1/ct/dt/pl` 存 RGBA**（alpha 可能是遮罩），`nm/nm2` 存 RGB 且 G 已翻转，`ma/ma2` 存 RGB。

### 覆盖（2026-11-01 实测，`python tools/audit_two_layers.py`）

| 指标 | 数 |
|---|---|
| 全库源模型 / 解析成功 | 68,744 / 68,744 |
| 带 `lyr` 的模型 | **7,984**（槽位 21,870） |
| 其中真有混合权重 | 6,965 个模型 |
| 权重来源（槽位） | `l1.alpha` 8,602 · `ctrl.R` 4,300 · `ctrl.G` 3,150 · `ctrl.B` 968 · `ctrl.A` 358 · 无 4,073 |
| 调色板进池 | 9,147 张（**不参与材质**） |
| 引用的贴图 id → PNG | 全部命中（审计会报缺） |

`control` 取不到图的只有 25 个 SDN 槽（`nbx_wall_woodplank_14long_ct` 不在已解包的任何 `.ytd` 里），退回单层、不报错。


---

## 五、还没做的（写在这里防止有人重踩）

| 项 | 现状 | 要做之前先确认 |
|---|---|---|
| `tintpalettetex` 调色 | 抽了、没用 | 它是 256×4 的 LUT，选择子来自逐顶点 `COLOR0`（`tintpaletteselector` CBuffer 默认 (0,0)）。直接整张乘上去会把码头木板染绿 —— 必须先解出选择子。 |
| 逐顶点混合权重（`COLOR1.R`） | 没读、没进 `.mdl` | 社区实现用它的 R 通道当混合因子。要用就得给 `.mdl` 加一条逐顶点属性（格式升版本），并重导几何。 |
| `dirtdiffusetex` 混合 | 只记 id | 权重在逐顶点 `COLOR0.A`（Sollumz 的 `vertex_color1_node.Alpha`），同样要动 `.mdl`。 |
| 法线/ORM 分层混合 | 已接（两层的 `_nm`/`_ma` 按同一 w 混） | 第 1 层没有法线的模型自动退回单层法线。 |

---

## 六、怎么验收 / 怎么 A/B

```powershell
# 单块重建（两层开，默认）
Set-Location "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source"
cmd /c 'tools\run.cmd D:\BrainMaker\大镖客2解包分析\_logs\region_20_lyr.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --python tools\_unbuffer.py -P tools\blender_continent.py -- --out "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions\20_wild2000_05_02.blend" --lib "D:\BrainMaker\大镖客2解包分析\assets\lib_native" --only-tile wild2000_05_02 --step 8 --rails --full --no-water'
```

* **关掉两层做 A/B**：命令里加 `--lyr off`（材质回到 2026-11-01 之前的单层）。
* 已存盘的 blend 想换材质（不重建几何）：
  `-P tools\relink_materials.py -- --lyr on|off`。
* 材质自带两个自定义属性可查：`layer1`（第 1 层贴图名）、`layer_mix`（权重来源，
  例如 `ctrl.B:nbx_ground_grass_bay_lsuh_mb` 或 `l1.alpha:nbx_dirt_moss_02dark_abal`）。

---

## 七、贴图池刷新（修「缩图缩黑」）

```powershell
# 只统计会变多少张
python "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source\tools\refresh_tex_pool.py" --dry
# 真刷（同名同路径覆盖，tex id 不变）
python "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source\tools\refresh_tex_pool.py" --jobs 12
```

判定口径：两边都缩到 32×32 比平均绝对差，`> 0.02` 或尺寸不同就重写。
2026-11-01 首次全量：32,878 张里 **3,348 张被改写**（10.2%，全部是带 alpha 的非方形贴图）。

---

## 八、验收记录（2026-11-01）

| 项 | 结果 |
|---|---|
| 单模型 A/B（`new_boats_02_lumberpile` / `new_18_ter_a_02` / `new_pie_03_dockmed3`） | 材质属性 `layer_mix` 分别报 `ctrl.R:` / `ctrl.B:` / `ctrl.alpha:`；草地图"两层开"是绿草 + 灰石庭院，"关"是整片土色 |
| 区域 #20 重建（**已落到官方路径** `deliverable\blender\regions\20_wild2000_05_02.blend`，旧版回退在 `_scratch\two_layer\region20_prev.blend`） | `VERIFY ENTITIES ... PASS` · `_check_region.py` **PASS**（18 类逐项一致）；4,378 个材质里 **1,356 个（31%）带两层** |
| 圣丹尼斯码头同机位 A/B（`≈2543, -1570, 46`） | 旧的木桩区是一片褐色糊；新的能看到一根根木桩与板缝 |
| 文件体积 | 旧 955 MB → 新 959 MB（两层**不显著**增加体积） |

复现图的命令（Blender 5.2，`-b` + EEVEE）：

```powershell
Set-Location "H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source"
cmd /c 'tools\run.cmd D:\BrainMaker\大镖客2解包分析\_logs\shot_dock_new.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b "D:\BrainMaker\大镖客2解包分析\deliverable\blender\regions\20_wild2000_05_02.blend" --python tools\_unbuffer.py -P "D:\BrainMaker\大镖客2解包分析\_scratch\two_layer\probe_region_shot.py" -- --at 2543 -1570 46 --radius 110 --out "D:\BrainMaker\大镖客2解包分析\_scratch\two_layer\region" --tag sdn_dock_new'
```

> 🔴 探针产物放**项目自己的** `大镖客2解包分析\_scratch\<主题>\`，不许放 `D:\BrainMaker\` 根
> （2026-11-01 用户裁定：那是多项目共用的根，见 `docs/AGENTS.md` §1.9）。
