# Q3-S2 Fixed-Split 敏感性結果

本輪在 Q3-S1 已驗證的整卡、啟動前 A10→A100 固定分流模型上，只執行預先凍結的五個單因素情景（S1–S5）與 FCFS／SJF-HOL。原始 224,112 jobs、hash namespace、First Fit、90 天窗口 `H=7,776,000` 秒和物理分區均保持不變；S0/M0 直接引用已驗證的 `outputs/b-q3-fixed-split-v1-final`，沒有重跑基線。

| 情景 | donor | routing | sigma |
| --- | ---: | ---: | ---: |
| S1 | 60 | 5% | 1 |
| S2 | 60 | 20% | 1 |
| S3 | 30 | 10% | 1 |
| S4 | 90 | 10% | 1 |
| S5 | 60 | 10% | 2 |

`S1 ⊆ S0 ⊆ S2` 的 routed job ID 集合、`S5=S0` 的 routed 集合，以及 30⊂60⊂90 的物理節點前綴均由原始資料獨立核對。每一個成功情景均保存完整 job timing 與逐節點 placement；`independent_verification.json` 對十組情景執行 raw ID、effective duration、同步 gang、逐節點 CPU/GPU、排空、獨立 metrics 與 paired finish replay。

## 主要結果

完整表格見 [Table Q3-S2-A](table_q3_s2_a.md)、[Table Q3-S2-B](table_q3_s2_b.md)，逐作業配對見 [paired_comparisons.json](paired_comparisons.json)。表中的 harmed jobs 以 S0 的同政策作為比較對象。

- **分流比例（60 台、sigma=1）**：FCFS 在 5% 時 A10 平均等待 `702.551 h`，10% S0 為 `587.875 h`，20% 時反升至 `1010.136 h`；SJF-HOL 分別為 `25.328/20.534/22.058 h`。SJF-HOL 的平均改善伴隨大量完成時間退化，不能只用平均等待選點。
- **借出容量（10%、sigma=1）**：FCFS 的 A10 平均等待在 30/60/90 台為 `916.407/587.875/539.109 h`；SJF-HOL 為 `25.565/20.534/19.214 h`。90 台首次出現原生 A100 損失：FCFS 5,735 個、SJF-HOL 2,150 個作業相對 S0 等待變差，平均新增等待分別 `0.0771/0.0185 h`。
- **sigma=2（60 台、10%）**：A10 平均等待仍低於 M0（FCFS `721.752 h` vs M0 `900.129 h`；SJF-HOL `25.106 h` vs M0 `32.906 h`），但相對 S0 的平均 finish delta 變為 `+143.811/+14.506 h`；A10 平均 JCT 為 `831.456/134.810 h`，不能將等待下降稱為完整收益。這只是 sigma=2 的情景結果，沒有硬體 benchmark，也沒有估計精確 `sigma*`。
- **公平性與尾部**：S1–S5 的 A10 P95/P99、最大等待、finish 改善／惡化、原零等待新增等待及正向完成延誤均保留在兩份表和 paired JSON。90 天完成數與完整排空分開報告；例如 S5 FCFS 90 天完成 177,166，但完整排空約 449.10 天。

圖 [donor capacity trade-off](figures/donor_capacity_wait_tradeoff.png) 將 30/60/90 台的 A10 平均等待改善與原生 A100 平均等待增加分開呈現；A100 的小幅損失未以放大尺度掩蓋其量級。

## 驗證與成本

- 執行器：`run_q3_sensitivity.py`，每次一個 scenario+policy，重用唯一 `q3.simulate()`；十組均完成，單 policy 約 17–19 秒。
- 獨立驗證器：`verify_q3_sensitivity.py`；十組全部 `PASS`，總回放約 152.5 秒。
- 3 個 sensitivity contract tests、repo checks、root tests 與 B 題 tests 由交付前執行；本輪沒有修改共用 DES/evaluator、原始 CSV、Q1/Q3-S1 正式結果或 Claude 來源。
- 原始資料 SHA256 沿用 S1：`node_info_df.csv`=`1aba2361…bc9d18`，`job_info_clean.csv`=`ef14d696…eedb0`；完整值見 `manifest.json`。

## GO／限制與交付

**GO（小型單因素研究）**：十個情景均物理合法且獨立 paired replay PASS，因此可以把這組結果納入 Q3 論文的條件性敏感性段落。不能宣稱存在全域最佳 donor、routing 或 sigma；SJF-HOL 的尾部與完成時間退化必須同時呈現。

下一個最小研究問題是：在已保留的 30/60/90 台與 5/10/20% 結果上，針對 SJF-HOL 的 A10 尾部完成延誤，預先指定一個公平性門檻並做一次小型 operating-point 判定；不啟動動態借用或大型矩陣。

大型逐作業輸出位於本機 `outputs/b-q3-s2-fixed-split-v1/`，約 57,534,861 bytes；新交付封存與舊 S1 ZIP 的 SHA256、大小和取得方式記於 `manifest.json`。目前沒有跨機共享儲存，故只宣稱本 worktree 可取得；重現命令與相對路徑不依賴個人絕對路徑。
