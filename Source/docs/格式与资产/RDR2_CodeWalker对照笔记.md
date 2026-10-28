# RDR2 动画格式 · 与 CodeWalker/AnimKit 权威对照（2026-10-16）

> 目的：把我们从零逆向的 `.ycd` 解码器，与**社区权威实现**逐行对照，判定"单帧台阶"到底是解码 bug 还是真实数据。
> 结论：**我们的解码器与权威实现逐行一致；唯一分歧（CachedQuaternion2）是我们对、CodeWalker 缺**；
> **"单帧台阶"不是通道解码 bug**。同时**拿到了社区工具链与教程清单**（本节末尾）。

---

## 1. 拿到了什么（网络可达性确认）

| 来源 | 内容 |
|---|---|
| `codeload.github.com/dexyfex/CodeWalker/zip/refs/heads/master` ✅ | **CodeWalker 全源码**（3.7 MB）→ `CodeWalker.Core/GameFiles/Resources/Clip.cs`（**4466 行，RAGE 动画权威实现**）|
| `codeload.github.com/citizenfx/AnimKit/zip/refs/heads/master` ✅ | **AnimKit 源码**（1.6 MB）→ `Core/{Asset,OnimFile,OadFile}.cs` + **`Core/Libs/CodeWalker.Core.dll`**（dexyfex 的编译版库，`.NETStandard 2.0`）|

两者已落在 `tools/ref/`（`CodeWalker-master/`、`AnimKit-master/`）。

**关键可用性**：`CodeWalker.Core.dll` 是 **netstandard2.0** ⇒ **.NET 9 可直接引用**（不必买 CodeX/不必联网）。
已建好探针工程 `tools/ref/CWProbe/`（`dotnet run -- <ycd> <chunkOffsetHex> <animSeqIndex>`）。

## 2. 逐行对照结果：我们的解码器 = 权威实现

| 环节 | 对照结论 |
|---|---|
| `AnimChannelType` 枚举 | 0 StaticQuaternion … 4 QuantizeFloat, 5 IndirectQuantizeFloat, 6 LinearFloat, **7 CachedQuaternion1, 8 CachedQuaternion2** ✅ 完全一致 |
| **Sequence 结构（32B 头）** | `+0x00 Unknown_00h / +0x04 DataLength / +0x08 Unused / +0x0C FrameOffset / +0x10 RootMotionRefsOffset / +0x14 Unused / +0x16 NumFrames / +0x18 FrameLength / +0x1A IndirectQuantizeFloatNumInts / +0x1C QuantizeFloatValueBits / **+0x1E ChunkSize** / +0x1F RootMotionRefCounts / +0x20 Data` ✅ **与我们的 README 逐字节相同** |
| `GetBits` / `ReadBits` / `BeginFrame` / `ReadFrameBits` | ✅ 逐行一致（`ChannelFrameOffset = (FrameOffset + FrameLength*f)*8`）|
| `AnimChannelQuantizeFloat` | ✅ 一致：`ValueBits/Quantum/Offset` 全局，`ReadFrame: bits=ReadFrameBits(ValueBits); val=bits*Quantum+Offset`（**无 chunk**）|
| `AnimChannelLinearFloat` | ✅ 一致（含 `numChunks = ceil(nFrames/ChunkSize)` 的全套 delta 扫描）|
| `AnimChannelCachedQuaternion` | ✅ 一致：`w = sqrt(max(1-\|x\|²-\|y\|²-\|z\|², 0))`，x/y/z 取 `Channels[0..2]` |
| `ParseData` 通道遍历顺序 | ✅ 一致（9 类型组 → 组内 index，帧循环同序）|
| `EvaluateVector`（通用路径）| ✅ 一致（StaticVec3/StaticQuat 展开 + 其余按 float 收 4 个）|

### 2.1 唯一分歧：`CachedQuaternion2`（**我们对，CodeWalker 缺**）

CodeWalker `EvaluateQuaternionType7`：
```csharp
var t7 = Channels[3] as AnimChannelCachedQuaternion;   // CachedQuaternion1
if (t7 == null) t7 = Channels[4] as AnimChannelCachedQuaternion;   // ← CachedQuaternion2 在这里被支持
```
**它明确支持 slot 4 的 Q2** —— 但入口被 `IsType7Quat` 门控，而 `ParseData` 里**只对 `CachedQuaternion1` 置位**（`Clip.cs:2526`）。
⇒ **Q2 的骨在 CodeWalker 里走不到缓存路径**，只能回落到通用路径（把 3 个**位移浮点**当 x,y,z）⇒ `|q| ≠ 1`。

而 RDR2 的 `SKEL_L_Thigh` 正是 `qF,qF,qF,·,CachedQ2` ⇒ **CodeWalker 解 RDR2 会得到非单位四元数**。
我们在上一轮为 Q2 也置了 `is_type7_quat` ⇒ **`|q| = 1.0000` 精确** ⇒ **我们的实现比 CodeWalker 更正确（就 RDR2 而言）**。

### 2.2 CodeWalker **根本解不了 RDR2 的 `.ycd`**（它自己的 bug）

`ParseData` 里：
```csharp
Sequences[i].Channels[j] = thisSeq.FirstOrDefault(a => a.Index == j)?.Channel;
if (Sequences[i].Channels[j].Type == AnimChannelType.CachedQuaternion1)   // ← Channels[j] 可为 null
```
RDR2 的通道槽**有空洞**（`SKEL_L_Thigh` 的 slot 3 是空的）⇒ **`Channels[j]` 为 null ⇒ NullReferenceException**。
实测：`Sequence.Read` 读头全部正确（见 §3），但 `ParseData` 抛 NPE ⇒ **整条 `YcdFile` 路径对 RDR2 不可用**。

## 3. 用权威读取器实测我们的文件（决定性）

`CWProbe` 把 `ResourceDataReader` 定位到我们 walk `.ycd` 的 Sequence chunk（body `0xb0`）后调 `Sequence.Read`：

```
DataLength=47996  FrameOffset=19816  RootMotionRefsOffset=47980
NumFrames=404  FrameLength=68  IndQ=0  QVB=520  ChunkSize=10  RMRC=53
Data=47996  Sequences=186
```

**与我们解码器读出的值逐字段相同**（404 / 68 / 19816 / 47996 / 186）✅

⭐ **特别重要**：`ChunkSize` 被**权威代码**读成 **10**（CodeWalker 的注释写 "64 or 255"，那是 GTA V 的典型值）
⇒ **我们的 `ChunkSize=10` 没读错** ⇒ 之前"chunk 边界导致单帧台阶"的假设**排除**。

## 4. 结论：「单帧台阶」不是通道解码 bug

综合 §2/§3：通道类型、Sequence 布局、bit 提取、各类通道的取值、CachedQuaternion（含 Q2）、chunk 取值 ——
**全部与权威实现一致**（且我们在 Q2 上更强）。而问题轨道（`SKEL_R_Foot` 等）用的是
`QuantizeFloat`（**全局 ValueBits、无 chunk**）⇒ 不存在"chunk 边界读错"的空间。

⇒ 剩下的两个解释（**都不是解码 bug**）：
1. **真实数据**：RDR2 的原地动画确实在这些帧有快速 snap（`RootMotionRefCounts=53` ⇒ 该 chunk 有 3 位置 + 5 旋转的 root-motion ref，说明切分点很多）；
2. **段边界的拼接**：walk 的台阶恰在 `404/2=202`。

**下一步定论手段**：拿 `walk_slow` f118~f124 的**游戏内画面**与我们的解码姿势对拍（这需要进游戏，无法离线做）。

---

## 5. ★ 社区教程/工具清单（回答"网上有没有教程"）

**有，而且不少**。按对我们的价值排序：

| 资源 | 是什么 | 价值 |
|---|---|---|
| `github.com/citizenfx/AnimKit` | **RAGE 动画创建/编辑工具**（开源，已下载）| ⭐ 源码 + `CodeWalker.Core.dll`；作者 Disquse |
| `forum.cfx.re/t/.../4778131` | **【教程】用 AnimKit 创建/编辑动画**（Disquse 亲写）| ⭐⭐ 讲清"拿现有 clip dictionary 当模板改"的完整流程 |
| `github.com/ultrahacx/Sollumz-RDR/tree/extra-skeleton-fix` | Sollumz-RDR 的 **extra-skeleton-fix 分支** | ⭐⭐ 直接对应我们缺的"额外骨骼（roll/挂点骨）"问题 |
| `nexusmods.com/reddeadredemption2/mods/9845` | **Sir Joseph's Sollumz RDR YLD and Skeleton Fix** | ⭐⭐ "fixes import/export of **skeletons and extra skeletons in drawables**"（作者 = 给我们 UPS 骨架 mod 的同一个人）|
| `github.com/Sollumz/Sollumz_RDR` | Sollumz 的 RDR 分支（Blender 插件，CodeWalker XML）| ⭐ RDR2 资产出/入 Blender 的标准路线 |
| `docs.sollumz.org` | Sollumz 官方文档 | ⭐ 有"export the ped skeletons (YFTs) to use when importing/exporting"的骨架工作流 |
| `rdr2mods.com/wiki/animations/records/` | **RDR2 动画数据库（13000 条动画）** | ⭐⭐ 可查动画字典/clip 全量名（找 `biped_q5` 的入口！）|
| YouTube: `CpKQujwpBPE` / `1KDP75_9ik8` / `Eacadwz6g_I` | RDR2 模型/角色/**高级动画**教程（Codewalker+Blender+Sollumz）| ⭐ 参考 |
| `escobarv110/Rage-Tools` | 另一套 GTA V 工具（"ycd clip dictionary support, every clip/track/keyframe"，可 retime/rename/delete）| ⭐（codeload 拉不到，需另找）|

**对我们的实际意义**：
- **导出侧**（RDR2 → 骑砍2）我们已自建且**比 CodeWalker 更正确**（§2.1），可继续用；
- **导入侧**（自建动画回 RDR2）：社区路线是 **Blender + Sollumz-RDR + CodeX XML**，
  其中 **extra-skeleton-fix** 正是处理"骨架里额外的骨"⇒ 与我们"6 根 roll 骨"的问题是同一件事；
- **`rdr2mods` 动画数据库**是**离线查 `biped_q5` 的最快入口**（下一步）。

## 6. 复现

```bash
# 1) 拉权威源码（codeload 可达）
cd D:/BrainMaker/大镖客2解包分析/tools/ref
curl -sL https://codeload.github.com/dexyfex/CodeWalker/zip/refs/heads/master -o CodeWalker.zip
curl -sL https://codeload.github.com/citizenfx/AnimKit/zip/refs/heads/master  -o AnimKit.zip

# 2) 用权威读取器实测我们的 .ycd（chunk 在 body 0xb0；animseq 下标见我们解码器）
cd CWProbe && "C:/Program Files/dotnet/dotnet.exe" run -- \
   "../../export/animations/mech_loco_m/mech_loco_m@generic@normal@unarmed@walk_slow.ycd" b0 92
```
