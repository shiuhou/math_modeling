# 2026 MCM Senior Problem B — Q2 獨立演算法正確性審查

**審查日期：2026-10-14。審查對象：使用者提供的 `2026_MCM_Problem_B_Source_Code.zip` 原版。**

本報告不代表已審查 GitHub 上後續修正版，也不把提供的原型程式稱為競賽官方程式。本次未修改原工程，未重寫調度器，未執行修正後策略的性能評比。官方題目 PDF 第 1–2 頁是模型契約；原始程式、稿件、獨立研究包及既有審查是分別核對的證據，而不是彼此替代的權威。

## 結論

**這是一套在官方 trace 上能產生合法完整排程的研究原型，但它目前沒有實現稿件所宣稱的完整演算法契約。**

本次直接執行原函式的七組完整 trace：42 個「策略配置 × GPU 池」的獨立逐節點資源帳本均通過，所有作業均被啟動並排空。這不等於預約、優先序、飢餓界或論文數字全部正確。可手算且在原函式上重現的反例證明：EASY 的一般節點級預約不安全；AMBF 普通排序偏重新到達而非 Aging；AMBF 的正常分支沒有預約式回填，但 urgent 分支確實有停止插隊的保護。

另有兩項重要新核對：單 GPU 快速分支缺少通用 CPU 安全條件，但官方 A10 資料符合其特殊閾值，不能因此否定本次 A10 全量排程；EASY-WF 的稿件結果未由所附原函式重現，其差異根因尚未定位。

---

## 0. 版本、定位和證據等級

全文行號指解壓後原檔，不是本報告行號：

| 縮寫 | 檔案 |
|---|---|
| S | `run_complete_q2_q3_experiments.py` |
| D | `document_en.tex` |
| F | `generate_figures.py` |
| R | 獨立包 `B_GPU_Research/research_calculations.py` |
| P | 官方 `2026_MCM_GPU_Scheduling.pdf`，頁碼按 PDF 自身順序 |

S 的 SHA-256：
`31ab2f2aeda99c26e916693fcc8255f0ef327e8819d6fcae4e5a51d551913e27`

D 的 SHA-256：
`7662808a9c3399d440ebfabf114471ff661954ea3ba288c5e496a833b48d014f`

R 的 SHA-256：
`f8a4c55f51679e37f233f0355b3d6fcf9fc0a975214324321af371dbfc01d08b`

本次環境：Python 3.13.5、NumPy 2.3.5、pandas 2.2.3；在分析容器中執行，不是使用者的 GPU 伺服器。

證據包的定位：

- **E1** `results/audit_results.json`：32 項定向契約探針、150 組隨機資源帳本檢查、5 項前綴不變性檢查和官方資料核對。
- **E2** `results/full_trace_results.jsonl`：七組原策略全量重跑結果及逐池帳本狀態。
- **E3** `results/cross_checks.json`：獨立參考實作測試、1,944 個枚舉可行性比對、獨立 FCFS 全量重跑、節點排序控制實驗、AMBF 無窮門檻反例。
- **E4** `source_lines.txt`：原程式、稿件、圖表與參考程式的帶行號文字，以及官方 PDF 分頁文字。
- `manifest.json`：原輸入檔案指紋；`audit_q2.py`、`cross_checks.py`：本次審查程式。

執行方式不是另寫一套相似調度器代替受測程式：審查器從原 ZIP 的 AST 載入原函式，跳過硬編碼頂層檔案讀取和實驗入口，函式本體不變。觀測器轉發原 heap 操作，只記錄實際啟動配置；独立帳本用記錄回放容量、型號、worker 數、啟動時刻及最終歸零。觀測與驗證耗時不能當成原演算法的純性能 benchmark。

`FAIL` 必須連同契約閱讀。E1 中的 18 個未滿足斷言，包括不同策略上的同一缺陷、被反例否定的論文主張，以及「連續時間提升」「slowdown 下限為 1」等條件式契約，**不是 18 個獨立生產程式錯誤**。

## 1. 按嚴重程度排序

| 等級 / ID | 發現 | 主要位置 | 判定與範圍 |
|---|---|---|---|
| P0-1 | EASY 用全池 GPU 數代替節點級預約，長回填可延誤隊首 | S:207–229 | 一般題目模型下已重現；WF、BF 均失敗；不等於已證明全量每一次預約失敗 |
| P0-2 | 單 GPU 快速分支對 CPU 容量有未驗證的 126/128 特化 | S:41–44,59–75 | 合法可行合成輸入上五種策略均可超配；官方 A10 恰符合特化 |
| P0-3 | 無法啟動的作業可被算成已完成，且得到負等待 | S:129–130,154–155,298,307 | 已重現；官方原 trace 所有作業完成，未觸發此路徑 |
| P1-1 | AMBF 的負 submit-time 項偏重新作業 | S:172–174；D:123–129 | 數學及實際排序均確認；稿件公式與程式一致，但名稱／意圖不一致 |
| P1-2 | AMBF 正常分支没有稿件所述 shadow reservation | S:258–296；D:129 | 已重現隊首 10→22 秒；urgent 分支有 HOL 保護，不能說完全沒有等待保護 |
| P1-3 | EASY-WF 稿件數值未重現；圖表存在手填／混合基線 | S:328–344；D:160；F:139–168 | 原函式全量重跑不一致，根因未定位；其他六組主要數值重現 |
| P1-4 | 等待上限、SAF 最優性、消除碎片、一般 Pareto 與複雜度聲明過強 | D:113,117–143,174–188 | 有直接反例或缺乏所需前提；須逐項限縮，不可借名稱繼承保證 |
| P2-1 | 限制的是失敗候選數；提升門檻不是獨立事件 | S:240–296 | 合法實作選擇，但不等於完整 work-conserving 掃描或連續提升 |
| P2-2 | FCFS 放置順序、BF 縮寫、SJF/SAF 語義未充分區分 | S:21,31,59–109,169–170；R:136 | 已用控制實驗定位重要基線差異 |
| P2-3 | 固定窗口和 slowdown 定義跨包不同；泛化與公平性解釋需限制 | S:9,298–325；R:208–221 | 多屬定義一致性，而非所有公式都錯 |

P0 表示不可在未修正或明確收窄輸入域前，將對應一般契約宣稱為正確；不表示原 trace 全部數字應丟棄。

## 2. 真正執行的五種策略

令作業有到達時間 a、時長 p、worker 數 w、每 worker GPU g、CPU c，GPU 工作量 V=wgp。全池作業先按 `(submit_time, job_name)` 排序。單 GPU 特化成立時，所有策略共用同一個 CPU 分桶 LIFO 放置，不執行一般 FF/WF/RM 排序。

| 名稱 | 作業優先序與阻塞行為 | 一般節點放置 | 是否保護預約 |
|---|---|---|---|
| FCFS-FF | 每 GPU 池按到達／名稱；隊首不可放置就停止 | 節點先依 GPU 容量、CPU 容量、名稱升序，再 First-Fit | 不做回填；HOL 本身防止後方插隊 |
| EASY-WF | 啟動 FCFS 前綴；對首個阻塞作業做 GPU 總量 shadow；最多檢查 199 個後方作業 | 每個 job 開始時按剩餘 GPU 降序排節點，再在一節點取盡可容納 workers | 有不完整的標量保護；一般 CPU/Gang 不安全 |
| EASY-BF | 和 EASY-WF 相同的隊列／shadow 邏輯 | Ratio-Matched Best-Fit | 同上 |
| SAF-BF | `(V,p,j)` 最小堆；放不下的暫存，繼續找；30 次失敗後停止 | Ratio-Matched Best-Fit | 無預約；BF 在此是放置 Best-Fit |
| AMBF | 普通 `(V^0.7−λa,p,j)`；超門檻改 urgent FIFO；普通分支跳過阻塞候選，urgent 阻塞則停止 | Ratio-Matched Best-Fit | 普通分支無預約；urgent 有不允許後方插隊的 HOL 保護 |

定位：S:180–238、240–296。

因此，`EASY-WF` 不是每放一個 worker 都重新找最空節點的逐 worker Spread；`SAF-BF` 不是「SJF + EASY Backfilling」；`AMBF` 也不能因名稱含 Backfilling 就被解讀成已有預約保障。

## 3. P0-1：EASY 的正確節點級契約

### 3.1 單個 Gang 的可行性是精確且容易計算的

對匹配型號節點 m，在時刻 u 的剩餘資源為 F_m^G(u)、F_m^C(u)。相同 workers 作業 j 在該節點最多可放：

\[
h_{jm}(u)=\begin{cases}
\min\left(\lfloor F_m^G(u)/g_j\rfloor,\lfloor F_m^C(u)/c_j\rfloor\right),&c_j>0,\\
\lfloor F_m^G(u)/g_j\rfloor,&c_j=0.
\end{cases}
\]

\[
\boxed{\mathrm{Fit}(j,F(u))\iff\sum_{m:\,type(m)=type(j)}h_{jm}(u)\ge w_j.}
\]

必要性：每個節點不能放超過自己的 worker 容量。充分性：按任意節點順序，選 0≤x_jm≤h_jm 的整數數量，直到總和 w_j 即可。這個證明依賴同一 job workers 完全相同、沒有額外拓撲／反親和性限制；本題恰有這些條件。不要把一般異質 worker 裝箱的 NP-hard 性質誤套成這個单 job 判定必須解 MILP。

S:77–84 已有一般路徑的這個正確思想。E3 的 1,944 個小枚舉比較全部一致，但這是公式驗證，**不是修正後 EASY 已經通過**。

### 3.2 正確預約時刻

在決策時刻 t，先處理完 t 上所有完成事件。只投影當前 running jobs 的既有固定配置和已知完成時間，不假設新作業未來到達。頭部作業 h 的最早完整可放置時刻：

\[
\boxed{R_h=\min\{u\in\{t\}\cup\{e_r:r\in\mathcal R(t)\}:\mathrm{Fit}(h,F^{base}(u))\}.}
\]

同時完成的作業必須一起釋放後判定；不是釋放到 GPU 總數夠就停止。已驗證單獨可行的 job，所有 running jobs 排空後必定能放；不存在有限 R 時應檢查不可行輸入或狀態錯誤，不得靜默吞掉。

### 3.3 安全回填的必要充分條件

固定同一個受保護 head 和原截止 R_h。令 B 為建立預約後已接納及本輪擬接納的回填作業，實際開始時刻為 t_b，已確定節點 worker 配置為 y_bm。基準投影不含 B，避免重複扣除。

\[
\widetilde F_m^r(R_h)=F_m^{base,r}(R_h)-\sum_{b\in B:\,t_b+p_b>R_h}y_{bm}d_b^r,\quad r\in\{G,C\}.
\]

候選現在能合法完整啟動，且：

\[
\boxed{\widetilde F(R_h)\ge0\quad\text{且}\quad\mathrm{Fit}(h,\widetilde F(R_h))}
\]

即為「在這組固定回填配置下，head 在原 R_h 仍可啟動」的必要充分條件。它保護的是既有承諾，不是後來重新計算的較晚時刻。

對只有目前 running jobs 釋放、沒有其他未來預約啟動的單 head 模型，R_h 後剩餘資源只增加。因此這一時刻可行，配合之後對 head 固定占用的容量保護，足以涵蓋整段執行。若要保護多個未來預約或另有未來固定啟動，則須檢查相应的完整時間資源輪廓。

簡單充分條件為：

\[
t_b+p_b\le R_h.
\]

這不是必要條件。跨過 R_h 的候選若使用真正多餘的 CPU/GPU 節點資源，也可安全運行。另一個易實作的充分條件是凍結一份 head 配置 z_hm，要求各節點在 R_h 的累積占用加 z_hm d_h 不超容量；這比允許 head 重新放置的完整判定更保守。

多個候選必須依序在**已扣除前面接納者**的狀態上檢查。每個候選都對最初快照單獨安全，不代表全部同時安全。正式 commit 必須使用安全檢查的同一份 placement，不能檢查 A 配置、實際放 B 配置。

### 3.4 原實作為何失敗

S:207–229 投影的是全池 GPU 總量，`extra_free_gpu` 也是總 GPU 數。它不考慮 CPU，也不考慮 GPU 是否分布在能容納同一 worker 的節點。S:230–231 確實對跨 shadow 的候選扣減 `extra_free_gpu`；問題**不是完全沒有累積 GPU 扣除**，而是扣除的抽象不足。

現有「候選在 shadow 前完成」分支在本模型和有效狀態下仍有可保留的安全性：當前 head 已阻塞，這種 GPU 總量 shadow 不晚於真正節點級 earliest start。主要反例是讓超過 shadow 的長作業只依 scalar extra 通過。

### 3.5 最小 CPU 反例：1 節點、3 作業，已執行

節點容量為 2 GPU、2 CPU。下表每個 job 均只有一個 worker，時間單位秒。

| 作業 | 到達 a | 時長 p | 每 worker GPU | 每 worker CPU |
|---|---:|---:|---:|---:|
| R，先運行 | 0 | 10 | 1 | 1 |
| H，受保護 head | 1 | 1 | 1 | 2 |
| B，後方候選 | 2 | 100 | 1 | 1 |

R 在 0–10 執行。t=2 時剩餘 (1 GPU,1 CPU)，H 缺 CPU，正確 R_H=10。原程式看到第 10 秒共 2 GPU、head 只要 1 GPU，判定 extra=1，因此讓 B 在 2–102 執行。第 10 秒僅剩 1 CPU，H 要 2 CPU，必須等到 102。

**原 EASY-WF、EASY-BF 均得到開始時刻 [0,102,2]，不是 [0,10,...]；兩者的容量帳本均 PASS。** 這正是「合法排程不等於安全預約」。證據 E1。

从初始空叢集、每 job 單獨可行的設定，需要先運行 blocker、被阻塞 head、越過 head 的候選，因此三 job 是此類反例的最小角色數；一節點已足夠。這不是靠構造一個永遠不可行 head 取巧。

### 3.6 純節點形狀／Gang 反例：2 節點、3 作業，已執行

兩節點各 4 GPU、128 CPU。

| 作業 | a | p | w | 每 worker GPU | 每 worker CPU |
|---|---:|---:|---:|---:|---:|
| R | 0 | 10 | 1 | 2 | 1 |
| H | 1 | 1 | 2 | 3 | 1 |
| B | 2 | 100 | 1 | 2 | 1 |

t=2 剩餘 GPU 為 (2,4)。GPU 總數 6 已等於 H 的總需求，但 worker slots 為 floor(2/3)+floor(4/3)=1<2，故 H 不能啟動。R 在 10 完成後兩節點全空，正確 R_H=10。

原程式投影 8 GPU，head 需求 6，extra=2，接納 B。BF 把 B 放第一節點，WF 放第二節點；第 10 秒分別剩 (2,4) 或 (4,2)，兩者都仍只有一個合法 worker slot。

**兩策略再次得到 H=102，而不是 10。** CPU 完全充足，因此只補「全池 CPU 總量」仍修不好。證據 E1。

### 3.7 不應過度擴張結論：A10 的特例

本次資料核對：A10 有 2,494 個單 GPU 節點，2 個 126 CPU、2,492 個 128 CPU；全部 workers 要 1 GPU，CPU 需求最多 128。另核對 CPU>126 的 13 個 A10 jobs 均為 CPU=128、w=1。

在這個非常特殊的資料域，低 CPU head 可用所有空閒節點；高 CPU head 只需一個 128 CPU 節點，若它被阻塞，所有這類節點均忙，當前能回填的只會是低 CPU 節點，不能擋住第一個 128 CPU 節點釋放。這能支持受限資料域的額外安全推理。

所以，通用 CPU/Gang 反例成立，**但不推出 A10 全量結果必然因該反例而錯**。本次也沒有完整記錄全 trace 每一次 head 預約與接納決策，因此未宣稱已完成所有池的逐預約全量驗收。

## 4. P0-2 / P0-3：資源特化與未完成記帳

### 4.1 單 GPU 不代表 CPU 同質

S:41 只確認所有節點與 workers 的 GPU 數都是 1，就進入 S:59–75 的 CPU 閾值快速路徑：c≤126 允許取任何 low/std 節點；c>126 只取 CPU≥128 節點。這不是一般 CPU eligibility 判定。

已執行的合法合成反例：兩節點為 (1 GPU,4 CPU)、(1 GPU,8 CPU)。R 在 a=0 到達，要 8 CPU、執行 10 秒；H 在 a=1 到達，也要 8 CPU、執行 1 秒。兩個 job 單獨都可放在 8 CPU 節點。

快速路徑先把 R 放 8 CPU 節點，隨後把 H 放剩下的 4 CPU 節點。五種受審查策略全部得到開始 [0,1]，獨立帳本顯示 CPU=8/4，違反容量約束。正確 H 應最早 10 秒開始。證據 E1。

相反，一個 1 GPU、127 CPU 節點配一個 CPU=127 的合法 job，原程式因為找不到 std≥128 而誤拒絕。

修正契約不是硬把常數換成另一組常數，而是：每個 worker 必須對實際节点 CPU/GPU 檢查；快速分支若保留，必須先證明其分類完全等價於通用判定，否則退回通用實作。

官方 A10 原資料满足目前特化，七組全量帳本都沒有發現超配；將模型拿去做縮放、改硬體、其他單 GPU 資料或未來 Q3 時則不再可以假定。

### 4.2 未啟動作業不能用完成時間 0 代表

S:129–130 把 start/finish 都初始化為零。S:154–155 在沒有下一事件時直接 break；S:298 計算 wait=start−arrival，S:307 把 finish≤H 都當完成。

對前述誤拒絕的合法 127 CPU 案例，以及一個真不可行 job，原函式都可回傳：

```
started = 0 jobs（獨立帳本）
wait = -1 second
completed_90d = 1
makespan = 0
```

這是記帳正確性缺陷，而不是「不好看的指標」。入口應先檢查單獨可行性；未開始用明確缺值及狀態表示，缺事件但還有等待時必須回報 infeasible/deadlock/incomplete，不得產生看似成功的結果。官方 trace 未觸發它不構成保留此行為的理由。

### 4.3 修 EASY 時需避免踩到現有雙重資源狀態

一般路徑修改 `free_gpu/free_cpu`；unit 路徑主要修改兩個空閒節點 stack 和 `total_free_gpu`，不維護每節點 free 陣列。因此目前 unit 分支依賴 stack 才是實際狀態。

新增 node-level projection 時，**不能直接複製 unit 模式中已過時的 free 陣列**。應從唯一權威資源帳本／實際 running allocations 重建，或使兩條路徑的狀態契約一致。這是修正介面的必要條件，不是本次已觀測到的額外全量超配。

## 5. P1-1：AMBF Aging 的數學方向

普通最小堆鍵為：

\[
K_j=V_j^{0.7}-\lambda a_j,\quad\lambda=0.01>0.
\]

對相同 V 的 old/new，若 a_new>a_old：

\[
K_{new}-K_{old}=-\lambda(a_{new}-a_{old})<0.
\]

所以新作業優先。較新且更大的作業也可能超前，只要其工作量 penalty 增量小於 λ 乘到達時間差。它是 recency preference，不是讓等待久者更優先。

如果小鍵優先、線性 aging 是等待越久鍵越小，正確表達為：

\[
K_j(t)=V_j^\alpha-\lambda(t-a_j)=V_j^\alpha+\lambda a_j-\lambda t.
\]

所有 waiting jobs 共用 −λt，所以堆可以存：

\[
\boxed{K_j^{heap}=V_j^\alpha+\lambda a_j.}
\]

**沒有每秒重新計算 heap 本身不是錯誤。** 線性 aging 的共同時間項可以精確消去；錯誤是 submit-time 的方向。對既有固定 waiting set，線性 aging 不改變兩作業的相對順序，其保護主要體現在對新進作業及 urgent 覆蓋上。

D:123–129 的公式和 S:172 完全同號，因此這是數學／命名與設計意圖不符，不是抄寫公式漏了一個符號。

已執行例：1 GPU、128 CPU；R 在 0–100；old 在1到達、new在2到達，兩者時長10、GPU/CPU需求相同，不觸發urgent。

| 實驗 | R / old / new 開始時刻 |
|---|---|
| 原 λ=0.01 | 0 / 110 / 100 |
| 移除時間項 λ=0 | 0 / 100 / 110 |
| 透過原參數取 λ=−0.01，即測試正 submit 係數 | 0 / 100 / 110 |

這只是排序機制反例與控制，沒有宣稱正號對全 trace 性能一定更好。修正符號後等待、完成數可能有取捨，不應以性能變差作為繼續稱反向項為 Aging 的理由。

建議正式規格用無量綱 key：`(V/V0)^alpha − beta * ((t−a)/t0)`，固定 V0,t0,beta 的單位與來源。原 λ 同時與 GPU-seconds 的冪及秒數結合，直接改時間單位會改策略；時間從秒改成小時必須相應換算係數，而不是沿用 0.01。

## 6. P1-2：AMBF 沒有 shadow reservation，但有 urgent HOL 保護

### 6.1 正常分支

S:279–296：取優先候選、試放、成功則啟動；失敗則暫存，繼續找後方候選。没有投影 running completion、沒有 R_h、沒有 safe-to-backfill 判斷。

在 1 節點 (2 GPU,128 CPU) 上：

| 作業 | a | p | w | 每 worker GPU / CPU |
|---|---:|---:|---:|---|
| R | 0 | 10 | 1 | 1 / 1 |
| H | 1 | 1 | 2 | 1 / 1 |
| B | 2 | 20 | 1 | 1 / 1 |

未達 urgent 門檻時，H 的工作量較小、優先鍵較好，但放不下；B 在2開始，至22完成，H 因而22才開始。原輸出 [0,22,2]。不接納 B 時 head 可在10開始。D:129 宣稱不延誤 head 的機制在此不存在。證據 E1。

### 6.2 urgent 分支

S:264–277：最老 waiting job 達門檻後，先嘗試它；若放不下，直接 break，不嘗試較新 job。上述案例以 cap=0 運行，原輸出 [0,10,11]。所以應描述為「到齡 FIFO 提升 + 阻塞時禁止後方插隊」，而不是沒有保護。

這個路徑甚至不允許本來安全、可在 head 預約前完成的回填；它是保守 HOL 保護，不是有空間／時間預約的 EASY。

### 6.3 門檻不等於等待上限，但可以有條件證明不飢餓

1 GPU 被 R 占到100秒，新 job 在1秒到達；即使 cap=5秒，它仍需等99秒。故不能宣稱 W≤cap；E1 已重現。

另一方面，若所有 job 單獨可行、時長有限、到達局部有限、同時到達平手順序確定、調度事件持續正確處理，则一旦某個最老等待 job 進 urgent，後方不再插入，現有 running jobs 最終排空，它必能啟動。對有限個更老 job 逐個歸納，即可得到每個 job 的有條件最終啟動性。

甚至可給一個**依當前狀態而變、不是 cap 本身**的保守界：令 u 為 j 到齡後首個實際調度 epoch，O_j(u) 是當時按 FIFO 排在 j 前面的等待作業，Rmax(u) 是當前 running jobs 的最大剩餘時長，則在上述正確可行性假設下：

\[
s_j\le u+R_{max}(u)+\sum_{i\in O_j(u)}p_i.
\]

理由是 j 及全部更老 waiting jobs 已 urgent，不再啟動其後新作業；等待现有運行作業清空後，將更老 jobs 串行處理就給出保守完成上界。此為數學推導，不是現有程式已輸出的服務承諾。它還含 u−(a_j+cap) 的事件觸發延遲、運行殘餘與前方工作量，不能改寫成固定最大等待 cap。

### 6.4 cap 的兩個端點

D:174 的「cap=0 為 FCFS、cap=∞ 為純 SAF」需要限制：

- cap=0 產生 FCFS **加目前的 RM/unit 放置**；一般不是 FCFS-FF。
- cap=∞ 只關掉 urgent。若 λ≠0，仍有 `−λa`，不等於 SAF。
- cap=∞ 且 λ=0 时，V^0.7 是 V 的單調變換，相同 tie 和掃描規則下才與 SAF 一致。

E3 的相同工作量 old/new 例已重現 AMBF∞ 與 SAF 不同。A10 上不同放置分支共用 unit 快速路徑，cap=0 的局部對應可成立，不能升格為全池定理。

### 6.5 到齡不是獨立事件；30 是失敗數，不是總候選數

原事件只有 arrival/completion，沒有 `AGE_THRESHOLD`。D:129 提到 decision epoch，因此「在下一 epoch 才提升」可是一個合法且應明示的契約，不必一律當成 bug。

但配合30次失敗上限，可真的留下長時間閒置：1個4GPU節點，t=0有兩個各1GPU作業，分別於100與2完成；老H於1到達，要3GPU、p100；t=2到達30個各要4GPU、p1的作業。t=2有3GPU可用，30個較小GPU-work候選都放不下，耗盡失敗預算，實際可放置H未被看到。cap=5秒，H於6到齡，但無事件直到100，故H在100才開始。這個33作業反例已執行。

若契約要求到齡即提升，应新增門檻事件；若保留event-epoch語義，須量化提升延遲且不得聲稱連續保護。若宣稱每epoch只處理30個jobs，也不成立：成功者不增加blocked count，可以處理多於30個。

## 7. SAF、SJF、SPT、Shortest GPU-work 不能混稱

| 名稱 | 正確需聲明的排序量 | 與本程式關係 |
|---|---|---|
| SPT | p，Shortest Processing Time | 非搶占固定 duration 場景的清楚時長排序 |
| SJF | 「job size」須定義；本研究參考包採 p | 不宜依名稱推定是GPU-work |
| SJF-HOL | p 優先；最短者放不下就停止 | R 的已實作基線 |
| SJF-fit | p 優先；跳過不可行者 | 不等於 SJF-HOL，也不自帶預約 |
| SAF / Smallest Area First | V=wgp，即GPU數×持續時間的資源時間面積 | S:28–29,169–170 正是這個 |
| Shortest GPU-work | V=wgp | 本題固定GPU請求下和上述 SAF 同義 |
| Smallest GPU-demand | wg，不含時長 | 又是另一種排序，不是 SAF |

S:169 的 heap 還以 p 打破 V 平手，再按排好序的 j 打破平手。`SAF-BF` 的 BF 表示 RatioBestFit 放置；其作業選擇是有限失敗掃描的可行候選填充，不提供 EASY 承諾。

### 7.1 直接反駁「SAF 最小化平均等待／平均隊長」

1個節點4GPU、1CPU；兩作業都在0到達，各需1CPU，因CPU瓶頸不能同時運行：

| 作業 | GPU | p | GPU-work V |
|---|---:|---:|---:|
| A | 4 | 10 | 40 |
| B | 1 | 20 | 20 |

SAF先B：等待B=0、A=20，平均10；SPT先A：等待A=0、B=10，平均5。SAF原函式實際開始[A,B]=[20,0]。反例在題目允許的資源約束內，不依賴搶占。

對有限且排空的樣本路徑，逐作業等待區間面積直接給出：

\[
\int_0^{T_{drain}}Q(t)\,dt=\sum_j W_j.
\]

所以本反例同時否定 D:117 的一般平均隊長最優性。SPT 的相鄰交換證明也有特定假設：單服務器、同時可用、無權重總完成時間；不能把它自動移植成異構多資源 gang + 到達時間模型的最優性。

### 7.2 Queueing 公式能作動機，不是本題保證

D:117 引用 Little／M/G/1 Pollaczek–Khintchine，但本題沒有證明 Poisson 到達、單服務器、平穩負載或對應服務時間分布；有限90天提交工作量比值也不是穩態利用率證明。GPU-hours 的 Gini 不能直接替代時長分布的二階矩或唯一決定 C_v^2。

PK 在適當的 M/G/1 FIFO 假設下涉及 E[S²] 和 ρ<1，不能用「多節點 GPU-work Gini 很大」直接推出本系統的等待數值或SAF最優性。保留為定性動機可以，正文需清楚分開假設、恆等式、觀察與定理。

## 8. 放置、事件與輸入域的其他發現

### 8.1 RatioBestFit 是 heuristic，不是消除碎片的不變量

S:91–97、D:131–140 的比例採 hardware CPU/GPU，不是 residual CPU/GPU。它優先匹配資源形狀並偏好較少空GPU的節點，但可行候選不足時仍會使用不理想節點。

已執行CPU stranded例：節點(1GPU,192CPU)、(8GPU,192CPU)。第一個要1GPU/192CPU的job在0運行100秒，占掉單GPU節點；第二個相同需求job在1到達、執行10秒，合法放在8GPU節點，直接留下7GPU而CPU=0。原RatioBestFit確實如此；容量合法但D:142所稱消除stranding不是不變量。E1。

已執行時間碎片例：兩節點各4GPU。依序到達占用1GPU至100、3GPU至11、另一節點1GPU至102的作業；在12秒，每節點餘3GPU。此時需要單節點4GPU的job不能啟動，儘管全池餘6GPU。原BF讓它100才開始。D:143不能從當下tight packing推出未來永無碎片。E1。

這些反例不否定RM在特定trace的實測改善，只否定「eliminating」「invariants」的一般保證。

### 8.2 應保留的正確行為

一般可行性失敗前已檢查總worker slots；在有效輸入及正常控制流程中，S:77–109 不會先放部分workers再因最後幾個放不下而失敗。本次没有發現一般blocked attempt留下部分配置的證據。`can_and_place` 成功就修改狀態，所以新增reservation預檢仍需拆出不修改狀態的planner。

S:158–175 先完成釋放、再入隊、再調度，和半開區間[s,e)相容；小數CPU與同時完成／到達例五種策略都通過。c=0在一般分支有处理；D:131的公式應補零CPU分支。Q2按互不相交GPU池獨立模擬在題目限制下成立。

官方P:1明確duration提交時已知。使用已到達job的duration、或以已啟動job已知duration計算completion，**不是未來資訊洩漏**。S的正常優先隊列只插入已到達jobs，5個前綴不變性探針通過；這是有限測試，不是對任意未來擾動的完整形式證明。

S:150–151在GPU全忙時跳過中間arrival到下一完成。有效輸入全都需要正GPU，此期間不可能有job啟動，因此对目前啟動決策是可成立的加速；若新增連續queue長度／到齡事件統計，仍需正確核算被跳過的到達，不能直接沿用舊事件日誌當完整過程。

### 8.3 邊界和可重現性要求

S:25,27 的astype(int)沒有先檢查整數性；不可讓非整數GPU/worker被靜默截斷。時長需正且有限，CPU非負，型號匹配，名稱唯一；空輸入、不存在資源池、非法策略名也需明確語義。這是接口完善要求，不是本次已發現官方資料違反這些規則。

S:126的CPU release上限clamp可能遮蔽累積誤差／重複釋放，不能代替帳本斷言。官方CPU可以精確百倍整數化；如採整數資源，先驗證精度，不對不符合精度的輸入偷偷round。

S:11的cap參數和policy字串分離：傳`AMBF-1350`不會自動令cap=1350，默認仍1200；目前正式driver有正確傳入。應序列化真實參數或驗證label與參數一致。

## 9. 全量重跑、稿件與基線可比性

### 9.1 本次七組完整原函式重跑

固定窗口H=7,776,000秒。等待對全部224,112個jobs統計；最後一次到達後排空。

| 策略 | 平均等待 h | 最大等待 h | H內完成數 | 42池次帳本中該配置的6池 |
|---|---:|---:|---:|---|
| FCFS-FF | 447.372958 | 1423.253889 | 164868 | PASS |
| EASY-BF | 446.148585 | 1422.130833 | 165114 | PASS |
| SAF-BF | 16.545790 | 3017.288056 | 217529 | PASS |
| AMBF-1080 | 105.328685 | 1414.024167 | 203110 | PASS |
| AMBF-1350 | 30.963808 | 1520.239722 | 217057 | PASS |
| AMBF-1500 | 22.253304 | 1573.375000 | 217337 | PASS |
| EASY-WF | 465.669855 | 1765.447778 | 161899 | PASS |

來源E2。這代表7×224,112次作業執行的全量帳本檢查；不代表每個策略的預約契約都通過。原始trace的全量SJF-HOL在本次沒有重跑，僅重跑獨立參考FCFS及其小案例雙策略測試。

### 9.2 EASY-WF：未重現的主表數據

| 指標 | D:160稿件 | 本次原函式 |
|---|---:|---:|
| 全體平均等待 h | 452.28 | 465.669855 |
| A100平均等待 h | 16.92 | 54.051716 |
| H內完成數 | 164607 | 161899 |
| 最大等待 h | 1709.1 | 1765.447778 |

其他六配置的主要數值與稿件表格重現。S:330的入口僅跑六配置，没有EASY-WF；本次明確額外調用了支援WF的原函式。

當前結論是「所附版本／本環境未重現該行」，**差異根因未定位**。可能是版本、設定或其他執行差異，沒有證據時不指定原因、不指控造假，也不能直接把舊表的16.92覆蓋成54.05就宣稱追溯問題已解決。應找回產生該行的原run及版本；找不到則撤下該行及其派生論點。

### 9.3 兩個FCFS不是同一個FirstFit契約

S:31按照 `(GPU容量, CPU容量, node_name)` 排序；R:136按照 `node_name`。提供的研究文字也明確後者採名稱FirstFit。

本次在GPU-series-1完成控制：

| 實作／節點序 | 平均等待 h |
|---|---:|
| 獨立參考原FCFS | 0.0291882713 |
| 原型FCFS-FF | 9.3825258967 |
| 獨立參考保持相同物理節點、改成原型的FirstFit節點序 | 9.3825258967 |

最後一組與原型**逐作業開始時間完全一致**。證據E3。

因此這個差異已定位到placement順序，不應解讀成浮點雜訊，也不必先假定兩個模擬器之一算錯。FF需要完整節點序契約；跨兩包取FCFS和SAF結果做比較，必須先統一placement、事件、時間窗口與排序。

### 9.4 圖表不是獨立實驗證據

F:139–142手填Q2結果；F:160–168所谓placement ablation把WF A100數字和FCFS GPU-series-1數字混用，另有EASY-FF數值但所附Q2函数分支／driver没有對應入口，RM列以0.001替代零；F:182–185手填額外cap曲線和Pure SAF(Inf)端點。

手填不等於數字必假，但無法確保版本一致，也不能把插值、視覺抬高零點、另一策略的數字当作同一次消融。正式圖表必須讀run_id對應結果，顯示原始單位和參數，缺run直接失敗。

## 10. 計算指標：哪些正確，哪些定義不同

### 10.1 固定窗口與完成狀態

對已正確排完的jobs，S:298–305的資源時間裁剪正確：

\[
U_G(H)=\frac{\sum_jw_jg_j[\min(e_j,H)-\max(s_j,0)]_+}{H\sum_mG_m}.
\]

S:341合併全部waiting times後計算全體分位數也是正確的，不是把各池分位數平均。原trace確實排空，不存在本次全量慢job被截掉的證據。

但source H=7,776,000；reference H=maxsubmit=7,775,878，相差122秒。相同source FCFS排程，在兩窗口完成数分别164868、164807，相差61。參考包原FCFS在自身H完成165035，還包含不同放置策略的影響。两个H都可作研究者明示的統計窗，但不能混用後稱差值來自演算法。

完成必須以真實狀態判定，否則P0-3使公式失真。應記錄submitted/started/completed/pending數並要求總和、唯一性、end=start+p和資源歸零一致。

### 10.2 Bounded slowdown 是口徑差異，不宜一概判成公式錯誤

S:308和D:113使用：

\[
B^{(A)}_j=\frac{W_j+p_j}{\max(p_j,60)}.
\]

R:213使用：

\[
B^{(B)}_j=\max\left(1,\frac{W_j+p_j}{\max(p_j,60)}\right).
\]

1秒且零等待的job，两者分别1/60、1。文獻存在不同口徑，因此不能只因沒有外層max1就宣稱source與稿件算錯。真正問題是跨包值不可直接比較，以及文字是否承諾每job至少1。E1相應FAIL針對的是「clamp-at-one」條件式契約，非對所有BSD定義的否定。

選定τ、是否外層clamp、分位數插值規則和單位後，兩包共同評價器需一致。長作業即使等很久，slowdown也可能小，不能拿它取代絕對最大等待。

### 10.3 不能從指標多就推出證據獨立

Q2的p固定，故mean JCT=mean wait+mean p，兩者排序相同。排空後總GPU資源時間Σwgp也由輸入固定；以各策略自己的makespan作分母時，全排空利用率和makespan有機械關係，不是互相獨立的收益。

分配率不是硬體計算核心的利用率；job間等待公平不是tenant級DRF公平；樣本max wait不是普遍starvation bound。完整trace已被探索，不能把末段事後命名為盲測；有排隊相依的224,112jobs不能直接當IID樣本。這些限制不否定確定性重播比較本身。

### 10.4 Pareto 必須明確列目標向量

D:181的「every metric」過強。本次A10原數據：FCFS CPU分配率19.284736%，AMBF-1080為18.757829%，下降；若把CPU分配率列為越大越好的座標，則不是全指標支配。某些等待與完成指標改善、另一些資源指標下降，可以是合理取捨。CPU分配率也未必應不加條件追求最大；應先說清目标集合，不要事後挑有利維度。

## 11. 稿件／文獻保證對照

| 主張 | 判定 | 可保留的精確說法 |
|---|---|---|
| EASY不延誤受保護head | 一般節點CPU/Gang下被反例否定 | 修node-level admission後、在明定模型和承諾範圍內成立 |
| AMBF有EASY shadow backfill | 正常分支未實作 | 目前是優先可行填充＋到齡FIFO/HOL；或另補真正預約 |
| cap是最大等待界 | 直接反例否定 | 到齡提升門檻；可證有條件最終啟動，不能等同W≤cap |
| max observed wait是Starvation Bound | 樣本極值不是一般界 | 稱本trace的最大等待 |
| SAF最小化平均隊長 | CPU瓶頸兩job反例否定 | GPU-work啟發式，在本trace觀察到特定收益與代價 |
| RM消除CPU stranded／未來碎片 | 兩個實際反例否定 | 降低某些配置的碎片風險；效果由同政策placement消融驗證 |
| cap∞等於SAF | λ非零時反例否定 | 需λ=0及一致tie/掃描/placement |
| PK/Little證明本集群排序最優性 | 未滿足PK模型假設；Little不選策略 | 提供動機／帳本面積關係，不是多資源排序定理 |
| DRF公平、策略防操縱、無嫉妒等 | 沒有實作DRF使用者分配問題 | 不得從CPU/GPU ratio或job等待指標繼承 |
| AMBF為optimal single-pool scheduling | 無精確最優解／界／證書 | 已評估候選中的一個啟發式；報告實測trade-off |
| 所有指標Pareto優越 | 目標向量未限定，存在反向座標 | 僅對明示坐標及本trace成立的支配／取捨 |
| 每事件近O(logQ+M) | 原控制流程不支持一般上界 | 分開每次placement、每次失敗掃描、每epoch及整場複雜度 |

經典EASY主要保護當下隊首，Conservative Backfilling保護更多等待作業。即使修好EASY，也不能自動保證每個job都不比另一條完整FCFS反事實排程晚，或繼承所有arrival-time guarantees。不同受保護集合是不同契約。

### 11.1 複雜度需按實際呼叫數記帳

S:88–97的候選節點排序不能一概忽略；一般比較排序通常含M log M。每epoch可能啟動很多job，30只限制失敗數；EASY還排序running heap（S:213）、對deque逐個remove（S:237–238），一次remove可達O(Q)。Lazy heap清理可能在一次epoch刪多個過時項；只看最頂O(1)不等於含清理的worst-case O(1)。

若A_t為本epoch实际placement嘗試數，R_t為running數，K為回填檢查預算，則至少要逐項計入類似：

\[
O\bigl(A_t(M\log M+\log N)+R_t\log R_t+KQ\bigr)
\]

的成本來源，並分清哪些分支真正使用哪些項。這是保守成本組成說明，不主張是所有NumPy排序／所有資料的緊確界。unit快速路徑另有較低成本，但仍有worker數與heap成本。D:45的O(K+N)、D:119的per-event式及D:147的實測耗時，應分別核對而非互相當作證明。

## 12. 正確演算法契約與回歸驗收

### 12.1 必須先凍結的契約

**輸入／世界。** 型號、每worker需求、worker同步、不可搶占、已知duration、時間0空叢集；CPU precision；無不可行job被靜默刪除。相同timestamp釋放全部完成、入隊全部到達、再決策；占用半開區間。

**策略。** job key及比較方向、平手規則、節點順序、掃描預算到底限制attempt/failure/start中的哪一個；urgent是否到齡立即觸發；BF究竟是Best-Fit還是protected backfill；policy label與真正參數一致。

**預約。** 指明protected job(s)、原deadline、當時基準投影；safe admission扣除已接納candidate的實際節點配置；不准把deadline往後移掩蓋違約；開始被保護job後轉為running容量约束。

**原子性。** preview不改狀態；確認全部workers及預約合法後，commit同一plan；失敗前後所有資源／queue membership完全一致；release一次且只一次。

**評價。** 共享evaluation window、所有到達jobs與排空規則、狀態計數、full precision、slowdown口徑、每job及每pool輸出；調度壁鐘與觀測器成本分離。

### 12.2 已執行與待驗收案例

| 測試 | 原版本次狀態 | 正式修正／保留標準 |
|---|---|---|
| 1node CPU預約，3jobs | WF/BF FAIL，head102 | head不晚於原R=10 |
| 2node形狀＋2worker gang預約 | WF/BF FAIL，head102 | head不晚於10，不能只比總量 |
| candidate恰在R完成 | WF/BF PASS | `[s,e)`，e=R可釋放給head |
| 安全跨R候選，4GPU/8CPU單節點 | WF/BF PASS | 完整空間EASY應允許；temporal-only版本可保守拒絕但需改名／聲明 |
| 多個候選累積扣除、固定R不後移 | 原版全量逐admission NOT_RUN | 每次admission和跨epoch都檢查同一承諾 |
| 相同V的old/new | 普通AMBF FAIL | 若稱Aging，older key不差；λ0、正號控制均已驗證 |
| AMBF正常分支head10→22 | reservation契約FAIL | 選擇補reservation或更正文稿，不能只改名稱留原保證 |
| AMBF urgent阻塞後不插隊 | PASS | 保留既有保護，或只允許經證明安全的backfill |
| cap5但wait99 | 固定等待界FAIL | 只驗證提升契約，不要求物理上不可能的W≤cap |
| cap∞與SAF | 原λ非零不相等 | 只有所需參數／placement一致才斷言等價 |
| 1GPU CPU4/8可行jobs | 五策略容量FAIL | 逐節點CPU不超額，H最早10 |
| 1GPU CPU127合法job | 誤拒絕且假完成FAIL | 能啟動；不能以0時間完成占位 |
| 真不可行job | 假完成FAIL | 明確拒絕或incomplete，無負等待／假完成 |
| CPU小數、同時完成到達 | 五策略PASS | 保留精度和同timestamp語義 |
| c=0、gang全分配 | PASS | 數學及程式皆有零CPU分支 |
| RM仍可CPUstranded／時間碎片 | 論文不變量FAIL | 不驗收「永不碎片」；驗收容量和實测代理指標 |
| 30failures＋age跨越 | 連續提升契約FAIL | 選擇event-epoch或門檻事件，按選定契約驗收 |
| 30隨機fixture×5policy | 150組ledger PASS | 只證資源／時序，不得冒充reservation測試 |
| 單job slot公式枚舉 | 1944組PASS | 可作獨立feasibility oracle |
| prefix不變性 | 5策略探針PASS | 擴展到同時到達／不同未來前綴，不偷用未到達job |
| 七配置完整trace | 42池次ledger PASS | 修正後重新跑，保留所有到達job、無超配、無漏完成 |
| EASY-WF稿件數值 | NOT_REPRODUCED | 找回產生數字的版本／設定，或撤下不支持的行 |
| 修正後工程測試／全量性能 | NOT_RUN | 本次沒有修改production，不可標成已通過 |

補充應新增的可手算安全性測試：兩個長候選各自對初始投影安全，但一起不安全；固定head placement不安全而換合法節點可安全；CPU充裕但GPU分散、GPU充裕但CPU集中、同時多完成需合併釋放；非法／空輸入；重複release；preview失敗不改queue和資源；unit mode的投影不能從過時free陣列建立。上述未提供當次執行記錄者均為待新增案例。

## 13. 可直接交給 Codex 的修正與驗收要求

### 任務邊界

只處理Q2正确性及證據鏈，不做Q3重構，不更換研究目標，不擅自推送main。先定位實際工作區、現有改動與source SHA；本報告針對指定ZIP，後續版本逐項確認是否仍存在，不機械套補丁。

### C1 — 固定基準與可觀測性

保存原策略的可定位版本、參數、資料指紋及E2比較值。在现有測試架構補逐作業start/end/placement和機讀完成狀態；共享原子資源模型與評價器。原全量42池次帳本已PASS應成為受保護行為，不能修reservation卻造成漏作業、超配或搶占。

### C2 — 修正一般資源與完成記帳

先修S:59–75：保留快速路徑的前提是其eligibility和通用CPU/GPU判定等價，否則fallback。验证空叢集可行性；未開始時間不得為0占位；無事件卻有等待作業需明確報錯／incomplete。用CPU4/8、CPU127、真不可行job先證明修前FAIL、修後PASS。不得靠過濾掉反例jobs過關。

### C3 — 實現正確 EASY admission

從實際node allocations投影CPU/GPU completion，使用slots公式求R_h；同timestamp全部釋放；採純planner檢查擬放置的實際plan，累積前面接納者，保存原deadline且不後移。可選較保守的固定head placement或temporal-only安全版本，但後者需如實標示，不得自稱已實現全部空間回填能力。

驗收：本報告兩個10→102反例回到head≤10；保留e=R安全邊界；新增累積candidate、跨epoch、換placement、zeroCPU、unit authoritative state、同時多完成测试。全trace另做逐admission reservation audit，**零次延誤原承諾**；不得只重跑容量帳本替代它。

### C4 — 先定 AMBF 契約，再改碼

普通排序若要Aging，採正確小鍵線性形式 `phi(V)+lambda*a`（或可證等價形式），同步稿件、單位、平手規則。urgent現有不插隊保護須保留或改為同等安全reservation，不要修正常分支時丟掉它。

對AMBF二選一：A.補真正node-level protected backfill；B.保留priority-feasible-fill＋urgent-HOL，撤下shadow承諾並命名清楚。cap稱promotion threshold；選定epoch提升或age事件，按選定語義驗收。cap∞、cap0端點要求附參數和placement條件。符號修正是語義正確性，不以平均等待是否下降決定是否算修好。

### C5 — 凍結比較與指標

FCFS、SPT/SJF-HOL、ShortestGPUWork-fit、EASY明確分離；排序／backfill／placement分開做控制。统一H、完整cohort、precision、slowdown及分位數定義；圖表直接讀結果。凡名稱相同但node順序不同的FF，不可當同一baseline。

EASY-WF必須查明稿件與現有來源不一致的run provenance；未查明標NOT_REPRODUCED，不用手填舊數字續做消融。若整體目的改為用現有版本重建正式實驗，清楚建立新run_id並撤下無來源舊圖，而非假稱舊圖已追溯。

### C6 — 收斂稿件保證与複雜度

逐條處理D:113、117–143、174–188。本報告有反例的普遍命題刪除或收窄；僅數據觀察改成empirical；缺原理前提者標假設。将單次placement、每epoch、總run和觀測器耗時分開；不得用「peek O(1)」概括lazy cleanup與整個決策。

### 最終驗收門檻

1. 原始反例在舊版本能重現，修正版滿足選定契約；沒有靠放寬断言或刪jobs通過。
2. 對全部224,112jobs，逐作業／逐節點容量、同步、型號、時長、排空與會計均通過。
3. 對宣稱有reservation的策略，獨立驗證每次接納與跨epoch原承諾不延誤。
4. 對Aging、urgent、掃描預算和端點，行為與公式／名稱完全一致。
5. 所有主表／圖表可從機讀run重建；EASY-WF差異有可追溯處理；不把未跑修正版寫成PASS。
6. 性能可改善、持平或退化，均如實呈現；**沒有「修正必須讓平均等待更好」這個驗收條件。**

## 附錄 A：重現命令與執行範圍

將證據包解壓，把三個原ZIP放到已知路徑；不用把原資料拷進新工程。

```bash
python audit_q2.py \
  --source-zip /path/to/2026_MCM_Problem_B_Source_Code.zip \
  --data-zip /path/to/2026_MCM_Senior_GPU_Scheduling.zip \
  --out /path/to/new_audit_results \
  --full

python cross_checks.py \
  --source-zip /path/to/2026_MCM_Problem_B_Source_Code.zip \
  --data-zip /path/to/2026_MCM_Senior_GPU_Scheduling.zip \
  --research-zip /path/to/B題_GPU調度_研究報告與計算包.zip \
  --out /path/to/new_audit_results
```

不加`--full`僅跑定向、隨機、前綴與資料核對；`--full`包含EASY-WF，耗時明顯高於另外六配置。腳本的FAIL結果是審查輸出，並非自動退出碼形式的生產驗收套件；Codex應把已確定要保護的契約移入現有tests，而不是直接把所有18個FAIL強制改成PASS。

本次沒有執行：修正版調度器、修正後全量性能、全量逐reservation admission帳本、使用者伺服器實機測試、新資料盲測。已提供的前期全量aging消融不是本次重跑結果；本報告僅採本次明確列出的符號小例控制。

## 附錄 B：理論來源與使用邊界

[1] Mu'alem, A. W. & Feitelson, D. G. (2001). *Utilization, predictability, workloads, and user runtime estimates in scheduling the IBM SP2 with backfilling*. IEEE TPDS 12(6), 529–543. DOI: 10.1109/71.932708。原作者機構頁確認EASY保護隊首、Conservative保護所有等待作業的區別；不能由此直接繼承本程式未實現的多資源保證。

[2] Slurm官方 *Scheduling Configuration Guide*，Backfill Scheduling節，核查2026-10-14。支持「何時／何處」以及不延誤較高優先作業的基本概念；Slurm自身具其他資源／搶占／分區語義，本報告沒有把它當成與本題完全相同的演算法。

[3] MIT *Urban Operations Research*，§4.7 M/G/1。用於核查Poisson、單服務器、FIFO與穩態條件；不是本trace已符合这些假設的證據。

[4] Ghodsi et al. (2011). *Dominant Resource Fairness: Fair Allocation of Multiple Resource Types*. UC Berkeley Technical Report UCB/EECS-2011-18／NSDI。DRF的使用者份額、策略性與公平性保證不會因本程式使用CPU/GPU比率就自動成立。

[5] 官方P:1–2；提供的獨立研究報告§5.2、§5.4、§10.1、§10.5；本次E1–E4。原題規則優先於早期研究中「duration未知」的推測。slowdown在兩包的差異直接由S:308、D:113、R:213建立，不需假定只有一種命名慣例。

**最終審查判定：保留已通過的模擬與資源會計基礎，拒絕未實作／被反例否定的普遍保證；修正以契約與可重現性為標準，不以漂亮結果為標準。**
