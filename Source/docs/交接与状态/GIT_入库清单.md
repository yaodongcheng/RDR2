# GIT 入库清单 —— 三个入口 + 一本账（2026-10-28 定稿）

> 🔴 **2026-10-28 更新**：本文的**分类口径仍然有效**（哪些是文本、哪些是账本、哪些不进库、怎么恢复），
> 但「在哪建仓库」已改：文本层搬进了骑砍2 mod 仓库 `Modules\RDR2\Source\`，
> D 盘 `docs/`、`tools/` 是 junction 指回去。**§5「初始化」里在 D 盘 `git init` 的步骤作废**；
> 根目录的 `.gitignore` / `.gitattributes` 已删除，白名单改由 `Source\.gitignore` 承担。
> 现行说明见 README「〇、文件在哪」与「〇.2 这次架构改了什么」。

> 目的：把"将来要进 git 的东西"在**不搬家、不改路径**的前提下圈死，避免每次 `git init` 都要重新挑一遍，
> 也避免下一次"清理"把不该删的删掉（见 `docs/交接与状态/资源清理清单.md`）。
>
> 配套文件（**现行**）：`Source\.gitignore`（白名单式）+ `Source\.gitattributes`（`.bat` 不做换行转换）。
> ~~根目录 `.gitignore` / `.gitattributes`~~ 已于 2026-10-28 删除，规则已并入上面两份。

---

## 0. 一句话

**只收文本（现行 = 已入库的部分）：`Source\docs\` 整棵 · `Source\tools\` 整棵 · `Source\README.md` · 4 篇入口 md · 3 个启动 bat。**
二进制一律不进（6.81 GiB blend、13 GB 模型库、51 GB raw、58 GB 预览 glTF/GLB/贴图），它们靠"哈希清单 + 第二份拷贝"保护。

> ⚠️ **本轮没纳入的**：`export/`（含 §3 里那些账本）与 `assets/lib_native/index*.json` ——
> 它们都在 15.9 GB 的 export 树里，文本与 glb 混在同一批目录、拆不开（见 README 〇.2 与 §3 顶部的红字）。
> **在补上之前，这些账本只有本机一份。**

> ⚠️ 目录名是 `tools/`，**不是 `scripts/`**。不要改名：`tools/README.md` 写明"脚本之间 `import 模块名`，不要移动文件"，
> 且 100+ 个脚本把 `D:/BrainMaker/大镖客2解包分析/tools` 写成了常量。

---

## 1. 三个入口

| # | 入口 | 内容（2026-10-28 实测） | 进 git 的方式 |
|---|---|---|---|
| ① | `docs/` | **69 篇 .md**（65 篇原文档 + 4 篇从根目录并进来的）+ 60 张证据图（图**不进 git**） | 整棵（图被白名单挡住） |
| ② | `tools/` | **333 个 .py** + `rdr2rpf/src/*.cs`（29 个）+ `run.cmd` / `watch_build.ps1` / `_unbuffer.py` / `read_text.py`；最终入库 **406 个** | 整棵，但 `tools/ref/**`（2307 个第三方文件）和 **`**/obj/**`** 排掉 |
| ③ | `export/` 的**文本层** | 约 44 个 .html + 约 60 个 .json + `export/levels/world/*.csv\|json` | 🔴 **本轮未纳入**（export 15.9 GB 拆不开，见 §3 红字） |

**第 ④ 项（容易被漏）**：入口文档 `README.md`（在 `Source\` 根）+ `AGENTS.md` / `TODO.md` / `STRUCTURE.md` / `README_骑砍2交接.md`（都在 `docs\` 根）
+ 三个启动 bat（在 `Source\launchers\`，D 盘根是符号链接）。
它们不属于上面三个目录，但"从哪读起、为什么会踩这些坑"全在里面——**丢了 AGENTS，下一个 AI 会重踩 GBK/共轭/0xc0000142**。

---

## 2. JSON 放哪：**不建独立目录，按"谁读它"留在原位**

这是本次唯一需要拍板的取舍。结论：**保持散落，用本文件当索引；不新建 `data/` 或 `json/`。**

理由（三条，都是硬约束）：

1. **脚本用绝对路径硬编码读它们**。例如 `tools/blender_continent.py:21-26` 写死了
   `work/terrain/H4.npy`、`export/world/world_meta.json`、`export/world/continent/tiles`。
   搬一个文件 = 整条构建链断，而且错在运行时（不是 import 时），最难查。
2. **页面用相对路径 fetch**。`export/vehicles/index.html` 读同目录 `data.json`；`export/avg/index.html` 读 `data/`。
   搬到别处 = 页面白屏，且这个错误只有打开浏览器才看得见。
3. **搬走必然产生第二份**，两份一漂移，就回到"以哪份为准"的老问题（`sdn_full` 与 `continent` 不可比就是这么来的）。

### 2.1 JSON 分四类（按读者归属）

| 类 | 路径 | 谁在读 | 数量 | 结论 |
|---|---|---|---|---|
| A 页面数据 | `export/<页面>/data.json`、`site.json`、`index.json`、`export/avg/data/*.json`、`export/story/*.json`、`export/cutscene/*.json` | 同名目录的 `.html`（相对路径） | ~60 | **跟页面一起进**，不许分开 |
| B 构建账本 | `export/world/continent/{index,models}.json` + `tiles/*.json`（43 块） | `blender_continent.py`（ymap→blend 的唯一事实层） | 45 | **必须进**，见 §3 |
| C 抽取账本 | `assets/lib_native/index*.json`、`raw/model_file_map.json`、`raw/rpf_*_state.json`、`raw/ingest_report.json` | `dump_model_lib` / `rebind_textures` / `ingest_extracted_models` | 8 | **必须进**，见 §3 |
| D 下游契约 | `export/world/bannerlord/{camp_scenes.json,Rdr2CampBehavior.cs}`、`deliverable/handoff/*`（17 个） | 骑砍2 侧 / 第三方 | 19 | **进**（契约天然该版本化） |

> 想"一处看全"用这张表，不要动文件。
> 若将来真要抽独立目录，唯一安全做法是**让脚本改读新路径 + 全链回归**，那是另一件事（不在本轮范围）。

---

## 3. 账本白名单（体积最小、价值最高，删了就恢复不出来）

> 🔴 **2026-10-28 实况：下面 10 项里只有 `tools/rdr2rpf/src/names.txt` 真进了库。**
> 其余 9 项全在 `assets/`、`raw/`、`export/` 里 —— 那三棵是"文本与二进制混在一起"的大树，
> 本轮决定不搬（见 README 〇.2），所以它们**目前只有本机一份**。
> 要补，只有一条干净路：把 `export/world/continent/`（含 43 个 tiles）与 `assets/lib_native/index*.json`
> 单独搬到仓库里留联接 —— 但这会牵动脚本的绝对路径，**另开一件事做，别顺手改**。

```
assets/lib_native/index.json            58,670 个模型 名字/hash/tid 对照（AGENTS §4：重跑 dump_model_lib 会覆盖成 10,076）
assets/lib_native/index_before_*.json   4 个入库前快照
raw/model_file_map.json                 9,780 个「无源模型 → 同名文件」
raw/rpf_extract_state.json              增量解包进度（删了 = 几十分钟全量重扫）
raw/rpf_tex_state.json                  增量抽贴图进度
raw/ingest_report.json                  入库报告
export/world/continent/index.json       地块索引
export/world/continent/models.json      模型清单
export/world/continent/tiles/*.json     43 块实体（10.6 万 ENTITIES 的来源，0.7 MB）
tools/rdr2rpf/src/names.txt             joaat → 资产名。没有它，hash 全是无名数字，铁路/贴图按名字匹配全部失效
```

合计约 **30 MB 文本**，是 `continent_v8.blend`（6.81 GiB）能不能重建、能不能核对的**前提**。

---

## 4. 明确不进 git 的（附恢复成本）

| 路径 | 体积 | 恢复方式 | 成本 |
|---|---|---|---|
| `deliverable/blender/**/*.blend` | 9.4 GiB | `blender_continent.py --rails --full` | 45~55 min，且要 lib + tiles 齐 |
| `assets/lib_native/{models,tex}/` | ~13 GB | `dump_model_lib.py` 增量 | 数小时，且**依赖上面的 index.json** |
| `raw/`（含 `raw_gtxd`、`txd_game` 28.5 GiB） | 51 GB | 从游戏 RPF 重抽 | 1~3 h/批；⚠️ `raw/towns` 的 bbox 只在源里 |
| `export/previews/*/tiles`、`export/world/tiles` | 2.6 GB | `export_sdn_gltf.py` / `build_settlement_previews.py` | 分钟级 |
| `export/**/*.glb`（npc / vehicles / viewer） | 3.2 GB | 导出脚本 | 分钟~小时 |
| `tools/ref/` | 0.07 GB / 2307 文件 | GitHub 重下 | 分钟级 |
| `manifest_*.jsonl` | 30 MB | 打开 blend 重出（7~10 min） | 每次构建都变，进 git 只会把仓库撑爆 |
| `*.log`、`*.blend1`、`*.bak`、`__pycache__` | — | 无需 | — |

**两个"不进但要单独备份"**：
- `录屏/` —— **不可再生**（要重录），但不属于工作流 → 外置归档；
- `deliverable/heightmap/` + `terrain_weights/`（71 MB）—— 可从游戏重烘，但重烘要 raw/terrain；先外置，等确认不再重烘再决定是否补进。

---

## 5. 初始化（等你点头再执行，本轮未做）

```powershell
cd "D:\BrainMaker\大镖客2解包分析"
git init
git add -A

# ① 先看体量：文件数 / 总量 / 最大的 20 个
git ls-files | Measure-Object -Line
git ls-files | ForEach-Object { [pscustomobject]@{MB=[math]::Round((Get-Item $_).Length/1MB,2); Path=$_} } |
  Sort-Object MB -Descending | Select-Object -First 20

# ② 单文件 >50 MB 就该拦下来（>10 MB 也要看一眼是不是 JSON 账本）
git ls-files | ForEach-Object { if((Get-Item $_).Length -gt 50MB){ $_ } }

# ③ 确认没有二进制误入
git ls-files | Select-String -Pattern '\.(blend|glb|gltf|bin|png|jpg|mdl)$'
```

预期：文件数 **500±50**，总量 **100~250 MB**（主要来自 `export/**/*.json`、`docs/**/img`、`assets/lib_native/index.json`）。
若超过 400 MB，说明有 JSON 账本过大 → 用 `git lfs` 单独挂，或把该文件移出（先改代码路径！）。

首次提交建议分三次，让历史可读：

```powershell
git add .gitignore .gitattributes *.md *.bat docs
git commit -m "baseline: 最高原则/AGENTS/TODO/交接文档 + 启动器"
git add tools
git commit -m "tools: 唯一构建管线 + 格式解码器 + 抽取链 + 观测基建"
git add export deliverable/handoff assets/lib_native/*.json raw/*.json
git commit -m "data: 页面文本层 + 构建账本 + 下游契约"
git tag continent-v8
```

---

## 6. 验收口径（每次 add 都要过）

- [ ] `git ls-files` 里**没有任何** `.blend/.glb/.gltf/.bin/.png/.jpg/.mdl`
- [ ] 单文件最大 **< 50 MB**，总量 **< 250 MB**
- [ ] `tools/blender_continent.py`、`tools/report_manifest.py`、`docs/最高原则_*.md`、`AGENTS.md` 都在
- [ ] `tools/rdr2rpf/src/names.txt` 在（这是"能从游戏恢复"的地基）
- [ ] `raw/` 只进了 4 个账本，`work/` 一个都没进（联接目录）
- [ ] `git status` 干净后再开始任何清理动作（删东西前先 `git diff` 一遍）

---

## 7. 已知风险（本轮发现，未修）

| # | 风险 | 影响 | 建议 |
|---|---|---|---|
| 1 | `tools/blender_continent.py.bak` / `.bak2` 混在 332 个脚本里 | 有人 `copy .bak → .py` 就回退到旧语义（`--full` 六步链会丢） | 移入 `tools/archive/`，改名带日期 |
| 2 | `tools/README.md` 只索引约 180 / 332，**10-28/29 的 classify/manifest/rebind/hide 链一个都没收录** | 照索引干活会漏掉"可核对性" | 补一节「构建后处理与验收」 |
| 3 | `README.md` §30 秒入口仍指向 `continent.blend`（已删，现为 `continent_v8.blend`） | 交接第一眼就找不到文件 | 改路径 |
| 4 | `names.txt` 有 `src/` 和 `bin/` 两份 | git 里双份（几 MB×2），且 `blender_continent.py:76` 读的是 `bin/` 那份 | 保留 bin/ 那份（已在 .gitignore 中放行），或让代码回退读 `src/` |
| 5 | `tools/archive/` 目录**不存在** | 资源清理清单 §7 的"归档而不是删"没法执行 | `mkdir tools\archive` 后迁 22 个探针 |

---

## 8. 与现有文档的关系

| 文档 | 关系 |
|---|---|
| `docs/最高原则_单一管线与分块即裁剪.md` | 决定 `tools/` 里哪些是"唯一管线"、哪些只是历史证据 → 见 `tools/archive/` 的取舍 |
| `AGENTS.md` §3 | 决定 `manifest` / `report_manifest` 必须进 git（否则验证规范失效） |
| `AGENTS.md` §4 | 决定 `.gitattributes` 里 `.bat -text`、以及 `names.txt` 必须留 |
| `docs/交接与状态/资源清理清单.md` | 资源维度（A/B/C/D）已完成，本文件补的是**脚本 + 账本维度** |
