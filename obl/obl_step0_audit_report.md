# OBL Step-0 audit report (GX10) — 2026-08-17

Executed per `INSTRUCTION_for_claude_code_on_gx10.md` (items 1–6). Numbers only; no manuscript or pipeline edits. All derived JSONs are in this directory (`results_out/`); the code that produced them is `audit_step0.py` (engine equivalence, recomputation, item 7, consistency) and `write_report.py` (this file + `license_check.json`).

Inputs read: `convention_gap_obl_results/games/*.json` (25 files: 5 self-play × 1000, 10 OBL1 cross-play × 100, 10 inter-level × 1000 = 16,000 games), `gap_results.json`, `gap_interlevel.json`, the local `hanabi-convention-gap` package (v1.1.0), this directory's `src/`, and `OBL_convention_gap_report_v4.5.pdf` (pdftotext).

## Summary of findings

| # | Check | Result |
|---|---|---|
| 1 | Engine equivalence (package vs `src/` joint posterior) | **PASS** — max \|Δ posterior\| = 0.0e+00 (bit-identical) over 380,298 plays in 16,000 games (all 25 files); marginal also 0.0e+00; 1926 brute-force enumeration checks max diff 0.0e+00 |
| 2 | Recompute Table 2 (6 conditions) | **PASS** — all 6 gaps, mean posteriors, loss rates, play counts reproduce the local JSON and the printed values exactly at printed precision; CI ends within ≤0.015 pp of local JSON (different bootstrap RNG stream, see §2); 0 values > 0.05 pp |
| 2 | Recompute Table 3 (18 strata) | **PASS** — all n and gaps identical to local JSON (max \|Δ\| 1e-14 pp) and equal to printed values at 1 dp; 0 values > 0.05 pp |
| 2 | Recompute Table 4 OBL1 row (4 pairings) + all 10 pairings | **PASS on point estimates** — gaps/scores/n identical to local JSON and printed values; 4 CI *ends* differ from the 1-dp printed value by 0.051–0.059 pp (rounding + RNG stream; ≤0.02 pp from local JSON) — see §2 |
| 2 | Package re-run vs local JSONs | **bit-identical**: re-running `hanabi-convention-gap` (random.Random(42)) reproduces every field of `gap_results.json` and `gap_interlevel.json` exactly |
| 3 | Item 7 (OBL1 hint strata by partner) | **NOT in report v4.5** (§9 Table 6 has fresh-color-cue and silence-channel splits only, no 0/1/2+ split of OBL1's plays by partner) → computed here (§3). Result: OBL1's 1-hint gap decays +5.00 → +2.50 pp self→×OBL5; within-stratum decay accounts for 44–72 % of the total decline, composition shift for the rest |
| 4 | License | CC BY-NC 4.0 (repo root; no separate license in the model zip; HLE submodule Apache-2.0). Derived JSON: freely redistributable with citation; exported logs: redistributable for NonCommercial use under CC BY-NC-compatible terms with the §3(a) attribution block; checkpoints: link, do not redistribute (§4) |
| 5 | Consistency arithmetic | **PASS** except one report typo: strata sum to totals in all 16 conditions; play counts match Table 2; 16,000/16,000 games replay to the HLE score; self-play mean scores match; **cross-play mean score is 20.895 (rounds 20.90), not the 20.99 printed in §3 and §5 of v4.5** (§5) |

**Action items for the manuscript build (numbers only, no edits made here):** (i) replace the cross-play score 20.99 → 20.90 in the two sentences that quote it (v4.5 §3 verification paragraph and §5 'Cross-play'; both are hard-coded strings in `build_report_v45.py` lines 829 and 869); the corrected value is *closer* to the ICML 5000-game cross-play figure the sentence compares it to (20.85). (ii) The item-7 stratification supports the partner-supplied-residual reading (Step 0.5d) — see §3 for the numbers to quote.

## 1. Engine equivalence

Method: every exported game was replayed twice — once with `convention_gap.replay_and_extract` (package, joint posterior primary) and once with an independent loop over `src.game_engine.HanabiState` + `src.joint_posterior.compute_joint_posterior` + `src.posterior.compute_life_loss_posterior` (mirror of `src/joint_replay.replay_game_both_posteriors`, raw floats). Per play we compared joint posterior, marginal posterior, playability of the actual card, hint-action count and turn index. Additionally every 197th hint-constrained play was verified against `src.joint_posterior.brute_force_joint_posterior` (exhaustive enumeration), and the manuscript's actual entry point `replay_game_both_posteriors` (12-significant-digit string rows) was exercised on 20 games per file.

| File | Games | Plays | max \|Δ joint\| | max \|Δ marginal\| |
|---|---:|---:|---:|---:|
| OBL1_selfplay | 1000 | 22,791 | 0.0e+00 | 0.0e+00 |
| OBL2_selfplay | 1000 | 24,204 | 0.0e+00 | 0.0e+00 |
| OBL3_selfplay | 1000 | 24,538 | 0.0e+00 | 0.0e+00 |
| OBL4_selfplay | 1000 | 24,731 | 0.0e+00 | 0.0e+00 |
| OBL5_selfplay | 1000 | 24,871 | 0.0e+00 | 0.0e+00 |
| OBL1_crossplay(10 pairs) | 1000 | 22,616 | 0.0e+00 | 0.0e+00 |
| OBL1xOBL2 | 1000 | 22,979 | 0.0e+00 | 0.0e+00 |
| OBL1xOBL3 | 1000 | 22,495 | 0.0e+00 | 0.0e+00 |
| OBL1xOBL4 | 1000 | 22,369 | 0.0e+00 | 0.0e+00 |
| OBL1xOBL5 | 1000 | 22,035 | 0.0e+00 | 0.0e+00 |
| OBL2xOBL3 | 1000 | 24,311 | 0.0e+00 | 0.0e+00 |
| OBL2xOBL4 | 1000 | 24,323 | 0.0e+00 | 0.0e+00 |
| OBL2xOBL5 | 1000 | 24,067 | 0.0e+00 | 0.0e+00 |
| OBL3xOBL4 | 1000 | 24,654 | 0.0e+00 | 0.0e+00 |
| OBL3xOBL5 | 1000 | 24,512 | 0.0e+00 | 0.0e+00 |
| OBL4xOBL5 | 1000 | 24,802 | 0.0e+00 | 0.0e+00 |
| **all** | **16,000** | **380,298** | **0.0e+00** | **0.0e+00** |

Row-count mismatches: 0; turn mismatches: 0; playable-flag mismatches: 0; hint-count mismatches: 0. Brute-force checks: 1926 of 379,464 plays with ≥1 hint-constrained other card in hand (stride 197), max |Δ| = 0.0e+00. String-row check: 7,605 plays, max |Δ| = 4.9e-13. Requirement max |Δ| < 1e-9: **met** (observed 0.0e+00).

Note: `diff` of `convention_gap/joint_posterior.py`, `game_engine.py`, `posterior.py` against `src/` shows the implementations differ only in docstrings and import paths (`convention_gap.` vs `src.`); the empirical run above confirms bit-identity of the outputs. Detail: `engine_equivalence.json`.

## 2. Independent recomputation (manuscript pipeline)

Method: per-play records from `src.replay.replay_and_extract` (hint-action counts, playability, game key) joined with the joint posterior from `src.joint_posterior` on (game_key, turn); gap = mean posterior − loss rate; CIs from `src.cluster_stats.cluster_bootstrap_gap_ci` (game-level cluster percentile bootstrap, 10,000 draws, `numpy.random.default_rng(42)`). The local package uses `random.Random(42)` with a different draw scheme, so CIs are expected to agree only up to bootstrap Monte-Carlo noise (observed ≤0.02 pp), while all point estimates must be identical. Detail: `recompute_ms_pipeline.json`, `recompute_pkg_rerun.json`, `diff_vs_local_and_report.json`.

### Table 2 — recomputed vs local `gap_results.json` vs report v4.5

| Condition | Games | Plays (rec / local / report) | Mean post. (rec / report) | Loss (rec / report) | Gap pp (rec / local / report) | 95% CI pp recomputed | CI local | CI report | max\|Δ\| vs local (pp) |
|---|---:|---|---|---|---|---|---|---|---:|
| OBL1_selfplay | 1000 | 22,791 / 22,791 / 22,791 | 0.0783 / 0.0783 | 0.0627 / 0.0627 | +1.568 / +1.568 / +1.57 | [+1.328, +1.804] | [+1.331, +1.811] | [+1.33, +1.81] | 0.007 |
| OBL2_selfplay | 1000 | 24,204 / 24,204 / 24,204 | 0.1541 / 0.1541 | 0.0301 / 0.0301 | +12.401 / +12.401 / +12.40 | [+12.111, +12.693] | [+12.104, +12.707] | [+12.10, +12.71] | 0.015 |
| OBL3_selfplay | 1000 | 24,538 / 24,538 / 24,538 | 0.1913 / 0.1913 | 0.0222 / 0.0222 | +16.907 / +16.907 / +16.91 | [+16.599, +17.214] | [+16.595, +17.207] | [+16.60, +17.21] | 0.007 |
| OBL4_selfplay | 1000 | 24,731 / 24,731 / 24,731 | 0.2235 / 0.2235 | 0.0247 / 0.0247 | +19.878 / +19.878 / +19.88 | [+19.548, +20.218] | [+19.541, +20.208] | [+19.54, +20.21] | 0.010 |
| OBL5_selfplay | 1000 | 24,871 / 24,871 / 24,871 | 0.2412 / 0.2412 | 0.0244 / 0.0244 | +21.680 / +21.680 / +21.68 | [+21.341, +22.025] | [+21.339, +22.015] | [+21.34, +22.02] | 0.010 |
| OBL1_crossplay(10 pairs) | 1000 | 22,616 / 22,616 / 22,616 | 0.0771 / 0.0771 | 0.0649 / 0.0649 | +1.219 / +1.219 / +1.22 | [+0.981, +1.453] | [+0.979, +1.454] | [+0.98, +1.45] | 0.002 |

Verdict: every gap, mean posterior, loss rate and n reproduces the local JSON to machine precision and the printed value at printed precision (+1.57 / +12.40 / +16.91 / +19.88 / +21.68 self-play, +1.22 cross-play). CI ends: max |Δ| vs local 0.015 pp (OBL2 upper); 6 of 12 printed CI ends differ from the recomputed value at the 2nd decimal by 0.005–0.017 pp — bootstrap RNG-stream noise, all far below the 0.05 pp flag threshold.

### Table 3 — hint-count strata (n / gap pp): recomputed vs report

| Condition | 0 hints rec | 0 hints report | 1 hint rec | 1 hint report | 2+ hints rec | 2+ hints report | Σn = total? |
|---|---|---|---|---|---|---|---|
| OBL1_selfplay | 990 / -11.65 | 990 / -11.7 | 8,951 / +5.00 | 8,951 / +5.0 | 12,850 / +0.20 | 12,850 / +0.2 | 22,791 = 22,791 ✓ |
| OBL2_selfplay | 375 / +6.46 | 375 / +6.5 | 13,201 / +22.15 | 13,201 / +22.1 | 10,628 / +0.50 | 10,628 / +0.5 | 24,204 = 24,204 ✓ |
| OBL3_selfplay | 332 / +16.78 | 332 / +16.8 | 13,887 / +28.95 | 13,887 / +29.0 | 10,319 / +0.70 | 10,319 / +0.7 | 24,538 = 24,538 ✓ |
| OBL4_selfplay | 390 / +15.44 | 390 / +15.4 | 14,524 / +32.78 | 14,524 / +32.8 | 9,817 / +0.97 | 9,817 / +1.0 | 24,731 = 24,731 ✓ |
| OBL5_selfplay | 394 / +21.03 | 394 / +21.0 | 15,058 / +34.42 | 15,058 / +34.4 | 9,419 / +1.33 | 9,419 / +1.3 | 24,871 = 24,871 ✓ |
| OBL1_crossplay(10 pairs) | 930 / -15.06 | 930 / -15.1 | 8,783 / +4.52 | 8,783 / +4.5 | 12,903 / +0.14 | 12,903 / +0.1 | 22,616 = 22,616 ✓ |

Verdict: all 18 n identical; all 18 gaps identical to the local JSON (|Δ| ≤ 1e-14 pp) and equal to the printed 1-dp values (largest rounding residual 0.049 pp, OBL2 1-hint: +22.149 printed +22.1). Recomputed strata CIs (not in the report) are in `recompute_ms_pipeline.json`.

### Table 4 — inter-level pairings (OBL1 row required; all 10 recomputed)

| Pairing | Score rec / local / report | n all (low+high) | Gap lower rec [CI] | local [CI] | report | Gap higher rec [CI] | local [CI] | report | Gap pair rec / local / report |
|---|---|---|---|---|---|---|---|---|---|
| OBL1xOBL2 | 21.370 / 21.370 / 21.37 | 22,979 (11,676+11,303) | +1.01 [+0.68, +1.35] | +1.01 [+0.68, +1.35] | +1.0 [+0.7, +1.3] | +8.42 [+8.00, +8.85] | +8.42 [+7.99, +8.86] | +8.4 [+8.0, +8.9] | +4.66 / +4.66 / +4.7 |
| OBL1xOBL3 | 20.501 / 20.501 / 20.50 | 22,495 (11,597+10,898) | +0.61 [+0.25, +0.96] | +0.61 [+0.25, +0.96] | +0.6 [+0.2, +1.0] | +8.58 [+8.14, +9.02] | +8.58 [+8.14, +9.02] | +8.6 [+8.1, +9.0] | +4.47 / +4.47 / +4.5 |
| OBL1xOBL4 | 20.079 / 20.079 / 20.08 | 22,369 (11,242+11,127) | +0.33 [-0.03, +0.69] | +0.33 [-0.02, +0.68] | +0.3 [-0.0, +0.7] | +9.01 [+8.58, +9.44] | +9.01 [+8.58, +9.45] | +9.0 [+8.6, +9.4] | +4.65 / +4.65 / +4.6 |
| OBL1xOBL5 | 19.330 / 19.330 / 19.33 | 22,035 (11,060+10,975) | +0.12 [-0.22, +0.45] | +0.12 [-0.22, +0.46] | +0.1 [-0.2, +0.5] | +8.38 [+7.89, +8.85] | +8.38 [+7.90, +8.86] | +8.4 [+7.9, +8.9] | +4.23 / +4.23 / +4.2 |
| OBL2xOBL3 | 23.582 / 23.582 / 23.58 | 24,311 (12,303+12,008) | +14.27 [+13.83, +14.72] | +14.27 [+13.83, +14.73] | +14.3 [+13.8, +14.7] | +13.79 [+13.36, +14.22] | +13.79 [+13.36, +14.23] | +13.8 [+13.4, +14.2] | +14.04 / +14.04 / +14.0 |
| OBL2xOBL4 | 23.536 / 23.536 / 23.54 | 24,323 (12,106+12,217) | +13.96 [+13.49, +14.40] | +13.96 [+13.51, +14.42] | +14.0 [+13.5, +14.4] | +13.75 [+13.31, +14.19] | +13.75 [+13.31, +14.19] | +13.7 [+13.3, +14.2] | +13.85 / +13.85 / +13.9 |
| OBL2xOBL5 | 23.188 / 23.188 / 23.19 | 24,067 (11,995+12,072) | +13.44 [+12.95, +13.94] | +13.44 [+12.94, +13.93] | +13.4 [+12.9, +13.9] | +14.02 [+13.58, +14.48] | +14.02 [+13.59, +14.47] | +14.0 [+13.6, +14.5] | +13.73 / +13.73 / +13.7 |
| OBL3xOBL4 | 23.999 / 23.999 / 24.00 | 24,654 (12,165+12,489) | +17.42 [+16.96, +17.89] | +17.42 [+16.96, +17.89] | +17.4 [+17.0, +17.9] | +17.64 [+17.18, +18.08] | +17.64 [+17.19, +18.10] | +17.6 [+17.2, +18.1] | +17.53 / +17.53 / +17.5 |
| OBL3xOBL5 | 23.798 / 23.798 / 23.80 | 24,512 (12,121+12,391) | +17.80 [+17.32, +18.28] | +17.80 [+17.33, +18.27] | +17.8 [+17.3, +18.3] | +17.35 [+16.88, +17.80] | +17.35 [+16.89, +17.80] | +17.3 [+16.9, +17.8] | +17.57 / +17.57 / +17.6 |
| OBL4xOBL5 | 24.119 / 24.119 / 24.12 | 24,802 (12,250+12,552) | +20.44 [+19.94, +20.94] | +20.44 [+19.95, +20.95] | +20.4 [+20.0, +20.9] | +20.20 [+19.75, +20.65] | +20.20 [+19.75, +20.66] | +20.2 [+19.7, +20.7] | +20.32 / +20.32 / +20.3 |

Verdict: all scores, gaps and n identical to the local JSON and to the printed values at printed precision. 4 CI *ends* exceed the 0.05 pp threshold against the 1-dp printed value only because of rounding (the local JSON value rounds to the printed value in every case; the recomputed value is within 0.02 pp of local):
- OBL1xOBL5 high_ci_hi_pp: recomputed +8.846, local +8.859, printed +8.9 (|Δ| vs local 0.013 pp, vs printed 0.054 pp)
- OBL2xOBL5 low_ci_lo_pp: recomputed +12.953, local +12.941, printed +12.9 (|Δ| vs local 0.012 pp, vs printed 0.053 pp)
- OBL4xOBL5 low_ci_lo_pp: recomputed +19.941, local +19.955, printed +20.0 (|Δ| vs local 0.013 pp, vs printed 0.059 pp)
- OBL4xOBL5 high_ci_lo_pp: recomputed +19.751, local +19.747, printed +19.7 (|Δ| vs local 0.004 pp, vs printed 0.051 pp)

OBL1 row (the value entering the preprint): OBL1's own gap +1.01 [+0.68, +1.35] → +0.61 [+0.25, +0.96] → +0.33 [−0.03, +0.69] → +0.12 [−0.22, +0.45] pp vs OBL2/3/4/5 partners (recomputed; identical point estimates to local JSON; ×OBL4 and ×OBL5 CIs include zero — the report prints ×OBL4 as [−0.0, +0.7], which is the same fact at 1 dp).

## 3. Item 7 — OBL1's plays by hint count, per partner level

Report v4.5 check: §7 (Table 4), §9 (Table 6: fresh-color-cue share/loss/gap per acting agent; silence-channel sentence), §10 (seed sweep) and §11 (masking) contain **no** 0/1/2+ hint-count stratification of OBL1's plays by partner. Table 3's OBL1 rows are self-play and pooled 10-pair cross-play only. So the analysis was run here.

Data: OBL1's own plays (acting seat = OBL1) in `OBL1_selfplay` (both seats, 1000 games) and in `interlevel_OBL1xOBLk` (k = 2..5, 1000 games each; seed-a models). Strata by hint ACTIONS that touched the played card (same definition as Table 3). CIs: game-cluster bootstrap, 10,000 draws, seed 42. Detail: `item7_obl1_hint_strata_by_partner.json`.

| Partner | OBL1 plays | OBL1 gap pp [CI] | 0 hints: n (share) / post / loss / gap [CI] | 1 hint: n (share) / post / loss / gap [CI] | 2+ hints: n (share) / post / loss / gap [CI] |
|---|---:|---|---|---|---|
| self(OBL1) | 22,791 | +1.57 [+1.33, +1.80] | 990 (4.3%) / 56.8 / 68.5 / -11.65 [-14.26, -9.07] | 8,951 (39.3%) / 12.8 / 7.8 / +5.00 [+4.46, +5.50] | 12,850 (56.4%) / 0.6 / 0.4 / +0.20 [+0.10, +0.30] |
| xOBL2 | 11,676 | +1.01 [+0.68, +1.35] | 645 (5.5%) / 58.2 / 76.0 / -17.74 [-20.51, -14.87] | 4,169 (35.7%) / 14.4 / 9.5 / +4.88 [+4.08, +5.68] | 6,862 (58.8%) / 1.0 / 0.6 / +0.42 [+0.25, +0.59] |
| xOBL3 | 11,597 | +0.61 [+0.25, +0.96] | 577 (5.0%) / 59.7 / 79.5 / -19.89 [-22.74, -17.04] | 3,746 (32.3%) / 14.9 / 10.5 / +4.37 [+3.40, +5.33] | 7,274 (62.7%) / 0.9 / 0.6 / +0.29 [+0.14, +0.44] |
| xOBL4 | 11,242 | +0.33 [-0.03, +0.69] | 536 (4.8%) / 58.8 / 78.5 / -19.73 [-22.75, -16.59] | 3,450 (30.7%) / 14.7 / 11.0 / +3.72 [+2.75, +4.69] | 7,256 (64.5%) / 0.9 / 0.7 / +0.21 [+0.04, +0.37] |
| xOBL5 | 11,060 | +0.12 [-0.22, +0.45] | 483 (4.4%) / 58.2 / 77.6 / -19.48 [-22.74, -16.15] | 3,411 (30.8%) / 14.3 / 11.8 / +2.50 [+1.58, +3.46] | 7,166 (64.8%) / 1.0 / 0.7 / +0.30 [+0.14, +0.46] |

Kitagawa decomposition of Δgap = gap(×OBLk) − gap(self) into a composition term Σ(share_k − share_self)·gap_self and a within-stratum term Σ share_k·(gap_k − gap_self):

| Partner | Δ total (pp) | composition (pp) | within-stratum (pp) | within share |
|---|---:|---:|---:|---:|
| xOBL2 | -0.557 | -0.311 | -0.246 | 44% |
| xOBL3 | -0.963 | -0.409 | -0.553 | 57% |
| xOBL4 | -1.235 | -0.462 | -0.773 | 63% |
| xOBL5 | -1.452 | -0.407 | -1.045 | 72% |

Reading (for Step 0.5d): (i) The 1-hint stratum — where OBL1's surplus lives — decays monotonically with partner level: +5.00 [+4.46, +5.50] (self) → +4.88 → +4.37 → +3.72 → +2.50 [+1.58, +3.46] pp (×OBL5); self vs ×OBL5 CIs do not overlap. Its literal posterior is *higher* against higher partners (12.8 → 14.3 %) while its realized loss rate rises (7.8 → 11.8 %): OBL1 keeps taking the same kind of 1-hint plays but they succeed less often, i.e. the harvestable correlation in the partner's hints thins out — this is the partner-supplied-correlation reading, not a composition artifact. (ii) Composition also shifts (1-hint share 39 → 31 %, 2+ share 56 → 65 %) and contributes −0.31 to −0.46 pp; the within-stratum term grows with partner distance and dominates from ×OBL3 on (57 → 72 % of the total decline). (iii) The 0-hint stratum (4–5 % of plays, forced plays) worsens from −11.7 to ≈ −19 to −20 pp against any higher partner but is roughly flat across ×OBL2..×OBL5, so it explains the self→cross step, not the monotone decay. (iv) The 2+ stratum is ≈ 0 throughout. Caveat: one seed model per level.

## 4. License (facebookresearch/off-belief-learning)

File: `$OBL_ROOT/off-belief-learning/LICENSE` (sha256 `28ef518c6052ef9cb4e4b6939e4e2dbf661e0df5b814ff077b24d08f70f58c4e`, 399 lines). First line verbatim: `Attribution-NonCommercial 4.0 International` → **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**. README §Copyright: “Copyright (c) Facebook, Inc. and its affiliates. All rights reserved. This source code is licensed under the license found in the LICENSE file in the root directory of this source tree.” The model zip (`icml_obl_models.zip`, fetched by `models/download.sh` from dl.fbaipublicfiles.com/hanabi_obl/) contains no separate license or README; the HLE submodule carries Apache-2.0 (game engine only). Verbatim excerpts of §§1a, 1i, 1j, 2a1, 2a5b, 3a, 8a and the assessment are in `license_check.json`. Key verbatim clauses:

> 2(a)(1) … the Licensor hereby grants You a worldwide, royalty-free, non-sublicensable, non-exclusive, irrevocable license to exercise the Licensed Rights in the Licensed Material to: a. reproduce and Share the Licensed Material, in whole or in part, for NonCommercial purposes only; and b. produce, reproduce, and Share Adapted Material for NonCommercial purposes only.
>
> 1(a) Adapted Material means material subject to Copyright and Similar Rights that is derived from or based upon the Licensed Material and in which the Licensed Material is translated, altered, arranged, transformed, or otherwise modified in a manner requiring permission under the Copyright and Similar Rights held by the Licensor.
>
> 3(a)(1) If You Share the Licensed Material (including in modified form), You must: a. retain … i. identification of the creator(s) …; ii. a copyright notice; iii. a notice that refers to this Public License; iv. a notice that refers to the disclaimer of warranties; v. a URI or hyperlink to the Licensed Material …; b. indicate if You modified the Licensed Material …; and c. indicate the Licensed Material is licensed under this Public License, and include the text of, or the URI or hyperlink to, this Public License. … 3(a)(4) If You Share Adapted Material You produce, the Adapter's License You apply must not prevent recipients of the Adapted Material from complying with this Public License.
>
> 8(a) … this Public License does not, and shall not be interpreted to, reduce, limit, restrict, or impose conditions on any use of the Licensed Material that could lawfully be made without permission under this Public License.

What it permits (reading of the text; not legal advice):

- **(a) Redistributing exported game logs.** The logs are outputs of running the licensed checkpoints. If treated as Adapted Material (conservative), 2(a)(1)(b) permits Sharing them **for NonCommercial purposes only**, with the 3(a) attribution block and an Adapter's License compatible with CC BY-NC (i.e. release the logs under CC BY-NC 4.0, not MIT/CC0/CC BY). If, as is likely for a bare move sequence, they carry none of the checkpoints' copyright, 8(a) says the license does not restrict them at all. Either way: **permitted for a non-commercial research release with attribution; a commercial-use grant is not permitted.**
- **(b) Derived JSON results** (`gap_results.json`, `gap_interlevel.json`, tables): aggregate facts about the logs, not reproductions or adaptations of the Licensed Material — **not restricted**; release under the paper's own license, citing Hu et al. 2021 and the repository (prudent 3(a)-style attribution).
- **(c) Attribution/citation.** For anything shared as derived from the checkpoints: creator + copyright notice (“Facebook, Inc. and its affiliates”), a CC BY-NC 4.0 notice + link to the license text, link to github.com/facebookresearch/off-belief-learning (and/or the model zip URL), a statement that the logs were generated by running the released `icml_OBL*` checkpoints, no implied endorsement (2(a)(6)); cite Hu et al., “Off-Belief Learning”, ICML 2021 (arXiv:2103.04000). **Do not redistribute the checkpoints**; point to the official download.

## 5. Consistency arithmetic

- Replay verification: 16,000 games across 16 conditions; replay mismatches (replayed score ≠ `hle_score` or game not terminal): 0 → **all verified** (matches the report's “1000/1000 in every condition”).
- Strata sums: hint strata n sum to the condition total in all 6 Table-2 conditions; low + high plays = all plays in all 10 pairings → **all OK**.
- Play counts equal Table 2's printed n in all 6 conditions: **True**. OBL1's own play counts in item 7 equal the Table-4 'low' n for each pairing and Table 2's n for self-play: **True**.
- Cross-play condition: 10 pair files × 100 games = 1000 games (per-pair mean scores 19.81–21.40).
- Mean scores (HLE ground truth = replayed): OBL1_selfplay 21.093 (report 21.09 ✓); OBL2_selfplay 23.451 (report 23.45 ✓); OBL3_selfplay 23.972 (report 23.97 ✓); OBL4_selfplay 24.054 (report 24.05 ✓); OBL5_selfplay 24.162 (report 24.16 ✓); OBL1_crossplay(10 pairs) 20.895 (report 20.99 ✗).
  - **Discrepancy:** the OBL1 cross-play mean score is **20.895** (rounds to 20.90), whereas v4.5 prints **20.99** in the §3 verification paragraph (“… 24.16 self-play OBL1–5, 20.99 cross-play — match the 5000-game evaluation … cross-play 20.85”) and in §5 (“score (20.99 vs 21.09)”). Both are hard-coded strings in the report builder (`build_report_v45.py` lines 829, 869; already present in the v1 builder). No JSON on disk contains 20.99. The correct value 20.90 is closer to the ICML cross-play figure (20.85) that the sentence compares against, and the §5 conclusion (“score essentially unchanged across seeds”, 20.90 vs 21.09) is unaffected. Δ = 0.095 → flagged.
- Inter-level scores: recomputed = local JSON = printed at 2 dp for all 10 pairings (21.37 / 20.50 / 20.08 / 19.33 / 23.58 / 23.54 / 23.19 / 24.00 / 23.80 / 24.12).
- Not re-verified here (out of the six items' data): the ICML paper Table-1 scores (20.92/23.41/23.93/24.10) and the “5000-game evaluation” figures (20.82/23.47/23.95/24.16/24.20; cross-play 20.85) quoted in v4.5 §3; the latter are traceable to an earlier `pyhanabi` eval run in this machine's session log (20.824 ± 0.053 / 23.474 / 23.954 / 24.155 / 24.202), consistent with the printed rounding.

## 6. Output files

- `engine_equivalence.json` — per-file max |Δ| joint/marginal, mismatch counters, brute-force stats.
- `recompute_ms_pipeline.json` — manuscript-pipeline recomputation: Table 2 (with strata + strata CIs), Table 4 all 10 pairings (all/low/high, with strata), mean HLE scores.
- `recompute_pkg_rerun.json` — package re-run with `identical_to_*_json` flags (all True).
- `diff_vs_local_and_report.json` — every compared value with |Δ| vs local JSON and vs printed report, flag > 0.05 pp.
- `item7_obl1_hint_strata_by_partner.json` — item 7 strata + decomposition.
- `consistency_checks.json` — replay verification, strata sums, scores, counts.
- `license_check.json` — sha256, verbatim excerpts, assessment.
- `audit_step0.py`, `write_report.py`, `audit_step0.log` — code and run log (wall clock 449 s).

## 7. Follow-up (2026-08-17): typo fixed in report v4.6

`convention_gap_followup/build_report_v46.py` (copy of the v4.5 builder) corrects both hard-coded strings (20.99 → 20.90 in the §3 verification paragraph and the §5 "Cross-play" sentence), bumps the header to "v4.6 · August 17, 2026", and appends the changelog entry "v4.6: cross-play mean score corrected 20.99→20.90 (Step-0 audit, verified against the 1000 exported cross-play games); all other numbers unchanged". Built with `CG_SHARED=$PWD/shared`. Verified by pdftotext diff against v4.5: the only text differences are the header line, the changelog entry, and the two corrected sentences (31 pages, unchanged). One incidental normalization: the local `exp4_humans/step6_results.json` labels three Table-12 rows with "colour", whereas the v4.5 PDF on disk shows "color"; the v4.6 builder maps those labels to "color" so the table matches v4.5 and the report's American spelling elsewhere. Copy of the PDF: `results_out/OBL_convention_gap_report_v4.6.pdf`.
