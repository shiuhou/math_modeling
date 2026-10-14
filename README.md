# Astra Modeling Team

`shiuhou/math_modeling` 是按任務分支與獨立 worktree 協作的數學建模研究倉庫。目標是讓題目、推導、程式、實驗證據與論文可以互相核對。

目前階段：**倉庫初始化**。選題、隊員分工、資料授權及正式運行環境待確認；題目原文尚未取得核對。模型、正式實驗、指標重算及論文建置入口均未建立。手冊中的 A／B 題附錄不表示團隊已選題。

## 從這裡開始

1. 閱讀唯一數模規範正文 [modeling.md](modeling.md)；Agent 入口是 [AGENTS.md](AGENTS.md)。
2. 查看 [專案現況、題目覆蓋與共用介面](docs/brief.md)，以及相關的 [任務筆記](notes/tasks/)。
3. 按 [CONTRIBUTING.md](CONTRIBUTING.md) 認領短期任務、建立獨立工作目錄、驗證並準備 PR。

[初始化委託原文](codex_repo_bootstrap_prompt.md) 保留作本輪範圍依據，不是另一套日常研究規範。

## 現在可執行的檢查

倉庫工具使用 **Python 3.10+ 標準函式庫與 Git**，無需安裝研究套件。現有 `team.py` 的 worktree／tmux 功能面向 Linux；開啟共用終端另需 tmux 與已授權的 Codex CLI，設定見 [主機說明](docs/host.md)。這些工具不代表研究環境已配置。

在倉庫根目錄執行：

```bash
python3 scripts/check_repo.py
python3 -m unittest discover -s tests -v
git diff --check
python3 scripts/team.py list
```

`check_repo.py` 檢查 Git 已追蹤及尚未被忽略的新檔案：行內 Markdown 連結的本地路徑，以及 JSON 語法（拒絕重複鍵與非有限數值）。它不查外部網址、頁內錨點、reference-style 連結、題目內容或實驗清單的研究語義。倉庫文件請使用可檢查的行內相對連結。

測試涵蓋檢查器的有效／無效輸入、CLI 失敗回傳、Git 忽略效果及既有協作工具的基本行為；不啟動 Codex、tmux 或建模實驗。[GitHub Actions](.github/workflows/repository-checks.yml) 執行相同倉庫檢查與測試；本地通過不代表遠端 CI 已執行。實際驗證狀態見 [專案摘要](docs/brief.md)。

## 目錄職責

| 位置 | 用途 |
| --- | --- |
| [docs/brief.md](docs/brief.md) | 唯一專案入口：選題、覆蓋、介面、依賴與驗證摘要 |
| [CONTRIBUTING.md](CONTRIBUTING.md)、[任務模板](.github/ISSUE_TEMPLATE/research_task.md)、[PR 模板](.github/pull_request_template.md) | 認領、審閱與整合 |
| [scripts/](scripts/)、[tests/](tests/) | 倉庫檢查及既有團隊工具；工程行為測試 |
| [src/](src/)、[experiments/](experiments/)、[notebooks/](notebooks/) | 可重用研究程式、實驗執行入口、探索；目前未實作模型 |
| [data/](data/README.md)、[outputs/](outputs/README.md) | 本機原始資料與可再生暫存；內容預設不進 Git |
| [results/](results/README.md) | 可追蹤的正式清單、指標及必要明細；目前只有格式示例 |
| [paper/](paper/draft.md)、[figures/](figures/) | 論文工作稿與選用圖表；寫作工具待確認 |
| [notes/tasks/](notes/tasks/) | 隨 Git 保存的任務交付摘要；已有 Issue 時引用其狀態 |
| [.agents/skills/](.agents/skills/) | 按需要選用的工具，不固定成員角色 |

## 既有共用終端工具

`python3 scripts/team.py --help` 可看完整操作。`new` 建立按任務命名的 `task/<任務>` 分支與相鄰 worktree，預設從本機 `main` 的**已提交版本**分出；未提交文件、資料和虛擬環境不會自動複製。`task/` 保留為既有工具的相容命名，手動 Git 任務使用 `feat/`、`fix/`、`docs/`、`chore/` 即可。

`list`／`note` 共用留言存在 Git metadata 中，不會上傳 GitHub，也不取代 Issue 或長期成果。`watch` 唯讀觀看，`take` 接手並斷開同 session 其他連線；先和操作者打招呼。主機配置與限制見 [docs/host.md](docs/host.md)，工具參考見 [docs/references.md](docs/references.md)。

研究方法保持開放，實驗預設由隊員執行。Git 提交、推送、PR 與合併依任務授權進行；各步驟分別記錄實際執行狀態。
