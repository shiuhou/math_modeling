# repo-bootstrap

目標：依 [初始化委託](../../codex_repo_bootstrap_prompt.md) 與 [數模規範](../../modeling.md) 補齊團隊入口；不選題或求解。

## 起點與範圍

- 日期：2026-10-14（Asia/Shanghai）。倉庫 `shiuhou/math_modeling`，起點 `main`／`17116759c618af160c570217046d976d4a0a2823`；遠端 HEAD 實際指向 `main`。
- 原本沒有已追蹤檔案修改；使用者提供的 `modeling.md`、`codex_repo_bootstrap_prompt.md` 未追蹤。兩份保留原文，不建立規範副本。
- 本輪本地分支 `chore/repo-bootstrap`；在原工作目錄切分支，沒有搬移或暫存使用者檔案。
- 沿用 `docs/brief.md`、`team.py` 和既有目錄；新增協作模板、正式證據約定與倉庫檢查。結果格式屬待團隊審閱提案。
- 初次初始化交付僅包含本地修改與驗證；後續隊員明確授權 commit 與 push，納入本次提交。遠端 Issue／PR、merge、遠端設定與研究實驗仍未執行，未建立成員或 CODEOWNERS。

## 實際檔案變更

| 類型 | 檔案與用途 |
| --- | --- |
| 修改 | [README](../../README.md)、[AGENTS](../../AGENTS.md)：唯一規範、工作入口及真實檢查 |
| 修改 | [docs/brief.md](../../docs/brief.md)：待確認事項、題目覆蓋、共用介面、依賴與驗證摘要 |
| 修改 | [.gitignore](../../.gitignore)：移除全域 `*.log`，使正式求解日誌可受追蹤 |
| 修改 | [data](../../data/README.md)、[outputs](../../outputs/README.md)、[experiments](../../experiments/README.md) 說明：授權、原始資料、暫存與正式證據的保留位置 |
| 新增 | [CONTRIBUTING.md](../../CONTRIBUTING.md)、[Issue 模板](../../.github/ISSUE_TEMPLATE/research_task.md)、[PR 模板](../../.github/pull_request_template.md)：任務至 PR 的操作流程 |
| 新增 | [results 約定](../../results/README.md)、[JSON 示例](../../results/manifest.example.json)：清單格式及明細保留，未運行 |
| 新增 | [檢查器](../../scripts/check_repo.py)、[檢查器測試](../../tests/test_repository.py)、[團隊工具測試](../../tests/test_team.py)、[workflow](../../.github/workflows/repository-checks.yml)：本地可執行檢查及待遠端執行的 CI |
| 新增 | 本任務筆記：變更、實際驗證及待辦 |

共修改 7 份既有檔案、新增 10 份檔案；另有使用者提供的兩份未追蹤原文，保持不變。既有 `scripts/team.py` 與 Skills 沒有修改。

## 原始文件識別

初始化前讀取的 SHA-256，用於交付時確認原文未改：

```text
modeling.md  54a7d83da7bbb7e55113f9b07d46a2665e10c688cfb0b1c67c93494a79244d31
codex_repo_bootstrap_prompt.md  18c5676cd2e8fb22ca566be09262854792af240d46cd8bf92b6ca83045f4a353
```

## 實際檢查

工作目錄均為本倉庫根目錄 `.`；本地 Linux x86_64、Python 3.12.3、Git 2.43.0。暫存測試案例是工程 fixture，沒有研究運行。

| 命令／檢查 | 狀態 | 證據與範圍 |
| --- | --- | --- |
| `git status --short --branch`、`git worktree list`、`git diff --name-status`、`git diff --cached --name-status` | PASS | 起點只有兩份未追蹤輸入、一個 worktree，沒有既有追蹤修改 |
| `git ls-remote --symref origin HEAD` | PASS | 遠端預設分支 `main`，與本機起點一致 |
| `python3 scripts/team.py --help`、`python3 scripts/team.py list` | PASS | 說明可用，本機尚無任務；未啟動終端 |
| `python3 scripts/check_repo.py` | PASS | 21 份 Markdown／JSON 的本地行內連結及 JSON 語法通過；不驗證錨點、外部網址或清單研究語義 |
| `python3 -m unittest discover -s tests -v` | PASS | 12 項測試通過：有效／缺漏連結、被忽略目標、越界路徑、程式碼區塊、無效 JSON、CLI 失敗回傳、忽略規則及 team 基本行為 |
| `git diff --check`、`git diff -- <本輪修改檔案>`，並讀取所有新增檔案 | PASS | 累計差異已審閱；新檔另核對，不把 git diff 當成包含未追蹤內容 |
| `python3 -`：使用本機既有 PyYAML 解析 workflow 與 Issue frontmatter | PASS | YAML 可解析，觸發事件、唯讀權限與執行命令已核對；非 Actions 執行、未用 actionlint；PyYAML 非倉庫工具依賴 |
| `python3 -`：以 `hashlib.sha256` 對照上列原文雜湊 | PASS | 兩份使用者原文逐位元組不變 |
| `git check-ignore --no-index -z --stdin`（由 Python 傳入探測路徑） | PASS | 本機輸入／暫存被忽略，正式 JSON、CSV、PDF、log 與兩份目錄 README 可追蹤；另有自動化測試 |
| `python3 -`：掃描可提交檔案的常見憑證格式、敏感檔名與個人家目錄路徑 | PASS | 未發現匹配項；檔案內容另經審閱，格式掃描不是完整秘密稽核 |
| GitHub Actions | NOT_RUN | 僅準備 workflow，未推送 |
| 模型／正式實驗／求解器、完整重現 | NOT_RUN | 本輪非研究求解；入口未建立 |

求解器實際狀態：不適用，未呼叫求解器。機器可讀清單只有 NOT_RUN 格式示例，未建立正式結果。

本地測試使用 Python 3.12.3；workflow 設定使用既有工具要求的最低 Python 3.10，該版本及 GitHub runner 尚未實際執行。

## 下一步

本次提交一併納入兩份原始文件。push 成功後，隊員可從 `origin/chore/repo-bootstrap` 建立獨立任務 worktree；初始化經 PR 合併後，改從更新的 `origin/main` 分出。commit／push 的實際結果以 Git 歷史及遠端分支核對；本筆記不預填尚未取得的提交雜湊。

選題、成員與審閱分工、資料授權、研究環境及遠端設定的缺口，集中見 [專案入口](../../docs/brief.md)。後續依其研究依賴順序認領任務。
