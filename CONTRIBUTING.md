# 按任務協作

數模原則以 [modeling.md](modeling.md) 為準；題目、共用介面與研究依賴集中在 [docs/brief.md](docs/brief.md)。目前已核對遠端預設分支為 `main`，採用 `main` → 短期任務分支 → PR 的流程。

## 認領與分出工作目錄

每個任務指定一名主要負責人，寫清可檢查的完成條件及審閱者；人選未確認時明示待確認。使用 [研究任務模板](.github/ISSUE_TEMPLATE/research_task.md)。已有 Issue 就引用其編號與連結，不再在專案文件抄寫相同狀態；未使用 Issues 時，將任務範圍與交付摘要保存在 `notes/tasks/`。

開始前讀相關入口並執行：

```bash
git status --short --branch
git worktree list
python3 scripts/team.py list
```

多人並行使用各自的 clone 或獨立 worktree，不共用可變的工作目錄。同名分支／目錄已存在時先檢查；不覆蓋、不重設、不自動 stash 隊友修改。

以下是初始化成果整合後的**操作示例，並非本輪已執行**。以實際任務名稱取代 `task-slug`，先確認目標路徑未被使用：

```bash
git fetch origin
git worktree add -b docs/task-slug ../math_modeling-task-slug origin/main
cd ../math_modeling-task-slug
git status --short --branch
```

按任務使用 `feat/<task>`、`fix/<task>`、`docs/<task>`、`chore/<task>`；不建立每人永久分支。有真實 Issue 編號時可加入名稱，不虛構編號。既有 `team.py new <任務> --base origin/main` 會建立 `task/<任務>`，可繼續使用；它不自動 fetch，也不帶入未提交檔案。由其管理的任務才使用 `start`／`watch`／`take`，詳見 [主機說明](docs/host.md)。

## 修改與共同介面

- 開始前確認負責的檔案範圍及依賴；同一檔案重疊修改時先協調。接手同一終端前先打招呼。
- 欄位、單位、切分、決策可用資訊、指標、模型輸入輸出或結果格式變更，先在專案入口提出具體版本與受影響任務，經審閱確認後再讓其他任務依賴。loader、評分器與成本公式沿用共用實作。
- 本地檢查按改動範圍執行。推導、模型、資料及正式比較的驗證依手冊第 3–8 章；純文件修改不需建模實驗。
- AI 協作記錄實際使用工具、用途、受影響產物及人工核對狀態；原始題目與 AI 披露規則尚未核對時明示。參照手冊第 11 章，不把 Agent 產出當成已核實結論。

## 驗證與準備 PR

在任務 worktree 根目錄執行相關檢查，完整的倉庫檢查入口如下：

```bash
python3 scripts/check_repo.py
python3 -m unittest discover -s tests -v
git diff --check
git diff
git status --short
```

`git diff` 不顯示未追蹤檔案內容，須一併開啟審閱。檢查範圍見 [README](README.md)。記錄命令、工作目錄、`PASS`／`FAIL`／`NOT_RUN`／`BLOCKED`、證據位置及限制；求解器實際狀態另列，不用檢查通過替代最優性證明。

使用 [PR 模板](.github/pull_request_template.md)，只填適用項。經任務授權後，選擇性 `git add` 經審閱的檔案、commit、push **任務分支**，在 GitHub 對 `main` 準備 PR。不要直接把任務合併或推送到 `main`。合併由獲授權的整合者在審閱與相關檢查後處理。

審閱者依影響核對假設、資料、模型、指標與論文的一致性，檢視實際證據及未驗證項。程式缺陷補有意義的回歸測試；文件小改動不強制重跑整套研究。CI 只執行公開且無需私人資料的倉庫檢查；遠端是否執行及結果須到實際 PR 核對。

## 保留與整合

正式運行使用唯一 ID 和獨立輸出位置，依 [results/README.md](results/README.md) 保存清單及足以重算指標的必要明細。大型或私有資料只記錄已確認且可授權存取的位置、版本及取得方式；不把原始資料加入 PR。

合併或歸檔前，確認必要程式、配置、環境與正式研究證據已有可追溯保留位置（手冊第 7、9、10 章）。基準、必要對照與有價值負面結果保留；不把 `outputs/` 或即時留言當唯一證據。清理 worktree／分支前確認內容已整合且屬授權範圍，不自動批量刪除。

## 遠端設定待確認

成員帳號、主要負責人及審閱分工未提供，暫不建立 `CODEOWNERS`。建議由管理者確認 PR 審閱要求、Actions 權限及 `main` 分支保護；待首次遠端 workflow 真實成功後，再核對檢查名稱是否可設為必需。以上是建議，未核對或修改 GitHub 保護、權限及可見性。
