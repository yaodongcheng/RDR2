# 荒野大镖客 2 · 解包分析

> 🔴 **最高原则（必读，优先级高于本文所有内容）**：`docs/最高原则_单一管线与分块即裁剪.md`
> 单一管线 · 分块即裁剪 · **五条绝对禁令**（禁擅自剔模型 / 禁擅自改地形 / 禁猜贴图 / 禁丢原名 / 禁伪造环境数据）
>
> 📋 **当前未完成**：`docs/TODO.md`（开头即"现在卡在哪"）
> 🤖 **工作准则**：`docs/AGENTS.md`（长任务必须后台+轮询、禁开大文件验证、已知坑）

> 从游戏资产解包 → 全大陆 3D 重建（Blender）→ 网页预览 → 剧情 / 任务 / 角色数据整理。
> 本文是**唯一入口**：有什么、在哪、怎么用、还缺什么。
> 最后更新：**2026-10-29**（§0 已整体替换为当日状态；更早的 10-26/27/28 记录见 `docs/交接与状态/`）。

---

## 〇、文件在哪（2026-10-28 起，**先读这一节**）

**文本层的真身 = 骑砍2 mod 的 git 仓库；D 盘这边是指回去的联接。两份是同一份文件，不存在"改哪份"的问题。**

```
H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source\
├─ docs\         69 篇 md ＋ 60 张证据图（图只在磁盘上，不进 git）
├─ tools\        2,880 个文件（333 个 .py / 29 个 .cs / names.txt / csproj…）
├─ launchers\    3 个启动 bat（GBK 编码，靠 .gitattributes 的 -text 原样保存）
├─ README.md     本文件
└─ .gitignore    只收文本：md py cs csproj sln html js mjs css json csv cmd bat ps1 toml txt
                  （.gitattributes 同目录：*.bat / *.cmd / *.ps1 一律 -text，禁换行转换）

D:\BrainMaker\大镖客2解包分析\
├─ README.md     → 符号链接，指向 Source\README.md（这里改不了内容，改的是真身）
├─ AGENTS.md     → **路标**（普通文件，仅 3 行：「规则真身 = docs\AGENTS.md」；不含规则）
├─ docs          → junction → Source\docs
├─ tools         → junction → Source\tools
├─ export\ deliverable\ assets\ raw\ archive\ …   原地不动（都是二进制/可重建）
└─ 打开*.bat ×3  符号链接 → Source\launchers\（已实测 `%~dp0` 解析的是链接所在目录，
                 所以照旧在数据根双击即可，脚本本身一行没改）
```

- **路径照旧**：100+ 个脚本里写死的 `D:/BrainMaker/大镖客2解包分析/tools` 仍然解析到同一份文件。
- **远端**：`https://github.com/yaodongcheng/RDR2.git`（分支 `main` = 文本；`assets` 分支 = 资源快照）。
- **故障恢复**：`git clone` 之后代码与文档就在 `Modules\RDR2\Source\`；数据面按
  `docs/交接与状态/GIT_入库清单.md` §4 的"恢复方式"列重跑。
- **换机器重建 D 盘侧链接**（clone 只会得到普通文件，链接要自己建；PowerShell，路径按实际改）：

  ```powershell
  $S = "H:\...\Modules\RDR2\Source"; $D = "D:\BrainMaker\大镖客2解包分析"
  New-Item -ItemType Junction     -Path "$D\docs"  -Target "$S\docs"
  New-Item -ItemType Junction     -Path "$D\tools" -Target "$S\tools"
  New-Item -ItemType SymbolicLink -Path "$D\README.md" -Target "$S\README.md"
  foreach ($f in @('打开查看器.bat','打开大陆_流畅.bat','打开夏洛蒂家_完整.bat')) {
      New-Item -ItemType SymbolicLink -Path "$D\$f" -Target "$S\launchers\$f" }
  ```

  另外在 D 盘根放一个**几行的 `AGENTS.md` 路标**（内容只有「规则真身 = `docs\AGENTS.md`，布局 = `README.md`」）——
  让落在数据根目录的 agent 能自动找到规则。**路标里不许写规则**（写了就与 `docs\AGENTS.md` 分叉）。
- **四条根文档搬进 docs 了**：`docs/AGENTS.md`、`docs/TODO.md`、`docs/STRUCTURE.md`、
  `docs/README_骑砍2交接.md`（D 盘根目录只留一个 README 路标）。

### 〇.1 新文档 / 新脚本放哪 —— **只有一处能动**（接手 Agent 必读）

**判据一句话：文本进 `Source\`（= git 仓库），二进制留在 D 盘原位。**
写在 `Source\` 以外 = **不进 git = 出事就没了**（D 盘那几棵大树没有任何版本管理）。

| 你要新增的东西 | 放哪 | 说明 |
|---|---|---|
| 文档 / 笔记 / 结论 / 交接 | `Source\docs\<主题>\` | 五类主题目录已存在；交接类进 `docs\交接与状态\` |
| Python / C# 脚本 | `Source\tools\` | 脚本之间靠 `import 模块名`，**不要另建一套目录** |
| 启动器 bat | `Source\launchers\` | 再在 D 盘根建同名**符号链接**；`%~dp0` 解析成数据根，脚本不用改 |
| 数据产物（glb / blend / png / 贴图 / 导出） | D 盘原位 `export\ deliverable\ assets\ raw\` | 不进 git，靠"能重跑"恢复 |
| 一次性探针 / 临时脚本 | `Source\tools\`（想留）或 D 盘任意子目录（不想留） | **别放 D 盘根** |

**三条硬规矩：**

1. **禁止在 D 盘根新建 `.md`** —— 那里只有一个 `README.md` 符号链接，新建的文件不进 git。
2. **新扩展名要先进白名单** —— `Source\.gitignore` 是**白名单制**（`*` 全排除，再按扩展名放行）。
   你写了个 `.yaml` / `.xml` 进去，它**不会进库**；要收就自己在「② 只放行文本」段加一行 `!*.yaml`。
3. **图片不进 git** —— docs 下 60 张证据图只在磁盘上；md 里引用它们没问题，但别指望 clone 能拿回图。

**从 D 盘看**：`D:\...\docs\` 和 `D:\...\tools\` 是 junction，
往里写 = **直接写进 git 仓库**（`git status` 立刻能看到），不需要再复制到别处。

### 〇.2 这次架构改了什么（2026-10-28）

**改之前**：`docs/`、`tools/`、根目录 5 篇 md、3 个启动 bat **全都在 D 盘，没有任何版本管理**
（原计划是「在 `D:\...\` 原地 `git init`」，那份 SOP 还没执行就作废了）。二进制也在 D 盘。

**改之后**：

| 内容 | 现在放哪 | 版本管理 |
|---|---|---|
| 文本层（docs / tools / 根文档 / 启动器） | `Modules\RDR2\Source\` | ✅ git 主分支 |
| 场景与世界数据（`scene.xscene` / `ModuleData`） | `Modules\RDR2\` | ✅ git 主分支 |
| 地形等大二进制（`*.bin` / `*.tpac`） | 本机 + 仓库 `assets` 分支快照 | ⚠️ **只存当前一份**（每次上传整个替换） |
| 数据面（`export` 15.9 GB / `deliverable` 20 GB / `assets` 10.5 GB / `raw` 108 GB） | D 盘原位不动 | ❌ 靠"能重跑"恢复 |

D 盘侧只剩**链接**（`docs` / `tools` = junction，`README.md` / 3 个 bat = 符号链接），
所以 100+ 个把 `D:/.../tools` 写成常量的脚本**一行没改**。

**为什么不是「在 D 盘原地 git init」**（三条理由）：

1. **只能有一个仓库** —— 两份文本必然漂移；junction 让"改哪份"这个问题根本不存在。
2. **绝对路径不能断** —— 脚本里写死 `D:/BrainMaker/大镖客2解包分析/tools`，搬家必须留联接，正好一并解决版本管理。
3. **仓库跟着 mod 走** —— 换机器 / 重装系统，`git clone` 一个仓库就把"能复现这套管线的东西"全拿回来。

> 🔴 **`docs/交接与状态/GIT_搬运_SOP.md` 的「§3 执行」已作废** —— 它按"在 D 盘原地 `git init`"写的，
> **现在不要再在 D 盘执行 `git init`**（`docs` / `tools` 是联接，在 D 盘建仓只会得到空目录或顺联接爬进去）。
> 那份 SOP 里**仍然有效**的只有三样：白名单思路（附录 B.1）、体积闸门阈值（§4：350~700 文件 / <250 MB / 单文件 <50 MB）、
> 异常决策树（§5）。

---

## 0. 当前状态（2026-10-29）

### 0.1 唯一主产物

| 文件 | 大小 | 内容 |
|---|---|---|
| `deliverable/blender/continent/continent_v9.blend` | 7.32 GB | 对象 **147,500** / `ENTITIES` **103,898** / 隐藏 **43,599**（`HIDDEN_TERRAIN_CELL` 30,549 + `HIDDEN_VEG` 10,860 + `HIDDEN_LOD` 2,186 + `HIDDEN_PARKED` 4） |
| 同目录 `manifest.json` / `manifest_continent_v9.json` / `.jsonl` | 30.7 MB | 对象级清单：名/hash/分类/位置/bbox/**贴图名**/隐藏标记；贴图用 **6,967** 种，无 albedo 对象 **17,682**（v8 是 66,222、v9 重绑前 62,467） |
| `export/world/missing_classified.json` | 9.9 MB | **缺模型分桶**（LOD 块 / 真件 / 包里有无），构建时 `VERIFY` 那行也读它 |
| 上一版 `continent_v8.blend` | 6.81 GiB | 保留作对照（可直接删） |

核对**不需要打开 blend**：

```powershell
uv run python tools/report_manifest.py            # 一行数字 + 明细
uv run python tools/report_manifest.py --find new_gar06_park_terrain
```

### 0.2 与旧版的关系（v2~v7 已删）

- `continent.blend`(9.87 GB)、`continent_v2`(8.07)、`v3`(8.07)、`v4`(7.90)、`v5`(6.31)、`v6`(6.36) **已删除**（2026-10-29 清理，释放 49.94 GiB）
- **v7 从未生成**（发现贴图缺口后主动取消）
- 演进一句话：v2/v3 在跟地形打架（`pad_field` 压平 1.12 m），v4/v5 在跟"擅自剔除"打架（113k→137k 对象），v6 解决可核对性（清单），**v8 解决贴图正确性（按名字重绑）**，
  **v9 解决材质身份（`alb_<贴图名>` + 一子网格一槽）与视口白块（`diffuse_color`）**，并修掉 `index.json` 未补零 key（找回 367 个模型）

### 0.3 当前已知缺陷（按观感排序）

| # | 现象 | 原因 | 状态 |
|---|---|---|---|
| 1 | 城区「发白 / 白块」 | **不是地面色图**：城区色图实测 RGB (29,30,25) 深色。真因是「无 albedo 的材质」在 Workbench/Solid 里用默认 `diffuse_color`(0.8 灰白) 显示 —— 默认视图不吃节点树里的暖灰 | ✅ **v9 已修并出图**：无 albedo 材质 / 顶点色材质 / 水面都设了 `diffuse_color`；对照图 `docs/世界与地编/img/verify/{v8,v9}_city.png` |
| 2 | 部分网格材质是"别人家的贴图" | 旧构建按 `tid` 建材质（`m_<id>`）并按 tid 去重槽位；贴图池 3,025→5,292 后 id 全错位 | ✅ **v9 根修**：材质名 `alb_<贴图名>`、**一个子网格一个槽**；`relink_materials.py` 同步改成按槽位重挂 |
| 3 | 水面灰色平板 | 只有节点树颜色，没有视口色；`blend_method` 在 5.2 已废 | ✅ **v9 已修并出图**：`diffuse_color` + `surface_render_method='BLENDED'`（几何仍是 1 quad，水位真值 40.5 不动）→ 俯视图里水已经是蓝的 |
| 4 | 4.4 万模型无 albedo / 5 万实体缺模型 | 两个口径都过期了。库 **55,608** 模型；缺模型 51,912 hash 里 **88.1% 是 LOD 合并块**（无独立资源），真实缺件 **3,783 实例**。贴图侧另有 **1,782 张孤儿贴图**（`tex/` 有 7,074 张、`tex` 表只登记 5,292 张） | ✅ 贴图：`register_orphan_textures.py` 按 id 补登记 + `--relink` 重挂 **71,929 个材质槽**，**20,858 个模型 / 23,099 个实例恢复 albedo**；模型：已澄清并重排优先级（`docs/世界与地编/RDR2_整图覆盖率核查_20261026.md` §10） |
| 5 | 地图北缘 1.46% 地面是"无数据白" | 地面色图在 y > 3200（真实地图外）没有数据（源 tile 缺失） | ⚪ 真实地图外，v9 仍保留；要补可用 `tools/patch_ground_town_white.py`（默认只 probe） |

### 0.4 旧记录（10-26/27，仅供追溯，其中的产物已删）

当时的主产物是 `continent.blend`（10.60 GB / 117,765 对象）。以下 §0.1~§0.9 保留原样作为技术记录：
四元数共轭、地形贴合实验（**pad 已确认默认关**：H4.npy 残差中位 0.19 m，H4_final 0.39 m）、室内 MLO 摆放等。
**不要照其中的文件名去找产物。**

---

## 0-old. 2026-10-26/27 重大突破（历史记录，产物已删，见 §0.4）

### 0.1 四元数旋向反了 —— 全图已修正重建

Blender 里所有实体朝向整体反了一个方向（主屋烟囱左右反、小物件"有的差 180° 有的差 45°"）。

**根因**：RDR2 ymap 的四元数旋向与 Blender 的 `rotation_quaternion` **相反**，装配时未取共轭。

**决定性证据**（纯几何，不依赖肉眼）：`p_fence04bx` 21 段栅栏围成畜栏，相邻段端点平均距离

| 方案 | 相邻段端点平均距离 |
|---|---|
| 原样 yaw | **1.65 m**（栅栏是断的） |
| **取共轭** | **0.56 m**（基本接上） |

**修法**（`tools/blender_continent.py`，已设为默认）：

```python
ob.rotation_quaternion = (e[7], -e[4], -e[5], -e[6])   # 共轭
```

`--no-conj-quat` 可回退对照。

**同时排除的假设**：不是镜像。比较 mesh bbox 与 ytyp archetype bbox 的 **min/max 绝对值**（镜像会让 min/max 互换），
`roc_01_ext_home01` / `roc_shed_01` / `roc_leanto` / `roc_01_ext_well` 全部**完全一致**。

**字段布局**（逐字节核对，144 字节结构）：hash@+8 / position@+32 / rotation@+48 / scale@+64 / lodDist@+76 / parentIndex@+132。

详见 `docs/格式与资产/RDR2_ymap实体变换解析.md`。

### 0.2 已重建的产物

| 文件 | 状态 |
|---|---|
| `deliverable/blender/continent/continent.blend` | **10.60 GB / 场景 117,765 对象**（`ENTITIES` **116,403** 分 12 类 + `RAILCELLS` 1,359），共轭重建 + 铁路装回 + 地形贴合 + 除植被 + **室内 79 包已摆** |
| `deliverable/blender/continent/continent_withveg.blend` | 8.95 GB，**除植被前**的回退版（114,015 对象），确认无误可删 |
| 地形贴合 | `tools/fit_terrain_to_buildings.py`（pad 模式）已应用：纯房屋贴地 17.3% → 47.0%。**没有保留贴合前的副本**，需要时用下面命令重建（约 15 min）：`blender -b -P tools/blender_continent.py -- --out <blend> --lib assets/lib_native --rails` |
| 地形贴合 | `tools/fit_terrain_to_buildings.py`（pad 模式）已应用：建筑浮空 61.8% → 24.2%，纯房屋贴地 17.3% → 47.0%（§0.8.2） |
| `deliverable/blender/willard/willard.blend` | 1.07 GB / 334 对象，原始 H4 地形 + 共轭，烟囱已在左端 |
| `deliverable/blender/willard/willard_full.blend` | 1.15 GB，外观 + **415 件室内** |

### 0.3 夏洛蒂家「陷地 / 悬空」的完整修复链

这不是一个问题，是**三层叠加**，修一层会暴露下一层：

| # | 层 | 现象 | 修法 |
|---|---|---|---|
| ① | `settlements_bannerlord.csv` 里 `hso` / `abe` / `roc` 的 `u,v` 写成 **`0,0`** | PAD 把这三个点算到**地图西北角** → 这片地形**从来没被压平** → **房子埋进地形 9 m** | 按 `settlements_world_v2.csv` 补正确的 u/v |
| ② | PAD 用「区域内所有实例 z 的**中位数**」压平 | roc 的建筑高度太分散（坟 158.5 / 主屋 168.6），中位算成 161 → **房子悬空 3.45 m** | 分区装配加 `--no-pad`，直接用原始 H4 |
| ③ | 我曾用 IDW 把地形强行压到建筑基底 | 悬空解决了，但**原始地形起伏被抹平**（游戏里房子周围是坡地） | 回退 IDW，改用原始 H4 |

**核对数据**：H4 在房子处 **165.23**，建筑底 **164.55**，差 **0.68 m** —— 这是正常的地基埋深，**本来就贴地**。

**结论：问题全在 PAD，不在高程数据。**

> 同类问题：整图里 POI 仍会被 PAD 误压平，因为 PAD 只覆盖 46 个据点。
> 精确看某个 POI 时，必须 `--only-tile <id> --no-pad`。

### 0.4 已量化的剩余问题（待修）

> 2026-10-27 全部重新实测，口径写清楚，避免再出现"数字对不上"。

| 问题 | 数据 | 结论 |
|---|---|---|
| **缺模型实体** | **52,627 个 hash / 54,094 实例**无模型。其中 2,133 名字像 LOD/代理/VFX、**718 像真模型（多为室内 `_int`）**、**49,776 完全无名**（`export/world/missing_classified.json`） | ⚠️ 52,627 高估了：扫 RPF 得到的 978 个命中里绝大多数是 `_slod/_vfx/_ph/_occ`（无几何）。真实可渲染缺口约 **700~2,000** |
| **白块** | 可装实例 146,183 中 **53,312（36.5%）** 引用的模型含 `tex_id=-1` 的 submesh；模型侧 6,897 / 52,566（13.1%） | 贴图缺口，非渲染 bug |
| **铁路铁轨** | ✅ **2026-10-27 已修**：`RAILCELLS` 1,359 件 / 覆盖 x[−5984,3401] y[−3789,1792] ≈ 9.4×5.6 km | 见 §0.7（旧文档"从未解包"是误判） |
| **建筑浮空 / 陷地（PAD）** | ✅ **2026-10-27 已修主要部分**：修前建筑底−地形中位 **+1.03 m**、浮空 61.8%、贴地仅 17.9%（纯房屋类 17.3%）；用地基台法修后中位 **+0.00 m**、MAE 2.16→**1.25**、贴地 **47.0%**。详见 §0.8.2 |
| **埋入地形（已澄清）** | 按类型拆：**建筑 −0.32 m / 道具 +0.21 m（都正常）**，只有**植被 −6 m** | 植被问题，用户已决定不管 |
| **室内** | ✅ **146 包全部解包**（5,061 文件）+ **2,301 模型入库**；**79 包 / 12,543 对象已摆进场景**（几何审计通过）。剩 57 包溢出宿主 1~5 m | 缺 `CMloArchetypeDef` rooms/portals；详见 §0.8.3 与交接文档 |
| **跨水桥梁 / 铁路（圣丹尼斯西南）** | ✅ **网格本身完整**（2026-10-27 核实）：桥+铁路全在 `wild2000_04_02` 板——铁路件 350、桥/栈桥件 86；栈桥序列 `n_1114_r_b_tres00..08` + 桥 `bri01c` + 枕木 `n_1114_r_b_sle04..18` 沿一条线连续排列，相邻间距中位 ~1.6 m、P90 ~22 m，无断口（唯一 73.8 m 间隔在道岔 `rrcross_01` 到正线之间，正常） | 不是缺模型，也不是水位问题。见交接文档 §三 |
| **室内摆放** | 146 包已解包、2,301 模型入库；**79 包 / 12,543 对象已摆**；57 包溢出宿主 1~5 m | 缺 `CMloArchetypeDef` rooms/portals |
| **植被** | ✅ **已清除**（用户决定不复原）：`willard_full` 删 450；`continent` 共删 **10,232**（含补漏 571，修了"名字 hash 丢前导零"的解析 bug）。现存 1,261 个杂草/常春藤，**默认隐藏**。工具 `tools/strip_vegetation.py`；回退版 `continent_withveg.blend` | 已完成 |
| **地面贴花** | 材质管线只取纹理 RGB，**alpha 未接到 BSDF** → 半透明污渍/贴花变成不透明黑（或白板） | 根因已定位，修法见 `docs/交接与状态/RDR2_室内装配与烘焙_交接.md` §三 |

### 0.5 室内模型与布局（2026-10-27）

**成果**：

| 项 | 数据 |
|---|---|
| 室内 ydr | 31 个（`roc_house_int.rpf`），27 个入 lib（双人床/壁炉/橱柜/炉子/镜子） |
| MLO 布局 | **455 项**（`roc_house_int.ytyp` 的 144 字节 entity 块），415 项装配成功 |
| 产物 | `deliverable/blender/willard/willard_full.blend`（1.15 GB，外观 + 室内） |
| 父级 | **已烘焙**，415 个件各自带世界变换，`INTERIOR_ROOT` 已删 |

**坐标链（可复现）**：

| 项 | 值 |
|---|---|
| MLO 实例 `roc_hse_int_lod` | pos (2990.42, 2188.85, 168.44)，yaw −70° |
| 室内整体 bbox | X[2982.26, 2994.29] Y[2181.34, 2196.39] Z[165.69, 171.03] |
| 房子墙体 bbox | X[2980.29, 2996.27] Y[2180.09, 2197.64] Z[164.55, 172.65] |
| **四边间隙** | X 左 1.97 / 右 1.98，Y 下 1.25 / 上 1.24（**对称**） |

**必须隐藏的"假几何"**（自带屋顶/地板，会和外壳重叠）：

| 类别 | hash |
|---|---|
| 房间壳 | `cba915be` `ac262389` `e6649809` |
| 细节件 | `b56905d2` `82519f88` `ae28fb80` `4be4a68c` |
| 木结构（带屋顶） | `b2afc32a` `d6a5cf80` |
| 代理盒 | `54b00fdf`(shadowproxy) `51b78358`(reflection) |
| 梁 / 木块 | `b93ccef5` `f0eaad82` |
| 地面污渍 | `d3f79faf` `59f1bb50` `3933f9d1` | `roc_dirt_stains`，**alpha 未生效 → 整块不透明黑** |
| 散装瓶子 | `a9d63ce4` `acec4310` `65c75ef` | `roc_hse_int_bottles01/02/03`，**6~8 m 宽、厚 0.1 m 的瓶子合集**，平铺像黑色地板 |

**数据读取坑（重要）**：

| 读法 | 结果 |
|---|---|
| `o.bound_box` | 旧缓存：给 20.2×21.1，实际 **16.0×17.5** |
| `o.matrix_world`（有 parent） | 返回**局部**（`matrix_parent_inverse` 抵消） |
| `evaluated_get(dg).matrix_world` | 同样不可靠 |
| **烘焙后读 `o.location`** | ✅ 可靠 |

**对齐方法（已验证可复用）**：室内整体 bbox 在房子 bbox 内**居中** + 用 `parent_clear(CLEAR_KEEP_TRANSFORM)` 烘焙父级。

详见 `docs/交接与状态/RDR2_室内装配与烘焙_交接.md`。

### 0.6 全图铺量 TODO（把夏洛蒂家的经验套到全部房子）

#### 规模：152 个室内包

游戏里 `levels/rdr3/interiors/` 下共 **152 个 `*_int.rpf`**：

| 前缀 | 数量 | 说明 |
|---|---|---|
| `new_*` | 30 | 新奥斯汀区域 |
| `shack_*` | 20 | 棚屋 |
| `val_*` | 14 | 瓦伦丁 |
| `van_*` | 10 | 范霍恩 |
| `str_*` | 9 | 草莓镇 |
| `rho_*` | 9 | 罗兹 |
| `old_*` | 8 | |
| `tum_*` | 6 | 风滚草镇 |
| 其他 | 46 | `mil` `pro` `q03` `ser` `qua` `pai` … |

#### 每栋房子的 5 步（夏洛蒂家已验证）

| # | 步骤 | 脚本 | 可自动化 |
|---|---|---|---|
| 1 | 解包 `*_int.rpf` | `rdr2rpf extract --recurse` | ✅ |
| 2 | 模型入库 | `tools/add_interior.py` | ✅ |
| 3 | 解析 MLO 布局 | `tools/parse_interior_mlo.py` | ✅ |
| 4 | 装配进房子 | `tools/merge_interior_into_willard.py` 改写 | ⚠️ 需每栋房子参数 |
| 5 | 清理假几何 + 烘焙 | `tools/bake_interior_root.py` | ⚠️ 需每栋 hash 清单 |

#### 四个必须先解决的通用问题

| # | 问题 | 现状 |
|---|---|---|
| ⚠️ **1** | **MLO 实例（世界位置/朝向）找不到** | 夏洛蒂家用 `roc_hse_int_lod` 顶替。其他房子不一定有同类 LOD 实例，**这是最大阻塞** |
| ⚠️ **2** | 假几何 hash 清单是逐栋不同的 | 现在只有 roc 的 17 个（壳/细节/木结构/代理/污渍/瓶子）。其他房子需要重新识别 |
| ⚠️ **3** | 房子外壳要逐栋定位 | 可用 `--only-tile <id>` 分区 + 按坐标查 |
| ⚠️ **4** | 室内可能跨多个 2000 m tile | 装配时要按房子实际所在位置取分块 |

#### 建议优先级

| 档 | 数量 | 内容 | 理由 |
|---|---|---|---|
| **P0** | ~50 | `val` `rho` `str` `van` `sdn`（主要城镇） | 玩家最常看，且房子密集 |
| **P1** | ~34 | `shack` `old` `tum` | 野外棚屋，结构简单 |
| **P2** | ~68 | `new` + 其他 | 低优先，多为重复模板 |

#### 铁路铁轨 —— ✅ 已修（2026-10-27，本节为结论，过程见 §0.7）

| 项 | 实测 |
|---|---|
| tiles 里精细铁路实例 | **1,382**（不按名反查则 **1,359 在库**） |
| 命中 `cell`（64/128 分块）规则 | **0** |
| **命中 `flat_wide`（又扁又宽）规则** | **1,024** ← 唯一的杀手 |
| 能通过过滤的 | 335（基本都是 `rrcross` 道岔） |
| 覆盖范围 | x[−5984, 3401] y[−3789, 1792] ≈ **9.4 × 5.6 km**（含主地图） |
| 现在的状态 | ✅ `continent.blend` 的 `RAILCELLS` **1,359 件 / 1,271 网格** |

> ⚠️ 旧版本这里写的是「主地图铁路从未解包，要解 `area/rails/*.rpf`」——**那是误判**，数据一直在 tiles 里。

#### 工作量估算

| 阶段 | 说明 |
|---|---|
| 解包 + 入库 + 解析（152 个） | 纯脚本，约 **2~4 小时**（磁盘和 RPF 读取是瓶颈） |
| 装配参数（每栋房子定位） | **最大瓶颈**，取决于问题 ① 能否解决 |
| 假几何识别 | 每栋 5~10 分钟人工确认，或按 hash 前缀推断 |

> **结论**：先把问题 ①（MLO 实例定位）解决，其余才能批量。否则每栋房子都要像夏洛蒂家一样手工调。

---

### 0.7 2026-10-27 复核：两处旧结论被推翻

#### 0.7.1 铁路：不是"没解包"，是被自己的剔除规则吃了

**误判**：旧文档说主地图铁路"从未解包"，需要去游戏里解 `levels/rdr3/area/rails/*_rails_c.rpf`。

**实测**：铁路数据一直在 `tiles/*.json` 里（1,382 精细实例，覆盖 9.4×5.6 km），模型 1,359 个也一直在 `lib_native`。
真正原因只有一条：

```python
# tools/blender_continent.py build_entities()
flat_wide = (dz < 2.0 and max(dx, dy) >= 16) or max(dx, dy) > 45
```

铁路地块的包围盒典型是 **22 × 14 × 1 m**（扁、宽）→ 命中 → 1,024 / 1,359 直接丢。
剩下的 335 件能过，是道岔之类的小件，这就是"为什么只有地图边缘有一点铁轨"。

**修法（已落地）**：

| 改动 | 位置 |
|---|---|
| 新增 `--rails` 开关：铁路件豁免 `TERRAIN_CELL / cell / flat_wide` 三条规则，并打印 `RAILS n` | `tools/blender_continent.py` |
| `rail_hashes()`：用 `names.txt` 建 joaat → 铁路哈希集合（规则与补丁脚本一致） | 同上 |
| 补丁脚本修旋向 + 去重 + 打印覆盖范围 + `tex_id<0` 给中性灰 | `tools/add_rail_network.py` |

**验证（可复现）**：

```bash
# 单 tile 对照（wild2000_01_03）
blender -b -P tools/blender_continent.py -- --out /tmp/a.blend --lib assets/lib_native --only-tile wild2000_01_03 --rails
#   → ENTITIES 6103 / RAILS 230
blender -b -P tools/blender_continent.py -- --out /tmp/b.blend --lib assets/lib_native --only-tile wild2000_01_03
#   → ENTITIES 5952 / 没有 RAILS 这一行
```

**验收图**：`deliverable/blender/continent/shots/rail_top.png`（站场俯视）、`rail_close_on.png`（近景双线+枕木+道砟）、`rail_air_on.png`（进隧道的正线）。

**⚠️ 一个反直觉结论（也推翻旧文档）**：旧文档建议"铁路最适合验证四元数共轭"。

| 判据 | 共轭 | 非共轭 | 能否区分 |
|---|---|---|---|
| 相邻段「长轴 vs 邻段方向」夹角 | 22.7° | 23.0° | ❌ |
| 相邻段最小角点距 | 4.309 m | 4.358 m | ❌ |

因为 **97.6% 的铁路地块 yaw = 0**（99.1% 是纯 yaw，绝大多数是单位四元数）——铁路是**轴对齐分块、轨道烘在网格里**，不靠实例旋转拼接。
所以铁路**验证不了旋向**；共轭的唯一硬证据仍然是栅栏 `p_fence04bx`（1.65 m → 0.56 m）。

另有一条**实测限制**：地形彩图（1 m/px 的地面色图）上本来就画着轨道，所以把 `RAILCELLS` 关掉后远看轨道仍在。
A/B 像素差只有 **2%（强差 0%）**——3D 铁路的价值在近景的枕木/道砟立体感，**不能**用"轨道消失了"来证明装成功。

#### 0.7.2 5 万个未命名部件：不是"LOD 代理不用装"，是模型真的没抽

旧文档写"未命名 archetype 来自无后缀主包，是 LOD 分块代理，本就不该装"。复核后不成立：

| 实测 | 数 |
|---|---|
| 未命名 archetype | **49,778 种 / 50,007 实例**（占实例 25%） |
| 其中 ≥8 m 大件 | **44,900** |
| 在 `lib_native` 里 | **只有 2 个** → 确实没抽 |
| 据点严格框内未命名大件 | **9,043**（sdn 2,124 / ann 308 / bla 291 / val 267 / cor 266 / rho 215 …） |

**新证据（决定了下一步怎么做）**：`export/levels/town/archetypes.json`（从 1,026 个 ytyp 解析出的 96,141 条）里，
**已经包含 49,595 / 49,778 个未命名 archetype（99.6%）**，带包围盒 + assetName hash，覆盖 49,806 / 50,007 实例。

所以缺口不是"解不出定义"，而是"有 hash 但没去抽 `.ydr`"。路径：

1. 从 ytyp archetype 定义取 `assetName`（`tools/ytyp_archetypes.py` 已能读 +88/+112 两个 hash，缺的是 assetName → 文件枚举这一步）；
2. 在 RPF 里按 hash 定位 drawable（`rdr2rpf find` 的 pattern 语义待验证；不支持就先 `tree` 全量导出 hash→路径表）；
3. 抽出的 `.ydr` 走 `dump_model_lib.py` 入库；
4. 重跑装配（建议同时带 `--rails`）。

**验收指标**：未命名实例 50,007 → **< 5,000**；圣丹尼斯"未命名大件 2,124" → < 300。

---

### 0.8 2026-10-27 第三次复核：夏洛蒂家那三个问题，全图到底解决到哪一步

> 逐项实测（不是"应该已经生效"）。结论：**旋转 ✅ 全图已解决；陷地 ⚠️ 已修复主要部分（有数字）；室内 ❌ 只做了 1 栋，且"对齐"方法本身有问题。**

#### 0.8.1 网格旋转 —— ✅ 全图已解决（硬证据）

在 `continent.blend` 里抽 6,000 个实体对象，与 tiles 里的四元数逐一对账：

| 分类 | 数量 |
|---|---|
| 恒等/纯 yaw=0（两种写法本就相同，不可判定） | 468 |
| **有旋转、且只匹配「共轭」** | **386** |
| 有旋转、只匹配「原样」 | **0** |
| 都不匹配 | **0** |

⇒ 单点修正（`blender_continent.py` 默认 `conj=True`）确实覆盖全图，没有残留的旧旋向对象。

#### 0.8.2 陷地 / 悬空 —— ⚠️ 根因是 PAD，已修主要部分

用 `Terrain` BVH 与 2,042 个建筑类实例逐栋量「建筑底 − 地形」，并拆开 PAD 的影响：

| 指标 | 数值 |
|---|---|
| 建筑底 − 地形（全图，修前） | 中位 **+1.03 m**；浮 >0.5 m **61.8%**；贴地仅 **17.9%** |
| **PAD 对地形的改动** | 中位 **−1.12 m**；**压低 >0.5 m 占 63.9%** |
| 只统计「PAD 未改动」的区域 | 中位 **−0.23 m（正常）** |

⇒ **模型与高程数据都没问题，是 `pad_field()` 把城区地形压到"所有实例 z 的中位数"（道具/围栏把中位拉低）**。
修法：新增 `tools/fit_terrain_to_buildings.py`（默认 `--mode pad`）——**给每栋建筑铺一块自己的地基台**，再把地形平滑过渡过去。

| 指标（纯房屋类 1,575 栋） | 修前 | 修后 |
|---|---|---|
| 中位 | +1.14 m | **+0.00 m** |
| MAE | 2.16 m | **1.25 m** |
| 浮 >0.5 m | 65.3% | **28.4%** |
| 埋 <−0.5 m | 17.4% | 24.6% |
| **贴地 \|d\|≤0.5** | **17.3%** | **47.0%** |

`continent.blend` 已应用（8.95 GB，`RAILCELLS` 1,359 保留）；回退副本 `continent_before_fit.blend`。
出图：`shots/str_near_continent.png`（修前，地基悬空）vs `str_near_continent_fit.png`（修后，落地）。

> 剩余 28% 浮空主要是**设计上就抬高的房子**（草莓镇那种架在柱子上的木屋）+ 4 m 分辨率地形在坡地上的量化误差，不是统一偏移。

#### 0.8.3 室内对齐 —— ❌ 没有全图解决，而且现有做法本身有问题

| 项 | 实测 |
|---|---|
| 游戏内室内包 | **144 个**（`levels_rdr3/interiors/*_int.rpf`，旧文档写 152） |
| 已装配完成的 | **1 个**（罗兹威拉德之息 = 夏洛蒂家） |
| **能否定位每栋的 MLO 实例** | ✅ **136 / 144 = 94%**（精确 129 + `_lod` 4 + `_main` 3）；仅 8 个无实例 |
| 结论 | **"找不到 MLO 实例"这个旧阻塞不成立**，但**摆位还没解对** |

**新发现（重要）**：夏洛蒂家当时用的是**替身实例** `roc_hse_int_lod`，而游戏里真实实例是 `roc_house_int`：

| | 位置 | yaw |
|---|---|---|
| 替身 `roc_hse_int_lod`（当年用的） | (2990.42, 2188.85, 168.44) | **−70°** |
| 真实 `roc_house_int`（游戏数据） | (2991.0, 2190.4, 166.8) | **+30°** |

两者**水平差 1.71 m、垂直差 1.60 m、yaw 差 100°**。当年用「旋转到房子 yaw + bbox 居中」把它强行掰正了 —— 所以"四边间隙对称 1.97/1.98、1.25/1.24"是**做出来的对称**，不是数据本身。

用真实例直接装配会怎样（实测 `willard.blend` + 415 件室内）：

| 方式 | 可见室内 bbox 四边间隙 | 结果 |
|---|---|---|
| 替身 + 强制对齐（现状 `willard_full.blend`） | X 3.80/4.35 · Y 2.94/2.61 | 视觉塞得进去，但旋转是掰的 |
| **真实例，不加对齐** | X 2.08/0.45 · Y 3.84/2.31 | **家具从屋顶西/北侧露出来**；壳 yaw −170° vs 房子 100°（差 90°） |
| 真实例 + 额外 ±90°/180° | 出现负间隙（更差） | 没有单一 yaw 能修好 |

⇒ **室内局部空间还缺一层变换**（大概率在 MLO archetype 的 rooms/portals 里，现在只用了 144 字节 entity 块），
这一层没解出来之前，**室内无法批量**。

**已交付工具（解除"定位"这一半阻塞）**：

| 文件 | 作用 |
|---|---|
| `tools/locate_interior_mlo.py` | 包名 → MLO 实例世界变换（pos/quat/yaw/scale）+ 最近宿主建筑；`--json` 导出映射表。全量：`136/144` |
| `tools/merge_interior.py` | 通用装配（原 `merge_interior_into_willard.py` 的泛化版）：`--pkg` 自动查真实例、`--align` 复刻老行为、`--extra-yaw` 试验额外旋转 |
| `export/world/interior_pkgs.txt` | 144 个室内包清单（从 `levels_3.rpf` 列出） |

**下一步（室内）**：解 `roc_house_int.ytyp` 的 **CMloArchetypeDef rooms / portals 变换**（不是 entity 块），
用 3 栋已知房子（`roc_house_int` / `val_hotel_int` / `new_com_bank_int`）做三角验证，找那层固定映射。

---

### 0.9 本轮会话（2026-10-27）小结 —— 交接看这里

> 完整交接：`docs/交接与状态/RDR2_20261027_会话交接.md`

**这轮修掉的十件事**（都有实测）：铁路补装（`--rails`）· 全图旋向核验 · PAD 陷地/浮空（地基台法）·
水面高于地形（桥下挖河床）· 植被清除（willard 450 + continent 10,232）· **12 类分类开关（N 面板）**·
预览提速（无贴图 + 减面 + 流式加载，43 s→13 s）· 室内 146 包解包 + 2,301 模型入库 ·
79 包室内摆放（12,543 对象）· `flat_wide` 误杀 3D 大件（+671 对象）。

**三个"以前一直错着"的 bug**：对象名 hash 丢前导零（5,864 个对象从未被识别）·
`flat_wide` 第二条不看高度（桥段/高架被剔）· 面板勾选与集合不同步。

**留给下一轮**：① 57 个室内包对齐 ② `unknown` 3,788 长尾 ③ `previews/sdn` 网页分块补铁路层（blend 侧已补齐，见 §5.1c）。

### 5.1c 圣丹尼斯「完整版」：补回桥 + 铁轨（2026-10-27）✅

**问题**：`sdn.blend`（10-19 版）里没有铁路网，西南跨水桥也不在。查下来是两个独立原因：

| # | 原因 | 证据 |
|---|---|---|
| 1 | 导出脚本按**圆形硬裁 r=620 m**（圆心 2555,−1151） | `tools/export_sdn_gltf.py:635-645`；桥距中心 750~1113 m ⇒ 全在圆外 |
| 2 | **模型库没抽铁路 ydr** | `work/sdn/models` 原有 3,647 个 ydr，`_r_c_`/`_r_b_` 铁路模型 **0 个** ⇒ 圆内 150 个铁路实例匹配不到模型，静默跳过 |

> `620` 是 `tools/build_settlement_previews.py:86` 给 sdn 的硬编码（其它城镇按 `eq/2+80`）。

**修复（本轮已做）**：

1. **抽铁路模型**：从游戏 `levels_1.rpf` 抽 `area/nopq_11_14/nopq_11_14_rails_a|b.rpf`（→ `n_1114_r_b_*` 桥/栈桥/枕木 185 个）
   和 `levels_2.rpf` 抽 `area/rails/nopq_11_14_rails_c.rpf`（→ `n_1114_r_c_*` 轨面 242 个），复制进 `work/sdn/models`
   （ydr 2,733 → **3,309**，铁路 408 个）；校验：1250 m 圆内 364 个铁路实例，**模型覆盖 364/364 = 100%**
2. **半径 620 → 1250**：`export_sdn_gltf.py --r 1250 --out export/levels/world/gltf/sdn_full`
   ⇒ **52 块 / 944 MB / 贴图 1,508 张**，其中 **354 个铁路 mesh + 73 个桥·栈桥 mesh**，分布在 20 块里
3. **装配**：`blender_assemble_sdn.py --no-props --no-int --area "1300,-2400,3810,100"`
   ⇒ `deliverable/blender/sdn_full/sdn_full.blend`（1.37 GB），包围盒 x[1327,3160] y[−1908,−696] span 1,833 m

**验收图**（`deliverable/blender/sdn_full/shots/`）：
`full_persp_bridge.png`（木栈桥 + 钢桁架桥 + 连续轨道，最直观）· `eevee_bridge.png`（带贴图）·
`full_top_all.png` · `full_top_bridge.png` · `full_persp_city.png` · `eevee_city.png`

**结论**：桥和铁轨的网格一直是完整的，缺的是**导出范围 + 模型库**这两步。现在城区 + 桥 + 铁路在同一场景里。

---

---

## 30 秒入口

双击根目录 **`打开查看器.bat`** → 本地服务起在 `http://127.0.0.1:8788/`（被占用会顺延到 8789~8792，**看启动窗口里那行 URL**）。
首页列出全部入口。要单独打开某一页：

| 我要… | 地址（相对 `http://127.0.0.1:8788/`） |
|---|---|
| **★ 用 AVG 看主线（观看段）** | `avg/index.html`（`?m=WNT1&at=110` 深链） |
| **主线游玩段：去哪里/找谁/打谁** | `avg/playbook.html`（`?m=WNT1`） |
| **看载具（马车/船/火车/炮车）** | `vehicles/index.html`（`?n=policewagongatling01x` 直连） |
| **★ 大陆最新效果（全图实拍）** | `preview_map/index.html`（含地形贴合前后对比、铁路、城镇） |
| **★ 沙盒大地图（46 据点微缩模型）** | `miniatures/map/index.html`（`?focus=sdn` 直达某城） |
| **看单个据点的微缩模型** | `miniatures/map/inspect.html?code=sdn` |
| **看游戏 UI（纹理/界面/控件）** | `ui/index.html` |
| **看兵种清单与覆盖真相** | `units/index.html` |
| **看随机任务还原** | `mission_flow/index.html`（`?cov=1` 看覆盖/缺失清单） |
| 看剧情 + 每句说话人 | `story/index.html` |
| 全部对话索引 | `story/conversations.html` |
| 过场解析总览 | `story/cutscene/index.html` |
| 场次卡（分镜+出场+台词） | `story/cutscene/scene_cards.html` |
| 相机机位俯视图 | `story/cutscene/camera.html` |
| 过场反拆解（录屏→镜头/台词） | `cutscene/index.html` |
| 角色 3D / 角色动画 | `npc/index.html` / `npc/anim.html` |
| 服饰清单 / 3D 试衣间 | `viewer/clothing.html` / `viewer/clothing3d.html` |
| 武器查看器 | `viewer/index.html#/weapons` |
| 43 城镇预览 | `previews/index.html` |
| 地图标定工具 | `anchor_picker.html` |
| 圣丹尼斯材质前后对比 | `previews/sdn_material_before_after.jpg` |

3D 大文件直接开：

| 我要… | 路径 |
|---|---|
| 整块大陆 | `deliverable/blender/continent/continent.blend`（7.80 GB） |
| 瓜玛岛（任务场景） | `deliverable/blender/guarma/guarma.blend`（0.29 GB） |
| 圣丹尼斯单城 | `deliverable/blender/sdn.blend`（2.23 GB） |

---

## 1. 八条产线，各自做到哪

| 产线 | 状态 | 关键数字 | 入口 |
|---|---|---|---|
| **世界重建** | 大陆装配完成、地形/材质/建筑齐全、**铁路已装回** | **200 303 个实例（装进 147 497 = 73.6%）/ 55 608 网格 / 46 个据点 / 铁路 1 359 件** | `deliverable/blender/` + `previews/` |
| **剧情与过场** | 过场结构、镜头、台词、说话人都已解出 | 668 过场 / 2 199 镜头 / 322 分钟 / 71 420 行对话 | `story/` |
| **随机任务** | **源代码级还原**，不是重做玩法 | 105/150 已还原 · 27 个带原文台词 1 398 句 | `mission_flow/` |
| **主线 AVG 化** | 按脚本过场段链拆「观看/游玩」两段 | **105 任务 / 800 段**（过场 434 + 游玩 366）· 8 625 句台词 · 41 立绘 · 62 背景 | `avg/` |
| 角色与物品 | 角色 GLB、服饰、武器齐全 | 412 GLB / 6 106 件服饰 / 408 条角色清单 | `npc/` + `viewer/` |
| **载具** | ✅ `vehicles.rpf` 全量解出并转 glTF | **108 个模型**（马车 50 / 火车 33 / 船 18 / 武器载具 5 / 电车 1 / 热气球 1） | `vehicles/` |
| **游戏 UI** | ✅ 纹理全解 + 界面/控件/影片清单 | **1 922 张纹理** / 461 界面 / 401 控件 / 378 影片 / 20 布局 | `ui/` |
| **兵种（gameplay ped）** | ⚠️ 清单全、模型 0 个（配方未解） | **1 086 个 archetype**；过场角色导出了 246 个 GLB | `units/` |
| **沙盒大地图（微缩模型）** | ✅ 46 个据点全做完、街区积木化 | **46 个 GLB（单材质顶点色）**，合计 18 404 面；同屏 22.8 万面 / 47 draw call | `miniatures/` |

---

## 2. 关键数字（都可复现，不是估的）

### 2.1 世界

| 指标 | 值 |
|---|---|
| 地图框 | x ∈ [−6844, 3924]，y ∈ [−4800, 3224] → 10 768 × 8 024 m ≈ **86.4 km²** |
| 高度图 | 2 692 × 2 006，**4 m/px**，16 bit（PNG + r16 raw，逐值一致） |
| 地形材质 | **7 层**权重，与高度图逐像素对齐，水陆 **IoU = 1.000** |
| 地面彩图 | 12 296² @1 m/px（0.23 GB，**默认用这张**）/ 24 592² @0.5 m/px（0.81 GB） |
| 建筑实例 | **200 303** 条（43 个 2000 m 分块；2026-10-27 复核口径，含后并入的植被） |
| 其中能装进 blend | **147 497（73.6%）**；缺口 52 806 里 **46 536 是 LOD 合并块**（无独立资源，见 `docs/世界与地编/RDR2_整图覆盖率核查_20261026.md` §10），其余是 VFX/代理/室内等 |
| 模型库 | **55 608** 个无损网格 + **5 292** 张 albedo |
| archetype | 唯一 **102 051** 种（可命名 52 273 / 51.2%）；`model_manifest.csv` 里 10 893 种是"有名字且有网格"的子集 |
| 据点 | **46** 个（v2，含 10 城 / 11 堡 / 12 村 / 4 营 / 4 POI / 2 藏身处 + 3 剧情点） |
| 建筑材质（圣丹尼斯） | albedo **512²** + `_nm` **法线 3811 材质** + `_ma`→**ORM 3447 材质**（metal/rough/AO）；查看器有 PMREM 环境光 |

### 2.2 剧情与任务

| 指标 | 值 |
|---|---|
| 任务 | **270** 个（15 类，含 150 个随机/支线） |
| 过场 | **668** 个 / **2 199** 镜头 / **19 318 s = 322 分钟** |
| 对白索引 | **71 420** 行 |
| 按步骤对白 | 38 个任务 / 6 224 句 |
| 字幕库全量 | 35 个任务 / **7 865 句** |
| **随机任务还原** | **105 / 150**；27 个带原文台词 **1 398 句**；8 个有目标文案 |

> 两套台词数是不同口径：7 865 是任务字幕库里的全部句子；1 398 是**能按脚本对话组归位**的句子。
> 还原方法见 `docs/任务与剧情/随机任务还原说明.md`。

### 2.2b 主线「观看 / 游玩」拆段（2026-10-25）

| 指标 | 值 |
|---|---|
| 主线任务 | **105**（76 个有脚本段链，29 个 `rcm_*` 兜底） |
| 观看段（过场） | **434 段**，304 段有明确时长，合计 **156.5 分钟** |
| 游玩段（纯游玩） | **366 段** |
| 过场台词 | **8 625 句**，**8 534 句**带说话人（98.9%） |
| 目标步骤卡 | **748** 张（100 张带字面坐标、263 张带对象） |
| AVG 素材 | 立绘 **41** 张（真实 GLB 渲染）· 2D 背景 **62** 张 / 34 个地点（每个任务按其坐标聚类落到最近据点） |
| 仍缺的 | 目标触发条件、敌人数量与站位、逐镜相机世界变换 |

> 拆段依据是脚本里的 `func_*(状态from, 状态to, mark1..5, "过场名或空", flag, clips)` 链：
> **名字非空 = 观看段，为空 = 纯游玩段**。详见 `docs/任务与剧情/RDR2_主线AVG化与游玩阶段解析.md`。

### 2.3 载具 / UI / 兵种（2026-10-24 新增）

| 指标 | 值 |
|---|---|
| 载具包 | `vehicles.rpf` 550 MB / 663 项 → 662 个文件（216 `.yft` + 445 `.ytd`） |
| 载具模型 | **108 个 base 载具**全部转成 glTF（+353 张 PNG，207 MB） |
| ★ 马车上架机枪 | `policewagongatling01x`（车厢+加特林一体，19 160 面）、`gatchuck` / `gatchuck_2`（炊事车+机枪） |
| ★ 轮船 | `ship_guama02`（270 386 面 / 78.6 m）、`tugboat2`、`turbineboat`、`boatsteam02x`、`keelboat` …共 18 条 |
| UI 纹理 | **1 922 张**（地图图标 321 / 物品图标 803 / 背包 326 / 武器轮盘 64 / 菜单 63 / 枪匠配色 107 …） |
| UI 定义 | 界面 screen **461** · 控件 widget **401** · Scaleform 影片 **378** · HUD 布局/配色/字体 **20** |
| 兵种 archetype | **1 086 个**（`metapeds.rpf`，一个兵种一个 ymt，含 55 骨偏移/表情/变体） |
| 兵种模型 | **0 个** —— 部件配方 `PedComponentSetName` 未解（详见 §6） |
| 过场角色 GLB | **246 个**（`cs_*` 是整只模型，可直接看） |

### 2.3b 沙盒大地图微缩模型（2026-10-25）

| 指标 | 值 |
|---|---|
| 据点 | **46 / 46** 全部产出（城 10 / 堡 11 / 村 12 / 营 5 / POI 6 / 藏身处 2） |
| 每个据点 | **1 个 GLB、单材质顶点色**；全城建筑按 30 m 网格并成街区，一街区一块实心积木 |
| 三角面 | 合计 **18 404**（最大圣丹尼斯 6 230） |
| 体积 | GLB **2.3 MB**（单材质顶点色，无贴图） |
| 比例 | **统一 1/29**，仅 6 个 <2.5 m 的点按规则放大（最大 3.63×） |
| 全图同屏 | **235 730 面 / 47 draw call**（地形 218 880 + 46 据点 + 水面） |
| 验收 | `uv run python tools/audit_miniatures.py` → 46/46 通过 |
| 规格 | `docs/世界与地编/RDR2_沙盒大地图_微缩模型规格.md`（7.0.1 重写版，含 46 行分档表） |
| **经验/踩坑** | **`docs/世界与地编/RDR2_微缩模型_经验与失败路径.md`** —— 9 条路线的实测结论、5 个硬坑、还差的那一步 |

> 一句话：**大地图只看"认得出是哪座城"**，街景请切场景看 `deliverable/blender/` 的整城模型。

> ⚠️ 这一版是"街区积木"：把全城建筑按 30 m 并成街区，一街区一块积木，**只是远景占位**。
> **单城的真实模型早就有了，别自己再造**：`export/previews/<code>/tiles/*.gltf`（43 城 / 2.61 GB，
> 圣丹尼斯 1.7 GB 分 38 块）。大地图缺的只是"点进去按需加载那座城的 tiles 并卸载"。
> 架构、体积、分块加载写法与 6 条弯路，见 `docs/世界与地编/RDR2_微缩模型_经验与失败路径.md`。

### 2.4 角色与物品
| 指标 | 值 |
|---|---|
| 角色/动物 GLB | **412** 个（清单 408 条，2.1 GB，贴图内嵌） |
| 服饰 | **6 106** 件（含缩略图 + 3D 试衣间） |
| 城镇 3D 预览 | **43** 个 |

---

## 3. 目录结构

```
大镖客2解包分析/
├── README.md                    本文件（唯一入口）
├── README_骑砍2交接.md           给下游骑砍2 Agent 的数据契约
├── STRUCTURE.md                 路径对照（联接说明）
├── 打开查看器.bat               ← 唯一启动器
├── docs/                        文档（五类，见 §7）
├── deliverable/                 交付物
│   ├── heightmap/               权威高度图（PNG + r16 + 水掩码/水深 + meta）
│   ├── terrain_weights/         7 层材质权重 + 打包 RGB + 自检图
│   ├── handoff/                 机读清单（model_manifest / settlements / npc）★ sdn_flat_table.csv / sdn_landmark_church.json
│   ├── blender/                 continent / guarma / sdn 三个成品
│   ├── miniatures/              46 据点微缩模型（models/ tex/ map/ audit）+ 地图 demo
│   └── map_check/               水陆一致性证据
├── export/                      网页 + 数据（脚本按此路径读写，别改名）
│   ├── index.html               首页
│   ├── mission_flow/            随机任务还原器
│   ├── avg/                     主线 AVG（播放器 + 游玩手册 + 立绘 + 背景 + data）
│   ├── story/                   剧情 / 过场 / 对白
│   ├── cutscene/                录屏反拆解
│   ├── npc/                     角色 3D + 动画
│   ├── viewer/                  服饰 / 武器 / 综合查看器 / models/vehicles（108 载具 glTF）
│   ├── vehicles/                载具页（马车/船/火车/炮车）
│   ├── ui/                      游戏 UI 页（纹理画廊 + 界面/控件/影片/布局清单）
│   ├── units/                   兵种页（1086 archetype 覆盖状态 + 平克顿专区）
│   ├── previews/                43 城镇预览
│   ├── world/                   地形数据 + 实例分块
│   └── levels/world/            任务 / 据点 / 对白 / 武器表（CSV/JSON）
├── assets/lib_native/           52 566 网格 + 7 065 贴图（RMDL1 二进制）
├── raw/                         原始解包素材（可重抽，见 §6）
├── archive/                     历史文件
├── tools/                       235 个 .py 脚本（索引见 tools/README.md）
├── 录屏/                        反拆解用录屏样本
└── 地图下载/                     参考地图
```

### 五档职责

| 目录 | 是什么 | 能不能删 |
|---|---|---|
| `deliverable/` | **交付物**，交接必须留 | ❌ |
| `export/` | 网页 + 数据，互相相对路径引用 | ❌（内部可重组） |
| `assets/lib_native/` | 模型/贴图源库 | ❌ |
| `raw/` | 从 RPF 抽出来的原料 | ⚠️ 可重抽（1~3 h/批），详见清理清单 |
| `archive/` | 历史文件 | ⚠️ 基本可删 |

### 目录联接（改路径前必读）

`export/` 和 `work/` 这两个名字仍在使用，是因为 **100+ 个脚本和全部文档按它们读写**。
真实文件已在 `deliverable/`、`raw/`，旧名只是入口：

| 旧路径 | 实际位置 |
|---|---|
| `work/*` | `raw/*` |
| `export/levels/world/blender/*` | `deliverable/blender/*` |
| `export/world/lib_native/*` | `assets/lib_native/*` |
| `export/levels/collision/*` | `raw/collision/*` |

> 硬改会打断整条流水线。**不要直接删这些联接**，用 `cmd //c dir` 确认。

### 机读表（给下游 / 第三方工具，2026-10-25 新增）

预览用的分块 glTF 是自包含的（节点变换 + 网格 → 材质 → 三张贴图都在一个文件里），
但下游往往要一张**扁平表**。为此加了一个一键摊平：

| 文件 | 内容 |
|---|---|
| `deliverable/handoff/sdn_flat_table.csv` | **17 433 行 / 26 列**：一行 = 一个实例的一个图元 |
| `deliverable/handoff/sdn_landmark_church.json` | 地标基准（大教堂）：世界坐标 / AABB / 四元数 / 参考机位 |
| `tools/build_flat_table.py` | 生成脚本，任意城镇可用：`--town val` |

字段（坐标系 = **RDR2 原生 X 东 / Y 北 / Z 上，米**）：

```
tile                     分块 glTF 名（c<k0>_<k1>.gltf）
instance                 实例名（= 模型名；同名多实例靠坐标区分）
mesh, prim               该实例的 meshes[i].primitives[j]
material                 材质名
tex_base / tex_normal / tex_orm    三张贴图文件名（tex_normal=空表示该材质无法线）
x, y, z                  实例原点
qx, qy, qz, qw           旋转四元数（x,y,z,w 顺序）
sx, sy, sz               缩放
verts, tris              顶点 / 三角
bbox_min_* / bbox_max_*  该图元局部包围盒（未乘实例变换）
```

覆盖：38 分块 / **2 781 实例** / **2 091 材质**；有漫反射 16 391 行、有法线 14 825 行、有高光 13 984 行。
贴图实际文件在 `export/previews/sdn/textures/`（`_ab.png` 漫反射 / `_nm.jpg` 法线 / `_ma_orm.jpg` 高光+粗糙+AO）。

> ⚠️ glTF 里**没有 TANGENT 属性**（three.js 用屏幕导数自己算切线）。要求显式切线的引擎需另导一份。

**地标基准（用来验证坐标 / 朝向换算是否正常）**：圣丹尼斯大教堂 `new_com_church_bldg1`

| 项目 | 值 |
|---|---|
| 世界原点 | **(2751.44, −1270.93, 48.87)** |
| 世界 AABB | min (2733.92, −1288.07, 45.95) → max (2768.96, −1253.79, **101.82**) |
| 尺寸 | 35.04 × 34.29 × **55.88 m**（尖塔，一眼能认） |
| 旋转 / 缩放 | 单位四元数 (0,0,0,1) / (1,1,1) —— **未旋转** |
| 朝向 | 塔楼在中殿**西北端**，中殿轴线约 NW→SE |
| 整组（10 部件） | x 2720~2800 · y −1312~−1237 · z 45.9~101.8 |

配套参考机位与四向截图见 `sdn_landmark_church.json` 的 `reference_views`。

---

## 4. 坐标与单位（改任何数据前先看这条）

**RDR2 世界是 X 东 / Y 北 / Z 上，单位米，Z=0 是海平面**（负值是海床/湖底，最深 −34.9 m）。
骑砍2 的 up 轴不同，**必须先做标定再批量导**。

三种分辨率的换算（最容易搞错的地方）：

```
高度图 / 权重 / 水面   4 m/px：  col = (x + 6844) / 4        row = (3224 − y) / 4
地面彩图（完整）       1 m/px：  px  = x + 7684               py  = 4100 − y
地面彩图（高清）       0.5 m/px：px  = (x + 7684) × 2          py  = (4100 − y) × 2
大地图沙盘 ↔ 世界米             ：x = −7684 + u × 14.5 ; y = 4100 − v × 14.5
```

- 所有位图 **行 0 = 北**。
- 实例数组字段：`[hash, x, y, z, qx, qy, qz, qw, sxy, sz, cls]`，四元数顺序 **(x,y,z,w)**，Blender 要 **(w,x,y,z)**。
- 完整参数以 `export/world/bannerlord/camp_scenes.json` 为**唯一权威**（C# 里曾有常量偏 852 m，已改）。

---

## 5. 怎么用

### 5.1 看

```bash
双击 打开查看器.bat        # 起本地服务并打开首页（纯看图，零风险）
双击 打开大陆_流畅.bat      # Blender 里自己逛：默认无贴图（最快），载入约 13 秒
```

关掉那个命令行窗口即停止服务。所有页面都是静态的，没有后端。

**Blender 预览的"不卡"约定（2026-10-27 第 3 版：默认无贴图）**：

| 做法 | 结果 |
|---|---|
| **默认 = Solid 无贴图 + 按贴图平均色着色**（`color_type='MATERIAL'`，颜色表 `export/world/mat_avg_color.json`，6,327 个材质已着色） | ✅ 最快档；不会变成一片灰，地面绿/水蓝/木头褐都能分辨 |
| 地形/水面**视口减面 50%**（Decimate 修改器，不改网格数据，`tour.undecimate()` 可还原） | ✅ 946 万 → 552 万顶点 |
| 分区（26 块）+ 每块按尺寸分 3 档子集合，只切换集合 | ✅ 切区 **0.2~0.9 s**（逐个物体 hide 要 2.6 ms/个，已彻底弃用） |
| 密集地块自动降载（>2 万对象只留 ≥4 m 主体；>1.2 万去 <1.5 m 杂物） | ✅ 圣丹尼斯 22,017 → **3,945 个可见** |
| **★ 流式加载（默认）**：按相机位置只显示附近地块（半径 = max(1200, 视距×1.3)，上限 6 km；视距 >9000 m 只留地形） | ✅ 每 0.5 s 检查一次，**只在集合变化时才切集合**（实测 144 个集合切换 ≈ 0.00 s） |
| 面板「显示范围」按钮 | **★ 流式加载 / 全图 / 当前地块** 三选一；全图 ≈ 9.8 万对象，一般别用 |
| 想开贴图 | `tour.textured()`（更真实、更慢）；**只看地形**用 `tour.map_view()`（地面贴图 + 隐藏建筑，只有 2 个对象，又快又好看） |
| 直接按 <kbd>Z</kbd> 切 Material Preview | ❌ 最卡的一档 —— 要材质预览请用 `tour.material()` |

#### 分类开关（2026-10-27 新增）

ENTITIES 已按用途重建为「**分类 × 地块**」两级集合（`ENTITIES/C_<key>_<中文名>/<key>|<tile>`），
Blender 里 **3D 视图按 N → 「RDR2」页签** 就是开关面板（每类一个勾选框 + 4 个预设按钮）。

| key | 分类 | 对象数 | 说明 |
|---|---|---:|---|
| `prop` | 道具 | 50,028 | 桶/箱/桌椅/灯/标牌/干草堆/木桩… |
| `part` | 建筑部件 | 17,988 | 墙/屋顶/门廊/栅栏/楼梯/甲板/梁/木板/原木 |
| `junk` | 杂物堆 | 12,072 | debris / rubble / 破布 / 砖块碎屑 |
| `rock` | 岩石地形 | 7,421 | 岩石 / 巨石 / 崖壁 |
| `struct` | **桥梁结构** | 1,247 |
| `unknown` | 未分类 | 3,788 | 名字长尾（明细见 `export/world/classify_unmatched.csv`，**没有静默丢弃**） |
| `bldg` | 建筑 | 3,077 | 房屋/教堂/酒馆/银行/车站/工厂/仓库… |
| `veh` | 载具 | 2,344 | 马车/船/火车/手摇车 |
| `decal` | 道路地面贴花 | 2,412 | `*_decal*`（岩石贴花、路面补丁）—— **默认隐藏** |
| `veg` | 植被 | 1,261 | 残留杂草/常春藤（树已删） |
| `int` | **室内** | 12,543 |
| `rail` | 铁路 | 2,222 | 道砟地块/枕木/钢轨/桥/隧道/道岔 |

```python
tour.cat_show("贴花", False)   # 关某一类（支持中文名或 key）
tour.cat_show("道具", True)
tour.cat_show("铁路", True)
```

面板预设按钮：**全开 / 全关 / 只看人造物（建筑+部件+铁路+载具+道具）/ 去杂物贴花**。

> 分类规则在 `tools/classify_entities.py`（顺序：铁路 → **桥梁结构** → 贴花 → 植被 → 岩石 → 载具 → 建筑 → 部件 → 杂物 → 道具 → 未分类），
> 重新分类并落盘：`blender -b <blend> -P tools/classify_entities.py -- --apply --out <out>`。

Python Console 里：`tour.tiles()` 列分区 / `tour.only("wild2000_05_00")` 切区 /
`tour.jump(2989.5, 2189.4, 40)` 飞到夏洛蒂家 / `tour.show_all()` 全图 / `tour.solid()` 退回纯色 / `tour.material()` 安全的材质预览。

### 5.1c 补全缺失模型（2026-10-27）

大陆 52,653 个实体没有模型。本轮先吃掉「本地已有文件」的那部分：

| 步骤 | 工具 | 结果 |
|---|---|---|
| ① raw 里反查 | `tools/add_missing_models.py` | 1,223 个缺失实体的 `.ydr` 已在 `raw/`；排除 LOD/代理后转换 **+16 个模型**（库 52,582） |
| ② 实例化 | `tools/instantiate_missing.py` | 补入 **762 个对象**（铁路 **+737**，总数 1,484 → **2,221**） |

场景对象 103,189 → **117,765**（含 79 个室内包 12,543 件），文件 **10.60 GB**。

**室内模型已全部入库**（2026-10-27）：从 `levels_3.rpf` 解出 **146 个室内包 / 5,061 个文件**，
用 `tools/import_interior_lib.py` 批量导入 **+2,301 个模型**（库 → **54,893**）。
验证图 `deliverable/blender/continent/shots/interior_lib_sample.png`（房间壳/棚屋内壳/窗帘都是真几何）。
> 模型入库 ≠ 已摆放：室内仍需按 MLO `rooms/portals` 变换装配（见 §5.1d / 交接文档 §九）。

**缺口构成审计**（`export/world/missing_classified.json`）：52,627 个缺模型 hash 里，
2,133 个名字就像 LOD/代理，718 个像真模型（多数是室内 `_int`），另有 **49,776 个完全无名**。
用 `tools/scan_rpf_for_missing.py` 递归扫 `levels_2/3` 拿到 974 个候选，
转换后大量是 `_ph`/`_occ`/空 `.yft`（无几何） ⇒ **52,627 严重高估**，
真实可渲染缺口约 **700~2,000**，以室内为主。

### 5.1b 「桥面缺口」已澄清：不是缺几何（2026-10-27）

看到的"桥面缺口"对应实体 `0xe66d959c`，其 archetype 名是 **`new_pie_train_slod1_children`**
（SLOD 子集合容器，本就不该当几何渲染）；真正的桥面件 `shwb_bridge05_slope` / `_dec` / `_ground`
都在场景里，已归入「桥梁结构」。

**结论：桥和铁轨的网格本身完整**。铁路/桥资产集中在 `wild2000_04_02` 板——铁路件 350、
桥+栈桥 86；栈桥 `n_1114_r_b_tres00..08` → 桥 `bri01c` → 枕木 `n_1114_r_b_sle04..18`
沿一条线连续，间距中位 1.6 m / P90 22 m，只有道岔到正线之间有一段 73.8 m（正常）。

### 5.2 复现核心产物

```bash
cd "D:/BrainMaker/大镖客2解包分析"

# 地形 / 材质
uv run python tools/build_terrain_weights.py      # 权重图（顺带打印水陆 IoU，应为 1.0000）

# 主线 AVG
uv run python tools/build_avg_main.py             # 拆段 + 目标 + 台词 → avg_main.json
uv run python tools/build_avg_portraits.py        # 41 张立绘（Blender）
uv run python tools/build_avg_bg.py               # 2D 背景（需先起本地服务）
uv run python tools/audit_avg_bg.py               # 只校验/重建背景清单

# 剧情与任务
uv run python tools/recover_mission_scripts.py    # 补全 任务↔脚本 映射（内容验证）
uv run python tools/build_mission_flow.py         # 随机任务源码级还原
uv run python tools/build_random_mission_pack.py  # 150 个任务卡（骑砍2 数据包）
uv run python tools/build_ambient_events.py       # 119 个路上遭遇

# 地图标定
uv run python tools/fit_map_anchors.py --rerender

# 扁平表（实例变换 + 三张贴图，一行一个图元）
uv run python tools/build_flat_table.py --town sdn
```

脚本全索引见 `tools/README.md`（235 个 `.py`，按职责分 6 类）。

### 5.3 环境

RPF 工具直接读游戏本体：`H:\EPICGAMES\RedDeadRedemption2`（Epic 版）。
```
dotnet tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.dll list <rpf>
```

---

## 6. 已知缺口（诚实记录）

| 缺口 | 现状 / 证据 |
|---|---|
| **随机任务的触发条件** | 在哪个坐标、什么时段触发——走运行时全局数组，脚本里没有常量。**未解** |
| **过场演员初始站位** | `.yad` 原地表演根位移仅 ±0.02~0.05 m；`.ycd` 无坐标；过场资产里没有独立场景文件 |
| **逐镜成片时长 / 镜序** | `.yad` 是并列 take 不是时间轴；`.ycd` 有名字和时长但没有顺序 |
| **大部分任务的目标文案** | UILOG key 由 `func_262()` 从 `Global_1347702[i].f_3` 取，是运行时字符串（88/105 已从 yldb 取到） |
| **目标 → 游玩段的一对一归属** | 目标索引是运行时变量（`func_1812(iLocal_1838)`）；现按脚本步骤顺序/数量均分，`avg_main.json` 里用 `basis` 标注 |
| **过场相机世界变换** | 只有局部坐标（`pos=[24.7,-7.7]`），无法放进世界场景；AVG 用固定机位渲真实场景替代 |
| **45 个随机任务定位不到脚本** | 文件名与 id 对不上，内容里也没有该 id 的标签。已在还原器「缺失清单」列出 |
| **`.ysc` 原始脚本** | 仍未解（TFIT2 tag `0xC6`，密钥表缺）。现用的是**反编译产物**（1 639 个 `.c`），够用 |
| **地形贴合散差** | 「实体原点 − 地面」std ≈ 3.3 m，<2 m 只占 58%。平滑场救不回来，需按模型分类 |
| **未命名部件（已澄清：不是缺口）** | 旧说法「**49,778 种 / 50,007 实例**没模型」**已推翻**：其中 **46,532 个 hash / 46,536 个实例是 LOD 合并块**（`*_lod_combine_metadata*` 定义、bbox 中位 **64 m**、P90 128 m；磁盘上没有独立 `.ydr`，游戏运行时现场合并）。真实缺件只剩 **3,783 个实例**（`real_ytyp` 3,268 + `no_definition` 515）。证据与逐条明细见 `docs/世界与地编/RDR2_整图覆盖率核查_20261026.md` §10 与 `export/world/missing_classified.json`；口径脚本 `tools/audit_missing_models.py` |
| **白块** | 可装实例的 **36.5%（53,312）** 引用含 `tex_id=-1` submesh 的模型；灰白/纯白板 |
| **地面贴花 alpha 未接** | `_mat_for()` 只取 RGB，没把贴图 alpha 接到 BSDF Alpha → 污渍/贴花变不透明黑或白板。修法：`blend_method='BLEND'` + Alpha 连线（注意排序副作用） |
| **小道具贴图缺失** | 硬币/罐头/书/杯子：扫 25 个 props 包 + `gtxd.rpf` + 3,696 个 ytd 全无，用近似色代替 |
| **碰撞体** | 12 331 个 `.ybn` 已抽出，但**还没有转换器**（骑砍2 物理要用） |
| **兵种穿着配方** | `metapeds.ymt` 的 `PedComponentSetName` 指向的部件集未解 → **gameplay 兵种导不出模型**。清单/骨骼/表情都在，缺"穿哪几件"。详见 `docs/角色与物品/RDR2_载具与UI与兵种覆盖审计.md` §3 |
| **SP 武器数值** | base `weapons.ymt` 142 条记录几乎全是默认值（记录间只差 4 个字段），真实数值在嵌套 `CWeaponInfoBlob`，需给 `tools/pso_xml` 加指针/数组解析。**MP 24 条有完整数值** |
| **载具涂装色** | 车体 albedo 实际是 `*_control` 控制图；真实配色在 `carcols.ymt` / `carvariations.ymt`，未套用（现用中性深灰漆近似） |
| **UI 影片播放** | `.gfx` 是 Scaleform 字节码，本地播放需要 Scaleform 运行时；已给完整清单 + 配套图集 |
| **`screens.rpf` / `widgets.rpf` 内容** | 里面 862 个 .ymt 带签名保护（`signature protected`），只能列名，内容未解 |
| **PSIN meta（旧）** | `metapeds.ymt`、`assets_tints.ymt`（服装真配色）未解 |

> 完整 TODO 见 `docs/交接与状态/TODO.md`。

---

## 7. 文档怎么找

`docs/` 按主题分五类：

| 目录 | 内容 |
|---|---|
| `交接与状态/` | 交接说明、TODO、清理清单、**`RDR2_20261027_会话交接.md`（本轮最新）**、归档的满版 README |
| `世界与地编/` | 地形、材质、据点、圣丹尼斯地编、**沙盒大地图微缩模型规格**、**微缩模型经验与失败路径** |
| `任务与剧情/` | 过场解析、剧情线、**随机任务还原说明**、**主线 AVG 化与观看/游玩拆段**、搬运方案 |
| `格式与资产/` | RPF/RSC8/ydr/ycd 等格式破解记录 |
| `角色与物品/` | NPC、服饰、武器 |

**要动手前先读的两份**：

- `docs/任务与剧情/随机任务还原说明.md` —— 还原方法与边界（哪些是真、哪些解不出）
- `docs/任务与剧情/RDR2_主线AVG化与游玩阶段解析.md` —— 观看/游玩怎么拆、AVG 的素材从哪来
- `docs/交接与状态/资源清理清单.md` —— 哪些能删、哪些一个都不能动

---

## 8. 体积与清理

当前约 **115 GB**（2026-10-27）。较 10-23 的 97 GB 增加的部分主要是：

| 新增 | 体积 | 说明 |
|---|---|---|
| `deliverable/blender/continent/continent.blend` | **8.95 GB** | 共轭重建 + 铁路（原 8.38 GB） |
| `deliverable/blender/continent/` | 8.95 GB | 只有 `continent.blend` 一份（贴合/铁路都可用脚本复现） |
| `deliverable/blender/willard/` | 4.4 GB | willard / willard_full / roc_interior + 验收图 |

| 档 | 内容 | 体积 | 建议 |
|---|---|---|---|
| 已清 | 重复文件（同 md5，保留 canonical）+ Blender 备份 + 探针 | 回收 5.2 GB | ✅ 已完成 |
| `raw/towns` `raw/sdn` `raw/npc` `raw/story` | 已抽完的原始解包 | ≈ 45 GB | 确认不重抽就外置归档 |
| 其余 `raw/` | 碰撞/贴图源/模型源 | ≈ 18 GB | 骑砍2 要用，建议留 |

> ⚠️ 反例：`raw/towns/*/gtxd_x`（2.2 GB）名字像残留，实测 **477 个文件 0 个有副本**，是独有贴图，**没删**。
> 按名字猜"重复"会删错，必须按 md5 比对。

---

## 9. 变更历史（压缩）

| 日期 | 做了什么 |
|---|---|
| 10-17 | 骨骼动画解码（4 个 bug 叠加）、NPC 解包、剧情对白 |
| 10-18 | 圣丹尼斯整城 + 27 室内、地形与材质第一版 |
| 10-21 | 整块大陆装配、网页查看器合并为单一入口 |
| 10-22 | 高度图 v2、7 层材质权重、据点名单修正、全服饰清单 |
| 10-23 上 | 过场资产解析（668 过场 / 2 199 镜头）、说话人覆盖 94.3% |
| 10-23 中 | 随机任务盘点（150 个）、坐标管线、清理 5.2 GB |
| 10-23 下 | **删除自创玩法，改为源码级还原**（105/150，1 398 句原文台词） |
| 10-24 | **载具 108 个 / UI 1 922 张纹理 / 兵种 1 086 清单** 三块补上；新写通用 PSIN 导出器 `tools/pso_xml`；三块都新建了页面 |
| 10-25 | **主线拆「观看/游玩」两段**：解出脚本过场段链（800 段）+ 逐句说话人 + 748 张步骤卡；新做 AVG 播放器、游玩手册、41 张立绘、62 张真实场景背景 |
| 10-25 补 | **建筑材质 PBR 化**：此前只导 albedo、roughness 恒 0.85/无高光无 AO（圣丹尼斯"塑料廉价"）→ 补 `_nm` 法线（翻 G）+ `_ma`→ORM，圣丹尼斯 4923 材质中法线 3811 / ORM 3447；查看器加 PMREM 环境光 + 跨分块贴图去重；新增扁平表与地标基准。详见 `docs/世界与地编/RDR2_圣丹尼斯地编破解.md` §5.9 |
| 10-25 下 | **沙盒大地图微缩模型**：46 据点各出 1 个 GLB + 1 张贴图（84 502 面），GoT 式开场运镜大地图（同屏 298 784 面 / 47 draw）；7.0.1 规格从「两把尺子」改成「按像素给预算」 |
| 10-26 | **微缩模型返工 6 轮**（方块→真实网格→乐高→街区积木），结论全部写进 `docs/世界与地编/RDR2_微缩模型_经验与失败路径.md`：①单城真实模型已存在（`export/previews/` 43 城 2.61 GB），**不该重造**；②大地图正确做法是「远景占位 + 聚焦时按需加载 `previews/<code>/tiles/`」；③若要轻量版，形状靠平面消融能保（2 650 万→270 万面），但材质 5 076 个必须打图集 |
| 10-27 | **复核并推翻两条旧结论**：① 铁路不是"没解包"，是 `flat_wide` 剔掉了 1,024/1,359 → 新增 `--rails` 开关 + 修 `add_rail_network.py` 旋向，`continent.blend` 已装回 **1,359 件**（8.95 GB / 场景 114,015 对象）；② 5 万未命名不是"LOD 代理"，是真没抽（ytyp 已覆盖 99.6%）。同时实测**铁路验证不了四元数共轭**（97.6% yaw=0） |
| 10-27 下 | **夏洛蒂家三个问题的全图核查**（§0.8）：① 旋向 **386/386 只用共轭 → 全图已解决**；② 陷地根因 = PAD 压低地形 1.12 m（63.9%），新增 `tools/fit_terrain_to_buildings.py` 地基台法，纯房屋贴地 **17.3%→47.0%**，`continent.blend` 已应用；③ 室内 **144 包只完成 1 包**，且当年用的是替身实例（yaw 差 100°）+ 强制居中"补"出来的对称，真实例直接装会偏出屋顶 → 还缺 rooms/portals 变换。新增 `locate_interior_mlo.py`（136/144 可定位）、`merge_interior.py` |
| **10-29** | **推翻「5 万未命名缺口」，并根修三处身份/显示问题**：① ytyp 按对解析 96,141 条 → `name == assetName` **100%**（没有第二个名字）；② 新建 `rdr2rpf hashindex` 原地读嵌套 TOC，扫出 **4,021 个 RPF / 74,449 条 drawable**，缺模型里能命中的只有 1,834 且几乎全无几何；③ `audit_missing_models.py` 分桶：**46,532 个 hash / 46,536 实例是 LOD 合并块**（非缺口），真缺口 **3,783 实例**、圣丹尼斯 **283**（旧验收线 <300 达成）；④ 材质改为 `alb_<贴图名>` + **一子网格一槽**（根修"门长草"）；⑤ 修 `index.json` 未补零 key（**找回 367 个模型**）、Workbench 白块（`diffuse_color`）、水面灰板、地图外 `*_tempbox*`（→`HIDDEN_PARKED`）、`privy` 误判植被、新增 `--bbox`；⑥ 重建 `continent_v9.blend` |

> 每一轮的详细结论、踩坑记录、原始数字都在
> `docs/交接与状态/README_归档_满版_20261023.md`（1 040 行），需要时再翻。

---

## 10. 给下游（骑砍2）的交接

先看 `README_骑砍2交接.md`（数据契约：高度图/材质权重/建筑坐标/贴图怎么取、字段含义、LOD 建议）。

三条铁律：

1. **别把 20 万个实例按 LOD0 全摆进去** —— 那是 300 M+ 三角面，任何引擎都跑不动。
   按分级/剔除做，单个城镇场景目标 ≤ 60 万面。
2. **网格只有 HD，没有 LOD 链** —— 10 893 个 archetype 里 92.5% 有网格，且每个只有最高精度，
   LOD1~6 要自己减面。
3. **先做坐标标定再批量导** —— RDR2 与骑砍2 的 up 轴不同；换算参数以
   `export/world/bannerlord/camp_scenes.json` 为准（不是 C# 里的常量）。

随机任务的搬运方案见 `docs/任务与剧情/RDR2随机任务搬运到骑砍2_方案.md`；
任务内容一律以 `mission_flow.json` 的还原数据为准，**不得自行编造数值或玩法**。
