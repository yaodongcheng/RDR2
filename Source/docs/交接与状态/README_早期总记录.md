> ⭐ **直接看这里 → [`README_交接.md`](README_交接.md)**
> （当前项目状态、交付物清单、复现命令、已知缺口、下一阶段；本文是早期资产提取的总记录）
>
> **2026-10-19 最新**：任务解析已做到「目标清单 → 任务树（大步骤/小步骤）→ 微步骤事件（S/A/B 分级）→ 对白归属」；
> 查看器升级为 12 页成果总览；样例见 [`RDR2_任务逐步骤拆解_WNT1.md`](RDR2_任务逐步骤拆解_WNT1.md)。

---

# 荒野大镖客 2 解包分析 · 交接文档

> ⭐ **想快速了解当前进度，先看 [`README_交接.md`](README_交接.md)**（最新状态 / 交付物 / 缺口 / 下一阶段）；`README_进度总结.md` 是 2026-10-18 的历史进度快照。
> 本文是完整技术文档（几何、动画、骨架、贴图材质、CodeWalker 对照等七大专项）。

> 工作目录：`D:\BrainMaker\大镖客2解包分析` ｜ 游戏：`H:\EPICGAMES\RedDeadRedemption2`（Epic）
> 最后更新：**2026-10-19** ｜ 本文件是**总纲**。历史 session 原文已归档到 **`交接历史.md`**。

**七份专项笔记**（细节都在这）：

| 文件 | 内容 |
|---|---|
| `RDR2_ycd动画解码.md` | 动画容器 + RAGE 通道编解码（含 §6.9 通道层两个真 bug）|
| `RDR2骨架_yft格式.md` | 骨架二进制结构（§2.9 bind 矩阵布局、**§2.10 骨名池**）|
| `RDR2_ydr几何格式.md` | `.ydr/.ydd/.yft` 几何、顶点布局、地形 LOD、材质 |
| `RDR2地形与城镇.md` | 地形 + `.ymap/.ytyp` + Valentine 复原 |
| `RDR2_CodeWalker对照笔记.md` | **与社区权威实现逐行对照**（含社区教程/工具清单）|
| `RDR2_REA反编译笔记.md` | REA/Ghidra 反编译 `RDR2.exe` 的结论（含"别再投"的理由）|
| ⭐ **`README_贴图与材质管线.md`** | 贴图/材质全流程：`.ytd` 结构/格式表/名字三坑/shader slot 语义/UV 来源/三级解析/9 条踩坑对照 |
| ⭐ **`RDR2_世界地图与据点浏览.md`** | **整个世界地图 + 真地形 + 全据点浏览**：`mapzones.meta` 官方区划、**`heightmap.dat` 经判据证明不是世界地形**、**真地形从地形瓦片重建的完整方法**（§2.1b：世界坐标 = `*_strm_0.ymap` 实例摆放，z0 = 基准高程）、相机与 OrbitControls 方向约定、「按需加载不卡」架构 |
| ⭐ **`RDR2_据点与城镇清单.md`** | **【本轮新增】43 个据点/城镇的正式化清单**：188/130/43 三个口径纠错、官方 zone vs 实测建成区的尺寸校准、按 848 大地图 / 1000 村庄 / 1200 城堡 / 3000 大城市 / 800 藏身处 / 2000 野战映射、逐条尺寸+坐标+大地图 uv；附 `settlements.csv/json` + 分布图 |
| ⭐ **`RDR2_骑砍2落地_势力与NPC.md`** | **【本轮新增】骑砍2 落地版**：10 城 / 11 堡 / 12 村 / 4 营地 / 4 野外点位 / 2 藏身处；12 个村全部绑定城或堡（远郊牧场升城堡、独屋改点位）；8 个势力 + 家族 + 领主逐条归属；**142 个具名角色**（势力/常驻地/置信度）；另附 **53 个城镇专属服务语音库**（店主/医生/警长）；产物 `settlements_bannerlord.csv`、`npc_roster.csv`、`service_npcs.csv`、`faction_map.png` |
| ⭐ **`RDR2_剧情与角色覆盖审计.md`** | **【本轮新增】剧情覆盖审计**：270 条任务定义（105 主线 + 121 支线/赏金）、1929 个对白文件（33.9 万条）、**181/181 过场包全解**（5,237 个 ycd/yad）、任务→角色 cast 映射（181 个出场角色）；明确缺口：`.ysc` 任务脚本仍为 0 |
| ⭐ **`RDR2_任务逻辑与武器道具破解.md`** | **【本轮新增】任务/武器/道具破解报告**：270 任务 + 261 目标 + 181 过场 cast；142 条 `CWeaponInfo`（118 字段 schema）、24 把 MP 武器数值、28/28/13 弹药、174 个武器资产；道具 `catalog_sp.ymt` 47 类型 schema。**明确卡点：`.ysc` 任务脚本 = 0、142 条武器名哈希未映射、道具 items Map 未走通** |
| ⭐ **`RDR2_武器道具模型与剧本对白.md`** | **【本轮新增】模型与对白**：武器 **289 模型 + 224 贴图**（513 文件，174 base）；道具 **10 个 prop 包、2,071 模型 + 884 贴图**（2,955 文件）；对白 **339,635 条**（中文 153,830），其中 **302 个任务音频库 49,290 条纯中文**已按任务/音频库拆分导出（原始 99,532 行含二进制噪声，已过滤） |
| ⭐ **`RDR2_模型图标与综合查看器.md`** | **【本轮新增】模型/图标/查看器/对白归属**：背包道具 2,071 模型（查看器 916）+ 武器 289 模型（查看器 45 把完整武器）；**HTML 查看器** `export/viewer/index.html`（45 把中文武器 + 916 背包道具 + 任务/对白 + 3D + 透明图标）；道具 446 张 albedo 贴图、武器 142 张法线贴图已接；对白 49,290 条中文（已清噪） |

---

## 0. 一句话现状

**四类格式（RPF8 / 几何 / 纹理 / 动画）+ 骨架 + 到骑砍2 的重定向全部打通**；
其中 `.ycd` 解码器已与社区权威实现（CodeWalker `Clip.cs`）**逐行对照确认一致**，
并且在 `CachedQuaternion2` 上**比 CodeWalker 更正确**（CodeWalker 根本解不了 RDR2 的 `.ycd`）。

### 0.1 能力矩阵

| 方向 | 状态 | 一句话 |
|---|---|---|
| 资产提取（RPF8） | ✅ | 自建 C# 提取器，从 20+ GB 级 `.rpf` 提出 **2 万+** 文件 |
| 几何 `.ydr/.ydd/.yft` | ✅ | 顶点是**平面分属性数组**；变换校验 ratio **1.000（38/38）**；LOD/碎片/道具全解 |
| 纹理 `.ytd` | ✅ | **27/27 完美 + 外部 mod 72 张验证通过**；纹理表基址**自动定位**（T2 已关）|
| 动画 `.ycd` | ✅ | 9 类通道全通；**权威对照确认**；语义已定（见 §0.2）|
| 骨架 | ✅ | **bind 矩阵布局 + 骨名池全解**（`yft_bind.json` 1050 tag / `player.yft` 756 骨全命名）|
| 地形 / 城镇 | ✅ | Valentine **2128/2263 实体（94%）** + 连续地形 + 树木 |
| **→ 骑砍2 重定向** | ✅ | **10 个 clip 全部过出厂闸门**；**28/28 映射骨** |
| ⭐ **材质 / UV** | ✅ | **真 UV**（`VertexDeclarationG9`）+ **按 shader slot 语义取材质**（195 shader 表）|
| ⭐ **小镇可视化** | ✅ | `town_textured.html`：69 栋高清建筑 + 高度场地形（**局部校准场**）+ 728 棵树 + 道路 |
| ⭐ **整个世界地图 + 真地形** | ✅ | `world_map.html`（**6.5 MB，单文件可用**）：**真地形**（30,697 个游戏地形 patch = 全集，对拍 RMSE 15 m）+ **官方几何配色**（STATE 并集 + 35 个官方水体）+ 130 个具名据点**内嵌**、58 个区域网格外部懒加载；点开据点默认给**灰盒**，可一键切 **L2 真模型**（已做 **Valentine** 69网格/22MB、**Annesburg** 162网格/43.5MB）。`heightmap.dat` 经判据证实**不是**世界高程（§2.1） |
| **CodeWalker XML** | ✅ | 自建读写 `rdr2_cwxml.py`（**不依赖 CodeX**）|
| 角色骨架/动画可视化 | 🟡 | 静态骨架 ✅（72 根 `SKEL_*`）；`walk` 播放器 ✅ 但**姿势不对**（见 §0.3-W1）|

### 0.2 ★ 已彻底解决的三条根因 —— **别再重复排查**

| # | 根因 | 正解（结论） | 验证 |
|---|---|---|---|
| 1 | **`.yft` 骨架 rest 是"退化"的** | `TransformationsInverted` 的 64B 块是**行向量仿射**（存 bind 全局的**逆**）⇒ `bind_rot = R(存储 3×3 原样)`、`bind_pos = −R·t`。**别用骨记录 (t,q) 做 FK**（那是"直骨姿势"）| 与既有产物 `player_bind_pos.json` 对拍 **755 骨误差 8e-6**；abe 出 **1.953 m** 干净 A-pose；RAGE 骨轴不变量 `R_parentᵀ·Δ ≈ (len,0,0)` |
| 1b | **`.yft` 骨名池解不出** | **`骨名 = NUL 字符串，起点 = NamePointer − 0x50000000 + 0x10`**（指针落在**上一个名字内部**）| delta=**0x10** → 31/34 命中（3 例=1 大小写 + 2 个 tag 空间碰撞）；`0x00/0x08/0x18` 全 0 |
| 2 | **动画"不自然"** | `.ycd` 的四元数是**相对 bind 的增量** ⇒ **`R_pose = R_bind ⊗ q_anim`**（不是绝对局部旋转）| 判决实验：`abs`→骨架坍缩(head.z 0.15)；`q⊗R_bind`→倒立(−0.50)；**`R_bind⊗q`→head.z 0.58/双脚行程 0.115 m** ✅ |
| 3a | **`SKEL_L_Thigh` 整条旋转轨被误杀** | `CachedQuaternion2`(type 8) 必须**走缓存四元数路径**（只存 3 分量、w 由模长补全）。原实现只认 type 7 ⇒ 把 3 个**位移浮点**当 x,y,z ⇒ `\|q\|=0.182` 被过滤 | 修后 `\|q\|=1.0000`；`L_Thigh` maxstep **65.8°**（走路本就该最大）；★ **CodeWalker 的 `Clip.cs` 里 `EvaluateQuaternionType7` 明确支持 slot 4 的 Q2**，只是入口被 `IsType7Quat` 门控漏了 ⇒ **我们比它更正确** |
| 3b | **混入非旋转轨 / 漏真旋转轨** | `Bones` 元素 = `{u16 boneId, u8 Unk0, u8 Track}`，**只有 `Track==1` 是旋转轨**（0x3b/0x8a/0x06/0x00 是位置轨）| 实测该文件 `Track==1` 恰好 24 条旋转轨；旧启发式（通道数+单位四元数）会混入位置轨 |
| **4** | ⚠️ **"顶点里没有 UV / 只有 40B 未知属性"是错的** | 顶点语义在 `VertexBuffer+0x38` 的 **`VertexDeclarationG9`**（RDR2 是 **SOA**，GTA V 是 AOS）。按声明读：建筑 = `POSITION/NORMAL/TANGENT/COLOR0/TEXCOORD0/TEXCOORD1`（40B）、地形 = `+TANGENT1/COLOR1/COLOR2/TEXCOORD0-2`（56B）| `tools/rdr2_vdecl.py` 实测：UV 随位置**线性**（`val_03_saloon_ext` geom1 `\|Δuv\|/\|Δpos\|` med 0.9929 / MAD 0.114）；地形 UV0 全局拟合 `1/a≈512 m` |
| **5** | **建筑/地形"贴图错"的根因** | 游戏是**分层材质**：建筑 `standard`/`standard_2lyr`/`standard_dirt`（`_ab` + `_abal` 用 `_ma` 遮罩混合 + `_pal` 调色板，`COLOR0` 逐顶点选择子）；地形 `terrain_uber_4lyr_*`（宏观色图 `l_09_t` 2048² + `_bkt_*.ytd` 图层集 + 混合遮罩 + 逐顶点权重）| shader 名由 `ShaderFX.Name`(joaat) 对 `names.txt` 的 `*/db/*.sps` 反查，**全部命中** |
| **6** | **`.ytd` 解码器静默丢格式** | 旧 `entries()` 有 `if f not in FMT: continue`，而 `FMT` 只有 BC1/BC3 ⇒ **调色板(0x5B B8G8R8A8) / BC7 / BC5 一律被当不存在** | 已扩 BC7(DX10 dxgi 98)/BC5/BC4/BGRA8/RGBA8；并修 `ytd_to_png.py` 自带假基址 bug（改复用 `rdr2_ytd.Ytd`）|
| **7** | ⚠️ **shader 纹理数组步长 bug** | `grmShader.m_textureRefs` 是 `pgPtr<grcTextureRef>` 数组、**元素 8 字节**、长度 = `m_parameterData.numTextures`；旧实现按 **16 字节**读 ⇒ 只读到**偶数 slot** ⇒ 材质全错位 | 权威依据 `citizenfx/fivem → rage-formats-x/include/rmcDrawable.h`（RDR3 分支）；修后 terrain=16 / standard=7 / standard_dirt=9 与 `ModRDRShaders.xml` **完全一致**；新增 `tools/rdr2_shader_params.py` |

### 0.3 🔴 未解决（按**价值**排序，含入口）

| # | 任务 | 价值 | 入口 / 证据 |
|---|---|---|---|
| **W1** ⭐ | **修 `walk` 的 `SKEL_L_Thigh` 坏轨** | ⭐⭐⭐ 让走路像人 | **已定位**：该轨是 `CachedQuaternion2`，w 连续 20+ 帧=0、角度饱和 180°、周期 202 帧（R_Thigh 是 40 帧）。5 种旋转合成与查看器均**已排除**（Blender 复算一致）。疑点：CachedQ2 落 slot 4（slot3=NULL），3 分量取 slot 0/1/2 还是 1/2/3；或该通道 `QuantizeFloat` 头读偏 2 字节。入口 `tools/rdr2_ycd.py` 的 `ChCachedQuat._v()` |
| **T1** ⭐ | **把地形宏观色图 `l_09_t` 接上** | ⭐⭐ 地面立刻像游戏 | 已抽到 `export/models/textures/terrain_l09/`（2048² 就是瓦伦丁俯视地表色：镇子/道路/河）；地形层 = `terrain_uber_4lyr` 4 层 + `lookuptexture`(`l_09_c`) + `tinttexture`(`l_09_t`) |
| **T2** | HD 地形瓦片 `l_09__hd_0_*` 世界摆位 | ⭐⭐ 地形 100% 贴合 | 网格已抽（stride 56，UV0 是**全局平面映射** `u=0.00192·x_local+b`，`1/a≈512 m`）⇒ 可用 UV 反推摆放 |
| **R1** | 道路接缝（首尾连接） | ⭐ 观感 | 20 块 decal 拼的；A: 拼成连续路带重算 UV / B: alphaTest 裁边 / C: 直接用 `l_09_t` 里的路网色 |
| **P1** | `cpv_only` 网格是灰块 | ⭐ 观感 | 该 shader 本就无贴图、颜色来自逐顶点 `COLOR0`；**本轮没导出 COLOR0** ⇒ 灰块。修法：导出带 `col` + 材质开 `vertexColors` |
| **A0** | ⭐ **用地形瓦片素材 + 分层材质重做 Valentine 的"地面/建筑"外观** | ⭐⭐⭐ 直接修"贴图都是错的" | 素材从未缺失，只是没抽/没按分层用：<br>① 地形：`levels_5.rpf → levels/rdr3/terrain/jklm_07_10/<j..m>_<07..10>_.rpf` → `<tile>_.ytd`(**含 `l_09_t` 2048² 宏观色图**)/`+hi`/`_bkt_*.ytd` + `<tile>__hd_0_i_j.ydr`(stride 56)<br>② 建筑：`standard_2lyr`/`standard_dirt` 的 `_ab`+`_abal`+`_ma`+`_pal`；共享 `.ytd` 在 `levels/rdr3/gtxd/<area>_gtxd`<br>③ 工具：`tools/rdr2_vdecl.py`（顶点声明/UV/权重）、`ytd_to_png.py`（BC7/BC5/BGRA 已补） |
| **A** | **找 `biped_q5` 骨架资源** | ⭐⭐⭐ 动画覆盖 **69/114 → 接近 114**，且可能补上 6 根 roll 骨 | `rdr2mods.com/wiki/animations/records/`（**13000 条动画库**）；`.ycd` 里 animation 名 = `biped_q5@biped@0_0.anim`；exe 里搜不到该串（已排除）|
| **B** | **6 根手臂 roll 骨**（`SKEL_L/R_UpperArm_02_01`、`Forearm_01_01`、`Hand_01_01`）**在任何 `.yft` 里都不存在**（连社区"终极骨架"mod 也没有）⇒ 只存在于**运行期合并骨架** | ⭐⭐ 手臂链精度 | 社区工具正对这个：`github.com/ultrahacx/Sollumz-RDR/tree/extra-skeleton-fix`、`nexusmods.com/reddeadredemption2/mods/9845`（"**extra skeletons in drawables**"）。现用"从运行期骨架接回 + 几何回退" |
| **C** | **单帧台阶**（walk f202/f121 等，多骨同帧） | ⭐ 观感 | **已定性：不是解码 bug**（通道类型/Sequence 布局/bit 提取/各通道取值/chunk 取值全与权威一致；出问题的轨道是 `QuantizeFloat`，全局 ValueBits 无 chunk）。剩两说：真实快速动作 / 段边界（walk 恰在 `404/2=202`）。**定论需进游戏对拍 f118~f124 画面** |
| **D** | 6 根"额外骨"以外的**骨名池边角** | ⭐ 低 | CodeX/社区工具**重写过的 `.yft` 内部布局会变**（名字指针 `+0x40`、tag `+0x0a`、骨表基址偏移）⇒ `yft_bind.py` 的常量只对 vanilla 家族成立 |
| **E** | 40 张未解包的共享 `.ytd`（现走"同族最近邻回退"）| ⭐ 低 | 从游戏包补抽对应 `.ytd` |

### 0.4 命令速查（端到端，可直接复制）

```bash
UV="C:/Users/yaodongcheng/AppData/Roaming/com.brainmaker.client/cowork-updates/uv-binary/uv.exe"
BL="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
DOTNET="C:/Program Files/dotnet/dotnet.exe"
cd "D:/BrainMaker/大镖客2解包分析"
RD="D:/BrainMaker/骑砍2动画重定向"
RP=tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe

# ---- 0) 资产提取（RPF8）----
$RP extract "<某.rpf>" work/xxx "关键词"            # list / tree / find / extract

# ---- 1) 骨架：抽 bind + 骨名（player+abe+male 合并）----
$UV run python tools/yft_bind.py
#   → export/skeleton_runtime/yft_bind.json（1050 tag 的 bind）
#   → export/skeleton_runtime/yft_skel.json（player 756 骨：i/tag/parent/**name**）

# ---- 2) 动画：.ycd → JSON（含 Track 过滤 + CachedQ2 + 孤立尖峰修复）----
$UV run python tools/export_anim_json.py "<某.ycd>" /tmp/a.json

# ---- 3) 源骨架导出（★ --skel yft：.yft 骨架 + 接回 6 骨 + 重挂父 + 臂链串线）----
$UV run python tools/export_gltf_source.py /tmp/a.json $RD/input/source/rdr2/<clip>.gltf \
        --name <clip> --skel yft

# ---- 4) 重定向（★ pelvis 按 clip 类型选：站立类 ground / 被扛类 delta）----
cd $RD && "$BL" -b --python pipeline/rigs/rdr2/retarget.py -- \
        --action <clip> --name <out> --pose align --pelvis ground --dump output/verify/dump_<out>.json

# ---- 5) 出厂闸门 ----
"$BL" -b --python pipeline/common/verify_modkit_fbx.py -- --fbx output/fbx/<out>.fbx

# ---- 6) 批量（幂等，已产出的自动跳过）----
bash "C:/Users/yaodongcheng/AppData/Local/Temp/codemaker/rdr2/batch_v14.sh"

# ---- 7) 纹理：单文件游戏格式 RSC8 解压 + .ytd 解码（基址自动定位）----
$UV run python tools/rsc8_standalone.py "<某.ytd>" /tmp/body.bin
$UV run python tools/ytd_to_png.py "<某.ytd>" export/models/textures/xxx

# ---- 8) 权威交叉验证（CodeWalker 的编译库 + .NET9）----
cd tools/ref/CWProbe && "$DOTNET" run -- "<某.ycd>" <chunk偏移hex> <animSeq下标>
```

# ---- 9) 贴图/材质 + 小镇可视化（本轮新增）----
$UV run python tools/rdr2_shader_params.py                    # shader → slot → 参数名（195 个）
$UV run python tools/rdr2_vdecl.py <某.ydr> [--check]         # 顶点声明 / UV / 权重
$UV run python tools/ytd_to_png.py <某.ytd> <outdir>          # 解码（BC1~BC7/BGRA，保留 alpha）
$UV run python tools/export_building_materials.py && $UV run python tools/build_material_viewer.py   # 4 栋近景
$UV run python tools/export_town_textured.py  && $UV run python tools/build_town_textured_viewer.py  # 整镇+地形+树
$UV run python tools/build_skel_viewer.py                     # 骨架查看器
$UV run python tools/build_walk_viewer.py                     # walk 动画查看器
$UV run python tools/rdr2_cwxml.py <某.ydr> <out.xml>         # 自建 CodeWalker XML（给 Blender）
$RP extract "H:/EPICGAMES/RedDeadRedemption2/levels_2.rpf" work/gtxd "levels/rdr3/gtxd/gtxd_valentine.rpf"  # 小镇共享纹理字典

# ---- 10) 世界地图 + 全据点（本轮新增）----
$RP extract "H:/EPICGAMES/RedDeadRedemption2/common_0.rpf" work/worldmeta "data/levels/rdr3/mapzones.meta"  # 官方区划
$UV run python tools/parse_mapzones.py       # mapzones.meta -> export/levels/world/zones.json
$UV run python tools/export_world_towns.py   # 4163 ymap -> towns.json + town_data/*.js (188 个)
$UV run python tools/build_world_map.py      # -> export/levels/world/world_map.html

**环境要点**：网络只通 `github.com / api.github.com / **codeload.github.com**`（可拉源码，拉不到 release 附件/PyPI）；
Office 走 `bm-office`；REA/Ghidra 见 `RDR2_REA反编译笔记.md`（**导入用 `-import … -noanalysis` 才快**）。

### 0.5 产物索引

| 想要什么 | 去哪 |
|---|---|
| ⭐ **整个世界地图 + 逐个据点（双击即开）** | `export/levels/world/world_map.html`（`?town=val` 直接进某镇 / `?all=1` 显示全部标记）|
| ⭐ **瓦伦丁小镇（真 UV + 原生贴图 + 地形 + 树）** | `export/levels/town/town_textured.html`（`?v=0 全镇 / 1 主街 / 2 街口`）|
| ⭐ **4 栋建筑材质近景 + 逐几何体材质清单** | `export/levels/town/materials_demo.html` |
| ⭐ **角色骨架 / walk 动画** | `export/skeleton_runtime/{rdr2_skeleton.html, rdr2_walk.html}` |
| ⭐ **CodeWalker XML 样本** | `export/cwxml_samples/*.xml` |
| **Valentine（旧版：box map 材质）** | `export/levels/town/valentine_real.html` |
| **骨架定义 / bind / 骨名** | `export/skeleton_runtime/{yft_bind.json, yft_skel.json, rdr2_skel_runtime.json, skel_full.tsv}` |
| **骑砍2 产物（最新一版）** | `骑砍2动画重定向/output/{fbx,trf}/rdr2_*_v14.{fbx,trf}`（10 套）|
| **源侧对照图** | `骑砍2动画重定向/output/verify/strip_v7b_*.png`、`strip2_*.png` |
| **纹理样例（含外部 mod 验证）** | `export/models/textures/{val_01_trainstn, mod_karen, proc}` |
| **权威源码 / 探针** | `tools/ref/{CodeWalker-master, AnimKit-master, CWProbe}` |
| **动画** | `export/animations/`（407 个 `.ycd`）|

### 0.6 踩过的坑（跨轮次汇总，**别再犯**）

1. **别用 `.yft` 骨记录 FK 反推 bind** —— 那是"直骨姿势"，脊柱与腿会同向。
2. **平移与旋转必须同时做坐标变换** —— 只共轭旋转会让局部位移落在错坐标系。
3. **改父/串链后必须走拓扑序** —— "父索引 < 子索引"不再成立，按 `sorted()` 遍历会 `KeyError` 或**静默用 identity 当父矩阵**（已加 `topo_order()`）。
4. **`Tag` 只能同物种对齐** —— 鸟骨架与人有 90 个 tag 重合但位置中位差 0.49 m。
5. **DDS 头必须正好 128 字节** —— 多写 4 字节 ⇒ 像素偏移 ⇒ 全 noise（会被误判成 tile/swizzle）。
6. **`.ytd` 纹理表基址每文件不同**（实测 0x40 / 0x2e0 / 0x360）—— 用 `find_base()` 自动定位，别硬编码。
7. **源 glTF 动画的时间轴是"秒"** —— 取帧必须 `argmin|t − frame/30|`，否则 f≥40 全取到最后一帧（曾因此白查半天）。
8. **glTF(Y-up) ↔ RDR2(Z-up)** —— 两侧关节对比时源侧要 `(x,−z,y)` 换回来，否则恒差 ~90°。
9. **验证产物前先确认文件真的写成了** —— 导出脚本报错时可能没落盘，而你一直在验证上一版。
10. **一个 `.ycd` 常有多段动画**（人/马/道具/base）⇒ 按**总运动量**选段，不能取第一段。
11. **`--pelvis` 必须按 clip 类型选**：站立类（walk/injured_idle）用 `ground`；**被扛/上马/搬运类必须用 `delta`**（否则逐帧贴地会把"被抬起"压回去，骨盆行程被放大 6.5×）。
12. **查看器按 clip 名两侧配对** —— 目标侧 GLB 的动画名必须 == 源侧 clip 名，否则停在 rest。
13. ⚠️ **Chrome 对同名 `file://` 页面有缓存** —— 改了代码截图却拿到旧图（会误判"改了没生效"）。**每次截图换新文件名**。
14. **three 的 `onBeforeCompile` 必须配 `customProgramCacheKey`** —— 否则打过补丁的材质会与同类 Lambert 共用 program（世界空间 UV 会污染建筑）。
15. **导出贴图必须保留 alpha** —— `decode_one` 旧版在末尾 `convert('RGB')` 抹掉 alpha，道路/贴花（decal）靠 alpha 混合 ⇒ 变成"实心白带"。
16. **几何体↔材质不能按下标对齐** —— `extract_at` 会跳过没有 VB 的几何体，下标错位 ⇒ 贴图挂错面。**按几何体自己的 `ShaderID`** 取。
17. **`.`ytd` 名字可能是粘接名**（`X_abX_al`）—— 切分要"第二段以第一段前缀开头"才算，别用单字母后缀硬切（会误伤 `cor_dr_*`）。
18. **地形基准不要用常量** —— 用**建筑底座**推出来的**局部校准场**（128² 网格 + 平滑 + 双线性），否则建筑会悬空/埋进土。
19. **shader 纹理数组步长 8 字节**（不是 16）—— 见 §0.2 第 7 条。

---

## 0.7 目录导航（找东西看这里）

> 所有本 session 的知识、产物、工具**都在 `D:\BrainMaker\大镖客2解包分析` 内**，没有散落在别处。

### 知识与结论（Markdown）

| 文件 | 内容 |
|---|---|
| `README.md` | 总纲（§0 = 接手速览：现状 / 已解决根因 / 未解决+入口 / 命令 / 产物 / 坑）|
| `RDR2_ydr几何格式.md` | **本轮重点**：`.ydr/.ydd/.yft` 几何、顶点布局、archetype 映射、变换校验、地形 LOD、植被实例、逻辑体过滤、box mapping 材质、纹理解码排除清单（§11–§18）|
| `RDR2_ycd动画解码.md` | 动画容器 + RAGE 通道编解码 |
| `RDR2骨架_yft格式.md` | 骨架结构 + 卡点 |
| `RDR2地形与城镇.md` | 地形 + `.ymap/.ytyp` + 城镇复原 |
| `README_资产提取.md` | RPF8 提取器 + 资产清单 |
| `交接历史.md` | **历史 session 记录归档**（15 段，按时序）|

### 交付产物

| 想做什么 | 去哪 |
|---|---|
| **看 Valentine（双击即开）** | `export/levels/town/valentine_real.html`（46MB，含地形/材质/真房子/灰盒/调试按钮）|
| 截图 | `export/levels/town/valentine_real_{default,mid,nobox,material,debug,close}.png` |
| 网格数据 | `valentine_{meshes,lod_meshes,prop_meshes,veg_meshes,veglod_meshes,terrain_meshes}.json`（都在 `export/levels/town/`）|
| 摆放表 | `export/levels/town/{terrain_instances,veg_instances,valentine_veg_instances,arealod_all_entities,lod_all_entities}.json` |
| 网页依赖 | `export/levels/town/three.module.js` + `addons/`（three.js 库，供各查看器内联使用）|
| 纹理 | `export/models/textures/`：`val_01_trainstn/*.png`（BC 解出的 27 张）、`sheet_bc3.png`/`sheet_trainstn.png`（拼图）、`proc/wood_wall.png`·`proc/plaster.png`（程序化材质）、`tex_wood.png` |
| UV/材质诊断页 | `export/levels/town/uv_probe/{uv_candidates,triplanar_test}.html` |
| 原始资产 | `export/{animations,models,levels}/` |

### 工具（全在 `tools/`）

| 工具 | 作用 |
|---|---|
| `rdr2rpf/`（C#） | RPF8 提取器（核心）|
| `rdr2_ydr.py` | `.ydr`/`.ydd` 网格解析（`extract` / `extract_at` / `extract_ydd` / `extract_frag`）|
| `rdr2_ytd.py` / `ytd_to_png.py` | `.ytd` 纹理表解析 / 按 BC 格式解 PNG |
| `ymap_entities.py` / `ytyp_archetypes.py` / `rage_meta.py` | `.ymap/.ytyp` 实体与原型 |
| `parse_veg_instances.py` | 植被实例（368B 记录）|
| `export_{building,lod,prop,veg,area_terrain}_meshes.py` | 各类网格导出 |
| `build_valentine_real.py` | 生成查看器（box mapping 材质在这里）|
| **`memscan.py`** | **运行期只读内存取证**（下一轮 T0 用）|
| `uv_probe.py`（+`uv_probe_template.html`） / `triplanar_probe.py` / `uv_probe_page_gen.py` | UV / 材质诊断页生成 |

> 注：`export/levels/town/area_lod_entities.json`、`lod_entities.json` 是早期版本的摆放表，已被 `*_all_entities.json` 取代（保留仅供追溯）。

### 临时/中间产物 —— ✅ **已清理（2026-10-14）**

原本 `work/` 下约 **14 GB** 中间输入（nested / props / veg / valarea / lod* / inst*）**已全部删除**，
项目从 27 GB 降到 **13 GB**，且**不影响 `export/` 里任何产物**（`export/models/` 里已保存全部抽好的模型：
道具 797、植被 1368、建筑 1747、LOD 454）。

> 需要重跑某一步时，按 **§6.1「重跑管线的输入准备对照表」** 从游戏包重新抽出输入即可。

---

## 1. 环境与约束（接手先看）

| 项 | 情况 |
|---|---|
| OS | Windows 11 |
| 语言/运行时 | `.NET 9`（`C:\Program Files\dotnet`）、Python 3.12（走 `uv`，见 §6）|
| 网络 | **只有 `github.com` / `api.github.com` / `codeload.github.com` 可达**；`raw.githubusercontent` / `objects.githubusercontent`（release 附件）/ PyPI / NuGet / crates.io **全部被墙** |
| 影响 | ❌ 拉不到任何二进制工具（CodeX/OpenIV）；✅ 可以从 codeload 下载源码自己编译 |
| PowerShell/cmd | 禁用；用 bash（Git Bash 语义）|
| 逆向工具 | **REA（`rea` CLI，内置）+ 本机 Ghidra 12.1.4 + JDK21** 已就绪，可反编译 native：<br>`export GHIDRA_INSTALL_DIR="D:\\BrainMaker\\tools\\re\\ghidra"; export JAVA_HOME="D:\\BrainMaker\\tools\\re\\jdk21"; export PATH="/d/BrainMaker/tools/re/jdk21/bin:$PATH"`<br>⚠️ `rea analyze RDR2.exe`（89 MB）会 **330 s 超时**，需分片/换小目标 |

> 关键第三方工具 **CodeX**（dexyfex，RDR2 的官方级资产工具）**闭源且拉不到**，
> 所以本项目所有解析器都是**自己逆向 + 移植 CodeWalker 的公开源码**写出来的。

---

## 2. 目录结构

```
大镖客2解包分析/
├─ README.md                    ← 本文件（总纲/交接）
├─ README_资产提取.md            ← 资产提取详解（原 README）
├─ RDR2_ycd动画解码.md           ← 【专项】动画容器 + RAGE 通道编解码
├─ RDR2骨架_yft格式.md           ← 【专项】骨架二进制结构 + 卡点
├─ RDR2地形与城镇.md             ← 【专项】地形 + .ymap/.ytyp + 城镇复原
├─ RDR2_ydr几何格式.md           ← 【专项】.ydr 几何/顶点格式（已攻克）
├─ inventory.csv                ← 20,074 个导出文件的清单（路径/大小/魔数）
├─ export/                      ← 交付产物（约 8.7 GB）
│  ├─ animations/               ← 407 个 .ycd（含"扛人上马"全流程）
│  ├─ models/                   ← player 1458 / weapons 514 / fragments 419 / buildings
│  ├─ levels/                   ← map_metadata 4228+1026 / collision 12301 ybn / terrain / town
│  └─ rdr2_decode_preview/      ← 动画/骨架的 HTML 验证预览
├─ tools/                       ← 全部自建工具（见 §5）
└─（work/ 已清理，见 §0.7）
```

---

## 3. 已完成（按模块）

### 3.1 RPF8 提取器（工具链，最底层）

RDR2 用 **RPF8**（魔数 `0x52504638`），与 GTA V 的 RPF7 **不同**，且：
- **目录表(TOC)被 TFIT2 密码加密**（开源库 `rage-rpf` 明确不支持）
- **条目只存 32 位 JOAAT 哈希，不存文件名** → 需要外部 name 表（已带 29.4 万条）
- 文件数据 **Oodle 压缩** → 用游戏自带 `oo2core_5_win64.dll` 解压

做法：从 GitHub 取 RDR2 RPF8 参考实现（`lazenes/RPF8_TOOL`、`amrshaheen61/RDR2-RPF-Tool`，
内含 TFIT2 密码 + PC 密钥表 + names 表），用 **dotnet 9 编译成命令行提取器**。

```
tools/rdr2rpf/                      ← 工具源码 + 构建产物
  ├─ Program.cs                     ← CLI（list / find / tree / extract / rawdec）
  ├─ src/                           ← RPF8/Cipher/RSC8/KeysContainer/names.txt（参考 Core）
  └─ bin/Release/net9.0/rdr2rpf.exe ← 可执行
```

用法：
```bash
rdr2rpf list    <archive.rpf>
rdr2rpf tree    <archive.rpf>
rdr2rpf extract <archive.rpf> <outdir> [关键词] [--recurse]
```

### 3.2 已提取资产清单

| 类别 | 位置 | 数量 | 体量 |
|---|---|---|---|
| 动画 `.ycd` | `export/animations/` | **407** | 34 MB |
| 角色模型（主角）`.ydd/.yld` | `export/models/player/` | 1458 | 304 MB |
| 武器 `.ydr/.ytd` | `export/models/weapons/` | 514 | 213 MB |
| 人物碎片 `.yft` | `export/models/fragments/` | 419 | — |
| **建筑模型 `.ydr` + 贴图 `.ytd`** | `export/models/buildings/val_01_/` | 32 + 23 | 75 MB |
| 地图元数据 `.ymap/.ytyp` | `export/levels/map_metadata/` | 4228 + 1026 | 86 MB |
| 地形碰撞 `.ybn` | `export/levels/collision/` | 12,301 | 8.0 GB |
| 地形高度 `heightmap.dat` 等 | `export/levels/terrain/` | 6 | 17 MB |
| 城镇成果（JSON+HTML+图） | `export/levels/town/` | — | 11 MB |

> 全部文件的逐条清单在 `inventory.csv`；结构校验脚本 `tools/validate_inventory.py`
> （除 `_cache.ych`/`_manifest.ymf` 等索引文件外，**所有资源 RSC8 魔数均正确**）。

### 3.3 动画解码（`.ycd`）—— ✅ 通

详见 `RDR2_ycd动画解码.md`。要点：
- `.ycd` = RSC8 v58 clip dictionary；**通道编解码已全通**（9 类：Static / Quantize /
  IndirectQuantize / Linear / Raw / CachedQuaternion），解出的四元数**模长=1** ✅
- `mech_carry_ped@dead@mount@stow@lt.ycd` 解析出 **10 个 clip + 人/马/道具三套 animation**
- **"把人扛起放到马上"的剪辑**：`mech_carry_ped@dead@mount@stow@lt/rt`（放上马）、
  `@pickup_body`（扛起）、`@carried@mount`（驮着）、`@mount@remove@lt/rt`（取下）
- 工具：`tools/rdr2_ycd.py`（解码器）· `tools/ycd_decode.py`（驱动）· `tools/export_anim_json.py`（导出）
- 预览：`export/rdr2_decode_preview/index.html`（骨骼朝向 gizmo + 时间轴）

### 3.4 骨架（`.yft`）—— ✅ **已通关**（本节保留为"当时怎么啃的"追溯；结论见 §0.2 的 1 / 1b）

> ⚠️ **本节记录的是当时的探索过程，其中"卡点 1/2"后来都已解决**：
> bind 几何 = `inverse(TransformationsInverted)`（§2.9）、索引↔骨名 = `Tag` + 骨名池 `NUL(ptr+0x10)`（§2.10）。

详见 `RDR2骨架_yft格式.md`。已挖到（样例 `meta_base_abe.yft`）：

| 结构 | 偏移 | 结果 |
|---|---|---|
| Skeleton 结构 | `0x024a80` | BonesCount = **335** |
| **父索引数组** | `0x015000` | 335×int16，**校验 0 错误** ✅ 真层级（根=1、最大深度 19）|
| 每骨结构 | `0x00110` 步长 `0x50` | `+0x14`=NextSiblingIndex、`+0x16`=ParentIndex（与父数组逐条一致）、`+0x20`=**单位四元数**、`+0x30`=**绑定位移** |
| 骨骼名池 | `0x026e40+` | 真实 RDR2 骨名（`SKEL_R_UpperArm`/`MH_*`/`PH_*`/`ES_*`…），用"取包含指针的整串"可解出 **309/335** 个名字 |

**卡点 1：FK 约定**。腿链（1.13，向下）与脊椎链（0.47，向上）在**所有 FK 变体下世界空间同向**
（人体上必须相反）⇒ 说明这 80 字节结构**可能不是"骨骼局部变换"**（RAGE bind pose 常是"直骨姿势"，
真正形态靠 inverse bind 矩阵）。试过 `xyzw/wxyz × 共轭 × 父/自身四元数 × 位移取父/自身 × 4 种矩阵约定` 均不通。

**卡点 2：索引↔骨名**。309 个名字解出来了，但用已知 RAGE 父子对校验**只过 1/12**
（如解出的 `SKEL_L_Calf` 父却是 `CH_R_Hand`）⇒ 对齐规则还没找到。
已排除 joaat(name) 方案（骨骼结构 5 个候选字段 0/335 命中）。

**结论：这两点都需要 CodeX 里那份 RDR2 `Skeleton` 精确结构定义**（闭源）。
工具：`tools/rdr2_yft.py`（提取器，注意偏移是**每文件不同**的，已带 `find_skeleton()`）。
预览：`export/rdr2_decode_preview/skel_body.html`（结构骨 FK，已能看出人形轮廓）。

### 3.5 地形 —— ✅ 已用**全区域 LOD 实例**铺满（2026-10-14 二次修复）

> **修复**：`heightmap.dat` 的垂直基准与 `.ymap` 世界坐标差 ~129 m（且局部形状与实体 z 只相关 0.06，
> 见 `RDR2_ydr几何格式.md` §10），常量偏移也救不回来 —— 会出现"小镇半埋在地里 / 地形像天花板压下来"。
> 现改为**使用游戏自带的地形 LOD 网格**：`jklm_07_10_area_slod4_children.ydd` 里的 4 块地形网格，
> 按它们自己的 `area_lod.ymap` 实体摆放（实体 z≈97~146，与小镇实体同基准）。
> 工具 `tools/export_area_terrain.py` → `valentine_terrain_meshes.json`；
> 查看器再加一块**基准地面**补住 LOD 覆盖不到的空洞。
> **二次修复（地面连续）**：真正的地形摆放表在 **`jklm_7_10_lod.ymap`（24 块 512 对齐瓦片）**
> 与 `jklm_7_10_area_lod_combine_metadata` 的 325 个 ymap 里，合计 **12310 个摆放实例 / 6760 种 archetype**。
> 把它们与 `*_slod*_children.ydd` 里的 drawable 对起来（命中 2494 个），
> 按「大瓦片全留 + 小物件 450m 内」裁剪后导出 → **地面连续铺满，蓝色空洞消失**。
> 关键坑：**同一瓦片 archetype 在多个格位复用**，按 hash 去重会丢实例，必须保留 `terrain_instances.json` 全量实例。
> heightmap 地形保留为可切换按钮（`地形(heightmap)`），**默认关闭**（实测与 .ymap 基准差 ~129 m、相关仅 0.54）。

详见 `RDR2地形与城镇.md`。

```
heightmap.dat 格式（直接可读）：
  magic "HMAP" | 1536×1536 | 世界 x[-7680,4608] y[-8192,4096] | 高程 -57~729 m
  数据 = 文件末尾 1536*1536*2 字节 u16，归一化到 [minZ,maxZ]
```
- 已导出 `height_768.bin` + `height_meta.json`，预览 `export/levels/terrain/terrain.html`
- 实测：**能看出 RDR2 地貌**（远处雪线山脉 + 大片平原）
- 🔸 远处山峰有竖向条纹：**已确认不是解包错误**（行/列均值连续、逐格中位差仅 0.4%；
  试过 row-major / col-major / 一维 tile / 二维 block 共 13 种排布，row-major 最平滑）⇒ 属**渲染/法线层面**问题

### 3.6 城镇复原（`.ymap` / `.ytyp`）—— ✅ 可见

**格式突破**：`.ymap`/`.ytyp` = RSC8 + **RAGE `Meta` 格式**（magic `0x50524430`）。
头结构（RDR2 实测偏移，body 内）：
```
+0x10 magic 0x50524430   +0x14 u16 平台(0x79)
+0x28 u64 StructureInfos +0x48 u16 count
+0x30 u64 EnumInfos      +0x4A u16 count
+0x38 u64 DataBlocks     +0x4C u16 count
+0x40 u64 Name
StructureInfo(32B): nameHash key u32 u32 | entriesPtr(8) size(4) u16 entriesCount
StructureEntry(16B): nameHash(4) dataOffset(4) dataType(1) unk(1) refTypeIdx(2) refKey(4)
DataBlock(16B): nameHash(4) dataLength(4) dataPtr(8)
```
**实体结构（144 字节）**：`archetype Hash @+8`、`flags @+12`、`guid @+16`、
**位置 float3 @+32**、**旋转 float4 @+48**、`scaleXY @+64`、`scaleZ @+68`（与 GTA V `CEntityDef` 同构）

**成果**：
- 扫 `val_*.ymap` **43 个** → **2263 个实体**（Valentine）
- 扫全部 1026 个 `.ytyp` → **96,141 个 archetype 的包围盒**（可复用到其他城镇）
- 城镇包围盒 x[-443.9,-158.6] y[586.2,969.1] z[104.7,140.8]
- 427/2263 个实体用了 archetype 真实尺寸渲染 ⇒ 看得出**成排房屋 + 街巷**

**产物**：
| 文件（`export/levels/town/`） | 说明 |
|---|---|
| ⭐ `valentine_real.html`（46.6 MB，含**材质 box map** 切换） | **连续地形 + 1308 个真实模型**（64 高清 `.ydr` + 431 LOD `.ydd` + 478 道具 `.ydr/.yft` + 30 地形瓦片 + 750 近景植被/物件 LOD），双击即可；按钮：`地形(heightmap) / 地形(游戏LOD) / 基准地面 / 真房子 / 灰盒(其余) / 变换调试 / 自动巡航`；`#dist=520&pitch=0.45&yaw=1.0` 全景 |
| ⭐ `valentine_terrain.html`（2.1 MB） | **地形 + 城镇灰盒**，**双击即可**（three.js/数据全内联）|
| `valentine_standalone.html`（1.5 MB） | 只有城镇灰盒，双击即可 |
| `valentine.html` | 需本地 http 服务（用 importmap + fetch）|
| `valentine_top.png` / `valentine_iso.png` / `valentine_terrain.png` | 早期截图 |
| `valentine_real_material.png`（贴木墙材质）/ `valentine_real_default.png` / `valentine_real_nobox.png` / `valentine_real_close.png` / `valentine_real_debug.png` | 真房子查看器截图（默认视角 / 关灰盒 / 变换调试）|
| `valentine.json` / `archetypes.json` / `valentine_meshes.json` | 原始数据（实体 / 包围盒 / 真实网格）|

> ⚠️ **重要坑**：浏览器在 `file://` 下**禁止** ES module import 和 `fetch()`。
> 早期用 `importmap + fetch(json)` 的页面**双击打开必然黑屏**（必须走 http 服务）。
> 现已改为**自包含单文件**（three.js 源码 + 数据全内联，Blob URL 动态 import）。
> 生成器：`tools/build_town_standalone.py`、`tools/build_town_terrain_viewer.py`。

### 3.7 建筑真模型（`.ydr`）—— ✅ 完成

详见 `RDR2_ydr几何格式.md`。**上一轮的卡点（DrawableModel → Geometry → VertexBuffer）已攻克。**

- **已提取**：`levels/rdr3/area/jklm_07_10/val_01_.rpf` … `val_07_.rpf` → **210 个 `.ydr`**
  （火车站 `val_01_trainstn_ext`、马厩 `val_01_aucyard_stables`、谷仓 `..._barn2/barn3`、
  银行/旅馆/枪店 `val_02_lockdown_*`、监狱 `val_03_jail_ext`、诊所 `val_03_doctor_ext`、
  酒馆 `val_03_saloon_ext`、杂货店 `val_03_genstore_ext_em_hd`、民宅 `val_05_res_*`、农场 `val_06_*`…）
- **格式突破（核心）**：
  `DrawableModel(+0x08/0x10) → Geometries[] → {VB@+0x08, IB@+0x10}`
  `VB: +0x08 VertexCount · +0x0c TotalStride · +0x18 Data*`
  ★ **顶点是「平面分属性数组」**：`Data[0 .. 12*count)` 就是 `f32×3` 位置数组，
    另两段（`16*count`、`12*count`）跟在后面，合计 `count × 40`。
    **不是 GTA V 的交织布局** ⇒ 这是上一轮移植 CodeWalker 读出 0 顶点/几何错位的根因。
- **自检**：用 IndexBuffer 还原三角形，中位边长 0.29 m（bbox 对角 54.5 m）；
  顶点数 = 索引唯一数；缓冲区在文件里连续平铺（`0xd0 + 104×40 = 0x1110`）。
- **archetype ↔ 模型名（精确映射）**：`.ymap` 实体的 archetype 哈希 == **`joaat(<ydr 文件名>)`**
  （32 个 `val_01_*` 全部命中 `.ytyp` archetype 结构的 `+88`/`+112`）。
- **覆盖（42 → 473 个实体）**：
  * `.ydr` 高清模型：把 `jklm_07_10` 整网格 31 个 area rpf 全过一遍 → **1286 个 `.ydr` + 461 个 `.ytd`**；
    匹配出 **42 栋 Valentine 高清建筑**（78.4 万顶点 / 59.8 万三角面）。
  * **`.ydd` LOD 字典（本轮新增）**：926 个未覆盖 archetype 里有 **431 个**存在于 `*_slod_children.ydd`。
    `.ydd` = DrawableDictionary：`{哈希数组(升序 u32)@+0x20/count@+0x2A, drawable指针数组 @+0x30/…}`，
    两个并行数组即 hash→drawable 映射；用 `rdr2_ydr.extract_ydd()` 抽出 **431 个 LOD 网格**（29.4 万顶点 / 19.2 万三角面）。
  * **植被实例（本轮突破）**：树**不走 ymap 实体**，而在 `levels/rdr3/terrain/instance_placement/<grid>_instance_placement.rpf`
    的 **`*_trees_*.ymap` / `*_grass_*.ymap`**；这些 ymap 用 **368 字节**/条的记录（普通实体是 144 B），
    世界坐标在记录内 **`+0x90`**（哈希仍在 `+0x08`）。解出 **3402 个植被实例**，
    模型本体在 `hd/levels/rdr3/props/vegetation/*.rpf` + `levels/rdr3/props/vegetation/*.rpf`，**270/270 全部匹配**。
    工具 `tools/parse_veg_instances.py` + `tools/export_veg_meshes.py`。
  * **`.yft` 道具（上一轮突破）**：剩下的大头**不是建筑而是道具**，且**不在 town 自己的 area rpf 里** ——
    它们在 `levels_3.rpf` 下的 **149 个 props 包**（`levels/rdr3/props/{generic,vegetation,structure,areas,lev_des}/*.rpf`），
    且多为 **`.yft`（fragment）**。`.yft` 的 drawable 挂在 fragment 头的指针上（`+0x20` 通常为主 drawable），
    用 `rdr2_ydr.extract_frag()` 解析 ⇒ 抽出 **478 个道具**（栅栏/水塔/桁架桥/长椅/木箱/马车/路灯/墓碑/水槽…，82.8 万顶点）。
  * 合计 **覆盖 2106 / 2263 实体（93%）**，**260 万三角面**，从小镇轮廓变成完整西部小镇。
  * 剩余 157 个经 `names.txt` 反查全部是 **vfx 粒子辅助体 / 贴花 / 室内件 / 阴影代理**（非可见几何）。
  * ⚠️ **重要观感修正**：这些"没模型的实体"里很多是 **`*_int_*`（室内 / 门厅 milo 体积）、`*_dcl`（贴花）、
    `val_audioemitter*`（音频发射器）、`*_em*`、`*_slod`、`lights_holder`** —— **游戏里本来就不渲染**。
    早期把它们一律画成灰盒，视觉上表现为"**每栋房子外面套一个方块**"。现已加**逻辑体过滤**
    （`build_valentine_real.py` 的 `_LOGIC_PAT`），不再为它们画盒子，画面立刻干净。
  * 高清建筑清单：
  酒馆 `val_03_saloon_ext`、银行 `val_bank`、旅馆 `val_hotel_ext`、杂货店 `val_genstore_ext`、
  枪店 `val_gunsmith_ext`、监狱 `val_03_jail_ext`、诊所 `val_03_doctor_ext`、警长宅 `val_shrffhs`、
  律师事务所 `val_lawoffice_ext`、拍卖行 `val_auchouse_ext`、魔术灯剧场 `val_07_magiclantern_ext`、
  货运站 `val_freightstn`、马厩 `val_03_stable_ext`、屠宰店、猪圈、绞刑架、民宅 `val_05_res_*`…
- **变换校验（数值通过）**：网格局部包围盒 vs archetype 包围盒 **ratio = 1.000**，**38/38 全部吻合**；
  实体四元数模长/缩放 **0/2263 异常** ⇒ `world = T·R·S·localMesh` 可直接用。
  查看器里有「变换调试」按钮，显示世界坐标轴 + 每栋建筑的世界包围盒线框（截图 `valentine_real_debug.png`）。
- **地形基准（⚠️ 待解）**：`heightmap.dat` 的 z 基准与 .ymap 世界 z **差 ~129 m**（实测地形在 Valentine 只有 -10 m，
  而城镇实体 z 是 104~141 m，后者被 area-LOD 实体 z 交叉验证）。查看器暂用**常量偏移 +129.47 m 做局部校准**。
- **贴图（P1）**：`.ytd` 的 sys 段已摸到「纹理表」（条目步长 `0xb0`，W/H 在 `+0x18`），但 **format 枚举未定、UV 未定位**，本轮未解码。
- **未做**：`attribute1/attribute2`（法线/UV/切线）语义未定；**贴图 `.ytd` 未解码**（P1）。

---

## 4. TODO · 交接任务清单（按优先级）

> ⚠️ **本表是早期版本**；当前结论与入口见 **§0.2 / §0.3**，历史见 `交接历史.md`。下面保留供追溯。

| # | 任务 | 依赖 | 预判工作量 | 备注 |
|---|---|---|---|---|
| ~~**P0**~~ | ~~解 `.ydr` 几何/顶点格式~~ | — | — | ✅ **已完成**（见 §3.7 + `RDR2_ydr几何格式.md`）|
| ~~**P1a**~~ | ~~`.ytd` 纹理解码~~ | — | — | ✅ **已完成**：根因是 **DDS 头多写 4 字节**（非 tile/swizzle）⇒ 27/27 完美；后续又关掉 T2（表基址自动定位）。见 §3.7 / `RDR2_ydr几何格式.md` §18 |
| ~~**P1b**~~ | 建筑材质（UV） | P1a | 中 | ✅ **已完成（box mapping 路径）**；⚠️ 但 note：**"顶点无 UV"的判据是错的**，见 §0.2 第 4 条 —— 顶点有 `TEXCOORD0/1`，真正该做的是**用原生 UV + 分层材质**（见 §0.3 A0）。**遗留**：纹理解码只可靠 2/7（BC1/部分 BC3 仍噪声）→ 见 P1a |
| ~~**P6**~~ | ~~地形基准~~ | — | — | ✅ **已绕过**：改用游戏地块 LOD 当地面（heightmap 基准仍差 ~129 m，保留为可选层）|
| **P6b** | 地形条纹（渲染层）| 无 | 低 | 数据没问题，属法线/着色；可选 |
| **P2** | **骨架 FK 约定 + 索引↔骨名** | 需 CodeX 规格 / 更多样本 | 高（不确定）| 见 §3.4；**候选方案：进游戏读运行期骨架（骨名↔索引、bind pose）** 或 REA+Ghidra 反编译（见 §1）|
| **P3** | 动画 ↔ 骨架对齐 → **骑砍2 28 骨重定向** | P2 | 高 | 参考仓 `D:\BrainMaker\骑砍2动画重定向` 的 `pipeline/rigs/*` |
| **P4** | archetype/模型名哈希 → 真名 | ✅ 已解 | — | archetype hash == `joaat(ydr 名)`，见 §3.7 |
| **P5** | 复用到其他城镇（Blackwater/Annesburg/Armadillo）| 无 | 低 | 换文件名重跑 `tools/ymap_entities.py` + 抽对应 area rpf |
| ~~**P7**~~ | ~~清理 work/ 中间产物~~ | — | — | ✅ **已完成**（2026-10-14，释放 14 GB，见 §0.7 / §6.1）|
| ~~**P8**~~ | ~~Valentine 覆盖补全~~ | — | — | ✅ **已完成**：**2106/2263（93%）**；剩余 157 全是 vfx/贴花/室内/阴影代理（非几何） |
| ~~**P8b**~~ | ~~树木/植被~~ | — | — | ✅ **已攻克**：`instance_placement/*_trees_*.ymap`（368B 记录、位置 @+0x90），270/270 模型匹配，728 棵树进场景 |
| **P9** | 路面材质 | P1b | 中 | **道路网格已解析出来**（`val_03_road_d_*`，无贴图所以只见轮廓线），等 UV/贴图打通后即可 |

**建议接手顺序**：P1b（先把 UV 找出来，贴图才上得去）→ P1a 的 BC1 收尾 → P2（骨架，可借 REA+Ghidra）。

---

## 5. 工具清单（`tools/`）

| 工具 | 语言 | 作用 |
|---|---|---|
| `rdr2rpf/`（含 `bin/.../rdr2rpf.exe`） | C# / dotnet9 | **RPF8 提取器**（核心工具）|
| `rage_meta.py` | Python | RAGE **Meta** 解析（`.ymap`/`.ytyp`/`.ymt` 通用）|
| `ymap_entities.py` | Python | 从 `.ymap` 抽实体（自动识别实体表）|
| `ytyp_archetypes.py` | Python | 扫全部 `.ytyp` → archetype 包围盒表 |
| `rdr2_ycd.py` | Python | **`.ycd` 动画通道编解码器**（核心）|
| `ycd_decode.py` | Python | `.ycd` 驱动（扫 Animation 块、读 Sequence/BoneIds）|
| `export_anim_json.py` | Python | 导出每骨四元数关键帧 → JSON |
| `rdr2_yft.py` | Python | **`.yft` 骨架提取**（父索引/每骨 quat+pos/名字池）|
| `rdr2_ydr.py` | Python | **`.ydr` 网格提取**（Drawable→Geometry→VB/IB→位置/索引，v2 已通）|
| `export_building_meshes.py` | Python | 批量导出 Valentine 引用的建筑网格 → `valentine_meshes.json` |
| `build_town_standalone.py` | Python | 生成**单文件**城镇查看器（file:// 可用）|
| `build_town_terrain_viewer.py` | Python | 生成**单文件**地形+城镇查看器 |
| `build_valentine_real.py` | Python | 生成**单文件**地形+**真实建筑网格**查看器（`valentine_real.html`）|
| `export_area_terrain.py` | Python | 从 `.ydd` 抽**游戏地形 LOD 网格**并按 `area_lod.ymap` 实体摆放 → `valentine_terrain_meshes.json` |
| `export_prop_meshes.py` | Python | 从 **props 包**抽 Valentine 的 **`.ydr`/`.yft` 道具** → `valentine_prop_meshes.json` |
| `parse_veg_instances.py` | Python | 解析**植被实例摆放**（`*_trees_*.ymap` 的 368B 记录，位置 @+0x90）|
| `export_veg_meshes.py` | Python | 导出植被模型 + 实例 → `valentine_veg_meshes.json` / `valentine_veg_instances.json` |
| `export_lod_meshes.py` | Python | 从 `.ydd`(LOD 字典) 抽 Valentine 的 LOD 网格 → `valentine_lod_meshes.json` |
| `rdr2_ytd.py` | Python | **`.ytd` 纹理表解析**（步长 0xB0，名称/W/H/格式字节/数据指针）|
| `ytd_to_png.py` | Python | 按真实 BC 格式解码 `.ytd` → PNG（`--sheet` 出拼图）|
| `build_ytd_preview.py` | Python | WebGL2 预览页（PIL 不支持 BC7 时的备用路径）|
| `dump_rpf8_header.py` / `validate_inventory.py` / `make_inventory.py` | Python | 诊断/校验/清单 |
| ⭐ `yft_bind.py` | Python | **抽 `.yft` bind + 骨名池** → `yft_bind.json`(1050 tag) / `yft_skel.json`(756 骨含 name) |
| ⭐ `export_gltf_source.py` | Python | **RDR2 骨架+`.ycd` → GLTF 源资产**（`--skel yft`：.yft 骨架 + 接回 6 骨 + 重挂父 + 臂链串线）|
| ⭐ `rsc8_standalone.py` | Python | **解磁盘上的单文件游戏格式 RSC8**（val1 压缩位 +1 规则 + `val2` 低32=size+11 + raw deflate）|
| `memscan.py` | Python | 运行期**只读内存取证**（骨名/索引/父子表）|
| `build_anim_case.py` | Python | 生成"成对/单条动画"的 HTML 案例页 |
| `uv_probe.py` / `triplanar_probe.py` / `uv_probe_page_gen.py` | Python | UV/材质诊断页 |
| ⭐ `rdr2_vdecl.py` | Python | **顶点声明 `VertexDeclarationG9` 解析**（语义布局 / UV / 颜色权重；`--check` UV 自检）——见 `RDR2_ydr几何格式.md` §20 |
| ⭐ `rdr2_shader_params.py` | Python | **shader → 纹理 slot → 参数名**（来源：Sollumz `ModRDRShaders.xml` + RedDead2Blend JSON，共 195 个 shader）|
| ⭐ `export_building_materials.py` / `build_material_viewer.py` | Python | 4 栋建筑**真 UV + slot 语义材质**导出 / 单文件查看器 |
| ⭐ `export_town_textured.py` / `build_town_textured_viewer.py` | Python | **整镇**（69 建筑 + 高度场地形 + 树 + 道路）导出 / 单文件查看器 |
| ⭐ `build_skel_viewer.py` / `build_walk_viewer.py` | Python | 静态骨架 / `walk` 动画 单文件查看器 |
| ⭐ `rdr2_cwxml.py` | Python | **自建 CodeWalker XML 读写**（`.ydr/.ydd/.yft → .xml` 给 Blender 用；`--read` 反向解读），不依赖 CodeX |
| `tools/ref/CWProbe/` | C# / net9 | **权威交叉验证探针**（引用 `CodeWalker.Core.dll` 解我们的 `.ycd`）|
| `tools/ref/{CodeWalker-master, AnimKit-master}` | C# | 社区权威源码（`Clip.cs` 等）|
| `tools/ref/{Sollumz-RDR-main, RedDead2Blend-main, fivefury-main, rdr2-unpack-main, RAGE-RDR2-Binary-Packer-main, AizenX-RDR2-XML-Forge-main}` | 多语言 | 社区 RDR2 工具/规格（CW XML schema、shader 参数表、RAGE 读取库）|
| `tools/ref/fivem-rdr3-formats/` | C++ 头文件 | **RDR3 权威结构体**（`rmcDrawable.h`/`grcTexture.h`/`ShaderInfo.h`）+ `ConvertFormats.RDR3.cpp` |
| ⭐ `export_building_materials.py` | Python | **按修正后材质管线导出建筑**（真 UV + shader slot 语义 albedo/albedo2/mask/palette）→ `materials_demo.json` |
| ⭐ `build_material_viewer.py` | Python | 生成**单文件场景材质查看器** `export/levels/town/materials_demo.html`（真实 UV + 原生贴图，带逐几何体材质清单） |
| ⭐ `build_skel_viewer.py` | Python | 生成**人类骨架查看器** `export/skeleton_runtime/rdr2_skeleton.html`（`.yft` 权威 bind，72 根 `SKEL_*`） |
| `tools/re/work/scripts/*.java` | Ghidra 脚本 | `FindStr*` / `DumpStrings` / `DumpAt` / `FindMagic2`（见 `RDR2_REA反编译笔记.md`）|

---

## 6. 复现命令速查

```bash
# Python 一律走 uv（本机无系统 python 依赖）
UVPY="C:/Users/yaodongcheng/AppData/Roaming/com.brainmaker.client/cowork-updates/uv-binary/uv.exe"

# 0) 编译提取器
cd tools/rdr2rpf && "C:/Program Files/dotnet/dotnet" build -c Release

# 1) 看封包内容 / 提取
RP=tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe
$RP tree  "H:/EPICGAMES/RedDeadRedemption2/anim_0.rpf"
$RP extract "H:/EPICGAMES/RedDeadRedemption2/common_0.rpf" export/levels/terrain "heightmap"

# 2) 城镇实体 + archetype
"$UVPY" run python tools/ymap_entities.py  export/levels/map_metadata "val_*.ymap" export/levels/town/valentine.json
"$UVPY" run python tools/ytyp_archetypes.py export/levels/map_metadata export/levels/town/archetypes.json
"$UVPY" run python tools/build_town_terrain_viewer.py     # → 单文件查看器

# 3) 动画解码
"$UVPY" run python tools/export_anim_json.py \
  "export/animations/mech_carry_ped/mech_carry_ped@dead@mount@stow@lt.ycd" \
  "export/rdr2_decode_preview/stow_lt.json"

# 4) 骨架
"$UVPY" run python tools/rdr2_yft.py "export/models/fragments/meta_base_abe.yft"

# 4.5) 纹理（.ytd）
"$UVPY" run python tools/rdr2_ytd.py export/models/buildings/val_01_/val_01_trainstn_ext+hidr.ytd
"$UVPY" run python tools/ytd_to_png.py export/models/buildings/val_01_/val_01_trainstn_ext+hidr.ytd     export/models/textures/val_01_trainstn --sheet export/models/textures/sheet_trainstn.png

# 5) 建筑真模型（.ydr 几何）
RP=tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe
"$RP" extract "H:/EPICGAMES/RedDeadRedemption2/levels_1.rpf" export/models/buildings "val_0" --recurse
"$UVPY" run python tools/rdr2_ydr.py export/models/buildings/val_01_/val_01_trainstn_ext.ydr
"$UVPY" run python tools/export_building_meshes.py      # → valentine_meshes.json
"$UVPY" run python tools/build_valentine_real.py        # → valentine_real.html（双击）
# 截图核验（headless Chrome + SwiftShader）
"/c/Program Files/Google/Chrome/Application/chrome.exe" --headless=new --no-sandbox \
  --enable-unsafe-swiftshader --use-angle=swiftshader --window-size=1600,900 \
  --virtual-time-budget=35000 --screenshot=val.png \
  "file:///D:/BrainMaker/大镖客2解包分析/export/levels/town/valentine_real.html#dist=200&pitch=0.25&yaw=1.02"
```

---

### 6.1 重跑管线的「输入准备」对照表（work/ 删了照这个重建）

> `work/` 只是**中间输入暂存**，删掉不影响 `export/` 里任何产物。
> 需要重跑某一步时，按下面把输入重新抽出来即可。

| 要重跑什么 | 输入从哪来 | 命令 | 输出到 |
|---|---|---|---|
| **Valentine 建筑网格** | `levels_1.rpf` → `jklm_07_10` 下 31 个 area rpf | `"$RP" extract "H:/EPICGAMES/RedDeadRedemption2/levels_1.rpf" work/valarea "jklm_07_10"` | `work/valarea/` |
| ↳ 再抽模型 | 上一步的 area rpf | 对每个 `.rpf`：`"$RP" extract <rpf> export/models/buildings_jklm/<name> ".ydr"` + `".ytd"` | `export/models/buildings_jklm/` |
| ↳ 生成网格 | 上一步 | `"$UVPY" run python tools/export_building_meshes.py` | `valentine_meshes.json` |
| **道具（.ydr/.yft）** | `levels_3.rpf` → `levels/rdr3/props/**` | `"$RP" extract "H:/EPICGAMES/RedDeadRedemption2/levels_3.rpf" work/props "props/"` | `work/props/`（149 个包）|
| ↳ 再抽模型 | 上一步 | 按需要名从各包抽 `.ydr`/`.yft` → `export/models/props/<pack>/` | `export/models/props/` |
| ↳ 生成网格 | 上一步 | `"$UVPY" run python tools/export_prop_meshes.py` | `valentine_prop_meshes.json` |
| **LOD 建筑（.ydd）** | `levels_1.rpf` → `area/lod/jklm_7_10_area_lod_combine.rpf` | `"$RP" extract <该rpf> export/models/area_lod_ydd ".ydd"` | `export/models/area_lod_ydd/` |
| ↳ 生成网格 | 上一步 | `"$UVPY" run python tools/export_lod_meshes.py` | `valentine_lod_meshes.json` |
| **地形 LOD** | `levels_1.rpf` 的 `area/lod/jklm_7_10_area_lod*.rpf` + `levels_5.rpf` 的 `terrain/jklm_07_10/jklm_7_10_lod_combine.rpf` | 抽 `.ydd` → `export/models/area_lod_ydd{,2}/` | 同上 |
| ↳ 摆放表 | `export/levels/map_metadata/jklm_7_10_{lod,area_lod}_combine_metadata/*.ymap` | `"$UVPY" run python tools/ymap_entities.py <dir> "*.ymap" <out>` | `town/{lod,arealod}_all_entities.json` |
| ↳ 生成网格 | 上两步 | `TERRAIN_RADIUS=1600 "$UVPY" run python tools/export_area_terrain.py` | `valentine_terrain_meshes.json` + `terrain_instances.json` |
| **植被实例** | `levels_4.rpf` → `terrain/instance_placement/jklm_7_10_instance_placement.rpf` | `"$RP" extract <该rpf> work/inst_veg "trees"` + `"grass"` | `work/inst_veg/`（123 个 ymap）|
| ↳ 解析实例 | 上一步 | `"$UVPY" run python tools/parse_veg_instances.py work/inst_veg export/levels/town/veg_instances.json` | `veg_instances.json` |
| ↳ 植被模型 | `levels_3.rpf` 的 `props/vegetation/*.rpf` + `hd_0.rpf` 的 `hd/levels/rdr3/props/vegetation/*.rpf` | 各抽 `.ydr`/`.yft` → `export/models/veg/` | `export/models/veg/` |
| ↳ 生成网格 | 上两步 | `VEG_RADIUS=420 "$UVPY" run python tools/export_veg_meshes.py` | `valentine_veg_meshes.json` |
| **查看器** | 以上全部 | `BM_TEX=<木纹png> "$UVPY" run python tools/build_valentine_real.py` | `valentine_real.html` |

（`$RP` = `tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe`；`$UVPY` 见本节开头）

## 7. 已知坑 / 注意事项

1. **偏移是每文件不同的**：`.yft` 的 `0x24a80/0x110/0x15000` 只对 `meta_base_abe.yft` 成立。
   各解析器里凡是硬编码偏移都要先跑 `find_*()` 定位。
2. **`file://` 黑屏**：见 §3.6 的警告。要么走 http 服务，要么生成"单文件版"。
3. **`.yft` 骨架里有大量重叠/重复骨 + 挂点/服装骨**（335 根里多数是 `MH_/PH_/ES_`），
   直接 FK 渲染会糊成一团；**只取"局部骨长 > 0.15"的 101 根结构骨**才看得清人形。
4. **`.ycd` 的 `BoneId(u16)` 不是名字哈希低 16 位**（实测 2/265），也不是小索引 —— 语义未定。
5. **RPF8 的段大小**：RSC8 头 `+0x08`(u32)=system 字节数、`+0x0C`(u32)=graphics 字节数
   （GTA V 那套页标志公式在 RDR2 上**不适用**）。
6. **RAGE 指针**：`0x50000000|off` → 资源体 system 段；`0x60000000|off` → graphics 段。
7. **不要 kill WPS/Office**；文件被锁时用 `safe_save`。

---

## 8. 外部参考（本机可复现获取）

| 资源 | 用途 |
|---|---|
| `dexyfex/CodeWalker`（codeload 可下） | GTA V 的 RAGE 结构**权威参考**（Meta/Drawable/Clip/Texture/VertexType 全有） |
| `lazenes/RPF8_TOOL` · `amrshaheen61/RDR2-RPF-Tool` | RDR2 RPF8 + TFIT2 密码 + 密钥表 + names 表 |
| `Sollumz/Sollumz_RDR` | Blender 插件（**只吃 CodeWalker XML**），`cwxml/drawable.py` 里有 RDR2 `Bone` 字段定义 |
| `Ilyxrl/Ilyxrls-RDR2-Ped-Tool` | 开源 Ped 工具，暴露 CodeX 的骨架 XML 结构（`Name/Index/ParentIndex`） |
| 社区结论 | **R\* 没有给 RDR2 官方资产编辑器**；资产编辑 = CodeX（闭源）↔ XML ↔ Blender(Sollumz+骨架修复插件) |
| `morluto/rea`（本机内置 `rea` CLI） | 逆向 agent；**本机已配好 Ghidra 12.1.4 + JDK21 可反编译 native**（见 §1）。`rea search/function/decompile <bin>` |
| `spicybung/BlenDR` | Blender GTA IV 导入器（RAGE IV 解析参考） |

### 8.1 ★ 社区 RDR2 mod 管线调研（2026-10-16，已落地到 `tools/ref/`）

**问题**：既然社区能做 mod / 资源替换，那**必然能提取**原资源 —— 他们是怎么做的？

```
① RPF8 解包            ← 需要 TFIT2 密钥（secrets.bin，不在游戏里！）
② RSC8 → RSC7 转换     ← ★ 社区的关键一步：CodeWalker/OpenIV **只吃 RSC7**
③ 二进制 ↔ CodeWalker XML（.ydr.xml / .ydd.xml …）   ← CodeX（闭源 dexyfex）
④ Blender 里编辑        ← Sollumz / Sollumz-RDR（XML 导入导出）
⑤ 按**原路径**替换        ← Lenny's Mod Loader（lml/ + install.xml）或打进 rpf
贴图单独一条线：RDR2 Texture Toolkit（GTA5 ytd → RedM ytd 转换器）；
地形大包（Terrain Textures Overhaul / nigeez 8K）就是**成批替换地形 .ytd**。
```

⇒ **结论：资源提取/替换是成熟且文档化的**；而且社区把**格式定义本身**开源了。
**本项目比社区更短一环**：②我们**不需要**（直接解析 RSC8），自己的 RPF8 提取器 + 密钥表也已具备。

**本轮已下载（`tools/ref/`）—— 权威规格来源：**

| 来源 | 价值 |
|---|---|
| ⭐ `citizenfx/fivem` → `code/components/rage-formats-x/include/rmcDrawable.h` | **RDR3 权威结构体**（带 `RAGE_FORMATS_GAME_RDR3` 分支）：`grcTexture`/`grcTexturePC`/`grcTextureRef`/`grmShader`/`grmShaderFx`/`grmShaderGroup`/`sgaShaderParamData`/`sgaInputLayout`/`grcVertexBuffer`/`grcVertexFormat` |
| ⭐ `…/rage-graphics-rdr3/include/grcTexture.h` · `ShaderInfo.h` | RDR3 运行时纹理 / shader 信息 |
| ⭐ `citizenfx/fivem` → `…/tool-formats/src/ConvertFormats.RDR3.cpp`（95 KB） | **RSC7 ↔ RSC8 的 RDR3 转换器**（社区就是靠它让 CodeWalker 能读 RDR2 资源） |
| ⭐ `ultrahacx/Sollumz-RDR` → `cwxml/ModRDRShaders.xml` | **197 个 RDR2 shader 的纹理参数表**（`slot → 参数名`）；已固化为 `tools/rdr2_shader_params.py` |
| `Hancapo/fivefury` | Python 版 RAGE 资源库（`read_ytd` / `read_ydr`），可交叉验证 |
| `QUITFIL3/rdr2-unpack` | 独立解包器（world index + GLB + PNG）；其 `ytd_to_png.py` 也**只按名字挑 `_ab/_al` 单张 albedo**（说明社区多数工具也只做单层） |
| `zlinz1995/RAGE-RDR2-Binary-Packer` | RSC8 检查/打包 + 附带样例 `.ydr` |
| `4izenX/AizenX-RDR2-XML-Forge` | 资产 → XML（YFT/YDD/YTD/YMT） |

**用权威规格校正了我们自己的实现（本轮实际修复，见 `RDR2_ydr几何格式.md` §21）：**

| # | 项 | 结果 |
|---|---|---|
| 1 | `.ytd` 条目 = RDR3 `grcTexture` | 我们的字段（W@+0x18 / H@+0x1A / fmt>>24 / name@+0x28 / data@+0x38）**逐字段对上**（我们是从结构体 `-8` 起读，RDR3 有 8B datBase 前缀）；并多认出语义：`m_blockSize / m_blockCount / m_flags(0x18008002) / m_dimension / m_levels(mip 数) / m_tileMode(0x0D) / m_srv` |
| 2 | ⚠️ **shader 纹理数组步长 bug** | `grmShader.m_textureRefs` = `pgPtr<grcTextureRef>` 数组，长度 = `m_parameterData->numTextures`，**元素 8 字节**；旧实现按 **16 字节**读 ⇒ **只读到偶数 slot，材质全错位**（"建筑贴图不对 / 地形把 `_nm` 当 albedo"的直接原因）。已修；实测 terrain=16 / standard=7 / standard_dirt=9，与 Sollumz 表**完全一致** |
| 3 | 顶点 SOA | `sgaInputLayout{ offsets[52]; sizes[52]; types[52]; hasSOA:1; … }` —— 与我们的 `VertexDeclarationG9` 一致，确认 RDR2 顶点是 SOA |
| 4 | 材质语义 | 修完后建筑能正确取 `diffusetex`/`diffusetex2`/`bumptex`/`tintpalettetex`；地形取到 **4 层 × (diffuse/bump/material)** + `lookuptexture` + `tinttexture`(=`l_09_t`) |

### 8.2 ★ 社区教程里的"XML"是什么？能不能解读？要不要 Blender 插件？

**结论：XML = CodeWalker XML（CW XML），纯文本、可完全解读；Blender 插件不是解读的必要条件。**

| 问题 | 答案 |
|---|---|
| **是什么** | **CodeWalker XML**（`.ydr.xml` / `.ydd.xml` / `.ymap.xml` …）。CodeWalker（GTA V）/ **CodeX**（RDR2，dexyfex，**闭源**）把二进制资产"反编译"成的**纯文本中间格式**：普通 XML 标签 + **空格/TAB 分隔的十进制数**（顶点一行一个、索引 24 个一行）。**无加密、无二进制负载。** |
| **能不能解读** | ✅ 能，纯文本级。权威 schema 就在 `tools/ref/Sollumz-RDR-main/cwxml/*.py`（RDR2 分支）：`Drawable` / `LodHigh|Med|Low|VeryLow` / `Item`(模型) / `Geometries` / `Item`(几何体) / `VertexLayout{Formats,NonInterleaved,Semantics}` / `Vertices` / `Indices` / `ShaderGroup{TextureDictionary,Shaders,Parameters}` / `RDR2DrawableDictionary` |
| **要不要 Blender 插件** | ❌ **不需要**。① **RedDeadBlend2**（`Sage-of-Mirrors/RedDead2Blend`）**根本不走 XML**——它用 **LibDrawable + PyLibDrawable** 直接读 `.ydr`；② **Sollumz_RDR** 走 XML，但 **RDR2 导入是 WIP**（`ydr/ydrimport.py` 里没有顶点解析，只有 `ydrexport.py` 导出）；③ 插件只是**可视化编辑器**，解析 XML 用 Python `ElementTree` 即可 |
| **CodeX 必需吗** | 对社区是（闭源工具只能靠它产 XML）。**对我们不是** —— 我们已能原生解析 RSC8，可自己产出同一套 XML（本轮已实现） |

**本轮落地：`tools/rdr2_cwxml.py`（自建 CW XML 读写，不依赖 CodeX）**

```bash
python tools/rdr2_cwxml.py <file.ydr|ydd|yft> <out.xml> [--max-verts N]   # 导出给 Blender 用
python tools/rdr2_cwxml.py --read <file.xml>                             # 反向解读
```

**实测校验（`val_03_saloon_ext.ydr`，导出 12.5 MB XML → 读回）**：

| 校验项 | 二进制 | XML 读回 |
|---|---|---|
| 首顶点位置 | `-1.50830078125, -12.5732421875, -5.74951171875` | `-1.5083008, -12.5732422, -5.7495117` ✅ |
| 首顶点 UV0 | `1.170654296875, 0.6468048095703125` | `1.1706543, 0.6468048` ✅ |
| 顶点/索引数 | 2150 / 4053 | 2150 / 4053 ✅ |
| 语义串 | 元素序 P N X C T T | `PNXCTT`（地形那块 `PNXXCCTTT`）✅ |
| 材质语义 | shader slot → 参数名 | 逐条还原（`diffusetex/lyr0diffusetex/tintpalettetex…`）✅ |

**Bonus：`RedDead2Blend` 自带 146 个每-shader JSON 参数表**（`data/shaders/*.json`，`{hash,name,uniforms:[{hash,name,size}]}`）——
与 Sollumz 的 `ModRDRShaders.xml` **uniform 顺序逐条一致**（互相校验通过），且额外给出**参数名 hash**；
已并入 `tools/rdr2_shader_params.py`（两来源合计 **195** 个 shader 定义：XML 给槽位名、JSON 给 hash→名）。

---


### 8.3 ★★ 本轮交付：**能看到的东西**（2026-10-16）

前面几轮全是"规格/格式"，这轮把**可见产物**做出来了。

| 产物（双击即开） | 内容 | 截图 |
|---|---|---|
| ⭐ **`export/levels/town/materials_demo.html`**（31 MB 单文件） | Valentine 4 栋建筑（酒店/银行/火车站/监狱）**用游戏原生 UV + 按 shader slot 语义的原生贴图**渲染；右侧实时列出每个几何体的 `shader / 语义串 / albedo / albedo2 / mask / normal / palette`；可切 `第二层`、调 UV 缩放、旋转平移 | `materials_demo_1.png`（酒馆近景）、`materials_demo_all.png`（4 栋一排） |
| ⭐ **`export/skeleton_runtime/rdr2_skeleton.html`**（1.3 MB 单文件） | **RDR2 人类骨架**：`.yft` 权威 bind 摆位，756 骨里筛出 **72 根 `SKEL_*`** 解剖骨（71 段），带骨名标签 + 世界坐标轴；Z-up / Y-up 视图切换 | `rdr2_skeleton.png` |
| ⭐ **`export/skeleton_runtime/rdr2_walk.html`**（1.6 MB 单文件） | **RDR2 `walk` 动画骨架演示**：`.ycd` → glTF → 本查看器；80 节点 / 22 条旋转轨 / **404 帧 @30fps（13.4 s）**；播放·暂停·0.25~1× 变速·帧拖动 | `walk_f0/100/200/300.png` |

**这一版"对"在哪**（相比之前的 Valentine 查看器）：

| 项 | 之前 | 现在 |
|---|---|---|
| UV | box mapping 现算（顶点"没 UV"的误判） | **游戏原生 `TEXCOORD0/1`**（`VertexDeclarationG9` 读出，实测随位置线性） |
| 材质 | 按文件名后缀猜一张，且 shader 纹理数组**步长写错**（只读到偶数 slot） | 按 **shader slot 语义**取 `diffusetex / lyr0diffusetex / tintpalettetex …`（步长 bug 已修） |
| 贴图来源 | 只索引 `buildings_jklm/**/*.ytd` | 全量 `.ytd` + **`gtxd_valentine`（Valentine 共享纹理字典，本轮新抽）**；**大小写不敏感**匹配（RDR2 名字是哈希） |
| 覆盖率 | — | 需要的贴图 **146 张，缺 3、回退 8**（缺的标 `（缺）`，回退标 `≈原图`；酒馆 4 块墙板属 3 个尚未定位的字典） |
| 骨骼 | 756 骨一把梭（糊成一团） | 72 根 `SKEL_*`，A-pose、1.635 m、骨名可读 |

**仍然没有的**：① 地形没有用真素材渲染（`l_09_t` 宏观色图已抽到，但还没接进查看器）；
② 建筑缺的 3 个贴图族（`val_be_wood01b_*`、`val_ew_woodplank55/56_*`）所在字典尚未定位；
③ 2 层混合的**遮罩通道**是经验取值（`materialA.r`），未从 `.sps` 反编译确认。

---


### 8.4 马赛克问题的根因与修复（2026-10-16 续）

用户反馈"局部有马赛克"。定位过程与结论：

| # | 现象 | 根因 | 修复 |
|---|---|---|---|
| 1 | 部分墙面呈**彩虹噪声** | 贴图解析顺序错：先走 `.ydr` **内嵌**再走 `.ytd` 索引。而 shader 的 `grcTextureRef` 结构里 `+0x18` 是 **pad**（不是 W/H），偶尔"看起来合法"⇒ 从 `.ydr` 里读到无关字节 ⇒ 噪声 | **顺序反转**：先全量 `.ytd` 索引（名字→条目权威配对），内嵌路径**只对 `*_pal` 开放**（调色板确实只在内嵌），并加 `blockSize ↔ 面积` 自洽校验 |
| 2 | 同名贴图有多个版本，取到低清/错版 | 索引用 `setdefault`，取到的只是 glob 顺序第一个 | 改**取面积最大**（优先 `+hi`/`+hidr` 的 HD 版） |
| 3 | 少数贴图仍标红（缺） | 它们的字典还没抽到（`rho_be_paintwood_*`、`rho_cs_depottrim_*` 等） | 加**关键词/词干回退**（`paintwood`→`woodpaintedoverlap`），并在 HUD 里用 `≈原名` 明示；缺 8 → **缺 5**、回退 37 |

**另外新查**：`gtxd_valentine`（Valentine 共享纹理字典，`levels_2.rpf → levels/rdr3/gtxd/gtxd_valentine.rpf`）已抽出并纳入索引；
`levels/rdr3/gtxd/gtxd.rpf` 里只有 `gtxd.ymt` 清单，**没有贴图**（排除一条路）。

---

## 9. 交付物一览（给接手人）

| 想做什么 | 去哪 |
|---|---|
| **看真房子（Valentine，双击）** | `export/levels/town/valentine_real.html` |
| 看动画数据 | `export/rdr2_decode_preview/index.html`（http 服务）|
| 看骨架结构 | `export/rdr2_decode_preview/skel_body.html`（http 服务）|
| **看城镇/地形（双击）** | `export/levels/town/valentine_terrain.html` |
| 看地形（http） | `export/levels/terrain/terrain.html` |
| **看解码出的纹理** | `export/models/textures/sheet_trainstn.png` + `val_01_trainstn/*.png` |
| 拿原始资产 | `export/animations/` `export/models/` `export/levels/` |
| 查文件清单 | `inventory.csv` |
| 搞清格式细节 | `RDR2_ycd动画解码.md` / `RDR2骨架_yft格式.md` / `RDR2地形与城镇.md` / `RDR2_ydr几何格式.md` |
