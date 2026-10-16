# Q3-S3：結論凍結、論文正文與可重現證據

本交付只對已完成的 Q3 S1/S2 結果做後處理與出版整理；`new_scheduling_runs=0`。沒有新增排程、模型、原型移植或大型實驗。第一輪 M1 在本包統一稱為 **S0**：60 台專屬完整 A100、10% SHA-256 固定分流、\(\sigma=1\)。

## 凍結的主張

- **固定分流收益（S0 對 M0）**：FCFS 的原始 A10 平均等待由 900.128570 降至 587.875069 小時（34.7%）；SJF-HOL 由 32.906454 降至 20.533731 小時（37.6%）。全體平均 JCT 分別為 523.961182→368.910053 與 93.352565→87.208824 小時；90 天全體完成數分別為 165,107→181,112 與 217,570→217,814。
- **原生池代價**：S0 在這條 trace 的兩種政策中，native A100 相對 M0／S0 的額外等待、P99、Max 與原零等待作業新增延遲均為零；這是 trace 結果，不是服務保證。
- **分流比例不是單調收益**：60 台 donor 下，FCFS 的 A10 平均等待在 5%/10%/20% 為 702.551/587.875/1010.136 小時；SJF-HOL 為 25.328/20.534/22.058 小時。20% 不能當成 10% 的自動改進。
- **容量取捨**：10% 分流下，30/60/90 台 donor 的 FCFS A10 平均等待為 916.407/587.875/539.109 小時，SJF-HOL 為 25.565/20.534/19.214 小時。90 台相對 S0 使 5,735 個 FCFS、2,150 個 SJF-HOL native A100 作業等待變長；平均新增等待相對 M0 為 0.077111 與 0.018492 小時，P99 為 2.074778 與 0.405622 小時，Max 為 6.185556 與 7.971944 小時。
- **\(\sigma=2\) 不是免費加速**：相對 M0，FCFS A10 平均 JCT 999.898326→831.455545 小時、全體平均 JCT 523.961182→440.320027 小時、90 天完成 165,107→177,166；SJF-HOL A10 平均 JCT 132.676210→134.809736 小時、全體平均 JCT 93.352565→94.411979 小時、90 天完成 217,570→217,521。SJF-HOL 的等待仍可下降，但完成時間變差；相對 S0 的 A10 平均 finish delta 是 +14.506248 小時（FCFS +143.810720 小時）。

上述數字都按原始 job ID 配對，等待/JCT 以完整排空計算，90 天完成數使用 \(H=7,776,000\) 秒。不同情景的等待降幅不能被宣稱為唯一因果貢獻比例。

## 文件與來源

- 英文論文正文：[q3_section.tex](../../problems/2026_gpu_scheduling/paper/q3_section.tex)
- 繁中正文：[q3_section_zh.html](../../problems/2026_gpu_scheduling/paper/q3_section_zh.html)
- 同一數值來源：[paper_ready_metrics.json](paper_ready_metrics.json)、[paper_ready_metrics.csv](paper_ready_metrics.csv)
- 主表：[q3_s3_main_table.tex](q3_s3_main_table.tex)
- 主張到來源欄位：[q3_claim_sources.json](q3_claim_sources.json)
- 生成與靜態檢查：[publication_checks.json](publication_checks.json)
- donor trade-off 圖：[q3_donor_capacity_wait_tradeoff.png](q3_donor_capacity_wait_tradeoff.png)

生成器只讀取 `results/20261015-b-q3-fixed-split-c9e8f1a2/metrics.json` 與 `results/20261015-b-q3-s2-fixed-split-v1/sensitivity_metrics.json`，命令為：

```text
env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH .venv/bin/python problems/2026_gpu_scheduling/experiments/make_q3_publication.py --out results/20261016-b-q3-s3-publication-9ac1d7f2
```

既有 S1/S2 的物理逐節點回放、paired comparison、路由核對與獨立驗證均保持其原始 `PASS` 證據；本輪不改寫那些歷史結果。LaTeX 編譯器在本環境不可用，因此 `publication_checks.json` 將編譯狀態記為 `NOT_RUN`，已完成靜態段落與資料一致性檢查。大型 S1/S2 ZIP 仍是本機交付物，跨機共享狀態為 `BLOCKED`，不能當成已上傳證據。

## 條件性結論與限制

60 台／10% 是在本 trace 上兼顧 A10 改善與 native 零新增等待的已測候選，不是全域最佳或安全容量上界。相容性與 \(\sigma\) 是情景假設，沒有 A10/A100 實測矩陣；allocation 是請求占用，不是利用率或可互換的 GPU-hours。沒有新增實體 GPU，也沒有動態借用、MIG、遷移、拍賣、RL 或 Q2×Q3 聯合排程。後續若要做 operating-point 判定，應先宣告公平性門檻，再以 S1–S5 證據做小型門檻分析。
