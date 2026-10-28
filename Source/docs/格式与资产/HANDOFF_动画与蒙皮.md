# 交接：RDR2 NPC 模型 / 蒙皮 / 动画（2026-10-17）

> 面向下一个 session。**先看 §0 结论，再看 §5「不要重复的坑」。**
> 相关：`README_NPC与剧情解包.md`（模型解包主文档）、`TODO.md`、`RDR2_ycd动画解码.md`（解码器原始笔记）

---

## 0. 一句话结论（2026-10-17 第二次更新）

- **模型解包：完成**（354 个 NPC → glTF，可浏览）
- **蒙皮/绑骨：完成**（80 骨，A-pose 干净）
- **骨骼动画：已修好**（见 `RDR2_ycd动画解码.md` §7）。之前"骨架畸形"是四个 bug：
  1. 缓存四元数第 4 分量恒按 `w`（不是 CodeWalker 的 `quat_index` 插位）
  2. `move`（走路）是 **121 帧 / q7** 那条，之前用的 404 帧是 **turn（转身）**
  3. q7 与 `.yft` 参考 rest 不同 ⇒ 每骨常量，用四元数均值 de-bias
  4. Blender 默认 24 fps 把 30 fps 的动画拉慢 25%
- **产物**：`export/npc/player/player_zero_walk.glb`（`rdr2_walk` 4.0 s），
  查看器 `根目录「打开查看器.bat」`（8788 → 首页「角色动画」），验收图 `work/npc/verify/bind_f00*.png`
- **第二轮（同日）**：腿"横着摆"已修 —— 大腿参考帧差 90°（共轭修正）+ 左大腿 z 通道爬升
  假数据（压常量）+ 左腿按右腿半周期复制。现在双脚是**前后迈步**（侧视验收
  `work/npc/verify/side_0*.png`）。
- **手臂已修**：`--keep-arm-bias`（de-bias 会把"手臂放下"的常量一起减掉 ⇒ 僵尸 A-pose）。
- **上身摇晃已修**：根骨轨是 mover 朝向，`--drop-root` 丢掉（yaw 163°→0°）。
- **★★ 关节轴心**：`.yft` 的 bind pos 是 tail，直接当节点位置 ⇒ 大腿转轴落在膝盖、小腿落在脚踝。
  已改为 head=父骨 tail；权重骨段同步改。见 `RDR2_ycd动画解码.md` §7.7(g)。
- **膝弯已修**：`walk_slow` 的 move 是 q7 低细节（小腿 3~6°）；改用
  `arthur@walk_interior` 的 q5 片段（398 帧，小腿 50~56°、抬脚 0.23 m）。
- **手臂已修**：导出加 `--arms-down 45`（世界空间绕 Y 压大臂；Rw 必须按拓扑序算）。

---

## 1. 已完成什么

### 1.1 模型解包（`export/npc/`，1.7 GB）

| 分类 | 数量 | 说明 |
|---|---|---|
| 剧情角色 `cs_*` | 228 | Dutch / Hosea / Sadie / Bill / Charles / Micah / Bronte… |
| 主角 | 2 | `player_zero`（Arthur）/ `player_three`（John） |
| 通用路人 | 6 | 按性别码拼装（非游戏内具名 ped，见主文档 §3-④） |
| 动物 | 118 | 马/狼/熊/鳄鱼… |

每个角色：`<name>.glb` + `textures/*.png` + `manifest.json`（部件/材质/贴图/来源 `.ydd`）。

**浏览入口**
- 静态模型：`根目录「打开查看器.bat」`（8788 → 首页「角色模型 3D」）→ `index.html`
- **带动画**：`根目录「打开查看器.bat」`（8788 → 首页「角色动画」）→ `anim.html`
- 纯骨骼看 12 个原生动作：`export/skeleton_runtime/rdr2_actions.html`（双击即开，无需 bat）

### 1.2 蒙皮 / 绑骨（已完成，可复用）

`tools/blender_bind_player_walk.py` —— 通用：换 `MESH` 路径即可给任意 NPC 绑定。

产物 `export/npc/player/player_zero_walk.glb`（3.4 MB，网格 + 蒙皮 + 动画）。

**验证过的状态**
- A-pose（rest）干净：头在肩正中、脊柱竖直、四肢对称（`work/npc/verify/apose_front/side.png`）
- 权重分布（离地高度 → 主导骨）**解剖学正确**：

```
0.00~0.10 m  鞋底      → Foot
0.10~0.20 m  脚踝      → Foot + Calf 混合
0.20~0.30 m  靴筒      → Calf
0.30~0.45 m  小腿      → Calf
0.45~0.60 m  大腿      → Thigh
```

- 顶点实际位移 平均 0.16 m / 最大 0.56 m（确认网格真被骨骼驱动）

---

## 2. 动画为什么坏 —— 证据链

### 2.1 先排除蒙皮

用 `rdr2_actions.html`（**不经过任何绑定**，直接用解码结果画骨骼）看 `walk`：

> 骨骼本身手臂横张、头后仰、脚底有骨漂移 —— **骨架就已畸形**。
> ⇒ 蒙皮是好的，问题在解码。

### 2.2 量化证据：9 根骨带 ~180° 常量偏移

对 `mech_loco_m@generic@normal@unarmed@walk_slow.ycd` 的两条动画测「每根骨相对 rest 的最大离位」：

| 骨 | 404 帧版 | 121 帧版 |
|---|---|---|
| `SKEL_L_Thigh` | **180°** | 26°（正常） |
| `SKEL_L_Clavicle` | — | **180°** |
| `SKEL_R_Clavicle` | — | **180°** |
| `SKEL_Spine5` | — | **180°** |
| `SKEL_L_UpperArm` | — | **178°** |
| `SKEL_R_UpperArm` | — | **172°** |
| `CH_L_Hand` | — | **165°** |

**判定依据**：这些骨的最大离位是 180°，但**单帧只变 0.3~4°**。真动作不可能这样 —— 是整段被翻过去。

### 2.3 已试过、**没解决**的办法

1. **四元数共轭**（q → q⁻¹）：仍 159~180°，无效
2. **减去首帧偏移**（q ← conj(q[0]) ⊗ q）：中位从 160~177° 降到 2~11°（5 根），
   但 `L_UpperArm` 残留 72°，且**骨架整体仍不像人** ⇒ 只治了标
3. 换 121 帧版（避开 L_Thigh 180°）：腿好了，上半身仍坏

### 2.4 根因假设（下一步要证伪/证实）

`.ycd` 里 `animationNames` = **`biped_q5@biped@0_0.anim` / `biped_q7@biped@0_0.anim`**
⇒ 动画是给**运行期骨架 `biped_q5`** 做的，而我们用的是 `meta_base_player.yft` 解出的 756 骨。

两者在**手臂链 / 颈椎 / Spine5** 这几段上的 rest 朝向不同（不是简单 180°，所以共轭/减首帧都不够）
⇒ 局部旋转套到错误参考系上，产生上面那批"常量偏移"。

这正是项目 `TODO.md` 里的老账：
> **A. 找 `biped_q5` 骨架资源** —— 动画覆盖 69/114 → 接近 114 的钥匙

---

## 3. 下一个 session 建议路线（2026-10-17 上午版，**已被 §0 取代，仅留档**）

### 路线 1（推荐）：重建 `biped_q5` 完整骨架

**可行性已验证**：`.ydd` 里**骨名是明文可读字符串**！

- 位置：每个 sub-drawable 的 `skeleton ptr = drawable+0x18` → `bone_count = skel+0x20`
  → `bones_ptr = skel+0x28`，步长 `0x50`，**每根骨 +0x30 是 `char*` 指向骨名**
- 已成功读出：`MH_Dress_Root`、`ES_HatBrimRoot`、`MH_RearBrimLift`、`CP_brimRight`…

做法：**把一个人所有 `.ydd` 的局部骨架取并集**（名字 + 父索引 + 局部变换），
补出 `yft` 里没有的骨（如 `MH_RearBrimLift`），得到接近运行期的完整骨架，
再用它当参考系重新解码/校正旋转。

### 路线 2（最快出效果）：用外部干净人形动画

现在有 **80 根命名清晰的 `SKEL_*` 骨**（`SKEL_L_Thigh` / `SKEL_Spine5` / …），
可以直接把 Mixamo / UE 的标准走路**按骨名重定向**到这套骨架 —— 完全绕开坏掉的 `.ycd`。
项目里 Blender 重定向流程是现成的（见 `骑砍2动画重定向/pipeline/`）。
**代价**：动作不再是 RDR2 原生；**收益**：一条像样的走路，几小时内可交付。

### 路线 3（兜底）：上肢锁 rest，只播腿

已经能做的状态：腿正常走、上肢保持 A-pose。不抽动，但不好看。

---

## 4. 已知的坑（这一轮踩过，**别再踩**）

### 4.1 格式 / 数据

| # | 坑 | 结论 |
|---|---|---|
| 1 | 顶点 `COLOR0` 当顶点色导出 | RDR2 的 `COLOR0` 是 **palette/tint 选择子**（均值 `(0.107,1,0)`）→ glTF 会乘到 baseColor 上，**整张脸和手变绿**。**不要导出 COLOR_0** |
| 2 | 人物几何的 up 偏移 | 顶点相对"骨盆"存放，Drawable 头里的 bbox 是绝对高度，恒差 **+1.0000 m**（5 个角色实测）|
| 3 | `.merge_N` 理解 | 是**分组**不是整套换装：`merge_17`=大衣组（无头）、`merge_22`=脑袋组。**要跨文件取并集** |
| 4 | `.ytd` 是多纹理字典 | 一个文件里 32+ 张。**必须按"贴图条目名"反查全局索引**（`tools/rdr2_tex_index.py`，32,721 条），按文件名匹配必错 |
| 5 | `_c*_999_ab` / 头发贴图 | 是 tint 遮罩，原文件本身是绿的（`hair_gen_999` RGB≈(52,119,37)）。真色靠调色板（未解）→ 现在**降饱和**处理 |
| 6 | `.ydd` 里的 `BoneIds` 翻译表 | GTA V 的 `DrawableGeometry` 布局（+0x68 BoneIdsPointer）**不适用** RDR2；按它扫 0..0xC0 找不到 |

### 4.2 骨架 / 蒙皮

| # | 坑 | 结论 |
|---|---|---|
| 7 | **bind 里的 `pos` 是骨头的"末端"** | 一根骨的范围 = **父骨 pos → 本骨 pos**。实测 `Pelvis -0.038(髋) / Thigh -0.481(膝) / Calf -0.902(踝)`。按"本骨→子骨"算会**整错一级**（小腿全被判给大腿）|
| 8 | **glTF 没有骨长，Blender 合成的 tail 是错的** | 实测 `Calf` 的 head/tail 的 z 完全相同（水平）。**永远不要用 `bone.tail_local` 算骨段** |
| 9 | 骨热（Automatic Weights）失败 | 游戏网格多壳/非流形 → `total weight = 0.0`。**必须自算权重**（最近骨 + 父/子骨 + 反距离² + 顶点组平滑 12 轮）|
| 10 | 靴子"硬绑到脚骨" | 会让**脚踝折断**、马刺/皮条甩成尖刺。删掉，靠平滑过渡（靴筒→Calf、脚掌→Foot）|
| 11 | 脚趾 3 根骨（Toe0/10/20） | 挨太近会把靴子撕成三块 → **趾骨权重并回 `*_Foot`** |

### 4.3 Blender 5.2 专属

| # | 坑 | 结论 |
|---|---|---|
| 12 | `BLENDER_EEVEE_NEXT` | 5.2 的枚举是 **`BLENDER_EEVEE`**，写 NEXE 抛 TypeError → 脚本中断 → **弹报错窗口，看起来像"卡死"** |
| 13 | Action 有 **slot** 机制 | 重新赋 `animation_data.action` 会**清掉 slot** → 动画完全不生效。**不要重新赋值**；必要时补 `action_slot = act.slots[0]` |
| 14 | glTF 导入器会造 **42 顶点 `Icosphere`** | 骨骼显示占位球（半径 1m）**罩住角色** = 用户看到的"只有一个球"。导入后必须删 |
| 15 | 导出时别把渲染地面带上 | `use_selection=True` + 全选会把 14 m 地面导进 glb → 外部查看器包围盒爆炸、地面挡住腿 |

### 4.4 查看器（three.js）

| # | 坑 | 结论 |
|---|---|---|
| 16 | `file://` 拦 ES module + fetch | three.js 必须**内联成 blob 模块**；glb 必须走 http（bat 起服务）。纯骨骼页（数据内联）可以双击 |
| 17 | `"%~dp0"` 结尾反斜杠 | `--directory "%~dp0"` 会把引号转义掉 → 服务根目录错位、404。用 **`"%~dp0."`** |
| 18 | 蒙皮网格的 `Box3.setFromObject` 不准 | 算出来落不了地（半个身子在地平线下）→ **按已知脚底高度硬定位**（这份 glb 是 `y = -1.019`）|

---

## 5. 工具清单（这一轮新增）

| 工具 | 作用 |
|---|---|
| `tools/rdr2_npc_export.py` | ★ `.ydd`(DrawableDictionary) → glb + 贴图 + manifest |
| `tools/rdr2_tex_index.py` | 全部 `.ytd` 建「贴图条目名 → (文件,下标)」索引（32,721 条）|
| `tools/make_generic_peds.py` | 按性别码拼通用路人的部件清单 |
| `tools/build_npc_viewer.py` | 静态模型浏览页 + bat |
| `tools/build_anim_viewer.py` | 动画预览页 + bat（含落地/取景修正）|
| `tools/build_skel_actions_viewer.py` | 纯骨骼多动作预览（12 个 clip）|
| **`tools/blender_bind_player_walk.py`** | ★ 网格 + 骨架 + 动画 → 蒙皮 glb（自算权重/平滑/趾骨合并）|
| `tools/blender_diag_bind.py` | 诊断渲染：网格 / 网格+骨骼 / 权重着色 |
| `tools/render_exported_glb.py` | 把导出的 glb 重新导回 Blender 渲染（验收文件真身）|
| `tools/open_bind_inspect.py` | GUI 打开 Blender 看模型（**不要在里面做 mode_set/op**，容易弹窗假死）|
| `tools/yldb_dump.py` | `.yldb` → 中文对白文本 |

---

## 6. 复现命令

```bash
cd "D:/BrainMaker/大镖客2解包分析"
UV="C:/Users/yaodongcheng/AppData/Roaming/com.brainmaker.client/cowork-updates/uv-binary/uv.exe"
BL="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"

# 1) 绑骨（当前用 rdr2_walk_ok.gltf：121 帧 + 除常量偏移）
"$BL" -b --python tools/blender_bind_player_walk.py

# 2) 验收（把导出的 glb 重新导回 Blender 渲染 4 帧）
"$BL" -b --python tools/render_exported_glb.py

# 3) 诊断（网格 / 骨骼叠加 / 权重着色）
"$BL" -b --python tools/blender_diag_bind.py

# 4) 看动画
根目录「打开查看器.bat」        # 8788 → 首页「角色动画」
export/skeleton_runtime/rdr2_actions.html   # 纯骨骼，双击即开
```

---

## 7. 下一 session 的第一个动作

```bash
# 确认现状（1 分钟）：打开纯骨骼页，看 walk 是否仍畸形
start "" "D:/BrainMaker/大镖客2解包分析/export/skeleton_runtime/rdr2_actions.html"
```

然后按 §3 选路线。**别再动蒙皮** —— 蒙皮已经验证是好的（A-pose 干净 + 腿部权重解剖学正确）。
