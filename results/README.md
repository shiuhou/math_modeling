# 正式研究證據

依 [modeling.md](../modeling.md) 第 7、9、10 章，這裡保留可受版本追蹤的正式實驗清單、小型指標及重算所需明細。目前保存 [Q1 重算清單](20261014-b-q1-intake-4a8f8f2b/manifest.json) 與九張小型核算表；PASS 限於清單列明的 Q1 計算／圖表檢查，未驗證 Q2 改進器或 Q3 性能。另見 [共用工程驗收](20261014-b-intake-ready/acceptance.json)，包含完整 FCFS／SJF-HOL 基線與 clone 驗收；基線與論文草稿的驗證狀態分開。[manifest.example.json](manifest.example.json) 仍是未運行的格式示例。

本輪 [Q1 論文與交付驗收](20261014-b-q1-publication-42b5a896/manifest.json) 保存兩頁英文／繁中／圖表、180 個每日需求區間、乾淨 clone 與解壓來源重現證據。原九表不重複入庫；全稿格式缺口與人工審閱仍分別記錄。

## 保留位置

- 臨時快取及可再生大型輸出放 [outputs/](../outputs/README.md)，原始資料依 [data 約定](../data/README.md) 管理。
- 正式運行使用 `results/<experiment_id>/manifest.json`；ID 由時間、任務代稱與隨機唯一後綴組成。先確認目錄不存在，再建立新目錄；重跑取得新 ID，不覆蓋舊運行。B 題 Q1 CLI 已拒絕覆蓋輸出；仍未建立通用實驗啟動器。
- 同一目錄保存可授權提交的指標及必要明細；例如逐情境／逐工作結果、約束檢查、求解器終止資訊。清單不能取代這些明細，截圖也不能取代數值資料。
- 大型或私有明細保存在團隊確認的穩定位置，清單記錄相對位置或可分享的識別碼、雜湊及取得方式。不要寫入個人機器絕對路徑、憑證或帶存取 token 的網址。
- 基準、必要對照及有價值的負面結果同樣保留。合併／歸檔前確認程式、配置、環境與證據可追溯；`latest` 或被忽略的本機輸出不能是唯一證據。

## JSON 清單約定 v1

示例的 `null` 表示未知／尚未取得，不代表零、成功或不適用；示例中的空陣列也不代表資料或種子已確認不需要。正式清單使用 `kind: "formal"`，保留以下適用資訊。真正不適用的條件欄位可省略並在 `not_applicable` 寫明原因；未確認的資訊保留未知並記入 `open_items`，不能偽填。

| 欄位 | 內容及條件 |
| --- | --- |
| `schema_version`、`kind`、`experiment_id` | 版本 `1`、`example`／`formal`、唯一運行識別碼；不得把示例改名當結果 |
| `question_or_claim` | 對應子問／主張及題目或任務來源 |
| `code.commit`、`code.dirty`、`code.changes` | 實際完整 commit、是否有未提交變更；有變更時保存 patch 及 SHA-256，另外保存未追蹤但參與運行的程式／配置與雜湊。只有 diff 雜湊而沒有可取得的內容不足以重現 |
| `data` | 適用時逐份列來源、版本／SHA-256、切分、取得方式及授權限制；原始資料不得改寫 |
| `configuration` | 模型／策略及參數、配置檔的可取得位置與版本／SHA-256；命令列覆寫也要記錄 |
| `seeds` | 適用的生成／切分／算法種子及用途；確定性運行在 `not_applicable` 解釋 |
| `command`、`working_directory` | 實際命令（含參數）及相對倉庫根目錄的工作目錄；清除憑證 |
| `environment` | 實際 runtime、套件版本或環境快照位置、OS、硬體、平行度及資源限制；效能比較另分處理／建模／求解／總耗時 |
| `duration_seconds` | 實際總耗時；未運行時為 `null`，不得填估算值冒充實測 |
| `validation` | `status` 為 `PASS`／`FAIL`／`NOT_RUN`／`BLOCKED`；`checks` 逐項附範圍、命令、狀態及證據位置，說明異常和未驗證項。尚未運行不得標為 PASS |
| `solver` | 使用求解器時保存其原始狀態、可行解是否存在、終止原因及可取得的目標／界／gap 與定義、容差；不使用驗證狀態冒充求解器狀態 |
| `results` | 每項指標／明細／日誌／圖表的用途、位置及雜湊；需包含足以重算正式指標的明細與重算入口 |
| `not_applicable`、`open_items` | 不適用欄位及原因；未知資訊、異常、證據缺口與結論限制 |

程式、資料與配置位置以倉庫根目錄為基準；運行產物位置以清單所在目錄為基準。外部保留位置另標 `external` 及存取方式，不能依賴未分享的本機路徑。

這是初始化提出的共用格式，待團隊審閱後供研究任務依賴。`check_repo.py` 目前只檢查 JSON 語法，**通用清單語義驗證器與實驗啟動器尚未建立**；B 題已有限定範圍的 Q1 重算／交接表核查入口。完整欄位、授權、可行性、求解證據與明細是否足夠，仍需任務審閱及將來的研究驗證。

## Q3 第一輪固定分流

[Q3 正式清單](20261015-b-q3-fixed-split-c9e8f1a2/manifest.json) 保存凍結配置、四報告來源／採納表入口、完整 M0/M1 指標、精確恢復與獨立驗證證據。大型原始 ID／實體節點帳本及可取得的來源快照另封裝為本機交付 ZIP，SHA256、重現命令與取得限制在清單中；跨機共享儲存尚未確認。PASS 是當前 trace／假設下的物理可行性與比較可信度，不是相容性或實測速度證明。

## Q3-S2 固定分流敏感性

[Q3-S2 正式清單](20261015-b-q3-s2-fixed-split-v1/manifest.json) 保存五個預先指定情景（5%/20% routing、30/90 donor nodes、sigma=2）、十組 FCFS／SJF-HOL 全 trace 結果、路由子集核對、逐節點獨立回放與 paired comparisons。表格和 donor-capacity 圖位於同一結果目錄；大型新帳本及交付 ZIP 只保留本機相對路徑，跨機共享仍未確認。GO 僅表示這些已驗證條件可納入敏感性分析，不代表全域最佳或硬體性能證明。

## Q3-S3 結論凍結與論文交付

[Q3-S3 出版交付](20261016-b-q3-s3-publication-9ac1d7f2/README.md) 只讀取 S1/S2 已保存的正式 JSON，將第一輪 M1 統一命名為 S0，生成英文 Q3 章節、繁中正文、主表、圖、CSV/JSON 與 claim-to-source map。`new_scheduling_runs=0`；S1/S2 的原始數值、逐節點驗證、原始 CSV、Q1 成果與共用模擬器均未改寫。LaTeX 編譯器在本環境不可用，出版清單保留 `NOT_RUN`；大型 ZIP 的跨機共享仍為 `BLOCKED`。

## Q3-S3 出版勘誤修訂版

[Q3-S3 r3 修訂交付](20261016-b-q3-s3-publication-9ac1d7f2-r3/README.md) 修正 M0/S0 反向 paired evidence、缺欄位語義與 LaTeX 生成；沒有新增排程。舊 S1/S2 結果與 manifest 不變。內建編譯請求未回傳完成 PDF，且 worktree 無本地 LaTeX 編譯器，因此狀態保留 `NOT_RUN`，逐頁檢查也保留 `NOT_RUN`。

## Q3-V2 R-shape bounded study

[Q3-V2 R-shape 結果](20261017-b-q3-v2-shape-a17c4e9d/README.md) 以 `2026-mcm-b-baseline-v1`／`4ee2c6bfa98cf7177ff976abe73b122889437f46` 為基準，固定 60 台 A100 接收節點，完成 FCFS／SJF-HOL × sigma 1/2 四組完整 trace。門檻由正式 node CSV 推導為 16 CPU/GPU；R-shape 保留 10,604 個 V1 hash-selected 作業。獨立 route／逐節點 replay／native timing-placement invariance 均 PASS。sigma=1 不優於 V1 R0；sigma=2 相對同 sigma R0 有固定 trace 的完成時間改善。Candidate B 因現有 `q3.route()` 缺少安全逐到達 callback，標記 `IMPLEMENTATION_DEFERRED`，不報告虛假 full-trace 數字。大型 evidence 跨機交付為 `BLOCKED`。

[Q3-S3 r4 分母修訂交付](20261016-b-q3-s3-publication-9ac1d7f2-r4/README.md) 只修正文生成器與出版數據。S4／90 台的 native A100 全體與正差分受損子群分母、平均新增等待、正延遲總量及群體分位數分開保存；S0／SJF-HOL 相對 M0 的 49,772、4,397、68,183.1825 job-hours 與 P95 變化納入正文。英文正文是 fragment，獨立 wrapper 為 `q3_section_preview.tex`；S1/S2 結果與 manifest 不變。內建編譯因隔離環境無法解析 sibling project files，狀態保留 `NOT_RUN`，跨機大型證據保留 `BLOCKED`。
