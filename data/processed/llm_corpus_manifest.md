# LLM corpus manifest (Appendix: LLM partners)

## Corpus definition

The LLM-vs-rule-agent corpus contains **1,861 games / 19,093 play records**
across **39 conditions** (3 LLM models × partner × chain-of-thought variants).
The corpus is the complete generation snapshot of 2026-04-24: every game that
had finished generating when the analysis snapshot was taken. **No quality
filter was applied** — three conditions are simply shorter prefixes of the
fixed seed schedule because their runs terminated early (compute budget):

| Condition | Games (seeds) |
|---|---|
| all 36 regular conditions | 50 (seeds 0–49) |
| GPT-5.4-mini+CoT × Intentional † | 45 (seeds 0–44) |
| Qwen3.6-A3B+CoT × IGGI † | 8 (seeds 0–7) |
| Qwen3.6-A3B+CoT × Intentional † | 8 (seeds 0–7) |

36×50 + 45 + 8 + 8 = 1,861. Four further Qwen3.6-A3B+CoT conditions
(× Flawed / Internal / Outer / Piers) had not been generated at snapshot
time and are not part of the corpus. †-flags match the paper's tables.

## Verification chain

- Replaying the raw logs restricted to this rule reproduces the original
  analysis records **exactly** (all 19,093 records, every field, in order;
  0 replay-vs-recorded score mismatches).
- `src/llm_joint_replay.py` recomputes the per-card posterior and requires
  float-exact agreement with the shipped `llm_cg_records.json` on every
  record before computing the joint posterior; 96 brute-force enumeration
  spot-checks of the joint dynamic program, maximum discrepancy 0.

## Fallback-action audit

The generation harness replaced LLM outputs that failed to parse with a
fallback **discard** action: 548 of 52,686 LLM actions (1.0%), concentrated
in the Qwen3.6-A3B no-CoT conditions (up to 97 per condition; per-condition
counts in `llm_fallback_counts.json`). **No play action was ever
fallback-substituted** — all 9,542 LLM play records carry `parse_ok = true` —
so restricting to parse-clean plays changes no value in the paper.

## Format notes (for regeneration)

Raw logs are not shipped (they embed full prompts). To regenerate
`llm_joint_posteriors.csv`, point `HANABI_LLM_RAW` at a checkout of the raw
results tree and run `python -m src.llm_joint_replay`. The LLM log format
differs from hanab.live: colors R,B,G,W,Y = 0–4; hands given directly as card
strings; draws replace in place at the same hand index; roles resolved via
`strategy[p] == "evolve_agent"` (LLM side).
