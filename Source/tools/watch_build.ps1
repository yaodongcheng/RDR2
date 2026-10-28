# -*- coding: utf-8 -*-
<#
tools\watch_build.ps1 —— 长任务看门狗（不阻塞、每次几秒出结论）

为什么要它：用户担心"agent 在瞎等"。这个脚本把「有没有进展」变成硬指标：
    日志行数在涨？ 日志最后写入多久之前？ 进程还在吗？ 内存涨到哪了？

用法：
    .\tools\watch_build.ps1                       # 默认看 build_v6.log
    .\tools\watch_build.ps1 -Log D:\BrainMaker\build_tile.log -ProcessName blender
    .\tools\watch_build.ps1 -Mark                 # 只记基线，不判定

判定：RUNNING（近 180 s 有写入）/ STALLED（>180 s 无写入但进程还在）/ EXITED（进程没了）
退出码：0 RUNNING，1 STALLED，2 EXITED
#>
param(
  [string]$Log = 'D:\BrainMaker\build_v6.log',
  [string]$ProcessName = 'blender',
  [int]$StallSec = 180,
  [switch]$Mark
)

$stateDir = Join-Path $env:TEMP 'wk_watch'
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
$key = ($Log -replace '[\\/:*?"<>|]', '_')
$state = Join-Path $stateDir "$key.json"

$now = Get-Date
if (-not (Test-Path -LiteralPath $Log)) {
  "[watch] 日志还不存在：$Log"
  exit 2
}
$f = Get-Item -LiteralPath $Log
$lines = (Get-Content -LiteralPath $Log -ErrorAction SilentlyContinue | Measure-Object -Line).Lines
$tail = (Get-Content -LiteralPath $Log -Encoding UTF8 -Tail 1 -ErrorAction SilentlyContinue)
$idle = [int]($now - $f.LastWriteTime).TotalSeconds

$procs = @(Get-Process -Name $ProcessName -ErrorAction SilentlyContinue)
$alive = $procs.Count -gt 0
$mem = if ($alive) { [math]::Round((($procs | Measure-Object WorkingSet64 -Sum).Sum / 1GB), 2) } else { 0 }
# CPU 累计秒数：用来区分「卡在等 IO」和「在算但不出日志」
$cpu = if ($alive) { [int](($procs | Measure-Object CPU -Sum).Sum) } else { 0 }

$prev = $null
if (Test-Path -LiteralPath $state) {
  try { $prev = Get-Content -LiteralPath $state -Raw | ConvertFrom-Json } catch { $prev = $null }
}
$dLines = if ($prev) { $lines - [int]$prev.lines } else { 0 }
$dCpu = if ($prev) { $cpu - [int]$prev.cpu } else { 0 }
$dSec = if ($prev) { [int]($now - [datetime]$prev.at).TotalSeconds } else { 0 }

if ($Mark) {
  @{ lines = $lines; cpu = $cpu; at = $now.ToString('o') } |
    ConvertTo-Json | Set-Content -LiteralPath $state -Encoding UTF8
  "[watch] 基线已记：第 $lines 行，CPU 累计 ${cpu}s"
  exit 0
}

# 判定要能区分「在算但不出日志」（大模型/大贴图，CPU 在涨）和真卡死（CPU 也不动）
$verdict = if (-not $alive) { 'EXITED' }
           elseif ($idle -le $StallSec) { 'RUNNING' }
           elseif ($dCpu -ge 5) { 'BUSY' }
           else { 'STALLED' }
"[watch {0}] {1} | 第 {2} 行 (+{3} / {4}s) | 最后写入 {5}s 前 | {6} 内存 {7} GB, CPU 累计 {8}s (+{9})" -f `
  $now.ToString('HH:mm:ss'), $verdict, $lines, $dLines, $dSec, $idle, $ProcessName, $mem, $cpu, $dCpu
"[watch] 末行：$tail"

@{ lines = $lines; cpu = $cpu; at = $now.ToString('o') } |
  ConvertTo-Json | Set-Content -LiteralPath $state -Encoding UTF8

if ($verdict -eq 'EXITED') { exit 2 }
if ($verdict -eq 'STALLED') { exit 1 }
exit 0
