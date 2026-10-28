# RDR2 反编译笔记（REA / Ghidra headless）

> 目标：用 REA/Ghidra 反编译 `RDR2.exe`，**辅助解析骨骼**（结构定义 / 骨名与骨 ID 空间 / 动画通道语义）。
> 结论先行：**exe 侧没有能解我们剩余卡点的东西** —— 骨名与类型名都只存在于资产里。
> 但这一轮仍拿到了几条**可复用的事实与工具**，且**排除了一整条路**（省掉后续投入）。

---

## 1. 工具链（已就绪，照抄即可）

| 项 | 值 |
|---|---|
| REA | `rea@6.4.0`（`C:\Users\...\cowork-updates\node-binary\bin\rea`）｜⚠️ `rea doctor`：**ghidra ok / host ok**，但 `node` 22.15.0 低于要求、`hopper` 缺失 ⇒ 本机**只用 Ghidra 路线**，别走 Hopper |
| Ghidra | `D:\BrainMaker\tools\re\ghidra`（12.1.4 PUBLIC） |
| JDK | `D:\BrainMaker\tools\re\jdk21` |
| Headless 入口 | `D:\BrainMaker\tools\re\ghidra\support\analyzeHeadless.bat` |

```bat
set JAVA_HOME=D:\BrainMaker\tools\re\jdk21
call "D:\BrainMaker\tools\re\ghidra\support\analyzeHeadless.bat" ^
     D:\BrainMaker\tools\re\work\ghidra_proj RDR2 ^
     -import H:\EPICGAMES\RedDeadRedemption2\RDR2.exe -noanalysis -max-cpu 4
```

> ⭐ **关键技巧：`-noanalysis`**。`r ea analyze RDR2.exe`（89 MB）会 330 s 超时，**但只做
> `-import ... -noanalysis` 只花 1~2 分钟**，而且**字符串/字节检索完全不需要预分析**
> ⇒ 本轮所有发现都是这么拿到的。只有要**反编译具体函数**时才需要分析。

**RDR2 项目**：`D:\BrainMaker\tools\re\work\ghidra_proj\RDR2`（已导入，未分析）
**仁王项目**（上一轮遗留，可参考脚本用法）：`...\ghidra_proj\Nioh`

## 2. 可复用脚本（`D:\BrainMaker\tools\re\work\scripts\`）

| 脚本 | 作用 |
|---|---|
`FindStrRDR2.java` / `FindStr3/4/5.java` | 按 ASCII 串搜全内存，打印命中地址；可列全部命中与命中处字符串 |
`DumpStrings.java <base> <span>` | 把一段内存里的**可读串连地址**打出来（看名字表最好用） |
`DumpAt.java <addr>...` | hex+ASCII dump 指定地址 ±0x100/0x300 |
`FindMagic2.java` | 在**代码段**找 4 字节立即数 magic（RSC8/RPF8/META/type id）+ dump 指针表 |
`FindStr.java`（仁王遗留） | 按串搜 + 打印**引用它的函数** |

配套 `run_*.bat`（`run_rdr2_import.bat` / `run_rdr2_str.bat` / `run_dumpstr*.bat` / `run_fs4.bat` / `run_fm2.bat`）
与日志 `rdr2_*.log` 都在 `D:\BrainMaker\tools\re\work\`。

## 3. 本轮拿到的事实

### 3.1 ★ RAGE **资源类型扩展名表** @ `0x143667e68`（4 字节一槽，三族）

```
y 族: ycd yld ypmd ypm yed ypt ymap ytyp ych yldb yjd yad ynv yhn ypl ynd yvr ywr ynh yfd yas
i 族: icd ild ipmd ipm ied ipt imap ityp ich ildb ijd iad inv ihn ipl ind ivr iwr inh ifd ias
# 族: #ld #pm #pt #map #typ #ch #ldb #jd #nv #hn #pl #nd #vr #wr #nh #fd #as
```

**紧跟着是一张【类型处理函数指针表】@ `0x143667f88`**（实测连续有效代码指针：`0x142b05d90 / 0x142b98ca8 / 0x142bab9b0 / …`）。

> ⚠️ **重要负面结果**：这张"扩展名表"里 **没有** `yft / ydd / ydr / ytd / ybn`
> ⇒ 图形类资源（drawable/fragment/texture/bounds）的类型名走的是**另一套**（不是扩展名形式）。
> 想靠它定位"drawable→Skeleton 解析"这条路**走不通**。

### 3.2 骨名相关字符串（exe 里只有 11 条）

| 地址 | 内容 |
|---|---|
| `0x1434268a0..0x143426910` | **`ID_SKEL_HEAD / SPINE10 / SPINE5 / TAIL0 / TAIL5 / TAIL10 / TAIL14`**（**16 字节定长槽**）|
| `0x14349ae20..0x14349ae50` | **`SKEL_L_Finger02` / `SKEL_R_Finger02` / `SKEL_L_Finger43` / `SKEL_R_Finger43`**（同样 16B 槽）|

* `ID_SKEL_*` 紧邻一张**动物/生物 rig 标签表**（`Front Right Foot` / `Front Left Foot` / `front left leg` / `left hand` / `right hand` / `body` / `middle of body` / `top of body` …）⇒ 是**受击/伤害定位用的骨 ID 标签**（我们运行期正好也有 `ID_PH_HEART`）。
* `SKEL_*_Finger0x` 是 exe **唯一引用的手指骨**（握持/IK 用）。
* ⚠️ **exe 里没有任何"全局骨名表"**（我们搜了 `SKEL_` 全量：只有上面 11 条）
  ⇒ **骨名只存在于资产（`.yft/.ydd`）里**，运行期 `f1a` 那套 tag 是**资产侧注册表**，exe 里查不到。

### 3.3 一路空白（都是**负面**但省钱的结论）

| 搜什么 | 结果 |
|---|---|
| `skeleton` / `Skeleton` / `SKELETON` / `yskel` / `ped_skeleton` / `human_skeleton` | **0** ⇒ RAGE 骨骼类型不以这些名字出现在 exe |
| `biped_q5` / `@biped@` | **0** ⇒ 动画骨架名是**资产侧**命名，exe 不持表（`q5@` 的 2 处命中是指针表低字节假命中）|
| `QuantizeFloat` / `CachedQuaternion` / `AnimSequence` / `ChunkSize` / `ValueBits` / `Quantum` / `ClipDictionary` / `NumFrames` / `FrameLength` | **全 0** ⇒ 通道/序列的字段名被剥符号 ⇒ **没法用字符串定位动画解码器** |
| `RSC8` / `RPF8` / META magic（`0x38435352` / `0x52504638` / `0x50524430`）在**代码段**作 4 字节立即数 | **0** ⇒ 比较不是这个形式（或不是 4 字节立即数）|
| `boneTag` | 1 处，但落在**存档反射字段名表**（`projDecalName/flipH/flipV/SPackedProjDecalSaveData`）里 = "投射物贴花挂在哪根骨"，**不是骨骼结构字段名** |

## 4. 结论与建议（重要）

**为什么 REA 对我们剩下的卡点低产**：剩下的三件事**全在资产/格式侧**，不在代码侧：

1. 45 个"三个 `.yft` 都没有"的动画骨 ID → 要找 **`biped_q5` 那份骨架资源**（资产）
2. 6 根手臂 roll 骨（`SKEL_L/R_UpperArm_02_01` …）→ 只存在于**运行期合并骨架**（资产装配顺序）
3. `.ycd` 的"单帧台阶"（帧号都落在 `chunk=10` 边界附近）→ 要**实验对照** `.ycd` 字节（资产）

⇒ **不要再把时间投在 89 MB 无符号 exe 的整体反编译上**。REA 的正确定位是：
**当"某个结构/常量的语义在资产里定不下来"时，用它做一次性、点位明确的反编译**（例如未来若要
确认"某函数怎么算 tag"再回到 §3.1 那张 handler 表去定点反编译）。

**下一步建议顺序**（沿用本笔记的证据）：
1. **找 `biped_q5` 骨架资源**（收益最大：69/114 → 接近 114，且可能补上 6 根 roll 骨）；
   入口：`names.txt` 里按 `biped` / `ped_skel` / `creature` 家族翻，或在 `packs/base/models/` 下按目录看。
2. **`.ycd` chunk 实验**：拿 `walk_slow` 的 f118~f124 做"改 chunk 字段重解"的对照实验，验证 `ValueBits` 是否按 chunk 变。
3. 若要继续 RE：**只做定点反编译** —— 从 §3.1 的 handler 表里挑一个与 `ycd` 对应的索引，反编译它追到序列解码。
