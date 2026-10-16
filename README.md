# Astra Modeling Team

`shiuhou/math_modeling` 以 Git 分支與 PR 協作，讓題目、推導、程式、實驗證據與論文可以互相核對。

目前狀態：**2026 MCM Problem B Baseline V1 已完成並合入 `main`**。第一輪 Q1、Q2、Q3 已整合；固定、不可變的參考點是 [`2026-mcm-b-baseline-v1`](https://github.com/shiuhou/math_modeling/releases/tag/2026-mcm-b-baseline-v1)，指向合併提交 `4ee2c6bfa98cf7177ff976abe73b122889437f46`。Q2 最新 SPT-HOL／SPT-FILL 比較已驗證；Q3 M0、S0、S1–S5 共 14 組情景已驗證；合併後共享 DES 已重跑 14 組，並與歷史排程逐 ID 精確一致。保底論文已產生 9 頁英文 PDF與 code supplement。正式競賽提交仍等待隊伍身份、人工作者確認與最終 AI 披露。

## 從這裡開始

1. 閱讀唯一數模規範正文 [modeling.md](modeling.md)；Agent 入口是 [AGENTS.md](AGENTS.md)。
2. 查看 [專案現況、題目覆蓋與共用介面](docs/brief.md)。
3. 按 [B 題唯一工程入口](problems/2026_gpu_scheduling/README.md) 核對 Baseline V1、正式證據與第二輪分工。
4. 按 [CONTRIBUTING.md](CONTRIBUTING.md) 從正確的研究分支開工並準備 PR。

## 第二輪研究流程

Baseline V1 是不可變參考。現有第二輪分支為 `feat/b-q2-k-ablation`、`feat/b-gang-placement` 與 `feat/b-q3-substitution-v2`；其他研究分支必須從 `2026-mcm-b-baseline-v1` 建立。純文件提交可以後續合入 `main`，但不移動 tag，也不改寫保底實驗。新方法必須沿用同一原始資料、指標、評價窗口與驗證標準；共享程式修改先經 PR 協調，已驗證的 results 不可覆寫。

## 檢查與目錄

在倉庫根目錄執行：

```bash
python3 scripts/check_repo.py
python3 -m unittest discover -s tests -v
git diff --check
```

| 位置 | 用途 |
| --- | --- |
| [docs/brief.md](docs/brief.md) | 當前研究、驗收與協作狀態 |
| [problems/2026_gpu_scheduling/README.md](problems/2026_gpu_scheduling/README.md) | B 題唯一工程與實驗入口 |
| [results/README.md](results/README.md) | 正式證據目錄與來源導航 |
| [scripts/](scripts/)、[tests/](tests/) | 倉庫檢查與工程測試 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 分支、驗證與 PR 流程 |

歷史研究日志與負面結果保留原狀；它們是歷史快照，不取代 Baseline V1 的正式證據。
