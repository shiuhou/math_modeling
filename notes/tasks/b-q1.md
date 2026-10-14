# B 題 Q1 定稿與可重現交付

分支 `feat/b-q1` 從已推送的原 Q1 提交正常快轉至整合基礎 `abdbc4c`，保留歷史；此輪僅提交／推送本分支，不合併 main，不改 Q2/Q3 研究分支。唯一操作說明見 [B README](../../problems/2026_gpu_scheduling/README.md)。

## 本輪內容

- 唯一英文 Q1 章節供全稿與獨立預覽共用，三部分：Data Characteristics、Supply–Demand Imbalance、Bottleneck Hypotheses；繁中逐段對照使用同一批結果與圖。
- 一表兩張正文圖、五張補充圖，沿用原始公式與九表。每日需求新增精確區間積分，保留 partial day；不是調度器或新的分析系統。
- `build_paper.py --scope q1|full`（預設 full）、`--bundle`，包含來源／依賴／雜湊／命令。`verify_q1.py --reference-dir` 允許首次 clone 不依賴對話附件。
- 共用入口受影響：`build_paper.py`、`generate_figures.py`、`verify_q1.py`、`q1.py`（僅增加聚合函式）、新增 `q1_publication.py`；論文 `preamble.tex`／Q1 章節抽取。DES／loader／evaluator、Q2/Q3 正文與舊中文原稿不修改。

## 驗收狀態

正式證據見 [本輪清單](../../results/20261014-b-q1-publication-42b5a896/manifest.json) 與 [逐項驗收](../../results/20261014-b-q1-publication-42b5a896/acceptance.json)。

- PASS：原 CSV 重算，39 項統計／九表與 Git 基準及可選交接 ZIP 均吻合；九表 bytes 相同。歷史 input byte 身份另列 BLOCKED。
- PASS：既有六項 Q1 數值測試、兩項新聚合邊界測試與兩項交付檢查；完整 B 測試共 18 項，根目錄 12 項。原資料逐區間獨立重疊核算與 180 個每日需求積分一致。
- PASS：兩頁 Q1，一表兩正文圖、五張補充圖；中英文共享數值／表格、PDF 逐頁檢視與中文離線 HTML／圖像／連結檢查。正文、表格、圖說約 11.059 PDF pt，水平圖中文字約 11.213 pt；數學上下標依慣例較小。
- PASS：全稿編譯九頁；FAIL：全稿競賽字體／溢出驗收，Q2/Q3 原有小字寬表與四處 overfull 仍待該階段處理，不以九頁即宣稱可提交。
- PASS：獨立 Git clone、新 venv、README 命令重現，不依賴 ChatGPT 附件；本機 Tectonic 0.17.0／套件快取沿用，未測試完全離線首次安裝。
- PASS：交付包解壓到 Git 外，僅指定 clone 中 raw CSV 即可重現九表／統計與兩頁 Q1；ZIP 約 1.1 MB，無原始資料、環境、快取、大型逐作業明細及 Q2/Q3 圖。
- NOT_RUN：團隊人工雙語審閱、全量調度重跑、競賽正式提交。Q1 可以供全文採用與後續人工審閱，整篇仍未達提交狀態。

本機成品在 `outputs/q1-final/`，Git 僅保存原始碼、小型核查證據與重現入口。交付包另含本輪驗收記錄；純 `--bundle` 重算生成的是 build-time 記錄，人工／呈現檢查需重新記錄。

## 整合到 Q2/Q3 時

相對 `abdbc4c` 的來源提交：`1583034`（雙語正文、圖、交付入口）及 `00f6f57`（保留 `tab:q1_summary` 舊標籤），其後為本輪證據／文件提交。整合者查看 `git log abdbc4c..feat/b-q1` 和完整 diff，再按各分支最新進度正常合併或選取，不重寫已推送歷史。

`fig:q1`、`eq:load_ratio`、`tab:q1_summary` 保留；新增需求圖會改變後續圖號，使用 label 引用。`build_paper.py` 預設仍 full；Q1 scope 無須歷史 Q2/Q3 圖資。`q1.py` 只增加區間積分函式，九表及 EDA 介面不變。未改 DES／evaluator／loader、Q2 起正文、歷史中文稿或 raw bytes；未操作兩個研究分支與 main。

## 未確認事項

歷史來源 job byte 雜湊不一致且缺原始 ZIP：BLOCKED；資料再散布範圍、姓名與最終 AI 披露、團隊人工審閱仍待確認。Q2/Q3 舊性能不在本輪驗證範圍，NOT_RUN；全稿既有寬表與小字須後續統一處理。

原 Q1 整合的九表與 39 項基準仍見 [歷史核查清單](../../results/20261014-b-q1-intake-4a8f8f2b/manifest.json)。先前全稿編譯與跨章需求舊值的缺口，已由 `abdbc4c` 共用整合處理，勿沿用舊狀態；歷史內容可由 Git 查閱。
