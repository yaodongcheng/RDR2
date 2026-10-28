# 荒野大镖客 2 · 脚本级任务解析

> 回答："完成脚本级的任务信息解析。"
>
> 本机 `script_rel.rpf` 仍因 AES key #198 无法解密；但它的 RPF 条目数是 **1639**，与社区反编译脚本库 build 1355 的 `script_rel/` 文件数 **1639** 完全一致。因此本轮以该反编译代码为脚本层数据源，逐任务还原：**脚本文件、目标键→中文、失败条件、生成调用、过场、高频 native**。

| 指标 | 数值 |
|---|---|
| 脚本文件总数 | 1,639（= 本机 RPF 条目数） |
| 解析到脚本的任务 | 194 / 270 |
| 其中主线 | 105 / 105 |
| 强匹配（脚本内 `<ID>_` 文本键 ≥10） | 116 |
| 脚本目标（键 + 中文） | 1054 条（98 个任务有目标文本） |
| 脚本失败条件 | 318 条 |

## 0. 数据来源与校验

| 项 | 值 |
|---|---|
| 本机脚本包 | `work/script_probe/.../script_rel.rpf`（113,038,110 B） |
| RPF 条目数 | **1639**（`rdr2rpf list` 读到的 EntryCount） |
| RPF tag | `0xC6(198)`，AES key 缺失，无法本地解密 |
| 脚本库 | `RDR3-Decompiled-Scripts`，build **1355**，`script_rel/` 下 **1639** 个 `.c` |
| 本地副本 | `work/script_probe/script_src/`（用到的 **164** 个脚本，299 MB，便于复现） |
| 对应关系 | 文件名 → 任务 ID：按脚本内 `<ID>_...` 文本键出现次数匹配 |

> 说明：这是**反编译后的 C 代码**，不是原始字节码；变量名多为 `uLocal_*` / `func_*`，但 native 调用、文本键、控制流是真实的。

## 1. 解析方法

1. **任务 → 脚本**：统计每个 `.c` 里 `"<ID>_..."` 形式的文本键数量，取最高的文件；≥10 记为强匹配。
2. **目标**：脚本里的文本键前缀不一定等于任务 ID（如 MUD6 → `MUD3B_*`、DST3 → `ODR3_*`）。先按"该前缀的键能在任务 yldb 里解析出中文"打分，自动选出真实前缀；再按"祈使句 / 含 OBJ"归类，按脚本内**首次出现顺序**排列。
3. **失败条件**：文案含"失败/已无法/被惊动/逃走/太远/死了/犯法/被抛弃"等，或 key 含 `FAIL`。
4. **生成调用**：统计 `PED::CREATE_PED` / `VEHICLE::CREATE_VEHICLE` / `OBJECT::CREATE_OBJECT` 的**调用点**（不是运行时数量）。
5. **过场**：脚本里的 `script@story@...` 动画场景名。
6. **高频 native**：按 `命名空间::函数` 统计，反映这一关主要在用哪些系统。

### 1.1 目标文本未能静态提取的主线（18 条）

这些任务的脚本已匹配，但目标文案由变量拼装或不在任务 yldb 中；仍可从脚本得到生成调用、过场与 native 画像。

| 任务 | 脚本 |
|---|---|
| 童叟无欺的蛇油 `BOU1` | `bounty1.c` |
| 自尊，负伤离场 `HNT1` | `hunting1.c` |
| 火上浇油：第 2 部分 `RMUD32` | `rcm_mudtown3_2.c` |
| 放债与更多罪孽：第 3 部分 `RDOWN3` | `rcm_down3.c` |
| 真爱之路：第 2 部分 `RBNP11` | `rcm_beau_and_penelope11.c` |
| 草根朋友 `RCHRB` | `rcm_coach_robbery1.c` |
| 谢迪贝莱之战 `RDTC2` | `rcm_dutch21.c` |
| 低开高走 `CABR01` | `act_bankrobbery01.c` |
| 帮修士一把 `RCLDN1` | `rcm_calderon1.c` |
| 修士修女一家亲 `RCLDN2` | `rcm_calderon2.c` |
| 人生的岔路口 `RDOPN` | `rcm_doctors_opinion1.c` |
| 亲爱的塔西佗叔叔 `RGNG02` | `rcm_gang02.c` |
| 毋须宽恕：第 1 部分 `REDW21` | `rcm_edith_down21.c` |
| 毋须宽恕：第 2 部分 `REDW22` | `rcm_edith_down22.c` |
| 简单的快乐 `MAR5` | `marston5_3.c` |
| 乡绅的乐土？ `RBCH12` | `rcm_beechers12.c` |
| 家装入门 `RBCH21` | `rcm_beechers21.c` |
| 工具盒 `MAR7` | `marston7.c` |

## 2. 主线逐任务

### 2.1 第一章 · 犁刀村

#### 1. 西部亡命之徒 `WNT1`

- 脚本：`winter1.c`（强匹配，108,096 行 / 3,117 个函数）
- **目标（脚本顺序）**
  1. 跟随迈卡。
  2. 跟随达奇。
  3. 保护达奇。
  4. 进入木屋。
  5. 继续搜查木屋。
  6. 出去与达奇会面。
  7. 搜寻完物资后，与达奇在外面会合。
  8. 返回牧场。
  9. 调查畜棚。
  10. 返回畜棚。
  11. 打开畜棚的门
  12. 将马牵引到拴马桩处。
  - …（另有 22 条）
- **失败条件**：离牧场太远了。；未检查畜棚。；帮派成员的马死了。；达奇和迈卡被抛弃了。；木屋中的人被惊动了。；离畜棚太远了。
- **生成调用点**：ped 3 / vehicle 0 / object 7 / pickup 1
- **过场**：`script@story@wnt1@leadout@int@leadout`；`script@story@WNT1@leadin@mcs1@leadin`；`script@story@WNT1@leadout@MCS1@leadout`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×367、PED::SET_PED_CONFIG_FLAG ×303、ENTITY::IS_ENTITY_DEAD ×280、PLAYER::GET_PLAYER_INDEX ×204、BUILTIN::TO_FLOAT ×150

#### 2. 回忆，粉墨登场 `WNT2`

- 脚本：`winter2.c`（强匹配，93,984 行 / 2,470 个函数）
- **目标（脚本顺序）**
  1. 杀死狼群。
- **生成调用点**：ped 2 / vehicle 0 / object 1 / pickup 0
- **过场**：`script@story@wnt2@mission_jump_cameras`；`script@story@wnt2@mission_ride_cameras`；`script@story@wnt2@ig@ig_16_deadhorse@ig_16_deadhorse`
- **高频 native**：PED::IS_PED_INJURED ×367、ENTITY::DOES_ENTITY_EXIST ×350、ENTITY::IS_ENTITY_DEAD ×223、PLAYER::GET_PLAYER_INDEX ×182、PLAYER::PLAYER_ID ×168

#### 3. 老朋友们 `DST1`

- 脚本：`odriscolls1.c`（强匹配，105,807 行 / 2,751 个函数）
- **目标（脚本顺序）**
  1. 跟随达奇。
  2. 追上奥德里斯科的手下并用套索套住他。
  3. 跟随达奇。
  4. 搜刮敌人尸体。
  5. 与帮派成员会合。
  6. 搜查建筑。
  7. 搜查
  8. 捆绑奥德里斯科的手下。
  9. 返回营地。
  10. 将奥德里斯科的手下放到您的马背上。
  11. 将奥德里斯科的手下扛起来。
  12. 扛着奥德里斯科的手下前往木屋。
  - …（另有 8 条）
- **失败条件**：奥德里斯科帮成员被惊动了。；帮派成员被抛弃了。；基兰死了。；奥德里斯科帮成员死了。；奥德里斯科的手下逃走了。
- **生成调用点**：ped 2 / vehicle 0 / object 16 / pickup 0
- **过场**：`script@story@odr1@ig@ig1_dutch_points_at_tracks_on_ground@ig1_dutch_points_at_tracks_on_ground`；`script@story@odr1@ig@ig2_dutch_explains_plan@ig2_dutch_explains_plan`；`script@story@odr1@ig@ig3_vantage_point_scripted_cutscene@ig3_vantage_point_dutch`
- **高频 native**：PLAYER::PLAYER_PED_ID ×646、ENTITY::DOES_ENTITY_EXIST ×308、ENTITY::GET_ENTITY_COORDS ×246、MISC::GET_GAME_TIMER ×224、PED::SET_PED_CONFIG_FLAG ×217

#### 4. 劫后余波 `RPRSN`

- 脚本：`rcm_pearson1.c`（强匹配，86,440 行 / 2,675 个函数）
- **目标（脚本顺序）**
  1. 返回查尔斯处。
  2. 返回狩猎区。
  3. 返回皮尔逊处。
  4. 返回鹿处。
  5. 跟随查尔斯。
  6. 从背后接近您的马。
  7. 跟随查尔斯。
  8. 前往皮尔逊处。
  9. 从背后接近您的马。
  10. 扛起鹿。
  11. 找回掉落的鹿。
  12. 将鹿放到您的马上。
  - …（另有 2 条）
- **生成调用点**：ped 1 / vehicle 0 / object 6 / pickup 0
- **过场**：`script@Story@RPRSN1@mission_jump_cameras`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×312、ENTITY::IS_ENTITY_DEAD ×225、PLAYER::GET_PLAYER_INDEX ×221、MISC::IS_BIT_SET ×153、MISC::GET_HASH_KEY ×149

#### 5. 利维提克斯·康沃尔到底是谁？ `WNT4`

- 脚本：`winter4.c`（强匹配，111,628 行 / 3,021 个函数）
- **目标（脚本顺序）**
  1. 骑上您的马。
  2. 跟随达奇。
  3. 与帮派一同骑行时，可按两下 移至队前或按两下 退至队后。
  4. 查看比尔的情况。
  5. 拿起线轴。
  6. 将引线连接到起爆器上。
  7. 返回帮派成员处。
  8. 跳上火车。
  9. 前往火车货运车厢的前部。
  10. 用 瞄准时，按 启用死神之眼。这个技能能让时间放慢。
  11. 干掉守卫。
  12. 前往火车头前端。
  - …（另有 15 条）
- **失败条件**：火车被抛弃了。
- **生成调用点**：ped 2 / vehicle 0 / object 33 / pickup 0
- **过场**：`script@Story@WNT4@mission_jump_cameras`；`script@Story@WNT4@train_loot_cameras`；`script@story@wnt4@ig@ig29_dynamite_bill_react@ig29_dynamite_bill_react`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×420、ENTITY::IS_ENTITY_DEAD ×410、VEHICLE::GET_TRAIN_CARRIAGE ×236、PED::SET_PED_CONFIG_FLAG ×193、PAD::DISABLE_CONTROL_ACTION ×173

#### 6. 东部边境 `MUD1`

- 脚本：`mudtown1.c`（强匹配，93,695 行 / 2,646 个函数）
- **目标（脚本顺序）**
  1. 按住 跟车队速度保持一致。
  2. 返回您的马车。
  3. 登上马车。
  4. 前往马掌望台。
  5. 与何西阿一起登上马车。
- **失败条件**：车队被抛弃了。；您离队伍成员太远了。；一匹篷车马死了。；马车已无法使用了。
- **生成调用点**：ped 2 / vehicle 12 / object 1 / pickup 0
- **过场**：`script@story@mud1@ig@ig15_wagon_craft@ig15_wagon_craft`；`script@story@mud1@ig@ig_10@wheel_fixing`；`script@story@mud1@ig@ig15_wagon_craft@ig15_wagon_craft_cam`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×399、ENTITY::IS_ENTITY_DEAD ×178、PLAYER::GET_PLAYER_INDEX ×159、BUILTIN::TO_FLOAT ×147、MISC::GET_HASH_KEY ×144

### 2.2 第二章 · 马掌望台

#### 1. 美式休息 `MUD2`

- 脚本：`mudtown2.c`（强匹配，87,726 行 / 2,433 个函数）
- **目标（脚本顺序）**
  1. 和汤米打架。
  2. 打败滋事暴徒。
  3. 抓住对方时，按 可以挥拳，或按住 使出锁喉。
  4. 抓住对方时，使用 或 并按 将对手朝相应方向扔出去。
  5. 从混战中脱身。
  6. 解救哈维尔。
- **生成调用点**：ped 2 / vehicle 1 / object 2 / pickup 0
- **过场**：`script@story@mud2@leadout@int@leadoutall`；`script@story@mud2@leadout@int@broken_table_only`；`script@story@MUD2@leadin@mcs_1@fight`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×254、ENTITY::IS_ENTITY_DEAD ×204、PLAYER::GET_PLAYER_INDEX ×155、BUILTIN::TO_FLOAT ×153、MISC::IS_STRING_NULL_OR_EMPTY ×152

#### 2. 礼貌社会，瓦伦丁风格 `MUD3`

- 脚本：`mudtown3.c`（强匹配，106,014 行 / 3,041 个函数）
- **目标（脚本顺序）**
  1. 帮助
  2. 帮助
  3. 杀死
  4. 救了吉米·布鲁克斯
  5. 找回脱缰的马
  6. 跟随大叔。
  7. 搜查旅店，找到凯伦。
  8. 跟随凯伦。
  9. 追上来自黑水镇的人。
  10. 将马还给马车夫。
  11. 与马车夫对话。
- **生成调用点**：ped 2 / vehicle 3 / object 2 / pickup 0
- **过场**：`script@story@mud3@ig@IG_2_PrayingKelonian@base`；`script@story@mud3@ig@ig_3_room2a@base`；`script@story@MUD3@IG@IG_8_KarensRoom@IG_8_KarensRoom`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×351、ENTITY::IS_ENTITY_DEAD ×225、PLAYER::GET_PLAYER_INDEX ×168、BUILTIN::TO_FLOAT ×149、MISC::IS_BIT_SET ×149

#### 3. 谁人无罪 `REV1`

- 脚本：`reverend1.c`（强匹配，100,380 行 / 2,990 个函数）
- **目标（脚本顺序）**
  1. 扛起斯旺森牧师。
  2. 寻找斯旺森牧师。
  3. 追上目击者。
  4. 前往斯旺森牧师处。
  5. 解救斯旺森牧师。
  6. 带斯旺森牧师返回马掌望台。
  7. 将斯旺森牧师放到他的床上。
  8. 从您的马上移除斯旺森牧师。
- **失败条件**：您的马死了。；目击者逃走了。；斯旺森牧师死了。
- **生成调用点**：ped 2 / vehicle 0 / object 1 / pickup 0
- **过场**：`script@story@rev1@ig@ig5_track_rescue@ig5_track_rescue`；`script@story@rev1@ig@ig1_witness_chat@ig1_witness_chat`；`script@story@rev1@ig@reverend_knocked_out@reverend_knocked_out`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×272、ENTITY::IS_ENTITY_DEAD ×200、PLAYER::GET_PLAYER_INDEX ×162、BUILTIN::TO_FLOAT ×156、MISC::GET_HASH_KEY ×146

#### 4. 在前的，将要在后了 `SEN1`

- 脚本：`sean1.c`（强匹配，95,278 行 / 2,507 个函数）
- **目标（脚本顺序）**
  1. 前往悬崖边缘。
  2. 返回哈维尔处。
  3. 把西恩放下来
  4. 跟随哈维尔和查尔斯。
  5. 找到那艘船。
  6. 跟随特里劳尼。
  7. 跟随特里劳尼。
  8. 返回特里劳尼处。
  9. 跟随哈维尔。
- **失败条件**：西恩死了。；西恩被抛弃了。；特里劳尼的马死了。；哈维尔的马死了。；哈维尔死了。
- **生成调用点**：ped 2 / vehicle 8 / object 12 / pickup 0
- **过场**：`script@story@sen1@ig@ig1_walk_to_horses@ig1_walk_to_horses`；`script@story@sen1@ig@ig2_charles_wave@IG2_Charles_Wave`；`script@story@sen1@ig@ig_3_drag_sean_off_boat@ig_3_boat`
- **高频 native**：PLAYER::PLAYER_PED_ID ×427、ENTITY::DOES_ENTITY_EXIST ×288、ENTITY::GET_ENTITY_COORDS ×219、ENTITY::IS_ENTITY_DEAD ×194、PED::IS_PED_INJURED ×190

#### 5. 童叟无欺的蛇油 `BOU1`

- 脚本：`bounty1.c`（强匹配，86,377 行 / 2,581 个函数）
- **失败条件**：悬赏目标死了。；悬赏目标被惊动了。
- **生成调用点**：ped 2 / vehicle 0 / object 7 / pickup 0
- **过场**：`script@story@bou1@leadin@mcs1@ilo@benny_sleeping`；`script@story@bou1@leadin@mcs1@ilo@props`；`script@story@bou1@ig@ig1_suspend_p1@ig1_suspend_p1`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×248、ENTITY::IS_ENTITY_DEAD ×172、PLAYER::GET_PLAYER_INDEX ×171、MISC::GET_HASH_KEY ×141、BUILTIN::TO_FLOAT ×140

#### 6. 安静时光 `SAL1`

- 脚本：`saloon1.c`（强匹配，89,194 行 / 2,539 个函数）
- **目标（脚本顺序）**
  1. 骑马前往瓦伦丁的酒馆。
  2. 返回酒馆。
  3. 前往吧台。
  4. 前往蓝尼处。
- **失败条件**：您离瓦伦丁太远了。；您离瓦伦丁太远了。；您离酒馆太远了。；您离酒馆太远了。
- **生成调用点**：ped 2 / vehicle 0 / object 3 / pickup 0
- **过场**：`script@story@sal1@leadin@int@ilo`；`script@story@sal1@leadin@mcs1@leadin_lenny`；`script@story@sal1@leadin@mcs1@leadin_arthur`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×251、ENTITY::IS_ENTITY_DEAD ×189、PLAYER::GET_PLAYER_INDEX ×158、MISC::GET_HASH_KEY ×148、BUILTIN::TO_FLOAT ×145

#### 7. 温柔的人有福了？ `UTP1`

- 脚本：`utopia1.c`（强匹配，102,970 行 / 2,874 个函数）
- **目标（脚本顺序）**
  1. 找到并与迈卡交谈。
  2. 想办法把迈卡救出来。
  3. 拉动蒸汽机上的控制杆。
  4. 跟随迈卡。
  5. 用 瞄准时，按 启用死神之眼。这个技能让时间放慢，让您在战斗中可以做出更多反应。按 关闭技能。
  6. 骑上您的马。
  7. 从地图上的红色搜索区域逃出来，躲避在警察的视线之外，直到他们停止寻找您。
  8. 与迈卡一起逃脱警察追捕。
  9. 保护迈卡。
  10. 抓住控制杆
  11. 抓住控制杆
- **生成调用点**：ped 2 / vehicle 2 / object 7 / pickup 0
- **过场**：`script@story@utp1@LEADIN@MCS_1@Leadin_Playlists`；`script@story@utp1@ig@ig23_grabhook@ig23_grabhookenter`；`script@story@utp1@ig@ig23_grabhook@ig23_grabhookexit`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×418、ENTITY::IS_ENTITY_DEAD ×284、PLAYER::GET_PLAYER_INDEX ×159、BUILTIN::TO_FLOAT ×151、MISC::GET_HASH_KEY ×145

#### 8. 自尊，负伤离场 `HNT1`

- 脚本：`hunting1.c`（强匹配，103,173 行 / 2,959 个函数）
- **生成调用点**：ped 2 / vehicle 0 / object 19 / pickup 0
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×445、PLAYER::PLAYER_ID ×227、ENTITY::IS_ENTITY_DEAD ×210、PED::IS_PED_INJURED ×177、PLAYER::GET_PLAYER_INDEX ×165

#### 9. 得人的渔夫 `RABI1`

- 脚本：`rcm_abigail11.c`（强匹配，80,413 行 / 2,602 个函数）
- **目标（脚本顺序）**
  1. 带杰克前往钓鱼点。
  2. 返回马掌望台。
  3. 前往杰克处。
  4. 前往钓鱼点。
  5. 返回杰克处。
  6. 返回钓鱼点。
- **失败条件**：杰克被吓坏了。；您的马死了。；杰克被抛弃了。；艾比盖尔死了。；警察被惊动了。
- **生成调用点**：ped 1 / vehicle 0 / object 16 / pickup 0
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×254、ENTITY::IS_ENTITY_DEAD ×210、PLAYER::GET_PLAYER_INDEX ×163、MISC::GET_HASH_KEY ×160、MISC::IS_BIT_SET ×149

#### 10. 美国脊梁 `RHMR0`

- 脚本：`rcm_homerob00.c`（强匹配，80,261 行 / 2,668 个函数）
- **目标（脚本顺序）**
  1. 将驿站马车驶入仓库。
  2. 与何西阿重新会合。
  3. 前往卡莫迪山谷。
  4. 将驿站马车送去翡翠牧场。
  5. 跟随何西阿去勘察卡莫迪山谷。
  6. 跟随何西阿到驿站马车处。
  7. 返回路线。
  8. 与何西阿交谈。
  9. 偷走藏匿物。
- **失败条件**：离路线太远了。；驿站马车已无法驾驶。；离驿站马车太远了。
- **生成调用点**：ped 1 / vehicle 1 / object 4 / pickup 0
- **高频 native**：ENTITY::IS_ENTITY_DEAD ×266、ENTITY::DOES_ENTITY_EXIST ×243、MISC::GET_HASH_KEY ×158、PLAYER::GET_PLAYER_INDEX ×154、BUILTIN::TO_FLOAT ×140

#### 11. 真爱易逝：第 3 部分 `MRY1`

- 脚本：`mary1.c`（强匹配，93,269 行 / 2,672 个函数）
- **目标（脚本顺序）**
  1. 制服切罗尼亚教首领。
  2. 走近切罗尼亚教徒。
  3. 说服切罗尼亚教首领让杰米离开。
  4. 返回切罗尼亚教首领处。
  5. 追上杰米。
  6. 解除杰米的武器。
  7. 走近杰米。
  8. 带杰米返回玛丽处。
  9. 在火车站与玛丽会合。
  10. 返回杰米处。
  11. 开枪打掉杰米手里的枪。
- **失败条件**：您离切罗尼亚教营地太远了。；杰米死了。；杰米逃走了。；玛丽死了。
- **生成调用点**：ped 2 / vehicle 1 / object 10 / pickup 0
- **过场**：`script@story@mry1@ig@ig_2@ig2_charm`；`script@story@mry1@leadout@mcs1@leadout`；`script@story@mry1@leadout@mcs4@leadout`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×345、ENTITY::IS_ENTITY_DEAD ×283、PLAYER::GET_PLAYER_INDEX ×184、PED::SET_PED_CONFIG_FLAG ×169、MISC::GET_HASH_KEY ×142

#### 12. 美国田园风光 `UTP2`

- 脚本：`utopia2.c`（强匹配，98,144 行 / 2,576 个函数）
- **目标（脚本顺序）**
  1. 攻击守卫并让驿站马车停下。
  2. 攻击敌对帮派成员。
  3. 跟随迈卡。
  4. 追上驿站马车。
  5. 返回驿站马车。
  6. 攻击守卫和敌对帮派成员。
  7. 与迈卡在驿站马车处会面。
  8. 射击挂锁。
- **失败条件**：驿站马车已无法驾驶。；离驿站马车太远了。
- **生成调用点**：ped 2 / vehicle 2 / object 4 / pickup 0
- **过场**：`script@story@UTP2@IG@IG_1_MICAH_COACH_REACT_WAIT@IG_1_MICAH_COACH_REACT_WAIT`；`script@story@UTP2@IG@IG_2_RIFLE_FOUND_ON_COACH@IG_2_RIFLE_FOUND_ON_COACH`；`script@story@UTP2@IG@IG_4_AMBUSH_REACT@IG_4_AMBUSH_REACT`
- **高频 native**：ENTITY::IS_ENTITY_DEAD ×612、ENTITY::DOES_ENTITY_EXIST ×299、PLAYER::GET_PLAYER_INDEX ×172、PED::SET_PED_CONFIG_FLAG ×152、BUILTIN::TO_FLOAT ×143

#### 13. 火上浇油：第 2 部分 `RMUD32`

- 脚本：`rcm_mudtown3_2.c`（弱匹配，62,935 行 / 2,046 个函数）
- **生成调用点**：ped 1 / vehicle 1 / object 0 / pickup 0
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×232、PLAYER::GET_PLAYER_INDEX ×148、MISC::GET_HASH_KEY ×148、ENTITY::IS_ENTITY_DEAD ×143、BUILTIN::TO_FLOAT ×136

#### 14. 火上浇油：第 4 部分 `MUD6`

- 脚本：`mudtown3b.c`（弱匹配，94,319 行 / 2,827 个函数）
- **目标（脚本顺序）**
  1. 驾驶马车去铁路交叉口。
  2. 将马车停在铁轨上。
  3. 干掉守卫。
  4. 逃脱警察追捕。
  5. 登上马车。
  6. 接上您的伙伴。
  7. 登上乘客车厢。
  8. 跟随约翰。
  9. 殴打乘客。
  10. 抢劫总数：~1$~
  11. 查看西恩的情况。
  12. 搜刮行李。
  - …（另有 5 条）
- **失败条件**：帮派成员被抛弃了。；西恩被抛弃了。；查尔斯被抛弃了。；约翰被抛弃了。；您杀死了无辜的乘客。
- **生成调用点**：ped 2 / vehicle 1 / object 3 / pickup 0
- **过场**：`script@story@mud3b@leadout@int@leadout`；`script@story@mud3b@ig@ig_8_wagon_descent@ig8_wagon_descent`；`script@story@mud3b@ig@ig_1@ig1_knockout_engineer`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×344、ENTITY::IS_ENTITY_DEAD ×192、PLAYER::GET_PLAYER_INDEX ×180、BUILTIN::TO_FLOAT ×157、MISC::GET_HASH_KEY ×149

#### 15. 绵羊和山羊 `MUD4`

- 脚本：`mudtown4.c`（强匹配，131,581 行 / 3,397 个函数）
- **目标（脚本顺序）**
  1. 与枪械铺老板交谈，查看武器目录并购买武器。枪械铺老板还会出售多种特殊弹药和武器模组。
  2. 把绵羊赶进拍卖场。
  3. 在酒馆与达奇会合。
  4. 把施特劳斯放在约翰的马上。
  5. 扛起施特劳斯。
  6. 除掉党羽。
  7. 前往马处。
  8. 逃离瓦伦丁。
  9. 朝挟持约翰的挟持者开火。
  10. 牵着您的马和约翰一起走。
  11. 骑上您的马。
  12. 朝牧工附近开枪来吓跑他们。
  - …（另有 18 条）
- **失败条件**：警察被惊动了。；枪械铺老板死了。；羊群逃走了。；羊群被抛弃了。；太多绵羊死了。；帮派成员被抛弃了。
- **生成调用点**：ped 2 / vehicle 7 / object 3 / pickup 2
- **过场**：`script@Story@MUD4@sheep_herding`；`script@story@MUD4@leadout@int@Leadout_p1`；`script@story@mud4@ig@ig_3_john_binoculars@john_binoculars`
- **高频 native**：ENTITY::IS_ENTITY_DEAD ×714、ENTITY::DOES_ENTITY_EXIST ×510、ENTITY::GET_PED_INDEX_FROM_ENTITY_INDEX ×273、PED::SET_PED_CONFIG_FLAG ×235、PLAYER::GET_PLAYER_INDEX ×220

#### 16. 邻居来串门 `RDST2`

- 脚本：`rcm_dusters21.c`（强匹配，87,107 行 / 2,542 个函数）
- **目标（脚本顺序）**
  1. 返回木屋。
  2. 搜查木屋。
  3. 用刀刺杀
  4. 搜查烟囱。
- **失败条件**：离藏身处太远了。
- **生成调用点**：ped 1 / vehicle 0 / object 6 / pickup 1
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×349、PED::IS_PED_INJURED ×320、MISC::GET_GAME_TIMER ×278、ENTITY::IS_ENTITY_DEAD ×239、PED::SET_PED_CONFIG_FLAG ×190

#### 17. 放债与更多罪孽：第 3 部分 `RDOWN3`

- 脚本：`rcm_down3.c`（弱匹配，71,282 行 / 2,344 个函数）
- **生成调用点**：ped 1 / vehicle 0 / object 2 / pickup 0
- **过场**：`script@Story@Downes1@ride_to_horseshoe`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×199、ENTITY::IS_ENTITY_DEAD ×153、MISC::GET_HASH_KEY ×150、PLAYER::GET_PLAYER_INDEX ×143、BUILTIN::TO_FLOAT ×140

#### 18. 罕异的善举 `RDTC1`

- 脚本：`rcm_dutch11.c`（强匹配，82,861 行 / 2,599 个函数）
- **目标（脚本顺序）**
  1. 骑马前往露莓溪。
  2. 搜查营地。
- **生成调用点**：ped 1 / vehicle 5 / object 7 / pickup 0
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×353、ENTITY::IS_ENTITY_DEAD ×254、PLAYER::GET_PLAYER_INDEX ×154、MISC::IS_BIT_SET ×153、BUILTIN::TO_FLOAT ×150

### 2.3 第三章 · 谢迪贝莱

#### 1. 重返罪恶之地 `MUD5`

- 脚本：`mudtown5.c`（强匹配，118,705 行 / 3,164 个函数）
- **目标（脚本顺序）**
  1. 跟随比尔前往瓦伦丁。
  2. 跟随帮派前往银行。
  3. 进入银行。
  4. 打开出纳员室的门。
  5. 进入保险库。
  6. 点燃导火线。
  7. 与比尔、凯伦和蓝尼重新会合。
  8. 搜刮
  9. 点燃导火线
  10. 前往马处。
  11. 与比尔、凯伦和蓝尼一起逃脱警察的追捕。
  12. 骑马前往唐斯牧场。
  - …（另有 2 条）
- **失败条件**：银行出纳员死了。；帮派成员被抛弃了。；警察被惊动了。；您杀死了无辜的人。；镇民被惊动了。
- **生成调用点**：ped 2 / vehicle 2 / object 17 / pickup 0
- **过场**：`script@story@MUD5@blendout2`；`script@story@MUD5@IG@IG_0_Move_Aside@IG_0_Move_Aside`；`script@story@MUD5@IG@IG_1_Bank_Robbery@IG_1_Bank_Robbery`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×479、PED::SET_PED_CONFIG_FLAG ×260、ENTITY::IS_ENTITY_DEAD ×239、PLAYER::GET_PLAYER_INDEX ×210、BUILTIN::TO_FLOAT ×173

#### 2. 新南方 `FUD1`

- 脚本：`feud1.c`（强匹配，107,101 行 / 2,806 个函数）
- **目标（脚本顺序）**
  1. 追上火车。
  2. 骑马与火车并排前进。
  3. 追上剩下的安德森帮成员。
  4. 扛起安德森帮成员。
  5. 返回安德斯·安德森处。
  6. 返回警长办公室处。
  7. 将安德斯·安德森带回警长办公室。
  8. 扛起安德斯·安德森。
  9. 将安德斯·安德森放到您的马上。
  10. 与何西阿交谈。
  11. 返回钓鱼点。
  12. 返回营地。
- **失败条件**：离钓鱼点太远了。；离营地太远了。；离警长办公室太远了。；安德斯·安德森被抛弃了。；一位安德森帮的成员死了。；安德斯·安德森死了。
- **生成调用点**：ped 2 / vehicle 1 / object 1 / pickup 0
- **过场**：`script@story@fud1@ig@ig_1_trainhangloop@ig_1_fc1_start`；`script@story@fud1@ig@ig_1_trainhangloop@ig_1_fc2_start`；`script@story@fud1@ig@ig_1_trainhangloop@ig_1_pullup`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×553、ENTITY::IS_ENTITY_DEAD ×424、PED::IS_PED_INJURED ×299、VEHICLE::GET_TRAIN_CARRIAGE ×242、ANIMSCENE::DOES_ANIM_SCENE_EXIST ×197

#### 3. 妇女投票权的更多疑问 `RSAD1`

- 脚本：`rcm_sadie11.c`（强匹配，84,565 行 / 2,677 个函数）
- **目标（脚本顺序）**
  1. 前往邮局。
  2. 返回马车上。
  3. 返回莎迪处。
  4. 击退歹徒。
  5. 前往莎迪处。
- **失败条件**：莎迪死了。；莎迪被抛弃了。；皮尔逊死了。；离罗兹太远了。
- **生成调用点**：ped 1 / vehicle 2 / object 30 / pickup 0
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×295、ENTITY::IS_ENTITY_DEAD ×281、PAD::DISABLE_CONTROL_ACTION ×159、MISC::IS_BIT_SET ×157、BUILTIN::TO_FLOAT ×151

#### 4. 美式制酒 `GRY1`

- 脚本：`grays1.c`（强匹配，102,249 行 / 2,842 个函数）
- **目标（脚本顺序）**
  1. 跟随阿奇伯德。
  2. 前往沼泽。
  3. 返回沼泽地。
  4. 扛起私酒贩。
  5. 找到比尔。
  6. 返回达奇处。
  7. 跟随达奇。
  8. 与达奇比赛回营地。
  9. 带领比尔向左或向右。
  10. 帮助比尔在不被发现的情况下击晕私酒贩。
  11. 捆绑昏迷的私酒贩。
  12. 将私酒贩带到马车处。
  - …（另有 3 条）
- **失败条件**：囚车已无法驾驶。；您的同伴被抛弃了。；一名私酒贩逃走了。；您杀死了一名私酒贩。；私酒马车已无法驾驶。；副警长阿奇伯德死了。
- **生成调用点**：ped 2 / vehicle 3 / object 6 / pickup 0
- **过场**：`script@story@gry1@leadout@int@sheriff_loop`；`script@story@gry1@ig@ig_2_deputycallover@action`；`script@story@gry1@leadin@mcs2@base_arthurline`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×453、PAD::DISABLE_CONTROL_ACTION ×246、ENTITY::IS_ENTITY_DEAD ×241、PED::SET_PED_CONFIG_FLAG ×199、PLAYER::PLAYER_ID ×184

#### 5. 真爱之路：第 2 部分 `RBNP11`

- 脚本：`rcm_beau_and_penelope11.c`（强匹配，71,293 行 / 2,351 个函数）
- **生成调用点**：ped 1 / vehicle 1 / object 6 / pickup 0
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×229、ENTITY::IS_ENTITY_DEAD ×167、MISC::IS_BIT_SET ×152、MISC::GET_HASH_KEY ×149、PLAYER::GET_PLAYER_INDEX ×147

#### 6. 真爱之路：第 3 部分 `RBNP12`

- 脚本：`rcm_beau_and_penelope12.c`（弱匹配，77,555 行 / 2,482 个函数）
- **目标（脚本顺序）**
  1. 跟随鲍。
  2. 返回鲍处。
  3. 返回任务路线。
  4. 返回鲍处。
  5. 返回马车处。
  6. 返回佩内洛普处。
  7. 带领鲍前往巷子。
  8. 带领鲍离开巷子。
  9. 与表亲交谈。
- **失败条件**：鲍死了。；鲍被抛弃了。；离马车太远了。；离任务路线太远了。；马车已无法驾驶。
- **生成调用点**：ped 1 / vehicle 1 / object 9 / pickup 0
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×277、ENTITY::IS_ENTITY_DEAD ×214、PAD::DISABLE_CONTROL_ACTION ×171、MISC::IS_BIT_SET ×154、PLAYER::GET_PLAYER_INDEX ×151

#### 7. 广告，美国的新派艺术：第 2 部分 `BRT1`

- 脚本：`braithwaites1.c`（强匹配，105,442 行 / 2,795 个函数）
- **目标（脚本顺序）**
  1. 回到马车上。
  2. 返回马车处。
  3. 等待何西阿返回马车上。
  4. 返回何西阿处。
  5. 将私酒运往布雷斯韦特庄园。
  6. 将私酒带到罗兹酒馆。
  7. 返回酒馆。
  8. 从马车后面取私酒。
  9. 跟随何西阿。
  10. 跟随何西阿上楼逃跑。
  11. 消灭莱莫恩掠夺者。
  12. 解决莱莫恩掠夺者。
  - …（另有 4 条）
- **失败条件**：离马车太远了。；何西阿被抛弃了。；您离酒馆太远了。；布雷斯韦特庄园的守卫被惊动了。；罗兹酒馆附近的警察被惊动了。；离布雷斯韦特庄园太远了。
- **生成调用点**：ped 2 / vehicle 2 / object 6 / pickup 1
- **过场**：`script@story@brt1@leadin@mcs_1@cat_part1`；`script@story@brt1@leadin@mcs_1@wagon_part1`；`script@story@brt1@leadin@mcs_1@part2`
- **高频 native**：ENTITY::IS_ENTITY_DEAD ×380、ENTITY::DOES_ENTITY_EXIST ×378、ANIMSCENE::SET_ANIM_SCENE_ENTITY ×216、PLAYER::GET_PLAYER_INDEX ×159、PAD::DISABLE_CONTROL_ACTION ×158

#### 8. 烟草的美妙乐趣 `BRT2`

- 脚本：`braithwaites2.c`（强匹配，95,900 行 / 2,737 个函数）
- **目标（脚本顺序）**
  1. 返回烟草田。
  2. 离开
  3. 守卫
  4. 登上马车。
  5. 等待西恩上马车。
  6. 前往卡利加种植园。
  7. 当西恩驾车进入卡利加种植园时，躲在马车里。
  8. 藏在马车中，直到安全后再出来。
  9. 悄悄解决守卫。
  10. 帮助西恩隐藏尸体。
  11. 返回马车谷仓。
  12. 跟随西恩。
  - …（另有 12 条）
- **失败条件**：守卫被惊动了。；西恩被抛弃了。；一匹逃跑的马死了。
- **生成调用点**：ped 2 / vehicle 2 / object 21 / pickup 0
- **过场**：`script@story@BRT2@leadin@int@livingRoom`；`script@story@brt2@ig@ig_1_hide_in_wagon@ig_1_hide_in_wagon`；`script@story@brt2@ig@ig_1_hide_in_wagon@ig_1_hide_in_wagon_p2`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×339、ENTITY::IS_ENTITY_DEAD ×234、PED::SET_PED_CONFIG_FLAG ×178、PLAYER::GET_PLAYER_INDEX ×162、BUILTIN::TO_FLOAT ×147

#### 9. 马肉大餐 `GRY2`

- 脚本：`grays2.c`（强匹配，97,439 行 / 2,801 个函数）
- **目标（脚本顺序）**
  1. 解决剩余追捕者。
  2. 解决剩余追捕者们。
  3. 偷马贼
  4. 去马厩见约翰和哈维尔。
  5. 返回约翰处。
  6. 跟随约翰。
  7. 和守卫谈话。
  8. 将马带去马厩。
  9. 拴好您的马。
  10. 骑上您的马。
  11. 下马。
  12. 靠近马倌。
  - …（另有 18 条）
- **失败条件**：布雷斯韦特的人被惊动了。；格雷家族的人被惊动了。；您的同伴被抛弃了。；哈维尔死了。；约翰死了。；哈维尔的马死了。
- **生成调用点**：ped 2 / vehicle 2 / object 7 / pickup 0
- **过场**：`script@story@gry2@ig@ig_10_caligahall_guard@ig_10_caligahall_guard`；`script@story@gry2@leadin@int@p0a1_dialogue`；`script@story@gry2@leadin@int@p0_dialogue`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×354、ENTITY::IS_ENTITY_DEAD ×208、PLAYER::GET_PLAYER_INDEX ×174、PED::SET_PED_CONFIG_FLAG ×174、MISC::GET_HASH_KEY ×147

#### 10. 赏玩魔术师 `TRE1`

- 脚本：`trelawny1.c`（强匹配，97,633 行 / 2,768 个函数）
- **目标（脚本顺序）**
  1. 进入特里劳尼的篷车。
  2. 返回特里劳尼的篷车的方向。
  3. 返回特里劳尼的篷车。
  4. 跟随足迹走。
  5. 返回赏金猎人的踪迹。
  6. 痛殴赏金猎人。
  7. 返回赏金猎人的营地。
  8. 审问
  9. 跟随查尔斯。
  10. 在田里找到并消灭赏金猎人。
  11. 返回玉米地。
  12. 解决掉谷仓里的赏金猎人。
  - …（另有 16 条）
- **失败条件**：离特里劳尼的位置太远了。；离特里劳尼的篷车太远了。；离赏金猎人的足迹太远了。；离赏金猎人的营地太远了。；离玉米地太远了。；离谷仓太远了。
- **生成调用点**：ped 2 / vehicle 0 / object 17 / pickup 0
- **过场**：`script@story@TRE1@IG@IG_INT@ILO`；`script@story@TRE1@IG@IG_INT@WnT_Dutch_Arthur`；`script@story@tre1@ig@ig1_the_house@ig1_the_house`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×320、ENTITY::IS_ENTITY_DEAD ×241、PED::SET_PED_CONFIG_FLAG ×175、PLAYER::GET_PLAYER_INDEX ×169、BUILTIN::TO_FLOAT ×153

#### 11. 草根朋友 `RCHRB`

- 脚本：`rcm_coach_robbery1.c`（强匹配，78,987 行 / 2,506 个函数）
- **生成调用点**：ped 1 / vehicle 0 / object 19 / pickup 0
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×272、ENTITY::IS_ENTITY_DEAD ×189、PLAYER::GET_PLAYER_INDEX ×157、MISC::IS_BIT_SET ×157、MISC::GET_HASH_KEY ×152

#### 12. 无心之过 `CRN1`

- 脚本：`cornwall1.c`（强匹配，100,074 行 / 2,726 个函数）
- **目标（脚本顺序）**
  1. 等待马车出现。
  2. 跟随大叔。
  3. 与帮派成员一同摆脱追捕者。
  4. 保持躲藏状态。
  5. 对付追捕者。
  6. 靠近马车。
  7. 抢劫马车。
  8. 返回马车处。
  9. 藏进谷仓里。
  10. 返回帮派成员处。
  11. 击退攻击者。
  12. 从谷仓墙上的洞逃出去。
  - …（另有 3 条）
- **失败条件**：帮派成员被抛弃了。
- **生成调用点**：ped 2 / vehicle 5 / object 12 / pickup 0
- **过场**：`script@story@crn1@ig@ig1_spot_wagon@ig1_spot_wagon`；`script@story@crn1@ig@ig2_stop_the_wagon@ig2_stop_the_wagon`；`script@story@crn1@ig@ig2_stop_the_wagon@ig2_wagon_guys`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×409、ENTITY::IS_ENTITY_DEAD ×313、PLAYER::GET_PLAYER_INDEX ×161、BUILTIN::TO_FLOAT ×149、MISC::GET_HASH_KEY ×145

#### 13. 布施谅解之人 `RXCF1`

- 脚本：`rcm_exconfed11.c`（强匹配，86,588 行 / 2,681 个函数）
- **目标（脚本顺序）**
  1. 搜查
  2. 骑上您的马。
  3. 等待蓝尼。
  4. 跟随蓝尼。
  5. 跟随马车。
  6. 把马藏在树林里。
  7. 使用掩体。
  8. 使用狙击枪瞄准镜侦查谢迪贝莱。
  9. 告诉蓝尼最后的决定。
  10. 射击炸药。
  11. 时机一到，攻击劫掠者。
  12. 干掉莱莫恩掠夺者。
  - …（另有 6 条）
- **失败条件**：蓝尼被抛弃了。；您的马被抛弃了。；离马车太远了。；车夫被惊动了。；您杀死了车夫。；马车已无法驾驶。
- **生成调用点**：ped 1 / vehicle 3 / object 16 / pickup 0
- **过场**：`script@Story@ExConFed1@ride_to_clemens`；`script@story@rxcf1@ig@ig_1_lennypreacher@ig_1_lennypreacher`；`script@story@rxcf1@ig@ig_1_guardidles@ig_1_guard_idle_0`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×336、ENTITY::IS_ENTITY_DEAD ×304、MISC::GET_HASH_KEY ×154、MISC::IS_BIT_SET ×154、PLAYER::GET_PLAYER_INDEX ×151

#### 14. 小镇信步 `GRY3`

- 脚本：`grays3.c`（强匹配，90,629 行 / 2,514 个函数）
- **目标（脚本顺序）**
  1. 击退伏击者。
  2. 跟随帮派。
  3. 返回帮派。
  4. 抵御攻击者。
  5. 跟随迈卡。
  6. 杀死格雷家的人。
- **失败条件**：帮派成员被抛弃了。
- **生成调用点**：ped 2 / vehicle 0 / object 6 / pickup 1
- **过场**：`script@story@GRY3@IG@IG_1_MeetBillMicah@leadin_front`；`script@story@GRY3@IG@IG_1_MeetBillMicah@IG_1_EnemyIdles`；`script@story@GRY3@IG@IG_1_MeetBillMicah@Walk_Through_Town`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×306、ENTITY::IS_ENTITY_DEAD ×260、PLAYER::GET_PLAYER_INDEX ×159、BUILTIN::TO_FLOAT ×156、MISC::GET_HASH_KEY ×143

#### 15. 古恨今仇 `BRT3`

- 脚本：`braithwaites3.c`（强匹配，88,779 行 / 2,472 个函数）
- **目标（脚本顺序）**
  1. 骑马跟随达奇。
  2. 与达奇一起离开庄园。
  3. 前往达奇处。
  4. 跟达奇一起走向庄园。
  5. 解决守卫。
  6. 等待达奇。
  7. 在庄园内搜寻杰克。
  8. 前往楼上达奇处。
  9. 杀死攻击者。
  10. 杀死儿子们。
- **失败条件**：布雷斯韦特的人被惊动了。；凯瑟琳·布雷斯韦特死了。
- **生成调用点**：ped 2 / vehicle 1 / object 1 / pickup 1
- **过场**：`script@Story@BRT3@GangRide`；`script@story@brt3@leadout@int@leadout`；`script@story@BRT3@IG@IG_1_StealAGodDamnBoy@IG_1_WalkToMansion`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×255、ENTITY::IS_ENTITY_DEAD ×243、PLAYER::GET_PLAYER_INDEX ×158、MISC::GET_HASH_KEY ×145、BUILTIN::TO_FLOAT ×144

#### 16. 谢迪贝莱之战 `RDTC2`

- 脚本：`rcm_dutch21.c`（强匹配，81,498 行 / 2,486 个函数）
- **生成调用点**：ped 1 / vehicle 4 / object 4 / pickup 1
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×372、ENTITY::IS_ENTITY_DEAD ×233、PLAYER::GET_PLAYER_INDEX ×153、MISC::GET_HASH_KEY ×149、BUILTIN::TO_FLOAT ×148

#### 17. 和平使者万岁 `DST3`

- 脚本：`odriscolls3.c`（弱匹配，103,949 行 / 2,868 个函数）
- **目标（脚本顺序）**
  1. 骑上您的马。
  2. 跟随迈卡。
  3. 回到会面地点。
  4. 前往观察位置。
  5. 使用双筒望远镜给达奇和迈卡望风。
  6. 从奥德里斯科帮成员处逃脱。
  7. 找一条出路逃跑。
  8. 骑马离开该区域。
  9. 骑马离开该区域。
  10. 回到克莱蒙斯岬。
- **失败条件**：亚瑟的马死了。；达奇的马死了。；迈卡的马死了；离会面地点太远了。
- **生成调用点**：ped 2 / vehicle 0 / object 5 / pickup 1
- **过场**：`script@Story@DST3@return_to_camp`；`script@story@odr3@ig@ig1_beaten@ig1_beaten`；`script@story@odr3@ig@ig2_escape_shot@ig2_escape_shot_gang`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×318、ENTITY::IS_ENTITY_DEAD ×307、PAD::DISABLE_CONTROL_ACTION ×221、PLAYER::GET_PLAYER_INDEX ×161、BUILTIN::TO_FLOAT ×153

### 2.4 第四章 · 圣丹尼斯

#### 1. 文明之乐 `MOB1`

- 脚本：`mob1.c`（强匹配，104,242 行 / 2,900 个函数）
- **目标（脚本顺序）**
  1. 跟随孩子。
  2. 返回孩子处。
  3. 追上孩子。
  4. 在酒馆附近找达奇。
  5. 返回吧台处。
  6. 前往吧台。
  7. 和酒保交谈。
  8. 返回搜索区域。
  9. 在巷子里打听勃朗特。
  10. 返回酒馆。
  11. 返回达奇处。
  12. 在巷子里搜寻孩子。
  - …（另有 1 条）
- **失败条件**：您犯法了。；一个孩子被吓坏了。；一个孩子被吓坏了。；小孩被吓坏了。；离吧台太远了。；离酒馆太远了。
- **生成调用点**：ped 2 / vehicle 14 / object 43 / pickup 0
- **过场**：`script@story@MOB1@leadout@int@Arthur_look_action`；`script@story@MOB1@leadout@int@poker_TEMP_loop`；`script@story@MOB1@leadout@int@tables_TEMP_loop`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×496、ENTITY::IS_ENTITY_DEAD ×326、PED::SET_PED_CONFIG_FLAG ×181、ANIMSCENE::SET_ANIM_SCENE_ENTITY ×171、PLAYER::GET_PLAYER_INDEX ×164

#### 2. 金鸟笼 `IND1`

- 脚本：`industry1.c`（强匹配，110,631 行 / 3,049 个函数）
- **目标（脚本顺序）**
  1. 跟随侍者。
  2. 跟随达奇。
  3. 在院子里与客人交谈。
  4. 将醉汉从市长身边拉走。
  5. 返回市长处。
  6. 跟随仆人且不要被发现。
  7. 从桌子里找出账本。
  8. 返回正在参加宴会的达奇处。
  9. 返回达奇处。
  10. 护送
  11. 离开仆人的视线，让他继续做事。
  12. 检查
  - …（另有 2 条）
- **失败条件**：达奇被抛弃了。；侍者被抛弃了。；离市长的宴会太远了。；宴会的保安被惊动了。；警察被惊动了。
- **生成调用点**：ped 2 / vehicle 1 / object 128 / pickup 0
- **过场**：`script@story@IND1@IG@IG4_ESCORT@IG4_Escort`；`script@story@IND1@LEADIN@MCS3@base_enter_exit_dialogue`；`script@story@IND1@LEADOUT@MCS3@leadout`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×437、ENTITY::IS_ENTITY_DEAD ×206、PLAYER::GET_PLAYER_INDEX ×161、PLAYER::PLAYER_ID ×158、MISC::GET_HASH_KEY ×148

#### 3. 正人君子安吉洛·勃朗特 `MOB2`

- 脚本：`mob2.c`（强匹配，102,476 行 / 2,846 个函数）
- **目标（脚本顺序）**
  1. 跟随达奇。
  2. 追击并解决盗墓者。
  3. 跟随约翰离开墓地。
  4. 返回勃朗特的庄园。
  5. 跟随约翰。
  6. 找到骚动的来源。
  7. 跟随达奇。
  8. 返回墓地。
  9. 返回墓地。
- **失败条件**：警察被惊动了。；勃朗特的守卫被惊动了。；勃朗特的守卫被惊动了。；离勃朗特的庄园太远了。
- **生成调用点**：ped 2 / vehicle 0 / object 12 / pickup 0
- **过场**：`script@story@mob2@leadin@int_a@retry_leadout`；`script@story@mob2@leadin@int_c@base`；`script@story@mob2@leadin@int_c@leadin_guard_l`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×410、ENTITY::IS_ENTITY_DEAD ×300、PLAYER::GET_PLAYER_INDEX ×171、BUILTIN::TO_FLOAT ×146、PED::SET_PED_CONFIG_FLAG ×145

#### 4. 城市消遣 `MOB3`

- 脚本：`mob3.c`（强匹配，92,970 行 / 2,582 个函数）
- **目标（脚本顺序）**
  1. 强迫收银员打开保险箱。
  2. 抢劫顾客。
  3. 击退警察。
  4. 击退警察。
  5. 返回车站。
  6. 搜刮保险箱。
  7. 搜刮
  8. 跟随蓝尼。
  9. 跟随蓝尼。
  10. 登上马车。
  11. 干掉追兵。
- **失败条件**：帮派成员被抛弃了。；马车已无法驾驶。
- **生成调用点**：ped 2 / vehicle 3 / object 18 / pickup 0
- **过场**：`script@story@mob3@leadout@int@dutch_lenny`；`script@story@mob3@ig@ig1_dutch_holds_up_cashier@ig1_dutch_holds_up_cashier`；`script@story@mob3@ig@ig2_lenny_searches@ig2_lenny_searches_lenny`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×373、ENTITY::IS_ENTITY_DEAD ×271、PLAYER::GET_PLAYER_INDEX ×159、BUILTIN::TO_FLOAT ×147、MISC::GET_HASH_KEY ×145

#### 5. 放荡狂欢夜 `IND3`

- 脚本：`industry3.c`（强匹配，109,025 行 / 3,028 个函数）
- **目标（脚本顺序）**
  1. 跟随特里劳尼进入裁缝铺。
  2. 进入
  3. 乘坐马车。
  4. 跟随特里劳尼前往码头。
  5. 在扑克牌桌入座。
  6. 跟随赌场老板去保险室。
  7. 解决守卫。
  8. 从裁缝铺购买精品三件套时装。
  9. 跟随特里劳尼前往理发铺。
  10. 在理发铺做发型或胡须造型。
  11. 进入马车。
  12. 登上游舫。
  - …（另有 11 条）
- **失败条件**：赌场老板被抛弃了。
- **生成调用点**：ped 2 / vehicle 3 / object 22 / pickup 0
- **过场**：`script@Story@IND3@pullout`；`script@story@ind3@leadout@int@leadout`；`script@story@ind3@ig@ig_1_wait_in_tailors@ig_1_wait_in_tailors`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×339、ENTITY::IS_ENTITY_DEAD ×306、BUILTIN::TO_FLOAT ×188、PLAYER::GET_PLAYER_INDEX ×156、MISC::IS_STRING_NULL_OR_EMPTY ×153

#### 6. 乡村追击 `MOB4`

- 脚本：`mob4.c`（强匹配，96,170 行 / 2,890 个函数）
- **目标（脚本顺序）**
  1. 离开小船
  2. 返回托马斯处。
  3. 返回搜索区域。
  4. 检查
- **失败条件**：朱尔斯溺死了。；达奇被抛弃了。；您的马死了。；达奇的马死了。
- **生成调用点**：ped 2 / vehicle 1 / object 16 / pickup 0
- **过场**：`script@story@MOB4@LEADOUT@INT@Leadout_Hosea`；`script@story@MOB4@LEADIN@MCS1@leadin`；`script@story@MOB4@LEADIN@MCS2@base_props_placement`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×303、ENTITY::IS_ENTITY_DEAD ×206、PLAYER::GET_PLAYER_INDEX ×186、PAD::DISABLE_CONTROL_ACTION ×174、BUILTIN::TO_FLOAT ×160

#### 7. 有仇必报 `MOB5`

- 脚本：`mob5.c`（强匹配，93,572 行 / 2,596 个函数）
- **目标（脚本顺序）**
  1. 跟随约翰。
  2. 跟随达奇。
  3. 扛起勃朗特。
  4. 找到勃朗特。
  5. 将勃朗特带去交给达奇。
- **失败条件**：勃朗特死了。；勃朗特溺死了。
- **生成调用点**：ped 2 / vehicle 1 / object 1 / pickup 5
- **过场**：`script@story@mob5@ig@ig_3_porchconversation@porchconversation`；`script@story@mob5@ig@ig_4_guardsfountain@guardsfountain`；`script@story@mob5@ig@ig_5_guardbackyard@guardbackyard`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×297、ENTITY::IS_ENTITY_DEAD ×211、PLAYER::GET_PLAYER_INDEX ×164、WEAPON::SET_CURRENT_PED_WEAPON ×146、BUILTIN::TO_FLOAT ×144

#### 8. 银行业，美国老派艺术 `NBD1`

- 脚本：`saint_denis1.c`（强匹配，120,427 行 / 3,303 个函数）
- **目标（脚本顺序）**
  1. 跟随达奇。
  2. 跟随车队前往圣丹尼斯。
  3. 跟随达奇。
  4. 强迫银行经理打开保险库。
  5. 干掉警察。
  6. 前往屋顶。
  7. 在帮派成员爬上屋顶时干掉警察。
  8. 跟随蓝尼穿过屋顶。
  9. 将马拴在拴马桩上。
  10. 与达奇一起等待何西阿分散注意力。
  11. 解开保险柜。
  12. 进入保险库。
  - …（另有 15 条）
- **失败条件**：达奇死了。；帮派成员被抛弃了。；您离车队太远了。；离银行太远了。；警察被惊动了。；平克顿侦探被惊动了。
- **生成调用点**：ped 2 / vehicle 10 / object 10 / pickup 0
- **过场**：`script@story@NBD1@IG@IG_1_OneMoreTime@IG_1_OneMoreTime`；`script@story@NBD1@IG@IG_3_ArriveAtBank@IG_3_Arrival_Dutch`；`script@story@NBD1@IG@IG_3_ArriveAtBank@IG_3_Arrival_Bill`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×677、ENTITY::IS_ENTITY_DEAD ×390、ANIMSCENE::DOES_ANIM_SCENE_EXIST ×174、PED::SET_PED_CONFIG_FLAG ×172、PLAYER::GET_PLAYER_INDEX ×165

#### 9. 低开高走 `CABR01`

- 脚本：`act_bankrobbery01.c`（强匹配，63,947 行 / 1,998 个函数）
- **生成调用点**：ped 1 / vehicle 0 / object 2 / pickup 0
- **过场**：`script@story@WNT4@ig@ig32_arthur_spool_pickups@ig32_arthur_spool_pickups`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×181、MISC::GET_HASH_KEY ×135、BUILTIN::TO_FLOAT ×135、ENTITY::IS_ENTITY_DEAD ×125、PLAYER::GET_PLAYER_INDEX ×118

#### 10. 不、不、还是不 `SUS1`

- 脚本：`susan1.c`（强匹配，86,518 行 / 2,437 个函数）
- **目标（脚本顺序）**
  1. 等待苏珊解决掉守卫。
  2. 搜查房屋，寻找蒂莉。
  3. 抓走安东尼·福尔曼。
  4. 上马车。
  5. 前往拉德利之屋。
  6. 进入房屋。
  7. 给蒂莉松绑。
  8. 返回拉德利草场。
  9. 追上党羽。
  10. 返回苏珊处。
  11. 追上帮派。
  12. 用套索套住帮派首领。
  - …（另有 4 条）
- **失败条件**：离拉德利草场太远了。；您杀死了首领。；帮派逃走了。；帮派首领逃走了。；苏珊死了。；蒂莉死了。
- **生成调用点**：ped 2 / vehicle 2 / object 3 / pickup 0
- **过场**：`script@story@sus1@leadin@INT@ilo`；`script@story@sus1@ig@ig2_tilly_foreman_interaction@ig2_tilly`；`script@story@sus1@LEADIN@mcs1@ilo`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×289、ENTITY::IS_ENTITY_DEAD ×284、PLAYER::GET_PLAYER_INDEX ×168、MISC::GET_HASH_KEY ×146、BUILTIN::TO_FLOAT ×141

#### 11. 启示录的骑士们 `ODR4`

- 脚本：`odriscolls4.c`（强匹配，96,232 行 / 2,662 个函数）
- **目标（脚本顺序）**
  1. 击退奥德里斯科帮的成员。
  2. 到前门去。
  3. 返回到谢迪贝莱前面。
  4. 击退奥德里斯科帮的成员。
  5. 撤回房子里。
  6. 推倒柜子。
  7. 击退奥德里斯科帮的成员。
  8. 找到莎迪。
  9. 跳窗去找莎迪。
  10. 保护莎迪。
  11. 保护帮派成员。
  12. 返回谢迪贝莱。
- **生成调用点**：ped 2 / vehicle 2 / object 2 / pickup 0
- **过场**：`script@story@odr4@ig@ig1_john_protects_jack_p1@ig1_john_protects_jack_p1`；`script@story@odr4@ig@ig2_flee_through_door_p1@ig2_flee_through_door_p1`；`script@story@odr4@ig@ig3_leave_mansion_p1@ig3_leave_mansion_p1`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×401、ENTITY::IS_ENTITY_DEAD ×199、BUILTIN::TO_FLOAT ×160、PLAYER::GET_PLAYER_INDEX ×156、MISC::GET_HASH_KEY ×142

#### 12. 帮修士一把 `RCLDN1`

- 脚本：`rcm_calderon1.c`（弱匹配，72,374 行 / 2,324 个函数）
- **生成调用点**：ped 1 / vehicle 0 / object 14 / pickup 0
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×345、ENTITY::IS_ENTITY_DEAD ×183、PLAYER::GET_PLAYER_INDEX ×175、MISC::GET_HASH_KEY ×152、MISC::IS_BIT_SET ×143

#### 13. 修士修女一家亲 `RCLDN2`

- 脚本：`rcm_calderon2.c`（弱匹配，69,426 行 / 2,253 个函数）
- **生成调用点**：ped 1 / vehicle 0 / object 26 / pickup 0
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×382、ENTITY::IS_ENTITY_DEAD ×209、PLAYER::GET_PLAYER_INDEX ×177、MISC::IS_BIT_SET ×152、MISC::GET_HASH_KEY ×149

#### 14. 美国父亲：第 2 部分 `RNATV2`

- 脚本：`rcm_native2.c`（强匹配，76,120 行 / 2,485 个函数）
- **目标（脚本顺序）**
  1. 返回飞鹰处。
  2. 打开
  3. 潜入工厂。
  4. 进入工厂。
  5. 潜行到楼上。
  6. 前往楼上。
  7. 潜入办公室。
  8. 进入办公室。
  9. 审问丹伯里。
  10. 等待丹伯里拿出文件。
  11. 拿取文件。
  12. 跳出窗户逃离办公室。
  - …（另有 5 条）
- **失败条件**：飞鹰死了。；飞鹰的马死了。；您的马死了。；丹伯里死了。；离工厂太远了。
- **生成调用点**：ped 1 / vehicle 1 / object 15 / pickup 0
- **过场**：`script@Story@NTS_RSC@WagonRide`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×262、ENTITY::IS_ENTITY_DEAD ×162、MISC::GET_HASH_KEY ×150、BUILTIN::TO_FLOAT ×143、PLAYER::GET_PLAYER_INDEX ×142

#### 15. 曾经的梦想：第 2 部分 `MRY3`

- 脚本：`mary3.c`（强匹配，90,979 行 / 2,491 个函数）
- **目标（脚本顺序）**
  1. 跟随玛丽。
  2. 跟随吉利斯先生。
  3. 进入驾驶座。
  4. 追上那马车。
  5. 追上买家。
  6. 驾车前往一处隐蔽的地方。
  7. 前往马厩。
  8. 在马厩与玛丽见面。
  9. 停下马车。
  10. 跳上马车。
  11. 登上马车。
  12. 从买家处获得玛丽的胸针。
  - …（另有 4 条）
- **失败条件**：玛丽死了。；警察被惊动了。；玛丽被抛弃了。；您杀死了吉利斯先生。；您杀死了买家。；您杀死了一名车夫。
- **生成调用点**：ped 2 / vehicle 5 / object 1 / pickup 0
- **过场**：`script@story@mry3@leadin@mcs1@leadin_p1`；`script@story@mry3@leadin@mcs1@leadin_p2`；`script@story@mry3@leadout@mcs1@mary_lets_follow`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×275、ENTITY::IS_ENTITY_DEAD ×191、PLAYER::GET_PLAYER_INDEX ×176、BUILTIN::TO_FLOAT ×146、MISC::GET_HASH_KEY ×143

### 2.5 第五章 · 瓜玛

#### 1. 欢迎来到新世界 `GUA2`

- 脚本：`guama2.c`（强匹配，87,286 行 / 2,507 个函数）
- **目标（脚本顺序）**
  1. 在海岸上搜寻幸存者。
  2. 和苦役犯一起走。
  3. 返回帮派处。
  4. 解决守卫。
  5. 解决剩余守卫。
  6. 跟帮派待在一起。
- **失败条件**：离搜索区域太远了。；帮派成员被抛弃了。
- **生成调用点**：ped 2 / vehicle 0 / object 8 / pickup 1
- **过场**：`script@story@GUA1@LEADOUT@EXT@LEADOUT_facedown`；`script@story@GUA2@IG@IG7_ARTHUR_COLLAPSE@IG7_ARTHUR_COLLAPSE_01`；`script@story@GUA2@IG@IG7_ARTHUR_COLLAPSE@IG7_ARTHUR_COLLAPSE_02`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×261、ENTITY::IS_ENTITY_DEAD ×164、PLAYER::GET_PLAYER_INDEX ×157、BUILTIN::TO_FLOAT ×154、MISC::GET_HASH_KEY ×148

#### 2. 天堂渐行渐远 `GUA3`

- 脚本：`guama3.c`（强匹配，99,221 行 / 2,591 个函数）
- **目标（脚本顺序）**
  1. 悄无声息地解决守卫。
  2. 解决守卫并突出重围返回船上。
  3. 前往瞭望台。
  4. 解决守卫。
  5. 解决守卫。
  6. 安放炸药。
  7. 跟随达奇。
  8. 等待迈卡放置完炸药。
  9. 跟随帮派。
  10. 营救船长。
  11. 跟随帮派成员返回船上。
  12. 前往操作火炮。
  - …（另有 2 条）
- **失败条件**：达奇死了。；比尔死了。；迈卡死了。；赫尔克里死了。；船长死了。
- **生成调用点**：ped 2 / vehicle 3 / object 4 / pickup 0
- **过场**：`script@story@gua3@ig@ig1_artillery@ig1_artillery_micah`；`script@story@gua3@ig@ig1_artillery@ig1_artillery_player`；`script@story@gua3@ig@ig2_artillery_hercule@ig2_artillery_hercule`
- **高频 native**：PLAYER::PLAYER_PED_ID ×503、PED::SET_BLOCKING_OF_NON_TEMPORARY_EVENTS ×294、ENTITY::DOES_ENTITY_EXIST ×285、TASK::OPEN_SEQUENCE_TASK ×249、TASK::CLOSE_SEQUENCE_TASK ×249

#### 3. 善良又慈祥的暴君 `FUS1`

- 脚本：`fussar1.c`（强匹配，97,564 行 / 2,673 个函数）
- **目标（脚本顺序）**
  1. 跟随达奇。
  2. 跟随格洛丽亚通过洞穴。
  3. 返回格洛丽亚处。
  4. 与达奇一起抬起破烂的大门。
  5. 靠近达奇。
  6. 偷偷接近守卫。
  7. 杀掉右边的守卫。
  8. 抬起尸体。
  9. 将尸体扔到灌木丛里。
  10. 去掩护位置。
  11. 等待守卫离开。
  12. 解决左边的守卫。
  - …（另有 14 条）
- **失败条件**：格洛丽亚被抛弃了。；格洛丽亚死了。；福萨尔的守卫们被惊动了。
- **生成调用点**：ped 2 / vehicle 0 / object 13 / pickup 0
- **过场**：`script@story@FUS1@ig@IG21_MEN_PREP_REFINERY_EXPLOSION@IG21_MEN_PREP_REFINERY_EXPLOSION`；`script@story@fus1@ig@ig_1_cliffsidetraverse@ig1_clifftraverse_dutch`；`script@story@fus1@ig@ig_1_cliffsidetraverse@ig1_clifftraverse_arthur`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×361、ENTITY::IS_ENTITY_DEAD ×197、PLAYER::GET_PLAYER_INDEX ×160、BUILTIN::TO_FLOAT ×148、MISC::GET_HASH_KEY ×142

#### 4. 释放野蛮 `FUS2`

- 脚本：`fussar2.c`（强匹配，92,041 行 / 2,645 个函数）
- **目标（脚本顺序）**
  1. 跟随利昂。
  2. 抓住
  3. 射击绞绳并解放吊着的工人们。
  4. 杀死刽子手。
  5. 解决福萨尔的手下。
- **失败条件**：福萨尔的手下被惊动了。；利昂死了。；一名工人死了。
- **生成调用点**：ped 2 / vehicle 0 / object 19 / pickup 0
- **过场**：`script@story@FUS2@IG@FUS2_IG16_Interrogation@ig16_interrogation`；`script@story@FUS2@IG@FUS2_IG16_Interrogation_Struggle@ig16_Interrogation_Struggle`；`script@story@FUS2@IG@FUS2_IG16_Interrogation_Struggle@ig16_Leon_Baptiste_Loop`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×306、ENTITY::IS_ENTITY_DEAD ×197、PLAYER::GET_PLAYER_INDEX ×163、BUILTIN::TO_FLOAT ×153、MISC::GET_HASH_KEY ×147

#### 5. 地狱无怨 `SMG2`

- 脚本：`smuggler2.c`（强匹配，94,120 行 / 2,499 个函数）
- **目标（脚本顺序）**
  1. 掩护左边
  2. 掩护右边
  3. 返回堡垒的屋顶。
  4. 帮助赫尔克里将火炮推到合适的位置。
  5. 跟随赫尔克里和达奇。
  6. 返回赫尔克里和达奇处。
  7. 返回战斗。
  8. 返回堡垒的底部。
  9. 指示赫尔克里和达奇。
  10. 跟随赫尔克里。
  11. 返回赫尔克里处。
  12. 摧毁福萨尔的船。
- **失败条件**：赫尔克里和达奇被抛弃了。
- **生成调用点**：ped 2 / vehicle 6 / object 19 / pickup 4
- **过场**：`script@story@SMG2@LEADOUT@INT@leadout`；`script@story@SMG2@IG@IG2_Bill_Sees_Incoming_Men@IG2_Bill_Sees_Incoming_Men`；`script@story@smg2@ig@ig3_cannon@ig3_cannon_p1_hercule`
- **高频 native**：ENTITY::IS_ENTITY_DEAD ×269、ENTITY::DOES_ENTITY_EXIST ×258、PLAYER::GET_PLAYER_INDEX ×154、BUILTIN::TO_FLOAT ×153、MISC::GET_HASH_KEY ×141

#### 6. 快乐易逝 `GNG1`

- 脚本：`gang1.c`（强匹配，94,150 行 / 2,688 个函数）
- **目标（脚本顺序）**
  1. 躲避到门后面。
  2. 跟随莎迪和比尔。
  3. 保护拉凯不受平克顿侦探的攻击。
  4. 前往马克沁重机枪处。
  5. 跟随莎迪。
  6. 返回您的同伴处。
  7. 返回莎迪处。
  8. 杀死机枪手。
- **生成调用点**：ped 2 / vehicle 1 / object 19 / pickup 2
- **过场**：`script@story@gng1@ig@ig_1_escape_bunkie@ig_1_escape_bunkie`；`script@story@gng1@ig@ig_1_escape_bunkie@ig_1_escape_bunkie_mrs_alder`；`script@story@GNG1@Leadin@MCS1@Leadin`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×378、ENTITY::IS_ENTITY_DEAD ×192、PLAYER::GET_PLAYER_INDEX ×157、BUILTIN::TO_FLOAT ×147、MISC::GET_HASH_KEY ×141

#### 7. 莫弗里领地 `RDCH3`

- 脚本：`rcm_dutch31.c`（强匹配，91,200 行 / 2,622 个函数）
- **目标（脚本顺序）**
  1. 和我一起走
  2. 与查尔斯交谈。
  3. 前往布彻河村。
  4. 打开笼子
  5. 将炸药扔进山洞中。
  6. 打开笼子。
  7. 前往安尼斯堡。
  8. 返回女人处。
- **失败条件**：女人死了。；女人被抛弃了。
- **生成调用点**：ped 1 / vehicle 1 / object 2 / pickup 0
- **过场**：`script@story@dutch3@horse_ride`；`script@story@dutch3@returntobeavers`；`script@story@dutch3@mission_jump_cameras`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×374、PED::IS_PED_INJURED ×292、ENTITY::IS_ENTITY_DEAD ×276、PLAYER::PLAYER_ID ×181、MISC::GET_HASH_KEY ×158

#### 8. 人生的岔路口 `RDOPN`

- 脚本：`rcm_doctors_opinion1.c`（强匹配，67,229 行 / 2,217 个函数）
- **生成调用点**：ped 1 / vehicle 0 / object 5 / pickup 0
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×189、MISC::GET_HASH_KEY ×146、BUILTIN::TO_FLOAT ×139、PLAYER::GET_PLAYER_INDEX ×138、ENTITY::IS_ENTITY_DEAD ×125

#### 9. 亲爱的塔西佗叔叔 `RGNG02`

- 脚本：`rcm_gang02.c`（弱匹配，68,779 行 / 2,242 个函数）
- **生成调用点**：ped 1 / vehicle 0 / object 4 / pickup 0
- **过场**：`script@Story@GNG0@RideToShadyBell`；`script@Story@GNG0@RideToLakay`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×173、PLAYER::GET_PLAYER_INDEX ×156、ENTITY::IS_ENTITY_DEAD ×147、MISC::GET_HASH_KEY ×147、BUILTIN::TO_FLOAT ×139

### 2.6 第六章 · 河狸岩洞

#### 1. 再见了，亲爱的朋友 `DST5`

- 脚本：`odriscolls5.c`（弱匹配，96,123 行 / 2,710 个函数）
- **目标（脚本顺序）**
  1. 跟随达奇。
  2. 与达奇一起跟随奥德里斯科帮成员。
  3. 想办法到达屋顶。
  4. 返回枪手的位置。
  5. 靠近枪手所在位置。
  6. 解决枪手。
  7. 拾取步枪并观看行刑。
  8. 干掉奥德里斯科帮成员来为达奇和莎迪开路。
  9. 返回达奇处。
- **失败条件**：警察被惊动了。
- **生成调用点**：ped 2 / vehicle 1 / object 19 / pickup 1
- **过场**：`script@story@dst5@ig@ig_1_CrowdWaits@ig_1_CrowdWaits`；`script@story@dst5@ig@ig_2_CrowdExits@ig_2_CrowdExits`；`script@story@dst5@ig@ig_2_CrowdExits@ig_2_CrowdExits_PostMCS3`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×338、ENTITY::IS_ENTITY_DEAD ×241、PLAYER::GET_PLAYER_INDEX ×157、BUILTIN::TO_FLOAT ×152、MISC::GET_HASH_KEY ×143

#### 2. 睦邻友好 `TRN1`

- 脚本：`train_robbery1.c`（强匹配，93,735 行 / 2,527 个函数）
- **目标（脚本顺序）**
  1. 跟随达奇。
  2. 返回达奇处。
  3. 释放马匹以逃跑。
  4. 和达奇以及迈卡一起摆脱追捕者。
- **失败条件**：帮派成员被抛弃了。；守卫被惊动了。；逃跑用的马死了。
- **生成调用点**：ped 2 / vehicle 2 / object 9 / pickup 0
- **过场**：`script@story@TRN1@IG@TRN1_WALK_AND_TALK@TRN1_WALK_AND_TALK`；`script@story@trn1@ig@ig1_micah_got_papers@ig1_micah_got_papers`；`script@story@trn1@leadin@mcs2@horse_fiddle`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×279、ENTITY::IS_ENTITY_DEAD ×213、PLAYER::GET_PLAYER_INDEX ×159、ENTITY::GET_ENTITY_COORDS ×150、BUILTIN::TO_FLOAT ×144

#### 3. 范霍恩的喜悦 `TRN2`

- 脚本：`train_robbery2.c`（强匹配，92,643 行 / 2,561 个函数）
- **目标（脚本顺序）**
  1. 跟随比尔前往伏击地点。
  2. 到达伏击位置。
  3. 前往会面地点。
  4. 等待比尔进攻。
  5. 干掉马车警卫。
  6. 返回位置。
  7. 干掉警察。
- **失败条件**：车队被惊动了。；巡逻队被惊动了。；比尔死了。
- **生成调用点**：ped 2 / vehicle 1 / object 4 / pickup 0
- **过场**：`script@story@trn2@ig1_bill_passed_out@ig1_bill_passed_out`；`script@story@trn2@ig1_bill_passed_out@ig1_bill_passed_out_wagon`；`script@story@trn2@ig1_law_spotted@ig1_law_spotted`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×309、ENTITY::IS_ENTITY_DEAD ×218、PLAYER::GET_PLAYER_INDEX ×168、BUILTIN::TO_FLOAT ×144、MISC::GET_HASH_KEY ×142

#### 4. 绝路桥 `TRN3`

- 脚本：`train_robbery3.c`（强匹配，85,875 行 / 2,402 个函数）
- **目标（脚本顺序）**
  1. 引爆
  2. 移动人力轨道车。
  3. 拿第一个炸药箱。
  4. 从桥边把炸药箱送下去。
  5. 爬下梯子。
  6. 爬下去并拾取一些炸药。
  7. 将炸药安放在柱子上。
  8. 安放剩下的炸药。
  9. 返回人力轨道车处。
  10. 避开迎面而来的火车。
  11. 跟随约翰。
  12. 使用起爆器。
- **失败条件**：马车已无法驾驶。；约翰死了。
- **生成调用点**：ped 1 / vehicle 1 / object 14 / pickup 0
- **过场**：`script@Story@trn3@gameover`；`script@story@trn3@IG@IG_1_PullLever`；`script@story@trn3@IG@IG_9_Detonate`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×299、ENTITY::IS_ENTITY_DEAD ×177、PLAYER::GET_PLAYER_INDEX ×155、BUILTIN::TO_FLOAT ×144、MISC::GET_HASH_KEY ×141

#### 5. 最真实的自己 `TRN4`

- 脚本：`train_robbery4.c`（强匹配，105,520 行 / 2,711 个函数）
- **目标（脚本顺序）**
  1. 跟随约翰前往马车处。
  2. 跟随达奇前往圣丹尼斯。
  3. 帮派的伪装被人识破了。
  4. 跳上马背
  5. 进入装甲车厢。
  6. 跟随约翰返回帮派成员处。
  7. 跟随达奇前往圣丹尼斯。
- **生成调用点**：ped 2 / vehicle 9 / object 9 / pickup 0
- **过场**：`script@story@trn4@ig@ig14_arthur_collects_dynamite@ig14_arthur_collects_dynamite`；`script@story@trn4@ig@ig15_gang_waits_cme@ig15_gang_waits_cme_dutch`；`script@story@trn4@scripted_cs_land_on_train`
- **高频 native**：PLAYER::PLAYER_PED_ID ×628、ENTITY::DOES_ENTITY_EXIST ×395、ENTITY::GET_OFFSET_FROM_ENTITY_IN_WORLD_COORDS ×314、PED::SET_PED_CONFIG_FLAG ×260、PED::FORCE_PED_AI_AND_ANIMATION_UPDATE ×227

#### 6. 考古学入门 `NTV1`

- 脚本：`native1.c`（强匹配，100,283 行 / 2,818 个函数）
- **目标（脚本顺序）**
  1. 跟随落雨。
  2. 返回落雨处。
  3. 前往营地。
  4. 帮助
  5. 返回军营。
  6. 离开该区域。
  7. 检查
- **失败条件**：落雨被抛弃了。；落雨和神圣烟斗被抛弃了。；您杀死了门罗上尉。；离军营太远了。；已无法抵达圣物处。；落雨的马死了。
- **生成调用点**：ped 2 / vehicle 0 / object 13 / pickup 0
- **过场**：`script@story@ntv1@ig@IG2_RF_Investigates@IG2_obj_loop`；`script@story@ntv1@ig@IG2_RF_Investigates@IG2_RF_Investigates`；`script@story@ntv1@ig@IG3_Arthur_Investigates@ig3_arthur_investigates`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×369、PLAYER::GET_PLAYER_INDEX ×276、ENTITY::IS_ENTITY_DEAD ×236、MISC::IS_STRING_NULL_OR_EMPTY ×149、MISC::GET_HASH_KEY ×147

#### 7. 对话的艺术 `NTV2`

- 脚本：`native2.c`（强匹配，94,480 行 / 2,637 个函数）
- **目标（脚本顺序）**
  1. 跟随落雨。
  2. 骑上您的马。
  3. 跟随查尔斯。
  4. 参与会面。
  5. 参加会面。
  6. 退回到您的马处。
  7. 与查尔斯一起逃跑。
  8. 等待门罗上尉骑上您的马。
  9. 和门罗上尉一起逃跑。
  10. 骑上您的马逃跑。
  11. 保护门罗上尉。
  12. 返回门罗上尉处。
- **失败条件**：您的马死了。；会面失败了。；门罗上尉被抛弃了。
- **生成调用点**：ped 2 / vehicle 1 / object 6 / pickup 0
- **过场**：`script@story@ntv2@ig@ig1_arrive_at_talk@ig1_arrive_at_talk`；`script@story@NTV2@IG@ig2_arthur_peeking@ig2_arthur_peeking`；`script@story@NTV2@IG@ig2_arthur_peeking_guards@ig2_arthur_peeking_guards`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×408、ENTITY::IS_ENTITY_DEAD ×265、PLAYER::GET_PLAYER_INDEX ×166、PED::SET_PED_CONFIG_FLAG ×154、BUILTIN::TO_FLOAT ×148

#### 8. 我最后的孩子 `NTV3`

- 脚本：`native3.c`（强匹配，112,732 行 / 2,661 个函数）
- **目标（脚本顺序）**
  1. 前往达奇处。
  2. 搜刮办公室。
  3. 前往瓦匹缇。
- **生成调用点**：ped 2 / vehicle 1 / object 5 / pickup 0
- **过场**：`script@story@ntv3@oil_fire`；`script@story@ntv3@ig17_injured_native_rider_cme1@ig17_injured_native_rider_cme1`；`script@story@ntv3@ig_ridingtocornwall@ig_ridingtocornwall`
- **高频 native**：PED::IS_PED_INJURED ×774、ENTITY::DOES_ENTITY_EXIST ×567、PED::SET_BLOCKING_OF_NON_TEMPORARY_EVENTS ×544、PED::SET_PED_COMBAT_ATTRIBUTES ×424、ENTITY::IS_ENTITY_DEAD ×339

#### 9. 释放愤怒 `NTS1`

- 脚本：`native_son1.c`（强匹配，94,900 行 / 2,623 个函数）
- **目标（脚本顺序）**
  1. 跟随飞鹰。
  2. 返回独木舟。
  3. 帮助落雨
  4. 放置炸药
  5. 抓住并骑上三匹马其中的一匹。
- **失败条件**：守卫被惊动了。；印第安人的马逃走了。
- **生成调用点**：ped 2 / vehicle 2 / object 15 / pickup 0
- **过场**：`script@story@nts1@leadin@mcs1@leadin`；`script@story@nts1@ig@ig1_dutch_charles_in_canoe@ig_1_dutch_charles_in_canoe`；`script@story@nts1@ig@ig3_boat_guard_card_game@ig_3_boat_guard_card_game`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×307、ENTITY::IS_ENTITY_DEAD ×223、PLAYER::GET_PLAYER_INDEX ×160、PED::SET_PED_CONFIG_FLAG ×147、BUILTIN::TO_FLOAT ×147

#### 10. 最爱的孩子们 `NTS2`

- 脚本：`native_son2.c`（强匹配，96,417 行 / 2,853 个函数）
- **目标（脚本顺序）**
  1. 引爆
  2. 返回帮派成员处。
- **失败条件**：帮派成员被抛弃了。；您死了。；飞鹰被抛弃了。；达奇被抛弃了。
- **生成调用点**：ped 2 / vehicle 2 / object 12 / pickup 0
- **过场**：`script@story@NTS2@IG@IG_SPOOL@IG_SPOOL`；`script@story@NTS2@IG@IG0_WALK_AND_TALK@IG0_WALK_AND_TALK`；`script@story@NTS2@IG@IG3_SIGNAL@IG3_SIGNAL`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×322、PLAYER::GET_PLAYER_INDEX ×193、ENTITY::IS_ENTITY_DEAD ×189、PED::SET_PED_CONFIG_FLAG ×153、BUILTIN::TO_FLOAT ×150

#### 11. 国王之子 `NTS3`

- 脚本：`native_son3.c`（强匹配，113,673 行 / 3,134 个函数）
- **目标（脚本顺序）**
  1. 跟随查尔斯。
  2. 与落雨交谈。
  3. 骑上您的马。
  4. 趟过河。
  5. 干掉守卫。
  6. 悄悄杀死守卫。
  7. 解决任意一名守卫。
  8. 爬上塔楼。
  9. 前往走道。
  10. 无声地射掉灯。
  11. 在守卫身上搜寻钥匙。
  12. 打开监狱门。
  - …（另有 11 条）
- **失败条件**：您的马死了。；离河岸太远了。；守卫被惊动了。；毁掉的灯离物资太远了。
- **生成调用点**：ped 2 / vehicle 3 / object 17 / pickup 0
- **过场**：`script@story@nts3@ig@ig0_charles_intro_wnt@ig0_charles_wnt`；`script@story@nts3@leadin@int@leadin`；`script@story@NTS3@IG@IG2_Crouch_Wave_Behind@ig2_crouch_wave_behind`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×524、ENTITY::IS_ENTITY_DEAD ×275、PED::SET_PED_CONFIG_FLAG ×183、PLAYER::GET_PLAYER_INDEX ×166、BUILTIN::TO_FLOAT ×159

#### 12. 伊卡洛斯和朋友们 `GNG2`

- 脚本：`gang2.c`（强匹配，103,798 行 / 2,993 个函数）
- **目标（脚本顺序）**
  1. 跟随莎迪。
  2. 骑上您的马。
  3. 使用 将热气球上升到所需的高度。
  4. 飞向西西卡监狱。
  5. 下降至西西卡监狱。
  6. 使用望远镜。
  7. 使用望远镜在田地里搜寻约翰。
  8. 放大镜头将视线聚焦到囚犯身上。
  9. 使用双筒望远镜辨认囚犯。
  10. 逃脱警察追捕。
  11. 解决正在追击的奥德里斯科帮成员。
  12. 使用绳索拉起莎迪。
  - …（另有 5 条）
- **失败条件**：守卫被惊动了。；莎迪被抛弃了。；莎迪的马死了。
- **生成调用点**：ped 2 / vehicle 2 / object 14 / pickup 0
- **过场**：`script@story@gng2@leadin@mcs1@balloonoperator`；`script@story@GNG2@IG@INT_WalknTalk@INT_WalknTalk`；`script@story@gng2@leadout@mcs1@operator`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×373、ENTITY::IS_ENTITY_DEAD ×221、BUILTIN::TO_FLOAT ×174、PLAYER::GET_PLAYER_INDEX ×164、MISC::GET_HASH_KEY ×147

#### 13. 探监记 `GNG3`

- 脚本：`gang3.c`（强匹配，103,126 行 / 2,960 个函数）
- **目标（脚本顺序）**
  1. 返回莎迪处。
  2. 寻找约翰。
  3. 拾起步枪。
  4. 搜查那片田地。
  5. 靠近监狱。
  6. 击退攻击者。
  7. 划船前往西西卡岛。
  8. 前往瞭望塔。
  9. 解决守卫。
  10. 干掉守卫。
  11. 追上莎迪。
  12. 将莎迪与约翰护送至船处。
  - …（另有 4 条）
- **失败条件**：莎迪被抛弃了。；守卫被惊动了。；您杀死了可能的人质。；您的马死了。
- **生成调用点**：ped 2 / vehicle 1 / object 11 / pickup 1
- **过场**：`script@story@GNG3@IG@IG_1_SadieIdles@Sadie_Idles`；`script@story@GNG3@IG@IG_2_Landing_Boat@Land_Boat`；`script@story@GNG3@IG@IG_4_Prison_Work@Prison_Work`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×424、ENTITY::IS_ENTITY_DEAD ×246、PLAYER::GET_PLAYER_INDEX ×163、PED::SET_PED_CONFIG_FLAG ×157、BUILTIN::TO_FLOAT ×151

#### 14. 血仇、血债、血偿 `FIN1`

- 脚本：`finale1.c`（强匹配，113,525 行 / 3,046 个函数）
- **目标（脚本顺序）**
  1. 骑马
  2. 回去拿钱
  3. 跟随莎迪安全到达范霍恩。
  4. 前往灯塔顶部。
  5. 掩护莎迪。
  6. 前往码头。
  7. 前往马处。
  8. 返回河狸岩洞。
  9. 击退平克顿侦探。
  10. 和约翰一起逃脱。
  11. 解决平克顿侦探。
  12. 突出重围前往河狸岩洞。
  - …（另有 16 条）
- **失败条件**：平克顿侦探被惊动了。；莎迪和艾比盖尔被抛弃了。；一匹用于逃离的马死了。；您离河狸岩洞太远了。；离钱太远了。
- **生成调用点**：ped 2 / vehicle 3 / object 29 / pickup 0
- **过场**：`script@story@fin1@ig@ig1_sadie_dragged_inside@ig1_sadie_dragged_inside`；`script@story@fin1@ig@ig2_kill_pinkertons@ig2_kill_pinkertons_women_idle`；`script@story@fin1@ig@ig2_kill_pinkertons@ig2_kill_pinkertons_men_idle`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×493、ENTITY::IS_ENTITY_DEAD ×387、PED::SET_BLOCKING_OF_NON_TEMPORARY_EVENTS ×209、PED::SET_PED_CONFIG_FLAG ×175、PLAYER::GET_PLAYER_INDEX ×167

#### 15. 盗亦有道 `RMNR1`

- 脚本：`rcm_monroe11.c`（强匹配，75,659 行 / 2,439 个函数）
- **目标（脚本顺序）**
  1. 跟随门罗上尉。
  2. 返回门罗上尉处。
  3. 返回马车处。
  4. 从物资马车处夺回药品。
  5. 将药品带回给门罗上尉。
  6. 守卫
- **失败条件**：门罗上尉被抛弃了。；门罗上尉死了。；离马车太远了。；您的马死了。；门罗上尉的马死了。
- **生成调用点**：ped 1 / vehicle 1 / object 1 / pickup 0
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×291、ENTITY::IS_ENTITY_DEAD ×242、MISC::IS_BIT_SET ×153、PLAYER::GET_PLAYER_INDEX ×150、MISC::GET_HASH_KEY ×149

#### 16. 毋须宽恕：第 1 部分 `REDW21`

- 脚本：`rcm_edith_down21.c`（弱匹配，65,470 行 / 2,158 个函数）
- **生成调用点**：ped 1 / vehicle 0 / object 2 / pickup 0
- **过场**：`script@story@mud2@ig@ig_15@fight_crowd@male_civ_17`；`script@story@mud2@ig@ig_15@fight_crowd@male_civ_18`；`script@story@mud2@ig@ig_15@fight_crowd@male_civ_11`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×195、ENTITY::IS_ENTITY_DEAD ×165、MISC::GET_HASH_KEY ×148、MISC::IS_BIT_SET ×144、PLAYER::GET_PLAYER_INDEX ×142

#### 17. 毋须宽恕：第 2 部分 `REDW22`

- 脚本：`rcm_edith_down22.c`（弱匹配，67,399 行 / 2,214 个函数）
- **生成调用点**：ped 1 / vehicle 0 / object 0 / pickup 0
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×211、ENTITY::IS_ENTITY_DEAD ×156、MISC::GET_HASH_KEY ×149、PLAYER::GET_PLAYER_INDEX ×142、BUILTIN::TO_FLOAT ×137

#### 18. 寡妇莎迪·阿德勒：第 2 部分 `RDST62`

- 脚本：`rcm_dusters62.c`（强匹配，74,184 行 / 2,311 个函数）
- **目标（脚本顺序）**
  1. 前往莎迪处。
- **生成调用点**：ped 1 / vehicle 0 / object 2 / pickup 1
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×258、ENTITY::IS_ENTITY_DEAD ×176、PED::IS_PED_INJURED ×151、MISC::GET_HASH_KEY ×150、PED::SET_PED_CONFIG_FLAG ×143

#### 19. 真爱之路：第 5 部分 `RBNP21`

- 脚本：`rcm_beau_and_penelope21.c`（弱匹配，79,764 行 / 2,537 个函数）
- **目标（脚本顺序）**
  1. 前往罗兹车站。
  2. 与鲍见面。
  3. 与鲍和佩内洛普见面。
  4. 返回鲍和佩内洛普处。
  5. 返回佩内洛普处。
  6. 追上火车。
- **失败条件**：火车司机死了。；警察被惊动了。；佩内洛普被抛弃了。；鲍和佩内洛普被抛弃了。；鲍死了。；佩内洛普死了。
- **生成调用点**：ped 1 / vehicle 1 / object 13 / pickup 0
- **过场**：`script@Story@RBNP12@TrainRideEscape`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×281、ENTITY::IS_ENTITY_DEAD ×237、BUILTIN::TO_FLOAT ×152、MISC::GET_HASH_KEY ×149、MISC::IS_BIT_SET ×145

### 2.7 尾声上 · 叉角羚牧场

#### 1. 天“轮”之乐 `MAR1`

- 脚本：`marston1.c`（强匹配，95,603 行 / 2,755 个函数）
- **目标（脚本顺序）**
  1. 前往草莓镇。
  2. 与店主交谈。
  3. 返回草莓镇。
  4. 与艾比盖尔在诊所见面。
  5. 返回您的马车处。
  6. 将货物运到叉角羚牧场。
  7. 夺回被偷的马车。
  8. 将马车带回叉角羚牧场。
  9. 追上被偷的马车。
- **失败条件**：您的家人被抛弃在草莓镇了。；您犯法了。；马车已无法驾驶。；您杀死了店主。；您杀死了一名店员。；安格斯·格迪斯死了。
- **生成调用点**：ped 2 / vehicle 1 / object 1 / pickup 0
- **过场**：`script@story@MAR1@IG@IG_3_StoreActivity@IG_3_Base_Owner`；`script@story@MAR1@IG@IG_3_StoreActivity@IG_3_CarryOut_Folk01`；`script@story@MAR1@IG@IG_3_StoreActivity@IG_3_CarryOut_Folk02`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×302、PLAYER::GET_PLAYER_INDEX ×209、ENTITY::IS_ENTITY_DEAD ×187、BUILTIN::TO_FLOAT ×152、MISC::GET_HASH_KEY ×146

#### 2. 简单的快乐 `MAR5`

- 脚本：`marston5_3.c`（强匹配，88,807 行 / 2,557 个函数）
- **生成调用点**：ped 2 / vehicle 0 / object 6 / pickup 0
- **过场**：`script@story@mar5@ig@s3_ig1@s3_ig1_meet_duncan_wnt`；`script@story@mar5@ig@s3_ig4@s3_ig4_john_help`；`script@story@mar53@racefinish`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×277、ENTITY::IS_ENTITY_DEAD ×208、PLAYER::GET_PLAYER_INDEX ×169、MISC::GET_HASH_KEY ×149、BUILTIN::TO_FLOAT ×147

#### 3. 傻人为父 `MAR2`

- 脚本：`marston2.c`（强匹配，95,903 行 / 2,755 个函数）
- **目标（脚本顺序）**
  1. 驾驶马车前往草莓镇。
  2. 将马车停在邮局旁。
  3. 取回邮件。
  4. 和杰克一同驾车前往叉角羚牧场。
  5. 驾驶马车前往叉角羚牧场。
  6. 返回杰克处。
  7. 将马车停进叉角羚牧场里。
- **生成调用点**：ped 2 / vehicle 2 / object 1 / pickup 0
- **过场**：`script@story@MAR2@leadout@int@leadout`；`script@story@MAR2@IG@IG_2_GiveJackReins@IG_2_GiveJackReins`；`script@story@MAR2@IG@IG_3_JohnExitWagon@IG_3_JohnExitWagon`
- **高频 native**：ENTITY::IS_ENTITY_DEAD ×364、ENTITY::DOES_ENTITY_EXIST ×268、PLAYER::GET_PLAYER_INDEX ×165、BUILTIN::TO_FLOAT ×153、MISC::GET_HASH_KEY ×143

#### 4. 务农入门 `MR52`

- 脚本：`marston5_2.c`（强匹配，87,401 行 / 2,551 个函数）
- **目标（脚本顺序）**
  1. 修理围栏。
  2. 竖起木桩。
  3. 钉上竖杆。
  4. 选择位置并放置横杆。
  5. 调查畜栏处的骚动。
  6. 抓住公牛。
  7. 安抚公牛。
  8. 将公牛带回畜棚。
  9. 返回畜栏。
  10. 返回公牛处。
- **失败条件**：狄更斯被抛弃了。
- **生成调用点**：ped 2 / vehicle 0 / object 1 / pickup 0
- **过场**：`script@story@mar5@ig@52_ig1@ptl_build_fence`；`script@story@mar5@ig@s2_ig3@sg2_ig3_move_bull`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×215、ENTITY::IS_ENTITY_DEAD ×159、PLAYER::GET_PLAYER_INDEX ×155、BUILTIN::TO_FLOAT ×151、MISC::GET_HASH_KEY ×146

#### 5. 为父入门 `MR53`

- 脚本：`marston5_3.c`（强匹配，88,807 行 / 2,557 个函数）
- **目标（脚本顺序）**
  1. 返回叉角羚牧场。
  2. 跟随亚伯。
  3. 帮助邓肯。
  4. 牵着马。
  5. 将马带进畜栏。
  6. 领着邓肯在畜栏内骑马转转。
  7. 停止牵引邓肯。
  8. 看着邓肯。
  9. 帮助格迪斯夫人。
  10. 去屋子那跟艾比盖尔交谈。
  11. 跟杰克一起走向马。
  12. 帮助杰克上马。
  - …（另有 9 条）
- **失败条件**：邓肯死了。；您杀死了一名牧工。；您杀死了亚伯。；您杀死了格迪斯夫人。；杰里米亚死了。
- **生成调用点**：ped 2 / vehicle 0 / object 6 / pickup 0
- **过场**：`script@story@mar5@ig@s3_ig1@s3_ig1_meet_duncan_wnt`；`script@story@mar5@ig@s3_ig4@s3_ig4_john_help`；`script@story@mar53@racefinish`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×277、ENTITY::IS_ENTITY_DEAD ×208、PLAYER::GET_PLAYER_INDEX ×169、MISC::GET_HASH_KEY ×149、BUILTIN::TO_FLOAT ×147

#### 6. 吉姆·米尔顿重出江湖？ `MAR4`

- 脚本：`marston4.c`（强匹配，95,932 行 / 2,703 个函数）
- **目标（脚本顺序）**
  1. 返回叉角羚牧场。
  2. 保护汤姆。
  3. 找到汤姆·狄更斯。
  4. 骑马前往垂犬牧场。
  5. 返回垂犬牧场。
- **失败条件**：亚伯的马死了。；汤姆的马死了。；亚伯死了。；汤姆死了。；您杀死了自己的马。；您让拉雷米逃走了。
- **生成调用点**：ped 2 / vehicle 0 / object 18 / pickup 1
- **过场**：`script@story@mar4@ig@ig0_pronghornranchfire@ig0_pronghornranchfire`；`script@story@mar4@ig@ig1_dickensattacked@ig1_dickensattacked_choke`；`script@story@mar4@ig@ig2_leaderchallangesjohn@ig2_leaderchallangesjohn`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×350、ENTITY::IS_ENTITY_DEAD ×236、PLAYER::GET_PLAYER_INDEX ×163、PED::SET_PED_CONFIG_FLAG ×162、BUILTIN::TO_FLOAT ×148

#### 7. 老习惯 `LAR1`

- 脚本：`laramie1.c`（强匹配，81,788 行 / 2,351 个函数）
- **目标（脚本顺序）**
  1. 殴打拉雷米帮的成员。
  2. 调查骚乱。
- **失败条件**：亚伯死了。
- **生成调用点**：ped 2 / vehicle 0 / object 15 / pickup 0
- **过场**：`script@story@lar1@ig@ig_1_watchingfight@ig1_watchingfight_laramierider^1`；`script@story@lar1@ig@ig_1_watchingfight@ig1_watchingfight_laramierider^2`；`script@story@lar1@ig@ig_1_watchingfight@ig1_watchingfight_abe`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×235、ENTITY::IS_ENTITY_DEAD ×191、PLAYER::GET_PLAYER_INDEX ×153、BUILTIN::TO_FLOAT ×150、MISC::GET_HASH_KEY ×141

#### 8. 为母之道 `AB21`

- 脚本：`abigail2_1.c`（强匹配，86,180 行 / 2,534 个函数）
- **目标（脚本顺序）**
  1. 拿取电报。
  2. 与屋子里的艾比盖尔交谈。
  3. 打扫厩舍
  4. 回去工作。
  5. 抬起竖杆以建造栅栏。
  6. 建造栅栏。
  7. 前往格迪斯的房子。
- **失败条件**：亚伯死了。；狄更斯先生死了。；信使死了。
- **生成调用点**：ped 2 / vehicle 2 / object 2 / pickup 0
- **过场**：`script@story@rabi21@walkandtalk`；`script@story@rbch11@ride_to_blackwater2`；`script@story@rbch11@ride_to_valentine`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×257、ENTITY::IS_ENTITY_DEAD ×178、BUILTIN::TO_FLOAT ×158、PLAYER::GET_PLAYER_INDEX ×154、MISC::GET_HASH_KEY ×145

#### 9. 有偿工作 `SAD2`

- 脚本：`sadie2.c`（强匹配，92,823 行 / 2,563 个函数）
- **目标（脚本顺序）**
  1. 跟随莎迪前往草莓镇。
  2. 踢开门进入内森·柯克的房间。
  3. 追捕内森·柯克。
  4. 将内森·柯克放到莎迪的马上。
  5. 扛起内森·柯克。
  6. 从阳台上跳下去。
  7. 询问小镇上的人关于内森·柯克的信息。
  8. 进入接待中心。
  9. 询问区域内的人，找出内森·柯克的位置。
  10. 前往内森·柯克的房间。
  11. 进入内森·柯克的房间。
  12. 返回草莓镇。
- **失败条件**：警察被惊动了。；离草莓镇太远了。；内森·柯克逃走了。
- **生成调用点**：ped 2 / vehicle 1 / object 6 / pickup 0
- **过场**：`script@Story@SAD2@ride_to_strawberry`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×293、ENTITY::IS_ENTITY_DEAD ×203、PLAYER::GET_PLAYER_INDEX ×177、ANIMSCENE::DOES_ANIM_SCENE_EXIST ×164、MISC::GET_HASH_KEY ×147

#### 10. 乡绅的乐土？ `RBCH12`

- 脚本：`rcm_beechers12.c`（弱匹配，74,177 行 / 2,472 个函数）
- **生成调用点**：ped 1 / vehicle 0 / object 1 / pickup 0
- **过场**：`script@story@Beechers1_2@ReturnToBlackwater`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×220、ENTITY::IS_ENTITY_DEAD ×178、PLAYER::GET_PLAYER_INDEX ×152、MISC::GET_HASH_KEY ×150、BUILTIN::TO_FLOAT ×149

### 2.8 尾声下 · 比彻之愿

#### 1. 新耶路撒冷 `BE22`

- 脚本：`beechers2_2.c`（强匹配，88,176 行 / 2,422 个函数）
- **目标（脚本顺序）**
  1. 放置
- **生成调用点**：ped 2 / vehicle 1 / object 1 / pickup 0
- **过场**：`script@story@be22@ig@ig1_establishing_shot@ig1_establishing_shot`；`script@story@be22@ig@ig2_foundations@ig2_2_0_foundations`；`script@story@be22@ig@ig2_foundations@ig2_2_1_foundations`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×235、PLAYER::GET_PLAYER_INDEX ×153、BUILTIN::TO_FLOAT ×153、ENTITY::IS_ENTITY_DEAD ×143、MISC::GET_HASH_KEY ×139

#### 2. 家装入门 `RBCH21`

- 脚本：`rcm_beechers21.c`（弱匹配，64,107 行 / 2,074 个函数）
- **生成调用点**：ped 1 / vehicle 2 / object 1 / pickup 0
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×166、MISC::GET_HASH_KEY ×153、BUILTIN::TO_FLOAT ×137、PLAYER::GET_PLAYER_INDEX ×136、ENTITY::IS_ENTITY_DEAD ×126

#### 3. 工具盒 `MAR7`

- 脚本：`marston7.c`（强匹配，93,832 行 / 2,767 个函数）
- **失败条件**：窃贼逃走了。；查尔斯被抛弃了。；马车已无法驾驶。；马车已无法驾驶。；尼尔斯死了。；韦恩先生死了。
- **生成调用点**：ped 2 / vehicle 2 / object 30 / pickup 0
- **过场**：`script@story@mar7@ig@ig0_approach@ig0_approach_wayne`；`script@story@mar7@leadin@mcs1@leadin`；`script@story@mar7@leadin@mcs2@leadin`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×363、ENTITY::IS_ENTITY_DEAD ×184、PLAYER::GET_PLAYER_INDEX ×175、MISC::GET_HASH_KEY ×147、BUILTIN::TO_FLOAT ×147

#### 4. 不打不重逢 `MAR6`

- 脚本：`marston6.c`（强匹配，95,312 行 / 2,726 个函数）
- **目标（脚本顺序）**
  1. 返回大叔处。
  2. 跟随大叔。
  3. 等待大叔。
  4. 在酒馆或者黑市打听查尔斯的下落。
  5. 在圣萨杜奈恩斯寻找查尔斯。
  6. 在圣萨杜奈恩斯寻找查尔斯。
  7. 观看搏斗。
  8. 跟随查尔斯前往码头。
  9. 返回查尔斯处。
  10. 干掉马特利的人。
  11. 与查尔斯一起登上马车。
  12. 与大叔会合。
  - …（另有 3 条）
- **失败条件**：大叔的马死了。；大叔被抛弃了。；查尔斯被抛弃了。
- **生成调用点**：ped 2 / vehicle 5 / object 7 / pickup 0
- **过场**：`script@story@MAR6@Bink@Mar6_Train`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×342、ENTITY::IS_ENTITY_DEAD ×248、PLAYER::GET_PLAYER_INDEX ×181、PED::SET_PED_CONFIG_FLAG ×153、BUILTIN::TO_FLOAT ×148

#### 5. 大叔的倒霉日 `MAR8`

- 脚本：`marston8.c`（强匹配，94,363 行 / 2,631 个函数）
- **目标（脚本顺序）**
  1. 跟随查尔斯。
  2. 杀死巡逻队或放行。
  3. 跟随马车车夫。
  4. 爬上高处。
  5. 护送大叔和查尔斯。
  6. 护送大叔和查尔斯离开营地。
  7. 护送大叔和查尔斯回到比彻之愿。
- **失败条件**：剥皮帮被惊动了。；发现一个死了的剥皮帮成员。；查尔斯死了。；大叔死了。
- **生成调用点**：ped 2 / vehicle 1 / object 24 / pickup 0
- **过场**：`script@story@mar8@leadout@mcs2@deadeye`；`script@story@mar8@ig@ig2_dismount@ig2_dismount_charles`；`script@story@fus2@ig@fus2_ig30_hanging_help@fus2_ig30_hanging_help`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×429、ENTITY::IS_ENTITY_DEAD ×227、PLAYER::GET_PLAYER_INDEX ×178、BUILTIN::TO_FLOAT ×147、MISC::GET_HASH_KEY ×144

#### 6. 重新开始 `RJCK2`

- 脚本：`rcm_jack2.c`（强匹配，72,009 行 / 2,372 个函数）
- **目标（脚本顺序）**
  1. 与杰克一起前往河边。
  2. 与杰克一起钓鱼。
  3. 寻找鲁弗斯。
  4. 寻找鲁弗斯。
  5. 寻找杰克。
  6. 帮助鲁弗斯。
- **失败条件**：鲁弗斯死了。；杰克被吓坏了。
- **生成调用点**：ped 1 / vehicle 0 / object 3 / pickup 0
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×191、PLAYER::GET_PLAYER_INDEX ×149、ENTITY::IS_ENTITY_DEAD ×148、MISC::GET_HASH_KEY ×147、BUILTIN::TO_FLOAT ×137

#### 7. 勾画未来 `RABI3`

- 脚本：`rcm_abigail31.c`（强匹配，76,491 行 / 2,423 个函数）
- **目标（脚本顺序）**
  1. 前往黑水镇。
  2. 前往照相馆。
  3. 前往帝国剧院。
  4. 前往岸边。
  5. 离开
- **失败条件**：杰克被吓坏了。；艾比盖尔死了。；艾比盖尔被抛弃了。；您划得太远了。；摄影师死了。；马车已无法驾驶。
- **生成调用点**：ped 1 / vehicle 2 / object 9 / pickup 0
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×226、PLAYER::GET_PLAYER_INDEX ×161、MISC::GET_HASH_KEY ×151、ENTITY::IS_ENTITY_DEAD ×147、BUILTIN::TO_FLOAT ×141

#### 8. 相助老友 `SAD3`

- 脚本：`sadie3.c`（强匹配，99,576 行 / 2,725 个函数）
- **目标（脚本顺序）**
  1. 与木材销售员交谈。
  2. 将雷蒙·科特斯放到马上。
  3. 骑上您的马。
  4. 骑马前往幻彩天空。
  5. 调查畜棚。
  6. 掩护莎迪。
  7. 干掉帮派成员。
  8. 追上雷蒙·科特斯。
  9. 骑马前往黑水镇的木材厂。
  10. 追杀攻击者。
  11. 与莎迪会合。
  12. 返回莎迪处。
- **失败条件**：雷蒙·科特斯逃走了。；莎迪被抛弃了。；警察被惊动了。；您杀死了雷蒙·科特斯。；您被杀死了。；警长死了。
- **生成调用点**：ped 2 / vehicle 3 / object 1 / pickup 0
- **过场**：`script@Story@SAD3@ReturnToBeechers`；`script@Story@SAD3@ride_to_sheriff`；`script@story@sad3@ig@ig1_sadie_house@ig1_sadie_house`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×371、ENTITY::IS_ENTITY_DEAD ×233、PLAYER::GET_PLAYER_INDEX ×177、PED::SET_PED_CONFIG_FLAG ×160、MISC::GET_HASH_KEY ×150

#### 9. 超级大野兽 `SAD4`

- 脚本：`sadie4.c`（强匹配，86,995 行 / 2,486 个函数）
- **目标（脚本顺序）**
  1. 跟随莎迪。
  2. 和莎迪一起前往尸体处。
  3. 与莎迪待在一起。
  4. 跟随莎迪。
  5. 找到踪迹。
  6. 跟随踪迹。
  7. 杀死熊。
  8. 护送莎迪到黑水镇。
  9. 与赏金猎人谈话。
  10. 保护莎迪。
- **失败条件**：莎迪的马死了。
- **生成调用点**：ped 2 / vehicle 0 / object 11 / pickup 0
- **过场**：`script@story@sad4@leadin@int@base`；`script@story@sad4@leadin@int@front`；`script@story@sad4@leadin@int@back`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×271、ENTITY::IS_ENTITY_DEAD ×208、PLAYER::GET_PLAYER_INDEX ×157、PLAYER::PLAYER_ID ×150、BUILTIN::TO_FLOAT ×146

#### 10. 勤恳劳作的一天 `SAD5`

- 脚本：`sadie5.c`（强匹配，92,727 行 / 2,618 个函数）
- **目标（脚本顺序）**
  1. 骑上您的马。
  2. 跟随莎迪。
  3. 使用双筒望远镜或带瞄准镜的武器观察犰狳镇。
  4. 扛起谢恩·芬利。
  5. 将谢恩·芬利放入牢房。
  6. 观察马队。
  7. 对付兰斯顿的手下。
  8. 将谢恩·芬利放到马上。
  9. 做出您的决定。
  10. 潜行杀死守卫。
  11. 在山脊上掩护莎迪。
- **失败条件**：与莎迪一起逃走。；帮众被惊动了。；马队被惊动了。
- **生成调用点**：ped 2 / vehicle 0 / object 0 / pickup 0
- **过场**：`script@story@sad5@ig@ig_1_scope@wnt`；`script@story@sad5@ig@ig_1_scope@action`；`script@story@sad5@ig@IG_2_bountymeets@posse@action`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×299、ENTITY::IS_ENTITY_DEAD ×230、PLAYER::GET_PLAYER_INDEX ×161、BUILTIN::TO_FLOAT ×144、MISC::GET_HASH_KEY ×142

#### 11. 美国毒物 `FIN2`

- 脚本：`finale2.c`（强匹配，96,813 行 / 2,636 个函数）
- **目标（脚本顺序）**
  1. 跟随莎迪前往草莓镇。
  2. 返回草莓镇。
  3. 返回克里特处。
  4. 返回绞刑台。
  5. 将克里特拖到绞刑架处。
  6. 拖着克里特走。
  7. 杀死迈卡。
  8. 与莎迪会合。
  9. 在草莓镇上搜寻克里特。
  10. 追上克里特。
  11. 殴打克里特。
  12. 强迫克里特上阶梯。
  - …（另有 17 条）
- **失败条件**：莎迪被抛弃在草莓镇。；莎迪和查尔斯被抛弃了。；克里特在透露迈卡的位置之前死了。
- **生成调用点**：ped 2 / vehicle 0 / object 4 / pickup 0
- **过场**：`script@Story@FIN2@RideToMtHagen`；`script@story@FIN2@fullcme`；`script@story@fin2@ig@ig1_cleet_spotted@ig1_cleet_spotted`
- **高频 native**：ENTITY::DOES_ENTITY_EXIST ×287、ENTITY::IS_ENTITY_DEAD ×248、PED::SET_PED_CONFIG_FLAG ×219、PLAYER::GET_PLAYER_INDEX ×182、PLAYER::PLAYER_ID ×180

## 3. 支线（有脚本的）

共 89 条支线匹配到脚本。

| 任务 | 脚本 | 目标数 | 失败数 |
|---|---|---|---|
| 迷途未知返 `GUA1` | `guama1.c` | 0 | 0 |
| 比尔想要些发油。 `IRBLPM` | `cv_cf_shared.c` | 0 | 0 |
| 查尔斯想要一根雕的羽毛。 `IRCHEF` | `cv_cf_shared.c` | 0 | 0 |
| 查尔斯想要些私酒。 `IRCHMS` | `cv_cf_shared.c` | 0 | 0 |
| 查尔斯想要些夹竹桃。 `IRCHOL` | `cv_cf_shared.c` | 0 | 0 |
| 达奇想要一只烟斗。 `IRDTPI` | `cv_cf_shared.c` | 0 | 0 |
| 何西阿喜欢犯罪小说，给他找一本。 `IRHOBK` | `cv_cf_shared.c` | 0 | 0 |
| 何西阿想要些人参。 `IRHOGN` | `cv_cf_shared.c` | 0 | 0 |
| 杰克想要一本恐怖小说。 `IRJKPD` | `cv_cf_shared.c` | 0 | 0 |
| 杰克想要一枚顶针。 `IRJKTH` | `cv_cf_shared.c` | 0 | 0 |
| 哈维尔想要些夹竹桃。 `IRJVOL` | `cv_cf_shared.c` | 0 | 0 |
| 基兰想要些牛蒡根。 `IRKIBR` | `cv_cf_shared.c` | 0 | 0 |
| 蓝尼想要一块怀表。 `IRLNPW` | `cv_cf_shared.c` | 0 | 0 |
| 玛丽贝思想要一支钢笔。 `IRMBFP` | `cv_cf_shared.c` | 0 | 0 |
| 莫莉想要一块化妆镜。 `IRMLPM` | `cv_cf_shared.c` | 0 | 0 |
| 皮尔逊想要一个海军罗盘。 `IRPRNC` | `cv_cf_shared.c` | 0 | 0 |
| 皮尔逊想要一只兔子。 `IRPRRB` | `cv_cf_shared.c` | 0 | 0 |
| 莎迪想要一支口琴。 `IRSDHM` | `cv_cf_shared.c` | 0 | 0 |
| 西恩想要些威士忌。 `IRSNWH` | `cv_cf_shared.c` | 0 | 0 |
| 苏珊想要些草药当调味品。 `IRSUSE` | `cv_cf_shared.c` | 0 | 0 |
| 蒂莉想要一条项链。 `IRTLNL` | `cv_cf_shared.c` | 0 | 0 |
| 大叔想要些制作药的材料。 `IRUNRM` | `cv_cf_shared.c` | 0 | 0 |
| 地主阶级 `RBCH11` | `rcm_beechers12.c` | 0 | 0 |
| 林赛·沃福德 `RBCON` | `rcm_bounty_exconfed1.c` | 0 | 2 |
| 约书亚·布朗 `RBDUL` | `rcm_bounty_duel1.c` | 0 | 0 |
| 真爱之路：第 1 部分 `RBNP10` | `rcm_beau_and_penelope10.c` | 0 | 0 |
| 马克·约翰逊 `RBRAN` | `rcm_bounty_rancher1.c` | 0 | 0 |
| 广告，美国的新派艺术：第 1 部分 `RBRT0` | `rcm_braithwaites01.c` | 0 | 0 |
| RBT03 `RBT03` | `rcm_bh_laramie_sleeping.c` | 0 | 0 |
| 爱丽·安妮·思旺 `RBT05` | `rcm_bh_wife_and_lover.c` | 0 | 2 |
| RBT12 `RBT12` | `rcm_bh_camp_return.c` | 0 | 0 |
| 罗比·莱德劳 `RBT14` | `rcm_bh_shack_escape.c` | 0 | 2 |
| 安东尼·福尔曼 `RBT15` | `rcm_bh_sd_saloon.c` | 1 | 0 |
| 奥蒂斯·斯金纳 `RBT18` | `rcm_bh_skinner_brother.c` | 0 | 2 |
| 伊莱亚斯·格林 `RBT20` | `rcm_bh_skinner_search.c` | 3 | 0 |
| RBT21 `RBT21` | `rcm_bh_blackwater_hunt.c` | 0 | 0 |
| 瓦金·阿罗约 `RBT22` | `rcm_bh_bandito_shack.c` | 4 | 1 |
| 埃斯塔班·科特斯 `RBT23` | `rcm_bh_bandito_mine.c` | 1 | 1 |
| 捆绑的纽带 `RBWCG1` | `rcm_chain_gang2.c` | 1 | 0 |
| 捆绑的纽带：第 2 部分 `RBWCG2` | `rcm_chain_gang3.c` | 1 | 0 |
| 捆绑的纽带：第 2 部分 `RBWCG3` | `rcm_chain_gang3.c` | 0 | 0 |
| 捆绑的纽带：第 3 部分 `RBWCG4` | `rcm_chain_gang5.c` | 1 | 0 |
| 枪手传 `RCAL11` | `rcm_callaway1.c` | 0 | 0 |
| 吸烟和其他爱好 `RCCIG` | `rcm_collect_cigarette_cards1.c` | 0 | 0 |
| 公爵夫人和其他动物 `RCEXO1` | `abigail2_1.c` | 0 | 0 |
| 公爵夫人和其他动物：第 2 部分 `RCEXO2` | `abigail2_1.c` | 0 | 0 |
| 公爵夫人和其他动物：第 3 部分 `RCEXO3` | `abigail2_1.c` | 0 | 0 |
| 公爵夫人和其他动物：第 4 部分 `RCEXO4` | `abigail2_1.c` | 0 | 0 |
| 公爵夫人和其他动物：第 5 部分 `RCEXO5` | `abigail2_1.c` | 0 | 0 |
| 一个聪明好动的男孩 `RCKPT1` | `rcm_crackpot1.c` | 0 | 0 |
| 一个聪明好动的男孩：第 2 部分 `RCKPT2` | `rcm_crackpot2.c` | 0 | 0 |
| 善恶参半：第 1 部分 `RCLD21` | `rcm_calderon21.c` | 0 | 0 |
| 好心没好报 `RCRLE` | `rcm_creole1.c` | 0 | 0 |
| 寡妇莎迪·阿德勒：第 1 部分 `RDST61` | `rcm_dusters61.c` | 2 | 0 |
| 募捐人 `REFND` | `beat_wagon_threat.c` | 0 | 0 |
| 金光闪闪 `RETH` | `rcm_treasure_hunter.c` | 0 | 0 |
| 艺术家的方式：第 2 部分 `RFMA2` | `rcm_for_my_art2.c` | 0 | 0 |
| 亲爱的塔西佗叔叔 `RGNG01` | `rcm_gang02.c` | 0 | 0 |
| 弗拉科·埃尔南德斯 `RGUN2` | `rcm_gunslinger2_1.c` | 0 | 0 |
| 比利·米德奈特 `RGUN3` | `rcm_gunslinger3_1.c` | 9 | 1 |
| 黑衣美人 `RGUN5` | `rcm_gunslinger5_1.c` | 0 | 0 |
| 拜访麦奎尔先生 `RHMRB` | `rcm_homerob01.c` | 0 | 0 |
| 长者的智慧：第 3 部分 `RHNTN3` | `rcm_poisoned_well3.c` | 0 | 0 |
| 他当然是英国佬 `RKTTY1` | `rcm_here_kitty_kitty1.c` | 0 | 0 |
| 他当然是英国佬：第 3 部分 `RKTTY3` | `rcm_here_kitty_kitty4.c` | 0 | 0 |
| 他当然是英国佬：第 4 部分 `RKTTY4` | `rcm_here_kitty_kitty4.c` | 0 | 0 |
| 爱好者的乐土：第 2 部分 `RMASN2` | `rcm_mason2.c` | 0 | 0 |
| 实用与理想主义入门：第 1 部分 `RMAYR1` | `rcm_mr_mayor1.c` | 0 | 0 |
| 实用与理想主义入门：第 2 部分 `RMAYR2` | `rcm_mr_mayor2.c` | 0 | 0 |
| 美国炼狱 `RMLLR1` | `rcm_evelyn_miller1.c` | 0 | 0 |
| 美国炼狱：第 2 部分 `RMLLR2` | `rcm_evelyn_miller2.c` | 0 | 0 |
| 美国炼狱：第 5 部分 `RMLLR5` | `rcm_evelyn_miller5.c` | 0 | 0 |
| 文明之乐 `RMOB01` | `rcm_mob01.c` | 1 | 0 |
| 文明之乐 `RMOB02` | `rcm_mob02.c` | 1 | 0 |
| 玛丽贝思 `RMRYB` | `rcm_marybeth1.c` | 0 | 0 |
| 美国父亲：第 1 部分 `RNATV1` | `rcm_native1.c` | 0 | 0 |
| 噢，兄弟 `ROBT1` | `rcm_oh_brother1.c` | 0 | 0 |
| 噢，兄弟：第 2 部分 `ROBT2` | `rcm_oh_brother2.c` | 0 | 0 |
| 噢，兄弟：第 3 部分 `ROBT3` | `rcm_oh_brother3.c` | 0 | 0 |
| “粉末”登台 `RODDF1` | `rcm_the_odd_fellows1.c` | 0 | 0 |
| “粉末”登台：第 2 部分 `RODDF2` | `rcm_the_odd_fellows2.c` | 0 | 0 |
| 知识的仁慈：第 3 部分 `RRTL3` | `rcm_ride_the_lightning3.c` | 0 | 0 |
| 知识的仁慈：第 7 部分 `RRTL7` | `rcm_ride_the_lightning7.c` | 0 | 0 |
| 美国梦 `RSKLR` | `rcm_serial_killer1.c` | 0 | 0 |
| 历史的罪恶 `RSLVC1` | `rcm_slave_catcher1.c` | 0 | 0 |
| 放债与更多罪孽：第 4 部分 `RSTR1` | `rcm_strauss11.c` | 0 | 0 |
| 放债与更多罪孽：第 5 部分 `RSTR2` | `rcm_strauss21.c` | 0 | 0 |
| 老兵：第 2 部分 `RWARV2` | `rcm_war_veteran2.c` | 0 | 0 |
| 老兵：第 4 部分 `RWARV4` | `rcm_war_veteran4.c` | 0 | 0 |

## 4. 局限

| 项 | 说明 |
|---|---|
| 反编译源码 | 变量名已丢失，无法直接看出"哪个 volume 触发哪个目标"；但 native 调用与文本键是真实的 |
| 目标不全 | 部分任务的目标由变量拼装（`func_xxx` 返回文本键），静态匹配抓不到全部 |
| 生成计数 | 是调用点数量，不是运行时实际生成数量 |
| 版本 | 脚本库为 build 1355；与本机 RPF 条目数一致，但若游戏版本不同可能有差异 |
| 78 条未匹配 | 主要是物品请求、配方、线上任务，它们走通用脚本 |
| 目标文本不全 | 部分任务的文案由变量拼装（`func_xxx` 返回键），或文本键不在任务 yldb，静态抓不到 |

## 5. 产物与复现

| 文件 | 内容 |
|---|---|
| `export/levels/world/mission_scripts.csv` | 192 条任务：脚本文件、行数、函数数、目标数、失败数、生成调用点 |
| `export/levels/world/mission_scripts.json` | 同上 + 完整目标/失败/过场/native 列表 |
| `work/script_probe/script_map_raw.json` | 任务 → 脚本匹配（含匹配置信度） |
| `tools/build_mission_scripts.py` | 解析脚本并生成上述数据 |

```bash
uv run python tools/build_mission_scripts.py
uv run python tools/render_mission_scripts_md.py
```
