# Complete fixed-cohort comparison / 固定原始群體主表

Hours unless count or job-hours is specified. Negative finish delta is earlier. M0 is one shared no-substitution schedule per policy (sigma N/A); its two direct R0 reverse comparisons are in paired.csv, not filled with zeros here. Native invariance means both timing and placement against the same-sigma 60-node partition. M0 has 432 native nodes, so this partition comparison is N/A.

### FCFS, A10 (n=111284)

| option | sigma | mean_wait_hours | mean_jct_hours | completed_at_horizon | vs_M0_mean_finish_delta_hours | vs_R0_mean_finish_delta_hours | vs_M0_harmed_jobs | vs_R0_harmed_jobs | vs_M0_positive_finish_delay_job_hours | vs_R0_positive_finish_delay_job_hours | p95_wait_hours | p99_wait_hours | max_wait_hours | native_mean_wait_delta_vs_M0_hours | native_invariant_vs_R0 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M0 | N/A | 900.128570 | 999.898326 | 54531 | 0.000000 | N/A | 0 | N/A | 0.000000 | N/A | 1408.477750 | 1419.616300 | 1423.253889 | 0.000000 | N/A |
| R0 | 1 | 587.875069 | 687.644825 | 70536 | -312.253500 | 0.000000 | 0 | 0 | 0.000000 | 0.000000 | 966.761181 | 987.569214 | 1184.843333 | 0.000000 | PASS |
| R0 | 2 | 721.751641 | 831.455545 | 66590 | -168.442781 | 0.000000 | 9292 | 0 | 11464975.865833 | 0.000000 | 2292.732681 | 2885.706778 | 3868.635833 | 0.000000 | PASS |
| R-shape | 1 | 656.355518 | 756.125275 | 66936 | -243.773051 | 68.480449 | 0 | 96504 | 0.000000 | 12795303.141667 | 1139.419292 | 1161.236206 | 1164.131944 | 0.000000 | PASS |
| R-shape | 2 | 656.355518 | 761.667687 | 66748 | -238.230639 | -69.787858 | 485 | 96101 | 307555.286667 | 12678622.744167 | 1139.419292 | 1161.236206 | 1164.131944 | 0.000000 | PASS |

### FCFS, ALL (n=224112)

| option | sigma | mean_wait_hours | mean_jct_hours | completed_at_horizon | vs_M0_mean_finish_delta_hours | vs_R0_mean_finish_delta_hours | vs_M0_harmed_jobs | vs_R0_harmed_jobs | vs_M0_positive_finish_delay_job_hours | vs_R0_positive_finish_delay_job_hours | p95_wait_hours | p99_wait_hours | max_wait_hours | native_mean_wait_delta_vs_M0_hours | native_invariant_vs_R0 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M0 | N/A | 446.970506 | 523.961182 | 165107 | 0.000000 | N/A | 0 | N/A | 0.000000 | N/A | 1356.501111 | 1416.304375 | 1423.253889 | 0.000000 | N/A |
| R0 | 1 | 291.919377 | 368.910053 | 181112 | -155.051129 | 0.000000 | 0 | 0 | 0.000000 | 0.000000 | 890.391847 | 985.319044 | 1184.843333 | 0.000000 | PASS |
| R0 | 2 | 358.396498 | 440.320027 | 177166 | -83.641154 | 0.000000 | 9292 | 0 | 11464975.865833 | 0.000000 | 972.445958 | 2837.571322 | 3868.635833 | 0.000000 | PASS |
| R-shape | 1 | 325.923707 | 402.914382 | 177512 | -121.046799 | 34.004330 | 0 | 96504 | 0.000000 | 12795303.141667 | 1065.733097 | 1154.281297 | 1164.131944 | 0.000000 | PASS |
| R-shape | 2 | 325.923707 | 405.666497 | 177324 | -118.294685 | -34.653530 | 485 | 96101 | 307555.286667 | 12678622.744167 | 1065.733097 | 1154.281297 | 1164.131944 | 0.000000 | PASS |

### SJF-HOL, A10 (n=111284)

| option | sigma | mean_wait_hours | mean_jct_hours | completed_at_horizon | vs_M0_mean_finish_delta_hours | vs_R0_mean_finish_delta_hours | vs_M0_harmed_jobs | vs_R0_harmed_jobs | vs_M0_positive_finish_delay_job_hours | vs_R0_positive_finish_delay_job_hours | p95_wait_hours | p99_wait_hours | max_wait_hours | native_mean_wait_delta_vs_M0_hours | native_invariant_vs_R0 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M0 | N/A | 32.906454 | 132.676210 | 107002 | 0.000000 | N/A | 0 | N/A | 0.000000 | N/A | 11.086875 | 1542.181042 | 3017.288056 | 0.000000 | N/A |
| R0 | 1 | 20.533731 | 120.303488 | 107246 | -12.372723 | 0.000000 | 49772 | 0 | 68183.182500 | 0.000000 | 12.690806 | 639.531831 | 2781.036667 | 0.000000 | PASS |
| R0 | 2 | 25.105831 | 134.809736 | 106953 | 2.133525 | 0.000000 | 56422 | 0 | 1406278.767778 | 0.000000 | 12.125194 | 1058.270331 | 4158.803611 | 0.000000 | PASS |
| R-shape | 1 | 24.358604 | 124.128360 | 107233 | -8.547850 | 3.824872 | 46803 | 47819 | 16051.659167 | 559301.142222 | 7.302444 | 1044.979175 | 2812.328056 | 0.000000 | PASS |
| R-shape | 2 | 24.358604 | 129.670773 | 107045 | -3.005438 | -5.138963 | 55465 | 47641 | 423048.517778 | 485546.711944 | 7.302444 | 1044.979175 | 2812.328056 | 0.000000 | PASS |

### SJF-HOL, ALL (n=224112)

| option | sigma | mean_wait_hours | mean_jct_hours | completed_at_horizon | vs_M0_mean_finish_delta_hours | vs_R0_mean_finish_delta_hours | vs_M0_harmed_jobs | vs_R0_harmed_jobs | vs_M0_positive_finish_delay_job_hours | vs_R0_positive_finish_delay_job_hours | p95_wait_hours | p99_wait_hours | max_wait_hours | native_mean_wait_delta_vs_M0_hours | native_invariant_vs_R0 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M0 | N/A | 16.361890 | 93.352565 | 217570 | 0.000000 | N/A | 0 | N/A | 0.000000 | N/A | 0.688583 | 363.347567 | 3017.288056 | 0.000000 | N/A |
| R0 | 1 | 10.218149 | 87.208824 | 217814 | -6.143741 | 0.000000 | 49772 | 0 | 68183.182500 | 0.000000 | 1.110556 | 124.253261 | 2781.036667 | 0.000000 | PASS |
| R0 | 2 | 12.488449 | 94.411979 | 217521 | 1.059413 | 0.000000 | 56422 | 0 | 1406278.767778 | 0.000000 | 1.136667 | 167.242447 | 4158.803611 | 0.000000 | PASS |
| R-shape | 1 | 12.117409 | 89.108085 | 217801 | -4.244480 | 1.899261 | 46803 | 47819 | 16051.659167 | 559301.142222 | 0.596236 | 166.585947 | 2812.328056 | 0.000000 | PASS |
| R-shape | 2 | 12.117409 | 91.860199 | 217613 | -1.492366 | -2.551779 | 55465 | 47641 | 423048.517778 | 485546.711944 | 0.596236 | 166.585947 | 2812.328056 | 0.000000 | PASS |
