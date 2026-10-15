# B-Q3 唯一活動記錄

## 範圍與當前狀態

2026-10-15：執行第一輪有限整卡、啟動前 A10→A100 固定分流。模型／來源採納表見 [Q3 模型](../../problems/2026_gpu_scheduling/docs/q3_model.md)。不執行 Initial Job Relocation、不整合 Q2、不做大型敏感度矩陣。

## Git 基礎

已 fetch 並安全 fast-forward feat/b-q3：abdbc4ce07c3877ac9fdb1e846a5b9c3b803f401 → 7075317883808b1cd7f80cadf3980be291c69cf0（Q1）；此前已推送。開始實作前再次核對本地 HEAD、origin/feat/b-q1、origin/feat/b-q3 均為後者，Q2 為 8da62ad4ff5c68d1fb730e04c94cd0492e37614f，未引入。開始研究時四份使用者研究全文在本 worktree 為未追蹤檔；本次隨 Q3 一併納入版本控制，原文內容保持不變。Q1 新下界、paper 與研究程式均已承接。

## 凍結與執行

- 使用者已選 60 專屬完整 A100 節點與 10% SHA256 確定性分流；sigma=1 是假設。配置於 `problems/2026_gpu_scheduling/configs/q3_fixed_split_v1.json`，性能實驗前凍結。
- 共用 data/simulator/placement/evaluation/validation 與原始 CSV、Q1 成果不修改；Q3 以獨立分區包裝重用 DES。
- 已完成：40 項 B 題測試（14 項 Q3）、12 項根目錄測試、repo／diff checks；兩政策完整 M0/M1、原始 ID／逐節點帳本／獨立 metrics 與配對核查均 PASS。

2026-10-15 使用者明確授權 commit 與 push 本輪研究成果至 `feat/b-q3`。本次提交包含模型、程式、四份原始報告、小型正式結果與驗證記錄；不重新執行性能實驗。

## 第一輪交付與實測

正式清單與來源：[manifest](../../results/20261015-b-q3-fixed-split-c9e8f1a2/manifest.json)、[完整結果報告](../../results/20261015-b-q3-fixed-split-c9e8f1a2/README.md)、[metrics](../../results/20261015-b-q3-fixed-split-c9e8f1a2/metrics.json)、[獨立驗證](../../results/20261015-b-q3-fixed-split-c9e8f1a2/verified.json)。

- M0：B=0／K 關閉均精確恢復直接 DES，歷史逐筆時間／placement 與 H=7775878 metrics 也相同。主窗口另用 90d。
- M1：224112 原始作業全部排空；11209 個 A10 被固定分流（原 A10 GPU-work 的 9.95068%）；全部 80877 原生 A100 保留。
- FCFS：A10 平均等待 900.128570→587.875069h；全體平均 JCT 523.961182→368.910053h；窗口完成 165107→181112。
- SJF-HOL：A10 平均等待 32.906454→20.533731h；全體平均 JCT 93.352565→87.208824h；窗口完成 217570→217814。但 A10 P95 等待 11.086875→12.690806h，49772 個作業更晚完成，正延誤 68183.1825 job-hours。
- Native donor cost：兩政策原生 A100 逐 ID 額外等待／P99／Max／原零等待新增延遲數皆 0，窗口完成 80101 不變；只限此 trace，無未來服務保證。
- 分區閒置／GPU、CPU allocation／逐型號完整 GPU-hours／vCPU-hours 已報告，不混為新增 GPU 或金額收益。K、sigma=1 未經 benchmark。
- 初次完整 pilot 後補 CLI 持久化測試與外部配置可攜處理，正式版重新執行同一配置，metrics 精確相同；未進行參數搜尋。
- 原始 CSV、Q1 研究程式／下界／論文／既有正式結果與共用程式逐 byte 對 Q1 基底核查 PASS，見 protected_sources.json。Q2／main 未整合或修改。

大型帳本、實際執行來源快照、四份原始報告與重現說明封存於本機 `outputs/Q3_fixed_split_v1_delivery.zip`，SHA256 見 manifest；不含 raw CSV。共享儲存未確認，不宣稱其他電腦已取得。研究程式與小型結果隨本次提交保存；精確提交與遠端同步狀態以 Git 記錄為準。大型交付 ZIP 維持本機保存，不隨此次 Git push 上傳。

## 停止點

**GO**：物理合法與反事實核查符合第一輪標準。下一輪可按模型文件預宣告單因素 5%/20% 分流、30/90 節點、sigma=2；本輪未執行。系統 break-even threshold 未求得，不從單一 sigma 點推斷。第一輪完成後停止，等待下一條任務。

## 提交與推送

提交前已重新 fetch：遠端 Q3 與本地基礎一致，無分歧；Q2 已有後續遠端提交，但不引入 Q3。檢查提交範圍並沿用既有完整模型驗證，另執行必要 repo／單元／staged diff checks。實驗清單的 code.commit／dirty 與封存 ZIP 保留實際運行當時的版本狀態，不改寫歷史實驗來源。

兩份原始研究報告保留原有 Markdown 行尾雙空白；`.gitattributes` 僅對這兩份來源允許該格式並保留原始位元組，來源 SHA256 不變。
