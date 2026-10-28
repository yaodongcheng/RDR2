#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
git_assets.py — 把「资源」（二进制大件）存到 GitHub 上当网盘（只留最新一份）

背景
    主分支 main 只进文本。资源 = SceneObj 下的 *.bin（地形本体 terrain.bin、植被表 flora.bin）
    与 AssetPackages 下编出来的 *.tpac —— 都被 .gitignore 挡在主分支外。
    它们的源不在任何 git 仓库里（地形要在 ModKit 里手动 Import，包由 ModKit Publish），
    所以本机这一份就是唯一一份。本脚本把它存进本仓库的一条 assets 分支，
    换电脑能拿回来，不用另开仓库、不用装别的工具。

怎么做到「不留历史」
    assets 分支永远只有一个提交，每次上传都整个重建再强推（不是往上面加一行），
    所以远程永远只有最新那一份，仓库不会越滚越大。
    主分支 main 完全不动 —— 工具全程不切分支、不 checkout，只造对象。

用哪些文件
    见下面 SOURCE_RULES：按「目录 + 通配」抓，按**仓库内相对路径**存进快照
    （SceneObj/Main_map/terrain.bin 存回去还是这个位置，不会被拉平成一个文件名）。

用法
    python git_assets.py            看两边一不一样（默认动作，只看不动）
    python git_assets.py status     同上
    python git_assets.py check      只报结论，给 GUI 判断按钮亮不亮（比 status 省流量）
    python git_assets.py save       上传（内容跟上次一样就什么都不做）
    python git_assets.py load       下载，覆盖本地
    python git_assets.py save --yes 远程那份你没见过时，别问，直接覆盖
    python git_assets.py load --yes 本地这份改过时，别问，直接覆盖

退出码
    0 = 正常 / 内容没变      1 = 出错      3 = 需要你确认（加 --yes 再跑一次）
    check 专用：0 = 两边一样   4 = 两边不一样   5 = 远程还没有快照

铁律
    .bak 备份文件绝不上传：名字里带 bak 的一律跳过。
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────────────────
GIT = "git"
BRANCH = "assets"
REF = f"refs/heads/{BRANCH}"
REMOTE_REF = f"refs/remotes/origin/{BRANCH}"
MAIN_BRANCH = "main"
MANIFEST_NAME = "_manifest.json"
MANIFEST_PATH = MANIFEST_NAME
NET_TIMEOUT = 300          # 联网命令（fetch/push/ls-remote）最多等多久，秒
CHUNK = 1024 * 1024

# ── 哪些文件算「资源」 ────────────────────────────────────────────────
#   (仓库内目录, 通配) —— 按**相对路径**入库，所以还原时原样回到同一个位置。
#   要加东西就往这张表加一行；不在表里的文件不会被上传。
SOURCE_RULES = [
    ("SceneObj", "**/*.bin"),        # 地形本体 / 植被表（每个场景各一份）
    ("AssetPackages", "*.tpac"),     # ModKit Publish 出来的包
]

# 路径里出现这些**目录名**就跳过（不是资源，或是别的资源的副本）：
#   Backups      —— ModKit 保存前的自动备份（里面又有一份 47 MB 的 terrain.bin）
#   ShaderCache  —— 着色器编译缓存（D3D11 产物，与显卡/驱动绑定，跨机器无意义）
EXCLUDE_DIRS = {"Backups", "ShaderCache"}


class GitError(Exception):
    """git 命令失败，或者环境不对 —— 一律友好报错、不吐栈。"""


# ── 基础工具 ──────────────────────────────────────────────────────────

def out(msg=""):
    print(msg)


def setup_console():
    """Windows 下重定向/管道时中文会乱码，强制 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def find_repo():
    """脚本自己就在仓库根，但用 git 问一次更稳。"""
    here = Path(__file__).resolve().parent
    p = subprocess.run([GIT, "-C", str(here), "rev-parse", "--show-toplevel"],
                       capture_output=True)
    if p.returncode != 0:
        raise GitError(f"这个目录不是 git 仓库：{here}")
    return Path(p.stdout.decode("utf-8", errors="replace").strip())


REPO = find_repo()


def rel(p):
    """绝对路径 → 仓库内相对路径（正斜杠，跨平台一致）。"""
    return Path(p).resolve().relative_to(REPO).as_posix()


def _base_cmd():
    # gc.auto=0 / maintenance.auto=false：不许 git 中途自己触发全仓重打包（会突然卡几分钟）
    return [GIT, "-c", "gc.auto=0", "-c", "maintenance.auto=false", "-C", str(REPO)]


def _run(args, *, as_bytes, env_extra=None, timeout=None, stdin=None):
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"      # 不许在终端里等输入（GUI 里会卡死）
    if env_extra:
        env.update(env_extra)
    try:
        p = subprocess.run(_base_cmd() + list(args), capture_output=True,
                           env=env, timeout=timeout, input=stdin)
    except subprocess.TimeoutExpired:
        raise GitError(f"git {args[0]} 等了 {timeout} 秒没反应，先检查网络")
    except FileNotFoundError:
        raise GitError("找不到 git，确认它在 PATH 里")
    err = p.stderr.decode("utf-8", errors="replace").strip()
    if as_bytes:
        return p.returncode, p.stdout, err
    return p.returncode, p.stdout.decode("utf-8", errors="replace"), err


def git(args, *, env_extra=None, timeout=None, stdin=None):
    """跑 git，失败就抛。返回 stdout（文本）。"""
    rc, o, e = _run(args, as_bytes=False, env_extra=env_extra, timeout=timeout, stdin=stdin)
    if rc != 0:
        raise GitError(e or f"git {' '.join(args)} 失败（退出码 {rc}）")
    return o


def git_bytes(args, *, env_extra=None):
    rc, o, e = _run(args, as_bytes=True, env_extra=env_extra)
    if rc != 0:
        raise GitError(e or f"git {' '.join(args)} 失败（退出码 {rc}）")
    return o


def git_ok(args, **kw):
    """跑 git，只关心成不成功（不抛）。"""
    rc, _, _ = _run(args, as_bytes=False, **kw)
    return rc == 0


# ── 文件与摘要 ────────────────────────────────────────────────────────

def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def md5_bytes(data):
    return hashlib.md5(data).hexdigest()


def is_excluded(relpath):
    """相对路径里有任何一段是 EXCLUDE_DIRS 里的目录名 → 不是资源。"""
    return any(part in EXCLUDE_DIRS for part in relpath.split("/")[:-1])


def list_assets():
    """本地要上传的资源 → [Path]（绝对路径，按相对路径排序、去重）。

    🔴 只认 SOURCE_RULES 里列的组合；名字里带 bak、或落在 EXCLUDE_DIRS 下的，一律不要。
    """
    seen = {}
    for sub, pattern in SOURCE_RULES:
        d = REPO / sub
        if not d.is_dir():
            continue
        for p in d.glob(pattern):
            if not p.is_file():
                continue
            if "bak" in p.name.lower():        # 备份：绝不上传
                continue
            r = rel(p)
            if is_excluded(r):                 # 自动备份 / 着色器缓存
                continue
            seen[r] = p
    return [seen[k] for k in sorted(seen)]


def scan_local():
    """→ {相对路径: {"md5":…, "bytes":…}}"""
    result = {}
    for p in list_assets():
        result[rel(p)] = {"md5": md5_file(p), "bytes": p.stat().st_size}
    return result


def fmt_size(n):
    if n >= 1024 * 1024:
        return f"{n / 1048576:.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n} B"


def fmt_map(files):
    """{名: {md5,bytes}} → md5 映射，用来比「内容一不一样」。"""
    return {name: info.get("md5") for name, info in (files or {}).items()}


# ── 远程读写 ──────────────────────────────────────────────────────────

def ls_remote():
    """→ (远程有没有这条分支, 它的 sha)。网络/认证失败直接抛，不跟「没分支」混为一谈。"""
    rc, o, e = _run(["ls-remote", "origin", REF], as_bytes=False, timeout=NET_TIMEOUT)
    if rc != 0:
        raise GitError(f"连不上远程（或认证过期）：{e or '未知原因'}")
    o = o.strip()
    if not o:
        return False, ""
    return True, o.split()[0]


def fetch_snapshot():
    # 远程这条分支每次都是重写的，必须加 `+` 才允许非快进更新
    git(["fetch", "origin", f"+{REF}:{REMOTE_REF}"], timeout=NET_TIMEOUT)


def ref_sha(ref):
    rc, o, _ = _run(["show-ref", "--verify", "--hash", ref], as_bytes=False)
    return o.strip() if rc == 0 and o.strip() else None


def read_manifest(rev):
    """读出某个提交里的清单；没有就返回 None。"""
    if not ref_sha(rev):
        return None
    if not git_ok(["cat-file", "-e", f"{rev}:{MANIFEST_PATH}"]):
        return None
    try:
        return json.loads(git_bytes(["cat-file", "blob", f"{rev}:{MANIFEST_PATH}"])
                          .decode("utf-8"))
    except (GitError, ValueError, UnicodeDecodeError):
        return None


def guard_head():
    """万一用户正站在 assets 分支上，赶紧停 —— 不然工作区会看起来一团乱。"""
    rc, o, _ = _run(["symbolic-ref", "-q", "HEAD"], as_bytes=False)
    if rc == 0 and o.strip() == REF:
        raise GitError(f"当前正站在 {BRANCH} 分支上，先切回 {MAIN_BRANCH} 再跑这个工具")


# ── 上传 ──────────────────────────────────────────────────────────────

def build_manifest(local):
    return {
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "files": local,
    }


def make_commit(files, manifest):
    """造一个「无父提交」—— 这就是「永远只有一个提交」的来源。

    全程用临时索引，不碰主索引、不碰工作区（碰主索引会把用户暂存的东西清掉）。
    🔴 路径用**仓库内相对路径**，资源回来时才回得到原位置。
    """
    idx_dir = tempfile.mkdtemp(prefix="rdr2_assets_")
    env = {"GIT_INDEX_FILE": os.path.join(idx_dir, "index")}   # 必须是绝对路径
    try:
        git(["read-tree", "--empty"], env_extra=env)

        for p in files:
            # --no-filters：绕开 autocrlf / .gitattributes 之类的内容改写
            sha = git(["hash-object", "-w", "--no-filters", "--", str(p)]).strip()
            git(["update-index", "--add", "--cacheinfo", "100644", sha, rel(p)],
                env_extra=env)

        blob = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        sha = git(["hash-object", "-w", "--no-filters", "--stdin"], stdin=blob).strip()
        git(["update-index", "--add", "--cacheinfo", "100644", sha, MANIFEST_PATH],
            env_extra=env)

        tree = git(["write-tree"], env_extra=env).strip()

        # 自查：写出来的树里，文件必须正好是我们想要的那几个（防临时索引残留出幽灵文件）
        got = {line for line in git(["ls-tree", "-r", "--name-only", tree]).splitlines() if line}
        want = {rel(p) for p in files} | {MANIFEST_PATH}
        if got != want:
            raise GitError(f"快照内容对不上，已中止。多出来：{sorted(got - want)}；"
                           f"少了：{sorted(want - got)}")

        msg = f"assets snapshot {manifest['saved_at']} ({len(files)} files)"
        return git(["-c", "commit.gpgsign=false", "commit-tree", tree, "-m", msg]).strip()
    finally:
        shutil.rmtree(idx_dir, ignore_errors=True)


def cleanup_loose():
    """把被替换掉的旧快照从本地 .git 里清掉（远程不受影响）。

    只动我们自己这条分支的 reflog，绝不用 --all（那会把用户别的分支的找回线索一起抹了）。
    也绝不用 gc --prune=now（大仓库要全量重打包，几分钟起步）。
    """
    if (REPO / ".git" / "index.lock").exists():
        return                                    # 用户正在别处操作 git，这次先不清
    git_ok(["reflog", "expire", "--expire=now", "--expire-unreachable=now", REF])
    git_ok(["prune", "--expire=now"])


def cmd_save(yes):
    guard_head()
    files = list_assets()
    if not files:
        raise GitError("没有可上传的资源（SceneObj 下没有 *.bin，AssetPackages 下没有 *.tpac）")

    local = scan_local()
    exists, remote_sha = ls_remote()

    remote_files = {}
    if exists:
        fetch_snapshot()
        m = read_manifest(REMOTE_REF)
        remote_files = (m or {}).get("files") or {}

    # ① md5 闸门：内容没变就一个字节都不传
    if exists and fmt_map(remote_files) == fmt_map(local):
        if ref_sha(REF) != remote_sha:
            git(["update-ref", REF, remote_sha])
        out(f"内容跟远程快照一模一样（{len(local)} 个文件），不用上传。")
        return 0

    # ② 冲突闸门：远程那份我没见过（另一台设备推过）→ 停下问
    my_last = ref_sha(REF)
    if exists and my_last != remote_sha and not yes:
        m = read_manifest(REMOTE_REF) or {}
        out("⚠️  远程快照不是你这台机器上次见到的那一份 —— 可能是另一台设备推过。")
        out()
        out(f"远程那份：保存于 {m.get('saved_at', '未知时间')}，共 {len(remote_files)} 个文件")
        for name, info in sorted(remote_files.items()):
            out(f"    {name}  {fmt_size(info.get('bytes', 0))}  {str(info.get('md5'))[:12]}")
        out(f"本地这份：共 {len(local)} 个文件")
        for name, info in sorted(local.items()):
            out(f"    {name}  {fmt_size(info.get('bytes', 0))}  {str(info.get('md5'))[:12]}")
        out()
        out("现在上传 = 把远程那份覆盖掉，且找不回来。")
        out("确认要覆盖，就加 --yes 再跑一次：python git_assets.py save --yes")
        return 3

    # ③ 造提交 → 强推 → 对齐本地 ref
    manifest = build_manifest(local)
    commit = make_commit(files, manifest)

    # 租约（force-with-lease）而不是裸 --force：万一这会儿别人推了，git 会拒，不会闷头覆盖
    lease = f"--force-with-lease={REF}:{remote_sha if exists else ''}"
    rc, _, err = _run(["push", "--porcelain", "origin", lease, f"{commit}:{REF}"],
                      as_bytes=False, timeout=NET_TIMEOUT)
    if rc != 0:
        if "stale info" in err:
            raise GitError("刚才有人先推了一步，远程已经变了。重新跑一次就能看到新内容。")
        raise GitError(f"推送失败：{err or '未知原因'}")

    git(["update-ref", REF, commit])          # 推成功了才更新本地记录
    cleanup_loose()

    total = sum(i["bytes"] for i in local.values())
    out(f"✅ 已上传 {len(local)} 个资源（{fmt_size(total)}）到远程 {BRANCH} 分支。")
    for name, info in sorted(local.items()):
        out(f"    {name}  {fmt_size(info['bytes'])}  {info['md5'][:12]}")
    return 0


# ── 下载 ──────────────────────────────────────────────────────────────

def write_atomic(target, data):
    """先写同目录临时文件 → 落盘 → 换名。绝不先删原件再写。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / f".{target.name}.tmp{os.getpid()}"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(3):
            try:
                os.replace(tmp, target)
                return
            except PermissionError:
                if attempt == 2:
                    raise GitError(f"写不进去：{target.name} —— 关掉游戏/编辑器再试")
                time.sleep(0.3)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def cmd_load(yes):
    guard_head()
    exists, remote_sha = ls_remote()
    if not exists:
        raise GitError("远程还没有快照 —— 先在资源的源头那台电脑上点一次「上传资产」")

    fetch_snapshot()
    manifest = read_manifest(REMOTE_REF)
    if not manifest or not manifest.get("files"):
        raise GitError("远程快照里没有文件清单，可能坏了")

    remote_files = manifest["files"]
    my_last_files = (read_manifest(REF) or {}).get("files") or {}

    # 本地改过的资源会被覆盖 → 先问
    would_clobber = []
    for name, info in sorted(remote_files.items()):
        p = REPO / name
        if not p.is_file():
            continue
        cur = md5_file(p)
        if cur == info.get("md5"):
            continue                                  # 已经一样
        if my_last_files.get(name, {}).get("md5") == cur:
            continue                                  # 只是旧版本，正常覆盖
        would_clobber.append(name)

    if would_clobber and not yes:
        out("⚠️  这些资源在本地改过，下载会把它们覆盖掉：")
        for n in would_clobber:
            out(f"    {n}")
        out()
        out("确认要覆盖，就加 --yes 再跑一次：python git_assets.py load --yes")
        return 3

    written, skipped = [], []
    for name, info in sorted(remote_files.items()):
        target = REPO / name
        blob = git_bytes(["cat-file", "blob", f"{REMOTE_REF}:{name}"])
        if md5_bytes(blob) != info.get("md5"):
            raise GitError(f"{name} 从远程取回来的内容和清单对不上，已中止")
        if target.is_file() and md5_file(target) == info["md5"]:
            skipped.append(name)
            continue
        write_atomic(target, blob)
        if md5_file(target) != info["md5"]:
            raise GitError(f"{name} 写盘后校验不通过，已中止")
        written.append(name)

    git(["update-ref", REF, remote_sha])              # 全部落地校验通过才记账

    out(f"✅ 已下载远程快照（保存于 {manifest.get('saved_at', '未知时间')}）")
    for n in written:
        out(f"    更新 {n}")
    for n in skipped:
        out(f"    跳过 {n}（本地已经一样）")

    local_now = scan_local()
    extra = sorted(set(local_now) - set(remote_files))
    if extra:
        out()
        out("注意：这些本地有、快照里没有（没动它们，下次上传会把它们加进去）：")
        for n in extra:
            out(f"    {n}")
    return 0


# ── 看两边一不一样 ────────────────────────────────────────────────────

def cmd_status():
    local = scan_local()
    exists, remote_sha = ls_remote()
    remote_files, saved_at = {}, None
    if exists:
        fetch_snapshot()
        m = read_manifest(REMOTE_REF) or {}
        remote_files = m.get("files") or {}
        saved_at = m.get("saved_at")

    out("本地资源（按 SOURCE_RULES 抓到的）")
    if local:
        for name, info in sorted(local.items()):
            out(f"    {name:<36} {fmt_size(info['bytes']):>10}  {info['md5'][:12]}")
    else:
        out("    （一个都没有）")

    out()
    if not exists:
        out(f"远程 {BRANCH} 分支：还没有（第一次上传会创建它）")
    else:
        out(f"远程 {BRANCH} 分支（保存于 {saved_at or '未知时间'}）")
        for name, info in sorted(remote_files.items()):
            out(f"    {name:<36} {fmt_size(info.get('bytes', 0)):>10}  {str(info.get('md5'))[:12]}")

    out()
    if not exists:
        out("结论：远程还没有快照 → 可以「上传资产」")
    elif fmt_map(local) == fmt_map(remote_files):
        out("结论：✅ 本地和远程一模一样，什么都不用做")
    else:
        same = set(fmt_map(local)) & set(fmt_map(remote_files))
        local_changed = [n for n in same if local[n]["md5"] != remote_files[n]["md5"]]
        local_only = sorted(set(local) - set(remote_files))
        remote_only = sorted(set(remote_files) - set(local))
        if local_only:
            out(f"    只有本地有：{', '.join(local_only)}")
        if remote_only:
            out(f"    只有远程有：{', '.join(remote_only)}")
        if local_changed:
            out(f"    两边不一样：{', '.join(local_changed)}")
        out("结论：两边不一致 —— 上传会覆盖远程，下载会覆盖本地，想清楚再点")
    return 0


# ── 快速核对（给 GUI 用）──────────────────────────────────────────────

def cmd_check():
    """只报一句结论、不写任何东西 —— 让 GUI 知道「上传/下载」该不该亮。

    比 status 省：本地见过远程那一份时，清单直接从本地引用读，
    不用把几十兆的资源再拉一遍。

    退出码：0 = 两边一样 · 4 = 两边不一样 · 5 = 远程还没有快照
    """
    local = scan_local()
    exists, remote_sha = ls_remote()
    if not exists:
        out("远程还没有资产快照（上传会建第一份）")
        return 5

    if ref_sha(REF) == remote_sha:
        manifest = read_manifest(REF) or {}       # 本地就有这份，免联网取包
    else:
        fetch_snapshot()
        manifest = read_manifest(REMOTE_REF) or {}

    remote_files = manifest.get("files") or {}
    if fmt_map(local) == fmt_map(remote_files):
        out(f"两边一样（{len(local)} 个文件）")
        return 0

    same = set(local) & set(remote_files)
    changed = sorted(n for n in same if local[n]["md5"] != remote_files[n]["md5"])
    local_only = sorted(set(local) - set(remote_files))
    remote_only = sorted(set(remote_files) - set(local))
    bits = []
    if changed:
        bits.append("改了 " + "、".join(changed))
    if local_only:
        bits.append("本地多 " + "、".join(local_only))
    if remote_only:
        bits.append("远程多 " + "、".join(remote_only))
    out("两边不一样 —— " + "；".join(bits))
    return 4


# ── 入口 ──────────────────────────────────────────────────────────────

def main(argv=None):
    setup_console()
    ap = argparse.ArgumentParser(
        description="把资源（*.bin / *.tpac）存到 GitHub 上当网盘（只留最新一份）")
    ap.add_argument("action", nargs="?", default="status",
                    choices=["status", "save", "load", "check"],
                    help="status=看两边差异（默认） check=只报结论 save=上传 load=下载")
    ap.add_argument("--yes", action="store_true",
                    help="需要确认的时候别问，直接干（覆盖远程 / 覆盖本地）")
    args = ap.parse_args(argv)

    try:
        if args.action == "save":
            return cmd_save(args.yes)
        if args.action == "load":
            return cmd_load(args.yes)
        if args.action == "check":
            return cmd_check()
        return cmd_status()
    except GitError as e:
        print(f"❌ {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
