#!/usr/bin/env python3
"""
Git 图形化快捷工具 - 完整版
"""

import tkinter as tk
from tkinter import messagebox, simpledialog, scrolledtext, ttk
import subprocess
import sys
import os
import threading

# 切换到项目目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Git 路径（根据您的系统调整）
# 如果 git 命令可以直接使用，设置为 None ，这就是终极的Git工具，不错
GIT_PATH = None

# 全局 UI 引用（在 main() 里赋值）
status_label = None
file_list_text = None
push_only_btn = None
assets_upload_btn = None
assets_download_btn = None
root_window = None
asset_note = ""          # 资产核对结论，贴在状态栏最后


def run_git(cmd):
    """运行 git 命令"""
    if GIT_PATH:
        full_cmd = cmd.replace('git ', f'"{GIT_PATH}" ', 1)
    else:
        full_cmd = cmd
    result = subprocess.run(full_cmd, shell=True, capture_output=True)
    stdout = result.stdout.decode('utf-8', errors='ignore') if result.stdout else ""
    stderr = result.stderr.decode('utf-8', errors='ignore') if result.stderr else ""
    return result.returncode == 0, stdout, stderr


def get_file_status():
    """获取文件状态，返回（暂存区列表，工作区列表，未跟踪列表）"""
    staged_files = []
    modified_files = []
    untracked_files = []

    # 获取暂存区的文件
    success, stdout, _ = run_git("git diff --cached --name-only")
    if success and stdout:
        staged_files = [line.strip() for line in stdout.strip().split('\n') if line.strip()]

    # 获取工作区已修改但未暂存的文件
    success, stdout, _ = run_git("git diff --name-only")
    if success and stdout:
        modified_files = [line.strip() for line in stdout.strip().split('\n') if line.strip()]

    # 获取未跟踪的文件
    success, stdout, _ = run_git("git ls-files --others --exclude-standard")
    if success and stdout:
        untracked_files = [line.strip() for line in stdout.strip().split('\n') if line.strip()]

    return staged_files, modified_files, untracked_files


def get_status():
    """获取当前状态（用于检查是否有变化）"""
    staged, modified, untracked = get_file_status()
    return len(staged) > 0 or len(modified) > 0 or len(untracked) > 0


def get_branch():
    """获取当前分支"""
    success, stdout, _ = run_git("git branch --show-current")
    if success:
        return stdout.strip()
    return "main"


def get_project_name():
    """从 git remote 提取项目名，失败时回退到文件夹名"""
    success, stdout, _ = run_git("git remote get-url origin")
    if success and stdout.strip():
        url = stdout.strip()
        if url.endswith('.git'):
            url = url[:-4]
        return url.rsplit('/', 1)[-1].rsplit(':', 1)[-1]
    return os.path.basename(os.path.dirname(os.path.abspath(__file__)))


def get_unpushed_count():
    """本地领先远程的提交数（未推送的提交数）"""
    success, stdout, _ = run_git("git rev-list --count @{u}..HEAD")
    if success and stdout.strip().isdigit():
        return int(stdout.strip())
    return 0


def get_behind_count():
    """远程领先本地的提交数（本地落后远程、需要拉取的提交数）

    注意：基于本地缓存的远程跟踪引用 @{u}，若未先 fetch 则可能过期。
    """
    success, stdout, _ = run_git("git rev-list --count HEAD..@{u}")
    if success and stdout.strip().isdigit():
        return int(stdout.strip())
    return 0


def fetch_remote():
    """从远程拉取最新引用信息（只更新 remote-tracking ref，不合并到工作区）"""
    success, _, stderr = run_git("git fetch")
    return success, stderr


def check_updates():
    """检查本地是否为最新：先 fetch 刷新远程引用，再比较领先/落后"""
    success, stderr = fetch_remote()
    if not success:
        messagebox.showerror("错误", f"获取远程信息失败:\n{stderr}")
        return

    ahead = get_unpushed_count()
    behind = get_behind_count()

    # 刷新界面，让状态栏反映最新的领先/落后情况
    update_file_list()
    update_status_label()

    if behind == 0 and ahead == 0:
        messagebox.showinfo("检查结果", "✅ 本地已是最新，与远程完全一致")
    elif behind > 0 and ahead == 0:
        messagebox.showwarning("检查结果",
                               f"⬇️ 本地落后远程 {behind} 个提交\n\n"
                               f"远程有新内容，点击「📥 拉取最新代码」更新到最新")
    elif behind == 0 and ahead > 0:
        messagebox.showinfo("检查结果",
                            f"⬆️ 本地领先远程 {ahead} 个提交\n\n"
                            f"你有未推送的提交，点击「📤 仅推送」上传")
    else:
        messagebox.showwarning("检查结果",
                               f"⚠️ 本地与远程已分叉\n\n"
                               f"本地领先 {ahead} 个、落后 {behind} 个提交\n"
                               f"建议先「📥 拉取最新代码」合并，再推送")


def show_file_details():
    """显示文件详情窗口"""
    staged, modified, untracked = get_file_status()

    detail_window = tk.Toplevel()
    detail_window.title("文件状态详情")
    detail_window.geometry("600x400")

    # 创建标签页
    notebook = ttk.Notebook(detail_window)
    notebook.pack(expand=True, fill='both', padx=10, pady=10)

    # 已暂存文件
    if staged:
        staged_frame = tk.Frame(notebook)
        notebook.add(staged_frame, text=f"已暂存 ({len(staged)})")

        text_area = scrolledtext.ScrolledText(staged_frame, wrap=tk.WORD, font=("Consolas", 9))
        text_area.pack(expand=True, fill='both', padx=5, pady=5)
        for f in staged:
            text_area.insert(tk.END, f"✓ {f}\n")
        text_area.config(state=tk.DISABLED)
    else:
        notebook.add(tk.Label(notebook, text="没有已暂存的文件", padx=20, pady=20), text="已暂存 (0)")

    # 已修改未暂存
    if modified:
        modified_frame = tk.Frame(notebook)
        notebook.add(modified_frame, text=f"已修改 ({len(modified)})")

        text_area = scrolledtext.ScrolledText(modified_frame, wrap=tk.WORD, font=("Consolas", 9))
        text_area.pack(expand=True, fill='both', padx=5, pady=5)
        for f in modified:
            text_area.insert(tk.END, f"⚡ {f}\n")
        text_area.config(state=tk.DISABLED)
    else:
        notebook.add(tk.Label(notebook, text="没有已修改的文件", padx=20, pady=20), text="已修改 (0)")

    # 未跟踪文件
    if untracked:
        untracked_frame = tk.Frame(notebook)
        notebook.add(untracked_frame, text=f"未跟踪 ({len(untracked)})")

        text_area = scrolledtext.ScrolledText(untracked_frame, wrap=tk.WORD, font=("Consolas", 9))
        text_area.pack(expand=True, fill='both', padx=5, pady=5)
        for f in untracked:
            text_area.insert(tk.END, f"? {f}\n")
        text_area.config(state=tk.DISABLED)
    else:
        notebook.add(tk.Label(notebook, text="没有未跟踪的文件", padx=20, pady=20), text="未跟踪 (0)")

    tk.Button(detail_window, text="关闭", command=detail_window.destroy).pack(pady=5)


def add_to_staging():
    """添加所有更改到暂存区"""
    staged, modified, untracked = get_file_status()

    if not modified and not untracked:
        messagebox.showinfo("提示", "没有需要添加的文件")
        return

    run_git("git add -A")
    messagebox.showinfo("成功", "已添加所有更改到暂存区")
    update_file_list()


def clear_staging():
    """清空暂存区"""
    staged, modified, untracked = get_file_status()

    if not staged:
        messagebox.showinfo("提示", "暂存区为空")
        return

    run_git("git reset HEAD")
    messagebox.showinfo("成功", "已清空暂存区")
    update_file_list()


def commit(push_after=False):
    """提交更改"""
    staged, modified, untracked = get_file_status()

    # 检查是否有文件需要提交
    if not staged and not modified and not untracked:
        messagebox.showinfo("提示", "没有需要提交的更改")
        return False

    # 自动将所有更改添加到暂存区（简化操作）
    if modified or untracked:
        run_git("git add -A")

    # 询问提交信息
    msg = simpledialog.askstring("提交", "输入提交信息:", initialvalue="更新代码")
    if not msg:
        return False

    success, stdout, stderr = run_git(f'git commit -m "{msg}"')
    if success:
        if push_after:
            push_success = push()
            update_file_list()
            update_status_label()
            return push_success
        else:
            messagebox.showinfo("成功", "本地提交成功！\n记得点击'推送'上传到 GitHub")
            update_file_list()
            update_status_label()
            return True
    else:
        messagebox.showerror("错误", f"提交失败:\n{stderr}")
        return False


def push():
    """推送到远程"""
    branch = get_branch()
    success, stdout, stderr = run_git(f"git push origin {branch}")
    if success:
        messagebox.showinfo("成功", f"已推送到 GitHub！\n分支: {branch}")
        return True
    else:
        # 检查是否需要设置上游分支
        if "no upstream branch" in stderr.lower():
            success, stdout, stderr = run_git(f"git push -u origin {branch}")
            if success:
                messagebox.showinfo("成功", f"已推送到 GitHub！\n分支: {branch}")
                return True
        messagebox.showerror("错误", f"推送失败:\n{stderr}")
        return False


def commit_and_push():
    """提交并推送"""
    if commit(push_after=True):
        update_status_label()


def push_only():
    """仅推送：用于本地已 commit 但 push 失败后的重试"""
    if get_unpushed_count() == 0:
        messagebox.showinfo("提示", "本地没有未推送的提交")
        return
    push()
    update_file_list()
    update_status_label()


def pull():
    """从远程拉取"""
    branch = get_branch()
    success, stdout, stderr = run_git(f"git pull origin {branch}")
    if success:
        messagebox.showinfo("成功", f"已从 GitHub 拉取最新代码！\n分支: {branch}")
        update_status_label()
        return True
    else:
        messagebox.showerror("错误", f"拉取失败:\n{stderr}")
        return False


def show_log():
    """显示提交历史，支持回退到指定版本"""
    success, stdout, _ = run_git("git log --oneline -20 --graph")
    if not success:
        messagebox.showerror("错误", "无法获取提交历史")
        return

    # 解析提交历史，提取提交哈希和消息
    commits = []
    for line in stdout.strip().split('\n'):
        line = line.strip()
        if line and not line.startswith('*') and not line.startswith('|') and not line.startswith('\\'):
            # 提取哈希值（前7位）和提交消息
            parts = line.split(' ', 1)
            if len(parts) >= 2:
                commit_hash = parts[0]
                message = parts[1]
                commits.append((commit_hash, message))
        elif line and (' ' in line):
            # 处理带 * 的行，如 "* abc1234 message"
            clean_line = line.replace('*', '').replace('|', '').strip()
            parts = clean_line.split(' ', 1)
            if len(parts) >= 2 and len(parts[0]) >= 7:
                commit_hash = parts[0]
                message = parts[1]
                commits.append((commit_hash, message))

    # 创建新窗口
    log_window = tk.Toplevel()
    log_window.title("提交历史")
    log_window.geometry("600x550")

    # 说明标签
    tk.Label(log_window, text="📋 提交历史列表",
             font=("Microsoft YaHei", 11, "bold"), pady=10).pack()

    tk.Label(log_window, text="选中一个版本，点击下方的【回退到选中版本】按钮",
             font=("Microsoft YaHei", 9), fg="gray").pack()

    # 创建列表框
    frame = tk.Frame(log_window)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    listbox = tk.Listbox(frame, font=("Consolas", 10), yscrollcommand=scrollbar.set, selectmode=tk.SINGLE)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=listbox.yview)

    # 填充列表
    for i, (commit_hash, message) in enumerate(commits):
        display_text = f"{commit_hash[:7]} - {message[:50]}"
        listbox.insert(tk.END, display_text)

    # 选中第一行（最新提交）
    if commits:
        listbox.selection_set(0)

    def do_reset():
        """执行回退操作"""
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个版本")
            return

        index = selection[0]
        commit_hash, message = commits[index]

        # 确认对话框（二次确认）
        if not messagebox.askyesno("⚠️ 确认回退",
                                   f"确定要回退到以下版本？\n\n"
                                   f"提交哈希: {commit_hash[:7]}\n"
                                   f"提交消息: {message[:40]}...\n\n"
                                   f"⚠️ 警告：这将丢失当前未提交的更改！\n"
                                   f"⚠️ 如果已推送到远程，可能需要强制推送！"):
            return

        # 再次确认（三次确认，防止误操作）
        if not messagebox.askyesno("最终确认",
                                   f"最后确认：真的要回退到 {commit_hash[:7]} 吗？\n\n"
                                   f"此操作不可撤销！"):
            return

        # 执行回退
        success, _, stderr = run_git(f"git reset --hard {commit_hash}")
        if success:
            messagebox.showinfo("成功", f"✅ 已回退到版本: {commit_hash[:7]}")
            log_window.destroy()
            update_file_list()
            update_status_label()
        else:
            messagebox.showerror("错误", f"回退失败:\n{stderr}")

    # 按钮区域
    btn_frame = tk.Frame(log_window)
    btn_frame.pack(pady=10)

    tk.Button(btn_frame, text="⏪ 回退到选中版本", width=18, height=2,
              font=("Microsoft YaHei", 10), bg="#f44336", fg="white",
              command=do_reset).pack(side=tk.LEFT, padx=5)

    tk.Button(btn_frame, text="刷新", width=12, height=2,
              font=("Microsoft YaHei", 10),
              command=lambda: [log_window.destroy(), show_log()]).pack(side=tk.LEFT, padx=5)

    tk.Button(btn_frame, text="关闭", width=12, height=2,
              font=("Microsoft YaHei", 10),
              command=log_window.destroy).pack(side=tk.LEFT, padx=5)


def discard_changes():
    """放弃所有未提交的更改"""
    # 检查是否有未提交的更改
    success, stdout, stderr = run_git("git status --porcelain")
    if not success:
        messagebox.showerror("错误", f"无法获取状态:\n{stderr}")
        return
    
    if not stdout.strip():
        messagebox.showinfo("提示", "工作区已经是干净状态，没有需要放弃的更改")
        return
    
    # 显示将要放弃的更改
    changes = stdout.strip().split('\n')
    change_summary = []
    for line in changes[:20]:  # 最多显示20个文件
        if line:
            status = line[:2]
            filename = line[3:]
            change_summary.append(f"  {status} {filename}")
    
    if len(changes) > 20:
        change_summary.append(f"  ... 还有 {len(changes) - 20} 个文件")
    
    change_text = '\n'.join(change_summary)
    
    # 确认对话框
    if not messagebox.askyesno("⚠️ 确认放弃更改",
                               f"确定要放弃以下未提交的更改吗？\n\n"
                               f"{change_text}\n\n"
                               f"⚠️ 警告：此操作不可撤销！\n"
                               f"已修改的文件将恢复到上次提交的状态。"):
        return
    
    # 执行放弃更改
    success, _, stderr = run_git("git checkout -- .")
    if success:
        # 同时清理未跟踪的文件（可选）
        has_untracked = any(line.startswith('??') for line in changes if line)
        if has_untracked:
            if messagebox.askyesno("清理未跟踪文件",
                                   "检测到未跟踪的文件（新文件），是否同时清理？\n\n"
                                   "选择「是」将删除这些新文件\n"
                                   "选择「否」保留这些新文件"):
                run_git("git clean -fd")
        
        messagebox.showinfo("成功", "✅ 已放弃所有更改，工作区已恢复干净状态")
        update_file_list()
        update_status_label()
    else:
        messagebox.showerror("错误", f"放弃更改失败:\n{stderr}")


def reset():
    """回退版本"""
    # 获取最近提交
    success, stdout, _ = run_git("git log --oneline -10")
    if not success:
        messagebox.showerror("错误", "无法获取提交历史")
        return
    
    # 显示提交历史并询问
    msg = "最近提交:\n\n" + stdout + "\n\n输入要回退的版本号 (前7位即可):"
    commit_hash = simpledialog.askstring("回退版本", msg)
    
    if not commit_hash:
        return
    
    if not messagebox.askyesno("确认", f"确定要回退到 {commit_hash}?\n这将丢失当前未提交的更改！"):
        return
    
    success, _, stderr = run_git(f"git reset --hard {commit_hash}")
    if success:
        # 强制推送到远程
        branch = get_branch()
        success_push, _, stderr_push = run_git(f"git push origin {branch} --force")
        if success_push:
            messagebox.showinfo("成功", "回退成功并已强制推送到 GitHub！")
        else:
            messagebox.showwarning("警告", f"本地回退成功，但推送失败:\n{stderr_push}")
        update_status_label()
    else:
        messagebox.showerror("错误", f"回退失败:\n{stderr}")


def update_file_list():
    """更新文件列表"""
    staged, modified, untracked = get_file_status()

    # 先启用编辑模式
    file_list_text.config(state=tk.NORMAL)
    file_list_text.delete(1.0, tk.END)

    if staged:
        file_list_text.insert(tk.END, "【已暂存 - 将被提交】\n", "staged_header")
        for f in staged:
            file_list_text.insert(tk.END, f"  ✓ {f}\n", "staged")
        file_list_text.insert(tk.END, "\n")

    if modified:
        file_list_text.insert(tk.END, "【已修改 - 未暂存】\n", "modified_header")
        for f in modified:
            file_list_text.insert(tk.END, f"  ⚡ {f}\n", "modified")
        file_list_text.insert(tk.END, "\n")

    if untracked:
        file_list_text.insert(tk.END, "【未跟踪 - 新文件】\n", "untracked_header")
        for f in untracked:
            file_list_text.insert(tk.END, f"  ? {f}\n", "untracked")
        file_list_text.insert(tk.END, "\n")

    if not staged and not modified and not untracked:
        file_list_text.insert(tk.END, "工作区干净，没有未提交的更改\n", "clean")

    # 写完后禁用编辑模式
    file_list_text.config(state=tk.DISABLED)


def update_status_label():
    """更新状态标签 + 仅推送按钮的启用状态"""
    staged, modified, untracked = get_file_status()
    branch = get_branch()
    unpushed = get_unpushed_count()
    behind = get_behind_count()

    parts = [f"分支: {branch}"]
    total = len(staged) + len(modified) + len(untracked)
    if total > 0:
        parts.append(f"已暂存: {len(staged)} | 已修改: {len(modified)} | 未跟踪: {len(untracked)}")
    if unpushed > 0:
        parts.append(f"⚠️ {unpushed} 个本地提交未推送")
    if behind > 0:
        parts.append(f"⬇️ 落后远程 {behind} 个提交")
    if total == 0 and unpushed == 0 and behind == 0:
        parts.append("工作区干净")

    if asset_note:
        parts.append(asset_note)

    if behind > 0 or unpushed > 0:
        color = "red"
    elif total > 0:
        color = "orange"
    else:
        color = "green"

    status_label.config(text=" | ".join(parts), fg=color)

    # 切换"仅推送"按钮状态
    if push_only_btn is not None:
        if unpushed > 0:
            push_only_btn.config(state=tk.NORMAL, bg="#f44336")
        else:
            push_only_btn.config(state=tk.DISABLED, bg="#9E9E9E")


# ============================================================
# 资产快照 —— 把资源（SceneObj 的 *.bin + AssetPackages 的 *.tpac）传到远程 assets 分支当网盘
#   远程那条分支永远只有一个提交（每次整个换掉），所以仓库不会越滚越大。
#   细节与判据见 git_assets.py 顶部说明。
# ============================================================

ASSET_TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "git_assets.py")

UPLOAD_COLOR = "#3F51B5"
DOWNLOAD_COLOR = "#009688"
GRAY_COLOR = "#9E9E9E"


def _call_asset_tool(action, yes=False, timeout=900):
    """跑 git_assets.py，返回 (退出码, 输出文本)"""
    if not os.path.isfile(ASSET_TOOL):
        return 1, f"找不到 {ASSET_TOOL}"
    cmd = [sys.executable, ASSET_TOOL, action] + (["--yes"] if yes else [])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return 1, f"等了 {max(1, timeout // 60)} 分钟还没结束，先检查网络再试"
    return result.returncode, ((result.stdout or "") + (result.stderr or "")).strip()


def _set_asset_buttons(same):
    """两边一模一样就把两个按钮压灰：按下去也只会弹"没有可传/可拉的东西"。"""
    state = tk.DISABLED if same else tk.NORMAL
    if assets_upload_btn is not None:
        assets_upload_btn.config(state=state, bg=GRAY_COLOR if same else UPLOAD_COLOR)
    if assets_download_btn is not None:
        assets_download_btn.config(state=state, bg=GRAY_COLOR if same else DOWNLOAD_COLOR)


def _apply_asset_state(code, text):
    """核对结果回来：0=一样 4=不一样 5=远程还没有，其他=没核对上（联网失败）"""
    global asset_note
    if code == 0:
        _set_asset_buttons(True)
    else:
        # 4/5 该亮；出错时也不锁死 —— 网络抖一下不该让按钮点不了
        _set_asset_buttons(False)

    first_line = (text or "").strip().splitlines()
    # 只取冒号前面那一小段，免得状态栏里括号套括号
    detail = (first_line[0] if first_line else "").split("：")[0].split("（")[0].strip("。 ")
    if code == 0:
        asset_note = "📦 资产：与远程一致"
    elif code == 4:
        asset_note = "📦 资产：有改动待上传"
    elif code == 5:
        asset_note = "📦 资产：远程还没有快照"
    else:
        # 只有"没核对上"才把原因贴出来（别的结论说了也够，状态栏放不下）
        asset_note = "📦 资产：未能核对" + (f"（{detail[:24]}）" if detail else "")
    update_status_label()


def refresh_asset_state():
    """后台比对本地包和远程快照的 md5，回来后决定按钮亮不亮（不卡界面）"""
    def work():
        code, text = _call_asset_tool("check", timeout=60)
        if root_window is not None:
            try:
                root_window.after(0, lambda: _apply_asset_state(code, text))
            except RuntimeError:
                pass               # 窗口已经关了
    threading.Thread(target=work, daemon=True).start()


def _run_asset_tool(action, title, ask_title, ask_question):
    """上传/下载资产；脚本说要确认（退出码 3）时弹框问一句，确认后带 --yes 重跑"""
    code, text = _call_asset_tool(action)
    if code == 3:
        if not messagebox.askyesno(ask_title, f"{text}\n\n{ask_question}"):
            return
        code, text = _call_asset_tool(action, yes=True)
    if code == 0:
        messagebox.showinfo(f"{title} - 完成", text or "（没有输出）")
    else:
        messagebox.showerror(f"{title} - 失败", text or "（没有输出）")


def assets_upload():
    """上传资产：把资源（*.bin / *.tpac）传到远程 assets 分支"""
    _run_asset_tool("save", "上传资产", "要覆盖远程快照吗？",
                    "上传会把远程那份整个换掉，找不回来。")
    refresh_asset_state()


def assets_download():
    """下载资产：把远程 assets 分支的 tpac 拉回本地"""
    _run_asset_tool("load", "下载资产", "要覆盖本地这些包吗？",
                    "下载会把本地改过的包覆盖掉，找不回来。")
    refresh_asset_state()


def main():
    """主界面"""
    global status_label, file_list_text, push_only_btn
    global assets_upload_btn, assets_download_btn, root_window

    project_name = get_project_name()

    root = tk.Tk()
    root_window = root
    root.title(f"Git 快捷工具 - {project_name}")
    root.geometry("620x690")
    root.resizable(False, False)

    # 居中显示
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - 310
    y = (root.winfo_screenheight() // 2) - 345
    root.geometry(f'+{x}+{y}')

    # 标题
    tk.Label(root, text="🚀 Git 快捷工具", font=("Microsoft YaHei", 18, "bold"), pady=10).pack()
    tk.Label(root, text=f"项目: {project_name}", font=("Microsoft YaHei", 10), fg="gray").pack()

    # 按钮框架
    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)

    # 第一行按钮
    row1 = tk.Frame(btn_frame)
    row1.pack(pady=5)

    btn_width = 15
    btn_height = 2

    # 主要功能：提交并推送（一键完成）
    tk.Button(row1, text="📤 提交并推送", width=btn_width, height=btn_height,
              font=("Microsoft YaHei", 11, "bold"), bg="#2196F3", fg="white",
              command=commit_and_push).pack(side=tk.LEFT, padx=5)

    tk.Button(row1, text="📥 拉取最新代码", width=btn_width, height=btn_height,
              font=("Microsoft YaHei", 11), bg="#FF9800", fg="white",
              command=lambda: [pull(), update_file_list(), update_status_label()]).pack(side=tk.LEFT, padx=5)

    tk.Button(row1, text="🔍 检查更新", width=btn_width, height=btn_height,
              font=("Microsoft YaHei", 11), bg="#4CAF50", fg="white",
              command=check_updates).pack(side=tk.LEFT, padx=5)

    # 第二行按钮（辅助功能）
    row2 = tk.Frame(btn_frame)
    row2.pack(pady=5)

    push_only_btn = tk.Button(row2, text="📤 仅推送", width=btn_width, height=btn_height,
                              font=("Microsoft YaHei", 10), bg="#9E9E9E", fg="white",
                              state=tk.DISABLED, command=push_only)
    push_only_btn.pack(side=tk.LEFT, padx=5)

    tk.Button(row2, text="🔄 刷新状态", width=btn_width, height=btn_height,
              font=("Microsoft YaHei", 10),
              command=lambda: [update_file_list(), update_status_label(),
                               refresh_asset_state()]).pack(side=tk.LEFT, padx=5)

    tk.Button(row2, text="📜 提交历史", width=btn_width, height=btn_height,
              font=("Microsoft YaHei", 10),
              command=show_log).pack(side=tk.LEFT, padx=5)

    tk.Button(row2, text="🗑️ 放弃更改", width=btn_width, height=btn_height,
              font=("Microsoft YaHei", 10), bg="#f44336", fg="white",
              command=discard_changes).pack(side=tk.LEFT, padx=5)

    # 第三行按钮（资产快照：把资源存到远程 assets 分支，换电脑能拿回来）
    row3 = tk.Frame(btn_frame)
    row3.pack(pady=5)

    assets_upload_btn = tk.Button(row3, text="📦 上传资产", width=btn_width, height=btn_height,
                                  font=("Microsoft YaHei", 10), bg=UPLOAD_COLOR, fg="white",
                                  command=assets_upload)
    assets_upload_btn.pack(side=tk.LEFT, padx=5)

    assets_download_btn = tk.Button(row3, text="📥 下载资产", width=btn_width, height=btn_height,
                                    font=("Microsoft YaHei", 10), bg=DOWNLOAD_COLOR, fg="white",
                                    command=assets_download)
    assets_download_btn.pack(side=tk.LEFT, padx=5)

    # 文件列表显示区
    list_frame = tk.LabelFrame(root, text="文件状态", font=("Microsoft YaHei", 11), padx=10, pady=10)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    file_list_text = scrolledtext.ScrolledText(list_frame, wrap=tk.WORD, font=("Consolas", 9), height=15)
    file_list_text.pack(fill=tk.BOTH, expand=True)

    # 配置文本样式
    file_list_text.tag_config("staged_header", foreground="#4CAF50", font=("Microsoft YaHei", 10, "bold"))
    file_list_text.tag_config("staged", foreground="#2E7D32")
    file_list_text.tag_config("modified_header", foreground="#FF9800", font=("Microsoft YaHei", 10, "bold"))
    file_list_text.tag_config("modified", foreground="#EF6C00")
    file_list_text.tag_config("untracked_header", foreground="#9E9E9E", font=("Microsoft YaHei", 10, "bold"))
    file_list_text.tag_config("untracked", foreground="#616161")
    file_list_text.tag_config("clean", foreground="#4CAF50", font=("Microsoft YaHei", 10))

    file_list_text.config(state=tk.DISABLED)

    # 状态显示
    status_frame = tk.Frame(root, bd=1, relief=tk.SUNKEN)
    status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

    status_label = tk.Label(status_frame, text="正在检查状态...", font=("Microsoft YaHei", 9))
    status_label.pack(pady=5)

    # 初始化状态
    update_file_list()
    update_status_label()
    refresh_asset_state()      # 后台联网比对一次，决定资产按钮亮不亮

    root.mainloop()


if __name__ == "__main__":
    main()