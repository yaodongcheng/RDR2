# RDR2 NPC 生成机制与生成后行为（实证版）

> 以**圣丹尼斯码头工人**为例，把「谁被刷出来 → 刷在哪 → 刷出来干什么」这条链
> 从解包数据里逐环节对上号。全部结论带**文件 + 行号**，可以自己 grep 复核。
> 取证日期：2026-11-01 ｜ 游戏版本：脚本反编译自 **1491.50**

---

## 0. 一句话结论

**RDR2 的 NPC 不是「一个刷怪函数」刷出来的，而是三层叠加**：

| 层 | 名字 | 谁决定 | 数据在哪 | 能不能改 |
|---|---|---|---|---|
| **L1** | 环境人群 ambient | 引擎按**区域密度 + 模型集**自己刷 | `ambientpedmodelsets.meta` + `popcycle.dat` + region_data | ✅ 文本可读 |
| **L2** | 常驻角色 PERSCHAR | **脚本显式注册**（954 个槽位） | `init_all_sp.c` + 各据点脚本 | ✅ 反编译源码 |
| **L3** | 事件 / 行为 | **场景点 + schedule + 道具** | `WORLD_HUMAN_*` 场景类型 + `pg_scenario_*.ymt` | ⚠️ 部分可读 |

**码头工人横跨 L1 和 L2**：既有 4 个具名常驻的 `SDN_DOCK_WORKER_1..4`，
也有环境人群用的模型集 `SDN_DOCKS_MALE`（2 个 ped 模型）——
**这就是为什么你在码头既能看到"固定的那几个工人"，也能看到"一直在换脸的路人搬运工"。**

---

## 1. 数据源清单（都在本仓库里，可直接读）

| 文件 | 体积 | 是什么 | 可读性 |
|---|---|---|---|
| `raw/sdn/ai/data/ai/ambientpedmodelsets.meta` | 30,578 行 | **模型集表**：971 个 `CAmbientModelSet`，每个 = 一组 ped 模型 + 刷出距离 + AI 记忆组 | ✅ 纯 XML |
| `raw/sdn/ai/data/levels/rdr3/popcycle.dat` | 2,379 行 | **时段密度表**：按区域 × 2 小时 × 工作日/周末，给车辆/马车/马的密度 | ✅ 纯文本（自带注释） |
| `raw/script_full/1491.50/*.c` | **1,639 个文件** | **全部脚本反编译源码**（含 `init_all_sp.c` 37,206 行） | ✅ 可读 C |
| `raw/sdn/props2/propgroups/pg_scenario_*.ymt` | 9 个 | 场景用**道具组**（砍柴/剥玉米/修鞍/搅拌锅…） | ❌ 二进制 |
| `raw/npc/meta/packs/base/data/metapeds.ymt` | — | **ped 穿搭配方**（PSIN） | ❌ 二进制（已知未解） |

> 🔴 前两项是本轮新发现的**文本层**证据。项目旧文档
> `docs/世界与地编/RDR2_圣丹尼斯还原度盘点.md:124` 写的是"行人密度**未找到**，应在 PSIN 二进制或引擎内" ——
> **这一条现在可以更正**：密度确实不在 PSIN 里，它在「区域数据 + 引擎倍率」里（见 §5）。

---

## 2. L2 层：954 个常驻角色槽位（`init_all_sp.c`）

### 2.1 注册函数在干什么

每个据点脚本都会调 `func_34(索引, perschar哈希, 区域id, 旗标)`：

```c
// init_all_sp.c:2777
void func_34(int iParam0, int iParam1, int iParam2, int iParam3)
{
    if (!func_145(iParam0)) return;                       // ① 索引必须在 [0,954)
    if (iParam2 != -1) {
        func_146(iParam2, &iVar0, &iVar1, 0, 0);          // ② 查这个区域的索引区间
        if (iParam0 < iVar0 || (iParam0 > iVar1 && !func_147(iParam3, (1 << 22))))
            return;                                       //    越界就丢弃
    }
    Global_1895087[iParam0 /*3*/] = iParam1;              // ③ 槽位[索引] = perschar 哈希
    Global_1895087[iParam0 /*3*/].f_1 = 0;                //    占用者脚本
    Global_1895087[iParam0 /*3*/].f_2 = 0;                //    占用者线程 id
    func_148(iParam0, 2 | iParam3);                       // ④ 写旗标表 Global_24887[]
    iVar2 = PERSCHAR::_GET_PERSCHAR_MODEL_NAME(iParam1);
    if (iVar2 != 0)
        PED::SET_PED_MODEL_IS_SUPPRESSED(iVar2, true);    // ⑤ 压制同名环境 ped，防重影
}
```

**⑤ 是最能说明问题的一行**：一个 perschar 注册后，它的**基础模型会被从环境人群里禁掉**，
保证"这一个家伙只有这一个实例"，不会被 popcycle 又刷出一个长得一样的路人。

- `func_145`（:8091）判定范围 = `iParam0 > -1 && iParam0 < 954` ⇒ **全局 954 个槽位**
- `Global_1895087[i][0..2]` = (perschar 哈希, 占用脚本, 占用线程)；
  全项目有 **5,093 处**引用这段数组，是"谁占着这个人"的全局锁
- SP 版一共注册 **950 条**（`grep -c '^\tfunc_34('`），占用 949 个槽位，留 5 个空槽

### 2.2 分区表（`func_146`，:8096）：区域 id → 索引区间

这就是**「哪个镇拥有哪一段 perschar」**的唯一真身。区间连续 ⇒ 一个镇的 NPC 是一个"块"。

完整的「区域 id ↔ 索引区间 ↔ 区名（含命名证据）」表在
**`docs/世界与地编/RDR2_NPC名单与环境人群表.md` §1.2** —— 其中 **32 个区**是由据点脚本里
写死的 `Global_1888801[<id>].f_4` 反查出来的（`annesburg.c:668` = 78、`valentine.c:811` = 76、
`rhodes.c:829` = 105、`blackwater.c:755` = 38、`saintdenis.c:784` = 5 …），**不是猜的**。

这里只留机制要点：

- `start` = 该 case 里第一个 `*uParam1`，`end` = 该 case 里 `*uParam2` 的**最大值**
  （`bParam3` 内容锁 / 线上模式只会把区间收窄）；
- 区间连续 ⇒ **一个镇的 NPC 就是一个"块"**，`func_34` 用它做越界校验；
- 例外两类：**`zone = -1` 完全跳过校验**（99 条：`GLO_*/SCM_*/PHR_*/CRD_*` 等），
  索引 64–68 的 `EA_HMSTD_*` 越界但带 `1<<22` 放行。

> **槽位几乎用满**：954 个里用掉 949 个，**空槽只有 5 个**（738 / 739 / 902 / 903 / 953）。
> `func_146` 的第二、三参数还会收窄：`bParam3` = 内容锁（PC 独占内容未解锁时只保留前段），
> `func_115() != -1` = 线上模式 ⇒ 大部分区直接判 −1（**该 NPC 在线上不存在**）。
> 这就是"同一个游戏，线上模式和单人模式码头人不一样"的机制位置。
> 逐条名单见 **`docs/世界与地编/RDR2_NPC名单与环境人群表.md`** 与 `deliverable/manifests/perschar_roster.csv`。

### 2.3 旗标（`iParam3`）

| 位 | 观察到用在哪 | 含义（实证 / 推断） |
|---|---|---|
| `1<<8`（=256） | 只出现在 `zone = -1` 的牲畜/散落条目（`CARMODY_DELL_COWS_PERSCHAR_1`、`CRD_BULL`、`CRD_DONKEY`） | 位名未知；与"不做区域校验 + 跨区共用"同时出现 |
| `1<<20` | 全部店主：`VAL_BARBER`/`VAL_DOCTOR`/`VAL_GUNSMITH`/`VAL_GENERAL_STORE`/`VAL_BUTCHER`/`RHD_FENCE`… | **服务类常驻**：必须一直在店里，不能随加载卸载（推断） |
| `1<<21` | `VAL_SHERIFF`、`VAL_SHERIFF_HELPER`、`RHD_SHERIFF`、`RHD_DEPUTY` | **执法者**（推断） |
| `1<<22` | `func_34` 里用于**豁免索引越界**（:2794）；`EA_HMSTD_*` 5 条靠它插在 64–68 | 允许开区间挂靠（**实证**） |

> 位名没有符号表，**上表右列是推断**。能确定的是"同一批语义的 NPC 用同一位"，
> 且 `1<<20` 与商店/服务业 100% 重合。

### 2.4 槽位名 ≠ 角色名：`VAL_SHERIFF` 的真名走另一个命名空间

`func_34` 注册进去的字符串是**职能名**（`VAL_SHERIFF`、`SDN_DOCK_WORKER_1`），
不是角色的姓名。真名由**独立的 discoverable name 表**提供，
运行时用 `PLAYER::_SET_PLAYER_HAS_DISCOVERED_CHARACTER_NAME_SP()` 解锁（读悬赏海报 / 见面 / 任务）：

```c
// bounty_poster.c:1140
MISC::GET_HASH_KEY("DISCOVERABLE_NAME_CURTIS_MALLOY" /* GXT: Sheriff Malloy */)
```

- 这套键全脚本共 **98 个**，分 3 个命名空间：`DISCOVERABLE_NAME_*` 90、`ALLY_*` 6、`COMP_*` 2，**98/98 在 `global.yldb` 有官方中文**；
- 罗兹镇警长走的是 `ALLY_` 那一支：**`ALLY_LEIGHGRAY` /* GXT: Sheriff Gray */** ⇒ **Leigh Gray（利·格雷）**，
  他的副手是 `ALLY_ARCHIBALD` = **Archibald MacGregor（阿奇伯德·麦格雷戈）**；
- 所以「瓦伦丁警长」的真名是 **柯蒂斯·马洛伊 / Curtis Malloy**，
  另一条独立证据是 `main.c:97855` 的信件 `DOCUMENT_LETTER_VAL_SHERIFF`，GXT 写着 **"Letter to Curtis from M"**；
- ⚠️ **槽位名有拼写坑**：风滚草镇警长拼成 `TBL_SHERRIF`（`SHERIFF` 少一个 `F`，`init_all_sp.c:583`），
  `grep "TBL_SHERIFF"` 会漏掉；他的真名是 **Samuel Freeman / 萨缪尔·弗里曼**（`DISCOVERABLE_NAME_SHERIFF_FREEMAN`）；
- 托马斯警长（Harmon Thomas）目前只在 `bounty_poster.c` 里出现，还没找到对应的 perschar 槽位。

⇒ 完整真名表和「槽位 → 真名」挂接见 `docs/世界与地编/RDR2_NPC名单与环境人群表.md` §1.6
与 `deliverable/manifests/character_names.csv`。

---

## 3. 码头工人：端到端切片

### 3.1 注册（`init_all_sp.c:377-405, 488-489`）

圣丹尼斯属于区域 5，区间 137–324。其中**码头段的索引 148–176 是连续的 28 条**：

| 索引 | 名字 | 索引 | 名字 |
|---:|---|---:|---|
| 148 | `SDN_DOCK_BOAT_GUARD_1` | 163 | `SDN_DOCK_COTTON_8` |
| 149 | `SDN_DOCK_CASTILLE_1` | 164–166 | `SDN_DOCK_LH_1/2/3` |
| 150 | `SDN_DOCK_CASTILLE_2` | 167 | `SDN_DOCK_LH_CAT` |
| 151 | `SDN_DOCK_CIVIL_1` | 168 | `SDN_DOCK_LH_DOG` |
| **152** | **`ILO_KICK_NEG`** ← 见下 | 169–172 | `SDN_DOCK_LUMBER_1..4` |
| 153 | `SDN_DOCK_CONSTR_2` | **173–176** | **`SDN_DOCK_WORKER_1..4`** |
| 154 | `SDN_DOCK_CONSTR_3` | 260 | `SDN_DOCK_POLICE_1` |
| 155 | `SDN_DOCK_CORNWALL_1` | 261 | `SDN_DOCK_POLICE_2` |
| 156–163 | `SDN_DOCK_COTTON_1..8` | | |

**可读信息量**：
- 码头不是"一个码头工人"，是**分工种的一整套**：棉花 8、木材 4、建造 2、康沃尔公司 1、Castille 2、
  船卫 1、平民 1、通用工人 4、警察 2、以及 `LH_1/2/3 + 猫 + 狗`（LH 含义未确认，看狗猫像"灯塔/更夫小屋"一类）
- `SDN_DOCK_*` 共 **30 条**，全部 `旗标 = 0`（**不是** `1<<20` 那种必须常驻的服务类）⇒ 他们会被剔除/卸载
- 🐞 **索引 152 是 `ILO_KICK_NEG`，不是 `SDN_*`**；而且 `CONSTR_2/3` 存在但**没有 `CONSTR_1`**
  ⇒ 高度疑似"152 原本是 `SDN_DOCK_CONSTR_1`，后来被别的用途覆盖/改名"。
  这是**游戏数据里的真实现象**，不是我们解析错。

### 3.2 模型集：环境层的码头工人（`ambientpedmodelsets.meta`）

```xml
<!-- :4016 -->
<Item type="CAmbientModelSet">
  <Name>SDN_DOCKS_MALE</Name>
  <Models>
    <Item><Name>A_M_M_NBXDOCKWORKERS_01</Name><Probability value="1.000000"/></Item>
    <Item><Name>A_M_M_SDDockWorkers_02</Name><Probability value="1.000000"/></Item>
  </Models>
  <SpawnDistance value="75.000000" />          <!-- 刷出距离 75 m -->
  <AIMemoryGroup>SAINTDENIS_RESIDENTS</AIMemoryGroup>
</Item>
```

| 模型集 | 模型 | SpawnDistance | AI 记忆组 | 行号 |
|---|---|---:|---|---:|
| `SDN_DOCKS_MALE` | `A_M_M_NBXDOCKWORKERS_01`、`A_M_M_SDDockWorkers_02` | **75 m** | SAINTDENIS_RESIDENTS | 4016 |
| `SDN_DOCKS_FOREMAN` | `A_M_M_SDDockForeman_01` | 75 m | SAINTDENIS_RESIDENTS | 4037 |
| `VHT_DOCK_WORKER`（范霍恩） | `A_M_M_VhtTownfolk_01` | **100 m** | VANHORNPOST_RESIDENTS | 7190 |

**这张表是整个 L1 层的"选人池"**：971 个模型集、其中 **79 个**挂在 `SAINTDENIS_RESIDENTS` 记忆组；
7 个集是空的（`<Models />`，`CANT_*` / `MUST_*` 之类的约束名）——
空的不是解包丢数据，是**只做约束不做供给**（推断）。

> **注意命名**：`A_M_M_*` = ambient（环境）ped，`S_M_M_*` = scripted ped，`G_M_M_*` = gang。
> 所以我们**手上有的 3,590 个通用部件**能拼出同类路人，但拼不出这两个具体的 `A_M_M_...DockWorkers`——
> 因为"某个 ped 由哪几件衣服组成"在 `metapeds.ymt` 的 PSIN 里，**仍未解**（见 §6）。

### 3.3 刷在哪：位置从哪来

perschar 的位置**不是**写死在注册表里，是运行时给的。三种来源都实测到：

| 来源 | 证据 | 例子 |
|---|---|---|
| **① 脚本硬编码坐标** | `PERSCHAR::_0x59C7AD6FEA2AC449(handle, v)`（590 处） | `annesburg.c:738`：`func_54(&uLocal_290, 935, 0, "", joaat("COAL_WAGON"), 2808.681f, 1367.038f, 70.8212f, -149.18f, 0, 0)` —— 索引 935 + 模型 + 坐标 + 朝向一次给全（安尼斯堡煤车，镇中心 2884,1348） |
| **② 找地图里烘焙好的场景点** | `TASK::FIND_SCENARIO_OF_TYPE_HASH(coords, 类型哈希, 半径, 0, false)`（`saintdenis.c:10447`、`:10281`） | 圣丹尼斯找 `WORLD_HUMAN_LEAN_BACK_WALL_SMOKING_BAR_CA`（靠墙抽烟），半径 1~3 m |
| **③ 没找到就当场造一个** | `TASK::CREATE_SCENARIO_POINT_HASH(type, pos, heading, …)`、`..._ATTACHED_TO_ENTITY`（`cv_amb_sack_wagon.c:5066/5076`） | 麻袋上车 vignette：先找，找不到就在车尾生成一个挂车上的场景点 |

> ② 是关键：**世界地图里确实烘焙着场景点数据**（否则 `FIND_SCENARIO_OF_TYPE_HASH` 无从查）。
> 但那批数据**不在我们解出来的 `.ymap` 里**（§6 说明）。

### 3.4 生成预算：引擎有"人手配额"

脚本在刷人前必须先预订名额，这是**全局上限**的实现位置：

```c
PED::_RESERVE_AMBIENT_PEDS_TOTAL(2);   // annesburg.c:2249  预订 2 个
PED::_ARE_ALL_AMBIENT_PED_RESERVATIONS_READY();  // 等配额到位
PED::_UNRESERVE_AMBIENT_PEDS(2);       // :2211 用完归还
PED::_GET_NUM_RESERVED_AMBIENT_PEDS_DESIRED();   // 当前想要的
PED::_GET_NUM_RESERVED_AMBIENT_PEDS_READY();     // 当前能给的
```

实测数量级：小镇 1~2、任务场景 5~10、狩猎/牧牛 26~33（`act_hunting_2.c:11592` = 33）。
**配额不够就不刷** —— 这是"为什么远处只有几个人"的直接原因。

---

## 4. 生成之后：行为是怎么驱动起来的

### 4.1 五件套：模型 → 场景 → 道具 → 任务 → 语音

一次"工人干活"的完整调用链（`cv_amb_sack_wagon.c` 为证）：

```c
// ① 加载场景类型资源
STREAMING::_REQUEST_SCENARIO_TYPE(typeHash, 15, 0, variantHash);   // :4828
STREAMING::_HAS_SCENARIO_TYPE_LOADED(typeHash, false);             // :7964

// ② 加载场景用的道具组
PROPSET::_REQUEST_PROP_SET_2(&set);        // :7935   道具组 = pg_scenario_*.ymt
PROPSET::_HAS_PROP_SET_LOADED_2(&set);     // :7933

// ③ 找一个场景点（地图里烘焙的 / 或新建）
point = TASK::FIND_SCENARIO_OF_TYPE_HASH(pos, typeHash, 1.0f, 0, false);        // :5056
if (!TASK::DOES_SCENARIO_POINT_EXIST(point))
    point = TASK::CREATE_SCENARIO_POINT_HASH(typeHash, pos, heading, 0,0,false); // :5066
TASK::_SET_SCENARIO_POINT_FLAG(point, 23, true);   // 各种开关位               // :8282

// ④ 让 ped 去用这个场景点
TASK::TASK_USE_SCENARIO_POINT(ped, point, variantHash, 0, false, true, 0, false, -1.0f, false); // :3325
// 或原地/指定位置版：
TASK::TASK_START_SCENARIO_IN_PLACE_HASH(ped, typeHash, dur, false, 0, -1.0f, false);            // :11000
TASK::TASK_START_SCENARIO_AT_POSITION(ped, typeHash, pos, heading, …);                          // :11008

// ⑤ 给手里塞道具（关键！"搬东西"靠这一行）
PED::_GIVE_PED_SCENARIO_PROP(ped, entity, "p_lumber09_piece01x_PH_R_HAND",
                             "WORLD_HUMAN_LUMBER_PUT_DOWN_1", 0, true);   // av_lumber_pass.c:1877
//              ↑道具模型（_PH_R_HAND = 右手挂点）  ↑绑定的场景类型
TASK::_ASSOCIATE_PROP_WITH_SCENARIO(point, prop, name, true);             // :12027
```

**`_GIVE_PED_SCENARIO_PROP` 是"码头工人看起来真的在干活"的根本**：
人本身只是播一个场景动画，**箱子/麻袋/木板是独立 entity，挂在右手骨骼上**。

### 4.2 场景类型命名空间：码头工在干什么，看名字就知道

全项目 **5,670 处** `WORLD_*` 场景类型字面量，命名是自解释的。
与码头/搬运直接相关的一批（`campfire_always.c:16584-16816`、`cv_amb_sack_wagon.c` 等）：

| 场景类型 | 动作 |
|---|---|
| `WORLD_HUMAN_SACK_PICKUP_1/2`、`SACK_PICKUP_COUNTER` | 抓麻袋（原地/柜台上） |
| `WORLD_HUMAN_SACK_PUT_DOWN_1/2`、`SACK_PUT_DOWN_COUNTER` | 放麻袋 |
| `WORLD_HUMAN_SACK_IN_CART_TARP` / `SACK_OUT_CART_TARP` | **往篷布马车上装 / 卸** ← 码头装车 |
| `WORLD_HUMAN_SACK_OUT_BIN_TARP` | 从货箱往外卸 |
| `WORLD_HUMAN_LUMBER_PICKUP_1..3` / `LUMBER_PUT_DOWN_1..3` | **搬木材**（对应 `SDN_DOCK_LUMBER_1..4`） |
| `WORLD_HUMAN_COAL_SACK_PICKUP_*` / `OUT_CART_TARP` | 搬煤袋（安尼斯堡煤码头） |
| `WORLD_HUMAN_SUGAR_SACK_PICKUP_*` | 搬糖袋（甘蔗/糖业码头） |
| `WORLD_HUMAN_RUM_CRATE_PICKUP_1..3` | 搬朗姆酒箱 |
| `WORLD_HUMAN_CHICKEN_CRATE_PICKUP_1/2` | 搬鸡笼 |
| `WORLD_HUMAN_GLASS_PICKUP_CRATE` / `GLASS_PUT_DOWN_CRATE_TABLE` | 搬玻璃箱 |
| `WORLD_HUMAN_PUSH_BROOM_WORKING/PICKUP/PUTDOWN/RESTING` | **扫地**（含"累了歇会儿"） |
| `WORLD_HUMAN_*_CARRYING`（SMOKE / STAND_WAITING / STARE_STOIC / WAITING_IMPATIENT） | 抱着东西时的抽烟/发呆/不耐烦 |

⇒ 一个"码头工人"的实际行为是**组合**出来的：
`SDN_DOCK_LUMBER_1` 这个 perschar → 站在木料堆旁的 `LUMBER_PICKUP` 场景点 → 右手挂 `p_lumber09_piece01x` → 走到车边 `LUMBER_PUT_DOWN`；
中途可能播 `STAND_WAITING_CARRYING` 的等待变体；被玩家挡住会换成 `*_CARRYING` 的"抱着东西被挡"分支。

**场景类型可以被全局开关**（做任务时临时关掉某类行为）：

```c
TASK::SET_SCENARIO_TYPE_ENABLED("WORLD_HUMAN_SACK_OUT_CART_TARP", false);  // rcm_bh_blackwater_hunt.c:1732
```

### 4.3 `schedule`：perschar 的"作息表"

常驻角色不是"一直站着不动"，每个 perschar 可以挂一份 **schedule**：

```c
PERSCHAR::_SET_PERSCHAR_SCHEDULE(perschar, &sched);   // cv_amb_sack_wagon.c:8673 / annesburg.c:2280
```

- 入参是 `struct<8>`（8 字节），脚本里用 `MISC::IS_STRING_NULL_OR_EMPTY()` 判空 ⇒ **按内联字符串/8 字节键处理**
- 存进 `Global_1360165[slot].f_39`（另一张 per-perschar 的 1157 字段大表）
- 相关配套：`PERSCHAR::_RETASK_PERSISTENT_CHARACTER(h)`（重派任务）、
  `_0x6759BEE6762E140B(h)`（刷新状态）、`_0x63AA2B8EB087886A(h, hash)`

> ⚠️ **8 字节的具体语义没解**（没有符号、没有 schema）。能确定的只有：
> 它是"给这个人的行为包"，配上场景类型一起生效。

### 4.4 出生/复活的完整状态机（`annesburg.c:2186` `func_80`）

这是**单个 NPC 从"想刷"到"刷出来站住"的 10 态机**，是整套机制最干货的一段：

| 状态 | 做什么 | 行号 |
|---:|---|---:|
| 0 | 检查 perschar 有效 / 该区域今天是否开放 | 2197 |
| 1 | **预订配额** `_RESERVE_AMBIENT_PEDS_TOTAL` + `REQUEST_MODEL` + `_REQUEST_PROP_SET` | 2211 / 2249 |
| 2 | 等模型流式加载完成 | 2233 |
| 3 | 配额到位后进下一步 | 2239 |
| 4 | 再确认模型还在（可能被踢出） | 2255 |
| 5 | 生成 / 失败回收 | 2266 |
| 7 | **`_SET_PERSCHAR_SCHEDULE` 挂作息**，再确认 ped 实体是否真存在 | 2277 |
| 6 | 位置对不上就 `_0x669C25840C6F7AE2(handle, pos)` 拉过去 | 2291 |
| 8 | **剔除分支：`CAMERA::IS_SPHERE_VISIBLE(pos, 3.0f)` 为假 → 立刻回收** | 2301 |
| 9/10 | 收尾 | 2319 |

另外两条阈值（`annesburg.c:2165`、`:8760`）：
- **距离 > 45 m** 才允许做"死亡/失效"处理（近处不处理，避免玩家看见）
- **距离 < 5 m / < 25 m** 两档做相机/交互准备

⇒ **"你看不见的地方，人就被换掉了"** —— 这就是为什么"码头工人的脸一直在变"。

### 4.5 语音：谁开口

- `speechcontextrulesets/*.meta`（160 个，`raw/_scratch/meta_probe/data/ai/` 已有 100+）
  定义"在什么场景上下文播哪一类台词"：`ambient` / `ambient_greets` / `ambient_local_events` /
  `law` / `guard` / `shopkeeper` / `bounty_hunter` / 每个帮派成员各一份
- 具体 ped 模型 → 语音标签的映射是**脚本里写死的 switch**：
  `0832_S_M_M_TRAINSTATIONWORKER_01_WHITE_01` → `"0832_TRAINWORKER"`（`saintdenis.c:12704-12711`）

---

## 5. 密度与时段：人群"多不多"

### 5.1 车辆层：`popcycle.dat`（纯文本，自带文档）

```text
// #MaxCars #Spacing #prkdcrs #lowprkdcrs #MaxScenVehs #MaxPreAssignedParked

TRAFFIC_ST_DENIS_MAIN_SCHEDULE          // :429
// DAY 10:00-20:00
  100  90  12  00  60  1  cars HORSE_SDN 12 HORSE_SDN_POSH 10
                          COACH_SDN_SMALL_POSH 30 COACH_SDN_SMALL_UTILITY 30 COACH_SDN_LARGE 18
// NIGHT 20:00-00:00
  100  50  15  00  60  1  cars HORSE_SDN 50 COACH_SDN_SMALL_POSH 25 COACH_SDN_LARGE 25
```

读法（文件头 :2-8 自带说明）：
`MaxCars` = 目标车辆数的**百分比倍率**（100 = 正常）；`Spacing` = 车距倍率（越大越稀）；
后面 `cars <车型> <占比>` 是**车型配比**。
**注意：这一层只管车/马车/马，不管人。**

### 5.2 行人层：区域数据（本轮新定位）

行人密度不在 `popcycle.dat` 里，走的是 **PARSEDDATA（`.pso`）的 `REGION_DATA`**：

```c
// startup_sp.c:4275 func_154
Global_1894899.f_175 = DATAFILE::_PARSEDDATA_LOAD_FILE_HASH(joaat("REGION_DATA"));   // :4288
while (!DATAFILE::PARSEDDATA_IS_FILE_LOADED(...)) WAIT(0);

sVar0.f_2 = -258890676;                    // 节点
DATAFILE::PARSEDDATA_RQ_FILLOUT_NODE(&sVar0.f_1, &sVar0);                            // :4303
while (_PARSEDDATA_GET_NUM_CHILDREN(...) > iVar23) {
    sVar0.f_2 = 1489686829;  _PARSEDDATA_RQ_FILLOUT_STRING_63(&uVar5, &sVar0);       // 区域名
    iVar13 = func_275(MISC::GET_HASH_KEY(&uVar5));                                   // → 区域槽
    sVar0.f_2 = 596301644;   _PARSEDDATA_RQ_FILLOUT_FLOAT(&uVar14, &sVar0);
    Global_1888801[iVar13 /*35*/].f_10 = uVar14;      // ★ 环境行人 距离/密度倍率
    sVar0.f_2 = 325957282;   _PARSEDDATA_RQ_FILLOUT_FLOAT(&uVar14, &sVar0);
    Global_1888801[iVar13 /*35*/].f_11 = uVar14;      // ★ 场景行人 距离倍率
    sVar0.f_2 = 426139466;   _PARSEDDATA_RQ_FILLOUT_STRING_63(&uVar15, &sVar0);
    Global_1888801[iVar13 /*35*/].f_12 = MISC::GET_HASH_KEY(&uVar15);  // ★ 该区用哪张 popcycle 表
}
```

每个据点脚本**每帧**把这两个倍率喂给引擎（`annesburg.c:333-337`）：

```c
PATH::SET_AMBIENT_PED_RANGE_MULTIPLIER_THIS_FRAME(Global_1888801[i /*35*/].f_10);
if (Global_1888801[i /*35*/].f_11 > 0.0f)
    PED::_SET_SCENARIO_PED_RANGE_MULTIPLIER_THIS_FRAME(Global_1888801[i /*35*/].f_11);
if (func_41())   // 例如封城/剧情
    PED::_SET_AMBIENT_HUMAN_DENSITY_MULTIPLIER_THIS_FRAME(0.0f);   // 一键清人
```

**这就把三个层次接上了**：
`区域(id)` → `f_10 环境行人倍率 / f_11 场景行人倍率 / f_12 popcycle 表` → 引擎按倍率刷人刷车。
`Global_1888801[i /*35*/]` 是**区域配置大表**（每区 35 个字段），`f_10/f_11/f_12` 只是行人相关的三项。

> 注：`REGION_DATA` / `REGIONS` 这两个 `.pso` **本机没抽**（`raw` 里没有任何 `.pso`），
> 所以"瓦伦丁的倍率具体是 1.3 还是 0.8"这类**数值**还拿不到。**机制已经清楚，参数未落地。**

---

## 6. 还没解的（诚实清单）

| # | 缺什么 | 影响 | 卡在哪 | 下一步 |
|---|---|---|---|---|
| 1 | **`metapeds.ymt` 的 PSIN** | 拼不出 `A_M_M_NBXDOCKWORKERS_01` 这一只，只能"同类路人" | 二进制、无字符串、无哈希（`docs/格式与资产/PSO_PSIN_格式规范.md` §7 有 schema 缺实例值） | 用 PSCH 的 `ReferenceKey` + 已知 ped 名反推实例布局 |
| 2 | **世界里的场景点数据**（`WORLD_HUMAN_*` 的坐标/朝向/所属模型集） | 拿不到"木料堆在哪个坐标""这个点配哪个模型集" | 已排除 `.ymap`：项目解析器（`tools/ymap_entities.py`）与 `tools/ref/rdr2-unpack-main/lib/ymap-rsc8.cjs` **都只处理 `CMapData` → `CEntityDef`(0x90 字节)**，没有场景块；按文件名也没搜到独立场景点资源 | 拿 `CScenarioPointRegion` 的 schema 反查 ymap 的其它 chunk（`0xd3593fa6` 之外） |
| 3 | **`REGION_DATA` / `REGIONS` 两个 `.pso`** | 行人密度倍率的具体数值、区域 id ↔ 名字的官方对照 | 没抽出来（`raw` 无 `.pso`） | `rdr2rpf extract --recurse` 补抽 `common/data/` |
| 4 | **`_SET_PERSCHAR_SCHEDULE` 的 8 字节** | schedule 到底写了什么 | 无符号表 | 对比多个 perschar 的 schedule 值找规律 |
| 5 | **perschar 定义表** | `SDN_DOCK_WORKER_1` 到底绑哪个模型（现在只能从模型集间接推） | 未定位文件 | 搜 `perschar` 相关 `.ymt` |

---

## 7. 复核命令（每条都能重跑）

```powershell
$S = "D:\BrainMaker\大镖客2解包分析\raw\script_full\1491.50"

# 1) 954 槽位 + 分区表 + 码头 30 条
Select-String -Path "$S\init_all_sp.c" -Pattern "SDN_DOCK_"
(Select-String -Path "$S\init_all_sp.c" -Pattern "^\tfunc_34\(").Count        # → 950

# 2) 模型集
$M = "D:\BrainMaker\大镖客2解包分析\raw\sdn\ai\data\ai\ambientpedmodelsets.meta"
Select-String -Path $M -Pattern "SDN_DOCKS|DOCKWORKER"
(Select-String -Path $M -Pattern 'type="CAmbientModelSet"').Count              # → 971

# 3) 场景类型全表（5,670 条）
Select-String -Path "$S\*.c" -Pattern '"WORLD_HUMAN_SACK|"WORLD_HUMAN_LUMBER'

# 4) 出生状态机 / 密度倍率
Select-String -Path "$S\annesburg.c" -Pattern "void func_80|SET_AMBIENT_PED_RANGE_MULTIPLIER"

# 5) 行人密度数据来源
Select-String -Path "$S\startup_sp.c" -Pattern "REGION_DATA|Global_1888801\[iVar13 /\*35\*/\].f_1[012]"
```

---

## 8. 给"把 NPC 放进我们自己场景"这件事的三条结论

1. **要"人"不要"机制"**：直接用 `export/npc/` 的 354 个 glb（剧情角色 / 主角 / 动物）——
   这些是完整还原。**路人只能用通用部件自己搭**（`make_generic_peds.py`），因为 PSIN 没解。
2. **要"码头工人"这个特型**：模型集名和它的 2 个 ped 名（`A_M_M_NBXDOCKWORKERS_01`、
   `A_M_M_SDDockWorkers_02`）已经确定，**但模型本体在 `metapeds_a..z.rpf`，本项目没抽**。
   要拿真模型就得先抽那几个包 + 解 PSIN。
3. **要"行为"**：行为不在模型里，在**场景点 + 场景类型 + 手部道具**三件套里。
   照抄这套结构（锚点 + 场景名 + 挂点道具）就能在自己的引擎里复现"工人搬箱子"，
   我们需要的只是 **`WORLD_HUMAN_LUMBER_PICKUP_1` 这类场景的动画**（`raw/script_full` 里能查到全部调用点，
   动画本身在 `.ycd`，见 `docs/格式与资产/RDR2_ycd动画解码.md`）。
