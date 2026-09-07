# Numbers diff v5 → v6 (branch: fix/neurips-review-2026-07)

Post: Phase 1 (engine/replay) + Phase 2 (analysis) + B1 (unique game_key)
+ B2/B4 (H-H bot exclusion, two-tier policy) + B3 (skill_level populated).

## Bot exclusion policy (2026-07-02 revision)

**Two-tier:**
- Tier 1 (game-level): 12 verified bots — drop every game they appear in.
- Tier 2 (account-level): 11 B-bucket (≥90% co-play with verified bot)
  + 16 C-bucket (identical-stats pair members). Drop only these accounts' plays;
  their (possibly-human) partners' plays remain.
- Not excluded: Buckets A (extreme volume+timing alone), D (volume + short-min-gap alone),
  E (volume-only), F (identical-lowvol pairs), G (single low-vol short-gap accounts) —
  no positive bot evidence beyond volume/timing.

## Robustness — H-H headline gap under both policies

| Policy | n_games | n_plays | H-H gap | mean score |
|---|---|---|---|---|
| Full corpus (no exclusion)   |  1431   |  26,229 | **+31.0 pp** | 15.47 |
| Game-level (verified only)   |   819   |  15,562 | **+29.8 pp** | 16.95 |
| Two-tier (verified + B+C)    |   597   |  10,961 | **+28.4 pp** | 16.14 |

_The two-tier headline (main analysis) is +28.4 pp; the more permissive game-level-only variant is +29.8 pp;
the difference (1.4 pp) is within the between-corpus noise. The paper uses the two-tier corpus._

## Corpus totals

| Setting | v5 rows / games | v6 rows / games |
|---|---|---|
| H-H (two-tier corpus)     | 23,479 / 1,157 | **10,961 / 597** |
| H-H (game-level, robustness)| — | 15,562 / 819 |
| H-AI                      | 29,049 / 2,040 | **29,049 / 2,040** |
| AI-AI                     | 62,890 / 4,446 (buggy dedup) | **62,890 / 4,900** (unique game_key) |

Total plays (v6, main corpus): **102,900**

## Headline convention gaps

| Setting | v5 | v6 (two-tier) |
|---|---|---|
| H-H | +30.5 pp | **+28.4 pp** |
| H-AI (human plays) | +16.9 pp | **+16.9 pp** |
| AI-AI | −0.5 pp | **−0.5 pp** |

## §4.4 Player Loss (AI-AI) — actor-based filter

| Agent | v5 (buggy) | v6 (actor filter) |
|---|---|---|
| bergh | — | **7.39%** (n=8,568) |
| flawed | — | **47.92%** (n=8,092) |
| iggi | — | **0.00%** (n=9,941) |
| internal | 5.8% | **0.00%** (n=6,970) |
| outer | 4.9% | **0.00%** (n=6,976) |
| piers | — | **14.02%** (n=10,010) |
| simple | — | **0.00%** (n=12,333) |

## §4.4/Fig 3 Partner Loss (AI-AI) — partner=a AND actor≠a (mirror games excluded)

| Agent | v5 (buggy) | v6 |
|---|---|---|
| bergh | — | **7.89%** (n=10,301) |
| flawed | — | **2.78%** (n=324) |
| iggi | — | **10.82%** (n=9,066) |
| internal | 6.8% | **11.14%** (n=8,962) |
| outer | 6.1% | **8.92%** (n=11,006) |
| piers | — | **7.01%** (n=10,089) |
| simple | — | **21.91%** (n=3,751) |

## §4.4 fold-increases (H-AI PL / AI-AI PL) and "within 0.7 pp"

| Metric | v5 | v6 |
|---|---|---|
| outer fold | 5.6× | **3.86×** |
| intentional fold | 2.6× | **1.58×** |
| Outer vs Intentional PL diff | 0.7 pp | **2.21 pp** |

## Fig 1a / §4.4 mean game scores — corrected (Appendix A: strike-out=0)

| Setting | v5 | v6 |
|---|---|---|
| H-H mean | 18.4 (n=1,157) | **16.14** (n=597) |
| H-AI mean | 10.8 (human-only, n=2,035) | **7.22** (n=2,040, all plays) |
| AI-AI mean | 11.0 (n=4,900) | **10.73** (n=4,900) |
| HAI vs AA Welch | p=0.55 | **t=-16.45, p=2.11e-58** |
| HH vs HAI Welch | (unreported) | t=20.24, p=3.99e-75 |

_Direction is preserved (H-H > AI-AI > H-AI) but the H-AI/AI-AI ordering flips vs v5, and all pairwise diffs are now significant._

## Table A2 game score by pair-type (v6 two-tier H-H)

| Pair | v5 mean | v6 mean (n_games) | v6 conv. gap |
|---|---|---|---|
| expert-expert | 22.9 | **23.44** (n=112) | **+30.8 pp** |
| expert-intermediate | — | **24.17** (n=18) | **+30.5 pp** |
| expert-beginner | — | **16.67** (n=3) | **+39.8 pp** |
| intermediate-intermediate | — | **18.66** (n=209) | **+28.4 pp** |
| intermediate-beginner | — | **7.50** (n=8) | **+25.5 pp** |
| beginner-beginner | 9.8 | **10.38** (n=247) | **+26.1 pp** |

## Main-text Table 1 — convention gap by hint count (all three settings, v6 two-tier)

| Hints on card | v5 H-H / HAI / AA (type-count) | v6 H-H / HAI / AA (action-count) |
|---|---|---|
| 0 | +41 / −12 / −11 | **+47.8 / -12.0 / -11.4 pp** |
| 1 | +39 / +24 / +1 | **+38.2 / +25.4 / +1.2 pp** |
| 2+ | ~0 / ~0 / ~0 | **+1.9 / +1.0 / -0.1 pp** |

## Table A4 — per-AI hint-count decomposition (human plays; unchanged from previous diff)

| AI | 0 hints | 1 hint | ≥2 hints |
|---|---|---|---|
| full | −5.7 pp (n=220) | +32.9 pp (n=3,542) | +2.0 pp (n=1,007) |
| intentional | −14.5 pp (n=390) | +31.2 pp (n=3,552) | +1.2 pp (n=1,180) |
| outer | −14.6 pp (n=168) | +11.5 pp (n=3,406) | +0.3 pp (n=2,007) |

## Abstract statistics — regenerated on v6 two-tier corpus

| Claim | v5 | v6 |
|---|---|---|
| 0-hint success H-H vs H-AI | 71%/16%, z=25.65 | **77.8%/15.7%, z=22.56** |
| H-H 0-hint gap | +41 pp | **+47.8 pp** |
| Full own-play gap | +18.0 pp (n=5,965) | **+18.0 pp** (n=5,965) |
| Intentional own-play gap | ≈0 pp (n=4,979) | **+0.01 pp** (n=4,979) |
| Outer own-play gap | ≈0 pp (n=2,633) | **-0.00 pp** (n=2,633) |
| Full vs Intentional H-AI Partner Loss | (unreported) | **14.4% vs 17.6%, z=-4.39** |

## §4.5 hint-record counts

| Claim | v5 | v6 |
|---|---|---|
| §4.5 "AI hint actions" (H-AI, hinter is AI) | 20,088 | **20,088** (unchanged) |
| README hint_records.csv total | 168,012 | **195,634** |
|   of which H-H (was missing in v5) | 0 | 27,622 |
|   of which H-AI                    | 43,222 | 43,222 |
|   of which AI-AI                   | 124,790 | 124,790 |

_The 20,088 in §4.5 refers to a specific subset (H-AI AI-hint actions) and is unchanged;
the 168,012 total (v5 README claim) is updated to 195,634 in the README only._

## Table A6 logistic — statsmodels.Logit unpenalized MLE (v6)

Values from notebook cell 13:

| Dataset | Model | N | AUC | Pseudo-R² | β(post) |
|---|---|---|---|---|---|
| human   | M1 posterior | 10,961 | ~0.78 | ~0.16 | ~5.0 |
| human   | M2 context   | 10,961 | ~0.82 | ~0.21 | ~4.2 |
| human   | M3 full      | 10,961 | ~0.84 | ~0.23 | ~4.1 |
| agent   | M1 posterior | 62,890 | 0.98  | 0.63  | ~9.4 |
| human_ai| M1 posterior | 15,472 | 0.87  | 0.34  | ~6.0 |

## Appendix N — Bayesian hierarchical (random slopes) models on v6 two-tier corpus

### H-H model (`convention_gap ~ 1 + game_seq + (1 + game_seq | player)`)
- n = 709 game×player observations across 31 players (≥10 games each)
- Population slope β(game_seq) = **+0.00090** (95% HDI **[−0.00036, +0.00207]**)
- P(β > 0) = **0.93**
- σ_β (between-player slope SD) = 0.00073
- 31/31 players have positive pooled slope

_v5 reported β=+0.00041, HDI [−0.00011, +0.00096], P(β>0)=0.94 — same story, larger point estimate on the smaller (bot-excluded) corpus._

## §3.3 corpus counts

| Sentence | v5 | v6 (two-tier) |
|---|---|---|
| H-H count | "1,157 games, 23,479 play records" | **"597 games, 10,961 play records"** |
| Skill classification (post-bot-exclusion) | (v5 unspecified) | 165 players, distribution below |

Skill distribution (v6 two-tier corpus):

- beginner: 64 players
- intermediate: 48 players
- expert: 53 players

## Cluster (game-level) vs play-level bootstrap CIs — v6

| Setting | Play-level 95% CI | Cluster (game) 95% CI |
|---|---|---|
| Full        | [+23.6, +25.6] | [+23.5, +25.6] |
| Intentional | [+19.9, +21.7] | [+19.8, +21.8] |
| Outer       | [+5.7, +7.7]   | [+5.7, +7.7]   |
| Human-human | [+27.8, +29.0] | [+27.6, +29.1] |

## Mirror-game exclusion (§3.4 documentation)

AI-AI Partner Loss uses `partner=a AND actor≠a` — mirror games (a_vs_a) are excluded.
Mirror plays excluded from Partner Loss: **9,391** of 62,890 total.

Flawed: n=324 for Partner Loss because flawed rarely lets its partner take actions
(random-hint design triggers early game-overs). Interpret Flawed's 2.8% cautiously.

---

# v6 → v7 (2026-07-03): completed-games filter + notes-signature bot + the account hashed a08ee96386551922

## New: `game_end_reason` in the replay engine

Each replayed game is now classified `strikeout` / `perfect` / `natural` /
`truncated`. `truncated` = the log ended without reaching a terminal state:
either an explicit hanab.live end-of-game marker (end conditions 3=timeout,
4=terminated, 6=idle — verified to carry recorded score 0), or the log stopped
mid-game with cards still in the deck. hanab.live ends the final round early
when no further points are possible, so a completed natural game's log may stop
one or two turns short of a full final round; reaching an empty deck therefore
counts as `natural` (validated: for a sample of such games the hanab.live
*recorded score equals the replayed fireworks* — 47/47).

**Validation:** HOAD 0 truncated, HanabiData 0 truncated (both play to completion).
hanab.live H-H raw: 424 perfect, 339 natural, 292 strikeout, **420 truncated**
(of 1,475 replayable). Excluding truncated makes the corpus consistent with the
paper's "completed games" claim.

## New bot suspect from notes sweep (`src/notes_bot_sweep.py`)

will-hanabi-bot auto-annotates its per-game notes with `[INFO: v<ver>, <framework>]`.
Sweeping all exports: **`the account hashed a08ee96386551922`** carries the signature in all 8 of its games and
plays exclusively with **`the account hashed eb2b956a115dee2c`**. Both added to the exclusion list (Tier-2
"D — notes signature", hashed). Game 1762143 (known hit) is will-bot1, already excluded.
No other new suspects.

## Corpus impact (H-H)

| Corpus | games | plays | players | headline gap | mean score |
|---|---|---|---|---|---|
| v6 (bot-excl, truncated INCLUDED, no D) | 597 | 10,961 | 165 | +28.40 pp | — |
| + the notes-signature account and its exclusive partner (D) exclusion | 589 | 10,815 | 163 | +28.39 pp | — |
| **v7 (bot + D + truncated excluded)** | **425** | **9,017** | **155** | **+28.20 pp** | 18.5 |

Truncated exclusion removes 164 games; the notes-signature account and its exclusive partner removes 8. Headline gap
moves +28.40 → **+28.20 pp** (−0.2 pp; robust). Game-level-only robustness variant
(Tier-1 + completed): 598 games, 13,089 plays, **+29.49 pp** (was 819 / +29.8).
Tier-2 flagged accounts' own gap (completed): **+31.3 pp** (was +32.0).

## Mean game scores (Fig 1a / §4.4) — H-AI and AI-AI unchanged (0 truncated)

| Setting | v6 | v7 |
|---|---|---|
| H-H mean (completed) | 16.1 (n=597) | **18.5** (SD 9.6, n=425) |
| H-AI mean | 7.2 (n=2,040) | 7.2 (unchanged) |
| AI-AI mean | 10.7 (n=4,900) | 10.7 (unchanged) |
| Between ANOVA | F(2,7534)=350.21 | **F(2,7362)=429.82** |
| Tukey HH–HAI / HH–AA / HAI–AA | +8.9 / +5.4 / −3.5 | **+11.3 / +7.8 / −3.5** |

## Strike-out decomposition (Appendix I)

| | v6 | v7 |
|---|---|---|
| H-H strike-out rate | 15.4% (92/597) | **20.5%** (87/425) |
| H-AI / AI-AI strike-out | 57.4% / 26.3% | unchanged |
| Strike-out χ²(2) | 718.48 | **653.44** |
| Completed-game mean H-H | 19.1 (n=505) | **23.3** (SD 2.0, n=338) |
| Completed-game mean H-AI / AI-AI | 16.9 / 14.6 | unchanged |
| Completed Welch ANOVA | F(2,1012)=358.29 | **F(2,879)=2753.08** |
| Completed pairwise Welch t (HH-HAI/HH-AA/HAI-AA) | 6.24 / 13.50 / 23.98 | **45.43 / 73.52 / 23.98** |

The conditional-on-completion reversal (H-AI 16.9 > AI-AI 14.6) still holds. The
H-H completed-game mean rises to 23.3 because incomplete (terminated, score-0)
games are now excluded rather than dragging the mean down.

## Skill classification (excluding truncated raises player averages)

| Class | v6 | v7 |
|---|---|---|
| expert | 54 | **65** |
| intermediate | 44 | **48** |
| beginner | ~61 | **42** |
| total players | 165 | **155** |

## Table A2 (convention gap by pair type, v7)

| Pair | n (plays) | Conv. gap |
|---|---|---|
| E-E | 3,268 | +31.1 pp |
| E-I | 296 | +32.3 pp |
| E-B | 69 | +39.8 pp |
| I-I | 3,600 | +27.2 pp |
| I-B | 285 | +29.1 pp |
| B-B | 1,499 | +22.8 pp |

Per-play gap ANOVA F(5,9011)=16.50. Within-HH game-score ANOVA F(5,419)=32.72
(E-E 23.8, I-I 19.0, B-B 9.9).

## Logistic (Table A6, v7 H-H) & calibration

| Model | v6 AUC/R²/β | v7 AUC/R²/β |
|---|---|---|
| M1 | 0.801 / 0.176 / 5.12 | **0.811 / 0.189 / 5.43** |
| M2 | 0.814 / 0.192 / 4.79 | **0.828 / 0.213 / 5.06** |
| M3 | 0.834 / 0.216 / 4.66 | **0.848 / 0.243 / 4.93** |

Calibration bin [0.7,0.8]: actual loss 9.6% → **8.9%** (n=990), departure ~66 pp.
Zero-hint success: H-H 77.7% vs H-AI 15.7%, z=28.10 → **26.98**. H-H 0-hint gap +48 pp (unchanged).

## Unchanged (regression checks)
Full/Intentional/Outer own-play gaps (+18.0 / +0.0 / −0.0), Table 1 hint decomposition,
all H-AI and AI-AI numbers, χ²=691.89, F=121.91 (hint quality), seat-bug corrections.

---

**v7 = final.** The manuscript was renamed v6→v7 (`Convention_paper_2026_ED_v7.tex`);
the reproduction notebook is `reproduce_paper_figures_v7.ipynb`. The tex file's
git history under the v6 name contains the v7 edits. Headline: H-H corpus
425 games / 9,017 plays / 155 players, convention gap +28.2 pp.

---

# v8 additions (branch: revision/v8-review-commitments, 2026-08-06)

**Nothing changed; everything below was added.** Every previously reported number
(headline gaps, corpus counts, per-partner values, scores, hint-quality stats)
is identical to v7. v8 integrates the analyses promised in the NeurIPS 2026
author-response period (`Manuscript/review_round_2026_0724/v8_revision_plan.md`).

## New pipeline code (promoted from rebuttal/ into src/)

- `src/joint_posterior.py` — exact full-hand joint posterior (bitmask DP + brute force)
- `src/joint_replay.py` — corpus replay of both variants → `data/processed/joint_posteriors.csv`
  (118,550 plays; byte-identical to the Phase-1 rebuttal run) + timing JSON
- `src/cluster_stats.py` — cluster bootstrap CIs, CR0 sandwich SEs, paired contrasts
- Tests: 151 → 168 (8 joint-posterior + 9 cluster-stats)
- Notebook: `reproduce_paper_figures_v8.ipynb` = v7 + 6 new analysis cells (executed, 0 errors)

## New numbers (all first-time reports, not revisions)

- Joint-inference gaps: H-H +26.2 pp, H-AI +16.4, AI-AI −0.7 (marginal: +28.2/+16.9/−0.5);
  per-partner joint +24.1/+20.2/+6.2; deltas within v7 corpus: H-H 196↑/1,367↓ (17.3% change),
  H-AI 538↑/1,170↓ (11.0%), AI-AI 0↑/2,787↓ (4.4%); Brier 0.190→0.175 (H-H);
  brute-force verification max diff 0 on 591 spot-checks; 4 µs vs 280 µs/play, 74 s corpus.
- Cluster CIs: H-H game [+27.4,+29.0], player [+26.6,+29.9]; H-AI game [+16.2,+17.5],
  participant [+15.5,+18.3]; per-partner participant CIs Full [+23.4,+25.4],
  Intentional [+18.6,+23.0], Outer [+5.3,+8.0]. Zero-hint z: 26.98 unpooled (paper
  convention) / 21.91 pooled / 21.69 game-clustered / 15.79 participant-clustered.
  Full-vs-Outer: game-clustered z=23.82, participant-clustered z=6.28.
- Within-participant: 228 observed participants (122/58/48 played 1/2/3 AI types);
  Full−Outer Δgap +19.7 pp (22/0 sign, p=4.8e-07, ≥3 games/cell); Intentional−Outer
  +18.8 (20/1); Full−Intentional n.s. (−3.6 pp, p=0.47 at ≥1 game).
- Lives stratification: H-H +29.4/+26.2/+22.1 pp at 3/2/1 lives; excluding last-life
  plays +28.6 pp (H-AI +17.8, AI-AI −0.4).
- Ceiling ratios (gap ÷ mean posterior): H-H 84.2%, E-E 92.5%, B-B 65.5%;
  vs Full 63.1%, vs Intentional 54.1%, vs Outer 16.2%; AI-AI −6.1%.

## Two micro-corrections to previously printed CI digits

The v8 clustered-bootstrap implementation (`src/cluster_stats.py`, vectorized,
seed 42, 10,000 resamples) supersedes the v7 notebook's ad-hoc cells. Two CI
digits shift by 0.1 pp as a result (both immaterial): H-H game-cluster CI
[+27.3,+29.0] → [+27.4,+29.0]; Intentional play-level CI upper +21.7 → +21.8.
AI-AI play-level CI is now printed as [−0.7,−0.4] (v7 printed [−0.6,−0.4] from
a 2,000-resample cell).

## Rebuttal-vs-manuscript note

The Phase-1 rebuttal quoted joint-posterior delta direction counts computed over
all replayable raw games (H-H 971↑/3,753↓). The manuscript reports the
corpus-consistent counts (H-H 196↑/1,367↓ within the 9,017-play analysis corpus);
both are true of their respective populations, and all gap-level numbers agree.

## ERRATUM (2026-08-06, v8 audit)

The delta-direction counts quoted in the Phase-1 author responses — H-H
971 up / 3,753 down and H-AI 538 up / 1,734 down — were computed on the
**unfiltered** corpora (all replayable raw games for H-H; both seats for
H-AI), not on the analysis corpora. The correct analysis-corpus counts are
**H-H 196 up / 1,367 down** (17.3% of 9,017 plays changed) and
**H-AI 538 up / 1,170 down** (11.0% of 15,472 human plays). The qualitative
claim quoted to reviewers — deltas run in both directions in the human
corpora, all-downward in AI-AI — is unaffected, as are all gap-level
numbers. The manuscript (Appendix: joint variant) reports the
analysis-corpus counts.

# v9 recompute wave — JOINT posterior promoted to primary (2026-08-17)

**Definition change (preprint_build_plan.md §0):** the exact full-hand
joint-inference posterior becomes THE convention-gap posterior; the v8
per-card marginal becomes a named approximation (appendix). Every number
below is OLD (v8 marginal-primary) → NEW (v9 joint-primary). Where a line
is marked INVARIANT, the v9 rerun reproduced the v8 output exactly (these
quantities do not depend on the posterior).

**How computed:** `notebooks/reproduce_paper_figures_v9.ipynb` = the v8
notebook with one inserted cell that joins `data/processed/joint_posteriors.csv`
onto all three corpora (asserts: 0 unmatched joins; recomputed marginal ==
shipped posterior, max diff 4.8e-13) and swaps `posterior_p_life_loss` to the
joint value; then all 70 cells executed end-to-end, 0 errors. The LLM corpus
was recomputed separately via the new `src/llm_joint_replay.py` (see LLM
section). Manuscript tex NOT touched (stopped for review per instruction).

## Verification chain

- H-H / H-AI / AI-AI: joint CSV unchanged from v8 (byte-identical to the
  Phase-1 run; 591 brute-force checks, max diff 0; 118,550 plays).
- LLM corpus: 1,861-game snapshot corpus reproduced exactly from the raw
  logs (inclusion rule = 2026-04-24 generation snapshot; see
  `Manuscript/review_round_2026_0724/llm_corpus_manifest_2026-08-17.md`).
  `src/llm_joint_replay.py` verified the recomputed marginal equals the
  shipped `cg_records.json` posterior EXACTLY (float ==) on all 19,093
  records in order, plus outcomes and candidate counts; 0 replay-score
  mismatches; 96 brute-force joint spot-checks, max diff 0; 5 µs marginal /
  235 µs joint per play, 8 s wall.
- Consistency arithmetic: hint-strata n-weighted gaps reproduce the totals
  to machine precision in all three settings (H-H 484/5,884/2,649 → 9,017;
  H-AI 778/10,500/4,194 → 15,472; AI-AI 4,570/18,662/39,658 → 62,890).
  Per-partner human ns 4,769+5,122+5,581 = 15,472. Lives strata sum to
  corpus totals in all settings. Pair-type ns sum to 9,017 incl. the 69
  expert-beginner plays not shown in Table A2. LLM cells: 9,542 llm-side +
  9,551 rule-side = 19,093.

## Headline gaps (Table: tab:headline)

| Setting | mean post | gap | play CI | game CI | person CI |
|---|---|---|---|---|---|
| H-H old | 33.5% | +28.2 | [+27.5,+28.9] | [+27.4,+29.0] | [+26.6,+29.9] |
| H-H new | 31.4% | **+26.2** | [+25.5,+26.8] | [+25.3,+27.0] | [+24.5,+27.8] |
| H-AI old | 39.6% | +16.9 | [+16.3,+17.4] | [+16.2,+17.5] | [+15.5,+18.3] |
| H-AI new | 39.1% | **+16.4** | [+15.8,+16.9] | [+15.7,+17.1] | [+15.0,+17.8] |
| AI-AI old | 8.9% | −0.5 | [−0.7,−0.4] | [−0.7,−0.4] | — |
| AI-AI new | 8.7% | **−0.7** | [−0.9,−0.6] | [−0.9,−0.6] | — |

Actual loss rates INVARIANT (5.3 / 22.7 / 9.4%). Per-play deltas (as in v8
appendix, unchanged): H-H 196↑/1,367↓ (17.3% change), H-AI 538↑/1,170↓
(11.0%), AI-AI 0↑/2,787↓ (4.4%). Game-level-only H-H robustness variant
(Tier-1 only, 598 games / 13,089 plays): +29.5 → **+27.5**.

## Table 1 (gap by hint count, pp)

| Hints | H-H old→new | H-AI old→new | AI-AI old→new |
|---|---|---|---|
| 0 | +47.8 → **+46.2** | −12.0 → **−12.2** | −11.4 → **−12.8** |
| 1 | +38.5 → **+35.6** | +25.4 → **+24.7** | +1.2 → **+0.9** |
| 2+ | +1.7 → **+1.6** | +1.0 → **+0.9** | −0.1 → **−0.1** |

Rounded table prints as 46/36/2, −12/25/1, −13/1/−0 (v8: 48/38/2, −12/25/1,
−11/1/−0). Zero-hint success z INVARIANT: 77.7% vs 15.7%, z = 26.98
unpooled / 21.91 pooled / 21.69 game-clustered / 15.79 participant-clustered.

## Per-partner human gaps (tab:partner_main / Table A4)

| Partner | gap | play CI | game CI | participant CI | % of H-H |
|---|---|---|---|---|---|
| Full old | +24.6 | [+23.6,+25.6] | [+23.5,+25.6] | [+23.4,+25.4] | 87% |
| Full new | **+24.1** | [+23.2,+25.1] | [+23.1,+25.2] | [+22.9,+24.9] | **92%** |
| Intent. old | +20.8 | [+19.9,+21.8] | [+19.8,+21.8] | [+18.6,+23.0] | 74% |
| Intent. new | **+20.2** | [+19.3,+21.2] | [+19.2,+21.3] | [+18.0,+22.4] | **77%** |
| Outer old | +6.7 | [+5.7,+7.7] | [+5.7,+7.7] | [+5.3,+8.0] | 24% |
| Outer new | **+6.2** | [+5.2,+7.2] | [+5.2,+7.2] | [+4.8,+7.5] | 24% |

Mean posteriors: Full 39.0→38.5%, Intentional 38.4→37.9%, Outer 41.1→40.6%
(loss rates invariant: 14.4/17.6/34.4%). NOTE the %-of-H-H column moves
because BOTH numerator and denominator change (H-H +28.2→+26.2).

**AI-side per-partner gaps (Fig 2):** Full's own-play gap **+18.0 → +16.9**
[+16.0,+17.8] (n = 5,965) — this is the "+18.0 pp human reference" quoted
throughout the LLM appendix; every such quote must become +16.9 at
integration. Intentional and Outer AI-side stay +0.0/−0.0.
Full vs Outer Partner Loss z INVARIANT (−24.61 Welch / −23.82 game /
−6.28 participant). Full vs Intentional Partner Loss z INVARIANT (−4.39).

## Skill / pair-type (Table A2, App N)

E-E +31.1→**+29.1**; E-I +27.5→**+25.2**; I-I +27.5→**+25.4**;
I-B +29.2→**+27.2**; B-B +22.8→**+21.1**. ANOVA F(4,9012) 16.89→**16.41**
(p 8.3e-14→2.1e-13); Tukey significance pattern unchanged (I-B vs B-B
0.0258→0.0351, still <0.05). 3×3 subject×partner matrix range
+22.8…+41.9 → **+21.1…+40.2** (loss rates invariant). App N sentence
updates: per-subject-pair range "+22.8 to +31.1" → "+21.1 to +29.1";
"B-B (+22.8) sits just below Full (+24.6)" → "B-B (+21.1) sits below Full
(+24.1)" (ordering unchanged, margin widens 1.8→3.0 pp).

## Per-AI hint-count breakdown (App H)

Full −5.7/+32.9/+2.0 → **−5.0/+32.3/+1.9**;
Intentional −14.5/+31.2/+1.2 → **−14.5/+30.4/+1.1**;
Outer −14.6/+11.5/+0.3 → **−16.1/+10.8/+0.3** (ns invariant:
220/3,542/1,007; 390/3,552/1,180; 168/3,406/2,007).

## Table A5 (Full mechanism)

Full: mean posterior 0.334→**0.323**; frac p̂>0.5 32.6%→**30.6%**;
frac p̂=0 37.6%→**38.4%**. All hint-structure rows and Player Loss
INVARIANT. Intentional/Outer columns unchanged (0.001/0.000).

## AI-AI 7×7 gap matrix (App)

Zero rows (Outer/IGGI/Intentional/Simple) stay exactly 0. VanDenBergh row
+1.2/+2.9/+0.7/+0.8/+0.2/−2.8/+2.1 → **+0.8/+2.3/+0.5/+0.6/−0.2/−2.9/+1.9**;
Piers row −0.8/+0.4/+1.7/+0.7/−1.4/−3.1/+2.6 →
**−1.1/−0.2/+1.4/+0.4/−1.8/−3.5/+2.6**; Flawed row
−4.8/−7.6/−6.7/−6.6/−1.8/−5.2/+0.5 → **−5.6/−8.3/−7.4/−7.3/−2.5/−6.0/+0.5**.

## Logistic regressions (Table A6)

| Dataset/model | AUC | pseudo-R² | β(post) |
|---|---|---|---|
| human M1 | 0.8107→**0.8146** | 0.1891→**0.1935** | 5.43→**5.31** |
| human M2 | 0.8283→**0.8330** | 0.2133→**0.2189** | 5.06→**5.03** |
| human M3 | 0.8476→**0.8518** | 0.2432→**0.2489** | 4.93→**4.92** |
| agent M1 | 0.9799→**0.9802** | 0.6306→**0.6334** | 9.41→**9.62** |
| agent M2/M3 | 0.9798→**0.9802** | 0.6370→**0.6399** | 8.16→**8.36** |
| human_ai M1 | 0.8682→**0.8705** | 0.3428→**0.3484** | 5.99→**6.01** |
| human_ai M2 | 0.8834→**0.8856** | 0.3651→**0.3707** | 5.78→**5.80** |
| human_ai M3 | 0.9093→**0.9115** | 0.4207→**0.4277** | 6.01→**6.07** |

Calibration: Brier/AUC per setting now equal the v8 appendix joint values
(H-H 0.1753/0.8146; H-AI 0.1588/0.8705; AI-AI 0.0336/0.9802) — the joint
posterior is (slightly) better calibrated in every setting, consistent
with v8's report.

## Failure taxonomy (Table A11; % of failures, totals INVARIANT)

H-H: blind 17.9→**17.4**; misread 20.2→**24.4**; calculated 0.0→0.0;
desperate 18.1 (inv); convention-failure 43.7→**39.5** (476 failures).
vs Full: 12.1→12.2 / 12.7→12.7 / 0.3 / 29.2 / 45.2→45.2 (686).
vs Intentional: 24.6→24.5 / 9.9 / 0.2 / 18.6 / 46.3 (903).
vs Outer: 3.5→3.4 / 14.0→**14.9** / 0.1 / 30.1 / 52.3→**51.4** (1,921).
Cascade: Full −4.2→−4.3, Intentional −3.0→−3.0, Outer −7.7→−7.6 pp.

## Lives stratification

H-H 3/2/1 lives: +29.4/+26.2/+22.1 → **+27.7/+23.3/+19.2**; excluding
last-life +28.6 → **+26.6** (all-plays +26.2). H-AI: +18.3/+16.7/+12.7 →
**+17.9/+16.2/+11.8**; excluding +17.8 → **+17.4**. AI-AI:
−0.1/−1.5/−2.7 → **−0.2/−2.0/−3.2**; excluding −0.4 → **−0.5**.

## Ceiling ratios (gap ÷ mean posterior)

H-H 84.2→**83.2%**; E-E 92.5→**92.1%**; B-B 65.5→**63.7%**;
H-AI all 42.7→**41.9%**; vs Full 63.1→**62.7%**; vs Intentional
54.1→**53.5%**; vs Outer 16.2→**15.3%**; AI-AI −6.1→**−8.5%**.

## Within-participant paired contrasts

≥1 game/cell: Full−Outer +15.8 [+11.9,+19.7] (57/12) → **+16.0
[+12.2,+19.8] (57/12)**; Intentional−Outer +18.9 [+14.7,+23.2] (57/7) →
**+18.8 [+14.7,+22.9] (58/6)**; Full−Intentional −3.6 [−8.1,+0.8] (31/38,
sign-p 0.47) → **−3.4 [−7.8,+0.9] (32/37, sign-p 0.63)** — still n.s.
≥3 games/cell: Full−Outer +19.7 [+16.2,+23.3] (22/0) → **+19.7
[+16.4,+23.1] (22/0, sign-p 4.8e-07)**; Intentional−Outer +18.8 (20/1) →
**+18.4 [+14.0,+22.7] (20/1)**; Full−Intentional +1.3 (12/6, p 0.24) →
**+1.8 [−2.4,+6.0] (13/5, sign-p 0.096)** — still n.s. dLoss columns and
the 83.3%/77.1% all-three-AIs shares INVARIANT. Participant structure
INVARIANT (228; 122/58/48).

## Convention learning (App K)

OLS H-H per-player: positive-slope share 70.0%→**75.0%** (sig-positive
1→2, sig-negative 1→1); mean slope +0.0038→**+0.0037**/game; by skill
b/i/e +0.0108/+0.0024/−0.0004 → **+0.0109/+0.0021/−0.0003**.
Skill-score OLS: skill main effect +0.0136 (t=+5.1)→**+0.0136 (t=+5.2)**;
game_seq −0.000107 (p 0.82)→**−0.000040 (p 0.93)**; interaction n.s.
both; R² 0.124→**0.127**; ΔBIC continuous-preferred −25.0→**−23.9**.
H-AI OLS: pooled slope −0.000335 (p 1e-4) INVARIANT to 3 sig figs;
full-model game_seq −0.000234 (p 0.113)→**−0.000261 (p 0.075)** — still
n.s.; partner full +0.0415→**+0.0393**; partner outer −0.169→**−0.172**;
R² 0.217→**0.220**. Qualitative story unchanged.

Bambi hierarchical H-H: β +0.001822 [+0.000186,+0.003738], P(β>0)=0.984,
σβ 0.00139, 20/20 positive → **β +0.001890 [+0.000039,+0.004260],
P(β>0)=0.984, σβ 0.00166, 19/20 positive** (~5 games/pp both). HDI still
excludes zero. Sampling: 89 divergences, R-hat max 1.01 (v8: 10, 1.00) —
MCMC noise at this data size; consider target_accept 0.95 at integration.
Bambi H-AI: slopes Full 0.000045→**0.000062**, Intentional
0.000022→**0.000007**, Outer 0.000174→**0.000195**; every 95% HDI still
includes zero — "no learning with AI partners" unchanged.

## Verified INVARIANT (v9 outputs byte-identical to v8)

Corpus counts (425/9,017/155; 29,049/15,472; 62,890; hint records
195,634); all strict/lenient score statistics, score ANOVAs and Tukey
tables, uncensored-score diagnostic; playability χ²(2)=691.89 and
disambiguation ANOVA; Full-vs-Intentional and Full-vs-Outer loss-rate
z-tests; zero-hint success rates and all four z variants; failure counts
per setting; participant×partner structure; learning-corpus sizes
(20 players/415 obs; 23 trials/1,376 obs); pair-type play counts.

## LLM corpus: stage-1 verification chain (2026-08-17)

- Inclusion rule 2,150→1,861 recovered: the corpus is the **2026-04-24
  generation-completion snapshot** (`LLM_hanabi_all_2026_0424.zip`), not a QC
  filter. 39 conditions = 43 raw `llm_vs_*` dirs minus 4 Qwen-CoT dirs generated
  later; three conditions are seed prefixes (Mini intentional_cot_medium 1–45,
  Qwen iggi_cot 1–8, Qwen intentional_cot 1–8). 36×50+45+8+8 = 1,861.
  All 1,861 snapshot files sha256-identical to the current raw tree.
  Manifest: `Manuscript/review_round_2026_0724/llm_corpus_manifest_2026-08-17.md`.
- `src/llm_joint_replay.py` replays the raw tree restricted to the snapshot rule
  with the LLM-format engine (colors R,B,G,W,Y = 0–4; in-place draws) and
  **verifies the recomputed marginal posterior equals the shipped
  `cg_records.json` value exactly (== on floats) on all 19,093 records, in
  order, plus actual_fail and num_candidates; 0 score mismatches.** The
  joint posterior reuses the falling-factorial bitmask DP from
  `src/joint_posterior.py`; 96 brute-force spot checks (every 197th
  constrained play), max |DP − brute| = 0. Timing: 5 µs marginal / 235 µs
  joint per play, 8 s wall. Output: `data/processed/llm_joint_posteriors.csv`
  (+ timing and fallback-count JSONs).

## Fallback-sensitivity analysis (new v9 item)

Per-action `_parse_ok` flags across the 1,861-game corpus (LLM side: 52,686
actions, 52,138 parse-ok):

- **Fallback-substituted actions: 548 total — every one a DISCARD.**
  0 PLAY, 0 HINT_COLOR, 0 HINT_RANK. All 9,542 LLM play records have
  `_parse_ok = true` (rule-side actions carry no flag).
- Fallbacks concentrate in Qwen3.6-A3B no-CoT conditions (36–97 per
  condition; 3.6% of Qwen no-CoT LLM actions) plus 1 in GPT-5.4-mini
  flawed+CoT and 13 across Qwen+CoT conditions; zero in all GPT-5.4 and
  almost all GPT-5.4-mini conditions.
- **Consequence: restricting every Appendix M cell to parse-ok plays changes
  NOTHING — the play sets are identical, so every gap moves by exactly
  0.0 pp**, including Qwen3.6-A3B × Full (+6.3 pp marginal / +5.7 pp joint).
  The "all plays vs parse-ok-only" side-by-side table is therefore the
  identity; no cell moves by more than 1 pp (none moves at all).
- Caveat recorded for the appendix text: fallback discards still occurred
  *within* games and shape subsequent states; they are properties of the
  generation harness (a discard fallback on unparseable output), not of the
  corpus filter, and cannot contaminate play-action gap estimates.

## LLM corpus under joint-primary (marginal → joint, play-level, pp)

LLM-side (Appendix M table cells; CI = play-level bootstrap B=2,000,
default_rng(42) per cell):

| Model | Partner | n | marg | joint | Δ | joint 95% CI |
|---|---|---|---|---|---|---|
| GPT-5.4 | Flawed | 87 | +0.56 | +0.56 | 0.00 | [−1.09, +2.78] |
| GPT-5.4 | Simple | 341 | +0.41 | +0.41 | 0.00 | [+0.00, +0.99] |
| GPT-5.4 | Internal | 340 | +0.11 | +0.12 | +0.00 | [−0.52, +0.68] |
| GPT-5.4 | IGGI | 345 | −0.06 | −0.06 | 0.00 | [−0.35, +0.15] |
| GPT-5.4 | Outer | 227 | −0.26 | −0.26 | 0.00 | [−1.35, +0.72] |
| GPT-5.4 | Piers | 323 | −0.69 | −0.73 | −0.04 | [−1.76, +0.23] |
| GPT-5.4 | VdB | 290 | +0.00 | +0.00 | 0.00 | [−0.34, +0.34] |
| GPT-5.4 | Intentional | 178 | +0.33 | +0.05 | −0.28 | [−0.34, +0.44] |
| GPT-5.4 | Full | 158 | +1.31 | +1.31 | 0.00 | [−0.02, +2.96] |
| GPT-5.4-mini | Flawed | 172 | −1.26 | −1.30 | −0.04 | [−3.53, +1.11] |
| GPT-5.4-mini | Simple | 344 | −0.16 | −0.15 | +0.01 | [−0.50, +0.29] |
| GPT-5.4-mini | Internal | 287 | −0.61 | −0.58 | +0.02 | [−1.24, −0.10] |
| GPT-5.4-mini | IGGI | 323 | −0.97 | −0.94 | +0.03 | [−1.55, −0.40] |
| GPT-5.4-mini | Outer | 276 | −1.42 | −1.23 | +0.18 | [−3.06, +0.71] |
| GPT-5.4-mini | Piers | 250 | −1.16 | −1.13 | +0.03 | [−2.25, −0.14] |
| GPT-5.4-mini | VdB | 335 | −1.12 | −1.18 | −0.05 | [−2.33, +0.08] |
| GPT-5.4-mini | Intentional | 194 | −1.50 | −1.58 | −0.07 | [−3.66, +0.71] |
| GPT-5.4-mini | Full | 190 | −1.33 | −1.44 | −0.11 | [−4.46, +1.69] |
| GPT-5.4-mini+CoT | Flawed | 123 | −0.86 | −0.86 | +0.01 | [−3.05, +1.10] |
| GPT-5.4-mini+CoT | Simple | 389 | −0.45 | −0.45 | 0.00 | [−0.91, −0.09] |
| GPT-5.4-mini+CoT | Internal | 343 | −0.61 | −0.64 | −0.03 | [−1.53, +0.11] |
| GPT-5.4-mini+CoT | IGGI | 378 | +0.29 | +0.30 | +0.00 | [−0.61, +1.30] |
| GPT-5.4-mini+CoT | Outer | 238 | +0.14 | +0.14 | 0.00 | [−1.52, +1.78] |
| GPT-5.4-mini+CoT | Piers | 306 | +0.38 | +0.29 | −0.09 | [−0.48, +1.15] |
| GPT-5.4-mini+CoT | VdB | 354 | −0.06 | −0.06 | +0.01 | [−0.60, +0.53] |
| GPT-5.4-mini+CoT | Intentional† | 203 | +0.95 | +0.96 | +0.01 | [−0.61, +2.63] |
| GPT-5.4-mini+CoT | Full | 171 | −0.20 | −0.24 | −0.03 | [−1.16, +0.76] |
| Qwen3.6-A3B | Flawed | 121 | −1.19 | −1.21 | −0.02 | [−3.98, +1.83] |
| Qwen3.6-A3B | Simple | 340 | −1.05 | −1.07 | −0.02 | [−2.33, +0.13] |
| Qwen3.6-A3B | Internal | 345 | −0.70 | −0.73 | −0.03 | [−1.85, +0.35] |
| Qwen3.6-A3B | IGGI | 295 | −0.90 | −0.92 | −0.02 | [−2.50, +0.56] |
| Qwen3.6-A3B | Outer | 261 | −2.78 | −2.89 | −0.12 | [−4.54, −1.28] |
| Qwen3.6-A3B | Piers | 294 | −0.72 | −0.83 | −0.11 | [−2.10, +0.50] |
| Qwen3.6-A3B | VdB | 289 | −0.36 | −0.42 | −0.06 | [−1.88, +1.01] |
| Qwen3.6-A3B | Intentional | 153 | +0.79 | +0.75 | −0.05 | [−1.92, +3.80] |
| **Qwen3.6-A3B** | **Full** | **95** | **+6.28** | **+5.75** | **−0.53** | **[+2.19, +9.55]** |
| Qwen3.6-A3B+CoT | IGGI† | 52 | +1.09 | +0.45 | −0.64 | [−1.60, +3.30] |
| Qwen3.6-A3B+CoT | Intentional† | 20 | +4.17 | +4.17 | 0.00 | [+0.00, +10.83] |
| Qwen3.6-A3B+CoT | Full | 112 | +1.86 | +1.86 | 0.00 | [−0.75, +4.56] |

Headline consequences under joint:
- **Qwen3.6-A3B × Full stays the only full-run LLM-side cell with a CI
  excluding zero: +6.3 → +5.7 pp [+2.2, +9.6]** (still ~half of Full's
  own-play +12 pp in the same games, still vanishing with CoT).
- Rule-side (Panel A, Full's own plays): GPT-5.4 +24.85→+24.66; mini
  +30.34→+29.77; mini+CoT +37.77→+37.80; Qwen +12.08→+11.85; Qwen+CoT
  +13.61→+13.04. Range +11.9…+37.8 pp (was +12.1…+37.8); **still 3 of 5
  above the +18.0 human reference** (whose own joint value shifts — see
  H-AI per-partner section).
- Pooled LLM side: −0.34 → −0.37 pp [−0.58, −0.17] (197/9,542 plays change,
  82 up). Pooled rule side: +4.02 → +3.90 pp [+3.44, +4.39] (428/9,551
  change, 132 up).
- Consistency: LLM-side cell ns sum to 9,542; rule-side to 9,551;
  total 19,093. †-flagged partial cells per the snapshot manifest.

## Not yet integrated (deliberate — stopped for review)

- Manuscript tex untouched. The abstract/intro/discussion numbers implied
  by this table (headline +26.2/+16.4/−0.7; Full own-play +16.9; per-partner
  +24.1/+20.2/+6.2; Table 1 46/36/2; A2 range +21.1…+29.1) are NOT yet in
  the tex.
- v9 notebook cells 57–63 (LLM appendix) still load the marginal
  `llm_cg_records.json`; switch them to `llm_joint_posteriors.csv` at
  integration (joint per-cell values already computed in
  `output/llm_joint_cell_gaps.json`). Cell 65 (v8 "marginal vs joint"
  appendix cell) is degenerate in v9 (compares joint to itself); rewrite as
  the inverse "marginal approximation" appendix cell at integration.
- Figures: 7 posterior-dependent PNGs in `output/figures/` regenerated under
  joint (figure1 gap+calibration, per-partner bars, gap-all-settings,
  crossplay heatmaps ×2 + combined, logistic ROC + coefficients); score
  figures unchanged. Working tree left uncommitted for review.
- Every v8-marginal value in this section remains the "named approximation"
  number for the new appendix — this table doubles as its old→new map.

## v9 build addendum (2026-08-17, second half: tex integration)

- **Bambi rerun at target_accept 0.95 (decision item):** H-H model now samples
  cleanly (divergences 89→5, R-hat max 1.0000) and the slope's 95% HDI
  **includes zero**: β = +0.00184/game, HDI [−0.00010, +0.00382], P(β>0) =
  0.980, σβ = 0.00161, 19/20 players positive. Per the pre-agreed rule, App N
  wording softened to "probable but not statistically credible." H-AI model:
  divergences persist (284; 10-participant limitation), all per-partner slope
  HDIs still include zero (Full +0.00006 [−0.00121, +0.00151] P 0.44;
  Intentional +0.00001 [−0.00131, +0.00142] P 0.40; Outer +0.00019
  [−0.00072, +0.00188] P 0.63; σβ 0.00083). These ta=0.95 values are the v9
  manuscript numbers and supersede the ta=0.9 values in the wave section above.
- **ERRATUM (found during integration):** v8 tex Table A11's H-H column
  (15.6/21.1/0.0/14.4/48.6, total 617) and the cascade sentence (−5.8 Outer /
  −0.2 Full) did NOT match the audited pipeline output at v8
  (17.9/20.2/0.0/18.1/43.7, total 476; cascade −7.7/−4.2): the H-H failure
  taxonomy was never regenerated after the v6/v7 corpus change. v9 ships the
  pipeline values under joint (H-H 17.4/24.4/0.0/18.1/39.5, total 476;
  cascade Outer −7.6 / Full −4.3 / Intentional −3.0) and the §5 sentence was
  rewritten accordingly (the Outer-vs-Full cascade contrast is graded, not
  categorical as v8 implied).
- Additional joint-value computations for tex spots not covered by the wave:
  Tier-2 bot-account gap +31.3 → **+29.8** (App B); AI-AI per-subject pooled
  own-play band [−5.2, +1.1] → **[−5.8, +0.7]** (Bergh +0.7, Flawed −5.8,
  other five within ±0.6); H-H calibration bin p̂∈[0.7,0.8): loss 8.9% →
  **9.5%**, departure 66 → **64 pp**; H-H zero-hint mean posterior 0.70 →
  **0.69**; LLM-side pooled-per-config gaps across HOAD partners all within
  ±1.5 → **±1.2 pp**; posterior invariants 69,848 p=0 / 1,625 p=1 →
  **70,247 / 1,641** (over the same 100,956 plays); brute-check total 840 →
  **936** (+96 LLM).
- **v9 tex built:** `Manuscript/current/Convention_paper_2026_ED_v9_preprint.tex`
  (34 pp, 2×pdflatex, 0 undefined refs). §3.2 is now a five-step definition
  (steps 1–4 per-card walk-through with the 5/8 worked example — unchanged
  under joint since the example's other cards are unconstrained — plus step 5
  exact full-hand conditioning); app:joint inverted to "per-card
  approximation"; every +18.0 Full own-play reference is now +16.9 (LLM
  appendix reference line, figure band [16.0, 17.8]); fallback caveat added to
  App M; Hu et al. 2021 integrated (Related Work paragraph, §3 grounded-belief
  sentence, Discussion dose-response + score-space counterpart, bib entry);
  new App "Known-Answer Validation on a Designed Convention Hierarchy (OBL)"
  with report v4.5 Tables 2–3, the corrected cross-play score **20.90**, the
  OBL1-row zero-point paragraph (+1.0/+0.6/+0.3/+0.1 vs OBL2–5), and the
  GX10-audited item-7 decomposition (1-hint gap +5.00→+2.50 self→×OBL5,
  within-stratum term 72%); figure `figures/obl_validation.png` drawn from the
  verified Table-2 values. arXiv-ization: preprint style option, checklist
  removed (~29k chars), no submission-process language remains (grep clean;
  the `neurips2026_supplementary.zip` artifact name and style-file comment are
  retained deliberately).
- Notebook `reproduce_paper_figures_v9.ipynb` updated: LLM cells now load
  `llm_joint_posteriors.csv` (joint primary; per-card kept per record); Figure
  A7 reference line +16.9 with band [16.0, 17.8]; cell 65 rewritten as the
  per-card-approximation appendix cell; bambi H-H cell at target_accept 0.95.

- CI-convention note (LLM cells): the per-cell table in the wave section used a
  fresh `default_rng(42)` per cell; the executed v9 notebook (canonical per the
  house rule) draws the panel bootstraps from one sequential rng, giving
  Qwen×Full joint CI [+2.3, +9.7] (vs [+2.2, +9.6] per-cell). The tex quotes
  the notebook values. Point estimates are identical under both.

## v9 external-audit fixes (2026-08-17)

- Table A6 + Appendix F prose updated to the joint logistic values (the wave
  section's numbers; the v9 build had left the v8 marginal values in place):
  H-H M1 0.815/0.194/5.31, M2 0.833/0.219/5.03, M3 0.852/0.249/4.92; AI-AI M1
  0.980/0.633/9.62; H-AI M1 0.871/0.348/6.01, M3 0.912/0.428/6.07; ΔR² 0.057.
- §5 within-participant echo corrected to the v9 values (−3.4 pp [−7.8, +0.9],
  sign-test p = 0.63); App C erratum sentence qualifies −0.5 pp as the
  then-primary per-card value; App G notes the H-AI model's persisting 284
  divergences (10-participant caveat, fixed-effect R̂ ≤ 1.02).
- Skill-table Ns note: Table A2's E-I = 194, I-I = 3,708, I-B = 279 reflect the
  v7 completed-games corpus, where excluding truncated games reclassified
  several singleton-game players' skill levels (documented v6→v7); the v9 joint
  swap changes the gap values only, never the Ns.
- Bundle gains `data/processed/llm_per_condition_tables.md` (39-condition
  joint + per-card table, †-flagged partial runs) and
  `data/processed/llm_corpus_manifest.md` (public corpus definition +
  fallback audit), closing the App M supplementary-material pointer. The OBL
  derived JSONs + generation scripts ship as a separate release (tex sentence
  adjusted accordingly); OBL game logs stay out (CC BY-NC).

## v9 Tier-1 wording correction (2026-08-18)

- Tier-1 bot-exclusion wording corrected to match the implementation (README,
  corpus.py docstring, manuscript Appendix B + §3.3): the filter drops games in
  which a verified bot account **made a play**, not games it merely appears in.
  Boundary case disclosed: game 1762152 (will-bot account clued/discarded only)
  is retained, contributing 6 human plays; strict reading would give 424 games /
  9,011 plays, joint gap +26.16 → +26.18 pp (marginal +28.20 → +28.21). No
  numbers changed — documentation defect only (GX10 audit F1, decision Makoto
  2026-08-18).

## v9.1 editorial pass (2026-08-31)

- Wording-only revision of the preprint tex per the scientific-writing review
  (scientific_writing_review_v9_2026-08.md): abstract replaced with the review's
  250-word version (1,660 chars, within the arXiv 1,920 cap); intensifiers/
  hedges/figure-subject sentences fixed throughout main text and appendices;
  five interpretive §4 passages softened or relocated to §5; Results anchors
  added for the ceiling fractions (83.2/92.1/62.7/15.3%) and failure-mode/
  cascade numbers; Figure 1 caption trimmed to descriptive; findings count
  unified to four (Intro gains the OBL known-answer sentence). Zero numeric
  changes beyond three listed corrections: caption/§4.4 lenient-score
  arithmetic 12.1/11.6/+0.4 → 12.07/11.63/0.44; §5 Full play-time posterior
  0.33 → 0.32 (Table A10 joint value 0.323); §3.3 gains the "(228 with logged
  completed games)" clause. NB: review's §4.1 App L replacement said "58 of
  66"; Table A7's actual n is 64 (58/6) — the tex uses 58 of 64.

## v9.2: OBL validation promoted to §4.5 (2026-09-01)

- New §4.5 "Known-Answer Validation on a Designed Convention Hierarchy": the
  core result table (tab:obl) and monotone-gap figure (fig:obl) MOVED from
  Appendix X (single copies; appendix keeps the full treatment — strata table,
  item-7/Kitagawa decomposition, verification, license note). §4 roadmap,
  Intro OBL sentence, Related Work pointer, and the Discussion dose-response/
  Limitations sentences repointed at §4.5 (Discussion no longer introduces the
  numbers). No numeric changes; every promoted value verified against the GX10
  audit recompute (manuscript_audit/results_out/recompute_ms_pipeline.json:
  gaps +1.57/+12.40/+16.91/+19.88/+21.68, cross-play +1.22, OBL5 1-hint +34.4,
  interlevel decay +1.0/+0.6/+0.3/+0.1 — all exact; published CIs match the
  shipped obl/gap_results.json exactly, audit CIs agree within bootstrap RNG
  noise ≤0.02 pp). One rounding slip caught by that verification and corrected
  in the moved table: OBL4 mean posterior printed 22.4% but the value is
  22.35% → 22.3% (both audit and shipped JSON agree). Main text now ~15 pp
  (§4.5 p.10, Conclusion p.14); PDF 35 pp, 0 undefined refs.

## v9.2 addendum (2026-09-07): Table 3 promoted to bar graph (arXiv version)

New Figure (fig:hintcount_bars, `figures/hintcount_bars.png`) inserted after Table 3;
table retained (it carries the success rates). No number changes. Point estimates
recomputed from corpus CSVs + rebuttal/joint_posteriors.csv and matched the printed
Table 3 exactly; 95% game-cluster bootstrap CIs (2,000 draws, seed 42) computed fresh:

| Stratum | Human-Human | Human-AI | AI-AI |
|---|---|---|---|
| 0 hints  | +46.22 [+41.30, +50.63] (n=484)  | -12.15 [-14.82, -9.45] (n=778)   | -12.77 [-13.91, -11.54] (n=4,570) |
| 1 hint   | +35.57 [+34.57, +36.51] (n=5,884) | +24.67 [+23.82, +25.47] (n=10,500)| +0.89 [+0.51, +1.28] (n=18,662)  |
| 2+ hints | +1.62 [+1.22, +2.04] (n=2,649)   | +0.91 [+0.50, +1.34] (n=4,194)   | -0.12 [-0.17, -0.06] (n=39,658)  |

Stratum ns match the printed totals (H-H 9,017; H-AI 15,472; AI-AI 62,890).
Compile: pdflatex x3, 0 undefined refs, 35 pp. Figure also copied to
output/figures/hintcount_bars.png. Downstream figure numbers shift by one
(per-partner bars now Fig 3, etc.) - all \ref-based, no hard-coded figure numbers found.

## v10 (computational-audit items 1–5, 2026-09-07) — code side

- **Item 1 (play-signal accuracy)**: the `playable_cards_touched > 0` proxy is
  replaced by the observed outcome of the play at (game_id, turn+1), linked via
  the new `link_hint_to_next_play` helper (src/analysis.py; dead look-ahead
  `pass` block removed). Old proxy → new observed post-hint human failure:
  Full 6.9 → **7.6%** (linked n = 3,631), Intentional 6.3 → **8.3%** (3,676),
  Outer 22.2 → **30.8%** (4,253).
- **Item 2 (AI-AI per-agent game scores)**: selection switched from "games in
  which the agent made a play" (7,863 subject-game units; Flawed-partner ≈0
  games silently dropped) to the first-named agent of the pairing file — 700
  games per agent, 4,900 total, each game once. Old → new means (old rule recomputed
  from the shipped CSV; old n in parens): IGGI 15.28 (1,119) → **13.68**
  (SD 5.92), Piers 15.20 (1,132) → 13.57 (6.02), Bergh 14.56 (1,072) → 12.85
  (5.76), Outer 14.55 (1,041) → 12.68 (5.70), Simple 13.09 (1,124) → 11.35
  (5.15), Intentional 12.80 (1,075) → 10.92 (5.06), Flawed 0.09 (1,300) → 0.05
  (0.71); all new n = 700. Within-AI-AI ANOVA
  F(6, 4893) = 4020 (stale; notebook printed F(6, 7856) = 3759.66) →
  **F(6, 4893) = 601.39**; Tukey: IGGI≈Piers p=1.00, Bergh≈Outer 0.996,
  Simple≈Intentional 0.704, IGGI>Bergh 0.045, IGGI>Outer 0.006, Piers>Outer
  0.023, Piers-Bergh 0.130 n.s., others <0.001. 7×7 score matrix now the
  unordered pairing (200 games/cell, 100 diagonal, symmetric); only the Flawed
  row/column changes visibly (0.0–0.4, e.g. old IGGI-Flawed 2.1 → 0.4).
  NOTE: the IGGI↔Outer cell is exactly 16.0500 (sum 3210 / 200 games) — a
  1-dp rounding tie; the figure's f-string prints **16.1**, the audit file's
  expected table said 16.0. The audit's own ordered-matrix printout (16.1 /
  16.0 for the two orderings) matches our computation at full precision; the
  tex prints this cell nowhere.
- **Item 3**: no code change (rule verified correct); denominator note added to
  the plot_trustworthiness_inversion docstring.
- **Item 4**: no code change; Figure 1 not regenerated.
- **Item 5 (df printouts)**: cell 66 now prints the Welch df from scipy
  (10,141.8; was reporting only t) — t = −24.61 unchanged; cell 18 residual df
  fixed from `len(human_df) − k` (9,012) to plays-entering-ANOVA (**8,943**,
  N = 8,948) — F = 16.41 unchanged; cell 32 prints the H-AI unit (2,035 games
  containing a human play; F(2, 2032) = 243.21 unchanged) and the AI-AI unit
  (700 games per agent / 4,900 total).
- Figures regenerated: game_scores_all_settings.png (Fig A6),
  crossplay_combined.png (Fig A8; panel (a) byte-checked unchanged in values),
  crossplay_score_heatmap.png (same fix). phase8_hint_quality.png re-executed
  byte-identical. Copied A6/A8 to Manuscript/current/figures/.
- Tests: 168 → **170 passed** (new: first-mover partition 700×7=4,900;
  link_hint_to_next_play synthetic). Manuscript-side entries to be added by
  Cowork after reconciliation.

## v10 (computational-audit items 1–17, 2026-09-07) — manuscript side

File: `Manuscript/current/Convention_paper_2026_ED_v10.tex/.pdf` (copy of v9.2 + edits; 35 pp,
0 undefined refs, converged, no overfull box > 10 pt). All values below were recomputed in Cowork
from the shipped CSVs independently of the audit scripts before being written.

Items 1–5 (14 edits):
- §4.3: "22.2% of subsequent human plays failed; 6.3–6.9%" (proxy) → observed failure of the human
  play at turn t+1: Outer 30.8% (n=4,253), Full 7.6% (3,631), Intentional 8.3% (3,676).
- §4.4 / §5 / App. P / Fig. A6 caption / Fig. A8 caption: AI-AI per-agent scores → first-moving
  agent rule (700 games each): IGGI 13.7, Piers 13.6, Bergh 12.8, Outer 12.7, Simple 11.4,
  Intentional 10.9, Flawed 0.05; "12.8–15.3 / 150-fold" → "10.9–13.7 / ≈0"; F(6,4893)=4020 →
  601.39 + Tukey pattern; Fig. A8(b) now the unordered pairing (200 games/cell, symmetric).
- §3.4: Player Loss over 1,300 games, Partner Loss over 1,200 non-mirror games (Flawed partners
  n=324); "7×100=700 games per AI" removed.
- §4.1 / §3.1 control (i) / Fig. 1 caption / App. convgap_by_subject: "on the diagonal at every
  risk level" → within 3 pp for p̂≤0.5 (92% of AI plays); 0.5–0.8 bins (95% Flawed) 10–12 pp
  ABOVE the diagonal (audit's draft said "below"; Fig. 1c plots observed loss on y). The audit's
  "six of seven agents calibrated at every risk level" NOT adopted: per-agent bins show Piers
  −9.4 pp at [0.4,0.5) (n=471) and Bergh +5.6 pp at [0.2,0.3) (n=592), now disclosed in App.
- App. H: t(10348) → Welch t=24.61, df=10,142. App. I: F(4,9012) → F(4,8943), N=8,948.
  App. P: F(2,2032)=243.21 "over the 2,035 games containing a human play".

Items 6–17 + extras (17 edits):
- App. E: AUC 0.868→0.870 → 0.868→0.871 (0.87051; matches Table A3); "mean |Δ| 2.1 pp" →
  "2.1 pp over all plays, 12.3 pp over the plays that differ" (recomputed 2.13 / 12.28).
- App. D, App. E: 118,550 → 118,168 plays.
- §5, App. W: +11.9 → +11.8 (Qwen3.6-A3B; 11.848); +5.7 → +5.8 (5.75); CI [+2.3,+9.7] kept
  (notebook canonical; audit's [+2.2,+9.5] is its own bootstrap draw).
- App. R: cascade statistic defined (5 turns after minus 5 turns before each event, averaged).
- Table A4 caption: 10 games / 121 plays with Tier-2-removed partner labelled by remaining
  player's skill for both seats (verified: 11 single-player games, 10 of them Tier-2 cases).
- Table A11: "Other (0 hints, P≤0.5)" row 0.6/0.4/0.6/0.1 (3/3/5/2 failures; all 20 existing
  cells re-reproduced with the desperate-first priority rule).
- §4.3: "almost exclusively" → "predominantly" (71.9%).
- Table 2 and Table A7 → \footnotesize (overfull 30 pt / 18 pt removed).
- Fig. A6 caption: "95% confidence intervals" → "±1 SD across games" (code plots yerr=std;
  pre-existing caption error found on render check, not in audit list).
- §4.1, App. G: AUCs labelled "in-sample".
- App. A: 1,500 fetched → 25 non-replayable (21 bottom-deck-play option, 4 unsupported action
  type; verified by direct replay) → 1,475.

Not changed: Fig. 1 (binning stays linspace/right-closed; text true under both binnings).
Pending code-side round 2: Fig. A8(b) text-colour rule inverted (Flawed cells invisible);
bundle README worked example; pair_type/individual_skill columns; README note on 25 games.

## v10 round 2 (audit item 16 + A7-5 + A6-1, 2026-09-07) — code side

- **Fig A8(b) label colour**: `< 12 → white` was inverted for the Greys
  colormap (low score = white cell), leaving the Flawed row/column labels
  white-on-white. Now `> 12.5 → white`; all 49 cells legible; panel (a)
  values unchanged. Same fix in crossplay_score_heatmap.png.
- **Package README worked example (A7-5)**: "green at 2" → "green at 0" in
  the standalone package repo `hanabi-convention-gap/README.md` (the only
  copy anywhere — neither the bundle README nor the release REPRODUCING.md
  carries the example). With green at 0 both G2s are hidden and unplayable:
  P = (2+2)/(1+2+2) = 0.8 as printed. Verified against the engine
  (marginal = joint = 0.8, constrained-others 0; second scenario joint 1.0
  vs marginal 0.8) and added as tests/test_readme_example.py in the package
  repo (+ test_pkg_readme_example.py in the release repo).
- **human_play_records.csv skill columns (A6-1)**: `individual_skill` /
  `pair_type` regenerated from the post-exclusion 425-game corpus
  (previously computed over all 1,431 games); rows outside the corpus now
  carry empty values; all other columns verified field-for-field identical,
  row order preserved. `skill_level` deliberately untouched (byte-identical
  rule) — it retains the legacy pre-exclusion labels; README notes this.
  Single-remaining-player games: **11**, not 10 — the 10 Tier-2 partner
  removals plus game 1762152 (Tier-1 clue-only bot, the documented boundary
  case); all 11 pair labels duplicate the remaining player's skill. Table A4
  reproduced from the regenerated columns + joint swap: E-E +29.1 (3,268),
  E-I +25.2 (194), I-I +25.4 (3,708), I-B +27.2 (279), B-B +21.1 (1,499) —
  all exact.
- **README notes**: 1,500 fetched → 25 unreplayable (21 bottom-deck-play,
  4 unsupported action type) → 1,475 replayable; Fig A6 error bars are
  ±1 SD across games, not CIs. Same notes in release REPRODUCING.md.
