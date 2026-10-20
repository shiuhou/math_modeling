# Q2 V2：K／timer 消融與 SPT-HEAD-TIME（2026-10-17）

本輪固定基準為 tag `2026-mcm-b-baseline-v1`、commit
`4ee2c6bfa98cf7177ff976abe73b122889437f46`，工作分支為
`feat/b-q2-k-ablation`。沒有修改 main、V1 tag、原始 CSV、Q1/Q3 或歷史結果。

## 實作

沿用唯一 DES、逐節點 atomic planner 與獨立 reservation validator。新增唯一候選
`SPT-HEAD-TIME`：SPT 首件阻塞時立即建立不可延後的節點級 `R`，保護首件身份；
只有目前完整可行且 `finish <= R` 的作業可回填，保護首件不受 K 裁剪，履約後才選
下一個 SPT 首件。它不使用 aging、FIXED/FLEX 或 urgent 身份。

`simulate_pool(..., diagnostics=True)` 增加低成本診斷：dispatch timestamp、
order build、candidate attempts、unique/repeated candidate IDs、budget exhaustion、
planner cache、reservation/certificate counters。`--no-diagnostics` 只停用候選
ID 集合；排程、K 記帳、timer、FF-id、事件和證據不變。診斷開／關的合成回歸中
starts、finishes、placements 與 events 完全相同。

## 固定實驗與狀態

所有子程序均使用 A10 原始節點、正式 `read_data()` 排序、FF-id、
`theta=604800s`、`H=7776000s`，並限制 900 秒／4 GiB RSS；每次只有一個昂貴
子程序。矩陣是 65,536 與 111,284 A10 作業的 SPT-FILL（K=200/2000，
shared-timer／arrival-completion-only）及 SPT-HOL（兩種 event mode）；候選各跑
shared-timer、K=200。14 組均 `PASS`，均有完整 timing、placements、空或完整
reservation evidence、獨立 capacity/reservation replay。

65k 摘要（小時；來源與所有欄位見正式 comparison）：

| 配置 | Mean | P99 | Max | wall s | reservations |
|---|---:|---:|---:|---:|---:|
| FILL K200 shared | 31.0417 | 1254.218 | 1860.19 | 81.0 | 0 |
| FILL K2000 shared | 31.2661 | 1257.256 | 1860.19 | 214.7 | 0 |
| FILL K200 arrival | 31.1103 | 1257.254 | 1860.19 | 57.6 | 0 |
| FILL K2000 arrival | 31.2661 | 1257.256 | 1860.19 | 146.3 | 0 |
| SPT-HOL shared/arrival | 30.3316 | 1252.840 | 1870.42 | 14.9/14.5 | 0 |
| SPT-HEAD-TIME shared | 30.3525 | 1252.396 | 1869.77 | 358.3 | 57,827 |

完整 A10 摘要：

| 配置 | Mean | P99 | Max | wall s | RSS MiB | reservations |
|---|---:|---:|---:|---:|---:|---:|
| FILL K200 shared | 34.9670 | 1575.462 | 3015.31 | 163.1 | 854.8 | 0 |
| FILL K2000 shared | 35.3704 | 1570.014 | 3012.49 | 458.7 | 540.7 | 0 |
| FILL K200 arrival | 34.9185 | 1571.349 | 3012.49 | 123.8 | 612.8 | 0 |
| FILL K2000 arrival | 35.3704 | 1570.014 | 3012.49 | 313.8 | 402.0 | 0 |
| SPT-HOL shared/arrival | 32.9065 | 1542.181 | 3017.29 | 26.6/24.9 | 537.3/382.5 | 0 |
| SPT-HEAD-TIME shared | 32.9238 | 1541.587 | 3017.73 | 651.9 | 2136.0 | 100,205 |

各規模使用自己的整數事件積分容量下界：65k 為 24.918189h，完整 A10 為
22.317931h；分解 `Capacity LB + Within-window Gap + Beyond-duration Waiting`
與正式 mean 精確閉合，未將 gap 解釋成可消除因果份額。

## 判斷

普通 SPT-HOL 在此 A10 trace 及 168h 門檻的平均等待最低（完整 A10 32.9065h），
但 Max wait 略高於 FILL；shared-timer 與 arrival-completion-only 對普通 HOL
沒有差異。FILL 的 K=2000 沒有帶來平均等待收益，反而使成本約 2.8 倍（65k）／
2.8 倍（完整）並使 mean 略升；因此在本輪配置不值得取代 K=200。

SPT-HEAD-TIME 相對普通 HOL 的 mean 僅增加 0.02084h（65k）／0.01735h（完整），
P99 略低，但 Max 沒有改善；其 validator／reservation 成本很高（完整 100,205
預約、peak 約 2.1 GiB）。它是可安全重播的候選，尚不足以取代 V1 的簡單 HOL 或
作為平均等待主方案。所有結論只適用上述 K、timer、FF-id、A10 trace 和門檻，
不推出一般無飢餓或全域最佳性。

## 產物與驗收

正式目錄為 `results/20261017-b-q2-v2-01/`；`comparison.json` 保存 14 組來源、
timing row/hash、成本、分組、分解、配對與原始資料 hash；`benchmarks/` 保存每組
runner compact manifest；`commands.sh` 保存重現命令。大型逐作業檔仍在可重建的
ignored `outputs/q2-v2-*`，沒有複製進 Git。

已執行並 PASS：3 個 V2 定向測試、Problem B 全部 88 tests、repo checks、root
tests、`git diff --check`。未執行新的完整 224,112-job 叢集矩陣或參數搜索。

## Q2-V2-R1 勘誤與採納凍結（2026-10-18）

修訂入口：`results/20261018-b-q2-v2-r1-01/`。原 14 組結果、manifest、
raw CSV 和 simulator 完全不變；本輪正式 scheduler 新運行數為 0。

- `unique_candidate_ids` 是 pool run 全程不同 bypass 候選數；repeated 包含跨
  timestamp 重查，不能量化同刻冗餘／浪費或等待因果份額。同刻統計 NOT_AVAILABLE。
- `dispatch_timestamps` 的程式定義是 dispatch 呼叫數；不能以 order_builds
  代替唯一時間戳。diagnostics=False 時兩個 ID 統計為 null，其餘 counter 仍累計。
- 原表 wall 實為 policy runtime；R1 改從 benchmark 讀真正 child wall，
  同時列 scheduler／reservation validator／I/O+hash，各欄不是 CPU time。
  原 65k「2.8 倍」及候選差值取位改以新精確生成表為準；所有歷史數值未改。
- 普通 HOL 維持主方案；K/timer 納入限定範圍穩健性；HEAD-TIME 保留實驗選項。
  完整 A10 HEAD-TIME 的 P99 略降、Mean/Max 略增，不稱全面尾部改善或 Pareto 支配。
  普通 HOL 不含 aging，168h 僅是 shared-timer 配置。
- 14 組本機 timing、placement、reservation/events、phase log 的 hash 與原
  summary 完全相符。索引和 14 份 summary 入庫；大型帳本仍 LOCAL_ONLY，無共享位置。
- 驗證範圍勘誤：原 runner PASS 為程序內獨立容量／預約驗證，未找到另一次
  persisted replay 報告（MISSING）。前述「持久化 replay PASS」不應沿用。
  本輪 hash 核查不冒充物理可行性回放，既有安全測試也不等同無飢餓保證。

新增跨 timestamp 小型計數測試；驗收與日誌見修訂目錄 checks.json。
