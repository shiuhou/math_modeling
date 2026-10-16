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

## 2026-10-15：固定 GPU 容量樣本路徑下界

本次從乾淨 `bf2b998` 延續，在 Q1 worktree 增加有界補充；不重做 Q1、不重構或執行 Q2/Q3。正式證據見 [來源清單](../../results/20261015-b-q1-capacity-bound/manifest.json)、[逐項驗收](../../results/20261015-b-q1-capacity-bound/acceptance.json) 與 [六池精確結果](../../results/20261015-b-q1-capacity-bound/q1_capacity_bounds.json)。

- `q1.py` 新增純計算函式、合併同刻事件的大整數／有理數積分、區間中途歸零三角形與排空尾段；既有 EDA 另輸出小型 `q1_capacity_bounds.json`。沒有改公式、九表、39 欄或 exact observation window。
- `q1_publication.py` 從新 JSON 產生 A10 下界 macro；英文章節與繁中稿增加同一橋接段落。正文仍兩頁、11pt 以上、一表兩圖。移到補充材料的應用類型限制及節點機制示例完整保留，不改結論。
- 唯一新增證明模板 `paper/q1_capacity_proof.html` 由原 build 合入 `supplementary.html`，並隨來源快照打包；六池精確有理數、A10 短時作業形狀與 Q2 引用界線也由資料生成。
- PASS：樣本路徑恆等式與容量下界推導核查；8 項原 Q1／聚合測試、8 項新增下界測試（含六池獨立 80 位 Decimal 下包絡積分）、2 項交付測試，共 18 項。零負載、尾段、中途歸零、同刻事件、合法排程恆等式、int64 外大乘積皆覆蓋。
- PASS：原 CSV 的 39 項統計及九表嚴格回歸，九表 bytes 相同；原 46 個出版數值不變。A10 前段／尾段／合計為 560.3121107156859／0.20925717461523632／560.5213678903011 h。A100、GPU-s1 精確為零；H800 為 0.000013501502196346032 h，GPU-s2 0.0014565503246249541 h，A800 0.025312126908034034 h，保留完整分數。
- PASS：A10 短時作業 `duration<=3600` 從 raw 算得 87,953 個，其中 377 個多 worker、最大 32 workers；節點為 2 個 (1 GPU,126 vCPU) 和 2,492 個 (1,128)。只支持「短不等於小 gang」動機，不引入調度性能或 QoS 主張。
- PASS：Q1 最終兩頁逐頁 PNG 檢視、繁中段落／證明視覺檢查、HTML 離線連結與圖片、無 TeX overfull／undefined；正文約 11.059 PDF pt 未縮小。交付 ZIP 1,089,667 bytes，包含新結果／證明，排除 raw／環境／快取／大型明細。從 ZIP 來源在乾淨目錄、沿用 Q1 已裝環境重建 PASS，六池／舊統計／九表／中英文 HTML 一致；沒有安裝或升級依賴。
- PASS：根目錄 12 項測試、倉庫連結／JSON、diff 空白檢查。共享 loader／DES／placement／evaluator／validation、raw、依賴、全局 preamble、全稿與 Q1 摘要逐 byte 對照 `bf2b998` 均未變。
- NOT_RUN：本輪全文編譯、Q2/Q3 排程與參數搜索、人工雙語審閱；BLOCKED：歷史 job byte 身份、再散布範圍、姓名／最終 AI 披露。未要求 Q2 停止，未操作其 worktree、環境、配置或結果，也未操作 Q3／main。

輸入 job SHA 仍為 `ef14d696adc1b5c7847db49b41a068a998c8cd669e63922c92b3f1c3f32eedb0`；與外部數值吻合不證明歷史 ZIP bytes 相同。560.3 h 原型與前段取位相符，但缺原型程式，不宣稱已定位漏尾段源碼錯誤。

本機新版成品：`outputs/q1-capacity-release/`；來源基準為 `bf2b998` 加此次 Q1 修改，build 記錄 dirty 狀態與所有實際來源雜湊，ZIP 保存精確快照。新 JSON 生成流程本身不執行測試，故其 `unit_tests=NOT_RUN`；已實際執行的測試狀態在上述獨立驗收證據中，不手改計算 JSON 來假裝自驗成功。

Q2 後續以保存的作業識別碼／start 聯結原始屬性，計算同一全量池 `sum(H*(start-submit))/sum(H)`；本次沒有加入指標或改運行 evaluator。GPU 工作量加權等待不是普通平均／個別／最大等待，也不是浪費 GPU-hours；零下界不證明零等待可行，不宣稱緊性、最優或等待守恆。不同作業子集、容量、duration、Q3 型號遷移須重新推導／計算，不直接引用原 A10 下界。

相對 `bf2b998` 的共用入口變更只在 Q1 模組與 build；整合者日後按分支最新進度正常選取／合併。此次不自動合併到 `main`、`feat/b-q2` 或 `feat/b-q3`。
