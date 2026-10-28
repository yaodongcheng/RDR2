# rdr2rpf — RDR2 (RPF8) 命令行提取器

本工具从《荒野大镖客 2》(RDR2 PC) 的 RAGE 封包 `.rpf`（RPF8）中列出/提取文件，
支持 TFIT2 加密目录表解密、Oodle/Deflate 解压、RSC8 资源重建、嵌套 rpf 下钻。

## 构建

需要 .NET 9 SDK（本机 `C:\Program Files\dotnet`）：

```bash
cd tools/rdr2rpf
dotnet build -c Release
# 产物: bin/Release/net9.0/rdr2rpf.exe（同目录已含 oo2core_5_win64.dll 与 names.txt）
```

## 用法

```bash
rdr2rpf list    <archive.rpf>                 # 列条目（大小/压缩/资源标记/名称）
rdr2rpf find    <archive.rpf> [关键词]        # 按名称过滤
rdr2rpf tree    <archive.rpf>                 # 按扩展名归类统计
rdr2rpf rawdec  <archive.rpf>                 # 诊断：打印头部字段 + 前 12 条 TOC 条目
rdr2rpf extract <archive.rpf> <outdir> [关键词] [--recurse]
```

- `--recurse`：遇到嵌套 `.rpf` 时自动解开并继续下钻（游戏动画/关卡大量为嵌套 rpf）。
- `关键词` 为空的字符串 `""` 表示提取全部条目。

## 依赖的文件（须与 exe 同目录）

| 文件 | 作用 |
|---|---|
| `oo2core_5_win64.dll` | Oodle 解压（游戏自带，或参考仓库自带） |
| `names.txt` | 30 万条 hash→资源名映射（JOAAT 反查） |

## 源码构成 (`src/`)

自 `lazenes/RPF8_TOOL`、`amrshaheen61/RDR2-RPF-Tool`（RDR2 RPF8 参考实现）精简而来：

- `RPF8.cs`（头部/TOC/条目结构与 GetFile）
- `Tfit2CbcCipher.cs` / `TfitCbcCipher.cs` / `Cipher.cs` / `StridedCipher.cs`（TFIT 密码族）
- `KeysContainer.cs`（PC 密钥表 + TFIT2 context + IV）
- `Compression.cs`（Oodle/Deflate）、`RSC8.cs`（资源头）、`RPFHelper.cs`(扩展名/名称)、`JOAATHash.cs`
- `Helper/`（FStream/MStream/IStream）
- `NamesContainer.cs`（本项目替换：从 names.txt 装载 hash→名）

> 说明：`FStream` 中原有的 `FileSecurity` 7 参构造在 .NET 9 已移除，已删除该未用构造函数。
