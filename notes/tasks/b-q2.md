# B 題 Q2：任務入口與整合決定

> 放置位置：`notes/tasks/b-q2.md`（相對倉庫根目錄）。若此位置已有隊員內容，合併相關章節，不整檔覆蓋。
> 本文件是 Q2 唯一活動任務記錄，不是新研究報告、最終論文或已完成驗收。
> 初始狀態：M0 / M1 / M2 / M3 均 NOT_RUN（指本次任務，不否定倉庫原有驗收）。
> 2026-10-14 查閱的遠端 `feat/b-q2`：`abdbc4ce07c3877ac9fdb1e846a5b9c3b803f401`。開工先重新核對目前 HEAD；不要把此 SHA 當成要求回退的目標。

## 1. 任務目的與邊界

在現有 `problems/2026_gpu_scheduling/` 中擴充 Q2，得到定義清楚、資源合法、預約可獨立驗證的排程器及公平對照。保留 Q1 與 Q3 介面，維持一個正式 DES 與一套共享 evaluator，不把原 ZIP 的過時程式重新啟用為第二套正式引擎。

先閱讀根目錄 `AGENTS.md`、`modeling.md` 的相關範圍、`docs/brief.md`、B 題 README、相關測試，以及 `results/README.md`。目前 repo 沒有另立 SPEC / DESIGN / PLAN，勿為本任務建立一套重複規範。規範的工作方式不代替本任務的研究驗收；本任務明確指定的測試及實驗才是執行範圍。

官方題目與資料契約優先。下列整合決定是本任務提出的工作選擇，並非三份 Pro 文件已完全一致；要與原文分開保存，不能把改動包裝成原作者共同結論。遇到數學錯誤或實质矛盾，提出最小反例、修訂建議，暫停受影響部分，不用實作便利靜默改規則。

## 2. 導入材料：各保存一次，不覆寫原內容

以下相對目的地均以 `problems/2026_gpu_scheduling/` 為根：

| 已提供來源 | 目的地 | 身份 |
|---|---|---|
| `Q2_Algorithm_Audit(1).md` | `docs/q2_algorithm_audit.md` | 原型審查與反例來源 |
| `Q2_Gang_Scheduling_研究設計與Codex規格(2).md` | `docs/q2_algorithm_design.md` | 候選設計、證明条件與偽代碼 |
| `Q2_正式實驗協議(2).md` | `docs/q2_experiment_protocol.md` | 指標、驗收、比較規則的來源 |
| `reconciliation(2).json` | `references/q2_pro_review/reconciliation.json` | 舊 FCFS 橋接與重新評分證據 |
| `cross_checks(1).json` | `references/q2_pro_review/cross_checks.json` | 舊審查／參考核對結果 |
| `full_trace_results(1).jsonl` | `references/q2_pro_review/full_trace_results.jsonl` | 七個原型配置的歷史重跑摘要 |

以上六個原檔的 SHA-256（2026-10-14 對本次上傳 backing files 計算）：

```text
q2_algorithm_audit.md
b4c783ab89315b9c73b1f510ce0420b9b29feeb70901b7eb45b57759ab5245b4
q2_algorithm_design.md
cad596f5c4aa6e770f0e5d6e8fe518a3f666ffa132d8bbdde2df44209c136db7
q2_experiment_protocol.md
d5e5207dff76cc1a72182087ee8f5574c0282620751a03cf1dcd6e40aff54177
reconciliation.json
082f19a9fb135557c8432a42b5ba9004f51aca61f1604512f5795ea303a2c798
cross_checks.json
6892f5d481a0febc674684440231efd1cd63be2877f39480e6c3086ce5c69073
full_trace_results.jsonl
806d37f1de9d99db314c256613cab69912025dd6476c5293ce42af4cfd81f685
```

相同內容已存在時引用原位置，不重複新增。改名不改 bytes；若 Git 換行策略改變工作樹 bytes，分開記錄導入源與工作樹雜湊，不偽報相同。原文內的 sandbox 連結不是 repo 內可用檔案；未取得的證據標明缺少，不假裝連結已轉換完成。

三段「貼上的文字」只作對話摘要，不再導入為三份規格。已有原題、資料、原程式歸檔和研究計算包內容不重複整包匯入。上述 JSON 不進新策略的正式結果表，也不充當程式測試本輪已通過的證據。

審查稿提及 `Q2_Algorithm_Audit_Evidence.zip`；本次提供的六件主材料中沒有該完整包。取得後優先取用 `audit_q2.py`、`cross_checks.py`、`audit_results.json`、manifest 及必要案例；審查用途與可執行安全性先確認，再整合可復用測試。缺包不阻止根據已明寫的反例建立本倉庫測試。

## 3. 已有工程：先復用，不機械修補舊 ZIP

查閱版本的 B 題 README 列出的活動模組：

- `src/gpu_scheduling/data.py`：共用資料讀取與精確 CPU 單位。
- `src/gpu_scheduling/simulator.py`：活動 DES，已有 FCFS 和 SJF-HOL。
- `src/gpu_scheduling/evaluation.py`：共享指標，預設最後提交時刻；名義 90 天可顯式指定。
- `src/gpu_scheduling/validation.py`：獨立節點帳本與小型参考。
- `experiments/run_baselines.py` / `verify_baseline.py` / `make_figures.py`：持久化運行、獨立重讀、圖表入口。
- `references/originals/`：原 ZIP 程式的 inert `.py.txt` 歸檔。

審查中的舊 P0 問題先對照活動程式。已被現有版本消除的問題，保留針對性回歸覆蓋，不重引入舊路徑再修一次。獨立驗證器應保留，不能因「只要一個 DES」而刪除其必要独立性。共享 loader/evaluator 的相容性改動要在 `docs/brief.md` 簡述並與 Q1/Q3 協調。

## 4. M0：資料來源和版本先核對

原 Pro 證據中的 `job_info_clean.csv` byte SHA-256：
`735bc06c3986b1d0c5932236f8685b7204463829118fc6a1d37030e253ed38e1`。

查閱版本的 B 題 README 記錄 repo raw 的 job SHA-256：
`ef14d696adc1b5c7847db49b41a068a998c8cd669e63922c92b3f1c3f32eedb0`。

兩邊 node SHA-256 都記錄為：
`1aba161961a5a4a1a61aa581383c5e5abe3400b59f8597ba8c4eef7597bc9d18`。

這是待核對的 bytes 差異，不等同於資料內容一定錯誤；目前不能推定原因是換行、浮點格式或排序。請使用使用者提供的原始 `2026_MCM_Senior_GPU_Scheduling.zip` 作只讀對照：

1. 記錄當前 repo、分支、HEAD、dirty 狀態與實際輸入 bytes hash；不要只抄 README。
2. 比較官方 ZIP 解出的兩份 CSV 與 repo raw：欄位、行數、唯一 ID、ID 集合和所有輸入欄位。按穩定 ID 對齊後用精確數值比較，避免浮點容差掩蓋差異。
3. 若只有序列化差異，記錄 byte 不同、欄位完全一致的實際證據；可維持現有 raw，後續 run 同時保留兩個來源及等價範圍。
4. 若欄位真的不同，列出最小差異及受影響作業，正式官方 trace 結論暫標 BLOCKED；不得擅自覆寫 raw 或靜默刪改行。一般合成測試可繼續。
5. 若目前環境取不到官方 ZIP，列明缺少的本機輸入；可檢查現有基線與合成案例，但不宣稱 byte 差異已消除。

原 ZIP 只需供執行環境讀取，不要求加入 Git；不憑 repo 中的同名檔案推定其 bytes 與歷史證據相同。

## 5. 本任務採用的整合選擇

這些條目明確解決 Pro B / Pro C 的衝突；來源仍按第 2 節保留。前置碼與合成測試可先做。新候選正式全量比較前，請由研究審查員對本節和相應實作作一次有界審查，再凍結配置。

### 5.1 不變條件

全部官方作業、全部節點，時間零 idle；每 worker 同節點 CPU/GPU、相同 workers 同步開始、執行期間配置固定；duration 提交時已知；型號隔離；不讀未來到達、不改 worker/時長、不做 Q3。

共用精確單作業 worker-slot 判定，CPU=0 省略 CPU 限制。先驗證 0.01 vCPU 表示精度再轉整數；規劃函式不得修改真實資源。正式狀態只有一個權威來源，索引只是等價視圖。

主 Q2 評分显式使用 `horizon_seconds=7776000`；等待/JCT 對全部作業排空後計算。保留 7775878 的歷史相容評分，分開標籤，不改共享 evaluator 預設而影響 Q1/Q3。BSLD 沿用共享定義 `max(1,JCT/max(p,60))`；分位數 linear。

首輪所有策略共同使用 FF-id，按已確認的原始數值型 node_name 排序並成塊放 workers，job tie 使用原始數值型 job_name，不使用 CSV 行號。若發現目前實際 ID 型別不是這一契約，先明示差異並修订，不能臨時把字串 hash 當同一排序。歷史 LIFO/容量排序只用於可定位的核對，不暗中混進主比較。

### 5.2 Timer 與事件順序

候選採精確 `a_j+theta` 提升，並保留 `R_h` 到期履約事件；這不同於 Pro C 原主設定的 event-driven promotion。所有事件合併同一 timestamp，先全部完成、再全部到達、再門檻處理，最後優先履行有效 protected head，再執行普通策略。

比較保護模組時，同一 theta 實驗組的所有對照，包括沒有 urgent 的基線，收到相同的池內 timer 日期集合 `{a_j+theta}`。Timer 在該作業到達後才登記；不因某個策略提早完成該作業就取消比較用 tick，否則不同策略會獲得不同額外重試機會。沒有保護的策略只把 tick 當調度機會，不建立 urgent。全部作業已完成則可結束，不必空跑剩餘 ticks。

同池同 timestamp 只共享一份掃描預算；到達/完成/timer/預約同刻不得反覆重設。其他池事件不觸發此池掃描。到期預約必須處理，版本過時的 guard event 忽略，不撤銷有效承諾。

相同 arrival/completion-only 對照保留為後續 timer 敏感性；自然產生的完成事件隨排程不同是正常差異，不從另一策略偷取完成事件。精確 timer 的額外成本如實記錄。

### 5.3 候選預算

主配置 `K=200`，意義為每池每 timestamp 的後方候選嘗試總數，成功和失敗均計數。普通策略在第一次遇到阻塞前可連續啟動優先前綴；一旦進入繞過阻塞的候選掃描，後续嘗試不能重新標記成 head 以規避 K。同刻重入迴圈、證書更新或有候選成功都不能重置預算。

protected head 的完整可行性與到期啟動不受 K 裁剪；head 啟動後立即處理下一個 urgent。達 K 記為 BUDGET_EXHAUSTED，不宣稱整池不存在可行工作。不以增加隱藏 tick 或無限重試解決預算造成的閒置；量測其影響。

兩次 SAFE_PLAN 放置嘗試算同一個候選檢查，但計算成本中分別計 planner / feasibility / reservation 呼叫數。

### 5.4 保護範圍與方法階梯

EASY 基線：FCFS，鎖定第一個不能立即放置的 head；持久承諾不因新到達或重排取消。它與下述候選不是同一保護範圍。

主候選 C*：普通鍵 SPT `(p,a,id)`，不帶連續 aging 加權；無 urgent 時做有限可行填充。只有最老 urgent 取得 protected 身份，每池至多一個 pending reservation；其餘 urgent 也可以在不延誤 head 時作為安全候選，FIFO 是取得保護次序而非所有啟動必須严格 FIFO。

初期對照階梯（保持排序、放置、theta、K 和 timer 組一致）：

| 描述性標籤 | 保護機制 |
|---|---|
| SPT-FILL | 無預約、無 urgent 保護 |
| SPT-URGENT-HOL | urgent 被阻塞時停止本池後續啟動 |
| SPT-URGENT-TIME | urgent 取得節點級 R；只接納 t+p<=R 的候選 |
| SPT-URGENT-FIXED | 同一 R 加固定節點放置證書，允許安全跨越 R |
| SPT-URGENT-FLEX | 同一 R、可更新未啟動 head 證書；普通放置＋固定證書容量第二次嘗試 |

名稱只是實驗標籤，不宣稱發明新類型。M1 先完成 TIME 保底與單預約核心；FIXED/FLEX 全量研究在 M2 才做。

另以 SGW `(w*q*p,p,a,id)` 替換 SPT 做一組同機制對照。不要把 C* 硬當成 Pro C 全因子表中的 A1+B2；後者可能保護普通阻塞頭，契約不同。先跑有針對性的階梯，不立即啟動 22 配置全因子或多池獨立调參。

### 5.5 預約、快照與安全條件

`R_h` 從當前實際 allocations 投影已知完成、每個完成時間整批釋放後用全池 slot 判定求得。建立後不往後移；可以提早啟動，但不能先撤销舊 promise 再以較晚時間重發。

維護 `current_free` 和针对固定 R 的 `future_free_at_R`。初始 future 已包含所有 `finish<=R` 的預計釋放；到 R 時先整批完成釋放，再履約。現實完成發生時不得再對 future 重複加資源；新啟動且 `finish>R` 才從 future 扣除。每次接納按累積更新後的狀態檢查，不混用「初始 snapshot 減全部回填」與「已扣回填的當前 future」兩種帳法。

TIME：候選目前有完整合法配置且 finish<=R，安全；不使用舊 GPU-count shadow 替代 node-level R。

FIXED：對跨 R 候選，保留 head 證書 Z，在有效容量 `min(current_free, future_free_at_R - Z*d_h)` 上構造完整配置。

FLEX：對某個已確定合法候選配置 Y，檢查扣除 crossing 占用後，所有資源非負且 head slot 總和>=w_h；通過則可以構造新 head 證書，不改 R。第一配置失敗後，可試固定證書有效容量；兩次都失敗只表示有限搜尋未找到，不代表不存在任何安全 Y。實際 commit 必須是已檢查的同一配置，與證書更新原子提交并檢查 state version。

此簡化限每池一個 pending reservation；不擅自推廣到多預約日曆。到期啟動 h 後，按真實运行配置維持資源合法。

### 5.6 參數與聲明

M1 的合成測試用可手算秒數，不為它調 trace 性能。首個歷史錨點候選可明示使用同一 `theta=1350h=4860000s`，所有池共用，並同步用該值生成無保護對照的比較 timers。這不是已校準最優值，也不是最大等待上限。

M2 首輪可預先列 `theta_hours=[24,168,720,1350]` 的有限探索網格；0 和 infinity 只作端點診斷。網格是源設計的建議，不是本次已授權啟動的完整實驗。先凍結與記錄配置，再跑，不按每池、負載、時間段各挑最佳再拼表。

保留 Pro C 的指標與零違規硬验收。其 5%/10%/2x 等性能容忍度尚未由本任務自動採納；未選定前展示精確配對差與实测非支配配置，不報「達成實用性能門檻」。正確性修正不以平均等待必須降低為條件；測得無收益或取捨也是有效研究結果。

**保證的適用條件（規格審查補充）。** 安全推導假設每個 `duration` 正、有限且精確兌現；節點容量及型號固定、無故障；同作業 workers 相同、每 worker 的 CPU/GPU 需求及運行配置固定；沒有額外拓撲限制、未記帳占用或本池第二個未來啟動承諾。所有接納均使用真實狀態、同一受檢配置，並累積更新預約證書。

**有條件最終啟動性（規格審查補充）。** 另要求每個作業在空池單獨可行；到達局部有限；每池共用的 `theta` 有限且固定；只有尚未啟動的等待作業進 urgent，依 `(a,id)` 取得保護，新作業不得取代既有 protected head；protected head 使用全池精確可行性判定，不受 `K` 裁剪；原 promise 按時履行，啟動後立即處理下一個 urgent；事件與時間推進不漏處理、不發生無限內部迴圈。在這些前提下，可主張每個作業最終啟動，但**不能**因此主張 `W<=theta`、所有作業共享固定最大等待、佇列穩定或完全 work-conserving；`theta=∞` 不適用這項 urgent 防飢餓論證。允許安全回填的模型，亦不能直接套用 urgent-HOL 停止後方新啟動所推得的較強排空時間界。

## 6. 執行里程碑：本輪先 M0 + M1

### M0：接手與資料橋接

核對目前 branch/HEAD/dirty 和已有驗收；導入或引用第 2 節材料；完成第 4 節資料核對。沿用 README 的真實測試入口，不從對話猜命令。原型歸檔的 P0 與活動程式逐項對照，只修仍存在的問題。

對歷史 FCFS 差異做必要的橋接或沿用可核對的既有證據，對照相同輸入/placement/tie 的逐作業時刻。不可為逼近 446.970506 或 447.372958 而調參；兩個數字並非新演算法的驗收目標。

### M1：共享引擎、單預約核心與保底候選

不新增第二個正式引擎，將純 planner、commit、預約投影與驗證接到活動 DES；檔案拆分以真實職責為準，不為模板增加空模組。

保留/接入 FCFS-HOL、SPT-HOL、SPT-FILL、SGW-FILL。EASY 先建立正確的單 head 預約核心，時間型版本明名 `EASY-TIME`，不可冒充已支援所有跨 R 安全回填的完整 EASY-NR。完成 SPT-URGENT-HOL 與 SPT-URGENT-TIME 的合成整合測試。

本輪必需测试：

- CPU4/8、CPU127 及真不可行輸入；沒有超配、誤拒絕、負等待或假完成。
- 同刻批次、fractional/zero CPU、gang all-or-nothing，失敗 plan 不改狀態。
- 審查稿 1 節點 CPU 反例、2 節點 GPU 形狀反例，正確 R=10 且 protected head<=10；TIME 拒絕危險跨 R 候選。
- 候選 finish=R 可接受；時間型拒絕某些安全 crossing 是設計保守性，不測成 FIXED/FLEX 的錯。
- 多次接納不破壞原 promise；跨 epoch 不換晚 R；當前與未來資源不重複加減。
- 普通優先與 urgent FIFO 語義；精確門檻位於到達/完成中間；到期 head 不受 K 限制。
- 同 timestamp 預算不重置；相同 timer 組只差被測機制；跨池事件不增加重試。
- 前綴不變性、打亂輸入行仍保持明示 ID 排序結果、同配置重跑 schedule hash 相同。
- 獨立 node ledger，總 GPU/CPU 工作量積分與隊列面積恒等式。

在資料契約成立、單元及 smoke 通過後，本輪明確允許在目前可用且獲授權的環境重跑既有 FCFS / SJF-HOL 完整基線及獨立持久化驗證，顯式 90 天評分，舊 exact-window 另列。不要同時啟動多組耗費資源的基準計時。沒有遠端授權時不登入伺服器、不調驅動、不終止他人的任務。

**M1 到此停止。** 交付可審核 diff、已實際運行的测试/配置/命令和結果、TIME 保底的小型驗證及最小未決事項。不自動啟動 FIXED/FLEX 全量調參、22 格矩陣、Q3、論文性能改寫或大批壓力測試。

### M2：審查後的候選與正式比較（本輪不自動執行）

對第 5 節完成有界規格審查後凍結比較設定。接入 FIXED/FLEX；對各次接受和原 R 承諾進行獨立驗證。EASY-NR 應使用与候選相同安全 planner 能力、但保護 FIFO 阻塞頭，避免拿較保守時間版冒充唯一強回填基線。

依第 5.4 節階梯逐步比較，再做 SPT/SGW 控制變因，最後才考慮另一種 placement。樣本全量运行先通過硬驗收再進主表；不承諾一定勝過 SJF。

### M3：必要敏感性與結果審稿（另行決定）

依凍結結果選少量負載/K/timer敏感性，成本和正確性觀測分時計。完成機制、受益/受損群組、原零等待群組與性能代價分析。Pro 對實際配置、code diff 和证据審核後才整合論文；不擴展 Q3 或不必要學習模型。

## 7. 運行輸出與獨立驗證

沿用 `results/README.md` 的格式，優先擴充現有 `run.json` / manifest，不另起相似的運行框架。必需保留：

- 原始輸入指紋、source commit；dirty 時保存能取得的 patch 和實際未跟蹤參與文件，而非只存 patch hash。
- 完整配置：policy / placement / K 計數規則 / theta 與 timer schedule 規則 / horizon / seeds / 單位 / 環境。
- job_times：全部作業恰一列、狀態清楚、未啟動為缺值而非 0。
- allocations：稀疏 `(job_id,node_id,worker_count)`，連同時刻可以重建容量。
- reservations：不可重用的 promise ID、protected job、issued_time、原 promised R、證書/版本更新、其下接納的 backfill 關聯及最終履約；不能只記 self-reported safe=true。
- metrics / validation / cost：獨立重算，PASS/FAIL/NOT_RUN/BLOCKED/INCOMPLETE/TIMEOUT 按實際行為標示；没有規劃的欄位不填零冒充實測。

獨立驗證器不得調用策略自身 safe() 當證明；從持久化事件和配置重播每節點容量、每個原 promise 及必要中間證書條件。沒有預約的 baseline 標 not applicable，不捏造有預約零違約。

正式小型 manifest、指標與驗證摘要入根目錄 `results/<experiment_id>/`；大型明細按 repo 約定留可取得的穩定共享位置與 hash。暫存可在 `outputs/`，但正式關鍵證據不能唯一存在某人的未共享本機目錄。每次运行不覆蓋前次，保留有意義的負面和失敗證據；不保存每秒完整狀態或無界 debug 日誌。

## 8. 與 Pro 的協作及完成回覆

不需要再開三個寬泛研究對話。現在可讓一個既有 Pro 審查第 5 節，針對 timer、K、urgent-only、promise 持久性、雙快照以及測試規格給出阻塞問題和最小修訂。M0/M1 的資料核對、既有基線驗收、無爭議單預約核心可並行；新候選正式全量比較在規格確認後才做。

Pro 應只更正有證據的問題，不另生一套主方案。M1 之後交給 Pro 的是目前完整提交/實際 diff、相關實作與測試、運行配置、驗證摘要和必要原始明細樣例，而非只有 Codex 的自然語言 PASS。正式結果到手後再審查性能主張，現在不先寫勝利結論。

Codex 本輪完成回覆控制在：修改與未改範圍、實際命令及驗證、資料橋接結論、產物位置、最小阻塞項。維護本文件的狀態與簡短結果區，不另建 summary/handoff/status 多份稿。未獲另行授權，不自動 commit/push/merge、force-push 或操作 main；不覆蓋隊友、不改公開權限或硬體環境。

## 9. 結果區（M1 契約補修後的靜態審查修正，2026-10-14）

- 審查基準：`0add5f1b56caad43048c93b38218b7f0bb1bfe84`；原 M0 與 M1 manifest 保留，未覆寫。
- M1 狀態：COMPLETE（契約補修、定向反例、持久化證據與必要回歸驗收均完成）；可進入 M2 規格審查，不代表 M2 性能實驗已完成。
- arrival-completion-only 已修正為只在到達／完成 epoch 檢查 `t-a >= theta`；shared-timer 仍在精確 `a+theta` tick 提升。兩者共用 urgent FIFO、immutable-R 與既有 K／EASY 同刻語義。
- 反例結果：theta=100 的 R/H/B 在歷史模式由修前 `[0,10,11]` 改為 `[0,10,1]`，H 在 t=1 不會提前取得 urgent。跨過 theta 的案例在歷史模式於下一個 epoch t=7 提升，共享 timer 於精確 t=5 提升。
- `validate_reservations()` 現在要求 `reservations`、`events` 都是顯式 list-of-records；null、缺欄位、錯誤型別、事件與記錄不一致均拒絕。修前 null 會錯誤接受，修後已拒絕。
- Problem B 測試 PASS（26 tests，原 23 個保留並新增 3 個定向測試）；root tests PASS（12）；`scripts/check_repo.py` PASS；`git diff --check` PASS。
- 兩種 event mode 的七 policy／六 GPU pool smoke 及獨立持久化驗證 PASS：`results/20261014-b-q2-m1-age-evidence-01/`，可重取明細在 `smoke-evidence.tar.gz`。
- 與審查基準的 FCFS-HOL／SPT-HOL 回歸 PASS：兩種模式、六池、前 64 jobs、兩個 horizon 共 24 組比較，時刻、放置、事件、預約及 metrics 均一致；證據見 `regression.json`。
- 新正式 manifest：`results/20261014-b-q2-m1-age-evidence-01/manifest.json`。
- 本輪未重跑完整 FCFS/SPT trace；先前完整基線與獨立驗證保留。M2 FIXED/FLEX、22 格矩陣、Q3 及論文性能修改仍未執行。

## 10. M2-A 結果（FIXED／FLEX／EASY-NR，2026-10-14）

- 起點：`960176cc5c45c59553183ac5d1637120d3475ecb`。三份 Pro 規格與三份 JSON 已存在於 `docs/`、`references/q2_pro_review/`，未建立重複規格。
- 新增 policy：`SPT-URGENT-FIXED`、`SPT-URGENT-FLEX`、FIFO-head `EASY-NR`。仍使用同一 DES、FF-id、K=200、單一 pending reservation 及兩種顯式 event mode。
- FIXED 對 crossing 候選使用 `min(current_free, future_free_at_R - Z*demand_h)`；FLEX 先試 current placement、失敗後試 FIXED，更新 head witness 但不延後原 R。證書以稀疏 `certificate_update` 事件記錄 plan、planner、版本鏈、future 增量及 head witness。
- 合成驗收 PASS：TIME 拒絕而 FIXED 可接受；FIXED 拒絕而 FLEX 換 head witness 可接受；累積候選由安全變不安全；`finish=R`；protected head 不受 K；偽造／刪除 certificate update 被獨立 validator 拒絕。
- Problem B 測試 PASS（30 tests）；shared-timer 與 arrival-completion-only 各 10 policy、6 pool、64 jobs/pool smoke 及持久化獨立驗證 PASS。
- A10 中型壓力：4096 jobs、theta=1350h 與 theta=4s 均獨立重播 PASS；summary 記錄 runtime、peak RSS、reservation 數、crossing accepted/rejected、certificate updates 及 hash。theta=4s 前綴沒有 accepted crossing，不能解讀為 crossing 性能結論；crossing 正確性由合成案例驗收。
- 正式證據：`results/20261014-b-q2-m2a-20261014/manifest.json`；大型明細仍在 ignored `outputs/`，沒有每筆 reservation 的密集整池快照。
- 未執行：22 格全因子矩陣、大量調參、完整 trace 的 M2 性能比較、Q3 與論文性能改寫。

## 11. M2-B 結果（證書重播修補與有界成本探針，2026-10-15）

- 基準：`83c7e12476c0b34c2bf7420c29fbf55a528e0fbd`。沿用 M2-A 的唯一 DES、planner、evaluator；沒有重建 M1 或新增第二套模擬器。
- 證書格式修補：每個 promise 保存不可變 `initial_placement_witness`；crossing `certificate_update` 改保存稀疏 `future_delta`，由獨立 validator 按事件／版本鏈累積重播。FIXED 使用更新前 witness，FLEX 才能明確更新 witness；最終 witness 不再被誤當成初始見證。每個更新仍保留 plan、planner、head witness、state version 與 promise 關聯，沒有保存每次完整 future vector。
- 新增 `test_q2_m2b.py` 定向測試：同一 promise 的 FIXED→FLEX、不可變初始 witness、偽造 FIXED、刪除／重排／偽造 delta、R 不變且按時履約、null reservations evidence；與原 M1 測試合計 20 個定向測試 PASS。M2-A 原有的完整 Problem B 測試亦於最終驗收重跑。
- 1350 小時錨點有界探針：A10 前綴 16,384 與 32,768，`FF-id`、`K=200`、`shared-timer`，TIME/FIXED/FLEX 各自獨立 child。六組均獨立 ledger／reservation replay PASS；同一前綴三個 schedule hash 相同，crossing accepted/rejected 與 reservation 均為 0，因此不能宣稱 FIXED/FLEX 有性能收益。16,384 scheduler 約 46.3–47.9 秒、peak RSS 約 193–196 MiB；32,768 約 115.0–117.3 秒、peak RSS 約 280–290 MiB。完整指標（Mean/P95/P99/Max wait、完成數、GPU/CPU 分配率）和成本列於正式摘要。
- 短門檻機制情景：`theta=4s`、A10 16,384、shared timer。TIME child 在約 141 秒時 observed RSS 約 3.0 GiB，仍未完成，已終止本輪自己啟動的 parent／child；短門檻 FIXED/FLEX、完整 224,112 trace 與九策略比較均標記 `TIMEOUT`／`NOT_RUN`。這是目前 validator／事件證據在高 reservation 頻率下的成本阻塞，不是算法不可行或性能結論。
- M2-B 工具：`experiments/run_m2b_benchmark.py` 對每策略分進程；`run_m2a_pressure.py` 補記 scheduler／validation／metrics／I/O 時間與 per-process RSS。大型 job times、allocations、events 留在 `outputs/q2-m2b-bounded-20261014/`（Git 忽略，依摘要 hash 與命令重算）；小型正式清單見 `results/20261015-b-q2-m2b-bounded/manifest.json`。
- 本輪狀態：證書重播修補與定向驗證 `PASS`；錨點前綴 `PASS`；短門檻成本 `TIMEOUT`；完整 trace `NOT_RUN`。下一步應先改善高頻預約／事件重播的時間與記憶體複雜度，再重新做短門檻探針；不啟動 22 格矩陣、Q3 或論文性能改寫。

## 12. M2-C 結果（效能與記憶體擴展性修正，2026-10-15）

- 基準：`ecd46e32ae77eeea065fff5891d5e22eb710fcfd`。只修共享 DES 的等價資料結構、證據保存與獨立 validator；沒有新增調度器、heuristic、RL、MILP 或 Q1/Q3 修改。
- 瓶頸測量：2048-job `theta=1350h` cProfile 顯示 dispatch 反覆 `_ordered()` 排序與 `plan_first_fit()/slots()` 為主要 scheduler 成本；512-job、501 reservations、2,848 events 的舊 validator 約 9.5s，主要耗在每個 promise/certificate 重掃 events 及 pandas `.iloc`。
- Scheduler 修正：每個 dispatch epoch 建立一次 ordered view，透過 waiting-members set 惰性移除已啟動作業；完整 SPT／SGW／FCFS key、FF-id、K、urgent FIFO、timer、R 與事件順序不變。4096 A10 錨點三策略 hash 與舊版相同，單策略 runtime 約 1.63s 降至 1.09s。
- Validator 修正：改為單次事件序列 ledger replay，於 issuance 建立 R future snapshot，於 certificate event 依版本鏈套用 sparse delta；FIXED 使用更新前 witness，FLEX 驗證更新後 witness。512-job／501-reservation 重播約由 9.5s 降至 0.02s；缺失、重排、偽造、legacy schema 仍拒絕。
- Evidence schema `2`：履約後移除 `current_free_initial`、`future_free_initial`、`future_free_at_R` dense vectors，保留 `snapshot_sha256`、immutable initial/final witness、版本、稀疏 delta、promise／履約與事件 ledger。活動中 reservation 仍保留 scheduler 所需 vectors。舊 schema 不靜默轉讀；需重新產生 schema 2 才可由新 validator 回放。
- A：A10、`shared-timer`、`K=200`、`theta=1350h`、FF-id，16,384／32,768 jobs，TIME/FIXED/FLEX 六組 schedule hash 全部與 M2-B 相同。scheduler 由約 46–48s 降至 43–45s（16k），由約 115–117s 降至 106–108s（32k）；candidate checks 不變，RSS 約 198–200MiB（16k）及 280–297MiB（32k）。六組 reservation/crossing 均 0，沒有性能收益主張。
- B：A10、`theta=4s`、4096／8192 jobs，三策略均獨立重播 PASS。4096 hash 與舊版相同；runtime 約 19.35s 降至 2.52–2.58s，RSS 約 539MiB 降至 148–150MiB，241 reservations。8192 完成：TIME 2,530 reservations、0 crossing；FIXED 2,528 reservations、5 crossing；FLEX 2,529 reservations、5 crossing；六次持久化 validator PASS，三者 hash 按策略差異保留，未把 crossing 填成零。
- 子程序控制：`run_m2b_benchmark.py` 新增 `--timeout-seconds` 與 `--max-rss-kib`，監測 `/proc/<pid>/status`，超限 kill 並保存 `*-status.json`／`benchmark.json` 的 `TIMEOUT` 或 `RSS_LIMIT`。用 16-job、1000KiB 上限實際觸發 `RSS_LIMIT`，退出碼 2，未冒充成功。
- 正式證據：M2-C manifest、A/B compact summaries、六份獨立 replay 摘要與 source/data/config hash 見 `results/20261015-b-q2-m2c/manifest.json`；大型明細留在 ignored `outputs/q2-m2c-*`，不覆寫 M2-A 證據。
- 狀態：M2-C validator／queue／evidence 修正 `PASS`；A/B 受控探針 `PASS`；16,384 `theta=4s`、短門檻更大前綴與完整 224,112 trace 仍 `NOT_RUN`／受限。正式 Q2 九策略全 trace 應在後續獨立核准後執行。

## 13. M2-D 結果（正式 A10 比較的受控前綴與停止，2026-10-15）

- 基準：`9d1ade07f1a61f587b32305503460317a9cffc77`；validator 增量修補與 M2-D 工具提交為 `c7c99f7`。保留 M2-C 與原始 M0/M1/M2-A/B 證據，沒有修改 scheduler、placement、evaluator 或 Q1/Q3。
- validator：`validate_reservations()` 以單一 `active_promise_id` 增量追蹤待履約承諾；start event 不再掃描歷史 `contexts.values()`。重疊承諾、缺履約、偽造 FIXED／FIXED→FLEX 更新仍拒絕；同一份有效 schema-2 FIXED→FLEX 證據由修補前後 verifier 均 PASS。Problem B 測試總數 36 PASS。
- 可重現工具：`run_m2b_benchmark.py` 對正式門檻標示 `exploratory-168h`／`historical-anchor-1350h`；`run_m2a_pressure.py` 增加固定分位 duration strata；`analyze_m2d_pairs.py` 以相同 jobs/theta 配對 TIME→FIXED→FLEX，保存等待差、長作業差與原零等待作業新增延遲。
- 資料範圍：原始 A10 為 111,284 jobs、2,494 nodes；raw SHA 沿用 node `1aba161...7bc9d18`、job `ef14d...32eedb0`；horizon `7,776,000` 秒、FF-id、K=200、shared-timer、精確 duration。
- 受控前綴實測：65,536 jobs、`theta=168h`、SPT-FILL 單一子程序完成，scheduler 約 360.13 s、validation 1.57 s、總 runtime 363.70 s、per-process peak RSS 557,120 KiB、35,685,893 candidate checks、0 reservations/crossings；capacity ledger 與 reservation replay PASS，schedule hash `7cc447d9...2a5067`。duration strata 與所有核心 metrics 在正式摘要保存。
- 成本停止：同一前綴 SPT-URGENT-HOL 在 900 s policy timeout 內未完成，RSS 上限未觸發（observed 216,564 KiB）；診斷保存為 `TIMEOUT`。依資源規範停止父程序，未把其餘 65,536 策略、`theta=1350h` 或 111,284 全量結果填成零或估算。
- 正式清單：`results/20261015-b-q2-m2d-01/manifest.json`；壓力摘要 `benchmark.json`、獨立重播 `prefix-65536-604800-spt-fill-verified.json`、超時診斷 `timeout-spt-urgent-hol.json`。大型 job times／allocations／events 仍在被忽略的 `outputs/q2-m2d-prefix-20261015/`，以摘要及雜湊追溯。
- 驗證狀態：repo check PASS、root 12 tests PASS、Problem B 36 tests PASS、git diff check PASS；M2-D 正式比較 `INCOMPLETE`。完整兩門檻六／九策略、TIME→FIXED→FLEX 配對與完整 A10 均 `NOT_RUN`，原因是 65,536 HOL 前綴已顯示目前成本不足以安全展開矩陣。theta=4s 仍僅屬工程壓力情景，不列入主表。

## 14. M2-D protected-HOL fast path（2026-10-15）

- 基準：`91124dfefcd0df68d9d06423b43ccfb60863a00c`；修補提交：`0f2b9b6f`。未重建 DES、未改變 placement／evaluator／Q1/Q3。
- 瓶頸重現：2,002-job 合成 trace 中，SPT-URGENT-HOL 的 protected head 在 reservation 期間不可行；修補前每次事件仍建立完整 `_ordered(waiting, ...)`。cProfile 顯示排序約 1.61 s、`order_builds=3663`。
- 最小修補：pending reservation 且 protected head 仍在 waiting、`current_plan` 不可行時，在排序前直接返回；head 可行時先履約，再回到同一 timestamp 的普通 dispatch。arrival、finish、timer、K、urgent FIFO、FF-id、immutable-R 與 schema-2 evidence 未改變。
- 反例 PASS：大量 waiting／多次 arrival-timer 期間 `protected_hol_blocked=1659`、`protected_hol_fastpath=1659`，`order_builds` 降至 2004，cProfile 的 `_ordered` 累計約 1.63→0.93 s、總模擬 2.85→2.17 s；starts、finishes、plans、promise／events hash 完全一致。另一反例確認 R 履約後同一 timestamp 立即啟動下一個 urgent job。
- A10 4,096／1350h 的 TIME、FIXED、FLEX：三者 schedule hash 均為既有 `ffdc1d15...41fa9df`，獨立 capacity ledger／reservation replay PASS。
- A10 65,536／168h SPT-URGENT-HOL：fast path 後執行 586.155 s，RSS 達 `4,195,872 KiB`，觸發 4 GiB `RSS_LIMIT`；未產生完整 schedule／metrics，沒有提高上限或把它當作 PASS。這表示主要剩餘瓶頸已從 protected-HOL 重複排序轉為高頻 reservation／event／job evidence 記憶體成長。
- 正式證據：`results/20261015-b-q2-m2d-fastpath-01/manifest.json`、`profile-comparison.json`、`a10-4096-verified.json`、`hol-65536-benchmark.json`。完整 168h 六策略、1350h 第二門檻與全量 A10 仍 `NOT_RUN`；本輪停止，不再盲目增加 timeout 或啟動大型重構。

## 15. M2-D RSS 恢復與交付（2026-10-15）

- 本輪基準為本地 `6caebca50d07c0c3f0886b876332275b6eade4c2`；保留未追蹤的 `notes/tasks/b-q2 _newest.md`，不納入提交。既有 validator context 釋放、phase boundary 與 source hash 修補均保留。
- 受控重試為 A10 前綴 65,536 jobs、`theta=604800` 秒（168h）、`SPT-URGENT-HOL`、`shared-timer`、`K=200`、FF-id、90 日 horizon，900 秒／4 GiB RSS 護欄。實際狀態 `PASS`：wall 654.13 秒、scheduler 551.60 秒、獨立 reservation validation 98.58 秒、peak RSS 914,604 KiB、38,253 reservations、314,306 events；schedule hash 為 `42129d2777d68d488cb37469a80275fc16f5c3b140f0846a84a00f2ac5171e18`。
- phase log 顯示 scheduler/capacity 結束 peak 348,608 KiB，reservation replay 結束 peak 348,608 KiB，metrics 結束 peak 348,608 KiB；process peak 914,604 KiB 出現在 persistence/write 階段。因此不能把本次峰值歸因於 scheduler 或 validator。完整 phase、source/data hash 與命令見 `results/20261015-b-q2-m2d-rss-01/manifest.json`。
- 獨立持久化驗證 `PASS`：`a10-65536-spt-urgent-hol-verified.json` 的 capacity replay 與 reservation replay 均通過。A10 4,096／8,192、theta=4s 的 TIME/FIXED/FLEX 小型 schedule/event hash 回歸與獨立 replay 均 `PASS`；Problem B 測試 43 個、root tests 12 個、repo check 與 `git diff --check` 均 `PASS`。受控 kill 探針保留為 `TIMEOUT` 診斷，不冒充成功。
- 本次只完成單一 HOL 壓力恢復，完整 M2-D 仍為 `INCOMPLETE`、GO/NO-GO 為 `NO-GO`：六／九策略矩陣、`theta=1350h`、111,284-job 全量比較與 TIME→FIXED→FLEX 配對尚未執行。下一個最小阻塞是於同一資源護欄下完成其餘凍結策略，或取得分階段執行核准；不在本輪補跑。

## 16. M2-D 65,536 前綴策略比較（2026-10-15）

- 本輪基準：`5cb1827520cdee30fe41ea5d3a0d5f8bb4fa8116`。固定 A10 前 65,536 jobs、`theta=604800s`（探索性 168h）、`shared-timer`、FF-id、K=200、90 日 horizon；每個策略獨立子程序，900 秒／4 GiB RSS 護欄，沒有並行昂貴程序。
- SPT-FILL 與 SPT-URGENT-HOL 的已完成證據保留：前者來自 `c7c99f7`、schedule hash `7cc447d9...2a5067`、363.70s／557,120 KiB、0 reservation，獨立 ledger/replay PASS；後者來自 `6caebca`、schedule hash `42129d27...5171e18`、653.53s／914,604 KiB、38,253 reservations、crossing accepted=0，獨立 capacity/reservation replay PASS。兩者版本不同，未宣稱同 commit 嚴格配對。
- 本輪新跑的 SPT-URGENT-TIME、SPT-URGENT-FIXED、SPT-URGENT-FLEX 全部在 scheduler 階段 `TIMEOUT`，不是 RSS_LIMIT：分別約 900.05s／230,732 KiB、900.02s／228,100 KiB、900.02s／226,612 KiB；停止時已到達全部 65,536 jobs，但約完成 45,723／45,740／45,336 jobs，未產生完整 job_times、allocations 或 reservations 可供獨立重播，因此 verification=`NOT_RUN`，不填主指標。
- 額外 gang-starvation 診斷已加入 `experiments/analyze_gang_starvation.py`，只讀完成的 job-times。SPT-FILL 的短單 worker（n=51,141）mean/p99/max wait=0.043/0.348/2.804h；短多 worker（n=283）=58.652/453.539/915.247h；長多 worker（n=122）=361.813/1509.567/1547.932h。URGENT-HOL 對應為 548.020/1163.483/1172.242h、1042.813/1167.675/1170.860h、905.167/1172.092/1172.427h。跨版本 pair 僅作診斷，未作嚴格策略性能結論。
- TIME→FIXED→FLEX 配對與 crossing 接納比較 `NOT_AVAILABLE`；沒有兩份完整、同配置 job timing。1350h、完整 111,284-job trace、其餘九策略矩陣均 `NOT_RUN`。正式 manifest：`results/20261015-b-q2-m2d-65536/manifest.json`；三份 timeout benchmark 與 phase log 位於對應 `outputs/q2-m2d-formal-65536-20261015-spt-urgent-*`。
- 停止判定：M2-D 仍 `INCOMPLETE`，下一步完整 A10 比較 `NO-GO`。最小阻塞是降低已實測 scheduler 成本或取得明確不同的資源護欄；不能把部分完成數據推算成全量結果，也不在本輪啟動新型 scheduler、Q3 或論文改寫。

## 17. M2-E 結果（有界 scheduler 診斷與比較恢復，2026-10-15）

- 基準 `8da62ad4ff5c68d1fb730e04c94cd0492e37614f`；核心等價優化提交 `7d5d26b1ecd79303ca482a35377e7d5817c9c532`。保留第 13–16 節失敗與恢復證據，未覆寫 `_newest`，未修改 Q1/Q3、validator、placement、evaluator 或 protected-HOL fast path。
- 熱點證據：原 16,384-job、168h 的三個 backfill policy cProfile 顯示 current placement 累計約 55–57s（其中 slots self 約 40–41s），排序約 13s、reservation 建立約 0.6s、list remove 約 0.05s。每次 top-level dispatch 對應一個 event epoch，沒有觀察到同 timestamp 重複呼叫；內部同刻重試仍維持既有 K。完整分類見 `results/20261015-b-q2-m2e-01/hotspots.json`，巢狀 cumulative times 不相加。
- 最小修補：純 current FF-id plan 依 `(GPU, CPU units, workers)` 快取（含不可行），每次真實 allocation／completion release 均清空；future snapshot／安全檢查／證書不快取。每 job 的完整不可變 priority tuple 只計算一次。沒有改變排序鍵、urgent FIFO、theta、K、R、gang 或 TIME/FIXED/FLEX 接納條件。16k TIME 未插 profiler 的 scheduler 由 64.55s 降至 10.80s（單次量測約 5.98 倍）；不把 profile 與 non-profile 時間混作精確加速比。
- 等價驗收 PASS：官方 16k 三策略的 starts/finishes/allocations、全部 promises/events 完全相同；官方 32k TIME 與 8192/theta4 三策略的 schedule/event/reservation hash 均相同。8192 機制情景 FIXED/FLEX 各有 5 crossing，不能只用零 crossing 驗等價。45 個 Problem B 測試含九策略、兩種 event mode 的 cached/uncached 完整比較，12 root tests、repo checks 與 diff check PASS。未新增第二套正式 DES。
- 中等規模主比較：同一 `7d5d26b` core、A10 全原始節點、原始 16,384／32,768 前綴、theta604800、shared-timer、K200、FF-id、H7776000、完整排空；10/10 子程序及持久化 capacity/reservation replay PASS。16k 五策略 schedule 相同，urgent 各 224 promises、crossing=0，不推論 FLEX 無價值。32k FILL/HOL/TIME/FIXED/FLEX mean wait 分別為 15.380/98.054/65.657/65.630/65.588h，reservation=0/6846/2575/2579/2576，crossing=0/0/0/30/49；scheduler=31.13/41.33/62.14/68.95/74.12s，峰值 RSS 約 315–376 MiB。
- 32k 配對：TIME→FIXED 改善 2481、惡化 140，mean delta=-0.02726h；TIME→FLEX 改善 3269、惡化 107，mean delta=-0.06921h，兩者原零等待新增延遲均 0。但 Max wait 由 TIME587.678h 升至 FIXED588.706h／FLEX591.661h，不能宣稱全面優勢。
- gang 機制：32k 短單 worker n=25662、短多 worker n=31、長多 worker n=35。FILL 三組 mean=0.030/41.288/118.662h；HOL=91.980/348.231/439.230h；TIME=50.753/305.925/438.310h。FIXED/FLEX 對短多 worker 幾乎無改善，長多 worker 略惡化。僅支持本前綴／探索性168h 的阻塞代價診斷，不作一般因果或最優性結論，不引用 Claude 原型數字。
- 65,536 恢復：中型正確性與等價成本證據支持先單獨 TIME 探針（`expansion-decision.json`）；TIME 實測 475.77s、peak819220KiB、19415 promises，持久化 replay PASS，故依 `expansion-followup.json` 逐一執行其餘四策略，仍每 child900s／4GiB。其餘四策略均完成，五策略持久化獨立 replay 全 PASS；完整 A10 仍未執行。
- 正式入口：`results/20261015-b-q2-m2e-01/manifest.json`、`commands.sh`、`comparison-16384.json`／`comparison-32768.json`、`pairs-32768.json`；完整 timing、allocation、schema2 events/promises 與 paired 明細壓縮保存在同目錄 `evidence-*.tar.gz`，`archives.json` 記 SHA256 並逐 archive member byte 驗證，不只留 ignored outputs。
- 完整111284-job A10／1350h第二門檻／九策略矩陣 NOT_RUN；不提高成本護欄、不實作 Mice Lane/RL/LP、不改論文性能結論。

### 17.1 65,536-job 同版本恢復結果

- 五策略均採相同 `7d5d26b` core 和官方輸入／契約，全部子程序在原900s／4GiB內排空，並由持久化檔案獨立重播 PASS。以下 waiting 單位為小時，allocation 為90天窗口的分配率，非 demand；完成數也固定90天窗口。

|策略|Mean / P95 / P99 / Max wait h|90天完成|GPU / CPU allocation|reservations / crossing / updates|scheduler / validator / I/O s|peak MiB|
|---|---|---|---|---|---|---|
|SPT-URGENT-TIME|350.528/1142.534/1160.951/1172.021|59030|0.999568/0.192678|19415/0/0|419.26/53.10/2.86|800.0|
|SPT-URGENT-FIXED|350.088/1142.474/1160.939/1172.027|59046|0.999569/0.192678|19419/62/62|449.50/53.51/2.96|795.3|
|SPT-URGENT-FLEX|349.715/1142.399/1160.881/1172.027|59069|0.999570/0.192678|19424/133/133|480.99/51.88/2.83|796.4|
|SPT-FILL|31.042/61.662/1254.218/1860.190|63403|0.988490/0.180874|0/0/0|71.56/1.78/2.12|545.2|
|SPT-URGENT-HOL|556.492/1153.620/1164.255/1172.427|54649|0.999338/0.192659|38253/0/0|317.32/99.14/2.98|893.0|

- TIME 配對：SPT-URGENT-FIXED mean delta -0.43923h，改善9504／惡化10096／原零等待新增延遲8；SPT-URGENT-FLEX mean delta -0.81254h，改善14207／惡化8207／原零等待新增延遲11；完整尾部、長作業與各群組配對見 `comparison-65536.json` 和 `pairs-65536.json`，不以平均值取代尾部代價。

|策略|短單 worker n / Mean / P99 / Max h|短多 worker n / Mean / P99 / Max h|長多 worker n / Mean / P99 / Max h|
|---|---|---|---|
|SPT-URGENT-TIME|51141/284.482/1159.869/1172.021|283/987.748/1161.407/1170.358|122/904.851/1171.863/1171.913|
|SPT-URGENT-FIXED|51141/283.919/1159.714/1172.027|283/987.768/1161.436/1170.365|122/904.856/1171.868/1171.913|
|SPT-URGENT-FLEX|51141/283.408/1159.559/1172.027|283/993.538/1161.429/1170.365|122/904.856/1171.869/1171.913|
|SPT-FILL|51141/0.043/0.348/2.804|283/58.652/453.539/915.247|122/361.813/1509.567/1547.932|
|SPT-URGENT-HOL|51141/548.020/1163.483/1172.242|283/1042.813/1167.676/1170.860|122/905.167/1172.092/1172.427|

- 本輪中型與65,536核心五策略比較 COMPLETE/PASS；EASY-NR、其他強基線、第二門檻與111,284-job全量 NOT_RUN，原M2-D完整研究仍 INCOMPLETE。65,536規模 GO 已獲實測支持；下一步完整 A10 多策略矩陣目前 NO-GO（未證明全量900s成本，65k→全量不作線性保證）。下一個最小工作為另行授權的單策略全量成本門檻探針，或先以已驗證65k做方法取捨；本輪不啟動。

- 方法取捨：本設定 TIME 相較 HOL 改善 38,700 個作業且無配對惡化；但相較 FILL 平均等待更高。FIXED/FLEX 雖真實接納62/133個crossing，平均等待只比TIME改善約0.125%/0.232%，新增受損作業10096/8207、原零等待新增延遲8/11，故目前不推薦以性能優勢為由取代TIME作預設。這不否定其安全正確性，也不外推至其他theta或完整trace。
