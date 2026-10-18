# GS1-V2-R1 修訂與勘誤

來源：`a20d73f`；原始八組、summary 與 manifest 保持逐 byte 不變。正式數字與來源 hash 見同目錄 comparison.json、window-comparison.json、manifest.json。

## 主要比較（H=7,776,000 秒）

等待、JCT 均為完整排空小時；allocation 為 [0,H) 的分配率。配對固定同政策 FF-id；成本為原 scheduler 計時（舊 run 未量測 RSS，不補造）。

| Policy | Placement | Mean / P99 / Max wait (h) | 零等待數 / 比例 | 90天完成 | GPU / CPU allocation | 改善 / 受損 | 正新增等待(h) | Scheduler(s) |
|---|---|---|---|---|---|---|---|---|
| FCFS-HOL | ff-id (original) | 0.029188271 / 0.000000 / 9.971111 | 9581 / 0.99357047 | 8221 | 0.608651862 / 0.348135133 | 0 / 0 | 0.000000 | 0.9613 |
| SPT-HOL | ff-id (original) | 0.434277052 / 14.491944 / 76.818056 | 9163 / 0.95022296 | 8213 | 0.607789495 / 0.347872154 | 0 / 0 | 0.000000 | 0.9717 |
| FCFS-HOL | ratio (corrected) | 0.000000000 / 0.000000 / 0.000000 | 9643 / 1.00000000 | 8221 | 0.608671848 / 0.348138419 | 62 / 0 | 0.000000 | 7.0893 |
| SPT-HOL | ratio (corrected) | 0.000000000 / 0.000000 / 0.000000 | 9643 / 1.00000000 | 8221 | 0.608671848 / 0.348138419 | 480 / 0 | 0.000000 | 7.4540 |

完整比較含 P95、Mean JCT、兩個 seed 的敏感性與新舊 ratio，見 comparison.csv。兩組新 child 總牆鐘約 7.60／7.95 秒，process peak RSS 約 146.51／146.48 MiB；900 秒／4 GiB 上限未觸發。

## 勘誤與證據

- 原 `_ratio_cmp` 含 index tie-break，反向呼叫同時反轉 tie。本輪讓 comparator 僅比較比例；兩組 tie 都由外層 numeric node_name 升序處理。DES 始終先排序節點；seed 只變更索引走訪順序，沒有重排陣列。FF primitive AST 與原提交相同，DES 檔案未改。
- 原 replay 缺 timing 身份、duration、重複 pair、整數與部分容量檢查；本輪嚴格 CSV adapter 復用正式 validation.py，先核對 raw 身份及全部屬性，再做原子 gang 事件回放。16 種故障注入會拒絕，合法同刻釋放／啟動會接受。原八組皆合法：old-replay.json 全 PASS。
- 新舊 ratio 逐 ID 比對：FCFS timing 15／placement 1347 改變；SPT timing 13／placement 1299 改變。不是只比較總指標；hash 見 fallback-changes.json。
- 原八組只做回放與後處理，未重跑；只串行重跑 FCFS-HOL+ratio、SPT-HOL+ratio 各一次。
- 原 H=7,767,629 保留，另算 H=7,776,000。10 組的完整等待 Mean/P99/Max 及 JCT 全不變；完成數及 GPU/CPU allocation 的變化逐項保存於 window-comparison.json。
- CPU 分層單位修為 vCPU/GPU：cpu_units 除以 100，原 100／400 units 門檻對應 1／4 vCPU，沒有調整分組集合或候選閾值。

## 採納判斷與限制

FCFS：相對同政策 FF-id，62 作業改善、0 作業受損；SPT：480 改善、0 受損。兩種政策分別得到全量 GS1 零等待可行構造，支持保留為 GS1 專用可選候選。這不是一般工作負載的全域最優定理；不同到達、CPU／GPU形狀或資源壓力可能使啟發式受損。不自動套用到其他 GPU 池，不改通用預設。

## 驗收

PASS：舊八組嚴格回放、新兩組嚴格回放、五項新增測試（含16種故障注入）、B 題94項測試。根目錄檢查與最後 diff 見各 log／acceptance.json。NOT_RUN：其他池大型矩陣、全叢集性能、論文編譯。

重現入口（會做兩組完整實驗，請使用新目錄）：
```bash
.venv/bin/python problems/2026_gpu_scheduling/experiments/revise_gs1_placement.py --out outputs/gs1-v2-r1-new
```
原八組來源為倉庫 results/20261017-b-gs1-placement-v2-04；不需要對話附件。
