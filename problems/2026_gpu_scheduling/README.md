# Problem B：Scheduling a GPU Cluster

唯一 B 題入口。題意依據為 [原題 PDF](docs/2026_MCM_GPU_Scheduling.pdf)，規範沿用 [modeling.md](../../modeling.md)。此分支只整合 **Q1**；`feat/b-intake` 的其他候選基準、原型與研究材料仍在獨立工作區，未包含於本次提交。

## 現況與驗證

| 範圍 | 狀態 | 證據／限制 |
| --- | --- | --- |
| Q1 原始 CSV 重算 | PASS | [q1_results.json](../../results/20261014-b-q1-intake-4a8f8f2b/q1_results.json)，全部 9 張表與交接包逐位元組相同 |
| Q1 交接比對 | PASS | [handoff_comparison.json](../../results/20261014-b-q1-intake-4a8f8f2b/handoff_comparison.json)，39 項非雜湊統計與 9 表吻合 |
| Q1 公式／圖／英文正文 | PASS | 6 項独立數值測試；四面板圖已重生並檢視；三部分正文與表格對齊 |
| 原資料 byte provenance | BLOCKED | job CSV 與交接包記錄雜湊不同；原始資料 ZIP 未提供，不能斷言編碼原因 |
| 英文全稿編譯／10 頁 | BLOCKED | 本機缺 LaTeX；原 ZIP 未附 Q2/Q3 圖，完整排版尚未核查 |
| Q2/Q3 | NOT_RUN | 本輪未跑調度實驗、未修改演算法或英文 Q2/Q3 章節；歷史性能結論未驗證 |

完整命令、參與程式與資料雜湊、實際檢查範圍見 [manifest.json](../../results/20261014-b-q1-intake-4a8f8f2b/manifest.json)。Q1 數值與圖可供正式論文採用；全稿還不能當作已驗證提交版。成員分工、資料公開再散布範圍、全隊正式環境待確認。原題第 3 頁要求英文不超過 10 A4 頁、字級不小於 11pt，列姓名並披露實際 AI 使用。

## 結構與唯一計算入口

```text
data/raw/                    既有兩個原始 CSV（未改寫）
docs/                        既有原題 PDF
src/gpu_scheduling/data.py   共用 checked byte loader
src/gpu_scheduling/q1.py     Q1 公式唯一實作
experiments/                eda_analysis、eda_deep、generate_figures、verify_q1
tests/test_q1.py             6 項獨立數值核查
paper/document_en.tex       英文 Q1 修正；其他章節保留原稿
requirements.txt            本機核查用固定套件版本
../../results/              小型統計表與驗證紀錄
../../outputs/              可再生 PDF／PNG（不提交）
```

[eda_analysis.py](experiments/eda_analysis.py) 為正式 Q1 CLI；[eda_deep.py](experiments/eda_deep.py) 僅轉用相同入口，避免公式漂移。[generate_figures.py](experiments/generate_figures.py) 延用原四面板配置、字體、配色與 `fig1_data_patterns.pdf/.png` 檔名，只生成 Q1，沒有 Q2/Q3 圖表硬編碼資料。

保留分型號統計、GPU/CPU 工作量、Lorenz、Gini、Top-k、Duration CCDF、時間變化與節點配比。修正口徑：

- `H_j = worker_num × gpu_request × duration`，單位 GPU-seconds；`rho = sum(H_j)/(T × GPU容量)`，`T=7,775,878` 秒。完整生命週期工作量／窗口容量不是實際利用率。
- A10 `rho=2.0640557`；假設提交時立即開始、忽略容量的 `[0,T)` 需求平均 **3,614.54040431** 張、峰值 **4,103** 張。事件積分與直接區間重疊一致，不能當作調度分配。
- GPU-series-1 包含 `(1GPU,128CPU)`、`(1,192)`、`(4,192)`、`(8,192)` 四種配置；超過 24 vCPU/GPU 門檻作業 **2,478** 個（**25.6974%**），佔該池工作量 **78.0668%**。
- `submit_time=0` 的 **3,512** 個作業是起點提交批次；節點初始空閒。24 小時分析稱 relative trace phase，校正部分小時 exposure，不猜真實時區。
- Lorenz 包含原點；CCDF 為 `P(duration > d)`，合併重複值；Top-k 用 `floor(n*f)`，前 1% 即 2,241 個作業、43.3025% 工作量。
- 全體平均 worker 數改為 **1.53889**，每 worker GPU 請求均值改為 **2.00277**，CPU 工作量／容量比改為 **0.47347**（英文四捨五入為 0.473）。

## 重現

在倉庫根目錄用 Python 3.11+。本機實際核查為 Python 3.12.3／NumPy 2.3.5／pandas 2.2.3／Matplotlib 3.10.8，並非已確認全隊環境。每次重跑換用尚不存在的 `run-id`，程式拒絕覆蓋結果。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r problems/2026_gpu_scheduling/requirements.txt
.venv/bin/python problems/2026_gpu_scheduling/experiments/eda_analysis.py --out results/run-id
.venv/bin/python problems/2026_gpu_scheduling/experiments/generate_figures.py --results results/run-id --out outputs/run-id-figures
PYTHONPATH=problems/2026_gpu_scheduling/src .venv/bin/python -m unittest discover -s problems/2026_gpu_scheduling/tests -v
# 比對交接成果需本機保留使用者提供的 ZIP，Git 不包含 ZIP 本體：
.venv/bin/python problems/2026_gpu_scheduling/experiments/verify_q1.py --handoff-zip Q1_final_handoff.zip --results results/run-id --out results/run-id/handoff_comparison.json
```

兩個資料／繪圖 CLI 的 `--data` 預設為本題 `data/raw`，可改成含兩個 CSV 的目錄或原始 ZIP，不依賴個人絕對路徑。loader 對此批 CPU 採精確 0.01 vCPU 縮放，遇到更細精度明確拒絕，不默默取整。小型證據可追蹤；ZIP、root 重複表、大型逐作業輸出、快取和可再生圖留在本機。

原 CSV 雜湊：

| 檔案 | SHA-256 |
| --- | --- |
| `data/raw/node_info_df.csv` | `1aba161961a5a4a1a61aa581383c5e5abe3400b59f8597ba8c4eef7597bc9d18` |
| `data/raw/job_info_clean.csv` | `ef14d696adc1b5c7847db49b41a068a998c8cd669e63922c92b3f1c3f32eedb0` |

歷史 job 雜湊 `735bc06c...ed38e1` 不同；獨立研究包兩份逐作業紀錄的 job ID 與 6 個輸入欄位曾逐欄核對吻合，摘要存於清單。不把欄位或統計相同等同於原檔位元組相同。

## 英文稿與繼續優化

[document_en.tex](paper/document_en.tex) 的 Q1 改為 **Data Characteristics、Supply–Demand Imbalance、Bottleneck Hypotheses**，保留一張精簡表與四面板圖。僅修改 Q1 正文及摘要中 Q1 項，Q2/Q3 章節逐位元組保留原文。

Q1 已移除利用率混稱、起點背景作業、現實鐘點高峰、未擬合 power-law 與確定因果敘述。但 Q3 仍引用旧 `3,664.0` 張／`~1,170` 張缺口；Q2/Q3 最優、性能与「全部獨立驗證」披露仍未核查。本輪尊重範圍沒有改動它們，後續跨章整合必須處理；不直接沿用全稿提交。

圖可用本地命令生成；將 Q1 PDF 放在論文編譯工作目錄，或設定該目錄的 graphicspath。缺的 Q2/Q3 圖資產與編譯器另行補齊再核查全稿，不以空白替代圖宣稱編譯通過。

下一步在本分支繼續 Q1 論述／圖表精簡與排版核查，保持計算口徑和重算比對。先完成該分支審閱，再與 `feat/b-intake` 協調共享 loader、README、requirements；不要覆蓋未提交 intake，亦不要將兩套模擬器接成平行正式入口。
