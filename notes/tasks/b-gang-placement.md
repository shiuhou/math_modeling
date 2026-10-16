# GS1 異質節點 placement v2

## 範圍與基準

本任務只研究 `GPU-series-1` 的一個資源形狀感知 placement 候選，沿用唯一 DES、FCFS-HOL／SPT-HOL 排隊規則、shared-timer、`theta=604800` 秒、同刻先完成再提交、初始全空閒及完整排空。基準為 tag `2026-mcm-b-baseline-v1`、commit `4ee2c6bfa98cf7177ff976abe73b122889437f46`。沒有改 scheduler、優先序、跨 GPU 替代或 V1 論文。

## 候選定義

對節點 `i` 與每 worker 作業 `j`：

`R_i = CPU_i / GPU_i`，`rho_j = cpu_j / gpu_j`。

目前可用 worker slots 使用真實整數資源：

`s_ij = min(floor(free_gpu_i / gpu_j), floor(free_cpu_i / cpu_j))`，`cpu_j=0` 時忽略 CPU 項。只有 `s_ij>0` 的節點進入排序；先取 `R_i >= rho_j`，依 `R_i-rho_j` 由小到大，再按 node id；不足時接著取 `R_i < rho_j`，依 `R_i` 由大到小，再按 node id。比例只排序，不刪除低比例但仍可行的節點。整個 gang 必須完整建構後才提交。

程式以整數交叉乘積比較比例，沒有浮點門檻。FF-id 是預設路徑；placement cache key 包含策略、節點順序及需求，任何 allocation/release 都失效。

## 數學定位與反例

在相同 worker、沒有額外 affinity 的模型中，單一作業當下可行，當且僅當 `sum_i s_ij >= worker_num_j`；這是 worker-slot 總和條件，不能把節點比例當成可行性定理。比例候選的作用是優先保留高 CPU/GPU 形狀節點給高 CPU 作業，並非保證全域最優。

三個最小反例（可由 `plan_ratio_matching` 手算）：

1. 一個低 CPU 作業先占高 CPU/GPU 節點，會讓後到的高 CPU 作業在其它節點不足時等待；比例排序把低 CPU 作業導向形狀較接近的節點，保留高 CPU 節點。
2. 比例排序不是 FF-id 的支配策略：若高比例節點的剩餘容量只容納一個 worker，而低比例節點可容納完整 gang，排序可能造成後續形狀需求較差；因此保留第二組 fallback，且不宣稱一般最優。
3. GPU 總量足夠不代表可行：兩個節點各有一張 GPU，但 CPU 各不足以承載一個高 CPU worker，`sum_i s_ij=0`。

若某 trace 出現零等待，只能稱為該實例的一份零等待構造，不能推廣為一般實例最優。

## 凍結矩陣與結果

入口：`python experiments/run_gs1_placement_matrix.py --data data/raw --out results/<run> --theta-seconds 604800`。

主矩陣為 FCFS-HOL／SPT-HOL × FF-id／ratio；另以相同實體節點順序和固定種子 17、29 執行 FF-id 敏感性對照。結果與獨立 replay 位於 `results/20261017-b-gs1-placement-v2-04/`。

在完整 9,643 個 GS1 作業上，ratio 相對 FF-id：

* FCFS-HOL：平均等待差 `-0.028873 h`；62 個作業改善、15 個受損；新增等待總量 `3.035833 h`；最大改善 `9.971111 h`、最大受損 `0.213889 h`。
* SPT-HOL：平均等待差 `-0.434004 h`；480 個作業改善、0 個受損；新增等待總量 `0 h`；最大改善 `76.818056 h`。

這些是同政策、同 trace 的 placement 配對差，不是跨政策收益，也不是全叢集新排程結論。實驗固定結果為 PASS，八組完整配置及 16 份 persisted timing/placement 檔均通過獨立資源重播。

## 驗證與限制

已測：CPU=0、多 GPU worker、gang 原子性、node tie、同刻事件、規劃失敗不改資源、低比例 fallback、重跑可重現、FF-id 預設 timing/placement 回歸。未跑其他 GPU 池大型矩陣；未修改 Q2/Q3 演算法、main、baseline tag 或 V1 論文。候選是否納入正式模型仍需 reviewer 檢查與後續跨池整合。
