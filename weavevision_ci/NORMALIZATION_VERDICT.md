# WeaveVision v0.7.0a1 Domain Normalization Verdict

Verdict: **PASS_WITH_RESTRICTIONS**

| Method | External AUROC | External FNR | External FPR | P95 ms | Gate |
|---|---:|---:|---:|---:|---|
| M0 raw source-frozen | 0.1478 | 0.0000 | 1.0000 | 125.008 | FAIL |
| M1 robust appearance | 0.5406 | 0.8750 | 0.0357 | 127.063 | FAIL |
| M2 self-similarity | 0.3219 | 0.0000 | 1.0000 | 194.864 | FAIL |
| M3 pattern-conditioned raw | 0.4228 | 0.7500 | 0.2500 | 125.053 | FAIL |

No method met AUROC >= 0.80, FNR <= 0.20, FPR <= 0.20 and P95 latency <= 250 ms together.

Next gate: separate domain compatibility from residual anomaly and abstain on domain mismatch.

Claim boundary: `OPEN_SOURCE_TEXTILE_PROXY_ONLY`; not company validation.
