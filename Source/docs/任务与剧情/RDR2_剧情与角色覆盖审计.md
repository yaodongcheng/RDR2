# 荒野大镖客 2 · 剧情与角色覆盖审计

> 回答："是否解包到了所有的主线和支线的剧情文件？里面涉及的所有角色都要考虑吧。"
>
> 结论先说：**任务定义和过场动画已经拿全了，对白是 100%，但任务脚本（`.ysc`）仍然是 0。**
> 所以"所有任务"能列出来，"所有过场里出现谁"也能自动生成；
> 但"任务里生成了哪些 ped、按什么顺序说话/行动"还不能 100% 还原。

---

## 0. 直接回答（4 条）

1. **剧情文件没有"全解"**：任务定义 **270/270**、本地化对白 **1929/1929**、过场动画包 **181/181**（本轮刚补齐）、角色模型 **283/283**；
   但 **任务脚本 `.ysc` = 0**（`script_rel.rpf` 的 TFIT2 key `0xC6` 不在密钥表里）。
2. **任务清单是完整的**：**270 条** = 105 主线 + 121 支线/随机/赏金 + 21 物品请求 + 15 配方 + 8 线上。
3. **角色能"按过场"列出来**：181 个过场包 → 从 clip 名解析出 **181 个出场角色**；
   其中 **106 个已进名册**，**75 个未进**（多数是角色型/群众，约 15 个可识别具名）。
4. **"每个任务出现谁"已经能自动生成**（`mission_cast.csv`）：95/105 主线、97/121 支线有 cast；
   剩下 72 条没有匹配到过场包：**物品请求 21 + 配方 15 + 赏金 12 + 随机 10 + 随机剧情 2 + 线上 2 + 主线 10**。
> 其中 8 条"主线无包"（MUD6 / HNT1 / DST1 / DST3 / MR52 / MR53 / BE22 / AB21 / RDCH3 / CABR01）更像**任务 ID 与包名不对应**，
> 不是真的没有过场；这 8 条需要人工核对包名映射。**但 clip 名有复用/幽灵片段，cast 是初筛，需按镜头复核。**

---

## 1. 剧情文件覆盖表

| 类别 | 游戏内 | 已解包 | 覆盖率 | 位置 / 说明 |
|---|---|---|---|---|
| **任务定义** `missions.meta` | **270** | **270** | **100%** | `update_1.rpf → common/data/missions.meta`（本轮新发现） |
| **本地化对白** `.yldb` | **1 929** | **1 929** | **100%** | 339,635 条（含中文 153,830 条）→ `export/story/dialogue_chinesesimp.txt` |
| **过场动画包** `cuts_*.rpf` | **181** | **181** | **100%** | 本轮补齐：5,237 个 `.ycd/.yad`，1.2 GB → `work/story/cutscene_all/extracted/` |
| **过场 CG** `.bk2` | 65 | 65 | 100% | 片头/卡通/回忆，**不是**主线过场 |
| **语音包** | 36（PEDS_00）+ 其他 | 36 样本 | 部分 | 只抽了样本，未全量 |
| **任务脚本** `.ysc` | 未定位 | **0** | **0%** | `script_rel.rpf`，TFIT2 key `0xC6` 缺失 |
| **过场角色模型** `cs_*` | **283** | **283** | **100%** | 282 个剧情角色目录 + 2 个主角 |

### 1.1 本轮补的东西

| 之前 | 现在 |
|---|---|
| 过场包只有 **3 个样本**（`fin1/gng1/mud1`） | **181/181 全部解出**（5,237 个文件） |
| 任务清单只有"130 个据点/38 个地名" | **270 条任务定义**（含主线/支线/赏金/物品请求） |
| 角色只有"283 个模型 + 85 个有名字" | **181 个过场出场角色 + 106 个进名册 + 75 个待补** |

---

## 2. 任务清单：270 条

| 分类 | 数量 | 说明 |
|---|---|---|
| **主线 第 1 章** | 6 | WNT1… |
| **主线 第 2 章** | 18 | MUD2… |
| **主线 第 3 章** | 17 | BRT1… |
| **主线 第 4 章** | 15 | MOB1… |
| **主线 第 5 章** | 9 | GUA1…（瓜玛） |
| **主线 第 6 章** | 19 | DST5… |
| **尾声 上（第 7 章）** | 10 | FIN1… |
| **尾声 下（第 8 章）** | 11 | MAR2… |
| **主线小计** | **105** | 与游戏内 104~105 个主线任务吻合 |
| **随机事件/陌生人** | 96 | `RANDOM_CHARACTER` |
| **随机剧情角色** | 12 | `RANDOM_STORY_CHARACTER` |
| **赏金任务** | 13 | `BOUNTY_HUNTING` |
| **支线小计** | **121** | |
| **物品请求** | 21 | `ITEM_REQUEST` |
| **配方（非剧情）** | 15 | `RECIPE` |
| **线上/无尽夏日** | 8 | `ENDLESS_SUMMER` |
| **合计** | **270** | |

产物：`export/levels/world/missions.csv`（270 行：ID / 分类 / 类型 / 描述 key / 过场包 / 是否已解）。

### 2.1 ✅ 任务中文名已解析（2026-10-19）

`global.yldb` 的 key→string 映射已打通（`tools/yldb_keys.py`）：

```
hash 表项  +0x00 u32 joaat(key)
           +0x08 u32 node_ptr
node       +0x20 u32 str_ptr     （字符串区起点）
           +0x28 u32 len         （UTF-8 字节数，含 \0）
字符串     数据在 str_ptr + 0x10，读 len 字节
```

于是 `WNT1` → **西部亡命之徒**、`WNT1_DESC` → 官方简介、`MUD1` → **东部边境**、
`MOB1` → **文明之乐**、`DST1` → **老朋友们**。**270 条任务中 250 条拿到中文标题、250 条拿到官方简介**，
并顺带解析出 **308 条任务挑战**（`challenges_sp_missions.meta` → `goals_sp_missions.meta` 的 label key → yldb）。

产物：`export/levels/world/missions_story.csv`、`mission_challenges.csv`、`RDR2_剧情任务解析.md`。

---

## 3. 过场 → 角色映射（本轮新能力）

### 3.1 怎么做的

过场包的 `.ycd` clip 名里直接带角色 ID：

```
pack:/cs_mrsadler_dual.clip
pack:/cs_charlessmith_face.clip
pack:/player_zero_face.clip
```

正则 `(cs_*|player_*)_(face|dual)` → 每个包的角色集合。

### 3.2 结果

| 指标 | 数值 |
|---|---|
| 过场包 | 181 |
| 有 cast 的包 | **181（100%）** |
| 解析出的出场角色 | **181** |
| 其中已进名册 | **106** |
| 其中未进名册 | **75** |
| 主线任务有 cast | **95 / 105** |
| 支线任务有 cast | **97 / 121** |
| 没有匹配到过场包的任务 | **72**（物品请求 21 / 配方 15 / 赏金 12 / 随机 10 / 随机剧情 2 / 线上 2 / 主线 10） |

**出场最多的角色**：

| 角色 | 出场任务数 |
|---|---|
| 亚瑟·摩根 | 174 |
| 约翰·马斯顿 | 124 |
| 达奇·范德林德 | 38 |
| 比尔·威廉姆森 | 32 |
| 哈维尔·埃斯奎拉 | 26 |
| 阿比盖尔 / 查尔斯 / 迈卡 / 大叔 | 23 |
| 施特劳斯 / 莎迪 | 20 |
| 何西阿 | 16 |

产物：
- `cutscene_cast.csv` — 181 个包的角色列表
- `mission_cast.csv` — 270 条任务的角色列表（含 cast_count）
- `actor_coverage.csv` — 181 个角色分别出现在多少包/任务、属于哪些章节

> ⚠️ **cast 是初筛**：clip 名可能被多个场景复用，或残留"幽灵片段"。
> 例如 `MUD1`（第 1 章）的 cast 里出现了飞鹰，明显是复用/误匹配。
> 要精确到"这个镜头里谁在"，还得用 ycd 的 scene/actor 轨道或 `.ysc` 复核。

---

## 4. 角色覆盖：283 → 142 → 181

| 层面 | 数量 | 说明 |
|---|---|---|
| `cs_` 过场角色模型 | **283** | 全部导出（228 男 + 55 女） |
| 过场里实际出现（clip 名） | **181** | 有些模型只在 gameplay/多人里用，不出现在过场 |
| 已进详细名册 | **142** | 势力 / 常驻地 / 置信度（高 65 / 中 46 / 低 31） |
| 过场出现但未进名册 | **75** | 约 15 个可识别具名，其余是角色型/群众 |

### 4.1 75 个未进名册的构成（抽样）

| 类型 | 例子 | 处理 |
|---|---|---|
| 可识别具名（~15） | Angus/David Geddes、Ansel Atherton、Mrs. Calhoun、Hector Fellowes | 已在本轮补进名册或标为待核 |
| **角色型**（~50） | `cs_chainprisoner_01/02`（锁链囚犯）、`cs_warvet`（老兵）、`cs_ringmaster`（马戏团主）、`cs_tigerhandler`（驯虎师）、`cs_poisonwellshaman`（投毒萨满） | 没有独立剧情身份，按"角色型"处理 |
| **通用**（~10） | `cs_genstorymale/female`（通用剧情男女）、`cs_nbxexecuted`（黑水被处决者） | 群众角色，不进名册 |

### 4.2 有名字的医生（上一轮问的）

| 名字 | ID | 常驻地 | 置信度 |
|---|---|---|---|
| 希金斯医生 | `cs_drhiggins_ms1` | 待核 | 中 |
| 马尔科姆·麦金托什医生 | `cs_drmalcolmmacintosh_ms1` | 待核 | 中 |
| 圣丹尼斯医生 | `cs_sddoctor_01_ms1` | 圣丹尼斯 | 高 |
| 克里奥尔医生 | `cs_creoledoctor_ms1` | 瓜玛/莱莫恩 | 中 |

> 这 4 个是**有名字/有固定身份的医生**；城镇里还有 8 类"角色型"医生（瓦伦丁、圣丹尼斯等），
> 见 `RDR2_骑砍2落地_势力与NPC.md` §4.11 的服务 NPC 矩阵。

---

## 5. 为什么还不能说"所有角色都考虑了"

| # | 缺口 | 影响 | 能不能补 |
|---|---|---|---|
| 1 | **任务脚本 `.ysc` = 0** | 不知道任务里生成哪些 ped、触发顺序、分支 | 脚本包已在 `update_2.rpf` 找到并抽出（113 MB，tag `0xC6`），只缺 AES key #198；目标与失败条件已从任务 yldb 还原 |
| 2 | **`metapeds.ymt` 未解** | 无法精确还原"任务专用 ped"（店员、赏金目标、随机 NPC） | 需要按 CodeWalker 的 PSIN 定义重写解析 |
| 3 | **cast 初筛有误匹配** | 个别任务会多出不该出现的角色（如 MUD1 的飞鹰） | 用 ycd scene 轨道 / `.ysc` 复核 |
| 4 | **72 条任务没有匹配到过场包** | 物品/配方/线上/部分赏金没有 cast；10 条主线更像包名映射问题 | 人工核对包名 + 用 `.ysc` 补 |
| 5 | **语音包只抽了 36 个样本** | 听不到全部任务语音 | 全量抽 `x64/audio/sfx/PEDS_*.rpf` |
| 6 | ✅ **任务中文名已映射** | 250/270 有中文标题（余 20 条为配方/未本地化赏金/未命名事件） | 已解 `global.yldb` key→string，见 §2.1 |

> 一句话：**"角色名单"和"过场出场"已经基本齐了；"任务里怎么用这些角色"还差 `.ysc` 这一层。**

---

## 6. 下一步（按收益排序）

1. **全量解 `script_rel.rpf` 的 `.ysc`**（补 key `0xC6`）—— 一次拿到所有任务的 actor 生成、对话、分支。
2. **用 ycd scene 轨道复核 cast** —— 把 181 个包的 cast 从"初筛"变成"逐镜头"。
3. **解 `metapeds.ymt`** —— 补任务专用 ped 的模型。
4. **解 `global.yldb` 的 key 表** —— 把 270 条任务 ID 变成中文任务名。
5. **全量抽语音包** —— 补齐任务语音。

---

## 7. 产物

| 文件 | 内容 |
|---|---|
| `export/levels/world/missions.csv` | 270 条任务定义（ID / 分类 / 类型 / 过场包 / 是否已解） |
| `export/levels/world/missions_story.csv` | 270 条任务：章序 / 中英标题 / 中英简介 / cast / 对白 / 挑战 |
| `export/levels/world/mission_challenges.csv` | 308 条任务挑战（含中文） |
| `RDR2_剧情任务解析.md` | 主线逐章 + 支线逐线的剧情解析 |
| `export/levels/world/mission_cast.csv` | 270 条任务的角色列表（cast_count + cast） |
| `export/levels/world/cutscene_cast.csv` | 181 个过场包的角色列表 |
| `export/levels/world/actor_coverage.csv` | 181 个角色：出场包数/任务数/章节/是否进名册 |
| `export/levels/world/mission_stats.json` | 任务分类统计 |
| `export/levels/world/cast_stats.json` | 过场/角色覆盖统计 |
| `work/story/cutscene_all/extracted/` | 181 个过场包，5,237 个 `.ycd/.yad`（1.2 GB） |

### 复现

```bash
cd "D:/BrainMaker/大镖客2解包分析"

# 1) 取任务定义（update_1.rpf）
RP=tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe
$RP extract "H:/EPICGAMES/RedDeadRedemption2/update_1.rpf" work/meta "common/data/missions.meta"

# 2) 全量过场包（anim_0.rpf → 181 个 cuts_*.rpf → 再逐个解）
$RP extract "H:/EPICGAMES/RedDeadRedemption2/anim_0.rpf" work/story/cutscene_all "anim/cutscene/cuts_" --recurse
for f in work/story/cutscene_all/anim/cutscene/*.rpf; do
  name=$(basename "$f" .rpf)
  $RP extract "$f" "work/story/cutscene_all/extracted/$name" ""
done

# 3) 任务清单 + 过场 cast
python tools/build_mission_inventory.py
python tools/build_cutscene_cast.py
```
