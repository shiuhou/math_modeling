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

## Q3-V2-R1：固定群體後處理（2026-10-18）

起點 `d460fdb348b58085aafd830be84d30f4d8821e9d`，本地與 origin 一致、工作區乾淨；固定 tag 仍為 `4ee2c6bfa98cf7177ff976abe73b122889437f46`。已核對其他 worktree 與程序；不停止或修改他人工作。

執行計畫（沿用唯一活動記錄）：

- 新增 `experiments/analyze_q3_v2_tradeoffs.py`，只讀既有 timing/placement、原始屬性與來源雜湊，不匯入路由器或 DES。先寫配對分母、反向非對稱統計、ID 缺件及離散最大值回歸。
- 新建 `results/20261018-b-q3-v2-r1-6f2c8a10/`：完整主表、雙基線配對、事後離散最大 JCT、集合與工作量、同源英中說明、來源映射與證據交付狀態。
- 核對所有情景的原始固定群體及 native A100 timing/placement；物理 replay 引用既有正式驗證，明示本輪未重新執行 replay 或排程。
- 執行後處理回歸、repo/root/diff checks，保存實際命令與範圍；只 commit/push 本分支並更新 Draft PR #4。Candidate B 保持 `IMPLEMENTATION_DEFERRED`。

初始 PR conflict 檢查：`git merge-tree --write-tree --name-only HEAD origin/main` 指出 `results/README.md`；base `8f2e99ccae31c9559fa726884fda2637d1c0f921`。不解衝突或合入其他分支。新結果直接由本記錄連結，不擴大共享索引改動。

R1 完成：新增 [同源英中補充說明](../../results/20261018-b-q3-v2-r1-6f2c8a10/README.md)、[完整主表](../../results/20261018-b-q3-v2-r1-6f2c8a10/main_table.md)、[事後離散最大值](../../results/20261018-b-q3-v2-r1-6f2c8a10/discrete_worst.md)。10 份既有 timing 形成 30 個固定群體列、66 個明示基線的配對列；本輪零新排程。M0 只共用每政策一份，M0 對兩個 R0 的反向配對直接從 timing 計算，不補零。

兩政策 sigma1 的平均效率均以 R0 較佳；兩離散點的最大 A10 JCT 均以 R-shape 較小。保留兩者，不改無條件預設；不宣稱區間上界、硬體 benchmark、單調性或因果效果。FCFS/sigma2 相對 R0 雖平均改善，仍有 96101 個 A10 較晚完成；SJF-HOL/sigma2 相對 M0 仍有 55465 個較晚完成。

獨立原始屬性、空池可行性算術、hash/shape 集合與逐 ID 配對核查 PASS；兩政策／倍率相同選中集合：R0 11209、R-shape 10604、排除 605（5.397448%），排除者占 R0 原始 GPU-work 44.182249%、CPU-work 84.476354%。native A100 對同 sigma R0 的 timing/placement 完全一致。物理 replay 本輪 NOT_RUN，沿用已雜湊核對的歷史 PASS，未把舊 verifier 的共享路由檢查冒稱獨立路由 oracle。

當前修訂驗證：[verification.json](../../results/20261018-b-q3-v2-r1-6f2c8a10/verification.json)。14 個後處理 tests、12 個 root tests、repo check 及 diff check PASS；未重跑含排程的完整 Problem B suite。測試源碼 hash 與提交前 HEAD 分開保存，不沿用上一輪 91/92 tests 作本輪聲明。舊 results／manifest、q3.py、共用 DES、V1 論文與 raw CSV 未修改。

完整 ZIP 22995288 bytes、SHA256 `797a6ceb7c9dff27992e79264728c92e83cd6f8b85492d38d7b70b6cf1cbdb64`，已核對存在及每個 R-shape 帳本與 archive bytes 一致；LOCAL_ONLY，跨機 BLOCKED。M0/R0 的獨立本機來源列於 manifest，ZIP 不包含這些參考帳本。PR #4 保持 Draft；`results/README.md` 衝突未處理。只推送本任務分支，完成後停止，不開始 B 或聯合實驗。
