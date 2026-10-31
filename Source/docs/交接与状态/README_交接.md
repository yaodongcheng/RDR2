# 荒野大镖客 2 · 解包分析交接 README

> 最后更新：**2026-10-30**
> 项目根：`D:\BrainMaker\大镖客2解包分析`
> 游戏：`H:\EPICGAMES\RedDeadRedemption2`（Epic）
>
> **一句话状态**：世界地图 / 43 据点 / **43 个据点 3D 预览** / **49 块野外分块 + 任意地点扎营** / 8 势力 / 142 具名角色 / 270 条任务（含脚本级、逐步骤、任务树、对白归属）/ 181 过场 / 45 武器 / 916 道具 / 408 角色模型 / 圣丹尼斯整城 / 14 页查看器，全部落地。
> **仍未解决**：任务字节码 `.ysc` 本地解密、对白"说话人"哈希映射、spawn 模型名与实体身份。

> 📌 **本轮的专项交接**：**§13（2026-10-30 · 槽位法线/高光补全 + v12）**
> （旧：§11 分类重排 / §12 13 类重构；`交接_角色与服饰与查看器_20261023.md`）

---

## 1. 三十秒上手

### ① 综合查看器（推荐）

```
双击项目根目录「打开查看器.bat」
（或 根目录「打开查看器.bat」）
→ http://127.0.0.1:8788/viewer/index.html
```

12 个页面：

| 分组 | 页面 |
|---|---|
| 总览 | 成果概览 |
| 世界与叙事 | 世界地图 / 据点势力名册 / 剧情任务 / 对白 / 过场动画 |
| 资产 | 武器 / 道具 / 角色模型 / 场景·圣丹尼斯 |
| 资料 | 文档中心 / 数据产物 |

- **剧情任务**：章节筛选 + 搜索；单任务看「目标清单 → 任务树 → 微步骤事件 → 对白 → 失败条件 → 挑战 → cast」。
- **3D 页面**：武器、道具、408 个角色 GLB，旋转/缩放/截图。
- **文档中心**：31 篇 Markdown 已渲染成带目录的网页。
- 必须走 bat（http）；直接双击 HTML 会因模块路径与 fetch 限制白屏。改数据后 **Ctrl+F5**。

### ② 全据点 3D 预览（新）

```
http://127.0.0.1:8788/previews/index.html
（综合查看器 → 资产 → 全据点 3D 预览）
```

43 个据点，同一套圣丹尼斯管线导出；左侧按档位分组（大城市 / 城镇 / 城堡 / 庄园 / 牧场 / 藏身处 / 小屋），
每镇带真实地貌底板（全图地面色贴图）、实例数 / 模型数 / 体积。圣丹尼斯：6 606 实例 / 2 819 模型。

### ③ 任意地点扎营（新）

```
http://127.0.0.1:8788/world/camp.html
（综合查看器 → 世界与叙事 → 任意地点扎营）
```

- 大地图点任意位置 → 算出「块 + 场景坐标 + 骑砍2 入口 JSON」；
- **点「在此扎营」**：落在据点半径内 → 黑屏过场进该镇 3D 场景；否则进野外场景并提示最近据点距离；
- 侧栏「前往 XX（距离）」可一键从野外进镇；
- 操作：`W/A/S/D` 走、`Shift` 加速、`Q` 升高 / `E` 降低、拖拽转视角；
- 右上角小地图（380 px）按**真实尺寸**画出据点范围并按类型着色/标名；**点据点直接进该场景**，点空地按坐标落点；
- 水面：湖=分位水位、河=贴床，可开关（`隐藏水面` 按钮）；
- 野外默认 **2000 m × 7×7 = 49 块**，精细档 **848 m × 15×15 = 225 块**（右上角可切）；
- **重要城镇不参与网格切分**：15 个据点各有「以自己为中心」的锚定场景（圣丹尼斯 3000 m、庄园/要塞 1200 m、城镇 1000 m），
  落在框内直接进据点场景；小地图上色块=锚定场景、细线=野外网格；
- 块外两级 LOD apron 一直铺到 7 km，配线性雾 —— 边界外不是虚空；
- 「关闭 apron」按钮是对照组，「边界测试」直接站到块边缘朝外看。

### ④ 圣丹尼斯整城（Blender）

```
export/levels/world/blender/sdn.blend          2.4 GB，Blender 5.2
export/levels/world/blender/preview/*.png      8 张成品图
export/levels/world/blender/sdn_report.html    图文报告
```

打开后：选中 `Terrain` → `Numpad .`；`N` → Clip End 改 20000；空格播放电车/火车。

### ⑤ 文档入口

- 本文 = 交接入口
- `README.md` = 早期资产提取总记录（几何/动画/骨架/贴图等专项）
- `RDR2_任务逐步骤拆解_WNT1.md` = 单任务从目标到微步骤事件的完整样例

---

## 2. 这一轮新增（2026-10-19）

| 能力 | 结果 | 产物 |
|---|---|---|
| **`.yldb` key→string** | 打通 hash→node→string 结构 | `tools/yldb_keys.py` |
| 任务中文名 / 简介 | **250 / 250** 条（270 条中） | `export/levels/world/missions_story.csv` |
| 任务挑战 | **308 条**（105 主线全覆盖） | `export/levels/world/mission_challenges.csv` |
| 玩家目标 / 失败条件 | **637 + 443 条** | `export/levels/world/mission_objectives.csv` |
| 脚本级解析 | **194 条任务**，主线 **105/105** | `export/levels/world/mission_scripts.csv` |
| 脚本目标 / 失败 | **1,054 / 318 条** | `export/levels/world/mission_scripts.json` |
| 逐步骤拆解 | **43 任务 / 215 步** | `export/levels/world/mission_steps.csv` |
| 微步骤事件 | **4,725 条**（TASK/CREATE/演出/转场/对白） | `export/levels/world/mission_events.csv` |
| 事件价值分级 | S 结构 / A 可见表演 / B 不可见管线 | `export/levels/world/mission_events.json` 的 `value` |
| 任务树 | **215 大步骤 / 1,102 小步骤** | `export/levels/world/mission_tree.json` |
| 对白按步骤归属 | **38 任务 / 1,378 组 / 6,224 行** | `export/levels/world/mission_dialogues.csv` |
| 成果查看器 | 12 页 + 31 篇文档渲染 | `export/viewer/` |

---

## 3. 任务解析的四层模型

```
① 定义层  missions.meta                 → 270 条任务、分类、过场包
② 目标层  各任务 <id>.yldb              → 637 条玩家目标、443 条失败提示
③ 脚本层  反编译 .c（build 1355）       → 1,054 条脚本目标、318 条失败、生成/行为
④ 调度层  阶段函数 + switch case + 事件 → 任务树、微步骤事件、价值分级
                 ↓
        对白层  对话组 + 字幕 yldb       → 1,378 组 / 6,224 行（按步骤归属）
```

### 任务树（总任务 → 大步骤 → 小步骤 → 执行）

| 层级 | 对应脚本概念 | 例子（WNT1） |
|---|---|---|
| 总任务 | `missions.meta` | 西部亡命之徒 `WNT1` |
| 大步骤 | 设置目标的阶段函数 | 步骤 1 `func_793` 跟随迈卡 |
| 小步骤 | 该函数的 `switch` 状态 | 前置 / case 0 / case 1 / case 2 |
| 执行 | 展开后的 TASK/CREATE/演出/对白 | `TASK_FOLLOW_NAV_MESH_TO_COORD(...)` |

> 这是**静态代码树**：前置与 case 是并列分支，不代表某一次游玩的单一路径。

### 事件价值分级

| 级别 | 内容 | 用途 |
|---|---|---|
| **S 结构与空间** | 目标、转场、带坐标走位、带资源生成、过场播放 | 直接重建 |
| **A 可见表演** | 转身、注视、站姿、动作序列、战斗/掩体、武器/马匹、等待 | 必须还原 |
| **B 不可见管线** | 资源加载、清除注视、状态查询、AI 分组/配置 | 可跳过 |

WNT1 示例：**S 189 / A 57 / B 31**（含 21 条对白事件）；TURN 111 条、LOOK_AT 78 条**全部为 A**，B 中没有任何 TURN/LOOK_AT。

---

## 4. 当前状态总表

| 域 | 状态 | 关键数字 | 入口 |
|---|---|---|---|
| **地形 / 大地图** | ✅ | 30,697 patch；1024² 高程；848×848 地图 | `RDR2_世界地图与据点浏览.md` |
| **据点 / 城镇** | ✅ | **43 条**：10 城 / 11 堡 / 12 村 / 4 营地 / 4 点位 / 2 藏身处 | `RDR2_据点与城镇清单.md` |
| **势力 / NPC** | ✅ | **8 势力**；**142 具名**；408 个角色模型；75 条服务语音库 | `RDR2_骑砍2落地_势力与NPC.md` |
| **剧情任务** | 🟢 | 270 条；脚本级 194；步骤 215；事件 4,725；树 1,102 | `RDR2_剧情任务解析.md`、`RDR2_任务调度解析.md`、`RDR2_脚本级任务解析.md` |
| **对白** | 🟢 | 41,005 行任务对白；1,378 组归属；说话人未映射 | `RDR2_剧情任务解析.md`、`export/levels/world/mission_dialogues.csv` |
| **武器** | 🟡 | 45 把完整模型 + 142 法线；289 模型资产；45 中文名 | `RDR2_任务逻辑与武器道具破解.md` |
| **道具** | 🟡 | 2,071 模型；916 个背包项；446 albedo | `RDR2_武器道具模型与剧本对白.md` |
| **圣丹尼斯地编** | ✅ | 2.4 GB blend；23,159 对象；62.77M 顶点；27 套室内 | `RDR2_圣丹尼斯_还原度提升总结.md` |
| **综合查看器** | ✅ | 12 页；31 篇文档；408 角色 / 45 武器 / 916 道具 | `export/viewer/index.html` |

---

## 5. 交付物清单

### 5.1 查看器

| 路径 | 内容 |
|---|---|
| `export/viewer/index.html` | 12 页成果总览 |
| `export/viewer/site.json` | 统一数据（任务/武器/道具/角色/据点/过场/文档/图集） |
| `export/viewer/docs/` | 31 篇 Markdown 渲染页 |
| `export/viewer/models/weapons/` | 45 把武器 glTF + 142 法线 |
| `export/viewer/models/items/` | 916 道具 glTF + 446 albedo |
| `export/viewer/dialogue/` | 129 个任务对白 |
| `export/viewer/dialogue_unmatched/` | 173 个活动音频库对白 |
| `打开查看器.bat` / `根目录「打开查看器.bat」` | 一键入口 |

### 5.2 任务 / 对白

| 路径 | 内容 |
|---|---|
| `export/levels/world/missions.csv` | 270 条任务定义 |
| `export/levels/world/missions_story.csv` | 270 条：章序 / 中英标题 / 中英简介 / cast / 对白 / 挑战 |
| `export/levels/world/mission_challenges.csv` | 308 条任务挑战 |
| `export/levels/world/mission_objectives.csv` | 637 目标 + 443 失败 |
| `export/levels/world/mission_scripts.csv` | 194 任务 → 脚本 / 行数 / 函数 / 目标 / 失败 / 生成 |
| `export/levels/world/mission_steps.csv` | 43 任务 / 215 步 |
| `export/levels/world/mission_events.csv` | 4,725 条微步骤事件（含 value 分级、坐标、条件） |
| `export/levels/world/mission_tree.json` | 4 层任务树（215 大步骤 / 1,102 小步骤） |
| `export/levels/world/mission_dialogues.csv` | 1,378 组对话 / 6,224 行（含条件触发标记） |
| `export/levels/world/mission_cast.csv` / `export/levels/world/cutscene_cast.csv` / `export/levels/world/actor_coverage.csv` | cast 与角色出场统计 |
| `export/story/mission_dialogue/` | 129 个任务对白 |
| `export/story/dialogue_chinesesimp.txt` | 全量原始对白（339,635 条，含噪声） |

### 5.3 世界 / 据点 / 场景

| 路径 | 内容 |
|---|---|
| `export/levels/world/settlements_bannerlord.csv` | 43 据点（类型/依附/势力/领主） |
| `export/levels/world/npc_roster.csv` | 142 具名角色 |
| `export/levels/world/factions.json` | 8 势力 |
| `export/levels/world/faction_map.png` / `export/levels/world/settlements_map.png` | 势力图 / 据点分布 |
| `export/levels/world/blender/sdn.blend` | 圣丹尼斯整城 2.4 GB |
| `export/npc/index.csv` + `export/npc/*.glb` | 408 个角色模型 |
| `export/weapons/models/` / `export/items/models/` | 武器 / 道具资产 |

---

## 6. 关键结论（别再踩）

1. **任务定义是 270 条，不是 105**：105 主线 + 121 支线/赏金 + 21 物品 + 15 配方 + 8 线上。
2. **过场 181/181 已解**，clip 名里带角色 ID，可反推 cast。
3. **`.ysc` 仍为 0**：`script_rel.rpf` 已从 `update_2.rpf` 抽出（113 MB，tag `0xC6`），差 AES key #198。
4. **任务名/简介在 `global.yldb`**：key→string 结构已打通，WNT1=西部亡命之徒、MUD1=东部边境。
5. **脚本目标前缀不一定等于任务 ID**：MUD6→`MUD3B_*`、DST3→`ODR3_*`，需按“能否解析出中文”自动识别。
6. **步骤顺序按“目标函数最早调用行”**，不是引擎状态机顺序。
7. **TURN/LOOK 是可见表演**：111 条 TURN、78 条 LOOK_AT 全部归 A；B 只剩加载/清理/查询/AI 配置。
8. **对白说话人未解**：会话表在 `audio/conversations.rpf`（18,417 个 PSIN），说话人哈希不映射到 `names.txt`。

---

## 7. 已知缺口（按优先级）

| # | 缺口 | 影响 | 下一步 |
|---|---|---|---|
| 1 | **`.ysc` 本地解密** | 触发器/生成/分支的**运行时**语义 | 补 tag `0xC6` 的 AES key，或 CodeX 反编译 |
| 2 | **对白说话人哈希映射** | 每句台词说不出“谁在说” | 解 PSIN voice/actor 引用表 |
| 3 | **spawn 模型名 / 实体身份** | `CREATE_PED` 不知道刷的是谁；`uLocal_1064[1]` 不知道是达奇还是迈卡 | 回溯 spawn 包装函数参数 / 槽位赋值 |
| 4 | **权威选项类型** | 目前只有启发式“选项候选” | 解会话 PSIN 的行类型字段 |
| 5 | yldb 物品 key 表 | 道具精确官方名 | 补 key→string |
| 6 | 武器 palette/tint | 武器颜色非逐把精确 | 实现 `_pal/_eg` |
| 7 | `metapeds.ymt` | 任务专用 ped 不能精确还原 | PSIN schema |
| 8 | MLO 门/房间 | 圣丹尼斯室内不能真正进门 | ytyp rooms/portals |

---

## 8. 复现命令

```bash
cd "D:/BrainMaker/大镖客2解包分析"

# 任务 / 对白 / 调度 / 树
uv run python tools/build_mission_story.py
uv run python tools/build_mission_objectives.py
uv run python tools/build_mission_scripts.py
uv run python tools/build_mission_steps.py
uv run python tools/build_mission_events.py
uv run python tools/build_mission_tree.py
uv run python tools/build_mission_dialogues.py

# 合并到查看器 + 生成文档页
uv run python tools/patch_viewer_missions.py
uv run python tools/build_viewer_site.py

# 世界 / 据点 / NPC（按需）
uv run python tools/build_bannerlord_factions.py
uv run python tools/build_settlement_list.py
uv run python tools/build_npc_viewer.py
```

RSC 工具：`tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe`
Oodle：与 exe 同目录 `oo2core_5_win64.dll`

---

## 9. 文档地图

### 9.1 当前主线（2026-10-19）

| 文档 | 管什么 |
|---|---|
| **README_交接.md**（本文） | 状态、入口、交付物、缺口 |
| `RDR2_剧情任务解析.md` | 主线逐章 + 支线逐线：标题/简介/cast/挑战/对白 |
| `RDR2_任务执行逻辑还原.md` | 玩家目标 + 失败条件（637 + 443） |
| `RDR2_脚本级任务解析.md` | 194 脚本、1054 目标、318 失败、生成/过场/native |
| `RDR2_任务调度解析.md` | 1,985 生成点 / 27,977 行为 / 324 阶段 |
| `RDR2_任务逐步骤拆解_WNT1.md` | WNT1 11 步 + 微步骤事件 + 对白 |
| `RDR2_剧情与角色覆盖审计.md` | 270 任务、181 过场、cast 覆盖 |
| `RDR2_据点与城镇清单.md` | 43 据点、场景尺寸、档位映射 |
| `RDR2_骑砍2落地_势力与NPC.md` | 层级、8 势力、142 NPC、服务语音库 |
| `RDR2_任务逻辑与武器道具破解.md` | 任务挑战、CWeaponInfo、弹药、道具 schema |
| `RDR2_武器道具模型与剧本对白.md` | 模型数量、对白拆分、导出 |
| `RDR2_模型图标与综合查看器.md` | 查看器、中文名、贴图、对白归属 |

### 9.2 地编 / 世界

`RDR2_世界地图与据点浏览.md` · `RDR2_整图还原_机器时间与架构.md` · `RDR2_地编还原方法论_v1.md` · `RDR2_圣丹尼斯地编破解.md` · `RDR2_圣丹尼斯_还原度提升总结.md` · `RDR2_圣丹尼斯还原度盘点.md`

### 9.3 格式 / 资产管线

`RDR2_ydr几何格式.md` · `RDR2_ycd动画解码.md` · `RDR2骨架_yft格式.md` · `README_贴图与材质管线.md` · `README_NPC与剧情解包.md` · `HANDOFF_动画与蒙皮.md` · `TODO.md`（历史待办）

---

## 10. 交接 Checklist

- [x] 地形 / 848 大地图 / 225 瓦片
- [x] 43 据点 + 场景尺寸 + 档位
- [x] 8 势力 / 142 具名 / 408 模型
- [x] 270 条任务定义 + 308 挑战
- [x] 任务中文名/简介 250 条
- [x] 玩家目标 637 + 失败 443
- [x] 脚本级 105/105 主线
- [x] 逐步骤 215 步 / 任务树 1,102 小步
- [x] 微步骤事件 4,725 条 + S/A/B 分级
- [x] 对白 41,005 行 + 1,378 组按步骤归属
- [x] 181 过场包 / 45 武器 / 916 道具
- [x] 圣丹尼斯整城 + 27 套室内
- [x] 12 页查看器 + 31 篇文档
- [ ] `.ysc` 解密
- [ ] 对白说话人映射 / 权威选项类型
- [ ] spawn 模型名与实体身份
- [ ] 道具精确官方名 / 武器 tint
- [ ] 圣丹尼斯 MLO 门 / 水位 / 马车

> 交接建议：先看 §1 打开查看器；需要核对数字就看 §2/§4；要复现看 §8；**不要从零重抽**，`work/` 与 `export/` 都在。

---

## 11. 2026-10-29 · 分类重排 + 地面覆盖抬高（v10 → v11）

> 本节是 **2026-10-29 上午**那一轮的交接（分类重排 + 地面覆盖）。
> **下午那一轮（分类体系重构 → v11）在 §12**。**不要再新建 `HANDOFF_*.md`**（规范：交接只写本文）。
> 写这一节的 agent 没有 H 盘写权限、也起不了子进程，所以下面全部写成可直接执行的形式。

### 11.1 背景与结论（已实测，不用重测）

`deliverable/blender/continent/continent_v10.blend`（7.38 GB）里，厂区 `new_wrh_03_ext_dec_03`
下方地面发黑。已定位三件事：

- **不是隐藏、不缺几何**：该点 11 个对象 `visible_get()` 全为 `True`（含 `Terrain`、`new_wrh_rds_09`、两层 decal）。
- **黑的是 `Terrain` 的地面色图没数据**：`export/world/world_ground_final.png` 在厂区那块是**纯黑**（RDR2 城区街面本来就不在地形色图里，由路面/场地模型盖住）。
- **同时存在 z-fighting**：`Terrain` 顶点 z **45.404 … 45.460**（中位 45.432），
  路面 `new_wrh_rds_09` z **45.04 … 45.57** —— 只差 **1~5 cm**，黑地形在若干小块上“赢”了。
- **用户拍板**：走「抬高地面覆盖」，**不动地形高度**（§6.2 禁令）。

### 11.2 根因之一：分类表漏了 RDR2 的缩写族

`unknown` 有 **7,221** 个对象。审计文件 `export/world/classify_unmatched.csv`（35,691 行）里，
`_rds_`（路面族）就占 **79 条**：`new_wrh_rds_09`、`new_com_rds_01b`…、`new_frn_rds_*`、
`new_gar_rds_*`、`new_slm_rds_*`、`new_pie_rds_wood`。也就是说**路面本体一直没被分类**。

**要做**：`tools/classify_entities.py` 的 `RULES` 扩 token（**只加不改序**）——
`rds fnc pst mos _doc tanks airshaft genframe walkway rubbish _floor planter bron rail01x`。

验收：`--report` 后 `unknown` 明显下降（≥ −1,000）、`decal` 从 2,713 上升；
确认后再 `--apply --out continent_v11.blend`（**不覆盖 v10**）。

### 11.3 抬高地面覆盖（用户已授权）

新建 `tools/raise_ground_cover.py`：只对集合 `C_decal_道路地面贴花` 的网格设
`delta_location.z = +0.05`，提供 `--report / --apply --dz / --undo`；
**不碰 bldg/struct/rail/veh/prop**，不改地形高度，可一键还原。
建议顺序：先 `--report` 报数量 → 用户确认 → `--apply` → 重跑 manifest → 视觉复核厂区 / 圣丹尼斯街面 / 码头。

### 11.4 本轮实测到的 4 个 bug

| # | 现象 | 位置 | 修法 |
|---|---|---|---|
| 1 | 所有 `alb_*` 材质 `diffuse_color` 仍是默认 (0.8,0.8,0.8) → Solid/MATERIAL 模式**全白灰** | `tools/relink_materials.py` | 建材质时按**贴图名**查平均色写 `diffuse_color`；平均色表键从旧 `m_<tid>` 改成**贴图名** |
| 2 | `flat_colored()` 平均色表**永不命中**（键是旧 tid，材质已叫 `alb_<名字>`） | `tools/blender_tour.py` | `if nm.startswith('alb_'): table.get(nm[4:])`，并保留 `nonalbedo_warmgray`/`water` 特例 |
| 3 | 面板「全图/勾选」只改集合 → **8.6 万对象仍是对象级隐藏**（`ENTITIES` 可见 20,750 / 107,334） | `blender_tour.show_all()`、`rdr2_cat_ui.py` | 恢复可见时同时 `o.hide_set(False)` |
| 4 | 面板里两个「植被」同名（10,860 的 `HIDDEN_VEG` 与 1,244 的 `C_veg_植被`） | `tools/rdr2_cat_ui.py` | 文案改「旧植被集合 (N，已隐藏)」 |

### 11.5 待提交改动（提交权在用户，见 `docs/AGENTS.md` §0）

`Source\AGENTS.md`、`Source\docs\AGENTS.md`（新增 **§0 提交权** + §4 八个坑 + §5 自检项）、
`Source\launchers\{打开大陆_流畅,打开夏洛蒂家_完整,打开查看器}.bat`（项目根多候选 + 路径全加引号 + 兜底 v10）、
`Source\tools\blender_tour.py`、`Source\tools\blender_autoload.py`（视口裁剪默认改 **2 m / 20000 m**）。

远程最新 commit：**`cacf205`**。AI **禁止** `git add/commit/push`，由用户用 `git_gui.py` 提交。

---

## 12. 2026-10-29 · 分类体系重构（13 类）+ 三处性能修复 + 一处待查

> 这一轮只动"分类/隐藏/清单"这一层，**几何、地形、材质一个字节没改**。
> 产出：`continent_v11.blend`（7.0 GB）+ `manifest_continent_v11.json`。

### 12.1 分类从"垃圾桶制"改成"划分制"

**旧做法**（v10 及以前）：分类完再跑 3 个脚本，把植被/地形块/远景碎片**搬出** ENTITIES 塞进
`HIDDEN_VEG` / `HIDDEN_TERRAIN_CELL` / `HIDDEN_LOD`。后果：被搬走的对象**不再属于任何类别**，
面板出现"两个植被"，任何按类统计都对不上。

**新做法**：一个对象**有且只有一个类别**；"藏"= 给这个类设默认不显示，**不搬对象**。
- 新增两类：`lod`（远景碎片 2,248）、`terrain_cell`（地形块 30,549）——它们本来就是被搬走的那批
- `veg` 判定收窄：盆栽 `p_pot_*`、花艺 `flowerarng*`、装饰 `p_cs_*` 是**道具**，归 prop
- `decal` 补 token：`_rds/_dec/_dcl/_ground/street/road/path`（+501）+ **几何兜底**（+341）：
  面积 ≥10 m²、厚 ≤1.5 m、厚/长边 ≤0.06、底面离地 ≤1.0 m，排除 water/litter/debris
- 新增 `LEFTOVER` 兜底规则：只对前面都没中的对象生效，可给旧类补 token 而不抢既有归属

**结果**：`unknown` 35,757 → **6,341**（其中 3,301 个是 `e_<hash>`，名字本身解不出）。

### 12.2 三处性能问题（都是 Blender 慢 API）

| 问题 | 实测 | 修法 |
|---|---|---|
| `ob.users_collection` 每对象 | **8.7 ms** → 15 万个 = 21 分钟 | 先遍历集合建表，循环里查字典；写清单 47 分钟 → **20 秒** |
| 面板开关重设全部 13 类 | 每次碰十几万对象 | 每类独立回调，只动被点的那一个 |
| `col.hide_viewport` / `col.hide_render` | 4.0~10 秒 / **6.3 秒** | 开关改用**视图层眼睛** `lc.hide_viewport` → **0.68 秒**；`hide_render` 拆成单独的「同步渲染可见性」按钮 |

🔴 **通用教训**：Blender 里凡是"每个对象调一次"的 API（`users_collection`/`hide_get`/`visible_get`）
在 15 万对象规模上都是分钟级；一律改成"先遍历集合建表，再查表"。

### 12.3 修掉的两个真 bug

1. **中文界面会崩**：`node_tree.nodes['Principled BSDF']` 在 `zh_HANS` 下取不到（叫「原理化 BSDF」）→
   全量重建在第一个模型上就 KeyError。已改成按 `node.type == 'BSDF_PRINCIPLED'` 找（`_bsdf()`）。
2. **面板"地形块"开关不存在**：集合名 `C_terrain_cell_地形块` 被 `split('_',2)` 切成 key=`terrain`。
   已改成按已知类名匹配。

### 12.4 ~~尚未查清~~ → 已解决（见 §16）

**现象**：v11 里某处俯视出现"绿白碎片化"的地表；**同样的位置在 v8 里看着是连续地形**。

**结论（2026-10-30）**：不是地形网格，是**启动器把默认隐藏类重新打开了**，
外加 `cats()` 把 `C_terrain_cell_地形块` 解析成 key=`terrain`（见 §16）。

留下的两条事实仍然有效：
- `Terrain` **不是连续网格**：构建时按 `ground_mask` 剔面（9,449,476 → 7,870,374，剔掉 158 万面）；
  遮罩实测 **83% 有地面 / 17% 空洞**，空洞是地图外的纸边角（`docs/世界与地编/地形高度图与材质权重图.md` §1）
- 该遮罩逻辑 v8 就有，**不是某一轮引入的**

### 12.5 环境事故（与本轮代码无关）

- 2026-10-29 11:32:55 机器内核崩溃（`0x1E`，参数 `c0000005` 空指针），当时正在跑全量重建。
  内存 64 GB 未耗尽、7 块 SSD 全健康；系统装有**青骓数据检测与响应系统**（`QzhddrDrv64.sys`，
  文件过滤驱动，altitude 482370 最高），重 I/O 时触发其缺陷的可能性最大。
- 全量重建实测速率随场景增长而下降（11.5 → 24 → 31.5 ms/模型），按当时进度推算全程约 30 分钟。

### 12.6 待提交文件（11 个）

`Source/tools/`：`classify_entities.py`、`veg_rules.py`（新）、`strip_vegetation.py`、
`hide_terrain_patches.py`、`hide_lod.py`、`write_manifest.py`、`manifest_from_jsonl.py`、
`report_manifest.py`、`rdr2_cat_ui.py`、`blender_continent.py`

AI **禁止** `git add/commit/push`，由用户用 `git_gui.py` 提交。

---

## 13. 2026-10-30 · 槽位法线/高光补全（v12）

> 触发：用户问"网格每个槽位的漫反射、法线、高光贴图都有吗"。
> 实测答案：**只有漫反射（槽位 97.73%）**，法线/高光 **0**。本轮补齐。

### 13.1 根因（一句话）

`assets/lib_native` 的 `.mdl` 每个子网格**只存一个 texId**（`SUB` = `texId,vc,ic,pos,nrm,uv,idx`），
`dump_model_lib.write_model()` 写库时只取 `g['tex']`，把同一次解析里已经拿到的
`g['ntex']` / `g['mtex']` **丢掉**。源 `.ydr` 里两张图一直都在
（抽样 3,000 模型 / 11,509 子网格：法线 **96.86%**、`_ma` **97.09%**）。

### 13.2 为什么不动 `.mdl`

改格式要重写 **10.34 GB / 58,837 个** `.mdl`，并且要同步改 6 个读取器
（`rdr2_mdl` / `relink_from_mdl` / `fix_ydd_textures` / `blender_city_lod` / `build_miniatures_real` / `dump_model_lib`），
风险远大于收益。改成 **index 侧车**：`models[h].st = [[nm_tid, ma_tid], …]`，与 `s` 等长同序，
`s` 与 `.mdl` 一个字节没动（老读取器全部无感）。

### 13.3 工具链（可重跑，四段可中断）

```powershell
python tools\extract_slot_textures.py --stage parse  --jobs 16   # 3.6 分钟，55,608 个源
python tools\extract_slot_textures.py --stage bind                # 三重校验
python tools\extract_slot_textures.py --stage decode --jobs 14    # 14,843 张图，6 分钟
python tools\extract_slot_textures.py --stage apply               # 回写 index.json（先备份）
python tools\audit_three_maps.py                                 # 不开 Blender 的覆盖率
```

**绑定规矩（三条同时成立才写，否则留 `-1`）**：槽数一致 / 该槽 vc·ic 全等 / 源 albedo 名字与库里 texId 名字一致。
槽数一致的 **221,492 / 225,412**，名字与几何双双对上 **221,492**，最终绑定 **212,207 槽**。

### 13.4 数字（v12 实测）

| 项 | 结果 |
|---|---|
| 贴图表 | 12,214 → **27,057**（`ab` 12,214 + `nm` 8,578 + `ma` 6,265） |
| 磁盘 PNG | 19,288 → **34,131**（`tex/` 是指向 `deliverable/blender/continent/tex` 的 junction） |
| 槽位覆盖 | 漫反射 97.73% / 法线 **93.38%** / 高光 **91.28%** / 两者都有 90.52% |
| 实例加权 | 94.65% / **91.11%** / **86.83%** |
| v12 清单 | 带法线对象 **136,063**（5,569 张图）/ 带 ORM 对象 **129,555**（4,419 张图） |
| blend 里实际材质 | 带 NormalMap 节点 **7,794** 个 / 带 SeparateColor **6,383** 个（材质共享，故小于对象数） |

**补不上的**：法线 **2,883** 个名字 + 高光 **4,718** 个名字 —— 磁盘上**任何 ytd 都没有**
（`raw/lib_gtxd` 59,960 个 + 模型同级目录 11,205 个全扫过，0 命中）；
与文档里早有的"2,813 个 albedo 名无图"同源，要等拿到游戏原包。

### 13.5 材质节点图（`tools/mat_rdr2.py`，构建/重挂共用）

```
TEX_IMAGE(albedo, sRGB) ─────────────────► BSDF.Base Color
TEX_IMAGE(_nm, Non-Color) ─► NORMAL_MAP ─► BSDF.Normal     ← _nm 入池时已翻 G（DirectX→OpenGL）
TEX_IMAGE(_ma, Non-Color) ─► SEPARATE_COLOR ─ Red ──► BSDF.Metallic   (R=metal)
                                            └ Green ─► BSDF.Roughness (G=rough)
```

`_ma` 的 B(AO) 暂不接：Principled 没有 AO 输入，硬乘 Base Color 会把颜色压暗。

### 13.6 本轮踩到的新坑

| 坑 | 现象 | 对策 |
|---|---|---|
| `if kr in bsdf.inputs` | `kr` 是分离节点的**通道名** `'Red'`，不是 BSDF 的 socket 名 → 恒 False，ORM 只连了 Color 输入没接 BSDF | 判 `'Metallic' in bsdf.inputs` / `'Roughness' in bsdf.inputs`。已写进 `mat_rdr2.py` 注释 |
| `cmd` 吃逗号 | `--at 2560,-1450` 到 argparse 只剩 `2560`（`unrecognized arguments: -1450`） | 传参改成 `--x 2560 --y=-1450`（已知坑的又一次实例） |
| `ROLE_MATERIAL` 不含 `material_layerN` | 若照抄 `export_sdn_gltf` 的常量，**地形（占网格大头）的 `_ma` 会被漏掉** | `tex_slots.py` 单独实现按层配对，不走那份常量 |
| Eevee 无 GUI 出图慢 | 1280×720 / 150k 对象 / 27k 贴图，单帧约 **6~8 分钟**（还有 `无法分配速度几何缓冲区` 警告，可忽略） | 验证出图用 `render_material_ab.py`，别在构建里顺带渲 |
| Workbench 看不见法线 | Workbench 只吃 `diffuse_color`，看 A/B 时"前后一样" | 必须 Eevee/Cycles；或看 manifest 的 `TMAPS` 行 |

### 13.7 验证入口（不用开 blend）

```powershell
uv run python tools\report_manifest.py        # 第一行 + TMAPS 行
uv run python tools\audit_three_maps.py       # 槽位级 / 实例加权 / 池子分 role
python tools\extract_slot_textures.py --stage bind   # 只重算绑定（不改盘）
```

A/B 出图（Eevee，同机位）：

```powershell
cmd /c 'tools\run.cmd D:\BrainMaker\_logs\ab.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b "D:\...\continent_v12.blend" --python tools\_unbuffer.py -P tools\render_material_ab.py -- --tag v12 --x 2560 --y=-1450'
# 产物 D:\BrainMaker\_test\ab\v12_on.png / v12_off.png
```

### 13.8 待提交文件（15 个）

改：`tools/blender_continent.py`、`tools/relink_materials.py`、`tools/write_manifest.py`、
`tools/manifest_from_jsonl.py`、`tools/report_manifest.py`、`tools/export_sdn_props2.py`、
`tools/README.md`、`README.md`、`docs/README_骑砍2交接.md`、
`docs/格式与资产/README_贴图与材质管线.md`、`docs/交接与状态/README_交接.md`

新：`tools/extract_slot_textures.py`、`tools/tex_slots.py`、`tools/mat_rdr2.py`、
`tools/audit_three_maps.py`、`tools/render_material_ab.py`、`tools/_probe_maps.py`

产物（不进 git）：`deliverable/blender/continent/continent_v12.blend`（7.39 GB）、
`manifest_continent_v12.json/.jsonl`、`assets/lib_native/index.json`（含 14,843 条新贴图）、
`deliverable/blender/continent/tex/` 新增 14,843 张 PNG。

AI **禁止** `git add/commit/push`，由用户用 `git_gui.py` 提交。
---

## 14. 2026-10-30 · 铁路补全（v13）

> 触发：用户看 v12 时说"安尼斯堡下面应该有一条从南到北的连续铁路，没看到"。
> **结论：不是解析失败，是这一步（抽铁路包的 RPF）从来没跑过。**

### 14.1 根因（一句话）

RDR2 的铁路网是**按区块的独立 RPF 包**（`levels/rdr3/area/rails/*.rpf`），
安尼斯堡所在区块的三个包**只建了空目录、没抽到文件**：

```
raw/rails_extract/jklm_15_18_rails_a_rpf/   ← 0 个文件
raw/rails_extract/jklm_15_18_rails_b_rpf/   ← 0 个文件
raw/rails_extract/fghi_15_18_rails_a_rpf/   ← 0 个文件
```

只有西部/南部的 `nopq_11_14_rails_{a,b,c}`、`nopq_15_18_rails_a` 抽成功
（`raw/rails_extract/{c114,c1518,rb_a,rb_b,lv1,levels}/`）。
于是 `town_data`（= 全量 ymap，184,593 条）里没有这 500 条铁路实例，
`lib_native` 里也没有它们引用的 500 个模型 → blend 里安尼斯堡只剩
4 段 `ann_02_rails_*`（约 120 m）+ 几块 `*_rail_decal`。

### 14.2 补了什么

| 步骤 | 结果 |
|---|---|
| 从 `levels_2.rpf` 抽 3 个铁路包 | 1,285 个文件：**500 .ydr / 8 .ytyp / 11 .ymap / 34 .ytd** |
| `tools/ingest_rail_packs.py` 入库 | **500 个模型**（0 失败），新贴图 5 张，**401 个带法线/高光槽位** |
| `tools/merge_rail_entities.py` 并实例 | 500 条 → 跳过 213 个 `_lod/_slod` → **287 条**进 `wild2000_05_00/01/02` |
| 重建 | **v13**：`ENTITIES 151,220`（+287）/ `rail` 类 **2,193**（+160）/ `RAILS` 豁免 **1,524**（+159） |

**安尼斯堡 900 m 内**：铁路对象 **65 → 217**；仍低于地形面的比例 **58% → 14%**。

### 14.3 数据构成（500 条新实例）

`rails` 详细段 152 / `_lod` 209 / `_sle` 枕木 27 / `_tres` 栈桥 26 / `_decal` 38 / `rrcross` 道岔 8 / 其他 36。
名字全是 `j_1518_r_a_*`、`fghi_1518_a_*`、`jklm_15_18_*` 三族，模型全在抽出来的三个包里（100% 命中）。

### 14.4 备份 / 回滚

- `assets/lib_native/index_before_rail_20261030_1321.json`
- `export/world/continent/tiles_before_rail_20261030_1321/`（只备份被改的 3 个 tile）
- 两个新脚本都可重跑：`ingest_rail_packs.py` 跳过已入库的；`merge_rail_entities.py` 按 (hash,x,y) 去重

### 14.5 还没解决的

- 仍有 14% 的铁路件在 H4 地形面以下（4 m/px 采不出路堑），要不要沿铁路**切路堑**需要用户拍板（最高原则 §6.2 禁擅自改地形）。
- 铁路模型只解出 5 张新贴图，其余复用了既有池子里同名图；如果看到某段钢轨发灰，先查 `tex[]` 里有没有对应名字。
---

## 15. 2026-10-30 · 全抽取（v16）—— 从"场景自洽"改成"源侧闭环"

> 触发：用户问"你凭什么说所有可见物品都抽了"。查下来，当时那句是错的：
> 验证只做了**场景内部自洽**（列出的实例都有模型），没验证**清单本身全不全**。
> 铁路整类漏抽（18 个包里只抽了 4 个）就是后果。

### 15.1 新的判据（四条，全零才算抽全）

| # | 判据 | 现在的数 |
|---|---|---|
| 1 | 游戏目录表里的嵌套包，**产出 0 文件**的个数 | **0** / 2,158 个包（176,097 文件 / 58.58 GB） |
| 2 | 抽出的 `.ydr/.yft`，**未能入库**的个数 | **4,076** / 72,407 — 逐条见 `work/unparsed_models.json` |
| 3 | tiles 里**缺模型**的实例 | **49,072** / 233,104（其中 46,569 是无名 lod_combine 块、964 占位、292 lod、3 阴影、**1,244 真缺口**） |
| 4 | 位置/四元数/缩放完整 | **100.000%**（233,104 条，零四元数 0、模长异常 0） |

### 15.2 这一轮修掉的两个"静默丢数据"bug

| bug | 影响 | 修法 |
|---|---|---|
| `dump_model_lib.write_model()` 要求**三个轴都 bmin<bmax** | 所有**完全扁平的网格**（地面/地台/地板/贴花，dz=0）被当成退化整只丢掉，且无报错 | 改成只拒"对角线长度为 0"的点网格；**回收 1,033 个模型** |
| 入库脚本只 glob `**/*.ydr` | **7,389 个 `.yft` fragment 从来没被扫过**（分支写了但不可达） | 加一行 glob；**回收 2,365 个模型、1,119 张贴图** |

模型库 59,546 → **71,790**；贴图 27,062 → **32,878**。

### 15.3 全量抽取做了什么

```powershell
python tools\extract_all_packs.py            # 2,158 个包全抽（约 45 分钟）
python tools\ingest_rail_packs.py --packs raw\all_packs   # 模型入库（含 .yft）
python tools\merge_rail_entities.py --packs raw\all_packs # 实例并进 tiles
python tools\fix_zero_quat.py                # 零四元数补成单位四元数
python tools\audit_full_extraction.py        # 四列验收数字
python tools\bucket_missing_models.py        # 缺模型分桶
python tools\list_unparsed_models.py         # 未入库逐条清单
```

实例 200,720 → **233,104**（+32,384 条，含铁路 417、道具/道具组、fragment 家具等）。

### 15.4 残留（已逐条说明，不是"不知道"）

| 项 | 数 | 说明 |
|---|---:|---|
| `default_shader` 模型 | 2,555 | 只有 `default` 着色器 = 引擎占位/代理，按既有规则不入库 |
| `other`（混合着色器/VFX 代理） | 1,051 | 如 `aba_01_vfx_.ydr` |
| `frag_no_geom` | 470 | `.yft` 里我们能定位到的 drawable 只有 1~3 个三角形的占位，真实几何在另一种 fragment 布局里，**解析未覆盖** |
| 缺模型的实例 | 1,244 | 全部来自上面那 470 个文件（如 `p_cl_garment11`、`s_inv_revolverammo01x`），占 233,104 的 **0.53%** |

### 15.5 教训（写给下一个接手的人）

1. **"我手里的清单内部自洽"不等于"清单全"**。任何"抽全了"的结论必须带**源侧**数字：游戏目录表里有多少包、每个包产出多少文件。
2. 空目录/0 产出目录是**最强证据**，不要当噪声跳过（`raw/rails_extract/jklm_15_18_rails_a_rpf/` 就是）。
3. 不要用"重建 blend"当进度条：一次 60~90 分钟，数据没定稿就是白跑。**先跑 `audit_full_extraction.py`，四列都收口了再开始建。**

---

## 16. 2026-10-30 · 「地形 LOD / 地形块设了隐藏却还看得见」根因与修复

### 16.1 根因有五层，按发现顺序

| # | 根因 | 后果 |
|---|---|---|
| ① | 启动器默认「全图」时调 `tour.show_all()`，它把 13 类**全部打开**（含默认隐藏的 lod/terrain_cell/veg/stone） | 满地图"浮着的褐色岛 / 地形碎片" |
| ② | 随后的"重新关回去"被 `if cur and nt:` 挡住 —— `nt` 来自 `tileify()`，已分类文件常返回 0 | 修了①还是看得见（用户报"用 bat 启动还是看到远景 LOD"） |
| ③ | `Collection.hide_viewport`（数据层）与 `LayerCollection.hide_viewport`（视层眼睛）是**两套状态**，只设一半 | 清单写"已隐藏"，画面仍可见 |
| ④ | `blender_tour.cats()` 用 `split('_', 2)` 解析集合名：`C_terrain_cell_地形块` → key=`terrain` | `cat_show('terrain_cell')` 找不到、`DEFAULT_HIDDEN` 判定**永不成立** → "地形块"这一类根本没被隐藏（旧版靠中文名 `'地形块'` 匹配才碰巧躲过） |
| ⑤ | `full()` / `follow()` 调用**未定义**的 `_set_sub()` | 拉远到中景（跟随时）直接 NameError，隐藏逻辑整段没执行 |

### 16.2 改了什么（12 个文件，全部可重跑）

- **`tools/class_registry.py`（新）**：`CLASSES`（14 类）+ `DEFAULT_HIDDEN` 唯一一份；`classify / tour / 面板 / 三个清单脚本` 全部 import 它。
- `blender_tour.py`：`cats()` 改**已知类名最长前缀匹配**；`show_all/full/only/_apply('all')` 统一按 `DEFAULT_HIDDEN` 处理，数据层与眼睛一起设；删掉 `_set_sub` 调用。
- `blender_autoload.py`：默认隐藏改用 `DEFAULT_HIDDEN + 贴花`；不再依赖 `nt`。
- `rdr2_cat_ui.py`：面板「全图」改调 `apply_defaults()`（原来调 `show_all()`，一点就把碎片放出来）。
- `classify_entities.py`：stone 规则收紧（只认 `rubble/wallstone/cobble/boulder/rock_stones/ruin_stone/...`，不再用泛化 `_stone` —— v17 曾把 `scr_01_stonehs_roof/wall/ext`、`agu_tower_stone_*`、`wll_stonehenge` 共 19 个建筑件藏掉）。
- `veg_rules.py`：排除 `plantpot`（盆栽是道具）、`_wall`（`tumbleweed_wall` 是墙）。
- 三个清单脚本：类表改用注册表；`classes_expected = len(CLASSES)`。

### 16.3 口径变更（会改数字，看旧报告时注意）

| 项 | 旧 | 新 |
|---|---|---|
| manifest 类表 | 写死 13 类，v17 漏算 **744** 个对象（stone 类），合计 183,288 ≠ entities 184,032 | 14 类，由注册表推 |
| `veg_should_delete` | "名字像植被却没归 veg 类"→ 把 `p_debris_nbd_docks_weed1`（码头杂物）、`smb_bridge_01_ivy`（带藤的桥）当错误，v17 **虚报 271** | "默认隐藏类里还有露着的对象"，正常应为 **0** |
| `manifest_from_jsonl` 的植被判定 | `from strip_vegetation import VEG`（那模块不导出 VEG）→ 每次静默落进兜底正则 | 统一 `veg_rules.is_veg` |

### 16.4 验收（三层，都有实测）

1. **保存态**：`blender -b <blend> -P tools\_check_class_visibility.py` —— v17 实测 14 类，lod/terrain_cell/veg/stone 的 `Collection.hide_viewport` 与 `LayerCollection.hide_viewport` **都=True**，其余都 False，无逐对象隐藏、ENTITIES 下无直挂对象。
2. **函数行为**：合成场景单测（不加载 7.8 GB）跑 `show_all → apply_defaults → cat_show('terrain_cell') → only() → full()`，五个函数全部正确。
3. **清单**：`python tools\manifest_from_jsonl.py --jsonl <v18.jsonl>` → `类 14/14 / 默认隐藏类未藏 0 → PASS`。

### 16.5 bat 打开说明

- `打开大陆_流畅.bat` 按修改时间自动挑最新的 `continent_v*.blend`，**不需要改 bat**。
- 判据只用 GUI 双击：`blender -b` **没有视口**，autoload 会走"保持文件保存态"分支，**测不出启动器画面**（2026-10-29 我拿 `-b` 当证据判错过一次）。
- 面板「全开（含隐藏类）」是显式例外：点了就会看见远景碎片/地形块，那是预期行为。

### 16.6 落地产物与数字（2026-10-30 夜）

| 版本 | 做了什么 | 结果 |
|---|---|---|
| v18 | 用收紧后的 stone 规则重分类 | **PASS**；stone 744 → **718**（踢出 26 个建筑件：石头房的 roof/wall/ext 8、`agu_tower_stone_*` 12、`wll_stonehenge*` 2、`stonebench` 2、`eri_stonewall006` 2，全部回到 part/rock/decal/unknown 且可见） |
| v19 | 回滚 `_wall` 排除（它误伤 38 个真植被） | **PASS**；veg 10,942 / stone 718 / 隐藏合计 44,633 = 2,290+30,683+10,942+718 |
| v20 | 补 `out_*` / `outg_*` 两套 1024 m 外围地形块 → `terrain_cell`（用户 2026-10-30 报 `out_c_05_hd_13`） | **PASS**；这 **156 个**（85 + 71）全部归地形块且 `hid=1`；terrain_cell 30,683 → **30,839**，unknown 7,828 → **7,672**；对象总数仍 184,032 |
| v21 | 用户逐个点名后的清理：① 新增 **`underground` 地下**（tempbox / `q_11_damn` / z<−80）② 新增 **`watertile` 水面块**（`a_water_*`）③ 新增 **`placeholder` 占位代理**（proxy/occ/placeholder/donotdelete/amb_pun/cubedelete）④ **rail 规则补窄词**（`sle\d`/`tressle`/`*track`/`rail_buffer`/`coatrack`/`_rhd_\d`，修 Annesburg 断轨）⑤ `decal` 几何兜底排除站台/地板/走道（26 个救回可见）⑥ `classify()` 先剥 `.001` | **PASS**，**17 类**；`rail` 2,288 → **2,592**（Annesburg 的 `maintrack_03/04` 现在可见）、`watertile` **321**、`placeholder` **64**、`underground` **17**（全部 `hid=1`）；decal 4,159 → 4,005；`p_litternbx02x` 的 33 个地表实例仍是 prop，只有 3 个掉在 −104.9 m 的进地下 |
| v22 | **二修铁路**（v21 只修好了路基，轨面/枕木仍藏在 decal）：Annesburg 以北真正的轨面是 `jklm_1518b_r_*` / `j_1518b_r_dec_*`、枕木是 `j_1518_r_a_dec_*`（贴图 `railroad_sleeper*`）—— 全落在 **decal**，而启动器默认关 decal。rail 规则补 `b_r_` 与 `_r_[abc]_dec`（**不加** `_r_[abc]_`，否则木栈桥/铁路桥 170 个会被抢走） | **PASS**；rail 2,592 → **2,641**，decal 3,966。**用渲图验收**（启动器同款可见性）：主线连续、枕木在、站场股道在 —— `D:\BrainMaker\_railcheck\close_top.png` / `close_along.png` / `close_yard.png` / `top.png` / `oblique.png` / `wide.png` |
| v23 | 用户点名两件事：① **枕木/道砟是独立地面片**（`*_rail_decal_*` / `*_track_decal_*`，贴图 `railroad_sleeper*`），340 个全在 decal → 被启动器藏 ⇒ "铁轨上没有枕木"。rail 规则补 `rail[_-]?decal|track[_-]?decal`；② **停在原点的实体**（`cumb_rock_hero_01` / `bgv_rock_04.020` / `dis_pun_00` 等，源数据 x=y=0）不是坐标兜底，是关卡"停放"件：源 tiles 实测 **1,141 条** x=y=0。加规则 `|x|<1 且 |y|<1` → `underground`（中文名改「地下停放」） | **PASS**；rail 2,641 → **2,980**（+339 枕木/道砟）、underground 17 → **1,158**、decal 3,966 → 3,625、veg −558 / rock −426（都是原点停放件） |

**两条规则教训（都写在 `veg_rules.py` 与 `classify_entities.py` 的注释里）**：

1. `VEG_EXCLUDE` **不能加 `_wall`** —— 为了踢掉 `tum_04__tumbleweed_wall` 会把
   `rdr_bush_kudzu_wall_01`（墙上的葛藤）、`lac_01_wall_vines` / `civ_ivy_thin_n_wall`（墙上的藤）、
   `civ_01_wall_weed_*`（墙头草）一起踢出植被类，实测误伤 **38 个**。
2. `plantpot` 要**同时在 veg 排除和 prop 兜底里**写，并且 `classify()` 里对 `bldg/part` 加前置跳过 ——
   只写前者时，`p_plantpotwallnbx02x`（壁挂花盆，30 个）会被 `part` 的 `wall` 规则先接走。
   **v19 / v20 里这 30 个仍标成"建筑部件"**（可见性不受影响，都是显示状态）；
   代码已改，**下次 reclassify 会自动归到 prop**。

### 16.6b 未修：粘连贴图名让泥路面发白（渲染验收时发现的）

`ann_04_d_maintrack_*`（安尼斯堡站内路床，也就是铁路旁那条"白带"）渲出来是**白色**。
根因不在分类，在**贴图名**：ytd 的 SYS 字符串表里这个名字本身就是两段粘在一起的
（原始字节实证 `std_annesburg_muddyroad_03_ab` + `std_annesburg_muddyroad_03_al`，无分隔符），
我们解出来的是那张近白的图（RGB 均值 218，1024²）。

- 量级：贴图表里这种「`A_ab` + `A_al` 粘连」共 **1,285 个名字 / 8,720 个子网格**；
  多数解出来颜色正常（是 albedo），但 **muddyroad 几族解成了白图**：
  `std_annesburg_muddyroad_03`（253 处）、`_01`（114）、`road_muddyroad_03`（69）、`road_muddyroadtnt_02`（83）。
- 下一步：`rdr2_ytd` 解这种名字时**选对子资源/层**（要 `_ab`，别拿 `_al`），再重跑贴图表 + 重绑 + 重建。
- 影响面：目前只在安尼斯堡站场、`road_muddyroad*` 这类泥路上看得出来（白缝）；其它粘连名目视正常。

### 16.7 待提交（本轮，AI 不提交）

`tools/class_registry.py`（新）· `classify_entities.py` · `blender_tour.py` · `blender_autoload.py` ·
`rdr2_cat_ui.py` · `veg_rules.py` · `write_manifest.py` · `manifest_from_jsonl.py` ·
`report_manifest.py` · `_check_class_links.py` · `_check_class_visibility.py` ·
`docs/交接与状态/README_交接.md` · `docs/AGENTS.md`
