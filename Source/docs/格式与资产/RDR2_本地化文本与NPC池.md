# 本地化文本挖到什么程度 + 路人 NPC 池

> 回答两个问题：**① 本地化文件是不是挖透了；② 能不能拿里面的名字批量刷 NPC。**
> 结论先说：**本地化基本挖透了（`global.yldb` 100% 建了中英索引）**；
> **NPC 池里还有 102 个具名人物没进名册**，可以拿来刷；
> 但**路人 ped 本身没有名字**，且**"某个路人穿哪几件"还没解**（卡在 PSIN 格式）。

---

## 1. 本地化包的结构与挖掘状态

游戏里简体中文在 `data_0.rpf`：

```
data/lang/chinesesimp_rel.rpf    6.4 MB（压缩）→ 解出 26 MB
  └─ 1 929 个 .yldb              （每个是一个"文本库"：global / 角色台词 / 报纸 / 帮助 / 制作名单…）
american_rel.rpf                 同一套 key，英文
```

### 1.1 数量

| 指标 | 数值 |
|---|---|
| `.yldb` 文件 | **1 929** |
| 解出体积 | 26 MB |
| 含中文的字符串 | **149 976** 条（按 CJK 字符过滤） |
| 其中 `global.yldb`（名词/地名/物品/信件） | 18 377 条中文 |
| 其中角色台词库（arthur / john / dutch / pearson …） | 约 13 万条 |

### 1.2 已建成什么

| 产物 | 内容 | 覆盖 |
|---|---|---|
| `raw/lang/{en,zh}/global.yldb` | 原始文本库 | 100% 文件 |
| `tools/official_name_map.py` | 用 **hash → (英文, 中文)** 配对 | **21 733 条** key |
| `export/story/dialogue_chinesesimp.txt` | 全部台词（含说话人 bank） | **341 683 条** |
| `deliverable/handoff/official_names_settlements.csv` | 46 个据点官方中文 | 100% |

### 1.3 `global.yldb` 到底挖干净没有

`global.yldb` 里能提取到 14 333 条**不重复中文串**（≥3 个汉字），
哈希表能索引到 21 733 个 key、覆盖其中 10 745 条；
剩下的 3 650 条看着像"漏了"，但**抽样 1 000 条，1 000 条都是已覆盖长文本的子串**
（`.yldb` 里长信件是一整段，我的正则会在控制字符处把片段切出来）。

> 所以：**`global.yldb` 的名词/信件已经全在索引里**，"27% 未覆盖"是统计口径问题，不是漏挖。

### 1.4 真正没挖的（不是本地化）

| 项 | 状态 | 影响 |
|---|---|---|
| **`metapeds.ymt`（1086 个 PSIN 二进制）** | ❌ **没解** | 拿不到"某个 ped 由哪几件衣服组成"，也就是**不能自动还原路人穿搭** |
| `.yldb` 里的 help / news / credit | 文件已解出，但没做"中文 txt 导出" | 都是提示/报纸/名单，不含地名与人名，优先级低 |
| `assets_tints.ymt`（配色调色板） | ❌ 没解 | 服装的"真配色"拿不到，只能用中性色近似 |

---

## 2. 角色：查看器里能看到多少

| 类别 | 数量 | 查看器 | 说明 |
|---|---|---|---|
| 剧情角色 + 主角 + 动物 | **408** | ✅ **全部 3D 可转** | `export/npc/index.html`（`打开查看器.bat`）；每人带贴图、可切全身/头部特写 |
| 通用路人部件（衣服/头/发/手…） | **6 106** | ✅ **全部有缩略图** | `export/viewer/clothing.html`（本轮新增）；2D 剪影 + 平均色，**不是 3D** |
| 单件衣服的 3D | 按需 | ⚠️ 需单件导出 | `rdr2_npc_export.py --ydd <文件>` → glb；6106 件全导代价太大（约 2~4 小时、十几 GB） |

> 服装缩略图是**点云投影**（96×144）：能看清"形状 + 主色 + 是披肩/马甲/长裙"，
> 适合挑衣服；要看细节还是单件导 3D。生成脚本 `tools/build_clothing_thumbs.py`（6106 件 5.5 分钟）。

---

## 3. NPC 池：1086 个 ped 配方

`packs/base/data/metapeds/metapeds.rpf` 里是 **1 086 个 `.ymt`**（每个 = 一个 ped 的"配方"）：

| 类别 | 数量 | 用途 | 有模型？ |
|---|---|---|---|
| `cs_` 过场角色 | **269** | 剧情/支线用 | ✅ 已导出 glb（282 个目录，含男女变体） |
| `a_c` 动物 | 239 | 马/鹿/狼… | ✅ 已有 118 种 glb |
| `u_` 独特人物 | 158 | 有专门外观的 NPC | ⚠️ 模型在 `metapeds_u.rpf`，需配方才拼得出来 |
| `re_` 随机事件 | 119 | 路边随机事件 | ⚠️ 同上 |
| `a_m`/`a_f` 路人 | 116 | **最常见的"平民"** | ⚠️ 只解出部件，配方未解 |
| 其它（`mes_`/帮派/执法…） | 85 | 任务/帮派/警力 | ⚠️ 同上 |
| `rcsp_` 随机遭遇预设 | 29 | 线上/随机遭遇 | ⚠️ 同上 |
| 主角 | 2 | 亚瑟 / 约翰 | ✅ |

> **关键限制**：这 1086 个是"配方名"，不是模型。真正的「这个路人穿哪件衬衫」在 PSIN 里，
> 现在只能拿到 3 653 个散件 + 282 个 `cs_` 整人。
> 也就是说：**剧情角色可以直接刷；路人目前只能"用通用部件自己搭"。**

### 3.1 可以自由搭的部件

`raw/npc/models/generic/` 3 590 件（男 2 032 / 女 1 041），按槽位：
外套 340、马甲 208、连体马甲 199、上衣 173、衬衫 148、连体外套 121、裤子 223、靴子 228、帽子 251、头发 386、头 428…

---

## 4. 还有 102 个具名 NPC 没进名册（可直接用）

从 `global.yldb` 里筛"英文 First Last → 中文带 ·"的条目，再去掉名册里已有的 142 人，
剩下 **102 个具名人物**，都是支线/陌生人/传奇枪手/赏金目标：

| 英文 | 官方中文 | 备注 |
|---|---|---|
| Billy Midnight | **比利·米德奈特** | 传奇枪手（火车上决斗） |
| Flaco Hernandez | **弗拉科·埃尔南德斯** | 传奇枪手（雪山） |
| Emmet Granger | **埃米特·格兰杰** | 传奇枪手（养猪场） |
| Otis Skinner | **奥蒂斯·斯金纳** | 传奇枪手 |
| Black Belle | **黑衣美人** | 传奇枪手（已在校正表里） |
| Jeremy Gill | 杰里米·吉尔 | 钓鱼名人 |
| Chick Matthews | 奇克·马修斯 | 赏金目标 |
| Anthony Foreman | 安东尼·福尔曼 | 福尔曼兄弟帮 |
| Marshall Thurwell | 马歇尔·瑟韦尔 | 警长（原表标"待核"） |
| Hector Fellowes | 赫克特·费洛斯 | 支线 |
| …（共 102 条） | | |

完整清单：**`deliverable/handoff/npc_names_extra.csv`**
（列：`name_en / name_zh / guess_id / matched_glb`；102 条里 6 条能按 ID 规则自动对上已导出的 glb，其余需要手工指定模型或走通用部件）

> 怎么用：这批名字是**官方译名**，可以直接写进骑砍2 的 NPC 名字表；
> 但 RDR2 里他们没有独立的 `cs_` 模型（多数是通用 ped + 专属头部），所以要么手工配外观，要么等 PSIN 解出来。

---

## 5. 结论

| 问题 | 回答 |
|---|---|
| 本地化挖透了吗 | **`global.yldb` 挖透了**（21 733 key，抽样 1000 条无遗漏）；台词 34 万条也全导出了；**没挖的是 `metapeds.ymt` 的 PSIN 和 `assets_tints.ymt`，这两块不是本地化，但决定了"路人长什么样/穿什么色"** |
| 有很多路人名字能刷 NPC 吗 | **名字：有 102 个额外具名人物**（官方中文），够做一批支线/赏金/枪手 NPC；**路人（a_m/a_f 那 116 个）本身没名字**，只有内部 ID |
| 查看器能看到所有角色和服装吗 | 角色 **408 全 3D**；服装 **6106 全有 2D 缩略图**，3D 需单件导出 |

---

## 6. 复现

```bash
# 1) 抽本地化包（两种语言）
cd tools/rdr2rpf/bin/Release/net9.0
./rdr2rpf.exe extract "H:/EPICGAMES/RedDeadRedemption2/data_0.rpf" <out> "chinesesimp_rel"
./rdr2rpf.exe extract "H:/EPICGAMES/RedDeadRedemption2/data_0.rpf" <out> "american_rel"
# 把 global.yldb 放到 raw/lang/{en,zh}/

# 2) 查/比对
uv run python tools/official_name_map.py --lookup "Horseshoe Overlook"
uv run python tools/official_name_map.py --search "mercer"

# 3) 服装缩略图
uv run python tools/build_clothing_thumbs.py
uv run python tools/build_clothing_catalog.py
```
