# 專案入口

唯一規範正文見 [modeling.md](../modeling.md)，協作見 [CONTRIBUTING.md](../CONTRIBUTING.md)。沒有另建 SPEC／DESIGN／PLAN 副本；B 題細節與可執行命令集中於 [B README](../problems/2026_gpu_scheduling/README.md)。

## 現況與題目覆蓋

| 項目 | 狀態 |
| --- | --- |
| 題目 | 使用者確認 2026 MCM Senior Problem B，已核對原題 PDF 與兩個 raw CSV |
| 規則 | 初始空閒、非搶佔、已知 duration、gang 同步、逐節點同 worker CPU/GPU；10 A4 頁英文、至少 11pt、姓名與真實 AI 披露 |
| 工程 | 一個活動 DES、共享 loader／evaluator、獨立 ledger replay；原 scripts 逐 byte inert 歸檔 |
| Q1 | feat/b-q1：唯一英文章節、繁中對照、正文／補充圖與獨立交付；數值沿用 39 統計／九表，最終狀態見 [Q1 任務](../notes/tasks/b-q1.md) |
| Q2 基線 | PASS：FCFS／嚴格 SJF-HOL 全 trace 各 224,112 jobs，節點容量及持久化 metrics 核查；改進算法 NOT_RUN |
| Q3 | 固定分流 pilot：60 完整 A100 節點、全 trace 10% SHA256 分流、假設 sigma=1；M0 恢復／M1 帳本與反事實核查 PASS，見 [Q3 任務](../notes/tasks/b-q3.md)；相容性與性能 benchmark 未驗證 |
| 論文 | 跨章 Q1 量綱／需求語義已修正；Q2/Q3 性能數字保留為未驗證歷史主張；編譯與排版狀態見整合驗收，不代表可提交 |
| 協作 | 各自在自己的電腦 clone；Q2/Q3 研究分支由同一整合提交建立。分工及 reviewer 待確認 |
| 資料／環境 | raw 保持不變、依賴固定；歷史 job byte 不同的原因未知；公開再散布範圍及全隊正式硬體待確認 |
| Git | 使用者授權整理後建立／推送 feat/b-q2、feat/b-q3；不推 main、不合併 PR |

## 共用介面與協調

- `read_data(source)` 回傳 nodes/jobs/input hashes；秒、每 worker 需求、0.01 vCPU 整數縮放。
- `simulate_pool(nodes,jobs,policy)` 是唯一活動 DES；FCFS 或 SJF-HOL，completions → arrivals → scheduling，FF 按 node_name；回傳 jobs/starts/ends/plans。
- `metrics(result,nodes,horizon)` 是共享 evaluator；全部作業排空等待，分配積分 `[0,H)`、完成 `end<=H`；預設 exact trace 窗口，名義 90 天須顯式設定。BSLD 最低為 1。
- Q1 build 新增 `--scope q1|full`，預設 full；全文與獨立預覽共用 `q1_section.tex`。整合者將 feat/b-q1 的共用入口變更併入 Q2/Q3，勿複製章節或手抄數字。
- Q1 兩個 EDA 入口共享 `q1.py`；完整生命週期工作量、immediate-start 假設需求、實際調度分配三者分開。論文共享 Q1 數值由 build 生成，不各章寫死。
- Q2 研究排序／放置；Q3 研究明示假設的耦合跨池方案；圖與全文由整合者協調。需要改共用 loader／DES／evaluator 介面時，在此記錄並由依賴方透過 PR 審閱，不另起永久引擎。
- 目前人員分工未指定，不把分支名當成已認領；不同電腦的 Codex 對話與本機 outputs 不會自動同步。

實際驗收與剩餘缺口見 [整合任務](../notes/tasks/b-intake.md)；正式證據按 [results 約定](../results/README.md) 保存。根目錄工程測試不證明模型正確，基線 PASS 不證明舊改進器／Q3 性能成立。使用者最新要求優先提供 Q2/Q3 開工基礎，本輪不測試或重構舊算法。

Q3 本輪以 disjoint physical partitions 包裝既有 `simulate_pool`，沒有變更共享 DES／loader／evaluator 接口；[正式模型與來源採納表](../problems/2026_gpu_scheduling/docs/q3_model.md) 明示 K、sigma、B、native donor cost 及固定分流。GO 僅表示可進小型敏感性研究，不證明真實硬體可相容或所有作業受益。Q2 分支未整合。
