# -*- coding: utf-8 -*-
"""bat 交付前检查：静态规则 + 干跑（不启动真程序）。

    python tools/_check_bat.py --bat "D:\\BrainMaker\\大镖客2解包分析\\打开大陆_流畅.bat" --dryrun

静态检查（这次实际踩过的坑）：
  · 编码必须 GBK、换行必须 CRLF（裸 LF = 0）
  · echo 行里 `<` `>` `|` `&` 必须转义成 ^< ^> ^| ^&（`<路径>` 会触发重定向、直接中止批处理）
  · `%~f0` / `%~dp0` 必须加引号（路径含 `Mount & Blade` 的 & 会裂行）
  · `for /f` 里的 dir 用 `2^>nul`；普通 dir 行用 `2>nul`
  · 每个 exit 前 3 行必须有 pause（否则双击窗口直接关）
干跑：把 `start ""...` 换成 echo、`pause` 换成 echo，再用 cmd /c 带参数跑，
      确认能解析到目标文件、错误分支有提示、不会中途语法错。
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

ROOT = r'D:/BrainMaker/大镖客2解包分析'


def static(path):
    b = open(path, 'rb').read()
    issues = []
    try:
        s = b.decode('gbk')
    except Exception as e:
        return ['GBK 解码失败: %s' % e]
    if b.count(b'\n') != b.count(b'\r\n'):
        issues.append('存在裸 LF（必须 CRLF）')
    lines = s.splitlines()
    for i, raw in enumerate(lines, 1):
        l = raw.strip()
        low = l.lower()
        if low.startswith('echo'):
            t = l[4:].replace('^<', '').replace('^>', '').replace('^|', '').replace('^&', '')
            # 管道右侧是命令（如 echo %ARG%| findstr ...），不是回显文本
            if '|' in t:
                t = t.split('|', 1)[0]
            # 去掉末尾重定向（>nul / 2>nul）
            t = re.sub(r'\s*(?:2>|>)\s*\S+\s*$', '', t)
            for ch in '<>|&':
                if ch in t:
                    issues.append('L%d: echo 里有未转义的 %r：%s' % (i, ch, l[:70]))
        if ('%~f0' in l or '%~dp0' in l) and not re.search(r'"[^"]*(%~f0|%~dp0)', l):
            issues.append('L%d: %%~f0/%%~dp0 未加引号（含 & 的路径会裂行）' % i)
        if low.startswith('for /f') and 'dir ' in l and '2^>nul' not in l:
            issues.append('L%d: for /f 里的 dir 缺少 2^>nul' % i)
        if low.startswith('dir /') and '2^>nul' in l:
            issues.append('L%d: 普通 dir 行应写 2>nul（不是 2^>nul）' % i)
    for i, l in enumerate(lines):
        if l.strip().lower().startswith('exit'):
            seg = [x.strip().lower() for x in lines[max(0, i - 3):i]]
            if not any(x.startswith('pause') for x in seg):
                issues.append('L%d: exit 前没有 pause（窗口会直接关）' % (i + 1))
    return issues


def dryrun(path, cases):
    s = open(path, 'rb').read().decode('gbk')
    lines = []
    for l in s.splitlines():
        st = l.strip().lower()
        if l.startswith('start ""'):
            lines.append('echo [DRYRUN] WOULD OPEN "%BLEND%"')
        elif st in ('pause', 'pause >nul'):
            lines.append('echo [DRYRUN] PAUSED')
        else:
            lines.append(l)
    tmp = os.path.join(tempfile.gettempdir(), 'lwn_dryrun_launcher.bat')
    open(tmp, 'wb').write(('\r\n'.join(lines) + '\r\n').encode('gbk'))
    out = {}
    for c in cases:
        p = subprocess.run(['cmd', '/c', tmp] + c, capture_output=True, timeout=60)
        out[' '.join(c) or '(none)'] = (p.stdout + p.stderr).decode('gbk', errors='replace')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bat', required=True)
    ap.add_argument('--dryrun', action='store_true')
    a = ap.parse_args()
    issues = static(a.bat)
    print('[bat] 静态检查：', 'PASS' if not issues else 'FAIL')
    for x in issues:
        print('   ', x)
    bad = bool(issues)
    if a.dryrun:
        cases = [['list'], ['19'], ['99']]
        outs = dryrun(a.bat, cases)
        for k, v in outs.items():
            print('\n[bat] dryrun %s:' % k)
            print(v.strip()[:1200])
        ok_list = '[审计分块]' in outs['list']
        ok_19 = ('[DRYRUN] WOULD OPEN' in outs['19']) or ('[ERROR]' in outs['19'])
        ok_99 = ('[ERROR]' in outs['99'])
        print('\n[bat] 干跑判定：list=%s  19=%s  99=%s' % (ok_list, ok_19, ok_99))
        bad = bad or not (ok_list and ok_19 and ok_99)
    print('\n[bat] 结论：', 'FAIL' if bad else 'PASS')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
