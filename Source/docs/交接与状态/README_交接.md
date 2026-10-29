# 荒野大镖客 2 · 解包分析交接 README

> 最后更新：**2026-10-29**
> 项目根：`D:\BrainMaker\大镖客2解包分析`
> 游戏：`H:\EPICGAMES\RedDeadRedemption2`（Epic）
>
> **一句话状态**：世界地图 / 43 据点 / **43 个据点 3D 预览** / **49 块野外分块 + 任意地点扎营** / 8 势力 / 142 具名角色 / 270 条任务（含脚本级、逐步骤、任务树、对白归属）/ 181 过场 / 45 武器 / 916 道具 / 408 角色模型 / 圣丹尼斯整城 / 14 页查看器，全部落地。
> **仍未解决**：任务字节码 `.ysc` 本地解密、对白“说话人”哈希映射、spawn 模型名与实体身份。

> 📌 **本轮的专项交接**：§11（2026-10-29 · 分类重排 + 地面覆盖抬高 + 4 个 bug + v10 数字）
> （旧：`交接_角色与服饰与查看器_20261023.md` —— 角色 408 / 服饰 6106 / 眼睛与头发 / 武器金属 / 据点名单 46 / 查看器收口 / 踩坑清单）

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

### 12.4 尚未查清（下一个接手的人从这里开始）

**现象**：v11 里某处俯视出现"绿白碎片化"的地表；**同样的位置在 v8 里看着是连续地形**。

已排除：
- 植被 91 / 地形块 69 / 远景碎片 63（该点 300 m 内）→ `visible_get()` 全为 **False**，隐藏生效
- 分类数字自洽：13 类相加 = 150,933 = ENTITIES 全部对象

已确认的事实：
- `Terrain` **不是连续网格**：构建时按 `ground_mask` 剔面（9,449,476 → 7,870,374，剔掉 158 万面）；
  遮罩实测 **83% 有地面 / 17% 空洞**，空洞是成片大区域
- 该遮罩逻辑 v8 就有，**不是这一轮引入的**

下一步建议：在 v11 里点一下那片东西，看左上角「活动物体」是 `Terrain` 还是别的；
或做 A/B 渲染对比（相机要放在地面**之上**，该点地面高度约 122 m）。

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
