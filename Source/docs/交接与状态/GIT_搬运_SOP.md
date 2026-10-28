# GIT 搬运 SOP —— 给执行 Agent 的作业指导书

> 🔴🔴 **2026-10-28 作废通知（先读再动手）**：本 SOP 建立在「在 `D:\BrainMaker\大镖客2解包分析`
> **原地** `git init`」这个前提上 —— **该方案已被取代，§3「执行」不要再跑**。
>
> 现行架构：文本层（`docs/`、`tools/`、根文档、启动器）已搬进
> `H:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\Modules\RDR2\Source\`
> （= 骑砍2 mod 的 git 仓库），D 盘侧是 junction / 符号链接。
> **在 D 盘执行 `git init` 只会得到空目录或顺联接爬进去，别再试。**
>
> 现行说明见仓库 README 的「〇、文件在哪」与「〇.2 这次架构改了什么」：`../../README.md`。
>
> **本文仍然有效的部分**：附录 B.1 的白名单思路、§4 的体积闸门阈值、§5 的异常决策树、§6 的禁令精神。

> 版本 2026-10-28。**本文件是唯一操作依据**，与聊天记录冲突时以本文件为准。
> 你的任务：在 `D:\BrainMaker\大镖客2解包分析` 里初始化 git，把「文本 + 小账本」纳入版本管理，
> **不移动、不删除、不改写任何既有文件**（只允许新增 §7 列出的那几样）。

---

## 0. 完成定义（DoD，缺一条就算没做完）

- [ ] `.git` 建在 `大镖客2解包分析\` 这一层（**不是** `D:\BrainMaker\`）
- [ ] 恰好 **3 个 commit** + **1 个 tag** `continent-v8`
- [ ] `git ls-files` 数量 **350~700**，总量 **< 250 MB**
- [ ] `git ls-files` 里**没有** `.blend / .glb / .gltf / .bin / .png / .jpg / .mdl`
- [ ] `git status --short` 为空（`_tmp/` 已被 ignore）
- [ ] 把 §8 回执写进 `_tmp\report.txt`，并原样贴给用户
- [ ] 既有文件 0 改动（`git status` 干净即证明）

---

## 1. 开工前必读（按顺序，别跳）

| # | 文件 | 你要从里面拿什么 |
|---|---|---|
| 1 | `AGENTS.md` | §2 长任务规范、§3 验证规范、§4 已知坑。**重点是 §2.6：不能从 pwsh 用管道抓子进程输出** |
| 2 | `docs/交接与状态/GIT_入库清单.md` | 三个入口、JSON 四类归属、账本白名单（"该进什么"的权威） |
| 3 | `docs/最高原则_单一管线与分块即裁剪.md` | §二.1：为什么 `tools/` 不能改名/移动 |
| 4 | `docs/交接与状态/资源清理清单.md` | §0 的反例：看着像垃圾其实不能删 |

---

## 2. 环境自检（任何一条不过就先停下报告）

```powershell
cd "D:\BrainMaker\大镖客2解包分析"
New-Item -ItemType Directory -Force _tmp | Out-Null

# ① 确认还没有 .git（若已有，立刻停手 —— 别人做过了）
cmd /c 'if exist .git (echo GIT_EXISTS) else (echo NO_GIT) > _tmp\pre0.log 2>&1'
Get-Content _tmp\pre0.log

# ② git 能用
cmd /c 'git --version > _tmp\pre.log 2>&1' ; Get-Content _tmp\pre.log

# ③ 磁盘余量（.git 预计 100~250 MB，留 2 GB 足够）
Get-PSDrive D | Select-Object @{n='FreeGB';e={[math]::Round($_.Free/1GB,1)}}
```

### 2.1 撞上 `0xC0000142` / `Access is denied` 怎么办

不是脚本错，是本机沙箱：**PowerShell 用管道抓子进程输出会被拒**（AGENTS §2.6）。
固定改法：**所有 git 命令一律 `cmd /c '... > 文件 2>&1'`，再用 `Get-Content` 读那个文件。**

```powershell
# 禁止
git status | Out-String

# 正确
cmd /c 'git status > _tmp\status.log 2>&1' ; Get-Content _tmp\status.log
```

> **引号规矩（照抄，别自创）**：PowerShell 侧用**单引号**包住整条 cmd 命令，cmd 内部用**双引号**。
> 不要写 `cmd /c "..."`，也不要在参数里出现中文文件名——全部用目录名或 `*.bat` / `*.md` 这类 glob。

---

## 3. 执行（7 步，每步都有"不通过怎么办"）

### 第 1 步 · 初始化

```powershell
cmd /c 'git init -b main > _tmp\init.log 2>&1'
cmd /c 'git config --local user.name RDR2GitBot >> _tmp\init.log 2>&1'
cmd /c 'git config --local user.email rdr2@local >> _tmp\init.log 2>&1'
cmd /c 'git config --local core.quotepath false >> _tmp\init.log 2>&1'
Get-Content _tmp\init.log
```

- 预期：`Initialized empty Git repository in ...`，无报错。
- 若 `-b main` 报 unknown option（老 git）：先 `git init`，再 `git symbolic-ref HEAD refs/heads/main`。
- **不要** `git config --global`（会污染用户全局配置）。

### 第 2 步 · 全量暂存（先摸清到底有多少东西）

```powershell
cmd /c 'git add -A > _tmp\add.log 2>&1'
Get-Content _tmp\add.log -Tail 20
```

- 预期：**无输出**，或只有少量 CRLF 警告。
- 可能耗时 1~5 分钟。**若 2 分钟没有任何输出**，起心跳，别干等：
  ```powershell
  while (Get-Process git -ErrorAction SilentlyContinue) { Start-Sleep 15; "[hb] {0}" -f (Get-Date -Format HH:mm:ss) }
  ```
- 出现 `warning: ... is a symbolic link` 且路径是 `export/levels/world/blender` 之类：**正常**（附录 B.4 已断开），不要动。

### 第 3 步 · 体积闸门（**这一步决定能不能提交**）

```powershell
cmd /c 'git -c core.quotepath=false ls-files > _tmp\files.txt 2>&1'
uv run python tools/git_size_report.py _tmp\files.txt > _tmp\size.log 2>&1
Get-Content _tmp\size.log
```

- 预期末行：`判定：PASS —— 可以提交（N 个文件 / X MB）`，退出码 0。
- **FAIL 就停手**，按 §5-A 处理，不许 commit。
- 再补一道二进制检查（输出必须为空）：

```powershell
Get-Content _tmp\files.txt | Select-String -Pattern '\.(blend|glb|gltf|bin|png|jpg|mdl)$' > _tmp\bad.txt
Get-Content _tmp\bad.txt
```
（这里用 PowerShell 读文件，不接子进程，安全。）

### 第 4 步 · 清索引，准备分三次提交

```powershell
cmd /c 'git rm -r --cached . > _tmp\unstage.log 2>&1'
Test-Path .gitignore     # 必须 True：这是"只清索引、不动文件"
```

### 第 5 步 · 三次提交（commit message 用英文，避免 cmd 936 代码页把中文踩成乱码）

```powershell
# ① 规则与文档（含根目录 5 篇 md + 3 个 .bat；用 glob 避开中文文件名）
cmd /c 'git add .gitignore .gitattributes docs *.md *.bat > _tmp\c1.log 2>&1'
cmd /c 'git commit -m "docs: baseline rules, AGENTS, TODO, handoff docs, launchers" >> _tmp\c1.log 2>&1'

# ② 代码
cmd /c 'git add tools > _tmp\c2.log 2>&1'
cmd /c 'git commit -m "tools: single build pipeline, rdr2 decoders, extractors, git size gate" >> _tmp\c2.log 2>&1'

# ③ 数据层（页面文本 + 账本 + 契约；git 自己会按 .gitignore 跳过 models/tex/二进制）
cmd /c 'git add export deliverable/handoff assets/lib_native raw > _tmp\c3.log 2>&1'
cmd /c 'git commit -m "data: viewer text layer, build ledgers, downstream contract" >> _tmp\c3.log 2>&1'

Get-Content _tmp\c1.log, _tmp\c2.log, _tmp\c3.log -Tail 5
cmd /c 'git log --oneline > _tmp\log.txt 2>&1' ; Get-Content _tmp\log.txt
```

- 预期：3 行 commit。
- 若 ① 报 `pathspec '*.md' did not match`：说明 `.gitignore` 顺序被改过 → 按 §5-C 停手。
- 若 ③ 报某些路径不存在：逐个确认 `export` / `deliverable/handoff` / `assets/lib_native` / `raw` 是否都在（都在就重跑；缺哪个就只 add 存在的）。

### 第 6 步 · 打 tag

```powershell
cmd /c 'git tag continent-v8 > _tmp\tag.log 2>&1'
cmd /c 'git tag -l > _tmp\tags.txt 2>&1' ; Get-Content _tmp\tags.txt
```

### 第 7 步 · 终检

```powershell
cmd /c 'git status --short > _tmp\status.log 2>&1' ; Get-Content _tmp\status.log
cmd /c 'git ls-files > _tmp\final.txt 2>&1'
"文件数 = " + (Get-Content _tmp\final.txt).Count
uv run python tools/git_size_report.py _tmp\final.txt > _tmp\size_final.log 2>&1
Get-Content _tmp\size_final.log -Tail 3
```

- `git status --short` 应为空。
- 文件数应在 350~700。

---

## 4. 判定阈值表

| 指标 | 期望 | 超出怎么办 |
|---|---|---|
| 文件数 | 350~700 | >1000 见 §5-B；<300 见 §5-C |
| 总量 | < 250 MB | 250~400 MB：报告最大的 10 个交用户定；>400 MB 直接 FAIL |
| 单文件 | < 50 MB | 见 §5-A |
| 二进制 | **0 个** | 见 §5-D |
| commit 数 | 3 | 多/少不用重来，如实报告 |
| 工作区改动 | 0 | 见 §5-E |

---

## 5. 异常决策树

**A. 闸门报某文件 >50 MB**
1. 先判断是不是"账本"（该留的：`export/world/continent/tiles/*.json`、`assets/lib_native/index*.json`、`export/levels/town/archetypes.json`、`export/story/conversation_index.json`）。
2. 是账本 → **不删、不改代码路径**，改走 LFS：
   ```powershell
   cmd /c 'git lfs install >> _tmp\lfs.log 2>&1'
   cmd /c 'git lfs track "export/levels/town/archetypes.json" >> _tmp\lfs.log 2>&1'
   ```
   **顺序很重要**：`track` 必须在文件被 `git add` 之前生效。所以做完这两条后，
   回到 §3 第 2 步重跑 `git add -A`，再跑第 3 步闸门（此时该文件应变成指针，自然过闸）。
   `.gitattributes` 的改动会落在第 5 步的 commit ① 里（这是**唯一**允许改 `.gitattributes` 的场景）。
3. 不是账本 → 只在 `.gitignore` **追加**一条排除，并在 `GIT_入库清单.md` §2 记一行。

**B. 文件数 >1000**（白名单漏了目录）——只用 PowerShell 统计，不要接子进程：
```powershell
Get-Content _tmp\files.txt | ForEach-Object { ($_ -split '/')[0] } |
  Group-Object | Sort-Object Count -Descending | Select-Object -First 10
```
把异常的顶层目录报出来，**不要自行决定排除**（可能是真数据）。

**C. 文件数 <300**：多半是 `.gitignore` 被改过（`!*/` 之前插了排除行会让 git 不下钻）。把 `.gitignore` 原文贴进报告，停手。

**D. 二进制混进来了**：不许 `git rm --cached` 一个个清。直接回滚（§9），把违规路径 + `git status` 一起报告——这说明 `.gitignore` 被改或用了 `git add -f`。

**E. 工作区非空**：`deliverable/blender/...manifest.json` 之类刚被构建改过是正常的；**不要** `git checkout` 覆盖，只报告文件名。

**F. `fatal: not a git repository`**：cwd 错。必须是 `D:\BrainMaker\大镖客2解包分析`。

**G. `Permission denied` / `0xC0000142`**：见 §2.1。

**H. 文件被占用（Blender 开着）**：关 Blender 重试；**不要**结束用户进程。

---

## 6. 绝对禁止（违反任一条 = 任务失败）

1. 禁 `git add -f` —— 白名单是安全边界，绕过它等于把 6.8 GB 塞进仓库。
2. 禁删除或改动 `.gitignore` 里已有的 `!` 放行行；只能追加排除。
3. 禁 `git reset --hard`、`git clean -fdx`、`git checkout -- .`。
4. 禁移动/重命名 `tools/`、`docs/`、`export/`、`assets/`（脚本里是绝对路径）。
5. 禁把任何 `.bat` 转成 UTF-8（GBK 是 cmd 的要求）。
6. 禁 `git push` / 加 remote / 配 global user。
7. 禁删 `raw/`、`assets/`、`deliverable/` 下任何文件。
8. 禁改 `AGENTS.md`、`docs/最高原则_单一管线与分块即裁剪.md`。
9. 禁在 `D:\BrainMaker`（上一级）执行 `git init`。
10. 禁把 `_tmp/` 或任何日志提交进去。
11. 禁 `git lfs`（除 §5-A 授权）。
12. 禁改 `tools/git_size_report.py` 的阈值。

---

## 7. 允许新增的文件（仅这几样）

| 文件 | 说明 |
|---|---|
| `.gitignore` | **已存在**，只许追加 |
| `.gitattributes` | **已存在**，只许在 LFS 场景追加 |
| `tools/git_size_report.py` | **已存在**，不许改阈值 |
| `docs/交接与状态/GIT_搬运_SOP.md` | 本文件 |
| `_tmp/`（临时） | 已 ignore，收尾可删 |

---

## 8. 回执模板（填好发给用户）

```markdown
## git 迁移结果

- 仓库路径：D:\BrainMaker\大镖客2解包分析\.git
- commit：3 个 / tag：continent-v8
  1. <hash> docs: ...
  2. <hash> tools: ...
  3. <hash> data: ...
- 文件数：N
- 总量：X MB
- 最大单文件：A MB（路径）
- 二进制检查：通过 / 发现 N 个（列路径）
- 闸门判定：PASS / FAIL（原因）
- 与预期不符的地方（没有就写"无"）：
- 遗留项：
```

---

## 9. 回滚

源文件全程未被修改，回滚 = 删元数据：

```powershell
cmd /c 'rmdir /s /q .git'
cmd /c 'rmdir /s /q _tmp'
```

（`.gitignore` / `.gitattributes` / 本 SOP / `tools/git_size_report.py` 是新增的，可留可删。）

---

## 附录 A · 如果用户要"独立一份仓库副本"

默认**不做**（两份文本必然漂移）。若用户明确要求，在方案 A 完成且闸门 PASS 之后：

```powershell
cmd /c 'git -c core.quotepath=false ls-files > _tmp\files.txt'
robocopy . D:\BrainMaker\rdr2-git /E /FROMFILE:_tmp\files.txt /NFL /NDL
```
再在副本里 `git init` 重跑 §3。**注意**：副本路径与脚本的绝对路径假设（`ROOT = D:/BrainMaker/大镖客2解包分析`）不一致，**只能当存档，不能当工作副本**。

---

## 附录 B · 为什么规则长这样（防止"顺手优化"）

1. **白名单（`*` + `!*.md`…）而非黑名单**：黑名单要穷举 90 GB 里所有二进制，漏一个就是灾难；白名单漏了只是少收一个文本。
2. **不搬家**：`blender_continent.py` 等把 `export/world/...`、`assets/lib_native/index.json` 写成常量路径，搬 = 运行时断链，错在运行期最难查。
3. **`.bat` 用 `-text`**：GBK 批处理被 git 做换行转换后，cmd 里中文 echo 会乱（AGENTS §4 踩过）。
4. **6 个目录联接必须断开**：`export/levels/world/blender → deliverable/blender`（9.4 GB）、`export/world/lib_native → assets/lib_native`（13 GB）、`export/levels/collision → raw/collision`（8 GB）、`export/levels/world/gltf → raw/gltf`、`export/models → raw/models`、`work → raw`。git 会顺着联接爬，`git add -A` 要么卡死要么误收（见 `STRUCTURE.md` §三）。
5. **JSON 不集中**：页面用相对路径 `fetch('data.json')`，构建脚本用绝对路径；集中 = 两处同时断。
6. **`names.txt` 必须进**：hash→资产名的唯一字典，没有它"铁路/贴图按名字绑定"全失效，连"从游戏恢复"这条路都断。
7. **`_tmp/` 单独放**：`.txt` 在白名单里，临时清单放根目录会被误提交。
8. **commit 用英文**：cmd 的 936 代码页会把中文踩成乱码，`git log` 从此不可读。
