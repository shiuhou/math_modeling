# 專案入口

本檔集中保存選題、覆蓋與共用依賴；唯一規範正文見 [modeling.md](../modeling.md)，協作見 [CONTRIBUTING.md](../CONTRIBUTING.md)。沒有另建 SPEC／DESIGN／PLAN 副本。

## 現況

| 項目 | 已知狀態 |
| --- | --- |
| 任務 | feat/b-q1：已審核 Q1 成果最小整合；其他 intake 在獨立工作區，未包含 |
| 選題／來源 | 使用者已確認 2026 MCM Senior Group Problem B；核對既有原題 PDF 第 1–3 頁與兩個 CSV |
| 規則 | 初始空閒、非搶佔、duration 提交時已知、同 worker CPU/GPU 同節點、gang 同步開始；10 A4 頁英文、至少 11pt、姓名與實際 AI 披露 |
| 協作 | 隊員各自 clone、短期任務分支與 GitHub PR；worktree 僅供同機多任務選用 |
| 分工 | 主要負責人、審閱者與整合者待確認，不自行分派 |
| 資料 | 既有 raw CSV 未改寫；雜湊見 B 題入口。歷史 job byte 雜湊不同，缺原資料 ZIP；公開再散布範圍待確認 |
| 環境 | 本機 Q1：Linux x86_64、Python 3.12.3、固定 numpy/pandas/matplotlib；全隊正式環境／硬體預算待確認 |
| 論文 | 英文 LaTeX Q1 已修正；全稿編譯及頁數 BLOCKED，缺 LaTeX 與 Q2/Q3 圖資產 |
| Git | 不推 main、不合併 PR。Q1 允許 commit／push feat/b-q1；其他整合尚待審閱 |

## 題目覆蓋

| 子問／原題來源 | 交付 | 證據／狀態 |
| --- | --- | --- |
| Q1，PDF 第 2 頁 (1) | 資料特徵、容量／需求、集中度與瓶頸假說 | PASS：原 CSV 計算、39 項統計／9 表對照、獨立小例核查與四面板圖；來源 byte／全稿限制見清單 |
| Q2，PDF 第 2 頁 (2) | 符合逐節點容量的排序與放置、共享評價 | NOT_RUN：此分支只保留原英文 Q2 章節；原性能主張未核查 |
| Q3，PDF 第 2 頁 (3) | 明示假設的跨型號技術／財務評估 | BLOCKED：缺可追溯耦合驗證；原性能／最優性主張未確認，本轮未修改 |

研究細節、命令與限制只維護於 [B 題唯一入口](../problems/2026_gpu_scheduling/README.md)，Q1 小型結果見 [驗證清單](../results/20261014-b-q1-intake-4a8f8f2b/manifest.json)。

## 共用介面與依賴

- 原始欄位、秒為時間單位、每 worker 需求等按原題；loader 精確縮放 0.01 vCPU，遇更細精度拒絕，不默默捨入。
- Q1 兩個 EDA 入口共享同一 q1 模組；GPU work 是全生命週期，immediate-start 是忽略容量的假設需求，不代表調度利用率。
- 新的跨任務 loader／評價接口仍需相關隊員審閱；現有 Q1 實際輸入／输出、取整與窗口定義見 B README，勿另建平行公式。
- 正式證據保存按 [results 約定](../results/README.md)，可再生圖／大明細留本機 outputs；數值結論不得僅存在被忽略的圖中。

## 驗證與下一步

工程檢查與研究核查分開：倉庫檢查不證明 scheduler 正確，Q1 資料分析不證明 scheduler 最優。遠端 CI、各隊員電腦、全稿編譯與 10 頁限制未完成，按適用範圍標記 NOT_RUN／BLOCKED。

接續在 feat/b-q1 優化 Q1 與排版；其後審閱 intake 及共用 loader 重疊，再授權 Q2/Q3 正式實驗。Q3 仍有旧 3,664／約 1,170 GPU 需求描述、AI 披露與性能主張待處理，不能把本轮 Q1 PASS 外推成全稿 PASS。

本輪 Codex 用於資源核對、Q1 程式整合／重算、圖與英文編修；沒有求解器或新調度算法，也尚未由全體隊員人工審閱。
