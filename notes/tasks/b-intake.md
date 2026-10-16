# B 題共用工程整合

整合基於 `feat/b-q1` 的 `5c933187d3d82d3a3ad8d6225946f32657fcbeff`，工作分支 `chore/b-intake-ready`。原 `feat/b-intake` 工作目錄與所有未提交修改保留；main 不動。使用者已授權整理完成後建立／推送 `feat/b-q2`、`feat/b-q3`，並要求優先開工，不測試／重構舊 Q2/Q3 方法。

選擇性導入兩 ZIP 與 Q1 交接包：原 Python／英文稿以 inert `.txt` 保存原 bytes／SHA，中文稿保留參考。只保留一個活動 DES、一個 evaluator、一條基線流程；獨立 replay、微型 oracle 與資料核算保留。排除 ZIP、cache、大型 job times／ledger、重複圖；逐 member 清單見 [intake_manifest](../../problems/2026_gpu_scheduling/references/intake_manifest.json)。

已執行：全 trace FCFS／SJF-HOL 各 224,112 jobs，獨立容量回放、保存後輸入／指標核查通過。FCFS 全體平均等待 446.970506h、窗口完成 165,035；SJF-HOL 16.361890h、217,501。這是本工程基線，不替換或背書舊 AMBF／Q3 性能表。

跨章修正：Q3 mean demand 改為 Q1 的 3,614.54、mean excess 1,120.54（非已證擴容需求）；Gini 不推導 Cv²／最優；BSLD 最低 1；節點配置例外、zero CPU、需求與利用率語義、披露同步。圖保留可用風格，Q1 原始資料重算，Q2/Q3 只畫帶 NOT_RUN 標記的原稿表值，不補造數字。英文仍為研究草稿，中文歷史參考未改性能結論。

基本 clone／命令與接口見 [唯一 B README](../../problems/2026_gpu_scheduling/README.md)。驗收詳情與編譯狀態保存於 [整合驗收](../../results/20261014-b-intake-ready/acceptance.json)。剩餘：舊 improved policies 與 Q3 不重驗；missing helper、歷史 node ledger、原資料 ZIP、資料公開範圍、正式環境、姓名、reviewer 待確認。Q2／Q3 研究後各自 PR，由整合者處理共用碼與論文衝突。

乾淨 clone 驗收 PASS：新 venv 安裝固定依賴、12 根測試／14 B 題測試、README smoke 與獨立持久化核查均通過；沒有附件 ZIP。全稿編譯 PASS，9 頁；原寬表縮字低於 11pt，提交版排版尚未完成，留待研究定稿，不阻塞 Q2/Q3 開工。
