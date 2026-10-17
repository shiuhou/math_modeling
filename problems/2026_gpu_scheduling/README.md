# Problem B：Scheduling a GPU Cluster

B 題唯一研究入口；題意依據是 [原題 PDF](docs/2026_MCM_GPU_Scheduling.pdf)，規範沿用 [modeling.md](../../modeling.md)。資料、程式、依賴及基本基線都在 Git 中，首次開工不需要任何對話附件或 ZIP。

## 目前正式狀態與開工

第一輪 Q1、Q2、Q3 已整合進 Baseline V1；正式 main 合併提交為 `4ee2c6bfa98cf7177ff976abe73b122889437f46`，技術整合驗收提交為 `9f76e086690e574d73ca54cfb0c08d7e9eb0b9fe`。固定參考 tag 是 `2026-mcm-b-baseline-v1`。正式最新來源為 Q2 `b91918bb084848b93de642ad4e3ea0a7d3f25e68` 與 Q3 `170cc37a820e830a969cb1b1cd3cadb1e8fdf256`。

Q2 的最新 SPT-HOL／SPT-FILL 比較已驗證。Q3 的 M0、S0、S1–S5 共 14 組情景已驗證；合併後共享 DES 重新執行 14 組，與歷史排程逐 ID 精確一致。9 頁英文保底論文與 code supplement 位於 [paper output](paper/output/)，完整來源索引見 [paper_sources.json](paper/paper_sources.json)。正式競賽提交仍待隊伍身份、人工作者確認及最終 AI 披露。

新隊員按分工使用既有第二輪分支：`feat/b-q2-k-ablation`、`feat/b-gang-placement`、`feat/b-q3-substitution-v2`。其他研究分支必須從 `2026-mcm-b-baseline-v1` 建立；Baseline V1、原始資料、容量、事件契約與共同 evaluator 都是不可變比較基準。不要覆寫已驗證 results；共享程式修改先經 PR 協調。

開工命令：

```bash
git clone https://github.com/shiuhou/math_modeling.git
cd math_modeling
git fetch origin --tags
git rev-parse 2026-mcm-b-baseline-v1^{}
# 依分工切換既有分支，例如：
git switch --track origin/feat/b-q2-k-ablation
python3 -m venv .venv
.venv/bin/python -m pip install -r problems/2026_gpu_scheduling/requirements.txt
python3 scripts/check_repo.py
python3 -m unittest discover -s tests -v
PYTHONPATH=problems/2026_gpu_scheduling/src .venv/bin/python -m unittest discover -s problems/2026_gpu_scheduling/tests -v
```

完整命令與歷史實驗仍保留在本文件後段；重新執行時使用新的輸出 ID，不覆蓋既有 results。正式證據與來源導航見 [results](../../results/README.md)。

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
- [run_gs1_placement_matrix.py](experiments/run_gs1_placement_matrix.py)：GS1 異質節點 placement v2 的唯一凍結入口；執行 FCFS-HOL／SPT-HOL × `ff-id`／`ratio` 及 seed 17／29 的 FF 敏感性，共八組，固定 `shared-timer`、`theta=604800` 秒與完整排空，並寫入 paired strata、persisted ledger 和獨立 replay。`ratio` 只排序原始 CPU/GPU 形狀，真正可行性仍由 worker slots 判定；預設 simulator placement 保持 `ff-id`。

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
  --timeout-seconds 900 --max-rss-kib 4194304 \
  --out outputs/q2-m2b-bounded-01
```

它為每個策略建立獨立 child process，分開記錄 scheduler、獨立 reservation replay、評價、I/O 與 process peak RSS；可用 timeout／RSS 上限中止子程序，並留下 `TIMEOUT` 或 `RSS_LIMIT` 狀態與診斷。短門檻只是機制壓力情景。若短門檻造成記憶體或時間失控，應停止並標記完整 trace `NOT_RUN`，不能從錨點前綴推論 FIXED/FLEX 性能收益。

reservation evidence schema `2` 在履約後移除 dense CPU/GPU vectors，只保留 snapshot hash、immutable witness、版本、稀疏 crossing delta、履約及事件 ledger；活動中的 reservation 才保留 scheduler 所需 snapshot。validator 不會把缺少 schema 或舊 schema 靜默當作新證據。

## 驗證狀態與舊程式處置

| 部件 | 狀態與範圍 |
| --- | --- |
| Q1 共用公式、九張核算表 | 已驗證 PASS：原 CSV 重算、39 項統計對照、九表 byte 相同、數值測試與圖檢視；[Q1 清單](../../results/20261014-b-q1-intake-4a8f8f2b/manifest.json) |
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

Q1 延續整合基礎 `abdbc4c`，其獨立交付已整合進 Baseline V1；以下命令只供歷史 Q1 交付重現，使用上方相同 Python 環境；另安裝 Tectonic（本機 0.17.0）或 pdflatex，首次編譯可能下載 TeX 套件。可用 `--compiler PATH` 指定編譯器，缺少時明示 BLOCKED。

```bash
# 從 Git 中的 raw CSV 生成兩頁英文、繁中離線 HTML、正文／補充圖與交付 ZIP。
.venv/bin/python problems/2026_gpu_scheduling/experiments/build_paper.py --scope q1 --out outputs/q1-run --bundle
# 與 Git 中已核查的 39 項統計及九張表比較，不需要原交接 ZIP。
.venv/bin/python problems/2026_gpu_scheduling/experiments/verify_q1.py --reference-dir results/20261014-b-q1-intake-4a8f8f2b --results outputs/q1-run/q1 --out outputs/q1-run-verified.json
# 相關數值／交付測試；不執行全量調度。
PYTHONPATH=problems/2026_gpu_scheduling/src .venv/bin/python -m unittest discover -s problems/2026_gpu_scheduling/tests -p 'test_q1*.py' -v
# 全稿仍是預設；包含明示 NOT_RUN 的 Q2/Q3 歷史圖，不重驗算法。
.venv/bin/python problems/2026_gpu_scheduling/experiments/build_paper.py --scope full --out outputs/b-paper-run
```

每次使用新的 `--out`。`--data` 可覆寫 CSV 目錄或原資料 ZIP。交付目錄包含 `q1_en.pdf`、`q1_zh.html`、`supplementary.html`、`figures/` 的 PDF／PNG、`q1/` 九表及統計、數值 macros、來源快照與 `build.json`；`--bundle` 額外產生低於 50 MB 的 `Q1_delivery.zip`。閱讀 HTML 必須保留相鄰圖像目錄，無須網路。ZIP 不重複裝入 raw CSV；重現時從 clone 的 `data/raw/` 取得，按 `DELIVERY.txt` 執行。歷史 job byte 差異仍未消除。

英文唯一章節為 [q1_section.tex](paper/q1_section.tex)，由全稿及獨立 PDF 共用；[q1_summary.tex](paper/q1_summary.tex) 提供摘要 Q1 項，[preamble.tex](paper/preamble.tex) 共用格式。[q1_zh.html](paper/q1_zh.html) 是繁中對照模板；舊 `document_zh.html` 仍只作歷史參考。英文、中文表格與全文 Q1 引用的數值由 [q1_publication.py](src/gpu_scheduling/q1_publication.py) 讀取既有結果產生，不另建公式。

正文固定六型號一表、兩圖：`fig1_data_patterns` 保留檔名，改為 Lorenz／CCDF 雙面板；新增 `fig1_demand`，以既有事件積分計算精確每日需求，保留最後不足一天。五張補充圖包括完整分型號分布、份額、每日提交／工作量、relative phase 與節點配比。單獨計算／繪圖仍可使用：

```bash
.venv/bin/python problems/2026_gpu_scheduling/experiments/eda_analysis.py --out outputs/b-q1-01
.venv/bin/python problems/2026_gpu_scheduling/experiments/generate_figures.py --results outputs/b-q1-01 --out outputs/b-q1-01-figures --figures all
```

`--figures main|supplementary|all` 預設 `main`；Q2/Q3 歷史圖須額外 `--paper-reference`。`eda_deep.py` 與 `eda_analysis.py` 仍共用 Q1 公式及原九表格式。`H_j=W_j*g_j*d_j` 是 GPU-seconds，`rho=sum(H)/(T*capacity)` 不是利用率。A10 exact-window immediate-start 平均 3,614.54040431、峰值 4,103、容量 2,494；平均差 1,120.54040431 不是已證擴容方案。GPU-s1 按四種節點配置分析，超過 24 vCPU/GPU 為 2,478 jobs（25.6974%）。t=0 是提交批次，24 小時是 relative trace phase；Lorenz 含原點、CCDF 使用嚴格大於並合併 ties，Top-k floor。

本輪 Q1 兩頁、全稿九頁；39 統計／九表、180 每日區間、18 項 B 測試與乾淨 clone 重現均 PASS。全稿 Q2/Q3 舊小字／寬表仍有格式缺口。驗收與未確認事項集中於 [Q1 任務筆記](../../notes/tasks/b-q1.md)。編譯與計算成功不代表人工審閱或整篇競賽提交已完成。整合 Q2/Q3 時須一併採用共用章節、數值及 build／figure 入口；新增 Q1 圖會自然改變後續圖號，應使用 LaTeX label 交叉引用。此分支不直接改動兩個研究分支。

### Q1 固定型號池等待下界補充

上述 EDA 與 `build_paper.py --scope q1` 會另生成 `q1/q1_capacity_bounds.json`，不改 39 項統計、九表或 `T=7775878` 秒。新純函式 `q1.capacity_bound(arrival,duration,quantity,capacity)` 使用大整數／有理數事件積分，包含最後立即完成事件之後的流體排空尾段；回傳工作量、積壓、面積、下界及流體排空時間。結果保留精確分子／分母，近似數值僅供顯示。

這是全量原始隔離池的 **GPU 工作量加權等待** `sum(H*waiting)/sum(H)` 下界，放鬆 CPU、節點形狀及 gang 約束；不是普通平均或個別等待下界，不證明最優。A10 前段 560.3121107156859 h，尾段 0.20925717461523632 h，合計 560.5213678903011 h；其他池的小正值沒有捨入成零。完整證明與六池精度結果隨既有 `supplementary.html`／交付 ZIP 生成；正文仍兩頁、一表兩圖，中英文 A10 數字共用生成 macro。

[新增驗收](../../results/20261015-b-q1-capacity-bound/acceptance.json)、[精確結果](../../results/20261015-b-q1-capacity-bound/q1_capacity_bounds.json) 記錄來源、測試與剩餘缺口。Q1 18 項針對性測試、六池獨立高精度核算、39 統計／九表回歸、兩頁呈現及來源快照乾淨目錄重現 PASS；團隊人工審閱 NOT_RUN，歷史 byte 身份／再散布範圍 BLOCKED。該 Q1 歷史快照當時未執行 Q2/Q3 或全文編譯；目前正式 Q2/Q3 驗收請以本文件「目前正式狀態」及 results 導航為準。

Q2 日後可將已保存 job ID／start 與原始 worker／GPU／duration 連結，計算同一完整池的加權等待，無須重新排程；本輪不改 evaluator。不得將全量 A10 下界套到作業子集、不同容量／時長或 Q3 跨型號 run。`q1_summary.tex`、全局 preamble、全稿 Q2/Q3、共享 loader／DES／evaluator 及兩個研究 worktree 都未修改。

## Q2／Q3 下一步

`feat/b-q2` 與 `feat/b-q3` 是已刪除的第一輪歷史分支名稱；其結果已由 Baseline V1 固定保存。第二輪請使用 `feat/b-q2-k-ablation`、`feat/b-gang-placement`、`feat/b-q3-substitution-v2`，或從 tag 建立新的研究分支。不要將歷史 AMBF 表視為驗收結果。

第二輪 Q3 研究仍須明示 compatibility、MIG／速度／價格與使用者行為假設，再研究耦合跨池方案；保留共享 evaluator。

主要負責人與 reviewer 待確認。不要求兩位隊員共用主機或同一 worktree；分支各自 commit/push，透過 PR 整合。Q1 後續變更由整合者協調進兩題，勿各自複製公式。此輪不重構／驗證舊 Q2/Q3，不推 main、不合併 PR。

## Q3 固定分流 v1

[模型與四報告採納表](docs/q3_model.md)、[唯一活動記錄](../../notes/tasks/b-q3.md)、[正式第一輪結果](../../results/20261015-b-q3-fixed-split-c9e8f1a2/metrics.json)。本版只做有限整卡、啟動前 A10→A100 替代；原始到達全 trace 使用固定 10% 雜湊分流，60 台 A100 外來專屬、372 台原生專屬。sigma=1 與相容性是假設，60 非最優；不使用第 0 天最長作業搬遷。沒有新增物理容量。

```bash
.venv/bin/python problems/2026_gpu_scheduling/experiments/run_q3_fixed_split.py --out outputs/b-q3-new-id
.venv/bin/python problems/2026_gpu_scheduling/experiments/verify_q3_fixed_split.py --run outputs/b-q3-new-id
```

主窗口 7776000 秒、等待與 JCT 完整排空；M0 的 B=0／關閉相容性均逐筆精確恢復原 DES。獨立驗證從 raw 重建分流，再重播單一實體節點帳本並重算指標。兩政策全 trace 第一輪 PASS，性能結論僅適用當前假設與 trace；SJF-HOL 平均改善仍伴隨部分 A10 延誤，不宣稱全面優越。原生 A100 全部納入比較，本 trace 新增等待為零；這不是原生服務的普遍保證。詳細數字及本機證據封存位置見活動記錄與正式 manifest。
