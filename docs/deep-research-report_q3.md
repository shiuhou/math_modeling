# 2026 MCM Senior Problem B 第三問：跨 GPU 型號資源調配的嚴格建模研究

## 資料邊界與研究結論

先釐清一個重要的來源問題。公開可驗證的 COMAP 2026 MCM/ICM 官方頁面中，MCM Problem B 是「Creating a Moon Colony Using a Space Elevator System」，不是 GPU 排程題。citeturn6view5 因此，你所稱的「2026 MCM Senior Problem B」應是另一套競賽、Senior 版本、內部題目版本，或未公開索引的題目；我沒有找到可公開驗證的 GPU 題官方頁面。另一方面，本對話目前也沒有可檢索的 Q1/Q2 文件。因此，下面**不會把任何 GPU 型號間的相容性、效能比或 benchmark 數字偽裝成題目事實**，而是嚴格區分：

> **題面／你已明示的條件**：GPU 型號異構、每個 job 有固定原生 GPU 需求、不可搶占、Gang Scheduling。  
> **若 Q1/Q2 資料中存在即可直接繼承的量**：GPU 各型號數量、job arrival/release time、native GPU type、GPU 數量需求、native duration、Q2 的目標函數與 baseline schedule。  
> **Q3 新增但沒有資料支持的量**：跨型號 compatibility、slowdown \(\alpha\)、GPU 數量換算比例、reserve 比例。這些都必須標成 **scenario assumption**，不能寫成 empirical fact。

這個區分非常重要。異構 GPU 排程研究確實會用「job × accelerator type」的效能矩陣；例如 Gavel 的 heterogeneity-aware formulation 直接以不同 workload 在不同 accelerator 上的 throughput 為輸入，而且論文明確允許某個 job 在某 accelerator 上不可執行。這正好說明：**若本題沒有 benchmark，不能反推一張真實的 performance matrix。** citeturn6view0turn8view0turn9view0

我的核心建議是：

\[
\boxed{\text{Q3 主模型}=\text{Binary Compatibility A}
+\text{Soft Capacity Protection C}
+\text{Slowdown B 的敏感度分析}}
\]

而不是在 A、B、C 中三選一。

原因是三者其實描述**不同層次**：

\[
\underbrace{c_{bk}}_{\text{能不能跑}}
\quad\longrightarrow\quad
\underbrace{\alpha_{bk}}_{\text{跑多慢}}
\quad\longrightarrow\quad
\underbrace{B_k}_{\text{最多准許借多少 donor GPU}}
\]

A 是**可行性層**；B 是**效能層**；C 是**資源治理／風險保護層**。真正在六天競賽中最穩健的做法，是先用 A+C 建立主模型，再把 B 作為 scenario sensitivity，而不是聲稱自己知道真實 \(\alpha\)。

此外，Gang Scheduling 本身意味著一組 worker 必須以 all-or-nothing 方式取得資源；現行 Kubernetes 的正式定義也是整個 group 無法滿足時就不進行部分配置。citeturn6view3 因此，在這題中應把一個 job 看成**不可拆的 GPU gang**，而不是把 GPU demand 當成可以任意 fractional conversion 的流量。

## 統一數學框架

### 基本集合與資料

令

\[
\mathcal J=\{1,\ldots,J\}
\]

為 jobs 集合，

\[
\mathcal K=\{1,\ldots,K\}
\]

為 GPU 型號集合，

\[
\mathcal B=\{1,\ldots,B\}
\]

為 job types。

對 job \(j\)，定義：

\[
b_j\in\mathcal B
\]

為 job type；

\[
n_j\in\mathcal K
\]

為它的 **native GPU type**；

\[
g_j\in\mathbb Z_+
\]

為原生 Gang GPU 數量；

\[
p_j>0
\]

為 native GPU 上的原生執行時間；

\[
r_j
\]

為 release/arrival time。

GPU 型號 \(k\) 的 cluster capacity 為

\[
C_k\in\mathbb Z_+.
\]

如果 Q1/Q2 已經定義 priority、deadline、weight 或 cost，Q3 應完全沿用，不應為了跨 GPU 額外改一套 scheduling objective。異構 accelerator 在實際系統中本來就需要區分型號；例如 Kubernetes Kueue 的 `ResourceFlavor` 明確將不同 GPU model 視為不同 flavor，而不是一種統一的「GPU unit」。citeturn6view1turn6view2

### GPU compatibility graph

建議不要畫「GPU A → GPU B」的圖，而應建立**有向二分圖**

\[
G_C=(\mathcal B\cup\mathcal K,E).
\]

對每個 job type \(b\) 與 GPU type \(k\)，定義

\[
c_{bk}=
\begin{cases}
1,&(b,k)\in E,\\
0,&\text{otherwise}.
\end{cases}
\]

其語意非常窄：

> \(c_{bk}=1\) 只代表「type \(b\) 的 job 被允許完整地在 type \(k\) GPU 上執行」。

它**不代表速度相同、不代表效能較好，也不代表一張 \(k\) GPU 可以等價成多少張 native GPU**。

原生邊固定為

\[
c_{b,n_b}=1.
\]

如果官方資料沒有提供 software architecture、memory requirement、runtime compatibility 等資訊，那麼唯一能由資料保證的就是 native edge。所有

\[
k\neq n_b
\]

的跨型號 edge 都應寫成 scenario edge。

這種「可執行性」與「效能」分離的方式與異構排程文獻的做法相符：Gavel 的 throughput matrix 可以把不能運行的 job–accelerator pairing 視為不可行，而各可行 pairing 再具有不同 throughput。citeturn8view0turn9view0

令決策變數

\[
x_{jk}\in\{0,1\},
\]

其中

\[
x_{jk}=1
\]

表示 job \(j\) 整次 execution 都使用 GPU type \(k\)。

必須滿足

\[
\sum_{k\in\mathcal K}x_{jk}=1
\qquad \forall j,
\]

以及

\[
x_{jk}\le c_{b_jk}
\qquad \forall j,k.
\]

這裡有一個非常重要的低風險假設：

\[
\boxed{\text{同一個 job 的 gang 不混用不同 GPU 型號}}
\]

也就是如果 job 需要 8 GPUs，它不是「4 張 A100 + 4 張另一型號」，而是整組選一個型號。

這個限制很值得保留。Gavel 等異構研究顯示，distributed-job throughput 不只取決於 accelerator type，也會受到 placement 等因素影響；在完全沒有 benchmark、通信與 topology 資料時，允許 mixed-type synchronous gangs 會額外引入 straggler 與同步效應，模型反而無法被題目資料識別。citeturn8view0

### Substitute GPU execution model

令 job \(j\) 的開始時間為

\[
s_j\ge r_j.
\]

如果 job 被放在 \(k\) 型 GPU，定義執行時間

\[
P_{jk}.
\]

最一般形式是

\[
P_{jk}=\alpha_{b_jk}p_j,
\]

其中

\[
\alpha_{b,n_b}=1.
\]

完成時間因此為

\[
C_j
=
s_j+
\sum_k P_{jk}x_{jk}.
\]

定義 occupancy indicator

\[
u_{jk}(t)
=
x_{jk}
\mathbf 1
\left\{
s_j\le t<C_j
\right\}.
\]

則 \(u_{jk}(t)=1\) 表示 job \(j\) 在時間 \(t\) 正完整占用 \(k\) 型 GPU。

這一個定義同時表達了兩個題目條件：

**不可搶占**

\[
[s_j,C_j)
\]

是一個連續執行區間，中間不能被切斷。

**Gang Scheduling**

job 必須在整個區間同時取得它所需的全部 GPU：

\[
\sum_j q_{jk}u_{jk}(t)
\le C_k
\qquad
\forall k,t,
\]

其中 \(q_{jk}\) 是 job \(j\) 如果使用 type \(k\) 時的實際 GPU 數量。

這比只寫「總 GPU-hours 不超容量」嚴格得多。Gang scheduling 是瞬時 concurrent-capacity constraint，而不是只控制總面積。正式 Kubernetes gang scheduling 同樣採 all-or-nothing admission，因此這是與題意一致的抽象。citeturn6view3

### Resource conversion model

這裡是最容易過度建模的地方。

可以一般性定義

\[
q_{jk}
=
\left\lceil
\rho_{b_jk}g_j
\right\rceil ,
\]

其中

\[
\rho_{b,n_b}=1.
\]

例如理論上：

\[
\rho_{bk}>1
\]

代表需要更多 substitute GPUs，

\[
\rho_{bk}<1
\]

代表少數高性能 substitute GPUs 可以取代較多 native GPUs。

但是，在你的題目前提「**原生作業需求固定**」與「沒有 benchmark」下，這個模型不應直接使用。

最低風險應固定：

\[
\boxed{q_{jk}=g_j\quad\forall\text{ compatible }k.}
\]

亦即：

> substitution 只換 GPU **型號**，不改 gang size。

這樣 GPU 轉換發生在**時間維度**：

\[
p_j
\longrightarrow
\alpha_{bk}p_j,
\]

而不是擅自發明

\[
8\text{ GPU-A}
\equiv
4\text{ GPU-B}.
\]

可再定義 GPU-time service demand：

\[
W_{jk}
=
q_{jk}P_{jk}.
\]

在 MVP 中，

\[
W_{jk}
=
g_j\alpha_{b_jk}p_j.
\]

因此相對 native 的 resource-consumption multiplier 是

\[
\kappa_{bk}
=
\frac{W_{jk}}{g_jp_j}
=
\alpha_{bk}.
\]

這是目前最乾淨的「resource conversion」：**不把不同 GPU 型號換算成虛假的 scalar GPU-equivalent，而把 substitute cost 表達成增加的 GPU-time。**

這點也有研究上的理由。Gavel 所觀察的 accelerator performance 是 workload-dependent，必須用每個 job 在各 accelerator 上的 throughput 矩陣描述，並非只依硬體型號給一個全域換算比例。citeturn6view0turn8view0

## 三種模型的比較與假設分層

A、B、C 應如下理解。

| 模型 | 數學核心 | 額外資料需求 | 主要優點 | 主要風險 |
|---|---|---:|---|---|
| A Binary Compatibility | \(c_{bk}\in\{0,1\}\) | 低 | 清晰、可解釋、容易做 scenario | 若直接假設 \(P_{jk}=p_j\)，其實偷偷假設了等效能 |
| B Continuous Slowdown | \(P_{jk}=\alpha_{bk}p_j\) | 高 | 可以描述 queueing benefit 與 performance penalty 的 trade-off | \(\alpha\) 沒 benchmark 就不可識別 |
| C Capacity Reservation | foreign usage \(\le B_k\) | 低至中 | 保護 donor pool、政策解釋強 | 若用 hard partition 會浪費容量 |

### Binary compatibility

最純粹的 A 模型是

\[
x_{jk}\le c_{b_jk}.
\]

若要進行完整 scheduling，又設定

\[
P_{jk}=p_j
\]

給所有 compatible \(k\)，那麼其實隱含：

\[
\alpha_{bk}=1.
\]

因此論文中不能寫：

> Compatible GPU has the same performance.

比較好的寫法是：

> For the structural compatibility experiment, execution duration is provisionally held at the native duration, representing an optimistic benchmark-free reference scenario.

也就是把 A 視為**結構性上界／optimistic scenario**，而不是物理真相。

### Continuous slowdown

B 使用

\[
P_{jk}
=
\alpha_{bk}p_j.
\]

原生：

\[
\alpha_{b,n_b}=1.
\]

最保守的 benchmark-free 版本可以設定跨型號：

\[
\alpha_{bk}\ge1
\qquad k\neq n_b.
\]

這不是說所有 substitute GPU 真的比較慢，而是一個**單向保守假設**：

> 不允許 Q3 因為沒有數據，憑空聲稱另一型號更快。

此時 substitution 的價值完全來自「少排隊」，而不是「GPU 更強」。

這是一個很漂亮的論述。

假設 Q2 中 job \(j\) 等 native GPU 的開始時間是

\[
s_j^{N}.
\]

如果現在 substitute GPU 可以在

\[
s_j^{S}
\]

開始，那麼 substitute 使該 job 較早完成的條件是

\[
s_j^{S}+\alpha_{bk}p_j
<
s_j^{N}+p_j.
\]

因此：

\[
\boxed{
\alpha_{bk}
<
1+
\frac{s_j^{N}-s_j^{S}}{p_j}
}
\]

定義

\[
\alpha_{jk}^{\mathrm{crit}}
=
1+
\frac{s_j^{N}-s_j^{S}}{p_j}.
\]

這是 Q3 很值得使用的一個 **benchmark-free break-even threshold**。

例子不是要假設某個 GPU 是 \(1.3\times\) 慢，而是回答：

> 「這次跨型號配置最多可以慢多少，仍然值得？」

這個量完全可以由 Q2 的 waiting time 和 job duration 推出。

如果 native 要等很久，則

\[
\alpha^{crit}
\]

會較大，代表即使 substitute GPU 顯著較慢，仍可能縮短 JCT。

如果 native 幾乎不用等，

\[
\alpha^{crit}\approx1,
\]

跨型號的價值就非常有限。

這比胡亂引用一張外部 GPU benchmark 表更符合數學建模競賽。

而且這種敏感性處理與異構 scheduling 文獻的核心認知一致：同一 accelerator 對不同 workload 的相對性能並非固定，所以可靠模型應保留 workload-dependent performance，而不是只依 GPU 型號建立一個單一 global ranking。citeturn6view0turn9view0

### Capacity reservation

C 最好不要設計成「把 \(20\%\) GPU 永久鎖死給外來 job」。

應先區分 **hard reservation** 與 **soft reservation**。

若令

\[
B_k
\]

為 type \(k\) 中最多允許被 foreign jobs 占用的 GPU 數量，hard partition 寫成：

\[
\sum_{j:n_j=k}g_ju_{jk}(t)
\le C_k-B_k
\]

以及

\[
\sum_{j:n_j\neq k}g_ju_{jk}(t)
\le B_k.
\]

這代表 \(B_k\) GPU 專屬 foreign pool。

問題是：foreign demand 為 0 時，native job 仍不能使用該區域，會產生人工 idle capacity。

因此我不推薦。

更好的 **soft borrowing cap** 是：

\[
\boxed{
\sum_{j:n_j\neq k}
g_j u_{jk}(t)
\le B_k
\qquad\forall k,t
}
\]

並仍有整體 capacity constraint

\[
\sum_jg_ju_{jk}(t)
\le C_k.
\]

這代表：

> native jobs 可以使用整個 \(C_k\)；但 foreign jobs 最多只准借 \(B_k\)。

令

\[
R_k=C_k-B_k,
\]

則至少有 \(R_k\) 張 type \(k\) GPU 不會被 foreign jobs 占住。

這是我建議的 **donor GPU pool protection constraint**。

它的概念和成熟資源排程系統中的 borrowing/lending quota 非常接近：Kueue 允許不同 resource flavors 有自己的 nominal quota，並對 borrowing 與 lending 設定上限；其文件也明確以不同 GPU models 作為 flavors 的例子。citeturn6view2

但注意：

\[
R_k>0
\]

**不等於「native jobs 保證零等待」**。

它只保證 foreign jobs 不可能占滿整個 donor pool。若 native demand 本身大於 \(R_k\) 或 native jobs 互相競爭，依舊會排隊。

### A、B、C 真正的關係

因此三種模型最正確的比較不是

\[
A\quad\text{vs.}\quad B\quad\text{vs.}\quad C,
\]

而是：

\[
\boxed{
A=\text{feasibility layer},
\quad
B=\text{performance layer},
\quad
C=\text{governance layer}.
}
\]

推薦完整結構：

\[
c_{bk}
\rightarrow
x_{jk}
\rightarrow
\alpha_{bk}
\rightarrow
P_{jk}
\rightarrow
u_{jk}(t)
\rightarrow
B_k.
\]

換句話說：

\[
\boxed{\text{A+C 是主模型；B 疊在其上做敏感度。}}
\]

## 哪些假設可由資料支持，哪些必須是 scenario

在沒有看到你 Q1/Q2 原文的情況下，最嚴謹的做法是用「證據等級」寫進報告。

### 可以視為題面支持的條件

依你明示的題意，可直接採用：

\[
\text{heterogeneous GPU types};
\]

\[
\text{fixed native job demand};
\]

\[
\text{non-preemption};
\]

\[
\text{gang scheduling}.
\]

其中 Gang Scheduling 的 all-or-nothing 含義本身也符合現代 cluster scheduler 的正式定義。citeturn6view3

如果官方 dataset/Q1/Q2 已提供以下欄位，也應直接繼承：

\[
C_k,\quad
n_j,\quad
g_j,\quad
p_j,\quad
r_j.
\]

此外，**Q2 的 objective 應原封不動延伸到 Q3**。

若 Q2 是

\[
\min\sum_j(C_j-r_j),
\]

Q3 就繼續用 JCT。

若 Q2 是

\[
\min\sum_j(s_j-r_j),
\]

就繼續用 waiting time。

若 Q2 是 makespan，就繼續 makespan。

這比在第三問突然發明新 KPI 更容易向評委證明 Q3 是 Q2 的自然 extension。

### 必須標成 scenario assumption

除非 official data 明確提供，以下都不能寫成觀察事實：

\[
c_{bk}=1,\qquad k\neq n_b;
\]

\[
\alpha_{bk};
\]

\[
\rho_{bk};
\]

\[
B_k/C_k;
\]

「更新一代 GPU 一定可以跑舊 workload」；

「高階 GPU 一定較快」；

「兩張低階 GPU 等於一張高階 GPU」；

「不同 GPU 可以在同一 distributed gang 混用」。

尤其是 \(\alpha\)。Gavel 的研究模型之所以能真正做 performance-aware heterogeneous scheduling，是因為它取得每個 job 在不同 accelerators 上的 throughput；該研究還指出 performance 會隨 workload architecture 改變。citeturn6view0turn8view0 本題既然明確要求不能假設 benchmark 存在，就應把 \(\alpha\) 當 sensitivity parameter，而非 estimated parameter。

### 如何避免假設過強

最有效的方法不是「少寫幾個假設」，而是遵守四個原則。

第一是 **baseline nesting**。

Q2 native-only schedule 必須永遠是 Q3 的一個 feasible solution。形式上保留所有 native edge：

\[
c_{b,n_b}=1.
\]

任何 job 都可以選

\[
x_{j,n_j}=1.
\]

因此 Q3 不會逼 job 一定要 substitution。

第二是 **count preservation**：

\[
q_{jk}=g_j.
\]

不要沒有資料就改 gang size。

第三是 **homogeneous gang**：

\[
\sum_kx_{jk}=1.
\]

一個 job 不混 GPU types。

第四是 **scenario envelope rather than point claim**。

不要說

\[
\alpha=1.4
\]

「因為某 GPU 約慢 40%」。

而是說：

\[
\alpha\in\{1,\alpha_2,\ldots\}
\]

代表 hypothetical slowdown scenarios，並利用

\[
\alpha^{crit}
\]

顯示結論何時翻轉。

同理 reservation 不要宣稱

\[
B_k=0.3C_k
\]

是最佳真實比例；應畫出

\[
B_k=0,\ldots,C_k
\]

或有限 grid 下的 trade-off/Pareto curve。

如果 Q1/Q2 已經有 native GPU utilization trace，則可以更進一步定義資料驅動 reserve：

\[
R_k(\beta)
=
Q_\beta
\left(
L_k^{Q2}(t)
\right),
\]

其中

\[
L_k^{Q2}(t)
\]

是 Q2 baseline 中 type \(k\) native load，

\[
Q_\beta
\]

是 empirical quantile。

這時 native demand distribution 是 data-derived，但

\[
\beta
\]

仍然是 policy scenario，不要把它包裝成客觀常數。

## Donor pool 保護與沒有 benchmark 時的嚴格處理

### 第一層：容量式保護

主模型使用：

\[
\sum_{j:n_j\neq k}
g_j u_{jk}(t)
\le B_k.
\]

或者寫為：

\[
\sum_{j:n_j\neq k}
g_j u_{jk}(t)
\le C_k-R_k.
\]

這是最容易解釋、最不依賴 benchmark 的 constraint。

從 scheduler governance 的角度看，這就是「最多借多少 flavor quota」；Kueue 的正式模型同樣區分 GPU resource flavors，並提供 borrowing limit 與 lending limit 控制共享程度。citeturn6view2

### 第二層：績效式保護

更創新的版本可以直接保護 Q2 baseline 的 native users，而不是保護抽象 capacity。

令 type \(k\) 的 native jobs 為

\[
\mathcal J_k^N
=
\{j:n_j=k\}.
\]

定義 Q2 native-only 平均 JCT：

\[
\overline{\operatorname{JCT}}_k^{(2)}
=
\frac{1}{|\mathcal J_k^N|}
\sum_{j\in\mathcal J_k^N}
(C_j^{(2)}-r_j).
\]

Q3 要求：

\[
\boxed{
\overline{\operatorname{JCT}}_k^{(3)}
\le
(1+\epsilon_k)
\overline{\operatorname{JCT}}_k^{(2)}
}
\]

其中

\[
\epsilon_k\ge0
\]

為容許的 donor-native degradation。

也可以改用 waiting time：

\[
\overline W_k^{(3)}
\le
\overline W_k^{(2)}+\Delta_k.
\]

這種 constraint 的解釋非常直接：

> 我們允許 type \(k\) 把空閒 capacity 借給其他 GPU-native jobs，但不允許其原生使用者平均 JCT 惡化超過 \(\epsilon_k\)。

這其實比「永遠 reserve 30%」更有意義。

但它比 capacity cap 複雜，所以我會把它放在**高創新版本**，而不是最小模型。

### 無 benchmark 的 slowdown 實驗

不要估 \(\alpha\)，改為求「臨界 \(\alpha\)」。

對一個 candidate substitution：

\[
\alpha_{jk}^{crit}
=
1+
\frac{s_j^N-s_j^S}{p_j}.
\]

然後把 substitution 分成三類：

\[
\alpha_{bk}
<
\alpha_{jk}^{crit}
\quad\Rightarrow\quad
\text{job-level substitution beneficial},
\]

\[
\alpha_{bk}
=
\alpha_{jk}^{crit}
\quad\Rightarrow\quad
\text{break-even},
\]

\[
\alpha_{bk}
>
\alpha_{jk}^{crit}
\quad\Rightarrow\quad
\text{native execution earlier completion}.
\]

例如不要報：

> GPU-B 比 GPU-A 慢 30%。

而報：

> 對這組 congested jobs，只要 substitute slowdown 低於 \(1.62\times\)，跨型號仍能降低 completion time。

後者是由 scheduling data 推出的 threshold，不需要硬體 benchmark。

系統層面仍需重新排程驗證，因為一個 job 的 substitution 會改變其他 jobs 的 resource contention；所以 \(\alpha^{crit}\) 最適合做**screening / interpretation tool**，不是完整 global optimality criterion。

## 可驗證實驗與六天競賽策略

Q3 最重要的不是做一個極複雜模型，而是建立一組「模型若正確就一定應該通過」的 sanity tests。

假設沿用 Q2 的 minimization objective：

\[
F.
\]

### Baseline recovery

設定所有 foreign borrowing 為零：

\[
B_k=0
\qquad\forall k.
\]

則任何跨型號 assignment 都被阻止，Q3 應完全退化回 Q2：

\[
\boxed{
F_{Q3}(B=0)=F_{Q2}.
}
\]

如果沒有回到同樣結果，表示 Q3 不只是「擴展 Q2」，而是意外改動了其他設定。

另一種 recovery test：

\[
c_{bk}
=
\mathbf 1(k=n_b).
\]

同樣必須得到 Q2。

### Feasible-set monotonicity

若新增 compatibility edges，而其他設定不變，native-only schedule 仍可行，因此 minimization optimum 不應惡化：

\[
E_1\subseteq E_2
\quad\Longrightarrow\quad
F(E_2)\le F(E_1).
\]

同理：

\[
B_k^{(1)}\le B_k^{(2)}
\]

表示 foreign borrowing cap 放寬，所以

\[
F(B^{(2)})
\le
F(B^{(1)})
\]

在沒有額外 substitution penalty 的情況下應成立。

這是很強的 implementation/model verification property。

### Benchmark-free 上下界

建立兩個極端情境。

Native-only baseline：

\[
c_{bk}=0
\quad k\neq n_b.
\]

得到

\[
F_N.
\]

Optimistic full-substitution bound：

\[
c_{bk}=1\quad\forall b,k,
\]

\[
\alpha_{bk}=1,
\]

\[
B_k=C_k.
\]

得到

\[
F_O.
\]

則對任何保留 native option、\(\alpha\ge1\) 的合理中間模型，通常有：

\[
\boxed{
F_O
\le
F_{Q3}
\le
F_N
}
\]

對 minimization objective 而言。

這個 inequality 本身就很適合放進論文：即使沒有 benchmark，也可以給出**理論 improvement envelope**。

### Slowdown sensitivity

對 \(\alpha\) 做 scenario sweep。

最有資訊量的 x 軸不是隨機 GPU benchmark，而是：

\[
\alpha/\alpha^{crit}.
\]

當

\[
\alpha/\alpha^{crit}<1
\]

是 beneficial region；

等於 1 為 break-even；

大於 1 為不利區。

系統輸出可以觀察：

\[
F(\alpha),
\]

平均 JCT，

native waiting time，

cross-type jobs 比例，

foreign GPU-time，

donor-native degradation。

Gavel 等研究證實 accelerator heterogeneity 對 scheduling objective 確實重要，但其模型依賴 workload-specific throughput information；因此在本題沒有 throughput measurements 時，敏感度分析比「校準單一 \(\alpha\)」更科學。citeturn6view0turn8view0

### Reservation sensitivity

對每種 GPU \(k\) 測試：

\[
B_k=0,\ldots,C_k
\]

或者以比例

\[
\beta_k=B_k/C_k
\]

表示。

畫兩個量的 Pareto curve：

\[
\text{system improvement}
\]

對

\[
\text{donor-native degradation}.
\]

理想形狀是前期增加 \(B_k\) 可以迅速改善 overloaded GPU queue，而 donor harm 還很小；後期繼續增加 borrowing 只有小幅 system gain，卻使 donor users 惡化。

這可以自然產生「推薦 operating point」，而不是武斷宣告 20% 或 30% reserve 最佳。

### Stress-case 驗證

至少應人工構造三個 conceptual case。

第一個是：

\[
\text{native A heavily congested},
\qquad
\text{B idle}.
\]

此時若

\[
c_{AB}=1
\]

且 slowdown 不過大，跨型號應有明顯價值。

第二個是：

\[
\text{A and B both saturated}.
\]

這時 substitution 不應創造魔法般的 improvement。

第三個是：

\[
\text{B currently idle but has imminent native demand}.
\]

這個 case 專門驗證 donor protection。由於 job **不可搶占**，一旦 foreign job 開始占用 B，就不能在 native B job 抵達時把它趕走。因此只根據「現在 idle」就借出所有 donor GPU 是危險的；這也正是 static/soft borrowing cap 在本題中有價值的原因。現實資源管理框架也會透過 quota borrowing/lending controls 限制這種共享。citeturn6view2

### 六天競賽的推薦排序

如果時間有限，我會把研究工作量依序投入：

\[
\text{Q2 baseline reproduction}
\rightarrow
\text{A compatibility}
\rightarrow
\text{C soft protection}
\rightarrow
\text{B sensitivity}
\rightarrow
\text{robust/innovation extension}.
\]

不要倒過來先做複雜的 performance prediction。

理由非常實際：沒有 benchmark 時，越複雜的 performance model，需要的無法驗證參數反而越多；異構 scheduling 的學術文獻有 throughput matrix 是因為它們實際量測或估計 performance，而不是因為只知道 GPU 名稱。citeturn8view0turn9view0

## 最終推薦方案

### Q3 最小可行研究模型

我建議把 Q3 的正式最小模型寫成：

\[
\boxed{
\text{Compatibility-constrained,
non-preemptive,
type-pure gang scheduling
with bounded cross-type borrowing}
}
\]

參數：

\[
C_k,n_j,g_j,p_j,r_j
\]

全部沿用 Q1/Q2。

Scenario 參數：

\[
c_{bk},
\quad
\alpha_{bk},
\quad
B_k.
\]

物理 GPU 數量不換算：

\[
q_{jk}=g_j.
\]

Assignment：

\[
\sum_kx_{jk}=1,
\]

\[
x_{jk}\le c_{b_jk}.
\]

Execution：

\[
P_{jk}=\alpha_{b_jk}p_j,
\]

\[
C_j=s_j+\sum_kP_{jk}x_{jk},
\]

\[
s_j\ge r_j.
\]

Capacity：

\[
\sum_jg_ju_{jk}(t)\le C_k.
\]

Donor protection：

\[
\boxed{
\sum_{j:n_j\neq k}
g_ju_{jk}(t)
\le B_k.
}
\]

Objective：

\[
\boxed{
\min F_{Q2}
}
\]

亦即**直接使用第二問的 objective**。

如果有多個同樣好的解，再用 lexicographic tie-break：

\[
\min
\sum_j\sum_{k\neq n_j}x_{jk}.
\]

也就是在 Q2 objective 相同時，選擇跨型號次數更少的 schedule。

如此可以避免模型為了極小、無意義的 objective improvement 而過度 migration/substitution。

### 低風險版本

論文主體使用：

\[
\boxed{A+C}
\]

即 Binary Compatibility + Soft Borrowing Cap。

所有 job：

\[
q_{jk}=g_j.
\]

禁止 mixed-type gangs。

禁止 preemption。

Compatibility 只做少量清楚的 scenario graphs。

例如：

\[
G_0=\text{native only},
\]

\[
G_1=\text{restricted substitution},
\]

\[
G_2=\text{more permissive substitution}.
\]

但不聲稱哪一張 graph 是「真實 GPU compatibility」。

主結果比較：

\[
F(G,B)
\]

相對 Q2 baseline 的改善。

Slowdown 不放進主模型校準，只在 robustness section 測：

\[
\alpha\ge1.
\]

最值得寫的一句結論會是：

> Cross-type scheduling is beneficial not because substitute GPUs are assumed faster, but because otherwise idle compatible resources can offset native-queue delay.

這樣幾乎完全避免 benchmark 爭議。

C 採

\[
\text{foreign occupancy}\le B_k
\]

而不是 hard carve-out。這與正式資源管理系統的 flavor quota、borrowing/lending 思想有清楚對應。citeturn6view2

**這是我認為六天競賽最合適的版本。**

### 高創新版本

建立 **Robust Break-even Substitution Model**。

第一步，不估計 \(\alpha\)，而由 Q2 算每個 candidate pair 的

\[
\alpha_{jk}^{crit}
=
1+\frac{s_j^N-s_j^S}{p_j}.
\]

第二步，將 uncertain slowdown 寫成 scenario set：

\[
\alpha_{bk}\in\mathcal A_{bk}.
\]

第三步，不只用 resource cap，而加入 donor-native service guarantee：

\[
\overline{\operatorname{JCT}}_k^{(3)}
\le
(1+\epsilon_k)
\overline{\operatorname{JCT}}_k^{(2)}.
\]

最後產生三維 trade-off：

\[
\text{system JCT}
\quad\text{vs}\quad
\text{substitution tolerance}
\quad\text{vs}\quad
\text{donor degradation}.
\]

可以定義 robust pair：

\[
\max\mathcal A_{bk}
<
\alpha_{jk}^{crit}.
\]

這表示在全部 slowdown scenarios 下，該 substitution 仍能比 native waiting 更早完成。

反之若：

\[
\min\mathcal A_{bk}
>
\alpha_{jk}^{crit},
\]

則這個 substitution 在所有考察 scenarios 下都不值得。

這樣你得到的是：

> 「跨型號策略能承受多大的性能不確定性？」

而不是：

> 「我們猜 GPU-B 是 GPU-A 的 0.73 倍。」

從建模競賽的論證品質來看，前者高很多。

### 不推薦方向

**不推薦用 peak FLOPS、CUDA cores、顯存容量等單一規格直接計算 GPU-equivalent。** 異構 accelerator 的 workload performance 本來就是 model-dependent；Gavel 類研究使用的是 job-specific throughput matrix，而不是以一個硬體規格比例當所有工作負載的 universal conversion factor。citeturn6view0turn8view0

**不推薦直接設定「A100 比 V100 快 \(x\%\)」之類外部 benchmark 數字。** 題目沒有 benchmark，這類數字既不屬於 official data，也會把硬體測試環境、framework、model architecture、batch size 等條件偷偷帶入模型。異構研究本身即顯示不同 workloads 在不同 accelerator 上的相對 performance 並不一致。citeturn9view0

**不推薦 physical GPU-count conversion**

\[
q_{jk}
=
\left\lceil
\rho_{bk}g_j
\right\rceil
\]

作為主模型。只要

\[
\rho_{bk}\neq1,
\]

你就在假設 distributed job 可以改變 worker count，這與「原生作業需求固定」至少存在強烈張力。除非官方題目明確說 jobs 是 elastic/malleable，否則不要使用。

**不推薦 mixed-GPU Gang**

\[
4\times A+4\times B.
\]

這需要額外的同步、straggler、通信/topology performance model，而題目沒有提供辨識這些參數的資料。已有異構 scheduling 研究也顯示 distributed-job performance 會受 accelerator type 與 placement 共同影響。citeturn8view0

**不推薦 hard reservation**：

\[
native\le C_k-B_k,\qquad foreign\le B_k.
\]

它會在 foreign demand 不足時強制浪費 GPU。更好的 constraint 是：

\[
foreign\le B_k,
\qquad
native+foreign\le C_k.
\]

也就是 native 能使用所有剩餘資源，foreign 只能有限 borrowing。

**不推薦「只要 donor 現在 idle 就全部借出」。** 在不可搶占條件下，一個長 foreign job 一旦開始，後來抵達的 donor-native job 無法 reclaim GPU；因此 donor protection 必須在 admission 時就考慮，而不能依靠未提供的 preemption 機制。

整體而言，第三問最穩健的論文敘事應是：

\[
\boxed{
\text{Q2 native-only scheduling}
}
\]

作為 baseline，

\[
\Downarrow
\]

新增一張

\[
\boxed{\text{job-type--GPU-type compatibility graph}}
\]

決定哪些 substitution 是 admissible，

\[
\Downarrow
\]

保持

\[
\boxed{q_{jk}=g_j}
\]

避免發明 GPU 數量換算，

\[
\Downarrow
\]

以

\[
\boxed{P_{jk}=\alpha_{bk}p_j}
\]

表示未知 performance effect，但把 \(\alpha\) 當 scenario parameter 而非 benchmark estimate，

\[
\Downarrow
\]

以

\[
\boxed{
\sum_{j:n_j\neq k}
g_ju_{jk}(t)\le B_k
}
\]

保護 donor GPU pool，

\[
\Downarrow
\]

最後用

\[
\boxed{
\alpha_{jk}^{crit}
=
1+
\frac{s_j^N-s_j^S}{p_j}
}
\]

回答真正值得研究的問題：

> **一個 job 最多可以在 substitute GPU 上慢多少，跨型號調配仍然值得；又能借出多少 donor capacity，而不傷害原生 workload？**

這個架構在沒有任何 GPU benchmark 的前提下仍然完整、可驗證，而且 Q3 對 Q2 是嚴格的 nested extension；相比直接猜 GPU 性能比，它更適合作為六天建模競賽的主線。