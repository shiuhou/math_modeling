# Publication acceptance and prior-check errata

The old R2 PDF and its acceptance table, and the eight-page correctness-patch PDF, are unchanged. Their old PASS labels are not the basis for this delivery.

| Prior claim | Correct interpretation and current evidence | Final PDF |
|---|---|---|
| Old A3: C0/ALL source accepted despite stale Table 5 | C0 all JCT is 93.33387935124699 h (display 93.334); all completions 217,578, identical to the six-pool PDF sum. All five rows are extracted and compared by explicit source field. | Tables 2, 5(a), pp. 3, 5 |
| Old E1: mixed A100 denominators accepted | Partition-own rates and 3456-GPU contributions are distinct; every displayed rate is compared with integer saved-schedule occupancy and the 2976/480 weighted identity. | p. 6 |
| Old F1 / summary: Shape-filtered wins at both speeds | Under both policies Hash-10% wins A10 mean JCT at sigma1, Shape-filtered at sigma2; Shape-filtered wins the two-point maximum comparison separately. Exact prose and actual printed numeric comparisons are checked. | pp. 1, 6 |
| Earlier font PASS did not measure ordinary embedded labels | Final ordinary text, tables, headers/footers and plot labels are measured at >=11 actual PDF points; script exceptions are individually listed. | all 8 pages |

Current final checks: 104 actual-PDF checks PASS; 8 A4 pages; final Poppler renders match the pages visually inspected; no clipped Figure 3 label remains. Actual comparison values, source fields and page numbers are in pdf_numeric_checks.json. Team human review is NOT_RUN.

The first standalone smoke exposed an unnecessary dependency on a historical Git-based CLI test. The final documented test selection contains the unchanged standalone core tests, and tests the portable reproduction CLI separately on synthetic data. No full trace or historical replay was run.

Follow-up requested by the team: the abstract now states about 45% of A10 jobs finish later in Hash-10%, sigma=1 (49,772/111,284 = 44.7252075770%); the internal SJF-HOL alias sentence is removed. The exact user-supplied AI disclosure is on p. 8. All eight final pages were visually inspected; pp. 2/4/5/6/7 are pixel-identical to the preceding accepted renders. The preceding artifact pair and all its records are preserved under history/a8a0b92. No scheduler or historical replay was called in this follow-up.

Windows code-package correction: the preceding ZIP failed the CRLF evidence fixture and the missing-resource smoke fixture. The corrected ZIP passes both, all 31 small tests and three synthetic CLI cases (5/5/2 jobs). Changing completion count 217,578 to 217,579 still fails the evidence check, as required. Only CRLF/LF is normalized; optional memory telemetry is null when resource is unavailable. This is Linux failure-mode verification; native Windows is NOT_RUN. Exact before/after exits and logs are in windows_compatibility/. Scheduling core, formal evidence, generated TeX/figures and the report PDF are byte-identical. No full-trace run or historical replay. Prior ZIP and related records are preserved under history/216dd3c/.
