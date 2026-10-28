# 荒野大镖客 2（Red Dead Redemption 2）资产解包分析

本目录用于从本机安装的《荒野大镖客 2》中提取可用资产。当前已完成：**动画资源**、**角色模型**、**关卡/地图编辑信息** 三大类的提取与结构校验。

- 游戏安装目录：`H:\EPICGAMES\RedDeadRedemption2`
- 工作目录：`D:\BrainMaker\大镖客2解包分析`
- 版本信息：主程序 `RDR2.exe`，资源封装为 RAGE `.rpf`（RPF8，PC / y 平台）

---

## 1. 封包格式分析（关键结论）

RDR2 与 GTA V 同属 Rockstar RAGE 引擎，但 RPF 版本与加密不同，这是本次解包的核心难点：

| 项目 | 结论 |
|---|---|
| 封包格式 | `.rpf`，魔数 `0x52504638`（`RPF8`，即 "RPF version 8"，RDR2 PC） |
| 头部结构 | `Magic(4) + EntryCount(4) + NamesLength(4) + DecryptionTag(2) + PlatformId(2)`，随后 256 字节 RSA 签名 |
| 平台标识 | `PlatformId = 121 (0x79)` = PC；`111` = PS4 |
| 目录表（TOC） | 每项 **24 字节**，整体被 **TFIT2 密码（Tfit2 CBC 变体）** 加密，用 `DecryptionTag` 选密钥 |
| 命名方式 | RPF8 的条目 **按 32 位 JOAAT 哈希索引，不存字符串名**；名字需用外部 names 表反查（`tools/rdr2rpf/src/names.txt`，294470 条） |
| 文件压缩 | `Compressorid`：0=None / 1=Deflate / 2=**Oodle**（用游戏自带 `oo2core_5_win64.dll` 解压） |
| 资源格式 | `.ydr/.ydd/.yft/.ytd/.ycd/.ymap/.ytyp/.ybn` 等均为 RSC8 资源（`Magic=0x38435352`，16 字节头 + Oodle/Deflate 数据段） |
| 每文件加密 | 条目可单独带 `EncryptionKeyId`，文件数据再用同一 TFIT2 家族密码（按 StridedCfg 分块）解密 |

> 注意：RDR2 的 RPF8 与开源库 `rage-rpf` 声称支持的 RPF8 不是同一上下文 —— 它明确拒绝 TFIT（"RDR2 keys not supported"）。本次使用的是自带密钥表的 RDR2 专用实现。

---

## 2. 工具链（自建，可复用）

本机无现成的 RDR2 RPF 工具，且处于受限网络（仅 `github.com / api.github.com / codeload.github.com` 可达，PyPI/NuGet/crates 均被墙）。做法是：

1. 从 GitHub 取得 RDR2 RPF8 参考实现（`lazenes/RPF8_TOOL`、`amrshaheen61/RDR2-RPF-Tool`），其中含 TFIT2 密码、PC 密钥表、RSC8 解析、names 表；
2. 用本机 **dotnet 9** 把这些 Core 源码编译成一个**无界面命令行提取器** `rdr2rpf`；
3. 用游戏自带的 `oo2core_5_win64.dll` 完成 Oodle 解压。

- 工具源码：`tools/rdr2rpf/`（`Program.cs` 命令行 + `src/` 参考 Core）
- 可执行：`tools/rdr2rpf/bin/Release/net9.0/rdr2rpf.exe`
- 用法：
  ```bash
  rdr2rpf list    <archive.rpf> [关键词]        # 列条目（名称/大小/压缩/是否资源）
  rdr2rpf find    <archive.rpf> [关键词]        # 过滤
  rdr2rpf tree    <archive.rpf>                 # 按扩展名统计
  rdr2rpf extract <archive.rpf> <outdir> [关键词] [--recurse]   # 提取（--recurse 自动下钻嵌套 rpf）
  ```
  运行前确保 `oo2core_5_win64.dll` 与 `names.txt` 在 exe 同目录（已随构建复制）。

---

## 3. 顶层封包结构

| 封包 | 内容 |
|---|---|
| `common_0.rpf` | `data/...` 全局 meta/dat（heightmap、mapzones、ai/conditionalanims 等） |
| `anim_0.rpf` | 582 个嵌套 `.rpf`：`anim/ingame/*`（玩法动画）、`anim/motions/*`、`anim/cutscene/*`（过场）、`anim/expressions/*` |
| `packs_0/1.rpf` | 角色/道具模型：`packs/base/models/metapeds_*`、`weapons`、`metaped_textures_*`；及各类 `.ymt` |
| `levels_0..7.rpf` | 世界地图：`levels/rdr3/area/*`（区域模型）、`terrain/*`（地形）、`*_metadata.rpf`（`.ymap/.ytyp`）、`*_collision.rpf`（`.ybn`）、`navmeshes*`（导航网格） |
| `data_0.rpf` | 全局 `.ymt/.xml/.ydd` 配置 |
| `textures_* / hd_0 / update_*` | 贴图、高清资产、补丁（本次未提取） |

---

## 4. 已导出资产（`export/`，共 20,074 个文件 / 约 8.6 GB）

| 分类 | 目录 | 数量 | 体量 | 内容 |
|---|---|---|---|---|
| 动画 | `export/animations/` | 407 | 34 MB | `.ycd` 动画剪辑字典（见 §5） |
| 角色模型 | `export/models/player/` | 1458 | 304 MB | 主角 `.ydd` 绘制字典（Arthur/John 等 player_*）/`.yld` |
| 武器模型 | `export/models/weapons/` | 514 | 213 MB | 武器 `.ydr` + `.ytd` 贴图 |
| 地图元数据 | `export/levels/map_metadata/` | 5364 | 81 MB | `.ymap`（4228，实体摆放）+ `.ytyp`（1026，原型定义） |
| 地形碰撞 | `export/levels/collision/` | 12331 | 8.1 GB | `.ybn`（碰撞网格，12301 个） |

完整逐文件清单（路径/大小/魔数）：`inventory.csv`（UTF-8-BOM，Excel 可直接打开）。

> 校验：除 `_cache.ych / _manifest.ymf` 这类索引/清单文件外，**全部资源文件的 RSC8 魔数均正确**，说明解密 + Oodle 解压链路无误。

---

## 5. 重点：把人扛起放到马上的动画（carry ped onto horse）

RDR2 里"把（死/伤）人搬上马"属于 **机械动画(mech)**，核心字典在
`anim/ingame/clip_mech_carry_ped.rpf`，已导出到 `export/animations/mech_carry_ped/`（25 个 `.ycd`）。

**最直接对应"扛起并放到马上"的剪辑：**

| `.ycd` 文件 | 含义 |
|---|---|
| `mech_carry_ped@dead@mount@stow@lt.ycd` | 把肩上扛的**尸体**放到马鞍上（左挂载位）——即"放上马"动作 |
| `mech_carry_ped@dead@mount@stow@rt.ycd` | 同上（右挂载位） |
| `mech_carry_ped@dead@mount@remove@lt/rt.ycd` | 从马鞍上取下尸体 |
| `mech_carry_ped@injured@mount@stow@lt/rt.ycd` | 把**伤员**放到马上 |
| `mech_carry_ped@injured@mount@remove@lt/rt.ycd` | 从马上取下伤员 |
| `mech_carry_ped@dead@carried@mount.ycd` | 尸体"被驮在马背上"的持续姿态（loop） |

配套的完整流程剪辑：
`mech_carry_ped@dead@pickup_body`（扛起）→ `...@carried@human`（扛着走）→ `...@mount@stow@*`（放上马）→ `...@mount@remove@*`（取下）→ `...@putdown_body / throw_body / drop_body`（放下/抛下/丢下）。

> 命名含义：`@lt`/`@rt` = 左/右挂载侧；`@dead`/`@injured` = 目标为尸体/伤员；`mount` = 上马（挂到坐骑）。

**伴随/相关动画**（一并导出）：
- `export/animations/veh_horseback/`（345 个）：`clip_veh_horseback.rpf` 全部骑行相关剪辑（含 `seat_saddle@*@dead@idle`、`exit@land@...@from_dead` 等"马鞍上的尸体"相关）。
- `export/animations/mech_hogtie/`（35 个）与 `export/animations/mech_drag/`（2 个）：捆绑、拖拽尸体/人相关。

---

## 6. 目录结构

```
大镖客2解包分析/
├─ README.md              # 本文件
├─ inventory.csv          # 逐文件清单
├─ export/                # 交付产物
│  ├─ animations/         #   .ycd 动画（carry_ped / horseback / hogtie / drag）
│  ├─ models/             #   player / weapons 模型
│  └─ levels/             #   map_metadata(.ymap/.ytyp) / collision(.ybn)
├─ tools/
│  ├─ rdr2rpf/            #   自建 RPF8 提取器（源码 + 构建产物 + oo2core dll + names.txt）
│  ├─ validate_inventory.py
│  └─ make_inventory.py
└─ work/
   └─ nested/             #   中间产物：从 game 顶层 rpf 抽出的嵌套 rpf
```

---

## 7. 踩坑记录 / 限制

- **TOC 加密**：RPF8 目录表被 TFIT2 加密，`rage-rpf` 等开源库不支持，必须用带密钥表的实现。参考实现里 `Decode()` 有把 `input[i+j]` 误写成 `input[j]` 的历史版本，需确认是正确版本再编译。
- **名字反查**：条目只有哈希，必须靠 `names.txt`（JOAAT 正查）还原路径名；否则只能得到 `0xXXXXXXXX`。
- **Oodle**：文件数据多为 Oodle 压缩，必须调用 `oo2core_5_win64.dll`；该 dll 用游戏自带或参考仓库自带版本均可。
- **IV 复用副作用**：TFIT2 的 `Decode()` 会在结尾改写全局 IV，对单次读取无影响，但连续解密多文件时需注意（本工具按文件新建密码实例）。
- **体量**：`.ybn` 碰撞数据体量巨大（本次 8.1 GB），如只需"地图编辑信息"可只保留 `export/levels/map_metadata/`。
- **未做可视化渲染**：`.ydr/.ydd/.ycd/.ymap` 均为 RSC8 二进制资源，需要专门的 RSC 解析器（如 Sollumz / CodeWalker）才能导入 Blender 预览；本次交付为**原始资源 + 结构校验**，未做 3D 预览。如需，可后续把 `.ydr` 转 glTF/FBX 做查看器。
- **未提取**：HD 贴图（`hd_0.rpf`、`metaped_textures_player.rpf` 779MB 等）、音频（`audio/`）、过场动画视频（`movies_0.rpf`）。

---

## 8. 复现步骤

```bash
# 1) 构建提取器
cd tools/rdr2rpf
dotnet build -c Release

# 2) 列出动画封包里的嵌套 rpf
bin/Release/net9.0/rdr2rpf.exe list  "H:/EPICGAMES/RedDeadRedemption2/anim_0.rpf"

# 3) 抽出某个嵌套动画字典并下钻提取(.ycd)
bin/Release/net9.0/rdr2rpf.exe extract "H:/EPICGAMES/RedDeadRedemption2/anim_0.rpf" work/nested "carry_ped"
bin/Release/net9.0/rdr2rpf.exe extract work/nested/anim/ingame/clip_mech_carry_ped.rpf export/animations/mech_carry_ped ""
```

---

## 9. 动画解码（RDR2 `.ycd` → 骨骼曲线）

动画数据不是"看图就能用"的：`.ycd` 是 **RSC8 v58** clip dictionary，骨架轨道用 RAGE 压缩编码，
主流工具（CodeWalker / Sollumz）只支持 GTA V。本轮已把容器 + 通道编解码打通，见：

- **逆向笔记**：[RDR2_ycd动画解码.md](RDR2_ycd动画解码.md)
- **解码器**：`tools/rdr2_ycd.py` / `tools/ycd_decode.py` / `tools/export_anim_json.py`
- **解码验证预览**：`export/rdr2_decode_preview/index.html`（gizmo 网格 + 幅度条 + 时间轴）

**已解出**：`mech_carry_ped@dead@mount@stow@lt.ycd`（扛人上马·左侧）内的
clip 列表、animation 列表（`biped_q5@biped@*` / `biped_q5@horse@*` / `prop_q5@tr3@*`）
与每根骨骼的四元数关键帧（模长≈1，验证通过）。

**未完成**：RDR2 `biped_q5` 骨架（骨骼名/层级/绑定姿势）需从 drawable 的 Skeleton 资源解析，
拿到后才能做骑砍2 重定向。
