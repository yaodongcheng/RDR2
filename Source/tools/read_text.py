# -*- coding: utf-8 -*-
"""读任意编码的文本文件 —— 本仓库的 .bat / 早期文档是 **GBK(936)**，按 UTF-8 读会直接报
`invalid UTF-8 text`。凡是要看 .bat 或老文档，先用这个，别再用只会 UTF-8 的读取器。

为什么不直接把 .bat 转成 UTF-8：cmd 按系统 OEM 码页（936）解析批处理，文件里还写着
`chcp 936`，转码后 echo 出来的中文会变乱码 —— 所以保持 GBK，改读法。

用法：
    uv run python tools/read_text.py 打开大陆_流畅.bat
    uv run python tools/read_text.py 打开大陆_流畅.bat --lines 1:20
    uv run python tools/read_text.py README.md --head 40
    uv run python tools/read_text.py --scan             # 扫全仓：列出不是 UTF-8 的文本文件
    uv run python tools/read_text.py --scan --root docs
"""
import os
import sys
import glob
import argparse

ROOT = r'D:/BrainMaker/大镖客2解包分析'
# 依次尝试；latin1 是兜底（永不失败）
ENCODINGS = ('utf-8-sig', 'utf-8', 'gbk', 'big5', 'latin1')
TEXT_EXT = ('.bat', '.cmd', '.md', '.txt', '.ps1', '.py', '.json', '.csv', '.ini', '.cfg', '.log')
SKIP_DIRS = ('raw', 'export', 'work', 'assets', 'deliverable', 'archive', '录屏', '地图下载',
             '__pycache__', '.git', 'Mod')


def decode(data):
  for e in ENCODINGS:
    try:
      return data.decode(e), e
    except UnicodeDecodeError:
      continue
  return data.decode('utf-8', 'replace'), 'utf-8(replace)'


def looks_text(path, sniff=4096):
  with open(path, 'rb') as f:
    return b'\x00' not in f.read(sniff)


def read(path, a=None, b=None):
  raw = open(path, 'rb').read()
  text, enc = decode(raw)
  lines = text.splitlines()
  if a is not None or b is not None:
    s = max(1, a or 1)
    e = b if b else len(lines)
    lines = lines[s - 1:e]
    base = s
  else:
    base = 1
  print('# %s  [%s, %d 行]' % (path, enc, len(text.splitlines())))
  for i, ln in enumerate(lines, base):
    print('%5d  %s' % (i, ln))
  return enc


def scan(root):
  bad = []
  n = 0
  for p in glob.glob(os.path.join(root, '**', '*'), recursive=True):
    if not os.path.isfile(p):
      continue
    if os.path.splitext(p)[1].lower() not in TEXT_EXT:
      continue
    if any(seg in os.path.relpath(p, root).split(os.sep)[:-1] for seg in SKIP_DIRS):
      continue
    try:
      if os.path.getsize(p) > 20 * 1024 * 1024 or not looks_text(p):
        continue
    except OSError:
      continue
    n += 1
    try:
      open(p, 'rb').read().decode('utf-8')
    except UnicodeDecodeError:
      enc = decode(open(p, 'rb').read())[1]
      bad.append((os.path.relpath(p, root), enc))
  print('扫描文本文件 %d 个，非 UTF-8 的 %d 个：' % (n, len(bad)))
  for p, enc in bad:
    print('  %-60s %s' % (p, enc))
  return bad


def main(argv=None):
  ap = argparse.ArgumentParser()
  ap.add_argument('file', nargs='?', default='')
  ap.add_argument('--lines', default='')
  ap.add_argument('--head', type=int, default=0)
  ap.add_argument('--scan', action='store_true')
  ap.add_argument('--root', default=ROOT)
  a = ap.parse_args(argv)

  if a.scan:
    scan(a.root)
    return 0
  if not a.file:
    ap.print_help()
    return 1
  p = a.file if os.path.isabs(a.file) else os.path.join(ROOT, a.file)
  if not os.path.exists(p):
    raise SystemExit('找不到 %s' % p)
  lo = hi = None
  if a.lines:
    parts = a.lines.split(':')
    lo = int(parts[0]) if parts[0] else 1
    hi = int(parts[1]) if len(parts) > 1 and parts[1] else None
  if a.head:
    lo, hi = 1, a.head
  read(p, lo, hi)
  return 0


if __name__ == '__main__':
  sys.exit(main())
