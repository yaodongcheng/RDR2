# -*- coding: utf-8 -*-
"""git 入库体积闸门：读 `git ls-files` 的清单，判断这批文件能不能提交。

为什么不让脚本自己调 git：本机沙箱禁止用管道接子进程 stdout（AGENTS.md §2.6），
`subprocess.run(..., capture_output=True)` 会直接 EPERM。所以拆成两步：

    mkdir _tmp
    cmd /c "git -c core.quotepath=false ls-files > _tmp\files.txt"
    uv run python tools/git_size_report.py _tmp\files.txt

判定（退出码）：
    0 = PASS    可以提交
    1 = FAIL    有单文件 >50 MB，或总量 >400 MB —— 停下来报告，不许 commit
    2 = 用法错  清单文件不存在（多半是上一步没跑）

阈值含义：
    单文件  >10 MB  偏大，要确认是不是"账本"（是就留，不是就排掉）
    单文件  >50 MB  不许进 git（要么 LFS，要么改代码路径后移出）
    总量   >400 MB  说明白名单漏了东西
"""
import io
import os
import sys

MAX_ONE = 50 * 1024 * 1024
WARN_ONE = 10 * 1024 * 1024
MAX_TOTAL = 400 * 1024 * 1024


def mb(n):
    return n / 1024.0 / 1024.0


def read_paths(p):
    """git 在不同 Windows 环境下可能吐 utf-8 或 ANSI(936)，两种都试。"""
    for enc in ('utf-8', 'gbk'):
        try:
            with io.open(p, encoding=enc) as f:
                return [ln.rstrip('\r\n') for ln in f if ln.strip()]
        except UnicodeDecodeError:
            continue
    with io.open(p, encoding='utf-8', errors='replace') as f:
        return [ln.rstrip('\r\n') for ln in f if ln.strip()]


def main():
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join('_tmp', 'files.txt')
    if not os.path.isfile(p):
        print('[!] 清单不存在: %s' % p)
        print('    先跑: cmd /c "git -c core.quotepath=false ls-files > %s"' % p)
        return 2

    paths = [x for x in read_paths(p) if x]
    total = 0
    rows = []
    missing = []
    for rel in paths:
        if not os.path.isfile(rel):
            missing.append(rel)
            continue
        size = os.path.getsize(rel)
        total += size
        rows.append((size, rel))
    rows.sort(key=lambda t: -t[0])

    print('文件数 %d / 总计 %.1f MB' % (len(paths), mb(total)))
    if missing:
        print('\n[!] 读不到 %d 个（路径不存在或编码不对），前 5 个：' % len(missing))
        for m in missing[:5]:
            print('    %s' % m)

    print('\n最大的 20 个：')
    for size, rel in rows[:20]:
        flag = ''
        if size > MAX_ONE:
            flag = '   <== 超过 50 MB，必须处理'
        elif size > WARN_ONE:
            flag = '   <-- 偏大，确认是不是账本'
        print('%9.2f MB  %s%s' % (mb(size), rel, flag))

    over = [r for r in rows if r[0] > MAX_ONE]
    print('\n判定：', end='')
    if over:
        print('FAIL —— %d 个文件超过 50 MB（见上）' % len(over))
        return 1
    if total > MAX_TOTAL:
        print('FAIL —— 总量 %.1f MB 超过 400 MB，白名单可能漏了东西' % mb(total))
        return 1
    print('PASS —— 可以提交（%d 个文件 / %.1f MB）' % (len(paths), mb(total)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
