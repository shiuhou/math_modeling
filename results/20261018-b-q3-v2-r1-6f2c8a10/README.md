# Q3-V2-R1 supplement / 補充說明

[Complete main table / 完整主表](main_table.md) · [Discrete maxima / 離散最大值](discrete_worst.md) · [Paired evidence](paired.csv) · [Routing/work](routing.json) · [Sources and access](manifest.json)

## Protocol / 比較口徑

M0: no substitution. R0: V1 eligibility and 10% SHA256, namespace `q3-fixed-split-v1`, 60 dedicated A100 nodes. R-shape: the same rule plus ≤16 vCPU/GPU. Native A100 uses the other 372 nodes. Fixed original cohorts: A10 n=111284 (routed and unrouted), ALL n=224112, native A100 n=80877. H=7776000 seconds; completed means finish≤H; waiting/JCT use complete drain. Sigma 1 and 2 are assumptions, not hardware measurements.

M0 不替代；R0 為 V1 eligibility、同命名空間 10% hash 與 60 台專區；R-shape 再加正式 16 vCPU/GPU 條件。固定原始群體包含分流與未分流作業；完成數用 90 天窗口，等待與 JCT 用完整排空。兩個 sigma 均為情景假設。

All paired deltas are candidate minus named reference over identical original IDs. Positive totals sum only positive per-ID deltas; harmed means use harmed n, and n=0 gives null/N/A. Unprefixed quantiles use the full named cohort; `harmed_` quantiles use only finish-delta>0. `wait_harmed_` uses start-delta>0. All quantiles use linear interpolation, independently in each direction.

配對差為候選減去指定基線；受損條件均值用受損人數，n=0 為 null。全群體分位數與受損子群分位數分開；零等待新增延遲以該列 reference 的原零等待作業為分母。M0 與同 sigma R0 不能互換。

## Observed tradeoffs / 已觀察取捨

FCFS, sigma=1: A10 mean JCT M0/R0/R-shape = 999.898326/687.644825/756.125275 h. R-shape vs R0: +68.480449 h; 96504 finish later, positive delay 12795303.141667 job-h; vs M0: -243.773051 h and 0 finish later.

繁中：FCFS、sigma=1，上述同群體三方案 JCT 及兩個基線分開比較；相對 R0 有 96504 個較晚完成，正延遲合計 12795303.141667 作業小時，相對 M0 較晚完成者為 0，不能把平均改善解讀為人人受益。

FCFS, sigma=2: A10 mean JCT M0/R0/R-shape = 999.898326/831.455545/761.667687 h. R-shape vs R0: -69.787858 h; 96101 finish later, positive delay 12678622.744167 job-h; vs M0: -238.230639 h and 485 finish later.

繁中：FCFS、sigma=2，上述同群體三方案 JCT 及兩個基線分開比較；相對 R0 有 96101 個較晚完成，正延遲合計 12678622.744167 作業小時，相對 M0 較晚完成者為 485，不能把平均改善解讀為人人受益。

SJF-HOL, sigma=1: A10 mean JCT M0/R0/R-shape = 132.676210/120.303488/124.128360 h. R-shape vs R0: +3.824872 h; 47819 finish later, positive delay 559301.142222 job-h; vs M0: -8.547850 h and 46803 finish later.

繁中：SJF-HOL、sigma=1，上述同群體三方案 JCT 及兩個基線分開比較；相對 R0 有 47819 個較晚完成，正延遲合計 559301.142222 作業小時，相對 M0 較晚完成者為 46803，不能把平均改善解讀為人人受益。

SJF-HOL, sigma=2: A10 mean JCT M0/R0/R-shape = 132.676210/134.809736/129.670773 h. R-shape vs R0: -5.138963 h; 47641 finish later, positive delay 485546.711944 job-h; vs M0: -3.005438 h and 55465 finish later.

繁中：SJF-HOL、sigma=2，上述同群體三方案 JCT 及兩個基線分開比較；相對 R0 有 47641 個較晚完成，正延遲合計 485546.711944 作業小時，相對 M0 較晚完成者為 55465，不能把平均改善解讀為人人受益。

## Post-hoc decision / 事後決策

For each fixed policy and option, F is original-A10 mean JCT and F_worst=max{F(1),F(2)}. R0 has lower mean JCT at sigma=1 in both policies; R-shape has the smallest two-point maximum among the three options in both policies. A choice stays fixed across the two scenarios; policies are never spliced. For conditions near the tested sigma=1, R0 can be preferable for average efficiency, but no neighborhood of superiority is proven.

每個固定政策及方案的 F 為原始 A10 平均 JCT；F_worst 為兩個已測點的最大值。兩政策在 sigma=1 都由 R0 有較佳平均效率，R-shape 則在三個選項中具有較小離散最大值，可作保守選項；不能每次事後知道 sigma 再換贏家，也不能跨政策拼接。接近 sigma=1 時偏重效率可考慮 R0，但未證明任何鄰域優勢。

This is post-hoc analysis, not a pre-frozen selection criterion, an upper bound on sigma∈[1,2], a guarantee at unknown true speed, or a global robust-optimization solution. No monotonicity is proven. There are no probabilities (including 50/50), interpolation, root finding, or precise/unique sigma*.

此為事後離散情景分析，不是事前凍結選點、區間上界、真實未知速度保證或全域 robust optimization。未證明單調性，端點不保證涵蓋區間最壞值；不假定概率、不插值、不求根或精確／唯一臨界倍率。

## Selection/work / 篩選與工作量

Excluded 605/11209 jobs (5.397448%); retained 10604. Excluded original GPU-work 1759818444 GPU-s (44.182249% of R0 selected GPU-work); CPU-work 82305115513 vCPU-s (84.476354% of R0 selected CPU-work).

繁中：排除 605 個，占 R0 轉移數 5.397448%；卻占 R0 原始 GPU-work 44.182249%、CPU-work 84.476354%。

Routing sets are identical across the two sigmas and policies; shape changes both resource composition and selected load. Original work uses original duration and worker requirements. Effective routed sigma2 work is twice original work; excluded jobs remain native under R-shape. No experiment identifies a pure CPU-ratio, duration or load causal contribution; matched controls would require additional experiments outside this task.

兩倍率與政策的選中集合相同；少量排除者占較大工作量，形狀與負載同時改變。原始工作量與替代後工作量分開。未識別 CPU 比例、時長或負載的單一因果效果；區分機制需額外實驗，本輪不執行。

## Adoption and evidence limits / 採納範圍與限制

Retain R0 and R-shape as explicit alternatives, including the sigma1 disadvantage; do not make R-shape an unconditional default. Candidate B remains IMPLEMENTATION_DEFERRED. No new schedules, sigma values, controls or candidates. Native A100 timing and placement match same-sigma R0 exactly; zero extra waiting vs M0 is an observation on this trace, not a future-trace guarantee. Existing physical replay PASS is cited with hashes; physical replay is not rerun in R1. Full timing/placement archives remain LOCAL_ONLY; cross-machine delivery BLOCKED. No PDF or V1 paper is changed.

保留 R0／R-shape 兩個明確選項與 sigma1 負面結果，不改無條件預設。B 延後、零新排程。原生 A100 對同分區 R0 的逐 ID timing／placement 完全一致；對 M0 零額外等待僅為此 trace 觀察。沿用有雜湊的既有物理 replay，R1 未重跑。大帳本仍 LOCAL_ONLY／跨機 BLOCKED；不更動 V1 論文或 PDF。

AI use: Codex generated the postprocessor, regression tests and bilingual supplement; human review remains pending.

## Retained/excluded distributions / 保留與排除分布

| group | measure | n | mean | min | p50 | p95 | p99 | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| retained_Rshape | duration_seconds | 10604 | 209394.065824 | 4.000000 | 579.000000 | 712356.650000 | 5804333.440000 | 15897599.000000 |
| retained_Rshape | gang_workers | 10604 | 1.040174 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 32.000000 |
| retained_Rshape | cpu_per_gpu | 10604 | 5.067333 | 1.000000 | 4.000000 | 8.000000 | 16.000000 | 16.000000 |
| excluded_R0_minus_Rshape | duration_seconds | 605 | 2908144.727273 | 3.000000 | 537842.000000 | 13531482.800000 | 15897599.000000 | 15897599.000000 |
| excluded_R0_minus_Rshape | gang_workers | 605 | 1.042975 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 27.000000 |
| excluded_R0_minus_Rshape | cpu_per_gpu | 605 | 45.052893 | 20.000000 | 48.000000 | 76.800000 | 96.000000 | 128.000000 |

Original-duration/worker distributions; quantiles use each named routed-set subgroup, not all A10. Work denominators and sigma-scaled work are in routing.json. / 此處分母為指定保留或排除子群，非全部 A10。

## Reproduction / 重現

Python/pandas/numpy versions and every input SHA256 are in manifest.json. Use the existing Problem B environment; obtain authorized local evidence at the listed relative paths first. This command reads saved timing only and requires a new output directory.

```bash
python problems/2026_gpu_scheduling/experiments/analyze_q3_v2_tradeoffs.py --out results/<new-unused-revision-id>
```

Physical replay and old scheduling suites are not executed by this command. Small result tables alone do not replace the unavailable cross-machine ledgers. / 先取得獲授權帳本；此命令僅後處理，不能把摘要表當成跨機帳本已交付。
