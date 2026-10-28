# 西部亡命之徒 `WNT1` · 逐步骤拆解

> 目标：把“这一关到底怎么跑”拆成可核对的步骤，而不是一句“跟随达奇”。
> 每一步都给出：**玩家目标 → 脚本函数 → 演员调度（行为/生成）→ 失败条件 → 说明**。

| 项 | 值 |
|---|---|
| 章节 | 第 1 章 · 犁刀村 |
| 脚本 | `winter1.c`（108,096 行 / 3,117 个函数） |
| 步骤 | **11 步** |
| 生成调用点 | ped 3 / vehicle 0 / object 7 |
| 行为调用 | 233 次 / 37 类 |
| 过场 | 5 段 · 对白 539 行 · 出场 21 人 |

## 0. 怎么读这张表

- **目标**：任务 HUD 上显示的那句话，来自任务 yldb 的 `WNT1_OBJ_*` 文本键。
- **脚本函数**：设置这个目标的函数，以及它在主流程里被哪个阶段函数调用（行号）。
- **演员调度**：该阶段函数（含两层子调用）里的 `TASK_*` 行为计数；生成是 `CREATE_*` 调用点。
- **失败条件**：该阶段函数里能找到的 `WNT1_*FAIL/LOST/DEAD` 文本；找不到的放在文末统一列。

**名词解释**：

- **行为**：脚本里 `TASK_*` 的调用点数量，表示“让演员做动作”（走位 / 战斗 / 掩体 / 上下马 / 交互），**不是运行时执行次数**。
- **生成**：`PED::CREATE_PED` / `VEHICLE::CREATE_VEHICLE` / `OBJECT::CREATE_OBJECT` 的调用点，表示“刷出角色/车/物”，数量在参数里，未展开。
- **对白**：脚本里的对话组名（如 `WNT1_BANT3`），字幕在任务音频库里按 `_1..N` 编号。
- **微步骤事件**：把阶段函数按调用树展开后的逐条 `TASK_* / CREATE_* / ANIMSCENE / 转场` 事件；坐标已从 `func_1013` 的 211 个坐标点解析出来。**事件带条件分支，不是单条时间轴**。

**重建价值分级**（决定哪些该看、哪些可以忽略）：

| 级别 | 内容 | 处理 |
|---|---|---|
| **S · 结构与空间** | 目标更新、阶段转场、带坐标的走位、带模型/坐标的生成、过场播放 | 直接用于重建 |
| **A · 可见表演** | 转身（TURN）、注视（LOOK）、站姿、动作序列、战斗/掩体、武器/马匹动作、节奏等待（PAUSE）、停止牵马 | 必须还原，需补资源名 |
| **B · 不可见管线** | 资源加载、清理注视、状态查询、AI 分组（CREATE_GROUP）、AI 配置（TASK_SET_*） | 不影响画面，可跳过 |

不含对白的 TASK/CREATE 事件共 227 条：**S 139 / A 57 / B 31**；加入对白后，树内共 277 条：**S 189 / A 57 / B 31**。下面每步只列 S/A，B 类保留在 CSV 里。

**关于 TURN / LOOK**：

- 43 个任务里，**TURN（转身）111 条全部是 A**，**LOOK_AT（注视）78 条全部是 A**；
- B 里没有任何 TURN/LOOK_AT，只有 58 条 `CLEAR_LOOK_AT`（清除注视，不是表演）。

WNT1 的可见朝向/注视事件：

| 步骤 | # | 动作 | 对象 | 说明 |
|---|---|---|---|---|
| 1 | 14 | `TASK_TURN_PED_TO_FACE_ENTITY` | 0 | 玩家可见的转身/注视 |
| 1 | 19 | `TASK_TURN_PED_TO_FACE_ENTITY` | 0 | 玩家可见的转身/注视 |
| 1 | 27 | `TASK_TURN_PED_TO_FACE_ENTITY` | 0 | 玩家可见的转身/注视 |
| 2 | 5 | `TASK_TURN_PED_TO_FACE_ENTITY` | 0 | 玩家可见的转身/注视 |
| 2 | 20 | `TASK_TURN_PED_TO_FACE_ENTITY` | 0 | 玩家可见的转身/注视 |

**怎么用它重建**：

1. 按步骤顺序搭出阶段；每步的“微步骤事件”就是该阶段要执行的演员指令清单。
2. 每条事件都带“条件”列：`if (...)` 是进入该指令的前置判断，重建时照抄条件即可还原分支。
3. 坐标已从 `func_1013` 解析（211 个点），可以直接在引擎里摆点。
4. 实体列 `0/Global_35` 是玩家，`uLocal_1064[n]` 是任务演员槽位，`iLocal_*` 是任务本地实体；具体是谁需要看该槽位的赋值。

> 注意：步骤顺序按“目标函数在主流程里第一次被调用的行号”排，不是引擎里的状态机顺序；少数分支（如木屋二次搜查、马匹教学）可能在实际游玩中是可选的。

## 1. 步骤总表

| # | 玩家目标 | 阶段函数 | 行为 | 生成 | 事件 |
|---|---|---|---|---|---|
| 1 | 跟随迈卡 | `func_793` | 28 | 0 | 43 |
| 2 | 跟随达奇 | `func_798` | 18 | 0 | 31 |
| 3 | 保护达奇 | `func_803` | 34 | 1 | 69 |
| 4 | 进入木屋 | `func_808` | 18 | 2 | 32 |
| 5 | 调查畜棚 | `func_813` | 3 | 0 | 40 |
| 6 | 将马牵引到拴马桩处 | `func_828` | 2 | 0 | 11 |
| 7 | 前往牛棚然后按 找掩护 | `func_1929` | 0 | 0 | 0 |
| 8 | 继续搜查木屋 | `func_1986` | 0 | 2 | 1 |
| 9 | 按住 将视线集中在奥德里斯科帮成员上 | `func_2013` | 0 | 0 | 0 |
| 10 | 按住 将视线集中在马上 | `func_2069` | 0 | 0 | 0 |
| 11 | 靠近马 | `func_2069` | 0 | 0 | 0 |

## 2. 任务树（总任务 → 大步骤 → 小步骤 → 执行）

```text
WNT1 西部亡命之徒
├─ 步骤 1 跟随迈卡。（64 事件）
│  ├─ 前置（59 事件）
│  ├─ case 0（1 事件）
│  ├─ case 1（4 事件）
│  ├─ case 2（0 事件）
├─ 步骤 2 跟随达奇。（33 事件）
│  ├─ 前置（30 事件）
│  ├─ case 0（1 事件）
│  ├─ case 1（1 事件）
│  ├─ case 2（1 事件）
│  ├─ case 3（0 事件）
├─ 步骤 3 保护达奇。（76 事件）
│  ├─ 前置（44 事件）
│  ├─ case 0（1 事件）
│  ├─ case 1（1 事件）
│  ├─ case 2（30 事件）
├─ 步骤 4 进入木屋。（46 事件）
│  ├─ 前置（45 事件）
│  ├─ case 0（1 事件）
│  ├─ case 1（0 事件）
├─ 步骤 5 调查畜棚。（40 事件）
│  ├─ 前置（40 事件）
│  ├─ case 0（0 事件）
├─ 步骤 6 将马牵引到拴马桩处。（17 事件）
│  ├─ 前置（17 事件）
│  ├─ case 0（0 事件）
├─ 步骤 7 前往牛棚然后按 找掩护。（0 事件）
│  ├─ 主体（0 事件）
├─ 步骤 8 继续搜查木屋。（1 事件）
│  ├─ 主体（1 事件）
├─ 步骤 9 按住 将视线集中在奥德里斯科帮成员上。（0 事件）
│  ├─ 主体（0 事件）
├─ 步骤 10 按住 将视线集中在马上。（0 事件）
│  ├─ 主体（0 事件）
├─ 步骤 11 靠近马。（0 事件）
│  ├─ 主体（0 事件）
```

> 大步骤＝目标所在的阶段函数；小步骤＝该函数的 switch 状态（前置 / case N）；执行＝展开后的 TASK/CREATE/演出事件。

## 3. 逐步拆解

### 步骤 1 · 跟随迈卡

- **目标**：跟随迈卡。
- **脚本**：目标函数 `func_1344`；由阶段函数 `func_793` 调用（行 35832）
- **演员调度**：28 次行为，主要是 PERFORM_SEQUENCE ×9、FOLLOW_NAV_MESH_TO_COORD ×7、FOLLOW_WAYPOINT_RECORDING ×4、DISMOUNT_ANIMAL ×3
- **生成**：0 个 CREATE_* 调用点
- **对白**：8 组对话，共 21 行
  - `WNT1_BANT`（条件触发）
    - 我很高兴你没事，迈卡。
    - 当然。
    - 问他是否见过约翰。
  - `WNT1_BANT3`（条件触发）
    - 你有把握吗，迈卡？
    - 摩根先生，我从没想过我会这么高兴看到你。
    - 我感觉有些......孤独。其他人去哪了？
    - 山上的老采矿营地。
  - `WNT1_HITCH`（条件触发）
    - 我们把马拴在这里。
- **说明**：雪夜骑行开场。迈卡带路，玩家只需要跟住；脚本在这一段大量使用“路径点走位 + 导航走位”，并安排了下马动作。

**微步骤事件（只列 S/A，共 39 条；另有 B 类 4 条已省略）**

| # | 价值 | 类型 | 对象 | 动作 | 参数（坐标已解析） | 条件 |
|---|---|---|---|---|---|---|
| 1 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[2], "pl_Arrival_Dutch", true);` | — |
| 2 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[2]);` | — |
| 4 | S | 行为 | 0 | `TASK_FOLLOW_WAYPOINT_RECORDING` | `TASK::TASK_FOLLOW_WAYPOINT_RECORDING(0, sLocal_880, 0, 25608, -1, 0, 0, -1);` | if (!func_177(iLocal_92, 4)) |
| 5 | A | 行为 | uLocal_1064[2] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(uLocal_1064[2], iLocal_1018);` | if (!func_177(iLocal_92, 4)) |
| 6 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-554.9, 2702.8, 319.4), 1.1f, 20000, 0.25f, 512, func_494(2, 7));` | — |
| 7 | A | 行为 | uLocal_1064[1] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(uLocal_1064[1], iLocal_1018);` | — |
| 10 | A | 行为 | 0 | `TASK_PAUSE` | `TASK::TASK_PAUSE(0, 1000);` | if (func_2469(cParam0)) |
| 11 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, func_1936(uLocal_182[3], "CS_Dutch", "PL_Arrival_Dutch"), 1.25f, 20000, 0.25f, 83` | if (func_2469(cParam0)) |
| 12 | A | 行为 | uLocal_1064[1] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(uLocal_1064[1], iVar0);` | if (func_2469(cParam0)) |
| 13 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-1088.1, 2549.2, 305.3), 1f, 20000, 0.25f, 1, 40000f);` | if (TASK::GET_SCRIPT_TASK_STATUS(uLocal_1064[1], 242628503,  |
| 14 | A | 行为 | 0 | `TASK_TURN_PED_TO_FACE_ENTITY` | `TASK::TASK_TURN_PED_TO_FACE_ENTITY(0, Global_35, -1, -1f, -1f, -1f);` | if (TASK::GET_SCRIPT_TASK_STATUS(uLocal_1064[1], 242628503,  |
| 15 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, func_1936(uLocal_182[5], "DUTCH", "pl_IG2_DUTCH_INSTRUCTS_TO_COVER"), 1f, 40000, ` | if (!func_177(iLocal_904, 536870912)) |
| 16 | S | 行为 | 0 | `TASK_FOLLOW_WAYPOINT_RECORDING` | `TASK::TASK_FOLLOW_WAYPOINT_RECORDING(0, sLocal_880, 0, 8, -1, 0, 0, -1);` | if (!func_177(iLocal_906, 268435456)) |
| 17 | S | 行为 | 0 | `TASK_DISMOUNT_ANIMAL` | `TASK::TASK_DISMOUNT_ANIMAL(0, 262144, 0, 0, 0, 0);` | if (!func_177(iLocal_906, 268435456)) |
| 18 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-1359.4, 2428.9, 306.8), 1f, 20000, 0.25f, 0, 40000f);` | if (!func_177(iLocal_906, 268435456)) |
| 19 | A | 行为 | 0 | `TASK_TURN_PED_TO_FACE_ENTITY` | `TASK::TASK_TURN_PED_TO_FACE_ENTITY(0, uLocal_1064[1], -1, -1f, -1f, -1f);` | if (!ENTITY::IS_ENTITY_DEAD(uLocal_1064[1])) |
| 20 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-1352.5, 2424.6, 306.9), 1.1f, 20000, 0.25f, 512, func_494(2, 7));` | — |
| 21 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, func_1936(uLocal_182[4], "CS_MicahBell", "PL_Arrival_Micah"), 1.25f, 20000, 0.25f` | if (func_2469(cParam0)) |
| 22 | A | 行为 | uLocal_1064[2] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(uLocal_1064[2], iVar0);` | if (func_2469(cParam0)) |
| 23 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-1359.4, 2428.9, 306.8), 1f, 20000, 0.25f, 1, 40000f);` | if (TASK::GET_SCRIPT_TASK_STATUS(uLocal_1064[2], 242628503,  |
| 24 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, -590.3934f, 2682.694f, 320.8356f, 1f, 20000, 0.25f, 1, 40000f);` | if (!func_177(iLocal_904, 536870912)) |
| 25 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, func_1936(uLocal_182[6], "CS_MicahBell", "pl_IG2_MICAH_TAKES_COVER"), 1f, 60000, ` | if (!func_177(iLocal_904, 536870912)) |
| 26 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, -571.3424f, 2690.15f, 319.0905f, 1f, 20000, 0.25f, 0, 40000f);` | — |
| 27 | A | 行为 | 0 | `TASK_TURN_PED_TO_FACE_ENTITY` | `TASK::TASK_TURN_PED_TO_FACE_ENTITY(0, Global_35, 0, -1f, -1f, -1f);` | — |
| 28 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-563.9, 2703.0, 319.4), 1f, 20000, 0.25f, 0, 40000f);` | — |
| 29 | S | 行为 | 0 | `TASK_PUT_PED_DIRECTLY_INTO_COVER` | `TASK::TASK_PUT_PED_DIRECTLY_INTO_COVER(0, (-563.9, 2703.0, 319.4), -1, 0, 0f, 1, 1, iLocal_1008, true, 0, 0);` | — |
| 30 | S | 行为 | uLocal_1064[2] | `TASK_PUT_PED_DIRECTLY_INTO_COVER` | `TASK::TASK_PUT_PED_DIRECTLY_INTO_COVER(uLocal_1064[2], (-563.9, 2703.0, 319.4), -1, 0, 0f, 1, 1, iLocal_1008, false, 0, ` | if (!PED::IS_PED_IN_COVER(uLocal_1064[2], false, false) && ! |
| 31 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-1344.8, 2418.2, 306.3), 1.25f, 20000, 0.25f, 512, func_494(2, 8));` | if (func_1331(Global_35, func_473(2, 8), 1) < 10f) |
| 32 | A | 行为 | Global_35 | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(Global_35, iLocal_1018);` | if (func_1331(Global_35, func_473(2, 8), 1) < 10f) |
| 33 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[28]);` | — |
| 34 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[7]);` | — |
| 35 | S | 生成 | — | `CREATE_OBJECT` | `Local_14.f_64[0] = OBJECT::CREATE_OBJECT(joaat("S_MRADLERFROZEN_BLKT"), -569.1129f, 2692.749f, 320.63f, true, true, fals` | if (!ENTITY::DOES_ENTITY_EXIST(Local_14.f_64[0]) && (iParam0 |
| 37 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[9], "PL_Idle", true);` | — |
| 38 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[9]);` | if (!ANIMSCENE::IS_ANIM_SCENE_RUNNING(uLocal_182[9], false)) |
| 39 | S | 转场 | — | `state -> 1` | `func_134(cParam0, 1);` | if (!func_177(iLocal_904, 536870912)) |
| 40 | S | 行为 | bParam0 | `TASK_DISMOUNT_ANIMAL` | `TASK::TASK_DISMOUNT_ANIMAL(bParam0, iParam12, 0, 0, 0, 0);` | if (!ENTITY::IS_ENTITY_DEAD(iVar0) && !func_1920(bParam0, 50 |
| 41 | A | 行为 | bParam0 | `TASK_LEAVE_ANY_VEHICLE` | `TASK::TASK_LEAVE_ANY_VEHICLE(bParam0, 0, iParam12);` | if (!ENTITY::IS_ENTITY_DEAD(iVar1) && !func_1920(bParam0, -8 |
| 42 | A | 行为 | iLocal_1084[0] | `TASK_STAND_STILL` | `TASK::TASK_STAND_STILL(iLocal_1084[0], -1);` | if (!func_923(iLocal_1084[0])) |
| 43 | S | 转场 | — | `state -> 2` | `func_134(cParam0, 2);` | if ((func_923(iLocal_1084[0]) ／／ ((!PED::IS_PED_ON_MOUNT(Glo |


### 步骤 2 · 跟随达奇

- **目标**：跟随达奇。
- **脚本**：目标函数 `func_1353`；由阶段函数 `func_798` 调用（行 35982）
- **演员调度**：18 次行为，主要是 FOLLOW_NAV_MESH_TO_COORD ×7、PERFORM_SEQUENCE ×6、TURN_PED_TO_FACE_ENTITY ×3、PUT_PED_DIRECTLY_INTO_COVER ×2
- **生成**：0 个 CREATE_* 调用点
- **对白**：1 组对话，共 2 行
  - `WNT1_IG2`（条件触发）
    - 你们两个，去藏起来......
    - 我们三个人一看就不是什么善类，还是我一个人去吧，这样才不会太吓人。
- **说明**：追上达奇，队伍从雪坡下到阿德勒牧场。行为以导航走位与转身面向为主，属于“到达目标点”的过渡段。

**微步骤事件（只列 S/A，共 26 条；另有 B 类 5 条已省略）**

| # | 价值 | 类型 | 对象 | 动作 | 参数（坐标已解析） | 条件 |
|---|---|---|---|---|---|---|
| 3 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[3]);` | — |
| 4 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-1088.1, 2549.2, 305.3), 1f, 20000, 0.25f, 0, 40000f);` | if (ENTITY::DOES_ENTITY_EXIST(uLocal_1064[1]) && !ENTITY::IS |
| 5 | A | 行为 | 0 | `TASK_TURN_PED_TO_FACE_ENTITY` | `TASK::TASK_TURN_PED_TO_FACE_ENTITY(0, Global_35, -1, -1f, -1f, -1f);` | if (ENTITY::DOES_ENTITY_EXIST(uLocal_1064[1]) && !ENTITY::IS |
| 6 | A | 行为 | uLocal_1064[1] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(uLocal_1064[1], iLocal_1018);` | if (ENTITY::DOES_ENTITY_EXIST(uLocal_1064[1]) && !ENTITY::IS |
| 7 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-1088.1, 2549.2, 305.3), 1f, 20000, 0.25f, 1, 40000f);` | if (TASK::GET_SCRIPT_TASK_STATUS(uLocal_1064[1], 242628503,  |
| 10 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, func_1936(uLocal_182[5], "DUTCH", "pl_IG2_DUTCH_INSTRUCTS_TO_COVER"), 1f, 40000, ` | if (!func_177(iLocal_904, 536870912)) |
| 11 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[5]);` | — |
| 12 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[4]);` | — |
| 13 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-1359.4, 2428.9, 306.8), 1f, 20000, 0.25f, 0, 40000f);` | if (ENTITY::DOES_ENTITY_EXIST(uLocal_1064[2]) && !ENTITY::IS |
| 14 | A | 行为 | uLocal_1064[2] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(uLocal_1064[2], iLocal_1018);` | if (ENTITY::DOES_ENTITY_EXIST(uLocal_1064[2]) && !ENTITY::IS |
| 15 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-1359.4, 2428.9, 306.8), 1f, 20000, 0.25f, 1, 40000f);` | if (TASK::GET_SCRIPT_TASK_STATUS(uLocal_1064[2], 242628503,  |
| 16 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, -590.3934f, 2682.694f, 320.8356f, 1f, 20000, 0.25f, 1, 40000f);` | if (!func_177(iLocal_904, 536870912)) |
| 17 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, func_1936(uLocal_182[6], "CS_MicahBell", "pl_IG2_MICAH_TAKES_COVER"), 1f, 60000, ` | if (!func_177(iLocal_904, 536870912)) |
| 18 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[6]);` | — |
| 19 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, -571.3424f, 2690.15f, 319.0905f, 1f, 20000, 0.25f, 0, 40000f);` | — |
| 20 | A | 行为 | 0 | `TASK_TURN_PED_TO_FACE_ENTITY` | `TASK::TASK_TURN_PED_TO_FACE_ENTITY(0, Global_35, 0, -1f, -1f, -1f);` | — |
| 21 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-563.9, 2703.0, 319.4), 1f, 20000, 0.25f, 0, 40000f);` | — |
| 22 | S | 行为 | 0 | `TASK_PUT_PED_DIRECTLY_INTO_COVER` | `TASK::TASK_PUT_PED_DIRECTLY_INTO_COVER(0, (-563.9, 2703.0, 319.4), -1, 0, 0f, 1, 1, iLocal_1008, true, 0, 0);` | — |
| 23 | S | 行为 | uLocal_1064[2] | `TASK_PUT_PED_DIRECTLY_INTO_COVER` | `TASK::TASK_PUT_PED_DIRECTLY_INTO_COVER(uLocal_1064[2], (-563.9, 2703.0, 319.4), -1, 0, 0f, 1, 1, iLocal_1008, false, 0, ` | if (!PED::IS_PED_IN_COVER(uLocal_1064[2], false, false) && ! |
| 24 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[7]);` | — |
| 25 | S | 生成 | — | `CREATE_OBJECT` | `Local_14.f_64[0] = OBJECT::CREATE_OBJECT(joaat("S_MRADLERFROZEN_BLKT"), -569.1129f, 2692.749f, 320.63f, true, true, fals` | if (!ENTITY::DOES_ENTITY_EXIST(Local_14.f_64[0]) && (iParam0 |
| 27 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[9], "PL_Idle", true);` | — |
| 28 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[9]);` | if (!ANIMSCENE::IS_ANIM_SCENE_RUNNING(uLocal_182[9], false)) |
| 29 | S | 转场 | — | `state -> 1` | `func_134(cParam0, 1);` | if (!PED::IS_PED_FULLY_ON_MOUNT(Global_35, true) && iLocal_3 |
| 30 | S | 转场 | — | `state -> 2` | `func_134(cParam0, 2);` | if ((ENTITY::IS_ENTITY_IN_VOLUME(Global_35, iLocal_1108[13], |
| 31 | S | 转场 | — | `state -> 3` | `func_134(cParam0, 3);` | if (func_1357() ／／ func_1358(&uLocal_1327) > 60f) |


### 步骤 3 · 保护达奇

- **目标**：保护达奇。；跟随达奇。
- **脚本**：目标函数 `func_1371`；由阶段函数 `func_803` 调用（行 36136）
- **演员调度**：34 次行为，主要是 PERFORM_SEQUENCE ×11、FOLLOW_NAV_MESH_TO_COORD ×6、PAUSE ×4、PUT_PED_DIRECTLY_INTO_COVER ×4
- **生成**：1 个 CREATE_* 调用点
- **对白**：4 组对话，共 7 行
  - `WNT1_EARLY`（条件触发）
    - 亚瑟，我说过我来处理！
    - 似乎不太顺利。
  - `WNT1_LEAVE`（条件触发）
    - 让他跑吧！他一个人在外面坚持不了多久的。
  - `WNT1_QUICK`（条件触发）
    - 亚瑟，我说过我来处理！
    - 似乎不太顺利。
    - 好吧，至少你快速解决了他们。
- **说明**：抵达牧场后进入交火。这是本关行为最密集的一段：行为序列 11 次、导航走位 6 次、进入掩体 4 次，并生成 1 个对象（掩体/道具）。

**微步骤事件（只列 S/A，共 60 条；另有 B 类 9 条已省略）**

| # | 价值 | 类型 | 对象 | 动作 | 参数（坐标已解析） | 条件 |
|---|---|---|---|---|---|---|
| 1 | S | 行为 | 0 | `TASK_COMBAT_HATED_TARGETS_IN_AREA` | `TASK::TASK_COMBAT_HATED_TARGETS_IN_AREA(0, ENTITY::GET_ENTITY_COORDS(Local_14.f_11[iLocal_903], true, false), 200f, 0, 0` | if (iLocal_903 == 2) |
| 2 | A | 行为 | Local_14.f_11[iLocal_903] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(Local_14.f_11[iLocal_903], iLocal_1018);` | if (iLocal_903 == 2) |
| 3 | A | 行为 | 0 | `TASK_PAUSE` | `TASK::TASK_PAUSE(0, MISC::GET_RANDOM_INT_IN_RANGE(0, 750));` | — |
| 4 | S | 行为 | 0 | `TASK_GO_TO_COORD_WHILE_AIMING_AT_ENTITY` | `TASK::TASK_GO_TO_COORD_WHILE_AIMING_AT_ENTITY(0, vVar0, Global_35, 2f, 1, 1056964608 /* Float: 0.5f */, 1082130432 /* Fl` | — |
| 5 | S | 行为 | 0 | `TASK_PUT_PED_DIRECTLY_INTO_COVER` | `TASK::TASK_PUT_PED_DIRECTLY_INTO_COVER(0, vVar0, 500, 1, 0f, 0, 0, uLocal_1013[iLocal_903], true, 0, 0);` | — |
| 6 | S | 行为 | uLocal_1064[2] | `TASK_COMBAT_PED` | `TASK::TASK_COMBAT_PED(uLocal_1064[2], Local_14.f_40[0], 0, 0);` | if (!ENTITY::IS_ENTITY_DEAD(Local_14.f_40[0])) |
| 7 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, -566.6384f, 2713.117f, 320.2408f, 2f, 20000, 0.25f, 0, 40000f);` | if (func_177(iLocal_906, 1073741824 /* Float: 2f */)) |
| 8 | S | 行为 | 0 | `TASK_FOLLOW_WAYPOINT_RECORDING` | `TASK::TASK_FOLLOW_WAYPOINT_RECORDING(0, sLocal_883, 0, 2052, -1, 0, 0, -1);` | if (func_177(iLocal_906, 1073741824 /* Float: 2f */)) |
| 9 | A | 行为 | Local_14.f_36[0] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(Local_14.f_36[0], iLocal_1018);` | if (func_177(iLocal_906, 1073741824 /* Float: 2f */)) |
| 10 | A | 行为 | 0 | `TASK_FLEE_COORD` | `TASK::TASK_FLEE_COORD(0, (-566.2, 2696.1, 318.5), 3, 8448, -1082130432 /* Float: -1f */, -1, 0);` | if (func_1331(Local_14.f_36[0], vVar0, 1) < 2f ／／ (TASK::GET |
| 11 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[7], sParam0, true);` | if (ANIMSCENE::_0x23E33CB9F4A3F547(uLocal_182[7], sParam0)) |
| 12 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[7]);` | if (!ANIMSCENE::IS_ANIM_SCENE_RUNNING(uLocal_182[7], false)) |
| 14 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[7], "PL_IG4_Odriscoll_Guns_Drawn", true);` | if (ANIMSCENE::IS_ANIM_SCENE_RUNNING(uLocal_182[7], false) & |
| 15 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[8], "PL_IG4_Reaction_Guns_Drawn", true);` | if (ANIMSCENE::IS_ANIM_SCENE_RUNNING(uLocal_182[7], false) & |
| 16 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[8]);` | if (!ANIMSCENE::IS_ANIM_SCENE_RUNNING(uLocal_182[8], false)) |
| 17 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[7], "PL_IG4_Odriscoll_No_Guns", true);` | if (ANIMSCENE::IS_ANIM_SCENE_RUNNING(uLocal_182[7], false) & |
| 18 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[8], "PL_IG4_Reaction_No_Guns", true);` | — |
| 19 | S | 行为 | 0 | `TASK_GO_TO_COORD_WHILE_AIMING_AT_ENTITY` | `TASK::TASK_GO_TO_COORD_WHILE_AIMING_AT_ENTITY(0, (-1093.9, 2541.7, 305.5), Local_14.f_11[0], 1f, 1, 1056964608 /* Float:` | — |
| 20 | S | 行为 | 0 | `TASK_PUT_PED_DIRECTLY_INTO_COVER` | `TASK::TASK_PUT_PED_DIRECTLY_INTO_COVER(0, (-1093.9, 2541.7, 305.5), -1, 0, 0f, 0, 0, iLocal_1007, false, 0, 0);` | — |
| 21 | A | 行为 | uLocal_1064[1] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(uLocal_1064[1], iLocal_1018);` | — |
| 22 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[8], sParam0, true);` | if (ANIMSCENE::_0x23E33CB9F4A3F547(uLocal_182[8], sParam0)) |
| 24 | S | 行为 | 0 | `TASK_PUT_PED_DIRECTLY_INTO_COVER` | `TASK::TASK_PUT_PED_DIRECTLY_INTO_COVER(0, (-563.9, 2703.0, 319.4), -1, 1, 0f, 1, 1, iLocal_1008, false, 0, 0);` | — |
| 26 | S | 行为 | 0 | `TASK_COMBAT_HATED_TARGETS_IN_AREA` | `TASK::TASK_COMBAT_HATED_TARGETS_IN_AREA(0, (-563.9, 2703.0, 319.4), 200f, 0, 2);` | — |
| 27 | A | 行为 | — | `TASK_STAY_IN_COVER` | `TASK::TASK_STAY_IN_COVER(0);` | — |
| 28 | A | 行为 | uLocal_1064[2] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(uLocal_1064[2], iLocal_1018);` | — |
| 29 | S | 行为 | 0 | `TASK_PUT_PED_DIRECTLY_INTO_COVER` | `TASK::TASK_PUT_PED_DIRECTLY_INTO_COVER(0, (-563.9, 2703.0, 319.4), -1, 0, 0f, 1, 1, iLocal_1008, false, 1, 0);` | if (iLocal_633 >= 2) |
| 30 | S | 生成 | — | `CREATE_OBJECT` | `Local_14.f_64[0] = OBJECT::CREATE_OBJECT(joaat("S_MRADLERFROZEN_BLKT"), -569.1129f, 2692.749f, 320.63f, true, true, fals` | if (!ENTITY::DOES_ENTITY_EXIST(Local_14.f_64[0]) && (iParam0 |
| 32 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[9], "PL_Idle", true);` | — |
| 33 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[9]);` | if (!ANIMSCENE::IS_ANIM_SCENE_RUNNING(uLocal_182[9], false)) |
| 34 | A | 行为 | Local_14.f_26[iVar0] | `TASK_PAUSE` | `TASK::TASK_PAUSE(Local_14.f_26[iVar0], MISC::GET_RANDOM_INT_IN_RANGE(500, 2000));` | if (func_497(Local_14.f_26[iVar0], 0)) |
| 35 | A | 行为 | 0 | `TASK_PAUSE` | `TASK::TASK_PAUSE(0, MISC::GET_RANDOM_INT_IN_RANGE(500, 1000));` | if (TASK::GET_SCRIPT_TASK_STATUS(Local_14.f_26[iVar0], 63541 |
| 36 | A | 行为 | 0 | `TASK_SMART_FLEE_PED` | `TASK::TASK_SMART_FLEE_PED(0, Global_35, 1000f, -1, 0, 1077936128 /* Float: 3f */, 0);` | if (TASK::GET_SCRIPT_TASK_STATUS(Local_14.f_26[iVar0], 63541 |
| 37 | A | 行为 | Local_14.f_26[iVar0] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(Local_14.f_26[iVar0], iVar1);` | if (TASK::GET_SCRIPT_TASK_STATUS(Local_14.f_26[iVar0], 63541 |
| 38 | S | 转场 | — | `state -> 1` | `func_134(cParam0, 1);` | if (func_177(iLocal_904, 16) ／／ func_1373(cParam0)) |
| 39 | S | 转场 | — | `state -> 2` | `func_134(cParam0, 2);` | if (iLocal_634 == 5) |
| 41 | A | 生成 | — | `CREATE_OBJECT` | `Local_219[iLocal_903 /*12*/] = OBJECT::CREATE_OBJECT(Local_219[iLocal_903 /*12*/].f_4, Local_219[iLocal_903 /*12*/].f_1,` | if (!ENTITY::DOES_ENTITY_EXIST(Local_219[iLocal_903 /*12*/]) |
| 42 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[10]);` | — |
| 43 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[10], sParam0, true);` | if (ANIMSCENE::_0x23E33CB9F4A3F547(uLocal_182[10], sParam0)) |
| 46 | S | 生成 | — | `CREATE_OBJECT` | `iLocal_1019 = OBJECT::CREATE_OBJECT(joaat("P_CS_ADLBLANKET02X"), ENTITY::GET_ENTITY_COORDS(iLocal_1105, true, false), tr` | if (!ENTITY::DOES_ENTITY_EXIST(Local_219[1 /*12*/])) |
| 47 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[12], "pl_IG8_Idle_At_Horse", true);` | — |
| 48 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[12]);` | if (!ANIMSCENE::IS_ANIM_SCENE_RUNNING(uLocal_182[12], false) |
| 49 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-1065.8, 2576.5, 306.0), 1f, -1, 0.25f, 4, func_494(4, 7));` | if (!ENTITY::IS_ENTITY_DEAD(uLocal_1064[2])) |
| 50 | S | 行为 | Global_35 | `TASK_DISMOUNT_ANIMAL` | `TASK::TASK_DISMOUNT_ANIMAL(Global_35, 0, 0, 0, 0, 0);` | if (func_2071(Global_35)) |
| 51 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, func_1936(uLocal_182[13], "CS_MicahBell", "pl_IG8_Micah_Idle_Outside"), 1f, -1, 0` | if (!ENTITY::IS_ENTITY_DEAD(uLocal_1064[2])) |
| 52 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-535.0, 2673.4, 317.9), fVar0, -1, 0.25f, 0, func_494(4, 12));` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[2])) |
| 53 | A | 行为 | 0 | `TASK_STAND_STILL` | `TASK::TASK_STAND_STILL(0, -1);` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[2])) |
| 54 | A | 行为 | iLocal_1084[2] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(iLocal_1084[2], iLocal_1018);` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[2])) |
| 55 | A | 行为 | 0 | `TASK_PAUSE` | `TASK::TASK_PAUSE(0, 2000);` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[0])) |
| 56 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-553.2, 2689.6, 318.8), fVar0, -1, 0.25f, 0, func_494(4, 13));` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[0])) |
| 57 | A | 行为 | iLocal_1084[0] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(iLocal_1084[0], iLocal_1018);` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[0])) |
| 58 | A | 行为 | 0 | `TASK_PAUSE` | `TASK::TASK_PAUSE(0, 4000);` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[1])) |
| 59 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-538.4, 2672.8, 318.0), fVar0, -1, 0.25f, 0, func_494(4, 11));` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[1])) |
| 60 | A | 行为 | iLocal_1084[1] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(iLocal_1084[1], iLocal_1018);` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[1])) |
| 61 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[13]);` | — |
| 63 | A | 生成 | — | `CREATE_OBJECT` | `Local_256[iLocal_903 /*12*/] = OBJECT::CREATE_OBJECT(Local_256[iLocal_903 /*12*/].f_4, Local_256[iLocal_903 /*12*/].f_1,` | if (!ENTITY::DOES_ENTITY_EXIST(Local_256[iLocal_903 /*12*/]) |
| 64 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[14], "pl_Enter_Cabin_to_Shelf", true);` | — |
| 65 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[14]);` | — |
| 66 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[14], sParam0, true);` | if (ANIMSCENE::_0x23E33CB9F4A3F547(uLocal_182[14], sParam0)) |
| 68 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, func_473(4, 14), 1f, -1, 0.25f, 0, func_494(4, 14));` | if (!ENTITY::IS_ENTITY_DEAD(uLocal_1064[2])) |
| 69 | A | 行为 | iParam0 | `TASK_START_SCENARIO_IN_PLACE_HASH` | `TASK::TASK_START_SCENARIO_IN_PLACE_HASH(iParam0, iParam1, iParam2, bParam3, iParam4, fParam5, false);` | — |


### 步骤 4 · 进入木屋

- **目标**：进入木屋。；继续搜查木屋。；出去与达奇会面。；搜寻完物资后，与达奇在外面会合。
- **脚本**：目标函数 `func_1382`；由阶段函数 `func_808` 调用（行 36277）
- **演员调度**：18 次行为，主要是 FOLLOW_NAV_MESH_TO_COORD ×6、PERFORM_SEQUENCE ×6、STAND_STILL ×3、PAUSE ×2
- **生成**：2 个 CREATE_* 调用点
- **对白**：5 组对话，共 14 行
  - `WNT1_FOLLOW`（条件触发）
    - 这里闻上去像开过了聚会。
    - 把这个地方翻个底朝天，尽可能多拿点物资。
    - 我们需要必需品。食物、药品......还有威士忌。
  - `WNT1_HUNGRY`（条件触发）
    - 我要饿死了。
    - 你现在应该吃点东西。补充点体力才好动身回去。
  - `WNT1_LOOT1`（条件触发）
    - 那边地上有一大滩干了的血。
    - 我看见了。
    - 可能是之前住在这里的可怜虫。迈卡在外面的马车里发现了一具尸体。
- **说明**：木屋段总控：进入木屋、继续搜查、出去与达奇会面、搜寻物资后会合，四个目标都挂在同一个阶段函数上。玩家在这里完成第一次搜刮。

**微步骤事件（只列 S/A，共 27 条；另有 B 类 5 条已省略）**

| # | 价值 | 类型 | 对象 | 动作 | 参数（坐标已解析） | 条件 |
|---|---|---|---|---|---|---|
| 2 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[10]);` | — |
| 3 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[10], sParam0, true);` | if (ANIMSCENE::_0x23E33CB9F4A3F547(uLocal_182[10], sParam0)) |
| 5 | S | 生成 | — | `CREATE_OBJECT` | `iLocal_1019 = OBJECT::CREATE_OBJECT(joaat("P_CS_ADLBLANKET02X"), ENTITY::GET_ENTITY_COORDS(iLocal_1105, true, false), tr` | if (!ENTITY::DOES_ENTITY_EXIST(Local_219[1 /*12*/])) |
| 6 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[12], "pl_IG8_Idle_At_Horse", true);` | — |
| 7 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[12]);` | if (!ANIMSCENE::IS_ANIM_SCENE_RUNNING(uLocal_182[12], false) |
| 8 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-1065.8, 2576.5, 306.0), 1f, -1, 0.25f, 4, func_494(4, 7));` | if (!ENTITY::IS_ENTITY_DEAD(uLocal_1064[2])) |
| 9 | A | 行为 | uLocal_1064[2] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(uLocal_1064[2], iLocal_1018);` | if (!ENTITY::IS_ENTITY_DEAD(uLocal_1064[2])) |
| 10 | S | 行为 | Global_35 | `TASK_DISMOUNT_ANIMAL` | `TASK::TASK_DISMOUNT_ANIMAL(Global_35, 0, 0, 0, 0, 0);` | if (func_2071(Global_35)) |
| 11 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, func_1936(uLocal_182[13], "CS_MicahBell", "pl_IG8_Micah_Idle_Outside"), 1f, -1, 0` | if (!ENTITY::IS_ENTITY_DEAD(uLocal_1064[2])) |
| 12 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-535.0, 2673.4, 317.9), fVar0, -1, 0.25f, 0, func_494(4, 12));` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[2])) |
| 13 | A | 行为 | 0 | `TASK_STAND_STILL` | `TASK::TASK_STAND_STILL(0, -1);` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[2])) |
| 14 | A | 行为 | iLocal_1084[2] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(iLocal_1084[2], iLocal_1018);` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[2])) |
| 15 | A | 行为 | 0 | `TASK_PAUSE` | `TASK::TASK_PAUSE(0, 2000);` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[0])) |
| 16 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-553.2, 2689.6, 318.8), fVar0, -1, 0.25f, 0, func_494(4, 13));` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[0])) |
| 17 | A | 行为 | iLocal_1084[0] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(iLocal_1084[0], iLocal_1018);` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[0])) |
| 18 | A | 行为 | 0 | `TASK_PAUSE` | `TASK::TASK_PAUSE(0, 4000);` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[1])) |
| 19 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-538.4, 2672.8, 318.0), fVar0, -1, 0.25f, 0, func_494(4, 11));` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[1])) |
| 20 | A | 行为 | iLocal_1084[1] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(iLocal_1084[1], iLocal_1018);` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[1])) |
| 21 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[13]);` | — |
| 23 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[14], "pl_Enter_Cabin_to_Shelf", true);` | — |
| 24 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[14]);` | — |
| 25 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[14], sParam0, true);` | if (ANIMSCENE::_0x23E33CB9F4A3F547(uLocal_182[14], sParam0)) |
| 27 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, func_473(4, 14), 1f, -1, 0.25f, 0, func_494(4, 14));` | if (!ENTITY::IS_ENTITY_DEAD(uLocal_1064[2])) |
| 28 | S | 生成 | — | `CREATE_OBJECT` | `Local_14.f_64[0] = OBJECT::CREATE_OBJECT(joaat("S_MRADLERFROZEN_BLKT"), -569.1129f, 2692.749f, 320.63f, true, true, fals` | if (!ENTITY::DOES_ENTITY_EXIST(Local_14.f_64[0]) && (iParam0 |
| 30 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[9], "PL_Idle", true);` | — |
| 31 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[9]);` | if (!ANIMSCENE::IS_ANIM_SCENE_RUNNING(uLocal_182[9], false)) |
| 32 | S | 转场 | — | `state -> 1` | `func_134(cParam0, 1);` | if (ENTITY::IS_ENTITY_IN_VOLUME(Global_35, iLocal_1108[0], t |


### 步骤 5 · 调查畜棚

- **目标**：调查畜棚。
- **脚本**：目标函数 `func_1392`；由阶段函数 `func_813` 调用（行 36408）
- **演员调度**：3 次行为，主要是 ENTER_ANIM_SCENE ×2、SWAP_WEAPON ×1
- **生成**：0 个 CREATE_* 调用点
- **说明**：调查畜棚。脚本用 2 次“进入动画场景” + 1 次“切换武器”来表现推门/查看，属于轻交互段。

**微步骤事件（只列 S/A，共 33 条；另有 B 类 7 条已省略）**

| # | 价值 | 类型 | 对象 | 动作 | 参数（坐标已解析） | 条件 |
|---|---|---|---|---|---|---|
| 1 | A | 行为 | Local_14.f_18[iLocal_903] | `TASK_STAND_STILL` | `TASK::TASK_STAND_STILL(Local_14.f_18[iLocal_903], -1);` | if (func_497(Local_14.f_18[iLocal_903], 0)) |
| 5 | A | 行为 | Global_35 | `TASK_SWAP_WEAPON` | `TASK::TASK_SWAP_WEAPON(Global_35, 1, 1, 0, 0);` | if (func_2008(iLocal_1298, 1)) |
| 6 | A | 行为 | Global_35 | `TASK_ENTER_ANIM_SCENE` | `TASK::TASK_ENTER_ANIM_SCENE(Global_35, uLocal_182[17], "ARTHUR", "PL_OpenDoor", 1069379748 /* Float: 1.48f */, 0, 0, 200` | if (func_2008(iLocal_1298, 1)) |
| 7 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[17]);` | if (!ANIMSCENE::IS_ANIM_SCENE_RUNNING(uLocal_182[17], false) |
| 8 | A | 行为 | Global_35 | `TASK_ENTER_ANIM_SCENE` | `TASK::TASK_ENTER_ANIM_SCENE(Global_35, uLocal_182[17], "ARTHUR", "PL_OpenDoor", 1069379748 /* Float: 1.48f */, 1, 0, 200` | if (func_1395(cParam0)) |
| 9 | A | 行为 | Global_35 | `TASK_PUT_PED_DIRECTLY_INTO_MELEE` | `TASK::TASK_PUT_PED_DIRECTLY_INTO_MELEE(Global_35, Local_14.f_18[0], joaat("AR_ATTACK_TURN_0_DIST_FAR"), 0, 0.5f, 1, 0);` | if (PAD::IS_CONTROL_JUST_PRESSED(0, joaat("INPUT_MELEE_ATTAC |
| 10 | A | 行为 | Global_35 | `TASK_PUT_PED_DIRECTLY_INTO_MELEE` | `TASK::TASK_PUT_PED_DIRECTLY_INTO_MELEE(Global_35, Local_14.f_18[0], 0, 0, 0f, 1, 0);` | if (!func_177(iLocal_908, -2147483648)) |
| 11 | A | 行为 | Local_14.f_18[0] | `TASK_PUT_PED_DIRECTLY_INTO_MELEE` | `TASK::TASK_PUT_PED_DIRECTLY_INTO_MELEE(Local_14.f_18[0], Global_35, 0, 0, 0f, 1, 0);` | if (ANIMSCENE::IS_ENTITY_EXITING_ANIM_SCENE_THIS_FRAME(uLoca |
| 12 | S | 生成 | — | `CREATE_OBJECT` | `iLocal_1019 = OBJECT::CREATE_OBJECT(joaat("P_CS_ADLBLANKET02X"), ENTITY::GET_ENTITY_COORDS(iLocal_1105, true, false), tr` | if (!ENTITY::DOES_ENTITY_EXIST(Local_219[1 /*12*/])) |
| 14 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[12], sParam0, true);` | if (!ANIMSCENE::_0x23E33CB9F4A3F547(uLocal_182[12], sParam0) |
| 15 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[12]);` | if (!ANIMSCENE::IS_ANIM_SCENE_RUNNING(uLocal_182[12], false) |
| 16 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-1065.8, 2576.5, 306.0), 1f, -1, 0.25f, 4, func_494(4, 7));` | if (!ENTITY::IS_ENTITY_DEAD(uLocal_1064[2])) |
| 17 | A | 行为 | uLocal_1064[2] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(uLocal_1064[2], iLocal_1018);` | if (!ENTITY::IS_ENTITY_DEAD(uLocal_1064[2])) |
| 18 | S | 行为 | Global_35 | `TASK_DISMOUNT_ANIMAL` | `TASK::TASK_DISMOUNT_ANIMAL(Global_35, 0, 0, 0, 0, 0);` | if (func_2071(Global_35)) |
| 19 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, func_1936(uLocal_182[13], "CS_MicahBell", "pl_IG8_Micah_Idle_Outside"), 1f, -1, 0` | if (!ENTITY::IS_ENTITY_DEAD(uLocal_1064[2])) |
| 20 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-535.0, 2673.4, 317.9), fVar0, -1, 0.25f, 0, func_494(4, 12));` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[2])) |
| 21 | A | 行为 | 0 | `TASK_STAND_STILL` | `TASK::TASK_STAND_STILL(0, -1);` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[2])) |
| 22 | A | 行为 | iLocal_1084[2] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(iLocal_1084[2], iLocal_1018);` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[2])) |
| 23 | A | 行为 | 0 | `TASK_PAUSE` | `TASK::TASK_PAUSE(0, 2000);` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[0])) |
| 24 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-553.2, 2689.6, 318.8), fVar0, -1, 0.25f, 0, func_494(4, 13));` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[0])) |
| 25 | A | 行为 | iLocal_1084[0] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(iLocal_1084[0], iLocal_1018);` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[0])) |
| 26 | A | 行为 | 0 | `TASK_PAUSE` | `TASK::TASK_PAUSE(0, 4000);` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[1])) |
| 27 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, (-538.4, 2672.8, 318.0), fVar0, -1, 0.25f, 0, func_494(4, 11));` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[1])) |
| 28 | A | 行为 | iLocal_1084[1] | `TASK_PERFORM_SEQUENCE` | `TASK::TASK_PERFORM_SEQUENCE(iLocal_1084[1], iLocal_1018);` | if (!ENTITY::IS_ENTITY_DEAD(iLocal_1084[1])) |
| 29 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[13]);` | — |
| 31 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[14], "pl_Enter_Cabin_to_Shelf", true);` | — |
| 32 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[14]);` | — |
| 33 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[14], sParam0, true);` | if (ANIMSCENE::_0x23E33CB9F4A3F547(uLocal_182[14], sParam0)) |
| 35 | S | 行为 | 0 | `TASK_FOLLOW_NAV_MESH_TO_COORD` | `TASK::TASK_FOLLOW_NAV_MESH_TO_COORD(0, func_473(4, 14), 1f, -1, 0.25f, 0, func_494(4, 14));` | if (!ENTITY::IS_ENTITY_DEAD(uLocal_1064[2])) |
| 36 | S | 生成 | — | `CREATE_OBJECT` | `Local_14.f_64[0] = OBJECT::CREATE_OBJECT(joaat("S_MRADLERFROZEN_BLKT"), -569.1129f, 2692.749f, 320.63f, true, true, fals` | if (!ENTITY::DOES_ENTITY_EXIST(Local_14.f_64[0]) && (iParam0 |
| 38 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[9], "PL_Idle", true);` | — |
| 39 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[9]);` | if (!ANIMSCENE::IS_ANIM_SCENE_RUNNING(uLocal_182[9], false)) |
| 40 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[24]);` | — |


### 步骤 6 · 将马牵引到拴马桩处

- **目标**：将马牵引到拴马桩处。；调查木屋中的动静。
- **脚本**：目标函数 `func_1429`；由阶段函数 `func_828` 调用（行 36821）
- **演员调度**：2 次行为，主要是 PLAY_ANIM ×1、STOP_LEADING_HORSE ×1
- **生成**：0 个 CREATE_* 调用点
- **对白**：2 组对话，共 6 行
  - `WNT1_KILL`（条件触发）
    - 那杂种还在里面？
    - 我搞定他了。
    - 很好。那看起来是匹好马，你应该留下它。
  - `WNT1_SPARED`（条件触发）
    - 你放了他吗？我看到那个小混蛋逃了。
    - 对，我想这天气他也跑不远。
    - 那看起来是匹好马，你应该留下它。
- **说明**：把马牵到拴马桩，同时触发“调查木屋中的动静”。行为只有播放动画与停止牵马，重点是位置与朝向。

**微步骤事件（只列 S/A，共 10 条；另有 B 类 1 条已省略）**

| # | 价值 | 类型 | 对象 | 动作 | 参数（坐标已解析） | 条件 |
|---|---|---|---|---|---|---|
| 1 | S | 生成 | — | `CREATE_OBJECT` | `iLocal_1019 = OBJECT::CREATE_OBJECT(joaat("P_CS_ADLBLANKET02X"), ENTITY::GET_ENTITY_COORDS(iLocal_1105, true, false), tr` | if (!ENTITY::DOES_ENTITY_EXIST(iLocal_1019)) |
| 2 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[26], "pl_leadin", true);` | — |
| 3 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[26]);` | — |
| 4 | S | 行为 | Global_35 | `TASK_PLAY_ANIM` | `TASK::TASK_PLAY_ANIM(Global_35, "mech_animal_interaction@horse@reaction", "reaction_player", 8f, -8f, -1, 66048, 0f, fal` | if (!func_2605(Global_35, Local_14.f_3[0], 0)) |
| 5 | A | 行为 | — | `TASK_STOP_LEADING_HORSE` | `TASK::TASK_STOP_LEADING_HORSE(Global_35);` | if (TASK::GET_IS_TASK_ACTIVE(Global_35, 8)) |
| 6 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(cParam0->f_7375.f_804, "NormalStart", true);` | if (func_2599(cParam0, 0)) |
| 7 | S | 生成 | — | `CREATE_OBJECT` | `Local_14.f_64[0] = OBJECT::CREATE_OBJECT(joaat("S_MRADLERFROZEN_BLKT"), -569.1129f, 2692.749f, 320.63f, true, true, fals` | if (!ENTITY::DOES_ENTITY_EXIST(Local_14.f_64[0]) && (iParam0 |
| 9 | S | 演出 | — | `SET_ANIM_SCENE_PLAY_LIST` | `ANIMSCENE::SET_ANIM_SCENE_PLAY_LIST(uLocal_182[9], "PL_Idle", true);` | — |
| 10 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[9]);` | if (!ANIMSCENE::IS_ANIM_SCENE_RUNNING(uLocal_182[9], false)) |
| 11 | S | 演出 | — | `START_ANIM_SCENE` | `ANIMSCENE::START_ANIM_SCENE(uLocal_182[24]);` | — |


### 步骤 7 · 前往牛棚然后按 找掩护

- **目标**：前往牛棚然后按 找掩护。
- **脚本**：目标函数 `func_2501`；由阶段函数 `func_1929` 调用（行 75194）
- **演员调度**：该阶段以目标/UI 为主，未直接调用 TASK（行为在更深层的子函数里）
- **生成**：0 个 CREATE_* 调用点
- **说明**：前往牛棚并进入掩体，准备迎击奥德里斯科帮。这一段是防守位布置，行为以进入掩体为主。

### 步骤 8 · 继续搜查木屋

- **目标**：继续搜查木屋。
- **脚本**：目标函数 `func_2547`；由阶段函数 `func_1986` 调用（行 76621）
- **演员调度**：该阶段以目标/UI 为主，未直接调用 TASK（行为在更深层的子函数里）
- **生成**：2 个 CREATE_* 调用点
- **说明**：补充搜查木屋（第二次搜索），并生成 1 个对象；对应“漏搜”的补救目标。

**微步骤事件（只列 S/A，共 1 条；另有 B 类 0 条已省略）**

| # | 价值 | 类型 | 对象 | 动作 | 参数（坐标已解析） | 条件 |
|---|---|---|---|---|---|---|
| 1 | S | 生成 | — | `CREATE_OBJECT` | `Local_14.f_55[0] = OBJECT::CREATE_OBJECT(joaat("P_CRD_CHIPBLUE01X"), -558.4589f, 2706.551f, 319.923f, true, true, false,` | if (!ENTITY::DOES_ENTITY_EXIST(Local_14.f_55[0]) && (iParam0 |


### 步骤 9 · 按住 将视线集中在奥德里斯科帮成员上

- **目标**：按住 将视线集中在奥德里斯科帮成员上。
- **脚本**：目标函数 `func_2574`；由阶段函数 `func_2013` 调用（行 77458）
- **演员调度**：该阶段以目标/UI 为主，未直接调用 TASK（行为在更深层的子函数里）
- **生成**：0 个 CREATE_* 调用点
- **说明**：瞄准奥德里斯科帮成员，进入最后的射击教学/战斗提示。

### 步骤 10 · 按住 将视线集中在马上

- **目标**：按住 将视线集中在马上。；安抚马。
- **脚本**：目标函数 `func_2618`；由阶段函数 `func_2069` 调用（行 78797）
- **演员调度**：该阶段以目标/UI 为主，未直接调用 TASK（行为在更深层的子函数里）
- **生成**：0 个 CREATE_* 调用点
- **说明**：可选的马匹互动教学：瞄准马、安抚马。

### 步骤 11 · 靠近马

- **目标**：靠近马。；按住 将视线集中在马上。；使用 轻拍马。
- **脚本**：目标函数 `func_2619`；由阶段函数 `func_2069` 调用（行 78798）
- **演员调度**：该阶段以目标/UI 为主，未直接调用 TASK（行为在更深层的子函数里）
- **生成**：0 个 CREATE_* 调用点
- **说明**：可选的马匹互动教学：靠近马、轻拍马。

## 4. 环境 / 条件对白

这些对话组不在某一步的目标函数里，通常是环境触发、战斗 bark 或条件分支（共 26 组 / 221 行）。

- `WINT1_IG13_P1`（条件触发）
  - 怎么了？
  - 这个家伙刚刚偷袭我！
  - 噢，是吗？
- `WINT1_IG13_P2`（条件触发）
  - 狡猾的兔崽子......要不要杀了他？
  - 不......先别杀......
  - 弄清楚他们来这里的目的，还有科尔姆的下落，
- `WNT1_APPROACH`（条件触发）
  - 看看这是谁......
- `WNT1_BANT4`（条件触发）
  - 你看到其他人吗？
- `WNT1_EXT`
  - 嘿，有人来了！
  - 好像是达奇。
  - 嘿，大家快看，达奇回来了。
  - 有什么发现么？
- `WNT1_EXTRA`（条件触发）
  - 噢，该死的雪。冷到骨头里了。
- `WNT1_GREET`（条件触发）
  - 那钱怎么办？
  - 我希望在那艘船上的事态恶化之前，你已经拿到钱了？
  - 是的......已经和其余的钱一起藏在镇上了。
  - 暂时安全了......但近期肯定不能回去拿东西。
- `WNT1_GREET_B`（条件触发）
  - 所以......你觉得在黑水镇的事，是个陷阱吗？
  - 那么多人？噢，他们知道我们会去。
  - 但那时候船上有钱好吗，有很多的钱。
- `WNT1_INTERA`（条件触发）
  - 科尔姆·奥德里斯科在哪？
  - 和其他人待在一起......在西南部老采矿营地那里，在湖的附近。
- `WNT1_INTERA2`（条件触发）
  - 噢，这个混蛋会交代的......
- `WNT1_INTERB`（条件触发）
  - 你们这些混蛋要干什么？为什么来这里？
  - 我们在准备抢火车，要把铁轨炸了。其他的我一概不知，我发誓！
- `WNT1_INT_CABIN`
  - 带他进来！
  - 盖斯凯尔小姐......
  - 赶紧生火。
  - 琼斯小姐，把我们所有的毛毯都给拿过来。
- `WNT1_INT_WAGON`
  - 艾比盖尔说他快不行了，达奇。
  - 我们得找个地方歇脚。
  - 亚瑟出去找了，我派他先去了。
  - 再不停下的话，我们都会没命的......
- `WNT1_KEEP`（条件触发）
  - 迈卡、亚瑟，继续搜。
  - 亚瑟，去看看那个畜棚里有什么。
  - 迈卡，你去搜木屋，看看我们遗漏了什么。
  - 好的。
- `WNT1_MCS1`
  - 迈卡。
  - 兄弟们。
  - 发现什么了吗？
  - 是的。
- `WNT1_MCS1_LI`（条件触发）
  - 前面是谁？
  - 报上名来！
- `WNT1_MCS2`
  - 离我远点！
  - 迈卡，你他娘的在干什么？
  - 看看我在地下室里面发现了什么。
  - 你性子还挺烈的啊？
- `WNT1_PHOTOA`（条件触发）
  - 看来这个可怜虫曾经也结过婚啊。
  - 这东西既不能吃又不能喝，把它放下吧。
- `WNT1_PHOTOB`（条件触发）
  - 这可怜虫也曾经结过婚啊。
- `WNT1_PLEAD`（条件触发）
  - 其他的我什么都不知道......
  - 求求你......饶了我吧。我保证再也不会出现在你面前，朋友。

## 5. 全关失败条件

来自任务 yldb 的玩家提示（不是全部脚本判定，但覆盖了主要失败面）：

- 帮派成员的马死了。
- 离畜棚太远了。
- 马匹被抛弃了。
- 离木屋太远了。
- 离牧场太远了。
- 达奇和迈卡被抛弃了。
- 木屋中的人被惊动了。

## 6. 全关演员调度概览

| 行为 | 次数 |
|---|---|
| `TASK_PERFORM_SEQUENCE` | 64 |
| `TASK_FOLLOW_NAV_MESH_TO_COORD` | 34 |
| `TASK_FOLLOW_WAYPOINT_RECORDING` | 22 |
| `TASK_STAND_STILL` | 20 |
| `TASK_PUT_PED_DIRECTLY_INTO_COVER` | 11 |
| `TASK_PAUSE` | 7 |
| `TASK_TURN_PED_TO_FACE_ENTITY` | 7 |
| `TASK_SWAP_WEAPON` | 6 |
| `TASK_DISMOUNT_ANIMAL` | 6 |
| `TASK_COMBAT_HATED_TARGETS_IN_AREA` | 6 |
| `TASK_GO_TO_COORD_WHILE_AIMING_AT_ENTITY` | 4 |
| `TASK_HORSE_ACTION` | 4 |
| `TASK_ACHIEVE_HEADING` | 4 |
| `TASK_LOOK_AT_ENTITY` | 3 |
| `TASK_SMART_FLEE_PED` | 3 |
| `TASK_PUT_PED_DIRECTLY_INTO_MELEE` | 3 |
| `TASK_COMBAT_PED` | 3 |
| `TASK_LEAVE_ANY_VEHICLE` | 2 |
| `TASK_ENTER_ANIM_SCENE` | 2 |
| `TASK_GRAPPLE` | 2 |

## 7. 这本书里其他任务的步骤

同一套方法已经跑完 43 个任务（共 215 步），完整数据在 `mission_steps.json`。

| 任务 | 脚本 | 步数 | 前几步 |
|---|---|---|---|
| 老朋友们 `DST1` | `odriscolls1.c` | 1 | 靠近您的马并按住 查看拥有的武器 |
| 西部亡命之徒 `WNT1` | `winter1.c` | 11 | 跟随迈卡 → 跟随达奇 → 保护达奇 → 进入木屋 → 调查畜棚 |
| 利维提克斯·康沃尔到底是谁？ `WNT4` | `winter4.c` | 12 | 干掉火车工程师 → 前往火车货运车厢的前部 → 骑上您的马 → 跟随达奇 → 查看比尔的情况 |
| 真爱易逝：第 3 部分 `MRY1` | `mary1.c` | 7 | 制服切罗尼亚教首领 → 走近切罗尼亚教徒 → 追上杰米 → 解除杰米的武器 → 带杰米返回玛丽处 |
| 美式休息 `MUD2` | `mudtown2.c` | 4 | 打败滋事暴徒 → 从混战中脱身 → 和汤米打架 → 帮助帮派击败滋事暴徒 |
| 绵羊和山羊 `MUD4` | `mudtown4.c` | 11 | 牵着您的马 → 将马拴在拴马桩上 → 进入枪械铺 → 和约翰会合 → 等待牧场工人 |
| 美国田园风光 `UTP2` | `utopia2.c` | 5 | 跟随迈卡 → 攻击守卫并让驿站马车停下 → 攻击敌对帮派成员 → 与迈卡在驿站马车处会面 → 射击挂锁 |
| 广告，美国的新派艺术：第 2 部分 `BRT1` | `braithwaites1.c` | 1 | 返回马车处 |
| 古恨今仇 `BRT3` | `braithwaites3.c` | 8 | 骑马跟随达奇 → 前往达奇处 → 解决守卫 → 等待达奇 → 前往楼上达奇处 |
| 马肉大餐 `GRY2` | `grays2.c` | 4 | 去马厩见约翰和哈维尔 → 追上哈维尔 → 返回哈维尔处 → 解决剩余追捕者 |
| 小镇信步 `GRY3` | `grays3.c` | 5 | 跟随帮派 → 击退伏击者 → 抵御攻击者 → 跟随迈卡 → 杀死格雷家的人 |
| 布施谅解之人 `RXCF1` | `rcm_exconfed11.c` | 1 | 骑上您的马 |
| 赏玩魔术师 `TRE1` | `trelawny1.c` | 10 | 跟达奇交谈 → 进入特里劳尼的篷车 → 跟随足迹走 → 痛殴赏金猎人 → 跟随查尔斯 |
| 金鸟笼 `IND1` | `industry1.c` | 6 | 跟随侍者 → 跟随达奇 → 在院子里与客人交谈 → 将醉汉从市长身边拉走 → 跟随仆人且不要被发现 |
| 放荡狂欢夜 `IND3` | `industry3.c` | 17 | 从裁缝铺购买精品三件套时装 → 跟随特里劳尼前往理发铺 → 在理发铺做发型或胡须造型 → 进入马车 → 跟随特里劳尼前往码头 |
| 文明之乐 `MOB1` | `mob1.c` | 6 | 前往吧台 → 在巷子里打听勃朗特 → 跟随孩子 → 追上孩子 → 在酒馆附近找达奇 |
| 曾经的梦想：第 2 部分 `MRY3` | `mary3.c` | 8 | 前往马厩 → 在马厩与玛丽见面 → 追上买家 → 追上那马车 → 驾车前往一处隐蔽的地方 |
| 善良又慈祥的暴君 `FUS1` | `fussar1.c` | 9 | 跟随达奇 → 跟随格洛丽亚通过洞穴 → 与达奇一起抬起破烂的大门 → 去掩护位置 → 保护哈维尔 |
| 释放野蛮 `FUS2` | `fussar2.c` | 2 | 射击绞绳并解放吊着的工人们 → 解决福萨尔的手下 |
| 快乐易逝 `GNG1` | `gang1.c` | 2 | 跟随莎迪 → 躲避到门后面 |
| 欢迎来到新世界 `GUA2` | `guama2.c` | 1 | 在海岸上搜寻幸存者 |
| 天堂渐行渐远 `GUA3` | `guama3.c` | 14 | 前往瞭望台 → 悄无声息地解决守卫 → 解决守卫 → 安放炸药 → 解决守卫 |
| 伊卡洛斯和朋友们 `GNG2` | `gang2.c` | 2 | 跟随莎迪 → 骑上您的马 |
| 对话的艺术 `NTV2` | `native2.c` | 4 | 与查尔斯一起逃跑 → 骑上您的马逃跑 → 保护门罗上尉 → 跟随查尔斯 |
| 睦邻友好 `TRN1` | `train_robbery1.c` | 3 | 跟随达奇 → 释放马匹以逃跑 → 和达奇以及迈卡一起摆脱追捕者 |
| 范霍恩的喜悦 `TRN2` | `train_robbery2.c` | 3 | 跟随比尔前往伏击地点 → 到达伏击位置 → 前往会面地点 |
| 最真实的自己 `TRN4` | `train_robbery4.c` | 1 | 进入装甲车厢 |
| 为母之道 `AB21` | `abigail2_1.c` | 5 | 与屋子里的艾比盖尔交谈 → 回去工作 → 抬起竖杆以建造栅栏 → 前往格迪斯的房子 → 拿取电报 |
| 老习惯 `LAR1` | `laramie1.c` | 2 | 调查骚乱 → 殴打拉雷米帮的成员 |
| 傻人为父 `MAR2` | `marston2.c` | 7 | 驾驶马车前往草莓镇 → 将马车停在邮局旁 → 取回邮件 → 和杰克一同驾车前往叉角羚牧场 → 返回杰克处 |
| 务农入门 `MR52` | `marston5_2.c` | 1 | 修理围栏 |
| 为父入门 `MR53` | `marston5_3.c` | 2 | 跟随亚伯 → 与杰克一同骑马 |
| 有偿工作 `SAD2` | `sadie2.c` | 2 | 进入内森·柯克的房间 → 踢开门进入内森·柯克的房间 |
| 美国毒物 `FIN2` | `finale2.c` | 13 | 跟随莎迪前往草莓镇 → 追上克里特 → 将克里特拖到绞刑架处 → 殴打克里特 → 强迫克里特上阶梯 |
| 不打不重逢 `MAR6` | `marston6.c` | 1 | 返回大叔处 |
| 相助老友 `SAD3` | `sadie3.c` | 8 | 骑上您的马 → 骑马前往幻彩天空 → 调查畜棚 → 追杀攻击者 → 掩护莎迪 |
| 勤恳劳作的一天 `SAD5` | `sadie5.c` | 8 | 骑上您的马 → 跟随莎迪 → 使用双筒望远镜或带瞄准镜的武器观察犰狳镇 → 做出您的决定 → 在山脊上掩护莎迪 |
| 罗比·莱德劳 `RBT14` | `rcm_bh_shack_escape.c` | 2 | 调查棚屋 → 搜查田地 |
| 安东尼·福尔曼 `RBT15` | `rcm_bh_sd_saloon.c` | 1 | 询问酒保 |
| 伊莱亚斯·格林 `RBT20` | `rcm_bh_skinner_search.c` | 2 | 调查营地 → 调查剥皮帮的地盘传来的枪声 |
| 捆绑的纽带：第 3 部分 `RBWCG4` | `rcm_chain_gang5.c` | 1 | 为这些人购买或配制一些疗伤药 |
| 文明之乐 `RMOB01` | `rcm_mob01.c` | 1 | 询问勃朗特的消息 |
| 文明之乐 `RMOB02` | `rcm_mob02.c` | 1 | 询问勃朗特的消息 |

## 8. 证据与局限

| 项 | 说明 |
|---|---|
| 步骤切分 | 以“目标文本键所在函数 + 该函数最早调用行”为依据 |
| 行为计数 | 阶段函数 + 两层子调用的 `TASK_*` 调用点，不是运行时执行次数 |
| 生成计数 | `CREATE_*` 调用点，数量在参数/表里，未展开 |
| 顺序 | 静态调用行号，不等于状态机执行顺序；分支/可选段可能错位 |
| 失败条件 | 只能抓到同函数内的 `*FAIL/LOST/DEAD` 文本，判定表达式仍在代码里 |

