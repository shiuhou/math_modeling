# Q3-S3 出版分母修訂版（r4）

本版本以 `79e93c315f006d67f743b14a1d7faf16b00dd072` 為基準，只修正出版生成器、正文與可重現證據交付；`new_scheduling_runs=0`。S1、S2 結果與 manifest、`q3.simulate`、共用 DES、原始 CSV 及 Q1 成果未修改。

## 修訂

- S4（90 台）native A100 的 S4−S0 等待差分分開保存全體分母與正差分受損子群：FCFS 全體 `n=80,877`、受損 `n=5,735`，平均新增等待 `0.077111426`／`1.087452630` 小時；SJF-HOL 全體 `n=80,877`、受損 `n=2,150`，平均新增等待 `0.018491695`／`0.695605943` 小時。
- 正新增等待總量為 FCFS `6236.540833`、SJF-HOL `1495.552778` job-hours。全體 P99 為 `2.074778`／`0.405622` 小時；受損子群 P99 另由正差分資料計算為 `4.099278`／`6.072953` 小時，均明確標示為 S4−S0。
- 正文補入 S0／SJF-HOL 相對 M0 的 `49,772` 個較晚完成 A10、`4,397` 個原零等待而新增等待作業、`68183.1825` positive completion-delay job-hours，以及 A10 waiting P95 `11.086875 → 12.690806` 小時。
- 正文保留負面尾部：S2／FCFS 的 A10 Max waiting `5445.367` 小時，以及 S3／FCFS 平均等待 `916.407` 小時高於 M0 的 `900.129` 小時。
- 英文正文現在是 fragment；`q3_section_preview.tex` 是獨立 wrapper，兩者由同一生成器產生。fragment 不含 document wrapper 或局部字級重定義。

## 入口

- 英文正文 fragment：[q3_section.tex](../../problems/2026_gpu_scheduling/paper/q3_section.tex)
- 英文獨立預覽 wrapper：[q3_section_preview.tex](../../problems/2026_gpu_scheduling/paper/q3_section_preview.tex)
- 繁中正文／預覽：[q3_section_zh.html](../../problems/2026_gpu_scheduling/paper/q3_section_zh.html)
- 修訂資料：[paper_ready_metrics.json](paper_ready_metrics.json)、[paper_ready_metrics.csv](paper_ready_metrics.csv)
- 生成主表：[q3_s3_main_table.tex](q3_s3_main_table.tex)
- 來源與計算範圍：[q3_claim_sources.json](q3_claim_sources.json)
- 檢查：[publication_checks.json](publication_checks.json)

## 編譯與跨機交付

內建編譯器可啟動 XeTeX，但其隔離環境不提供 sibling project files，`q3_section_preview.tex` 的 `\input{q3_section.tex}` 因此未取得 PDF；狀態保留 `NOT_RUN`，沒有宣稱編譯 PASS，也未進行逐頁 PDF 檢查。整合者需將 fragment、主表與 `figures/q3_donor_capacity_wait_tradeoff.png` 放在同一 paper 目錄後編譯 wrapper。

大型 schedule／delivery evidence 仍只在本機，跨機共享位置未獲授權，狀態為 `BLOCKED`；本輪沒有因而重跑實驗。
