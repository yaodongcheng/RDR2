# TODO —— 交接版（2026-10-28 23:30）

> 交接顺序：1) 本文件 2) `AGENTS.md`（长任务/禁开大文件/已知坑）3) `docs/最高原则_单一管线与分块即裁剪.md`（五条禁令）
> 历史 TODO 在 `docs/交接与状态/TODO.md`。

---

## 0.5 最重要的下一步（2026-10-28 23:30 重排）

**结论：补全模型库** —— 把 ytyp 的 `assetName` 解出来、回填 `archetypes.json`、按 hash 从 RPF 抽件、入库、重建。

四步与验收已写在 `docs/世界与地编/RDR2_整图覆盖率核查_20261026.md` §7，**别从头再设计一遍**：

| 步 | 做什么 | 判据 |
|---|---|---|
| 1 | `tools/ytyp_archetypes.py` 增存 `assetName` 并回填 `export/levels/town/archetypes.json` | 49,595 种 archetype 里有 assetName |
| 2 | RPF 按 hash 定位 drawable（`rdr2rpf find` 支不支持裸 hash 待验） | 抽得到 `.ydr` |
| 3 | `dump_model_lib.py` 入库 | `index.json` 模型数上升 |
| 4 | `blender_continent.py --rails --full` 重建 | **未命名实例 50,007 → <5,000；圣丹尼斯 2,124 → <300** |

**为什么是它** —— 一件事同时解三个缺口：

1. 大陆 **50,007 个「未命名 archetype」实例**（≈4.4 万大件摆不出来）；
2. 本文件 #4（4.4 万模型无 albedo）与 #5（52,807 实体缺模型）；
3. **骑砍2 侧的圣丹尼斯缺口**：源 `.ymap` 半径内约 **24,000** 实体，导出瓦片只有 **6,568**。
   ⚠️ 这一条是**高度可能同根**（模型库缺件 → 导出侧取不到几何就跳过），但**尚未证实**；
   第 1~2 步做完，**先看瓦片实例数涨没涨**就能定性（涨 = 同根，不涨 = 导出侧另有过滤，
   见骑砍2 侧 `H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\LivingWorldNpcs\plans\大镖客2还原\00-总纲.md` 的「下一步 TODO」第 1 项）。

**为什么不先做 #1（材质仍是旧 tid）**：它只需跑一遍现成脚本 + 7~10 分钟存盘，但**模型补齐后反正要重建 blend，材质会一起重生成** —— 现在做等于白做一次。真要现在看效果，再跑也不迟。

---

## 一句话状态

**唯一主产物：`deliverable/blender/continent/continent_v8.blend`（6.81 GiB，21:53 存）**
对象 147,499 / `ENTITIES` 106,095 / `HIDDEN_VEG` 10,860 / `HIDDEN_TERRAIN_CELL` 30,550 / `HIDDEN_LOD` 2,187。
贴图已从"按 tid"改为**按名字重绑**（池 3,025 → 5,292；模型 89.7% 有 albedo、子网格 90.1%），
但**已存盘 blend 的材质仍是旧 tid**，所以肉眼修复只完成了一部分（见未完成 #1）。

---

## 1. 五分钟上手

```
① 双击 打开大陆_流畅.bat   → 自动打开目录里最新的 continent_v*.blend（当前 v8）
② 3D 视图按 N              → 「RDR2」页签：12 类开关 / 全图·当前地块 / 水面 / 水位 / 植被
③ 验贴图                   → 搜 new_gar06_park_terrain（草坪网格已在场景里，材质问题见 #1）
④ 不开 blend 核对          → uv run python tools/report_manifest.py
```

默认隐藏的集合（想看要单独勾）：`HIDDEN_VEG`（植被）· `HIDDEN_TERRAIN_CELL`（地形 patch）· `HIDDEN_LOD`（远景 LOD 碎片）

---

## 2. 文件清单

### 有效产物

| 文件 | 大小 | 说明 |
|---|---|---|
| `deliverable/blender/continent/continent_v8.blend` | 6.81 GiB | **唯一主产物** |
| `.../continent_v8.blend1` | 6.81 GiB | 21:50 自动备份（**可删**） |
| `.../manifest*.json(l)` | 30.9 MB | 对象级清单 + 汇总 |
| `deliverable/blender/sdn_full2/sdn_full2.blend` | 1.30 GiB | **2026-10-28 从 archive 恢复**：圣丹尼斯单城 r=2000，含两条铁路线 + 钢桁架桥（glTF 管线，无水面）；archive 原件仍在 |
| `deliverable/blender/willard/willard_full.blend` | 1.03 GiB | 夏洛蒂家（陷地修复未验证）；`willard_full_orig.blend` 可删 |
| `deliverable/blender/guarma/guarma.blend` | 0.29 GiB | 瓜马岛 |
| `assets/lib_native/` | — | 模型 **58,670** / 贴图 **5,292** |
| `work/lib_gtxd/txd/` | 3.6 GB | 贴图池 660 个 ytd（32 个 gtxd 包） |
| `work/lib_gtxd/txd_prev/` | 0.9 GB | 各区域预览已解析的 2,917 张命名 PNG（已登记 index） |
| `work/lib_gtxd/txd_world/` | — | 重抽的 646 个 ytd（与上面基本重复） |
| `raw/_missing/` | — | 从游戏 RPF 抽的 5,581 个 .ydr/.yft，已入库 3,745 |

### 建议删除（等你点头，脚本可一次性清）

| 目录/文件 | 占用 | 原因 |
|---|---|---|
| `work/lib_gtxd/txd_game/` | **28.5 GiB** | 19,058 个 ytd，几乎全是 `ui_*`/`metaped_*`（角色/UI），场景不用 |
| `archive/废弃_sdn_full管线/` | 4.3 GiB + `sdn_full2.blend` 1.30 | 废弃 glTF 管线产物（模型库残缺，禁当基准） |
| `continent_v8.blend1` / `willard_full_orig.blend` | 6.81 + 1.03 GiB | 上一版/原始备份 |

### 已删除（别再找）

`continent.blend`(9.87 GB) · `continent_v2`(8.07) · `v3`(8.07) · `v4`(7.90) · `v5`(6.31) · `v6`(6.36) ·
`raw/verify/tile_test.blend`(2.43) · `raw/_scratch/tile_test/tile_v6test.blend`(0.93) · `raw/sdn/test_ground.blend`(0.02)。
**v7 从未生成。** 合计释放 49.94 GiB。

---

## 3. 关键脚本

| 脚本 | 用途 |
|---|---|
| `tools/blender_continent.py` | **唯一构建入口**：`--rails --full [--veg hide\|delete\|keep] [--pad]` |
| `tools/postprocess_continent.py` | 补跑分类/植被/地形隐藏/清单（`--skip-classify`、`--veg hide`、`--manifest-only`） |
| `tools/report_manifest.py` | **不开 Blender 核对** + `--find/--class/--tile` 查询 |
| `tools/write_manifest.py` | 写对象级清单；`_mat_tex` 把 `tid<0` 或 `>=0xFFFFFFF0` 视为无 albedo |
| `tools/rebind_textures.py` | 模型→贴图**按名字**重绑（禁 fuzzy）；自动追加 `work/model_file_map.json` |
| `tools/relink_materials.py` | 按当前 index 给**已存盘 blend** 重挂材质（按"首次出现去重"对齐槽位） |
| `tools/hide_lod.py` | 远景 LOD → `HIDDEN_LOD`（隐藏不删）；`--shots` 顺带出图 |
| `tools/fix_mis_tagged_hidden.py` | 把误判成 `terrain_cell` 的对象放回 `ENTITIES`（判定：名字无 `__hd_0_`） |
| `tools/render_check.py` | 无 GUI 俯视检查图（Workbench+TEXTURE，几秒一张） |
| `tools/harvest_preview_textures.py --index` | 收割 `export/previews/*/textures` 并登记进 index |
| `tools/extract_missing_from_game.py` / `ingest_extracted_models.py` | 抽缺失模型 / 增量入库（先备份 index） |
| `tools/extract_textures_from_game.py` | 抽 .ytd（`--only gtxd`、`--out` 分流） |
| `tools/run.cmd` | 本机起子进程的唯一稳妥方式（见 AGENTS §2.6） |
| `tools/read_text.py` | 读 GBK/任意编码文本（`.bat` 必用） |
| `tools/watch_build.ps1` | 长任务看门狗（RUNNING/BUSY/STALLED/EXITED） |
| `tools/_unbuffer.py` | Blender 内嵌 Python stdout 行缓冲（否则日志空白） |

---

## 4. 常用命令

```powershell
# 全量重建（实测 45~55 分钟）
cmd /c 'tools\run.cmd D:\BrainMaker\build_vN.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --python tools\_unbuffer.py -P tools\blender_continent.py -- --out D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent\continent_vN.blend --lib D:\BrainMaker\大镖客2解包分析\assets\lib_native --rails --full'

# 单步补丁（每次加载+存盘实测 7~10 分钟，别按"几分钟"估）
cmd /c 'tools\run.cmd D:\BrainMaker\_p.log "<blender>" -b <blend> --python tools\_unbuffer.py -P tools\hide_lod.py -- --shots'
cmd /c 'tools\run.cmd D:\BrainMaker\_p.log "<blender>" -b <blend> --python tools\_unbuffer.py -P tools\relink_materials.py'

# 核对 / 贴图 / 模型
uv run python tools/report_manifest.py --find new_gar06_park_terrain
uv run python tools/harvest_preview_textures.py --index
uv run python tools/rebind_textures.py
uv run python tools/extract_textures_from_game.py --packs textures_0 --only gtxd --out work/lib_gtxd/txd_world
uv run python tools/extract_missing_from_game.py --packs levels_1 levels_2
uv run python tools/ingest_extracted_models.py
```

---

## 4.5 上轮 TODO（2026-10-28）对照 —— 哪些已经做掉了

| 上轮 # | 事项 | 现状 |
|---|---|---|
| 1 | `continent_v6` 重建失败 | ✅ **已完成**：v8 已生成（147,499 对象 / 6.81 GiB） |
| 2 | 44,849 个模型无源 ydr | ⚠️ **转化**：现表述为"4.4 万模型无 albedo"，见未完成 #4 |
| 3 | 62,989 个实体缺模型 | ⚠️ **收窄**：52,807（levels_0~7 已扫完），见未完成 #5 |
| 4 | `pad_field` 默认开启 | ✅ **已作废**：默认关，要压平需显式 `--pad` |
| 5 | H4 地形空洞 26.7% | ✅ **已作废**：`valid_full.npy` 99.34%，H4.npy 无 NaN |
| 6 | `manifest.json` 未做 | ✅ **已完成**：v6 起有，`report_manifest.py` 可不开 Blender 核对 |
| 7 | `--bbox` 未做 | ❌ **仍未做**，见未完成 #7 |
| 8 | `sdn_full` / `sdn_full2` 未清理 | ✅ **已归档**；且按用户要求把 `sdn_full2.blend` **恢复到 `deliverable/blender/sdn_full2/`** |
| 9 | 植被误删未核实 | ✅ **已根治**：改为隐藏（`HIDDEN_VEG` 10,860），不删数据 |
| 10 | 地形色图城区偏深 | ⚠️ **变向**：现在是**发白**（RGB 236,240,240），见未完成 #2 |
| 11 | willard 陷地修复未验证 | ❌ **仍未验证**，见未完成 #6 |

**结论：11 项里 6 项完成 / 3 项转化 / 2 项仍开（`--bbox`、willard 验证）。**

---

## 5. 未完成（按优先级）

| # | 事项 | 现状（数据） | 下一步 |
|---|---|---|---|
| **1** | **blend 里材质仍是旧 tid** | 重绑后库已正确（草坪 s=[2607 草, 2606 土]），但 blend 里是 `m_352`门皮/`m_353`门皮；`relink_materials` 只改了 11,199 槽，**59,385 个网格因槽数≠子网格数被跳过**（后已改成"首次出现去重"对齐，跑过一次未存盘即被叫停） | ①重跑 `relink_materials.py`（这次的去重对齐版本）；②根修：构建时**每个子网格一个材质、按贴图名字建**，不做槽去重 |
| 2 | 城区地面发白 | 地面色图城区≈纯白（(2434,−1207) 实测 RGB 236,240,240） | 重烘色图，或用路面/草地网格覆盖；不许猜色（禁 6.3） |
| 3 | 水面灰色平板 | 1 个 quad，z=40.5，无材质 | 加半透明水材质（纯显示，不动水位） |
| 4 | 4.4 万模型无 albedo | 库内 48,594 个模型无 ydr 源；按"hash==joaat(文件名)"扫盘只对上 **9,780**（20%） | 🔴 **不是"要自写 ytyp 解析"** —— 定义段早解析过（`tools/ytyp_archetypes.py` 扫 1,026 个 ytyp，49,595 种已进 `archetypes.json`）。缺的是**把 `assetName` 抽出来回填**。四步见 §0.5 |
| 5 | 缺模型 52,807（实体口径） | levels_0~7 已扫完；`textures_0/1`+`packs` 已验证无更多世界贴图 | 与 #4 **同一件事**，见 §0.5。⚠️ 骑砍2 侧同根：圣丹尼斯源 24,000 实体、导出瓦片只有 6,568 |
| 6 | willard 陷地未验证 | `willard_full.blend` 已跑 `blender_fit_ground.py`（613 顶点） | 用 `render_check.py` 数值化验证 |
| 7 | `--bbox` 未做 | 只有 `--only-tile` | 加 `--bbox x0,y0,x1,y1` |
| 8 | `classify` 的 `ivy` 误命中 `privy` | `cal_privy_01`（厕所）被分进 veg | 正则加边界 |
| 9 | 两个异常对象 | `wll_tempbox2` / `wli_tempbox` 在 z ≈ −1001 m | 查来源后修正或隐藏 |
| 10 | 远景 LOD 与真实几何重叠 | 2,187 个已进 `HIDDEN_LOD`（未删） | 保持默认隐藏 + N 面板开关即可 |
| 11 | 资源快照还没上传 | 本机有 2×`terrain.bin` + 2×`flora.bin` + 2×`*.tpac` = 57.6 MB；远程只有 `main` 分支 | GUI 点「📦 上传资产」= `python git_assets.py save`（`assets` 分支永远只存一份） |

### 已作废的旧条目（别再查）

- ~~H4 地形空洞 26.7%~~：`valid_full.npy` 99.34%，H4.npy 无 NaN
- ~~换 H4_final 高程~~：实体残差中位 H4.npy **0.19 m** vs H4_final 0.39 m → **继续用 H4.npy**
- ~~pad_field 默认开~~：默认关，要压平显式 `--pad`
- ~~植被删除~~：改隐藏（`HIDDEN_VEG`），不丢数据
- ~~manifest 未做~~：已做（v6 起）
- ~~`scan_rpf_for_missing.py` 没跑过~~：跑过（978 命中/1,011 抽取），已被新工具取代

---

## 6. 本轮已完成（别重复）

| 项 | 结果 |
|---|---|
| 贴图按名字重绑 | 池 3,025→**5,292**；两次共改绑 2,863 + 4,131 个模型；模型 89.7% / 子网格 90.1% 有 albedo |
| 修 id 串号 | v6 里"门绑草地"已修；追加 `work/model_file_map.json`（9,780 个无源模型找到同名文件） |
| 预览贴图收割 | `export/previews/*/textures` 2,917 个唯一名字 → 池 + 登记 index（+1,874） |
| 模型解包 | levels_0~7 全扫 43 分钟，抽出 5,581 个，入库 +3,745（54,925→58,670） |
| v8 重建 | 对象 137,314→**147,499**，ENTITIES 99,012→**106,095**，RAILS 1,284→**1,365** |
| 植被/地形/LOD 隐藏 | `HIDDEN_VEG` 10,860 / `HIDDEN_TERRAIN_CELL` 30,550 / `HIDDEN_LOD` 2,187 |
| 修"草坪被当地形 patch 隐藏" | 9 个对象放回 ENTITIES；`TERRAIN_CELL` 正则去掉 `_terrain`/`_ground\d*$`（根因已在代码里改） |
| 清单体系 | `manifest.jsonl` + 汇总 + `report_manifest.py`（不开 blend 核对） |
| 渲染检查 | `render_check.py`（Workbench+TEXTURE，几秒一张俯视图） |
| 清理 | 释放 49.94 GiB（旧 blend 全删） |
| 工具基建 | `run.cmd`、`read_text.py`、`_unbuffer.py`、`watch_build.ps1` |
| 文本层入库（2026-10-28） | `docs/`、`tools/`、根文档、3 个启动器搬进骑砍2 mod 仓库 `Modules\RDR2\Source\`；D 盘留 junction / 符号链接，**脚本里的绝对路径一行没改**。511 个文件 / 21.5 MB，已提交 `68766b7`、`8555a4a` |

---

## 7. 已知坑（详见 AGENTS.md §4）

- **贴图只存 tid 不存名字 → 池子一变就串号**：v6"门长草"、v8"草坪发黄"都是同一个根因
- **已存盘 blend 不会跟随 index 更新**：重绑之后必须 relink 或重建
- 构建时材质槽**按 tid 去重**，槽序与 `s` 不对齐 → 外部脚本不能按 `s` 顺序硬挂
- 长任务别用阻塞命令；实测单步"加载+存盘"= 7~10 分钟，不要给"10 分钟"这种乐观承诺
- 从 pwsh 直接起 python/blender → `Access is denied` / `0xc0000142` 弹窗 → 走 `tools\run.cmd`
- Blender `-b` 日志全缓冲 → 加 `--python tools/_unbuffer.py`
- `strip_vegetation --mode delete` 极慢 → 默认 `hide`
- 游戏运行时 rpf 全被独占锁 → 抽包前先关 RDR2
- `cmd` 把 `--packs a,b,c` 的逗号当分隔符 → 用空格（`nargs='+'`）
- `--lib` 必须绝对路径
- 相对路径 `--out work\verify` 会被解析到 `C:\work\verify`（用绝对路径）
