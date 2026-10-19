# Paper Content R1 delivery

This directory records read-only post-processing and the publication mapping for the new paper candidate. It does not contain a scheduler rerun.

- `paper_content_mapping.md`: official question -> model/algorithm -> evidence -> visible chapter/figure mapping.
- `input_comparison.json`: byte and parsed-field comparison of the formal-run job CSV (`ef14d696...`) and the available historical-hash CSV (`735bc06c...`).
- `r1_metrics.json`: compact values used for the six-pool table, Q2 decomposition, GS1 comparison, Q3 allocation denominator check, and Q3 main table.
- `build_provenance.json`: generated source/PDF hashes and build checks.

The full formal input hashes are retained in the repository source index. Large timing and placement ledgers remain in their existing evidence locations and are not copied into this paper package.
