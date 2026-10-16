# 2026 MCM Senior Problem B Q2：研究設計與 Codex 演算法規格

**版本：2026-10-14；狀態：研究設計，尚未對新方法完成 trace 實驗。**

本文件不指定最終演算法名稱，不授權修改或推送 GitHub。後續實作須先閱讀實際倉庫規範、狀態與已有測試。所有性能改善均為待驗證假說；下列安全性結論是在明示模型假設下的數學推導，不是實測性能結論。

## 0. 推薦結論

主方案採用：**一般佇列按 SPT 或 Shortest GPU-work 排序；共同等待門檻觸發 Urgent FIFO；每個 GPU 池只維持一個不可延後的受保護開始時刻；使用節點級雙快照驗證，允許未啟動受保護作業的放置證書更新；候選的第二次放置嘗試使用固定證書的安全容量。**

首個主實驗以 SPT 為一般排序，Shortest GPU-work 作必做對照；不加入連續 aging 加權項。放置先比較明確定義的 First-Fit 與 GPU-first Best-Fit，資源形狀分數不默認啟用。

低風險備用：**保持相同 SPT／Urgent FIFO 邏輯，但有受保護作業時，只接納能在其預約時刻前完成的回填；使用完整節點可行性與 First-Fit。**它較保守，但保留可證明的預約安全與防飢餓性質。

另研究一條真正不同的路線：**所有等待作業都有持久化時間區間預約的 Conservative Backfilling**。其逐作業承諾更早、更強，但多區間日曆成本及預約損失較大，作小型或代表性窗口對照，不列六天競賽主實作。

## 1. 已讀來源、基線與證據邊界

### 1.1 原始來源

- [S1] `2026_MCM_Senior_GPU_Scheduling.zip` 內的 `2026_MCM_GPU_Scheduling.pdf`，已讀第 1–3 頁並檢視第 1–2 頁頁面。第 1 頁：同作業 workers 相同、per-worker CPU/GPU、提交時已知 duration、不可搶占；第 2 頁：逐節點容量、同步開始、時間零全部節點空閒及評估取捨。
- [S2] 同 ZIP 的兩份原始 CSV，本次重新讀取並核对規模與節點類別。
- [S3] `2026_MCM_Problem_B_Source_Code.zip` 內的 `run_complete_q2_q3_experiments.py`，特別是第 21–115、140–175、194–296 行；及 `document_en.tex` 的 Q2 方法與結果段落。
- [S4] `B題_GPU調度_研究報告與計算包.zip` 內的 `research_calculations.py`、`calculations/baseline_metrics.json`、`calculations/data_audit.json`、完整中文研究報告。
- [S5] `deep-research-report-topicB.md`、`B題_GPU調度_研究計劃.md`、既有程式審查文字 `生成深度研究提示詞.txt`。深度研究早期版本中「必須預測 duration／已知時長只能作 oracle」的前提不適用於正式題面。

原始檔指紋：

```text
node_info_df.csv SHA256
1aba161961a5a4a1a61aa581383c5e5abe3400b59f8597ba8c4eef7597bc9d18
job_info_clean.csv SHA256
735bc06c3986b1d0c5932236f8685b7204463829118fc6a1d37030e253ed38e1
run_complete_q2_q3_experiments.py SHA256
31ab2f2aeda99c26e916693fcc8255f0ef327e8819d6fcae4e5a51d551913e27
research_calculations.py SHA256
f8a4c55f51679e37f233f0355b3d6fcf9fc0a975214324321af371dbfc01d08b
baseline_metrics.json SHA256
8aa234418c40b94a445a0b2c4d85ddec69ef11352482c867534fca52c0547eca
```

### 1.2 既有結果，不是本次新方法實驗

| 來源／策略 | 全體平均等待（小時） | 最大等待（小時） | 備註 |
|---|---:|---:|---|
| 獨立計算包 FCFS + node-name First-Fit | 446.970506 | 1423.253889 | JSON 已有結果 |
| 獨立計算包 SJF-HOL + 同一 First-Fit | 16.361890 | 3017.288056 | 最短者不可行即停，不是 shortest-feasible |
| 既有程式審查中的原程式 FCFS-FF | 447.37 | 1423.3 | 與獨立包不是完全相同的放置規則 |
| 既有程式審查中的原程式 SAF-BF | 16.55 | 3017.3 | 按 GPU-work，允許有限候選跳過 |
| 既有程式審查中的 AMBF-1350 | 30.96 | 1520.2 | 不代表已實現安全預約或 1350h 硬上限 |

兩套 FCFS 的節點順序不同：獨立包按 `node_name`，原 Q2 程式一般分支按 `(gpu_capacity_num,cpu_num,node_name)`；A10 另有共用 CPU 類別堆疊。窗口也不同：獨立包用最後提交時刻 7,775,878 秒，原 Q2 用 90 天 7,776,000 秒。不能把不同實作、窗口下的結果拼成一個公平比較。

### 1.3 源碼行為需如實保留的區分

1. 原 SAF 的 `volumes = worker_num * gpu_request * duration` 是 **Shortest GPU-work**，不是單純 SPT；名稱中的 BF 指放置，該分支沒有時間預約。
2. 原 AMBF 的一般最小堆鍵為 `volume**0.7 - aging_w*submit_time`；同體量下，新到達者鍵更小。這不是正向等待 aging。
3. 原 AMBF 一般分支會跳過不可行候選；urgent 分支遇到不可行最老作業會 `break`。後者確有停止新啟動、等待資源排空的保護作用，不應把整個 AMBF 說成完全沒有長作業保護；但它沒有所宣稱的節點級安全回填預約。
4. 原 EASY 僅以全池 GPU 累計釋放和 `extra_free_gpu` 判定跨越 shadow 的候選，不能保證節點 CPU/GPU 與 gang 的安全。
5. 原 A10 fast path 修改空閒節點堆疊，沒有同步修改一般分支的 `free_gpu/free_cpu` 陣列。新增 reservation 若直接讀這些陣列會讀到錯誤狀態，必須先統一資源狀態介面。
6. 原 RatioBestFit 用原始節點 CPU/GPU 比，不是當前剩餘資源比。原始資料中多個 8-GPU 池只有一種節點配置，ratio 項對同一候選是常數，實際排序退化為剩餘 GPU 數。A10 共用特化分支則繞過一般 placement_mode。消融必須確認分支真的改變了放置。

## 2. 正式模型與資訊契約

作業 j 的參數為 `(a_j,p_j,w_j,q_j,c_j,g_j)`：提交時刻、執行時長、worker 數、每 worker GPU、每 worker CPU、GPU 型號。節點 m 為 `(G_m,C_m,g_m)`。

決策為開始時刻 `s_j` 及整數 `x_jm >= 0`，表示節點 m 上的 worker 數；完成時刻 `b_j=s_j+p_j`。

\[
s_j\ge a_j,\quad \sum_m x_{jm}=w_j,\quad g_m\ne g_j\Rightarrow x_{jm}=0.
\]

\[
\sum_{j:s_j\le u<b_j}q_jx_{jm}\le G_m,\qquad
\sum_{j:s_j\le u<b_j}c_jx_{jm}\le C_m,\quad\forall m,u.
\]

每個作業共用一個開始時刻、配置在半開區間 `[s_j,b_j)` 固定，分別表達 gang 同步啟動與非搶占、不遷移。模型不包含額外 topology、顯存、相容替代或彈性 worker。

採線上決策：在 t 只允許使用 `a_j<=t` 的作業及其已知 duration、已啟動作業的配置與完成時刻。預約使用已啟動作業的未來完成時刻是合法的，不得預讀尚未到達的作業。

Q2 各 GPU 池的節點集合互不重疊，可獨立調度。每池最多一個 pending reservation，不是全叢集只保護一個作業。

### 2.1 指標與研究目標

\[
W_j=s_j-a_j,\quad JCT_j=W_j+p_j.
\]

固定全部作業與 duration 時，平均 JCT 與平均等待只差常數。主要研究目標為：在安全性零違規及事先指定的長作業／尾部退化容許範圍內，降低平均等待；若未指定可接受退化，展示 Pareto 前緣而非捏造單一最優分數。

同時報告 P95/P99/max wait、長作業分層等待、固定 90 天完成數、GPU/CPU 配置率、最後完成時刻、實際調度成本。有限 trace 上的最大等待是樣本統計，不自動等於理論 starvation bound。

### 2.2 單作業即時可行性：精確而非啟發式

定義節點剩餘向量 `f_m=(f_m^C,f_m^G)` 與 worker 槽函數：

\[
\kappa_j(f_m)=
\begin{cases}
\min\{\lfloor f_m^C/c_j\rfloor,\lfloor f_m^G/q_j\rfloor\},&c_j>0,\\
\lfloor f_m^G/q_j\rfloor,&c_j=0.
\end{cases}
\]

不相容節點的槽數為零。則

\[
\boxed{j\text{ 可完整放置}\iff H_j(f):=\sum_m\kappa_j(f_m)\ge w_j.}
\]

必要性：每個節點不能超過槽數。充分性：依任何節點順序取 `x_jm=min(remaining,kappa_j(f_m))`，總和足夠即能完成全部 workers。單作業判定 O(M_g)，无需 MILP；多作業共同選擇與時序最佳化仍不因此變容易。

「搜尋有限節點沒找到」不得回報為精確不可行。不可行的 protected head 必須以完整池判定；資源不足也不得只看 GPU 總數。

## 3. 排序語義：SPT、GPU-work 與 Aging

SPT／本題已知時長 SJF 使用鍵 `(p_j,a_j,job_id)`。Shortest GPU-work 使用 `(v_j,p_j,a_j,job_id)`，其中 `v_j=w_jq_jp_j`。SAF 必須寫出 area 的定義；若指 GPU×duration，便是後者。兩種排序另須說明採 HOL、feasible-first 或 protected backfilling。

兩個全在時間零到達的反例可說明沒有一個指標通吃：

- 8-GPU 節點上，A 需 8 GPU、p=2，B 需 1 GPU、p=5。SPT 的總等待為 2；GPU-work 先 B，總等待為 5。
- 2-GPU 節點上，A 需 2 GPU、p=2，B、C 各需 1 GPU、p=3。SPT 先 A，總等待為 4；B、C 同時先跑，再 A，總等待為 3。

單機、所有作業同時可用、每作業獨占同一資源的特例中，交換相鄰 i、j 的總等待差為 `p_i-p_j`，可證 SPT 最優；不得把該特例的定理直接移植到本題多節點 gang。

若需要比較連續 aging，最小化鍵的正確符號為

\[
k_j(t)=f(v_j)-\lambda(t-a_j)=f(v_j)+\lambda a_j-\lambda t.
\]

同一決策時刻可去掉公共項 `-lambda*t`，靜態堆鍵應是 `f(v_j)+lambda*a_j`。同斜率線性 aging 不會改變兩個已在等待作業間的相對次序，但會減少未來新到達者超越旧作業的機會。這仍不是資源可用或最大等待保證。若使用該公式，必須定義單位與縮放；主方案不需要此項。

即使某個 gang 永遠排第一，只要「放不下就略過」並持續補入交错短作業，仍可能永遠湊不齊同步資源。因此優先權提升與資源承諾須分開。

## 4. 模組 A：單一受保護開始時刻的安全回填

### 4.1 未來資源快照

令 `A(t)` 為當前運行作業，包含先前已接納的 backfill。若此後不再啟動其他作業，則對 `u>=t`：

\[
f_m^r(u\mid t)=C_m^r-\sum_{i\in A(t):b_i>u}x_{im}d_i^r,
\quad r\in\{C,G\}.
\]

`d_i=(c_i,q_i)`；這個函數逐維非遞減，因為只有作業完成、沒有未來新增佔用。

為 protected head h 建立

\[
R_h=\min\{u\ge t:H_h(f(u\mid t))\ge w_h\}.
\]

只需檢查現在和已運行作業的不同完成時刻。到某個完成時刻時必須一次釋放所有同時完成者，再判斷 gang；不能用逐個 worker 的局部可行來代替全部同步。

建立具體證書 `z_hm`：總和為 w_h 且 `z_hm*d_h^r<=f_m^r(R_h|t)`。證書記錄「屆時確實有一種合法配置」。h 的開始承諾 R_h 一旦建立不能因後方作業而延後。

### 4.2 充分條件一：時間不重疊

候選 j 現在可原子放置且

\[
t+p_j\le R_h
\]

則安全。等號可接納，因為佔用區間半開，R_h 時先完成釋放再啟動 h。這是充分條件而非必要條件。

### 4.3 充分條件二：保留固定放置證書

設候選現在的配置為 y_m，結束時刻 e=t+p_j。如果 e>R_h，要求

\[
y_md_j^r\le f_m^r(t),\qquad
y_md_j^r+z_{hm}d_h^r\le f_m^r(R_h\mid t),\quad\forall m,r.
\]

可把它化成新的有效容量：

\[
\boxed{B_m^r=\min\{f_m^r(t),f_m^r(R_h\mid t)-z_{hm}d_h^r\}.}
\]

在 B 上用相同的槽數公式放置 j 即可。这仍允许在同一預約節點分享剩餘 CPU/GPU，並非整台節點鎖住。

證明：R_h 前只有當前作業與 j，已由現在容量保證；R_h 時加上 h 仍逐節點合法；R_h 後，這些已承諾作業只會完成，因此容量不會再次惡化。未來再接納其他作業時須重新套用安全檢查。

### 4.4 更寬鬆的精確條件：固定時間、可更換未啟動配置

只維持一個未啟動的受保護作業時，沒有必要永遠綁死 z。對給定的合法候選配置 y：

\[
\tilde f_m^r(R_h)=f_m^r(R_h\mid t)-\mathbf1(e>R_h)y_md_j^r.
\]

\[
\boxed{H_h(\tilde f(R_h))\ge w_h.}\tag{SAFE}
\]

在「只有當前運行作業、j 和單一未來 h」的模型中，這是**保留 h 於原 R_h 啟動的必要且充分條件**。必要性由槽數上限得出；充分性由槽數构造新證書及單調釋放性得出。

這不表示任意候選放置都好：若一個試探配置 y 失敗，只能說該 y 不安全，不代表不存在其他安全 y。

推荐的有限成本放置流程：先在現在資源上做普通 FF/BF，若 SAFE 通過便更新 h 的證書；若不通過，再在固定證書容量 B 上嘗試一次。兩次都失敗就拒絕本輪候選，不偷偷改 R_h。該流程對安全性精確，對「是否存在某種安全候選配置」可能保守。

### 4.5 精確處理兩作業共同放置的可選 DP

這是小案例 oracle／罕見失敗診斷，不列第一版主路徑。

當 e>R_h，候選 j 在節點 m 最多能放 `k_m=kappa_j(f_m(t))` 個 workers。放 k 個造成 h 的槽數損失

\[
\ell_m(k)=\kappa_h(f_m(R_h))-\kappa_h(f_m(R_h)-k d_j).
\]

可用損失預算 `S=H_h(f(R_h))-w_h`。求解

\[
\min\sum_m\ell_m(y_m)\quad\text{s.t.}\quad
0\le y_m\le k_m,\ \sum_m y_m=w_j,\ y_m\in\mathbb Z.
\]

其最小值不超過 S，當且僅當存在安全候選配置。多選背包 DP 為

\[
D[m,u]=\min_{0\le k\le\min(k_m,u)}\{D[m-1,u-k]+\ell_m(k)\}.
\]

`D[0,0]=0`，其他初值無限大。時間 O(M_g w_j k_max)，成本記憶體 O(w_j)；直接保留回溯指標需 O(M_g w_j)。不能在每個全量候選都運行而不測成本。限縮節點集合的 DP 只對該子集精確，不能把失敗稱為整池不可行。

### 4.6 不能只看 GPU，連 CPU/GPU 總量一起看也不夠

兩個同型號節點，每個 `(CPU,GPU)=(8,2)`。運行中的 r 在節點 1 使用 `(4,1)` 到 t=10。h 於 t=1 到達，需要兩個 workers，每個 `(6,1)`，duration=5。

t=1 時，節點 1 剩 `(4,1)`、節點 2 剩 `(8,2)`，只容納一個 h worker；最早 R_h=10。

j 在 t=2 到達，需要一個 `(4,1)` worker、duration=100，放在節點 1。到 t=10，兩節點合計剩 CPU=12、GPU=3，看似滿足 h 的總 CPU=12、GPU=2，但兩節點分別只有 `(4,1)`、`(8,2)`，仍只能放一個 h worker。h 要等到 t=102。

原 EASY 的 GPU surplus 可能接納這個候選；逐節點 SAFE 必須拒絕。這是數學手算反例，不是 trace 性能數據。

### 4.7 單預約的三個工程不變量

- 每接納一個 crossing backfill 都更新 R_h 快照，再檢查下一個；不可讓多個候選獨立借用同一份原始餘量。
- 對固定 R_h，初次 f(R_h) 已計入 b_i<=R_h 的未來釋放；現實時鐘到達這些完成事件時，不得再往 f(R_h) 加一次資源。只更新當前資源；新接納且 e>R_h 的作業才需從 f(R_h) 扣除。
- 候選資源提交與新預約證書更新是同一原子操作。R_h 不變，state_version 改變；過期 plan 必須失效。

## 5. 模組 B：選擇性保護、等待界與另一條設計路線

### 5.1 路線一：等待觸發的單一持久預約

每池使用固定共同門檻 theta_g，作業在

\[
u_j=a_j+\theta_g
\]

進入 urgent。排序 `(a_j,job_id)` 決定獲得 protected-head 身份的次序；新 urgent 不能取代現有 head。urgent 的 FIFO 指「取得保護的次序」，不禁止後方 urgent 在不延誤 head 時提前回填。

一般候選採 SPT 或 GPU-work。只有最老 urgent 得到一個持久 R_h，其餘作業可以按一般短作業鍵做安全回填。head 啟動後，立即讓下一個 urgent 取得保護，不等下一次外部事件。

沒有 urgent 時採有明確掃描預算的 shortest-feasible 填充，不為每個被跳過的普通作業建立預約。這是有意保留短作業自由度，不宣稱它符合 head-preserving EASY。

### 5.2 已證明：何時能保證不飢餓

條件：所有作業在空池單獨可行；運行時長有限；每個有限時間區間只有有限到達；節點不故障；共同 theta_g 有限；urgent FIFO 不被新作業插隊；protected head 不受候選上限裁剪；預約不延後且在 R_h 有強制派送事件。

對已取得 head 身份的 h，目前只有有限個運行作業，全部有限時間完成，所以有有限 R_h。安全檢查保證 h 最遲於 R_h 啟動。對任意 j，進入 urgent 時只有有限個前序 urgent；依前序逐一開始的歸納，j 最終也取得 head 並在有限時間開始。

這個結果不需要假設整體平均負載小於一，但不保證佇列穩定、平均等待有界或同一全域 SLA。持續過載下，越晚到達的作業可能有越大的等待。

原型的 urgent-HOL 排空分支也可在相應有限性條件下達到防飢餓；本方案的附加價值是「允許安全填補洞，而不丟失保護承諾」，不是聲稱首次發明 urgent queue。

### 5.3 三種「界」不可混用

1. **優先權提升門檻 theta_g**：只規定何時 eligible for protection，不是 s_j 的上界。
2. **取得 head 時的事後可計算承諾**：若於 v_j 取得預約 R_j，則 `s_j<=R_j`，因此 `W_j<=R_j-a_j`。
3. **額外有全域 P_max 與積壓界時的粗上界**：若 p_i<=P_max，j 在 u_j 進 urgent 時有 K_j 個前序 pending urgent，則

\[
\boxed{W_j\le\theta_g+(K_j+1)P_{\max}.}
\]

因為每次輪到新的 head，即便完全等目前運行作業結束，也不超過 P_max。逐個 head 最多這麼久即可啟動。此界很鬆；本 trace 最長 duration 約 184 天，不能把這個公式包裝成良好服務品質。

不存在對任意輸入都成立的固定小 W_max：一個 GPU 上 n 個時長為 1 的作業同時到達，至少一個等待 n-1；或一個不可搶占作業已佔 GPU 任意長時間。若要預先固定 SLA，必須再限制服務時間、突發到達與積壓，或允許 admission control。本題要求全部作業排程，不得藉丟棄／隱藏排隊來製造 SLA。

有限 trace 且最終排空時，純 SPT 的極端延後也不宜直接稱作「已觀測到無限飢餓」；那是對持續到達序列的理論風險。

### 5.4 路線二：所有等待作業保留時間區間的 Conservative Backfilling

每個新到達作業依 FCFS 順序，在既有運行作業和全部已承諾預約日曆中找到最早可行的固定配置 `[R_j,R_j+p_j)`。記錄承諾 `D_j=R_j`。允許 SPT 候選提前執行，但不得破壞其餘作業的日曆。

設日曆剩餘資源為 F_m^r(u)。若試圖讓 j 從 s 運行至 s+p_j，定义

\[
B_{jm}^r(s)=\min_{u\in[s,s+p_j)}F_m^r(u).
\]

\[
\boxed{\sum_m\kappa_j(B_{jm}(s))\ge w_j}
\]

當且僅當存在整段不移動 workers 的固定配置。每個節點先求整段最小容量，再算槽數；不能只檢查開始時刻，也不能在每一時刻另找不同節點而偷偷允許遷移。

日曆只在已知作業開始／完成時刻跳變。最早可行開始可從現在、到達時刻與日曆事件邊界中搜尋；實作時以小型完整事件搜尋作 oracle，勿假定與單一 future reservation 相同的單調性。

候選提前執行時，先在暫存日曆移除它自己的舊預約，再檢查新區間；成功才替換，失敗必須恢復舊預約。其他作業不得重排得更晚。到達任一承諾時刻，該作業的預約派送不受短作業掃描上限影響。

**保證：**一旦 j 獲得有限承諾 D_j，後來到達作業不能使其開始晚於 D_j。因為可將新作業排在所有既有區間結束之後，所以在有限日曆、單獨可行時一定能形成某個有限承諾。

**代價：**每個普通長作業都建立預約，可能過早限制後來短作業；維護所有等待作業的日曆與區間查詢昂貴。完整日曆的存在不意味著對所有輸入有共同固定 W_max。

### 5.5 路線比較

| 項目 | 選擇性單預約 | 全等待作業時間區間預約 |
|---|---|---|
| 保護開始 | 等待門檻後依 FIFO 取得 head | 新到達建立日曆時 |
| 每池未啟動預約 | 最多一個 | 可達等待作業數 |
| 核心判定 | 現在與 R_h 的雙快照 | 完整執行區間的節點最小容量 |
| 未啟動 head 可否換節點 | 可以，時間不變、重建證書 | 需檢查全部其他區間，不能逐個獨立判定 |
| 普通短作業自由度 | 高 | 較受限，但實測優劣仍依工作負載 |
| 可證明性 | head 不延遲、條件式防飢餓 | 每個已預約作業不晚於個別承諾 |
| 六天定位 | 主方案 | 小型／代表性對照、後續延伸 |

## 6. 模組 C：CPU/GPU 放置

### 6.1 First-Fit

固定按 node_id 排序，以槽數成塊放入 `min(remaining,slots)` workers。對同質 worker，完整掃描本身就是精確的可行性判定與構造；不需要逐 worker 回溯。成本 O(M_g)，但對其他作業未來可用形狀沒有最佳性保證。

### 6.2 GPU-first lexicographic Best-Fit

在合法的實際或安全有效容量上，排序鍵明確規定為

\[
(f_m^G-q_j,\ f_m^C-c_j,\ node\_id).
\]

逐維字典序，GPU 殘量優先，CPU 殘量為平手條件；不得稱為「所有多維 Best-Fit 的唯一標準」。選中節點後盡量成塊放置相同 workers。若使用固定預約有效容量 B，優先按 B 的殘量排序，實際容量只作後續平手資訊。

全節點排序 O(M_g log M_g)；可用 GPU 數量桶和 CPU 有序結構加速。它傾向保留完整 GPU 節點，但不保證消除所有 CPU stranding 或達成最優等待。

### 6.3 Queue-conditioned shape-aware 放置：可選消融

只使用已到達 queue 的小型參考集合 S，移除當前要啟動作業，於本次規劃內固定集合與權重。對代表性 gang z 定義

\[
\Phi(f)=\sum_{z\in S}\pi_z\min\{1,H_z(f)/w_z\},\quad\sum_z\pi_z=1.
\]

在已滿足真正安全約束的候選配置中，偏好最大化放置後 Phi（或最小化機會損失）的配置。這是「其他代表性作業各自的可放置程度」代理，不是它們能同時啟動的數量，更不是完成時間保證。

可以維護每個代表性 z 的 H_z；試放一個 worker 只更新該節點的槽數貢獻。用 K_shape 個代表和 K_node 個候選節點，逐 worker 搜尋約 O(w_j K_node K_shape)，另加參考槽數的建立與索引成本。有限節點 shortlist 只用於挑選配置，不用來證明 protected head 不可行。

CPU/GPU 殘量平方差或硬體原始比例都是代理，不能僅因看起來平衡就採用。Synergy/FGD 可提供多資源與 fragmentation 動機，但原方法包含本題沒有的 profiling 或 fractional-GPU 設定，不原樣移植。

### 6.4 A10 的精確特化

本次重新讀原始 CSV：A10 有 2,494 個單 GPU 節點，2 個 CPU=126、2,492 個 CPU=128；111,284 個 A10 作業中有 110,497 個單 worker。全部 A10 每 worker 請求一 GPU。[S2]

單 GPU 池中，節點是空閒或被某一 worker 完全佔去 GPU，CPU 相容集合呈巢狀：要求 CPU 越高，可用節點集合越小。對同一候選，優先選 CPU 最小但足夠的空閒節點，能保留所有 CPU 門檻對應的高容量空閒節點數；這可用交換論證，不能擴大成整體平均等待最優定理。

設每個符合 c_h 的節點下一個可用時刻為 `ell_m=t`（現在空閒）或所佔作業的完成時刻。R_h 為相容節點 ell_m 的第 w_h 小值，不是把所有 CPU 類別混合計數。

對 e>R_h 的候選 j，定義 `S=H_h(f(R_h))-w_h`。候選佔用一個同樣能服務 h 的目前空閒節點，恰損失一個 h 槽；佔用不相容於 h、但相容於 j 的節點，損失零。先用損失零的節點，再在 S 預算內用損失一的節點，就能精確判定並構造安全配置。这是第 4.5 節 DP 的閉式特例。

CPU 桶由輸入容量動態建立並驗證，不能把 126／128 寫死為通用演算法規則。特化必須與通用公式逐案例比較；FF 與 CPU-smallest-fit 是不同放置規則，不可為加速悄悄互換。

## 7. 可交付的偽代碼

### 7.1 建立最早單預約

```text
BUILD_RESERVATION(h, t, state):
    F <- copy of current per-node free CPU/GPU
    H <- sum(slots(h, F[m]) over all compatible nodes)
    if H >= workers[h]:
        return (R=t, F_at_R=F, witness=PLACE(h,F))

    releases <- active jobs sorted by (finish_time, job_id)
    for each group of jobs with identical finish time u:
        for each finished job i in group:
            for each (node m, worker_count k) in allocation[i]:
                old <- slots(h,F[m])
                F[m] <- F[m] + k * demand[i]
                H <- H + slots(h,F[m]) - old
        if H >= workers[h]:
            return (R=u, F_at_R=F, witness=PLACE(h,F))

    raise INPUT_OR_STATE_ERROR   # empty-cluster feasibility should prevent this
```

`PLACE` 不更改真實狀態；可以按 FF/BF 產生任何合法完整配置。

### 7.2 安全候選規劃

```text
SAFE_PLAN(j, t, state, reservation):
    Y0 <- PLACE(j, current_free)                 # pure, full-gang plan
    if Y0 does not exist: return REJECT_NOW_FIT
    if reservation does not exist:
        return proposed_commit(Y0, no_reservation_change)

    (h,R,F_R,Z) <- reservation
    if t + duration[j] <= R:
        return proposed_commit(Y0, F_R unchanged, Z unchanged)

    F_trial <- F_R minus demand of Y0 on touched nodes
    if sum(slots(h,F_trial[m])) >= workers[h]:
        Z_new <- retain Z if still valid, otherwise PLACE(h,F_trial)
        return proposed_commit(Y0,F_trial,Z_new,R unchanged)

    B[m] <- componentwise_min(current_free[m], F_R[m]-Z[m]*demand[h])
    Y1 <- PLACE(j,B)
    if Y1 exists:
        return proposed_commit(Y1,F_R-demand(Y1),Z unchanged,R unchanged)

    return REJECT_RESERVATION   # not a proof that no alternative safe Y exists
```

A10 可用第 6.4 節精確特化直接產生 Y。DP 只在小型驗證或明確限額的研究開關中執行。

### 7.3 主方案事件循環

```text
Initialize all nodes idle; no future jobs visible to policy.
Initialize arrival events, completion heap, threshold events, guard events.

At each next event time t:
    release ALL jobs completing at t
    enqueue ALL jobs arriving at t
    activate ALL still-waiting jobs with a_j + theta_g <= t
    process due guard identities; discard stale events using version/job state

    for each affected GPU pool:
        repeat at the same t:
            h <- existing protected job; otherwise oldest urgent waiting job

            if h exists:
                if h fits now on the FULL compatible pool:
                    validate and atomically START h
                    clear its reservation; remove h from waiting/urgent queues
                    continue                    # next urgent checked immediately
                if h has no reservation:
                    guard <- BUILD_RESERVATION(h,t,state)
                    schedule wakeup at guard.R
                assert t < guard.R             # due but infeasible is a failure

            candidates <- up to K waiting jobs in base-key order, excluding h
            starts_this_pass <- 0
            for each j in candidates:
                proposal <- SAFE_PLAN(j,t,state,guard)
                if proposal accepted:
                    validate state version, now capacity and future certificate
                    atomically commit job AND any reservation witness update
                    add completion at t+p_j; remove j from waiting
                    starts_this_pass += 1

            if starts_this_pass == 0: break
            # A successful pass continues at the same simulated time.
            # Do not postpone already feasible work merely because K was reached.

    advance to earliest arrival/completion/threshold/reservation event

After last arrival: continue until EVERY input job completes.
```

每次 candidate pass 最多 K 次嘗試；有成功就同時刻再進一輪。protected head 的完整可行性及到期派送不計入 K，不能因掃描限制失去保證。普通工作在 K 個候選全被阻擋時可暫停，因此本實作不是全佇列最優或完全 work-conserving，須量測 scan-limit idle。

### 7.4 低風險備用的唯一核心替換

```text
SAFE_PLAN_BACKUP(j,t,state,guard):
    if guard exists and t + duration[j] > guard.R:
        return REJECT_DURATION_CROSSING
    return full-pool atomic First-Fit plan if feasible
```

仍需完整節點級 BUILD_RESERVATION、urgent FIFO、threshold/guard events、半開區間與累積資源狀態。不能用原本 GPU-count shadow 取代真正的 R。

### 7.5 Conservative 路線偽代碼

```text
On arrivals at time t, after processing due completions/starts:
    for new job j in (arrival,job_id) order:
        enumerate candidate start times from t and calendar event boundaries
        find earliest s with a constant full-gang placement over [s,s+p_j)
        add per-node CPU/GPU reservation for that whole interval
        store immutable promised_start[j] = s

On scheduling opportunities:
    execute every due committed reservation first
    for short candidates j within budget:
        trial_calendar <- calendar with ONLY j's own old reservation removed
        if j fits on fixed nodes over [t,t+p_j) in trial_calendar:
            atomically replace its old reservation with actual running interval
        otherwise leave the calendar unchanged
```

兩種路線不能共用「只驗 R_h」的安全函數：單預約函數必須斷言本池沒有其他未來起動承諾。

## 8. 時間與空間複雜度

令 N 為作業數，M_g 為池節點數，Q 為等待長度，r_t 為當時運行作業數，L_t 為運行作業的非零 job-node 配置項數，A 為實際候選嘗試總數，E 為事件處理／候選階段數。

- 到達排序與 heap 維護：O(N log N)；可用到達指標避免把全部到達放入 heap。
- 普通即時可行性及 FF：O(M_g)。全節點 BF 排序：O(M_g log M_g)。不能把放置整體寫成 O(log Q)。
- BUILD_RESERVATION：O(M_g + r_t log r_t + L_t)，另加一次見證放置的排序成本。增量更新 h 槽數避免每個釋放事件重掃 M_g。
- SAFE 對給定配置的槽數更新可只訪問被影響節點；若要重建證書，可能再有 O(M_g) 或 BF 排序成本。
- 一個 reservation 在 head 啟動前不撤销，建立次數最多 N，不需每次 arrival 都重建。
- 每次 pass 最多 K 候選、每個成功 pass 至少啟動一個新作業，因此 A 的粗界為 O(K(E+N))。E 包含 arrival、completion、threshold、guard 等，仍是 O(N) 級數量；但常數和每次放置成本不可忽略。

主方案總成本可按實測計数表示為

\[
O\left(N\log N+A(C_{place}+\log Q)+
\sum_{reservation\ creations}(M_g+r_t\log r_t+L_t)\right),
\]

其中一般 FF 時 `C_place=O(M_g)`，BF 時包含排序與證書維護。這不是無條件近線性性能承諾。

因每個運行作業至少佔一個正整數 GPU，運行作業數不超過全叢集 10,412 張 GPU；當前非零配置項也不超過已分配 GPU 數。大量等待作業不需要 224,112×4,278 的全密集矩陣。

空間使用作業陣列 O(N)、節點陣列 O(M)、等待／事件結構 O(N)、每池單預約 O(M_g)、稀疏 allocation ledger O(全部實際 job-node 配置項)。如保留每個 worker 的歷史也須按總 workers 說明，不籠統聲稱 O(N)。

Conservative 日曆若有 B 個全局邊界，一次試探 s 的朴素完整區間檢查可達 O(M_g B)，枚舉 B 個候選開始便達 O(M_g B^2)；實際需事件 sweep、區間樹或分段日曆加速。即使做了索引，也不得聲稱其維護全部等待預約只需 O(log N)。

實作優先級：A10 CPU 類別桶／可用時刻順序統計 → 保留通用向量化 oracle → profile reservation 建立次數及候選嘗試 → 再決定編譯加速。沒有量測前，不承諾全量新方案耗時數秒。

## 9. 失效條件與需要明確降級的情況

安全推導依賴：exact duration、靜態容量、無故障、固定 worker 需求、同質 workers、合法 GPU 型號、非搶占、無未建模拓撲限制。duration 超時、節點故障或動態 capacity 降低會使原承諾失效；在題目外不能沿用硬保證。

單快照預約不能擴充成多預約，除非升級為完整時間區間檢查。分別證明兩個未來作業「各有一種配置」，不代表它們的配置可以同時存在。

主方案可能性能不佳的原因：theta 太小使大量長作業過早取得保護；theta 太大仍允許長期延後；少數剛被接納的極長作業可阻擋尚未取得 head 的 urgent；候選上限可能造成空閒；固定證書 fallback 有保守損失；形狀代理只改善分數不改善等待。

一個試探 placement 被 SAFE 拒絕，不證明沒有安全 placement；局部形狀最佳不代表時間排程最佳；已驗證安全不代表平均等待接近 SPT 的某個理論比例。

## 10. 正確性測試與驗收

以下是必須實作的測試規格，**本文件未聲稱新排程器已通過它們**。

| 測試 | 輸入／操作 | 預期 |
|---|---|---|
| 原子 gang | 只容納 w-1 workers | plan 失敗且狀態完全不變 |
| worker 不可拆 | 兩節點各 1 GPU，worker 要 2 GPU | 不可行 |
| CPU 零／小數 | c=0、c=0.6、反覆分配釋放 | 整數化後精確守恆，不除零 |
| 聚合反例 | 第 4.6 節兩節點、三作業 | 拒絕 j crossing；h 最遲 t=10 |
| 等號邊界 | j 在 R_h 恰好完成 | 可回填，先釋放再啟動 h |
| 空間安全 crossing | N1=(8 CPU,2GPU)，r 使用(4,1)至10；N2=(2,1)空閒；h 要(8,2)，j 要(2,1)且運行越過10 | j 可放 N2，h 仍10；time-only 備用可保守拒絕 |
| 可移動證書 | 兩節點均(8,2)；N1 的 r 用(4,1)至10，N2 的 r 用(8,2)至10；h 要(8,2)，原證書選N1；j 現在只能在N1放(4,1)且越過10 | 固定證書拒絕，但彈性 SAFE 改 h 至N2 可接納 |
| 累積餘量 | 多個 j 單獨可接受、合起來超出 guard 槽數餘量 | 後一個必須按更新後 f(R_h) 被拒絕 |
| 不可撤銷 | 更短作業在 guard 建立後到達 | 不替換 guard、不延後 R_h |
| 門檻事件 | a+theta 位於兩個外部事件之間 | 精確觸發 urgent，不等到下個 completion |
| 到期保證 | R_h 到達，普通隊列超過 K | head 仍先派送，無候選裁剪 |
| 先前資源釋放已預計 | b_i<=R_h 的作業現實完成 | 不重複增加 f(R_h) |
| 多預約時間陷阱 | 一節點新作業要[0,10)，既有預約[5,7) | start-only 通過也必須被區間法拒絕 |
| 禁止虛擬遷移 | N1只在[0,5)空閒、N2只在[5,10)空閒；job需固定一節點運行10 | 全區間固定配置判定拒絕 |
| 有限 trace 排空 | 最後 arrival 後仍有長作業與 urgent | 全部完成，無負等待、无未啟動作業計為完成 |
| 同到達平手 | 調換 CSV 行順序 | 在 job_id／node_id 契約下結果相同 |
| 加速等價 | A10 桶對同一 placement 規則的通用 oracle | feasibility、R、配置合法性、開始時間一致 |

獨立驗證不能只調用 scheduler 自己的 `safe()`：保存每作業開始、結束與稀疏配置，按節點獨立重播帳本。保存 reservation_created / certificate_updated / protected_started，核對每個有效承諾 `s_h<=R_h`、有效配置及 version 關聯。

小實例可枚舉候選配置與 h 配置，验证 SAFE 與存在性；使用第 4.5 節 DP 比較啟發式的安全配置漏失率。小規模 CP-SAT 排程可作最優下界／gap，不列全 trace 求解器。超時時區分 incumbent、best_bound 和已證最優；下界為零時不要除零報相對 gap。

## 11. 消融與實驗協議

### 11.1 先對齊共同平台

固定 CPU 單位、秒數精度、到達／完成順序、初始空池、平手規則、GPU 型號隔離與窗口。新比較建議 `T_eval=90*86400`；另可重算 `max(submit_time)` 舊窗口作來源對照，但不可混列未標記。

CPU 使用 Decimal 或等價精度驗證後轉整數單位；本資料可用 1/100 vCPU，不能一般化為未檢查的截斷。所有 starts 初值用 None/-1 而不是 0。每個 pool 完成數必須等於輸入數，最後資源全部還原；卡死時 fail loud。

### 11.2 不堆全因子，按問題分階段

第一階段只用相同 FF：FCFS-HOL、SPT-HOL、SPT-feasible、GPU-work-feasible、正確 FIFO-head EASY。其目的為區分排序、HOL 跳過與真正預約。

第二階段固定一般排序與放置，比較：

1. 無保護；
2. urgent FIFO 遇阻即停止全部新啟動（排空）；
3. urgent + time-only 安全回填；
4. urgent + 固定節點資源證書回填；
5. urgent + 彈性證書雙快照與固定證書 fallback。

這組回答「改善來自何處」「同節點餘量與重新配置到底值不值得」。第 2 項可以防飢餓，不能錯寫成無保護。第 3–5 項共享不可延後 R。

第三階段在選定保護機制上比較 SPT 與 GPU-work；同一 theta、K 和 placement。不能用 SAF 的 BF 對 SPT 的 FF 直接歸因於排序。

第四階段固定排序與保護，才比較 FF、GPU-first BF、shape-aware。另跑 BF 剔除 ratio 項以確認原始硬體 ratio 是否有獨立貢獻。WF 可做壓力對照，不默認作主方案。

Conservative 全日曆在可負擔的小型或代表性情景中與單預約比較，檢查個別承諾、預約拒絕機會與成本；狀態需從相同初始化重播，不任意重置每天積壓。

### 11.3 參數有限且有單位

先限定 theta 候選為 `{24,168,720,1350}` 小時；0 與 infinity 僅作端點診斷（所有作業立即 urgent／完全無 urgent）。這是建議探索網格，不是官方要求或已校準最佳值。第一輪用全池共同 theta，避免六池各調一組參數。

候選預算 K 建議 `{32,128}`，再以少量 `{512}` 做飽和檢查。形狀代表數先用固定小值，例如 16，僅在前面對照有需求時啟用。沒有實測證據前不繼承原 AMBF 的 0.7、0.01、1350 等參數作「最佳設定」。

### 11.4 指標不能只看平均

- 每池及全體：mean/P50/P95/P99/max wait、固定窗口完成數、最後完成時刻。
- 長作業：按預先固定 duration 門檻、duration 分位組及 GPU-work 組分層；同時觀察絕對等待及 bounded slowdown。
- 保護：`s_h-R_h` 最大值應不大於 0；取得 head 前的 urgent wait 與取得 head 後的 reservation wait 分開；theta 超越量不是安全違規。
- 成本：feasibility_checks、candidate_attempts、reservation_builds、certificate_rebuilds、crossing_accepts、reservation_rejects、scan_limit_hits、CPU wall time、peak memory。
- 配置率：容量時間加權，不是 GPU 核心實測使用率。固定工作量全部排空後，資源總 work 不會因調度而憑空改變。

### 11.5 資源預約損失的可操作度量

「有空 GPU」不等於「預約造成浪費」。記錄目前可放置但因 SAFE 被拒絕的候選數及資源形狀，並做 time-only→固定證書→彈性證書的同條件比較。

對抽樣快照與相同候選集合，定义不保護與保護下的可行啟動集合 F_free、F_safe，後者是前者子集。若精確求解相同 GPU 啟動量目標，則

\[
L_{res}(t)=\max_{B\in F_{free}}\sum_{j\in B}w_jq_j
-\max_{B\in F_{safe}}\sum_{j\in B}w_jq_j\ge0.
\]

它是當前可啟動容量的機會差，不是全程 GPU-hours 損失或唯一因果占比。若兩邊只用啟發式，不保證估計差非負，須標明。另記錄彈性證書額外接納的 crossing jobs，不能把其工作量直接等同整體性能收益。

### 11.6 壓力、統計與泛化

到達壓縮、整節點容量變動、同時到達平手排序及極端大 gang 作壓力情景；不改 duration 或需求來美化主實驗。完整 trace 已被探索過，後續時間切分只能稱內部穩健性研究，不能事後宣稱 untouched test。確定性重播的重複執行只量測 wall-time 波動，不增加獨立工作負載樣本；作業等待相依，不直接把 224,112 jobs 當 IID 做顯著性。

## 12. 最小接口與輸出契約

以下是語義接口，不要求為每個接口新增檔案或框架；沿用現有 repo 結構。

```text
Job(a,p,w,q,c,g,id)
Node(id,g,G,C)
AllocationPlan(job_id, [(node_id,worker_count)], state_version)
Reservation(job_id, created_at, start_time, witness, F_at_R, version)

slots(job, resource_view) -> per-node integer slot counts
plan(job, resource_view, placement_rule) -> full AllocationPlan | None
build_reservation(head, now, state) -> Reservation
safe_plan(job, now, state, reservation) -> Proposal | RejectReason
commit(proposal) -> allocation + event + reservation update, all atomic
release(job_id) -> exact inverse of actual allocation
validate_ledger(all_jobs, allocations, reservations) -> PASS or explicit failure
```

必須保存的逐作業欄位：job_id、arrival、duration、start、finish、GPU type、workers、q、c、base_key、urgent_time（若曾進入）、protection_acquired_at（若曾取得）、promised_start（若有）、稀疏 allocation。需要記錄不同事件而非只存最終 guard，才能驗證不可延後。

不得把偽資料補入圖表。正式圖表只讀結果檔；記錄輸入 hash、程式 revision、config、時間窗口、機器環境與驗證狀態。舊程式結果保留為可定位的歷史對照，不將其錯誤的 EASY 契約當作正確基線。

## 13. 六天交付順序與停止條件

第 1 天：統一模型、資料契約與來源；重現真正的共同 FF 基線、獨立帳本、slot 函數；處理 A10 狀態介面。

第 2 天：完成 urgent FIFO + 正確 R + time-only 備用；通過手算與小型枚舉，完成全量可執行性與成本量測。備用是完整可交付路線，不等最後一天才寫。

第 3 天：加入雙快照 SAFE、可更新證書與固定證書 fallback；測 crossing、cumulative slack、threshold、forced dispatch；不實作全量 DP 或多預約日曆。

第 4 天：完成有限 theta/K 與 SPT/GPU-work 對照；有證據才加入 BF／shape 模組；凍結主架構。若主方案仍存在任何 reservation violation，使用已驗證備用，不能以平均結果較好掩蓋。

第 5 天：消融、分層、壓力、成本；可負擔的小實例 Conservative／DP oracle。若 shape 模組無穩健收益或成本過高，移除。若彈性證書相對備用沒有足夠收益，可保留備用為最終方法，正文如實說明。

第 6 天：鎖定數字、獨立驗證、10 頁正文方法與限制、可重現入口及 AI disclosure。安全證明、實驗表與程式分支必須逐項對應。

主方案是否比備用更好、theta 最佳值、BF／shape 是否值得保留：目前全部 **NOT_RUN**。已完成的工作是讀取／核對来源、建立可證明條件與可執行的實驗規格，不是新方法性能驗收。

## 14. 核心文獻與可引用範圍

文獻只用來定位經典方法與相關動機。本文件的双快照、固定證書及等待界採上文自己的完整推導，不把它們聲稱為新發明，也不借文獻替代條件驗證。

[L1] Ahuva W. Mu'alem and Dror G. Feitelson, *Utilization, Predictability, Workloads, and User Runtime Estimates in Scheduling the IBM SP2 with Backfilling*, IEEE TPDS 12(6), 529–543 (2001), DOI 10.1109/71.932708. EASY 保護隊首，Conservative 保護所有等待預約；相對性能依工作負載，不是某一方法全面勝出。

[L2] David Talby and Dror G. Feitelson, *Supporting Priorities and Improving Utilization of the IBM SP Scheduler Using Slack-Based Backfilling* (1999). 優先權、slack 與可預測等待的經典方向；不能將其摘要中的 bounded wait 不帶模型條件地複製到本題。

[L3] SchedMD, *Scheduling Configuration Guide* 與 *slurm.conf*（本次 2026-10-14 查閱官方文件）。說明 backfill 的 higher-priority start-time protection、計算预算、等待年齡後才預約等實務機制。Slurm 為性能可整節點預約，本題允許節點內 CPU/GPU 共置，不能因此聲稱必須整節點鎖定。

[L4] Jayashree Mohan et al., *Looking Beyond GPUs for DNN Scheduling on Multi-Tenant Clusters*, OSDI 2022 (Synergy). 可借多資源放置動機，不移植 profiling／調整需求。

[L5] Qizhen Weng et al., *Beware of Fragmentation: Scheduling GPU-Sharing Workloads with Fragmentation Gradient Descent*, USENIX ATC 2023. 可借需求分布條件化 fragmentation 動機；原研究含 fractional-GPU sharing，本題已移除 fractional GPU，不直接採用原資源模型。

官方／作者來源：

```text
https://cris.huji.ac.il/en/publications/utilization-predictability-workloads-and-user-runtime-estimates-i/
https://cris.huji.ac.il/en/publications/supporting-priorities-and-improving-utilization-of-the-ibm-sp-sch/
https://slurm.schedmd.com/sched_config.html
https://slurm.schedmd.com/slurm.conf.html
https://www.usenix.org/conference/osdi22/presentation/mohan
https://www.usenix.org/conference/atc23/presentation/weng
```
