# RDR2 名单篇：常驻角色 / ped 模型 / 环境人群模型集

> 配套文档：**`docs/世界与地编/RDR2_NPC生成与行为机制.md`**（讲"怎么刷、刷完干什么"）。
> 本篇只干一件事：**把名单和模型全部列出来、能机读、能复核**。
> 取证：脚本 1491.50 ｜ 数据：`ambientpedmodelsets.meta` + 5 个 `metapeds*.rpf` ｜ 日期 2026-11-01

---

## 0. 七份清单在哪

全部在 **`deliverable/manifests/`**（机读，UTF-8-BOM，Excel 直接开）。

| 文件 | 行数 | 一行 = 什么 | 主要列 |
|---|---:|---|---|
| **`perschar_roster.csv`** | **950** | 一个常驻角色槽位 | `index / name / **name_zh** / role_zh / **real_name_en / real_name_zh / full_name_en / full_name_zh / real_name_evidence** / zone_id / **zone_code / zone_name_en / zone_name_zh / zone_name_source** / zone_min..max / in_zone_range / flags_dec / flag_bits / source_line / note`（**26 列**） |
| `perschar_by_zone.csv` | 49 | 一个区域 | `zone_id / zone_code / zone_name_en / **zone_name_zh** / zone_name_source / 区间 / 人数 / 店主数 / 执法数 / 前缀画像 / 中文样例 / 原名样例` |
| **`ped_model_catalog.csv`** | **1,272** | 一个 ped 模型 | `model / package / kind / rpf_entry_size / name_hash / used_by_n_modelsets` |
| **`ambient_modelsets.csv`** | **2,468** | 「模型集 × 模型」一条（2,461 条模型 + 7 个空集占位行） | `set_name / ai_memory_group / spawn_distance / model / probability / loadout / outfit / rarity / time_of_day / set_source_line` |
| `ambient_modelsets_summary.csv` | 971 | 一个模型集 | `set_name / 组 / 刷出距离 / 模型数 / 全部模型 / outfit / rarity / 源行号` |
| `ambient_by_group.csv` | 32 | 一个 AI 记忆组（31 个命名组 + `(none)`） | `组名 / 集数 / 模型条目数 / 刷出距离构成` |
| **`character_names.csv`** | **98** | 一个「人物名键」（见 1.6；3 个命名空间） | `key / namespace / name_en(GXT) / name_zh(global.yldb) / n_refs / scripts / perschar_slots` |

**生成方式**：`python tools\perschar_lists.py`（管线脚本，已登记 `tools/README.md`；见 §6）。

---

## 1. 常驻角色名单（950 条）

### 1.1 总量与槽位占用

| 指标 | 数值 | 说明 |
|---|---:|---|
| `func_34()` 注册调用 | **950** | `init_all_sp.c` 第 185–1017 行区间内 |
| 去重后的角色名 | **942** | 8 个名字跨区复用（见 1.3） |
| 全局槽位 | **954** | `func_145`：`0 ≤ index < 954` |
| 实际用到的槽位 | **949** | 几乎全满 |
| 空槽 | **5** | `738`、`739`、`902`、`903`、`953` |
| 涉及区域 | **49** | 48 个有区间定义 + 1 个 `zone = -1` |

### 1.2 按区域汇总（`perschar_by_zone.csv` 全文）

**区名不是猜的**：每个据点脚本里都写死了自己的区域下标 ——
`annesburg.c:668` 是 `Global_1888801[78].f_4`、`valentine.c:811` 是 `[76]`、`saintdenis.c:784` 是 `[5]`、
`rhodes.c:829` 是 `[105]`、`blackwater.c:755` 是 `[38]`……
一次 grep 全部 `Global_1888801[<id>]` 就能把「id → 脚本 → 地名」对上（**32 个区**由此定名），
另外 6 个区靠「perschar 前缀 = 本项目据点编码」对上，2 个靠间接线索。中文取 `.yldb` 官方译名
（`deliverable/manifests/official_names_settlements.csv`）。

| 区 id | 槽位区间 | 人数 | 店主 | 执法 | **区名（中文）** | 命名证据 |
|---:|---|---:|---:|---:|---|---|
| -1 | *不校验* | 99 | 1 | 0 | **无区域校验** | `func_34` 跳过区间检查 |
| 3 | 644–656 | 13 | 0 | 0 | **拉格拉斯** | `script:lagras.c` |
| 5 | 137–324 | 188 | 10 | 0 | **圣丹尼斯** | `script:saintdenis.c` |
| 6 | 657–658 | 2 | 0 | 0 | **奥兰治种植园** | `prefix+code`（ORA=ora） |
| 11 | 807–833 | 27 | 0 | 0 | **伐木营** | 推断：`long_update` 的 `ea_logCampRestrict` |
| 21 | 780–782 | 3 | 0 | 0 | **未定（前缀 PAI）** | — |
| 22 | 715–723 | 9 | 0 | 0 | **叉角羚牧场** | `script:pronghornranch.c` |
| 23 | 801–801 | 1 | 0 | 0 | **未定（前缀 RGS）** | — |
| 26 | 472–502 | 31 | 1 | 2 | **草莓镇** | `script:strawberry.c` |
| 28 | 802–803 | 2 | 0 | 0 | **华莱士车站** | `prefix+code`（WAL=wal） |
| 29 | 744–744 | 1 | 0 | 0 | **未定（前缀 WTC）** | — |
| 32 | 325–344 | 20 | 0 | 0 | **西西卡监狱** | `script:sisikapenitentiary.c` |
| 35 | 691–700 | 10 | 0 | 0 | **华莱士堡** | `script:oldfortwallace.c` |
| 38 | 508–553 | 46 | 5 | 0 | **黑水镇** | `script:blackwater.c` |
| 42 | 794–798 | 5 | 0 | 0 | **切兹波特** | `prefix+code`（CHE=che） |
| 56 | 701–708 | 8 | 1 | 0 | **瓦匹缇** | `script:wapiti.c` |
| 61 | 380–381 | 2 | 0 | 0 | **未定（前缀 LEV）** | — |
| 64 | 736–740 | 3 | 0 | 0 | **未定（前缀 CRD）** | — |
| 65 | 566–588 | 23 | 0 | 0 | **康沃尔煤焦油厂** | `script:cornwallkerosene.c` |
| 66 | 745–750 | 6 | 0 | 0 | **未定（前缀 CRO）** | — |
| 68 | 554–565 | 12 | 0 | 0 | **唐斯牧场** | `script:downsranch.c` |
| 69 | 589–612 | 24 | 0 | 0 | **翡翠牧场** | `script:emeraldranch.c` |
| 70 | 751–754 | 4 | 0 | 0 | **未定（前缀 GRH）** | — |
| 72 | 733–735 | 3 | 0 | 0 | **未定（前缀 LAR）** | — |
| 75 | 503–506 | 4 | 0 | 0 | **未定（前缀 SWA）** | — |
| 76 | 0–63 | 69 | 7 | 2 | **瓦伦丁** | `script:valentine.c` |
| 77 | 731–732 | 2 | 0 | 0 | **阿伯丁猪场** | `prefix+code`（APF=abe） |
| 78 | 382–431 | 50 | 1 | 2 | **安尼斯堡** | `script:annesburg.c` |
| 82 | 659–690 | 32 | 0 | 0 | **布彻河村** | `script:butchercreek.c` |
| 86 | 768–772 | 5 | 0 | 0 | **未定（前缀 MLH）** | — |
| 89 | 799–800 | 2 | 0 | 0 | **未定（前缀 RKS）** | — |
| 92 | 443–471 | 29 | 1 | 0 | **范霍恩贸易站** | `script:vanhorntradingpost.c` |
| 93 | 613–625 | 13 | 0 | 0 | **布雷斯韦特庄园** | `script:braithwaitemanor.c` |
| 95 | 626–641 | 16 | 0 | 0 | **卡利加种植园** | `script:caligahall.c` |
| 96 | 741–743 | 3 | 0 | 0 | **未定（前缀 CFJ）** | — |
| 97 | 642–643 | 2 | 0 | 0 | **克莱蒙斯岬** | `prefix+code`（CLE=cle） |
| 100 | 755–763 | 9 | 0 | 0 | **未定（前缀 DAI）** | — |
| 101 | 804–806 | 3 | 0 | 0 | **未定（前缀 SCM）** | — |
| 102 | 764–767 | 4 | 0 | 0 | **未定（前缀 LNS）** | — |
| 105 | 69–136 | 68 | 3 | 2 | **罗兹** | `script:rhodes.c` |
| 110 | 724–730 | 7 | 0 | 0 | **石兰贸易站** | `script:manzanitapost.c` |
| 115 | 345–375 | 31 | 0 | 1 | **风滚草镇** | `script:tumbleweed.c` |
| 116 | 783–790 | 8 | 0 | 0 | **未定（前缀 RKF）** | — |
| 117 | 507–507 | 1 | 0 | 0 | **未定（前缀 BEN）** | — |
| 120 | 432–442 | 12 | 0 | 0 | **犰狳镇** | `script:armadillo.c` |
| 124 | 791–793 | 3 | 0 | 0 | **脊木农场** | `script:ridgewoodfarm.c` |
| 125 | 376–379 | 4 | 0 | 0 | **未定（前缀 TWR）** | — |
| 126 | 773–779 | 7 | 0 | 0 | **麦克法兰牧场** | `prefix+group` MACFARLANESRANCH_RESIDENTS |
| 128 | 834–857 | 24 | 0 | 0 | **牧场营地** | 推断：`EA_RCAMP` 命名 |

> **32 个区有名、17 个区只有前缀**（PAI/RGS/WTC/LEV/CRD/CRO/GRH/LAR/SWA/MLH/RKS/CFJ/DAI/SCM/LNS/RKF/BEN/TWR）。
> 这 17 个区一共只占 66 个槽位（7%），而且都是小牧场/小站；要补全只差 `regions.pso` 那张表（本轮没抽到）。

> **一句话读法**：圣丹尼斯 188 人 > 瓦伦丁 69 ≈ 罗兹 68 > 安尼斯堡 50 > 黑水镇 46 > 布彻河村 32
> ≈ 风滚草镇 31 ≈ 草莓镇 31 > 范霍恩 29 —— 这就是"为什么圣丹尼斯最有生活气息"的直接量化。

### 1.3 中文名是怎么生成的（可复核）

`name` 按 `_` 切成词素，逐个查 `tools/perschar_lists.py` 里的 `TOKEN_ZH`（314 个词素全覆盖），
多词再走 `PHRASE_ZH` 做合并，最后拼成 `区域·角色·序号`：

| 原名 | 中文 |
|---|---|
| `SDN_DOCK_WORKER_1` | **圣丹尼斯·码头工人·1** |
| `SDN_DOCK_COTTON_3` | **圣丹尼斯·码头棉花工·3** |
| `VAL_GENERAL_STORE` | **瓦伦丁·杂货铺** |
| `RHD_SHERIFF` | **罗兹·警长** |
| `LAG_FISHERMAN1` | **拉格拉斯·渔夫·1** |
| `EA_LCMP_CHOPPER_2` | **伐木营·伐木工·2** |
| `SDN_STREETKIDS` | **圣丹尼斯·街头小孩** |
| `VHT_DOCK_WORKER`（模型集） | 范霍恩·码头工人 |

规则要点：
1. **首词素是区域前缀**（`SDN_/VAL_/ASB_`…），已经单列成区域列，不在角色名里重复 ——
   `EA_LCMP_*` 这种「前缀 + 地名缩写」会自动去重成 `伐木营·工头`；
2. **专有名词故意保留英文**：`PHR_DAVID_GEDDES` → `DAVID·盖迪斯`（不硬造译名）；
3. **残留英文只有 22 / 950 行**：7 条是人名（`TOM_DICKENS`、`MRS_GEDDES`、`ANGUS_GEDDES`…），
   5 条是未定站点前缀（`CRD/CRO/PAI/MLH/DAI`），5 条是码头未解缩写 `LH_*`，1 条是异常行 `ILO_KICK_NEG`，
   2 条是 `03A/03B` 这种变体后缀；
4. ⚠️ **这些中文是「角色语义翻译」，不是游戏内官方称号** —— RDR2 里路人本来就不显示名字，
   `BARTENDER` 在游戏内也没有「酒保」这条本地化文本。**地名那半截是官方译名**（`.yldb`）。


「人数」= 该区注册条数；「店主」= 带 `1<<20`；「执法」= 带 `1<<21`。
区名一列是**按名字前缀 + 我们据点编码表推断**的，不是官方 `regions.pso`（那个还没抽）。

> 这就是"为什么圣丹尼斯最有生活气息"的直接量化。

### 1.4 码头切片（`SDN_DOCK_*` 30 条，全在区 5）

| 索引 | 名字 | 旗标 | 源行 |
|---:|---|---|---:|
| 148 | `SDN_DOCK_BOAT_GUARD_1` | 0 | 377 |
| 149–150 | `SDN_DOCK_CASTILLE_1..2` | 0 | 378–379 |
| 151 | `SDN_DOCK_CIVIL_1` | 0 | 380 |
| 153–154 | `SDN_DOCK_CONSTR_2..3` | 0 | 382–383 |
| 155 | `SDN_DOCK_CORNWALL_1` | 0 | 384 |
| 156–163 | `SDN_DOCK_COTTON_1..8` | 0 | 385–392 |
| 164–166 | `SDN_DOCK_LH_1..3` | 0 | 393–395 |
| 167–168 | `SDN_DOCK_LH_CAT` / `_DOG` | 0 | 396–397 |
| 169–172 | `SDN_DOCK_LUMBER_1..4` | 0 | 398–401 |
| **173–176** | **`SDN_DOCK_WORKER_1..4`** | 0 | 402–405 |
| 260–261 | `SDN_DOCK_POLICE_1..2` | 0 | 488–489 |

**全部 `flags = 0`** ⇒ 不享受店主/执法那种常驻保护，会被视距剔除后换人。

### 1.5 六个我逐个核对过的边角（都在 CSV 的 `note` 列里）

| # | 现象 | 数量 | 证据 / 解释 |
|---|---|---:|---|
| 1 | **`zone = -1` 的注册** | 99 | `func_34` 里 `if (iParam2 != -1)` 才查区间 ⇒ **−1 = 不做区域校验**。这批是 `GLO_*`(21)/`SCM_*`(17)/`PHR_*`(6)/`CRD_*`(6)/`HEN_*`(6) 等，旗标多为 `256` |
| 2 | **索引越界的 5 条** | 5 | `EA_HMSTD_FOREMAN/WORKER_1/WORKER_2/MAN/WOMAN` = 索引 **64–68**，声明区 76（区间 0–63）。**但都带 `1<<22`**，`func_34` 的越界检查被豁免 ⇒ **照常注册**（不是死数据） |
| 3 | **索引是算出来的** | 1 | `init_all_sp.c:822`：`func_34((1 << 9), joaat("BLW_PRISONER_02"), 38, 0)` ⇒ 索引 **512**（CSV 的 `index_expr` 列保留原式） |
| 4 | **同名跨区复用** | 8 | `CRD_BULL`/`CRD_DONKEY`/`CARMODY_DELL_COWS_PERSCHAR_1` 各 ×3，`AMD_GENERAL_STORE`/`SCM_HORSE_SHOP_OWNER` 各 ×2 —— 同一 perschar 挂到多个点的槽上 |
| 5 | **码头块里混进一条非码头** | 1 | 索引 **152** 是 `ILO_KICK_NEG`，夹在 `SDN_DOCK_CIVIL_1` 与 `SDN_DOCK_CONSTR_2` 之间；且 `CONSTR_2/3` 存在但**没有 `CONSTR_1`** ⇒ 疑似 152 原本是 `SDN_DOCK_CONSTR_1` 被改用途 |
| 6 | **空槽 5 个** | 5 | `738 739 902 903 953` —— 954 个槽里只有这 5 个从来没被写过 |

---

### 1.6 「真名」在另一套人物名键：`DISCOVERABLE_NAME_*` / `ALLY_*` / `COMP_*`

`VAL_SHERIFF` 这种只是**职能名**（= 槽位名）。角色的真名走**独立命名空间**，
由悬赏海报 / 任务触发 `PLAYER::_SET_PLAYER_HAS_DISCOVERED_CHARACTER_NAME_SP()` 解锁 ——
全部 **98 个**，分 3 个命名空间 —— `DISCOVERABLE_NAME_*` 90 个（路人/悬赏目标）、`ALLY_*` 6 个（盟友：Leigh Gray、Archibald MacGregor、Rains Fall、Captain Monroe…）、`COMP_*` 2 个（同伴：Eagle Flies、Kieran）—— **98 / 98 在 `global.yldb` 里都有官方中文**（见 `character_names.csv`）。

⚠️ **命名空间不止一个**：`DISCOVERABLE_NAME_*`（90）是路人/悬赏目标，
`ALLY_*`（6）是任务盟友（Leigh Gray、Archibald MacGregor、Rains Fall、Captain Monroe…），
`COMP_*`（2）是同伴（Eagle Flies、Kieran）。**2026-11-02 第一版只扫了 `DISCOVERABLE_NAME_*`，漏了 `ALLY_*`**，
所以当时罗兹警长"查不到名字"—— 他走的正是 `ALLY_LEIGHGRAY`。

**瓦伦丁警长 = 柯蒂斯·马洛伊（Curtis Malloy）**，三条证据互相咬合：

| 证据 | 位置 | 原文 |
|---|---|---|
| 悬赏海报解锁的就是他 | `bounty_poster.c:1140` | `DISCOVERABLE_NAME_CURTIS_MALLOY` /* GXT: **Sheriff Malloy** */ |
| 瓦伦丁警长办公室那封信 | `main.c:97855` | `DOCUMENT_LETTER_VAL_SHERIFF` /* GXT: **Letter to Curtis from M** */ ⇒ 瓦伦丁警长叫 Curtis |
| 官方中文自己写的 | `global.yldb` | 「如需了解信息或领取赏金，请联系~n~**C·马洛伊警长**。**瓦伦丁**警长办公室」；另有一条独立人名文本「**柯蒂斯·马洛伊**」 |

同一套方法（官方中文里同时出现「镇名 + 警长名」）把别的镇也查了：

| perschar 槽位 | 真名（英文） | 官方中文 | 镇 | 证据 |
|---|---|---|---|---|
| `VAL_SHERIFF` | Curtis Malloy | 柯蒂斯·马洛伊 / 马洛伊警长 | 瓦伦丁 | 见上三条 |
| `SDN_POLICE_CHIEF` | Benjamin Lambert | 本杰明·兰伯特 / 兰伯特警长 | 圣丹尼斯 | 「**圣丹尼斯**警长办公室…**B·兰伯特**」「兰伯特警长…有轨电车站需要大量警力」 |
| `BLW_POLICE_CHIEF` | Oswald Dunbar | 奥斯瓦尔德·邓巴 / 邓巴警长 | 黑水镇 | 「**O·邓巴警长**，**黑水镇**警局」 |
| `STR_SHERIFF` | Vernon Farley | 弗农·法利 / 法利警长 | 草莓镇 | 「**V·法利**…所有赏金都由**草莓镇**警局警长支付」 |
| `RHD_SHERIFF` | **Leigh Gray** | 利·格雷 / 格雷警长 | **罗兹（莱莫恩州）** | 键 `ALLY_LEIGHGRAY` /* GXT: **Sheriff Gray** */；官方中文任务文本「追上**利**」「**利**死了」「**格雷**家族」；罗兹即 Gray 家族地盘 |
| `RHD_DEPUTY` | **Archibald MacGregor** | 阿奇伯德·麦格雷戈 / 副手麦格雷戈 | **罗兹** | `fud1aud.yldb`「**这是我的副手，阿奇伯德·麦格雷戈**」+ GXT「Deputy MacGregor」 |
| **`TBL_SHERRIF`** | **Samuel Freeman** | 萨缪尔·弗里曼 / 弗里曼警长 | **风滚草镇** | 键 `DISCOVERABLE_NAME_SHERIFF_FREEMAN`；城镇介绍「风滚草镇由专横，严苛的**弗里曼警长**统治着」、悬赏信落款「**弗里曼警长，风滚草镇警长办公室**」、整支支线 `spd_sheriffoftumbleweed.c`（`CS_SHERIFFFREEMAN`）；⚠️ 名来自外部资料（见下） |
| `CLE_CLAY` / `CLE_CLIVE` | Clay / Clive | 克莱 / 克莱夫 | 克莱蒙斯岬 | 机械匹配（去前缀即同名键） |
| `PHR_DAVID/ANGUS/DUNCAN_GEDDES`、`PHR_MRS_GEDDES`、`PHR_ABE`、`PHR_TOM_DICKENS` | David / Angus / Duncan Geddes、Mrs Geddes、Abe、Tom Dickens | 大卫 / 安格斯 / 邓肯·格迪斯、格迪斯夫人、亚伯、汤姆·狄更斯 | 无区域 | 机械匹配 |

**还没对上槽位的一个**：

| 人物名键 | 显示名 | 全名 | 数据里能查到什么 |
|---|---|---|---|
| `DISCOVERABLE_NAME_HARMON_THOMAS` | 托马斯警长 | **Harmon Thomas / 哈蒙·托马斯** | 只在 `bounty_poster.c` 里按海报解锁（`func_38` 的 case 13/15/154），没找到镇名绑定 |

⚠️ **拼写坑（我自己踩过）**：风滚草镇的警长槽位拼成 **`TBL_SHERRIF`** —— `SHERIFF` 少一个 `F`。
`grep "TBL_SHERIFF"` 会整个漏掉它，于是上一版我误判成"风滚草镇没有警长槽位、警长是任务脚本临时生成的"。
`init_all_sp.c:583` 才是真身：`func_34(348, joaat("TBL_SHERRIF"), 115, (1 << 21))` —— **348 号，law 旗标，区 115 = 风滚草镇**。
⇒ 教训：查这类"某某有没有槽位"必须用 `SHERR?IF` 正则，别按正确拼写去 grep。

⚠️ **「Samuel / 萨缪尔」在已解包数据里查不到** —— 搜过 1,639 个脚本、`names.txt`（29.4 万条命名）、
`global.yldb`（21,733 条中英文本），**只有姓 Freeman，没有名**。
所以这个名记为**外部资料（用户提供）**，`character_names.csv` 的 `full_name_source` 列写明来源，
不冒充数据结论。

#### 为什么不能把 950 个都解出来：上限分析（2026-11-02）

试过自动配平（脚本内共现 + 行距打分），**结论是这条路不通**，原因很硬：

| 事实 | 数字 |
|---|---|
| perschar 槽位 | **950**（全是职能名） |
| 人物名键（`DISCOVERABLE_NAME_*` + `ALLY_*` + `COMP_*`） | **98** |
| 其中由**剧情/悬赏脚本**（`rcm_*`/`mob*`/`spd_*`…）设置 | **79** ⇒ 这些是悬赏目标/任务角色，**任务脚本自己生成，不占 perschar 槽位** |
| 由**通用内容脚本**（`caten_*`/`act_*`/`beat_*`）设置 | 19 ⇒ 才可能是常驻世界 NPC |
| 机械同名（去区域前缀即同名键） | 9 命中，**8 个采用**（`BANK_TELLER` 是通用称呼，排除） |
| 靠「城镇 + 职务 + 人名」的官方文本反查 | 7（五位警长/局长 + 罗兹副警长 + 弗里曼） |

**共现法实测**：950 个槽位全都被脚本引用过（942 个唯一名），98 个名键也全都被引用；
但把「同一文件内」的候选全排出来是 **4,144 对，0 对 strong**（行距 ≤40），
因为名键设在通用内容脚本里、perschar 引用在任务脚本里，**两者基本不同框**。
口径可复核：对每个槽位名（`joaat("名字")`）与每个人物名键取其出现行号，**只在同一脚本文件内**算最小行距，
≤40 行算 strong、≤300 算 medium。这批数据跑出来是 **4,144 对 / strong 0 / medium 4**。
（一次性探针，按 `docs/AGENTS.md` §1.6「一轮内收口」已连产物一起删除，不留在项目里。）

剩下 10 个"通用脚本类"名键 —— Antony Foreman、Elias Green、Ellie Anne Swan、Esteban Cortez、
Joaquín Arroyo、Joshua Brown、Lindsey Wofford、Mark Johnson、Otis Skinner、Robbie Laidlaw ——
看着像"某镇的人"，但**他们其实是悬赏目标**（`bounty_poster.c` 就是靠海报解锁这批名字），不是常驻槽位。

⇒ 目前 950 个槽位里 **15 个**有真名（7 位官员 + 8 个同名匹配），**上限也就 15~17 个**。不是技术没做到，而是
**800 多个槽位在游戏里根本不存在名字**：`SDN_DOCK_COTTON_3` 就是"第 3 号码头棉花工"，
没有姓名，官方文本里也从没提过。

**唯一还有加分余地的**：`ASB_SHERIFF`（安尼斯堡）查不到名字 —— 数据里只叫「安尼斯堡警长」
（`global.yldb`：「将公主送到~o~安尼斯堡警长~s~处」）。要确认他是不是 `HARMON_THOMAS`，
得解开 `bounty_poster.c` 里**海报 id ↔ 城镇**的映射（`func_38` 的 case 11/13/14/15/17/19 就是海报槽），本轮没解。

⚠️ `name_zh` 的取值优先级：**有官方真名就用真名**（`瓦伦丁·马洛伊警长`），
没有才退回职能名（`瓦伦丁·警长`）；`role_zh` 永远保留职能名，方便按职能统计。

这条也解释了 §1.3 里那些残留英文：**它们本来就是人名/未定站点码**，
现在其中 6 行已经换成官方真名（`大卫·格迪斯`、`汤姆·狄更斯`、`格迪斯夫人`…）。

---

## 2. ped 模型目录（1,272 个）

### 2.1 五个包

`packs/base/data/metapeds/*.rpf` 里每个 ped 一个 `.ymt`（配方），文件名就是模型名。

| 包 | 模型数 | 说明 |
|---|---:|---|
| `metapeds.rpf` | **1,086** | 全集（含 `cs_` 剧情、`a_c_` 动物、`g_m_` 帮派、`u_` 独特人物…） |
| `metapeds_sd.rpf` | 95 | 圣丹尼斯专用（**码头工人在这里**） |
| `metapeds_val.rpf` | 44 | 瓦伦丁专用 |
| `metapeds_rhd.rpf` | 26 | 罗兹专用 |
| `metapeds_asb.rpf` | 21 | 安尼斯堡专用 |
| **合计（互不重复）** | **1,272** | |

按命名分类（`kind` 列）：

| kind | 数量 | 命名 | 用途 |
|---|---:|---|---|
| `scripted/gang/unique` | 318 | `s_` / `g_` / `u_` / `mp_` / `re_` / `mes_` / `rcsp_` | 剧情/帮派/独特人物 |
| `cutscene/player` | 292 | `cs_*` / `player_*` | 过场与主角（**已 3D 导出 354 个**） |
| `animal` | 239 | `a_c_*` | 动物 |
| `other` | 232 | 其它 | — |
| `ambient human` | 191 | `a_m_*` / `a_f_*` / `a_o_*` | **环境人群真正用的就是这 191 个** |

### 2.2 命名规则（照这个读，名字自带信息）

```
a_m_m_sddockworkers_02
│ │ │  └── 地域/团体 + 身份 + 序号
│ │ └──── 性别/体型：m=男 f=女 o=老年
│ └────── 类别：a=ambient(环境) s=scripted(脚本) g=gang(帮派) u=unique(独特) cs=cutscene(过场)
└─────── 物种：m=人 f=动物? 实际：a_c_=动物
```

### 2.3 码头 / 劳力类模型（这次要的）

| 模型 | 包 | 被几个模型集引用 |
|---|---|---:|
| **`a_m_m_nbxdockworkers_01`** | metapeds_sd | **3**（`SDN_DOCKS_MALE`、`NEAR_LUMBER_MALES`、`HORSE_TENDING_MALES`） |
| **`a_m_m_sddockworkers_02`** | metapeds_sd | **1**（`SDN_DOCKS_MALE`） |
| **`a_m_m_sddockforeman_01`** | metapeds_sd | **1**（`SDN_DOCKS_FOREMAN`） |
| `a_m_m_nbxlaborers_01` | metapeds_sd | 4 |
| `a_m_m_sdlaborers_02` | metapeds_sd | 3 |
| `a_m_m_lowersdtownfolk_01/02` | metapeds_sd | 4 / 3 |
| `a_m_m_middlesdtownfolk_01/02/03` | metapeds_sd | 7 / 4 / 4 |
| `u_m_m_nbxliveryworker_01` | metapeds_sd | 0（脚本专用，不进环境人群） |

> **同一个模型被 3 个集复用**这件事说明了：`a_m_m_nbxdockworkers_01` 不是"码头专属皮肤"，
> 而是"**圣丹尼斯的壮劳力外观**"——码头、木料场、马房都会用。

### 2.4 全环境人群引用最多的模型（Top 12）

| 模型 | 包 | 引用集数 |
|---|---|---:|
| `a_c_pronghorn_01`（叉角羚） | metapeds | 41 |
| `a_c_crow_01`（乌鸦） | metapeds | 33 |
| `s_m_m_liveryworker_01`（马夫） | metapeds | 31 |
| `s_m_m_trainstationworker_01`（车站工人） | metapeds | 31 |
| `a_c_bighornram_01` | metapeds | 29 |
| `a_c_fox_01` | metapeds | 26 |
| `s_m_y_newspaperboy_01`（报童） | metapeds | 26 |
| `a_c_deer_01` | metapeds | 23 |
| `a_c_owl_01` / `a_c_hawk_01` / `a_c_skunk_01` / `a_c_coyote_01` | metapeds | 21~22 |

> 注意：`s_m_m_liveryworker_01` 这种 `s_`（脚本）模型也会出现在环境人群集里 ——
> 前缀分的是"资产来源"，不是"会不会被环境刷出来"。

---

## 3. 环境人群：971 个模型集 = 选人池

### 3.1 一个模型集长什么样

```xml
<Item type="CAmbientModelSet">
  <Name>SDN_DOCKS_MALE</Name>              ← 集名（世界里的场景点按名字引用它，见 §5）
  <Models>                                  ← 2,461 条里有 1,701 条是纯 Name+Probability
    <Item>
      <Name>A_M_M_NBXDOCKWORKERS_01</Name>
      <Variations type="NULL" />            ← 762 条这里是 CAmbientPedModelVariations
      <Probability value="1.000000" />      ← 权重（不是归一化概率，见 3.3）
      <TimeOfDay />                         ← 只有 8 条有值
      <InventoryInfoHash />                 ← 本表全空
    </Item>
  </Models>
  <SpawnDistance value="75.000000" />       ← 75 m 内才刷
  <AIMemoryGroup>SAINTDENIS_RESIDENTS</AIMemoryGroup>   ← 记忆/关系组
</Item>
```

`Variations`（762 条）里还带 4 个行为/外观开关：

```xml
<Variations type="CAmbientPedModelVariations">
  <LoadOut>LO_GUARD</LoadOut>                       <!-- 装备组：LO_GUARD×18, LOADOUT_DEFAULT×14, LO_GUARD_LANTERN×2 -->
  <Outfit>AM_ROBTRAIN_REAR_GUARD_01</Outfit>        <!-- 命名外观预设 -->
  <Health />
  <DomesticatedLevel>ADL_DefaultSpecies</DomesticatedLevel>  <!-- 家养/野生：494/155/110 -->
  <RarityLevel>ARL_Common</RarityLevel>             <!-- Common×749, Rare×7, Legendary×3 -->
</Variations>
```

### 3.2 31 个命名记忆组 + `(none)`（= 按城镇分池）

`ambient_by_group.csv` 全文。**「(none)」495 个集没有记忆组**，多数是野外/动物/通用集。

| 组 | 集数 | 模型条目 | 刷出距离构成 |
|---|---:|---:|---|
| (none) | 495 | 1,699 | 100m×455, 0m×26, 250m×11, 200m×1, 90m×1 |
| **SAINTDENIS_RESIDENTS** | **79** | **135** | **75m×54, 100m×25** |
| DUTCH_GANG | 61 | 99 | 100m×61 |
| VALENTINE_RESIDENTS | 50 | 80 | 100m×46, 0m×4 |
| RHODES_RESIDENTS | 45 | 76 | 100m×43, 0m×2 |
| BLACKWATER_RESIDENTS | 43 | 95 | 100m×39, 0m×4 |
| STRAWBERRY_RESIDENTS | 28 | 41 | 100m×21, 0m×7 |
| VANHORNPOST_RESIDENTS | 25 | 32 | 100m×22, 0m×3 |
| ANNESBURG_RESIDENTS | 20 | 38 | 100m×18, 0m×2 |
| BUTCHERCREEK_RESIDENTS | 15 | 22 | 100m×12, 0m×3 |
| TUMBLEWEED_RESIDENTS | 15 | 26 | 100m×15 |
| ARMADILLO_RESIDENTS | 13 | 19 | 100m×13 |
| WAPITI_RESIDENTS | 12 | 18 | 100m×12 |
| LAGRAS_RESIDENTS | 12 | 15 | 100m×12 |
| EMERALDRANCH_RESIDENTS | 12 | 14 | 100m×10, 0m×2 |
| OLDFORTWALLACE_RESIDENTS | 10 | 10 | 100m×9, 0m×1 |
| MANZANITAPOST / MANICATO | 5 / 5 | 5 / 7 | 100m 为主 |
| DOWNSRANCH / MACFARLANESRANCH | 3 / 3 | 4 / 3 | 100m |
| CARMODYDELL / GUTHRIEFARM / MACLEANSHOUSE / HAGENORCHARDS / RIDGEWOODFARM / PAINTEDSKY / RATHSKELLERFORK / HILLHAVENRANCH | 各 2 | 2~3 | 100m |
| FLATNECKSTATION / SCARLETMEADOWS_HORSESHOP / LARNEDSOD / GRANGERSHOGGERY | 各 1 | 1~3 | 100m |

### 3.3 刷新参数的真实分布（这就是"规则"）

| 参数 | 分布 | 读法 |
|---|---|---|
| **集合级 `SpawnDistance`** | 100 m ×846、**0 m ×57**、75 m ×54、250 m ×11、90 m ×1、200 m ×1 | 超过这个距离**根本不生成**。`0` = 只能由脚本显式摆放（不参与环境刷新，推断） |
| **条目级 `Probability`** | 1.0 ×2,410、0.5/0.3/0.1 各 9、0.8 ×7、0.2 ×5、**2.0 ×4**、0.25 ×4… | 出现过 2.0 ⇒ **是权重不是概率**；同一集内按权重抽 |
| **`TimeOfDay`** | 空 2,453 / 有值 8（`Evening Night`） | **时段几乎不在这层控制**；昼夜差异主要来自 `popcycle.dat` 的车流和引擎侧密度 |
| **`RarityLevel`** | Common 749 / Rare 7 / Legendary 3 | 稀有度只标在 `Variations` 里，且极少用 |
| **`DomesticatedLevel`** | DefaultSpecies 494 / Domesticated 155 / Wild 110 | 家畜/野兽分野（决定 AI 与是否可驯养） |
| **`LoadOut`** | LO_GUARD 18 / LOADOUT_DEFAULT 14 / LO_GUARD_LANTERN 2 | 只有守卫类给装备组 |

### 3.4 圣丹尼斯的 54 个 `75m` 集：按阶级/性别/族裔分层

这是本表最有意思的一处——**同一个城里的人不是随机抽的，是先分池再抽**：

| 维度 | 集名 |
|---|---|
| 阶级 | `SDN_UPPERCLASS_*`、`SDN_MIDDLECLASS_*`、`SDN_LOWERCLASS_*`、`SDN_SLUMS_*`、`SDN_LABORERS*` |
| 性别/年龄 | `_MALE` / `_FEMALE` / `_MALE_YOUNG` / `_FEMALE_YOUNG`、`SDN_STREETKIDS` |
| 族裔 | `_WHITE` / `_BLACK` / `_HISPANIC` |
| 职业/特殊 | `SDN_DOCKS_MALE`、`SDN_DOCKS_FOREMAN`、`SDN_POLICE`、`NBX_POLICE`、`SDN_POLICE_CHIEF`、`SDN_COWPOKE`、`SDN_PHOTOGRAPHER`、`SDN_BRONTE_GOON`、`SDN_CHINATOWN_MALE/FEMALE`、`SDN_PROSTITUTE(_FANCY)`、`NBX_WHORES`、`SDN_OBESE_MALE/FEMALE` |

> ⇒ **码头工人 = 两个集**：`SDN_DOCKS_MALE`（75 m，2 个模型）+ `SDN_DOCKS_FOREMAN`（75 m，1 个模型）。
> 街上还有 `SDN_LABORERS*` 三件套（`_` / `_WHITE` / `_BLACK`）作为"劳力"通用池。

---

## 4. 完整刷新链路（把三张表串起来）

```
① 引擎按玩家位置找「区域」                     → region_data.pso（未抽）
   每区给：环境行人倍率 f_10 / 场景行人倍率 f_11 / 用哪张 popcycle 表 f_12
② 世界里的场景点（WORLD_HUMAN_*）带一个
   「模型集名」（如 SDN_DOCKS_MALE）           → 场景点数据（未定位，见 §5）
③ 引擎在该集里按 Probability 抽一个模型        → ambient_modelsets.csv
   过滤：TimeOfDay（8 条才有）/ RarityLevel
   套用：Variations → LoadOut / Outfit / DomesticatedLevel
④ 在 SpawnDistance 内生成实体，登记到 AIMemoryGroup → ambient_by_group.csv
⑤ 脚本层再叠一层：
   · 配额：_RESERVE_AMBIENT_PEDS_TOTAL(n)   ← 刷不出人就说明配额被占满
   · 倍率：SET_AMBIENT_PED_RANGE_MULTIPLIER_THIS_FRAME(f_10)
   · 清场：_SET_AMBIENT_HUMAN_DENSITY_MULTIPLIER_THIS_FRAME(0.0)
⑥ 常驻角色（950 条）不走路 ③~④：
   直接 _CREATE_PERSISTENT_CHARACTER(hash) → _FORCE_SPAWN_PERSCHAR → 挂 schedule
   并 SET_PED_MODEL_IS_SUPPRESSED(model) 把同名环境 ped 按掉
```

---

## 5. 仍然缺的一环：`perschar` → 模型

**这是这次唯一没打通的地方，我把负面结果也记下来，省得下一轮重做。**

| 尝试 | 做法 | 结果 |
|---|---|---|
| 把 `levels/rdr3/perschars.rpf` 抽出来 | 118 个 `.ymt`，合计 11.2 MB | ✅ 已抽到系统临时目录（用完即删，命令见 §6） |
| 在里面搜 950 个人类 perschar 的名字哈希 | 大端 u32 全扫 | ❌ **0 命中** |
| 在里面搜 1,272 个 ped 模型名的哈希 | 同上 | ❌ **0 命中** |
| 搜 ASCII 字符串 | 118 个文件全扫 | ❌ 一个都没有（纯哈希，符合旧结论） |
| 反向验证：动物 perschar | 同上 | ✅ **15 个文件 / 82 条**命中，全是 `VHT_GOAT_1`、`SDN_COW_1`、`VAL_PIGS_NORTH` 这类**牲畜** |
| `metapeds.ymt`（802 KB 主表） | 搜两类哈希 | ❌ 0 命中 |

命中的 15 个文件（动物 perschar 所在）：

```
0x105EB9B1 0x2B1E056D 0x58101F5A 0x593879D2 0x5A057ECE 0x5DB1EFFF 0x5F95F80D
0x82FF2897 0x8B8190DE 0x94245D05 0xA9449881 0xB488D319 0xBC8780D4 0xD01658E5 0xFF85C7E0
```

**结论**：`perschars.rpf` 里放的是**牲畜类** perschar 的出生定义；**人类 perschar 的"名字→模型"表不在这两个文件里**。

> 🔴 **2026-11-02 补：这张"表"可能根本不存在。** 三条新证据：
> 1. `PERSCHAR::_GET_PERSCHAR_MODEL_NAME(h)` 是**读当前模型**，不是查静态表 —— 它在
>    `_CREATE_PERSISTENT_CHARACTER` **之前**就被调用（`abigail2_1.c:78350`）。
> 2. 还有一个**改模型**的原生 `PERSCHAR::_0x8BC555034A5A5E8C(h, modelHash)`，
>    全脚本 **864 次**，第二参数**全部**是 `Global_40.f_4942[i].f_7`（帮派成员表里存的模型哈希）
>    ⇒ 模型是**可写属性**，不是注册时定死的常量。
> 3. `perschars.rpf` 里 118 个 ymt **只有动物**（82 条命中，15 个文件）—— 动物必须显式给模型；
>    人类 0 命中，说明**人类 perschar 定义里压根不存模型**。
>
> ⇒ 所以人类 perschar 的默认模型更可能是**引擎在创建时按区域/popcycle/默认池决定的**，
> 而不是某张"perschar → 模型"的静态清单。要拿全表，只剩**运行时 hook**
> （打印 950 次 `_GET_PERSCHAR_MODEL_NAME` 的返回值）这一条可靠路。

> 🟢 **同日更新：表找到了 —— 不在文件里，在内存里。**（2026-11-02 10:10，游戏运行中实测）
>
> 对运行中的 RDR2 进程**只读**扫描 **7.26 GB**，采到 **6,674** 个 perschar 哈希窗口，做步长/偏移结构恢复得到：
>
> | 项 | 值 |
> |---|---|
> | **记录步长** | **176 字节** |
> | `[+0]` | perschar 身份名哈希 |
> | **`[+4]`** | **模型名哈希**（部分记录为 0） |
> | 命中链 | 750 条连续记录，其中 81 条 `[+4]` 命中模型表 |
>
> 已导出 **92 条配对** → `deliverable/manifests/perschar_model_pairs.csv`
> （**71 条**"内存表 + 名字吻合" = high，**21 条**"仅内存表" = medium）。
> 工具：**`tools/perschar_mem_pairs.py`**（只读，需游戏在跑）。
>
> 样本（全部可在 CSV 里复核）：
> `VAL_SHERIFF`→`cs_valsheriff`／`u_m_m_valsheriff_01`、`RHD_SHERIFF`→`u_m_m_rhdsheriff_01`、
> `SDN_POLICE_CHIEF`→`u_m_m_sdpolicechief_01`、`BLW_POLICE_CHIEF`→`u_m_o_blwpolicechief_01`、
> `SDN_BARTENDER`→`u_m_m_nbxbartender_01`、`PHR_DAVID_GEDDES`→`cs_davidgeddes`、
> `EA_HMSTD_WOMAN`→`u_f_m_htlwife_01`、`LAG_MOTHER1`→`u_f_m_lagmother_01`。
>
> 另一个实测结论：**942 个身份哈希全部出现在内存里**（不只是当前在场的），
> 说明这是"全注册表"；覆盖率只有 92/950 是因为 `[+4]` 只有一部分记录有值（或未被当前加载区解析），
> **换区/跑图后再跑一次，数量会变**。

#### ❌ 找「此刻场上有哪些 NPC」时试过、并已证伪的三条路（2026-11-02，别再走）

| 方法 | 结果 | 为什么不行 |
|---|---|---|
| 最近邻配对（perschar 哈希 ±2KB 内找模型哈希） | 632 "配对"，全错 | 哈希在内存里是密集数组，邻居无关联 |
| 全内存步长聚类 | 最强链 730 条/35 种模型 | 地址在 **`MEM_IMAGE`**（exe 镜像），是**静态模型注册表**：记录里是指针+递增计数器（`00000001/00010001/00020001…`），**没有坐标** |
| 堆（`MEM_PRIVATE`）+ "附近有世界坐标" 过滤 | 3,476 个候选 / 573 "实体簇" | 判据太松：`a_c_horse_americanstandardbred_buckskin ×61` 这种结果说明命中的是**品种/定义表**，不是活实体 |

**结论**：活 ped 在**分页对象池 + handle** 里，光靠哈希扫描区分不了"定义"与"实例"。
要精确答案只能**调原生函数**：`PERSCHAR::_GET_PERSCHAR_PED_INDEX(h)` → `ENTITY::DOES_ENTITY_EXIST` →
`ENTITY::GET_ENTITY_MODEL` → `GET_ENTITY_COORDS`，对 950 个 perschar 句柄跑一遍
（即 `ScriptHookRDR2` 小插件，或 Lua/C# mod），一次就能输出「谁在场 + 模型 + 坐标」。

一个可验证的动物记录现场（`0x105EB9B1.ymt @0xC310`）：

```
0000C310  07 A2 54 98 00 00 00 00 2A 00 00 08 00 00 00 00
          └─ 0x07A25498 = joaat("VHT_GOAT_1")
```

**下一步建议**（按性价比）：
1. **运行时 hook** —— 现在看是**唯一可靠**的路：把 950 次 `_GET_PERSCHAR_MODEL_NAME` 的返回值打印出来；
2. ~~按 `PERSCHAR::_GET_PERSCHAR_MODEL_NAME` 的调用点反查数据文件~~ —— 已证伪：人类 perschar 定义里不存模型（见上面 🔴）；
3. 补抽 `common/data/` 的 `regions.pso` / `region_data.pso` —— 仍值得做，能把区域 id ↔ 官方名字对上。

### 5.1 「一个 perschar 到底带几个模型」——把三层说清楚（2026-11-02 补）

**结论：一个 perschar = 一个 base 模型 + 一个 outfit + 若干 component variation，不是"包含多个模型"。**

| 层 | 是什么 | 数据在哪 | 我们有没有 |
|---|---|---|---|
| **① 模型（metaped）** | 身体/头/配件的基础外形，如 `a_m_m_sddockworkers_02` | `metapeds*.rpf` 的 1,272 个 `.ymt` | ✅ 名单全有（`ped_model_catalog.csv`） |
| **② outfit** | 穿戴/城镇变体，哈希命名 `META_OUTFIT_*` | 脚本里以哈希传入，**71 个具名 outfit** | ✅ 名字全有，**但哪个 perschar 用哪个是运行时变量** |
| **③ component variation** | 模型内部的部件随机组合（胡子/外套/帽） | `metapeds.ymt` 内容 | ❌ 只用了文件名，内容未解 |

**运行时接口（脚本里 15 个 `PERSCHAR::` 原生函数，实测计数）**：

| 原生 | 次数 | 作用 |
|---|---:|---|
| `_IS_PERSISTENT_CHARACTER_VALID` | 9,043 | 有效性 |
| `_FORCE_DESPAWN_PERSCHAR` / `_FORCE_SPAWN_PERSCHAR` | 4,226 / 1,202 | 强制卸载/生成 |
| `_CREATE_PERSISTENT_CHARACTER` | 2,869 | 注册后创建 |
| **`_GET_PERSCHAR_MODEL_NAME`** | **2,734** | **读当前模型**（= 记录 `[+4]`，已由内存扫描证实；可在 `_CREATE_PERSISTENT_CHARACTER` 之前调用）|
| `_GET_PERSCHAR_PED_INDEX` | 2,709 | 拿 ped 句柄 |
| `_SET_PERSCHAR_SCHEDULE` | 1,018 | 作息表 |
| **`_SET_PERSCHAR_OUTFIT`** | **254** | **换装**（覆盖 49 个身份，全是店主/警长/工头这类岗位） |
| `_GET_PERSCHAR_OUTFIT` | 42 | 读当前 outfit |

**71 个 `META_OUTFIT_*` 的构成**：9 个通用状态（`DEFAULT`/`CASUAL`/`WARM_WEATHER`/
`WARM_WEATHER_CASUAL`/`COOL_WEATHER`/`COLD_WEATHER`/`KIDNAPPED`/`INJURED`/`HASH`）
+ **8 个城镇 × 3 变体**（`BLACKWATER_/EMERALDRANCH_/RHODES_/SAINTDENIS_/STRAWBERRY_/TUMBLEWEED_/VALENTINE_/VANHORN_VAR_01..03`）
+ 38 个动物外观（传说鱼 12、白化兽 8、毒鱼 7、灵兽 2 …）+ `FIELD_DRESSING_001`。

⇒ 这就是"街上的圣丹尼斯人穿得像圣丹尼斯人、瓦伦丁人穿得像瓦伦丁人"的实现方式：
**同一个 base 模型 + 不同 `META_OUTFIT_<城镇>_VAR_0N`**。

**950 条身份的构成**：**人形 720 + 动物 230**；942 个唯一名；49 个区域；
最大区圣丹尼斯 188 条，散落（`zone=-1`）99 条。

**名字法能配出多少（推断级，非官方绑定）**：模型名自带「城镇代码 + 职务」
（`u_m_m_valbarber_01` = `val`+`barber`），双条件命中 **69 / 950**
（如 `VAL_SHERIFF`→`u_m_m_valsheriff_01`、`SDN_DOCK_WORKER_1..4`→`a_m_m_sddockworkers_02`）；
只按职务词命中 153 个（噪声大）；**728 个对不上**（多为通用 `a_m_m_*`/`s_m_m_*` 或动物）。

---

## 6. 复现

```powershell
$ROOT = "D:\BrainMaker\大镖客2解包分析"
$RP   = "$ROOT\tools\rdr2rpf\bin\Release\net9.0\rdr2rpf.exe"

# 1) 抽 perschars.rpf（118 个 ymt，11 MB）
& $RP extract "$ROOT\raw\all_packs\perschars\levels\rdr3\perschars.rpf" "$env:TEMP\rdr2_perschar\perschars"

# 2) 5 个 metapeds 包的 TOC（拿到 1,272 个模型名）
foreach ($p in 'metapeds','metapeds_sd','metapeds_val','metapeds_rhd','metapeds_asb') {
  & $RP list "$ROOT\raw\npc\meta\packs\base\data\metapeds\$p.rpf" > "$env:TEMP\rdr2_perschar\toc_$p.txt"
}

# 3) 生成 7 份 CSV
python "$ROOT\tools\perschar_lists.py"

# 4) 抽查（码头切片 + 真名）
Import-Csv "$ROOT\deliverable\manifests\perschar_roster.csv" |
  Where-Object { $_.name -like 'SDN_DOCK*' } | Format-Table index,name,name_zh,zone_id,flag_bits,source_line
Import-Csv "$ROOT\deliverable\manifests\perschar_roster.csv" |
  Where-Object { $_.real_name_zh } | Format-Table name,name_zh,real_name_zh,real_name_evidence

# 5) 真名证据（两条命令就能复核「瓦伦丁警长 = 马洛伊」）
Select-String -Path "$ROOT\raw\script_full\1491.50\bounty_poster.c" -Pattern 'CURTIS_MALLOY'
Select-String -Path "$ROOT\raw\script_full\1491.50\main.c" -Pattern 'DOCUMENT_LETTER_VAL_SHERIFF'
```

**验收口径**：`perschar_roster.csv` = 950 行 / 949 个唯一槽位 / 5 个空槽；`character_names.csv` = 98 行（98/98 有中文）；
`ambient_modelsets.csv` = 2,468 行（2,461 条模型 + 7 个空集）；`ped_model_catalog.csv` = 1,272 行。
三个数字对不上就说明脚本或输入变了。

---

## 7. 本轮新增/改动的文件（**未提交**，按 `docs/AGENTS.md` §0 由用户 `git_gui.py` 提交）

| 文件 | 说明 |
|---|---|
| `docs/世界与地编/RDR2_NPC名单与环境人群表.md` | 本文（新增） |
| `docs/世界与地编/RDR2_NPC生成与行为机制.md` | 机制文档（本轮补「槽位名≠角色名」，见其 §2.4） |
| `deliverable/manifests/perschar_roster.csv` 等 **7 个** CSV | 机读清单（二进制区，不进 git）；本轮新增 `character_names.csv`（98 个人物名键） |
| `tools/perschar_lists.py` | 清单生成器（已登记） |
