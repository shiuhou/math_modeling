# B-Q3 V2 唯一活動記錄

## 基準與範圍

分支 `feat/b-q3-substitution-v2`，基準 tag `2026-mcm-b-baseline-v1`、commit `4ee2c6bfa98cf7177ff976abe73b122889437f46`。保持 V1 的 60 台 A100 接收專區、372 台 native A100、224112 個原始作業、同 node_name 順序、worker CPU/GPU、gang、不可搶占／遷移與 H=7776000。不得修改 main、tag、V1 論文或歷史結果。

## R-shape

R-shape 先套用 V1 eligibility 與 `q3-fixed-split-v1` 10% hash，再以正式節點資料推導 CPU/GPU 容量門檻。60 台 donor 的 `node_info_df.csv` 全為 128 CPU／8 GPU，故門檻為 16 CPU/GPU。V1 10% 路由 11209 個作業；R-shape 固定保留 10604 個，GPU-work 5.5542456%、CPU-work 1.5589017%。這是作業形狀與轉移量同時改變的政策，不能作純比例因果解讀。

四組完整情景已完成：FCFS/SJF-HOL × sigma 1/2。結果與獨立驗證見 [r-shape result](../../results/20261017-b-q3-v2-shape-a17c4e9d/README.md)。sigma=1 相對 R0 的 A10 mean JCT 分別 +68.480449／+3.824872 h，R-shape 不優於 V1；sigma=2 相對同 sigma R0 分別 −69.787858／−5.138963 h，並將 SJF-HOL 相對 M0 的 sigma=2 JCT 從 V1 的退化改為 −3.005438 h，但這仍是固定 trace 結果。

四組 native A100 的逐作業 timing 與 placement 均與同 sigma R0 完全一致；independent verification PASS。短／長×單／多 worker 分層、尾部、positive delay、zero-wait 新延遲、GPU/CPU allocation 與 idle 均已保存。

## Candidate B

`completion-cost` 保留 `IMPLEMENTATION_DEFERRED`。既有 `q3.route()` 是整份 trace 先路由，再呼叫唯一 DES，不能安全宣稱逐到達預測。已保存 `eta=0` 規格、可用／禁止資訊、同時到達 job ID 順序、最小 `route_on_arrival(state, job)` 接口與 scalar example；沒有執行 B 完整 trace。

## 交付與限制

正式小型結果在 `results/20261017-b-q3-v2-shape-a17c4e9d/`；完整 timing／placement 在 ignored local output 與 delivery ZIP，跨機交付 `BLOCKED`。V1 的 M0/S0/S5 schedule 只作同契約已驗證 reference，沒有修改歷史結果。

工程回歸：repo check 309 files PASS；根目錄 12 tests PASS；Problem B 92 tests PASS（含 7 項 V2 R-shape/B deferred 測試）；`git diff --check` PASS。大型 delivery ZIP 僅本機保存，跨機共享為 BLOCKED。
