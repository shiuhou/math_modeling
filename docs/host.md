# 主機設定

## 工具與登入

腳本使用 Python 標準函式庫；不需要 pip install。Linux 上先有 Python 3.10+、Git、tmux 和 Codex CLI。

Ubuntu / Debian 的基礎工具可由管理員安裝：

```bash
sudo apt-get update
sudo apt-get install git tmux python3
```

Codex 的安裝方式見 [官方 CLI 文件](https://developers.openai.com/codex/cli)。目前官方提供的 Linux 安裝命令為：

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
codex --version
```

在要執行 Codex 的身分下，依你的方案完成授權。無桌面的主機可用 `codex login --device-auth`；使用前可能需要在帳號安全設定或 workspace 權限中啟用裝置碼登入。也可依 [官方認證文件](https://developers.openai.com/codex/auth) 選擇其他方式。

模板不設定模型代號、不關閉 sandbox，也不接管 API key。先在一個 worktree 中確認 `codex` 可啟動，再用 `team.py start`。

## 預設：同一執行身分

多個 SSH 終端使用同一 Linux 執行身分、同一份倉庫時，`team.py` 會選到同一個專用 tmux server。每人可設定 `export TEAM_MEMBER=Alice` 作為看板留言署名；這不是身分驗證。

共享終端也共享進程權限及 Codex 的執行身分，**不會自動得到各自獨立的登入、額度或帳號隔離**。只在獲授權、可信任的專用環境使用；不要分享個人登入憑證。可控制 shell 的人也可能讀取該執行身分的憑證，不能只靠 `watch` 保護秘密。

## 可選：個人 SSH 帳號，共看一個 tmux server

以下是需管理員配合的設定示例，**不是模板自動配置的功能**。假設執行身分是 `alice`，隊員是 `bob`、`carol`，三者已屬於 `modelteam` 群組；主機的 tmux 支援 `server-access`。

管理員準備只有團隊能進入的父目錄：

```bash
sudo install -d -o alice -g modelteam -m 2750 /srv/modeling
```

由 `alice` 將倉庫 clone 到 `/srv/modeling/repo`，確保隊友可讀取倉庫及 Git metadata。在建立任務後，先選定共用 socket 再啟動：

```bash
cd /srv/modeling/repo
export TEAM_TMUX_SOCKET=/srv/modeling/session.sock
python3 scripts/team.py start model
chgrp modelteam "$TEAM_TMUX_SOCKET"
chmod 660 "$TEAM_TMUX_SOCKET"
tmux -S "$TEAM_TMUX_SOCKET" server-access -a bob
tmux -S "$TEAM_TMUX_SOCKET" server-access -w bob
tmux -S "$TEAM_TMUX_SOCKET" server-access -a carol
tmux -S "$TEAM_TMUX_SOCKET" server-access -w carol
```

隊員在自己的 SSH shell：

```bash
# 只信任已核對的這個共用倉庫，不使用 safe.directory '*'.
git config --global --add safe.directory /srv/modeling/repo
cd /srv/modeling/repo
export TEAM_TMUX_SOCKET=/srv/modeling/session.sock
python3 scripts/team.py watch model
# 要接手時，先退出觀看，再執行：
# python3 scripts/team.py take model
```

`new / start / note` 由 `alice` 的 shell 執行即可，避免再管理多人寫 Git metadata 的權限。其他帳號可用 `list / path / watch / take`；接手後的 shell 和 Codex **仍以 alice 身分執行**。這是受信任的共同控制，不是憑證隔離方案。

所有相關 shell 都要使用同一個 `TEAM_TMUX_SOCKET`；不要開了一半才切換。server 重啟、socket 重建後，重新配置 socket 權限與 `server-access`。僅設定檔案權限不等於已完成 tmux 授權。

## 資料與環境

共享資料可放在團隊可讀的固定目錄，啟動 session 前設定：

```bash
export TEAM_DATA_DIR=/srv/modeling-data
```

這個變數只提供路徑，不會下載資料、建立目錄或設定唯讀權限。各任務的 `outputs/` 分開存放，選用的結果再整理進 Git。運算套件與 Python 環境由你按題目選擇；worktree 不會自動複製 `.venv`。

腳本將啟動時的 PATH 帶入新 session；共用環境需要改套件時先和其他人說一聲。正在運算的 session 不要被多人同時改環境。

## 中斷與恢復

SSH 中斷不等於 tmux 進程結束；重新 `take` 即可。主機重啟後需重開終端，再 `codex resume` 選原對話。`list` 的 `exists` 只表示 tmux 還在，不代表模型仍在運算或登入成功。

Git worktree 是檔案／分支分工工具，不是安全沙箱。即時看板和工作目錄含本機路徑，啟動後不要任意搬移倉庫；需要遷移時先保存成果並處理 Git worktree 路徑。
