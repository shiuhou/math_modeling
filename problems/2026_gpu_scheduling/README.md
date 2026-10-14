# Problem B：Scheduling a GPU Cluster

B 題唯一研究入口；題意依據是 [原題 PDF](docs/2026_MCM_GPU_Scheduling.pdf)，規範沿用 [modeling.md](../../modeling.md)。資料、程式、依賴及基本基線都在 Git 中，首次開工不需要任何對話附件或 ZIP。

## 開工與驗收

本次共用基礎在 `chore/b-intake-ready`，包含 `feat/b-q1` 已提交的 Q1。`feat/b-q2`、`feat/b-q3` 從相同整合提交起步；尚未合併 main。隊員各自在自己的電腦執行，將最後一行的分支換為所需題目：

```bash
git clone https://github.com/shiuhou/math_modeling.git
cd math_modeling
git fetch origin
git switch --track origin/feat/b-q2
# Q3 使用 git switch --track origin/feat/b-q3
python3 -m venv .venv
.venv/bin/python -m pip install -r problems/2026_gpu_scheduling/requirements.txt
python3 scripts/check_repo.py
python3 -m unittest discover -s tests -v
PYTHONPATH=problems/2026_gpu_scheduling/src .venv/bin/python -m unittest discover -s problems/2026_gpu_scheduling/tests -v
.venv/bin/python problems/2026_gpu_scheduling/experiments/run_baselines.py --smoke --out outputs/b-smoke-01
.venv/bin/python problems/2026_gpu_scheduling/experiments/verify_baseline.py --run outputs/b-smoke-01 --out outputs/b-smoke-01-verified.json
```

`--out` 拒絕覆蓋：重跑請改運行 ID。Python 3.11+；本機驗收為 Linux、Python 3.12.3、固定 numpy/pandas/matplotlib。Windows 請用 `.venv\Scripts\python.exe`；環境變數設定依 shell 調整，尚未在 Windows 驗證。全隊正式硬體／環境待確認。

Smoke 只取每型號前 64 個作業，用於工程驗收，不能作性能結論。完整確定性基線：

```bash
.venv/bin/python problems/2026_gpu_scheduling/experiments/run_baselines.py --out outputs/b-full-01
.venv/bin/python problems/2026_gpu_scheduling/experiments/verify_baseline.py --run outputs/b-full-01 --out outputs/b-full-01-verified.json
.venv/bin/python problems/2026_gpu_scheduling/experiments/make_figures.py --run outputs/b-full-01 --out outputs/b-full-01-figures
```

## 結構、資料與生成物

```text
data/raw/               原有兩個 CSV，保持原始 bytes
docs/                   原題、研究計畫、中文參考報告
src/gpu_scheduling/     唯一 DES、共享資料／評價器、Q1、獨立核查
experiments/            顯式 CLI；import 不啟動實驗
paper/                  英文整合草稿；原中文 HTML 僅供參考
references/originals/   ZIP 原始 Python／英文稿的逐 byte .txt 歸檔
references/             來源清單、小型歷史 JSON；非正式性能證據
tests/                  手算、容量、輸入／指標及持久化核查
../../results/          Q1 核算表、整合驗收與基線指標
../../outputs/          本機運行明細、圖與 LaTeX build（Git 忽略）
```

原題：節點初始空閒；CPU/GPU 是每 worker 請求；gang 同步開始、非搶佔；duration 提交時已知；同 worker 的 CPU/GPU 同節點且 GPU 型號匹配。共 224,112 jobs、4,278 nodes、10,412 GPUs。共享 loader 精確縮放至 0.01 vCPU，遇更細精度拒絕，不默默捨入。

| 資料（已在 Git） | SHA-256 |
| --- | --- |
| `data/raw/node_info_df.csv` | `1aba161961a5a4a1a61aa581383c5e5abe3400b59f8597ba8c4eef7597bc9d18` |
| `data/raw/job_info_clean.csv` | `ef14d696adc1b5c7847db49b41a068a998c8cd669e63922c92b3f1c3f32eedb0` |

所有計算 CLI 的 `--data` 可指定含兩個 CSV 的目錄或原資料 ZIP，不依賴機器絕對路徑。歷史交接記錄的 job byte 雜湊 `735bc06c…ed38e1` 不同，缺原資料 ZIP，不能推斷原因；歷史逐作業明細的 ID 與六個輸入欄位吻合目前 raw。資料公開再散布範圍待團隊確認。

不提交原 ZIP、cache、大型逐作業 CSV／節點 ledger、可重生圖。正式小型指標、檢查與來源雜湊保存到 [results](../../results/README.md)；大型明細由記錄的命令重算，正式研究需另外確認穩定的共享保存位置。不要只將論文數字留在本機 outputs。

## 共用實作與接口

- [data.py](src/gpu_scheduling/data.py)：`read_data(source) -> nodes, jobs, hashes`；時間秒、每 worker 欄位、`cpu_units` 為百分之一 vCPU；穩定排序。
- [simulator.py](src/gpu_scheduling/simulator.py)：唯一活動 DES，`simulate_pool(nodes, jobs, policy)`。保留 `FCFS`／`SJF-HOL` 相容別名，正式基線名為 `FCFS-HOL`／`SPT-HOL`；M1 提供 `SPT-FILL`、`SGW-FILL`、`EASY-TIME`、`SPT-URGENT-HOL`、`SPT-URGENT-TIME`；M2-A 新增 `SPT-URGENT-FIXED`、`SPT-URGENT-FLEX`、`EASY-NR`。所有策略共用 node-level CPU/GPU gang planner；TIME 只接納 `finish <= immutable promised_R`，FIXED/FLEX/EASY-NR 以可重播證書安全地接受 crossing。
- [evaluation.py](src/gpu_scheduling/evaluation.py)：唯一共享評價器。等待／JCT 包含全部作業直至排空；分位數 linear；BSLD 為 `max(1,JCT/max(duration,60s))`。分配率只積分 `[0,H)`，完成數 `finish <= H`；預設 `H = 最後提交時刻`，名義 90 天需顯式 `--horizon-seconds 7776000`。
- [validation.py](src/gpu_scheduling/validation.py)：獨立節點 CPU/GPU ledger 回放；微型 scalar oracle 僅供測試，不是第二套正式引擎。
- [run_baselines.py](experiments/run_baselines.py)：唯一基線／M1／M2-A 流程，記錄 `run.json`、來源 commit／dirty snapshot／雜湊、資料、參數、環境、耗時、全部 metrics、job times、node placements 及 reservation/event/certificate evidence；[verify_baseline.py](experiments/verify_baseline.py) 在另一程序從持久化明細核查，不信任 metrics 自報成功。`--theta-seconds`、`--reservation-k` 與 `--event-mode` 均明示配置。

Q2 M1 工程 smoke（只做正確性與持久化驗收，不是性能結論）：

```bash
.venv/bin/python problems/2026_gpu_scheduling/experiments/run_baselines.py \
  --smoke --theta-seconds 4860000 --reservation-k 200 \
  --event-mode shared-timer \
  --policies FCFS-HOL SPT-HOL SPT-FILL SGW-FILL EASY-TIME \
             SPT-URGENT-HOL SPT-URGENT-TIME --out outputs/q2-m1-smoke
.venv/bin/python problems/2026_gpu_scheduling/experiments/verify_baseline.py \
  --run outputs/q2-m1-smoke --out outputs/q2-m1-smoke-verified.json
```

`--event-mode shared-timer` 讓同一 theta 組的所有 policy 收到相同池內 ticks；沒有 urgent 的 policy 只把 tick 當調度機會。歷史 arrival/completion-only 對照使用 `--event-mode arrival-completion-only`，不能用 policy 名稱暗中選擇比較模式。 兩種模式均要求等待年齡 `t-a >= theta` 才有 urgent 資格：shared-timer 在精確 `a+theta` 提升；arrival-completion-only 在下一個到達／完成 epoch 檢查並提升，沿用相同 urgent FIFO 及原 promise 保護。預約驗證要求顯式 `reservations`／`events` 清單（無預約可為空清單）；缺失、null 或錯誤型別均驗證失敗。

Q2 以此引擎擴充排序／放置，勿另建 DES／評分器。Q3 保持此資料與評價口徑，跨池機制需耦合節點容量，不能各池各自許諾相同 donor 資源。改共用接口前於 [docs/brief.md](../../docs/brief.md) 提出並透過 PR 協調；不覆蓋 Q1 或另一題的修改。

M2-B 有界成本探針（只比較已明示的 A10 前綴，不能代替完整 trace）可用：

```bash
.venv/bin/python problems/2026_gpu_scheduling/experiments/run_m2b_benchmark.py \
  --jobs 16384 32768 --theta-seconds 4860000 --short-theta-seconds 4 \
  --reservation-k 200 --event-mode shared-timer \
  --policies SPT-URGENT-TIME SPT-URGENT-FIXED SPT-URGENT-FLEX \
  --out outputs/q2-m2b-bounded-01
```

它為每個策略建立獨立 child process，分開記錄 scheduler、獨立 reservation replay、評價、I/O 與 process peak RSS；短門檻只是機制壓力情景。若短門檻造成記憶體或時間失控，應停止並標記完整 trace `NOT_RUN`，不能從錨點前綴推論 FIXED/FLEX 性能收益。

## 驗證狀態與舊程式處置

| 部件 | 狀態與範圍 |
| --- | --- |
| Q1 共用公式、九張核算表、四面板圖 | 已驗證 PASS：原 CSV 重算、39 項統計對照、九表 byte 相同、數值測試與圖檢視；[Q1 清單](../../results/20261014-b-q1-intake-4a8f8f2b/manifest.json) |
| 正式 FCFS／SJF-HOL 基線及 evaluator | 已驗證 PASS：手算／30 組雙策略小案例、CLI 持久化核查；全 trace 各 224,112 jobs 已跑並獨立回放，不代表所有未來算法正確 |
| 源碼 ZIP 的 AMBF／EASY／特殊單 GPU 分支 | 待修正：GPU-only reservation 未保護 CPU/gang；特殊路徑硬編容量／排序；BSLD 缺外層 max；已作 inert `.py.txt` 歸檔，不接入正式流程 |
| 原 Q3 donor／MIG／pricing | 待修正／BLOCKED：缺 helper，donor 耦合與相容性／速度／價格假設未核實；不啟動舊算法 |
| 第二套可執行 DES、舊硬編圖／臨時路徑入口 | 待淘汰：不匯入為永久入口；原始 bytes 留存 Git，可研究方法後選擇性移植 |
| 中文研究報告／HTML、英文 Q2/Q3 性能表 | 參考資料／NOT_RUN；不是已驗證最終論文，圖中明示 archived claims |

[來源清單](references/intake_manifest.json) 保存每份 ZIP／member 雜湊、Git 原文位置、導入／排除理由。兩套來源差異：

| 面向 | 源碼 ZIP | 獨立研究包／整合基線 |
| --- | --- | --- |
| 排序 | FCFS、SAF、aging／EASY | FCFS `(submit,id)`；SJF-HOL `(duration,submit,id)`，不跳隊首 |
| 放置 | 動態排序；單 GPU 分支 LIFO／硬編 | FF `node_name`；逐節點 CPU/GPU、atomic gang |
| 事件 | 完成先於同時提交；部分分支可卡住 | 同事件順序；不可能作業顯式拒絕 |
| 窗口 | 名義 90 天 | 預設最後提交，與名義窗口分開 |
| 集中度 | floor | 原研究包 ceil；整合統一 floor |
| FCFS 全體平均等待／完成數 | 舊論文 447.37h／164,868，NOT_RUN | 重跑 446.970506h／165,035，PASS |
| 非 FCFS | SAF-BF 16.55h，NOT_RUN | SJF-HOL 16.361890h，PASS；不同策略不能當同方法誤差 |

獨立資料核算、歷史明細欄位／metric 核查及 ledger replay 留存。歷史 timings 沒有 node ledger，其舊容量可行性 BLOCKED；不能只因重算 metrics 相同就標成可行。不要將全部差異歸因於 122 秒窗口差異；放置和排序也不同。實際已做核查見 [intake_checks.json](references/intake_checks.json)。

## Q1 與論文入口

```bash
.venv/bin/python problems/2026_gpu_scheduling/experiments/eda_analysis.py --out outputs/b-q1-01
.venv/bin/python problems/2026_gpu_scheduling/experiments/generate_figures.py --results outputs/b-q1-01 --out outputs/b-q1-01-figures
# 可選：需本機 tectonic 或 pdflatex（不影響基本測試／基線）。
.venv/bin/python problems/2026_gpu_scheduling/experiments/build_paper.py --out outputs/b-paper-01
```

`eda_deep.py` 共用 Q1 入口，不重複公式。`H_j=W_j*g_j*d_j` 是 GPU-seconds；`rho=sum(H)/(T*capacity)` 不是利用率。A10 exact-window immediate-start 平均 3,614.54040431、峰值 4,103、容量 2,494；平均差 1,120.54040431 不是已證擴容方案。GPU-s1 按四種節點配置分析，超過 24 vCPU/GPU 為 2,478 jobs（25.6974%）。t=0 是提交批次，24 小時是 relative phase；Lorenz 含原點、CCDF 嚴格處理 ties，Top-k floor。

`build_paper.py` 從 raw 重算 Q1、生成共享數值 macros 及正式 Q1 圖；Q2/Q3 圖只重繪明示 NOT_RUN 的原稿表值，未執行舊方法，無插補值。Q3 的需求／容量圖改用精確事件積分。缺編譯器明示 BLOCKED。編譯結果、頁數與 logs 在 build 目錄；編譯成功不能代替研究或提交格式驗收。英文已修正需求／利用率混淆、錯誤 Gini 推論、BSLD 公式與披露；中文原稿保留參考。

## Q2／Q3 下一步

`feat/b-q2`：研究排序與放置，在共用 DES 接入候選，與本基線比較；不要將歷史 AMBF 表視為驗收結果。

`feat/b-q3`：先明示 compatibility、MIG／速度／價格與使用者行為假設，再研究耦合跨池方案；保留共享 evaluator。

主要負責人與 reviewer 待確認。不要求兩位隊員共用主機或同一 worktree；分支各自 commit/push，透過 PR 整合。Q1 後續變更由整合者協調進兩題，勿各自複製公式。此輪不重構／驗證舊 Q2/Q3，不推 main、不合併 PR。
