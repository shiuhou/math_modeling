# Q3-V2 R-shape bounded study

本輪以 `2026-mcm-b-baseline-v1`／`4ee2c6bfa98cf7177ff976abe73b122889437f46` 為基準，只研究固定 60 台 A100 接收專區的資源形狀感知分流。原始 224,112 個作業、372 台 native A100、worker CPU/GPU、gang、啟動前決策、完整排空與 `H=7,776,000` 秒均保持不變；沒有修改 V1 論文或歷史結果。

## R-shape 規則

先套用 V1 的 eligibility 與 `q3-fixed-split-v1` 10% SHA-256 門檻，再要求 `cpu_request / gpu_request <=` 由正式 `node_info_df.csv` 選出的 60 台 A100 節點推導的容量比。資料核對為每台 128 CPU／8 GPU，門檻是 `16 CPU/GPU`。V1 選中的 11,209 個作業中，R-shape 保留 10,604 個；因此 GPU-work、CPU-work 與作業形狀同時變化，結果不能宣稱純 CPU 比例的因果效果。

## 完整 trace 結果

| 情景／policy | R-shape routed | routed GPU-work | routed CPU-work | A10 mean JCT (h) | 全體 mean JCT (h) | 90d 完成 | A10 mean JCT vs same-sigma R0 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| sigma=1 / FCFS | 10,604 | 5.554% | 1.559% | 756.125275 | 402.914382 | 177,512 | +68.480449 h |
| sigma=1 / SJF-HOL | 10,604 | 5.554% | 1.559% | 124.128360 | 89.108085 | 217,801 | +3.824872 h |
| sigma=2 / FCFS | 10,604 | 5.554% | 1.559% | 761.667687 | 405.666497 | 177,324 | -69.787858 h |
| sigma=2 / SJF-HOL | 10,604 | 5.554% | 1.559% | 129.670773 | 91.860199 | 217,613 | -5.138963 h |

R-shape 的 sigma=1 兩政策 A10 JCT 都劣於 V1 R0（FCFS +68.480449 h、SJF-HOL +3.824872 h），所以不能回答為「優於 V1」。sigma=2 則相對同 sigma R0 改善 A10 JCT（FCFS −69.787858 h、SJF-HOL −5.138963 h）；相對 M0，FCFS −238.230639 h、SJF-HOL −3.005438 h。這是固定 trace 的反事實比較，不是硬體性能或因果識別。

原生 A100 對同 policy、同 sigma 的 R0 逐作業 start/finish 與 placement 均完全一致；四組均通過獨立逐節點 replay。A10／全體的 Mean/P95/P99/Max waiting、Mean JCT、relative completion delay、90 日完成、positive completion delay、zero-wait 新延遲及短／長×單／多 worker 分層均保存在 `shape_metrics.json`。

## Candidate B

完成時間代價感知候選為 `IMPLEMENTATION_DEFERRED`。目前 `q3.route()` 在 DES 前一次決定整份路由，尚無可安全接入「已到達／運行剩餘／當前資源」的 callback；本輪只交付數學規格、`eta=0`、資訊邊界、同時到達 job ID 順序與最小 `route_on_arrival(state, job)` 接口，沒有虛構完整 trace 數字。

## 證據與限制

- 四組完整 trace 串行執行，每組約 35–37 秒，低於 900 秒上限；沒有參數搜索。
- `independent_verification.json`：route replay、逐節點 CPU/GPU ledger、timing、finish identity、原始 ID 集合與 native invariance 均 PASS。
- 大型 timing/placement 及本機 delivery ZIP 未放入 Git；跨機共享位置未授權，狀態 `BLOCKED`。ZIP SHA256 見 manifest。
