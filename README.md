# Astra Modeling Team

一台主機，多個任務 worktree，多個 Codex 終端。隊員可觀看、接手同一個 session；模型方法保持開放，實驗預設由人執行。

## 先放上 GitHub

解壓後進入此目錄，在 GitHub 建立**空白倉庫**，不要先加入 README。再執行：

```bash
git init -b main
git add .
git commit -m "Initial modeling team workspace"
git remote add origin git@github.com:YOUR_NAME/YOUR_REPO.git
git push -u origin main
```

把 `YOUR_NAME/YOUR_REPO` 換成你的倉庫。壓縮包沒有 `.git` 或帳號憑證；commit 需要你自己的 Git 姓名／信箱，push 需要已設定的 GitHub SSH key。比賽用專案可先建為 Private。

## 在主機開工

目標環境：Linux、Python 3.10+、Git、tmux、已安裝且完成授權的 Codex CLI。此模板不安裝套件、不登入帳號、不修改系統權限。[安裝與共用方式](docs/host.md)

```bash
git clone git@github.com:YOUR_NAME/YOUR_REPO.git
cd YOUR_REPO

# 先在主分支補題目、資料位置與共用接口；有內容才填。
# 編輯 docs/brief.md 後 commit，再分出任務。

python3 scripts/team.py new data  --goal "資料與圖表"
python3 scripts/team.py new model --goal "模型推導與實作"
python3 scripts/team.py new paper --goal "論文與敘事"

python3 scripts/team.py start model
python3 scripts/team.py take model
```

每個任務會得到 `task/<名稱>` 分支、相鄰的獨立工作目錄，以及一份簡短任務筆記。`new` 預設從 `main` 的已提交版本建立；未提交檔案、資料、虛擬環境不會自動複製。

進入 Codex 後直接給任務即可，例如：

> 讀題目與現有內容，先找出值得推進的建模方向，再把主要方案推導並實作。方法由你選；實驗留給我執行，給我命令即可。

腳本不寫死模型名稱。使用共用執行身分既有的 Codex 模型與權限設定；需要切模型時，在 Codex 內自行選擇。

## 觀看、接手、交接

在另一個 SSH 終端、相同倉庫內執行：

```bash
python3 scripts/team.py list
python3 scripts/team.py watch model             # 唯讀觀看
python3 scripts/team.py take model              # 接手輸入
python3 scripts/team.py note model "推導已完成；下一步接求解器" --by Alice
```

`take` 使用 tmux 的 `attach -d`：會斷開該 session 的**所有其他連線，包括觀眾**，但不會終止裡面的 Codex 或運算。其他人重新 `watch` 即可。這是簡單的交接約定，不是無法繞過的操作者鎖；接手前打聲招呼。

`Ctrl-b`，放開，再按 `d`：離開畫面，保留終端。從 SSH shell 執行 `watch / take`，不要套在另一層 tmux 裡。Codex 結束後會留下 shell，可在原目錄執行 `codex resume` 選取對話；主機重開機則不會保留 tmux 進程。

**預設只在同一 Linux 執行身分下共用。** 不同 UID 不會因為 SSH 到同一台機器就自動共享；跨帳號設定見 [host.md](docs/host.md)。tmux 的 `watch` 只是避免誤輸入，不是秘密資訊的隔離邊界。

## 這個骨架包含什麼

```text
AGENTS.md                    少量共用工作約定
.agents/skills/              modeling / data-analysis / paper-writing / handoff
scripts/team.py              worktree、tmux、共用留言
docs/                        題目簡報、主機說明、工具參考
notes/tasks/                 各任務交接摘要，由 new 建立
src/                         可重用程式
experiments/                 你要執行的實驗入口
notebooks/                   探索性工作
paper/                       論文原稿
figures/                     選用圖表
outputs/                     各 worktree 本機輸出，不進 Git
data/                        本機資料，不進 Git
```

四個 Skills 按需要使用，不必全部載入。Codex 支援根目錄的 `AGENTS.md` 與 `.agents/skills/<名稱>/SKILL.md`；可直接在 Codex 對話中輸入 `$modeling` 等名稱選用。[官方依據](docs/references.md)

沒有固定模型、預設實驗結果、強制完整測試、CI、Git hooks 或自動 push。

## 狀態與成果不要混在一起

`team.py list / note` 的資料放在 Git 共用 metadata 的 `astra-team/` 下，所有 worktree 讀同一份，不需要等 merge。留言是最近一次人工摘要，不表示誰持有控制權。

程式與 `notes/tasks/<任務>.md` 則跟著各自分支；完成後正常 commit / merge。GitHub 不會收到即時看板、Codex 對話或本機輸出。值得保存的結論請放進程式、筆記或論文。

例如合併模型成果：

```bash
# 任務 worktree 中，由有授權的隊員提交相關檔案。
cd "$(python3 scripts/team.py path model)"
git status
# git add <要提交的檔案>
# git commit -m "Implement model"
```

接著在**另一個主要倉庫終端**整合：

```bash
git switch main
git merge task/model
git push origin main
```

`AGENTS.md`、Skills 和 `docs/brief.md` 也透過 Git 整合，不會跨分支即時更新。需要新內容的任務可在自己的 worktree 中合併 `main`；更新 `AGENTS.md` 後重啟 Codex 載入新規則，原有對話可用 `codex resume` 接回。

## 其他常用操作

```bash
python3 scripts/team.py info
python3 scripts/team.py path model
python3 scripts/team.py new alternative --base task/model --goal "另一條模型路線"
python3 scripts/team.py start data
python3 scripts/team.py start paper
```

`start <任務> -- <Codex 參數>` 會原樣轉交參數；已存在的終端不重複啟動。新終端要接回特定對話可用 `start <任務> -- resume <SESSION_ID>`。沒有自動停止、刪分支或清理 worktree 的命令，避免誤刪尚未整合的工作。

倉庫預設不附開源授權；要公開讓他人重用時再加入你選擇的 LICENSE。
