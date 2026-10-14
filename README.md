# Astra Modeling Team

`shiuhou/math_modeling` 由隊員各自在自己的電腦 clone，按任務分支與 GitHub PR 協作。目標是讓題目、推導、程式、實驗證據與論文可以互相核對。

目前階段：**Problem B Q1 修正版整合**。原題與兩個 CSV 已核對，Q1 已重算；此分支未整合或驗證 Q2/Q3 演算法。題目程式、狀態與重現命令見 [B 題唯一入口](problems/2026_gpu_scheduling/README.md)。隊員分工、資料公開範圍與正式環境待確認。

## 從這裡開始

1. 閱讀唯一數模規範正文 [modeling.md](modeling.md)；Agent 入口是 [AGENTS.md](AGENTS.md)。
2. 查看 [專案現況、題目覆蓋與共用介面](docs/brief.md)，以及相關的 [任務筆記](notes/tasks/)。
3. 按 [CONTRIBUTING.md](CONTRIBUTING.md) 認領短期任務、在自己的 clone 開分支、驗證並準備 PR。

[初始化委託原文](codex_repo_bootstrap_prompt.md) 保留作本輪範圍依據，不是另一套日常研究規範。

## 現在可執行的檢查

倉庫檢查使用 **Python 3.10+ 標準函式庫與 Git**，無需安裝研究套件。每位隊員在自己的電腦準備環境並登入自己的 GitHub／Codex 帳號，見 [個人電腦設定](docs/host.md)。完整測試包含舊 Linux 工具，目前只在 Linux 驗證；其他平台狀態見該文件。B 題研究套件與本機版本見 B 題入口；全隊正式環境待確認。

在倉庫根目錄執行：

```bash
python3 scripts/check_repo.py
python3 -m unittest discover -s tests -v
git diff --check
```

`check_repo.py` 檢查 Git 已追蹤及尚未被忽略的新檔案：行內 Markdown 連結的本地路徑，以及 JSON 語法（拒絕重複鍵與非有限數值）。它不查外部網址、頁內錨點、reference-style 連結、題目內容或實驗清單的研究語義。倉庫文件請使用可檢查的行內相對連結。

測試涵蓋檢查器的有效／無效輸入、CLI 失敗回傳、Git 忽略效果及既有協作工具的基本行為；不啟動 Codex、tmux 或建模實驗。[GitHub Actions](.github/workflows/repository-checks.yml) 執行相同倉庫檢查與測試；本地通過不代表遠端 CI 已執行。實際驗證狀態見 [專案摘要](docs/brief.md)。

## 目錄職責

| 位置 | 用途 |
| --- | --- |
| [docs/brief.md](docs/brief.md) | 唯一專案入口：選題、覆蓋、介面、依賴與驗證摘要 |
| [CONTRIBUTING.md](CONTRIBUTING.md)、[任務模板](.github/ISSUE_TEMPLATE/research_task.md)、[PR 模板](.github/pull_request_template.md) | 認領、審閱與整合 |
| [scripts/](scripts/)、[tests/](tests/) | 倉庫檢查及既有團隊工具；工程行為測試 |
| [src/](src/)、[experiments/](experiments/)、[notebooks/](notebooks/) | 可重用研究程式、實驗執行入口、探索；B 題實作集中於 problems/2026_gpu_scheduling |
| [data/](data/README.md)、[outputs/](outputs/README.md) | 本機原始資料與可再生暫存；內容預設不進 Git，B 題沿用既有已追蹤 raw CSV |
| [results/](results/README.md) | 可追蹤的正式清單、指標及必要明細；已有 Q1 重算表及清單，完整論文仍未驗證 |
| [paper/](paper/draft.md)、[figures/](figures/) | 論文工作稿與選用圖表；寫作工具待確認 |
| [notes/tasks/](notes/tasks/) | 隨 Git 保存的任務交付摘要；已有 Issue 時引用其狀態 |
| [.agents/skills/](.agents/skills/) | 按需要選用的工具，不固定成員角色 |

## 第一次 clone 與開任務

在自己的電腦執行，把 `task-slug` 換成實際任務名稱：

```bash
git clone https://github.com/shiuhou/math_modeling.git
cd math_modeling
git switch -c feat/task-slug
codex
```

已有 clone 的隊員，先保存目前任務並確認工作目錄乾淨，再切回 `main`、執行 `git pull --ff-only origin main`，從最新主線開新分支。提交、推送及 PR 步驟見 [協作流程](CONTRIBUTING.md)。

各自的 clone 已隔離工作目錄，不要求額外 worktree 或 tmux。`scripts/team.py` 是保留的舊共用主機工具，不用於目前跨電腦協作，其留言也不會隨 Git push 同步。

研究方法保持開放，實驗預設由隊員執行。Git 提交、推送、PR 與合併依任務授權進行；各步驟分別記錄實際執行狀態。
