# Q3 v1：有限整卡、啟動前固定分流

本版是情景模型與確定性調度實驗，目標為可行性與完整反事實比較，並非最優性證明。依據官方 `2026_MCM_GPU_Scheduling.pdf` 的 worker 同節點 CPU/GPU、gang 同步、不可搶占與全部完成要求。保留官方原始 CSV、Q1 成果及共用 DES/evaluator 不變。SPT 對應既有 **SJF-HOL**：只考慮已到達作業，隊首不能放置就等待，不回填。

## 來源採納／修訂／排除

四份使用者提供全文均在本 worktree 取得並閱讀，來源不是新一輪原論文查證。原始全文不改寫；確切 SHA256 見正式結果 `sources.json`。文獻適配只表示報告中的機制啟發，不宣稱重現或重新核對 Gavel、Synergy、HiveD、Themis 系統。

| 報告／本機來源 | 採納 | 修訂 | 本輪排除 |
| --- | --- | --- | --- |
| Q3 方案選擇 `docs/4.md` | 有限異構替代、接收池損失 | 原生政策凍結為已驗證 FCFS/SJF-HOL，Q2 不整合 | 動態策略與額外調度器 |
| GPU 調度文獻適配 `docs/貼上的文字 (1)(2).txt` | Gavel 的異構性能參數、Synergy 的 CPU/GPU 匹配、HiveD 的資源形狀／保護、Themis 的 JCT 視角 | K 與 sigma 都是情景假設；按原始 ID 配對 | MIG、拍賣、RL、系統復刻 |
| Q3 反事實分析 `docs/貼上的文字 (2)(2).txt` | 固定原始群體、全到達序列、完整 donor cost | 該報告部分 M1 為新增容量；本版 M1 明確重新命名為同實體容量固定分流 | 12 情景矩陣、Shapley、唯一因果貢獻比例 |
| `docs/deep-research-report_q3.md` | K／sigma／B 分層、無替代恢復 | 池容量約束補為逐節點物理約束；本 pilot 採已選定硬分區，與軟借用建議區分；官方本地 Senior 題目優先 | 動態借用、最優／單調性推論、未查證的競賽身份疑慮 |

Static-60 只定義容量情景；不是「第 0 天最長 480 個作業搬遷」。Initial Job Relocation 不在本次實驗。

## 正式模型

作業 j 的原始 ID、到達 a_j、原生型號 n_j、duration p_j（秒）、worker 數 w_j、每 worker 整卡需求 q_j、CPU 需求 c_j 皆保留。節點 i 的型號 g_i、GPU 容量 G_i、CPU 容量 C_i 來自原始資料。實際型號 m_j、相容性 K_jm∈{0,1}、倍率 sigma_jm>0；p'_j=sigma_jm p_j。本版原生邊 K_j,n_j=1，唯一外來邊為假設 A10→A100-SXM4-80GB；未經 benchmark 證明相容或加速。sigma=1 只是等時情景，不是保守界或最佳收益上界。

變數為啟動 s_j≥a_j、完成 f_j=s_j+p'_j，以及整數 y_ji≥0（j 在 i 的 workers）。要求：

- K_j,m_j=1，sum_i y_ji=w_j；y_ji>0 僅可在 g_i=m_j 的允許分區。
- 任意節點 i、時間 t：sum_{j:s_j≤t<f_j} q_j y_ji≤G_i，sum_{j:s_j≤t<f_j} c_j y_ji≤C_i。
- 一個 worker 的 CPU/GPU 在同節點；全部 workers 同時啟動與結束；一個 job 不混型號、不中斷、不遷移、不複製，所有原始作業最終完成。

A100 節點按 node_name 升序，首 60 台為外來專屬 D，其餘 372 台為原生專屬 N。B_A100=sum_{i∈D}G_i=480 整卡；借出 CPU 為這些節點的實體 CPU（7680 vCPU），不能另外憑空借用。D 與 N 不交疊，不重複佔用 A100。D 閒置也不服務 native；須報告其閒置及 native 成本。若 B=0 或相容性關閉，完全撤除分區，432 台回到原生池。分區後任何原生作業空池不可行即拒絕情景，不丟棄作業。

本研究評估策略，不將確定性 heuristic 偽裝為求解最優化。主要結果為原生 A10 的等待/JCT/尾部與完成數，保護指標為原生 A100 的配對延遲/尾部/原零等待新增延遲；全體平均 JCT、正完成延誤總量、固定窗口完成數與實體分配／執行成本同時列出。

## 凍結的分流規則

1. eligibility：原生 A10、允許假設替代邊，且完整 job 能在空 D 中依每 worker CPU/GPU 同節點放下。只讀本 job 與預先固定容量；不看等待結果、duration 大小、日期或未來到達。
2. UTF-8 `q3-fixed-split-v1:<十進位 job_name>` 的 SHA256 全 256 位整數 U；當 10U<2^256，固定分往 D。10% 是雜湊門檻，不是精確名額；實際筆數與 GPU-work 比例另報。
3. 不合格留原池並標原因；合格未選中留原池；已選中但暫時不足容量就在 D 隊列等候，不 fallback、不重路由。
4. FCFS 用 (arrival, ID)，SJF-HOL 用 (effective duration, arrival, ID)。節點升序 First Fit，先全部完成釋放、再到達、再排程。採既有可知 duration 假設；分流本身不用 duration 選受益者。

跨池共享接口的最小設計就是 `route(nodes,jobs,config) -> disjoint physical pools, effective jobs`；各分區獨立呼叫同一 `simulate_pool`，回傳同一原始 ID 與實體節點帳本。沒有第二套永久 DES，也沒有修改共用接口供其他任務依賴。當前硬分區不需要動態共享引擎。

## 比較與驗證協議（性能執行前凍結）

- 固定 224112 原始 IDs，全 trace 到達，兩政策均比較 M0 隔離與 M1 固定分流。M0 與直接原 DES 逐筆 start/finish/實體 placements 精確相同；B=0 與 K 關閉各驗證一次。
- 主窗口 H=7776000 秒（90d），分配積分 [0,H)，完成為 f≤H；等待/JCT 由完整排空計算，不刪未於 H 完成者。歷史基線 H=7775878 另重算核對，不混口徑。
- 原生 A10 群體包含分流與未分流；原生 A100 全部保留。每情景按原始 ID 配對。wait=s-a，JCT=f-a；分位數為 NumPy/pandas 預設線性插值。正延遲總量=sum max(0,f_M1-f_M0)，與有符號平均差區分。
- physical allocation 為實際型號／分區 work 除其實體容量×H；全體除原始全部物理容量。不把原生 A10 當作實際 A10 分配分母。
- 成本報完整 GPU-hours（逐實際型號）和 vCPU-hours；沒有定價，不報金額、不將不同型號 GPU-hours 當等效算力。M1 沒有新增 GPU；新增實體容量如未來使用須獨立對照。
- 獨立驗證器從原始資料重建 eligibility/hash/partition，從持久化 ledger 逐節點重播，檢查整數時間／完整 ID／原始欄位／duration／worker／資源，並獨立重算指標、配對差、queue 積分及資源工作量恆等式。不是以 repo checks 代替模型驗證。

Q1 新下界約 560.521h 為原始 A10 隔離池的 GPU-work 加權等待下界，非普通平均等待、非 Q3 下界。本版只承接其資料契約與工程基礎。

## 執行與下一輪條件

```bash
.venv/bin/python problems/2026_gpu_scheduling/experiments/run_q3_fixed_split.py --out outputs/b-q3-fixed-split-v1 --historical-baseline /home/shiuhou/math_modeling-b-intake-ready/outputs/b-intake-full-final
.venv/bin/python problems/2026_gpu_scheduling/experiments/verify_q3_fixed_split.py --run outputs/b-q3-fixed-split-v1
```

歷史比較參數是本機可選回歸來源；核心重現只需官方兩 CSV 與版本化配置，不依賴另一 worktree。輸出目錄必須不存在，不覆蓋前次證據。來源快照、配置、每 job/每節點帳本、metrics、recovery、verified 與雜湊封存一併交付；小型正式結果進 results，大帳本封存於 outputs，未確認跨機共享儲存。

GO 條件為兩政策 M0 恢復與 M1 全帳本／ID／指標驗證均 PASS，不要求 M1 優於 M0。下一輪僅預宣告單因素 routing .05/.20、donor 30/90 節點、sigma=2（其餘保持本版），本輪不執行。沒有 benchmark，只能報給定 sigma 條件結果；固定啟動下單 job sigma_crit=1+(s_M0-s_M1)/p 僅為代數條件，實際系統 break-even 需要重跑時間表，不能由本次單一點聲稱已找到。
