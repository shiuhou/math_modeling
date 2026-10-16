# Q3-S3 出版修訂版（勘誤 r3）

本版本只修正 Q3-S3 出版層，沒有新增情景、排程或模擬；`new_scheduling_runs=0`。原 S1/S2 結果與其 manifest 保持不變。

## 勘誤

1. M0 的 `paired_s0` 不再錯誤地重用 M0 對 M0 的零比較。M0 對 S0 的平均 finish delta 由既有 S0−M0 配對證據反向重算：FCFS `+312.253500` 小時，SJF-HOL `+12.372723` 小時。
2. 改善／惡化作業數按同一配對反向互換。正延遲總量、P99、Max 與 zero-wait 新延遲等非對稱欄位不直接取負，改以 `null` 和 `REVERSED_SYMMETRIC_ONLY` 明確標示未計算。
3. 生成器加入回歸：反向平均差互為相反數；M0 對 S0 平均 finish delta 等於兩群體平均 JCT 差；改善／惡化數互換。
4. LaTeX 表格每個資料列輸出兩個反斜線；`node_name` 輸出為 `\texttt{node\_name}`；worker 數 `W_j` 與等待 `\omega_j` 分開。表格不使用 `\scriptsize` 縮小字體。

## 交付

- 英文正文：[q3_section.tex](../../problems/2026_gpu_scheduling/paper/q3_section.tex)
- 繁中正文：[q3_section_zh.html](../../problems/2026_gpu_scheduling/paper/q3_section_zh.html)
- 修正版資料：[paper_ready_metrics.json](paper_ready_metrics.json)、[paper_ready_metrics.csv](paper_ready_metrics.csv)
- 主表：[q3_s3_main_table.tex](q3_s3_main_table.tex)
- 來源對照：[q3_claim_sources.json](q3_claim_sources.json)
- 檢查：[publication_checks.json](publication_checks.json)

出版資料仍只來自 S1 的 `metrics.json` 與 S2 的 `sensitivity_metrics.json`。完整排空指標、90 天完成數及 native harm 的分母與比較基線均在同一份 paper-ready rows 中。大型 ZIP 跨機交付狀態獨立記錄為 `BLOCKED`，不因而重跑任何實驗。

LaTeX 編譯結果以 `publication_checks.json` 為準。本輪內建編譯請求未回傳完成 PDF；worktree 也沒有本地編譯器，因此狀態保留 `NOT_RUN`，不將靜態檢查宣稱為編譯通過。
