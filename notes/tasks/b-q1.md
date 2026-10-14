# B 題 Q1 定稿與可重現交付

分支 `feat/b-q1` 從已推送的原 Q1 提交正常快轉至整合基礎 `abdbc4c`，保留歷史；此輪僅提交／推送本分支，不合併 main，不改 Q2/Q3 研究分支。唯一操作說明見 [B README](../../problems/2026_gpu_scheduling/README.md)。

## 本輪內容

- 唯一英文 Q1 章節供全稿與獨立預覽共用，三部分：Data Characteristics、Supply–Demand Imbalance、Bottleneck Hypotheses；繁中逐段對照使用同一批結果與圖。
- 一表兩張正文圖、五張補充圖，沿用原始公式與九表。每日需求新增精確區間積分，保留 partial day；不是調度器或新的分析系統。
- `build_paper.py --scope q1|full`（預設 full）、`--bundle`，包含來源／依賴／雜湊／命令。`verify_q1.py --reference-dir` 允許首次 clone 不依賴對話附件。
- 共用入口受影響：`build_paper.py`、`generate_figures.py`、`verify_q1.py`、`q1.py`（僅增加聚合函式）、新增 `q1_publication.py`；論文 `preamble.tex`／Q1 章節抽取。DES／loader／evaluator、Q2/Q3 正文與舊中文原稿不修改。

## 驗收狀態

本節在最終重現後填入實際證據；目前已有原 CSV 重算／39 統計與九表核對、兩頁 Q1 與九頁全稿編譯、PDF 與中文離線初檢。這些不代表完整交付包驗收已結束。

## 未確認事項

歷史來源 job byte 雜湊不一致且缺原始 ZIP：BLOCKED；資料再散布範圍、姓名與最終 AI 披露、團隊人工審閱仍待確認。Q2/Q3 舊性能不在本輪驗證範圍，NOT_RUN；全稿既有寬表與小字須後續統一處理。

原 Q1 整合的九表與 39 項基準仍見 [歷史核查清單](../../results/20261014-b-q1-intake-4a8f8f2b/manifest.json)。先前全稿編譯與跨章需求舊值的缺口，已由 `abdbc4c` 共用整合處理，勿沿用舊狀態；歷史內容可由 Git 查閱。
