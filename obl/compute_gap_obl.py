"""Compute the convention gap for exported OBL game data.

For each condition (game JSON file): verify replay, then report
n plays, mean joint posterior, actual life-loss rate, gap, cluster
bootstrap CI, and the 0/1/2+ hint stratification.
"""
import glob
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, "$OBL_ROOT/hanabi-convention-gap")

from convention_gap import (
    process_games,
    convention_gap,
    gap_by_hint_count,
    cluster_bootstrap_gap_ci,
    replay_and_extract,
)

SP = "/tmp/claude-1002/-home-makotof-research-Hanabi-offbelief-learning/2f15f1ab-92f8-42b0-8e7d-65de0f3c304a/scratchpad"


def analyze(name, games):
    # Hard verification: replayed score must equal HLE score on every game
    n_bad = 0
    for g in games:
        _, state = replay_and_extract(g)
        reason = state.get_game_end_reason(hit_terminate_marker=False)
        cg_score = 0 if reason == "strikeout" else state.get_final_score()
        # HLE ends the game the moment the score reaches 25; the replay
        # engine only flags game_over via strikeout/countdown, so a
        # perfect game legitimately ends by exhausting the action list.
        if cg_score != g["hle_score"] or not (state.game_over or reason == "perfect"):
            n_bad += 1
    assert n_bad == 0, f"{name}: {n_bad} replay mismatches"

    records = process_games(
        games,
        data_source="obl_selfplay",
        subject_type="agent",
        partner_type="agent",
        game_key_prefix=name,
    )
    agg = convention_gap(records)
    lo, hi = cluster_bootstrap_gap_ci(records)
    strata = gap_by_hint_count(records)

    print(f"\n=== {name} ===  ({len(games)} games, replay-verified)")
    print(
        f"  plays={agg['n']}  mean_posterior={agg['mean_posterior']:.4f}  "
        f"loss_rate={agg['loss_rate']:.4f}"
    )
    print(f"  GAP = {agg['gap']*100:+.2f} pp   (95% cluster-bootstrap CI: "
          f"[{lo*100:+.2f}, {hi*100:+.2f}] pp)")
    for k in sorted(strata.keys(), key=str):
        s = strata[k]
        print(
            f"    hints={k}: n={s['n']}  mean_post={s['mean_posterior']:.4f}  "
            f"loss={s['loss_rate']:.4f}  gap={s['gap']*100:+.2f} pp"
        )
    return name, agg, (lo, hi), strata


def main():
    results = []

    # Self-play conditions
    for L in ["OBL1", "OBL2", "OBL3", "OBL4", "OBL5"]:
        path = os.path.join(SP, "games", f"{L}_selfplay.json")
        games = json.load(open(path))
        results.append(analyze(f"{L}_selfplay", games))

    # Cross-play: pool the 10 pair files into one condition
    cross_games = []
    for p in sorted(glob.glob(os.path.join(SP, "games", "OBL1_cross_*.json"))):
        cross_games.extend(json.load(open(p)))
    results.append(analyze("OBL1_crossplay(10 pairs)", cross_games))

    # Summary table
    print("\n\n===================== SUMMARY =====================")
    print(f"{'condition':<26} {'plays':>6} {'mean_post':>9} {'loss':>7} "
          f"{'gap(pp)':>8} {'95% CI(pp)':>18}")
    for name, agg, (lo, hi), _ in results:
        print(
            f"{name:<26} {agg['n']:>6} {agg['mean_posterior']:>9.4f} "
            f"{agg['loss_rate']:>7.4f} {agg['gap']*100:>+8.2f} "
            f"[{lo*100:+.2f}, {hi*100:+.2f}]"
        )

    with open(os.path.join(SP, "gap_results.json"), "w") as f:
        json.dump(
            [
                {
                    "condition": name,
                    **agg,
                    "ci95": [lo, hi],
                    "by_hints": {str(k): v for k, v in strata.items()},
                }
                for name, agg, (lo, hi), strata in results
            ],
            f,
            indent=2,
        )


if __name__ == "__main__":
    main()
