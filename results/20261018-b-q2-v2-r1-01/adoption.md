# Q2-V2-R1 方法採納／整合入口

|項目|建議|證據及限制|
|---|---|---|
|普通 SPT-HOL|維持平均等待主要方案|兩個規模和已測 K/event 配置中 Mean 最低；沒有 aging；仍有受損作業，Max 不是最低|
|K/timer 矩陣|納入方法穩健性證據|保留全部 12 格及負面結果；K=2000 是有界 FILL，不是無上限；部分尾部改善但 Mean 未改善|
|SPT-HEAD-TIME|保留實驗選項，不設為預設|完整 A10 P99 略降，Mean/Max 略升；大量預約與回放成本；無普遍性能／無飢餓保證|
|新增診斷|保留計數器，採 R1 解釋|run-wide repeated 不等於同刻重檢或浪費；同刻統計 NOT_AVAILABLE|

數值唯一來源為原 results/20261017-b-q2-v2-01/comparison.json 及其 benchmarks。
本目錄 tables.md、results_en.md、results_zh.md 由 build_revision.py 生成；
exact_comparison.json 原樣保存 metrics、四個互斥群組、分解與配對。
各規模的下界分開，不能解讀 gap 為可完全消除的因果損失。

成本是單次歷史 elapsed time；CPU time 未記錄。原表的 policy runtime 並非
完整 child wall，新表使用 wrapper 的 child_wall_seconds。scheduler_seconds
包括內部 capacity check；validation_seconds 是之後的 reservation replay；
I/O 欄沿用包含 schedule hash 成本的原欄位。不要宣稱獨立測到 CPU 使用成本。

## 證據分發與驗證範圍

- REPOSITORY_AVAILABLE：原聚合 JSON、這輪新增 14 份逐 byte summary、來源索引、
  hash、精確表格、完整重現參數和程序源碼（d29d895）。
- LOCAL_ONLY：14 組完整 timing、placement、reservation/events 及 phase log，
  位於 evidence_index.json 的相對 outputs 路徑；已逐檔核對原 summary hash。
  取得方式：由目前保管此 worktree 的隊員按索引交付原檔並驗 hash；尚無共享 URL
  或 committed archive。命令可重算不代表原始帳本已跨機分發。
- MISSING：未找到 14 組額外的獨立「持久化檔案回放」報告。原 runner 的
  validate()/validate_reservations() 使用程序內結果；summary PASS 代表這個範圍。
  本輪僅做檔案／來源核查，沒有補跑 scheduler 或把 hash check 寫成容量重播。

這修正前次任務記錄及對話對持久化驗證的過廣描述。原 manifest 保持不變，
以 R1 為整合時的語義勘誤；不改 V1 論文或歷史實驗數值。
