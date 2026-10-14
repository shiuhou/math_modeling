# 個人電腦設定

目前協作方式是**隊員各自在自己的電腦 clone 倉庫、開任務分支，透過 GitHub PR 整合**。每位隊員使用自己的 GitHub 與 Codex 帳號。首次 clone、開分支與推送命令見 [CONTRIBUTING.md](../CONTRIBUTING.md)。

## 工具與環境

- 安裝 Git，以及執行倉庫檢查所需的 Python 3.10+；倉庫檢查使用標準函式庫，不需安裝研究套件。
- 使用 Codex CLI 時，在自己的電腦安裝、登入後，從任務所在倉庫目錄執行 `codex`。使用桌面應用程式時，開啟自己的 clone 作為專案。
- Codex 安裝及登入方式依 [官方 CLI 文件](https://developers.openai.com/codex/cli) 與 [認證文件](https://developers.openai.com/codex/auth)；帳號、憑證和登入狀態由各自管理。
- 研究套件、求解器與硬體需求待選題確認後記錄，不能把某位隊員的本機環境當作全隊配置。

在自己的倉庫根目錄檢查：

```bash
git --version
python3 --version
python3 scripts/check_repo.py
python3 -m unittest discover -s tests -v
```

目前本地驗證是在 Linux／Python 3.12.3 完成；CI 設定使用 Ubuntu／Python 3.10。完整測試包含舊 `team.py`，該程式使用 Unix `fcntl`，不能宣稱支援 Windows 原生 Python。Windows 隊員可使用 WSL 執行這組命令；macOS、Windows／WSL 的實際驗證尚未完成。

## 跨電腦同步

Git push／pull 同步已提交的程式、配置、文件及可授權的研究證據。本機未提交檔案、虛擬環境、被忽略的 `data/`／`outputs/`、Codex 對話和登入憑證不會同步。

依 [資料約定](../data/README.md) 各自取得已授權資料，核對版本／雜湊；路徑由各自的本機配置提供。正式結果按 [results 約定](../results/README.md) 保留，跨電腦比較時記錄各自環境與硬體差異。

任務狀態透過 Issue／PR 與隨 Git 保存的任務筆記交接。隊員在自己的電腦開啟 Codex 對話，提供任務目標、輸入、範圍、驗收條件及執行授權。

## 舊工具的定位

`scripts/team.py` 是舊共用主機方案留下的 Linux worktree／tmux 工具，目前協作不需要執行 `new`、`start`、`watch` 或 `take`。其 `list`／`note` 僅讀寫該 clone 的 Git metadata，不能跨電腦傳遞留言。程式保留供既有用途，本輪只調整文件，沒有部署共用主機或變更作業系統支援。
