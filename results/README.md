# 正式研究證據

這裡是可版本追蹤的正式結果與來源導航。Baseline V1 的固定參考是 tag `2026-mcm-b-baseline-v1`，目標提交 `4ee2c6bfa98cf7177ff976abe73b122889437f46`。歷史結果、負面結果與未執行項目保留原目錄，不覆寫、不把 `NOT_RUN` 改成 `PASS`。

## Baseline V1 正式入口

- **Q1**：[Q1 重算清單](20261014-b-q1-intake-4a8f8f2b/manifest.json)、[Q1 論文與交付驗收](20261014-b-q1-publication-42b5a896/manifest.json)、[容量下界驗收](20261015-b-q1-capacity-bound/acceptance.json)。
- **Q2**：M2-G 與 cross-review 修訂保留於 `20261015-b-q2-*` 結果目錄；以各目錄的 `manifest.json`、`checks.json`、`regression.json` 與 paired evidence 為準。Q2 最新來源 commit 為 `b91918bb084848b93de642ad4e3ea0a7d3f25e68`。
- **Q3**：[固定分流正式清單](20261015-b-q3-fixed-split-c9e8f1a2/manifest.json)、[S1/S2 敏感性清單](20261015-b-q3-s2-fixed-split-v1/manifest.json)、[r4 出版交付](20261016-b-q3-s3-publication-9ac1d7f2-r4/README.md)。Q3 最新來源 commit 為 `170cc37a820e830a969cb1b1cd3cadb1e8fdf256`。
- **整合回歸**：[Baseline release checks](../problems/2026_gpu_scheduling/paper/output/baseline_release_checks.json)、[runtime equivalence](../problems/2026_gpu_scheduling/paper/output/integration_runtime_equivalence.json)、[整合驗收報告](../problems/2026_gpu_scheduling/paper/output/integration_runtime_equivalence_report.md)。合併後共享 DES 已跑 14 組並與歷史排程逐 ID 精確一致。
- **論文與程式**：[paper_sources.json](../problems/2026_gpu_scheduling/paper/paper_sources.json)、[9 頁英文 PDF](../problems/2026_gpu_scheduling/paper/output/pdf/problem_b_baseline_v1.pdf)、[code supplement](../problems/2026_gpu_scheduling/paper/output/code_supplement_baseline_v1.zip)。

Q3 大型逐作業／節點帳本仍受跨機共享限制，保留 `BLOCKED`／取得限制；這不影響已保存的小型指標與整合驗收狀態。正式競賽提交仍需人工完成，不在此宣稱 `SUBMISSION_READY`。

## 保存規則

正式運行使用唯一 `results/<experiment_id>/manifest.json`；重跑建立新 ID，不覆蓋舊運行。清單記錄 code commit、dirty 狀態、資料與配置雜湊、命令、環境、驗證狀態、結果位置及限制。大型或私有明細只記錄已確認的共享位置、版本、雜湊與取得方式，不寫入個人絕對路徑或憑證。

基準、必要對照與有價值負面結果同樣保留。`outputs/`、`latest` 或即時留言不能是唯一證據；歷史 `NOT_RUN`、`BLOCKED` 與限制說明不得因導航整理而改寫。

## JSON 清單約定

正式清單使用 `kind: "formal"`，`validation.status` 僅可為 `PASS`、`FAIL`、`NOT_RUN` 或 `BLOCKED`。`NOT_RUN` 表示未執行，`BLOCKED` 表示有明確外部限制；未知值不可填零或假成功。完整欄位規範與示例保留於 [manifest.example.json](manifest.example.json) 及各正式清單。
