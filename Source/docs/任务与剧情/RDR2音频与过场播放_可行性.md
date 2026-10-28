# RDR2 语音与过场 CG：能不能在查看器里播？（实测结论）

> 回答用户两个问题：
> 1. 能不能在查看器里播**每一句对白的声音**？过场 CG 能不能播？
> 2. 如果必须启动游戏，暂停说话很难（只能 ESC），怎么办？
>
> 本文只写**实测**，每条都有命令/字节级证据。日期：2026-10-23

---

## 0. 一句话结论

| 诉求 | 结论 | 原因 |
|---|---|---|
| 过场 CG 在查看器播 | ❌ **当前不行** | 65 个 `.bk2` **全部是 Bink 2（`KB2j`）**，本机 ffmpeg 明确报 `Bink 2 video is not implemented`；Bink2 是闭源编解码，没有可用解码器 |
| 逐句对白音频 | ⚠️ **音频在，但是"整场一包"** | 每场戏一个 `*_MASTERED_ONLY.awc`（ADAT 容器 + 内嵌 Vorbis），**包里没有台词键**，要按句切必须先解 ADAT |
| 逐句说话人 | ⚠️ 同上 | 说话人只体现在**音轨**（每角色一套语音库）与演出编排里，静态文本无此字段 |
| 需要暂停游戏吗 | ✅ **不需要** | 正确做法是 hook 记录事件流，正常玩一遍即可，不用暂停 |

---

## 1. 过场 CG：Bink 2，无解（除非换解码器）

```bash
ls export/story/movies/movies/*.bk2 | wc -l      # 65
python -c "import glob,collections;print(collections.Counter(open(p,'rb').read(4) for p in glob.glob('export/story/movies/movies/*.bk2')))"
# Counter({b'KB2j': 65})

ffmpeg -i export/story/movies/movies/2secondsblack.bk2
# [in#0] Bink 2 video is not implemented
```

**可选出路**（按成本排序）：
1. **游戏内录屏**（OBS / Xbox Game Bar）——最省事，画质取决于设置；
2. **RAD Bink2 SDK**（官方免费给开发者，但需要授权与集成）——能离线转码；
3. 找现成 Bink2 解码器 —— 目前没有可靠开源实现，不建议投入。

> 注意：这 65 个是**片头/章节标题/回忆**这类预渲染 CG，**不是主线过场**。主线过场是实时演算（anim scene），本来就不能"播视频"。

---

## 2. 逐句对白音频：场景级音频已定位，按句切需要解 ADAT

### 2.1 找到了什么

`x64/audio/sfx/CUTSCENE_MASTERED_ONLY.rpf`（646 个条目，**640 个能反查出名字**）：

```
WNT1_INT_CABIN_MASTERED_ONLY.awc      16 692 288 B
WNT1_INT_WAGON_MASTERED_ONLY.awc
MRY1_INT_MASTERED_ONLY.awc
NTV2_EXT_MASTERED_ONLY.awc
...
```

命名规则：`<任务>_<场次>_MASTERED_ONLY.awc`，正好对应脚本里 `func_784(..., "WNT1_INT_CABIN", 18, -1)` 这种场次名。

### 2.2 包内结构（实测）

```
magic  : ADAT
version: 0x0001 / 0xff05...
streams: 头部第 3 个 u32 = 0x82 (130?)；文件内 vorbis 头 18 处
codec  : Xiph.Org libVorbis I 20150105（每个流是独立 vorbis 流）
字符串 : 无任何台词键（WNT1_INT_CABIN / BANT / ARTHUR 计数均为 0）
```

- ✅ 音频确实在，而且**每场戏一包**，音质是母带级；
- ❌ 包里**没有"哪句对应哪个流"的名称表**，流是按顺序排的 Vorbis；
- ⚠️ 要"按句播"，需要：解 ADAT → 拆出每个 Vorbis 流 → 重新封装成 Ogg/Opus → 再按行序对齐。

> 这条路技术上可行（RAGE AWC 有公开格式描述），但本机没有 vgmstream/ww2ogg 之类现成工具，
> 需要自己写 ADAT 解析 + Ogg 封装（约 1~2 天工作量），而且**只能按"行序"对齐**，无法保证一句一包。

### 2.3 更快的替代：直接录游戏

既然音频是"整场一包"，那么**录一遍游戏里的这场戏**和"解包再切"信息量一样，但零风险：
- 录制：OBS 录系统声音（或游戏内 5.1 下混立体声）；
- 切句：用下面第 3 节的**时间戳日志**自动切片（`apply_speaker_log.py --audio`）。

---

## 2.4 已经做好的「无插件」方案：录一段，自动切句

不需要装 ScriptHook、也不需要暂停游戏：

```bash
# 1) 你用 OBS 录一段对话（一个对话组一段最好），得到 rec.wav / rec.mp4
# 2) 切句 + 按台词顺序命名
uv run python tools/split_capture_audio.py raw/capture/rec.wav --group WNT1_BANT
#    切出 6 段、对话组 6 句 -> 自动写成 export/story/audio/WNT1_BANT_1..6.wav
# 3) 重建查看器
uv run python tools/build_story_viewer.py
```

效果：剧本页每句台词后面出现播放器（已用合成音频验证：4 句 → 4 个播放器）。
段数不等时脚本会提示；确认录音只含这一段后加 `--force` 强配。

> 实测：VAD 用「自适应能量阈值 + 合并短停顿」，合成三段音（0.8s/0.9s/0.7s + 0.6/0.7s 静音）
> 切出 3 段、边界误差 < 0.1s。

---

## 2.45 ★ 更正：截图/录屏**可以**用——因为字幕自带说话人

用户提供的实测录屏（`录屏/第5秒约翰说 继续努力,不是吗.mp4`）帧里，画面下方字幕是：

```
约翰：继续努力，不是吗？
```

也就是说 **RDR2 的字幕本身就带说话人前缀**（至少 stranger/随机对话是这样）。
之前判断"截图没用"是错的——**截图能拿到说话人**，只是要靠逐句截帧 + 读字幕。

已落地的两个工具：

| 工具 | 作用 |
|---|---|
| `tools/extract_subtitle_frames.py` | 对录屏做 VAD，按每句话截一帧（默认只裁画面下方 30% 的字幕区），输出 `manifest.csv` |
| `tools/apply_frame_manifest.py` | 把填好的 `speaker,text` 对回 beat 表 → 写 `speaker_overrides.json` + 按时间切音频 |

实测（该录屏 19.2s）：VAD 切出 7 段，但**只有 1 段是台词**（其余是环境音/音乐），
截图读出 `约翰 / 继续努力，不是吗？`；这句属于陌生人任务，不在已解的 133 个任务里，所以匹配不到剧本。
**若录的是主线对话，就能自动对上并回填说话人。**

> 结论：要说话人，**录屏（字幕开着）+ 逐句截帧** 就够，不需要插件、不需要拆 AWC。

---

## 2.5 一键流程（不用插件、不用暂停）

1. 双击根目录 **`开始录音分析.bat`**（盯着 `raw/capture/`）
2. 进游戏，OBS 录一段对话，停止录制（文件自动落到 `raw/capture/`）
3. 脚本自动：解码 → VAD 切句 → 在该任务的对白组里挑最匹配的一组 → 写 `export/story/audio/<组>_<n>.wav` → 重建查看器

匹配依据：**段数 ≈ 句数 + 总时长 ≈ 句数×2.6s + 每句时长与台词字数的相关性**。
置信度不够时落到 `raw/capture/pending/<文件名>/`，`_report.json` 会列出候选组，人工改名即可。

> 实测：合成 4 段音（时长按 WNT2_HELPJAVIER 的真实字数比例）→ 自动判为
> `WNT2_HELPJAVIER`（score 0.97）vs `WNT2_RIDEBACK4`（1.06），差 0.09 → 标为 low-confidence 并落 pending。
> 真实语音里相关性更明显，区分度会更高。

---

## 3. 不需要暂停：hook 记录事件流

用户担心"说话不好暂停，只能 ESC"——**根本不需要暂停**。

### 3.1 要记的东西

每句开始播时记一行：`t_ms, ped, line_key`，例如

```csv
t_ms,ped,line_key
12345,cs_dutch_ms1,WNT1_BANT_1
13980,player_zero,WNT1_BANT_2
```

- `line_key`：脚本里本来就有（`GET_CURRENT_SCRIPTED_CONVERSATION_LINE("WNT1_BANT")` 就能拿到当前句序号）；
- `ped`：播这句的实体，hook 在 `AUDIO::PLAY_*_SPEECH` / scripted conversation 相关 native 上取；
- 正常玩，不用暂停、不用重玩——日志只是旁路记录。

### 3.2 拿到日志之后（已实现）

```bash
uv run python tools/apply_speaker_log.py raw/capture/wnt1.csv
# -> export/story/speaker_overrides.json   （自动并进查看器，逐句显示说话人）
# -> export/story/capture_segments.csv     （起始/结束 ms + 台词键，用于切音频）

# 如果同时录了整段音频：
uv run python tools/apply_speaker_log.py raw/capture/wnt1.csv --audio raw/capture/wnt1.wav
# -> export/story/audio/<组>_<序号>.wav    （按日志时间戳切片，一句一个文件）
```

查看器已支持：只要 `export/story/audio/<组>_<n>.wav` 存在，就会在对应台词旁出现播放按钮（逐步接入）。

---

## 4. 建议的执行顺序

| 步骤 | 做什么 | 产出 | 成本 |
|---|---|---|---|
| 1 | 用 OBS 录一段任务（如 WNT1 的营地对话） | 一段 wav/mp4 | 10 分钟 |
| 2 | 用 ScriptHook 插件记录 `t_ms,ped,line_key` | 一个 csv | 需装 ScriptHook + 插件（一次） |
| 3 | `apply_speaker_log.py --audio` | 逐句音频 + 说话人 | 1 分钟 |
| 4 | 回填查看器 | 剧本页每句都能听、都能看到是谁说的 | 自动 |

> 若不想装 ScriptHook：也可以**手动**按 `line_key,ped` 两列填 CSV（比如边看录像边听），
> 一个任务的对话通常 50~200 句，熟手 20 分钟能填完。

---

## 5. 复现命令

```bash
# 列出 CG 的编码（全部 KB2j）
python -c "import glob,collections;print(collections.Counter(open(p,'rb').read(4) for p in glob.glob('export/story/movies/movies/*.bk2')))"

# 反查 CUTSCENE_MASTERED_ONLY 里的场次音频名
cd tools/rdr2rpf/bin/Release/net9.0
./rdr2rpf.exe list "H:/EPICGAMES/RedDeadRedemption2/x64/audio/sfx/CUTSCENE_MASTERED_ONLY.rpf" | head

# 合并采集日志
uv run python tools/apply_speaker_log.py <log.csv> [--audio <rec.wav>]
```
