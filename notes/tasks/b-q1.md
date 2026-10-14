# B 題 Q1 修正版整合

依使用者授權，Q1 成果提交／推送目標為 `feat/b-q1`；`feat/b-intake` 的其他研究資源整合保留本機，不合併 main、不建立 PR。唯一工作入口與下一步見 [B README](../../problems/2026_gpu_scheduling/README.md)，實際數值與驗證見 [Q1 清單](../../results/20261014-b-q1-intake-4a8f8f2b/manifest.json)。

Q1 公式採交接包，兩個 EDA CLI 共用一份實作；四面板圖改為資料驅動。英文只修改 Q1 和摘要 Q1 項，Q2/Q3 章節雜湊保持原樣。原資料未改寫，ZIP／大明細／可再生圖未提交。

實際 PASS：從原 CSV 重跑、39 項統計和 9 表比對、6 項 Q1 数值測試、四面板重生與視覺檢查；12 項根目錄工程測試。獨立 intake 的 13 項小案例檢查已通過，但不是 fresh 全 trace 調度驗證。

剩餘：原資料 ZIP 與歷史 job byte 身份 BLOCKED；全稿編譯／10 頁 BLOCKED；Q3 仍有旧 3664／1170 需求敘述（跨章一致性 FAIL），本輪未越界修改；Q2/Q3 性能 NOT_RUN。後續先在 feat/b-q1 优化 Q1 排版／表述，再與 intake 協調 loader／README，勿覆蓋其他整合工作。

後續狀態：以上是 Q1 分支交付時的歷史記錄；共用工程、跨章修正與 Q2/Q3 分支建立見 [intake 任務](b-intake.md)，勿將原本 BLOCKED 當作最新狀態。
