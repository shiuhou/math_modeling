#!/usr/bin/env python3
"""Small Git-worktree + tmux helper for a trusted modeling team (Python 3.10+)."""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterator


class TeamError(Exception):
    """An actionable setup or task error."""


def run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if check and result.returncode:
        raise TeamError(result.stderr.strip() or result.stdout.strip() or shlex.join(args))
    return result


def need(program: str) -> str:
    path = shutil.which(program)
    if not path:
        raise TeamError(f"找不到 {program}；請先安裝並確認 PATH。")
    return path


def task_id(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,39}", value):
        raise argparse.ArgumentTypeError("任務名稱請用 1–40 個小寫英數字、-、_，並以英數字開頭。")
    return value


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


class Team:
    def __init__(self) -> None:
        need("git")
        # Resolve from this script, so commands also work inside linked worktrees.
        here = Path(__file__).resolve().parent.parent
        result = run("git", "rev-parse", "--git-common-dir", cwd=here, check=False)
        if result.returncode:
            raise TeamError("這裡還不是 Git 倉庫。先依 README 執行 git init、git add 和首次 commit。")
        common = Path(result.stdout.strip())
        self.common = (here / common).resolve() if not common.is_absolute() else common.resolve()
        first = run("git", "worktree", "list", "--porcelain", "-z", cwd=here).stdout.split("\0")[0]
        if not first.startswith("worktree "):
            raise TeamError("無法找到主要 worktree；此工具需要一般的非 bare 倉庫。")
        self.root = Path(first[len("worktree "):])
        if not (self.root / "AGENTS.md").is_file():
            raise TeamError("主要 worktree 缺少 AGENTS.md；請在完整的模板倉庫中使用。")
        self.state = self.common / "astra-team"
        self.tasks = self.state / "tasks"
        self.trees = self.root.parent / f"{self.root.name}.worktrees"
        digest = hashlib.sha256(str(self.common).encode()).hexdigest()[:12]
        self.prefix = f"astra-{digest}"
        socket = os.environ.get("TEAM_TMUX_SOCKET")
        if socket:
            socket_path = Path(socket).expanduser().resolve()
            if len(os.fsencode(socket_path)) > 100:
                raise TeamError("TEAM_TMUX_SOCKET 路徑太長；請改用較短的 Unix socket 路徑。")
            self.tmux = ["tmux", "-S", str(socket_path)]
        else:
            self.tmux = ["tmux", "-L", self.prefix]

    @contextlib.contextmanager
    def lock(self) -> Iterator[None]:
        self.tasks.mkdir(parents=True, exist_ok=True)
        with (self.state / ".lock").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def load(self, name: str) -> dict[str, Any]:
        path = self.tasks / f"{name}.json"
        if not path.is_file():
            raise TeamError(f"任務 {name} 不存在；先執行 new {name}。")
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, task: dict[str, Any]) -> None:
        # Atomic replacement: a concurrent viewer never reads half a JSON file.
        with tempfile.NamedTemporaryFile("w", dir=self.tasks, encoding="utf-8", delete=False) as handle:
            tmp = Path(handle.name)
            json.dump(task, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        try:
            tmp.chmod(0o644)  # Task metadata contains no credentials.
            os.replace(tmp, self.tasks / f"{task['id']}.json")
        finally:
            tmp.unlink(missing_ok=True)

    def session(self, name: str) -> str:
        return f"{self.prefix}-{name}"

    def live(self, name: str) -> bool:
        return run(*self.tmux, "has-session", "-t", f"={self.session(name)}", check=False).returncode == 0

    def new(self, name: str, goal: str, base: str) -> None:
        with self.lock():
            if (self.tasks / f"{name}.json").exists():
                raise TeamError(f"任務 {name} 已存在；可用 path、start 或 take。")
            run("git", "rev-parse", "--verify", "HEAD", cwd=self.root)
            branch, tree = f"task/{name}", self.trees / name
            if tree.exists():
                raise TeamError(f"目錄已存在，未覆寫：{tree}")
            self.trees.mkdir(parents=True, exist_ok=True)
            existing = run("git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", cwd=self.root, check=False)
            if existing.returncode == 0:
                run("git", "worktree", "add", str(tree), branch, cwd=self.root)
            else:
                if base.startswith("-"):
                    raise TeamError("--base 必須是分支或 commit，不可為選項。")
                run("git", "rev-parse", "--verify", f"{base}^{{commit}}", cwd=self.root)
                run("git", "worktree", "add", "-b", branch, str(tree), base, cwd=self.root)
            task = {"id": name, "goal": goal, "branch": branch, "path": str(tree),
                    "note": "", "by": "", "updated": now()}
            self.save(task)
            note = tree / "notes" / "tasks" / f"{name}.md"
            note.parent.mkdir(parents=True, exist_ok=True)
            if not note.exists():
                note.write_text(f"# {name}\n\n目標：{goal or '待分配'}\n\n目前：尚未開始。\n\n下一步：\n\n成果／重現命令：\n", encoding="utf-8")
        print(f"已建立 {branch}\n{tree}\n啟動：python3 scripts/team.py start {name}")

    def start(self, name: str, extra: list[str]) -> None:
        need("tmux")
        with self.lock():
            task = self.load(name)
            tree = Path(task["path"])
            if not tree.is_dir():
                raise TeamError(f"工作目錄不存在：{tree}。曾移動倉庫時請先修復路徑。")
            if self.live(name):
                print(f"終端已存在，不另開 Codex。接手：python3 scripts/team.py take {name}")
                return
            codex = need("codex")
            if extra[:1] == ["--"]:
                extra = extra[1:]
            command = shlex.join([codex, *extra])
            # Leave a shell after Codex exits, preserving its output and working directory.
            command += '; result=$?; printf "\\nCodex exited (%s). Use codex resume to continue.\\n" "$result"; exec /bin/bash'
            env = {"TEAM_TASK": name, "TEAM_ROOT": str(self.root),
                   "TEAM_STATE_DIR": str(self.state), "TEAM_WORKTREE": str(tree),
                   "PATH": os.environ.get("PATH", os.defpath)}
            # No API keys or Codex credentials are copied to files or command arguments.
            for key in ("VIRTUAL_ENV", "CONDA_PREFIX", "TEAM_DATA_DIR"):
                if key in os.environ:
                    env[key] = os.environ[key]
            args = [*self.tmux, "new-session", "-d", "-s", self.session(name), "-c", str(tree)]
            for key, value in env.items():
                args.extend(["-e", f"{key}={value}"])
            run(*args, command)
        print(f"已啟動 {name}；登入／信任提示可能正在終端內等候。\n接手：python3 scripts/team.py take {name}")

    def attach(self, name: str, watch: bool) -> None:
        need("tmux")
        self.load(name)
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise TeamError("watch / take 需要互動式終端；遠端連線可使用 ssh -t。")
        if os.environ.get("TMUX"):
            raise TeamError("請先 Ctrl-b d 離開目前 tmux，再從 SSH shell 執行 watch / take。")
        if not self.live(name):
            raise TeamError(f"任務尚未啟動：python3 scripts/team.py start {name}")
        if not watch:
            print("接手會斷開此 session 的其他觀看／操作連線，不會終止其中的程式。", flush=True)
        # -E avoids importing the attaching person's environment into the shared session.
        args = [*self.tmux, "attach-session", "-E", "-r" if watch else "-d", "-t", f"={self.session(name)}"]
        os.execvp(args[0], args)

    def listing(self) -> None:
        paths = sorted(self.tasks.glob("*.json"))
        if not paths:
            print("尚無任務。例：python3 scripts/team.py new model --goal '建立模型'")
            return
        print("TASK\tTERMINAL\tCLIENTS\tGOAL / LAST NOTE")
        for path in paths:
            task = json.loads(path.read_text(encoding="utf-8"))
            status, clients = "no tmux", "-"
            if shutil.which("tmux"):
                active = self.live(task["id"])
                status = "exists" if active else "stopped"
                if active:
                    result = run(*self.tmux, "list-clients", "-t", f"={self.session(task['id'])}", "-F", "#{client_readonly}", check=False)
                    values = result.stdout.splitlines()
                    clients = f"{values.count('0')} control / {values.count('1')} watch"
            print(f"{task['id']}\t{status}\t{clients}\t{task['goal']}")
            if task["note"]:
                print(f"  {task['updated']} [{task['by'] or '-'}] {task['note']}")
        print("exists 只表示 tmux 終端存在；不代表 Codex 正在運算。note 是最近人工留言，不是操作者鎖。")

    def note(self, name: str, message: str, by: str) -> None:
        with self.lock():
            task = self.load(name)
            task.update(note=message, by=by, updated=now())
            self.save(task)
        print("共用看板已更新；長期保留的成果可寫進該任務的 notes/tasks/ 檔案並 commit。")

    def info(self) -> None:
        print(f"主要倉庫：{self.root}\n工作目錄：{self.trees}\n即時狀態：{self.state}")
        print(f"tmux 前綴：{shlex.join(self.tmux)}")
        for tool in ("git", "tmux", "codex"):
            print(f"{tool}: {shutil.which(tool) or '未安裝'}")
        print("套用既有 Codex 設定；不設定模型、不更改 sandbox、不處理帳號登入。")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    new = commands.add_parser("new", help="建立任務分支與 worktree，不啟動 Codex")
    new.add_argument("task", type=task_id)
    new.add_argument("--goal", default="")
    new.add_argument("--base", default="main", help="新分支起點；預設 main")
    start = commands.add_parser("start", help="在 tmux 啟動 Codex；-- 後原樣傳給 Codex")
    start.add_argument("task", type=task_id)
    start.add_argument("codex_args", nargs=argparse.REMAINDER)
    for name, help_text in (("watch", "唯讀觀看"), ("take", "接手並斷開其他連線"), ("path", "顯示任務的絕對路徑")):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("task", type=task_id)
    commands.add_parser("list", help="查看所有任務與人工留言")
    commands.add_parser("info", help="顯示主機路徑與工具位置")
    note = commands.add_parser("note", help="更新共用看板上的一則短留言")
    note.add_argument("task", type=task_id)
    note.add_argument("message")
    note.add_argument("--by", default=os.environ.get("TEAM_MEMBER", ""), help="顯示名稱；也可設 TEAM_MEMBER")
    args = parser.parse_args()
    try:
        team = Team()
        if args.command == "new":
            team.new(args.task, args.goal, args.base)
        elif args.command == "start":
            team.start(args.task, args.codex_args)
        elif args.command in ("watch", "take"):
            team.attach(args.task, args.command == "watch")
        elif args.command == "path":
            print(team.load(args.task)["path"])
        elif args.command == "list":
            team.listing()
        elif args.command == "note":
            team.note(args.task, args.message, args.by)
        else:
            team.info()
    except (TeamError, OSError, ValueError, KeyError) as exc:
        print(f"team: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
