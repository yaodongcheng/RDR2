# RDR2 · 任务逻辑 / 武器 / 道具 破解报告

> 目标：1）破解完任务具体逻辑；2）把武器和道具都破解掉。
>
> 结论：**两项都没有"完全破解"**。任务逻辑卡在 `.ysc` 任务脚本（游戏里找不到/没解出来）；
> 武器拿到了 142 条 schema 和 24 把可读数值，但 142 条的**名称哈希没映射**；
> 道具目录的 **schema 已破**，但 `items` 的 PSO Map 数据还没走通。

---

## 0. 状态总表

| 目标 | 状态 | 已拿到 | 卡点 |
|---|---|---|---|
| **任务具体逻辑** | 🟡 **目标层已完成，脚本层受阻** | 270 条任务定义+中文标题/简介、308 条挑战、**637 条玩家目标 + 443 条失败条件**、181 个过场包、95/105 主线 cast | **`.ysc` 仍解不开**：脚本包已在 `update_2.rpf` 找到并抽出（113 MB），但 RPF8 tag `0xC6` 的 AES key #198 缺失 |
| **武器** | 🟡 **部分完成** | 142 条 `CWeaponInfo`（118 字段 schema）、24 把 MP 武器完整数值、28 弹药 + 28 投掷物 + 13 投射物、174 个武器资产 | 142 条的 `Name` 是**未映射哈希**；伤害/射程在嵌套指针结构里，尚未走通 |
| **道具** | 🟡 **结构破解** | `catalog_sp.ymt`（3.5 MB）+ 47 个类型的 schema（`catalog/items/type/version/key/layout`） | `items` 的 PSO Map 数据未走通；没有道具名/价格清单 |

---

## 1. 任务：定义和 cast 齐了，但"具体逻辑"还差 `.ysc`

### 1.1 已经拿到的

| 内容 | 数量 | 产物 |
|---|---|---|
| 任务定义 | **270**（105 主线 + 121 支线/赏金 + 21 物品请求 + 15 配方 + 8 线上） | `missions.csv` |
| 任务目标/挑战 | **261** | `goals_sp_missions.csv` |
| 过场包 | **181/181**（5,237 个 ycd/yad） | `work/story/cutscene_all/extracted/` |
| 出场角色 | **181**（106 已进名册） | `actor_coverage.csv` |
| 任务 → 角色 cast | **198/270 有 cast**（主线 95/105、支线 97/121） | `mission_cast.csv` |
| 任务中文标题 / 官方简介 | **250 / 250**（打通 `.yldb` key→string） | `missions_story.csv` |
| 玩家目标 / 失败条件 | **637 + 443 条**（从各任务 `<id>.yldb` 抽取） | `mission_objectives.csv`、`RDR2_任务执行逻辑还原.md` |

### 1.2 261 条任务目标/挑战（抽样）

| goal | 统计项 | 比较 | 目标值 |
|---|---|---|---|
| No_Deaths | DEATHS | LESS_THAN | 1 |
| HealthItems_None | MEDICINE_ITEMS_USED | LESS_THAN | 1 |
| ProvisionItems_None | PROVISION_ITEMS_USED | LESS_THAN | 1 |
| OnlySidearms | — | LESS_THAN | 1 |
| OnlyLongarms | — | LESS_THAN | 1 |

> 完整 261 条见 `goals_sp_missions.csv`。

### 1.3 脚本包在哪：已定位、已抽出，卡在密钥

**2026-10-19 更新：`script_rel.rpf` 找到了。**

```
H:/EPICGAMES/RedDeadRedemption2/update_2.rpf
  → x64/levels/rdr3/script/script_rel.rpf     113,038,110 B
  → x64/levels/rdr3/script/script_mp_rel.rpf   23,679,568 B
  → x64/levels/rdr3/script/parseddata.rpf       3,797,514 B
```

已抽出到 `work/script_probe/x64/levels/rdr3/script/script_rel.rpf`。包头：

```
8FPR (RPF8) · version 1639 · entries 27470 · tag 0x00C6 · platform 121
```

`rdr2rpf list` 仍然失败：

```
[error] Can't get encoder key!
   at RDR2_RPF_Tool.Core.Cipher.GetCipher(...)
```

`KeysContainer.keysValues` 只有 tag 0–162 + 192，**没有 198(0xC6)**。
`parseddata.rpf` 的 615 个 ymt 全部 `signature protected`，也不是任务脚本。

### 1.4 脚本层拿不到，但"目标层"已经还原

`.ysc` 提供的是**触发器 / 生成 / 分支 / 奖励**；而"玩家被要求做什么、什么情况会失败"在任务自己的
`<mission_id>.yldb` 里是明文。本轮已抽取：

- **637 条玩家目标**（如 MOB1：在酒馆附近找达奇 → 在市场里搜寻孩子 → 在巷子里搜寻孩子 → 在巷子里打听勃朗特）
- **443 条失败条件**（如：您跟丢了孩子 / 离酒馆太远了 / 基兰死了 / 平克顿侦探被惊动了）

产物：`export/levels/world/mission_objectives.csv`，说明见 **`RDR2_任务执行逻辑还原.md`**。

### 1.5 脚本级任务信息已解析（build 1355 反编译库）

本机 RPF 解不开，但 `script_rel.rpf` 的条目数是 **1639**，与社区反编译库 build 1355 的
`script_rel/` 文件数 **1639** 完全一致。据此完成脚本级解析：

- **105/105 主线**、194 个任务匹配到脚本文件（如 `WNT1 → winter1.c`、`DST1 → odriscolls1.c`）
- **1054 条脚本目标**：脚本里的文本键（自动识别 `MUD3B_*`、`ODR3_*` 这类真实前缀）→ 任务 yldb 中文，按脚本内首次出现排序
- **318 条脚本失败条件**：`*_FAIL_*` / `*_LOST` / `*_DEAD` 等
- 每关还统计了：生成调用点（ped/vehicle/object）、过场名、高频 native

样例（WNT1）：跟随迈卡 → 跟随达奇 → 保护达奇 → 进入木屋 → 继续搜查木屋 → 出去与达奇会面；
失败：离牧场太远 / 未检查畜棚 / 帮派成员的马死了 / 达奇和迈卡被抛弃了。

产物：`export/levels/world/mission_scripts.csv`，详见 **`RDR2_脚本级任务解析.md`**。

### 1.6 还缺什么

| 缺 | 影响 | 路线 |
|---|---|---|
| 触发器 / 区域判定 | 不知道目标在什么位置、什么条件下推进 | CodeX 反编译 `.ysc`；或补 AES key #198 |
| 生成表（ped/载具/道具） | 不知道一关刷多少人 | 同上 + `metapeds.ymt` PSIN schema |
| 分支 / 失败表达式 | 不知道"如果…则…" | 同上 |
| 奖励与结算 | 不知道给多少钱/物品 | 同上 |

---

## 2. 武器：schema 和 24 把数值拿到了，142 条名字还没映射

### 2.1 数据源

| 文件 | 内容 |
|---|---|
| `update_4.rpf → x64/packs/base/data/ai/weapons.ymt` | **142 条 `CWeaponInfo`**，每条 2768 字节，**118 个字段** |
| `common_0.rpf → packs/base/data/ai/weapons_mp.meta` | **24 把 MP 武器**的可读数值（XML） |
| `packs_1.rpf → packs/base/models/weapons.rpf` | **513 个武器资产**（.ydr/.ydd/.ytd） |

### 2.2 `CWeaponInfo` 的 schema（118 字段，抽样）

| 偏移 | 类型 | 字段 |
|---|---|---|
| 32 | String | **Name** |
| 36 | String | **Model** |
| 56 | String | **Audio** |
| 60 | String | **Slot** |
| 64 | Enum | **FireType** |
| 68 | String | **Group** |
| 72 | Enum | **WeaponType** |
| 88 | Structure | 伤害/穿透结构（Damage / DamageType / Penetration / AmmoInfo） |
| 160 | Structure | **爆头距离**（Min/Max AI/Player） |
| 192 | Structure | 伤害修正（爆头/轻甲/载具） |
| 248 | Structure | 伤害时间 |
| 272 | Structure | 力/击退（Force / ForceFalloff） |
| 336 | Float | — |
| 368 | Float | FragImpulse |
| 372 | Float | VerticalLaunchAdjustment |
| 380 | Float | DropForwardVelocity |
| 384 | Float | **Speed** |
| 392 | Float | **BatchSpread** |
| 720 | Float | BulletDirectionOffsetInDegrees |

> 完整 118 字段见 `export/levels/world/CWeaponInfo.csv` 的表头，或 `work/items/weapons_schema.txt`。

### 2.3 24 把 MP 武器的可读数值（XML）

| 武器 | 伤害衰减（距离:伤害） | 精度衰减起/止 | 锁定距离 |
|---|---|---|---|
| WEAPON_REVOLVER_CATTLEMAN | 35:20 / 50:18 / 80:10 | 15 / 40 | 30 |
| WEAPON_REVOLVER_DOUBLEACTION | 35:20 / 50:18 / 80:10 | — | — |
| WEAPON_REVOLVER_SCHOFIELD | 35:20 / 50:18 / 80:10 | — | — |
| WEAPON_PISTOL_VOLCANIC | 35:20 / 50:18 / 80:10 | — | — |

> 24 把完整表见 `weapons_mp.csv`（含爆头距离 AI/Player、精度衰减、锁定距离）。

### 2.4 弹药

| 表 | 条目 | 字段 |
|---|---|---|
| `CAmmoInfo.csv` | **28** | 22 个标量字段 |
| `CAmmoThrownInfo.csv` | **28** | 68 个标量字段 |
| `CAmmoProjectileInfo.csv` | **13** | 66 个标量字段 |
| `CVehicleWeaponInfo.csv` | **2** | 4 个标量字段 |

### 2.5 武器资产（174 个唯一 base / 513 个文件）

| 类别 | 唯一 base 数 |
|---|---|
| 霰弹枪 | 35 |
| 步枪 | 29 |
| 连发步枪 | 25 |
| 左轮手枪 | 18 |
| 手枪 | 17 |
| 近战 | 16 |
| 特殊 | 6 |
| 其他（大号弓/投掷/望远镜等） | 28 |

> 完整清单见 `weapon_assets.csv`（base / 类别 / 资产数 / 模型数 / 文件列表）。

### 2.6 还差什么

1. **142 条 `CWeaponInfo` 的 Name 是哈希**（如 `0xBEAEFBF9`），不是 `joaat("WEAPON_*")`、
   不是 `joaat("w_*")`、也不是显示名的 joaat。**哈希算法/名称表还没找到**。
2. **伤害/射程在嵌套指针结构里**：schema 有 `Damage`、`WeaponRange`、`AccuracySpread`，
   但 `CWeaponInfo` 的 Structure 字段是**指针**，不是内联；需要实现 PSO 指针/数组 walker 才能取到值。
3. 24 把 MP 武器的 XML 是**可读的**，但 SP 的 142 条要等上面两条解决。

---

## 3. 道具：schema 破了，数据 Map 还没走通

### 3.1 已拿到的

| 内容 | 状态 |
|---|---|
| `data/itemdatabase/catalog_sp.rpf → catalog_sp.ymt` | ✅ 已抽出（3.5 MB） |
| PSO schema | ✅ **47 个类型**，字段名可读 |
| `catalog` 结构 | ✅ `type` / `version` / `items`（Map） |
| 物品结构 | ✅ `Key`（String）/ `Item`（Structure） |
| 其他道具文件 | ✅ `shop_items.ymt`（7.9 MB）、`satchelitems.ymt`（789 KB）、`quickselectitems.ymt` |

### 3.2 catalog 的 schema（47 类型，关键几条）

| 类型 | 大小 | 字段 |
|---|---|---|
| `catalog` | 40 | `type` / `version` / **`items`（Map）** |
| Map node | 192 | `Key`（String）/ `Item`（Structure） |
| item 根 | 184 | `Name` / `UInt` / 两个子结构 |
| 其他 | — | `key` / `layout` / `flags` / `items` |

> 完整 47 类型见 `work/items/catalog_schema.txt`。

### 3.3 为什么还没出"道具清单"

`items` 是 **PSO Map**，不是普通数组：

- Map 的节点是 192 字节的 `{Key, Item}`；
- 但 PSO Map 的**计数/指针布局**没有公开定义，CodeWalker 也没有 `CCatalog` / `CItem` 的 PSO 类型；
- 直接按 192 字节步长扫，扫出来的不是干净的 key 序列（数据里有类型头/指针混合）。

所以现在只能给出 **schema**，给不出"道具 ID → 名称 → 价格/重量"的完整表。

> 下一步：写一个 PSO Map walker（识别 count/entries 指针 + 192 字节节点），
> 或者找到 RDO/CodeX 的物品类型定义（`CCatalog` / `CItem`）直接映射。

---

## 4. 产物

| 文件 | 内容 |
|---|---|
| `missions.csv` | 270 条任务定义 |
| `goals_sp_missions.csv` | 261 条任务目标/挑战 |
| `mission_cast.csv` | 270 条任务的出场角色（198 有 cast） |
| `cutscene_cast.csv` | 181 个过场包的角色 |
| `actor_coverage.csv` | 181 个角色的出场统计 |
| `CWeaponInfo.csv` | 142 条武器 × 88 个标量字段（Name 为哈希） |
| `CAmmoInfo.csv` / `CAmmoThrownInfo.csv` / `CAmmoProjectileInfo.csv` | 28 / 28 / 13 条弹药 |
| `weapons_mp.csv` | 24 把 MP 武器的可读数值 |
| `weapon_assets.csv` | 174 个唯一武器 base / 513 个资产 |
| `work/items/weapons_schema.txt` | `CWeaponInfo` 等 84 个类型的完整 schema |
| `work/items/catalog_schema.txt` | 道具目录 47 个类型的 schema |

### 复现

```bash
cd "D:/BrainMaker/大镖客2解包分析"
RP=tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe
G=H:/EPICGAMES/RedDeadRedemption2

# 武器 YMT
$RP extract "$G/update_4.rpf" work/items "x64/packs/base/data/ai/weapons.ymt"
# 武器 MP XML
$RP extract "$G/common_0.rpf" work/items/meta "packs/base/data/ai/weapons_mp.meta"
# 武器模型
$RP extract "$G/packs_1.rpf" work/weapons "packs/base/models/weapons.rpf"
# 道具目录
$RP extract "$G/data_0.rpf" work/items "data/itemdatabase/catalog_sp.rpf"
$RP extract work/items/data/itemdatabase/catalog_sp.rpf work/items/catalog ""

# 解析
python tools/build_mission_inventory.py
python tools/build_cutscene_cast.py
python tools/build_weapon_item_data.py
# PSO schema/数组导出（C#）
cd tools/pso_dump && dotnet run -c Release -- <ymt> CWeaponInfo CAmmoInfo ...
```

---

## 5. 一句话总结

> **任务**：270 条定义 + 261 条目标 + 181 个过场的 cast 都有了，但 **`.ysc` 任务脚本是 0**，
> 所以"任务具体逻辑"（生成/分支/失败条件）**没破解完**。
> **武器**：142 条 `CWeaponInfo` 的 **schema 已破**、24 把 MP 数值可读、174 个资产已列；
> 但 142 条的名字哈希没映射、嵌套伤害/射程指针没走。
> **道具**：目录的 **47 类型 schema 已破**，但 `items` 的 PSO Map 数据没走通，还出不了道具清单。
