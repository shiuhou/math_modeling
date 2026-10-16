# 專案入口

唯一規範正文見 [modeling.md](../modeling.md)，協作見 [CONTRIBUTING.md](../CONTRIBUTING.md)。B 題工程與實驗命令集中於 [B 題 README](../problems/2026_gpu_scheduling/README.md)。

## 目前狀態

| 項目 | 狀態 |
| --- | --- |
| 題目與資料 | 2026 MCM Senior Problem B、原題 PDF 與兩個 raw CSV 已核對；原始資料與容量不可改寫 |
| 第一輪正式研究 | **完成**：Q1、Q2、Q3 已整合至 Baseline V1 |
| Q2 | 最新 SPT-HOL／SPT-FILL 比較已驗證；正式來源 commit `b91918bb084848b93de642ad4e3ea0a7d3f25e68` |
| Q3 | M0、S0、S1–S5 共 14 組情景已驗證；正式來源 commit `170cc37a820e830a969cb1b1cd3cadb1e8fdf256` |
| Baseline V1 技術驗收 | **PASS**：整合驗收 `9f76e086690e574d73ca54cfb0c08d7e9eb0b9fe`；共享 DES 14 組重跑與歷史排程逐 ID 精確一致 |
| Baseline V1 合併 | **PASS**：main `4ee2c6bfa98cf7177ff976abe73b122889437f46`；不可變 tag `2026-mcm-b-baseline-v1` |
| 論文工程 | **PASS**：9 頁英文保底 PDF、`paper_sources.json`、`baseline_release_checks.json` 與 code supplement 已保存 |
| 正式競賽提交 | 尚待人工完成：隊伍身份、人工作者確認與最終 AI 披露；不得標為 `SUBMISSION_READY` |
| 第二輪研究 | 三條新 feat 分支已從 Baseline V1 建立並推送；依各分支實際證據判定進行中或尚未啟動 |
| 大型證據 | Q3 大型逐作業／節點帳本仍有跨機共享限制，保持 `BLOCKED`，不把限制誤標為已解決 |

## 共用接口與驗收口徑

`read_data(source)` 提供 nodes、jobs 與 input hashes；時間、每 worker 資源需求與 0.01 vCPU 整數縮放保持不變。`simulate_pool(nodes, jobs, policy)` 是唯一共享 DES；`evaluation.py` 是唯一 evaluator，等待／JCT、分配窗口與完成數口徑由其定義。Q2、Q3 與第二輪方法沿用這些接口，不另建或覆寫引擎。

Baseline V1 是不可變參考。新方法比較時使用同一原始資料、容量、事件契約、指標、評價窗口與驗證標準；已驗證 results 不覆寫。若純文件後續合入 main，不代表 tag 或實驗基準改變。共享程式修改先在此提出並透過 PR 協調。

## 協作狀態

既有第二輪分支為 `feat/b-q2-k-ablation`、`feat/b-gang-placement`、`feat/b-q3-substitution-v2`；其他研究分支必須從 `2026-mcm-b-baseline-v1` 建立。第一輪歷史日志、Q3 pilot、舊 Q2 方法與 `NOT_RUN`／`BLOCKED` 證據保留為歷史快照，不當作目前唯一成果，也不因文件更新而重寫。

實際正式證據按 [results 約定](../results/README.md) 保存；根目錄工程測試不取代模型或性能證明。
