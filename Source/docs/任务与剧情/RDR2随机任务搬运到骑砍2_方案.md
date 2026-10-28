# RDR2 随机任务 → 骑砍2 搬运方案

> 目标：把《荒野大镖客 2》的**随机任务 / 陌生人任务 / 赏金 / 物品请求 / 路上遭遇**搬到
> 《骑马与砍杀 2：霸主》，并说清"该怎么做、先做什么、哪条路走不通"。
>
> 本文所有数字都可用 `tools/` 里的脚本复现，出处逐项标注。写于 2026-10-23。

---

## 0. 一句话结论

**能搬，但不是"把数据搬过去"，而是"把剧本骨架搬过去、在骑砍2 里用原生任务系统重做"。**

> 👉 **源码级还原入口**：`http://127.0.0.1:8788/mission_flow/index.html`
> （105/150 个任务按脚本行号还原，27 个带原文台词共 1 398 句，含缺失清单）
> 方法与边界见 `docs/任务与剧情/随机任务还原说明.md`
>
> ⚠️ 早先那版「可玩原型」是自创玩法（成功率/荣誉/赶路距离均为虚构），**已删除**。
> 本方案里的"分层落地"仍是设计建议，但任务内容必须以还原数据为准，不得再编。

三条硬结论（都有证据，见 §3）：

1. **RDR2 的随机任务共有 150 个**（96 陌生人 + 21 物品请求 + 13 赏金 + 12 剧情随机 + 8 尾声），
   每个都有**中文标题、中文描述、出场角色、对白量、目标/失败条件**——这部分**已经可以直接用**。
2. **场地坐标只有定制任务能提**：150 个里只有 **9 个**能从脚本常量挖出专属坐标；
   赏金和陌生人任务是**模板化**的（脚本里那份坐标表是所有任务共用的一张"据点锚点表"，
   场地由运行时数据表选点）。所以**别指望"照抄坐标摆任务"**，要在骑砍2 侧按据点二次分配。
3. **骑砍2 侧已经有半座桥**：`export/world/bannerlord/` 里已有「RDR2 世界坐标 ↔ 大地图 (u,v) ↔
   野外 7×7 网格场景」的换算代码。**但其中的常量有 852 m 偏差**（§3.3），做任务落位前必须先修。

---

## 1. 现在手上有什么（素材盘点）

### 1.1 任务层

| 数据 | 文件 | 覆盖 | 用途 |
|---|---|---|---|
| 任务分类清单 | `export/levels/world/missions.csv` | **270** 条 | 分类/子类型 |
| 中文名 + 描述 + 出场角色 + 对白量 | `export/levels/world/missions_story.csv` | **270** 条（100%） | **直接可做任务卡** |
| 目标 / 失败条件（中文） | `mission_objectives.csv` | 105 个任务 | 任务目标文案 |
| 对白（分步骤） | `mission_dialogues.json` | 38 个任务 | 台词库 |
| 事件树（每步做什么） | `mission_tree.json` / `mission_events.json` | 43 个任务 | 行为拆解 |
| 生成表（刷什么模型） | `mission_schedule.json` | 194 个任务 | 道具/NPC 需求 |
| 场地坐标 | `mission_coords.csv` | 288/1251 脚本有专属坐标 | 落位（见 §3.2） |
| 演出结构（beats/对白） | `export/story/beats_index.csv` | 133 个任务 / 9 921 beats | 演出复杂度评估 |

### 1.2 随机任务五类的实际成色

| 类别 | 数量 | 有中文名 | 有目标 | 有对白 | 有生成表 | 有专属坐标 | 搬运档 |
|---|---:|---:|---:|---:|---:|---:|---|
| `RANDOM_CHARACTER`（陌生人） | 96 | 96 | 8 | 部分 | 45 | 4 | **T3** |
| `ITEM_REQUEST`（物品请求） | 21 | 21 | 0 | 0 | 21 | 0 | **T1** |
| `BOUNTY_HUNTING`（赏金） | 13 | 13 | 9 | 13 | 13 | 3 | **T2** |
| `RANDOM_STORY_CHARACTER`（剧情随机） | 12 | 12 | 0 | 0 | 6 | 0 | **T4** |
| `ENDLESS_SUMMER`（尾声） | 8 | 8 | 0 | 0 | 4 | 0 | T3 |
| **合计** | **150** | **150** | 17 | — | 89 | **9** | — |

> 复现：`uv run python tools/build_random_mission_pack.py`
> 产出：`export/world/bannerlord/random_missions.json`（150 条完整任务卡）+ `.csv` + `_index.json`

### 1.3 还没开发的资产（本轮的"新矿脉"）

| 资产 | 量 | 状态 | 价值 |
|---|---|---|---|
| `beat_*` 路上随机遭遇 | **119 个** | **已结构化**（`ambient_events.json`） | 这才是"野外随机事件"的主体 |
| 中文语言表 | 91 250 条字符串 / **20 853 条中文** | 已可解析（`tools/yldb_dump.py`） | 任何标签 → 中文 |
| 角色模型 | 412 个 GLB | 可用 | 任务 NPC 换皮 |
| 据点坐标 v2 | 46 个 | 可用 | 任务落点基准 |

---

## 2. 骑砍2 侧能接住什么（能力对照）

> ⚠️ 本节是**设计对照**；具体 API 签名请在 modkit（`TaleWorlds.CampaignSystem`）里再核一次。
> 本地未安装骑砍2 本体，无法直接比对 DLL。

| RDR2 的东西 | 骑砍2 对应物 | 匹配度 | 说明 |
|---|---|---|---|
| 物品请求（"某某想要 X"） | **Notable Issue**（如 `ArtisanNeedsCraftingMaterials`、`HeadmanNeedsGrain` 这类"收集并交付"） | ★★★★★ | 只换物品和文案，逻辑现成 |
| 赏金（通缉→追捕→交人） | **Issue + Quest**（`MerchantNeedsHelpWithOutlaws` 打匪 + 自定义交人任务） | ★★★★☆ | 打匪现成；"活捉押送"要自己写 |
| 陌生人小剧本（1~3 步） | 自定义 `QuestBase` + `QuestTaskBase` | ★★★☆☆ | 每步都要写代码，无模板 |
| 剧情随机任务（多幕演出） | `QuestBase` + `MissionState` 过场 | ★★☆☆☆ | 过场演出成本最高 |
| 路上随机遭遇（`beat_*`） | `CampaignBehaviorBase` + `HourlyTickParty` 生成 `MobileParty` / `MapEvent` | ★★★☆☆ | 大地图上做"遭遇"，不必开 3D 场景 |
| 场景内演出（对话/动作） | `MissionBehavior` + 对白行 + 动画 | ★★☆☆☆ | 骑砍2 对话是静态镜头 |
| 对白条件分支 | `dialogues.xml` 条件 + `DialogFlow` | ★★★★☆ | 条件系统够用 |

**关键判断**：骑砍2 的强项是**大地图上的遭遇/任务**，弱项是**场景内的电影化演出**。
所以搬运要**优先做"大地图层"的任务**，把场景演出降级。

---

## 3. 本轮三个硬发现（含证据）

### 3.1 随机任务是"模板 + 数据表"，不是"手摆的"

`rcm_bh_sd_saloon`（圣丹尼斯酒馆赏金）、`rcm_bh_blackwater_hunt`（黑水狩猎赏金）、
`rcm_bh_laramie_sleeping`（拉勒米）三个脚本各有 87 个坐标三元组，
**其中 85 个完全相同、各 0 个独有**：

```
rcm_bh_sd_saloon      ∩ rcm_bh_blackwater_hunt = 85  (A独有 0, B独有 0)
rcm_bh_sd_saloon      ∩ rcm_bh_laramie_sleeping = 85  (A独有 0, B独有 0)
rcm_bh_bandito_mine   → 独有 7 个（矿洞固定点位，可提）
```

那 85 个是**全脚本共用的据点锚点表**（瓦伦丁、罗兹、圣丹尼斯、安尼斯堡…）。
⇒ **模板化任务的场地不在脚本里**，由运行时数据表选点。

**这反而是好消息**：说明 RDR2 自己也是"先有模板、再选点"，
搬到骑砍2 时同样应该"模板化 + 按据点选点"，而不是搬 150 个手摆坐标。

### 3.2 坐标提取管线（已落地）

`tools/extract_mission_coords.py`：两趟算法——先找出**跨脚本重复出现**的坐标（判为共享锚点），
剔除后再聚簇，剩下的才是该任务自己的布点。

结果（可复现）：

| 指标 | 值 |
|---|---|
| 含坐标的脚本 | 1 251 / 1 639 |
| 共享锚点（出现在 ≥3 个脚本） | 1 529 个 |
| 能提专属坐标的脚本 | **288** |
| 模板化（无专属坐标） | 963 |
| 150 个随机任务里有专属坐标的 | **9** |

已验证的样本（名字对得上）：

| 任务 | 脚本 | 落到 | 距离 |
|---|---|---|---|
| RBT18 奥蒂斯·斯金纳 | `rcm_bh_skinner_brother` | 石兰贸易站 | 208 m |
| RBT22 瓦金·阿罗约 | `rcm_bh_bandito_shack` | 安尼斯堡 | 60 m |
| RBT23 埃斯塔班·科特斯 | `rcm_bh_bandito_mine` | 安尼斯堡 | 60 m |

章节任务覆盖率高得多（CHAPTER_6 有 17/19、CHAPTER_8 有 10/11 可提）——
说明**主线任务是真手摆的，随机任务是模板生成的**。

### 3.3 ⚠️ 坐标桥接有 852 m 偏差（做任务落位前必须修）

`export/world/bannerlord/camp_scenes.json` 里写的是：

```json
"campaign": { "map_units": 848, "m_per_unit": 14.5,
              "origin_world": [-7684, 4100],
              "desc": "x = -7684 + u*14.5 ; y = 4100 - v*14.5" }
```

而 `Rdr2CampBehavior.cs` 里的常量是 `ORIGIN_X = -8536`、`ORIGIN_Y_NORTH = 4952`。

用 46 个据点反算验证（`u,v` 与 `world_x,world_y` 都是已知的）：

| 据点 | 数据 x | JSON 反算 | C# 反算 |
|---|---:|---:|---:|
| 安尼斯堡 | 2883.6 | **2883.6** ✅ | 2031.6 ❌ |
| 圣丹尼斯 | 2554.5 | **2554.5** ✅ | 1702.5 ❌ |
| 罗兹 | 1217.5 | **1217.5** ✅ | 365.5 ❌ |

**结论：`camp_scenes.json` 的公式是对的，C# 里的两个常量各偏 852 m。**
C# 内部往返自洽（所以不会报错），但和所有数据产物对不上——
一旦用它给任务落位，**每个任务都会偏到 1.2 km 外**。

> 修法：`WildGrid.CampaignToWorld` / `WorldToCampaign` 改用 `origin_world = (-7684, 4100)`；
> `Resolve()` 的网格原点改用 `grid_origin = (-8456, 5712)`。
> **已修**（2026-10-23）：`Rdr2CampBehavior.cs` 改成从 `camp_scenes.json` 读参数
> （新增 `WildGrid.Calibrate()`），不再硬编码；`tools/build_random_mission_pack.py` 也用同一套参数。

### 3.4 顺带修掉：3 个据点的 `u,v` 是旧值

用 46 个据点做 world↔campaign 反算，发现 `settlements_world_v2.csv` 里有 6 行对不上：

| 据点 | 表内 u,v | 应为 | 原因 |
|---|---|---|---|
| 瓦匹缇 `wap` | 573.2, 141.4 | 561.4, 129.2 | v2 修了坐标，`u,v` 没跟着改 |
| 朗尼棚屋 `lon` | 660.8, 314.8 | 471.2, 334.3 | 同上（这行偏了 **2.7 km**） |
| 豁牙裂口 `gap` | 145.9, 484.6 | 117.1, 504.2 | 同上 |
| 威拉德之息 / 马掌望台 / 阿伯丁猪场 | 空 | 已补 | v2 新增的三个剧情点没填 `u,v` |

**已按 `x = -7684 + u*14.5` 重算并写回**，复验：46 个据点最大误差 **0.6 m**（`u,v` 保留 1 位小数）。

> 影响：任何人拿 `u,v` 去摆点时，那 3 个镇会偏 176 m ~ 2.7 km。

---

## 4. 怎么玩：四层落地路线

> 原则：**每一层都能单独交付、单独验证**。不要一次性把 150 个任务全搬。

### L0 · 换皮（T1，21 个物品请求）— 1~2 天量级

RDR2 那 21 条长这样：

```
IRBLPM  比尔想要些发油。
IRHOBK  何西阿喜欢犯罪小说，给他找一本。
IRSNWH  西恩想要些威士忌。
```

**这就是骑砍2 的 Notable Issue**。做法：

1. 在 `random_missions.json` 里筛 `tier == 1`，拿到 `title_zh`；
2. 在骑砍2 里新增一个 `IssueBase` 子类（"某 notable 要 N 个某物品"），
   物品换成卡拉迪亚的等价物（发油→油、威士忌→酒、犯罪小说→书）；
3. 文案直接把 `title_zh` 塞进 `TextObject`；
4. 验收：酒馆/村庄里能接到，交齐物品能结算。

**价值**：用最低成本把"RDR2 任务文案"这条链路跑通（数据 → 骑砍2 界面），
后面所有层都复用这条链路。

### L1 · 骨架复用（T2，13 个赏金）— 1 周量级

RDR2 赏金任务的数据最完整（13 个全有对白，9 个有目标，13 个有生成表）：

```
RBCON  林赛·沃福德    目标 2  对白 216 行  生成 3 个模型
RBRAN  马克·约翰逊    目标 3  对白 307 行  生成 2 个模型
RBT05  爱丽·安妮·思旺 目标 2  对白 163 行  生成 2 个模型
```

目标里甚至直接写了**失败条件**（"XXX 死了 / XXX 逃走了"），
这跟骑砍2 的任务失败判定是同一个模型。

做法：
1. **模板**：`BountyQuest : QuestBase`——接受 → 前往据点（`Settlement`）→ 打一场（`MapEvent` 或场景）→ 押回 → 结算；
2. **落点**：不要用 RDR2 坐标，直接用 `settlements_world_v2.csv` 的据点 + `camp_scenes.json` 的 `site_<code>` 锚定场景（据点任务天然在据点里）；
3. **对白**：从 `mission_dialogues.json` 取，按"接单/途中/交付"三段切；
4. **验收**：13 个全部可接可交，失败条件能触发。

**为什么先做赏金**：骑砍2 有现成的"打匪徒"issue 骨架，赏金是**唯一一类两边结构几乎同构**的任务。

### L2 · 剧本移植（T3，104 个陌生人 + 尾声）— 逐个做

这 104 个是真正的"陌生人小剧本"。每个的复杂度差异很大，用
`random_missions.json` 里的 `dialogue.lines` / `objectives` / `beats.cutscene_clips` 排序做**性价比筛选**：

- 优先做 **对白 ≥ 50 行、目标 2~3 个、无过场** 的（信息量够、成本低）；
- 跳过 `cutscene_clips > 0` 的（要搬演出，成本翻倍）。

做法：
1. 每个任务建一个 `QuestBase` 子类；
2. 场景用 `WildGrid.Resolve()`（**修好 §3.3 的偏差后**）落到 7×7 野外块；
3. 演出**降级**：RDR2 的长过场 → 骑砍2 的静态对话 + 任务日志文本。

### L3 · 演出级（T4，12 个剧情随机任务）— 最后做，或不做

`RANDOM_STORY_CHARACTER` 是"随机外壳 + 主线级演出"，搬运性价比最低。
建议**只抽用它们的对白**（`mission_dialogues.json` 里有），不做场景复刻。

### 另一条线 · 路上遭遇（`beat_*`，119 个）— **已结构化**

这才是 RDR2 "随机"的灵魂：在野外走着遇到抢劫、抛锚马车、绞刑、伏击…
玩家记得住的"随机感"几乎全来自这里，而不是 150 个陌生人任务。

**本轮已把它变成数据**：`tools/build_ambient_events.py` → `export/levels/world/ambient_events.json`

| 指标 | 值 |
|---|---|
| 遭遇事件 | **119** 个 |
| 有目标提示（UILOG） | 116 个 |
| 有场地坐标 | 35 个 |
| 会生成 NPC | 116 个 |
| 用载具 | 20 个 |
| 含击倒行为 | 8 个 |

每条含：`spawn`（生成什么/几个）、`tasks`（用了哪些行为 + 中文）、
`anim_scene_calls`（演出量）、`tags`、`complexity`（搬运成本评分）、`location`。

抽样（复杂度从高到低，落点对得上）：

| 事件 | 行为数 | 演出 | 落点 |
|---|---:|---:|---|
| `beat_public_hanging` 公开绞刑 | 100 | 242 | 瓦伦丁 ✅ |
| `beat_trapped_woman` 受困女子 | 111 | 216 | 马掌望台 ✅ |
| `beat_savage_fight` 野蛮斗殴 | 139 | 67 | 马掌望台 ✅ |
| `beat_herbalist_camp` 药师营地 | 87 | 39 | 马掌望台 ✅ |
| `beat_train_holdup` 劫火车 | 147 | 78 | — |

**落地建议**（骑砍2 侧）：
1. 用 `CampaignBehaviorBase` + `HourlyTickParty`：玩家在野外时按权重 roll 一个事件；
2. 生成 `MobileParty`（匪徒/车队）或直接弹 `GameMenu` 给 2~3 个选项（帮/不帮/抢）；
3. **不需要 3D 场景**——大地图遭遇就能拿到 80% 的体感，成本比 L2 低一个数量级；
4. 建议先做 `complexity < 8` 的那批（约 60 个），再挑高复杂度的做招牌事件。

---

## 5. 数据契约（给骑砍2 侧 Agent）

### 5.1 主交付

`export/world/bannerlord/random_missions.json` —— 150 条任务卡：

```jsonc
"IRBLPM": {
  "id": "IRBLPM",
  "category": "ITEM_REQUEST",
  "title_zh": "比尔想要些发油。",
  "desc_zh": "…",
  "cast_count": 2,
  "cast": ["比尔·威廉姆森", "…"],
  "objectives": [],                    // 物品请求没有 objective 行
  "dialogue": { "lines": 0, "steps_with_dialogue": 0, "bank": "" },
  "beats": { "cutscene_clips": 0 },
  "spawn": { "count": 0, "models": [], "counts": {}, "task_top": [] },
  "location": {
     "world": [x, y, z],               // null 表示模板化、需二次落位
     "campaign_uv": [u, v],            // 大地图沙盘坐标（848 单位 = 12296 m，1 单位 = 14.5 m）
     "tile_scene": "wild2000_05_03",   // 野外块场景名（可直接给 MissionInitializerRecord.SceneName）
     "scene_local": [sx, sy],          // 块内坐标（块中心为原点，y 向北）
     "kind": "wilderness_tile | settlement_anchor | unplaced",
     "source": "script_const | template",
     "nearest_settlement": { "code": "ann", "zh": "安尼斯堡", "dist_m": 60.0 }
  },
  "port": {
     "tier": 3,
     "tier_note": "…",
     "template_only": true,            // true = 脚本里没有专属坐标
     "blockers": ["…"]
  }
}
```

### 5.2 配套文件

| 文件 | 说明 |
|---|---|
| `random_missions.csv` | 同上拍平，排序按 tier，给人看/给策划筛 |
| `random_missions_index.json` | 分类计数、分级计数、坐标来源说明 |
| `export/levels/world/mission_coords.csv` | 1 251 个脚本的场地坐标（含 `has_own_coords` 标记） |
| `export/levels/world/shared_coord_anchors.csv` | 被剔除的 1 529 个共享锚点（本身有用：据点/布告板坐标） |
| `export/world/bannerlord/camp_scenes.json` | 野外网格 + 据点锚定场景（**坐标换算的唯一权威**） |

### 5.3 铁律

1. **用 `camp_scenes.json` 的 `campaign.origin_world`，不要用 C# 里的 `ORIGIN_X`**（§3.3）。
2. `campaign_uv` 已经是沙盘坐标，直接可喂 `MobileParty.Position`；
   `tile_scene` + `scene_local` 直接可喂 `MissionInitializerRecord`。
3. `location.kind == "unplaced"` 的任务**不要猜坐标**——按 §4 的模板规则在骑砍2 侧选点。
4. 坐标系：RDR2 是 **X 东 / Y 北 / Z 上，单位米**；骑砍2 的 up 轴不同，进场景前要转一次。

---

## 6. 首批可做清单（建议按此顺序）

| 顺序 | 内容 | 数量 | 依赖 | 验收 |
|---|---|---|---|---|
| 1 | 修 `WildGrid` 的 852 m 偏差 | 1 处 | 无 | 用 46 个据点反算，误差 < 1 m |
| 2 | L0 物品请求换皮 | 21 个 | 修坐标（其实不依赖，物品请求在据点内） | 酒馆能接、能交 |
| 3 | ~~`beat_*` 结构化~~ **已完成** | 119 个 | 无 | `export/levels/world/ambient_events.json` |
| 4 | 大地图遭遇系统 | 1 套 | #3 | 野外走动能 roll 出匪徒遭遇 |
| 5 | L1 赏金模板 + 13 个 | 13 个 | #1 | 接单→打→押回全通 |
| 6 | L2 陌生人剧本（先做对白≥50、无过场的 20 个） | 20 个 | #1 | 任务可完成、对白显示正确 |

---

## 7. 已知风险 / 走不通的路

| 项 | 结论 |
|---|---|
| 想要"150 个任务的原版坐标" | **做不到**。模板化任务的场地在运行时数据表，反编译脚本里只有共享锚点表。要靠骑砍2 侧选点。 |
| 想要"RDR2 的过场演出 1:1 复刻" | 成本极高（要搬 668 个过场、2 199 个镜头），且骑砍2 的对话系统不支持。建议只搬文本。 |
| 想要"照 RDR2 地图原样摆任务" | 可以，但前提是 §3.3 的坐标桥修好，否则全体偏 1.2 km。 |
| `.ysc` 原始脚本（非反编译） | 仍未解（TFIT2 tag `0xC6`，密钥表缺）。现用的是**反编译产物**（`raw/script_full/1491.50/*.c`，1 639 个），够用。 |
| 任务触发体积（trigger volume） | 未见解出。随机遭遇的"在哪触发"可能要另找 `.ymap` 里的 volume 数据。 |

---

## 8. 复现命令

```bash
cd "D:/BrainMaker/大镖客2解包分析"

# 1) 从脚本挖任务坐标（两趟：剔共享锚点 → 聚簇）
uv run python tools/extract_mission_coords.py

# 2) 打包 150 个随机任务 → 骑砍2 数据包
uv run python tools/build_random_mission_pack.py

# 2b) 结构化 119 个路上遭遇（beat_*）
uv run python tools/build_ambient_events.py

# 3) 重复文件清理（预演 / 执行）
uv run python tools/dedupe_raw.py
uv run python tools/dedupe_raw.py --apply
```

---

## 9. 与其它文档的关系

- 坐标 / 高度图 / 材质 / 模型 → `README_骑砍2交接.md`（数据契约）
- 清理与体积 → `docs/交接与状态/资源清理清单.md`
- 地形与据点修正 → `docs/世界与地编/RDR2_骑砍2落地_据点修正_v2.md`
- 过场解析（668 过场 / 2 199 镜头）→ `export/story/cutscene/index.html`
