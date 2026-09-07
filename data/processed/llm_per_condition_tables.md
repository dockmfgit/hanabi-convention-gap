# LLM corpus: per-condition convention gaps (joint posterior)

Point estimates and 95% play-level bootstrap CIs (B=2,000, per-cell seed 42)
from `llm_joint_posteriors.csv`; the per-card approximation value is shown
for comparison. Games per condition: 50 unless †-flagged as a partial run
(45 for GPT-5.4-mini+CoT × Intentional; 8 for Qwen3.6-A3B+CoT × IGGI and
× Intentional; see `llm_corpus_manifest.md`). Canonical panel CIs quoted in
the paper's Figure A7 cells come from the executed notebook's sequential
bootstrap stream and can differ from these per-cell CIs in the last digit.

## LLM-side (the LLM's own plays)

| LLM config | Partner | n | Gap joint (pp) | 95% CI | Gap per-card (pp) |
|---|---|---|---|---|---|
| GPT-5.4 | Flawed | 87 | +0.56 | [-1.09, +2.78] | +0.56 |
| GPT-5.4 | Full | 158 | +1.31 | [-0.02, +2.96] | +1.31 |
| GPT-5.4 | IGGI | 345 | -0.06 | [-0.35, +0.15] | -0.06 |
| GPT-5.4 | Intentional | 178 | +0.05 | [-0.34, +0.44] | +0.33 |
| GPT-5.4 | Internal | 340 | +0.12 | [-0.52, +0.68] | +0.11 |
| GPT-5.4 | Outer | 227 | -0.26 | [-1.35, +0.72] | -0.26 |
| GPT-5.4 | Piers | 323 | -0.73 | [-1.76, +0.23] | -0.69 |
| GPT-5.4 | Simple | 341 | +0.41 | [+0.00, +0.99] | +0.41 |
| GPT-5.4 | VdB | 290 | +0.00 | [-0.34, +0.34] | +0.00 |
| GPT-5.4-mini | Flawed | 172 | -1.30 | [-3.53, +1.11] | -1.26 |
| GPT-5.4-mini+CoT | Flawed | 123 | -0.86 | [-3.05, +1.10] | -0.86 |
| GPT-5.4-mini | Full | 190 | -1.44 | [-4.46, +1.69] | -1.33 |
| GPT-5.4-mini+CoT | Full | 171 | -0.24 | [-1.16, +0.76] | -0.20 |
| GPT-5.4-mini | IGGI | 323 | -0.94 | [-1.55, -0.40] | -0.97 |
| GPT-5.4-mini+CoT | IGGI | 378 | +0.30 | [-0.61, +1.30] | +0.29 |
| GPT-5.4-mini | Intentional | 194 | -1.58 | [-3.66, +0.71] | -1.50 |
| GPT-5.4-mini+CoT | Intentional† | 203 | +0.96 | [-0.61, +2.63] | +0.95 |
| GPT-5.4-mini | Internal | 287 | -0.58 | [-1.24, -0.10] | -0.61 |
| GPT-5.4-mini+CoT | Internal | 343 | -0.64 | [-1.53, +0.11] | -0.61 |
| GPT-5.4-mini | Outer | 276 | -1.23 | [-3.06, +0.71] | -1.42 |
| GPT-5.4-mini+CoT | Outer | 238 | +0.14 | [-1.52, +1.78] | +0.14 |
| GPT-5.4-mini | Piers | 250 | -1.13 | [-2.25, -0.14] | -1.16 |
| GPT-5.4-mini+CoT | Piers | 306 | +0.29 | [-0.48, +1.15] | +0.38 |
| GPT-5.4-mini | Simple | 344 | -0.15 | [-0.50, +0.29] | -0.16 |
| GPT-5.4-mini+CoT | Simple | 389 | -0.45 | [-0.91, -0.09] | -0.45 |
| GPT-5.4-mini | VdB | 335 | -1.18 | [-2.33, +0.08] | -1.12 |
| GPT-5.4-mini+CoT | VdB | 354 | -0.06 | [-0.60, +0.53] | -0.06 |
| Qwen3.6-A3B | Flawed | 121 | -1.21 | [-3.98, +1.83] | -1.19 |
| Qwen3.6-A3B | Full | 95 | +5.75 | [+2.19, +9.55] | +6.28 |
| Qwen3.6-A3B+CoT | Full | 112 | +1.86 | [-0.75, +4.56] | +1.86 |
| Qwen3.6-A3B | IGGI | 295 | -0.92 | [-2.50, +0.56] | -0.90 |
| Qwen3.6-A3B+CoT | IGGI† | 52 | +0.45 | [-1.60, +3.30] | +1.09 |
| Qwen3.6-A3B | Intentional | 153 | +0.75 | [-1.92, +3.80] | +0.79 |
| Qwen3.6-A3B+CoT | Intentional† | 20 | +4.17 | [+0.00, +10.83] | +4.17 |
| Qwen3.6-A3B | Internal | 345 | -0.73 | [-1.85, +0.35] | -0.70 |
| Qwen3.6-A3B | Outer | 261 | -2.89 | [-4.54, -1.28] | -2.78 |
| Qwen3.6-A3B | Piers | 294 | -0.83 | [-2.10, +0.50] | -0.72 |
| Qwen3.6-A3B | Simple | 340 | -1.07 | [-2.33, +0.13] | -1.05 |
| Qwen3.6-A3B | VdB | 289 | -0.42 | [-1.88, +1.01] | -0.36 |

## Rule-side (the rule agent's own plays)

| LLM config | Partner | n | Gap joint (pp) | 95% CI | Gap per-card (pp) |
|---|---|---|---|---|---|
| GPT-5.4 | Flawed | 316 | +1.18 | [-3.03, +5.12] | +1.38 |
| GPT-5.4 | Full | 391 | +24.66 | [+20.51, +28.66] | +24.85 |
| GPT-5.4 | IGGI | 244 | -0.92 | [-1.82, -0.22] | -0.76 |
| GPT-5.4 | Intentional | 288 | +0.00 | [+0.00, +0.00] | +0.00 |
| GPT-5.4 | Internal | 220 | +0.00 | [+0.00, +0.00] | +0.00 |
| GPT-5.4 | Outer | 205 | +0.00 | [+0.00, +0.00] | +0.00 |
| GPT-5.4 | Piers | 188 | +0.00 | [+0.00, +0.00] | +0.00 |
| GPT-5.4 | Simple | 220 | +0.00 | [+0.00, +0.00] | +0.00 |
| GPT-5.4 | VdB | 308 | -1.17 | [-3.46, +1.05] | -1.13 |
| GPT-5.4-mini | Flawed | 252 | +2.74 | [-1.47, +6.86] | +2.97 |
| GPT-5.4-mini+CoT | Flawed | 299 | -2.13 | [-5.94, +1.76] | -1.85 |
| GPT-5.4-mini | Full | 273 | +29.77 | [+25.23, +34.60] | +30.34 |
| GPT-5.4-mini+CoT | Full | 333 | +37.80 | [+33.71, +41.55] | +37.77 |
| GPT-5.4-mini | IGGI | 289 | -1.12 | [-2.04, -0.27] | -1.08 |
| GPT-5.4-mini+CoT | IGGI | 269 | -1.78 | [-2.75, -0.96] | -1.74 |
| GPT-5.4-mini | Intentional | 230 | +0.00 | [+0.00, +0.00] | +0.00 |
| GPT-5.4-mini+CoT | Intentional† | 262 | +0.00 | [+0.00, +0.00] | +0.00 |
| GPT-5.4-mini | Internal | 184 | +0.00 | [+0.00, +0.00] | +0.00 |
| GPT-5.4-mini+CoT | Internal | 212 | +0.00 | [+0.00, +0.00] | +0.00 |
| GPT-5.4-mini | Outer | 144 | +0.00 | [+0.00, +0.00] | +0.00 |
| GPT-5.4-mini+CoT | Outer | 199 | +0.00 | [+0.00, +0.00] | +0.00 |
| GPT-5.4-mini | Piers | 215 | +0.00 | [+0.00, +0.00] | +0.00 |
| GPT-5.4-mini+CoT | Piers | 217 | +0.00 | [+0.00, +0.00] | +0.00 |
| GPT-5.4-mini | Simple | 140 | +0.00 | [+0.00, +0.00] | +0.00 |
| GPT-5.4-mini+CoT | Simple | 224 | +0.00 | [+0.00, +0.00] | +0.00 |
| GPT-5.4-mini | VdB | 303 | -1.02 | [-2.82, +0.52] | -0.99 |
| GPT-5.4-mini+CoT | VdB | 330 | -1.13 | [-3.06, +0.64] | -1.01 |
| Qwen3.6-A3B | Flawed | 287 | -4.96 | [-8.73, -1.33] | -4.66 |
| Qwen3.6-A3B | Full | 409 | +11.85 | [+7.91, +15.68] | +12.08 |
| Qwen3.6-A3B+CoT | Full | 404 | +13.04 | [+9.30, +16.70] | +13.61 |
| Qwen3.6-A3B | IGGI | 270 | -0.27 | [-1.57, +1.04] | -0.09 |
| Qwen3.6-A3B+CoT | IGGI† | 48 | -1.59 | [-4.07, +0.00] | -1.22 |
| Qwen3.6-A3B | Intentional | 302 | +0.00 | [+0.00, +0.00] | +0.00 |
| Qwen3.6-A3B+CoT | Intentional† | 55 | +0.00 | [+0.00, +0.00] | +0.00 |
| Qwen3.6-A3B | Internal | 178 | +0.00 | [+0.00, +0.00] | +0.00 |
| Qwen3.6-A3B | Outer | 166 | +0.00 | [+0.00, +0.00] | +0.00 |
| Qwen3.6-A3B | Piers | 199 | +0.00 | [+0.00, +0.00] | +0.00 |
| Qwen3.6-A3B | Simple | 177 | +0.00 | [+0.00, +0.00] | +0.00 |
| Qwen3.6-A3B | VdB | 301 | +0.11 | [-1.85, +1.96] | +0.34 |

Pooled llm-side: n=9,542, joint -0.37 pp [-0.58, -0.17] (per-card -0.34).
Pooled rule-side: n=9,551, joint +3.90 pp [+3.44, +4.39] (per-card +4.02).