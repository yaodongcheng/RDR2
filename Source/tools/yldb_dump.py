"""RDR2 本地化 `.yldb` → 可读文本。

实测（2026-10-17）：`.yldb` 是 **RSC8 资源**（魔数 `0x38435352`），
资源体内紧跟文件头之后是**连续的 UTF-8 字符串表**（中文台词**完全明文**，未加密/未压缩）。
台词带 RDR2 富文本标记：`~z~` 起始、`~n~` 换行、`~sl:a:b~` 时间轴、`~INPUT_XXX~` 按键提示。

用法:
  uv run python tools/yldb_dump.py --dir <目录> --out <输出.txt> [--lang 中文标签]
"""
import os
import re
import sys
import argparse

RSC8 = 0x38435352

# UTF-8 字符合法范围（含 CJK）
_UTF8_RX = re.compile(
    rb'(?:[\x20-\x7e]|[\xc2-\xdf][\x80-\xbf]|'
    rb'[\xe0-\xef][\x80-\xbf]{2}|[\xf0-\xf4][\x80-\xbf]{3}){2,}')


def strings_of(path):
    data = open(path, 'rb').read()
    body = data[16:] if (len(data) > 16 and int.from_bytes(data[:4], 'little') == RSC8) else data
    out = []
    for m in _UTF8_RX.finditer(body):
        s = m.group(0)
        try:
            t = s.decode('utf-8')
        except UnicodeDecodeError:
            continue
        if len(t.strip()) < 2:
            continue
        out.append((m.start(), t))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--label', default='')
    a = ap.parse_args()

    files = sorted(os.path.join(a.dir, f) for f in os.listdir(a.dir)
                   if f.lower().endswith('.yldb'))
    total = 0
    cjk = 0
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as fh:
        fh.write('# RDR2 本地化对白导出（.yldb → UTF-8 文本）\n')
        fh.write('# 源目录: %s\n# 文件数: %d\n' % (a.dir, len(files)))
        fh.write('# 格式: <文件名>\\t<偏移(hex)>\\t<原文>\n')
        fh.write('# 注意: 原文含 RDR2 富文本标记 ~z~ ~n~ ~sl:a:b~ ~INPUT_XXX~，不是错误\n')
        fh.write('#' + '=' * 76 + '\n')
        for p in files:
            nm = os.path.basename(p)
            rows = strings_of(p)
            if not rows:
                continue
            fh.write('\n### %s  (%d 条)\n' % (nm, len(rows)))
            for off, t in rows:
                total += 1
                if any('\u4e00' <= ch <= '\u9fff' for ch in t):
                    cjk += 1
                fh.write('%s\t%08x\t%s\n' % (nm, off, t.replace('\t', ' ')))
    print('文件 %d 个，字符串 %d 条（含中文 %d 条）-> %s' % (len(files), total, cjk, a.out))


if __name__ == '__main__':
    main()
