# RDR2 骨骼提取（`.yft` fragment · RSC8 v58）—— 逆向笔记

> 承接 `RDR2_ycd动画解码.md`。动画曲线已解出；本文记录**骨架**（骨骼名/层级/绑定姿势）的逆向进展。
> 关键结论：RDR2 社区**确实能换骨骼**，官方路线是 **CodeX（二进制 ↔ `.yft.xml`）**——
> 本文把 `.yft` 的二进制结构读通，等价于复刻了 CodeX 的骨架部分。

---

## 1. 社区路线（回答"能不能换骨骼"）

| 环节 | 工具 |
|---|---|
| 从游戏解出 `.yft` 并转 **`.yft.xml`**（含 `Skeleton`） | **CodeX**（dexyfex，未开源） |
| 在 XML 里**加/改骨骼**（"Skeleton Merger"：拷骨骼、**修正骨骼编号与父子连接**、统计骨数） | `Ilyxrl/Ilyxrls-RDR2-Ped-Tool`（开源 Python） |
| 把 `.yft.xml` 转回 `.yft` 装回游戏 | **CodeX** |
| 骨数超上限会崩 | `RDR2-No-Bone-Limit`（运行时 ASI 补丁） |

**CodeX 的骨骼 XML 结构**（从 ilyxrl 工具源码确认）：
```xml
<Skeleton><Bones>
  <Item><Name>SKEL_ROOT</Name><Index value="0"/><ParentIndex value="-1"/>
        <NextSiblingIndex value="-1"/><LastSiblingIndex value="..."/></Item>
  ...
</Bones></Skeleton>
<BoneTransforms>
  <Item><Heading/><Pitch/><Roll/><X/><Y/><Z/></Item>
</BoneTransforms>
```
→ 骨骼**名 + 索引 + 父索引 + 绑定姿势**齐全。**这就是重定向需要的一切。**

### 1.1 调研补充（本轮）

- **官方编辑器**：❌ R\* **没有**给 RDR2 官方资产编辑器。官方只有游戏内的 **Rockstar Editor（视频剪辑）**，
  且对 RDR2 还是靠 mod 补上的。资产编辑全靠社区工具。
- **Blender 路线（关键）**：**Sollumz** 有 RDR 分支，且有第三方实验插件
  **"Sir Joseph's Sollumz RDR YLD and Skeleton Fix"**（`nexusmods.com/reddeadredemption2/mods/9845`）——
  明确写着 **"fixes import and export of skeletons and extra skeletons in drawables"**，
  即 **Blender 能导入/导出 RDR2 骨架**。
- **Sollumz_RDR 源码里的 RDR2 `Bone` 字段**（`cwxml/drawable.py`，直接印证我二进制读到的结构）：
  `Name / Tag / Flags / Index / ParentIndex(-1) / TransformUnk(quat) / NextSiblingIndex / LastSiblingIndex / Position(vec3) / Rotation(quat) / Scale(vec3)`。
- **社区对 ped 骨头的描述**："Ped models have hundreds of bones (skeletal + many other kinds, like interface/attach/reference points)"
  —— 正好对应我从 `.yft` 读出的 `SKEL_*`（本体）+ `MH_*/PH_*/CP_*/SH_*/SM_*/RB_*/OH_*/ES_*`（挂点/道具/服装/布料骨）。

### 1.2 服装/换头类 mod 的绑定方式（回答"新衣服怎么绑骨"）

1. CodeX 把身体 `.ydd` + 服装 `.ydd` + `.ymt` 导成 XML；
2. Blender 里导入 HEAD/UPPER/LOWR/FEET 等 YDD 得到"基础身体"，服装网格**蒙皮到同一套骨架**；
3. 服装自带的额外骨（`MH_/SH_/…`）需要 **skeleton merge** 进本体骨架（ilyxrl 工具干的就是这个）；
4. 导回并在游戏内 stream。

因为 CodeX 未开源、其二进制在本机网络下也拉不到，所以本轮改为**直接解析 `.yft` 二进制**（结果见下）。

---

## 2. `.yft` 二进制结构（实测偏移）

样例：`export/models/fragments/meta_base_abe.yft`（162,784 字节，RSC8 v58，system 段含 0x50000000 基址指针）。

| 结构 | 偏移 | 说明 |
|---|---|---|
| **Skeleton 结构** | `0x024a80` | `+0x10`=BoneTags 指针；`+0x18`=409(cap)；`+0x20`=(335,1)；`+0x28`=Bones 指针；`+0x30`=0x5000bd40；`+0x38`=0x50006980；`+0x40`=0x50014ff0；**`+0x5C`=1，`+0x5E`=BonesCount=335** |
| **ParentIndices** | **`0x015000`** | 335 × `int16`；`[-1,0,1,2,3,4,4,6,4,4,4,4,3,…]` **校验 bad=0**（每项 ∈{-1}∪[0,i)）✅ 真层级 |
| **Bones（每骨结构）** | `0x00110` 起，**步长 0x50(80B)**，335 条 | `+0x00`=名字指针；**`+0x14`=u16 NextSiblingIndex、`+0x16`=u16 ParentIndex**（与父索引数组逐条吻合 ✅）；**`+0x20`=绑定四元数 (x,y,z,w)，|q|=1 ✅**；**`+0x30`=绑定位移 (x,y,z)**；`+0x40`=1,1,1,1 |
| **骨骼名字符串池** | `0x026e40`~`0x027b80` | 含 `SKEL_*`（核心骨）、`MH_*`/`PH_*`/`CP_*`/`SH_*`/`SM_*`/`RB_*`/`OH_*`/`ES_*`（挂点/道具/服装骨），如 `SKEL_R_UpperArm`、`SKEL_Spine_Root`、`SKEL_L_Finger41`、`HairScale_loc` |
| **Transformations / Inverted** | `0x006980` / `0x00bd40` | 335 × 64B（4×4 float），语义待定 |

**已确认**：
- 层级 = 真父子表（**0 错误**；1 个根、最大深度 19；左/右肢镜像成对，如骨2/19、3/20、4/21 位移完全对称）。
- 线段长度=骨长（腿链 `0.446+0.424+0.158 ≈ 1.03`），**根骨在骨盆高度**，腿沿 −Z 伸展
  ⇒ **模型是 RAGE 的 Z-up 空间**（不是 Y-up），这是之前 FK "看着不像人形"的主因。
- 每骨绑定 = 四元数 + 位移，且**单位四元数校验通过**（例：骨0 = `(0,0.7071,0,0.7071)` = 绕 Y 90°；骨1 = `(-0.0235,0.0388,-0.0359,0.9982)`）。

**待定**（🔴 本轮的关键发现）：
1. **FK 框定遇到硬点 —— 脊柱链与腿链在世界空间里「同向」**：
   - 腿链 `0→1→2→3→4→14`：局部位移 `0.13/0.446/0.424/0.158`，**总长 1.13**（= 骨盆→髋→大腿→小腿→脚）
   - 脊柱链 `0→88→…→95`：6~7 段 `0.059…0.111`，**总长 0.47**（= 骨盆→胸的脊椎节）→ 再分叉出手臂链 `95→166(0.166)→167(0.3)→168(0.259)`
   - **但两条链在 world 里都朝 −Z**（腿**向下**、脊柱**向上**，人体上必须相反）⇒ 仅用「父四元数旋转子位移」的 FK 解释不通。
   - 试过的约定（xyzw/wxyz × conj × 用父/自身四元数 × 位移取自身/父 × 4 种矩阵约定）**没有一种**能让腿与脊柱分离。
   - ⇒ 最可能：**这 80 字节结构不是"骨骼局部变换"，而是别的东西**（RAGE bind pose 常是"所有骨同向"的直骨姿势，
     真正的形态靠 **inverse bind 矩阵** 或模型表达）；或**该 `0x20` 四元数不是绑定旋转**。
     ⇒ 需要 **CodeX 的 RDR2 Skeleton 结构定义**（闭源）或更多样本交叉验证。
2. **索引→名字**（🔸 本轮实测）：
   - 名字池（`0x26e40+`）确为**名称表**：部分区段是 **16 字节定长槽**（`SKEL_R_Finger20`/`MH_Belt_LS_Root`/`CP_R_WaistOuter` 都是 15 字符+`\0`），
     另有 15 字节/变长区段；顺序像**哈希桶**（非字典序）。
   - 把每骨 `+0x00` 指针解析为「**包含该指针的那个完整字符串**」，得到 **309 个不同名字 / 335 骨**（覆盖很好）。
   - **但用已知 RAGE 父子对校验（12 组）只过 1 组**（`SKEL_L_Hand→SKEL_L_Forearm` 通过）；
     例：解出的 `SKEL_L_Calf` 的父却是 `CH_R_Hand`。⇒ **名字与骨骼索引的对齐规则还没找到**。
   - 排除了 **joaat(name)** 方案：骨骼结构里 `+0x08/+0x0C/+0x10/+0x18/+0x1C` 各字段**没有一个**等于名字池里任何名字的 joaat（0/335）。
   - 也确认了 **父索引数组唯一**：全文件扫描只有 `0x15000` 一处满足"父指针性质"（其余 5 处候选 bad≥1）。
3. **动画↔骨架对齐**：`.ycd` 的 `BoneId(u16)` 映射未定。
4. 🔸 **偏移是每文件不同的**：`tools/rdr2_yft.py` 里的 `0x24a80 / 0x110 / 0x15000` 只对 `meta_base_abe.yft` 成立；
   已加 `find_skeleton()` + `read_skeleton_dyn()` 做动态定位（还需再调）。

---

## 2.5 【已解·2026-10-15】运行期骨架 = 卡点 2 的答案（内存只读取证）

`.yft` **静态解析**卡在"索引↔骨名对齐"，本轮改走**运行期内存取证**（`tools/memscan.py`，只读、不注入）。

**方法**（游戏开单人模式）：
```bash
python tools/memscan.py --pid <RDR2.exe> str "SKEL_R_UpperArm"     # 扫骨名 → 拿地址
python tools/memscan.py --pid <PID> ptr 0x242d5ce05a0 --span 1024  # 回溯持有者结构
```
命中一个**逐骨结构数组**（步长 `0x50`，与 `.yft` 完全一致），且每个结构 `+0x00` 指向一条骨名——**索引↔骨名当场对上**。

**80 字节结构全解**（与 CodeX 的 `<Skeleton><Bones>` 字段一一对应）：

| 偏移 | 字段 | 说明 |
|---|---|---|
| `+0x00` | `char* Name` | 指向骨名（16B 槽池）|
| `+0x14` | `u16 NextSiblingIndex` | 已验证（如 `SKEL_L_Thigh(3)`→19）|
| `+0x16` | **`u16 ParentIndex`** | 65535 = 根 |
| `+0x18` / `+0x1c` | `u16 Index`（两处相等）| 本骨索引 |
| `+0x1a` | `u16`（名哈希低 16 位） | |
| `+0x20` | `f32×4 Rotation (xyzw)` | 单位四元数 |
| `+0x30` | `f32×3`（**非父相对位移**，见下）| |
| `+0x40` | `f32×4 = (1,1,1,1)` | Scale |

**结果：133 根骨，`索引 / 骨名 / 父索引` 全部解剖学自洽**（不再是之前的 1/12）：

```
0  SKEL_ROOT
1  SKEL_Spine_Root → 0        2  SKEL_Pelvis → 1
3  SKEL_L_Thigh  → 2          4  SKEL_L_Calf → 3     5 SKEL_L_Foot → 4
19 SKEL_Spine0 → 2            20 SKEL_Spine1 → 19    21 SKEL_Spine2 → 20
22 SKEL_Neck0 → 21            25 SKEL_Head  → 24
36 SKEL_L_Clavicle → 21       37 SKEL_L_UpperArm → 36
53 SKEL_R_Clavicle → 21       54 SKEL_R_UpperArm → 53   ✅
```
**⇒ 卡点 2（索引↔骨名）彻底解决。** 产物：`export/skeleton_runtime/`（`rdr2_skel_runtime.json` + `skel_full.tsv` + 原始 `*.bin` + `runtime_skeleton.html`/`.png`）。

**卡点 1 的更新（重要修正）**：运行期结构的 `+0x30` 字段**不是"父相对绑定位移"**——
证据：`SKEL_L_Thigh` 与 `SKEL_R_Thigh` 的该字段完全相同（`0.0675,0,0`，仅 `-0`），
用 `world = T·R·S·local` 任何约定做 FK，**左右腿都重合**（见 `runtime_skeleton.png`：两腿叠成一条竖线）。
⇒ 该字段更像"沿骨轴的标量/长度"，而**真正的绑定几何应来自模型的 inverse bind 矩阵**（drawable 侧），
`.yft` 的 `+0x30`（腿链 0.446/0.424/0.158，FK 出 1.69 m 人形）才是可用的 bind pose。

**`.yft` 名字池**：确认是**字节紧凑的共享后缀池**（指针落在串中部，如 `0x2768f` → `...Ca|ll`），
不是 16B 定长槽；`containing-string` 还原会串行（父链出现 `Toe0→ArmRoll`）。**待后续专门解**。

## 2.6 ⚠️ 已推翻：「骨表后的 4×4 矩阵数组 A 块 = 世界 bind」不成立

> **本节记录一次被推翻的结论**，留给接手人避免重犯。

运行期字节 `skel_array_raw.bin` 里，骨表（0x50 步长）之后确有一段 **4×4 矩阵数组（0x40 步长，共 266 条）**：

| 块 | bin 偏移 | 平移分量 |
|---|---|---|
| **A** | `0x2a50 + k*0x40`（k=0..133）| 小、但沿链「累积」（`0.148`）|
| **B** | `0x2a50 + (134+k)*0x40`（k=0..131）| **逐条 == 骨结构 `+0x30` 字段** |

A 块当初看起来很像 world bind，因为：**肢体上索引对齐**（`A[3]=L_Thigh`、`A[25]=Head`）、
**左右严格镜像**（`Z` 反号）。**但硬检验推翻了它**：

```
|A[child] - A[parent]|  应 ==  该骨局部位移长度   （此判据与坐标系约定无关）
实测通过率： 11 / 132        ← 脊柱 ratio 1.1~2.2、手臂 1.6、Toe 3~8 全部对不上
```

⇒ **A 不是这具层级的 world bind**（`A[0]=A[1]=0` 而 `Spine_Root` 长 0.0642 就对不上）。

**因此**：`core_skeleton.png` / `full_skeleton.png` 画的**不是绑定姿态**，
它只是把某个尚未定性的 per-bone 数据当坐标画了出来 —— 所以看着不像 T/A pose。

**当前状态**：
- ✅ 骨名 / 索引 / 父子表（§2.5）**成立**；
- ✅ 每骨 `+0x20` 单位四元数（旋转）**成立**；
- ❌ **真实 bind 几何仍未拿到**（`+0x30` 不作父相对位移，A 块也不是 world bind）。

**下一步线索**：`.yft` 的 `+0x30` 是**真位置**（腿链 `0.446/0.424/0.158`，FK 出 **1.69 m** 人形），
但玩家 `.yft`（`meta_base_player.yft`）的 Skeleton 结构定位器会误报，需专门解其偏移；
或运行期再做一次定向取证（找 bind pose 矩阵数组 / inverse bind）。

**产物（保留备用，`worldPos` 字段已标注不可信）**：`export/skeleton_runtime/rdr2_skel_full.json`。

---

## 2.7 【2026-10-15】`.yft` 骨架定位器（离线）—— 结构已定位，FK 仍未解

`find_skeleton`（原启发式）**会误报**（对玩家文件返回 257 且指针全 0）。
改用**扫 Skeleton 结构尾**（`u16 1, u16 BonesCount, u16 ≤N+64` 且 `+0x28/+0x40` 是 `0x50000000` 基指针）后定位准确：

| 文件 | Skeleton 结构 | BonesCount | 骨表 | 父索引数组 | 校验 |
|---|---|---|---|---|---|
| `meta_base_abe.yft` | `0x24a80` | 335 | `+0x28→0xd0`，实际记录 `@0x110` | `+0x40→0x14ff0`，实际 `@0x15000` | bad=0，1 root ✅ |
| `meta_base_player.yft` | **`0x41e20`** | **756** | `+0x28→0xd0`，记录 `@0x110` | **`+0x40→0x2f4f0`，实际 `@0x2f500`** | bad=0，1 root ✅ |

> 规则：结构 `+0x28`/`+0x40` 给的是**数组头指针**，真实数组 = 指针偏移 **+0x40（骨表）/ +0x10（父表）**；
> 骨记录仍为 `0x50` 步长，`+0x20` 四元数、`+0x30` 位移（`unitq 335/335`、`756/756` 全通过）。
> 扫「最长父索引 run」也能独立定位（abe `@0x15000` len 336；player `@0x2f500` len 757）。

**FK 约定仍未解**：对上述两套骨架穷举 `order{xyzw,wxyz} × 共轭 × 乘法顺序 × 旋转来源{父世界,父世界⁻¹,自身,自身⁻¹}`
共 32 组约定，渲染结果**全部是星爆/缠绕**（knee 角 72°，离共线 180° 很远）。
⇒ `.yft` 的 `+0x30` 虽是**真实骨长**（腿链 0.446/0.424/0.158），但**无法用简单层级旋转复现出人形**。
产物：`export/skeleton_runtime/fk_conventions.png`（32 组约定对比）、`abe_fk.png`、`player_yft_fk.png`。

**结论**：离线路已拿到 `.yft` 骨架的**结构**（骨数 / 父表 / 骨长），**bind 几何仍未拿到**。

---

## 2.8 【2026-10-15】CodeWalker 权威定义（从 codeload 拉源码获得）

`codeload.github.com/dexyfex/CodeWalker/zip/refs/heads/master` 可下（3.7 MB）。关键三件：

### (a) `Bone` 结构 = **80 字节**（`CodeWalker.Core/GameFiles/Resources/Drawable.cs:2574`）

| GTA V 偏移 | 字段 | RDR2 实测偏移（字段重排后）|
|---|---|---|
| `+0x00` | Quaternion **Rotation** | `+0x20` |
| `+0x10` | Vector3 **Translation** | `+0x30` |
| `+0x20` | Vector3 **Scale** | `+0x40`（=1,1,1）|
| `+0x30` | short NextSiblingIndex | `+0x14` |
| `+0x32` | short **ParentIndex** | `+0x16` |
| `+0x38` | ulong NamePointer | `+0x00` |
| `+0x42` | short Index | `+0x18` |
| `+0x44` | ushort Tag | `+0x1a` |
| `+0x46` | short Index2 | `+0x1c` |

⇒ 与运行期实测字段**完全对应**（RDR2 只是把名字/索引提到了前面）。

### (b) `Skeleton` 里**确实存了 bind 矩阵**

```
Matrix[] Transformations          // N 条，CodeWalker 注释：局部矩阵
Matrix[] TransformationsInverted  // N 条，= bind 全局逆（bone.BindTransformInv）
short[]  ParentIndices
```
abe 实测：`+0x28`=Bones(`0xd0`，数据 `@0x110`)、`+0x30`=`0xbd40`、`+0x38`=`0x6980`、`+0x40`=ParentIndices(`0x14ff0`，数据 `@0x15000`)、`+0x5E`=335。
**`0xbd40 - 0x6980 = 0x53C0 = 335 × 0x40`** —— 两条数组正好首尾相接 ✅

### (c) **FK 算法 + 精确旋转公式**（`Skeleton.BuildTransformations()` / `Utils/Quaternions.cs`）

```csharp
// 全局变换：从 bone 自己往上溯
pos = bone.Translation; ori = bone.Rotation;
for (p = bone.Parent; p != null; p = p.Parent) {
    pos = p.Rotation.Multiply(pos) + p.Translation;   // ← 用父的局部旋转
    ori = p.Rotation * ori;                            // ← 父 ⊗ 己
}
global = AffineTransformation(1.0f, ori, pos);

// QuaternionExtension.Multiply(this Quaternion a, Vector3 b) —— 行向量约定（= 标准式的转置）
out.X = b.X*((1-2yy)-2zz) + b.Y*(2xy-2wz) + b.Z*(2xz+2wy)
out.Y = b.X*(2xy+2wz) + b.Y*((1-2xx)-2zz) + b.Z*(2yz-2wx)
out.Z = b.X*(2xz-2wy) + b.Y*(2yz+2wx) + b.Z*((1-2xx)-2yy)
```

> ⚠️ 之前自研的 `qrot`（列向量约定）是它的**转置** —— 方向反了。已按上面逐字移植（`tools/` 可加 `cw_fk.py`）。
> 但**注意**：`|W[child]-W[parent]| == 骨长` 这条判据对**任何**正确 FK 都恒成立（旋转保长），**不能用来验约定** —— 必须拿算出的 global 去对文件里存的 `TransformationsInverted`。

### (d) ✅ **已解：bind 几何 = `inverse(TransformationsInverted)`**（2026-10-15）

**矩阵排布**（`Transformations` 与 `TransformationsInverted` 同）：
- 行 0-2 = 3×3 旋转（**CW 行向量式** `QuaternionExtension.ToMatrix`）
- 行 3 = `(tx, ty, tz, 1)` 平移
- **数组实际基址 = Skeleton 结构里对应指针偏移 + `0x50`**（不是指针值本身！）

**验证**（`meta_base_abe.yft`）：
`Transformations[i]` 与 `Affine(1, R_i, T_i)`（R/T 取自 bone 记录）**误差 = 0.00000**（base=`0x69d0`）⇒ 布局确定。

**bind 全局矩阵 = `inverse(TransformationsInverted[i])`**，取第 4 行做位置：

| 文件 | Inverted 数组基址 | 骨数 | 结果 |
|---|---|---|---|
| `meta_base_abe.yft` | `0xbd40 + 0x50 = 0xbd90` | 335 | **干净人形**（XZ 视图：双臂展开/双腿下垂/头在顶），Z 范围 **1.95 = 身高** ✅ |
| `meta_base_player.yft` | `0x1aa10 + 0x50 = 0x1aa60` | 756 | **人形**（少数异常骨，多为奇异矩阵/非骨记录）|

**坐标约定**：**Z = 上**（身高方向）、X = 左右、Y = 前后。
⇒ **卡点 1（FK 约定）与 bind 几何同时解决**：不需要 FK，直接取文件里存好的 `TransformationsInverted` 求逆即可。

> 关键教训：`|W[child]-W[parent]| == 骨长` 对任何正确 FK **恒成立**（旋转保长），**验证不了约定**；
> 真正的判据是拿算出的矩阵去对**文件里存好的 `Transformations`**（CodeWalker 源码里那句被注释掉的 `//just testing! - all ok` 就是这个）。

**产物**：`export/skeleton_runtime/abe_bind.png`、`player_bind.png`、`player_bind_pos.json`。

---

## 2.9 【2026-10-15 终解】bind 矩阵布局定死 + 工具化（本轮）

**2.8(d) 的结论是对的，但当时没把"矩阵怎么读"写死**，所以下游一直没接上。本轮补完并**交叉验证**：

### (a) 每个 64B 块 = **行向量仿射**，存的是 **bind 全局的逆**

```
rows[0..2] = (R 的 3 列 | 0)        # R = 3x3 旋转
rows[3]    = (tx, ty, tz | 0)
```
其逆（= **bind 全局**，标准列向量约定）：
```
bind_global.rot = R                # 三处 3x3 元素【原样使用】
bind_global.pos = -R @ t           # 标准矩阵-向量乘
```

### (b) 三重验证（都过）

| 判据 | 结果 |
|---|---|
| 与既有产物 `player_bind_pos.json` 对拍 | **755 骨最大误差 8e-6** ✅ |
| `meta_base_abe.yft` 形态 | Z 跨度 **1.953 m**、头 z=+0.649 / 脚 z=−0.963 / 骨盆 −0.038 / 双臂 x=±0.41（镜像）✅ |
| **RAGE 骨轴不变量** | `R_parentᵀ·(pos_child−pos_parent) ≈ (len,0,0)` —— 直骨姿势下每骨位移沿自身 +X；实测 10/16 精确成立（不成立的 6 根是"运行期父 ≠ .yft 父"的骨，属口径差异）✅ |

> ⚠️ **别再用 FK 从骨记录 (t,q) 反推 bind** —— `.yft` 的骨记录是"直骨姿势"，
> 用它 FK 出来的脊柱与腿**同向**（就是 §2 卡点 1 的现象）。bind 只在
> `TransformationsInverted` 里。

### (c) Tag 是跨表对齐的钥匙（**仅限同一物种**）

运行期骨结构 `+0x1a` 与 `.yft` 骨结构 `+0x1a` 是同一个 `Tag` ⇒ 拿它做 `.yft ↔ 运行期骨架` 的索引映射。

| 文件 | 覆盖 runtime 133 骨 |
|---|---|
| `meta_base_player.yft`(756) / `meta_base_abe.yft`(335) / `meta_base_male.yft`(674) | **37 骨**（含 20/28 映射骨），三者对同一 tag **完全一致**（误差 ≤1e-4）|
| 鸟 `roseatespoonbill_01.yft`(195) | 表面 90，但与人的重叠 tag 位置中位误差 **0.49 m** ⇒ **不可用** |

⇒ **Tag 不是全局哈希，是"按骨架注册顺序发的槽位号"**，跨物种会碰撞。
**只用人类 .yft**。

### (d) 工具（本轮新增）

```bash
# 抽 bind 表（默认 player + abe + male 三个合并 → 1050 个 tag）
uv run python tools/yft_bind.py
#   → export/skeleton_runtime/yft_bind.json   {tag: {pos:[3], rot:[[3x3]]}}

# 导出源资产（骨架 rest 用权威 bind；见 tools/export_gltf_source.py）
uv run python tools/export_gltf_source.py <anim.json> <out.gltf> --name <clip>
```
验证：导出的 GLTF 复算世界位置与 bind **逐骨误差 0.00000**；Blender 导入后
`SKEL_Head` head = `(0,−0.015,0.649)`（= RDR2 bind）⇒ **坐标系链路正确**。

### (e) 仍未覆盖

`SKEL_L/R_UpperArm_02_01`、`SKEL_L/R_Forearm_01_01`、`SKEL_L/R_Hand_01_01`
这 6 根"手臂 roll/twist"骨在三个人类 `.yft` 里都没有（tag 不在表内）⇒
`export_gltf_source.py` 用**几何回退**（沿父骨轴中点、姿态随父），
骨长/朝向可用但非精确。要 100% 覆盖需要能读 `.yft` 骨名池
（本轮复核：确实是**共享后缀池**，指针落在串中部，朴素还原会串行 —— 仍未解）。

---

## 2.10 【2026-10-16 突破】骨名池解出 —— **756/756 全部命名**

从第一份 README 起就挂着"`0x26e40` 起共享后缀池、只能还原 309/335、对齐 1/12"的卡点。
**已解，且是精确规则**：

```
骨名 = NUL 字符串，起点 = NamePointer(bone+0x00) − 0x50000000 + 0x10
```
即 `NamePointer` 指向 **名字起点前 0x10 字节**（落在**上一个名字内部**）—— 这就是当年用
"取包含指针的整串"只能得到尾部片段（`_Seam` / `and` / `31`）的原因。

**验证**（`meta_base_player.yft`，以运行期已知的 34 根骨为真值）：

| delta | 命中 |
|---|---|
| 0x00 / 0x08 / 0x18 | **0 / 34** |
| **0x10** | **31 / 34** |

3 个未命中全部可解释：
* `PH_Hat_loc`（池）vs `PH_Hat_Loc`（运行期）—— **纯大小写差异**
* `SKEL_L_Hand_01_02` vs 池 `SCALE_L_Forearm`、`SKEL_R_Pelt_D03` vs 池 `SC_SatchelPosition`
  —— **tag 空间碰撞**（同一个 tag 在运行期骨架与 `.yft` 里指的不是同一根骨）

**产物质量**（`meta_base_player.yft` 756 骨）：

```
可读名 756/756（0 个空/异常）；重名仅 2 个（PH_L/R_SpinePosition）
前缀分布：MH 274 / PH 102 / SKEL 72 / SPR 37 / SCALE 35 / SC 24 / SH 23 / OH 22 / RB 21 / CP 19 / TGT 17 / ES 16
```
与社区描述完全吻合（"Ped 有数百根骨：skeletal + interface/attach/reference points"）。

**顺带解决的**：
* ⭐ **`SKEL_L_Finger00`(idx 191) / `SKEL_R_Finger00`(idx 283) 找到了** —— 这就是 README §0.6 N6 / §0.5h M5
  一直缺的两根手指骨；接上后**映射骨 26 → 28（满）**，`源缺骨` 警告消失。
* 动画轨道名从 `T<tag>` 变成真名（例：`T4126 → CH_R_Hand`、`T33869 → SKEL_Spine5`）。

**工具**：`tools/yft_bind.py` 的 `read_yft_names()`；名字写进 `export/skeleton_runtime/yft_skel.json`
的 `bones[].name`；`export_gltf_source.py --skel yft` 的命名优先级 =
① 运行期骨名（保 map.json 兼容）→ ② `.yft` 池真名 → ③ `T<tag>`。

### 仍未解

* `SKEL_L/R_UpperArm_02_01`、`SKEL_L/R_Forearm_01_01`、`SKEL_L/R_Hand_01_01` 这 6 根**在 `player.yft` 里不存在**
  （tag 也不在），继续用"从运行期骨架接回 + 几何回退"。若要精确，需找含这些骨的其它 `.yft/.ydd`。

---

## 3. 复现

```bash
# 1) 从 packs 抽出 metaped fragments（419 个 .yft）
tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe extract \
  work/nested/packs/base/models/metaped_fragments.rpf export/models/fragments ""
# 2) 读骨架（父索引/每骨 quat+pos/名字池）—— 已封装：
uv run python tools/rdr2_yft.py export/models/fragments/meta_base_abe.yft
#    → bones=335 roots=1 maxdepth=19；parents @0x15000；bones @0x110(步长0x50, quat@+0x20, pos@+0x30)
```

---

## 4. 下一步（离"完整角色 3D + 骑砍2重定向"还差）

1. 定 FK 轴/空间 → 骨架能摆成站立人形（**验证：脚在最低、头在最高、左右对称**）。
2. 还原 索引→骨骼名。
3. 建立 `.ycd` 动画序列 ↔ 骨架骨的对应。
4. 按 `D:/BrainMaker/骑砍2动画重定向` 的 `pipeline/rigs/*` 加 `rdr2_biped` 映射 → FBX + TRF + 查看器。
