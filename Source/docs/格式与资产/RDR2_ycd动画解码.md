# RDR2 `.ycd` 动画解码（RSC8 v58）—— 逆向笔记 + 进度

> 目标：把《荒野大镖客2》`.ycd`（clip dictionary）里的骨骼动画曲线解出来，
> 用于在 HTML 预览 + 重定向到骑砍2 28 骨。
> 本文记录**已打通**的容器与通道解码，以及**尚未打通**的骨架环节。

---

## 1. 结论速览

| 环节 | 状态 |
|---|---|
| RPF8（`.rpf`）解密 + 解压 + 提取 `.ycd` | ✅ 已通（见 `tools/rdr2rpf/`、根目录 `README.md`） |
| RSC8 v58 资源头 + RAGE 虚拟指针寻址 | ✅ 已通 |
| ClipDictionary / ClipMapEntry / ClipAnimation / Animation / Sequence 结构 | ✅ 已通 |
| RAGE 动画**通道编解码**（Static/Quantize/IndirectQuantize/Linear/Raw/CachedQuaternion） | ✅ 已通，解出的四元数**模长≈1（单位四元数）**，证明解码正确 |
| **骨架（bone 名/层级/绑定姿势）** | ❌ **未通** —— 需解析 RDR2 drawable（`.ydd/.ydr`）里的 Skeleton 资源；RDR2 drawable 的结构与 GTA V 不同 |
| 重定向 → 骑砍2 28 骨 → TRF → 查看器 | ⏳ 依赖上一项 |

**当前可见产物**：`export/rdr2_decode_preview/index.html`（打开可交互预览解出的动画数据）。

---

## 2. RSC8 v58 容器

`.ycd` 文件 = **16 字节 RSC8 头 + 资源体**。

```
偏移  字段
0x00  Magic  = 0x38435352 ("RSC8")
0x04  Val1   (u32)： bit0-7 = 资源类型ID；bit8-12=压缩；bit13-15=签名保护；bit16-23=加密keyId；bit24-31=加密配置
0x08  Val2   (u64)： systemFlags(u32) + graphicsFlags(u32)（页标志，描述 system/graphics 段大小）
```

资源体 = `system` 段（+ 可选 `graphics` 段）。**RAGE 指针**：`0x50000000 | offset` 指向 system 段，`0x60000000 | offset` 指向 graphics 段（本批 `.ycd` 无 graphics 段）。

> 本仓库提取出的 `.ycd` 已是「RSC8 头 + 已解压资源体」，可直接按上面的方式寻址。
> 注意：`.ycd` 体内的指针是 `0x5001xxxx` 这类值，`offset = ptr - 0x50000000` 就是资源体内的字节偏移。

---

## 3. 结构（本项目实测偏移）

> 说明：RDR2 的外层比 GTA V 多几字节，但 **Animation / Sequence / 通道 部分与 GTA V 完全同构**（已用 NumFrames 交叉验证）。

### 3.1 ClipDictionary（资源体起点 0x00）
外层字段与 GTA V 不同（0x18/0x28 处非指针）。**但可以绕过**：直接扫描 Animation 块（见 3.4），不必先解 ClipDictionary。

### 3.2 ClipMapEntry（实测在 body 0x68 起）
```
+0x00  Hash (u32)        // clip 名（小写）的 JOAAT
+0x04  Unknown (u32)     // 实测=2
+0x08  ClipPointer (u64) // → ClipAnimation
+0x10  NextPointer (u64)
```
验证：`joaat("mech_carry_ped@dead@mount@stow@lt") = 0xd1a2849b` 正落在 +0x00。

### 3.3 ClipAnimation / ClipBase
含 `NamePointer`(→ 名字串，如 `pack:/enter_rf_ped.clip`) + 名字长度，以及 → Animation 的指针。
（body 0x19480 处即 clip 名串所在。）

### 3.4 Animation（本项目按 `Frames/Duration` 特征扫描定位）
```
+0x14  Frames (u16)
+0x16  SequenceFrameLimit (u16)
+0x18  Duration (f32)      // = Frames/30
+0x38  MaxSeqBlockLength (u32)
+0x40  Sequences 块 { ptr(u64)@+0x40, count(u16)@+0x48, cap(u16)@+0x4A }
+0x50  BoneIds  块 { ptr(u64)@+0x50, count(u16)@+0x58, cap(u16)@+0x5A }
```
- `Sequences.ptr` → **Sequence 指针数组**（u64[]）。
- `BoneIds` = 数组，每项 4 字节：`{ BoneId:u16, Unk0:u8, Track:u8 }`（Track 0=位置, 1=旋转）。

### 3.5 Sequence（chunk）——与 GTA V 完全一致（实测）
```
+0x00  Identifier (u32)
+0x04  DataLength (u32)
+0x0C  FrameOffset (u32)        // 帧数据的字节偏移
+0x10  RootMotionRefsOffset (u32)
+0x16  NumFrames (u16)          // ← 与 Animation.Frames 一致（实测 157=157 ✅）
+0x18  FrameLength (u16)        // 每帧步长（实测 12）
+0x1A  IndirectQuantizeFloatNumInts (u16)
+0x1C  QuantizeFloatValueBits (u16)
+0x1E  ChunkSize (u8)
+0x1F  RootMotionRefCounts (u8) // 高4位=位置ref数, 低4位=旋转ref数
+0x20  Data[DataLength]
```

### 3.6 通道编解码（9 类，序号即类型）
```
0 StaticQuaternion   1 StaticVector3   2 StaticFloat   3 RawFloat
4 QuantizeFloat      5 IndirectQuantizeFloat           6 LinearFloat
7 CachedQuaternion1  8 CachedQuaternion2
```
Data 内布局：
```
[0 .. FrameOffset)                    : 通道参数/量化表（按 9 个类型组顺序）
[FrameOffset .. +FrameLength*NumFrames) : 每帧位数据
then 9×u16 通道计数, 再 通道数据(u16/float...)
```
逐通道：`channelDataBit = u16`（`seq = bit>>2`, `idx = bit&3`；CachedQuaternion 另有 quatIndex）。
每帧按 `BeginFrame(f)` 用 **位偏移** 读各通道的 `ReadFrameBits`。

四类值通道：
- **QuantizeFloat**：`value = bits*Quantum + Offset`，每帧读 `ValueBits` 位。
- **IndirectQuantizeFloat**：值表 + 每帧下标位。
- **LinearFloat**：分块（chunk）+ 块起始值 + 差分扫描到 `1` 位（前向差分），每帧前向累加。
- **RawFloat**：32 位 float。
- **CachedQuaternion**：只存 x/y/z 三通道，w = `sqrt(1-x²-y²-z²)`；`QuatIndex` 指示 w 插在四元数哪一位。

旋转取值：`AnimSequence.EvaluateQuaternion(frame)`（type7 走 cached 路径，否则由 4 个 float 通道拼）。

---

## 4. 实测：`mech_carry_ped@dead@mount@stow@lt.ycd`

字典内的 **clip**：
`base, base_ped, base_horse, base_camera, enter_lf, enter_lf_horse, enter_lf_ped, enter_rf, enter_rf_horse, enter_rf_ped`
（`lt` = 左侧；`enter_*_horse/_ped` 即"上马/上人"相关段）

字典内的 **animation**：
`biped_q5@biped@0_0…0_3.anim`、`biped_q5@horse@0_0…0_2.anim`、`prop_q5@tr3@0_0.anim`
→ 说明该 clip 同时驱动 **人(biped_q5)** + **马(horse)** + **道具(tr3)** 三套骨架。

扫到的 4 个 Animation 块：

| 块 | frames | 时长 | boneIds | 有幅度的旋转骨 | 判读 |
|---|---|---|---|---|---|
| 0x13b70 | 157 | 5.20s | 820 | 3（幅度≈0） | **绑定/基准姿势**（全静态） |
| 0x13be0 | 157 | 5.20s | 141 | 7 | 一段过渡（`enter_*` 之一） |
| 0x13c50 | 83 | 2.73s | 6 | 0 | 极小段 |
| 0x13e10 | 157 | 5.20s | 157 | 20 | 主过渡段（幅度最大） |

骨骼名：`.ycd` 内只有根骨名 `SKEL_ROOT` + 占位 `CHANGEME`；**完整骨骼名/层级不在 `.ycd` 内**。

---

## 5. 工具与复现

| 文件 | 作用 |
|---|---|
| `tools/rdr2_ycd.py` | RSC8 体读取 + RAGE 动画通道编解码（纯 Python，移植自 CodeWalker `Clip.cs`） |
| `tools/ycd_decode.py` | 驱动：扫 Animation 块、读 Sequence/BoneIds、解析 |
| `tools/export_anim_json.py` | 导出每骨四元数关键帧 → JSON |
| `export/rdr2_decode_preview/index.html` | 交互预览（gizmo 网格 + 幅度条 + 时间轴） |

```bash
uv run python tools/export_anim_json.py \
  "export/animations/mech_carry_ped/mech_carry_ped@dead@mount@stow@lt.ycd" \
  "export/rdr2_decode_preview/stow_lt.json"
# 打开 export/rdr2_decode_preview/index.html（需本地 http 服务）
```

---

## 6.5 ★ 2026-10-15 重大修正：四元数是**相对 bind 的增量**（不是绝对局部旋转）

本轮把 `.yft` 权威 bind 打通后（见 `RDR2骨架_yft格式.md` §2.9），
**终于能在 RDR2 原始空间做判决性实验**：拿同一段 `walk_slow` 的 404 帧，
从 bind 出发、分别按三种语义 FK，看骨架是否成立：

| 语义 | 公式 | head.z | 双脚前后行程 | 判定 |
|---|---|---|---|---|
| `abs`（旧假设）| `R_pose = q` | 0.15（骨架坍缩）| 0.05 m | ❌ |
| `Xbind` | `R_pose = q ⊗ R_bind` | **−0.50**（整体倒立）| 0.04 m | ❌ |
| **`bindX`（正确）** | **`R_pose = R_bind ⊗ q`** | **0.58** | **0.115 / 0.119 m** | ✅ |

正解下：head.z ∈ [0.573, 0.584]、脚 z ∈ [−0.999, −0.926]、骨盆 −0.038，
与 bind（head 0.649 / 脚 −0.963 / 骨盆 −0.038）自洽，**且双脚有真实前后摆幅** ⇒ 是真走路。

**旁证（为什么会这样）**：多个骨的 `q ≈ 单位阵`，而它的 bind 局部旋转是 **~180°**
（`SKEL_ROOT` q=(1,0,0,0)、`SKEL_L_Clavicle` q=(0,0,0,1)、`SKEL_L_Forearm` q≈单位）——
若按 `abs` 理解，等于**把 bind 旋转整个抹掉**，骨架必崩。所以这恰好证实了本文 §1 里
`RDR2骨架_yft格式.md` 提到的**假设 B**。

**已接线**：`tools/export_gltf_source.py` 现在写
`conv_q(bind_local_quat ⊗ q_anim)`（RDR2 空间先合成、再转 GLTF 空间）。
> ⚠️ 旧流程把 `q_anim` 当节点绝对旋转、拿"idle 第 0 帧"当 rest —— **结构上就是错的**，
> 这是此前所有"重定向动作不自然"的总根因之一。

### 6.6 ⚠️ 遗留缺陷（已定性，**不是**解码器坏）：骨 ID 空间与运行期骨架不重合

> ⚠️ 本节在 2026-10-15 晚**被修正过一次**：最初我判成"`BoneIds` 块读到指针数组混排 ⇒ 损坏"，
> **这个判断是错的**。与"已知能用"的 `stow@lt.ycd` 逐字段对照后证明两文件结构**完全同构**，
> `Bones` 数组本身没坏。真正的问题是下面的**ID 空间**。

**`Bones` 数组的真实结构**（`Animation + 0x50`，`ptr(u64) / count(u16) / cap(u16)`）：

* 元素 **4 字节**：`{ u16 boneId, u16 flags }` —— **骨 ID 在低 16 位**，高 16 位是标志位。
* 数组**按整个 u32 升序排**（RAGE 为二分查找排序），**与 `Sequences[0].AnimSequences` 下标平行**
  ⇒ `AnimSequence[i]` 的骨 = `Bones[i].boneId`。
* 因此看起来"前半段小值、后半段 `0x0101xxxx`"是**排序结果**，不是损坏。

**真正的问题：三套 ID 空间互不重合**

| 空间 | 条目数 | walk_slow 的 114 个 distinct 骨 ID 命中 |
|---|---|---|
| 运行期 dump 骨架 `skel_full.tsv` 的 `f1a` | 131 | **25** |
| `meta_base_player.yft` 的 `+0x1a` tag | 754 | **65** |
| `meta_base_abe.yft` 的 `+0x1a` tag | 310 | 54 |

* `walk_slow` 与 `stow@lt` 命中数是**一模一样**的 25 / 65 / 54 ⇒ 这两个 ID 集合是稳定、一致的
  （同一套全局骨注册表），不是随机噪声。
* 运行期 dump 的 `f1a` **只是这套空间的一个子集**（README §2.5 的"133 核骨"），
  所以 `tag2idx` 会**静默丢掉**不在其中的轨道：

```
walk_slow：[覆盖] 映射成功 15 条 / 丢弃 8 条（丢弃运动量合计 90.5°）
   丢弃 boneId=4126   maxstep=48.4°   ← 全片第二大运动，且 4126 是 .yft 里存在的骨
   丢弃 boneId=33869  maxstep=20.4°
   丢弃 boneId=14415  maxstep=11.7°   ← 14410/11/12 是 Spine0/1/2 ⇒ 14413~14416 应是 Spine3~6
   丢弃 boneId=22798  maxstep= 8.9°
   丢弃 boneId=34606  maxstep= 1.1°
   （14413 / 14414 / 14416 运动量 ≈ 0）
```

**下一步（= 本章最值钱的入口）**：把**源骨架改成从 `.yft` 建** —— ✅ **已完成，见 §6.7。**

---

## 6.7 ★ 2026-10-15 晚：源骨架改建自 `.yft` —— 覆盖率 15 → 23 条轨道、align 覆盖 17 → 21 骨

**做法**（`tools/export_gltf_source.py --skel yft`，配套 `tools/yft_bind.py` 新增导出 `yft_skel.json`）：

1. **基底**：`meta_base_player.yft`（756 骨）的层级 + tag，bind 取合并后的 `yft_bind.json`（1050 tag）。
   节点名：tag 在运行期骨架里查得到就用运行期骨名（**34 根**），否则叫 `T<tag>`。
2. **接回**：map.json 需要但 `.yft` 缺的 6 根手臂 roll 骨
   （`SKEL_L/R_UpperArm_02_01`/`Forearm_01_01`/`Hand_01_01`）从运行期骨架接回来（几何回退）。
3. **重挂父**：把 34 根有名骨挂到它的**运行期父**下（9 根被改，如
   `SKEL_Pelvis→SKEL_Spine_Root`、`SKEL_L_Clavicle→SKEL_Spine2`、`SKEL_L_Hand_01_02→SKEL_L_Hand_01_01`）。
4. **臂链串线**：骑砍臂链是
   `clavicle → upperarm_twist → upperarm_twist1 → foretwist → foretwist1 → hand` 的**线链**，
   而 RDR2 的 roll 骨与手骨是**兄弟**（`Forearm → {Forearm_01_01, Hand_01_01}`）。
   不串线，align 的 `mapped_kids` 配对会落空 —— 实测 `l_foretwist`/`l_hand` 的肢段方向差 **~100°**。
   串线后（`Forearm→UpperArm_02_01`、`Hand_01_01→Forearm_01_01`）降到 **0.02°**。

> **安全性**：`LOC = inv(Gx[父]) @ G[自己]` ⇒ 重挂父/串链**不改变任何有 bind 的骨的世界位置**。
> 逐骨验证：34 根有名骨最大误差 **2e-6**。

⚠️ **过程中发现并修掉一个真 bug**：重挂父后"父索引 < 子索引"不再成立，
而 `build_rest` 与 IBM 累积原本按 `sorted(bones)` 遍历 ⇒ 会拿到未初始化的父
（`KeyError` / 静默用 identity 当父矩阵）。已改为**拓扑序**（`topo_order()`）。

**结果（walk_slow）**：

| 指标 | 旧（运行期骨架） | 新（.yft 骨架 + 串链） |
|---|---|---|
| 动画轨道映射 | 15 条 / 丢 8 条（丢 90.5°） | **23 条 / 丢 0 条** |
| 映射到骑砍的源骨 | 26 | **26**（持平；仅缺 `SKEL_L/R_Finger00`，运行期也没有）|
| align 覆盖骨 | 17 | **21**（补上 `foretwist1`×2、`upperarm_twist1`×2）|
| align 优化口径误差（父骨单映射子骨子集） | mean 19.12° / max 101.80° | **mean 0.02° / max 0.09°** |
| 出厂闸门 `verify_modkit_fbx.py` | PASS | **PASS** |

> 剩余的大误差只在 `l/r_thigh`(64/146°)、`l/r_clavicle`(66.5°) —— 它们的父骨
> （`pelvis` / `spine2`）有**多个**映射子骨，而 align 每骨只能对齐**一支**（选了躯干侧）。
> 这是**度量口径伪影**，不是动画错：thigh 自身的旋转已由 `A_align['l_thigh']` 对齐。

可视验证：`output/verify/strip_v7_{front,side}.png`（PIL 直画两侧关节条）——
正视图里源侧是清晰的行走人形（双臂外下垂 + 双腿交替屈伸）。

---

---

## 6.8 ★ 2026-10-16：批量重产 + 单帧大跳变定性

### (a) 全部 10 个 RDR2 clip 已用新管线重产

见 `README.md` §0.5i。要点：**align 覆盖统一 21 骨**、align 子集误差 **0.01~0.12°（max 0.09°）**、
**10/10 过 `verify_modkit_fbx.py`**；`drop_body` 的 `CHECK_POS` 从 **1.295 → −0.028**（README N5 已修）。

### (b) 单帧大跳变：多骨同帧出现

| clip | 帧 | 骨（幅度） |
|---|---|---|
| walk | **202**（=404/2） | R_Foot 64.7°、L_Calf 52.0°、R_Calf 50.2°、T4126 48.4° |
| stow@lt | 83 / 120 | L_Foot 180.0°、Root 163.9°、T34606 126.0° |
| carried_mount | 51 | L_Foot 166.5°、Root 121.5° |
| remove_lt | 89 / 126 | R_Foot 130.0°、Root 95.4° |
| throw_body | 40 / 45 | L_Toe0 179.7°、R_Toe0 96.4° |

**已排除**：四元数符号翻转（全 clip `dot<0` = 0 处）；帧区定长假设不成立
（`Frames == NumFrames`，帧区 `[frame_off, frame_off+framelen*nframes] ⊆ data`）；
`MaxSeqBlockLength` 分块（该字段是**字节长度**，非帧数）。

**特征**：跳变是**台阶**不是尖峰（跳变后数值继续平滑），且只影响少数骨。
⇒ 更像**真实快速动作**（foot-plant/摔落）或**段边界**（walk 恰在 404/2）。

**处置**：`tools/export_anim_json.py` 新增 `repair_isolated_jumps()` —— 只修
"前后都平滑、仅单帧突跳"的**孤立尖峰**（θ>20°/20°，且首尾<10°）。实测**触发 0 次**
（观察到的都是台阶），这类**不做插值修复**，以免抹掉真动作。

**下一步**：拿 `walk_slow` f190~f210 与游戏内同帧画面对拍，判定真动作 vs 解码错。
若确认是解码错，重点查 `ChQuantFloat` 的逐帧 bit 读取（`chQuantFloor` 的
`ValueBits` 在 chunk 边界是否变宽）。

---

## 6.9 ★ 2026-10-16：通道层两个真 bug —— `CachedQ2` 与 `Track` 过滤

### (a) `CachedQ2`(type 8) 被漏掉 ⇒ `SKEL_L_Thigh` 整条被误杀

`SKEL_L_Thigh`(tag 65478) 的 animseq 槽位是 **`QuantFloat,QuantFloat,QuantFloat,·,CachedQ2`**，
而 `SKEL_R_Thigh` 是 `QuantFloat,QuantFloat,QuantFloat,CachedQ1`。

`parse_sequence` 原先**只在 `C_CACHED_Q1` 时置 `is_type7_quat`** ⇒ L_Thigh 落到"通用路径"，
把 3 个量化的**位移**浮点当成四元数 x,y,z ⇒ `|q| = 0.182` ⇒ 被导出器的"单位四元数"判据过滤掉。
**结果：走路只有右大腿有旋转轨**（`maxstep` 榜上永远没有 `SKEL_L_Thigh`）。

**修复**：`CachedQ1/Q2` 走**同一条**缓存四元数路径（只存 3 分量、w 由模长补全；
`quat_index` 决定 w 插在第几位）。修后 `|q| = 1.0000` 精确成立，`L_Thigh` 的 maxstep = **65.8°**
（走路本来就该是大腿摆幅最大）。

### (b) `Track` 字节一直没被用 ⇒ 过滤靠启发式

`Bones` 元素 = `{u16 boneId, u8 Unk0, u8 Track}`（README 早就写了 **Track 0=位置 / 1=旋转**），
但导出器用的是"通道数 ≥3 + 单位四元数"的启发式。实测本文件：

| Track | 槽位形态 | 含义 |
|---|---|---|
| `0x01` | `qF,qF,qF,Q7` / `·,·,·,Q7` / `qF,qF,qF,·,Q8` … | **旋转轨（共 24 条）** |
| `0x3b` / `0x8a` / `0x06` | `sF,sF,·,·,Q8` … | 位置轨 |
| `0x00` | 单通道 `qF` | 位移分量 |

**修复**：导出器改为 `Track != 1 → skip`（保留单位四元数做二次兜底）。

### (c) 效果（10 个 clip 全量重产，v14）

| clip | 轨数(旧→新) | 映射骨 | CHECK_POS |
|---|---|---|---|
| walk | 23 → **24** | 28 | −0.090 → **−0.0116** |
| stow_lt | 24 → **27** | 28 | 0.037 |
| pickup_body | 29 → **31** | 28 | 0.107 |
| remove_lt | 24 → **27** | 28 | 0.000 |
| putdown_body | 26 → 21 | 28 | 0.216 |
| throw_body | 29 → 21 | 28 | 0.240 |
| 其余 4 个 | 持平 | 28 | ≈0 |

> putdown / throw 的**下降是修对**：旧启发式把 `Track≠1` 的**位置轨**当成旋转轨收进来了。

10/10 `verify_modkit_fbx.py` **PASS**；align 覆盖 21 骨；align 口径误差 mean **0.022° / max 0.093°**。

### (d) 残留：单帧台阶（仍未解）

修完 (a)(b) 后再看跳变分布，`SKEL_L_Thigh` 是**干净的**（中位 3.91°，仅 **1 帧** >30°）：

| 骨 | max 跳变 | 帧 |
|---|---|---|
| SKEL_L_Thigh | 65.8° | **121** |
| SKEL_R_Thigh | 19.6° | 202 |
| SKEL_R_Foot / L_Calf / R_Calf | 64.7 / 52.0 / 50.2° | **202** |

注意 **walk 的 121 / 202** 与 **stow 的 120 / 83** —— 120/121 相邻，且这些帧都落在
`chunk=10` 的边界附近（120=12×10、202=20×10+2、121=12×10+1、83=8×10+3）。
⇒ 仍是**"chunk 边界附近偶发单帧错"**的嫌疑最大；下一步应重点查
`ChQuantFloat` 的 `ValueBits` **是否按 chunk 变化**（Sequence 结构里有
`QuantizeFloatValueBits @+0x1C` 与 `IndirectQuantizeFloatNumInts @+0x1A` 两个字段，目前只用了全局值）。


---

## 7. ★ 2026-10-17：walk 修好了（三个真 bug + 一次 clip 认错）

> 产物：`export/npc/player/player_zero_walk.glb`（80 骨 + `rdr2_walk` 4.0 s），
> 查看器 `根目录「打开查看器.bat」`（8788 → 首页「角色动画」）。
> 验收图：`work/npc/verify/bind_f000..003.png`（Blender 渲染）、`web_*.png`（网页查看器）。

### 7.1 bug①：缓存四元数的第 4 分量不是"插到 `quat_index` 位"

`AnimSequence.evaluate_quat` 原先照搬 CodeWalker 的 `QuatIndex` 语义
（`qi=1 → (x, n, y, z)`）。**RDR2 不是这样**：3 个显式通道就是 `(x, y, z)`，
缓存通道就是 `w`。

判决性证据（同一条数据、只改这一处）：

| 场景 | 旧（按 quat_index） | 新（恒 x,y,z,w） |
|---|---|---|
| `idle` 的 `SKEL_R_Clavicle` | `(0,1,0,0)` = **180° 翻转** | 单位阵 |
| `walk_slow` 的 `SKEL_Spine6` | `(0,0,1,0)` = **180°** | 单位阵 |
| `walk_slow` 的 `SKEL_R_Forearm` | `(0,1,0.011,0)` = **180°** | 小角度 |
| 整段 FK 的 `head.z` | **0.35**（脊柱塌、手臂横张） | **0.64**（直立） |

实现：`tools/rdr2_ycd.py` 顶部 `QUAT_INDEX_MODE='w'`（保留 `'cw'` 可回退）。
> 这正是 HANDOFF 里"9 根骨带 ~180° 常量偏移"的来源 —— 不是骨架不匹配，是解码摆放错。

### 7.2 bug②：一直拿"转身"当走路

`.ycd` 里每个 clip 通过 **Clip → ClipAnimation → Animation** 的指针链取动画。
这次把链接通了（Clip 在 `+0x40` 存 `{ptr,count,cap}` 指向 ClipAnimation 指针数组；
ClipAnimation 的 `+0x18` 是时长、`+0x28` 时长 f32、`+0x30` 指向动画名字符串）：

| clip | ClipAnimation | 名字 | 时长 | 帧数 |
|---|---|---|---|---|
| **move**（走路） | `0xf590` | `biped_q7@biped@0_0.anim` | **4.00 s** | **121** |
| turn_l1 / l2 / r1 / r2 | `0xf7c0` | `biped_q5@biped@0_0.anim` | 13.43 s | 404 |

⇒ 之前一直渲染的 **404 帧那条是 turn（原地转身）**，所以 `SKEL_L_Thigh` 才会出现
"整段 180°"（转身时腿要拧过去）。**走路要用 121 帧那条**。

### 7.3 bug③：参考骨架 rest ≠ `.yft` rest ⇒ 每骨常量偏移（de-bias）

`move` 是 **q7** 骨骼的动画，我们用 `meta_base_player.yft`（metaped）当参考，
两者在部分骨上 rest 朝向不同 ⇒ 每根骨带一个常量。做法：
`C = 四元数均值(q)`，`q' = C⁻¹ ⊗ q`，姿态仍用 `R = R_bind ⊗ q'`。

- 加 de-bias 前：`head.z` 0.44~0.48（躯干前倾）
- 加 de-bias 后：`head.z` **0.64~0.65**，双腿交替、手在体侧

### 7.4 bug④（顺带）：Blender 默认 24fps

glTF 关键帧是按**秒**写的（帧号/30）。Blender 默认 24fps 会把 121 帧解释成 151 帧
⇒ 动作慢 25%。`blender_bind_player_walk.py` 已显式 `scene.render.fps = 30`。

### 7.5 现在的状态 & 残留

✅ 直立、双腿交替、脚不离地错位、手在体侧、循环 4 s。
⚠️ **残留 1**：手臂基本停在 bind 的 A-pose 附近（动画本身的臂轨很小；已加
`--clamp-arms 22` 把臂/锁骨相对均值的摆幅限到 22°，避免偶发横张）。
⚠️ **残留 2**：左半身（`SKEL_L_Thigh` / `SKEL_L_UpperArm` / `SKEL_L_Calf`）的通道
仍然可疑 —— 右大腿 43° 摆幅、左大腿却是 180°；左小腿只弯 6°（走路应 40°+）。
怀疑左半身的通道参数/帧比特仍有错位（左骨的序列普遍比右骨"少通道"，如
`QuantF|None|None|Cached`）。下一步：拿一条左右对称的 clip 逐骨对拍
左右同名骨的四元数曲线，定位是"通道头"还是"帧比特"错位。

### 7.6 复现

```bash
cd "D:/BrainMaker/大镖客2解包分析"
UV="C:/Users/yaodongcheng/AppData/Roaming/com.brainmaker.client/cowork-updates/uv-binary/uv.exe"
BL="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"

# 1) ycd → JSON（fix① + de-bias + 臂摆幅钳制）
"$UV" run python tools/rdr2_walk_fix.py   "export/animations/mech_loco_m/mech_loco_m@generic@normal@unarmed@walk_slow.ycd"   work/npc/anim/walk_move_q7_clamp.json --anim 0 --debias --clamp-arms 22

# 2) JSON → glTF（.yft 骨架 + bindX）
"$UV" run python tools/export_gltf_source.py work/npc/anim/walk_move_q7_clamp.json   "D:/BrainMaker/骑砍2动画重定向/input/source/rdr2/rdr2_walk.gltf" --skel yft --name rdr2_walk --anim 0

# 3) glTF → 蒙皮 glb + 4 帧验收图
"$BL" -b --python tools/blender_bind_player_walk.py

# 4) 看（带蒙皮的 glb）
根目录「打开查看器.bat」

# 5) 纯骨骼页（rdr2_actions.html）里那 10 个 clip 一起重产 + 重建页面
"$UV" run python tools/rebuild_rdr2_clips.py
"$UV" run python tools/build_skel_actions_viewer.py
```

> ⚠️ `export/skeleton_runtime/rdr2_actions.html` 的数据源是
> `骑砍2动画重定向/input/source/rdr2/*.gltf`。这批 gltf 是上午用旧解码器产的，
> 所以**页面里一直是畸形骨架**；2026-10-17 下午已用修好的解码器全部重产
> （`tools/rebuild_rdr2_clips.py`），页面同时重建。
> 旧的 walk 变体（`rdr2_walk_ok / _fixed / _clean / _yft`）已移到
> `input/source/rdr2_bak_20261017/_old_variants/`，避免下拉框里混进旧数据。

### 7.7 ★ 第二轮：腿"横着摆"→ 真前后摆（2026-10-17 晚）

第一轮修完后骨架直立了，但**腿是往左右两侧张的**，不是前后迈步。三个追加修正：

**(a) 大腿骨的参考帧差 90°（`--fix-thigh-axis`）**
`.yft` 里大腿的 local Z → 世界 X（矢状轴），而动画数据把摆动放在 local Y（= 世界的横轴/外展轴）。
⇒ 数据本身没错，是两套骨骼的 roll 约定差一个绕 X 的 90°。按 `q' = D⁻¹ q D`（D = 绕 X −90°）
共轭一次即可。判决数据（121 帧走路的双脚轨迹）：

| | 左脚 X/Y 行程 | 右脚 X/Y 行程 |
|---|---|---|
| 修前 | **0.52 / 0.47**（横向 0.52，横着摆） | 0.48 / 0.41 |
| 修后 | **0.19 / 0.68**（横向 0.19、前后 0.68） | 0.16 / 0.69 |

只有大腿要修 —— 小腿 rest 本身带 72° 绕 Z，local Z 已经指向世界 X，动了反而坏。

**(b) `SKEL_L_Thigh` 的 z 通道是爬升假数据（`--repair-ramps`）**
该通道 15 bit / quantum 1.3e-4 / offset −4.31，整段从 0 匀速爬到 −4.31、**占满量程**
（x/y 和右腿完全对称、都是好的）。判据：值域 > 60% 量程 + 单调 + 首尾差 > 80% 值域 ⇒ 判死，
压成常量。修后该骨 maxstep 179° → 47°（剩下的是别的抖动，见 (c)）。

**(c) 左大腿剩余的跳变用右腿轨道按半周期复制（`--mirror-left-leg`）**
走路左右腿是"同动作、差半周期"。对右大腿 z 做自相关得**周期 40 帧（corr 0.996）**，
于是 `L[t] = R[(t+20) % N]`。修后左右脚印的前后行程都在 0.34~0.69 m、横向量 < 0.25 m。

**验收**：`work/npc/verify/side_0*_f*.png`（正侧机位，能直接看前后迈步）、
`work/npc/verify/web_v3.png`、`skel_v3.png`。


**(d) 手臂"僵尸感"：de-bias 把"手臂放下"的常量也一起减掉了（`--keep-arm-bias`）**

腿修好后仍然像僵尸 —— 因为**手臂一直张在 bind 的 A-pose**。原因：手臂骨的整段旋转里带着
一个常量（≈15~30°），它的物理含义正是"把手臂从 A-pose 放下来"。第一轮的 de-bias
把每根骨的均值减掉 ⇒ 顺手把这个"放下来"也减没了。

实测三组手的位置（世界坐标，静息手在 `(±0.58, −0.13, 0.09)`）：

| 变体 | 左手 x | 左手 z | 结论 |
|---|---|---|---|
| 全骨 de-bias（旧） | 0.52~0.62 | −0.01~0.21 | 张在 A-pose（僵尸） |
| **手臂不 de-bias（现）** | **0.29~0.36** | **−0.13~−0.03** | 手臂自然下垂、贴体侧 |
| 手臂不 de-bias + 再共轭 90° | 0.57~0.65 | 0.04~0.29 | 又抬起来了（手臂**不要**用大腿那个共轭） |

⇒ 手臂要"保留常量"，大腿要"去掉常量 + 绕 X 共轭"，两者不能一刀切。
现在的配方：`--debias --keep-arm-bias --fix-thigh-axis --repair-ramps
--mirror-left-leg --clamp-arms 22`。


**(e) 根骨(tag 0)的旋转是 **mover（实体朝向）**，根本不该套到骨架根骨上（`--drop-root`）**

用户反馈"盆骨/上身前后晃"。量化后确认：**头部 Y（前后）摆幅 0.29 m、身体 yaw 摆幅 163°**
—— 人在走路时不可能这样。根因：根骨这条轨道的 q 其实是**实体的朝向（mover rotation）**，
游戏里作用在 entity 上；我们把它当骨骼旋转塞进根骨，根骨 bind 又是个 180° 翻转，
于是"偏航"被解成了"绕一条斜轴来回转"，整个人跟着摇。

| 处理 | 身体 yaw 摆幅 | 头部 Y 摆幅 | 左脚 Y/X | 右脚 Y/X |
|---|---|---|---|---|
| 套用根骨轨（旧） | **163°** | **0.29 m** | 0.36 / **0.25** | 0.73 / 0.16 |
| **丢掉根骨轨（现）** | **0°** | **0.08 m** | 0.40 / **0.05** | 0.41 / **0.06** |

丢掉后是干净的"原地走"：不摇、不转，双脚前后 0.40 m、横向只有 5~6 cm。

> 顺带：即使把根骨改成"世界左乘"，也救不回来（yaw 仍 163°）⇒ 这条轨道不是姿态数据。
> 对 turn_l1/r1 这类转身 clip 同理：转身是 mover 干的，原地预览应该丢掉。


**(f) 膝盖"在大腿根就折"：换片段 + 手臂下压（2026-10-17 深夜）**

用户反馈"前进时腿在大腿根就折了、膝盖不对"。量化后确认：不是膝关节点错，是**小腿几乎不转**
（`walk_slow` 那条 move 的小腿只有 3~6°，而正常走路膝弯 40°+），所以整条腿像在髋关节处整体折叠。

原因：`walk_slow.ycd` 的 `move` 是 **q7（低细节 LOD）** 版本。同一目录里
`mech_loco_m@character@arthur@normal@unarmed@walk_interior.ycd` 的 **block1（398 帧 / 13.2 s，q5）**
才是完整步态：

| 片段 | R/L 大腿 | R/L 小腿 | 抬脚高度 |
|---|---|---|---|
| `walk_slow` move（q7，旧） | 40° / — | **3~6°** | 0.08~0.12 m |
| **`walk_interior` block1（q5，现）** | 40~62° | **50~56°** | **0.23 m** |

换过去之后膝盖会正常屈伸。另外补了两处：

* **`--arms-down 45`**：这条片段的臂轨本身不含"把手臂放下"的量，绑定态是 A-pose ⇒ 在导出时
  给两根大臂加一个**世界空间绕 Y 的 45°** 常量（`q_local = (Rw⁻¹ q_world Rw) ⊗ r`）。
* ⚠️ 这里踩了一个坑：算 `Rw`（骨的世界 rest 旋转）必须按**拓扑序**累积。
  之前按索引号遍历，重挂父之后"父 < 子"不成立 ⇒ Rw 全错 ⇒ 加的手臂旋转落在错误轴上
  （表现：改成"手往上抬"）。改成拓扑序后手从 `x0.58/z0.15` 落到 `x0.41/z−0.03`。

验收：`work/npc/verify/int45b_f001.png`（正视，手臂垂在体侧）、
`work/npc/verify/side_int_0*.png`（侧视，能清楚看到后腿膝盖弯起、脚跟离地）。

> 注：手臂数据本身只有 ±5~20° 的前后摆，所以摆臂偏小（真人走路约 ±25°）；
> 要更明显只能等 q5 的走路片段（见下）。


**(g) ★★ 真正的元凶：关节位置整体错了一段（2026-10-17 深夜，用户连续两次指出才挖到）**

`.yft` 的 bind 里每根骨记的 `pos` 是**骨末端(tail)**。导 glTF 时如果直接把它当节点位置，
那么"大腿关节"就落在**膝盖**上、"小腿关节"落在**脚踝**上 —— 而 glTF/Blender 里
**关节节点就是旋转轴心**，于是每根骨都在比自己低一段的位置转：

| 关节 | 修复前 head z | 修复后 head z | 应该是 |
|---|---|---|---|
| SKEL_L_Thigh | **−0.481**（膝盖） | **−0.038** | 髋 |
| SKEL_L_Calf | **−0.902**（脚踝） | **−0.479** | 膝 |
| SKEL_L_Foot | −0.952 | −0.884 | 踝 |
| SKEL_L_Toe0 | −0.979 | −0.987 | 趾 |

所以"走路时腿在大腿根就折了"—— 因为整条腿的转轴都比真实关节低一段。

**修法**：
1. `export_gltf_source.py`：关节位置 = **本骨 head = 父骨 tail**（`HEADW[i] = pos(parent)`），
   局部平移取 `R_parentᵀ·(H_i − H_parent)`；旋转部分不变。
2. `blender_bind_player_walk.py`：权重骨段改成 **本骨 head → 子骨 head**
   （旧写法是"父骨 head → 本骨 head"，那是修复前才成立的对应关系，改完会整体错一格）。
3. 顺带补了**逐帧落地**：`.ycd` 的位移轨没导，脚会飘；按帧把根骨上下平移，让双脚踩地。


### 7.8 ★ 双向对拍（2026-10-17 晚，用户要求）

**方向 B：我们的走路 → 骑砍2 官方骨架**（用项目现成管线，最可信的一侧）

```bash
cd "D:/BrainMaker/骑砍2动画重定向"
uv run python pipeline/run_retarget.py --rig rdr2 --clip rdr2_walk --name rdr2_walk_check --pose align
# → output/fbx/rdr2_walk_check.fbx + output/trf/rdr2_walk_check.trf
blender -b --python ../大镖客2解包分析/tools/xcheck_rdr2_on_bannerlord.py
```

结果：骑砍2 28 骨小人播我们的走路 → **正常步态**（`work/npc/verify/bl_rdr2walk_1.png`），
量出来的膝角 **最大 50°**、左右交替（`l膝21° r膝50°` 这类）。

**方向 A：已知正常的走路 → 我们这套 RDR2 骨架**

用 `tools/make_synth_walk.py` 生成一条教科书走路（大腿 ±25°、膝 0~55°），走同一条导出/绑定管线：
`work/npc/verify/synth_walk_proof.png` —— 膝盖位置、弯曲、重心都正常。
（另写了 `tools/xcheck_ue_rdr2.py` 想做 UE 002_01 → RDR2 的世界旋转拷贝，
但 002_01 这条本身是站立/待机，且跨骨架世界拷贝还需要 rest-aware 处理，暂留作工具。）

**结论**：骨架 ✅、蒙皮 ✅、解出来的走路数据 ✅。RDR2 角色看起来"在大腿根折"，
是因为 **Arthur 的长风衣盖住了膝盖**，而风衣下摆是绑在大腿上的 —— 腿一摆，下摆就在
髋部折起来，视觉上像腿在那儿折。下一步如果要好看，应该改**风衣下摆的权重**
（挂到 pelvis/spine 让它垂，而不是跟着大腿转），而不是继续动骨架。

> 教训：之前只量了"脚的前后/横向行程、头部高度"，这些指标在轴心错位时**照样正常**，
> 所以一路没发现。以后验收必须直接打印**关节世界高度**（髋/膝/踝），而不是只看末端轨迹。


### 7.9 ★ 更正：RDR2 骨架**是好的**，问题在 `.ycd` 的解码（2026-10-17 深夜）

上一节我用"我们的走路 → 骑砍2 骨架"推断"数据没问题"，这个结论**错了**（那条链路上还叠了 20 骨映射，
躯干扭不一定出在数据侧）。用更干净的一条链路重做：

**UE 002_01 走路（已知正常）→ rest-aware 增量套到 RDR2 骨架 → 用 RDR2 网格渲染**
（`tools/bake_ue_walk_to_rdr2.py`，产物 `export/npc/player/player_zero_ue_walk.glb`）。

结果：**正常走路** —— 前后迈步、膝盖正常屈伸、手臂随动。⇒ **RDR2 骨架 + 蒙皮 ✅**

（第一版这条我判断错了：只看两帧静止图就说"不像走路"，实际连续播放是正常步态。教训：
判定动作要看**多帧/连续**，不能拿单帧下结论。）

同时说明：`.ycd` 解出来的那条走路在**同一套骨架、同一个网格**上明显僵硬 —— 两者的唯一差别就是数据。
⇒ 剩下的战场在 **`.ycd` 解码（每根骨的参考帧 / 旋转轴）**，不在骨架。

这条 UE 重定向还顺手补了两处：
* `neck_01 → SKEL_Neck1`（原来只喂 Neck0，头显得前伸）；
* 把 UE 骨盆的竖直起伏（+0.06 m）搬到根骨上（原来骨盆"定死"，重心不上下动）。


### 7.10 运行期骨架取证（2026-10-17 晚，游戏内 dump）

新工具 `tools/dump_live_skeleton.py`（管理员权限，从 RDR2 进程读骨架）：

* 骨记录 = 0x50 字节：`+0x00` 骨名指针 / `+0x20` 局部四元数 / `+0x30` 位置 / `+0x40` scale
* 定位法：扫骨名字符串 → 找指向它的指针 → 沿 0x50 步长验证连续记录 → 再往前/后扩
* 实测：`@0x26BDDB60100`，**124 根 ped 骨**（SKEL_ROOT / Spine_Root / Pelvis / Thigh… / Pelt* / Tail*）

**关键发现 1**：连拍 60 秒（120 次采样）**0 根骨在动** ⇒ 这份是**静态 rest 模板**，
不是"当前姿态"。也就是说 —— **我们终于拿到了游戏真正的动画参考骨架 rest**。

**关键发现 2**：这份 rest 与 `meta_base_player.yft` 的 bind 逐骨差 **60~180°**
（Thigh 99.6°、Calf 110.8°、Clavicle 116.8°、Head 179.9°…）⇒ 之前拿 `.yft` bind
当参考系是**根本性错误**，这也解释了为什么"每根骨都要打一个不同的 90°/常量补丁"。

**还没打通**：用这份 rest 做世界增量重定向，姿势仍然崩（父子表只有 108/124 能对上，
模板层级可能与动画骨架不完全一致）。下一步：
1. 抓到**会动的那份骨架实例**（扫描要按结构找，而不是只找某个骨名串的引用）；
2. 逐帧与 `.ycd` 解码曲线对拍，定死每根骨的参考帧。

**仍然没解决的**：手臂摆动幅度偏小（≈±10°）（该 clip 臂轨本来就只有 ±5~20°）；
膝弯幅度很小（小腿轨只有 3~6°），走动更像"溜达"而不是标准步态 —— 怀疑这条 `move`
是 q7（低细节 LOD）版本，真正的 q5 走路不在这一个 `.ycd` 里。下一步应在游戏包里
找 `mech_loco_m@...@walk.ycd` 这类文件，取 q5 的 move 段。

---

## 8. 未完成 & 下一步（2026-10-15 视角，保留）

1. **骨架（关键阻塞）**：需要 RDR2 `biped_q5` 骨架的 **骨骼名 + 父子索引 + 绑定姿势矩阵**。
   - 来源应在 drawable（`.ydd/.ydr`）里的 **Skeleton** 资源；
   - GTA V 的 Skeleton VFT 在 RDR2 drawable 中不匹配（实测），需另找 RDR2 drawable 定位方式；
   - 拿到后可把动画的 `BoneId`(u16) 映射到骨骼名，再按名映射到骑砍2 28 骨。
2. **补全 Animation 扫描**：当前靠 `frames/duration` 特征扫到 4 块；补上 ClipDictionary→ClipAnimation→Animation 的指针链可精确对应 clip。
3. **重定向**：参照 `D:/BrainMaker/骑砍2动画重定向`（`pipeline/rigs/*`、`run_retarget.py`）新增 `rdr2_biped` rig 映射，出 FBX + TRF。
4. **查看器**：按该仓 `viewer/` 约定新增 dataset。
